// Firefly Blue Ghost (F-51): a box-shaped composite body with three decks (top: sky view; middle: rover mounts; bottom:
// surface access), 2 m tall and 3.5 m across the legs; four composite legs with honeycomb crush cores; the LEROS 4-ET
// main engine at the bottom centre; RCS thrusters round the body; an X-band dish and three S-band antennas; three
// solar panels. Tank count and positions are unpublished: two tanks are drawn inside, labelled schematic.
import * as THREE from 'three';
import { builder, lathe, shellProfile, bellProfile, strut, radial, at, V3 } from '../parts.js';

const DOWN = V3(0, -1, 0), Y = V3(0, 1, 0);

export function build(mats, opts) {
  const b = builder(mats, opts), a = 0.8, y0 = 0.55, y1 = 1.95, span = 1.75, s = b.seg(24);
  const body = b.part('body', 'Composite body (49 struts)', { distance: 0 });
  b.mesh(body, lathe(shellProfile(a * Math.SQRT2, y0, y1, 0, 0, 0.04, 1), 4), 'mli_silver', { cut: true, capColor: '#c4cad3', rot: { y: Math.PI / 4 } });
  const decks = b.part('decks', 'Three decks', { axis: Y, distance: 0.6 });
  for (const y of [y0, (y0 + y1) / 2, y1]) b.mesh(decks, new THREE.BoxGeometry(2 * a + 0.12, 0.04, 2 * a + 0.12), 'white_paint', { pos: V3(0, y, 0) });
  const tanks = b.part('tanks', 'Propellant tanks (schematic)', { axis: Y, distance: 0.9, representative: true, note: 'Tank count and positions are unpublished' });
  for (const x of [-0.38, 0.38]) b.mesh(tanks, new THREE.SphereGeometry(0.3, s, b.seg(16)), 'aluminium', { cut: true, capColor: x < 0 ? '#c9b48a' : '#7fb3db', pos: V3(x, 0.95, 0) });
  const eng = b.part('engine', 'LEROS 4-ET main engine', { axis: DOWN, distance: 0.6 });
  b.mesh(eng, lathe(bellProfile(0.04, 0.13, 0.3, 0.01), b.seg(24)), 'dark_metal', { cut: true, pos: V3(0, y0, 0) });
  const rcs = b.part('rcs', 'RCS thrusters', { axis: Y, distance: 0.4 });
  for (let k = 0; k < 4; k++) for (const dy of [0.25, 1.15]) b.mesh(rcs, new THREE.ConeGeometry(0.03, 0.09, 8), 'dark_metal', { pos: at(k * Math.PI / 2 + Math.PI / 4, a * Math.SQRT2 + 0.03, y0 + dy), rot: { z: Math.PI / 2 } });
  const ant = b.part('antennas', 'X-band dish and S-band antennas', { axis: Y, distance: 0.7 });
  b.mesh(ant, new THREE.CylinderGeometry(0.025, 0.025, 0.35, 8), 'aluminium', { pos: V3(0.4, y1 + 0.17, -0.4) });
  b.mesh(ant, new THREE.CylinderGeometry(0.22, 0.06, 0.09, b.seg(20)), 'white_paint', { pos: V3(0.4, y1 + 0.38, -0.4), rot: { x: -0.4 } });
  for (const [x, z] of [[-0.55, 0.55], [0.55, 0.55], [-0.55, -0.55]]) b.mesh(ant, new THREE.CylinderGeometry(0.02, 0.02, 0.22, 6), 'white_paint', { pos: V3(x, y1 + 0.11, z) });
  for (let k = 0; k < 3; k++) {
    const ang = k * Math.PI / 2, p = b.part(`solar${k}`, 'Solar panel', { axis: radial(ang), distance: 0.7 });
    p.userData.group = 'solar';
    const c = at(ang, a + 0.05, (y0 + y1) / 2), panel = new THREE.BoxGeometry(0.03, 0.9, 1.3);
    b.mesh(p, panel, 'solar_cell', { pos: c, rot: { y: -ang } });
  }
  for (let k = 0; k < 4; k++) {
    const ang = k * Math.PI / 2 + Math.PI / 4, leg = b.part(`leg${k}`, 'Composite leg with crush core', { axis: radial(ang), distance: 0.6 });
    leg.userData.group = 'legs';
    const knee = at(ang, a * Math.SQRT2 * 0.95, y0 + 0.3), foot = at(ang, span - 0.15, 0.06);
    b.mesh(leg, strut(knee, foot, 0.04), 'white_paint');
    b.mesh(leg, strut(knee.clone().lerp(foot, 0.35), knee.clone().lerp(foot, 0.6), 0.065), 'mli_gold');   // the crush-core section
    b.mesh(leg, new THREE.CylinderGeometry(0.13, 0.16, 0.05, b.seg(16)), 'aluminium', { pos: foot.clone().setY(0.025) });
  }
  for (const x of [-0.38, 0.38]) b.flow('propellant', [V3(x, 0.7, 0), V3(x * 0.4, 0.62, 0.1), V3(0, y0, 0)]);
  b.flow('power', [at(0, a + 0.05, 1.25), V3(0.3, 1.5, 0.2), V3(0.4, y1 + 0.2, -0.4)]);
  b.flow('cargo', [V3(0, y1 + 0.2, 0), V3(0, y1 + 0.3, a + 0.8), V3(0, 0.2, a + 1.4)]);
  return b.finish({ id: 'blue_ghost' });
}
