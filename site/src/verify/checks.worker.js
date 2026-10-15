// Phase-3 verification checks, run off the main thread. Each check compares a browser computation with a Python
// reference (a committed fixture or site/verify/refs.json from scripts/make_verify_refs.py) and posts
// {group, name, reference, computed, tolerance, unit, pass, basis}. Message in: {base, refs}.
import { MlpPolicy, checkPolicy } from '../policy.js';
import * as LP from '../lander/physics.js';
import { CLASSES } from '../lander/classes.js';
import { DescentEnv, targetVelocity } from '../lander/env.js';
import { RoverTerrain } from '../rover/terrain.js';
import { plan } from '../rover/expert.js';
import { DriveEnv, expertController } from '../rover/env.js';
import { legProfile, driveProfile } from '../rover/tables.js';
import { LITAKER_SMG_KMH } from '../rover/physics.js';

const post = c => self.postMessage({ type: 'check', check: c });
const md = (a, b) => { let m = 0; for (let i = 0; i < a.length; i++) m = Math.max(m, Math.abs(a[i] - b[i])); return m; };
const getJson = async u => { const r = await fetch(u); if (!r.ok) throw new Error(`${u}: HTTP ${r.status}`); return r.json(); };
const fail = (group, name, err) => post({ group, name, reference: '–', computed: 'error: ' + err.message, tolerance: '–', pass: false, basis: '' });
function fnv1a(bytes) { let h = 0x811C9DC5; for (let i = 0; i < bytes.length; i++) h = Math.imul(h ^ bytes[i], 0x01000193) >>> 0; return h >>> 0; }

async function policies(base) {
  const G = 'Trained policies';
  try {
    const idx = await getJson(base + 'lab/policies/index.json');
    for (const id of idx.policies) {
      try {
        const p = new MlpPolicy(await getJson(`${base}lab/policies/${id}.json`)), c = checkPolicy(p, await getJson(`${base}lab/policies/${id}.check.json`));
        post({ group: G, name: `${id}: forward pass on ${c.n} check vectors vs ${c.against}`, reference: 'Python actions', computed: `max |Δ| ${c.maxErr.toExponential(2)}`, tolerance: String(c.tolerance), pass: c.maxErr <= c.tolerance, basis: `data/policies/${id}.check.json` });
        if (c.sb3) post({ group: G, name: `${id}: vs Stable-Baselines3 float32 actions`, reference: 'SB3 actions', computed: `max |Δ| ${c.sb3.maxErr.toExponential(2)}`, tolerance: String(c.sb3.tolerance), pass: c.sb3.ok, basis: `${id}.check.json sb3_act` });
      } catch (e) { fail(G, id, e); }
    }
  } catch (e) { fail(G, 'policy index', e); }
}

async function lander(base) {
  const G = 'Lander environment (JS port vs Python)';
  let F; try { F = await getJson(base + 'verify/lander_parity.json'); } catch (e) { fail(G, 'tests/fixtures/lander_parity.json', e); return; }
  const tol = F.tolerance, src = `tests/fixtures/lander_parity.json (env v${F.env_version})`;
  for (const r of F.physics) {
    let s = Float64Array.from(r.state0), ws = 0, wt = 0;
    r.actions.forEach((a, k) => { const [n, t] = LP.step(s, a, CLASSES[r.cls], r.dt, r.thrust_scale, r.isp_scale, r.m_dry); ws = Math.max(ws, md(n, r.states[k])); wt = Math.max(wt, Math.abs(t - r.thrust[k])); s = n; });
    post({ group: G, name: `Physics, ${r.cls}: ${r.actions.length} steps incl. propellant run-out`, reference: 'Python states and thrust', computed: `max |Δstate| ${ws.toExponential(2)}, |Δthrust| ${wt.toExponential(2)}`, tolerance: String(tol), pass: ws <= tol && wt <= tol * 1e3, basis: src });
  }
  let tv = 0; for (const t of F.target_velocity) tv = Math.max(tv, md(targetVelocity(t.pos, t.vel), t.v_targ));
  post({ group: G, name: `Velocity field, ${F.target_velocity.length} samples`, reference: 'Python v_target', computed: `max |Δ| ${tv.toExponential(2)}`, tolerance: String(tol), pass: tv <= tol, basis: src });
  const pols = {};
  for (const e of F.episodes) {
    try {
      const pol = pols[e.policy] ||= new MlpPolicy(await getJson(`${base}lab/policies/${e.policy}.json`));
      const env = new DescentEnv({ cls: e.cls, variant: e.variant, randomize: e.randomize, sensor: e.sensor, envVersion: F.env_version });
      let obs = env.reset(e.seed), ws = 0, wr = 0, wo = 0, k = 0, out = null;
      for (; k < e.steps.length; k++) { const ref = e.steps[k], r = env.step(pol.act(obs).map(Math.fround)); obs = r.obs; ws = Math.max(ws, md(env.state, ref.state)); wr = Math.max(wr, Math.abs(r.reward - ref.reward)); wo = Math.max(wo, md(obs, ref.obs)); if (r.terminated || r.truncated) { out = r.outcome; k++; break; } }
      const same = k === e.steps.length && out && (out.failure_kind ?? null) === (e.outcome.failure_kind ?? null);
      post({ group: G, name: `Episode, ${e.cls}, ${e.policy}, no dispersion`, reference: `${e.steps.length} steps, ${e.outcome.failure_kind ?? 'ok'}`, computed: `${k} steps, ${out ? out.failure_kind ?? 'ok' : '–'}; max |Δstate| ${ws.toExponential(2)}, |Δreward| ${wr.toExponential(2)}, |Δobs| ${wo.toExponential(2)}`, tolerance: String(tol), pass: same && ws <= tol && wr <= tol && wo <= tol, basis: src });
    } catch (err) { fail(G, `episode ${e.cls}`, err); }
  }
}

async function rover(base, refs) {
  const G = 'Rover model (JS port vs Python and data)';
  const R = refs.rover;
  // flat leg, teleop: speed made good vs the JSC measurements and vs Python's own run
  try {
    const fm = R.flat_leg.meta, L = fm.layers, mk = (lay, Arr) => ({ width: lay.shape[1], height: lay.shape[0], data: new Arr(lay.shape[0] * lay.shape[1]) });
    const v0 = Math.round((100 - fm.z_encoding.offset_m) / fm.z_encoding.scale_m_per_unit), h5 = mk(L.height_5m, Uint16Array), h20 = mk(L.height_20m, Uint16Array); h5.data.fill(v0); h20.data.fill(v0);
    const flat = new RoverTerrain(fm, h5, h20, mk(L.slope_20m, Uint8Array));
    for (const [rtt, jsc] of Object.entries(LITAKER_SMG_KMH)) {
      const env = new DriveEnv(flat); let obs = env.reset({ waypoints: R.flat_leg.route, autonomy: 'teleop', rttS: +rtt, sunAz: null }); const ctl = expertController(env.route); let leg = null;
      for (;;) { const r = env.step(ctl.act(obs, env)); obs = r.obs; if (r.terminated || r.truncated) { leg = r.leg; break; } }
      const smg = leg.distance_m / leg.time_s * 3.6, py = R.flat_leg.smg_kmh[rtt];
      post({ group: G, name: `Flat 2.6 km leg, teleop at ${rtt} s round trip: speed made good`, reference: `${jsc} km/h (Litaker et al. 2025)`, computed: `${smg.toFixed(4)} km/h (${((smg / jsc - 1) * 100).toFixed(2)} %)`, tolerance: '2 %', pass: Math.abs(smg / jsc - 1) <= 0.02, basis: 'JSC teleoperation trials (Measured)' });
      post({ group: G, name: `Flat leg at ${rtt} s: same drive as Python`, reference: `${py.toFixed(10)} km/h`, computed: `${smg.toFixed(10)} km/h`, tolerance: '1e-9 relative', pass: Math.abs(smg / py - 1) <= 1e-9, basis: 'site/verify/refs.json' });
    }
  } catch (e) { fail(G, 'flat leg', e); }
  // terrain pack: decoding, shadows, BASE -> PSR
  let t;
  try { t = await RoverTerrain.load(base + 'terrain/hero/'); } catch (e) { fail(G, 'terrain pack', e); return; }
  const T = refs.terrain; let lo = Infinity, hi = -Infinity; for (let i = 0; i < t.z5.length; i++) { const z = t.z5[i]; if (z < lo) lo = z; if (z > hi) hi = z; }
  post({ group: 'Terrain pack', name: 'Decoded 5 m heights: range vs meta.json stats', reference: `${T.meta_z_min.toFixed(3)} … ${T.meta_z_max.toFixed(3)} m`, computed: `${lo} … ${hi} m`, tolerance: `${T.scale_m_per_unit} m (one quantisation step)`, pass: Math.abs(lo - T.meta_z_min) <= T.scale_m_per_unit && Math.abs(hi - T.meta_z_max) <= T.scale_m_per_unit, basis: 'data/terrain/connecting_ridge/meta.json' });
  post({ group: 'Terrain pack', name: 'Decoded 5 m heights: range vs Python decoder', reference: `${T.z5_min} … ${T.z5_max} m`, computed: `${lo} … ${hi} m`, tolerance: 'exact', pass: lo === T.z5_min && hi === T.z5_max, basis: 'site/verify/refs.json' });
  for (const [az, ref] of Object.entries(refs.shadow)) {
    t._shadow.clear(); const g = t.shadowGrid(+az); let n = 0; for (let i = 0; i < g.length; i++) n += g[i];
    const h = fnv1a(g);
    post({ group: 'Terrain pack', name: `Cast shadows, sun ${az}° at 1.5°: computed in the browser`, reference: `${ref.shadowed_cells} cells, FNV-1a ${ref.fnv1a}`, computed: `${n} cells, FNV-1a ${h}`, tolerance: 'identical', pass: n === ref.shadowed_cells && h === ref.fnv1a, basis: 'lunarsim.terrain.cast_shadow (site/verify/refs.json)' });
  }
  try {
    const sites = await getJson(base + 'terrain/hero/sites.json'), P = Object.fromEntries(sites.sites.map(s => [s.id, s.xy_m])), B = R.base_psr_sun90;
    const route = plan(t, P.BASE, P.PSR, 90), prof = legProfile(t, route, 90), d = driveProfile(prof, 'autonomous', 0, 90);
    post({ group: G, name: 'BASE → PSR, sun 90°: A* route', reference: `${B.route_points} points, ${B.length_m.toFixed(3)} m`, computed: `${route.length} points, ${prof.length_m.toFixed(3)} m`, tolerance: '1e-9 m', pass: route.length === B.route_points && Math.abs(prof.length_m - B.length_m) <= 1e-9, basis: 'site/verify/refs.json' });
    post({ group: G, name: 'BASE → PSR: leg-integrator energy', reference: `${B.integrator_energy_wh.toFixed(6)} Wh`, computed: `${d.energy_wh.toFixed(6)} Wh`, tolerance: '1e-9 relative', pass: Math.abs(d.energy_wh / B.integrator_energy_wh - 1) <= 1e-9, basis: 'site/verify/refs.json' });
    const env = new DriveEnv(t); let obs = env.reset({ waypoints: route, autonomy: 'autonomous', rttS: 0, sunAz: 90 }); const ctl = expertController(env.route); let leg = null;
    for (;;) { const r = env.step(ctl.act(obs, env)); obs = r.obs; if (r.terminated || r.truncated) { leg = r.leg; break; } }
    post({ group: G, name: 'BASE → PSR, autonomous: step drive vs Python', reference: `${B.drive_autonomous.energy_wh.toFixed(6)} Wh, ${B.drive_autonomous.time_s} s`, computed: `${leg.energy_wh.toFixed(6)} Wh, ${leg.time_s} s`, tolerance: '1e-9 relative', pass: Math.abs(leg.energy_wh / B.drive_autonomous.energy_wh - 1) <= 1e-9 && leg.time_s === B.drive_autonomous.time_s, basis: 'site/verify/refs.json' });
    let table = null; try { const idx = await getJson(base + 'lab/rover/driving-index.json'); table = await getJson(`${base}lab/rover/legs/${idx.legs['BASE->PSR']}`); } catch (e) { /* table absent */ }
    if (table) { const T90 = table.autonomy.autonomous.rtt_s['0'].lighting['90'].energy_kwh.mean * 1000;
      post({ group: G, name: 'BASE → PSR, autonomous: live drive energy vs the driving table', reference: `${T90.toFixed(1)} Wh (driving-v1 mean)`, computed: `${leg.energy_wh.toFixed(1)} Wh (${((leg.energy_wh / T90 - 1) * 100).toFixed(2)} %)`, tolerance: '5 %', pass: Math.abs(leg.energy_wh / T90 - 1) <= 0.05, basis: 'data/driving/driving-v1.json' }); }
  } catch (e) { fail(G, 'BASE → PSR', e); }
  post({ group: G, name: 'Documented difference: BASE → PSR, teleop 4 s, night (long step drive)', reference: 'Python step drive', computed: 'states identical to 1e-9 for 5,476 of 9,033 steps, then a chaotic drift up to 38 m mid-leg; same steps, time and interventions; energy 616.66 vs 616.62 Wh (0.006 %)', tolerance: 'not a pass/fail check', pass: null, basis: 'one-ulp differences in V8 vs CPython sin/cos/atan, amplified by the 4 s steering delay (F-8 report)' });
}

self.onmessage = async e => {
  const { base, refs } = e.data;
  await policies(base); await lander(base); await rover(base, refs);
  self.postMessage({ type: 'done' });
};
