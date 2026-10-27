// Shared pieces for the F-51 kit models (rovers, hoppers): a closed wheel (tyre torus + hub), a closed box shell that
// the cutaway can cap, a crew seat, a mast with a camera head and a dish, and four wheels as one part group each.
// Every solid is closed, so Inside caps it. Rovers face +z with the ground at y = 0.
import * as THREE from 'three';
import { lathe, shellProfile, strut, V3 } from '../parts.js';

// a wheel in group g at pos: tyre torus of diameter d and width w (closed), hub cylinder; axle along x
export function wheel(b, g, pos, d, w, tyre = 'tyre') {
  const r = d / 2, tube = Math.min(w / 2, r * 0.3);
  b.mesh(g, new THREE.TorusGeometry(r - tube, tube, b.seg(12), b.seg(32)).rotateY(Math.PI / 2), tyre, { cut: true, pos });
  b.mesh(g, new THREE.CylinderGeometry(r * 0.55, r * 0.55, w * 0.9, b.seg(20)).rotateZ(Math.PI / 2), 'aluminium', { cut: true, pos });
}
// four (or n) wheels at the corners of a wheelbase × track rectangle, each its own part in the 'wheels' group
export function wheels(b, { d, w, track, base, label, n = 4, tyre, distance = 0.5 }) {
  const rows = n / 2;
  for (let i = 0; i < n; i++) {
    const side = i % 2 ? -1 : 1, row = Math.floor(i / 2), z = rows > 1 ? base / 2 - row * base / (rows - 1) : 0;
    const p = b.part(`wheel${i}`, label, { axis: V3(side, 0, 0), distance });
    p.userData.group = 'wheels';
    wheel(b, p, V3(side * track / 2, d / 2, z), d, w, tyre);
  }
}
// a closed hollow box (wall t) from y0 to y1, half sizes hx × hz: a square lathe scaled to the rectangle
export function boxShell(b, g, { hx, hz, y0, y1, t = 0.03, mat = 'white_paint', cap = '#c7ccd3', pos }) {
  const geo = lathe(shellProfile(Math.SQRT2, y0, y1, 0, 0, t * Math.SQRT2 / Math.min(hx, hz), 1), 4).rotateY(Math.PI / 4).scale(hx, 1, hz);
  return b.mesh(g, geo, mat, { cut: true, capColor: cap, pos });
}
// a crew seat (closed boxes): base and back, facing +z
export function seat(b, g, pos, mat = 'mli_silver') {
  b.mesh(g, new THREE.BoxGeometry(0.5, 0.08, 0.5), mat, { pos: pos.clone() });
  b.mesh(g, new THREE.BoxGeometry(0.5, 0.55, 0.08), mat, { pos: pos.clone().add(V3(0, 0.3, -0.22)) });
}
// a mast from foot to height h with a camera head at h and a dish above it
export function mast(b, g, foot, h, { dish = 0.25, head = [0.3, 0.12, 0.12] } = {}) {
  b.mesh(g, strut(foot, foot.clone().setY(h), 0.035), 'aluminium');
  b.mesh(g, new THREE.BoxGeometry(...head), 'dark_metal', { pos: foot.clone().setY(h) });
  if (dish) b.mesh(g, new THREE.CylinderGeometry(dish, dish * 0.3, 0.08, b.seg(20)), 'white_paint', { pos: foot.clone().setY(h + 0.22), rot: { x: -0.5 } });
}
// a solar panel (thin closed box) at pos, w wide and h tall, facing ±x
export const panel = (b, g, pos, w, h) => b.mesh(g, new THREE.BoxGeometry(0.03, h, w), 'solar_cell', { pos });
