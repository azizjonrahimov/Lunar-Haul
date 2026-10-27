// Astrolab CLV-1 (F-51), NASA's Phase 1 LTV adapted from FLEX: about 907 kg, two crew seats, a compact stowed form,
// faster than 9.7 km/h on level ground. Its dimensions and layout are unpublished, so the body follows the schematic
// LTV recipe of the research notes (warm box low in the centre, mast at the front, solar on the sides).
import * as THREE from 'three';
import { builder, strut, V3 } from '../parts.js';
import { wheels, boxShell, seat, mast, panel } from './kit-common.js';

export const kit = {
  story: {
    whole: 'Astrolab’s CLV-1, one of NASA’s two Phase 1 lunar terrain vehicles (May 2026): about 907 kg, two crew seats, faster than 9.7 km/h on level ground, 10 km on a charge. Its size is unpublished, so the body here is schematic.',
    cutaway: 'Cut level with the warm box: battery and avionics sit low in the centre, insulated, for a low centre of mass and warmth through the night.',
    exploded: 'Deck, seats, mast, arm and wheels apart; every part except the seats and wheels is a schematic placement.',
  },
  cut: { dir: 'down', at: 0.32 }, shell: ['chassis'], atc: 'warmbox',
  dims: [{ label: 'Length', text: 'about 4 m as drawn', axis: 'z', src: ['assumed'], conf: 'Low' }],
  parts: {
    chassis: { what: 'The deck and frame, adapted from Astrolab’s FLEX cargo rover; folds compact for the lander.', size: '~907 kg vehicle', src: ['nasaMay26'], conf: 'Low' },
    warmbox: { what: 'Battery and avionics in an insulated warm box low in the centre.', size: 'kWh unpublished; 10 km a charge', src: ['nasaOct26', 'viper'], conf: 'Low' },
    seats: { what: 'Two seats for suited crew; it can also drive itself or be driven from Earth.', size: '2 seats', src: ['nasaMay26'], conf: 'High' },
    mast: { what: 'Cameras and a gimballed antenna on a mast at the front.', size: '~2-2.3 m (VIPER pattern)', src: ['astrolab', 'viper'], conf: 'Low' },
    arm: { what: 'A robotic arm on a deck corner, as on FLEX; whether CLV-1 keeps it is not stated.', size: '6 axes on FLEX', src: ['astrolab'], conf: 'Low' },
    solar: { what: 'Solar panels on the sides catch the low polar sun.', size: 'not published', src: ['assumed'], conf: 'Low' },
    wheels: { what: 'Four wheels on flexible airless tyres, the tyres FLIP flies first.', size: '4 wheels', src: ['nasaOct26'], conf: 'High' },
  },
};

export function build(mats, opts) {
  const b = builder(mats, opts), L = 4.0, W = 2.2, d = 0.85, deckY = 1.0;
  const ch = b.part('chassis', 'Deck and frame', { distance: 0, representative: true });
  boxShell(b, ch, { hx: W / 2 - 0.35, hz: L / 2 - 0.25, y0: deckY - 0.4, y1: deckY, mat: 'white_paint' });
  const wb = b.part('warmbox', 'Warm box: battery and avionics', { axis: V3(0, -1, 0), distance: 0.9, representative: true });
  b.mesh(wb, new THREE.BoxGeometry(0.9, 0.28, 1.2), 'mli_gold', { cut: true, capColor: '#d9b867', pos: V3(0, deckY - 0.22, -0.2) });
  const st = b.part('seats', 'Crew seats', { axis: V3(0, 1, 0), distance: 0.8 });
  for (const x of [-0.45, 0.45]) seat(b, st, V3(x, deckY + 0.05, -0.2));
  const m = b.part('mast', 'Mast: cameras and antenna', { axis: V3(0, 1, 0), distance: 0.7, representative: true });
  mast(b, m, V3(0.55, deckY, L / 2 - 0.45), 2.1);
  const arm = b.part('arm', 'Robotic arm (as on FLEX)', { axis: V3(0, 0, 1), distance: 0.8, representative: true });
  const s0 = V3(-0.6, deckY + 0.05, L / 2 - 0.5), s1 = V3(-0.6, deckY + 0.6, L / 2 - 0.2), s2 = V3(-0.3, deckY + 0.35, L / 2 + 0.05);
  b.mesh(arm, strut(s0, s1, 0.05), 'aluminium'); b.mesh(arm, strut(s1, s2, 0.04), 'aluminium');
  const sol = b.part('solar', 'Side solar panels', { axis: V3(1, 0, 0), distance: 0.6, representative: true });
  for (const x of [-1, 1]) panel(b, sol, V3(x * (W / 2 - 0.3), deckY - 0.2, -L / 2 + 0.9), 1.1, 0.35);
  wheels(b, { d, w: 0.25, track: W - 0.2, base: 2.6, label: 'Wheel, flexible airless tyre' });
  b.flow('power', [V3(W / 2 - 0.3, deckY - 0.2, -1.1), V3(0.3, deckY - 0.25, -0.5), V3(0, deckY - 0.22, -0.2)]);
  b.flow('cargo', [V3(0, deckY + 0.3, -1.3), V3(0, deckY + 0.6, -L / 2 - 0.4), V3(0, 0.2, -L / 2 - 1)]);
  return b.finish({ id: 'clv1' });
}
