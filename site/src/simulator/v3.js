// /simulator/ v3 (F-37): the browser simulator on the site's design system. The engine is unchanged: web/sim.js (also
// run by web/worker.js in background workers), formats.js (trace and scenario files), api.js (the optional local Python
// engine) and ref.js (the stored Python reference) load as classic scripts from /simulator/engine/ and leave their
// globals (makeScenario, PRESETS, MECHS, MECH_LABEL, mean, ci95, WORLD, readTrace, PY_API, PY_REF ...) for this module.
// This module is v2's app.js on glass panels and segmented controls: results as stat chips and Observable Plot charts,
// Compare as one answer card per job rule, and "Watch this year in 3D". v2 stays at /simulator/v2/ for one release.
import './v3.css';
import { segmented, statChip, sceneChips, h } from '../ui/index.js';
import { createTimescale } from '../ui/timescale.js';

const $ = id => document.getElementById(id);
const BASE = import.meta.env.BASE_URL, ENGINE = BASE + 'simulator/engine/';
const fmtN = (x, d = 1) => (Number.isFinite(x) ? x.toLocaleString('en-GB', { maximumFractionDigits: d, minimumFractionDigits: d }) : '–');
const esc = x => String(x).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const css = k => getComputedStyle(document.querySelector('.sim')).getPropertyValue(k).trim();   // the palette lives on .sim
const PHASE_TEXT = { P1: 'Phase 1, before 2029: about 5 t a year', P2: 'Phase 2, 2029–2032: about 30 t a year', P3: 'Phase 3, after 2032: about 74 t a year' };
const MECH_TEXT = { inhouse: 'Separate fleets: each owner uses only its own carrier', pooled_greedy: 'Shared fleet: nearest free rover takes the oldest job', central_assign: 'Shared fleet: best rover-to-job matching every hour', marketplace: 'Marketplace: rovers bid for jobs' };
const SRC = n => `LunarHaul browser engine (sim.js), ${n} simulated year${n === 1 ? '' : 's'}`;
// Observable Plot (with d3, about 85 kB gz) is fetched at once but after the controls and stat chips; charts draw when it lands
let Plot = null;
import('./plot-marks.js').then(m => { Plot = m; if (lastRuns) renderRun(lastRuns, replay.tr); if (compareRuns) renderCompare(compareRuns, compareRuns.marketplace.length); })
  .catch(e => { for (const id of ['chart_delay', 'chart_timeline', 'chart_c1']) $(id).textContent = `The chart library could not load (${e.message}); the tables give the same numbers.`; });

// ---------- worker pool ----------
const N_WORKERS = Math.max(1, Math.min(4, (navigator.hardwareConcurrency || 2) - 1));
const workers = [], pending = new Map();
let msgId = 0;
for (let i = 0; i < N_WORKERS; i++) {
  const w = new Worker(ENGINE + 'worker.js');
  w.onmessage = e => { const m = e.data, p = pending.get(m.id); if (!p) return; if (m.type === 'progress') p.onProgress?.(m.done, m.total); else { pending.delete(m.id); p.resolve(m); } };
  w.onerror = e => console.error(e);
  workers.push(w);
}
function workerCall(msg, onProgress) { return new Promise(resolve => { const id = ++msgId; pending.set(id, { resolve, onProgress }); workers[id % workers.length].postMessage({ id, ...msg }); }); }
async function runSeeds(sc, mechName, seeds, opts, onProgress) {   // split seeds across workers; the first chunk carries the trace
  const chunks = [], per = Math.ceil(seeds.length / workers.length);
  for (let i = 0; i < seeds.length; i += per) chunks.push(seeds.slice(i, i + per));
  const progress = new Array(chunks.length).fill(0);
  const results = await Promise.all(chunks.map((ch, k) => workerCall({ type: 'run', scenario: sc, mechanism: mechName, seeds: ch, opts, trace: k === 0 },
    (done, total) => { progress[k] = done / total; onProgress?.(progress.reduce((a, b) => a + b, 0) / chunks.length); })));
  const runs = results.flatMap(r => r.runs).sort((a, b) => a.seed - b.seed);
  return [runs, results[0].trace ? readTrace(results[0].trace) : null];   // lunarsim-trace v1 -> replay model (formats.js)
}

// ---------- state and scenario controls ----------
const ui = { phase: 'P2', mech: 'marketplace' };
let fleet = JSON.parse(JSON.stringify(PRESETS[4]));
let lastRuns = null, compareRuns = null, scenarioName = 'lunarsim-live';
const replay = { tr: null, t: 0, playing: false, last: 0 };

const phaseSeg = segmented({ legend: 'Base phase (cargo landed a year)', options: [{ value: 'P1', label: 'Phase 1' }, { value: 'P2', label: 'Phase 2' }, { value: 'P3', label: 'Phase 3' }], value: ui.phase,
  onChange: v => { ui.phase = v; const ph = PHASES[v]; $('bulk').value = ph.bulk.reduce((s, b) => s + b[2], 0); $('ops').value = ph.nOps; $('ops_v').textContent = ph.nOps; notes(); } });
const mechSeg = segmented({ legend: 'How rovers get their jobs', options: Object.keys(MECHS).map(k => ({ value: k, label: MECH_LABEL[k] })), value: ui.mech, onChange: v => { ui.mech = v; notes(); } });
$('phase-host').append(phaseSeg.el); $('mech-host').append(mechSeg.el);
function notes() { $('phase-note').textContent = PHASE_TEXT[ui.phase]; $('mech-note').textContent = MECH_TEXT[ui.mech]; $('market').hidden = ui.mech !== 'marketplace'; }
notes();

function readScenario() { return Object.assign(makeScenario({ phase: ui.phase, bulkT: +$('bulk').value, fleet: fleet.map(f => ({ ...f })), night: +$('night').value, rtt: +$('rtt').value, nOps: +$('ops').value, duty: +$('duty').value, mtbf: +$('mtbf').value, std: +$('std').value }), { name: `lunarsim-live-${ui.phase}` }); }
function marketOpts() { return { bundling: $('c_bundling').checked, consolidate: $('c_consolidate').checked, team_lift: $('c_team').checked, night_aware: $('c_night').checked, anticipate: $('c_anticipate').checked, backhaul: $('c_backhaul').checked, priority: $('c_priority').checked }; }
function renderFleet() {
  const el = $('fleet'); el.replaceChildren();
  const sel = (i, k, label, pairs) => { const s = h('select', { 'aria-label': `${label}, rover ${i + 1}` }, pairs.map(([v, t]) => h('option', { value: v, selected: v === fleet[i][k] }, t))); s.addEventListener('change', () => { fleet[i][k] = s.value; }); return s; };
  fleet.forEach((f, i) => {
    const del = h('button', { class: 'ui-btn sim-del', type: 'button', 'aria-label': `Remove rover ${i + 1}` }, '×');
    del.addEventListener('click', () => { fleet.splice(i, 1); renderFleet(); });
    el.append(h('div', { class: 'veh' }, sel(i, 'owner', 'Owner', [['NASA', 'NASA'], ['CoA', 'Co. A'], ['CoB', 'Co. B'], ['CoC', 'Co. C']]), sel(i, 'cls', 'Rover type', [['LTV', 'LTV'], ['HAUL', 'HAUL'], ['MICRO', 'MICRO']]),
      sel(i, 'autonomy', 'Who drives', [['teleop', 'from Earth'], ['supervised', 'supervised'], ['autonomous', 'autonomous']]), del));
  });
}
$('preset').addEventListener('change', e => { fleet = JSON.parse(JSON.stringify(PRESETS[e.target.value])); renderFleet(); });
$('addveh').addEventListener('click', () => { fleet.push(LTV('CoC')); renderFleet(); });
for (const [id, fmt] of [['night', v => (+v).toFixed(2)], ['rtt', v => (+v).toFixed(1)], ['ops', v => v], ['duty', v => (+v).toFixed(2)], ['mtbf', v => (+v).toFixed(2)], ['std', v => (+v).toFixed(2)]]) {
  const inp = $(id), upd = () => { $(id + '_v').textContent = fmt(inp.value); }; inp.addEventListener('input', upd); upd();
}
renderFleet();

// ---------- tabs ----------
const TABS = [{ value: 'run', label: 'Run' }, { value: 'compare', label: 'Compare rules' }, { value: 'replay', label: 'Replay a year' }, { value: 'verify', label: 'Verification' }, { value: 'about', label: 'Method' }];
function showTab(v) {
  for (const t of TABS) $('tab-' + t.value).hidden = t.value !== v;
  if (v === 'replay') drawMap();
  try { localStorage.setItem('lunarsim.tab3', v); } catch (e) { /* storage blocked */ }
}
let tab0 = 'run'; try { tab0 = localStorage.getItem('lunarsim.tab3') || 'run'; } catch (e) { /* storage blocked */ }
if (!TABS.some(t => t.value === tab0)) tab0 = 'run';
const tabs = sceneChips({ label: 'Simulator view', scenes: TABS, value: tab0, onChange: showTab });
const vbadge = h('span', { class: 'sim-badge', id: 'vbadge', 'data-state': 'pending' }, 'verification not run');
$('sim-tabs').append(tabs.el, vbadge);
showTab(tab0);

// ---------- scenario and result files ----------
const UI_SLIDER_IDS = { night: 'night', rtt: 'rtt', nOps: 'ops', duty: 'duty', mtbf: 'mtbf', std: 'std' };
const UI_MARKET_IDS = { bundling: 'c_bundling', consolidate: 'c_consolidate', team_lift: 'c_team', night_aware: 'c_night', anticipate: 'c_anticipate', backhaul: 'c_backhaul', priority: 'c_priority' };
function readUi() { const u = { name: scenarioName, phase: ui.phase, bulk: +$('bulk').value, fleet: fleet.map(f => ({ ...f })), market: marketOpts() }; for (const [k, id] of Object.entries(UI_SLIDER_IDS)) u[k] = +$(id).value; return u; }
function applyUi(u) {   // sets the controls the file provides; returns notes for values a control could not hold exactly
  const out = [];
  if (u.phase !== undefined) { ui.phase = u.phase; phaseSeg.set(u.phase); }   // without the phase defaults for soil and drivers
  if (u.bulk !== undefined) { $('bulk').value = u.bulk; if (+$('bulk').value !== u.bulk) out.push(`bulk ${u.bulk} t/yr shown as ${$('bulk').value}`); }
  if (u.fleet !== undefined) { fleet = u.fleet.map(f => ({ ...f })); renderFleet(); }
  for (const [k, id] of Object.entries(UI_SLIDER_IDS)) if (u[k] !== undefined) {
    const el = $(id); el.value = u[k]; el.dispatchEvent(new Event('input'));
    if (Math.abs(+el.value - u[k]) > 1e-9) out.push(`${el.labels[0] ? el.labels[0].firstChild.textContent.trim() : id}: ${u[k]} is outside the slider's range or step; set to ${el.value}`);
  }
  if (u.market) for (const [k, id] of Object.entries(UI_MARKET_IDS)) if (u.market[k] !== undefined) $(id).checked = u.market[k];
  if (u.name !== undefined) scenarioName = u.name;
  notes();
  return out;
}
function showScenarioNote(list) { const el = $('scnote'); el.hidden = !list.length; el.innerHTML = list.length ? '<b>Approximated on import:</b><ul>' + list.map(n => `<li>${esc(n)}</li>`).join('') + '</ul>' : ''; }
$('exportScenario').addEventListener('click', () => { const j = uiToScenario(readUi()); download(`${j.name.replace(/[^\w.-]+/g, '-')}.json`, JSON.stringify(j, null, 2), 'application/json'); });
$('importScenario').addEventListener('change', e => {
  const f = e.target.files[0]; if (!f) return; const r = new FileReader();
  r.onload = () => {
    try { const { form, ui: u, notes: n } = scenarioToUi(String(r.result)); if (u.name === undefined) u.name = f.name.replace(/\.json$/i, ''); const all = n.concat(applyUi(u)); showScenarioNote(all);
      status(`Loaded scenario "${u.name || f.name}" (${form} form${all.length ? `, ${all.length} approximation${all.length > 1 ? 's' : ''}: see the note` : ''}).`); }
    catch (err) { status(`Could not read ${f.name}: ${err.message}. Controls unchanged.`); }
  };
  r.onerror = () => status(`Could not read ${f.name}.`);
  r.readAsText(f); e.target.value = '';
});
function download(name, text, type) {
  try { const url = URL.createObjectURL(new Blob([text], { type })), a = h('a', { href: url, download: name }); document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 2000); }
  catch (e) { navigator.clipboard?.writeText(text); status('Download blocked here; content copied to the clipboard instead.'); }
}
function toCsv(rows) { if (!rows.length) return ''; const keys = Object.keys(rows[0]).filter(k => typeof rows[0][k] !== 'object'); return [keys.join(',')].concat(rows.map(r => keys.map(k => r[k]).join(','))).join('\n'); }
$('exportRuns').addEventListener('click', () => { if (lastRuns) download('lunarsim-runs.csv', toCsv(lastRuns), 'text/csv'); });
$('exportCompare').addEventListener('click', () => { if (compareRuns) download('lunarsim-compare.csv', toCsv(Object.entries(compareRuns).flatMap(([m, rs]) => rs.map(r => ({ mechanism: m, ...r })))), 'text/csv'); });
const status = m => { $('status').textContent = m; };

// ---------- run ----------
$('run').addEventListener('click', async () => {
  const sc = readScenario(), mechName = ui.mech, n = Math.max(1, Math.min(500, +$('seeds').value)), seeds = Array.from({ length: n }, (_, i) => i);
  setBusy(true, 'running…'); const t0 = performance.now();
  const [runs, trace] = await runSeeds(sc, mechName, seeds, mechName === 'marketplace' ? marketOpts() : {}, p => { $('prog').value = p; });
  lastRuns = runs;
  setBusy(false, `${n} simulated year${n > 1 ? 's' : ''} with ${MECH_LABEL[mechName]} in ${((performance.now() - t0) / 1000).toFixed(1)} s (${workers.length} background worker${workers.length > 1 ? 's' : ''}).`);
  renderRun(runs, trace); setupReplay(trace);
});
$('runprec').addEventListener('click', async () => {
  const sc = readScenario(), mechName = ui.mech, opts = mechName === 'marketplace' ? marketOpts() : {}; let runs = [], trace0 = null, n = 0;
  setBusy(true, 'running…'); const t0 = performance.now();
  for (;;) {
    const seeds = Array.from({ length: 40 }, (_, i) => n + i), [r, tr] = await runSeeds(sc, mechName, seeds, opts, null); if (!trace0) trace0 = tr; runs = runs.concat(r); n += 40;
    const vals = runs.map(x => x.delay_prio1_mean_h), hw = ci99(vals), m = mean(vals), rel = hw / Math.abs(m);
    status(`${n} years: average urgent wait ${fmtN(m, 2)} h, 99 % interval ±${fmtN(hw, 2)} h (${(100 * rel).toFixed(2)} % of the average)`); $('prog').value = Math.min(1, 0.02 / Math.max(rel, 1e-9)); renderRun(runs, trace0);
    if ((rel <= 0.02 && n >= 80) || n >= 2000) break;
  }
  lastRuns = runs; setupReplay(trace0); setBusy(false, $('status').textContent + ` — stopped after ${n} simulated years in ${((performance.now() - t0) / 1000).toFixed(0)} s.`);
});
function setBusy(b, msg) { for (const id of ['run', 'runprec', 'runpy', 'compare']) $(id).disabled = b; $('prog').hidden = !b; if (b) $('prog').value = 0; if (msg) status(msg); }

// results as stat chips: the average over the simulated years, with its 95 % interval under it
const KPIS = [['Urgent cargo: 90 % delivered within', 'delay_prio1_p90_h', 1, 1, 'h', 'cool'], ['Urgent cargo delivered within 24 h (share)', 'sl24_prio1', 3, 1, ''], ['Landed cargo no rover can move', 'immovable_share', 1, 100, '% of mass'],
  ['Rover trips per year', 'jobs', 0, 1, ''], ['Rovers caught out by darkness (per year)', 'night_strandings', 2, 1, ''], ['Driver hours on Earth per year', 'operator_hours', 0, 1, 'h'],
  ['Cost per kg moved (US $)', 'cost_per_kg_usd', 0, 1, ''], ['Cost per kg of landed cargo (US $)', 'cost_per_landed_kg_usd', 0, 1, ''], ['Team lifts per year (2–3 rovers, one item)', 'team_lifts', 1, 1, ''], ['Share of time the fleet is busy', 'utilisation', 3, 1, '']];
function chip(label, vals, digits, unit, tone, src) {
  const m = mean(vals), c = statChip({ label, value: +m.toFixed(digits), unit, flag: 'Modelled', digits, tone, source: `${src}; 95 % interval ±${fmtN(ci95(vals), digits)}` });
  c.el.append(h('span', { class: 'sim-ci' }, `± ${fmtN(ci95(vals), digits)} · 95 % CI · n = ${vals.length}`));
  return c.el;
}
function renderRun(runs, trace) {
  $('kpis').replaceChildren(...KPIS.map(([lab, key, d, scale, unit, tone]) => chip(lab, runs.map(r => r[key] * scale), d, unit, tone, SRC(runs.length))));
  const labs = ['consumables', 'science', 'equipment', 'infrastructure', 'element', 'bulk', 'return'], cols = ['--s8', '--s3', '--s1', '--s6', '--s4', '--muted', '--s5'].map(css);
  const rows = labs.map((l, i) => { const v = runs.map(r => r.delay_by_class[l]).filter(Number.isFinite); return { cls: l[0].toUpperCase() + l.slice(1), m: mean(v), ci: ci95(v), col: cols[i] }; }).filter(r => Number.isFinite(r.m));
  if (Plot) plot($('chart_delay'), {
    height: 270, marginLeft: 46, marginBottom: 56, x: { label: null, domain: rows.map(r => r.cls), tickRotate: -35 }, y: { label: 'hours', grid: true, zero: true },
    marks: [Plot.barY(rows, { x: 'cls', y: 'm', fill: 'col', rx: 3, title: r => `${r.cls}: ${fmtN(r.m, 2)} ± ${fmtN(r.ci, 2)} h` }),
      Plot.ruleX(rows, { x: 'cls', y1: r => Math.max(0, r.m - r.ci), y2: r => r.m + r.ci, stroke: css('--ink-2') }),
      Plot.text(rows, { x: 'cls', y: r => r.m + r.ci, text: r => fmtN(r.m, r.m < 20 ? 1 : 0), dy: -8, fill: css('--ink') })],
  });
  if (trace && Plot) timelineChart(trace);
  const keys = [['seed', 'Year (seed)', 0], ['delay_prio1_p90_h', 'Urgent 90 % (h)', 1], ['delay_prio1_mean_h', 'Urgent avg (h)', 2], ['sl24_prio1', 'Within 24 h', 3], ['immovable_share', 'Can\'t move', 3], ['jobs', 'Trips', 0], ['bundled_jobs', 'Shared trips', 0], ['team_lifts', 'Team lifts', 0], ['repositions', 'Sent to pad', 0], ['night_strandings', 'Caught by dark', 0], ['faults', 'Breakdowns', 0], ['operator_hours', 'Driver h', 0], ['landed_kg', 'Landed kg', 0], ['delivered_kg', 'Delivered kg', 0], ['backlog_kg', 'Still waiting kg', 0]];
  $('seedtable').innerHTML = '<tr>' + keys.map(k => `<th class="n" scope="col">${k[1]}</th>`).join('') + '</tr>' + runs.slice(0, 200).map(r => '<tr>' + keys.map(k => `<td class="n">${fmtN(r[k[0]], k[2])}</td>`).join('') + '</tr>').join('');
}
function plot(host, spec) {
  const w = Math.max(280, host.clientWidth || 560);
  const fig = Plot.plot({ width: w, style: { background: 'transparent', color: css('--ink-2'), fontFamily: 'inherit', fontSize: '11px' }, ...spec });
  fig.querySelectorAll('g[aria-label]').forEach(g => g.removeAttribute('aria-label'));   // aria-label on a plain <g> is prohibited (axe)
  const svg = fig.tagName === 'svg' ? fig : fig.querySelector('svg'), title = host.closest('figure')?.querySelector('h3')?.textContent;
  if (svg && title) { svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', `${title} (the tables give the same numbers)`); }
  host.replaceChildren(fig);
}
function timelineChart(tr) {
  const items = tr.cargo.filter(c => c.tDelivered !== null).map(c => ({ day: c.tReady / 24, d: Math.max(0.5, c.tDelivered - c.tReady), prio: c.prio, label: `${c.cls} ${fmtN(c.mass, 0)} kg → ${c.dest}\nready day ${Math.floor(c.tReady / 24)}, waited ${fmtN(c.tDelivered - c.tReady, 1)} h` }));
  const nights = tr.nights.map(([a, b]) => ({ a: Math.max(0, a) / 24, b: Math.min(tr.horizon, b) / 24 })).filter(n => n.b > n.a);
  const col = { 1: css('--s8'), 2: css('--s3'), 3: css('--muted') }, name = { 1: 'urgent', 2: 'normal', 3: 'bulk' };
  plot($('chart_timeline'), {
    height: 260, marginLeft: 46, x: { label: 'day', domain: [0, tr.horizon / 24] }, y: { type: 'log', label: 'waited (h, log)', grid: true, domain: [0.5, Math.max(100, ...items.map(i => i.d)) * 1.3] },
    color: { domain: ['urgent', 'normal', 'bulk'], range: [col[1], col[2], col[3]], legend: true },
    marks: [Plot.rectX(nights, { x1: 'a', x2: 'b', fill: css('--ink'), fillOpacity: 0.14 }),
      Plot.ruleX(tr.landings, { x: l => l[0] / 24, y1: 0.5, y2: 0.75, stroke: css('--s2'), strokeWidth: 1.6, title: l => `${l[1]} landing, day ${Math.floor(l[0] / 24)}` }),
      Plot.dot(items, { x: 'day', y: 'd', r: i => (i.prio === 3 ? 1.7 : 2.6), fill: i => name[i.prio], fillOpacity: 0.85, title: 'label' })],
  });
}

// ---------- compare: one answer card per job rule ----------
$('compare').addEventListener('click', async () => {
  const sc = readScenario(), n = Math.max(1, Math.min(500, +$('seeds').value)), seeds = Array.from({ length: n }, (_, i) => i), res = {}, t0 = performance.now();
  setBusy(true, 'comparing…');
  for (const mn of Object.keys(MECHS)) { $('cstatus').textContent = `running ${MECH_LABEL[mn]}…`; [res[mn]] = await runSeeds(sc, mn, seeds, mn === 'marketplace' ? marketOpts() : {}, null); }
  compareRuns = res; setBusy(false, 'comparison done.'); $('cstatus').textContent = `done in ${((performance.now() - t0) / 1000).toFixed(1)} s (${n} simulated years × 4 rules).`; renderCompare(res, n);
});
function renderCompare(res, n) {
  const mn = Object.keys(res), avg = (m, key, s = 1) => mean(res[m].map(r => r[key] * s)), ci = (m, key, s = 1) => ci95(res[m].map(r => r[key] * s));
  const best = mn.reduce((a, b) => (avg(b, 'delay_prio1_p90_h') < avg(a, 'delay_prio1_p90_h') ? b : a));
  const rank = [...mn].sort((a, b) => avg(a, 'delay_prio1_p90_h') - avg(b, 'delay_prio1_p90_h'));
  $('ccards').replaceChildren(...mn.map(m => {
    const p90 = avg(m, 'delay_prio1_p90_h'), r = rank.indexOf(m) + 1;
    return h('article', { class: 'ui-glass sim-answer', 'data-best': String(m === best), style: `--rule: ${css(MECH_COLOR[m].replace(/var\((--s\d)\)/, '$1'))}` },
      h('p', { class: 'ui-label' }, `${r === 1 ? 'Fastest for urgent cargo' : `${['', '', 'Second', 'Third', 'Fourth'][r]} fastest`}`),
      h('h3', { class: 'sim-answer-rule' }, MECH_LABEL[m]),
      h('p', { class: 'sim-answer-q' }, 'Urgent cargo: 90 % delivered within'),
      h('p', { class: 'sim-answer-a' }, h('span', { class: 'v' }, fmtN(p90, 1)), h('span', { class: 'u' }, ' h'), h('span', { class: 'sim-ci' }, ` ± ${fmtN(ci(m, 'delay_prio1_p90_h'), 1)}`)),
      h('dl', { class: 'sim-answer-dl' },
        h('dt', {}, 'Urgent within 24 h'), h('dd', {}, `${fmtN(100 * avg(m, 'sl24_prio1'), 0)} %`),
        h('dt', {}, 'Cargo no rover can move'), h('dd', {}, `${fmtN(avg(m, 'immovable_share', 100), 1)} % of mass`),
        h('dt', {}, 'Rovers caught by the dark'), h('dd', {}, `${fmtN(avg(m, 'night_strandings'), 2)} a year`),
        h('dt', {}, 'Trips'), h('dd', {}, `${fmtN(avg(m, 'jobs'), 0)} a year`)),
      h('p', { class: 'sim-answer-note' }, MECH_TEXT[m]));
  }));
  // paired differences: the same simulated years under two rules
  const paired = (a, b, key, d = 2) => { const diff = res[a].map((r, i) => r[key] - res[b][i][key]); return [mean(diff), ci95(diff), d]; };
  const vs = `${MECH_LABEL.marketplace} minus ${MECH_LABEL.pooled_greedy}`;
  const diffChip = (label, [m, c, d], unit) => { const s = statChip({ label, value: +m.toFixed(d), unit, flag: 'Modelled', digits: d, source: `${SRC(n)}; difference on the same years, 95 % interval ±${fmtN(c, d)}` }); s.el.append(h('span', { class: 'sim-ci' }, `± ${fmtN(c, d)} · difference on the same years · n = ${n}`)); return s.el; };
  $('ckpis').replaceChildren(diffChip(`${vs}: urgent 90 % delivered within`, paired('marketplace', 'pooled_greedy', 'delay_prio1_p90_h'), 'h'), diffChip(`${vs}: urgent share within 24 h`, paired('marketplace', 'pooled_greedy', 'sl24_prio1', 3), ''),
    diffChip(`${vs}: trips per year`, paired('marketplace', 'pooled_greedy', 'jobs', 1), ''), diffChip(`${MECH_LABEL.marketplace} minus ${MECH_LABEL.inhouse}: urgent 90 % delivered within`, paired('marketplace', 'inhouse', 'delay_prio1_p90_h'), 'h'));
  const rows = mn.map(m => ({ rule: MECH_LABEL[m], m: avg(m, 'delay_prio1_p90_h'), c: ci(m, 'delay_prio1_p90_h'), col: css(MECH_COLOR[m].replace(/var\((--s\d)\)/, '$1')) }));
  $('cfig').hidden = false;
  if (Plot) plot($('chart_c1'), { height: 220, marginLeft: 46, x: { label: null, domain: rows.map(r => r.rule) }, y: { label: 'hours', grid: true, zero: true },
    marks: [Plot.barY(rows, { x: 'rule', y: 'm', fill: 'col', rx: 3, title: r => `${r.rule}: ${fmtN(r.m, 2)} ± ${fmtN(r.c, 2)} h` }), Plot.ruleX(rows, { x: 'rule', y1: r => Math.max(0, r.m - r.c), y2: r => r.m + r.c, stroke: css('--ink-2') }),
      Plot.text(rows, { x: 'rule', y: r => r.m + r.c, text: r => fmtN(r.m, 1), dy: -8, fill: css('--ink') })] });
  const keys = [['delay_prio1_p90_h', 'Urgent 90 % (h)', 1], ['delay_prio1_mean_h', 'Urgent avg (h)', 2], ['sl24_prio1', 'Within 24 h', 3], ['immovable_share', 'Can\'t move', 3], ['backlog_kg', 'Still waiting kg', 0], ['jobs', 'Trips', 0], ['bundled_jobs', 'Shared trips', 0], ['team_lifts', 'Team lifts', 1], ['night_strandings', 'Caught by dark', 2], ['operator_hours', 'Driver h', 0], ['empty_km_share', 'Empty km share', 3], ['revenue_gini', 'Revenue inequality (Gini)', 2], ['cost_per_kg_usd', '$/kg moved', 0]];
  $('ctablecard').hidden = false;
  $('ctable').innerHTML = '<tr><th scope="col">Rule</th>' + keys.map(k => `<th class="n" scope="col">${k[1]}</th>`).join('') + '</tr>' + mn.map(m => `<tr${m === 'marketplace' ? ' class="hl"' : ''}><th scope="row">${MECH_LABEL[m]}</th>` + keys.map(k => `<td class="n">${fmtN(avg(m, k[0]), k[2])} <span class="muted">±${fmtN(ci(m, k[0]), k[2])}</span></td>`).join('') + '</tr>').join('');
}

// ---------- replay ----------
function setupReplay(tr, source) {
  if (!tr) return;
  Object.assign(replay, { tr, t: 0, playing: false }); $('play').textContent = 'Play'; $('tslider').max = Math.floor(tr.horizon); $('tslider').value = 0;
  const owners = [...new Set(tr.vehicles.map(v => v.owner))];
  $('maplegend').innerHTML = owners.map((o, i) => `<span style="--c: var(--s${(i % 8) + 1})">${esc(o)}</span>`).join('') + '<span style="--c: var(--s2)">landing pad</span><span style="--c: var(--night)">night</span>';
  const m = tr.meta || {}, val = x => (x === null || x === undefined || x === '' ? '–' : esc(x));
  $('replayhead').innerHTML = `<span>engine <b>${val(m.engine)}</b></span><span>scenario <b>${val(m.scenario)}</b></span><span>job rule <b>${val(MECH_LABEL[m.mechanism] || m.mechanism)}</b></span><span>year (seed) <b>${val(m.seed)}</b></span><span class="muted">${source ? (source.startsWith('sample ') ? 'bundled ' : 'from file ') + esc(source) + (m.legacy ? ' (no format header; read as v1)' : '') : 'from the last run'}</span>`;
  $('exportTrace').disabled = false; $('openWorld').disabled = false; drawMap();
}
function loaded(tr, label) { return `Loaded ${label}: ${tr.vehicles.length} vehicles, ${tr.jobs.length} trips, ${tr.cargo.length} cargo items, ${tr.landings.length} landings, ${tr.nights.length} nights.`; }
$('importTrace').addEventListener('change', e => {
  const f = e.target.files[0]; if (!f) return; const r = new FileReader();
  r.onload = () => { try { const tr = readTrace(String(r.result)); setupReplay(tr, f.name); $('rstatus').textContent = loaded(tr, f.name); } catch (err) { $('rstatus').textContent = `Could not read ${f.name}: ${err.message}. The previous replay is unchanged.`; } };
  r.onerror = () => { $('rstatus').textContent = `Could not read ${f.name}.`; };
  r.readAsText(f); e.target.value = '';
});
$('sampleTrace').addEventListener('change', async e => {   // bundled Python traces, fetched on demand only
  const file = e.target.value; if (!file) return; const label = e.target.selectedOptions[0].textContent; e.target.disabled = true; $('rstatus').textContent = `Loading ${label}…`;
  try {
    let res; try { res = await fetch(ENGINE + 'samples/' + file); } catch (err) { throw new Error('the sample could not be fetched (network error)'); }
    if (!res.ok) throw new Error(`the sample is not available here (HTTP ${res.status})`);
    const tr = readTrace(await res.text()); setupReplay(tr, 'sample ' + file); $('rstatus').textContent = loaded(tr, label);
  } catch (err) { $('rstatus').textContent = `Could not load ${label}: ${err.message}. The previous replay is unchanged.`; }
  finally { e.target.disabled = false; e.target.value = ''; }
});
// "Full 3D replay on GitHub": the run-queue issue form (.github/ISSUE_TEMPLATE/run-scenario.yml) prefilled through URL
// query parameters keyed by its field ids; dropdown values must match the form's option text. What the form cannot hold
// (soil, duty, reliability, interface share, a custom fleet) is written into its Purpose box.
const GH_FORM = 'https://github.com/azizjonrahimov/Lunar-Haul/issues/new';
function ghLink() {
  const n = Math.max(1, Math.min(500, +$('seeds').value || 1)), def = { P2: '6', P3: '9' }[ui.phase], pre = $('preset').value;
  const fleetDesc = fleet.map(f => `${f.cls} (${f.owner}, ${{ teleop: 'from Earth', supervised: 'supervised', autonomous: 'autonomous' }[f.autonomy]})`).join(', ');
  const same = JSON.stringify(fleet) === JSON.stringify(PRESETS[pre]);
  const fleetOpt = same && pre === def ? 'phase default' : same && ui.phase === 'P2' && ['2', '4', '6', '8'].includes(pre) ? `P2: ${pre} vehicles` : 'phase default';
  const q = new URLSearchParams({ template: 'run-scenario.yml', title: `Run: ${ui.phase} ${ui.mech} (from the browser simulator)`, phase: ui.phase, fleet: fleetOpt, mechanism: ui.mech,
    night_fraction: (+$('night').value).toFixed(2), rtt_s: (+$('rtt').value).toFixed(1), n_operators: $('ops').value, seeds: String(n),
    purpose: `Opened from the browser simulator (/simulator/). Settings the form has no field for: Moon soil ${$('bulk').value} t a year; owner's other work ${(+$('duty').value).toFixed(2)}; reliability ${(+$('mtbf').value).toFixed(2)} x normal; standard interface share ${(+$('std').value).toFixed(2)}${ui.mech === 'marketplace' ? `; marketplace features: ${Object.entries(marketOpts()).filter(([, v]) => !v).map(([k]) => k).join(', ') || 'all on'}${Object.values(marketOpts()).some(v => !v) ? ' off' : ''}` : ''}. Browser fleet: ${fleetDesc}${fleetOpt === 'phase default' && !(same && pre === def) ? ' (the form has no field for it; the run uses the phase default)' : ''}.` });
  return `${GH_FORM}?${q}`;
}
for (const el of document.querySelectorAll('#tab-run, .sim-rail')) el.addEventListener('input', () => { $('ghRun').href = ghLink(); });
$('ghRun').addEventListener('pointerdown', () => { $('ghRun').href = ghLink(); });
$('ghRun').addEventListener('focus', () => { $('ghRun').href = ghLink(); });
$('ghRun').href = ghLink();
// "Trace replay of this run": the trace goes to the site's 3D trace viewer on the LOLA terrain (same origin)
$('openWorld').addEventListener('click', () => {
  if (!replay.tr) return;
  try { localStorage.setItem('lunarsim.worldTrace', JSON.stringify(traceToJson(replay.tr))); }
  catch (e) { $('rstatus').textContent = 'This browser would not store the trace (storage full or blocked); use "Export this trace" and load the file in the 3D world instead.'; return; }
  location.href = BASE + 'world/trace/?from=simulator';
});
$('exportTrace').addEventListener('click', () => {
  if (!replay.tr) return; const m = replay.tr.meta || {};
  const name = ['lunarsim-trace', m.scenario, m.mechanism, m.seed === null || m.seed === undefined ? null : 'seed' + m.seed].filter(x => x !== null && x !== undefined && x !== '').join('_').replace(/[^\w.-]+/g, '-') + '.json';
  download(name, JSON.stringify(traceToJson(replay.tr)), 'application/json'); $('rstatus').textContent = `Exported ${name}.`;
});
// F-50: the shared time scale, 5 min a second to start; keys work while the Replay tab is open
const ts = createTimescale({ speeds: [60, 300, 900, 3600, 21600, 86400, 259200], value: 300, id: 'speed', active: () => !$('tab-replay').hidden, onPlayPause: () => { if (replay.tr) $('play').click(); } });
$('speed-host').replaceWith(ts.el);
$('tslider').addEventListener('input', e => { replay.t = +e.target.value; drawMap(); });
$('play').addEventListener('click', () => { replay.playing = !replay.playing; $('play').textContent = replay.playing ? 'Pause' : 'Play'; if (replay.playing) { replay.last = performance.now(); requestAnimationFrame(tick); } });
function tick(now) {
  if (!replay.playing || !replay.tr) return;
  replay.t += (now - replay.last) / 1000 * ts.h; replay.last = now;
  if (replay.t >= replay.tr.horizon) { replay.t = replay.tr.horizon; replay.playing = false; $('play').textContent = 'Play'; }
  $('tslider').value = Math.floor(replay.t); drawMap(); if (replay.playing) requestAnimationFrame(tick);
}
function sitePos(name, W, H) {
  const s = WORLD.sites[name], xs = SITES.map(q => q.x), ys = SITES.map(q => q.y);
  const minx = Math.min(...xs) - 0.5, maxx = Math.max(...xs) + 0.6, miny = Math.min(...ys) - 0.5, maxy = Math.max(...ys) + 0.5, scale = Math.min((W - 60) / (maxx - minx), (H - 60) / (maxy - miny));
  return [30 + (s.x - minx) * scale, H - 30 - (s.y - miny) * scale];
}
function vehiclePos(v, tr, t, W, H) {
  let loc = 'DEPOT', loaded = 0, pos = null;
  for (const j of tr.jobs) {
    if (!j.team.includes(v.id)) continue; if (t < j.t0) break;
    if (t >= j.t1) { const sg = j.segments[j.segments.length - 1]; loc = sg ? sg[1] : loc; continue; }
    for (const [a, b, s0, s1, kg] of j.segments) {
      if (t < s0 || t > s1) continue;
      loaded = kg;
      if (a === b) loc = a;
      else {
        const path = WORLD.path(a, b), total = WORLD.distance(a, b); let dcum = (t - s0) / Math.max(1e-9, s1 - s0) * total;
        for (let i = 0; i + 1 < path.length; i++) { const d = WORLD.edges[path[i] + '|' + path[i + 1]].dist; if (dcum <= d) { const [x0, y0] = sitePos(path[i], W, H), [x1, y1] = sitePos(path[i + 1], W, H), f = dcum / d; pos = [x0 + f * (x1 - x0), y0 + f * (y1 - y0)]; break; } dcum -= d; }
        if (!pos) pos = sitePos(b, W, H);
      }
      break;
    }
    break;
  }
  return { pos: pos || sitePos(loc, W, H), loaded };
}
function drawMap() {
  const cv = $('map'); if (!cv || $('tab-replay').hidden) return;
  const ctx = cv.getContext('2d'), W = cv.width, H = cv.height, tr = replay.tr, t = replay.t, font = getComputedStyle(document.body).fontFamily, mono = css('--font-num') || 'monospace';
  ctx.clearRect(0, 0, W, H); ctx.fillStyle = css('--bg-2'); ctx.fillRect(0, 0, W, H);
  const slopeCol = { flat: css('--tol-cyan'), moderate: css('--s4'), steep: css('--s8') };
  for (const [a, b, sl] of EDGES) {
    const [x0, y0] = sitePos(a, W, H), [x1, y1] = sitePos(b, W, H);
    ctx.strokeStyle = slopeCol[sl]; ctx.lineWidth = sl === 'steep' ? 8 : sl === 'moderate' ? 6 : 4; ctx.lineCap = 'round'; ctx.globalAlpha = 0.8; ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke(); ctx.globalAlpha = 1;
    ctx.fillStyle = css('--ink-3'); ctx.font = `11px ${mono}`; ctx.fillText(WORLD.edges[a + '|' + b].dist.toFixed(1) + ' km', (x0 + x1) / 2 + 5, (y0 + y1) / 2 - 5);
  }
  const night = tr && tr.nights.some(([a, b]) => t >= a && t < b); if (night) { ctx.fillStyle = css('--night'); ctx.fillRect(0, 0, W, H); }
  const waiting = {}; if (tr) for (const c of tr.cargo) if (c.tReady <= t && (c.tPicked === null || c.tPicked > t) && !c.stranded) waiting[c.origin] = (waiting[c.origin] || 0) + 1;
  for (const s of SITES) {
    const [x, y] = sitePos(s.name, W, H), w = waiting[s.name] || 0;
    if (w) { ctx.strokeStyle = css('--s2'); ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(x, y, 16 + Math.min(34, 3 * w), 0, 2 * Math.PI); ctx.stroke(); ctx.fillStyle = css('--s2'); ctx.font = `600 12px ${font}`; ctx.fillText(w + ' waiting', x + 20 + Math.min(34, 3 * w), y - 12); }
    ctx.fillStyle = s.kind === 'pad' ? css('--s2') : s.kind === 'base' ? css('--s1') : css('--ink-2'); ctx.beginPath(); if (s.kind === 'pad') ctx.rect(x - 10, y - 10, 20, 20); else ctx.arc(x, y, 9, 0, 2 * Math.PI); ctx.fill();
    ctx.fillStyle = css('--ink'); ctx.font = `600 13px ${font}`; ctx.fillText(s.name.replace('_', ' '), x + 14, y + 5);
  }
  if (tr) for (const [tl, name, pad] of tr.landings) if (t >= tl && t < tl + 72) { const [x, y] = sitePos(pad, W, H); ctx.strokeStyle = css('--s2'); ctx.lineWidth = 2; ctx.setLineDash([5, 5]); ctx.beginPath(); ctx.arc(x, y, 30, 0, 2 * Math.PI); ctx.stroke(); ctx.setLineDash([]); ctx.fillStyle = css('--s2'); ctx.font = `12px ${font}`; ctx.fillText(name + ' landed', x - 34, y + 48); }
  if (tr) {
    const owners = [...new Set(tr.vehicles.map(v => v.owner))];
    for (const v of tr.vehicles) {
      const { pos: [x, y], loaded } = vehiclePos(v, tr, t, W, H), c = css(`--s${(owners.indexOf(v.owner) % 8) + 1}`), r = v.cls === 'HAUL' ? 12 : v.cls === 'LTV' ? 9 : 6.5, ox = (v.id % 3) * 5 - 5, oy = Math.floor(v.id / 3) * 5 - 5;
      ctx.beginPath(); ctx.arc(x + ox, y + oy, r, 0, 2 * Math.PI); ctx.fillStyle = loaded > 0 ? c : css('--panel'); ctx.strokeStyle = c; ctx.lineWidth = 2.5; ctx.fill(); ctx.stroke();
      if (loaded > 0) { ctx.fillStyle = css('--ink'); ctx.font = `10.5px ${mono}`; ctx.fillText(Math.round(loaded) + ' kg', x + ox + r + 3, y + oy + 4); }
    }
  }
  $('clock').textContent = `day ${Math.floor(t / 24)}, ${String(Math.floor(t % 24)).padStart(2, '0')}:00${night ? ' · night' : ''}`;
  if (tr) { const delivered = tr.cargo.filter(c => c.tDelivered !== null && c.tDelivered <= t).length, waitingN = Object.values(waiting).reduce((a, b) => a + b, 0), jobsSoFar = tr.jobs.filter(j => j.t0 <= t).length;
    $('replaystats').textContent = `${delivered} items delivered so far · ${waitingN} waiting · ${jobsSoFar} trips started · ${tr.landings.filter(l => l[0] <= t).length} of ${tr.landings.length} landings so far`; }
}
new MutationObserver(() => drawMap()).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });   // the map's colours follow the theme

// ---------- verification ----------
const pill = ok => `<span class="sim-pill" data-ok="${ok}">${ok ? 'PASS' : 'FAIL'}</span>`;
$('verify').addEventListener('click', async () => {
  $('vstatus').textContent = 'running…'; const { checks } = await workerCall({ type: 'verify' }), np = checks.filter(c => c.passed).length;
  $('vstatus').textContent = `${np} of ${checks.length} checks passed.`; vbadge.textContent = `${np}/${checks.length} checks pass`; vbadge.dataset.state = np === checks.length ? 'pass' : 'fail';
  $('vtable').innerHTML = '<tr><th scope="col">Check</th><th class="n" scope="col">Expected</th><th class="n" scope="col">Simulated</th><th class="n" scope="col">Error</th><th class="n" scope="col">Allowed</th><th scope="col">Where the expected value comes from</th><th scope="col">Result</th></tr>' +
    checks.map(c => `<tr><td>${c.name}</td><td class="n">${fmtN(c.ref, 4)} ${c.unit}</td><td class="n">${fmtN(c.sim, 4)} ${c.unit}</td><td class="n">${(100 * c.err).toFixed(3)}%</td><td class="n">${(100 * c.tol).toFixed(1)}%</td><td class="small">${c.basis}</td><td>${pill(c.passed)}</td></tr>`).join('');
});
const XCHECK_KEYS = [['delay_prio1_mean_h', 'Urgent cargo, average wait (h)'], ['delay_prio1_p90_h', 'Urgent cargo, 90 % delivered within (h)'], ['sl24_prio1', 'Urgent cargo within 24 h (share)'], ['jobs', 'Trips per year'], ['night_strandings', 'Rovers caught out by darkness'], ['delivered_share', 'Share of cargo delivered']];
$('xcheck').addEventListener('click', async () => {
  const live = $('xlive').checked && PY_API.connected, REF = window.PY_REF || null;
  if (!live && !REF) { $('xstatus').textContent = 'No Python reference embedded in this build. Connect a local engine in the Engine card to run it live.'; return; }
  $('xcheck').disabled = true;
  const sc = makeScenario({ phase: 'P2', bulkT: 500, fleet: PRESETS[6], night: 0.15, rtt: 5, nOps: 3, duty: 0.3, mtbf: 1, std: 1 }), seeds = Array.from({ length: 30 }, (_, i) => i), rows = [];
  const pyJob = live ? PY_API.compare('P2-default', seeds, {}) : null; if (pyJob) pyJob.catch(() => {});   // awaited below
  const jsRuns = {}; for (const mn of Object.keys(MECHS)) { $('xstatus').textContent = `browser: running ${MECH_LABEL[mn]}…${live ? ' (Python engine running in parallel)' : ''}`; [jsRuns[mn]] = await runSeeds(sc, mn, seeds, {}, null); }
  let ref = REF, src = 'embedded reference (paper E1 suite)';
  if (live) {
    $('xstatus').textContent = 'waiting for the Python engine…';
    try { const res = await pyJob; ref = {}; for (const mn of Object.keys(MECHS)) { const pr = (res.runs[mn] || []).map(pyRowToPage); ref[mn] = {}; for (const [key] of XCHECK_KEYS) { const v = pr.map(r => r[key]); ref[mn][key] = { mean: mean(v), ci: ci95(v), n: v.length }; } } src = `live Python engine at ${PY_API.base}, same seeds 0–29, ${(res.ms / 1000).toFixed(1)} s`; }
    catch (err) { engineFailed(err); $('xcheck').disabled = false; $('xstatus').textContent = `Python engine failed: ${err.message}. Untick the live option to use the embedded reference.`; return; }
  }
  for (const mn of Object.keys(MECHS)) for (const [key, lab] of XCHECK_KEYS) { const js = jsRuns[mn].map(r => r[key]), r0 = ref[mn] && ref[mn][key]; if (!r0) continue; const mj = mean(js), cj = ci95(js); rows.push({ mn, lab, mj, cj, ref: r0, overlap: Math.abs(mj - r0.mean) <= (cj + r0.ci) }); }
  $('xcheck').disabled = false; $('xstatus').textContent = `${rows.filter(r => r.overlap).length} of ${rows.length} numbers agree within their combined 95 % intervals. Python side: ${src}.`;
  $('xtable').innerHTML = '<tr><th scope="col">Job rule</th><th scope="col">Number</th><th class="n" scope="col">Browser (average ± 95 %)</th><th class="n" scope="col">Python (average ± 95 %)</th><th scope="col">Agree</th></tr>' +
    rows.map(r => `<tr><td>${MECH_LABEL[r.mn]}</td><td>${r.lab}</td><td class="n">${fmtN(r.mj, 2)} ± ${fmtN(r.cj, 2)}</td><td class="n">${fmtN(r.ref.mean, 2)} ± ${fmtN(r.ref.ci, 2)}</td><td>${pill(r.overlap).replace('PASS', 'yes').replace('FAIL', 'no')}</td></tr>`).join('');
});

// ---------- optional local Python engine (api.js) ----------
const PY_CLASSES = ['consumables', 'science', 'equipment', 'infrastructure', 'element', 'bulk', 'return'];
function pyRowToPage(r) {   // Python Metrics.summary() row -> the keys renderRun() reads (null -> NaN, shown as '–')
  const n = x => (x === null || x === undefined ? NaN : x), o = {};
  for (const k of Object.keys(r)) o[k] = n(r[k]);
  o.delay_by_class = {}; for (const c of PY_CLASSES) o.delay_by_class[c] = n(r['delay_mean_' + c]);
  if (r.immovable_share === undefined) o.immovable_share = o.stranded_kg / Math.max(o.landed_kg, 1e-9);
  if (r.cost_per_landed_kg_usd === undefined) o.cost_per_landed_kg_usd = NaN;   // Python's bulk_kg is not the delivered-bulk mass the JS formula subtracts
  return o;
}
function setEngineState(kind, text) { const el = $('apistate'); el.dataset.state = kind; $('apistatetext').textContent = text; }
function renderEngine() { const on = PY_API.connected; $('apiconnect').textContent = on ? 'Disconnect' : 'Connect'; $('apibase').disabled = on; $('xlive').disabled = !on; if (!on) $('xlive').checked = false; $('runpy').hidden = !on; }
function engineFailed(err) { if (err && err.status === 0) { PY_API.disconnect(); renderEngine(); setEngineState('err', `Lost the connection: ${err.message}. Back to the browser engine and the embedded reference.`); } }
try { $('apibase').value = localStorage.getItem('lunarsim.apibase') || PY_API.defaultBase(); } catch (e) { $('apibase').value = PY_API.defaultBase(); }
$('apibase').addEventListener('keydown', e => { if (e.key === 'Enter') $('apiconnect').click(); });
$('apiconnect').addEventListener('click', async () => {
  if (PY_API.connected) { PY_API.disconnect(); renderEngine(); setEngineState('off', 'Disconnected. Using the browser engine and the embedded Python reference.'); return; }
  $('apiconnect').disabled = true; setEngineState('off', 'Connecting…');
  try { const hh = await PY_API.connect($('apibase').value); try { localStorage.setItem('lunarsim.apibase', PY_API.base); } catch (e) { /* storage blocked */ }
    renderEngine(); $('xlive').checked = true; setEngineState('on', `Connected to ${PY_API.base}: ${hh.engine || 'python'} engine ${hh.version || ''}. "Run in Python" is in the rail; the cross-check below uses the live engine.`); }
  catch (err) { PY_API.disconnect(); renderEngine(); setEngineState('err', `Not connected: ${err.message}.`); }
  finally { $('apiconnect').disabled = false; }
});
$('runpy').addEventListener('click', async () => {
  if (!PY_API.connected) return;
  const mechName = ui.mech, want = Math.max(1, Math.floor(+$('seeds').value) || 1), n = Math.min(PY_API.MAX_SEEDS, want), seeds = Array.from({ length: n }, (_, i) => i);
  const opts = mechName === 'marketplace' ? marketOpts() : {}, scenario = uiToScenario(readUi()), capped = want > n ? ` (capped at ${PY_API.MAX_SEEDS} per request)` : '';
  setBusy(true, `Python engine: running ${n} simulated year${n > 1 ? 's' : ''} with ${MECH_LABEL[mechName]}${capped}…`); $('prog').removeAttribute('value');   // the server reports no progress
  try {
    const [res, tr] = await Promise.all([PY_API.run(scenario, mechName, seeds, opts), PY_API.trace(scenario, mechName, seeds[0], opts).catch(() => null)]);
    const runs = res.runs.map(pyRowToPage).sort((a, b) => a.seed - b.seed); let trace = null; try { trace = tr ? readTrace(tr) : null; } catch (e) { trace = null; }
    lastRuns = runs; renderRun(runs, trace); if (trace) setupReplay(trace);
    setBusy(false, `${n} simulated year${n > 1 ? 's' : ''} with ${MECH_LABEL[mechName]} on the Python engine in ${(res.ms / 1000).toFixed(1)} s${capped}.${trace ? ' The Replay tab shows year 0.' : ''}`);
  } catch (err) { engineFailed(err); setBusy(false, `Python engine: ${err.message}`); }
});
renderEngine();

// ---------- open with a result ----------
(async () => {
  const [runs, trace] = await runSeeds(readScenario(), 'marketplace', [0, 1, 2], marketOpts(), null);
  lastRuns = runs; renderRun(runs, trace); setupReplay(trace);
  status('Showing a quick start: 3 simulated years of Phase 2 with the marketplace. Change anything on the left and press Run simulation.');
})();
let rz = 0;
new ResizeObserver(() => { clearTimeout(rz); rz = setTimeout(() => { if (lastRuns) renderRun(lastRuns, replay.tr); if (compareRuns) renderCompare(compareRuns, compareRuns.marketplace.length); }, 200); }).observe($('tab-run'));
if (import.meta.env.DEV) window.__sim = { ui, replay, get lastRuns() { return lastRuns; } };
