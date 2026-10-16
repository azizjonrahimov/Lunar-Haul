// Port of lunarsim/lander/env.py (lunar/Descent-v0) without Gymnasium: episode setup with dispersion and domain
// randomisation, the sensor model, the 15-float observation, the touchdown classification and the rewards.
// Randomness: numpy's generator cannot be reproduced here, so episodes draw from the same distributions with a
// seeded JS generator (sfc32 + Box-Muller). With randomize=false and sensor=false an episode uses no random
// numbers and must match Python step for step (the parity fixture).
import * as P from './physics.js';
import { CLASSES, G_MOON, GATE, TIPOVER_DEG, TOUCHDOWN } from './classes.js';

export const ENV_ID = 'lunar/Descent-v0', ENV_VERSION = 3;   // v2 (B-10b): kappa 50, crash -5, tracking x(1 + 3 max(0, 1 - z/30));
                                                             // v3 (B-10e): optional observation v3 (19 values); rewards as v2
export const DT_S = 0.2, MAX_STEPS = 750, LOST_RANGE_M = 3000.0;
export const DISP = { downrange_m: 25.0, crossrange_m: 25.0, altitude_m: 20.0, vh_mps: 2.0, vcross_mps: 1.0, vz_mps: 1.0, tilt0_deg: [10.0, 30.0] };
export const DR = { dry_mass: [0.95, 1.05], prop: [0.90, 1.10], thrust: [0.95, 1.05], isp: [0.97, 1.03], sensor_noise: [0.5, 2.0] };
export const SENSOR = { nav_bias_m: 1.5, nav_noise_m: 0.5, vel_noise_mps: 0.05, alt_noise_hi_m: 0.2, low_alt_m: 30.0, alt_bias_low_m: 1.0, alt_noise_low_m: 0.5, alt_dropout_p: 0.05 };
export const K_VH_DEG_PER_MPS = 3.0, K_VZ_DEG_PER_MPS = 1.0, SITE_SLOPE_DEG = [0.0, 5.0];
// reward tables by env version: a policy is scored with the rewards of the env_version it was trained on
const variants = base => ({ baseline: { ...base }, no_eta: { ...base, eta: 0.0, crash: 0.0 }, hover_bonus: { ...base, eta: 0.3 },
  fuel_heavy: { ...base, beta: -0.5 }, plume_aware: { ...base, low_time: -0.02, low_thrust: -0.1 } });
const BASE_V1 = { alpha: -0.05, beta: -0.05, delta: -0.05, zeta: -0.01, eta: 0.01, kappa: 10.0, lost: -10.0, crash: -1.0, low_time: 0.0, low_thrust: 0.0, near_gain: 0.0 };
const BASE_V2 = { ...BASE_V1, kappa: 50.0, crash: -5.0, near_gain: 3.0 };
export const REWARDS_BY_VERSION = { 1: variants(BASE_V1), 2: variants(BASE_V2), 3: variants(BASE_V2) };
export const REWARD_VARIANTS = REWARDS_BY_VERSION[ENV_VERSION];
export const VF = { v0_mps: 20.0, hover_alt_m: 15.0, tau_hi_s: 20.0, tau_lo_s: 100.0, vz_hi_mps: -2.0, vz_lo_mps: -1.0 };
export const OBS_NAMES = ['x', 'y', 'h', 'vx', 'vy', 'vz', 'ex', 'ey', 'ez', 'tx', 'ty', 'wx', 'wy', 'prop_frac', 'tw_max'];
// Observation v3 (B-10e): the 15 v2 values plus the altimeter's recent history, so a memoryless policy can tell a held
// (dropped-out) reading from a fresh one; scales 30 m, 2 s, 30 m, 30 m; offsets 0; no extra random draws.
export const OBS_NAMES_V3 = [...OBS_NAMES, 'h_last_valid', 'h_valid_age_s', 'h_prev1', 'h_prev2'];
export const OBS_VERSIONS = { 2: OBS_NAMES, 3: OBS_NAMES_V3 };
/* observation version from a policy card's obs.names (lunarsim.lander.env.obs_version_of) */
export function obsVersionOf(names) {
  for (const [v, n] of Object.entries(OBS_VERSIONS)) if (names.length === n.length && names.every((x, i) => x === n[i])) return +v;
  throw new Error(`unknown observation layout (${names.length} names)`);
}
/* lunarsim.lander.env.alt_history_step, line by line: hist = null at reset; features describe the state BEFORE this
   reading enters prev1/prev2. held = the altimeter repeated its last value because of a dropout. */
export function altHistoryStep(hist, h, held, tNow) {
  if (hist === null || hist === undefined) hist = { valid: h, valid_t: tNow, prev1: h, prev2: h };
  let valid, validT;
  if (!held) { valid = h; validT = tNow; } else { valid = hist.valid; validT = hist.valid_t; }
  const feats = [valid, tNow - validT, hist.prev1, hist.prev2];
  return [{ valid, valid_t: validT, prev1: h, prev2: hist.prev1 }, feats];
}
export const ACT_NAMES = ['throttle', 'tilt_rate_x_cmd', 'tilt_rate_y_cmd'];
const RAD = Math.PI / 180, DEG = 180 / Math.PI, clip = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const norm3 = (a, b, c) => Math.sqrt(a * a + b * b + c * c);

export function obsScale(cls, obsVersion = 2) { const tm = cls.tilt_max_deg * RAD, wm = cls.tilt_rate_max_dps * RAD, v2 = [500, 500, 500, 30, 30, 15, 10, 10, 10, tm, tm, wm, wm, 1, 3]; return obsVersion === 2 ? v2 : [...v2, 30, 2, 30, 30]; }

/* Gaudet-style velocity field towards a hover point 15 m above the target, then down at 1 m/s */
export function targetVelocity(pos, vel) {
  let r, off, tau;
  if (pos[2] > VF.hover_alt_m) { r = [pos[0], pos[1], pos[2] - VF.hover_alt_m]; off = VF.vz_hi_mps; tau = VF.tau_hi_s; }
  else { r = [pos[0], pos[1], pos[2]]; off = VF.vz_lo_mps; tau = VF.tau_lo_s; }
  const rn = norm3(r[0], r[1], r[2]);
  if (rn < 1e-6) return [0.0, 0.0, off];
  const tGo = rn / Math.max(norm3(vel[0], vel[1], vel[2] - off), 1e-3), k = -VF.v0_mps * (1.0 - Math.exp(-tGo / tau)) / rn;
  return [k * r[0], k * r[1], k * r[2] + off];
}

export function classify(td, slopeDeg, padRadiusM, sensorFault) {
  const vh = Math.hypot(td[P.VX], td[P.VY]), vz = td[P.VZ], tilt = P.tiltDeg(td[P.TX], td[P.TY]), rate = Math.hypot(td[P.WX], td[P.WY]) * DEG;
  const landed = slopeDeg + K_VH_DEG_PER_MPS * vh + K_VZ_DEG_PER_MPS * Math.max(0.0, Math.abs(vz) - TOUCHDOWN.vz_max_mps);
  const miss = Math.hypot(td[P.X], td[P.Y]);
  const velOk = Math.abs(vz) <= TOUCHDOWN.vz_max_mps && vh <= TOUCHDOWN.vh_max_mps, attOk = tilt <= TOUCHDOWN.tilt_max_deg && rate <= TOUCHDOWN.rate_max_dps;
  let kind = !velOk ? 'velocity' : (!attOk || landed > TIPOVER_DEG) ? 'tilt' : miss > padRadiusM ? 'offpad' : null;
  if ((kind === 'velocity' || kind === 'tilt') && sensorFault && Math.abs(vz) <= 2 * TOUCHDOWN.vz_max_mps) kind = 'sensor';
  return { miss_m: [td[P.X], td[P.Y]], v_td: [td[P.VX], td[P.VY], vz], tilt_deg: tilt, rate_dps: rate, landed_tilt_deg: landed, slope_deg: slopeDeg,
    touchdown_ok: velOk && attOk && landed <= TIPOVER_DEG, ok: kind === null, failure_kind: kind };
}

/* reward for one step from stored quantities (shared by step() and the re-scoring panel) */
export function stepReward(rw, rec) {
  const near = 1.0 + (rw.near_gain || 0) * Math.max(0.0, 1.0 - rec.z / SENSOR.low_alt_m);   // v2; 1 in v1
  let r = rw.alpha * near * rec.vErr + rw.beta * rec.tf + rw.eta;
  if (rec.z < SENSOR.low_alt_m) {
    r += rw.delta * Math.max(0.0, rec.tiltDeg - TOUCHDOWN.tilt_max_deg) / 6.0;
    r += rw.zeta * rec.rateDps;
    r += rw.low_time + (rec.z < 10.0 ? rw.low_thrust * rec.tf * rec.tf : 0);
  }
  if (rec.terminal === 'touchdown') {
    if (rec.out.touchdown_ok) r += rw.kappa * (0.5 + 0.5 * Math.exp(-Math.hypot(rec.out.miss_m[0], rec.out.miss_m[1]) / 10.0));
    else { const vh = Math.hypot(rec.out.v_td[0], rec.out.v_td[1]), vz = Math.abs(rec.out.v_td[2]); r += rw.crash * (Math.max(0.0, vz - TOUCHDOWN.vz_max_mps) + Math.max(0.0, vh - TOUCHDOWN.vh_max_mps)); }
  } else if (rec.terminal === 'lost') r += rw.lost;
  return r;
}

// sfc32 seeded generator with Box-Muller normals (different numbers from numpy; same distributions)
export function makeRng(seed) {
  let a = 0x9E3779B9 ^ seed, b = 0x243F6A88 ^ (seed * 7919), c = 0xB7E15162 ^ (seed * 104729), d = 1 + (seed >>> 0), spare = null;
  const next = () => { a >>>= 0; b >>>= 0; c >>>= 0; d >>>= 0; let t = (a + b) | 0; a = b ^ (b >>> 9); b = (c + (c << 3)) | 0; c = (c << 21) | (c >>> 11); d = (d + 1) | 0; t = (t + d) | 0; c = (c + t) | 0; return (t >>> 0) / 4294967296; };
  for (let i = 0; i < 20; i++) next();
  return { random: next, uniform: (lo, hi) => lo + (hi - lo) * next(),
    normal: (mu, sd) => { if (spare !== null) { const z = spare; spare = null; return mu + sd * z; } const u = 1 - next(), v = next(), r = Math.sqrt(-2 * Math.log(u)); spare = r * Math.sin(2 * Math.PI * v); return mu + sd * r * Math.cos(2 * Math.PI * v); } };
}

export class DescentEnv {
  constructor({ cls = 'CLPS', variant = 'baseline', envVersion = ENV_VERSION, randomize = true, sensor = true, padRadiusM = TOUCHDOWN.delivery_radius_m, siteSlopeDeg = SITE_SLOPE_DEG, maxSteps = MAX_STEPS, dt = DT_S, obsVersion = 2 } = {}) {
    if (!CLASSES[cls]) throw new Error(`unknown lander class ${cls}`);
    const table = REWARDS_BY_VERSION[envVersion]; if (!table) throw new Error(`unknown env version ${envVersion}`);
    if (!table[variant]) throw new Error(`unknown reward variant ${variant}`);
    Object.assign(this, { clsName: cls, cls: CLASSES[cls], variant, envVersion, rw: table[variant], randomize, sensorOn: sensor, padRadiusM, siteSlopeDeg, maxSteps, dt });
    if (!OBS_VERSIONS[obsVersion]) throw new Error(`obsVersion must be one of ${Object.keys(OBS_VERSIONS).join(', ')}`);
    this.obsVersion = obsVersion; this.scale = obsScale(this.cls, obsVersion); this.state = null;
  }
  reset(seed = 0) {
    const rng = this.rng = makeRng(seed), c = this.cls;
    const u = lh => this.randomize ? rng.uniform(lh[0], lh[1]) : 1.0, n = s => this.randomize ? rng.normal(0.0, s) : 0.0;
    this.mDry = c.m_dry_kg * u(DR.dry_mass); const prop = c.prop_gate_kg * u(DR.prop);
    this.thrustScale = u(DR.thrust); this.ispScale = u(DR.isp); this.noise = this.sensorOn ? u(DR.sensor_noise) : 0.0;
    const psi = this.randomize ? rng.uniform(0.0, 2 * Math.PI) : 0.0, e = [Math.cos(psi), Math.sin(psi)], nrm = [-e[1], e[0]];
    const gate = { ...GATE, ...c.gate_overrides };
    const down = gate.downrange_m + n(DISP.downrange_m), cross = n(DISP.crossrange_m);
    const posH = [-down * e[0] + cross * nrm[0], -down * e[1] + cross * nrm[1]];
    const z = gate.altitude_m + n(DISP.altitude_m);
    const vhm = gate.vh_mps + n(DISP.vh_mps), vc = n(DISP.vcross_mps), vH = [vhm * e[0] + vc * nrm[0], vhm * e[1] + vc * nrm[1]];
    const vz = gate.vz_mps + n(DISP.vz_mps);
    const tilt0 = (this.randomize ? rng.uniform(DISP.tilt0_deg[0], DISP.tilt0_deg[1]) : 20.0) * RAD;
    const [tx, ty] = P.anglesFromDirection(-Math.sin(tilt0) * e[0], -Math.sin(tilt0) * e[1], Math.cos(tilt0));
    this.state = P.makeState([posH[0], posH[1], z], [vH[0], vH[1], vz], this.mDry + prop, tx, ty);
    this.m0 = this.state[P.M]; this.approach = psi;
    this.slopeDeg = this.randomize ? rng.uniform(this.siteSlopeDeg[0], this.siteSlopeDeg[1]) : this.siteSlopeDeg[0];
    const s = this.noise;
    this.navBias = s ? [n(SENSOR.nav_bias_m * s), n(SENSOR.nav_bias_m * s)] : [0, 0];
    this.altBias = s ? n(SENSOR.alt_bias_low_m * s) : 0.0;
    this.altHold = null; this.dropoutsRecent = 0; this.lastAltErr = 0.0; this.steps = 0; this.tBelow30 = 0.0;
    this.hHist = null; this.hFeats = null;   // altimeter history (obs v3), see altHistoryStep
    this.thrustN = P.throttleToThrust(0.0, c, this.thrustScale);
    return this.obs();
  }
  measure() {
    const s = this.state, k = this.noise, rng = this.rng;
    const x = s[P.X] + this.navBias[0] + (k ? rng.normal(0, SENSOR.nav_noise_m * k) : 0.0);
    const y = s[P.Y] + this.navBias[1] + (k ? rng.normal(0, SENSOR.nav_noise_m * k) : 0.0);
    const v = k ? [s[P.VX] + rng.normal(0, SENSOR.vel_noise_mps * k), s[P.VY] + rng.normal(0, SENSOR.vel_noise_mps * k), s[P.VZ] + rng.normal(0, SENSOR.vel_noise_mps * k)] : [s[P.VX], s[P.VY], s[P.VZ]];
    const z = s[P.Z]; let h, held = false;
    if (!k) h = z;
    else if (z >= SENSOR.low_alt_m) { h = z + rng.normal(0, SENSOR.alt_noise_hi_m * k); this.altHold = h; }
    else if (this.altHold !== null && rng.random() < SENSOR.alt_dropout_p) { h = this.altHold; this.dropoutsRecent = 10; held = true; }
    else { h = z + this.altBias + rng.normal(0, SENSOR.alt_noise_low_m * k); this.altHold = h; }
    this.dropoutsRecent = Math.max(0, this.dropoutsRecent - 1); this.lastAltErr = h - z;
    [this.hHist, this.hFeats] = altHistoryStep(this.hHist, h, held, this.steps * this.dt);
    return [[x, y, h], v];
  }
  obs() {
    const [pos, vel] = this.measure(), vt = targetVelocity(pos, vel), s = this.state;
    const propFrac = Math.max(0.0, s[P.M] - this.mDry) / Math.max(this.cls.prop_gate_kg, 1e-9), tw = this.cls.t_max_n / (s[P.M] * G_MOON);
    const raw = [pos[0], pos[1], pos[2], vel[0], vel[1], vel[2], vel[0] - vt[0], vel[1] - vt[1], vel[2] - vt[2], s[P.TX], s[P.TY], s[P.WX], s[P.WY], propFrac, tw];
    if (this.obsVersion === 3) raw.push(...this.hFeats);
    this.lastEst = [pos, vel];
    return Float32Array.from(raw.map((r, i) => clip(r / this.scale[i], -10, 10)));   // float32, as Gymnasium returns it
  }
  /* step(action) -> {obs, reward, terminated, truncated, outcome, rec} ; rec keeps what the re-scoring panel needs */
  step(action) {
    const c = this.cls, prev = this.state, [next, thrust] = P.step(prev, action, c, this.dt, this.thrustScale, this.ispScale, this.mDry);
    this.thrustN = thrust; this.steps += 1;
    const z = next[P.Z];
    if ((0 < z && z < SENSOR.low_alt_m) || (z <= 0 && 0 < prev[P.Z] && prev[P.Z] < SENSOR.low_alt_m)) this.tBelow30 += this.dt;
    const tf = thrust / (c.t_max_n * this.thrustScale);
    const vt = targetVelocity([next[P.X], next[P.Y], next[P.Z]], [next[P.VX], next[P.VY], next[P.VZ]]);
    const rec = { z, tf, vErr: norm3(next[P.VX] - vt[0], next[P.VY] - vt[1], next[P.VZ] - vt[2]), tiltDeg: P.tiltDeg(next[P.TX], next[P.TY]), rateDps: Math.hypot(next[P.WX], next[P.WY]) * DEG, terminal: null, out: null };
    let terminated = false, truncated = false, outcome = null;
    if (z <= 0.0) {
      const td = P.touchdown(prev, next); this.state = td;
      const out = classify(td, this.slopeDeg, this.padRadiusM, this.noise > 0 && (Math.abs(this.lastAltErr) > 1.0 || this.dropoutsRecent > 0));
      rec.terminal = 'touchdown'; rec.out = out; terminated = true; outcome = this.finish(out);
      const reward = stepReward(this.rw, rec);
      return { obs: this.obs(), reward, terminated, truncated, outcome, rec, thrust };
    }
    this.state = next;
    if (Math.hypot(next[P.X], next[P.Y]) > LOST_RANGE_M || z > LOST_RANGE_M) { rec.terminal = 'lost'; terminated = true; outcome = this.finish(this.airborne('lost')); }
    else if (this.steps >= this.maxSteps) { truncated = true; outcome = this.finish(this.airborne('timeout')); }
    const reward = stepReward(this.rw, rec);
    return { obs: this.obs(), reward, terminated, truncated, outcome, rec, thrust };
  }
  airborne(kind) {
    const s = this.state;
    return { miss_m: [s[P.X], s[P.Y]], v_td: [s[P.VX], s[P.VY], s[P.VZ]], tilt_deg: P.tiltDeg(s[P.TX], s[P.TY]), rate_dps: Math.hypot(s[P.WX], s[P.WY]) * DEG,
      landed_tilt_deg: null, slope_deg: this.slopeDeg, touchdown_ok: false, ok: false, failure_kind: kind };
  }
  finish(out) { return { ...out, prop_used_kg: this.m0 - this.state[P.M], t_below_30m_s: this.tBelow30, t_flight_s: this.steps * this.dt, cls: this.clsName }; }
}
