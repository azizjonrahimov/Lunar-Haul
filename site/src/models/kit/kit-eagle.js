// Lunar Outpost Eagle (F-51): the cargo-class LTV built with GM, Goodyear, MDA Space and Leidos; a reconfigurable
// cargo bed, a robotic arm, designed to work through two-week nights at about -173 °C (company, Medium). Dimensions
// unpublished: drawn at a cargo-class size, about twice Pegasus.
import * as THREE from 'three';
import { builder, strut, V3 } from '../parts.js';
import { wheels, boxShell, seat, mast, panel } from './kit-common.js';

export const kit = {
  story: {
    whole: 'Lunar Outpost’s Eagle: a reconfigurable cargo bed, a robotic arm and night survival, built with GM, Goodyear, MDA Space and Leidos. Pegasus, its lighter evolution, won the NASA Phase 1 award. Its size here is schematic.',
    cutaway: 'Cut through the body: the battery and the heaters that carry it through the two-week night sit low in the centre.',
    exploded: 'Bed, arm, seats and wheels apart.',
  },
  cut: { dir: 'down', at: 0.3 }, shell: ['chassis'], atc: 'battery',
  dims: [{ label: 'Length', text: 'about 4.6 m as drawn', axis: 'z', src: ['assumed'], conf: 'Low' }],
  parts: {
    chassis: { what: 'A cargo-class chassis built with GM, Goodyear, MDA Space and Leidos.', size: 'not published', src: ['eagle'], conf: 'Medium' },
    battery: { what: 'Battery, avionics and heaters to survive two-week nights at about -173 °C.', size: 'not published', src: ['eagle'], conf: 'Medium' },
    bed: { what: 'A reconfigurable cargo bed at the back.', size: 'not published', src: ['eagle'], conf: 'Medium' },
    arm: { what: 'A robotic arm (MDA Space) for loading and tools.', size: 'not published', src: ['eagle'], conf: 'Medium' },
    seats: { what: 'Seats for two suited crew.', size: '2 seats', src: ['eagle'], conf: 'Low' },
    solar: { what: 'Solar panels; their layout is not published.', size: 'not published', src: ['assumed'], conf: 'Low' },
    mast: { what: 'Cameras and antenna on a mast.', size: 'not published', src: ['assumed'], conf: 'Low' },
    wheels: { what: 'Four wheels on airless tyres (Goodyear).', size: '4 wheels', src: ['eagle'], conf: 'Medium' },
  },
};

export function build(mats, opts) {
  const b = builder(mats, opts), L = 4.6, W = 2.5, d = 1.0, deckY = 1.15;
  const ch = b.part('chassis', 'Chassis', { distance: 0, representative: true });
  boxShell(b, ch, { hx: W / 2 - 0.35, hz: L / 2 - 0.25, y0: deckY - 0.45, y1: deckY, mat: 'white_paint' });
  const bat = b.part('battery', 'Battery, avionics and heaters', { axis: V3(0, -1, 0), distance: 0.9, representative: true });
  b.mesh(bat, new THREE.BoxGeometry(1.0, 0.3, 1.4), 'mli_gold', { cut: true, capColor: '#d9b867', pos: V3(0, deckY - 0.25, 0.3) });
  const bed = b.part('bed', 'Reconfigurable cargo bed', { axis: V3(0, 1, -1), distance: 0.8 });
  b.mesh(bed, new THREE.BoxGeometry(W - 0.6, 0.08, 1.5), 'aluminium', { pos: V3(0, deckY + 0.04, -L / 2 + 1.0) });
  for (const x of [-1, 1]) b.mesh(bed, new THREE.BoxGeometry(0.06, 0.35, 1.5), 'aluminium', { pos: V3(x * (W / 2 - 0.33), deckY + 0.2, -L / 2 + 1.0) });
  b.mesh(bed, new THREE.BoxGeometry(0.9, 0.5, 0.8), 'mli_gold', { pos: V3(0, deckY + 0.33, -L / 2 + 1.0) });
  const arm = b.part('arm', 'Robotic arm', { axis: V3(1, 0, 0), distance: 0.8 });
  const a0 = V3(W / 2 - 0.45, deckY + 0.05, -0.2), a1 = a0.clone().add(V3(0, 0.9, -0.3)), a2 = a1.clone().add(V3(-0.1, -0.1, -0.9));
  b.mesh(arm, strut(a0, a1, 0.07), 'aluminium'); b.mesh(arm, strut(a1, a2, 0.055), 'aluminium');
  const st = b.part('seats', 'Crew seats', { axis: V3(0, 1, 0), distance: 0.7 });
  for (const x of [-0.45, 0.45]) seat(b, st, V3(x, deckY + 0.05, 0.6));
  const sol = b.part('solar', 'Solar panels', { axis: V3(-1, 0, 0), distance: 0.6, representative: true });
  for (const x of [-1, 1]) panel(b, sol, V3(x * (W / 2 - 0.32), deckY - 0.25, 1.4), 1.0, 0.4);
  const m = b.part('mast', 'Mast: cameras and antenna', { axis: V3(0, 1, 0), distance: 0.6, representative: true });
  mast(b, m, V3(-W / 2 + 0.5, deckY, L / 2 - 0.4), 2.2);
  wheels(b, { d, w: 0.3, track: W - 0.1, base: 3.0, label: 'Wheel, airless tyre' });
  b.flow('cargo', [V3(0, deckY + 0.6, -1.3), V3(W / 2 + 0.3, deckY + 1.0, -1.1), V3(W / 2 + 0.6, 0.2, -1.1)]);
  return b.finish({ id: 'eagle' });
}
