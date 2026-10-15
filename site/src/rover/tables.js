// Port of the deterministic parts of lunarsim/rover/tables.py (leg_profile, drive_profile): the fast leg integrator
// the driving tables are built with. Its random parts (lognormal speed factor u_leg, Poisson interventions) are not
// re-drawn here: the page shows them from driving-v1.json and this module gives t_move, stops, energy and lambda.
import * as R from './physics.js';
import { densify } from './expert.js';

export const SPEED_SIGMA = 0.10;
export const HAZARD_PER_KM = { teleop: 0.05, supervised: 0.10, autonomous: 0.20 };
export const HAZARD_SLOPE_PER_KM = 1.0, HAZARD_ROUGH_PER_KM = 1.0, HAZARD_SHADOW_MULT = 2.0;
const pmod = (a, b) => { const m = a % b; return (m !== 0 && (m < 0) !== (b < 0)) ? m + b : m; };

export function legProfile(t, route, sunAz) {
  const p = densify(route, 5.0), n = p.length - 1, ds = new Float64Array(n), grade = new Float64Array(n), heading = new Float64Array(n), slope = new Float64Array(n), shadow = new Uint8Array(n), rough = new Float64Array(n);
  const z = p.map(q => t.height(q[0], q[1])), sh = sunAz === null || sunAz === undefined || sunAz === R.NIGHT ? null : t.shadowGrid(+sunAz), rg = t.roughness20();
  let length = 0;
  for (let k = 0; k < n; k++) {
    const dx = p[k + 1][0] - p[k][0], dy = p[k + 1][1] - p[k][1], mx = 0.5 * (p[k + 1][0] + p[k][0]), my = 0.5 * (p[k + 1][1] + p[k][1]);
    ds[k] = Math.hypot(dx, dy); length += ds[k];
    grade[k] = Math.atan2(z[k + 1] - z[k], Math.max(ds[k], 1e-9)) * 180 / Math.PI;
    heading[k] = pmod(Math.atan2(dx, dy) * 180 / Math.PI, 360);
    slope[k] = t.slope(mx, my);
    const [j, i] = t.cell(mx, my);
    shadow[k] = sunAz === R.NIGHT ? 1 : sh ? sh[j * t.c20 + i] : 0;
    rough[k] = rg[j * t.c20 + i];
  }
  return { p, z, ds, grade, heading, slope, shadow, rough, length_m: length };
}

/* deterministic leg result: t_move_s (before u_leg), stops, stop seconds, energy_wh, lambda */
export function driveProfile(prof, autonomy, rtt, sunAz) {
  const cap = R.speedCapMps(autonomy, rtt); let tDet = 0, e = 0, lam = 0, blockedN = 0;
  for (let k = 0; k < prof.ds.length; k++) {
    const sl = R.slip(prof.grade[k]), f = R.slopeSpeedFactor(prof.slope[k]) * R.lightingFactor(prof.heading[k], sunAz, !!prof.shadow[k]);
    const v = cap * f * (1.0 - sl), blocked = v <= 0 || sl >= R.DIG_IN_SLIP;
    if (blocked) blockedN++; else tDet += prof.ds[k] / v;
    e += R.energyWh(prof.ds[k], prof.grade[k], Math.min(sl, 0.95));
    let haz = HAZARD_PER_KM[autonomy] + HAZARD_SLOPE_PER_KM * (prof.slope[k] > R.ROVER.slope_nominal_deg ? 1 : 0) + HAZARD_ROUGH_PER_KM * (prof.rough[k] > 0.5 * R.INTERVENTION.roughness_m ? 1 : 0);
    haz *= prof.shadow[k] ? HAZARD_SHADOW_MULT : 1.0; lam += haz * prof.ds[k] / 1000.0;
  }
  lam += blockedN;
  const [every, stopS] = R.stopPlan(autonomy, rtt), stops = Number.isFinite(every) ? Math.floor(prof.length_m / every) : 0;
  return { t_move_s: tDet, stops, stop_s: stopS, time_s_nominal: tDet + stops * stopS, energy_wh: e, lambda: lam, length_m: prof.length_m };
}
