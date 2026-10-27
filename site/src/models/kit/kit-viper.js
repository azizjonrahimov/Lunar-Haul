// NASA VIPER (F-51), the best-documented modern rover (Bluethmann, NASA, Nov 2024): 1.7 × 1.7 × 2.5 m, four wheel
// modules (50 cm wheels, active suspension), a mast with the navigation cameras and lights at 2.0 m and the high-gain
// antenna at 2.3 m, solar arrays on three sides, two internal batteries (5.42 kWh), radiators on top, the avionics
// in a warm box, and the 1 m TRIDENT drill. Positions inside the body follow the slide set; sizes are drawn.
import * as THREE from 'three';
import { builder, strut, V3 } from '../parts.js';
import { wheels, boxShell, panel } from './kit-common.js';

export const kit = {
  story: {
    whole: 'NASA’s VIPER, flying to the south pole in 2027 on a Blue Moon MK1: 1.7 × 1.7 × 2.5 m, 490 kg at launch, a mast 2.3 m high, solar on three sides for a sun that never climbs. The best-documented modern rover: most of its layout here is published.',
    cutaway: 'Cut through the body: two batteries (5.42 kWh) and the warm box with the flight avionics, IMU and motor controllers; radiators on top shed their heat.',
    exploded: 'Solar arrays out, radiators up, the drill down, the wheel modules out.',
  },
  cut: { dir: 'down', at: 0.25 }, shell: ['body', 'solar'], atc: 'warmbox',
  dims: [
    { label: 'Height', text: '2.5 m', axis: 'y', src: ['viper'], conf: 'High' },
    { label: 'Width', text: '1.7 m', part: 'body', axis: 'x', src: ['viper'], conf: 'High' },
  ],
  parts: {
    body: { what: 'The chassis between the four wheel modules.', size: '1.7 × 1.7 × 2.5 m overall', src: ['viper'], conf: 'High' },
    batteries: { what: 'Two internal batteries for driving through shadow; 50 hours of survival in low-power mode.', size: '5.42 kWh total', src: ['viper'], conf: 'High' },
    warmbox: { what: 'The warm box: flight avionics, IMU and motor controllers, each driving six motors on two wheel modules.', size: 'not published', src: ['viper'], conf: 'High' },
    radiators: { what: 'Radiators on top, fed by loop heat pipes, shed the electronics’ heat.', size: 'not published', src: ['viper'], conf: 'High' },
    solar: { what: 'Solar arrays on three sides; at the pole the sun stays near the horizon.', size: '320 W a panel (450 W on a corner)', src: ['viper'], conf: 'High' },
    mast: { what: 'Navigation cameras and lights on a pan-tilt at 2.0 m; the high-gain antenna on a pan-tilt at 2.3 m.', size: '2.0 m and 2.3 m', src: ['viper'], conf: 'High' },
    drill: { what: 'The TRIDENT drill takes samples from up to 1 m down.', size: '1 m', src: ['viper'], conf: 'High' },
    wheels: { what: 'Four wheel modules with ±50° steering and active suspension (7-43 cm ground clearance).', size: '50 cm wheels, 2.5 cm grousers', src: ['viper'], conf: 'High' },
  },
};

export function build(mats, opts) {
  const b = builder(mats, opts), S = 1.7, d = 0.5, y0 = 0.35, y1 = 1.05;
  const body = b.part('body', 'Chassis', { distance: 0 });
  boxShell(b, body, { hx: 0.55, hz: 0.68, y0, y1, mat: 'white_paint' });
  const bat = b.part('batteries', 'Batteries (2)', { axis: V3(0, -1, 0), distance: 0.6 });
  for (const x of [-0.25, 0.25]) b.mesh(bat, new THREE.BoxGeometry(0.32, 0.2, 0.5), 'radiator', { cut: true, capColor: '#7f9ab8', pos: V3(x, y0 + 0.16, -0.25) });
  const wb = b.part('warmbox', 'Warm box: avionics, IMU, motor controllers', { axis: V3(0, 0, 1), distance: 0.6 });
  b.mesh(wb, new THREE.BoxGeometry(0.75, 0.25, 0.4), 'mli_gold', { cut: true, capColor: '#d9b867', pos: V3(0, y0 + 0.2, 0.3) });
  const rad = b.part('radiators', 'Radiators (on top)', { axis: V3(0, 1, 0), distance: 0.5 });
  b.mesh(rad, new THREE.BoxGeometry(1.0, 0.04, 1.2), 'radiator', { pos: V3(0, y1 + 0.03, 0) });
  const sol = b.part('solar', 'Solar arrays (3 sides)', { axis: V3(0, 0, -1), distance: 0.5 });
  for (const x of [-1, 1]) panel(b, sol, V3(x * 0.6, y1 + 0.35, 0), 1.3, 0.9);
  b.mesh(sol, new THREE.BoxGeometry(1.15, 0.9, 0.03), 'solar_cell', { pos: V3(0, y1 + 0.35, -0.7) });
  const m = b.part('mast', 'Mast: cameras, lights, high-gain antenna', { axis: V3(0, 1, 0), distance: 0.5 });
  b.mesh(m, strut(V3(0.3, y1, 0.55), V3(0.3, 2.0, 0.55), 0.04), 'aluminium');
  b.mesh(m, new THREE.BoxGeometry(0.42, 0.12, 0.14), 'dark_metal', { pos: V3(0.3, 2.0, 0.55) });
  b.mesh(m, new THREE.CylinderGeometry(0.2, 0.06, 0.08, b.seg(20)), 'white_paint', { pos: V3(0.3, 2.3, 0.5), rot: { x: -0.6 } });
  const dr = b.part('drill', 'TRIDENT drill', { axis: V3(0, -1, 0), distance: 0.4 });
  b.mesh(dr, new THREE.CylinderGeometry(0.035, 0.035, 1.0, 10), 'dark_metal', { pos: V3(-0.45, 0.65, 0.62) });
  wheels(b, { d, w: 0.18, track: S - 0.2, base: 1.25, label: 'Wheel module, 0.5 m' });
  b.flow('power', [V3(0.6, y1 + 0.35, 0), V3(0.4, y0 + 0.3, -0.2), V3(0.25, y0 + 0.16, -0.25)]);
  return b.finish({ id: 'viper' });
}
