// Line-by-line port of lunarsim/rover/physics.py: rover driving physics shared by the step environment and the
// leg integrator. Constants keep their flags and sources (FLAGS / SOURCES below) for the page's constants table.
export const G_MOON = 1.62;
export const KMH = 1.0 / 3.6;
const RAD = Math.PI / 180, DEG = 180 / Math.PI;
export const LITAKER_URL = 'https://ntrs.nasa.gov/api/citations/20240011392/downloads/Teleops%20IEEE%20Paper%20FY24%20FINAL.pdf';
export const HU_URL = 'https://arxiv.org/abs/2405.11001';
export const LRV_URLS = ['https://www.apollojournals.org/alsj/a17/a17.clsout3.html', 'https://nssdc.gsfc.nasa.gov/planetary/lunar/apollo_lrv.html'];

export const ROVER = { mass_kg: 1600.0, wheelbase_m: 3.0, steer_max_deg: 30.0, steer_rate_dps: 20.0, accel_mps2: 0.3, slope_nominal_deg: 15.0, slope_hard_deg: 20.0 };
export const AUTONOMY_LEVELS = ['teleop', 'supervised', 'autonomous'];
export const SPEED_CAP_KMH = { autonomous: 9.0, supervised: 3.0 };
export const SUPERVISED_STOP = { every_m: 500.0, stop_s: 60.0 };
export const LITAKER_SMG_KMH = { 0: 3.24, 4: 2.56, 6: 2.03, 8: 1.76 };
export const TELEOP_V0_KMH = 3.80, TELEOP_DV_KMH_PER_S = (3.80 - 3.55) / 4.0, TELEOP_T_LOOK_S = 30.0;

export const teleopMoveKmh = rtt => TELEOP_V0_KMH - TELEOP_DV_KMH_PER_S * rtt;
export const teleopStopS = rtt => TELEOP_T_LOOK_S + 2.0 * rtt;
function cadencePoint(rtt, smg) { const overhead = 3.6 / smg - 3.6 / teleopMoveKmh(rtt); return teleopStopS(rtt) / overhead; }
export const TELEOP_CADENCE_M = Object.fromEntries(Object.entries(LITAKER_SMG_KMH).map(([r, v]) => [r, cadencePoint(+r, v)]));
export function teleopCadenceM(rtt) {
  const xs = Object.keys(TELEOP_CADENCE_M).map(Number).sort((a, b) => a - b);
  if (rtt <= xs[0]) return TELEOP_CADENCE_M[xs[0]];
  for (let k = 0; k + 1 < xs.length; k++) { const a = xs[k], b = xs[k + 1]; if (rtt <= b) { const f = (rtt - a) / (b - a); return TELEOP_CADENCE_M[a] + f * (TELEOP_CADENCE_M[b] - TELEOP_CADENCE_M[a]); } }
  return TELEOP_CADENCE_M[xs[xs.length - 1]];
}

// slip vs slope along the heading (Hu et al. 2024 anchors), Modelled
export const SLIP_TABLE_DEG = [0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0];
export const SLIP_TABLE = [0.05, 0.08, 0.15, 0.22, 0.35, 0.55, 0.85];
export const SLIP_DOWNHILL = 0.05, DIG_IN_SLIP = 0.80;

/* numpy.interp: linear, clamped to the end values */
export function interp(x, xp, fp) {
  if (x <= xp[0]) return fp[0];
  if (x >= xp[xp.length - 1]) return fp[fp.length - 1];
  let k = 0; while (k + 1 < xp.length && xp[k + 1] < x) k++;
  if (x === xp[k + 1]) return fp[k + 1];
  const slope = (fp[k + 1] - fp[k]) / (xp[k + 1] - xp[k]);   // numpy's evaluation order (bit-identical results)
  return slope * (x - xp[k]) + fp[k];
}
export function speedCapMps(autonomy, rtt = 0.0) {
  let ground;
  if (autonomy === 'teleop') ground = teleopMoveKmh(rtt);
  else if (autonomy in SPEED_CAP_KMH) ground = SPEED_CAP_KMH[autonomy];
  else throw new Error(`unknown autonomy level ${autonomy}`);
  return ground * KMH / (1.0 - SLIP_TABLE[0]);
}
export function stopPlan(autonomy, rtt = 0.0) {
  if (autonomy === 'teleop') return [teleopCadenceM(rtt), teleopStopS(rtt)];
  if (autonomy === 'supervised') return [SUPERVISED_STOP.every_m, SUPERVISED_STOP.stop_s];
  return [Infinity, 0.0];
}
export function slip(grade) {
  if (grade > SLIP_TABLE_DEG[SLIP_TABLE_DEG.length - 1]) return 0.95;
  if (grade > 0) return interp(Math.min(Math.max(grade, 0.0), SLIP_TABLE_DEG[SLIP_TABLE_DEG.length - 1]), SLIP_TABLE_DEG, SLIP_TABLE);
  return SLIP_DOWNHILL;
}
export const slopeSpeedFactor = s => interp(s, [0, 10, 15, 20, 20.001], [1.0, 1.0, 0.5, 0.25, 0.0]);

// lighting (JSC lighting study; sun 1-2 deg)
export const UP_SUN_HALF_ANGLE_DEG = 45.0, UP_SUN_TACK_DEG = 25.0, SHADOW_SPEED_FACTOR = 0.5, NIGHT = 'night';
export function lightingFactor(headingDeg, sunAzDeg, inShadow) {
  let f = inShadow ? SHADOW_SPEED_FACTOR : 1.0;
  if (sunAzDeg !== null && sunAzDeg !== undefined && sunAzDeg !== NIGHT) {
    const t = headingDeg - sunAzDeg + 180.0, m = t % 360.0, d = Math.abs((m !== 0 && m < 0 ? m + 360.0 : m) - 180.0);
    if (d <= UP_SUN_HALF_ANGLE_DEG && !inShadow) f = f * Math.cos(UP_SUN_TACK_DEG * RAD);
  }
  return f;
}

// energy (Apollo LRV calibration, Measured -> effective rolling coefficient, Modelled)
export const LRV_WH_PER_KM = 58.5, LRV_MASS_KG = 700.0;
export const C_RR_EFF = LRV_WH_PER_KM * 3.6 * (1.0 - SLIP_TABLE[0]) / (LRV_MASS_KG * G_MOON);
export const DRIVE_EFF = 0.7, HOTEL_W = 0.0;
export function energyWh(ds, grade, slipRatio, massKg = ROVER.mass_kg) {
  const th = grade * RAD, fRoll = C_RR_EFF * massKg * G_MOON * Math.cos(th), fGrade = Math.max(0.0, massKg * G_MOON * Math.sin(th)) / DRIVE_EFF;
  return (fRoll + fGrade) * ds / (1.0 - slipRatio) / 3600.0;
}

export const INTERVENTION = { corridor_m: 25.0, slope_deg: ROVER.slope_hard_deg, stall_s: 30.0, roughness_m: 0.5, recovery_s: 300.0 };
export const interventionCostS = rtt => rtt + INTERVENTION.recovery_s;

/* kinematic bicycle, one step (state: x, y, psi rad map azimuth, v m/s, delta rad); returns a new object */
export function step(state, steerRateCmd, throttleCmd, vCap, dt) {
  const s = { ...state }, dmax = ROVER.steer_max_deg * RAD;
  s.delta = Math.max(-dmax, Math.min(dmax, s.delta + Math.max(-1.0, Math.min(1.0, steerRateCmd)) * (ROVER.steer_rate_dps * RAD) * dt));
  const vTarget = Math.max(0.0, Math.min(1.0, throttleCmd)) * vCap;
  const dv = Math.max(-ROVER.accel_mps2 * dt, Math.min(ROVER.accel_mps2 * dt, vTarget - s.v));
  s.v = Math.max(0.0, s.v + dv);
  return s;
}
const TWO_PI = 2 * Math.PI, pmod = (a, b) => { const m = a % b; return (m !== 0 && (m < 0) !== (b < 0)) ? m + b : m; };
export function advance(state, groundV, dt) {
  const s = { ...state };
  s.psi = pmod(s.psi + groundV / ROVER.wheelbase_m * Math.tan(s.delta) * dt, TWO_PI);
  s.x += groundV * Math.sin(s.psi) * dt; s.y += groundV * Math.cos(s.psi) * dt;
  return s;
}

export const FLAGS = {
  mass_kg: ['Assumed', 'LTV-class vehicle with cargo (LTV payload ≥ 800 kg)'], wheelbase_m: ['Assumed', ''], steer_max_deg: ['Assumed', ''], steer_rate_dps: ['Assumed', ''], accel_mps2: ['Assumed', ''],
  slope_nominal_deg: ['Spec', 'designs converge on 15° nominal (VIPER, Intrepid)'], slope_hard_deg: ['Spec', 'LTV / RACER / Endurance 20° requirement'],
  autonomous_kmh: ['Measured', `Apollo LRV moving average 8.1–9.2 km/h (analogue): ${LRV_URLS[0]}`], supervised_kmh: ['Assumed', 'within the 0.5–3.6 km/h modelling range; no lunar demonstration'],
  teleop_smg: ['Measured', `Litaker et al. 2025, JSC simulator: ${LITAKER_URL}`], t_look_s: ['Assumed', '>95 % of navigation at 6–8 s used the 180° camera pan (Litaker)'],
  slip_table: ['Modelled', `Hu et al. 2024 anchors (Chrono CRM validated against NASA GRC SLOPE lab): ${HU_URL}`], dig_in: ['Measured', `Hu et al. 2024: slip above 80 % raises dig-in risk: ${HU_URL}`],
  lighting: ['Assumed', 'JSC lighting study: drivers up-sun tacked ±20–30°; shadowed slopes "very difficult"'], energy: ['Modelled', `Apollo LRV 57–60 Wh/km (Measured) → effective rolling coefficient ${C_RR_EFF.toFixed(3)}: ${LRV_URLS.join(', ')}`],
  intervention: ['Assumed', 'corridor 25 m, slope > 20°, stall 30 s, roughness > 0.5 m; recovery 300 s + RTT'],
};
export { RAD, DEG };
