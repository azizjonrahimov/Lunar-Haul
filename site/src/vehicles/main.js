// /vehicles/ (F-32b): the fleet at true scale on the shared stage, in the reference reel's pattern. Scene chips pick
// a group and a vehicle; View cuts it open or takes it apart; Follow traces propellant, power or cargo; the story
// card, stat chips, callouts, part list and properties all read the catalogue. A loading door covers the stage until
// the catalogue is in; Enter then starts the 3D view (WebGL set-up and shader compiles are the heavy part, so they
// wait for the visitor) and the door opens when the scene is ready. Tier 0 shows the numbers and parts without 3D.
import './vehicles.css';
import * as THREE from 'three';
import { segmented, sceneChips, narrative, statChip, door, tooltip, h, reducedMotion } from '../ui/index.js';
import { detectTier } from '../stage/tier.js';
import { loadCatalog } from '../catalog.js';
import { buildVehicle, createMaterials, GROUPS, astronaut } from '../models/index.js';
import { STORIES, CHIPS, render, para, nightText } from './stories.js';
import { createFlows } from './flows.js';
import { num } from '../components/num.js';

const $ = id => document.getElementById(id);
const BASE = import.meta.env.BASE_URL;
const ui = { group: 'landers', id: 'MK1', view: 'whole', follow: 'none', scale: false };
const q = new URLSearchParams(location.search);
if (q.get('v')) { const g = Object.keys(GROUPS).find(k => GROUPS[k].includes(q.get('v'))); if (g) Object.assign(ui, { group: g, id: q.get('v') }); }

const gate = door({ title: 'The LunarHaul fleet', subtitle: 'Vehicle catalogue and 3D models, built in your browser at true scale.', skip: { href: '#v-tree-h', label: 'Skip to the parts list' },
  enterLabel: 'Enter the 3D view', beforeOpen: () => start3D() });
$('v-view').append(gate.el);
const story = narrative({ label: 'Vehicle story' });
$('v-story').append(story.el);

let catalog, mats, stage, flows, vehicle, explode, refs = null, tierInfo, stopFlow = null;
try {
  [catalog, tierInfo] = await Promise.all([loadCatalog(undefined, { fetchFn: url => gate.fetch(url, { label: 'catalogue' }) }), detectTier()]);
} catch (e) { gate.fail(`Could not load the vehicle catalogue (${e.message}).`); throw e; }
mats = createMaterials(catalog.doc.materials);

// ---------- pickers ----------
const nameOf = id => catalog.entry(id).name.replace(/\s*\(.*\)\s*$/, '');
const groupChips = sceneChips({ label: 'Vehicle groups', scenes: [{ value: 'landers', label: 'Landers', note: '3 classes' }, { value: 'rovers', label: 'Rovers', note: '3 classes' }, { value: 'base', label: 'Base', note: '5 elements' }],
  value: ui.group, onChange: g => { ui.group = g; drawVehicleChips(); choose(GROUPS[g][0]); } });
$('v-groups').append(groupChips.el);
let vehicleChips;
function drawVehicleChips() {
  vehicleChips = sceneChips({ label: 'Vehicles', scenes: GROUPS[ui.group].map(id => ({ value: id, label: shortName(id) })), value: ui.id, onChange: id => choose(id) });
  $('v-vehicles').replaceChildren(vehicleChips.el);
}
const SHORT = { CLPS: 'CLPS class', MK1: 'MK1 class', LARGE: 'Large cargo', LTV: 'LTV', HAUL: 'HAUL (concept)', MICRO: 'MICRO', habitat: 'Habitat', pad: 'Landing pad', solar_tower: 'Solar tower', comms_mast: 'Comms mast', cargo_pallet: 'Cargo pallet' };
const shortName = id => SHORT[id] || id;
drawVehicleChips();

$('v-modes').append(
  segmented({ legend: 'View', options: [{ value: 'whole', label: 'Whole' }, { value: 'cutaway', label: 'Cutaway' }, { value: 'exploded', label: 'Exploded' }], value: ui.view, onChange: v => { ui.view = v; applyView(); } }).el,
  segmented({ legend: 'Follow', options: [{ value: 'none', label: 'Nothing' }, { value: 'propellant', label: 'Propellant' }, { value: 'power', label: 'Power' }, { value: 'cargo', label: 'Cargo' }], value: ui.follow, onChange: v => { ui.follow = v; applyFollow(); } }).el);

// ---------- stage (started by the door's Enter button) ----------
const tier = tierInfo.tier;
async function start3D() {
  const { createStage } = await import('../stage/index.js');
  stage = await createStage({ canvas: $('v-canvas'), labelsHost: $('v-labels'), preset: 'exhibit', tier, onPick: select,
    onStatus: st => { if (st === 'lost') story.set({ eyebrow: 'WebGL', title: 'The 3D view paused', html: '<p>The graphics context was lost; it will come back by itself.</p>' }); } });
  flows = createFlows(stage.scene);
  if (import.meta.env.DEV) window.__stage = stage;   // console access while developing
  stage.director.bindKeys($('v-canvas'));
  stage.director.limits({ maxPolar: 88 });
  mount(); applyView(true); applyFollow();
}

// ---------- choosing a vehicle ----------
function choose(id) {
  ui.id = id; vehicleChips?.set(id);
  { const u = new URL(location.href); u.searchParams.set('v', id); history.replaceState(null, '', u); }   // F-40: other parameters (?tier, ?gpumem) stay
  const e = catalog.entry(id);
  if (stage) { stage.clearSubject(); flows.clear(); }
  vehicle = buildVehicle(catalog, mats, id);
  if (stage) mount();
  drawChips(e); drawTree(); drawProps(null);
  const rep = $('v-rep'); rep.hidden = !vehicle.root.userData.representative;
  applyView(true); applyFollow();
}
// put the current vehicle on the stage: subject, explode, callouts, camera shots, scale references
function mount() {
  stage.setSubject(vehicle.root, { cutTargets: vehicle.cutTargets });
  explode = stage.explode(vehicle.explode);
  for (const p of pickLabels(vehicle.parts)) stage.labels.add({ id: p.name, text: p.label.replace(/ \(.*\)$/, ''), object: p.object, anchor: p.anchor, onSelect: select });
  frame(); placeRefs();
}
// 4-6 callouts: one per distinct part group, biggest first
function pickLabels(parts) {
  const seen = new Set(), out = [];
  for (const p of parts) { const g = p.object.userData.group || p.name; if (seen.has(g)) continue; seen.add(g); out.push(p); }
  return out.slice(0, 6);
}
// camera shots from the vehicle's bounding sphere, so a 1.7 m rover and a 52 m lander both fill the view
function frame() {
  const box = new THREE.Box3().setFromObject(vehicle.root), c = box.getCenter(new THREE.Vector3()), r = box.getBoundingSphere(new THREE.Sphere()).radius;
  const cam = stage.camera, fov = Math.min(cam.fov, 2 * Math.atan(Math.tan(cam.fov * Math.PI / 360) * cam.aspect) * 180 / Math.PI) * Math.PI / 180;
  const d = r / Math.sin(fov / 2) * 1.05, dir = (az, el) => new THREE.Vector3(Math.sin(az) * Math.cos(el), Math.sin(el), Math.cos(az) * Math.cos(el));
  const shot = (name, az, el, k) => { const p = c.clone().addScaledVector(dir(az, el), d * k); stage.director.shot(name, { position: p.toArray(), target: c.toArray() }); };
  shot('home', 0.6, 0.28, 1); shot('cutaway', 0.25, 0.22, 1); shot('exploded', 0.6, 0.32, 1.35);
  stage.director.limits({ minDistance: r * 0.4, maxDistance: d * 4 });
}
function applyView(instant = false) {
  if (!vehicle) return;
  const v = ui.view, e = catalog.entry(ui.id), s = STORIES[ui.id] || {};
  story.set({ eyebrow: `${shortName(ui.id)} · ${v}`, title: nameOf(ui.id), html: para(render(s[v] || s.whole || '', catalog, ui.id)) + (e.representative && v === 'whole' ? `<p class="small">${e.representative_note || ''}</p>` : '') });
  if (!stage) return;
  const facing = new THREE.Vector3(Math.sin(0.25), 0, Math.cos(0.25));
  stage.setCut(v === 'cutaway' ? 'plane' : 'off', { facing, origin: new THREE.Box3().setFromObject(vehicle.root).getCenter(new THREE.Vector3()).setY(0) });
  explode.to(v === 'exploded' ? 1 : 0);
  stage.director.go(v === 'whole' ? 'home' : v, { instant });
}
function applyFollow() {
  if (!stage || !vehicle) return;
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
function drawTree() {
  const groups = new Map();
  for (const p of vehicle.parts) { const g = p.object.userData.group || p.name; if (!groups.has(g)) groups.set(g, []); groups.get(g).push(p); }
  $('v-tree').replaceChildren(...[...groups.values()].map(list => {
    const p = list[0], label = list.length > 1 ? `${p.label} × ${list.length}` : p.label;
    return h('li', {}, h('button', { type: 'button', class: 'v-part', 'data-part': p.name, onclick: () => select(p.name) }, label, p.representative ? h('span', { class: 'v-tag' }, 'representative') : null));
  }));
}
function select(name) {
  const p = vehicle.parts.find(x => x.name === name); if (!p) return;
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
  if (!stage) return;
  if (refs) { refs.forEach(r => { stage.scene.remove(r.root); r.root.traverse(o => o.geometry?.dispose()); }); refs = null; }
  if (!ui.scale) return stage.invalidate();
  const box = new THREE.Box3().setFromObject(vehicle.root), a = astronaut(mats), lrv = buildVehicle(catalog, mats, 'apollo_lrv', { lod: 'simple' });
  a.root.position.set(box.max.x + 1.2, 0, box.max.z * 0.2); lrv.root.position.set(box.max.x + 2.2 + lrv.size.x / 2, 0, box.max.z * 0.2 - 2.5);
  refs = [a, lrv]; refs.forEach(r => stage.scene.add(r.root)); stage.invalidate();
}
$('v-scale').addEventListener('click', e => { ui.scale = !ui.scale; e.currentTarget.setAttribute('aria-pressed', String(ui.scale)); placeRefs(); });
$('v-pause').addEventListener('click', e => { const v = e.currentTarget.getAttribute('aria-pressed') !== 'true'; e.currentTarget.setAttribute('aria-pressed', String(v)); stage?.pause(v); });
for (const b of document.querySelectorAll('[data-cam]')) b.addEventListener('click', () => {
  const d = stage?.director; if (!d) return;
  ({ left: () => d.nudge(-20), right: () => d.nudge(20), up: () => d.nudge(0, -10), down: () => d.nudge(0, 10), in: () => d.zoom(1.25), out: () => d.zoom(0.8), home: () => applyView() })[b.dataset.cam]();
});
tooltip($('v-rep'), 'Where the real shape is unpublished (legs, an elevator, a concept vehicle), the model shows a labelled representative shape at the catalogue’s dimensions. The part list marks which parts.');

choose(ui.id);
if (tier === 0 && !tierInfo.forced) {
  $('v-fallback').hidden = false; $('v-fallback').textContent = `No 3D view on this device (${tierInfo.gpu}); the numbers and parts list below describe each vehicle.`;
  gate.open();
} else gate.ready();   // Enter starts the 3D view
