// The safety program of Lunar ATC in the browser (F-54): a line-by-line port of the Move half of
// lunarsim/atc/safety.py (B-78), one vehicle per call instead of numpy arrays. Same constants, same rule order, same
// fallback candidates (no acceleration, then full braking). Parity with Python is checked on B-78's 20 stored
// encounters (data/atc/encounter_fixtures; tests/atc-safety.test.mjs, and on the page). Infinity stands for numpy's inf
// (the fixtures store it as null). Reservations (R3/R10 table side) are not ported: they reach a move as its stop line.
export const G_MOON = 1.62, G_MARS = 3.71;
export const RHO_S = 1.0, A_ACC = 0.2, B_MIN_FLAT = 0.5, B_MAX = 0.8, D0_M = 5.0, MU_DEFAULT = 0.45;
export const STEEP_DEG = 10.0, STEEP_STOP_M = 15.0, R_CREW_SLOW_M = 50.0, R_CREW_MARGIN_M = 10.0, V_CREW_MS = 1.0 / 3.6, MOVING_MS = 0.05;

// first violated rule of a proposal (MoveVerdict.rule)
export const RULES = { 0: null, 1: 'R1', 2: 'R2', 3: 'stop line', 5: 'R5', 6: 'R6' };

const rad = d => d * Math.PI / 180;
export function bGuaranteed(thetaDeg, mu = MU_DEFAULT, g = G_MOON) {
  const th = rad(thetaDeg);
  return Math.min(B_MIN_FLAT, mu * g * Math.cos(th)) - g * Math.sin(th);
}
export function stopDistance(v, b) { return b > 0 ? v * v / (2 * b) : (v > 0 ? Infinity : 0); }
export function rssDmin(vRear, vFront, bRear, rho = RHO_S, aAcc = A_ACC, bFront = B_MAX, d0 = D0_M) {
  const vr = vRear + rho * aAcc;
  const d = vRear * rho + 0.5 * aAcc * rho * rho + stopDistance(vr, bRear) - vFront * vFront / (2 * bFront);
  return Math.max(d, 0) + d0;
}
export function vMaxR2(thetaDeg, mu, sight, vClass, rho = RHO_S, g = G_MOON) {
  const b = bGuaranteed(thetaDeg, mu, g);
  if (!(b > 0)) return 0;
  const s = Math.max(sight, 0);
  const vSight = b * (-rho + Math.sqrt(rho * rho + 2 * s / b));
  const vSteep = thetaDeg > STEEP_DEG ? Math.sqrt(2 * b * STEEP_STOP_M) : Infinity;
  return Math.min(vClass, vSight, vSteep);
}
export const rCrewStop = (v, b) => stopDistance(v, b) + R_CREW_MARGIN_M;

// speed after the step and distance covered (no reversing: a vehicle that would stop mid-step stays stopped)
export function afterStep(v, a, dt) {
  const v1 = Math.max(v + a * dt, 0);
  const t = a < 0 ? Math.min(dt, v / -a) : dt;
  return [v1, Math.max(v * t + 0.5 * a * t * t, 0)];
}

// rule check of acceleration a: [ok, first violated rule code]
function check(m, a, b, vmax) {
  const [v1, x1] = afterStep(m.v, a, m.dt);
  const r2 = v1 <= vmax + 1e-9;
  const [vl1, xl1] = afterStep(m.v_lead, -B_MAX, m.dt);
  const gap1 = m.gap_lead - x1 + xl1;
  const r1 = (gap1 >= rssDmin(v1, vl1, b) || a <= -b + 1e-9) && gap1 > 0;
  const rs = x1 + stopDistance(v1, b) <= m.d_stop + 1e-9;
  const dc1 = m.d_crew - x1;
  const dAny = m.d_crew_any ?? m.d_crew;
  const slowRoom = dAny - x1 - R_CREW_SLOW_M;
  const toSlow = v1 > V_CREW_MS ? (v1 * v1 - V_CREW_MS ** 2) / (2 * (b > 0 ? b : 1e-9)) : 0;
  const r6 = (dc1 >= rCrewStop(v1, b) || v1 <= 1e-9) && (slowRoom >= toSlow || v1 <= V_CREW_MS + 1e-9);
  return [r2 && r1 && rs && r6, !r6 ? 6 : !r1 ? 1 : !rs ? 3 : !r2 ? 2 : 0];
}

// m: {v, a_prop, dt, theta, mu, v_class, sight, gap_lead, v_lead, d_stop, d_crew, d_crew_any?, must_exit?, a_max?, g?}
// -> {a, modified, noSafe, rule}
export function safetyMove(m) {
  const g = m.g ?? G_MOON, aMax = m.a_max ?? A_ACC;
  const b = bGuaranteed(m.theta, m.mu, g);
  const vmax = vMaxR2(m.theta, m.mu, m.sight, m.v_class, RHO_S, g);
  const aProp = Math.min(m.a_prop, aMax);
  const must = !!m.must_exit;
  // R5: inside a closing zone the planner may not choose to slow down (the exit candidate is full acceleration)
  const aFirst = must ? Math.max(aProp, Math.min(aMax, (vmax - m.v) / m.dt)) : aProp;
  let [ok, rule] = check(m, aFirst, b, vmax);
  if (must && aProp < aFirst && rule === 0) rule = 5;
  let a = ok ? aFirst : NaN;
  for (const cand of [Math.min(aFirst, 0), Math.max(-b, -B_MAX * 4)]) if (Number.isNaN(a) && check(m, cand, b, vmax)[0]) a = cand;
  const noSafe = Number.isNaN(a);
  if (noSafe) a = Math.max(-b, -B_MAX * 4);
  return { a, modified: a !== aProp, noSafe, rule };
}
