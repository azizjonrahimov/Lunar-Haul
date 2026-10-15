// /verification: every check that ties the browser code to the Python reference or to independent data, with a
// "N of M checks pass" badge. Engine checks and the cross-implementation check reuse the simulator's worker
// (simulator/worker.js + sim.js); Phase-3 checks run in checks.worker.js.
import './verify.css';
import refs from '../../verify/refs.json';
import { esc } from '../components/num.js';

const $ = id => document.getElementById(id);
const BASE = import.meta.env.BASE_URL, SIM = BASE + 'simulator/';
const checks = [];   // {group, name, reference, computed, tolerance, pass (true|false|null), basis}
const GROUP_ORDER = ['Simulation engine (13 checks, as in the paper)', 'Python vs browser engine', 'Trained policies', 'Lander environment (JS port vs Python)', 'Rover model (JS port vs Python and data)', 'Terrain pack'];

function add(c) { checks.push(c); render(); }
function render() {
  const scored = checks.filter(c => c.pass !== null), ok = scored.filter(c => c.pass).length;
  $('v-badge').textContent = scored.length ? `${ok} of ${scored.length} checks pass` : 'not run yet';
  $('v-badge').className = 'v-badge ' + (!scored.length ? 'idle' : ok === scored.length ? 'ok' : 'bad');
  const groups = [...new Set(GROUP_ORDER.concat(checks.map(c => c.group)))].filter(g => checks.some(c => c.group === g));
  $('v-results').innerHTML = groups.map(g => {
    const cs = checks.filter(c => c.group === g), n = cs.filter(c => c.pass !== null), k = n.filter(c => c.pass).length;
    return `<section class="v-group" aria-label="${esc(g)}"><h2>${esc(g)} <span class="v-count">${k} / ${n.length}</span></h2><div class="v-scroll"><table class="w-table"><thead><tr><th>Check</th><th>Reference</th><th>Computed here</th><th>Tolerance</th><th>Result</th></tr></thead><tbody>` +
      cs.map(c => `<tr><td>${esc(c.name)}${c.basis ? `<div class="small muted">${esc(c.basis)}</div>` : ''}</td><td class="mono small">${esc(c.reference)}</td><td class="mono small">${esc(c.computed)}</td><td class="small">${esc(c.tolerance)}</td><td>${c.pass === null ? '<span class="pill note">documented</span>' : c.pass ? '<span class="pill pass">pass</span>' : '<span class="pill fail">FAIL</span>'}</td></tr>`).join('') +
      '</tbody></table></div></section>';
  }).join('');
}
const fmt = (x, d = 4) => Number.isFinite(x) ? x.toLocaleString('en-GB', { maximumFractionDigits: d, minimumFractionDigits: d }) : '–';

// ---------- simulator engine (classic worker from the simulator build) ----------
function simWorker() { return new Worker(SIM + 'worker.js'); }
function call(w, msg) { return new Promise(res => { const id = Math.random(); const h = e => { if (e.data.id === id && e.data.type !== 'progress') { w.removeEventListener('message', h); res(e.data); } }; w.addEventListener('message', h); w.postMessage({ ...msg, id }); }); }
async function engineChecks() {
  const G = 'Simulation engine (13 checks, as in the paper)';
  try {
    const w = simWorker(), m = await call(w, { type: 'verify' }); w.terminate();
    for (const c of m.checks) add({ group: G, name: c.name, reference: `${fmt(c.ref)} ${c.unit}`, computed: `${fmt(c.sim)} ${c.unit}`, tolerance: `${(100 * c.tol).toFixed(c.tol < 0.001 ? 7 : 1)} %`, pass: c.passed, basis: c.basis });
  } catch (e) { add({ group: G, name: 'simulator worker', reference: '–', computed: 'error: ' + e.message, tolerance: '–', pass: false, basis: '' }); }
}
function loadScript(src) { return new Promise((res, rej) => { const s = document.createElement('script'); s.src = src; s.onload = res; s.onerror = () => rej(new Error(`${src} did not load`)); document.head.appendChild(s); }); }
async function crossCheck() {
  const G = 'Python vs browser engine'; $('v-cross').disabled = true; $('v-cross-status').textContent = 'running 30 seeds × 4 rules…';
  try {
    // sim.js is a classic script: its top-level const/let (PRESETS, mean, ci95) are global lexical bindings, not window
    // properties, so they are read as bare names once it has loaded
    /* global makeScenario, PRESETS, mean, ci95 */
    if (typeof makeScenario === 'undefined') await loadScript(SIM + 'sim.js');
    const refTxt = await (await fetch(SIM + 'ref.js')).text(), PY = JSON.parse(refTxt.slice(refTxt.indexOf('=') + 1).trim().replace(/;$/, ''));
    const sc = makeScenario({ phase: 'P2', bulkT: 500, fleet: PRESETS[6], night: 0.15, rtt: 5, nOps: 3, duty: 0.3, mtbf: 1, std: 1 }), seeds = Array.from({ length: 30 }, (_, i) => i);
    const n = Math.max(1, Math.min(8, (navigator.hardwareConcurrency || 4) - 1)), ws = Array.from({ length: n }, simWorker);
    const KEYS = [['delay_prio1_mean_h', 'urgent mean delay (h)'], ['delay_prio1_p90_h', 'urgent p90 delay (h)'], ['sl24_prio1', 'urgent within 24 h'], ['jobs', 'trips per year'], ['night_strandings', 'night strandings'], ['delivered_share', 'delivered share']];
    for (const mech of ['inhouse', 'pooled_greedy', 'central_assign', 'marketplace']) {
      $('v-cross-status').textContent = `running ${mech}…`;
      const per = Math.ceil(seeds.length / n), parts = await Promise.all(ws.map((w, k) => call(w, { type: 'run', scenario: sc, mechanism: mech, seeds: seeds.slice(k * per, (k + 1) * per), opts: {}, trace: false })));
      const runs = parts.flatMap(p => p.runs);
      for (const [key, lab] of KEYS) {
        const r = PY[mech] && PY[mech][key]; if (!r) continue; const v = runs.map(x => x[key]), m = mean(v), ci = ci95(v);
        add({ group: G, name: `${mech}: ${lab}`, reference: `${fmt(r.mean, 3)} ± ${fmt(r.ci, 3)} (Python, n = ${r.n})`, computed: `${fmt(m, 3)} ± ${fmt(ci, 3)} (browser, n = 30)`, tolerance: 'means within the combined 95 % CIs', pass: Math.abs(m - r.mean) <= ci + r.ci, basis: 'results/E1_phases.csv, Phase-2 default fleet' });
      }
    }
    ws.forEach(w => w.terminate()); $('v-cross-status').textContent = 'done.';
  } catch (e) { add({ group: G, name: 'cross-implementation check', reference: '–', computed: 'error: ' + e.message, tolerance: '–', pass: false, basis: '' }); $('v-cross-status').textContent = 'failed.'; }
  $('v-cross').disabled = false;
}

// ---------- Phase-3 checks (module worker) ----------
function phase3() {
  return new Promise(res => {
    const w = new Worker(new URL('./checks.worker.js', import.meta.url), { type: 'module' });
    w.onmessage = e => { if (e.data.type === 'check') add(e.data.check); else if (e.data.type === 'done') { w.terminate(); res(); } };
    w.onerror = e => { add({ group: 'Phase-3 checks', name: 'worker', reference: '–', computed: 'error: ' + (e.message || 'worker failed'), tolerance: '–', pass: false, basis: '' }); res(); };
    w.postMessage({ base: BASE, refs });
  });
}

async function runAll() {
  $('v-run').disabled = true; checks.length = 0; render(); $('v-status').textContent = 'Running the engine checks and the Phase-3 checks…';
  const t0 = performance.now(); await Promise.all([engineChecks(), phase3()]);
  $('v-status').textContent = `Done in ${((performance.now() - t0) / 1000).toFixed(1)} s. The cross-implementation check (about 15 s) runs separately.`; $('v-run').disabled = false;
}
$('v-run').addEventListener('click', runAll);
$('v-cross').addEventListener('click', crossCheck);
$('v-refs').textContent = `Reference numbers for the Phase-3 checks: site/verify/refs.json, made by site/scripts/make_verify_refs.py from the Python code at commit ${refs.generated.commit.slice(0, 7)} (${refs.generated.time}).`;
render();
runAll();
