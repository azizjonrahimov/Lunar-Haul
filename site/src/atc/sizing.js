// /atc/ section 3 (F-72: split from main.js and loaded when the section comes near, for the page's script budget):
// what Lunar ATC puts inside each vehicle, from B-81's sizing (E48) and B-105's per-robot timing and measured memory.
import { h } from '../ui/index.js';
import { upgradeFlags } from '../ui/tooltip.js';
import { num, esc, fmt } from '../components/num.js';
import { robotRound } from './e48-robot.js';
import { sizingHtml, sm } from './sizing-note.js';   // F-81: section 3's text, pure so a test reads it as rendered

const BASE = import.meta.env.BASE_URL, $ = id => document.getElementById(id);

// ---------- 3. Inside each vehicle: B-81's sizing (E48, results/E48_sizing.json), placeholders until it loads ----------
const SZ = 'results/E48_sizing.json';
const CLASSES = [   // [column, 3D viewer id, E48 class]
  ['Phase 1 LTV', 'clv1', 'LTV1'], ['Cargo LTV (FLEX, Eagle)', 'flex', 'CARGO'], ['Small rover (VIPER, MAPP)', 'viper', 'SMALL'], ['Hopper', 'moonfall', 'HOPPER'], ['Lander', 'MK1', null], ['Base computer', 'atc_computer', 'BASE'],
];
// software parts and failure behaviour are the design; every measured or derived value comes from E48
const ROWS = [
  ['Software parts', c => c === 'Base computer' ? 'job market (leader), ledger, failover to board B' : c === 'Lander' ? 'safety program (landing closures), radio unit' : 'safety program, planner, radio unit', 'design'],
  ['Computing per safety check', 'cpu', 'measured'],
  ['Computing per market round (the simulator’s whole-fleet call, not one robot’s bid)', 'auction', 'measured'],
  ['Memory of the on-robot parts (planner, checks, reservations, ledger copy, bid policy)', 'mem', 'measured'],
  ['Radio at the worst 5 km hop (flat ground)', 'link', 'derived'],
  ['Radio at the worst hop over a curved Moon (ITU-R P.526)', 'sph', 'derived'],
  ['Messages per robot-hour', 'msgs', 'measured'],
  ['Power', 'power', 'assumed'],
  ['If it fails', c => c === 'Base computer' ? 'board B takes over; if both fail, the robots elect a leader' : 'stops at the next safe point; others treat its last reservation as occupied, and after the timeout its segment is marked unconfirmed and entered only at caution speed', 'design'],
];
function cell(S, key, k) {
  const C = S.classes[k], p = `classes.${k}`, F = S.flight, hz = S.targets.safety_hz;
  if (key === 'cpu') {
    const t = C.cpu_safety_check_us, base = k === 'BASE', share = x => t.p99 * x * hz / 1e6;
    return `${sm(t.p99, ' µs', 0, `${p}.cpu_safety_check_us.p99`)} on the laptop (p99${base ? `, the reservation check over ${fmt(t.entries, 0)} entries` : ''}); ` +
      (base ? `${sm(t.p99 * F.factor / 1e3, ' ms', 1, `${p}.cpu_safety_check_us.p99 × flight.factor`)} on the flight core`
        : `${sm(share(F.factor), '', 2, `${p}.cpu_safety_check_us.p99 × flight.factor × targets.safety_hz / 1e6`)} of a flight core at ${fmt(hz, 0)} Hz (${fmt(share(F.factor_range[0]), 2)}–${fmt(share(F.factor_range[1]), 2)})`);
  }
  if (key === 'auction') { const a = C.cpu_auction_round_ms; return `median ${sm(a.median, ' ms', 1, `${p}.cpu_auction_round_ms.median`)}, p99 ${sm(a.p99, ' ms', 1, `${p}.cpu_auction_round_ms.p99`)} (laptop)`; }
  if (key === 'mem' && k !== 'BASE' && robotRound(S)) {   // F-72 (B-105): measured on one robot's view; the estimate beside it
    const R = robotRound(S);
    return `${R.mem} measured on the laptop (Python's allocations; interpreter and code not counted), against an estimate of ${R.estimate}, of ${num({ value: F.memory_mb, unit: ' MB', digits: 0, flag: 'Spec', source: `${SZ}: flight.memory_mb (${F.processor})` })}`;
  }
  if (key === 'mem') return `about ${sm(C.peak_memory_mb, ' MB', 2, `${p}.peak_memory_mb (an estimate: the sum of the parts, not a measurement)`)} by an estimate (not measured), of ${num({ value: F.memory_mb, unit: ' MB', digits: 0, flag: 'Spec', source: `${SZ}: flight.memory_mb (${F.processor})` })}`;
  if (key === 'sph') {   // F-70b (B-104): the same worst hop over a spherical Moon, beside the flat-ground row
    const R = S.revision_b104?.per_class?.[k]; if (!R) return '–';
    const W = R.worst_hop, src = `revision_b104.per_class.${k}.worst_hop`;
    const r = W.kbps.spherical_ground, db = W.spherical_minus_flat_db;   // one decimal where rounding would hide it (4.9 kbit/s, 5.73 dB)
    return `${sm(r, ' kbit/s', r < 100 ? 1 : 0, `${src}.kbps.spherical_ground`)} at ${fmt(W.d_m / 1e3, 1)} km, ${sm(db, ' dB', Number.isInteger(db) ? 0 : 1, `${src}.spherical_minus_flat_db`)} more loss than on flat ground`;
  }
  if (key === 'link') {
    const L = C.link, ant = `${fmt(L.antenna_m, L.antenna_m % 1 ? 1 : 0)} m antenna, ${fmt(L.tx_power_w, L.tx_power_w % 1 ? 2 : 0)} W`;
    // F-67 (B-89): flat-ground law with the smooth-Moon horizon check; two 1 m antennas cannot see each other at 5 km
    const rate = L.beyond_horizon_at_worst_hop
      ? `beyond the ${sm(L.mutual_horizon_m / 1e3, ' km', 1, `${p}.link.mutual_horizon_m`)} horizon at ${fmt(L.worst_hop_m / 1e3, 0)} km; ${sm(L.longest_hop_kbps, ' kbit/s', 1, `${p}.link.longest_hop_kbps`)} at ${sm(L.longest_hop_m, ' m', 0, `${p}.link.longest_hop_m`)}`
      : sm(L.worst_hop_kbps / 1e3, ' Mbit/s', 1, `${p}.link.worst_hop_kbps`);
    return `${rate} (${ant})` + (k === 'BASE' ? '' : `; the mast in direct view at ${sm(L.reachable_share * 100, ' %', 0, `${p}.link.reachable_share`)} of route points`);
  }
  if (key === 'msgs') {
    if (k === 'BASE') return `receives the fleet's: ${sm(S.h10.link_kbps_needed_20_robots_secured_mac8, ' kbit/s', 2, 'h10.link_kbps_needed_20_robots_secured_mac8')} for ${fmt(S.targets.robots, 0)} robots`;
    const by = S.messages.per_robot_hour_by_type['1'];
    return `${sm(S.messages.per_robot_hour['1'], '', 0, 'messages.per_robot_hour.1')}: status once a second, ${sm(by['auction (bid, award, claim)'], '', 2, 'messages.per_robot_hour_by_type.1')} for the market`;
  }
  if (key === 'power') return num({ value: C.power_w.value, unit: ' W', digits: 0, flag: C.power_w.flag, source: `${SZ}: ${p}.power_w` });
}
function insideTable(S) {
  const head = h('tr', {}, h('th', { scope: 'col' }, 'What'), ...CLASSES.map(([c, id]) => h('th', { scope: 'col' }, c, h('br'), h('a', { class: 'small', href: `${BASE}vehicles/?v=${id}&atc=1${id === 'atc_computer' ? '&view=cutaway' : ''}` }, 'see it in 3D'))));
  const rows = ROWS.map(([label, fn, kind]) => h('tr', {}, h('th', { scope: 'row' }, label), ...CLASSES.map(([c, , k]) => typeof fn === 'function'
    ? h('td', {}, fn(c), ' ', h('span', { class: 'atc-tag atc-design' }, 'our design'))
    : S && k ? h('td', { html: cell(S, fn, k) })
      : h('td', { class: 'atc-pending' }, S ? 'not sized (E48 sized the robots and the base)' : [h('span', { class: 'atc-tag' }, `B-81 · ${kind}`), h('span', { class: 'visually-hidden' }, ' not measured yet')]))));
  $('atc-inside').replaceChildren(h('table', { class: 'atc-table atc-inside-t' }, h('caption', { class: 'visually-hidden' }, 'What Lunar ATC adds to each kind of vehicle; the radio row uses the flat-ground law (free space, then two-ray) with the smooth-Moon horizon'), h('thead', {}, head), h('tbody', {}, rows)),
    S ? null : h('p', { class: 'small muted' }, 'Tags: "our design" is how Lunar ATC is built; "B-81 · measured / derived / assumed" marks a value still to come.'));
  if (S) { sizingNote(S); upgradeFlags($('atc-inside')); }
}
// what the numbers add up to, against the targets written before the measurement (P3's H10)
function sizingNote(S) {
  $('atc-sizing').innerHTML = sizingHtml(S);
  upgradeFlags($('atc-sizing'));
}

export function mount() {
  insideTable(null);
  fetch(BASE + 'atc/E48_sizing.json').then(r => (r.ok && /json/.test(r.headers.get('content-type') || '') ? r.json() : null)).then(S => S && insideTable(S)).catch(() => {});
}
