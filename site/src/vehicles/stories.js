// Narrative text per vehicle and mode for /vehicles/. Numbers are never typed here: {{path}} looks the value up in the
// catalogue for the current vehicle ({{ID:path}} for another one) and renders it through components/num.js with its
// flag and source. Modifiers: |t (kg to tonnes), |kN (N to kN), |0 |1 |2 (decimals).
import { num, esc } from '../components/num.js';

export function render(text, catalog, id) {
  return text.replace(/\{\{([\w]+:)?([\w.]+)((?:\|[\w]+)*)\}\}/g, (_, other, path, mods) => {
    const ms = mods.split('|').filter(Boolean), opts = { digits: 1 };
    for (const m of ms) {
      if (m === 't') Object.assign(opts, { scale: 1e-3, unit: 't' });
      else if (m === 'kN') Object.assign(opts, { scale: 1e-3, unit: 'kN', digits: 0 });
      else if (/^\d$/.test(m)) opts.digits = +m;
    }
    return num(catalog.q(other ? other.slice(0, -1) : id, path, opts));
  });
}
export const para = s => `<p>${s}</p>`;

const LANDER_CUT = 'The cut shows the propellant tanks as solid sections inside the hull. Follow Propellant to trace the feed lines to the engine.';
const ROVER_CUT = 'The cut opens the body to show the battery and avionics box, the part that decides how far it drives between charges. Follow Power to trace the cables.';
const BASE_CUT = 'The cut shows the wall as a solid section.';

export const STORIES = {
  CLPS: {
    whole: 'A commercial lander of the Nova-C class: {{dims.height_m|2}} tall, six legs spanning {{dims.leg_span_m}}. It brings {{capacity_kg|0}} of cargo at most to the surface.',
    cutaway: LANDER_CUT,
    exploded: 'Six legs, a hexagonal body wrapped in silver insulation, two tanks and one methane-oxygen engine.',
  },
  MK1: {
    whole: 'A Blue Moon MK1-class lander, {{dims.height_m|2}} tall and {{dims.diameter_m|2}} across, landing about {{capacity_kg|t}} of cargo. Its legs are a representative shape: the real ones are unpublished.',
    cutaway: 'Liquid hydrogen fills the large upper tank and liquid oxygen the lower one. The BE-7 engine burns them with a nearly invisible flame, up to {{gate.t_max_n|kN}}.',
    exploded: 'Tanks up, engine down, legs out: the parts of a single-stage cargo lander.',
  },
  LARGE: {
    whole: 'A Starship HLS-class cargo lander: {{dims.height_m|0}} tall and {{dims.diameter_m|0}} across, carrying up to {{capacity_kg|t}}. Cargo comes down to the ground on an elevator.',
    cutaway: 'Two huge steel tanks fill most of the hull. Near the ground it lands on thrusters high on the body, which keeps the main engines’ blast off the surface.',
    exploded: 'The tanks rise out of the hull; the legs, the elevator and the landing thrusters move clear.',
  },
  LTV: {
    whole: 'A lunar terrain vehicle of the CLV-1 class: {{dims.length_m|1}} long on four {{dims.wheel_d_m|2}} wheels. It carries {{capacity_kg|t}} at {{speed_kmh|0}} and parks through the lunar night.',
    cutaway: ROVER_CUT,
    exploded: 'Four wheels with crab-steer pivots, a deck, a solar panel and a small arm.',
  },
  HAUL: {
    whole: 'The heavy hauler is our concept, with no built counterpart: a flat bed on six {{dims.wheel_d_m|1}} wheels, carrying {{capacity_kg|t}} and working through the night on batteries and radiators.',
    cutaway: ROVER_CUT,
    exploded: 'Six big wheels, the bed with pallet rails, the night-power pack and the radiators that shed its heat.',
  },
  MICRO: {
    whole: 'A small VIPER-scale rover, {{dims.height_m|1}} tall on four {{dims.wheel_d_m|1}} wheels: it carries {{capacity_kg|0}} at {{speed_kmh|0}}.',
    cutaway: ROVER_CUT,
    exploded: 'Four wheels with grousers, a body, vertical solar panels for the low sun, and a mast with lights.',
  },
  habitat: { whole: 'A habitat module, {{dims.length_m|1}} long and {{dims.diameter_m|1}} across.', cutaway: BASE_CUT + ' Inside: the floor deck.', exploded: 'Shell, floor, radiators, legs and airlock.' },
  pad: { whole: 'A landing pad {{dims.diameter_m|0}} across, ringed by a berm {{dims.berm_height_m|1}} high that catches the blasted dust.', cutaway: BASE_CUT, exploded: 'The berm lifts away from the sintered surface.' },
  solar_tower: { whole: 'A solar tower {{dims.height_m|0}} tall: at the pole the sun stays near the horizon, so the array stands upright.', cutaway: BASE_CUT, exploded: 'Mast and array.' },
  comms_mast: { whole: 'A communications mast {{dims.height_m|0}} tall, with a dish for Earth and a panel for the local link.', cutaway: BASE_CUT, exploded: 'Tower, dish and panel.' },
  cargo_pallet: { whole: 'A standard cargo pallet, {{dims.length_m|1}} by {{dims.width_m|1}}: the unit every lander and rover moves.', cutaway: BASE_CUT, exploded: 'One pallet.' },
};

// stat chips per vehicle: [label, path, opts] or [label, {text, flagFrom: path}] for worded values
export const CHIPS = {
  lander: [['Height', 'dims.height_m', { digits: 2 }], ['Carries', 'capacity_kg', { scale: 1e-3, unit: 't' }], ['Max thrust', 'gate.t_max_n', { scale: 1e-3, unit: 'kN', digits: 0 }, 'warm']],
  rover: [['Carries', 'capacity_kg', { scale: 1e-3, unit: 't' }], ['Speed', 'speed_kmh', { digits: 0 }, 'cool'], ['Night', { night: 'night_ops' }]],
  base: [],
};
export const nightText = v => v ? 'drives in the dark' : 'parks in the dark';
export { esc };
