// /world/ v2 (F-36): one simulated year of the base from a scene package (B-31), chosen from the gallery (B-36) or
// opened from the run queue (?run=<id>, runs/<id>/scene/). The page side: gallery chips, the loading door, scene
// shots (Overview, Pads & keep-out, Rover legs, Base, Night), icons or true scale, play and speed, a timeline with
// landings, nights and Earth set/rise, stat chips, the story card for the current moment and a text mirror. The 3D
// scene loads on Enter (v2-scene.js); Follow keeps the camera on cargo, a rover, the next lander or the base at night;
// "Compare with" adds a second scene of the same seed as ghost rovers with its own chips. Without 3D (tier 0) the same
// controls drive a 2D plan of the package (plan-v2.js). Traces from the browser simulator, the service and trace files
// open in the trace viewer (/world/trace/). Speed (F-50): the shared time scale; overview 1 h/s, close shots and Follow
// 5 min/s until the visitor picks a speed, landings at 10 s a second with their last 60 s at real time, quiet time skipped.
import './v2.css';
import { door, segmented, sceneChips, narrative, statChip, timeline, h, reducedMotion, viewPad } from '../ui/index.js';
import { detectTier } from '../stage/tier.js';
import { loadScene } from './scene-data.js';
import { loadTrajectories } from '../lander/trajectories.js';
import { createTimescale, hoursText, landingX, landingPrefix } from '../ui/timescale.js';
import { motionIndex, quietJump } from './quiet.js';

const $ = id => document.getElementById(id);
const BASE = import.meta.env.BASE_URL;
const q = new URLSearchParams(location.search);
// the old entry points (simulator hand-off, service runs, bundled traces, the 2D plan) belong to the trace viewer
if (q.has('from') || q.has('sample') || q.get('view') === '2d') location.replace(`${BASE}world/trace/${location.search}`);

const fmt = (v, d = 0) => (Number.isFinite(v) ? v.toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d }) : '–');
const day = t => `day ${Math.floor(t / 24)}, ${String(Math.floor(t % 24)).padStart(2, '0')}:${String(Math.floor((t % 1) * 60)).padStart(2, '0')}`;
const GROUP_LABEL = { phases: 'Base size and job rule', pads: 'Pad distance', earth: 'Earth link', fleet: 'Fleet' };
// F-50: the default speed per shot (simulated seconds per second) until the visitor picks one
const SHOT_SPEED = { overview: 3600, pads: 300, legs: 300, base: 300, night: 300 }, CLOSE = 300;

const ui = { scene: q.get('scene') || 'p2-marketplace', run: q.get('run'), shot: 'overview', icons: true, follow: 'none', compare: '' };
// F-40: a moment of the year in the URL hash, written by "Copy link to this moment" (the scene or run stays in the query):
// #t=812.5021&view=pads&follow=rovers&compare=p2-inhouse&cam=x,y,z,tx,ty,tz (hours; camera position and target in metres)
const SHOTS = ['overview', 'pads', 'legs', 'base', 'night'], FOLLOWS = ['none', 'cargo', 'rovers', 'landers', 'night'];
function readHash() {
  const h = new URLSearchParams(location.hash.slice(1)), t = parseFloat(h.get('t')), cam = (h.get('cam') || '').split(',').map(Number);
  return { t: Number.isFinite(t) ? t : null, view: SHOTS.includes(h.get('view')) ? h.get('view') : null, follow: FOLLOWS.includes(h.get('follow')) ? h.get('follow') : null,
    compare: h.get('compare') || '', cam: cam.length === 6 && cam.every(Number.isFinite) ? cam : null };
}
let moment = readHash();
if (moment.follow) ui.follow = moment.follow;
if (moment.compare) ui.compare = moment.compare;
const story = narrative({ label: 'What is happening' });
$('w2-story').append(story.el);
story.set({ eyebrow: 'A year at the base', title: 'Rovers, landers, night and Earth', html: '<p>Press Enter to load the terrain and the year (about 4 MB), then play it.</p>' });
const status = m => { $('w2-status').textContent = m; };

let gallery = null;
try { gallery = await (await fetch(BASE + 'scenes/gallery.json')).json(); } catch (e) { status(`Could not load the scene gallery (${e.message}).`); }
const entry = () => gallery?.scenes.find(s => s.id === ui.scene) || gallery?.scenes[0];
if (gallery && !ui.run) drawGallery();
headline();

const tierInfo = await detectTier();
let sc = null, pkg = null, chunks = [], traj = null, tl = null, shotChips = null, followSeg = null, chips = {}, pkgB = null, chunksB = [], chipsB = null, linkChip = null, linkText = '', followStart = false;
let lastSlow = 0, lastStory = '', ts = null, motion = null;   // module state is declared before the tier-0 path runs open() at load
const time = { t: 0, playing: false };
if (tierInfo.tier === 0 && !tierInfo.forced || q.get('view2d') === '1') {
  const mod = await import('./plan-v2.js');
  sc = mod.createPlanScene({ host: $('w2-view'), canvas: $('w2-canvas') });
  $('w2-shots').hidden = true;
  status(`No 3D on this device (${tierInfo.gpu}): the 2D plan shows the same year.`);
  controls(true);
  await open();
} else {
  const gate = door({ title: 'A year at the base', subtitle: 'One simulated year on the real terrain round the base: rovers, landers, the night and Earth.',
    skip: { href: '#w2-mirror-h', label: 'Skip to the text version' }, enterLabel: 'Enter the 3D world', beforeOpen: () => start(gate) });
  $('w2-view').append(gate.el); gate.ready();
}

function drawGallery() {
  const host = $('w2-gallery'); host.replaceChildren();
  for (const [g, label] of Object.entries(GROUP_LABEL)) {
    const scenes = gallery.scenes.filter(s => s.group === g); if (!scenes.length) continue;
    host.append(sceneChips({ label, scenes: scenes.map(s => ({ value: s.id, label: s.title })), value: scenes.some(s => s.id === ui.scene) ? ui.scene : null,
      onChange: id => { ui.scene = id; { const u = new URL(location.href); u.searchParams.set('scene', id); u.hash = ''; history.replaceState(null, '', u); } drawGallery(); headline(); if (sc) open(); } }).el);
  }
}
function headline() {
  const e = entry(), host = $('w2-headline');
  if (ui.run) { host.replaceChildren(h('p', {}, `Run ${ui.run} from the run queue.`)); return; }
  if (!e) return;
  $('w2-scene-title').textContent = e.title; $('w2-scene-desc').textContent = e.description;
  const m = gallery.metrics.filter(k => e.headline?.[k.key]);
  host.replaceChildren(...m.map(k => statChip({ label: k.label, value: e.headline[k.key].mean, unit: k.unit, digits: k.digits, flag: k.flag,
    source: `${gallery.common.seeds} seeds, mean ± ${fmt(e.headline[k.key].ci95, k.digits)} (95 %); ${e.source || 'data/scenes/gallery.json'}` }).el));
}

// ---------- start: the 3D scene, the trajectories, the package ----------
async function start(gate) {
  const fetchFn = label => url => gate.fetch(url, { label });
  const [mod, tj] = await Promise.all([import('./v2-scene.js'), loadTrajectories(BASE + 'lab/policies/trajectories-v1.json', { fetchFn: fetchFn('landing recordings') }).catch(() => null)]);
  traj = tj;
  sc = await mod.createWorldScene({ canvas: $('w2-canvas'), labelsHost: $('w2-labels'), tier: Math.max(1, tierInfo.tier), fetchFn: fetchFn('catalogue'),
    onStatus: s => status(s === 'lost' ? 'The graphics context was lost; it will come back by itself.' : '') });
  if (import.meta.env.DEV) window.__w2 = { sc, ui, time, get pkg() { return pkg; } };
  sc.stage.director.bindKeys($('w2-canvas')); $('w2-view').append(viewPad(sc.stage.director));   // F-40: orbit and zoom without a drag
  { let down = null; const cv = $('w2-canvas');   // F-51: a click (not a drag) on a rover or lander opens Look inside
    cv.addEventListener('pointerdown', e => { down = [e.clientX, e.clientY]; });
    cv.addEventListener('click', e => { if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5) return; const hit = sc.pickAt?.(e.clientX, e.clientY); if (hit) { picked = hit; openInside(hit); } }); }
  sc.stage.director.limits({ minDistance: 20, maxDistance: 22000, maxPolar: 88 });
  controls();
  await open(fetchFn('the year'));
}

async function open(fetchFn = fetch) {
  setPlaying(false);
  const base = ui.run ? `${BASE}runs/${encodeURIComponent(ui.run)}/scene/` : `${BASE}scenes/${entry().package}/`;
  status('Loading the year…');
  try {
    pkg = await loadScene(base, { fetchFn });
    chunks = await Promise.all(pkg.index.chunks.map((_, k) => pkg.chunk(k)));
  } catch (e) { status(`Could not load ${ui.run ? 'run ' + ui.run : 'the scene'} (${e.message}).`); return; }
  pkg.index.landings.sort((a, b) => a.t_h - b.t_h);   // the code below takes the next landing in array order
  motion = motionIndex(pkg, chunks);
  sc.setPackage(pkg, traj); sc.shots();
  sc.setNoLink(!!pkg.index.comms && pkg.index.comms.mode !== 'off');   // F-40: legs a rover waits to start for want of an Earth link turn red
  linkChip?.el.remove(); linkChip = null; linkText = '';
  if (ui.compare) { compareSelect.fill?.(); await openCompare(); }
  if (urgentP90(pkg.index, 0) === null) chips.urgent.el.querySelector('.ui-label').textContent = 'Urgent: 90 % within (whole year)';
  const idx0 = pkg.index, L0 = idx0.landings.find(L => L.ok && !nightAt(L.t_h)) || idx0.landings[0];
  time.t = L0 ? Math.max(0, L0.t_h - 0.1) : 0;
  update(true);
  if (moment.t !== null) { await applyMoment(moment); moment.t = null; drawTimeline(); update(true); status(`The moment from the link: ${day(time.t)}. Press Play to go on.`); return; }
  if (L0 && sc.frameAt) { ui.shot = 'pads'; shotChips?.set('pads'); await sc.frameAt(sc.sitePos(L0.pad), 600, 22, 35, true); }
  else await sc.go(ui.shot, true);
  shotSpeed();
  drawTimeline(); update(true); status('');
  if (!reducedMotion()) setPlaying(true);
}

// ---------- controls ----------
function controls(plan = false) {
  shotChips = sceneChips({ label: 'Scenes', scenes: [{ value: 'overview', label: 'Overview' }, { value: 'pads', label: 'Pads & keep-out' }, { value: 'legs', label: 'Rover legs' }, { value: 'base', label: 'Base' }, { value: 'night', label: 'Night' }],
    value: ui.shot, onChange: v => chooseShot(v) });
  if (!plan) $('w2-shots').append(shotChips.el);
  const r1 = $('w2-row1');
  const play = h('button', { class: 'ui-btn primary', type: 'button', id: 'w2-play', 'aria-pressed': 'false' }, 'Play');
  play.addEventListener('click', () => setPlaying(!time.playing));
  ts = createTimescale({ value: CLOSE, skip: true, onPlayPause: () => { if (pkg) setPlaying(!time.playing); } });
  r1.append(play, ts.el,
    plan ? '' : segmented({ legend: 'Vehicles', options: [{ value: 'icons', label: 'Icons' }, { value: 'true', label: 'True scale' }], value: 'icons', onChange: v => {
      ui.icons = v === 'icons'; sc.setIcons(ui.icons); update(true);
      if (!ui.icons) { const f = sc.followTarget?.('rovers', time.t, pkg.hourly(chunks[pkg.chunkIndex(time.t)], time.t)); if (f) sc.frameAt(f.pos, 45, 18, 35);
        status(`True scale: vehicles at their real size (an LTV is ${fmt(sc.catalog.entry('LTV').dims.length_m.value, 1)} m long); from the overview they would be dots.`); }
      else { sc.go(ui.shot); status(''); }
    } }).el,
    plan ? '' : (followSeg = segmented({ legend: 'Follow', options: [{ value: 'none', label: 'Free' }, { value: 'cargo', label: 'Cargo' }, { value: 'rovers', label: 'Rovers' }, { value: 'landers', label: 'Landers' }, { value: 'night', label: 'Night' }],
      value: ui.follow, onChange: v => { ui.follow = v; sc.clearFollow?.(); followStart = true; if (v === 'night') nextNight(); if (v === 'none') status(''); shotSpeed(); update(true); } })).el,
    plan ? '' : h('label', { class: 'w2-check' }, h('input', { type: 'checkbox', checked: true, onchange: e => sc.setTrails?.(e.target.checked) }), ' Trails (last 2 h)'),
    compareSelect(), h('button', { class: 'ui-btn', type: 'button', id: 'w2-copy', onclick: copyMoment }, 'Copy link to this moment'),
    plan ? '' : h('button', { class: 'ui-btn', type: 'button', id: 'w2-inside', onclick: () => openInside(picked || insideDefault()) }, 'Look inside a vehicle'));
  const host = $('w2-chips');
  chips = {
    delivered: statChip({ label: 'Delivered so far', value: 0, unit: 't', digits: 1, flag: 'Modelled', source: "Sum of the deliveries up to this moment (the scene package's scene.json → deliveries)", tone: 'cool' }),
    waiting: statChip({ label: 'Waiting now', value: 0, unit: 't', digits: 1, flag: 'Modelled', source: 'Cargo waiting at all sites this hour (scene package hourly series)', tone: 'warm' }),
    trips: statChip({ label: 'Trips done', value: 0, unit: '', digits: 0, flag: 'Modelled', source: 'Jobs finished up to this moment (scene package job list)' }),
    urgent: statChip({ label: 'Urgent: 90 % delivered within', value: NaN, unit: 'h', digits: 1, flag: 'Modelled', source: "90th percentile of the wait (ready to delivered) of the priority-1 deliveries so far (the scene package's scene.json → deliveries)", tone: 'warm' }),
  };
  host.append(...Object.values(chips).map(c => c.el));
}
// F-50: overview 1 h/s, close shots and Follow 5 min/s, unless the visitor (or ?speed=) chose a speed
function shotSpeed() { if (ts && !ts.touched) ts.set(ui.follow !== 'none' ? CLOSE : SHOT_SPEED[ui.shot] ?? CLOSE); }
// F-51 part 4: Look inside: the vehicle viewer in a side panel (lazy), for the clicked vehicle, else a driving rover;
// the year pauses while it is open (two 3D views at once are heavy)
let picked = null;
const insideDefault = () => { const v = sc.vehicles.find(q => q.state === 'driving') || sc.vehicles[0]; return v ? { cls: v.cls, what: `${v.cls} ${v.id}` } : { cls: 'LTV', what: 'LTV' }; };
async function openInside(hit) { setPlaying(false); const { lookInside } = await import('../ui/look-inside.js'); lookInside(hit.cls, { name: hit.what }); }
function nightAt(t) { return pkg.index.nights.some(([a, b]) => t >= a && t < b); }   // hoisted: the tier-0 path calls open() at load
// Pads: play up to the next landing and frame the pads with their rings; Rover legs: a driving rover at rover scale;
// Base: the base cluster; Night: the next night, framed on a rover that works in the dark (its headlights) or the base
function chooseShot(v) {
  ui.shot = v; lastStory = '';
  const idx = pkg.index, hrNow = () => pkg.hourly(chunks[pkg.chunkIndex(time.t)], time.t);
  if (v === 'pads') { const n = idx.landings.find(L => L.t_h > time.t + 0.15) || idx.landings[0]; if (n) seek(n.t_h - 0.12); sc.go('pads'); }
  else if (v === 'legs') {
    // nobody driving now: play ahead (up to 3 days, quarter-hour steps) to the next moment a rover is on the road
    const driving = t => { const ch = chunks[pkg.chunkIndex(t)]; return pkg.index.vehicles.some(q => pkg.position(ch, q.id, t)?.driving); };
    if (!driving(time.t)) for (let t = time.t + 0.25; t < Math.min(pkg.horizon - 1e-3, time.t + 72); t += 0.25) if (driving(t)) { seek(t + 0.05); break; }
    let f = sc.followTarget?.('rovers', time.t, hrNow());
    if (f && sc.frameAt) sc.frameAt(f.pos, 260, 30, 35); else sc.go('legs');
  } else if (v === 'night') {
    nextNight();
    const hn = sc.vehicles.find(q => q.night_ops && q.group?.visible);
    if (sc.frameAt) sc.frameAt(hn ? hn.group.position : sc.sitePos('BASE'), hn ? 320 : 800, 20, 35); else sc.go('night');
  } else sc.go(v);
  shotSpeed(); update(true);
}
function nextNight() { const n = pkg.index.nights.find(([, b]) => b > time.t) || pkg.index.nights[0]; if (n && !(time.t >= n[0] && time.t < n[1])) seek(n[0] + 2); }
function compareSelect() {
  if (!gallery || ui.run) return '';
  const sel = h('select', { id: 'w2-compare', class: 'w2-select' }, h('option', { value: '' }, 'nothing'));
  const fill = () => { sel.replaceChildren(h('option', { value: '' }, 'nothing'), ...gallery.scenes.filter(x => x.id !== ui.scene).map(x => h('option', { value: x.id }, x.title))); sel.value = ui.compare; };
  fill(); compareSelect.fill = fill;
  sel.addEventListener('change', () => { ui.compare = sel.value; openCompare(); });
  return h('label', { class: 'w2-compare' }, h('span', { class: 'ui-label' }, 'Compare with (same seed)'), sel);
}
async function openCompare() {
  chipsB?.forEach(c => c.el.remove()); chipsB = null; pkgB = null; chunksB = []; sc.setCompare?.(null);
  const e = gallery?.scenes.find(x => x.id === ui.compare);
  if (!e) { update(true); return; }
  status(`Loading ${e.title} to compare…`);
  try { pkgB = await loadScene(`${BASE}scenes/${e.package}/`); chunksB = await Promise.all(pkgB.index.chunks.map((_, k) => pkgB.chunk(k))); }
  catch (err) { status(`Could not load ${e.title} (${err.message}).`); pkgB = null; return; }
  if (pkgB.index.seed !== pkg.index.seed) status(`Note: ${e.title} is seed ${pkgB.index.seed}, this scene seed ${pkg.index.seed}.`); else status('');
  sc.setCompare?.(pkgB);
  const src = `${e.title}, same seed (scene package)`;
  chipsB = [statChip({ label: `B · delivered so far`, value: 0, unit: 't', digits: 1, flag: 'Modelled', source: src, tone: 'cool' }),
    statChip({ label: `B · waiting now`, value: 0, unit: 't', digits: 1, flag: 'Modelled', source: src, tone: 'warm' })];
  $('w2-chips').append(...chipsB.map(c => c.el));
  update(true);
}
// numpy-style (linear) 90th percentile of the priority-1 waits delivered by time t; null when the package has no columns
function urgentP90(idx, t) {
  const cols = idx.delivery_columns || [], pi = cols.indexOf('priority'), wi = cols.indexOf('wait_h');
  if (pi < 0 || wi < 0) return null;
  const w = idx.deliveries.filter(d => d[pi] === 1 && d[0] <= t).map(d => d[wi]).sort((a, b) => a - b);
  if (!w.length) return NaN;
  const r = 0.9 * (w.length - 1), lo = Math.floor(r);
  return w[lo] + (w[Math.min(lo + 1, w.length - 1)] - w[lo]) * (r - lo);
}
// direct when any part of Earth's disc is above the horizon at BASE; otherwise relay only (if the scene has a relay) or none
function linkState(idx, hr) {
  if (!idx.comms) return null;
  if (hr.earth_el_deg + hr.earth_radius_deg > 0) return 'direct to Earth';
  return idx.comms.mode.includes('relay') ? 'relay only' : 'none';
}

function setPlaying(v) {
  time.playing = v; const b = $('w2-play'); if (!b) return;
  b.textContent = v ? 'Pause' : 'Play'; b.setAttribute('aria-pressed', String(v));
  if (v) { if (time.t >= pkg.horizon - 1) time.t = 0; sc.stage.animate(tick); }
}
function tick(dt) {
  if (!time.playing) return false;
  // a descent at 10 sim-seconds per second, its last 60 s at real time (the shared landing rule), so the landing is seen
  const act = sc.activeLandings[0], landing = !!act, toTd = act ? (act.t_h - time.t) * 3600 : Infinity, lx = act ? landingX(toTd, ts.x) : 0;
  const rate = landing ? lx / 3600 : ts.h;
  ts.override(landing ? lx : null, landingPrefix(toTd));
  // one frame at 1 day/s is ~0.4 h and a descent ~0.05 h: stop at the next descent's start instead of stepping over it
  let next = time.t + dt * rate;
  const s0 = !landing && sc.nextLandingStart ? sc.nextLandingStart(time.t) : Infinity;
  if (s0 <= next) next = s0 + 1e-4;
  // F-50: nothing driving and no landing near: jump to a second before the next drive or landing
  else if (!landing && ts.skip && motion) { const j = quietJump(time.t, rate, motion, s0); if (j !== null && j > next) { ts.toast(`Skipped ${hoursText(j - time.t)}, nothing moving`); next = j; } }
  time.t = Math.min(pkg.horizon - 1e-3, next);
  update();
  if (time.t >= pkg.horizon - 1e-3) setPlaying(false);
  return time.playing;
}
// a moment from the hash: that hour, view, follow mode and camera, paused (a shared link shows what was shared)
async function applyMoment(m) {
  time.t = Math.max(0, Math.min(pkg.horizon - 1e-3, m.t)); tl?.set(time.t);
  if (m.view) { ui.shot = m.view; shotChips?.set(m.view); }
  if (m.follow) { ui.follow = m.follow; followSeg?.set(m.follow); followStart = !m.cam; }
  update(true);
  const c = sc.stage.director.controls;
  if (m.cam && c) c.setLookAt(...m.cam, false); else await sc.go(ui.shot, true);
  update(true);
}
async function copyMoment() {
  if (!pkg) return;
  const c = sc.stage.director.controls, r = v => Math.round(v * 10) / 10;
  let hash = `t=${time.t.toFixed(4)}&view=${ui.shot}${ui.follow !== 'none' ? '&follow=' + ui.follow : ''}${ui.compare ? '&compare=' + encodeURIComponent(ui.compare) : ''}`;
  if (c) { const v = sc.stage.camera.position, p = c.getPosition(v.clone()), g = c.getTarget(v.clone()); hash += '&cam=' + [p.x, p.y, p.z, g.x, g.y, g.z].map(r).join(','); }
  const url = `${location.origin}${location.pathname}${ui.run ? '?run=' + encodeURIComponent(ui.run) : '?scene=' + ui.scene}#${hash}`;
  history.replaceState(null, '', url);
  status(`The link to ${day(time.t)} is in the address bar.`);   // stays if the clipboard is refused or never answers
  try { await navigator.clipboard.writeText(url); status(`Link to ${day(time.t)} copied.`); } catch { /* the address bar has it */ }
}
addEventListener('hashchange', () => {   // a pasted link on the open page
  const m = readHash(); if (m.t === null || !pkg) return;
  setPlaying(false);
  if (m.compare !== ui.compare) { ui.compare = m.compare; compareSelect.fill?.(); openCompare(); }
  applyMoment(m);
});
function seek(t) { time.t = Math.max(0, Math.min(pkg.horizon - 1e-3, t)); tl?.set(time.t); update(true); }   // F-40: the timeline follows a seek while paused

// ---------- timeline: landings, nights (bands), Earth set and rise, Earth-link waits ----------
function drawTimeline() {
  const idx = pkg.index, ev = idx.landings.map(L => ({ t: L.t_h, kind: 'landing', label: `${L.cls} lands at ${L.pad.replace('_', ' ')}${L.ok ? '' : ' (failed: ' + L.failure_kind + ')'}` }));
  // Earth set/rise at BASE from the hourly series (upper limb against the geometric horizon)
  let up = null;
  for (const ch of chunks) for (let i = 0; i < ch.hRows; i++) {
    const t = ch.firstHour + i, hr = pkg.hourly(ch, t + 0.5), now = hr.earth_el_deg + hr.earth_radius_deg > 0;
    if (up !== null && now !== up) ev.push({ t, kind: 'info', label: now ? 'Earth rises' : 'Earth sets' });
    up = now;
  }
  for (const w of idx.comms_waits || []) if (w[4] === 'start') ev.push({ t: w[1], kind: 'strand', label: `Rover ${w[0]} waits for Earth (${w[3]})` });
  ev.sort((a, b) => a.t - b.t);
  const el = timeline({ label: 'Time in the year', min: 0, max: pkg.horizon, step: 'any', value: time.t, format: day, events: ev,
    bands: idx.nights.map(([a, b]) => ({ from: a, to: b })), bandLabel: 'Lunar night', onInput: v => { setPlaying(false); seek(v); } });
  if (tl) tl.el.replaceWith(el.el); else $('w2-time').append(el.el);
  tl = el; ui.events = ev;
}

// ---------- the moment ----------
function update(force = false) {
  if (!sc || !pkg) return;
  const t = time.t, k = pkg.chunkIndex(t), ch = chunks[k];
  sc.setTime(t, ch, pkgB ? chunksB[pkgB.chunkIndex(t)] : null);
  const now = performance.now();
  if (!force && now - lastSlow < 250) return;
  lastSlow = now;
  const idx = pkg.index, hr = pkg.hourly(ch, t);
  const delivered = idx.deliveries.reduce((s, d) => s + (d[0] <= t ? d[2] : 0), 0) / 1000;
  const waiting = Object.values(hr.waiting).reduce((s, w) => s + w.kg, 0) / 1000;
  const trips = idx.jobs.reduce((s, j) => s + (j[1] !== 'reposition' && j[5] <= t ? 1 : 0), 0);
  chips.delivered.set(delivered); chips.waiting.set(waiting); chips.trips.set(trips);
  const u = urgentP90(idx, t); chips.urgent.set(u === null ? idx.summary?.delay_prio1_p90_h : u);
  if (u !== null) { const lab = Number.isNaN(u) ? 'Urgent: none delivered yet' : 'Urgent: 90 % delivered within', le = chips.urgent.el.querySelector('.ui-label'); if (le.textContent !== lab) le.textContent = lab; }   // F-40: say why there is no value early in the year
  const link = linkState(idx, hr);
  if (link !== null && link !== linkText) {
    linkText = link; linkChip?.el.remove();
    linkChip = statChip({ label: 'Earth link now', text: link, flag: 'Modelled', source: `Earth's hourly elevation at BASE (terrain horizon not applied here); link mode ${idx.comms.mode}${idx.comms.mode.includes('relay') ? ', relay up about 80 % of hours (its windows are not in the package)' : ''} (the scene package: scene.json → comms, the hourly chunks → earth_el_deg)` });
    $('w2-chips').insertBefore(linkChip.el, chips.urgent.el.nextSibling);
  }
  if (pkgB && chipsB) {
    const chB = chunksB[pkgB.chunkIndex(t)], hb = pkgB.hourly(chB, t);
    chipsB[0].set(pkgB.index.deliveries.reduce((a, d) => a + (d[0] <= t ? d[2] : 0), 0) / 1000);
    chipsB[1].set(Object.values(hb.waiting).reduce((a, w) => a + w.kg, 0) / 1000);
  }
  if (ui.follow !== 'none' && sc.followTarget) {
    const f = sc.followTarget(ui.follow, t, hr), c = sc.stage.director.controls;
    if (f) {
      c.moveTo(f.pos.x, f.pos.y, f.pos.z, !reducedMotion());
      if (followStart) { c.dollyTo(f.dist, !reducedMotion()); followStart = false; }
      status(`Following ${f.what}.`);
    }
  }
  if (tl && time.playing) tl.set(t);
  narrate(t, hr);
  mirror(t, hr, delivered, waiting, trips);
}

function narrate(t, hr) {
  const idx = pkg.index, act = sc.activeLandings[0], vs = sc.vehicles, count = st => vs.filter(v => v.state === st).length;
  let s;
  const last = idx.landings.filter(L => L.t_h <= t && t - L.t_h < 6).pop();
  if (act) s = { eyebrow: 'Landing', title: `A ${act.cls}-class lander comes down at ${act.pad.replace('_', ' ')}`, html: `<p>It carries ${fmt(act.cargo_kg)} kg. Rovers stay outside the ${fmt((idx.keepout_windows.find(k => k[2] === act.pad && k[1] >= act.t_h) || [0, 0, 0, 1])[3], 1)} km keep-out ring until the dust settles; the descent replays the recorded ${act.trajectory?.pilot || 'classical'} landing nearest this one (${fmt(act.miss_m, 1)} m from the pad centre).</p>` };
  else if (last) s = { eyebrow: 'Landed', title: last.ok ? `Down at ${last.pad.replace('_', ' ')}, ${fmt(last.miss_m, 1)} m from the centre` : `A failed landing at ${last.pad.replace('_', ' ')}`, html: `<p>${last.ok ? 'Its cargo now waits on the pad for a rover.' : `It failed (${last.failure_kind}); its cargo is lost.`}</p>` };
  else if (hr.night > 0.5) s = { eyebrow: 'Lunar night', title: `${count('parked_night')} of ${vs.length} rovers parked`, html: '<p>The sun is below the horizon for days. Rovers without night power park; those with headlights and batteries keep working.</p>' };
  else if (count('waiting_for_earth')) s = { eyebrow: 'No Earth link', title: `${count('waiting_for_earth')} rover${count('waiting_for_earth') > 1 ? 's' : ''} waiting for Earth`, html: '<p>Supervised rovers need a link to Earth to drive. Earth is below the ridge line now, so they hold until it rises.</p>' };
  else if (count('standdown')) s = { eyebrow: 'Keep-out', title: 'Holding outside the landing zone', html: '<p>A lander is due; rovers keep out of the plume ring until the stand-down ends.</p>' };
  else s = chipStory(t, hr, count);
  const key = s.eyebrow + s.title; if (key === lastStory) return; lastStory = key; story.set(s);
}

function chipStory(t, hr, count) {
  const idx = pkg.index, place = p => p.replace('_', ' '), inH = h => h > 48 ? `${fmt(h / 24)} days` : `${fmt(h, 1)} h`;
  if (ui.shot === 'pads') {
    const n = idx.landings.find(L => L.t_h > t), w = n && idx.keepout_windows.find(k => k[2] === n.pad && k[1] >= n.t_h);
    return n ? { eyebrow: 'Pads & keep-out', title: `Next landing: a ${n.cls}-class lander at ${place(n.pad)} in ${inH(n.t_h - t)}`,
      html: `<p>${w ? `While it lands, rovers keep outside a ${fmt(w[3], 1)} km ring round the pad for ${fmt(w[1] - w[0], 1)} h, then go in for its ${fmt(n.cargo_kg)} kg of cargo.` : `It brings ${fmt(n.cargo_kg)} kg of cargo.`}</p>` }
      : { eyebrow: 'Pads & keep-out', title: 'No landings left this year', html: '<p>Cargo already on the pads waits for a rover.</p>' };
  }
  if (ui.shot === 'legs') {
    const legs = sc.activeLegs?.() || [], v = sc.vehicles.find(q => q.state === 'driving');
    return { eyebrow: 'Rover legs', title: legs.length ? `${legs.length} leg${legs.length > 1 ? 's' : ''} in use now` : 'No rover on the road right now',
      html: `<p>${legs.length ? `Bright lines are the legs being driven: ${legs.slice(0, 3).map(place).join('; ')}${legs.length > 3 ? '…' : ''}.` : 'The faint lines are the planned routes between the sites.'}${v ? ` ${v.cls} ${v.id} is driving${v.load > 0 ? ` with ${fmt(v.load)} kg` : ' empty'}.` : ''}</p>` };
  }
  if (ui.shot === 'base') {
    const w = hr.waiting.BASE || { items: 0, kg: 0 };
    return { eyebrow: 'Base', title: w.items ? `${fmt(w.items)} item${w.items > 1 ? 's' : ''} waiting at the base` : 'Nothing waiting at the base',
      html: `<p>${w.items ? `${fmt(w.kg)} kg sits on pallets at the habitat until a rover moves it on.` : 'Deliveries to the base have kept up.'} ${count('loading')} rover${count('loading') === 1 ? ' is' : 's are'} loading or unloading somewhere on the base.</p>` };
  }
  if (ui.shot === 'night') {
    const n = idx.nights.find(([, b]) => b > t);
    return { eyebrow: 'Night', title: n ? `The next night begins in ${inH(n[0] - t)}` : 'No more nights this year',
      html: '<p>At the pole the sun circles the horizon and dips below the ridges for days at a time. Only rovers with night power keep driving, by headlight.</p>' };
  }
  return { eyebrow: day(t), title: `${count('driving') + count('team_lift')} driving, ${count('loading')} loading`, html: '<p>Rovers carry cargo between the pads, the depot and the base along their planned routes. Cargo waiting at each site stacks up as pallets.</p>' };
}

function mirror(t, hr, delivered, waiting, trips) {
  const idx = pkg.index, rows = [
    ['Scene', ui.run ? `run ${ui.run}` : `${entry().title} (seed ${idx.seed})`], ['Time', day(t)],
    ['Sun', hr.night > 0.5 ? 'below the horizon (night)' : `azimuth ${fmt(hr.sun_az_deg)}°, 1.5° up`],
    ['Earth seen from BASE', `${fmt(hr.earth_el_deg, 1)}° up, bearing ${fmt(hr.earth_bearing_deg, 1)}°${hr.earth_el_deg + hr.earth_radius_deg > 0 ? '' : ' (below the horizon)'}`],
    ['Delivered so far', `${fmt(delivered, 1)} t`], ['Waiting now', `${fmt(waiting, 1)} t`], ['Trips done', fmt(trips)],
    ...sc.vehicles.map(v => [`${v.cls} ${v.id} (${v.owner})`, `${(sc.STATE_STYLE[v.state] || [0, v.state])[1]}${v.load > 0 ? `, carrying ${fmt(v.load)} kg` : ''}`]),
    ...Object.entries(hr.waiting).filter(([, w]) => w.items > 0).map(([s, w]) => [`Waiting at ${s.replace('_', ' ')}`, `${fmt(w.items)} items, ${fmt(w.kg)} kg`]),
  ];
  $('w2-mirror').replaceChildren(...rows.flatMap(([a, b]) => [h('dt', {}, a), h('dd', {}, b)]));
}
