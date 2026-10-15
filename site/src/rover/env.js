// Port of lunarsim/rover/env.py (lunar/Drive-v0) without Gymnasium, plus drive_expert(). Deterministic for a given
// route: the only randomness in Python is the random-route picker, which the lab does not use.
// Order of PurePursuit.closest() calls matters (it advances a monotone index), so it follows Python exactly.
import * as R from './physics.js';
import { PurePursuit, densify } from './expert.js';
import { pyMod } from './terrain.js';

export const ENV_ID = 'lunar/Drive-v0', ENV_VERSION = 1, DT_S = 1.0, PATCH = 32, PATCH_RES_M = 5.0, PATCH_BEHIND = 8;
export const SCALAR_NAMES = ['speed_frac', 'heading_err', 'dist_wp', 'sun_rel', 'shadow'];
const f32 = Math.fround, clip = (v, lo, hi) => Math.max(lo, Math.min(hi, v)), TWO_PI = 2 * Math.PI;

export class DriveEnv {
  constructor(terrain) { this.t = terrain; }
  /* reset({waypoints, autonomy, rttS, sunAz}) -> obs */
  reset({ waypoints, autonomy = 'autonomous', rttS = 4.0, sunAz = 0.0 }) {
    if (!R.AUTONOMY_LEVELS.includes(autonomy)) throw new Error(`unknown autonomy level ${autonomy}`);
    this.autonomy = autonomy; this.rtt = +rttS; this.sun = sunAz;
    this.route = waypoints.map(p => [+p[0], +p[1]]);
    this.pp = new PurePursuit(this.route);
    const p0 = this.route[0], p1 = this.route[1];
    this.state = { x: p0[0], y: p0[1], psi: pyMod(Math.atan2(p1[0] - p0[0], p1[1] - p0[1]), TWO_PI), v: 0.0, delta: 0.0 };
    this.shadow = this.sun === null || this.sun === undefined ? null : this.sun === R.NIGHT ? 'all' : this.t.shadowGrid(+this.sun);
    this.rough = this.t.roughness20();
    this.vCap0 = R.speedCapMps(this.autonomy, this.rtt);
    [this.everyM, this.stopS] = R.stopPlan(this.autonomy, this.rtt);
    const lag = this.autonomy === 'teleop' ? Math.round(this.rtt / DT_S) : 0;
    this.queue = Array.from({ length: lag }, () => [0, 0]);
    this.timeS = this.energyWh = this.distM = 0.0; this.sinceStop = 0.0; this.stops = this.interventions = 0; this.stallS = 0.0; this.steps = 0;
    const L = this.pp.s[this.pp.s.length - 1];
    this.maxSteps = Math.trunc(Math.min(50000, 10 + 6 * L / Math.max(this.vCap0 * 0.25, 0.05)));
    return this.obs();
  }
  inShadow(x, y) { if (this.shadow === null) return false; if (this.shadow === 'all') return true; const [j, i] = this.t.cell(x, y); return !!this.shadow[j * this.t.c20 + i]; }
  vCap(x, y, psi) { const heading = psi * 180 / Math.PI; let f = R.slopeSpeedFactor(this.t.slope(x, y)); f *= R.lightingFactor(heading, this.sun, this.inShadow(x, y)); return this.vCap0 * f; }
  obs() {
    const s = this.state, sp = Math.sin(s.psi), cp = Math.cos(s.psi), z0 = this.t.height(s.x, s.y);
    const patch = new Float32Array(3 * PATCH * PATCH), n = PATCH * PATCH, c20 = this.t.c20;
    for (let a = 0; a < PATCH; a++) {                 // rows: forward, from 8 cells behind
      const F = (a - PATCH_BEHIND) * PATCH_RES_M;
      for (let b = 0; b < PATCH; b++) {               // columns: left .. right
        const Lt = (b - PATCH / 2 + 0.5) * PATCH_RES_M, X = s.x + F * sp + Lt * cp, Y = s.y + F * cp - Lt * sp, k = a * PATCH + b, [j, i] = this.t.cell(X, Y);
        patch[k] = clip((this.t.height(X, Y) - z0) / 10.0, -10, 10); patch[n + k] = clip(this.t.slope(X, Y) / 20.0, -10, 10); patch[2 * n + k] = clip(this.rough[j * c20 + i] / 1.0, -10, 10);
      }
    }
    const k = this.pp.closest(s.x, s.y), tgt = this.pp.path[Math.min(this.pp.path.length - 1, k + Math.trunc(this.pp.lookahead))];
    const bearing = Math.atan2(tgt[0] - s.x, tgt[1] - s.y), herr = pyMod(bearing - s.psi + Math.PI, TWO_PI) - Math.PI;
    const e = this.route[this.route.length - 1], distWp = Math.hypot(e[0] - s.x, e[1] - s.y);
    const sunRel = (this.sun === null || this.sun === undefined || this.sun === R.NIGHT) ? 0.0 : (pyMod(+this.sun - s.psi * 180 / Math.PI + 180, 360) - 180) / 180.0;
    const cap = Math.max(this.vCap(s.x, s.y, s.psi), 1e-6);
    const scalars = Float32Array.from([s.v / cap, herr / Math.PI, Math.min(distWp / 100.0, 10.0), sunRel, this.inShadow(s.x, s.y) ? 1 : 0].map(v => clip(f32(v), -10, 10)));
    return { patch, scalars };
  }
  intervene() {
    this.interventions += 1; this.timeS += R.interventionCostS(this.rtt);
    const k = this.pp.closest(this.state.x, this.state.y), p = this.pp.path[k], q = this.pp.path[Math.min(this.pp.path.length - 1, k + 5)];
    const psi = (q[0] !== p[0] || q[1] !== p[1]) ? pyMod(Math.atan2(q[0] - p[0], q[1] - p[1]), TWO_PI) : this.state.psi;
    Object.assign(this.state, { x: p[0], y: p[1], psi, v: 0.0, delta: 0.0 }); this.stallS = 0.0;
  }
  /* step([steerRate, throttle]) -> {obs, reward, terminated, truncated, leg, rec} ; rec has what the telemetry shows */
  step(action) {
    let a = [clip(f32(action[0]), -1, 1), clip(f32(action[1]), -1, 1)];
    if (this.queue.length) { this.queue.push(a); a = this.queue.shift(); }   // teleop: the command acts RTT later
    let s = this.state;
    const cap = this.vCap(s.x, s.y, s.psi);
    s = R.step(s, a[0], a[1], cap, DT_S);
    const zA = this.t.height(s.x, s.y), zB = this.t.height(s.x + Math.sin(s.psi), s.y + Math.cos(s.psi));
    const grade = Math.atan(zB - zA) * 180 / Math.PI, sl = R.slip(grade), gv = s.v * (1.0 - sl);
    const before = this.pp.s[this.pp.closest(s.x, s.y)];
    s = R.advance(s, gv, DT_S); this.state = s;
    const ds = gv * DT_S; this.distM += ds; this.sinceStop += ds;
    const eStep = R.energyWh(ds, grade, sl); this.energyWh += eStep; this.timeS += DT_S; this.steps += 1;
    let stopped = false;
    if (this.sinceStop >= this.everyM) { this.timeS += this.stopS; this.stops += 1; this.sinceStop = 0.0; stopped = true; }
    this.stallS = (a[1] > 0.1 && gv < 0.05) || sl >= R.DIG_IN_SLIP ? this.stallS + DT_S : 0.0;
    const k = this.pp.closest(s.x, s.y), xte = Math.hypot(this.pp.path[k][0] - s.x, this.pp.path[k][1] - s.y), [j, i] = this.t.cell(s.x, s.y);
    let why = null;
    if (xte > R.INTERVENTION.corridor_m) why = 'left the corridor'; else if (this.t.slope(s.x, s.y) > R.INTERVENTION.slope_deg) why = 'slope above 20°';
    else if (this.stallS >= R.INTERVENTION.stall_s) why = 'stalled'; else if (this.rough[j * this.t.c20 + i] > R.INTERVENTION.roughness_m) why = 'rough ground';
    if (why) this.intervene();
    const progress = this.pp.s[this.pp.closest(this.state.x, this.state.y)] - before, reward = progress / 10.0 - 0.001;
    const reached = this.pp.done(this.state.x, this.state.y), truncated = !reached && this.steps >= this.maxSteps;
    const leg = reached || truncated ? { time_s: this.timeS, energy_wh: this.energyWh, interventions: this.interventions, distance_m: this.distM, stops: this.stops, reached, autonomy: this.autonomy, rtt_s: this.rtt, sun_az_deg: this.sun } : null;
    const rec = { action: a, cap, grade, slip: sl, gv, eStep, stopped, intervention: why, xte };
    return { obs: this.obs(), reward, terminated: reached, truncated, leg, rec };
  }
}

/* controller interface for the lab: {name, act(obs, env) -> [steerRate, throttle]}; the expert drives with its own
   PurePursuit on the route, exactly as drive_expert() in Python. B-13's ONNX driver will implement the same. */
export function expertController(route) {
  const pp = new PurePursuit(route);
  return { name: 'Scripted expert (A* + pure pursuit)', pp, act: (obs, env) => pp.action(env.state) };
}
export { densify };
