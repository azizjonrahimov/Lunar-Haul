// NASA/JPL MoonFall hopper drone (F-51), delivered by Firefly in 2028: about 2.1 m wide × 1.2 m tall and 250 kg with
// propellant, 10 cameras (press, Medium). Tanks, thrusters and legs are unpublished: drawn to the schematic hopper
// recipe of the research notes (central tanks and a COPV, downward thrusters under the centre of mass, four legs,
// solar and avionics on the top deck, cameras round the rim).
import * as THREE from 'three';
import { builder, lathe, shellProfile, bellProfile, strut, radial, at, V3 } from '../parts.js';

export const kit = {
  story: {
    whole: 'One of four MoonFall drones that NASA/JPL plan to fly to the south pole in 2028: about 2.1 m wide and 1.2 m tall, 250 kg with propellant. Each hops for about 14 days and covers some 50 km, mapping landing sites with 10 cameras.',
    cutaway: 'Cut through the body: a central propellant tank and a small pressurant tank. None of this is published; it is the usual hopper layout, labelled schematic.',
    exploded: 'Tanks up, thrusters down, legs out, the top deck lifted off.',
  },
  cut: { dir: 'side' }, shell: ['body'], atc: 'avionics',
  dims: [
    { label: 'Width', text: '2.1 m', axis: 'x', src: ['moonfall'], conf: 'Medium' },
    { label: 'Height', text: '1.2 m', axis: 'y', src: ['moonfall'], conf: 'Medium' },
  ],
  parts: {
    body: { what: 'A low, wide body: about 250 kg with propellant.', size: '2.1 m wide × 1.2 m tall', src: ['moonfall'], conf: 'Medium' },
    tanks: { what: 'A central propellant tank and a small pressurant (COPV) tank.', size: 'not published', src: ['assumed'], conf: 'Low' },
    thrusters: { what: 'Downward thrusters under the centre of mass lift and land the drone.', size: 'not published', src: ['assumed'], conf: 'Low' },
    cameras: { what: 'Ten cameras round the rim map landing sites.', size: '10 cameras', src: ['moonfall'], conf: 'Medium' },
    avionics: { what: 'Solar panel and avionics on the top deck.', size: 'not published', src: ['assumed'], conf: 'Low' },
    legs: { what: 'Four short landing legs.', size: 'not published', src: ['assumed'], conf: 'Low' },
  },
};

export function build(mats, opts) {
  const b = builder(mats, opts), R = 0.72, y0 = 0.35, y1 = 0.95, span = 1.05, s = b.seg(32);
  const body = b.part('body', 'Body', { distance: 0, representative: true });
  b.mesh(body, lathe(shellProfile(R, y0, y1, 0.12, 0.08, 0.03), s), 'mli_silver', { cut: true, capColor: '#c4cad3' });
  const tk = b.part('tanks', 'Propellant tank and COPV', { axis: V3(0, 1, 0), distance: 0.6, representative: true });
  b.mesh(tk, new THREE.SphereGeometry(0.3, s, b.seg(16)), 'aluminium', { cut: true, capColor: '#c9b48a', pos: V3(0, 0.62, 0) });
  b.mesh(tk, new THREE.SphereGeometry(0.11, b.seg(20), b.seg(12)), 'mli_gold', { cut: true, capColor: '#e0c060', pos: V3(0.45, 0.62, 0) });
  const th = b.part('thrusters', 'Downward thrusters', { axis: V3(0, -1, 0), distance: 0.4, representative: true });
  for (let k = 0; k < 4; k++) b.mesh(th, lathe(bellProfile(0.03, 0.08, 0.16, 0.008), b.seg(16)), 'dark_metal', { cut: true, pos: at(k * Math.PI / 2, 0.16, y0 - 0.06) });
  const cam = b.part('cameras', 'Cameras round the rim (10)', { axis: V3(0, 1, 0), distance: 0.3 });
  for (let k = 0; k < 10; k++) { const a = k * 2 * Math.PI / 10, p = at(a, R + 0.03, 0.62); b.mesh(cam, new THREE.BoxGeometry(0.06, 0.06, 0.06), 'dark_metal', { pos: p, rot: { y: -a } }); }
  const av = b.part('avionics', 'Top deck: solar panel and avionics', { axis: V3(0, 1, 0), distance: 0.5, representative: true });
  b.mesh(av, new THREE.CylinderGeometry(R * 0.85, R * 0.85, 0.04, s), 'solar_cell', { pos: V3(0, y1 + 0.13, 0) });
  b.mesh(av, new THREE.BoxGeometry(0.4, 0.1, 0.3), 'mli_gold', { cut: true, capColor: '#d9b867', pos: V3(-0.25, y1 - 0.05, 0.1) });
  for (let k = 0; k < 4; k++) {
    const a = k * Math.PI / 2 + Math.PI / 4, leg = b.part(`leg${k}`, 'Landing leg', { axis: radial(a), distance: 0.4, representative: true });
    leg.userData.group = 'legs';
    const knee = at(a, R * 0.9, y0 + 0.05), foot = at(a, span - 0.1, 0.04);
    b.mesh(leg, strut(knee, foot, 0.025), 'aluminium');
    b.mesh(leg, new THREE.CylinderGeometry(0.08, 0.1, 0.03, b.seg(12)), 'aluminium', { pos: foot.clone().setY(0.015) });
  }
  b.flow('propellant', [V3(0, 0.33, 0), V3(0.1, 0.3, 0.1), at(0, 0.16, y0 - 0.06)]);
  return b.finish({ id: 'moonfall' });
}
