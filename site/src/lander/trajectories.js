// Recorded descents (lunarsim-trajectories v1, B-33: data/policies/trajectories-v1.json) as functions of time, for the
// 3D lander view and the effects demo. No three.js here, so Node tests can import it.
// Frames: the file's pad frame is x, y horizontal, z up (altitude above the local ground plane); the scene is
// x east, y up, z south, so a pad-frame point (x, y, z) is the scene point (x, z, -y) and a quaternion [w, x, y, z]
// is the scene quaternion (x, z, -y, w). Rows: positions and velocities at 10 Hz (t = 0.1 i) plus the touchdown instant;
// per 0.2 s guidance step k (covering [0.2 k, 0.2 (k + 1)]): throttle, thrust direction, attitude, propellant, the
// altimeter reading the pilot saw and the reward terms.
export const STEP_S = 0.2;

// how the lab names the pilots in the file (pilot id -> kind and plain label)
export function pilotKind(p) {
  if (p.pilot === 'classical') return { kind: 'classical', label: 'Classical guidance law' };
  if (p.pilot === 'memoryless') return { kind: 'memoryless', label: 'Classical law, no altimeter memory' };
  if (/hover_bonus/.test(p.pilot)) return { kind: 'hover', label: 'Hover hack (network paid to hover)' };
  if (/_baseline_/.test(p.pilot)) return { kind: 'ppo', label: 'Network trained by trial and error (PPO)' };
  return { kind: 'network', label: 'Network (imitation of the classical law)' };
}
export const PILOT_ORDER = ['network', 'classical', 'memoryless', 'ppo', 'hover'];
export const PICKS = { p10: 'Close landing (10th percentile miss)', p50: 'Typical landing (median miss)', p90: 'Wide landing (90th percentile miss)', first_failure: 'First failure' };

export async function loadTrajectories(url, { fetchFn = fetch } = {}) {
  const r = await fetchFn(url);
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  const doc = await r.json();
  if (doc.format !== 'lunarsim-trajectories' || doc.version !== 1) throw new Error('not a lunarsim-trajectories v1 file');
  return doc;
}

// pilots flown for a class, in the lab's order
export const pilotsFor = (doc, cls) => doc.pilots.filter(p => p.cls === cls)
  .map(p => ({ ...p, ...pilotKind(p) })).sort((a, b) => PILOT_ORDER.indexOf(a.kind) - PILOT_ORDER.indexOf(b.kind));

/* episodeView(ep) -> functions of time t (s) for one recorded episode; positions in the pad frame */
export function episodeView(ep) {
  const n = ep.n_samples, ns = ep.n_steps, tEnd = ep.t_end_s, rw = ep.reward;
  const tAt = i => (i < n - 1 ? 0.1 * i : tEnd);
  const clampT = t => Math.max(0, Math.min(tEnd, t));
  function sample(arr, t) {
    t = clampT(t);
    let i = Math.min(n - 2, Math.floor(t / 0.1 + 1e-9)); if (tAt(i + 1) < t) i = n - 2;
    const a = arr[i], b = arr[i + 1], f = (t - tAt(i)) / Math.max(1e-9, tAt(i + 1) - tAt(i));
    return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
  }
  const step = t => Math.max(0, Math.min(ns - 1, Math.floor(t / STEP_S)));
  // completed steps at time t; the last (touchdown) step completes at touchdown, mid-step
  const done = t => (t >= tEnd ? ns : Math.max(0, Math.min(ns, Math.floor(t / STEP_S + 1e-9))));
  // cumulative score after each completed step: sum of the terms plus eta per step (the file's definition)
  const cum = new Float64Array(ns + 1);
  for (let k = 0; k < ns; k++) cum[k + 1] = cum[k] + rw.track[k] + rw.effort[k] + rw.low_alt[k] + rw.terminal[k] + rw.eta_per_step;
  // altimeter dropouts: the env repeats the last reading when the altimeter drops out
  const dropout = Uint8Array.from({ length: ns }, (_, k) => (k > 0 && ep.alt_meas_m[k] === ep.alt_meas_m[k - 1] ? 1 : 0));
  const firstBelow = h => { for (let i = 0; i < n; i++) if (ep.pos_m[i][2] <= h) return tAt(i); return tEnd; };
  return {
    ep, tEnd, nSteps: ns, seed: ep.seed, pick: ep.pick, outcome: ep.outcome, miss: ep.miss_m,
    pos: t => sample(ep.pos_m, t), vel: t => sample(ep.vel_mps, t),
    // scene position of the pad-frame point (x, y, z): (x, z, -y)
    toScene: ([x, y, z]) => [x, z, -y],
    throttle: t => (t >= tEnd ? 0 : ep.throttle[step(t)]),
    dir: t => ep.thrust_dir[step(Math.min(t, tEnd - 1e-6))],
    quatScene: t => { const [w, x, y, z] = ep.quat_wxyz[step(Math.min(t, tEnd - 1e-6))]; return [x, z, -y, w]; },
    prop: t => ep.prop_kg[step(t)],
    altMeas: t => ep.alt_meas_m[step(t)], dropout: t => !!dropout[step(t)], dropouts: dropout,
    // score so far: completed steps only, so it ticks every 0.2 s like the env
    score: t => cum[done(t)],
    scoreFinal: cum[ns],
    terms(t) {
      const k = done(t), s = { track: 0, effort: 0, low_alt: 0, terminal: 0, eta: rw.eta_per_step * k };
      for (let j = 0; j < k; j++) for (const key of ['track', 'effort', 'low_alt', 'terminal']) s[key] += rw[key][j];
      return s;
    },
    // phase boundaries: Approach until 20 m up, Hover until 3 m, then Touchdown (5 m above the 15 m hover point; legs)
    phases: { approach: 0, hover: firstBelow(20), touchdown: firstBelow(3) },
    phaseAt(t) { return t >= this.phases.touchdown ? 'touchdown' : t >= this.phases.hover ? 'hover' : 'approach'; },
  };
}
