// Port of classical_action() in lunarsim/lander/evaluate.py: ZEM/ZEV feedback guidance to a point 10 m above the
// target at -1 m/s, then a vertical terminal phase holding -1 m/s with horizontal PD nulling (SPLICE terminal
// profile). Uses the env's *estimated* state, as the policy does. Gains are Assumed (as in Python).
import * as P from './physics.js';
import { G_MOON } from './classes.js';

export const ZEM_AIM_ALT_M = 10.0, ZEM_AIM_VZ = -1.0, TERM_VZ = -1.0, K_VZ = 1.0, K_PH = 0.05, K_VH = 0.6, EST_ALPHA = 0.3, CMD_ALPHA = 0.25, HOLD_ALT_M = 3.0;
const RAD = Math.PI / 180;

export function classicalAction(env) {
  const [pos, velEst] = env.lastEst, s = env.state, c = env.cls;
  if (env.steps === 0 || !env._cl) env._cl = { vel: [...velEst], u: null };
  const mem = env._cl;
  mem.vel = mem.vel.map((v, i) => (1 - EST_ALPHA) * v + EST_ALPHA * velEst[i]);
  const vel = mem.vel, m = s[P.M], g = [0.0, 0.0, -G_MOON], h = pos[2], terminal = h <= ZEM_AIM_ALT_M + 5.0;
  let a;
  if (!terminal) {
    const rf = [0.0, 0.0, ZEM_AIM_ALT_M], vf = [0.0, 0.0, ZEM_AIM_VZ];
    const tgo = Math.max(3.0, 2.0 * (h - ZEM_AIM_ALT_M) / (Math.max(-vel[2], 0.5) + Math.abs(ZEM_AIM_VZ)));
    const zem = [0, 1, 2].map(i => rf[i] - (pos[i] + vel[i] * tgo + 0.5 * g[i] * tgo * tgo));
    const zev = [0, 1, 2].map(i => vf[i] - (vel[i] + g[i] * tgo));
    a = [0, 1, 2].map(i => 6.0 * zem[i] / (tgo * tgo) - 2.0 * zev[i] / tgo);
  } else a = [-K_PH * pos[0] - K_VH * vel[0], -K_PH * pos[1] - K_VH * vel[1], G_MOON + K_VZ * (TERM_VZ - vel[2])];
  const F = a.map(x => m * x); F[2] = Math.max(F[2], 1e-3 * m);   // the engine cannot push down
  const tmax = c.tilt_max_deg * RAD, fh = Math.hypot(F[0], F[1]);
  if (fh > F[2] * Math.tan(tmax)) { const k = F[2] * Math.tan(tmax) / fh; F[0] *= k; F[1] *= k; }   // keep the vertical component
  const T = Math.hypot(F[0], F[1], F[2]); let u = F.map(x => x / T);
  if (terminal && mem.u !== null) {
    if (h < HOLD_ALT_M) u = mem.u;
    else { u = u.map((x, i) => (1 - CMD_ALPHA) * mem.u[i] + CMD_ALPHA * x); const L = Math.hypot(u[0], u[1], u[2]); u = u.map(x => x / L); }
  }
  mem.u = u;
  const [tx, ty] = P.anglesFromDirection(u[0], u[1], u[2]), wmax = c.tilt_rate_max_dps * RAD;
  const rx = Math.max(-1.0, Math.min(1.0, (tx - s[P.TX]) / (env.dt * wmax))), ry = Math.max(-1.0, Math.min(1.0, (ty - s[P.TY]) / (env.dt * wmax)));
  return Float32Array.from([P.thrustToThrottle(T, c), rx, ry]);   // float32 like the Python controller
}
