// Line-by-line port of lunarsim/lander/physics.py: 3-DoF point-mass lander with a rate-limited thrust axis.
// State (Float64Array, 11): 0 x, 1 y, 2 z, 3 vx, 4 vy, 5 vz, 6 m, 7 tx, 8 ty, 9 wx, 10 wy. Pure; never mutates its input.
import { G_MOON, G0 } from './classes.js';

export const X = 0, Y = 1, Z = 2, VX = 3, VY = 4, VZ = 5, M = 6, TX = 7, TY = 8, WX = 9, WY = 10, STATE_SIZE = 11;
const RAD = Math.PI / 180, clip = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

export function makeState(pos, vel, m, tx = 0.0, ty = 0.0) {
  const s = new Float64Array(STATE_SIZE);
  s[X] = pos[0]; s[Y] = pos[1]; s[Z] = pos[2]; s[VX] = vel[0]; s[VY] = vel[1]; s[VZ] = vel[2]; s[M] = m; s[TX] = tx; s[TY] = ty;
  return s;
}
export const thrustDirection = (tx, ty) => [Math.sin(tx) * Math.cos(ty), Math.sin(ty), Math.cos(tx) * Math.cos(ty)];
export const tiltDeg = (tx, ty) => Math.acos(clip(Math.cos(tx) * Math.cos(ty), -1.0, 1.0)) / RAD;
export function anglesFromDirection(ux, uy, uz) { return [Math.atan2(ux, uz), Math.asin(clip(uy, -1.0, 1.0))]; }   // [tx, ty]
export function throttleToThrust(a0, cls, thrustScale = 1.0) { a0 = clip(a0, -1.0, 1.0); return thrustScale * (cls.t_min_n + 0.5 * (a0 + 1.0) * (cls.t_max_n - cls.t_min_n)); }
export function thrustToThrottle(tN, cls, thrustScale = 1.0) { return clip(2.0 * (tN / thrustScale - cls.t_min_n) / (cls.t_max_n - cls.t_min_n) - 1.0, -1.0, 1.0); }

/* step(state, action, cls, dt, thrustScale, ispScale, mDry) -> [newState, thrustN] */
export function step(state, action, cls, dt, thrustScale = 1.0, ispScale = 1.0, mDry = null) {
  const s = Float64Array.from(state);
  if (mDry === null || mDry === undefined) mDry = cls.m_dry_kg;
  const a0 = clip(+action[0], -1.0, 1.0), a1 = clip(+action[1], -1.0, 1.0), a2 = clip(+action[2], -1.0, 1.0);
  // slew the thrust axis at the commanded rate, angles limited to +-tilt_max
  const tiltMax = cls.tilt_max_deg * RAD, rateMax = cls.tilt_rate_max_dps * RAD;
  const txNew = clip(s[TX] + a1 * rateMax * dt, -tiltMax, tiltMax), tyNew = clip(s[TY] + a2 * rateMax * dt, -tiltMax, tiltMax);
  s[WX] = (txNew - s[TX]) / dt; s[WY] = (tyNew - s[TY]) / dt;
  s[TX] = txNew; s[TY] = tyNew;
  // thrust and mass flow
  let thrust = throttleToThrust(a0, cls, thrustScale), mdot = thrust / (cls.isp_s * ispScale * G0);
  const prop = s[M] - mDry;
  if (prop <= 0.0) { thrust = 0.0; mdot = 0.0; }
  else if (mdot * dt > prop) { thrust *= prop / (mdot * dt); mdot = prop / dt; }   // burn the last propellant for part of the step
  const [ux, uy, uz] = thrustDirection(s[TX], s[TY]);
  const ax = thrust * ux / s[M], ay = thrust * uy / s[M], az = thrust * uz / s[M] - G_MOON;
  s[X] += s[VX] * dt + 0.5 * ax * dt * dt;
  s[Y] += s[VY] * dt + 0.5 * ay * dt * dt;
  s[Z] += s[VZ] * dt + 0.5 * az * dt * dt;
  s[VX] += ax * dt; s[VY] += ay * dt; s[VZ] += az * dt;
  s[M] -= mdot * dt;
  return [s, thrust];
}

/* state at the instant z crosses 0 between two steps (linear interpolation of every component) */
export function touchdown(prev, next) {
  const z0 = prev[Z], z1 = next[Z], f = z0 === z1 ? 1.0 : clip(z0 / (z0 - z1), 0.0, 1.0);
  const s = new Float64Array(STATE_SIZE); for (let i = 0; i < STATE_SIZE; i++) s[i] = prev[i] + f * (next[i] - prev[i]);
  s[Z] = 0.0; s[WX] = next[WX]; s[WY] = next[WY];
  return s;
}
