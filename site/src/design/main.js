// /design/ (development page, F-30): every Phase 4 UI component in the instrument and the reading theme, and a
// contrast table computed live from the CSS variables over several backdrops. The vehicle numbers come from the
// catalogue (lunarsim/catalog-v1.json, B-30), like on every 3D page.
import './design.css';
import { segmented, statChip, narrative, callouts, sceneChips, timeline, door, counter, tooltip, h } from '../ui/index.js';
import { num } from '../components/num.js';
import { rgba, over, ratio, tokens } from '../ui/contrast.js';
import { loadCatalog } from '../catalog.js';

const $ = id => document.getElementById(id);
const BASE = import.meta.env.BASE_URL;
const SUN_EL = 1.5;   // degrees: the polar sun elevation (research notes §2.2)
const cat = await loadCatalog();
const height = cat.q('MK1', 'dims.height_m', { digits: 2 });
const SPEC = {
  height, diameter: cat.q('MK1', 'dims.diameter_m', { digits: 2 }),
  thrust: cat.q('MK1', 'gate.t_max_n', { scale: 1e-3, unit: 'kN', digits: 0 }),
  shadow: { value: height.value / Math.tan(SUN_EL * Math.PI / 180), unit: 'm', flag: 'Modelled', digits: 0,
    source: `catalogue height ${height.value} m / tan(${SUN_EL}°), the polar sun elevation (research notes §1.7)` },
};

// ---------- shared specimen content ----------
const steps = [
  { eyebrow: 'Whole', title: 'A Blue Moon MK1-class lander', html: `<p>A representative model at true scale: ${num(SPEC.height)} tall and ${num(SPEC.diameter)} across. Its one hydrogen-oxygen engine leaves an almost invisible plume.</p>` },
  { eyebrow: 'Cutaway', title: 'Inside: tanks and feed lines', html: '<p>The cut shows tank walls as solid sections, so their thickness reads correctly. The landing legs are a representative shape: the real layout is unpublished.</p>' },
  { eyebrow: 'On site', title: 'Under a 1.5° sun', html: `<p>At the south pole the sun stays near the horizon, so this lander casts a shadow about ${num(SPEC.shadow)} long.</p>` },
];
const modes = [{ value: 'whole', label: 'Whole' }, { value: 'cutaway', label: 'Cutaway' }, { value: 'exploded', label: 'Exploded' }];
const follow = [{ value: 'all', label: 'All' }, { value: 'prop', label: 'Propellant' }, { value: 'power', label: 'Power' }, { value: 'cargo', label: 'Cargo' }];
const scenes = [{ value: 'landers', label: 'Landers', note: '3 classes' }, { value: 'rovers', label: 'Rovers', note: '3 classes' }, { value: 'base', label: 'Base', note: '6 elements' }];
const chipSpecs = [
  { label: 'Height', ...SPEC.height }, { label: 'Diameter', ...SPEC.diameter },
  { label: 'Engine thrust', tone: 'warm', ...SPEC.thrust }, { label: 'Shadow', tone: 'cool', ...SPEC.shadow },
];
// a specimen year: landings, nightfalls with night bands, one stranding (MOCK: the world page reads the trace)
const DAY = 29.53, events = [], bands = [];
for (let k = 0; k < 13; k++) {
  const n0 = 12 + k * DAY;
  if (n0 < 365) { events.push({ t: n0, kind: 'night', label: `night ${k + 1} begins` }); bands.push({ from: n0, to: Math.min(365, n0 + 9.5) }); }
  const l = 4 + k * 28.1;
  if (l < 365) events.push({ t: l, kind: 'landing', label: `landing ${k + 1}` });
}
events.push({ t: 201.4, kind: 'strand', label: 'rover HAUL-2 stranded' });
const dayFmt = v => { const d = Math.floor(v), hh = Math.floor((v - d) * 24); return `Day ${d + 1}, ${String(hh).padStart(2, '0')}:00`; };

function counterBox(slot) {
  const c = counter({ label: 'Score', value: -71, unit: 'pts', unitLabel: 'points' });
  const row = h('div', { class: 'd-counter-ctl' },
    h('button', { class: 'ui-btn', type: 'button', onclick: () => c.set(c.value - 25) }, '−25'),
    h('button', { class: 'ui-btn', type: 'button', onclick: () => c.set(c.value + 25) }, '+25'),
    h('button', { class: 'ui-btn', type: 'button', onclick: () => { c.set(-71, { animate: false }); setTimeout(() => { c.set(40); c.commit(); }, 50); } }, 'Play −71 to +40'));
  slot.append(c.el, row);
  return c;
}

// ---------- instrument stage ----------
const stage = $('d-stage'), view = $('d-view');
const story = narrative({ steps, label: 'Lander story' });
$('i-story').append(story.el);
counterBox($('i-counter'));
$('i-scenes').append(sceneChips({ label: 'Scenes', scenes, value: 'landers' }).el);
for (const s of chipSpecs) $('i-chips').append(statChip(s).el);
$('i-modes').append(
  segmented({ legend: 'View', options: modes, onChange: v => story.go(modes.findIndex(m => m.value === v)) }).el,
  segmented({ legend: 'Follow', options: follow }).el);
$('i-timeline').append(timeline({ label: 'Simulated year (specimen)', min: 0, max: 365, step: 1 / 24, value: 0, format: dayFmt, events, bands }).el);

const layer = callouts(view);
const PARTS = [['lh2', 'Hydrogen tank'], ['lox', 'Oxygen tank'], ['engine', 'BE-7 engine', 'warm'], ['leg', 'Landing leg'], ['solar', 'Solar array']];
let picked = null;
const pills = PARTS.map(([id, text, tone]) => layer.add({ id, text, tone, onSelect: pid => {
  picked = picked === pid ? null : pid;
  for (const p of pills) p.setPressed(p.id === picked);
} }));
function placeCallouts() {
  const box = view.getBoundingClientRect();
  for (const p of pills) {
    const a = view.querySelector(`[data-anchor="${p.id}"]`).getBoundingClientRect();
    p.place(a.left + a.width / 2 - box.left, a.top + a.height / 2 - box.top);
  }
  layer.layout();
}
new ResizeObserver(placeCallouts).observe(view);

$('d-backdrop-ctl').append(segmented({
  legend: 'Behind the glass',
  options: [{ value: 'scene', label: 'Lunar scene' }, { value: 'black', label: 'Black' }, { value: 'grey', label: 'Mid grey' }, { value: 'regolith', label: 'Sunlit regolith' }, { value: 'white', label: 'White' }],
  onChange: v => { stage.dataset.bg = v; },
}).el);

// ---------- loading door (real fetches of the terrain pack) ----------
const PACK = ['meta.json', 'sites.json', 'hillshade_20m.png', 'slope_20m.png', 'height_20m.png'];
let gate;
async function runDoor() {
  if (gate) gate.el.remove();
  gate = door({
    title: 'Connecting Ridge, 16 km', subtitle: 'LOLA terrain from NASA PGDA, 20 m posts. The 3D view opens when it has loaded.',
    skip: { href: '#door-text', label: 'Skip to the text version' },
    onEnter: ({ focus }) => { if (focus) $('door-after').focus(); },
  });
  $('door-box').append(gate.el);
  try {
    await Promise.all(PACK.map(f => gate.fetch(`${BASE}terrain/hero/${f}`, { label: f })));
    gate.ready();
  } catch (e) { gate.fail(`Could not load the terrain (${e.message}).`); }
}
$('door-replay').addEventListener('click', runDoor);
runDoor();

// ---------- reading theme ----------
const rStory = narrative({ steps, label: 'Lander story (reading theme)', level: 4 });
$('r-story').append(rStory.el);
$('r-seg').append(segmented({ legend: 'View', options: modes, name: 'r-view' }).el, segmented({ legend: 'Follow', options: follow, name: 'r-follow' }).el);
for (const s of chipSpecs) $('r-chips').append(statChip(s).el);
$('r-scenes').append(sceneChips({ label: 'Scenes (reading theme)', scenes, value: 'rovers' }).el);
$('r-timeline').append(timeline({ label: 'Simulated year (specimen)', min: 0, max: 365, step: 1 / 24, value: 120, format: dayFmt, events, bands }).el);
counterBox($('r-counter'));
tooltip($('r-tip'), 'Every number carries a flag: Measured, Spec, Modelled or Assumed. Hover, focus or tap a flag to see its source.');
const rLayer = callouts($('r-callouts'));
const rPills = [['a', 'Pad A (1 km)'], ['b', 'Keep-out ring', 'warm']].map(([id, text, tone]) => rLayer.add({ id, text, tone }));
const rBox = $('r-callouts');
new ResizeObserver(() => { rPills[0].place(rBox.clientWidth * 0.3, rBox.clientHeight * 0.62); rPills[1].place(rBox.clientWidth * 0.72, rBox.clientHeight * 0.7); rLayer.layout(); }).observe(rBox);

// ---------- typography specimens ----------
const SAMPLE = 'Cutaway · Follow propellant · Landers';
const sizes = [12, 13, 14, 16, 20, 28];
$('d-type').append(
  h('div', { class: 'd-tablewrap', tabindex: '0', role: 'region', 'aria-label': 'Sora by size' }, h('table', { class: 'd-typetable' },
    h('caption', { class: 'visually-hidden' }, 'Sora by size'),
    h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, 'Size'), h('th', { scope: 'col' }, 'Sora (display)'))),
    h('tbody', {}, sizes.map(px => h('tr', {}, h('th', { scope: 'row' }, `${px} px`),
      h('td', { style: `font: 600 ${px}px/1.3 var(--font-display)` }, SAMPLE)))))),
  h('div', { class: 'd-typenums' },
    h('p', { class: 'ui-label' }, 'JetBrains Mono, tabular figures'),
    h('p', { class: 'd-mono' }, '0123456789 · −71 → +40 · 1,234.5 t · 06:42:10'),
    h('p', { class: 'ui-label' }, 'Source Sans 3, reading text'),
    h('p', {}, 'The urgent-cargo wait grows by about a third for every kilometre between the landing pad and the base, at the typical fleet load.')));

// ---------- contrast table ----------
const TEXT = 4.5, LARGE = 3;
const ROWS = [
  ['ink', 'Text', TEXT], ['ink-2', 'Muted text', TEXT], ['ink-3', 'Faint (24 px and larger only)', LARGE],
  ['accent', 'Data, guidance (cool)', TEXT], ['warm', 'Thrust, heat (warm)', TEXT], ['pos', 'Positive score', TEXT], ['neg', 'Negative score', TEXT],
  ['link', 'Link', TEXT], ['flag-measured', 'Flag: Measured', TEXT], ['flag-spec', 'Flag: Spec', TEXT], ['flag-modelled', 'Flag: Modelled', TEXT],
  ['flag-assumed', 'Flag: Assumed', TEXT], ['focus', 'Focus ring', LARGE], ['accent', 'Selected pill against its track', LARGE, 'state'],
  ['on-accent', 'Text on a selected pill', TEXT, 'onAccent'],
];
const TOL = ['tol-blue', 'tol-red', 'tol-green', 'tol-yellow', 'tol-cyan', 'tol-purple', 'tol-grey'].map(t => [t, `Category mark: ${t.slice(4)}`, LARGE]);
const NAMES = [...new Set([...ROWS, ...TOL].map(r => r[0]).concat(['bg', 'panel']))];
const BACKS = [['Black', '#000000'], ['Mid grey', '#808080'], ['Sunlit regolith', '#b0b0b0'], ['White (worst case)', '#ffffff']];

function readReading(theme) {   // reading tokens for 'light' or 'dark', read synchronously so nothing repaints
  const root = document.documentElement, was = root.dataset.theme;
  root.dataset.theme = theme;
  const t = tokens(root, NAMES);
  if (was) root.dataset.theme = was; else delete root.dataset.theme;
  return t;
}

function table(caption, cols, rows, t) {
  let pass = 0, total = 0;
  const body = rows.map(([name, role, need, kind]) => h('tr', {}, h('th', { scope: 'row' }, h('span', { class: 'd-sw', style: `background:rgb(${t[name].slice(0, 3)})` }), role,
    h('code', {}, kind === 'onAccent' ? 'on-accent / accent' : `--${name}`)),
  h('td', { class: 'n' }, `${need}:1`),
  cols.map(([, surface]) => {
    const fg = kind === 'onAccent' ? t['on-accent'] : t[name];
    const bg = kind === 'onAccent' ? over(t.accent, surface) : surface;
    const r = ratio(fg, bg), ok = r >= need;
    total++; if (ok) pass++;
    return h('td', { class: `n ${ok ? 'ok' : 'bad'}` }, r.toFixed(2), h('span', { class: 'd-pf' }, ok ? ' pass' : ' FAIL'));
  })));
  return { pass, total, el: h('div', { class: 'd-tablewrap', tabindex: '0', role: 'region', 'aria-label': caption }, h('table', { class: 'd-ctable' },
    h('caption', {}, caption),
    h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, 'Pair'), h('th', { scope: 'col', class: 'n' }, 'Needs'), cols.map(([label]) => h('th', { scope: 'col', class: 'n' }, label)))),
    h('tbody', {}, body))) };
}

function contrast() {
  const it = tokens(document.querySelector('.d-inst'), NAMES);
  const icols = [['Page, no panel', it.bg], ...BACKS.map(([l, c]) => [`Glass over ${l.toLowerCase()}`, over(it.panel, rgba(c))])];
  const tabs = [table('Instrument theme (glass: --panel composited over the backdrop)', icols, [...ROWS, ...TOL], it)];
  for (const theme of ['light', 'dark']) {
    const t = readReading(theme);
    tabs.push(table(`Reading theme, ${theme}`, [['Page', t.bg], ['Panel', over(t.panel, t.bg)]], ROWS, t));
  }
  const pass = tabs.reduce((s, x) => s + x.pass, 0), total = tabs.reduce((s, x) => s + x.total, 0);
  $('c-summary').textContent = `${pass} of ${total} pairs pass${pass === total ? '' : ' (failures are marked FAIL)'}.`;
  $('c-summary').dataset.ok = String(pass === total);
  $('c-tables').replaceChildren(...tabs.map(x => x.el));
}
contrast();
