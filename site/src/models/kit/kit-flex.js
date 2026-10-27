// Astrolab FLEX (F-51), the cargo-class parent of CLV-1: 2,000 kg on two top-deck payload interfaces, an underslung
// bay between the wheels for up to 3 m³, a six-axis arm with modular end effectors and a gimballing antenna
// (astrolab.space, company claims). Overall dimensions are unpublished: the bay is drawn at its 3 m³.
import * as THREE from 'three';
import { builder, strut, V3 } from '../parts.js';
import { wheels, boxShell, mast } from './kit-common.js';

export const kit = {
  story: {
    whole: 'Astrolab’s FLEX, a cargo-class rover: 2,000 kg on two top-deck interfaces and up to 3 m³ slung underneath, a six-axis arm to load itself. Not under NASA contract; its size here is schematic.',
    cutaway: 'Cut through the frame: the warm box sits forward, the underslung bay hangs between the wheels.',
    exploded: 'Both deck interfaces up, the bay down, the arm and antenna clear.',
  },
  cut: { dir: 'down', at: 0.55 }, shell: ['frame'], atc: 'warmbox',
  dims: [{ label: 'Underslung bay', text: '3 m³', part: 'bay', axis: 'z', src: ['astrolab'], conf: 'High' }],
  parts: {
    frame: { what: 'A high frame on four wheels with room for cargo underneath.', size: 'not published', src: ['astrolab'], conf: 'Low' },
    decks: { what: 'Two top-deck payload interfaces carry up to 2,000 kg together.', size: '2,000 kg', src: ['astrolab'], conf: 'High' },
    bay: { what: 'The underslung payload interface between the wheels: the rover drives over cargo and lifts it.', size: 'up to 3 m³', src: ['astrolab'], conf: 'High' },
    arm: { what: 'A six-axis robotic arm with modular end effectors.', size: '6 axes', src: ['astrolab'], conf: 'High' },
    mast: { what: 'A gimballing antenna for high-bandwidth links to Earth, and sensors for lining up cargo.', size: 'not published', src: ['astrolab'], conf: 'High' },
    warmbox: { what: 'Battery and avionics; their size and place are not published.', size: 'not published', src: ['assumed'], conf: 'Low' },
    wheels: { what: 'Four wheels on flexible airless tyres.', size: '4 wheels', src: ['nasaOct26'], conf: 'High' },
  },
};

export function build(mats, opts) {
  const b = builder(mats, opts), L = 4.2, W = 2.8, d = 1.0, top = 1.9;
  const fr = b.part('frame', 'Frame', { distance: 0, representative: true });
  boxShell(b, fr, { hx: W / 2 - 0.3, hz: L / 2 - 0.2, y0: top - 0.35, y1: top, mat: 'white_paint' });
  for (const x of [-1, 1]) for (const z of [-1, 1]) b.mesh(fr, strut(V3(x * (W / 2 - 0.4), top - 0.35, z * (L / 2 - 0.4)), V3(x * (W / 2 - 0.15), d / 2, z * 1.35), 0.07), 'aluminium');
  const dk = b.part('decks', 'Top-deck payload interfaces (2)', { axis: V3(0, 1, 0), distance: 0.9 });
  for (const z of [-0.85, 0.85]) b.mesh(dk, new THREE.BoxGeometry(1.5, 0.5, 1.2), 'mli_gold', { cut: true, capColor: '#d9b867', pos: V3(0, top + 0.25, z) });
  const bay = b.part('bay', 'Underslung payload bay (3 m³)', { axis: V3(0, -1, 0), distance: 0.6 });
  b.mesh(bay, new THREE.BoxGeometry(1.6, 0.75, 2.5), 'mli_silver', { cut: true, capColor: '#b8c0c9', pos: V3(0, top - 0.35 - 0.45, 0) });   // 1.6 × 0.75 × 2.5 = 3 m³
  const wb = b.part('warmbox', 'Warm box: battery and avionics', { axis: V3(0, 1, 1), distance: 0.6, representative: true });
  b.mesh(wb, new THREE.BoxGeometry(1.2, 0.22, 0.5), 'radiator', { cut: true, capColor: '#7f9ab8', pos: V3(0, top - 0.17, L / 2 - 0.5) });
  const arm = b.part('arm', 'Six-axis robotic arm', { axis: V3(1, 0, 0), distance: 0.8 });
  const a0 = V3(W / 2 - 0.45, top + 0.05, -L / 2 + 0.45), a1 = a0.clone().add(V3(0.1, 0.9, 0.3)), a2 = a1.clone().add(V3(-0.2, -0.2, 0.8)), a3 = a2.clone().add(V3(-0.3, -0.5, 0.1));
  for (const [p, q, r] of [[a0, a1, 0.07], [a1, a2, 0.06], [a2, a3, 0.05]]) b.mesh(arm, strut(p, q, r), 'aluminium');
  const m = b.part('mast', 'Gimballing antenna and sensors', { axis: V3(0, 1, 0), distance: 0.6 });
  mast(b, m, V3(-W / 2 + 0.45, top, L / 2 - 0.45), top + 0.7, { dish: 0.3 });
  wheels(b, { d, w: 0.3, track: W - 0.1, base: 2.7, label: 'Wheel, flexible airless tyre' });
  b.flow('cargo', [V3(0, top + 0.6, 0.85), V3(W / 2 + 0.4, top + 0.6, 0.85), V3(W / 2 + 0.6, 0.3, 0.85)]);
  b.flow('cargo', [V3(0, 0.3, L / 2 + 1.2), V3(0, 0.6, 0.6), V3(0, top - 0.8, 0)]);
  return b.finish({ id: 'flex' });
}
