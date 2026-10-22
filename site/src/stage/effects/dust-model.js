// Landing dust as numbers (no three.js, so Node can test it; dust.js draws it). Research §1.4:
//  - particles leave the surface on ballistic paths, p(t) = p0 + v t + ½ g t², g = 1.62 m/s², no drag (no air);
//  - launch angle 1–3° above the horizontal (Measured: Apollo descent-video photogrammetry, Immer et al., NTRS
//    20130012063); azimuths bunch into streaks (the Görtler vortices in landing footage, JHU 2025), 70 % of particles;
//  - erosion starts when the nozzle is below an onset height that grows with thrust: 15 m for the CLPS class
//    (Measured: Blue Ghost SCALPSS, NASA 2025); other classes h_on = 15 m × √(T / 5 kN) (Assumed: a free jet's pressure
//    on the ground falls as T / h² and erosion starts at a fixed pressure; this gives ~45 m for a 44 kN lander, the
//    order Apollo crews reported);
//  - reach: ranges log-uniform between 2 % and 100 % of the scenario's keep-out radius, so the sheet's edge is the
//    keep-out ring the simulator plans with (Modelled);
//  - the obscuration layer follows the emission rate over the last 0.6 s and is zero from engine cut-off on (no air to
//    hold dust up); the scour mark grows with the dust thrown so far.
// Everything is drawn from the seed: the same seed and timeline give the same particles, frame by frame.
import { hash01, mulberry32 } from './rng.js';

export const G_MOON = 1.62;
export const LAUNCH_DEG = [1, 3];
export const ONSET_REF = { thrustN: 5000, heightM: 15 };
export const ONSET_SOURCES = {
  measured: 'Blue Ghost M1 SCALPSS: thruster plumes start acting on the surface at ~15 m (NASA, March 2025)',
  assumed: 'scaled from the CLPS value as √thrust (free-jet ground pressure ∝ T / h²); design_research §1.4',
};
const STREAKS = 40, STREAK_SHARE = 0.7, STREAK_HALF_DEG = 1.2, RANGE_MIN_FRAC = 0.02, OBSCURE_WINDOW_S = 0.6;

// onset height (m) of surface erosion under a thrust T (N)
export const onsetHeight = thrustN => ONSET_REF.heightM * Math.sqrt(Math.max(0, thrustN) / ONSET_REF.thrustN);

// linear interpolation in a sorted time series
function sampler(t) {
  const n = t.length;
  return (arr, x) => {
    if (x <= t[0]) return arr[0];
    if (x >= t[n - 1]) return arr[n - 1];
    let lo = 0, hi = n - 1;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (t[m] <= x) lo = m; else hi = m; }
    const f = (x - t[lo]) / (t[hi] - t[lo]);
    return arr[lo] + (arr[hi] - arr[lo]) * f;
  };
}

/* buildLandingDust({timeline, cutoff, keepoutM, seed, n})
   timeline: arrays over time: t (s), h (nozzle exit height above the ground, m), thrust (N), gx, gy, gz (the ground
   point under the nozzle, scene metres, y up). cutoff: engine cut-off (s). n: particle count (the largest tier's; a
   tier draws the first n of them, a uniform subsample because birth slots are shuffled).
   Returns typed arrays (birth, origin xyz, vel xyz, life, size) and functions of time. */
export function buildLandingDust({ timeline, cutoff, keepoutM = 1000, seed = 1, n = 30000 }) {
  const T = timeline.t, at = sampler(T), m = T.length;
  const raw = new Float64Array(m), rate = new Float64Array(m);
  for (let i = 0; i < m; i++) {
    const on = onsetHeight(timeline.thrust[i]), x = on > 0 ? timeline.h[i] / on : 1;
    raw[i] = timeline.thrust[i] * Math.pow(Math.max(0, 1 - x), 1.5);
    rate[i] = T[i] > cutoff ? 0 : raw[i];
  }
  // cumulative emission, each segment clipped at the cut-off
  const cum = new Float64Array(m); let peak = 0;
  for (let i = 1; i < m; i++) {
    const a = T[i - 1], b = T[i], e = Math.min(b, cutoff);
    const re = raw[i - 1] + (raw[i] - raw[i - 1]) * (b > a ? (e - a) / (b - a) : 0);
    cum[i] = cum[i - 1] + (a >= cutoff ? 0 : 0.5 * (raw[i - 1] + re) * (e - a));
  }
  for (let i = 0; i < m; i++) peak = Math.max(peak, rate[i]);
  const total = cum[m - 1];

  // stratified birth times by inverse CDF, then shuffled so any prefix is a uniform subsample
  const slots = new Float64Array(n);
  let j = 0;
  for (let k = 0; k < n; k++) {
    const u = total * (k + hash01(seed, k, 0)) / n;
    while (j < m - 2 && cum[j + 1] < u) j++;
    const span = cum[j + 1] - cum[j];
    slots[k] = total > 0 ? Math.min(cutoff, T[j] + (span > 0 ? (u - cum[j]) / span : 0) * (T[j + 1] - T[j])) : -1e9;
  }
  const rnd = mulberry32(seed ^ 0x5bd1e995);
  for (let k = n - 1; k > 0; k--) { const r = Math.floor(rnd() * (k + 1)), s = slots[k]; slots[k] = slots[r]; slots[r] = s; }

  const streakAz = Array.from({ length: STREAKS }, (_, s) => hash01(seed, s, 99) * 2 * Math.PI);
  const birth = new Float32Array(n), origin = new Float32Array(3 * n), vel = new Float32Array(3 * n), life = new Float32Array(n), size = new Float32Array(n);
  const D = Math.PI / 180;
  for (let i = 0; i < n; i++) {
    const tb = slots[i]; birth[i] = tb;
    const az = hash01(seed, i, 1) < STREAK_SHARE
      ? streakAz[Math.floor(hash01(seed, i, 2) * STREAKS)] + (hash01(seed, i, 3) - 0.5) * 2 * STREAK_HALF_DEG * D
      : hash01(seed, i, 2) * 2 * Math.PI;
    const th = (LAUNCH_DEG[0] + (LAUNCH_DEG[1] - LAUNCH_DEG[0]) * hash01(seed, i, 4)) * D;
    const range = keepoutM * Math.exp(Math.log(RANGE_MIN_FRAC) * hash01(seed, i, 5));
    const v = Math.sqrt(range * G_MOON / Math.sin(2 * th));
    const h = Math.max(0, at(timeline.h, tb)), r0 = (0.5 + 0.6 * h) * Math.sqrt(hash01(seed, i, 6));
    const c = Math.cos(az), s = Math.sin(az);
    origin[3 * i] = at(timeline.gx, tb) + r0 * c; origin[3 * i + 1] = at(timeline.gy, tb); origin[3 * i + 2] = at(timeline.gz, tb) + r0 * s;
    vel[3 * i] = v * Math.cos(th) * c; vel[3 * i + 1] = v * Math.sin(th); vel[3 * i + 2] = v * Math.cos(th) * s;
    life[i] = 2 * v * Math.sin(th) / G_MOON;
    size[i] = 0.5 + hash01(seed, i, 7);
  }

  const rateAt = x => (x > cutoff ? 0 : at(rate, x));
  return {
    n, seed, keepoutM, cutoff, birth, origin, vel, life, size, peakRate: peak,
    // 0..1: the emission rate relative to its peak
    emission: x => (peak > 0 ? rateAt(x) / peak : 0),
    // 0..1: the ground-hugging layer; mean emission over the last 0.6 s, zero from cut-off on
    obscuration(x) {
      if (x >= cutoff || peak <= 0) return 0;
      const a = Math.max(T[0], x - OBSCURE_WINDOW_S);
      if (x <= a) return 0;
      return Math.min(1, (at(cum, x) - at(cum, a)) / (x - a) / peak);
    },
    // 0..1: share of the landing's dust thrown up to time x (the scour mark's strength)
    scour: x => (total > 0 ? Math.min(1, at(cum, Math.min(x, cutoff)) / total) : 0),
    // particle i's position at time x into out[0..2]; false when it is not in flight
    positionAt(i, x, out) {
      const a = x - birth[i];
      if (a < 0 || a > life[i]) return false;
      out[0] = origin[3 * i] + vel[3 * i] * a;
      out[1] = origin[3 * i + 1] + vel[3 * i + 1] * a - 0.5 * G_MOON * a * a;
      out[2] = origin[3 * i + 2] + vel[3 * i + 2] * a;
      return true;
    },
    alive(x, count = n) { let k = 0; for (let i = 0; i < count; i++) { const a = x - birth[i]; if (a >= 0 && a <= life[i]) k++; } return k; },
  };
}
