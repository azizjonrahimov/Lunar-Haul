// The Lunar ATC base computer (F-51, our design, not a maker's): the box Lunar ATC adds to each vehicle. Two compute
// boards run the safety program and the planner side by side, so either can take over (failover); memory and storage,
// a power supply on the vehicle's bus, a watchdog that switches boards, a finned lid that sheds heat into the
// vehicle's own radiator. Sizes are drawing sizes until B-81 measures compute, memory, bandwidth and power.
import * as THREE from 'three';
import { builder, V3 } from '../parts.js';
import { boxShell } from './kit-common.js';

export const kit = {
  story: {
    whole: 'The Lunar ATC base computer, about the size of a shoebox: the box our design adds to every rover and lander. It runs the safety program and the planner, and keeps running if one board fails. This is our design, not any maker’s.',
    cutaway: 'Two compute boards side by side run the same safety program; a watchdog switches to the second if the first stops answering. Memory and storage sit between them; the power supply takes the vehicle’s bus.',
    exploded: 'Lid and fins up, both boards out, the power supply down.',
  },
  cut: { dir: 'down', at: 0.55 }, shell: ['case'],
  dims: [{ label: 'Length', text: '0.30 m (drawing size)', axis: 'z', src: ['design'], conf: 'Design' }],
  parts: {
    case: { what: 'A sealed aluminium case; it bolts to the vehicle’s warm box so the vehicle keeps it warm at night.', size: '0.30 × 0.12 × 0.22 m (drawing)', src: ['design'], conf: 'Design' },
    boardA: { what: 'Compute board A runs the safety program (the rules of the road) and the planner.', size: 'measured in B-81', src: ['design'], conf: 'Design' },
    boardB: { what: 'Compute board B runs the same safety program in step, ready to take over (failover).', size: 'measured in B-81', src: ['design'], conf: 'Design' },
    memory: { what: 'Memory and storage: the map, the agreed plans and the log of every decision, for audits on Earth later.', size: 'measured in B-81', src: ['design'], conf: 'Design' },
    power: { what: 'The power supply, fed from the vehicle’s own battery bus.', size: 'measured in B-81', src: ['design'], conf: 'Design' },
    watchdog: { what: 'A watchdog that switches to board B if board A stops answering.', size: 'small', src: ['design'], conf: 'Design' },
    lid: { what: 'A finned lid that passes heat to the vehicle’s radiator.', size: 'drawing', src: ['design'], conf: 'Design' },
  },
};

export function build(mats, opts) {
  const b = builder(mats, opts), y0 = 0.02, y1 = 0.14;
  const c = b.part('case', 'Case', { distance: 0 });
  boxShell(b, c, { hx: 0.11, hz: 0.15, y0, y1, t: 0.006, mat: 'aluminium', cap: '#9aa3ad' });
  for (const [name, label, x, col] of [['boardA', 'Compute board A', -0.045, '#2f7d5b'], ['boardB', 'Compute board B (failover)', 0.045, '#2f6d7d']]) {
    const p = b.part(name, label, { axis: V3(Math.sign(x), 0.3, 0), distance: 0.12 });
    b.mesh(p, new THREE.BoxGeometry(0.008, 0.08, 0.24), 'radiator', { cut: true, capColor: col, pos: V3(x, 0.08, 0) });
    b.mesh(p, new THREE.BoxGeometry(0.02, 0.03, 0.04), 'dark_metal', { pos: V3(x + Math.sign(x) * -0.012, 0.09, 0.03) });   // the processor
  }
  const mem = b.part('memory', 'Memory and storage', { axis: V3(0, 1, 0), distance: 0.1 });
  b.mesh(mem, new THREE.BoxGeometry(0.05, 0.05, 0.08), 'mli_gold', { cut: true, capColor: '#d9b867', pos: V3(0, 0.06, -0.05) });
  const pw = b.part('power', 'Power supply', { axis: V3(0, 0, 1), distance: 0.12 });
  b.mesh(pw, new THREE.BoxGeometry(0.06, 0.05, 0.05), 'dark_metal', { cut: true, capColor: '#5b6a7a', pos: V3(0, 0.055, 0.1) });
  const wd = b.part('watchdog', 'Watchdog (failover switch)', { axis: V3(0, 1, 1), distance: 0.1 });
  b.mesh(wd, new THREE.BoxGeometry(0.03, 0.02, 0.03), 'mli_silver', { cut: true, capColor: '#c4cad3', pos: V3(0, 0.05, 0.04) });
  const lid = b.part('lid', 'Finned lid', { axis: V3(0, 1, 0), distance: 0.14 });
  for (let k = 0; k < 7; k++) b.mesh(lid, new THREE.BoxGeometry(0.2, 0.025, 0.006), 'aluminium', { cut: true, pos: V3(0, y1 + 0.0125, -0.12 + k * 0.04) });
  b.flow('power', [V3(0, 0.055, 0.2), V3(0, 0.055, 0.1), V3(-0.045, 0.08, 0), V3(0.045, 0.08, 0)]);
  return b.finish({ id: 'atc_computer' });
}
