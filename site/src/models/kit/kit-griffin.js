// Astrobotic Griffin (F-51), the 2021 payload user's guide layout: a square aluminium bus whose deck and radiator panels
// carry the avionics underneath, the launch-vehicle adapter cone at the bottom centre with the main engines inside it,
// four propellant tanks spaced round the cone (two fuel, two oxidiser), four clusters of three attitude thrusters,
// side solar panels, antennas, four legs. The overall size is unpublished: the envelope (3 m bus, 2 m tall, 4.5 m
// across the legs) is drawn from the deck and cone and the catalogue's reference entry, and labelled schematic.
import * as THREE from 'three';
import { builder, lathe, shellProfile, bellProfile, strut, radial, at, V3 } from '../parts.js';

const DOWN = V3(0, -1, 0), Y = V3(0, 1, 0);

export function build(mats, opts) {
  const b = builder(mats, opts), a = 1.5, y0 = 1.0, y1 = 2.0, span = 2.25, s = b.seg(24);
  const bus = b.part('bus', 'Bus: decks and radiator panels', { distance: 0, representative: true, note: 'Overall size unpublished: drawn from the deck and the adapter cone' });
  b.mesh(bus, lathe(shellProfile(a * Math.SQRT2, y0, y1, 0, 0, 0.05, 1), 4), 'radiator', { cut: true, capColor: '#c8ced6', rot: { y: Math.PI / 4 } });
  const cone = b.part('cone', 'Launch-vehicle adapter cone', { distance: 0 });
  b.mesh(cone, lathe([V3(0, 0.45, 0), V3(0.95, 0.45, 0), V3(0.62, y0, 0), V3(0, y0, 0)].map(p => new THREE.Vector2(p.x, p.y)), s), 'aluminium', { cut: true, capColor: '#b9c0ca' });   // closed: Inside and X-ray open it onto the engines
  const eng = b.part('engines', 'Main engines (5, inside the cone)', { axis: DOWN, distance: 0.9 });
  for (let k = 0; k < 5; k++) {
    const p = k === 4 ? V3(0, y0 - 0.05, 0) : at(k * Math.PI / 2, 0.3, y0 - 0.05);
    b.mesh(eng, lathe(bellProfile(0.04, 0.12, 0.5, 0.012), b.seg(20)), 'dark_metal', { cut: true, pos: p });
  }
  // four tanks round the cone, alternating fuel and oxidiser
  for (let k = 0; k < 4; k++) {
    const fuel = k % 2 === 0, t = b.part(`${fuel ? 'fuel' : 'ox'}${k}`, fuel ? 'Fuel tank (MMH type)' : 'Oxidiser tank (MON-3)', { axis: radial(k * Math.PI / 2 + Math.PI / 4).add(V3(0, 0.6, 0)), distance: 1.1 });
    t.userData.group = fuel ? 'fuel' : 'oxidiser';
    b.mesh(t, new THREE.SphereGeometry(0.4, s, b.seg(16)), 'aluminium', { cut: true, capColor: fuel ? '#c9b48a' : '#7fb3db', pos: at(k * Math.PI / 2 + Math.PI / 4, 0.98, (y0 + y1) / 2) });
  }
  const av = b.part('avionics', 'Avionics under the deck panels', { axis: Y, distance: 0.8 });
  for (const [x, z] of [[0.55, 0.55], [-0.55, -0.55]]) b.mesh(av, new THREE.BoxGeometry(0.6, 0.16, 0.45), 'mli_gold', { cut: true, pos: V3(x, y1 - 0.14, z) });
  const pay = b.part('payload', 'Payload deck', { axis: Y, distance: 1.0 });
  b.mesh(pay, new THREE.BoxGeometry(0.9, 0.45, 0.7), 'mli_gold', { pos: V3(-0.5, y1 + 0.23, 0.4) });
  b.mesh(pay, new THREE.BoxGeometry(0.6, 0.3, 0.6), 'white_paint', { pos: V3(0.6, y1 + 0.15, -0.5) });
  const solar = b.part('solar', 'Side solar panel', { axis: V3(1, 0, 0), distance: 0.8 });
  b.mesh(solar, new THREE.BoxGeometry(0.04, 0.85, 1.9), 'solar_cell', { pos: V3(a + 0.05, (y0 + y1) / 2, 0) });
  const ant = b.part('antennas', 'Antennas', { axis: Y, distance: 0.9 });
  b.mesh(ant, new THREE.CylinderGeometry(0.03, 0.03, 0.5, 8), 'aluminium', { pos: V3(-a + 0.25, y1 + 0.25, -a + 0.25) });
  b.mesh(ant, new THREE.CylinderGeometry(0.26, 0.08, 0.1, b.seg(20)), 'white_paint', { pos: V3(-a + 0.25, y1 + 0.55, -a + 0.25), rot: { x: -0.5 } });
  const acs = b.part('acs', 'Attitude thrusters (4 clusters of 3)', { axis: Y, distance: 0.5 });
  for (let k = 0; k < 4; k++) for (let j = 0; j < 3; j++) {
    const c = at(k * Math.PI / 2, a + 0.06, y0 + 0.2 + j * 0.12);
    b.mesh(acs, new THREE.ConeGeometry(0.035, 0.1, 8), 'dark_metal', { pos: c, rot: { z: Math.PI / 2 } });
  }
  for (let k = 0; k < 4; k++) {
    const ang = k * Math.PI / 2 + Math.PI / 4, leg = b.part(`leg${k}`, 'Landing leg', { axis: radial(ang), distance: 0.7 });
    leg.userData.group = 'legs';
    const knee = at(ang, a * Math.SQRT2 * 0.95, y0 + 0.15), foot = at(ang, span - 0.2, 0.06);
    b.mesh(leg, strut(knee, foot, 0.045), 'aluminium');
    b.mesh(leg, strut(at(ang, a * Math.SQRT2 * 0.9, y0 + 0.7), at(ang, span - 0.75, 0.4), 0.03), 'aluminium');
    b.mesh(leg, new THREE.CylinderGeometry(0.16, 0.2, 0.05, b.seg(16)), 'aluminium', { pos: foot.clone().setY(0.025) });
  }
  for (let k = 0; k < 4; k++) b.flow('propellant', [at(k * Math.PI / 2 + Math.PI / 4, 0.98, 1.1), at(k * Math.PI / 2 + Math.PI / 4, 0.6, 0.95), V3(0, 0.95, 0)]);
  b.flow('power', [V3(a + 0.05, 1.5, 0), V3(0.9, 1.8, 0.2), V3(0.55, y1 - 0.14, 0.55)]);
  b.flow('cargo', [V3(-0.5, y1 + 0.5, 0.4), V3(-0.5, y1 + 0.6, a + 0.6), V3(-0.5, 0.2, a + 1.2)]);
  return b.finish({ id: 'griffin' });
}
