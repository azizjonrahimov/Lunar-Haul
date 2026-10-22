// Lander generators at true scale from the catalogue (dims.*.value, metres; y up, ground at y = 0). Shapes follow the
// reference vehicles in the catalogue; where the real shape is unpublished (MK1 and HLS-class legs) the part is
// flagged representative. Inside each hull sit closed propellant tanks, so Cutaway has something true to show.
import * as THREE from 'three';
import { builder, lathe, shellProfile, tankProfile, bellProfile, ringProfile, strut, radial, at, V2, V3 } from './parts.js';

const Y = V3(0, 1, 0), DOWN = V3(0, -1, 0);
const v = (e, k) => e.dims[k].value;

// CLPS class: Nova-C-like hexagonal body, six legs, top-deck solar panel, one methalox bell (VR900)
export function clps(e, mats, opts) {
  const b = builder(mats, opts), H = v(e, 'height_m'), R = v(e, 'diameter_m') / 2, span = v(e, 'leg_span_m') / 2, n = v(e, 'leg_count');
  const y0 = 0.95, y1 = H - 0.45;   // body between the leg knees and the top deck
  const body = b.part('body', 'Hexagonal body (MLI)', { distance: 0 });
  b.mesh(body, lathe(shellProfile(R, y0, y1, 0, 0, 0.04, 1), 6), 'mli_silver', { cut: true, capColor: '#b9c0ca' });
  b.mesh(body, new THREE.CylinderGeometry(R * 1.02, R * 1.02, 0.06, 6), 'white_paint', { pos: V3(0, y1 + 0.03, 0) });
  const tanks = b.part('tanks', 'Methane and oxygen tanks', { distance: 1.2 });
  b.mesh(tanks, lathe(tankProfile(R * 0.55, 1.55, 1.75, R * 0.5, 8), b.seg(32)), 'aluminium', { cut: true, capColor: '#9fc6e6' });
  b.mesh(tanks, lathe(tankProfile(R * 0.55, 2.55, 2.75, R * 0.5, 8), b.seg(32)), 'aluminium', { cut: true, capColor: '#c9b48a' });
  const solar = b.part('solar', 'Top-deck solar panel', { distance: 0.9 });
  b.mesh(solar, new THREE.BoxGeometry(1.1, 0.04, 0.9), 'solar_cell', { pos: V3(0, y1 + 0.1, 0) });
  b.mesh(solar, new THREE.CylinderGeometry(0.03, 0.03, H - y1 - 0.06, 8), 'aluminium', { pos: V3(0.35, y1 + 0.06 + (H - y1 - 0.06) / 2, -0.25) });   // antenna to the full height
  const engine = b.part('engine', 'VR900 engine (methalox)', { axis: DOWN, distance: 0.7 });
  b.mesh(engine, lathe(bellProfile(0.09, 0.32, 0.55, 0.015), b.seg(40)), 'dark_metal', { cut: true, pos: V3(0, y0, 0) });
  for (let k = 0; k < n; k++) {
    const a = (k + 0.5) * 2 * Math.PI / n, leg = b.part(`leg${k}`, 'Landing leg', { axis: radial(a), distance: 0.6 });
    leg.userData.group = 'legs';
    const knee = at(a, R * 0.85, y0 + 0.25), foot = at(a, span - 0.18, 0.06);   // pad edge at the leg span
    b.mesh(leg, strut(knee, foot, 0.035), 'aluminium');
    b.mesh(leg, strut(at(a, R * 0.8, y0 + 1.0), at(a, span - 0.62, 0.35), 0.025), 'aluminium');
    b.mesh(leg, new THREE.CylinderGeometry(0.15, 0.18, 0.05, b.seg(16)), 'aluminium', { pos: foot.clone().setY(0.025) });
  }
  b.flow('propellant', [V3(0, 1.75 - R * 0.5, 0), V3(0.25, 1.3, 0.1), V3(0.1, y0 + 0.1, 0), V3(0, y0, 0)]);
  b.flow('propellant', [V3(0, 2.55 - R * 0.5, 0), V3(-0.3, 2.0, 0.2), V3(-0.25, 1.2, 0.1), V3(0, y0, 0)]);
  b.flow('power', [V3(0, y1 + 0.1, 0), V3(0.4, y1 - 0.3, 0.3), V3(0.5, 2.2, 0.3)]);
  b.flow('cargo', [V3(0, y1 + 0.3, 0), V3(0, y1 + 0.3, 1.4), V3(0, 0.3, 2.0)]);
  return b.finish({ id: e.id });
}

// MK1 class: 8.05 m x 3.08 m cylinder, BE-7 hydrolox bell, side solar panels; four representative legs
export function mk1(e, mats, opts) {
  const b = builder(mats, opts), H = v(e, 'height_m'), R = v(e, 'diameter_m') / 2, span = v(e, 'leg_span_m') / 2, n = v(e, 'leg_count');
  const y0 = 1.6, y1 = H - 0.6, s = b.seg(48);
  const hull = b.part('hull', 'Hull (white paint)', { distance: 0 });
  b.mesh(hull, lathe(shellProfile(R, y0, y1, 0.25, 0.6, 0.05), s), 'white_paint', { cut: true, capColor: '#c7ccd3' });
  const lh2 = b.part('lh2', 'Liquid hydrogen tank', { distance: 2.2 });
  b.mesh(lh2, lathe(tankProfile(R * 0.86, 4.4, 6.3, R * 0.55), s), 'mli_silver', { cut: true, capColor: '#a9d4f5' });
  const lox = b.part('lox', 'Liquid oxygen tank', { distance: 1.2 });
  b.mesh(lox, lathe(tankProfile(R * 0.8, 2.6, 2.9, R * 0.5), s), 'mli_silver', { cut: true, capColor: '#7fb3db' });
  const engine = b.part('engine', 'BE-7 engine (hydrolox, faint plume)', { axis: DOWN, distance: 1.0 });
  b.mesh(engine, lathe(bellProfile(0.14, 0.62, 1.15, 0.02), b.seg(40)), 'dark_metal', { cut: true, pos: V3(0, y0 - 0.05, 0) });
  for (const side of [1, -1]) {
    const p = b.part(`solar${side > 0 ? 'E' : 'W'}`, 'Side solar panel', { axis: V3(side, 0, 0), distance: 1.4 });
    p.userData.group = 'solar';
    b.mesh(p, new THREE.BoxGeometry(0.05, 2.6, 1.7), 'solar_cell', { pos: V3(side * (R + 0.08), 5.2, 0) });
  }
  for (let k = 0; k < n; k++) {
    const a = (k + 0.5) * 2 * Math.PI / n, leg = b.part(`leg${k}`, 'Landing leg (representative)', { axis: radial(a), distance: 1.0, representative: true,
      note: 'MK1 legs are unpublished: four legs at the Apollo LM footprint ratio (catalogue leg_span_m, Assumed)' });
    leg.userData.group = 'legs';
    const knee = at(a, R * 0.95, y0 + 0.6), foot = at(a, span - 0.45, 0.08);   // pad edge at the leg span
    b.mesh(leg, strut(knee, foot, 0.07), 'aluminium');
    b.mesh(leg, strut(at(a, R * 0.95, y0 + 2.0), at(a, span - 1.1, 0.8), 0.05), 'aluminium');
    b.mesh(leg, new THREE.CylinderGeometry(0.4, 0.45, 0.08, b.seg(20)), 'aluminium', { pos: foot.clone().setY(0.04) });
  }
  const deck = b.part('deck', 'Payload deck', { distance: 1.6 });
  b.mesh(deck, new THREE.CylinderGeometry(R * 0.8, R * 0.8, 0.3, s), 'mli_gold', { pos: V3(0, H - 0.15, 0) });
  b.flow('propellant', [V3(0, 4.4 - R * 0.55, 0), V3(0.9, 3.3, 0.4), V3(0.5, 2.0, 0.3), V3(0, y0, 0)]);
  b.flow('propellant', [V3(0, 2.6 - R * 0.5, 0), V3(-0.4, 1.9, 0), V3(0, y0, 0)]);
  b.flow('power', [V3(R + 0.08, 5.2, 0), V3(R * 0.6, 5.0, 0.4), V3(0, 7.2, 0)]);
  b.flow('cargo', [V3(0, H, 0), V3(0, H, R + 1.5), V3(0, 0.4, R + 3)]);
  return b.finish({ id: e.id });
}

// LARGE class: Starship-HLS-like 52 m x 9 m stainless hull, no flaps, a solar band, an airlock and an elevator to the
// ground, mid-body landing thrusters; six representative legs
export function large(e, mats, opts) {
  const b = builder(mats, opts), H = v(e, 'height_m'), R = v(e, 'diameter_m') / 2, span = v(e, 'leg_span_m') / 2, n = v(e, 'leg_count');
  const y0 = 3.2, yNose = 44, s = b.seg(64);
  const hull = b.part('hull', 'Stainless-steel hull', { distance: 0 });
  const nose = [];
  for (let i = 0; i <= 10; i++) { const t = i / 10; nose.push(V2(R * Math.sqrt(1 - t * t * 0.98), yNose + (H - yNose) * t)); }
  const prof = shellProfile(R, y0, yNose, 0.6, 0, 0.12);
  const outer = prof.slice(0, prof.findIndex(p => p.y >= yNose) + 1).concat(nose.slice(1)); outer[outer.length - 1].x = 0;
  const innerR = R - 0.12;
  b.mesh(hull, lathe(outer.concat([V2(0, H - 0.3), V2(innerR * 0.6, H - 1.5), V2(innerR, yNose), V2(innerR, y0), V2(0, y0 - 0.48)]), s), 'stainless_steel', { cut: true, capColor: '#b9b8b4' });
  const ch4 = b.part('ch4', 'Methane tank', { distance: 18 });   // explode distances scale with the 52 m hull
  b.mesh(ch4, lathe(tankProfile(R - 0.3, 22, 28, 2.2), s), 'stainless_steel', { cut: true, capColor: '#c9b48a' });
  const lox = b.part('lox', 'Liquid oxygen tank', { distance: 9 });
  b.mesh(lox, lathe(tankProfile(R - 0.3, 7.5, 17, 2.4), s), 'stainless_steel', { cut: true, capColor: '#7fb3db' });
  const band = b.part('solar', 'Solar band', { distance: 0, note: 'A band of solar panels around the circumference (catalogue, Starship HLS)' });
  b.mesh(band, lathe(ringProfile(R + 0.01, R + 0.08, 38, 41.5), s), 'solar_cell', { cut: true });
  const airlock = b.part('airlock', 'Airlock and elevator', { axis: V3(0, 0, 1), distance: 10, representative: true,
    note: 'Elevator from the deck to the surface (catalogue, Starship HLS); its shape here is representative' });
  b.mesh(airlock, new THREE.BoxGeometry(2.6, 3.2, 1.4), 'white_paint', { pos: V3(0, 35.6, R + 0.5) });
  b.mesh(airlock, new THREE.BoxGeometry(2.4, 0.25, 2.2), 'aluminium', { pos: V3(0, 12, R + 1.4) });   // the elevator platform, part-way down
  for (const x of [-1.3, 1.3]) b.mesh(airlock, new THREE.BoxGeometry(0.18, 34, 0.18), 'aluminium', { pos: V3(x, 17.5, R + 1.25) });
  const thr = b.part('thrusters', 'Mid-body landing thrusters', { axis: Y, distance: 7, representative: true,
    note: 'Reported GOX/GCH4 landing thrusters in the mid-body, used within ~100 m of the surface (catalogue note)' });
  for (let k = 0; k < 6; k++) {
    const a = k * Math.PI / 3 + Math.PI / 6, g = new THREE.Group(); thr.add(g);
    b.mesh(g, lathe(bellProfile(0.12, 0.38, 0.75, 0.03), b.seg(24)), 'dark_metal', { pos: at(a, R + 0.05, 30.5) });
  }
  const eng = b.part('engines', 'Raptor engines (3 sea-level, 3 vacuum)', { axis: DOWN, distance: 6 });
  for (let k = 0; k < 6; k++) {
    const vac = k % 2 === 0, a = k * Math.PI / 3, r = vac ? 3.1 : 1.3;
    b.mesh(eng, lathe(bellProfile(0.22, vac ? 1.15 : 0.65, vac ? 2.3 : 1.3, 0.04), b.seg(32)), 'dark_metal', { cut: true, pos: at(a, r, y0 - 0.2) });
  }
  for (let k = 0; k < n; k++) {
    const a = (k + 0.5) * 2 * Math.PI / n, leg = b.part(`leg${k}`, 'Landing leg (representative)', { axis: radial(a), distance: 8, representative: true,
      note: 'HLS legs are unpublished; six legs at the catalogue leg_span_m (Assumed)' });
    leg.userData.group = 'legs';
    const knee = at(a, R - 0.2, 9), foot = at(a, span - 1.6, 0.15);   // pad edge at the leg span
    b.mesh(leg, strut(knee, foot, 0.32), 'stainless_steel');
    b.mesh(leg, strut(at(a, R - 0.2, 4), at(a, span - 3.5, 2.6), 0.22), 'stainless_steel');
    b.mesh(leg, new THREE.CylinderGeometry(1.4, 1.6, 0.3, b.seg(20)), 'stainless_steel', { pos: foot.clone().setY(0.15) });
  }
  b.flow('propellant', [V3(0, 22 - 2.2, 0), V3(1.5, 19, 1), V3(1.6, 8, 1), V3(1.3, y0, 0)]);
  b.flow('propellant', [V3(0, 22 - 2.2, 0), V3(-2, 26, 2), V3(-3.8, 30.5, 2.2)]);
  b.flow('power', [V3(0, 39.7, R), V3(0, 37, R - 1), V3(0, 35.6, R - 0.5)]);
  b.flow('cargo', [V3(0, 35.6, R + 0.5), V3(0, 35.6, R + 1.4), V3(0, 1, R + 1.4), V3(0, 0.3, R + 6)]);
  return b.finish({ id: e.id });
}
