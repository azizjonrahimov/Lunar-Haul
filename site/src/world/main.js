// /world: replay a simulated year on the real terrain (F-6). Loads a trace (bundled sample, the simulator's last run,
// or a file), builds the layout from the terrain pack, and drives the 3D scene, the 2D plan view and the DOM
// telemetry rail from one state snapshot per frame. Starts paused (WCAG 2.2.2); reduced motion = no camera tweens.
import './world.css';
import { loadTerrain } from '../terrain.js';
import { num, esc } from '../components/num.js';
import { readTrace } from './trace.js';
import { buildLayout } from './layout.js';
import { indexTrace, snapshot, steps, descentH } from './state.js';
import { createPlan } from './plan2d.js';
import { OWNER_COLOURS } from './colours.js';
import { viewPad } from '../ui/viewpad.js';

const $ = id => document.getElementById(id);
const BASE = import.meta.env.BASE_URL;
const SIM_KEY = 'lunarsim.worldTrace';
const SAMPLES = { P1: 'P1_marketplace_seed3.json', P2: 'P2_marketplace_seed3.json', P3: 'P3_marketplace_seed3.json', P2V2: 'P2_marketplace_seed3_v2.json' };
const DESCENT_RATE_H = 10 / 3600;      // during a descent, play at most 10 sim-seconds per second
const reduced = matchMedia('(prefers-reduced-motion: reduce)');

const st = { terrain: null, sites: null, graph: null, layout: null, tr: null, ix: null, scene: null, plan: null, inset: null,
  t: 0, playing: false, last: 0, mode: '3d', lastRail: 0, raf: 0, source: '' };

function status(msg) { $('w-status').textContent = msg; }

async function fetchJson(url) { const r = await fetch(url); if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`); return r.json(); }

async function boot() {
  try {
    const terrainUrl = BASE + 'terrain/hero/';
    [st.terrain, st.graph] = await Promise.all([loadTerrain(terrainUrl), fetchJson(BASE + 'world/site_graph.json')]);
    try { st.sites = await fetchJson(terrainUrl + 'sites.json'); } catch (e) { st.sites = null; }
  } catch (err) { status(`Could not load the terrain (${err.message}).`); return; }
  st.mode = await pickMode();
  wireControls();
  const q = new URLSearchParams(location.search);
  if (q.get('from') === 'simulator' || q.get('from') === 'service') loadFromSimulator(q.get('from') === 'service' ? `service run ${q.get('run') || ''}`.trim() : null); else loadSample(q.get('sample') && SAMPLES[q.get('sample')] ? q.get('sample') : 'P2');
}

// ---------- GPU tier: detect-gpu with self-hosted benchmarks; tier 0 or no WebGL2 -> 2D plan view ----------
async function pickMode() {
  const forced = new URLSearchParams(location.search).get('view');
  if (forced === '2d') return '2d';
  const gl = document.createElement('canvas').getContext('webgl2'); if (!gl) { $('w-tier').textContent = 'No WebGL2: showing the 2D plan view.'; return '2d'; }
  try {
    const { getGPUTier } = await import('detect-gpu');
    const g = await getGPUTier({ benchmarksURL: BASE + 'detect-gpu/benchmarks' });
    $('w-tier').textContent = `GPU tier ${g.tier}${g.gpu ? ' (' + g.gpu + ')' : ''}${g.tier === 0 ? ': showing the 2D plan view' : ''}.`;
    return g.tier === 0 && forced !== '3d' ? '2d' : '3d';
  } catch (e) { $('w-tier').textContent = 'GPU tier unknown; using 3D.'; return '3d'; }
}

// ---------- loading ----------
async function loadSample(key) {
  status(`Loading the bundled ${key} sample…`);
  try { setTrace(await (await fetch(BASE + 'world/samples/' + SAMPLES[key])).text(), `bundled sample ${SAMPLES[key]}`); st.sampleKey = key; applyMoment(); }
  catch (err) { status(`Could not load the ${key} sample: ${err.message}.`); }
}
function loadFromSimulator(label) {   // the simulator and the Account page hand a trace over through localStorage
  let raw = null; try { raw = localStorage.getItem(SIM_KEY); } catch (e) { /* blocked storage */ }
  if (!raw) { status('No run from the simulator was found in this browser. Run one there and press "Open in 3D world", or load a sample.'); loadSample('P2'); return; }
  setTrace(raw, label || 'the simulator’s last run');
}
function setTrace(text, source) {
  st.sampleKey = null;   // set again by loadSample: only a bundled sample can be reopened from a link
  let tr;
  try { tr = readTrace(text, new Set(st.graph.sites.map(s => s.name))); }
  catch (err) { status(`Could not read ${source}: ${err.message}. The previous replay is unchanged.`); return; }
  const standoff = tr.meta.standoffKm !== null && tr.meta.standoffKm !== undefined ? String(tr.meta.standoffKm) : '1';
  const prevKey = st.layout && st.layout.key;
  st.layout = buildLayout(st.terrain, st.sites, st.graph, standoff, tr.siteXY);
  st.tr = tr; st.ix = indexTrace(tr); st.source = source; st.t = 0; setPlaying(false);
  $('w-scrub').max = String(Math.floor(tr.horizon)); $('w-scrub').value = '0';
  if (st.scene && prevKey !== st.layout.key) {   // sites moved: rebuild the 3D scene on a fresh canvas
    st.scene.dispose(); st.scene = null; st.views = null;
    const old = $('w-canvas'), fresh = old.cloneNode(false); old.replaceWith(fresh);
  }
  ensureViews(); st.scene && st.scene.setTrace(tr);
  renderHeader(); renderSteps(); renderLegend(); renderFollow();
  status(`Loaded ${source}: ${tr.vehicles.length} vehicles, ${tr.jobs.length} trips, ${tr.cargo.length} cargo items, ${tr.landings.length} landings, ${tr.nights.length} nights.`);
  if (st.scene) st.scene.preset('overview', false);
  draw(true);
}

// ---------- F-40: a moment in the URL hash (#t=812.5021&follow=3&cam=x,y,z,tx,ty,tz), the bundled sample in the query ----------
let moment = null, pendingCam = null;   // pendingCam: a linked camera waiting for the 3D scene (built after the trace loads)
const setCam = c => { st.scene.camera.position.set(c[0], c[1], c[2]); st.scene.controls.target.set(c[3], c[4], c[5]); st.scene.controls.update(); };
function readHash() {
  const h = new URLSearchParams(location.hash.slice(1)), t = parseFloat(h.get('t')), cam = (h.get('cam') || '').split(',').map(Number);
  return Number.isFinite(t) ? { t, follow: h.get('follow') || '', cam: cam.length === 6 && cam.every(Number.isFinite) ? cam : null } : null;
}
moment = readHash();
// the pending moment, once a trace is loaded: that hour, that vehicle followed and that camera, paused
function applyMoment() {
  const m = moment; moment = null; if (!m || !st.tr) return;
  setPlaying(false); st.t = Math.max(0, Math.min(st.tr.horizon, m.t));
  const f = $('w-follow'); if (m.follow && [...f.options].some(o => o.value === m.follow)) { f.value = m.follow; st.scene && st.scene.followVehicle(+m.follow); }
  if (m.cam) { if (!st.scene) pendingCam = m.cam; else if (!st.scene.isFollowing()) setCam(m.cam); }
  draw(true); status(`The moment from the link: ${clock(st.t)}. Press Play to go on.`);
}
async function copyMoment() {
  if (!st.tr) return;
  const r = v => Math.round(v * 10) / 10, f = $('w-follow').value;
  let hash = `t=${st.t.toFixed(4)}${f ? '&follow=' + f : ''}`;
  if (st.scene && st.mode === '3d') { const p = st.scene.camera.position, g = st.scene.controls.target; hash += '&cam=' + [p.x, p.y, p.z, g.x, g.y, g.z].map(r).join(','); }
  const url = `${location.origin}${location.pathname}${st.sampleKey ? '?sample=' + st.sampleKey : location.search}#${hash}`;
  history.replaceState(null, '', url);
  const note = st.sampleKey ? '' : ' It reopens this moment only where this trace is loaded (a file or a simulator run is not in the link).';
  status(`The link to ${clock(st.t)} is in the address bar.${note}`);   // stays if the clipboard is refused or never answers
  try { await navigator.clipboard.writeText(url); status(`Link to ${clock(st.t)} copied.${note}`); } catch { /* the address bar has it */ }
}
addEventListener('hashchange', () => { moment = readHash(); applyMoment(); });

// ---------- views ----------
let sceneMod = null;
async function ensureViewsAsync() {
  if (st.mode === '3d' && !st.scene) {
    try {
      sceneMod = sceneMod || await import('./scene.js');
      const tierText = $('w-tier').textContent;
      st.scene = sceneMod.createScene({ canvas: $('w-canvas'), labelHost: $('w-labels'), terrain: st.terrain, layout: st.layout,
        onAssets: msg => { if (msg !== 'horizon') $('w-tier').textContent = `${tierText} Terrain light: ${msg}.`; draw(true); } });
      st.sceneRO && st.sceneRO.disconnect();
      st.sceneRO = new ResizeObserver(() => { if (st.scene) { st.scene.resize(); draw(true); } }); st.sceneRO.observe($('w-canvas'));
      st.scene.resize(); if (st.tr) st.scene.setTrace(st.tr); st.scene.preset('overview', false);
      if ($('w-follow').value) st.scene.followVehicle(+$('w-follow').value); else if (pendingCam) setCam(pendingCam);   // a linked moment's view
      pendingCam = null;
      // F-40: orbit and zoom without a drag (top right: the inset map holds the bottom corner)
      if (!document.querySelector('#w-stage .ui-viewpad')) $('w-stage').append(viewPad({ nudge: (a, p) => { st.scene?.nudge(a, p); draw(true); }, zoom: f => { st.scene?.zoom(f); draw(true); } }, { place: 'top' }));
    } catch (err) { st.mode = '2d'; $('w-tier').textContent = `3D view unavailable (${err.message}): showing the 2D plan view.`; }
  }
  document.body.classList.toggle('w-2d', st.mode === '2d');
  st.plan = createPlan($('w-plan'), st.layout); st.inset = createPlan($('w-inset'), st.layout);
  if (!st.stageRO) { st.stageRO = new ResizeObserver(() => { st.plan && st.plan.resize(); st.inset && st.inset.resize(); draw(true); }); st.stageRO.observe($('w-stage')); }
  draw(true);
}
function ensureViews() {
  if (st.views) { st.plan = createPlan($('w-plan'), st.layout); st.inset = createPlan($('w-inset'), st.layout); return; }
  st.views = ensureViewsAsync();
}

// ---------- frame loop ----------
function draw(force) {
  if (!st.tr) return;
  const snap = snapshot(st.tr, st.ix, st.t);
  if (st.scene && st.mode === '3d') { st.scene.update(st.tr, snap, { labels: $('w-labels-on').checked }); st.scene.render(performance.now()); }
  if (st.mode === '2d' && st.plan) st.plan.draw(st.tr, snap);
  if (st.inset && st.mode === '3d') st.inset.draw(st.tr, snap);
  const now = performance.now();
  if (force || now - st.lastRail > 250) { renderRail(snap); st.lastRail = now; }
  $('w-scrub').value = String(Math.floor(st.t)); $('w-clock').textContent = clock(st.t) + (snap.night ? ' · night' : '');
  return snap;
}
function tick(now) {
  st.raf = 0;
  if (st.playing && st.tr) {
    const dt = st.last ? Math.min(0.1, (now - st.last) / 1000) : 0; st.last = now;
    let rate = +$('w-speed').value, next = st.t + rate * dt;
    if ($('w-slow').checked) {
      if (st.tr.landings.some(l => st.t >= l.t - descentH(l) && st.t < l.t)) next = st.t + Math.min(rate, DESCENT_RATE_H) * dt;   // inside a descent
      else { const l = st.tr.landings.find(x => st.t < x.t - descentH(x) && next >= x.t - descentH(x)); if (l) next = l.t - descentH(l); }  // stop at its start
    }
    st.t = Math.min(st.tr.horizon, next); if (st.t >= st.tr.horizon) setPlaying(false);
  }
  draw(false);
  if (st.playing || (st.scene && st.mode === '3d')) st.raf = requestAnimationFrame(tick);   // 3D keeps rendering for orbit/damping
}
function kick() { if (!st.raf) { st.last = 0; st.raf = requestAnimationFrame(tick); } }
function setPlaying(p) { st.playing = p; const b = $('w-play'); b.setAttribute('aria-pressed', String(p)); b.querySelector('[data-label]').textContent = p ? 'Pause' : 'Play'; document.body.classList.toggle('w-playing', p); if (p) kick(); }

// ---------- controls ----------
function wireControls() {
  $('w-play').addEventListener('click', () => { if (st.tr && st.t >= st.tr.horizon) st.t = 0; setPlaying(!st.playing); });
  $('w-scrub').addEventListener('input', e => { st.t = +e.target.value; draw(true); });
  $('w-sample').addEventListener('change', e => { const v = e.target.value; e.target.value = ''; if (v === 'sim') loadFromSimulator(); else if (SAMPLES[v]) loadSample(v); });
  $('w-file').addEventListener('change', e => { const f = e.target.files[0]; if (!f) return; const r = new FileReader(); r.onload = () => setTrace(String(r.result), 'file ' + f.name); r.onerror = () => status(`Could not read ${f.name}.`); r.readAsText(f); e.target.value = ''; });
  for (const b of document.querySelectorAll('[data-preset]')) b.addEventListener('click', () => { if (st.scene) { st.scene.preset(b.dataset.preset, !reduced.matches); kick(); } });
  $('w-follow').addEventListener('change', e => { if (!st.scene) return; const v = e.target.value; if (v === '') st.scene.followVehicle(null); else { st.scene.followVehicle(+v); } kick(); });
  $('w-labels-on').addEventListener('change', () => draw(true));
  $('w-copy').addEventListener('click', copyMoment);
  $('w-view2d').addEventListener('change', e => { st.mode = e.target.checked ? '2d' : (st.scene ? '3d' : '2d'); document.body.classList.toggle('w-2d', st.mode === '2d'); st.plan && st.plan.resize(); draw(true); kick(); });
  document.addEventListener('keydown', e => {
    if (e.target.closest('input, select, textarea, button')) return;
    if (e.key === ' ') { e.preventDefault(); setPlaying(!st.playing); }
    else if (e.key === 'ArrowRight') { st.t = Math.min(st.tr.horizon, st.t + 24); draw(true); } else if (e.key === 'ArrowLeft') { st.t = Math.max(0, st.t - 24); draw(true); }
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) setPlaying(false); });
}

// ---------- DOM: header, steps, legend, rail ----------
function renderHeader() {
  const m = st.tr.meta, v = x => x === null || x === undefined || x === '' ? '–' : esc(x);
  $('w-head').innerHTML = `<span>trace <b>v${m.version}</b></span><span>engine <b>${v(m.engine)}</b></span><span>scenario <b>${v(m.scenario)}</b></span><span>mechanism <b>${v(m.mechanism)}</b></span><span>seed <b>${v(m.seed)}</b></span><span class="muted">${esc(st.source)}</span>`;
  const notes = [`Layout: ${st.layout.provisional ? 'provisional (schematic site graph centred on the tile; sites.json not found)' : st.layout.source === 'trace' ? `site positions from the trace, pad standoff ${st.layout.standoff} km` : `sites.json, pad set ${st.layout.standoff} km`} — <span class="flag" data-flag="Assumed" title="Assumed: a modelling assumption">Assumed</span> layout on <span class="flag" data-flag="Measured" title="Measured: LOLA laser altimetry">Measured</span> terrain.`];
  if (m.version === 1) notes.push('This v1 trace was simulated on the schematic site graph; vehicles are drawn along the same graph legs on the terrain, so on-screen speeds are illustrative. Energy, interventions and sheltering need a v2 trace.');
  $('w-notes').innerHTML = notes.map(n => `<p>${n}</p>`).join('');
}
function renderSteps() {
  $('w-steps').innerHTML = steps(st.tr).map(s => `<li><button class="btn" type="button" data-step="${s.id}" ${s.t === null ? 'disabled aria-disabled="true" title="Not in this trace"' : ''}>${esc(s.label)}${s.t === null ? '' : ` <span class="muted">day ${Math.floor(s.t / 24)}</span>`}</button></li>`).join('');
  for (const b of $('w-steps').querySelectorAll('[data-step]')) b.addEventListener('click', () => {
    const s = steps(st.tr).find(x => x.id === b.dataset.step); if (!s || s.t === null) return; st.t = s.t; setPlaying(false);
    if (st.scene && s.focus) st.scene.preset(s.focus === 'BASE' ? 'base' : 'site:' + s.focus, !reduced.matches);
    draw(true); kick();
  });
}
function renderLegend() {
  const owners = [...new Set(st.tr.vehicles.map(v => v.owner))];
  $('w-legend').innerHTML = owners.map(o => `<span><i style="background:${OWNER_COLOURS[o] || '#AA3377'}"></i>${esc(o)}</span>`).join('') +
    '<span><i class="sq" style="background:#66CCEE"></i>landing pad</span><span><i class="ring"></i>cargo waiting (ring size = items)</span><span><i class="ring y"></i>plume keep-out</span>';
}
function renderFollow() {
  $('w-follow').innerHTML = '<option value="">Follow vehicle…</option>' + st.tr.vehicles.map(v => `<option value="${v.id}">${esc(v.cls)} ${v.id} · ${esc(v.owner)}</option>`).join('');
}
const M = (value, unit, digits = 0, src = 'this trace') => num({ value, unit, flag: 'Modelled', digits, source: src });
const NA = why => `<span class="muted" title="${esc(why)}">not in this trace</span>`;
function renderRail(s) {
  const tr = st.tr, rows = [
    ['Sim clock', `<span class="mono">${clock(s.t)}</span>`],
    ['Deliveries', `${M(s.deliveredN, 'items')} <span class="muted">·</span> ${M(s.deliveredKg / 1000, 't', 1)}`],
    ['Cargo waiting', `${M(s.waitKg / 1000, 't', 1)} <span class="muted">· ${s.waitN} items</span>`],
    ['Vehicles busy', `${M(s.busy, `of ${tr.vehicles.length}`)}`],
    ['Parked for the night', M(s.parkedNight, 'vehicles')],
    ['Caught driving at night', M(s.strandedNight, 'vehicles')],
    ['Sheltering (plume)', s.sheltering === null ? NA('Needs a v2 trace with plume windows') : M(s.sheltering, 'vehicles')],
    ['Energy used', s.energyKwh === null ? NA('Needs a v2 trace (jobs[].energy_kwh)') : M(s.energyKwh, 'kWh')],
    ['Interventions', s.interventions === null ? NA('Needs a v2 trace (jobs[].interventions)') : M(s.interventions, '')],
    ['Fleet cost accrued', s.fleetCostMusd === null ? NA('Needs the trace summary (fleet_cost_musd)') : M(s.fleetCostMusd, 'M USD', 1, 'summary.fleet_cost_musd × elapsed share of the year (amortisation is linear in time); operator cost not included')],
    ['Trips started', M(s.tripsStarted, '')],
    ['Landings', `${M(s.landingsSoFar, `of ${s.landingsTotal}`)}`],
  ];
  $('w-rail-body').innerHTML = rows.map(([k, v]) => `<tr><th scope="row">${k}</th><td>${v}</td></tr>`).join('');
  const w = Object.entries(s.waiting).sort((a, b) => b[1].kg - a[1].kg);
  $('w-waiting').innerHTML = w.length ? w.map(([site, x]) => `<li>${esc(site.replace('_', ' '))}: ${x.n} items, ${(x.kg / 1000).toFixed(1)} t</li>`).join('') : '<li class="muted">none</li>';
  $('w-events').textContent = [s.night ? 'Lunar night.' : '', s.landers.filter(l => l.phase === 'descent').map(l => `${l.landing.type} descending to ${l.landing.pad}.`).join(' '), s.plume.map(p => `Stand-down at ${p.pad}, ${(p.t1 - s.t).toFixed(1)} h left.`).join(' ')].filter(Boolean).join(' ') || '—';
}
function clock(t) { const d = Math.floor(t / 24), h = Math.floor(t % 24), m = Math.floor((t * 60) % 60); return `day ${d}, ${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`; }

if (import.meta.env.DEV) window.__world = { st, draw };  // dev-only probe for checks
boot();
