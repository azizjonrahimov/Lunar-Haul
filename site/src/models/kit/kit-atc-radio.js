// The Lunar ATC plug-in radio unit (F-51, our design, not a maker's): a small module that plugs into a vehicle's
// payload connector and links it to the other robots and the base (the robot mesh, B-70) on its own antenna. Inside:
// the radio board, a power amplifier, a shielded front end and the plug; on top, a short whip antenna on a hinge.
// Sizes are drawing sizes until B-81 measures bandwidth and power.
import * as THREE from 'three';
import { builder, strut, V3 } from '../parts.js';
import { boxShell } from './kit-common.js';

export const kit = {
  story: {
    whole: 'The Lunar ATC radio unit: a module that plugs into any rover or lander and links it to the other robots and the base, on its own antenna, with or without Earth in view. This is our design, not any maker’s.',
    cutaway: 'The radio board makes and reads the signal; the power amplifier gives it reach over the ridges; a shield keeps it from upsetting the vehicle’s own radios.',
    exploded: 'The board, amplifier and shield out of the case, the antenna up.',
  },
  cut: { dir: 'down', at: 0.5 }, shell: ['case'],
  dims: [{ label: 'Length', text: '0.18 m (drawing size)', part: 'case', axis: 'z', src: ['design'], conf: 'Design' }],
  parts: {
    case: { what: 'A plug-in case that fits a standard payload slot.', size: '0.18 × 0.06 × 0.12 m (drawing)', src: ['design'], conf: 'Design' },
    board: { what: 'The radio board: it sends and receives the robots’ messages (positions, plans, bids).', size: 'measured in B-81', src: ['design'], conf: 'Design' },
    amp: { what: 'A power amplifier that gives the signal its reach over the terrain.', size: 'measured in B-81', src: ['design'], conf: 'Design' },
    shield: { what: 'A metal shield round the front end, so the unit does not disturb the vehicle’s own radios.', size: 'drawing', src: ['design'], conf: 'Design' },
    plug: { what: 'The connector: power in, data to the base computer.', size: 'drawing', src: ['design'], conf: 'Design' },
    antenna: { what: 'A short whip antenna on a hinge, folded flat for launch.', size: '~0.3 m (drawing)', src: ['design'], conf: 'Design' },
  },
};

export function build(mats, opts) {
  const b = builder(mats, opts), y0 = 0.01, y1 = 0.07;
  const c = b.part('case', 'Case', { distance: 0 });
  boxShell(b, c, { hx: 0.06, hz: 0.09, y0, y1, t: 0.004, mat: 'white_paint', cap: '#c7ccd3' });
  const bd = b.part('board', 'Radio board', { axis: V3(1, 0, 0), distance: 0.08 });
  b.mesh(bd, new THREE.BoxGeometry(0.09, 0.006, 0.15), 'radiator', { cut: true, capColor: '#2f7d5b', pos: V3(0, 0.025, 0) });
  const amp = b.part('amp', 'Power amplifier', { axis: V3(0, 1, 0), distance: 0.07 });
  b.mesh(amp, new THREE.BoxGeometry(0.035, 0.015, 0.04), 'dark_metal', { cut: true, capColor: '#5b6a7a', pos: V3(-0.02, 0.037, 0.04) });
  const sh = b.part('shield', 'RF shield', { axis: V3(0, 1, 0), distance: 0.1 });
  b.mesh(sh, new THREE.BoxGeometry(0.05, 0.02, 0.05), 'stainless_steel', { cut: true, capColor: '#b9b8b4', pos: V3(0.02, 0.04, -0.03) });
  const pl = b.part('plug', 'Plug', { axis: V3(0, 0, -1), distance: 0.08 });
  b.mesh(pl, new THREE.BoxGeometry(0.07, 0.03, 0.02), 'mli_gold', { cut: true, capColor: '#d9b867', pos: V3(0, 0.04, -0.1) });
  const an = b.part('antenna', 'Whip antenna', { axis: V3(0, 1, 0), distance: 0.08 });
  b.mesh(an, new THREE.CylinderGeometry(0.008, 0.008, 0.02, 10), 'dark_metal', { pos: V3(0.035, y1 + 0.01, 0.06) });
  b.mesh(an, strut(V3(0.035, y1 + 0.02, 0.06), V3(0.035, y1 + 0.32, 0.06), 0.003), 'aluminium');
  b.flow('power', [V3(0, 0.04, -0.12), V3(0, 0.03, -0.05), V3(-0.02, 0.037, 0.04), V3(0.035, y1 + 0.3, 0.06)]);
  return b.finish({ id: 'atc_radio' });
}
