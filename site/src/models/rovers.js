// Rover generators at true scale from the catalogue (front = +z, ground at y = 0). LTV is CLV-1/FLEX-like, MICRO is
// VIPER-scale, HAUL is the concept (no flown counterpart, so the whole vehicle is representative), and the Apollo
// LRV is the scale reference. Wheels are closed tori with instanced chevrons or grousers on the full level.
import * as THREE from 'three';
import { builder, strut, V3 } from './parts.js';

const v = (e, k) => e.dims[k].value;
const Y = V3(0, 1, 0), FWD = V3(0, 0, 1);

// a wheel: closed torus tyre + hub disc; tread: 'chevron' | 'grouser' | null (instanced, full level only)
function wheel(b, group, pos, d, width, tread) {
  const r = d / 2, tube = width / 2, g = new THREE.Group(); g.position.copy(pos); group.add(g);
  b.mesh(g, new THREE.TorusGeometry(r - tube, tube, b.seg(12), b.seg(36)).rotateY(Math.PI / 2), 'tyre', { cut: true });
  b.mesh(g, new THREE.CylinderGeometry(r * 0.55, r * 0.55, width * 0.9, b.seg(24)).rotateZ(Math.PI / 2), 'aluminium', { cut: true });
  if (tread && b.full) {
    const n = 24, geo = tread === 'chevron' ? new THREE.BoxGeometry(width * 0.95, 0.025, d * 0.07) : new THREE.BoxGeometry(width * 0.9, 0.025, 0.02);
    const im = new THREE.InstancedMesh(geo, g.children[0].material, n), m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(1, 1, 1);
    for (let i = 0; i < n; i++) {
      const a = i / n * Math.PI * 2;
      q.setFromAxisAngle(new THREE.Vector3(1, 0, 0), a).multiply(new THREE.Quaternion().setFromAxisAngle(Y, tread === 'chevron' ? (i % 2 ? 0.35 : -0.35) : 0));
      m.compose(new THREE.Vector3(0, Math.cos(a) * r, Math.sin(a) * r), q, s); im.setMatrixAt(i, m);
    }
    im.castShadow = true; g.add(im);
  }
  return g;
}

// LTV: deck on four large wheels with crab-steer pivots, a tilted solar panel, a small robotic arm
export function ltv(e, mats, opts) {
  const b = builder(mats, opts), L = v(e, 'length_m'), W = v(e, 'width_m'), H = v(e, 'height_m'), d = v(e, 'wheel_d_m');
  const wb = v(e, 'wheelbase_m'), tr = v(e, 'track_m'), deckY = v(e, 'deck_height_m');
  const chassis = b.part('chassis', 'Chassis and deck', { distance: 0 });
  b.mesh(chassis, new THREE.BoxGeometry(W - 0.5, 0.12, L - 0.02), 'aluminium', { cut: true, pos: V3(0, deckY, 0) });   // the deck sets the 4 m length
  b.mesh(chassis, new THREE.BoxGeometry(W - 1.0, 0.45, L - 1.2), 'white_paint', { cut: true, pos: V3(0, deckY - 0.3, 0) });
  const batt = b.part('battery', 'Battery and avionics box', { axis: Y, distance: 1.2 });
  b.mesh(batt, new THREE.BoxGeometry(W - 1.3, 0.3, 1.1), 'radiator', { cut: true, capColor: '#5b6a7a', pos: V3(0, deckY - 0.3, -0.6) });
  for (const [i, x, z] of [[0, 1, 1], [1, -1, 1], [2, 1, -1], [3, -1, -1]]) {
    const w = b.part(`wheel${i}`, 'Wheel with crab-steer pivot', { axis: V3(x, 0, 0), distance: 0.8 });
    w.userData.group = 'wheels';
    wheel(b, w, V3(x * tr / 2, d / 2, z * wb / 2), d, 0.25, 'chevron');
    b.mesh(w, new THREE.CylinderGeometry(0.08, 0.08, deckY - d / 2, b.seg(12)), 'aluminium', { pos: V3(x * tr / 2, (deckY + d / 2) / 2, z * wb / 2) });
    b.mesh(w, strut(V3(x * tr / 2, deckY - 0.1, z * wb / 2), V3(x * (W / 2 - 0.4), deckY - 0.1, z * (wb / 2 - 0.3)), 0.05), 'aluminium');
  }
  const solar = b.part('solar', 'Solar panel', { axis: V3(0, 1, -0.5), distance: 1.0, representative: true });
  b.mesh(solar, new THREE.CylinderGeometry(0.05, 0.05, H - deckY - 0.2, 10), 'aluminium', { pos: V3(0, deckY + (H - deckY - 0.2) / 2, -L / 2 + 0.5) });
  b.mesh(solar, new THREE.BoxGeometry(W - 0.3, 0.04, 1.0), 'solar_cell', { pos: V3(0, H - 0.2, -L / 2 + 0.6), rot: { x: -0.35 } });
  const arm = b.part('arm', 'Robotic arm', { axis: FWD, distance: 0.9, representative: true });
  const s0 = V3(0.6, deckY + 0.1, L / 2 - 0.9), s1 = V3(0.5, deckY + 0.85, L / 2 - 0.5), s2 = V3(0.2, deckY + 0.55, L / 2 - 0.1);   // stowed inside the 4 m length
  b.mesh(arm, strut(s0, s1, 0.05), 'aluminium'); b.mesh(arm, strut(s1, s2, 0.04), 'aluminium');
  for (const p of [s0, s1, s2]) b.mesh(arm, new THREE.SphereGeometry(0.08, 12, 8), 'white_paint', { pos: p });
  const cargo = b.part('cargo', 'Cargo on the deck', { axis: Y, distance: 0.8 });
  b.mesh(cargo, new THREE.BoxGeometry(1.0, 0.7, 1.4), 'mli_gold', { cut: true, pos: V3(0, deckY + 0.41, 0.3) });
  b.flow('power', [V3(0, H - 0.2, -L / 2 + 0.6), V3(0, deckY + 0.3, -L / 2 + 0.6), V3(0, deckY - 0.3, -0.6), V3(tr / 2, d / 2, wb / 2)]);
  b.flow('power', [V3(0, deckY - 0.3, -0.6), V3(-tr / 2, d / 2, -wb / 2)]);
  b.flow('cargo', [V3(0, deckY + 0.8, 0.3), V3(0, deckY + 1.2, L / 2 + 0.5), V3(0, 0.4, L / 2 + 1.5)]);
  return b.finish({ id: e.id });
}

// HAUL: the concept heavy hauler: low flat bed on six 1.5 m wheels, pallet rails, radiators, headlights, no solar mast
export function haul(e, mats, opts) {
  const b = builder(mats, opts), L = v(e, 'length_m'), W = v(e, 'width_m'), H = v(e, 'height_m'), d = v(e, 'wheel_d_m');
  const wb = v(e, 'wheelbase_m'), tr = v(e, 'track_m'), deckY = v(e, 'deck_height_m');
  const note = 'HAUL has no flown or built counterpart (nearest: JPL ATHLETE); the whole vehicle is a concept';
  const bed = b.part('bed', 'Flat bed (concept)', { distance: 0, representative: true, note });
  b.mesh(bed, new THREE.BoxGeometry(W - 1.0, 0.3, L - 0.6), 'white_paint', { cut: true, pos: V3(0, deckY, 0) });
  b.mesh(bed, new THREE.BoxGeometry(W - 2.0, 0.5, L - 1.4), 'aluminium', { cut: true, pos: V3(0, deckY - 0.4, 0) });
  const rails = b.part('rails', 'Pallet interface rails', { axis: Y, distance: 0.6, representative: true, note });
  for (const x of [-0.8, 0.8]) b.mesh(rails, new THREE.BoxGeometry(0.12, 0.08, L - 1.0), 'aluminium', { pos: V3(x, deckY + 0.19, 0) });
  const batt = b.part('battery', 'Battery and night-power pack', { axis: Y, distance: 1.4, representative: true, note });
  b.mesh(batt, new THREE.BoxGeometry(W - 2.2, 0.45, 1.8), 'mli_silver', { cut: true, capColor: '#5b6a7a', pos: V3(0, deckY - 0.45, -L / 2 + 1.6) });
  const rad = b.part('radiators', 'Radiators (night operation)', { axis: V3(0, 0.3, -1), distance: 1.2, representative: true, note });
  for (const x of [-1, 1]) b.mesh(rad, new THREE.BoxGeometry(0.06, H - deckY - 0.15, 1.6), 'radiator', { pos: V3(x * (W / 2 - 0.9), deckY + (H - deckY) / 2 + 0.05, -L / 2 + 1.0) });
  const lights = b.part('lights', 'Headlights', { axis: FWD, distance: 0.8, representative: true, note });
  for (const x of [-1, 1]) {
    b.mesh(lights, new THREE.BoxGeometry(0.35, 0.22, 0.2), 'aluminium', { pos: V3(x * (W / 2 - 1.0), deckY + 0.3, L / 2 - 0.35) });
    b.mesh(lights, new THREE.BoxGeometry(0.28, 0.15, 0.03), 'lamp', { pos: V3(x * (W / 2 - 1.0), deckY + 0.3, L / 2 - 0.24) });
  }
  [-1, 0, 1].forEach((zk, j) => [1, -1].forEach((x, i) => {
    const w = b.part(`wheel${j * 2 + i}`, 'Wheel, 1.5 m (concept)', { axis: V3(x, 0, 0), distance: 0.9, representative: true, note });
    w.userData.group = 'wheels';
    wheel(b, w, V3(x * tr / 2, d / 2, zk * wb / 2), d, 0.6, 'chevron');   // 0.6 m wide: track 3.4 + one wheel = the catalogue's 4 m
    b.mesh(w, strut(V3(x * tr / 2, d / 2, zk * wb / 2), V3(x * (W / 2 - 1.1), deckY - 0.45, zk * wb / 2), 0.09), 'aluminium');
  }));
  const pallet = b.part('cargo', 'Cargo pallet', { axis: Y, distance: 1.0 });
  b.mesh(pallet, new THREE.BoxGeometry(1.0, 1.0, 1.5), 'white_paint', { cut: true, pos: V3(0, deckY + 0.73, 0.6) });
  b.flow('power', [V3(0, deckY - 0.45, -L / 2 + 1.6), V3(0, deckY - 0.5, 0), V3(tr / 2, d / 2, wb / 2)]);
  b.flow('power', [V3(0, deckY - 0.45, -L / 2 + 1.6), V3(-(W / 2 - 0.9), deckY + 1.0, -L / 2 + 1.0)]);
  b.flow('cargo', [V3(0, deckY + 1.3, 0.6), V3(0, deckY + 1.8, L / 2 + 0.8), V3(0, 0.5, L / 2 + 2)]);
  return b.finish({ id: e.id });
}

// MICRO: VIPER-scale body on four 0.5 m wheels with grousers, a mast with lights, vertical solar panels
export function micro(e, mats, opts) {
  const b = builder(mats, opts), L = v(e, 'length_m'), W = v(e, 'width_m'), H = v(e, 'height_m'), d = v(e, 'wheel_d_m');
  const body = b.part('body', 'Body', { distance: 0 });
  b.mesh(body, new THREE.BoxGeometry(W - 0.5, 0.55, L - 0.4), 'mli_silver', { cut: true, capColor: '#9aa3ad', pos: V3(0, 0.75, 0) });
  const batt = b.part('battery', 'Battery', { axis: Y, distance: 0.7 });
  b.mesh(batt, new THREE.BoxGeometry(0.6, 0.25, 0.5), 'radiator', { cut: true, capColor: '#5b6a7a', pos: V3(0, 0.72, -0.2) });
  for (const [x, rotY] of [[1, 0], [-1, 0]]) {
    const p = b.part(`solar${x > 0 ? 'E' : 'W'}`, 'Vertical solar panel', { axis: V3(x, 0, 0), distance: 0.6 });
    p.userData.group = 'solar';
    b.mesh(p, new THREE.BoxGeometry(0.04, 0.75, L - 0.5), 'solar_cell', { pos: V3(x * (W / 2 - 0.2), 1.42, 0), rot: { y: rotY } });
  }
  const mast = b.part('mast', 'Mast with cameras and lights', { axis: Y, distance: 0.6 });
  b.mesh(mast, new THREE.CylinderGeometry(0.04, 0.05, H - 1.25, 10), 'aluminium', { pos: V3(0.25, 1.02 + (H - 1.25) / 2, 0.45) });
  b.mesh(mast, new THREE.BoxGeometry(0.32, 0.16, 0.18), 'white_paint', { pos: V3(0.25, H - 0.12, 0.45) });
  for (const x of [0.15, 0.35]) b.mesh(mast, new THREE.CylinderGeometry(0.03, 0.03, 0.03, 10).rotateX(Math.PI / 2), 'lamp', { pos: V3(x, H - 0.12, 0.55) });
  for (const [i, x, z] of [[0, 1, 1], [1, -1, 1], [2, 1, -1], [3, -1, -1]]) {
    const w = b.part(`wheel${i}`, 'Wheel, 0.5 m with grousers', { axis: V3(x, 0, 0), distance: 0.4 });
    w.userData.group = 'wheels';
    wheel(b, w, V3(x * (W / 2 - 0.12), d / 2, z * (L / 2 - 0.25)), d, 0.15, 'grouser');
    b.mesh(w, strut(V3(x * (W / 2 - 0.12), d / 2, z * (L / 2 - 0.25)), V3(x * (W / 2 - 0.3), 0.6, z * (L / 2 - 0.4)), 0.03), 'aluminium');
  }
  b.flow('power', [V3(W / 2 - 0.2, 1.42, 0), V3(0.3, 0.9, 0), V3(0, 0.72, -0.2), V3(W / 2 - 0.12, d / 2, L / 2 - 0.25)]);
  return b.finish({ id: e.id });
}

// Apollo LRV, the 1971 scale reference: open frame, four 0.818 m wire-mesh wheels, two seats
export function lrv(e, mats, opts) {
  const b = builder(mats, opts), L = v(e, 'length_m'), d = v(e, 'wheel_d_m'), wb = v(e, 'wheelbase_m'), tr = v(e, 'track_m'), H = v(e, 'height_m');
  const frame = b.part('frame', 'Apollo LRV (scale reference)', { distance: 0 });
  b.mesh(frame, new THREE.BoxGeometry(tr - 0.5, 0.08, L - 0.3), 'aluminium', { pos: V3(0, v(e, 'ground_clearance_m') + 0.1, 0) });
  for (const z of [-0.3, 0.3]) b.mesh(frame, new THREE.BoxGeometry(0.5, 0.5, 0.45), 'aluminium', { pos: V3(z * 1.4, 0.75, -0.2) });
  b.mesh(frame, new THREE.CylinderGeometry(0.02, 0.02, H - 0.5, 8), 'aluminium', { pos: V3(0, 0.5 + (H - 0.5) / 2, L / 2 - 0.5) });
  for (const [x, z] of [[1, 1], [-1, 1], [1, -1], [-1, -1]]) wheel(b, frame, V3(x * tr / 2, d / 2, z * wb / 2), d, 0.23, null);
  return b.finish({ id: e.id });
}
