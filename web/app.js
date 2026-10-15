'use strict';
/* LunarSim Live: UI layer. The engine lives in sim.js and runs in worker.js. */

const $ = id => document.getElementById(id);
const PY_REF = (typeof window !== 'undefined' && window.PY_REF) || null;
const fmtN = (x, d = 1) => Number.isFinite(x) ? x.toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d }) : '–';

// ---------- theme ----------
(function initTheme() {
  try { const t = localStorage.getItem('lunarsim.theme'); if (t) document.documentElement.setAttribute('data-theme', t); } catch (e) {}
  $('theme').addEventListener('click', () => {
    const cur = document.documentElement.getAttribute('data-theme');
    const dark = cur ? cur === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
    const next = dark ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem('lunarsim.theme', next); } catch (e) {}
    drawMap();
  });
})();

// ---------- tooltip ----------
const tip = $('tip');
function attachTips(root) {
  root.querySelectorAll('[data-tip]').forEach(el => {
    el.addEventListener('mousemove', e => { tip.textContent = el.getAttribute('data-tip'); tip.style.opacity = 1; tip.style.left = (e.clientX + 12) + 'px'; tip.style.top = (e.clientY + 12) + 'px'; });
    el.addEventListener('mouseleave', () => { tip.style.opacity = 0; });
  });
}

// ---------- worker pool ----------
const N_WORKERS = Math.max(1, Math.min(4, (navigator.hardwareConcurrency || 2) - 1));
const workers = [];
let msgId = 0;
const pending = new Map();
for (let i = 0; i < N_WORKERS; i++) {
  const w = new Worker('worker.js');
  w.onmessage = (e) => { const m = e.data; const p = pending.get(m.id); if (!p) return; if (m.type === 'progress') p.onProgress && p.onProgress(m.done, m.total); else { pending.delete(m.id); p.resolve(m); } };
  w.onerror = (e) => { console.error(e); };
  workers.push(w);
}
function workerCall(msg, onProgress) { return new Promise(resolve => { const id = ++msgId; pending.set(id, { resolve, onProgress }); const w = workers[id % workers.length]; w.postMessage(Object.assign({ id }, msg)); }); }
async function runSeeds(sc, mechName, seeds, opts, onProgress) {
  // split seeds across workers; the first chunk carries the trace
  const chunks = []; const per = Math.ceil(seeds.length / workers.length);
  for (let i = 0; i < seeds.length; i += per) chunks.push(seeds.slice(i, i + per));
  const progress = new Array(chunks.length).fill(0);
  const results = await Promise.all(chunks.map((ch, k) => workerCall({ type: 'run', scenario: sc, mechanism: mechName, seeds: ch, opts, trace: k === 0 },
    (done, total) => { progress[k] = done / total; onProgress && onProgress(progress.reduce((a, b) => a + b, 0) / chunks.length); })));
  const runs = results.flatMap(r => r.runs).sort((a, b) => a.seed - b.seed);
  return [runs, results[0].trace ? readTrace(results[0].trace) : null];  // lunarsim-trace v1 -> replay model (formats.js)
}

// ---------- statistics ----------
// mean, ci95, ci99, tQuantile come from sim.js

// ---------- state ----------
let fleet = JSON.parse(JSON.stringify(PRESETS[4]));
let lastRuns = null, lastTrace = null, compareRuns = null, lastScenario = null;
let replay = { tr: null, t: 0, playing: false, last: 0 };  // declared before the saved-tab restore below, which may draw the map

function readScenario() { return Object.assign(makeScenario({ phase: $('phase').value, bulkT: +$('bulk').value, fleet: fleet.map(f => ({ ...f })), night: +$('night').value, rtt: +$('rtt').value, nOps: +$('ops').value, duty: +$('duty').value, mtbf: +$('mtbf').value, std: +$('std').value }), { name: `lunarsim-live-${$('phase').value}` }); }
function marketOpts() { return { bundling: $('c_bundling').checked, consolidate: $('c_consolidate').checked, team_lift: $('c_team').checked, night_aware: $('c_night').checked, anticipate: $('c_anticipate').checked, backhaul: $('c_backhaul').checked, priority: $('c_priority').checked }; }
function renderFleet() {
  const el = $('fleet'); el.innerHTML = '';
  fleet.forEach((f, i) => {
    const row = document.createElement('div'); row.className = 'veh';
    row.innerHTML = `<select aria-label="owner" data-i="${i}" data-k="owner">${['NASA', 'CoA', 'CoB', 'CoC'].map(o => `<option ${o === f.owner ? 'selected' : ''}>${o}</option>`).join('')}</select>` +
      `<select aria-label="class" data-i="${i}" data-k="cls">${['LTV', 'HAUL', 'MICRO'].map(o => `<option ${o === f.cls ? 'selected' : ''}>${o}</option>`).join('')}</select>` +
      `<select aria-label="autonomy" data-i="${i}" data-k="autonomy">${['teleop', 'supervised', 'autonomous'].map(o => `<option ${o === f.autonomy ? 'selected' : ''}>${o}</option>`).join('')}</select>` +
      `<button class="btn ghost small" type="button" data-del="${i}" aria-label="remove vehicle">×</button>`;
    el.appendChild(row);
  });
  el.querySelectorAll('select').forEach(s => s.addEventListener('change', e => { fleet[+e.target.dataset.i][e.target.dataset.k] = e.target.value; }));
  el.querySelectorAll('button[data-del]').forEach(b => b.addEventListener('click', e => { fleet.splice(+e.currentTarget.dataset.del, 1); renderFleet(); }));
}
$('preset').addEventListener('change', e => { fleet = JSON.parse(JSON.stringify(PRESETS[e.target.value])); renderFleet(); });
$('addveh').addEventListener('click', () => { fleet.push(LTV('CoC')); renderFleet(); });
for (const [id, fmt] of [['night', v => (+v).toFixed(2)], ['rtt', v => (+v).toFixed(1)], ['ops', v => v], ['duty', v => (+v).toFixed(2)], ['mtbf', v => (+v).toFixed(2)], ['std', v => (+v).toFixed(2)]]) {
  const inp = $(id); const upd = () => $(id + '_v').textContent = fmt(inp.value); inp.addEventListener('input', upd); upd();
}
$('phase').addEventListener('change', e => { const ph = PHASES[e.target.value]; $('bulk').value = ph.bulk.reduce((s, b) => s + b[2], 0); $('ops').value = ph.nOps; $('ops_v').textContent = ph.nOps; });
document.querySelectorAll('nav.tabs button').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('nav.tabs button').forEach(x => x.setAttribute('aria-selected', x === b));
  document.querySelectorAll('.tabpane').forEach(p => p.classList.toggle('hidden', p.id !== 'tab-' + b.dataset.tab));
  if (b.dataset.tab === 'replay') drawMap();
  try { localStorage.setItem('lunarsim.tab', b.dataset.tab); } catch (e) {}
}));
try { const t = localStorage.getItem('lunarsim.tab'); if (t) document.querySelector(`nav.tabs button[data-tab="${t}"]`)?.click(); } catch (e) {}
renderFleet();

// ---------- scenario import / export ----------
// The mapping between files and controls lives in formats.js (scenarioToUi / uiToScenario); this block only reads and sets the DOM.
let scenarioName = 'lunarsim-live';
const UI_SLIDER_IDS = { night: 'night', rtt: 'rtt', nOps: 'ops', duty: 'duty', mtbf: 'mtbf', std: 'std' };
const UI_MARKET_IDS = { bundling: 'c_bundling', consolidate: 'c_consolidate', team_lift: 'c_team', night_aware: 'c_night', anticipate: 'c_anticipate', backhaul: 'c_backhaul', priority: 'c_priority' };
function readUi() { const ui = { name: scenarioName, phase: $('phase').value, bulk: +$('bulk').value, fleet: fleet.map(f => ({ ...f })), market: marketOpts() }; for (const [k, id] of Object.entries(UI_SLIDER_IDS)) ui[k] = +$(id).value; return ui; }
function applyUi(ui) {  // sets the controls the file provides; returns notes for values a control could not hold exactly
  const notes = [];
  if (ui.phase !== undefined) $('phase').value = ui.phase;  // no 'change' event: that would reset bulk and operators to the phase defaults
  if (ui.bulk !== undefined) { $('bulk').value = ui.bulk; if (+$('bulk').value !== ui.bulk) notes.push(`bulk ${ui.bulk} t/yr shown as ${$('bulk').value}`); }
  if (ui.fleet !== undefined) { fleet = ui.fleet.map(f => ({ ...f })); renderFleet(); }
  for (const [k, id] of Object.entries(UI_SLIDER_IDS)) if (ui[k] !== undefined) { const el = $(id); el.value = ui[k]; el.dispatchEvent(new Event('input'));
    if (Math.abs(+el.value - ui[k]) > 1e-9) notes.push(`${el.labels[0] ? el.labels[0].firstChild.textContent.trim() : id}: ${ui[k]} is outside the slider's range or step; set to ${el.value}`); }
  if (ui.market) for (const [k, id] of Object.entries(UI_MARKET_IDS)) if (ui.market[k] !== undefined) $(id).checked = ui.market[k];
  if (ui.name !== undefined) scenarioName = ui.name;
  return notes;
}
function showScenarioNote(notes) { const el = $('scnote'); el.classList.toggle('hidden', !notes.length); el.innerHTML = notes.length ? '<b>Approximated on import:</b><ul>' + notes.map(n => `<li>${n.replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c])}</li>`).join('') + '</ul>' : ''; }
$('exportScenario').addEventListener('click', () => { const j = uiToScenario(readUi()); download(`${j.name.replace(/[^\w.-]+/g, '-')}.json`, JSON.stringify(j, null, 2), 'application/json'); });
$('importScenario').addEventListener('change', e => {
  const f = e.target.files[0]; if (!f) return; const r = new FileReader();
  r.onload = () => { try { const { form, ui, notes } = scenarioToUi(String(r.result)); if (ui.name === undefined) ui.name = f.name.replace(/\.json$/i, ''); const all = notes.concat(applyUi(ui)); showScenarioNote(all);
      $('status').textContent = `Loaded scenario "${ui.name || f.name}" (${form} form${all.length ? `, ${all.length} approximation${all.length > 1 ? 's' : ''}: see the note` : ''}).`; }
    catch (err) { $('status').textContent = `Could not read ${f.name}: ${err.message}. Controls unchanged.`; } };
  r.onerror = () => { $('status').textContent = `Could not read ${f.name}.`; };
  r.readAsText(f); e.target.value = '';
});
function download(name, text, type) {
  try { const blob = new Blob([text], { type }); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 2000); }
  catch (e) { navigator.clipboard?.writeText(text); $('status').textContent = 'Download blocked here; content copied to the clipboard instead.'; }
}
function toCsv(rows) { if (!rows.length) return ''; const keys = Object.keys(rows[0]).filter(k => typeof rows[0][k] !== 'object'); return [keys.join(',')].concat(rows.map(r => keys.map(k => r[k]).join(','))).join('\n'); }
$('exportRuns').addEventListener('click', () => { if (lastRuns) download('lunarsim-runs.csv', toCsv(lastRuns), 'text/csv'); });
$('exportCompare').addEventListener('click', () => { if (compareRuns) download('lunarsim-compare.csv', toCsv(Object.entries(compareRuns).flatMap(([m, rs]) => rs.map(r => Object.assign({ mechanism: m }, r)))), 'text/csv'); });

// ---------- run ----------
function kpi(lab, runs, key, d = 1, scale = 1, accent = false) { const vals = runs.map(r => r[key] * scale); return `<div class="kpi${accent ? ' accent' : ''}"><div class="lab">${lab}</div><div class="num">${fmtN(mean(vals), d)}</div><div class="ci">± ${fmtN(ci95(vals), d)} · 95% CI · n=${vals.length}</div></div>`; }
$('run').addEventListener('click', async () => {
  const sc = readScenario(), mechName = $('mech').value, n = Math.max(1, Math.min(500, +$('seeds').value)); const seeds = Array.from({ length: n }, (_, i) => i);
  setBusy(true, 'running…'); const t0 = performance.now();
  const [runs, trace] = await runSeeds(sc, mechName, seeds, mechName === 'marketplace' ? marketOpts() : {}, p => $('prog').value = p);
  lastRuns = runs; lastTrace = trace; lastScenario = sc; setBusy(false, `${n} seed(s) of ${MECH_LABEL[mechName]} in ${((performance.now() - t0) / 1000).toFixed(1)} s on ${workers.length} worker(s).`);
  renderRun(runs, trace); setupReplay(trace);
});
$('runprec').addEventListener('click', async () => {
  const sc = readScenario(), mechName = $('mech').value; const opts = mechName === 'marketplace' ? marketOpts() : {}; let runs = [], trace0 = null, n = 0; setBusy(true, 'running…'); const t0 = performance.now();
  for (;;) {
    const seeds = Array.from({ length: 40 }, (_, i) => n + i); const [r, tr] = await runSeeds(sc, mechName, seeds, opts, null); if (!trace0) trace0 = tr; runs = runs.concat(r); n += 40;
    const vals = runs.map(x => x.delay_prio1_mean_h); const hw = ci99(vals), m = mean(vals); const rel = hw / Math.abs(m);
    $('status').textContent = `n=${n}: mean urgent delay ${fmtN(m, 2)} h, 99% CI ±${fmtN(hw, 2)} h (${(100 * rel).toFixed(2)}% of mean)`; $('prog').value = Math.min(1, 0.02 / Math.max(rel, 1e-9)); renderRun(runs, trace0);
    if ((rel <= 0.02 && n >= 80) || n >= 2000) break;
  }
  lastRuns = runs; lastTrace = trace0; lastScenario = sc; setupReplay(trace0); setBusy(false, $('status').textContent + ` — stopped after ${n} seeds in ${((performance.now() - t0) / 1000).toFixed(0)} s.`);
});
function setBusy(b, msg) { $('run').disabled = b; $('runprec').disabled = b; $('compare').disabled = b; $('prog').classList.toggle('hidden', !b); if (b) $('prog').value = 0; if (msg) $('status').textContent = msg; }

function renderRun(runs, trace) {
  $('kpis').innerHTML = kpi('Urgent cargo · 90th-percentile delay (h)', runs, 'delay_prio1_p90_h', 1, 1, true) + kpi('Urgent cargo delivered within 24 h', runs, 'sl24_prio1', 3) + kpi('Landed cargo mass immovable (%)', runs, 'immovable_share', 1, 100)
    + kpi('Vehicle trips per year', runs, 'jobs', 0) + kpi('Vehicles caught by the night (per yr)', runs, 'night_strandings', 2) + kpi('Operator console hours per year', runs, 'operator_hours', 0)
    + kpi('System cost per kg moved ($)', runs, 'cost_per_kg_usd', 0) + kpi('System cost per landed kg ($)', runs, 'cost_per_landed_kg_usd', 0) + kpi('Team lifts per year', runs, 'team_lifts', 1) + kpi('Fleet utilisation', runs, 'utilisation', 3);
  const labs = ['consumables', 'science', 'equipment', 'infrastructure', 'element', 'bulk', 'return'];
  barChart($('chart_delay'), labs.map(l => l[0].toUpperCase() + l.slice(1)), labs.map(l => mean(runs.map(r => r.delay_by_class[l]))), labs.map(l => ci95(runs.map(r => r.delay_by_class[l]))),
    ['var(--s8)', 'var(--s3)', 'var(--s1)', 'var(--s6)', 'var(--s4)', 'var(--muted)', 'var(--s5)'], 'hours');
  if (trace) timelineChart($('chart_timeline'), trace);
  const keys = [['seed', 'Seed', 0], ['delay_prio1_p90_h', 'Urgent p90 (h)', 1], ['delay_prio1_mean_h', 'Urgent mean (h)', 2], ['sl24_prio1', 'Within 24 h', 3], ['immovable_share', 'Immovable', 3], ['jobs', 'Trips', 0], ['bundled_jobs', 'Bundled', 0], ['team_lifts', 'Team lifts', 0], ['repositions', 'Staging', 0], ['night_strandings', 'Night', 0], ['faults', 'Faults', 0], ['operator_hours', 'Operator h', 0], ['landed_kg', 'Landed kg', 0], ['delivered_kg', 'Delivered kg', 0], ['backlog_kg', 'Backlog kg', 0]];
  $('seedtable').innerHTML = '<tr>' + keys.map(k => `<th class="num">${k[1]}</th>`).join('') + '</tr>' + runs.slice(0, 200).map(r => '<tr>' + keys.map(k => `<td class="num">${fmtN(r[k[0]], k[2])}</td>`).join('') + '</tr>').join('');
}

// ---------- charts ----------
function barChart(svg, labels, means, cis, colors, unit, yMax) {
  const W = 560, H = +svg.getAttribute('viewBox').split(' ')[3], pad = { l: 46, r: 12, t: 14, b: 44 };
  const vals = means.map((m, i) => (m || 0) + (cis[i] || 0)); const ymax = yMax || Math.max(1e-9, ...vals.filter(Number.isFinite)) * 1.12; const n = labels.length, bw = (W - pad.l - pad.r) / n; const y = v => pad.t + (H - pad.t - pad.b) * (1 - v / ymax);
  let s = ''; const ticks = 4; const dec = ymax < 2 ? 2 : (ymax < 20 ? 1 : 0);
  for (let i = 0; i <= ticks; i++) { const v = ymax * i / ticks; s += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line-2)" stroke-width="1"/><text x="${pad.l - 6}" y="${y(v) + 4}" text-anchor="end" font-size="10" fill="var(--muted)">${fmtN(v, dec)}</text>`; }
  labels.forEach((lab, i) => { const m = means[i]; const x = pad.l + bw * i + bw * 0.18, w = bw * 0.64;
    if (Number.isFinite(m)) { s += `<rect x="${x}" y="${y(m)}" width="${w}" height="${Math.max(0, y(0) - y(m))}" rx="3" fill="${colors[i % colors.length]}" data-tip="${lab}\n${fmtN(m, 2)} ± ${fmtN(cis[i], 2)} ${unit}"/>`; if (cis[i] > 0) { const cx = x + w / 2; s += `<line x1="${cx}" x2="${cx}" y1="${y(Math.max(0, m - cis[i]))}" y2="${y(m + cis[i])}" stroke="var(--ink2)" stroke-width="1.2"/><line x1="${cx - 4}" x2="${cx + 4}" y1="${y(m + cis[i])}" y2="${y(m + cis[i])}" stroke="var(--ink2)" stroke-width="1.2"/><line x1="${cx - 4}" x2="${cx + 4}" y1="${y(Math.max(0, m - cis[i]))}" y2="${y(Math.max(0, m - cis[i]))}" stroke="var(--ink2)" stroke-width="1.2"/>`; }
      s += `<text x="${x + w / 2}" y="${y(m) - 5}" text-anchor="middle" font-size="10.5" font-weight="600" fill="var(--ink)">${fmtN(m, dec)}</text>`; }
    s += `<text x="${x + w / 2}" y="${H - pad.b + 15}" text-anchor="middle" font-size="10.5" fill="var(--ink2)">${lab.length > Math.floor(bw / 6.5) ? lab.slice(0, Math.max(6, Math.floor(bw / 6.5) - 1)) + '…' : lab}</text>`; });
  s += `<text x="${pad.l}" y="${H - 6}" font-size="10" fill="var(--muted)">${unit}</text>`; svg.innerHTML = s; attachTips(svg);
}
function timelineChart(svg, tr) {
  const W = 560, H = 250, pad = { l: 46, r: 12, t: 10, b: 34 }; const items = tr.cargo.filter(c => c.tDelivered !== null); const ymin = 0.5, ymax = Math.max(100, ...items.map(c => c.tDelivered - c.tReady)) * 1.3;
  const x = t => pad.l + (W - pad.l - pad.r) * t / tr.horizon; const y = v => pad.t + (H - pad.t - pad.b) * (1 - (Math.log10(Math.max(v, ymin)) - Math.log10(ymin)) / (Math.log10(ymax) - Math.log10(ymin)));
  let s = ''; for (const [a, b] of tr.nights) s += `<rect x="${x(a)}" y="${pad.t}" width="${x(b) - x(a)}" height="${H - pad.t - pad.b}" fill="var(--night)"/>`;
  for (const v of [1, 10, 100, 1000]) if (v < ymax) s += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line-2)"/><text x="${pad.l - 5}" y="${y(v) + 4}" text-anchor="end" font-size="10" fill="var(--muted)">${v}</text>`;
  for (const [t, name] of tr.landings) s += `<line x1="${x(t)}" x2="${x(t)}" y1="${H - pad.b}" y2="${H - pad.b - 9}" stroke="var(--s2)" stroke-width="1.6" data-tip="${name} landing, day ${Math.floor(t / 24)}"/>`;
  const col = { 1: 'var(--s8)', 2: 'var(--s3)', 3: 'var(--muted)' };
  for (const c of items) { const d = c.tDelivered - c.tReady; s += `<circle cx="${x(c.tReady)}" cy="${y(d)}" r="${c.prio === 3 ? 1.7 : 2.8}" fill="${col[c.prio]}" opacity="0.85" data-tip="${c.cls} ${fmtN(c.mass, 0)} kg → ${c.dest}\nreleased day ${Math.floor(c.tReady / 24)}, delay ${fmtN(d, 1)} h"/>`; }
  for (let d = 0; d <= 365; d += 73) s += `<text x="${x(d * 24)}" y="${H - pad.b + 15}" text-anchor="middle" font-size="10" fill="var(--muted)">day ${d}</text>`;
  s += `<text x="${pad.l}" y="${H - 4}" font-size="10" fill="var(--muted)">delay (h, log)</text>`;
  s += `<g font-size="10" fill="var(--ink2)"><circle cx="${W - 150}" cy="${pad.t + 6}" r="3" fill="var(--s8)"/><text x="${W - 143}" y="${pad.t + 9}">urgent</text><circle cx="${W - 100}" cy="${pad.t + 6}" r="3" fill="var(--s3)"/><text x="${W - 93}" y="${pad.t + 9}">normal</text><circle cx="${W - 50}" cy="${pad.t + 6}" r="2" fill="var(--muted)"/><text x="${W - 44}" y="${pad.t + 9}">bulk</text></g>`;
  svg.innerHTML = s; attachTips(svg);
}

// ---------- compare ----------
$('compare').addEventListener('click', async () => {
  const sc = readScenario(), n = Math.max(1, Math.min(500, +$('seeds').value)); const seeds = Array.from({ length: n }, (_, i) => i); setBusy(true, 'comparing…'); const res = {}; const t0 = performance.now();
  for (const mn of Object.keys(MECHS)) { $('cstatus').textContent = `running ${MECH_LABEL[mn]}…`; const [runs] = await runSeeds(sc, mn, seeds, mn === 'marketplace' ? marketOpts() : {}, null); res[mn] = runs; }
  compareRuns = res; setBusy(false, 'comparison done.'); $('cstatus').textContent = `done in ${((performance.now() - t0) / 1000).toFixed(1)} s (${n} seeds × 4 rules).`; renderCompare(res, n);
});
function renderCompare(res, n) {
  const mn = Object.keys(res), labels = mn.map(m => MECH_LABEL[m]), colors = mn.map(m => MECH_COLOR[m]);
  const mk = (key, scale = 1) => [mn.map(m => mean(res[m].map(r => r[key] * scale))), mn.map(m => ci95(res[m].map(r => r[key] * scale)))];
  let [m1, c1] = mk('delay_prio1_p90_h'); barChart($('chart_c1'), labels, m1, c1, colors, 'hours'); let [m2, c2] = mk('sl24_prio1'); barChart($('chart_c2'), labels, m2, c2, colors, 'share', 1.05); let [m3, c3] = mk('immovable_share', 100); barChart($('chart_c3'), labels, m3, c3, colors, '%'); let [m4, c4] = mk('night_strandings'); barChart($('chart_c4'), labels, m4, c4, colors, 'per year');
  const paired = (a, b, key, d = 2) => { const diff = res[a].map((r, i) => r[key] - res[b][i][key]); return `${fmtN(mean(diff), d)} ± ${fmtN(ci95(diff), d)}`; };
  $('ckpis').innerHTML = `<div class="kpi accent"><div class="lab">Marketplace − pooled greedy · urgent p90 (h)</div><div class="num">${paired('marketplace', 'pooled_greedy', 'delay_prio1_p90_h')}</div><div class="ci">paired difference · 95% CI · n=${n}</div></div>`
    + `<div class="kpi"><div class="lab">Marketplace − pooled greedy · within 24 h</div><div class="num">${paired('marketplace', 'pooled_greedy', 'sl24_prio1', 3)}</div><div class="ci">paired difference</div></div>`
    + `<div class="kpi"><div class="lab">Marketplace − pooled greedy · trips per year</div><div class="num">${paired('marketplace', 'pooled_greedy', 'jobs', 1)}</div><div class="ci">paired difference</div></div>`
    + `<div class="kpi"><div class="lab">Marketplace − in-house · urgent p90 (h)</div><div class="num">${paired('marketplace', 'inhouse', 'delay_prio1_p90_h')}</div><div class="ci">paired difference</div></div>`;
  const keys = [['delay_prio1_p90_h', 'Urgent p90 (h)', 1], ['delay_prio1_mean_h', 'Urgent mean (h)', 2], ['sl24_prio1', 'Within 24 h', 3], ['immovable_share', 'Immovable', 3], ['backlog_kg', 'Backlog kg', 0], ['jobs', 'Trips', 0], ['bundled_jobs', 'Bundled', 0], ['team_lifts', 'Team lifts', 1], ['night_strandings', 'Night', 2], ['operator_hours', 'Operator h', 0], ['empty_km_share', 'Empty km', 3], ['revenue_gini', 'Revenue Gini', 2], ['cost_per_kg_usd', '$/kg moved', 0]];
  $('ctable').innerHTML = '<tr><th>Rule</th>' + keys.map(k => `<th class="num">${k[1]}</th>`).join('') + '</tr>' + mn.map(m => `<tr class="${m === 'marketplace' ? 'hl' : ''}"><td>${MECH_LABEL[m]}</td>` + keys.map(k => `<td class="num">${fmtN(mean(res[m].map(r => r[k[0]])), k[2])} <span class="note">±${fmtN(ci95(res[m].map(r => r[k[0]])), k[2])}</span></td>`).join('') + '</tr>').join('');
}

// ---------- replay ----------
function setupReplay(tr, source) { if (!tr) return; replay.tr = tr; replay.t = 0; replay.playing = false; $('play').textContent = 'Play'; $('tslider').max = Math.floor(tr.horizon); $('tslider').value = 0; const owners = [...new Set(tr.vehicles.map(v => v.owner))]; $('maplegend').innerHTML = owners.map((o, i) => `<span style="--c: var(--s${(i % 8) + 1})">${o}</span>`).join('') + `<span style="--c: var(--s2)">landing pad</span><span style="--c: var(--night)">night</span>`; replayHeader(tr, source); $('exportTrace').disabled = false; drawMap(); }
function replayHeader(tr, source) { const m = tr.meta || {}, esc = x => String(x).replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[ch]); const val = x => x === null || x === undefined || x === '' ? '–' : esc(x);
  $('replayhead').innerHTML = `<span>engine <b>${val(m.engine)}</b></span><span>scenario <b>${val(m.scenario)}</b></span><span>mechanism <b>${val(MECH_LABEL[m.mechanism] || m.mechanism)}</b></span><span>seed <b>${val(m.seed)}</b></span><span class="src">${source ? 'from file ' + esc(source) + (m.legacy ? ' (no format header; read as v1)' : '') : 'from the last run'}</span>`; }
$('importTrace').addEventListener('change', e => {
  const f = e.target.files[0]; if (!f) return; const r = new FileReader();
  r.onload = () => { try { const tr = readTrace(String(r.result)); setupReplay(tr, f.name); $('rstatus').textContent = `Loaded ${f.name}: ${tr.vehicles.length} vehicles, ${tr.jobs.length} trips, ${tr.cargo.length} cargo items, ${tr.landings.length} landings, ${tr.nights.length} nights.`; }
    catch (err) { $('rstatus').textContent = `Could not read ${f.name}: ${err.message}. The previous replay is unchanged.`; } };
  r.onerror = () => { $('rstatus').textContent = `Could not read ${f.name}.`; };
  r.readAsText(f); e.target.value = '';
});
$('exportTrace').addEventListener('click', () => { if (!replay.tr) return; const m = replay.tr.meta || {}; const name = ['lunarsim-trace', m.scenario, m.mechanism, m.seed === null || m.seed === undefined ? null : 'seed' + m.seed].filter(x => x !== null && x !== undefined && x !== '').join('_').replace(/[^\w.-]+/g, '-') + '.json'; download(name, JSON.stringify(traceToJson(replay.tr)), 'application/json'); $('rstatus').textContent = `Exported ${name}.`; });
$('tslider').addEventListener('input', e => { replay.t = +e.target.value; drawMap(); });
$('play').addEventListener('click', () => { replay.playing = !replay.playing; $('play').textContent = replay.playing ? 'Pause' : 'Play'; if (replay.playing) { replay.last = performance.now(); requestAnimationFrame(tick); } });
function tick(now) { if (!replay.playing || !replay.tr) return; const dt = (now - replay.last) / 1000; replay.last = now; replay.t += dt * (+$('speed').value); if (replay.t >= replay.tr.horizon) { replay.t = replay.tr.horizon; replay.playing = false; $('play').textContent = 'Play'; } $('tslider').value = Math.floor(replay.t); drawMap(); if (replay.playing) requestAnimationFrame(tick); }
function sitePos(name, W, H) { const s = WORLD.sites[name]; const xs = SITES.map(q => q.x), ys = SITES.map(q => q.y); const minx = Math.min(...xs) - 0.5, maxx = Math.max(...xs) + 0.6, miny = Math.min(...ys) - 0.5, maxy = Math.max(...ys) + 0.5; const scale = Math.min((W - 60) / (maxx - minx), (H - 60) / (maxy - miny)); return [30 + (s.x - minx) * scale, H - 30 - (s.y - miny) * scale]; }
function vehiclePos(v, tr, t, W, H) {
  let loc = 'DEPOT', loaded = 0, pos = null;
  for (const j of tr.jobs) { if (!j.team.includes(v.id)) continue; if (t < j.t0) break; if (t >= j.t1) { const sg = j.segments[j.segments.length - 1]; loc = sg ? sg[1] : loc; continue; }
    for (const sg of j.segments) { const [a, b, s0, s1, kg] = sg; if (t >= s0 && t <= s1) { loaded = kg; if (a === b) { loc = a; } else { const path = WORLD.path(a, b); const total = WORLD.distance(a, b); let dcum = (t - s0) / Math.max(1e-9, s1 - s0) * total; for (let i = 0; i + 1 < path.length; i++) { const d = WORLD.edges[path[i] + '|' + path[i + 1]].dist; if (dcum <= d) { const [x0, y0] = sitePos(path[i], W, H), [x1, y1] = sitePos(path[i + 1], W, H); const f = dcum / d; pos = [x0 + f * (x1 - x0), y0 + f * (y1 - y0)]; break; } dcum -= d; } if (!pos) pos = sitePos(b, W, H); } break; } } break; }
  if (!pos) pos = sitePos(loc, W, H); return { pos, loaded };
}
function drawMap() {
  const cv = $('map'); if (!cv) return; const ctx = cv.getContext('2d'); const W = cv.width, H = cv.height; const css = getComputedStyle(document.documentElement); const col = k => css.getPropertyValue(k).trim(); ctx.clearRect(0, 0, W, H); ctx.fillStyle = col('--panel-2'); ctx.fillRect(0, 0, W, H); const tr = replay.tr; const t = replay.t;
  const slopeCol = { flat: '#9ec5f4', moderate: col('--s4'), steep: col('--s8') };
  for (const [a, b, sl] of EDGES) { const [x0, y0] = sitePos(a, W, H), [x1, y1] = sitePos(b, W, H); ctx.strokeStyle = slopeCol[sl]; ctx.lineWidth = sl === 'steep' ? 8 : sl === 'moderate' ? 6 : 4; ctx.lineCap = 'round'; ctx.globalAlpha = 0.8; ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke(); ctx.globalAlpha = 1; ctx.fillStyle = col('--muted'); ctx.font = '11px ' + col('--mono'); ctx.fillText(WORLD.edges[a + '|' + b].dist.toFixed(1) + ' km', (x0 + x1) / 2 + 5, (y0 + y1) / 2 - 5); }
  const night = tr && tr.nights.some(([a, b]) => t >= a && t < b); if (night) { ctx.fillStyle = col('--night'); ctx.fillRect(0, 0, W, H); }
  const waiting = {}; if (tr) for (const c of tr.cargo) { if (c.tReady <= t && (c.tPicked === null || c.tPicked > t) && !c.stranded) waiting[c.origin] = (waiting[c.origin] || 0) + 1; }
  for (const s of SITES) { const [x, y] = sitePos(s.name, W, H); const w = waiting[s.name] || 0; if (w) { ctx.strokeStyle = col('--s2'); ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(x, y, 16 + Math.min(34, 3 * w), 0, 2 * Math.PI); ctx.stroke(); ctx.fillStyle = col('--s2'); ctx.font = '600 12px ' + col('--font'); ctx.fillText(w + ' waiting', x + 20 + Math.min(34, 3 * w), y - 12); }
    ctx.fillStyle = s.kind === 'pad' ? col('--s2') : (s.kind === 'base' ? col('--s1') : col('--ink2')); ctx.beginPath(); if (s.kind === 'pad') ctx.rect(x - 10, y - 10, 20, 20); else ctx.arc(x, y, 9, 0, 2 * Math.PI); ctx.fill(); ctx.fillStyle = col('--ink'); ctx.font = '600 13px ' + col('--font'); ctx.fillText(s.name.replace('_', ' '), x + 14, y + 5); }
  if (tr) for (const [tl, name, pad] of tr.landings) { if (t >= tl && t < tl + 72) { const [x, y] = sitePos(pad, W, H); ctx.strokeStyle = col('--s2'); ctx.lineWidth = 2; ctx.setLineDash([5, 5]); ctx.beginPath(); ctx.arc(x, y, 30, 0, 2 * Math.PI); ctx.stroke(); ctx.setLineDash([]); ctx.fillStyle = col('--s2'); ctx.font = '12px ' + col('--font'); ctx.fillText(name + ' landed', x - 34, y + 48); } }
  if (tr) { const owners = [...new Set(tr.vehicles.map(v => v.owner))]; tr.vehicles.forEach(v => { const { pos, loaded } = vehiclePos(v, tr, t, W, H); const [x, y] = pos; const c = col(`--s${(owners.indexOf(v.owner) % 8) + 1}`); const r = v.cls === 'HAUL' ? 12 : v.cls === 'LTV' ? 9 : 6.5; const ox = (v.id % 3) * 5 - 5, oy = Math.floor(v.id / 3) * 5 - 5; ctx.beginPath(); ctx.arc(x + ox, y + oy, r, 0, 2 * Math.PI); ctx.fillStyle = loaded > 0 ? c : col('--panel'); ctx.strokeStyle = c; ctx.lineWidth = 2.5; ctx.fill(); ctx.stroke(); if (loaded > 0) { ctx.fillStyle = col('--ink'); ctx.font = '10.5px ' + col('--mono'); ctx.fillText(Math.round(loaded) + ' kg', x + ox + r + 3, y + oy + 4); } }); }
  const day = Math.floor(t / 24), hr = Math.floor(t % 24); $('clock').textContent = `day ${day}, ${String(hr).padStart(2, '0')}:00${night ? ' · night' : ''}`;
  if (tr) { const delivered = tr.cargo.filter(c => c.tDelivered !== null && c.tDelivered <= t).length, waitingN = Object.values(waiting).reduce((a, b) => a + b, 0), jobsSoFar = tr.jobs.filter(j => j.t0 <= t).length; $('replaystats').textContent = `${delivered} items delivered so far · ${waitingN} waiting · ${jobsSoFar} trips started · ${tr.landings.filter(l => l[0] <= t).length} of ${tr.landings.length} landings`; }
}

// ---------- verification ----------
$('verify').addEventListener('click', async () => {
  $('vstatus').textContent = 'running…'; const m = await workerCall({ type: 'verify' }); const checks = m.checks; const np = checks.filter(c => c.passed).length;
  $('vstatus').textContent = `${np} of ${checks.length} checks passed.`; $('vbadge').textContent = `${np}/${checks.length} checks pass`; $('vbadge').classList.toggle('pending', np !== checks.length);
  $('vtable').innerHTML = '<tr><th>Check</th><th class="num">Reference</th><th class="num">Simulated</th><th class="num">Error</th><th class="num">Tolerance</th><th>Basis</th><th>Result</th></tr>' + checks.map(c => `<tr><td>${c.name}</td><td class="num">${fmtN(c.ref, 4)} ${c.unit}</td><td class="num">${fmtN(c.sim, 4)} ${c.unit}</td><td class="num">${(100 * c.err).toFixed(3)}%</td><td class="num">${(100 * c.tol).toFixed(1)}%</td><td class="note">${c.basis}</td><td><span class="pill ${c.passed ? 'pass' : 'fail'}">${c.passed ? 'PASS' : 'FAIL'}</span></td></tr>`).join('');
});
$('xcheck').addEventListener('click', async () => {
  if (!PY_REF) { $('xstatus').textContent = 'No Python reference embedded in this build.'; return; } $('xcheck').disabled = true;
  const sc = makeScenario({ phase: 'P2', bulkT: 500, fleet: PRESETS[6], night: 0.15, rtt: 5, nOps: 3, duty: 0.3, mtbf: 1, std: 1 }); const seeds = Array.from({ length: 30 }, (_, i) => i); const rows = [];
  for (const mn of Object.keys(MECHS)) { $('xstatus').textContent = `running ${MECH_LABEL[mn]}…`; const [runs] = await runSeeds(sc, mn, seeds, {}, null);
    for (const [key, lab] of [['delay_prio1_mean_h', 'Urgent mean delay (h)'], ['delay_prio1_p90_h', 'Urgent p90 delay (h)'], ['sl24_prio1', 'Urgent within 24 h'], ['jobs', 'Trips per year'], ['night_strandings', 'Night strandings'], ['delivered_share', 'Delivered share']]) { const js = runs.map(r => r[key]); const ref = PY_REF[mn] && PY_REF[mn][key]; if (!ref) continue; const mj = mean(js), cj = ci95(js); rows.push({ mn, lab, mj, cj, ref, overlap: Math.abs(mj - ref.mean) <= (cj + ref.ci) }); } }
  $('xcheck').disabled = false; $('xstatus').textContent = `${rows.filter(r => r.overlap).length} of ${rows.length} metric cells agree within combined 95% CIs.`;
  $('xtable').innerHTML = '<tr><th>Rule</th><th>Metric</th><th class="num">Browser (mean ± CI)</th><th class="num">Python (mean ± CI)</th><th>Agree</th></tr>' + rows.map(r => `<tr><td>${MECH_LABEL[r.mn]}</td><td>${r.lab}</td><td class="num">${fmtN(r.mj, 2)} ± ${fmtN(r.cj, 2)}</td><td class="num">${fmtN(r.ref.mean, 2)} ± ${fmtN(r.ref.ci, 2)}</td><td><span class="pill ${r.overlap ? 'pass' : 'fail'}">${r.overlap ? 'yes' : 'no'}</span></td></tr>`).join('');
});

// ---------- open with a result ----------
(async () => { const sc = readScenario(); const [runs, trace] = await runSeeds(sc, 'marketplace', [0, 1, 2], marketOpts(), null); lastRuns = runs; lastTrace = trace; lastScenario = sc; renderRun(runs, trace); setupReplay(trace); $('status').textContent = `Opened with a 3-seed marketplace run of the Phase-2 scenario on ${workers.length} worker(s). Change anything in the rail and run again.`; })();
