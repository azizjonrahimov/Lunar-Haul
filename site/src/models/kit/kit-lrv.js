// The Apollo Lunar Roving Vehicle (F-51), 1971-72, from the NSSDC page: 3.1 m long, 2.3 m wheelbase, 1.14 m tall,
// 36 cm ground clearance; four 81.8 × 23 cm wire-mesh wheels, each with its own 0.25 hp hub motor; two 36 V
// silver-zinc batteries in the forward chassis; a mesh dish on a mast at the front centre; two seats with the
// T-handle between them; payload aft; a chassis of three folding sections.
import * as THREE from 'three';
import { builder, strut, V3 } from '../parts.js';
import { wheels, seat } from './kit-common.js';

export const kit = {
  story: {
    whole: 'The Apollo rover of 1971-72: 210 kg, 490 kg of payload, 3.1 m long, driven by two astronauts. Everything here is published.',
    cutaway: 'Cut through the chassis: the two silver-zinc batteries sat in the forward section, under dust covers and radiators.',
    exploded: 'The three folding chassis sections apart, the wheels with their hub motors out.',
  },
  cut: { dir: 'down', at: 0.45 }, shell: [], atc: 'batteries',
  dims: [
    { label: 'Length', text: '3.1 m', axis: 'z', src: ['lrv'], conf: 'High' },
    { label: 'Height', text: '1.14 m', axis: 'y', src: ['lrv'], conf: 'High' },
  ],
  parts: {
    chassis: { what: 'Three sections that folded up for the ride in the lunar module.', size: '3.1 m long, 2.3 m wheelbase', src: ['lrv'], conf: 'High' },
    batteries: { what: 'Two 36 V, 121 Ah silver-zinc batteries in the forward chassis.', size: '~8.7 kWh', src: ['lrv'], conf: 'High' },
    seats: { what: 'Two seats; the T-handle between them steered and drove.', size: '2 seats', src: ['lrv'], conf: 'High' },
    antenna: { what: 'A mesh dish on a mast at the front centre talked directly to Earth.', size: 'not published', src: ['lrv'], conf: 'High' },
    payload: { what: 'Tools and samples rode in the aft payload area.', size: '490 kg total payload', src: ['lrv'], conf: 'High' },
    wheels: { what: 'Four wire-mesh wheels, each with its own 0.25 hp hub motor and 80:1 harmonic drive.', size: '81.8 × 23 cm', src: ['lrv'], conf: 'High' },
  },
};

export function build(mats, opts) {
  const b = builder(mats, opts), L = 3.1, wb = 2.3, d = 0.818, y = 0.55;
  const ch = b.part('chassis', 'Chassis (3 folding sections)', { distance: 0 });
  for (const [z0, z1] of [[0.6, L / 2], [-0.6, 0.6], [-L / 2, -0.6]]) b.mesh(ch, new THREE.BoxGeometry(1.15, 0.1, z1 - z0 - 0.04), 'aluminium', { cut: true, capColor: '#b9c0ca', pos: V3(0, y, (z0 + z1) / 2) });
  for (const x of [-1, 1]) for (const z of [-1, 1]) b.mesh(ch, new THREE.BoxGeometry(0.5, 0.35, 0.08), 'aluminium', { pos: V3(x * 0.8, y + 0.12, z * wb / 2) });   // fenders
  const bat = b.part('batteries', 'Batteries (2, silver-zinc)', { axis: V3(0, 1, 1), distance: 0.6 });
  for (const x of [-0.25, 0.25]) b.mesh(bat, new THREE.BoxGeometry(0.4, 0.25, 0.35), 'mli_gold', { cut: true, capColor: '#d9b867', pos: V3(x, y + 0.18, L / 2 - 0.3) });
  const st = b.part('seats', 'Seats and T-handle', { axis: V3(0, 1, 0), distance: 0.6 });
  for (const x of [-0.32, 0.32]) seat(b, st, V3(x, y + 0.1, -0.05), 'aluminium');
  b.mesh(st, strut(V3(0, y + 0.06, 0.35), V3(0, y + 0.42, 0.35), 0.02), 'dark_metal');
  const ant = b.part('antenna', 'Dish antenna on its mast', { axis: V3(0, 1, 0), distance: 0.5 });
  b.mesh(ant, strut(V3(0, y + 0.05, L / 2 - 0.05), V3(0, 1.1, L / 2 - 0.05), 0.02), 'aluminium');
  b.mesh(ant, new THREE.CylinderGeometry(0.45, 0.12, 0.1, b.seg(24)), 'white_paint', { pos: V3(0, 1.14, L / 2 - 0.05), rot: { x: -0.5 } });
  const pay = b.part('payload', 'Payload area (aft)', { axis: V3(0, 0, -1), distance: 0.6 });
  b.mesh(pay, new THREE.BoxGeometry(0.9, 0.3, 0.6), 'mli_silver', { pos: V3(0, y + 0.2, -L / 2 + 0.35) });
  wheels(b, { d, w: 0.23, track: 1.8, base: wb, label: 'Wire-mesh wheel with hub motor' });
  b.flow('power', [V3(0.25, y + 0.18, L / 2 - 0.3), V3(0.6, y + 0.05, 0.8), V3(0.9, d / 2, wb / 2)]);
  return b.finish({ id: 'lrv' });
}
