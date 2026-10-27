// Lunar Outpost MAPP (F-51), the small rover: 45 × 38 × 40 cm, 5-10 kg, 15 kg of payload, 10 cm/s (company table).
// Four wheels, a body with solar on top, a camera head and an antenna; the inside layout is unpublished.
import * as THREE from 'three';
import { builder, V3 } from '../parts.js';
import { wheels, boxShell } from './kit-common.js';

export const kit = {
  story: {
    whole: 'Lunar Outpost’s MAPP, a suitcase-sized rover: 45 × 38 × 40 cm, up to 10 kg, 15 kg of payload, 10 cm a second. Next to an LTV it is a toy; next to the astronaut, a carry-on bag.',
    cutaway: 'Cut through the body: battery and electronics fill it; their layout is not published.',
    exploded: 'Solar lid up, wheels out.',
  },
  cut: { dir: 'down', at: 0.55 }, shell: ['body'], atc: 'electronics',
  dims: [
    { label: 'Length', text: '45 cm', axis: 'z', src: ['loRovers'], conf: 'High' },
    { label: 'Height', text: '40 cm', axis: 'y', src: ['loRovers'], conf: 'High' },
  ],
  parts: {
    body: { what: 'The body of a rover the size of a carry-on suitcase.', size: '45 × 38 × 40 cm, 5-10 kg', src: ['loRovers'], conf: 'High' },
    electronics: { what: 'Battery and electronics; their layout is not published.', size: 'not published', src: ['assumed'], conf: 'Low' },
    solar: { what: 'A solar panel on the lid.', size: 'not published', src: ['assumed'], conf: 'Low' },
    head: { what: 'Cameras and an antenna; MAPP carries user equipment for the lunar LTE network.', size: 'not published', src: ['loRovers'], conf: 'Low' },
    wheels: { what: 'Four wheels; top speed 10 cm a second.', size: '10 cm/s', src: ['loRovers'], conf: 'High' },
  },
};

export function build(mats, opts) {
  const b = builder(mats, opts), L = 0.45, W = 0.38, d = 0.16;
  const body = b.part('body', 'Body', { distance: 0 });
  boxShell(b, body, { hx: W / 2 - 0.06, hz: L / 2 - 0.02, y0: 0.06, y1: 0.3, t: 0.008, mat: 'white_paint' });
  const el = b.part('electronics', 'Battery and electronics', { axis: V3(0, 1, 0), distance: 0.25, representative: true });
  b.mesh(el, new THREE.BoxGeometry(0.16, 0.08, 0.26), 'mli_gold', { cut: true, capColor: '#d9b867', pos: V3(0, 0.13, 0) });
  const sol = b.part('solar', 'Solar lid', { axis: V3(0, 1, 0), distance: 0.15, representative: true });
  b.mesh(sol, new THREE.BoxGeometry(W - 0.1, 0.012, L - 0.05), 'solar_cell', { pos: V3(0, 0.307, 0) });
  const hd = b.part('head', 'Camera head and antenna', { axis: V3(0, 1, 1), distance: 0.15, representative: true });
  b.mesh(hd, new THREE.BoxGeometry(0.1, 0.05, 0.05), 'dark_metal', { pos: V3(0, 0.36, L / 2 - 0.06) });
  b.mesh(hd, new THREE.CylinderGeometry(0.004, 0.004, 0.12, 6), 'aluminium', { pos: V3(-0.1, 0.37, -0.15) });
  wheels(b, { d, w: 0.05, track: W - 0.02, base: L - 0.12, label: 'Wheel', distance: 0.1 });
  return b.finish({ id: 'mapp' });
}
