// Base elements at true scale from the catalogue: habitat module, landing pad with its berm, solar tower, comms mast,
// cargo pallets (instanced), and the 1.8 m astronaut silhouette used as a scale reference.
import * as THREE from 'three';
import { builder, lathe, shellProfile, ringProfile, strut, at, V2, V3 } from './parts.js';

const v = (e, k) => e.dims[k].value;
const Y = V3(0, 1, 0);

// habitat: a horizontal cylinder with domed ends on short legs; the shell is closed so Cutaway shows the floor inside
export function habitat(e, mats, opts) {
  const b = builder(mats, opts), D = v(e, 'diameter_m'), L = v(e, 'length_m'), R = D / 2, s = b.seg(48), y = R + 0.8;
  const shell = b.part('shell', 'Pressure shell', { distance: 0, representative: true, note: e.representative_note || '' });
  const g = lathe(shellProfile(R, -L / 2 + R * 0.5, L / 2 - R * 0.5, R * 0.5, R * 0.5, 0.12), s).rotateZ(Math.PI / 2);
  b.mesh(shell, g, 'white_paint', { cut: true, capColor: '#c7ccd3', pos: V3(0, y, 0) });
  const floor = b.part('floor', 'Floor deck', { axis: Y, distance: 0 });
  b.mesh(floor, new THREE.BoxGeometry(L - D * 0.6, 0.15, D * 0.75), 'aluminium', { cut: true, pos: V3(0, y - R * 0.45, 0) });
  const rad = b.part('radiators', 'Radiators', { axis: V3(0, 0, 1), distance: 2 });
  for (const z of [-1, 1]) b.mesh(rad, new THREE.BoxGeometry(L * 0.5, 2.2, 0.08), 'radiator', { pos: V3(0, y + R * 0.3, z * (R + 0.4)) });
  const legs = b.part('legs', 'Support legs', { axis: V3(0, -1, 0), distance: 1 });
  for (const x of [-L / 3, 0, L / 3]) for (const z of [-1, 1]) b.mesh(legs, strut(V3(x, y - R * 0.8, z * R * 0.6), V3(x, 0.05, z * R * 0.75), 0.15), 'aluminium');
  const lock = b.part('airlock', 'Airlock', { axis: V3(1, 0, 0), distance: 2, representative: true });
  b.mesh(lock, new THREE.CylinderGeometry(1.1, 1.1, 2.4, s).rotateZ(Math.PI / 2), 'mli_silver', { cut: true, pos: V3(L / 2 + 0.9, y - 0.6, 0) });
  b.flow('power', [V3(0, y + R, 0), V3(L / 4, y + R * 0.6, R), V3(L / 2, y, 0)]);
  return b.finish({ id: e.id });
}

// landing pad: a sintered disc and a berm ring with the catalogue's crest, base and slope
export function pad(e, mats, opts) {
  const b = builder(mats, opts), D = v(e, 'diameter_m'), bh = v(e, 'berm_height_m'), crest = v(e, 'berm_crest_m'), base = v(e, 'berm_base_m'), br = v(e, 'berm_radius_m');
  const s = b.seg(96);
  const disc = b.part('disc', 'Sintered pad surface', { distance: 0 });
  b.mesh(disc, new THREE.CylinderGeometry(D / 2, D / 2, 0.12, s), 'sintered_regolith', { cut: true, pos: V3(0, 0.06, 0) });
  const berm = b.part('berm', 'Blast berm', { axis: Y, distance: 3, note: 'Height, crest, base and 52° slope from the catalogue; radius Assumed' });
  b.mesh(berm, lathe(ringProfile(br - base / 2, br + base / 2, 0, bh, br - crest / 2, br + crest / 2), s), 'regolith_dust', { cut: true });
  const marks = b.part('marks', 'Pad markings', { axis: Y, distance: 1 });
  b.mesh(marks, new THREE.RingGeometry(D * 0.18, D * 0.2, s).rotateX(-Math.PI / 2), 'white_paint', { pos: V3(0, 0.125, 0) });
  return b.finish({ id: e.id });
}

// solar tower: a mast with a vertical array that tracks the low sun
export function solarTower(e, mats, opts) {
  const b = builder(mats, opts), H = v(e, 'height_m'), AH = v(e, 'array_height_m'), AW = v(e, 'array_width_m');
  const mast = b.part('mast', 'Mast', { distance: 0 });
  b.mesh(mast, new THREE.CylinderGeometry(0.18, 0.28, H, b.seg(16)), 'white_paint', { cut: true, pos: V3(0, H / 2, 0) });
  b.mesh(mast, new THREE.CylinderGeometry(1.2, 1.4, 0.3, b.seg(24)), 'aluminium', { pos: V3(0, 0.15, 0) });
  const arr = b.part('array', 'Vertical solar array', { axis: V3(0, 0, 1), distance: 1.5 });
  b.mesh(arr, new THREE.BoxGeometry(AW, AH, 0.08), 'solar_cell', { pos: V3(0, H - AH / 2, 0.35) });
  b.mesh(arr, new THREE.BoxGeometry(AW + 0.1, 0.1, 0.12), 'aluminium', { pos: V3(0, H - AH / 2, 0.35) });
  b.flow('power', [V3(0, H - AH / 2, 0.35), V3(0, H - AH / 2, 0), V3(0, 0.3, 0), V3(3, 0.05, 0)]);
  return b.finish({ id: e.id });
}

// comms mast: a tapered tower with a dish and a small panel antenna
export function commsMast(e, mats, opts) {
  const b = builder(mats, opts), H = v(e, 'height_m');
  const tower = b.part('tower', 'Tower', { distance: 0 });
  b.mesh(tower, new THREE.CylinderGeometry(0.12, 0.35, H, b.seg(12)), 'aluminium', { cut: true, pos: V3(0, H / 2, 0) });
  for (let k = 0; k < 3; k++) b.mesh(tower, strut(at(k * 2.094, 2.2, 0.05), at(k * 2.094, 0.2, 4.5), 0.05), 'aluminium');
  const dish = b.part('dish', 'Dish antenna (direct to Earth)', { axis: V3(0, 0.2, 1), distance: 1.5 });
  const prof = []; for (let i = 0; i <= 10; i++) { const r = i / 10 * 1.2; prof.push(V2(r, 0.25 * (r / 1.2) ** 2)); }
  for (let i = 10; i >= 0; i--) { const r = i / 10 * 1.2; prof.push(V2(r, 0.25 * (r / 1.2) ** 2 - 0.04)); }
  b.mesh(dish, lathe(prof, b.seg(32)).rotateX(-Math.PI / 2 + 0.1), 'white_paint', { pos: V3(0, H - 1.6, 0.4) });
  const panel = b.part('panel', 'Panel antenna (local link)', { axis: V3(1, 0, 0), distance: 1 });
  b.mesh(panel, new THREE.BoxGeometry(0.08, 1.2, 0.5), 'white_paint', { pos: V3(0.35, H - 0.6, 0) });
  return b.finish({ id: e.id });
}

// cargo pallet: one pallet, or n instanced pallets in a grid (for stacks at sites)
export function cargoPallet(e, mats, opts = {}) {
  const b = builder(mats, opts), L = v(e, 'length_m'), W = v(e, 'width_m'), H = v(e, 'height_m'), n = opts.count || 1;
  const p = b.part('pallet', n > 1 ? `Cargo pallets (${n})` : 'Cargo pallet', { distance: 0 });
  const box = new THREE.BoxGeometry(W, H, L);
  if (n === 1) {
    b.mesh(p, box, 'white_paint', { cut: true, pos: V3(0, H / 2, 0) });
    b.mesh(p, new THREE.BoxGeometry(W + 0.06, 0.08, L + 0.06), 'aluminium', { pos: V3(0, 0.04, 0) });
  } else {
    const im = new THREE.InstancedMesh(box, mats.get('white_paint'), n), m = new THREE.Matrix4(), cols = Math.ceil(Math.sqrt(n));
    for (let i = 0; i < n; i++) { m.makeTranslation((i % cols) * (W + 0.3), H / 2 + Math.floor(i / (cols * cols)) * H, Math.floor(i / cols) % cols * (L + 0.3)); im.setMatrixAt(i, m); }
    im.castShadow = im.receiveShadow = true; p.add(im);
  }
  return b.finish({ id: e.id });
}

// a 1.8 m standing astronaut silhouette (scale reference; not a model of any suit)
export function astronaut(mats) {
  const b = builder(mats), g = b.part('astronaut', 'Astronaut, 1.8 m (scale reference)', { distance: 0 });
  b.mesh(g, new THREE.CapsuleGeometry(0.23, 0.55, 4, 12), 'white_paint', { pos: V3(0, 1.12, 0) });
  b.mesh(g, new THREE.SphereGeometry(0.16, 16, 12), 'white_paint', { pos: V3(0, 1.64, 0) });
  b.mesh(g, new THREE.BoxGeometry(0.42, 0.5, 0.22), 'white_paint', { pos: V3(0, 1.2, -0.25) });
  for (const x of [-0.11, 0.11]) b.mesh(g, new THREE.CapsuleGeometry(0.09, 0.62, 4, 8), 'white_paint', { pos: V3(x, 0.4, 0) });
  for (const x of [-0.3, 0.3]) b.mesh(g, new THREE.CapsuleGeometry(0.07, 0.5, 4, 8), 'white_paint', { pos: V3(x, 1.1, 0) });
  return b.finish({ id: 'astronaut', height: 1.8 });
}
