// Port of lunarsim/lander/classes.py: lander classes, the SPLICE gate and touchdown box. Plain data; every
// constant keeps its flag and source so the page can show them. Keep in step with the Python file.
export const G_MOON = 1.62;      // m/s^2, Spec
export const G0 = 9.80665;       // m/s^2, Spec (standard gravity, defines Isp in seconds)

const SPLICE_URL = 'https://ntrs.nasa.gov/api/citations/20200002415/downloads/20200002415.pdf';
const BE7_URLS = ['https://en.wikipedia.org/wiki/Blue_Moon_(spacecraft)', 'https://en.wikipedia.org/wiki/BE-7', 'https://newspaceeconomy.ca/2025/11/15/what-is-the-be-7/'];
const APOLLO_DPS_URL = 'https://www.lpi.usra.edu/lunar/documents/Bennett_NASA-TM-X-58040.pdf';
const REPORT = 'reports/Lunar landing and rover autonomy logistics.md';

function lander(d) { return Object.freeze({ ...d, gate_overrides: d.gate_overrides || {}, m_dry_kg: d.m_gate_kg - d.prop_gate_kg, hover_tw: d.t_max_n / (d.m_gate_kg * G_MOON) }); }

export const CLPS = lander({
  name: 'CLPS', m_gate_kg: 2000.0, prop_gate_kg: 300.0, t_max_n: 5000.0, t_min_n: 1000.0, isp_s: 311.0, tilt_max_deg: 45.0, tilt_rate_max_dps: 10.0,
  flags: { m_gate_kg: 'Spec', prop_gate_kg: 'Assumed', t_max_n: 'Spec', t_min_n: 'Assumed', isp_s: 'Assumed', tilt_max_deg: 'Assumed', tilt_rate_max_dps: 'Assumed' },
  sources: {
    m_gate_kg: `SPLICE robotic reference lander, 2,000 kg with a 5,000 N motor: ${SPLICE_URL}`, t_max_n: SPLICE_URL,
    t_min_n: `20 % throttle floor; Assumed (no CLPS throttle range published; Apollo DPS throttled to 10 %: ${APOLLO_DPS_URL})`,
    isp_s: `Apollo DPS full-thrust Isp 311 s used as a stand-in for a storable CLPS engine: ${APOLLO_DPS_URL}`,
    prop_gate_kg: '15 % of gate mass; Assumed (terminal descent from the gate needs ~100 kg at Isp 311)', tilt_max_deg: 'Assumed', tilt_rate_max_dps: 'Assumed' },
});
export const MK1 = lander({
  name: 'MK1', m_gate_kg: 9000.0, prop_gate_kg: 1000.0, t_max_n: 44000.0, t_min_n: 8900.0, isp_s: 440.0, tilt_max_deg: 45.0, tilt_rate_max_dps: 8.0,
  flags: { m_gate_kg: 'Assumed', prop_gate_kg: 'Assumed', t_max_n: 'Spec', t_min_n: 'Spec (conflicting)', isp_s: 'Assumed', tilt_max_deg: 'Assumed', tilt_rate_max_dps: 'Assumed' },
  sources: {
    m_gate_kg: `Blue Moon MK1 dry mass unpublished (21,350 kg fuelled, 3,000 kg payload); ~9,000 kg at the gate is Assumed: ${BE7_URLS[0]}`,
    t_max_n: `BE-7 44 kN maximum, the one figure all sources agree on: ${BE7_URLS[0]}; ${BE7_URLS[1]}`,
    t_min_n: `8.9 kN deep throttle per Blue Origin's BE-7 page as quoted by Wikipedia; CONFLICTS with ~2,000 lbf (8.9 kN, 20 %) in the BE-7 infobox and 1,000 lbf (4.4 kN) elsewhere: ${BE7_URLS.join(', ')}`,
    isp_s: `BE-7 vacuum Isp 460 s is uncited and ~453 s is an estimate; 440 s Assumed: ${BE7_URLS[1]}`, prop_gate_kg: 'Assumed', tilt_max_deg: 'Assumed', tilt_rate_max_dps: 'Assumed' },
});
const LARGE_M = 60000.0;
export const LARGE = lander({
  name: 'LARGE', m_gate_kg: LARGE_M, prop_gate_kg: 5000.0, t_max_n: 1.5 * LARGE_M * G_MOON, t_min_n: 0.25 * 1.5 * LARGE_M * G_MOON, isp_s: 350.0, tilt_max_deg: 45.0, tilt_rate_max_dps: 5.0,
  flags: { m_gate_kg: 'Assumed', prop_gate_kg: 'Assumed', t_max_n: 'Modelled', t_min_n: 'Assumed', isp_s: 'Assumed', tilt_max_deg: 'Assumed', tilt_rate_max_dps: 'Assumed' },
  sources: {
    m_gate_kg: `Parametric 60 t cargo lander (Starship HLS / Blue Moon MK2 cargo class; dry masses unpublished, cargo 12-15 t per NASA IAC 2025): ${REPORT}`,
    t_max_n: 'hover T/W 1.5 at the gate mass (Modelled)', t_min_n: '25 % throttle floor (Assumed)', isp_s: 'methalox landing engines, Assumed', prop_gate_kg: 'Assumed',
    tilt_max_deg: 'Assumed', tilt_rate_max_dps: 'Assumed',
    gate_overrides: 'Assumed: at T/W 1.5 the SPLICE robotic gate (250 m, 30 m/s) is past the stopping distance (30^2 / (2 * 1.8 m/s^2) = 250 m at best), so the large class starts 400 m downrange at 25 m/s' },
  gate_overrides: { downrange_m: 400.0, vh_mps: 25.0 },
});
export const CLASSES = { CLPS, MK1, LARGE };

export const GATE = { slant_range_m: 500.0, downrange_m: 250.0, altitude_m: 430.0, vz_mps: -15.0, vh_mps: 30.0, flag: 'Spec', source: SPLICE_URL };
export const TOUCHDOWN = { vz_max_mps: 2.0, vh_max_mps: 1.0, tilt_max_deg: 6.0, rate_max_dps: 2.0, delivery_radius_m: 50.0, flag: 'Spec', source: SPLICE_URL };
export const TIPOVER_DEG = 12.0;   // Spec/Measured: Apollo LM 12 deg effective-slope design limit
export const TIPOVER_SOURCE = 'https://ntrs.nasa.gov/api/citations/20205009125/downloads/Lunar%20Landing%20&%20Launch%20Pads%20v1.pdf';
