// ULA Centaur V upper stage (F-51), CV-HE: 5.4 m across and 12.6 m tall; stainless-steel balloon tanks, liquid hydrogen
// forward and liquid oxygen aft, split by a common bulkhead (two steel skins round a fibreglass honeycomb core); two
// RL10 engines at the aft end; the avionics on the forward adapter. Tank lengths are computed from the propellant
// masses (LH2 ~4.9 m of barrel, LOX ~1.8 m); the barrel is shortened a little here so the domes fit the 12.6 m.
import * as THREE from 'three';
import { builder, lathe, shellProfile, tankProfile, bellProfile, V3 } from '../parts.js';

const DOWN = V3(0, -1, 0), Y = V3(0, 1, 0);

export function build(mats, opts) {
  const b = builder(mats, opts), R = 2.7, y0 = 2.55, top = 12.6, s = b.seg(56);
  const skin = b.part('skin', 'Tank walls (stainless steel, 0.51 mm)', { distance: 0 });
  b.mesh(skin, lathe(shellProfile(R, y0 + 0.6, top - 1.25, 0.6, 0.9, 0.05), s), 'stainless_steel', { cut: true, capColor: '#b9b8b4' });
  const lox = b.part('lox', 'Liquid oxygen tank (aft)', { axis: DOWN, distance: 1.6 });
  b.mesh(lox, lathe(tankProfile(R - 0.12, y0 + 1.1, y0 + 2.6, 0.8), s), 'mli_silver', { cut: true, capColor: '#7fb3db' });
  const bh = b.part('bulkhead', 'Common bulkhead', { distance: 0 });
  b.mesh(bh, new THREE.CylinderGeometry(R - 0.12, R - 0.12, 0.12, s), 'mli_gold', { cut: true, capColor: '#d9c27a', pos: V3(0, y0 + 3.5, 0) });
  const lh2 = b.part('lh2', 'Liquid hydrogen tank (forward)', { axis: Y, distance: 2.4 });
  b.mesh(lh2, lathe(tankProfile(R - 0.12, y0 + 4.4, top - 2.2, 0.8), s), 'mli_silver', { cut: true, capColor: '#a9d4f5' });
  const av = b.part('avionics', 'Forward adapter with the avionics', { axis: Y, distance: 1.4 });
  b.mesh(av, new THREE.CylinderGeometry(R * 0.82, R * 0.95, 0.7, s), 'aluminium', { cut: true, capColor: '#9aa3ad', pos: V3(0, top - 0.35, 0) });
  for (let k = 0; k < 6; k++) { const a = k * Math.PI / 3; b.mesh(av, new THREE.BoxGeometry(0.5, 0.25, 0.35), 'mli_gold', { pos: V3(Math.cos(a) * R * 0.7, top - 0.82, Math.sin(a) * R * 0.7), rot: { y: -a } }); }
  const eng = b.part('engines', 'RL10 engines (2)', { axis: DOWN, distance: 1.8 });
  for (const x of [-1.05, 1.05]) {
    b.mesh(eng, lathe(bellProfile(0.12, 0.78, 2.1, 0.02), b.seg(40)), 'dark_metal', { cut: true, pos: V3(x, y0 - 0.15, 0) });
    b.mesh(eng, new THREE.CylinderGeometry(0.28, 0.32, 0.5, b.seg(16)), 'aluminium', { pos: V3(x, y0 + 0.05, 0) });   // turbopump and valves
  }
  b.flow('propellant', [V3(0, y0 + 0.4, 0), V3(0.6, y0 + 0.2, 0.3), V3(1.05, y0 - 0.1, 0)]);
  b.flow('propellant', [V3(0, y0 + 3.6, 0), V3(-R + 0.4, y0 + 2.4, 0.4), V3(-R + 0.5, y0 + 0.4, 0.4), V3(-1.05, y0 - 0.1, 0)]);
  b.flow('power', [V3(R * 0.7, top - 0.82, 0), V3(R * 0.5, top - 3, 0.6), V3(1.05, y0 + 0.1, 0)]);
  return b.finish({ id: 'centaur_v' });
}
