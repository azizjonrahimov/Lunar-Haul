// /vehicles/ (F-32b): the fleet at true scale on the shared stage, in the reference reel's pattern. Scene chips pick
// a group and a vehicle; View cuts it open or takes it apart; Follow traces propellant, power or cargo; the story
// card, stat chips, callouts, part list and properties all read the catalogue. A loading door covers the stage until
// the catalogue is in; Enter then starts the 3D view (WebGL set-up and shader compiles are the heavy part, so they
// wait for the visitor) and the door opens when the scene is ready. Tier 0 shows the numbers and parts without 3D.
// F-51: four views with deep links (?v=<id>&view=own|cutaway|exploded|xray): On its own (a pad, a slow turntable, an
// astronaut, a 1 m bar and the key dimensions as measured lines), Inside (the vehicle's preset cut, with a movable
// section), Exploded and X-ray (the shell see-through); the part list says what each part does, its size, source and
// whether it is published or schematic (kit-data.js), and hovering a row outlines the part, and the other way round.
import './vehicles.css';
import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { segmented, sceneChips, narrative, statChip, door, tooltip, h, reducedMotion } from '../ui/index.js';
import { detectTier } from '../stage/tier.js';
import { loadCatalog } from '../catalog.js';
import { buildVehicle, createMaterials, GROUPS, astronaut } from '../models/index.js';
import { STORIES, CHIPS, render, para, nightText } from './stories.js';
import { createFlows } from './flows.js';
import { num } from '../components/num.js';
import { KIT, SOURCES, ATC_LAYER, published, tagOf } from './kit-data.js';

const $ = id => document.getElementById(id);
const BASE = import.meta.env.BASE_URL;
const VIEWS = ['own', 'cutaway', 'exploded', 'xray'];
const ui = { group: 'landers', id: 'MK1', view: 'own', follow: 'none', scale: false, section: 0, atc: false };
const q = new URLSearchParams(location.search);
{ const v = q.get('view') === 'whole' ? 'own' : q.get('view'); if (VIEWS.includes(v)) ui.view = v; ui.atc = q.get('atc') === '1'; ui.compare = q.get('compare') === '1'; ui.light = q.get('light') === 'lunar' ? 'lunar' : 'studio'; }
// F-51 part 4: ?embed=1 is the look-inside panel of /world/ and the stories: no site chrome or pickers, 3D starts itself
const EMBED = q.get('embed') === '1';
if (EMBED) document.documentElement.classList.add('v-embed');
// F-51: the kit's own models join the catalogue's (each a lazy chunk, kit-data.js load()); rockets get a group
const VGROUPS = { landers: [...GROUPS.landers, 'griffin', 'blue_ghost'], rockets: ['centaur_v'], rovers: [...GROUPS.rovers, 'clv1', 'pegasus', 'flex', 'eagle', 'viper', 'lrv', 'mapp'],
  hoppers: ['moonfall', 'micro_nova'], atc: ['atc_computer', 'atc_radio'], base: GROUPS.base };
const ATC_GROUPS = ['landers', 'rockets', 'rovers', 'hoppers'];   // the vehicles the "Lunar ATC inside" layer applies to
if (q.get('v')) { const g = Object.keys(VGROUPS).find(k => VGROUPS[k].includes(q.get('v'))); if (g) Object.assign(ui, { group: g, id: q.get('v') }); }

const gate = door({ title: 'The LunarHaul fleet', subtitle: 'Vehicle catalogue and 3D models, built in your browser at true scale.', skip: { href: '#v-tree-h', label: 'Skip to the parts list' },
  enterLabel: 'Enter the 3D view', autoEnter: EMBED, beforeOpen: () => start3D() });
$('v-view').append(gate.el);
const story = narrative({ label: 'Vehicle story' });
$('v-story').append(story.el);

let catalog, mats, stage, flows, vehicle, explode, refs = null, tierInfo, stopFlow = null;
try {
  [catalog, tierInfo] = await Promise.all([loadCatalog(undefined, { fetchFn: url => gate.fetch(url, { label: 'catalogue' }) }), detectTier()]);
} catch (e) { gate.fail(`Could not load the vehicle catalogue (${e.message}).`); throw e; }
mats = createMaterials(catalog.doc.materials);

// ---------- pickers ----------
// a kit-only vehicle has no catalogue entry: a stand-in with its title (no stat chips; its numbers are in the part list)
const entryOf = id => KIT[id]?.load ? { id, name: KIT[id].title, kind: 'kit', dims: {} } : catalog.entry(id);
const nameOf = id => entryOf(id).name.replace(/\s*\(.*\)\s*$/, '');
const count = g => `${VGROUPS[g].length} ${g === 'base' ? 'elements' : g === 'atc' ? 'parts, our design' : VGROUPS[g].length === 1 ? 'stage' : 'vehicles'}`;
const groupChips = sceneChips({ label: 'Vehicle groups', scenes: [['landers', 'Landers'], ['rockets', 'Rockets'], ['rovers', 'Rovers'], ['hoppers', 'Hoppers'], ['atc', 'Lunar ATC'], ['base', 'Base']].map(([value, label]) => ({ value, label, note: count(value) })),
  value: ui.group, onChange: g => { ui.group = g; drawVehicleChips(); choose(VGROUPS[g][0]); } });
$('v-groups').append(groupChips.el);
let vehicleChips;
function drawVehicleChips() {
  vehicleChips = sceneChips({ label: 'Vehicles', scenes: VGROUPS[ui.group].map(id => ({ value: id, label: shortName(id) })), value: ui.id, onChange: id => choose(id) });
  $('v-vehicles').replaceChildren(vehicleChips.el);
}
const SHORT = { CLPS: 'Nova-C (CLPS class)', MK1: 'Blue Moon MK1', LARGE: 'Starship HLS', LTV: 'LTV', HAUL: 'HAUL (concept)', MICRO: 'MICRO', habitat: 'Habitat', pad: 'Landing pad', solar_tower: 'Solar tower', comms_mast: 'Comms mast', cargo_pallet: 'Cargo pallet' };
const shortName = id => SHORT[id] || KIT[id]?.short || id;
drawVehicleChips();

$('v-modes').append(
  segmented({ legend: 'View', options: [{ value: 'own', label: 'On its own' }, { value: 'cutaway', label: 'Inside' }, { value: 'exploded', label: 'Exploded' }, { value: 'xray', label: 'X-ray' }], value: ui.view, onChange: v => { ui.view = v; ui.section = 0; $('v-section').value = '0'; if (ui.compare) choose(ui.id); else applyView(); } }).el,
  h('label', { class: 'v-section', id: 'v-section-l', hidden: ui.view !== 'cutaway' }, h('span', { class: 'ui-label' }, 'Section'),
    h('input', { type: 'range', id: 'v-section', min: '-0.45', max: '0.45', step: '0.01', value: '0', 'aria-describedby': 'v-section-h', oninput: e => { ui.section = +e.target.value; cut(); } }),
    h('span', { id: 'v-section-h', class: 'small muted' }, 'moves the cut through the vehicle')),
  // F-52: the studio light reads shapes best; the lunar sun shows them as they would look at the pole (1.5° up, long shadows)
  segmented({ legend: 'Light', options: [{ value: 'studio', label: 'Studio' }, { value: 'lunar', label: 'Lunar sun (1.5°)' }], value: ui.light, onChange: v => { ui.light = v; writeUrl(); setLight(); } }).el,
  segmented({ legend: 'Follow', options: [{ value: 'none', label: 'Nothing' }, { value: 'propellant', label: 'Propellant' }, { value: 'power', label: 'Power' }, { value: 'cargo', label: 'Cargo' }], value: ui.follow, onChange: v => { ui.follow = v; applyFollow(); } }).el);

// ---------- stage (started by the door's Enter button) ----------
const tier = tierInfo.tier;
async function start3D() {
  const { createStage } = await import('../stage/index.js');
  stage = await createStage({ canvas: $('v-canvas'), labelsHost: $('v-labels'), preset: 'exhibit', tier, onPick: select, onHover: name => hotRow(name),
    onStatus: st => { if (st === 'lost') story.set({ eyebrow: 'WebGL', title: 'The 3D view paused', html: '<p>The graphics context was lost; it will come back by itself.</p>' }); } });
  flows = createFlows(stage.scene);
  if (import.meta.env.DEV) window.__stage = stage;   // console access while developing
  stage.director.bindKeys($('v-canvas'));
  stage.director.limits({ maxPolar: 88 });
  await choosing;   // a kit model (or the whole line-up) may still be loading
  if (ui.compare) mountCompare(); else { mount(); applyView(true); applyFollow(); }
  if (ui.light === 'lunar') setLight();
}

// ---------- choosing a vehicle ----------
// the catalogue's models build at once; the kit's own load their chunk first (a newer choice wins)
let choosing = null, chooseGen = 0;
function choose(id) { return (choosing = chooseNow(id)); }
async function make(id, lod = 'full') {
  const mod = KIT[id]?.load ? await KIT[id].load() : null;
  if (!mod) return buildVehicle(catalog, mats, id, { lod });
  if (mod.kit) Object.assign(KIT[id], mod.kit);
  const v = mod.build(mats, { lod }); v.entry = entryOf(id); v.root.userData.representative = v.representative; return v;
}
async function chooseNow(id) {
  const gen = ++chooseGen;
  ui.id = id; vehicleChips?.set(id); ui.compare = false; $('v-compare').setAttribute('aria-pressed', 'false');
  writeUrl();
  const e = entryOf(id), next = await make(id);
  if (gen !== chooseGen) return;
  if (stage) { setXray(false); clearExtras(); stage.clearSubject(); flows.clear(); }
  vehicle = next;
  atcParts = []; lineup = null;   // the old vehicle's layer (or the line-up) went with its subject
  if (stage) mount(); else atcLayer();
  drawChips(e); drawTree(); drawProps(null);
  const rep = $('v-rep'); rep.hidden = !vehicle.root.userData.representative;
  applyView(true); applyFollow();
}
// ---------- Compare sizes (F-51 part 4): every lander, rocket, rover and hopper on one line at true scale ----------
// smallest first, 1 m apart (or 15 % of the width), an astronaut at the small end; a name callout on each; the part
// list becomes a size table whose buttons open each vehicle (deep link ?compare=1)
const COMPARE = [...VGROUPS.landers, ...VGROUPS.rockets, ...VGROUPS.rovers, ...VGROUPS.hoppers];
let lineup = null;
function compare() { return (choosing = compareNow()); }
async function compareNow() {
  const gen = ++chooseGen;
  ui.compare = true; $('v-compare').setAttribute('aria-pressed', 'true'); writeUrl();
  story.set({ eyebrow: 'Compare sizes', title: 'Every vehicle at true scale', html: '<p>Loading the models…</p>' });
  const list = await Promise.all(COMPARE.map(async id => ({ id, v: await make(id, 'simple') })));
  if (gen !== chooseGen) return;
  if (stage) { setXray(false); clearExtras(); stage.setCut('off'); stage.clearSubject(); flows.clear(); stage.director.autoRotate(0); }
  if (refs) { refs.forEach(r => { stage?.scene.remove(r.root); r.root.traverse(o => o.geometry?.dispose()); }); refs = null; }
  atcParts = [];
  const row = new THREE.Group(), placed = []; let x = 0;
  for (const { id, v } of list.map(q => ({ ...q, b: new THREE.Box3().setFromObject(q.v.root) })).sort((a, b) => a.b.max.y - b.b.max.y).map(q => ({ id: q.id, v: q.v }))) {
    const b = new THREE.Box3().setFromObject(v.root), w = b.max.x - b.min.x;
    v.root.position.set(x - b.min.x, 0, -(b.min.z + b.max.z) / 2); row.add(v.root);
    placed.push({ id, v, h: b.max.y, w, l: b.max.z - b.min.z, anchor: new THREE.Vector3((b.min.x + b.max.x) / 2, b.max.y + 0.2, (b.min.z + b.max.z) / 2).add(v.root.position) });
    x += w + Math.max(1, w * 0.15);
  }
  const a = astronaut(mats); a.root.position.x = -1.2; row.add(a.root);
  const merged = mergeByMaterial(row);
  for (const p of placed) { p.mark = new THREE.Object3D(); p.mark.position.copy(p.anchor); merged.add(p.mark); }
  lineup = { row: merged, placed };
  if (stage) mountCompare();
  story.set({ eyebrow: 'Compare sizes', title: 'Every vehicle at true scale', html: `<p>${placed.length} vehicles on one line, smallest first, with a 1.8 m astronaut at the small end. A ${fmtM(placed.at(-1).h)} ${shortName(placed.at(-1).id)} stands next to a ${fmtM(placed[0].h)} ${shortName(placed[0].id)}. Zoom in on the small end; pick a vehicle in the list to open it.</p>` });
  drawCompareTable(); drawProps(null); $('v-chips').replaceChildren(); $('v-rep').hidden = true;
}
// F-52: the line-up never moves, so it is drawn as one mesh per material (1,811 draw calls -> a few dozen); each
// vehicle keeps an empty marker at its callout point
function mergeByMaterial(row) {
  row.updateMatrixWorld(true);
  const byMat = new Map(), out = new THREE.Group();
  row.traverse(o => {
    if (!o.isMesh || o.isInstancedMesh) return;
    const g = (o.geometry.index ? o.geometry.toNonIndexed() : o.geometry.clone()).applyMatrix4(o.matrixWorld);
    for (const k of Object.keys(g.attributes)) if (k !== 'position' && k !== 'normal') g.deleteAttribute(k);
    const key = o.material.userData.catalogMaterial || o.material.uuid;   // every part has its own clone (createMaterials): group by kind
    if (!byMat.has(key)) byMat.set(key, { mat: o.material, list: [] });
    byMat.get(key).list.push(g);
  });
  row.traverse(o => o.geometry?.dispose());
  for (const { mat, list } of byMat.values()) { const m = new THREE.Mesh(mergeGeometries(list), mat); m.castShadow = m.receiveShadow = true; out.add(m); list.forEach(g => g.dispose()); }
  return out;
}
const fmtM = v => `${v < 10 ? v.toFixed(v < 1 ? 2 : 1) : Math.round(v)} m`;
function mountCompare() {
  if (!lineup) return;
  stage.setSubject(lineup.row);
  for (const p of lineup.placed) stage.labels.add({ id: `cmp-${p.id}`, text: shortName(p.id), object: p.mark, onSelect: () => choose(p.id) });
  // the whole line from the front, a little above, filling the width
  const box = new THREE.Box3().setFromObject(lineup.row), c = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3()), cam = stage.camera;
  const hfov = 2 * Math.atan(Math.tan(cam.fov * Math.PI / 360) * cam.aspect), d = Math.max(size.x / 2 / Math.tan(hfov / 2), size.y / 2 / Math.tan(cam.fov * Math.PI / 360)) * 1.08;
  stage.director.shot('compare', { position: [c.x, c.y + size.y * 0.15, c.z + d], target: c.toArray() });
  stage.director.limits({ minDistance: 1, maxDistance: d * 3 });
  stage.director.go('compare', { instant: true });
}
function drawCompareTable() {
  $('v-tree').replaceChildren(...lineup.placed.map(p => h('li', { class: 'v-row-part' },
    h('button', { type: 'button', class: 'v-part', onclick: () => choose(p.id) }, shortName(p.id), h('span', { class: 'v-tag pub' }, 'open')),
    h('p', { class: 'v-meta small' }, `Height ${fmtM(p.h)} · width ${fmtM(p.w)} · length ${fmtM(p.l)}, as drawn${p.v.root.userData.representative ? ' (parts schematic)' : ''}`))));
}
$('v-scale').before(h('button', { class: 'ui-btn', type: 'button', id: 'v-compare', 'aria-pressed': 'false', onclick: () => (ui.compare ? choose(ui.id) : compare()) }, 'Compare sizes'));

// put the current vehicle on the stage: subject, explode, callouts, camera shots, scale references
function mount() {
  stage.setSubject(vehicle.root, { cutTargets: vehicle.cutTargets });
  explode = stage.explode(vehicle.explode);
  for (const p of pickLabels(vehicle.parts)) stage.labels.add({ id: p.name, text: p.label.replace(/ \(.*\)$/, ''), object: p.object, anchor: p.anchor, onSelect: select });
  frame(); placeRefs(); atcLayer();
}
// 4-6 callouts: one per distinct part group, biggest first
function pickLabels(parts) {
  const seen = new Set(), out = [];
  for (const p of parts) { const g = p.object.userData.group || p.name; if (seen.has(g)) continue; seen.add(g); out.push(p); }
  return out.slice(0, 6);
}
// camera shots fitted to the vehicle's box (F-52: the bounding sphere left a low, wide Griffin small and a tall MK1 cut
// at the top): the height against the vertical field of view, the plan diagonal against the horizontal one, plus half
// the diagonal so the near side fits too, so a 0.45 m MAPP and a 52 m HLS both fill the view
function frame() {
  const box = new THREE.Box3().setFromObject(vehicle.root), c = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3()), r = box.getBoundingSphere(new THREE.Sphere()).radius;
  const cam = stage.camera, vf = cam.fov * Math.PI / 360, hf = Math.atan(Math.tan(vf) * cam.aspect), hx = Math.hypot(size.x, size.z) / 2;
  const d = (Math.max(size.y / 2 / Math.tan(vf), hx / Math.tan(hf)) + hx) * 1.15, dir = (az, el) => new THREE.Vector3(Math.sin(az) * Math.cos(el), Math.sin(el), Math.cos(az) * Math.cos(el));
  const shot = (name, az, el, k) => { const p = c.clone().addScaledVector(dir(az, el), d * k); stage.director.shot(name, { position: p.toArray(), target: c.toArray() }); };
  shot('home', 0.6, 0.28, 1); shot('cutaway', 0.25, 0.22, 1); shot('exploded', 0.6, 0.32, 1.35);
  stage.director.limits({ minDistance: r * 0.4, maxDistance: d * 4 });
}
// F-51: the four views; the story text of the old Whole view serves On its own, Cutaway's serves Inside
const VIEW_NAME = { own: 'on its own', cutaway: 'inside', exploded: 'exploded', xray: 'X-ray' };
const XRAY_TEXT = '<p>X-ray: the outer shell is drawn see-through and everything inside stays solid, so the layout reads at a glance. Hover a part in the list to find it.</p>';
const LUNAR_SUN = { az: 200, el: 1.5 };
function setLight() {
  if (!stage) return;
  stage.setPreset(ui.light === 'lunar' ? 'onsite' : 'exhibit', { sun: LUNAR_SUN }); stage.setToneMapping('neutral', ui.light === 'lunar' ? 2 : 1);
}
function writeUrl() {   // F-40: other parameters (?tier, ?gpumem) stay
  const u = new URL(location.href); u.searchParams.set('v', ui.id);
  if (ui.view === 'own') u.searchParams.delete('view'); else u.searchParams.set('view', ui.view);
  if (ui.atc) u.searchParams.set('atc', '1'); else u.searchParams.delete('atc');
  if (ui.compare) { u.searchParams.set('compare', '1'); u.searchParams.delete('view'); } else u.searchParams.delete('compare');
  if (ui.light === 'lunar') u.searchParams.set('light', 'lunar'); else u.searchParams.delete('light');
  history.replaceState(null, '', u);
}
function applyView(instant = false) {
  if (!vehicle) return;
  const v = ui.view, e = entryOf(ui.id), s = STORIES[ui.id] || KIT[ui.id]?.story || {}, key = v === 'own' ? 'whole' : v;
  writeUrl(); $('v-section-l').hidden = v !== 'cutaway';
  story.set({ eyebrow: `${shortName(ui.id)} · ${VIEW_NAME[v]}`, title: KIT[ui.id]?.title || nameOf(ui.id),
    html: (v === 'xray' ? XRAY_TEXT : para(render(s[key] || s.whole || '', catalog, ui.id))) + (e.representative && v === 'own' ? `<p class="small">${e.representative_note || ''}</p>` : '') });
  if (!stage) return;
  // tier 1 (F-51 part 4): no turntable and no explode animation; the cut is drawn on demand, so it costs a still frame
  cut(); if (tier === 1) explode.set(v === 'exploded' ? 1 : 0); else explode.to(v === 'exploded' ? 1 : 0); setXray(v === 'xray');
  if (v === 'own') showExtras(); else clearExtras();
  stage.director.autoRotate(v === 'own' && !reducedMotion() && tier >= 2 ? 4 : 0);   // a slow turntable on its own (a turn in 90 s)
  stage.director.go(v === 'cutaway' || v === 'exploded' ? v : 'home', { instant });
}
// the preset cut: 'side' a vertical plane through the axis (landers: tanks and engine), 'down' a horizontal one at a
// fraction of the height (rovers: through the warm box); the Section slider moves it by up to 45 % of the vehicle
function cut() {
  if (!stage || !vehicle) return;
  if (ui.view !== 'cutaway') { stage.setCut('off'); return; }
  const box = new THREE.Box3().setFromObject(vehicle.root), c = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3()), k = KIT[ui.id]?.cut || { dir: 'side' };
  if (k.dir === 'down') stage.setCut('plane', { dir: new THREE.Vector3(0, 1, 0), origin: c.clone().setY(box.min.y + size.y * Math.min(0.95, Math.max(0.05, (k.at ?? 0.5) + ui.section))) });
  else { const facing = new THREE.Vector3(Math.sin(0.25), 0, Math.cos(0.25)); stage.setCut('plane', { facing, origin: c.clone().setY(0).addScaledVector(facing, ui.section * Math.max(size.x, size.z)) }); }
}
// X-ray: the kit's shell parts get see-through copies of their materials (the kit's materials are shared)
let xray = [];
function setXray(on) {
  for (const [m, mat, sh] of xray) { m.material.dispose(); m.material = mat; m.castShadow = sh; }
  xray = [];
  if (on && vehicle) for (const name of KIT[ui.id]?.shell || []) vehicle.root.traverse(o => {
    if (!o.isMesh || o.userData.cutHelper || !partOf(o, name)) return;
    const c = o.material.clone(); c.transparent = true; c.opacity = 0.14; c.depthWrite = false;
    xray.push([o, o.material, o.castShadow]); o.material = c; o.castShadow = false;
  });
  stage?.invalidate();
}
const partOf = (o, name) => { for (let p = o; p; p = p.parent) if (p.userData.part) return p.userData.part === name || p.userData.group === name; return false; };
// On its own: a sintered pad, an astronaut, a 1 m bar and the key dimensions drawn as measured lines
let extras = null;
function clearExtras() {
  if (!extras || !stage) return;
  stage.scene.remove(extras);
  extras.traverse(o => { o.geometry?.dispose(); if (o.material && !o.userData.sharedMat) o.material.dispose(); });
  for (const id of extras.userData.labels) stage.labels.remove(id);
  extras = null; stage.invalidate();
}
function showExtras() {
  clearExtras();
  const g = new THREE.Group(), box = new THREE.Box3().setFromObject(vehicle.root), size = box.getSize(new THREE.Vector3()), span = Math.max(size.x, size.z);
  g.userData.labels = [];
  const padMat = mats.get('sintered_regolith').clone(); padMat.polygonOffset = true; padMat.polygonOffsetFactor = -1; padMat.polygonOffsetUnits = -1;
  const pad = new THREE.Mesh(new THREE.CircleGeometry(span * 0.85 + 1, 72).rotateX(-Math.PI / 2), padMat);
  pad.position.y = 0.004; pad.receiveShadow = true; pad.userData.noPick = true; g.add(pad);
  const a = astronaut(mats); a.root.position.set(box.min.x - 0.9, 0, box.max.z * 0.3);   // left: the height line stands on the right
  a.root.traverse(o => { o.userData.noPick = true; if (o.isMesh) o.userData.sharedMat = true; }); g.add(a.root);
  // a 1 m bar of two 0.5 m halves, light and dark, on the ground in front
  const bar = new THREE.Group(); bar.position.set(box.min.x, 0.03, box.max.z + 0.6);
  for (const [i, col] of [[0, '#f2f2f2'], [1, '#2b2f36']]) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.04, 0.08), new THREE.MeshBasicMaterial({ color: col })); m.position.x = 0.25 + i * 0.5; m.userData.noPick = true; bar.add(m);
  }
  g.add(bar); addLabel(g, 'dim-bar', '1 m', bar, new THREE.Vector3(0.5, 0.05, 0));
  // dimension lines along the measured box edge of the vehicle or of one part, offset out of the way, with end ticks
  const lineMat = new THREE.LineBasicMaterial({ color: '#e7c66a', toneMapped: false });
  (KIT[ui.id]?.dims || []).forEach((d, i) => {
    const target = d.part ? vehicle.parts.find(p => p.name === d.part || p.object.userData.group === d.part)?.object : vehicle.root; if (!target) return;
    const b = new THREE.Box3().setFromObject(target), off = span * 0.12 + 0.3, A = new THREE.Vector3(), B = new THREE.Vector3();
    if (d.axis === 'y') { A.set(box.max.x + off, b.min.y, box.max.z); B.set(box.max.x + off, b.max.y, box.max.z); }   // right: the story card covers the top left
    else if (d.axis === 'x') { A.set(b.min.x, (b.min.y + b.max.y) / 2, box.max.z + off); B.set(b.max.x, A.y, A.z); }
    else { A.set(box.max.x + off, Math.max(0.05, (b.min.y + b.max.y) / 2), b.min.z); B.set(A.x, A.y, b.max.z); }
    const tick = d.axis === 'y' ? new THREE.Vector3(off * 0.25, 0, 0) : new THREE.Vector3(0, off * 0.25, 0);
    const ln = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints([A, B, A.clone().sub(tick), A.clone().add(tick), B.clone().sub(tick), B.clone().add(tick)]), lineMat);
    ln.userData.noPick = true; g.add(ln);
    const mid = new THREE.Object3D(); mid.position.copy(A).add(B).multiplyScalar(0.5); g.add(mid);
    addLabel(g, `dim-${i}`, `${d.label} ${d.text}${published(d.conf) || d.conf === 'Design' ? '' : ' (schematic)'}`, mid);
  });
  extras = g; stage.scene.add(g); stage.invalidate();
}
function addLabel(g, id, text, object, anchor = new THREE.Vector3()) { stage.labels.add({ id, text, object, anchor, tone: 'warm' }); g.userData.labels.push(id); }
function applyFollow() {
  if (!stage || !vehicle || ui.compare) return;
  const n = ui.follow === 'none' ? (flows.clear(), 0) : flows.show(vehicle.flows[ui.follow], ui.follow, Math.max(vehicle.size.x, vehicle.size.y, vehicle.size.z));
  stopFlow?.(); stopFlow = null;
  if (n && !reducedMotion()) stopFlow = stage.animate(dt => flows.tick(dt));   // dashes move; static under reduced motion
  if (ui.follow !== 'none' && !n) story.set({ eyebrow: `${shortName(ui.id)} · follow`, title: nameOf(ui.id), html: `<p>No ${ui.follow} path on this element.</p>` });
  stage.invalidate();
}

// ---------- chips, tree, properties ----------
function drawChips(e) {
  const box = $('v-chips'); box.replaceChildren();
  for (const [label, path, opts, tone] of CHIPS[e.kind] || []) {
    try {
      if (path.night) { const qv = e[path.night]; box.append(statChip({ label, text: nightText(qv.value), flag: qv.flag, source: qv.source }).el); continue; }
      box.append(statChip({ label, tone, ...catalog.q(e.id, path, opts) }).el);
    } catch (err) { /* this element has no such quantity */ }
  }
  if (e.kind === 'base') for (const [k, qv] of Object.entries(e.dims).slice(0, 3)) box.append(statChip({ label: k.replace(/_m$|_deg$/, '').replace(/_/g, ' '), ...catalog.q(e.id, `dims.${k}`, { digits: 1 }) }).el);
}
// F-51: one row per part or part group: its name with a published / schematic / our design tag (a button that selects
// it), what it does, its size and sources; hovering or focusing a row outlines the part in the view
function drawTree() {
  if (ui.compare) { drawCompareTable(); return; }
  const groups = new Map(), kit = { ...KIT[ui.id]?.parts, ...ATC_LAYER };
  for (const p of [...vehicle.parts, ...atcParts]) { const g = p.object.userData.group || p.name; if (!groups.has(g)) groups.set(g, []); groups.get(g).push(p); }
  $('v-tree').replaceChildren(...[...groups.entries()].map(([key, list]) => {
    const p = list[0], label = list.length > 1 ? `${p.label} × ${list.length}` : p.label, k = kit[key];
    const tagText = k ? tagOf(k.conf) : p.representative ? 'schematic' : 'published';
    const tag = h('span', { class: `v-tag${tagText === 'published' ? ' pub' : tagText === 'our design' ? ' ours' : ''}`, title: k ? `Confidence: ${k.conf === 'Design' ? 'our design' : k.conf}` : null }, tagText);
    const hot = on => () => stage?.highlightPart(on ? key : null);
    const src = (k?.src || []).map(id => SOURCES[id]).filter(Boolean).map(x => x.url ? h('a', { href: x.url, rel: 'noopener', target: '_blank' }, x.label) : h('span', {}, x.label));
    return h('li', { class: 'v-row-part', 'data-key': key, onmouseenter: hot(true), onmouseleave: hot(false) },
      h('button', { type: 'button', class: 'v-part', 'data-part': p.name, onclick: () => select(p.name), onfocus: hot(true), onblur: hot(false) }, label, tag),
      k ? h('p', { class: 'v-what' }, k.what) : null,
      k ? h('p', { class: 'v-meta small' }, `Size: ${k.size} · `, ...src.flatMap((x, i) => i ? ['; ', x] : [x])) : null);
  }));
}
// F-51 part 3, "Lunar ATC inside": our design's base computer and radio unit (teal) on the vehicle's KIT atc part,
// or on its top; their rows in the part list say "our design", and the callouts name them
let atcParts = [], atcMat = null;
function atcLayer() {
  for (const p of atcParts) { p.object.removeFromParent(); p.object.traverse(o => o.geometry?.dispose()); stage?.labels.remove(p.name); }
  atcParts = [];
  $('v-atc').hidden = !ATC_GROUPS.includes(ui.group);
  if (ui.compare) return;
  if (!vehicle || !ui.atc || !ATC_GROUPS.includes(ui.group)) { stage?.invalidate(); return; }
  atcMat ||= new THREE.MeshStandardMaterial({ color: '#27b3a0', emissive: '#0b4d45', roughness: 0.5, metalness: 0.3, name: 'Lunar ATC (our design)' });
  vehicle.root.updateMatrixWorld(true);
  const at = KIT[ui.id]?.atc, anchor = at && vehicle.parts.find(p => p.name === at || p.object.userData.group === at)?.object;
  const box = new THREE.Box3().setFromObject(anchor || vehicle.root), top = new THREE.Vector3((box.min.x + box.max.x) / 2, box.max.y, (box.min.z + box.max.z) / 2);
  const add = (name, dx, meshes) => {
    const g = new THREE.Group(); g.name = name; g.userData = { part: name, label: ATC_LAYER[name].label };
    g.position.copy(top).add(new THREE.Vector3(dx, 0, 0)); for (const m of meshes) g.add(m);
    vehicle.root.add(g); atcParts.push({ name, label: ATC_LAYER[name].label, object: g });
    stage?.labels.add({ id: name, text: ATC_LAYER[name].label, object: g, anchor: new THREE.Vector3(0, 0.12, 0), onSelect: select, tone: 'cool' });
  };
  const mesh = (geo, y) => { const m = new THREE.Mesh(geo, atcMat); m.position.y = y; m.castShadow = true; return m; };
  add('atc_computer', -0.16, [mesh(new THREE.BoxGeometry(0.22, 0.12, 0.3), 0.06)]);
  add('atc_radio', 0.16, [mesh(new THREE.BoxGeometry(0.12, 0.06, 0.18), 0.03), mesh(new THREE.CylinderGeometry(0.006, 0.006, 0.3, 8), 0.21)]);
  stage?.invalidate();
}
// a hover in the view marks the row of that part (or of its group)
function hotRow(name) {
  const p = name && [...(vehicle?.parts || []), ...atcParts].find(x => x.name === name), key = p ? p.object.userData.group || p.name : null;
  for (const li of document.querySelectorAll('.v-row-part')) li.classList.toggle('is-hot', li.dataset.key === key);
}
function select(name) {
  if (ui.compare) return;
  const p = [...vehicle.parts, ...atcParts].find(x => x.name === name); if (!p) return;
  stage?.labels.setPressed(name);
  for (const b of document.querySelectorAll('.v-part')) b.setAttribute('aria-pressed', String(b.dataset.part === name || (vehicle.parts.find(x => x.name === b.dataset.part)?.object.userData.group || '#') === (p.object.userData.group || '-')));
  drawProps(p);
}
function drawProps(p) {
  const el = $('v-props');
  if (!p) { el.replaceChildren(h('p', { class: 'muted' }, 'Pick a part in the list, in the view or on a callout.')); return; }
  const size = new THREE.Box3().setFromObject(p.object).getSize(new THREE.Vector3()), matIds = new Set(); let tris = 0;
  p.object.traverse(o => { if (o.isMesh && !o.userData.cutHelper) { matIds.add(o.material.userData.catalogMaterial); const g = o.geometry; tris += (g.index ? g.index.count : g.attributes.position.count) / 3; } });
  const dims = ['x', 'y', 'z'].map(k => num({ value: size[k], unit: 'm', digits: 2, flag: 'Modelled', source: 'measured on the 3D model built from the catalogue dimensions' })).join(' × ');
  const matText = [...matIds].filter(Boolean).map(id => catalog.doc.materials[id]?.description || id).join('; ');
  el.innerHTML = `<dl class="v-dl"><dt>Part</dt><dd>${p.label}</dd><dt>Size (x × y × z)</dt><dd>${dims}</dd><dt>Material</dt><dd>${matText}</dd>` +
    `<dt>Triangles</dt><dd>${Math.round(tris).toLocaleString('en-GB')}</dd>${p.note ? `<dt>Note</dt><dd>${p.note}</dd>` : ''}${p.representative ? '<dt>Shape</dt><dd>Representative: the real shape is unpublished</dd>' : ''}</dl>`;
}

// ---------- scale references, pause, camera, representative label ----------
function placeRefs() {
  if (!stage || ui.compare) return;
  if (refs) { refs.forEach(r => { stage.scene.remove(r.root); r.root.traverse(o => o.geometry?.dispose()); }); refs = null; }
  if (!ui.scale || ui.id === 'apollo_lrv') return stage.invalidate();
  const box = new THREE.Box3().setFromObject(vehicle.root), lrv = buildVehicle(catalog, mats, 'apollo_lrv', { lod: 'simple' });
  lrv.root.position.set(box.max.x + 2.6 + lrv.size.x / 2, 0, box.max.z * 0.2 - 2.5);   // the astronaut stands by every vehicle On its own (F-51)
  refs = [lrv]; refs.forEach(r => stage.scene.add(r.root)); stage.invalidate();
}
// F-51 part 3: the Lunar ATC layer, for rovers, landers, rockets and hoppers (deep link &atc=1)
$('v-scale').after(h('button', { class: 'ui-btn', type: 'button', id: 'v-atc', 'aria-pressed': String(ui.atc), onclick: e => { ui.atc = !ui.atc; e.currentTarget.setAttribute('aria-pressed', String(ui.atc)); writeUrl(); atcLayer(); drawTree(); } }, 'Lunar ATC inside (our design)'));
$('v-scale').addEventListener('click', e => { ui.scale = !ui.scale; e.currentTarget.setAttribute('aria-pressed', String(ui.scale)); placeRefs(); });
$('v-pause').addEventListener('click', e => { const v = e.currentTarget.getAttribute('aria-pressed') !== 'true'; e.currentTarget.setAttribute('aria-pressed', String(v)); stage?.pause(v); });
for (const b of document.querySelectorAll('[data-cam]')) b.addEventListener('click', () => {
  const d = stage?.director; if (!d) return;
  ({ left: () => d.nudge(-20), right: () => d.nudge(20), up: () => d.nudge(0, -10), down: () => d.nudge(0, 10), in: () => d.zoom(1.25), out: () => d.zoom(0.8), home: () => applyView() })[b.dataset.cam]();
});
tooltip($('v-rep'), 'Where the real shape is unpublished (legs, an elevator, a concept vehicle), the model shows a labelled representative shape at the catalogue’s dimensions. The part list marks which parts.');

if (ui.compare) compare(); else choose(ui.id);
if (tier === 0 && !tierInfo.forced) {
  $('v-fallback').hidden = false; $('v-fallback').textContent = `No 3D view on this device (${tierInfo.gpu}); the numbers and parts list below describe each vehicle.`;
  gate.open();
} else gate.ready();   // Enter starts the 3D view
