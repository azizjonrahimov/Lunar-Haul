// Intuitive Machines Micro-Nova "Grace" (F-51): about 1 m tall, 8-10 kg of payload over more than 25 km, deployed from
// the lander on a rail; IMU, star tracker, navigation camera, lidar and a situational-awareness camera (LPSC 2024,
// IM page). The body, tanks and engines are unpublished: a schematic hopper about 1 m tall.
import * as THREE from 'three';
import { builder, lathe, shellProfile, bellProfile, strut, radial, at, V3 } from '../parts.js';

export const kit = {
  story: {
    whole: 'Intuitive Machines’ Micro-Nova, about 1 m tall: it rides a rail off the lander, then flies parabolas or level hops of more than 25 km with up to 8-10 kg of payload. On IM-2 it never left: the lander tipped over.',
    cutaway: 'Cut through the body: the tanks and engine are not published, so they are drawn schematic; the sensors are the published list.',
    exploded: 'Sensors out, tanks up, engine down, legs out.',
  },
  cut: { dir: 'side' }, shell: ['body'], atc: 'sensors',
  dims: [{ label: 'Height', text: 'about 1 m', axis: 'y', src: ['microNova'], conf: 'High' }],
  parts: {
    body: { what: 'The hopper’s body; its shape is not published.', size: '~1 m tall', src: ['microNova'], conf: 'Low' },
    sensors: { what: 'IMU, star tracker, optical navigation camera, lidar and a situational-awareness camera.', size: '5 sensors', src: ['microNova', 'microNovaIm'], conf: 'High' },
    payload: { what: 'Up to 8-10 kg of payload carried over 25 km and more.', size: '8-10 kg', src: ['microNova', 'microNovaIm'], conf: 'High' },
    tanks: { what: 'Propellant and pressurant; reported as hydrazine by one source only.', size: 'not published', src: ['assumed'], conf: 'Low' },
    engine: { what: 'A downward engine and small thrusters; not published.', size: 'not published', src: ['assumed'], conf: 'Low' },
    legs: { what: 'Landing legs; their number and shape are not published.', size: 'not published', src: ['assumed'], conf: 'Low' },
  },
};

export function build(mats, opts) {
  const b = builder(mats, opts), R = 0.32, y0 = 0.3, y1 = 0.88, s = b.seg(32);
  const body = b.part('body', 'Body', { distance: 0, representative: true });
  b.mesh(body, lathe(shellProfile(R, y0, y1, 0.06, 0.1, 0.02), s), 'mli_gold', { cut: true, capColor: '#d9b867' });
  const tk = b.part('tanks', 'Propellant tanks', { axis: V3(0, 1, 0), distance: 0.4, representative: true });
  for (const x of [-0.12, 0.12]) b.mesh(tk, new THREE.SphereGeometry(0.13, b.seg(20), b.seg(12)), 'aluminium', { cut: true, capColor: '#c9b48a', pos: V3(x, 0.55, 0) });
  const en = b.part('engine', 'Engine', { axis: V3(0, -1, 0), distance: 0.3, representative: true });
  b.mesh(en, lathe(bellProfile(0.03, 0.08, 0.16, 0.008), b.seg(16)), 'dark_metal', { cut: true, pos: V3(0, y0 - 0.04, 0) });
  const sn = b.part('sensors', 'Sensors: IMU, star tracker, cameras, lidar', { axis: V3(0, 0, 1), distance: 0.3 });
  b.mesh(sn, new THREE.BoxGeometry(0.1, 0.07, 0.06), 'dark_metal', { pos: V3(0, 0.7, R + 0.02) });   // navigation camera
  b.mesh(sn, new THREE.CylinderGeometry(0.04, 0.04, 0.08, 12), 'dark_metal', { pos: V3(0.15, 0.6, R - 0.02), rot: { x: Math.PI / 2 } });   // lidar
  b.mesh(sn, new THREE.CylinderGeometry(0.035, 0.035, 0.07, 12), 'white_paint', { pos: V3(0, y1 + 0.13, 0) });   // star tracker
  const pl = b.part('payload', 'Payload', { axis: V3(0, 1, 0), distance: 0.35 });
  b.mesh(pl, new THREE.BoxGeometry(0.22, 0.1, 0.22), 'mli_silver', { pos: V3(0, y1 + 0.03, 0) });
  for (let k = 0; k < 4; k++) {
    const a = k * Math.PI / 2 + Math.PI / 4, leg = b.part(`leg${k}`, 'Landing leg', { axis: radial(a), distance: 0.25, representative: true });
    leg.userData.group = 'legs';
    const knee = at(a, R * 0.9, y0 + 0.05), foot = at(a, 0.5, 0.03);
    b.mesh(leg, strut(knee, foot, 0.015), 'aluminium');
    b.mesh(leg, new THREE.CylinderGeometry(0.05, 0.06, 0.02, b.seg(12)), 'aluminium', { pos: foot.clone().setY(0.01) });
  }
  return b.finish({ id: 'micro_nova' });
}
