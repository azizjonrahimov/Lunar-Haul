// Lunar Outpost Pegasus (F-51), NASA's other Phase 1 LTV: a lighter evolution of Eagle, "less than half the size of
// Eagle", no robotic arm; two seats, two solar arrays and spring-mesh tyres (NASA image captions); four in-wheel
// motors and GM batteries with heaters (one report). Dimensions unpublished: drawn at about half of Eagle.
import * as THREE from 'three';
import { builder, V3 } from '../parts.js';
import { wheels, boxShell, seat, mast, panel } from './kit-common.js';

export const kit = {
  story: {
    whole: 'Lunar Outpost’s Pegasus, the second Phase 1 lunar terrain vehicle: lighter than Eagle, two seats, two solar arrays, spring-mesh tyres and no arm; faster than 14.5 km/h. Its size is unpublished, so the body is schematic.',
    cutaway: 'Cut through the body: GM battery packs with heaters and insulation sit low in the centre (one report; schematic here).',
    exploded: 'Solar arrays out, seats up, wheels with their in-hub motors out.',
  },
  cut: { dir: 'down', at: 0.33 }, shell: ['chassis'], atc: 'battery',
  dims: [{ label: 'Length', text: 'about 3.2 m as drawn', axis: 'z', src: ['assumed'], conf: 'Low' }],
  parts: {
    chassis: { what: 'A light frame, “less than half the size of Eagle”, with a much smaller cargo capacity.', size: 'not published', src: ['pegasus'], conf: 'Medium' },
    battery: { what: 'GM high-nickel lithium-ion packs with heaters and insulation for the night.', size: 'kWh unpublished', src: ['pegasus'], conf: 'Low' },
    seats: { what: 'Two seats for suited astronauts; it also drives itself or from Earth.', size: '2 seats', src: ['nasaOct26'], conf: 'High' },
    solar: { what: 'Two solar arrays.', size: '2 arrays', src: ['nasaOct26'], conf: 'High' },
    mast: { what: 'Cameras and antenna on a short mast.', size: 'not published', src: ['assumed'], conf: 'Low' },
    wheels: { what: 'Four wheels on spring-mesh tyres, each with its own in-wheel motor.', size: '4 wheels', src: ['nasaOct26', 'pegasus'], conf: 'High' },
  },
};

export function build(mats, opts) {
  const b = builder(mats, opts), L = 3.2, W = 1.9, d = 0.75, deckY = 0.85;
  const ch = b.part('chassis', 'Frame and deck', { distance: 0, representative: true });
  boxShell(b, ch, { hx: W / 2 - 0.3, hz: L / 2 - 0.2, y0: deckY - 0.35, y1: deckY, mat: 'mli_silver' });
  const bat = b.part('battery', 'Battery packs (GM)', { axis: V3(0, -1, 0), distance: 0.8, representative: true });
  b.mesh(bat, new THREE.BoxGeometry(0.75, 0.22, 1.0), 'radiator', { cut: true, capColor: '#7f9ab8', pos: V3(0, deckY - 0.2, -0.1) });
  const st = b.part('seats', 'Crew seats', { axis: V3(0, 1, 0), distance: 0.7 });
  for (const x of [-0.4, 0.4]) seat(b, st, V3(x, deckY + 0.05, -0.1));
  const sol = b.part('solar', 'Solar arrays (2)', { axis: V3(1, 0, 0), distance: 0.6 });
  for (const x of [-1, 1]) panel(b, sol, V3(x * (W / 2 + 0.02), deckY + 0.35, -0.9), 1.0, 0.6);
  const m = b.part('mast', 'Mast: cameras and antenna', { axis: V3(0, 1, 0), distance: 0.5, representative: true });
  mast(b, m, V3(0, deckY, L / 2 - 0.35), 1.7, { dish: 0.18 });
  wheels(b, { d, w: 0.22, track: W - 0.1, base: 2.1, label: 'Wheel, spring-mesh tyre, in-wheel motor' });
  b.flow('power', [V3(W / 2, deckY + 0.35, -0.9), V3(0.3, deckY - 0.1, -0.4), V3(0, deckY - 0.2, -0.1)]);
  return b.finish({ id: 'pegasus' });
}
