// /protocol/ data staged at build time (prepare-data). E50 (B-90) trace for figure 1: results/E50_trace.json
// (lunarsim-e50-trace v1: one month at 1x, seed 1, the two vehicles that drove most; per layer set err_m and b95_m,
// the maximum over each 30 min bin) reduced to what the figure draws: per vehicle the hours driven, a 0/1 string of
// the bins in which it moved (its position changed before the next bin) and, per layer set, err_m and b95_m.
// Layer sets whose two series equal another set's are marked same_as (in 2028 the satellite layer adds nothing).
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { ROOT } from './pages.mjs';
import { lripDecode } from '../src/protocol/lrip.js';
import { num } from '../src/components/num.js';
export { lripDecode };

export const E50_SRC = 'results/E50_trace.json';
export const E50_OUT = 'protocol/e50-trace.json';
export const E50_SETS = ['dr', 'dr+ranging', 'dr+ranging+fixes', 'dr+ranging+fixes+lans', 'lans@2030'];

export function compactE50(doc) {
  if (doc.format !== 'lunarsim-e50-trace' || doc.version !== 1) throw new Error(`${E50_SRC}: format ${doc.format} version ${doc.version}`);
  const vehicles = {};
  for (const [id, v] of Object.entries(doc.vehicles)) {
    const n = v.xy_m.length, sets = {};
    for (const k of E50_SETS) {
      const s = v.sets[k];
      if (!s) throw new Error(`${E50_SRC}: vehicle ${id} has no layer set ${k}`);
      if (s.err_m.length !== n || s.b95_m.length !== n) throw new Error(`${E50_SRC}: vehicle ${id} ${k}: ${s.err_m.length} / ${s.b95_m.length} bins, positions ${n}`);
      sets[k] = { err_m: s.err_m, b95_m: s.b95_m };
    }
    for (let i = 1; i < E50_SETS.length; i++) {
      const a = sets[E50_SETS[i]], same = E50_SETS.slice(0, i).find(k => !sets[k].same_as && JSON.stringify([sets[k].err_m, sets[k].b95_m]) === JSON.stringify([a.err_m, a.b95_m]));
      if (same) sets[E50_SETS[i]] = { same_as: same };
    }
    const moving = v.xy_m.map((p, i) => (i + 1 < n && (p[0] !== v.xy_m[i + 1][0] || p[1] !== v.xy_m[i + 1][1]) ? '1' : '0')).join('');
    vehicles[id] = { drive_h: v.drive_h, bins: n, moving, sets };
  }
  return { format: 'lunarsim-e50-trace-site', version: 1, source: E50_SRC, experiment: doc.experiment, mult: doc.mult, seed: doc.seed,
    t0_h: doc.t0_h, bin_min: doc.bin_min, budget_m: doc.budget_m, sets: E50_SETS, vehicles };
}

export function stageE50(PUB) {
  const src = join(ROOT, E50_SRC);
  if (!existsSync(src)) { console.log(`prepare-data: ${E50_SRC} missing; /protocol/ figure 1 says so`); return null; }
  const out = compactE50(JSON.parse(readFileSync(src, 'utf8')));
  mkdirSync(join(PUB, 'protocol'), { recursive: true });
  const text = JSON.stringify(out);
  writeFileSync(join(PUB, E50_OUT), text);
  console.log(`prepare-data: ${E50_OUT} staged (${Math.round(text.length / 1024)} kB, ${Object.keys(out.vehicles).length} vehicles)`);
  return out;
}

// F-56 / B-93: /protocol/ figure 5 shows a real LRIP v0.1 POSITION report: the golden vector POSITION / profile N /
// mac8 of data/atc/lrip/conformance-v0.1.json, laid out by lunarsim/schemas/lrip-v0.1.json (Space Packet primary
// header, LRIP header, the message's fields, the security header, the 8-byte MAC). The other POSITION vectors give
// the sizes without authentication and on the broadband profile.
export const LRIP_SCHEMA = 'lunarsim/schemas/lrip-v0.1.json';
export const LRIP_GOLDEN = 'data/atc/lrip/conformance-v0.1.json';
export const LRIP_OUT = 'protocol/lrip-position.json';

export function lripLayout(schema, message = 'POSITION', trailer = 'mac8') {
  const fr = schema.framing, msg = schema.messages.find(m => m.name === message);
  if (!msg) throw new Error(`${LRIP_SCHEMA}: no message ${message}`);
  const F = [];
  for (const [name, bits] of fr.space_packet.fields) F.push({ part: 'head', name, bits });
  for (const [name, bits] of fr.lrip_header.fields) F.push({ part: 'lrip', name, bits, ...(name === 't_valid' ? { scale: fr.lrip_header.t_valid_unit_s, unit: 's' } : {}) });
  for (const [name, type, bits, scale, unit] of msg.fields) F.push({ part: 'pay', name, bits, type, scale, unit: unit.split(' ')[0], note: unit, ...(type.startsWith('enum:') ? { enum: schema.enums[type.slice(5)] } : {}) });
  for (const [name, bits] of fr.security_header.fields) F.push({ part: 'sec', name, bits });
  F.push({ part: 'mac', name: trailer, bits: 8 * fr.trailer[trailer] });
  return { message: msg.name, id: msg.id, fields: F, bits: F.reduce((a, f) => a + f.bits, 0) };
}

export function compactLrip(schema, golden) {
  const pos = golden.vectors.filter(v => v.message === 'POSITION');
  const main = pos.find(v => v.profile === 'N' && v.auth === 'mac8');
  if (!main) throw new Error(`${LRIP_GOLDEN}: no POSITION vector for profile N with mac8`);
  const layout = lripLayout(schema);
  lripDecode(main.hex, layout);   // throws if the sizes disagree
  return { format: 'lunarsim-lrip-figure', version: 1, source: LRIP_GOLDEN, schema: LRIP_SCHEMA, layout,
    vector: { hex: main.hex, bytes: main.bytes, sender: main.sender, seq: main.seq, t_valid_s: main.t_valid_s, fields: main.fields },
    sizes: pos.map(v => ({ profile: v.profile, auth: v.auth, bytes: v.bytes })) };
}

export function stageLrip(PUB) {
  const s = join(ROOT, LRIP_SCHEMA), g = join(ROOT, LRIP_GOLDEN);
  if (!existsSync(s) || !existsSync(g)) { console.log(`prepare-data: ${LRIP_GOLDEN} or the schema missing; /protocol/ figure 5 says so`); return null; }
  const out = compactLrip(JSON.parse(readFileSync(s, 'utf8')), JSON.parse(readFileSync(g, 'utf8')));
  mkdirSync(join(PUB, 'protocol'), { recursive: true });
  writeFileSync(join(PUB, LRIP_OUT), JSON.stringify(out));
  console.log(`prepare-data: ${LRIP_OUT} staged (${out.vector.bytes}-byte POSITION report, ${out.layout.fields.length} fields)`);
  return out;
}

// F-56 / B-91: /protocol/ figure 3 reads E51 (results/E51_clocks.json): per oscillator class and resync interval on
// the lunar time scale, over 30 seeds, the measured one-way and two-way ranging error, the largest clock offset and
// the reservation conflicts at each guard; with H11's rule and verdict.
export const E51_SRC = 'results/E51_clocks.json';
export const E51_OUT = 'protocol/e51.json';
const E51_KEEP = ['sync_fail_share', 'one_way_m_median', 'one_way_m_p95', 'two_way_single_sided_m_p95', 'max_abs_clock_s',
  'conflicts_guard_0.01', 'conflicts_guard_0.1', 'conflicts_guard_1', 'conflict_pairs_checked'];
export function compactE51(doc) {
  if (!Array.isArray(doc.rows) || !doc.h11) throw new Error(`${E51_SRC}: no rows or no h11`);
  const rows = doc.rows.filter(r => r.scale === 'lunar' && (r.class === 'crystal' || r.class === 'csac'))
    .map(r => ({ class: r.class, interval_s: r.interval_s, seeds: r.seeds, ...Object.fromEntries(E51_KEEP.map(k => [k, r[k]])) }));
  if (!rows.length) throw new Error(`${E51_SRC}: no lunar rows for crystal or csac`);
  return { format: 'lunarsim-e51-site', version: 1, source: E51_SRC, experiment: doc.experiment, guard_s: doc.constants?.guard_s,
    uwb_sigma_m: doc.design?.uwb_sigma_m, contact_share: doc.contact_share_mean, h11: doc.h11, rows };
}
export function stageE51(PUB) {
  const src = join(ROOT, E51_SRC);
  if (!existsSync(src)) { console.log(`prepare-data: ${E51_SRC} missing; /protocol/ figure 3 says so`); return null; }
  const out = compactE51(JSON.parse(readFileSync(src, 'utf8').replace(/\bNaN\b/g, 'null')));
  mkdirSync(join(PUB, 'protocol'), { recursive: true });
  writeFileSync(join(PUB, E51_OUT), JSON.stringify(out));
  console.log(`prepare-data: ${E51_OUT} staged (${out.rows.length} rows)`);
  return out;
}

// F-56 / B-93: E53 (results/E53_table.csv) numbers in /protocol/ problem 5's text, at build time:
// <!--@e53:geometry:auth:position_hz:rovers:column--> gives a flagged number; a fits_* column gives "fits" or "does not fit".
export const E53_SRC = 'results/E53_table.csv';
let e53rows = null;
const E53_UNIT = { one_hop_sum_kbps: [' kbit/s', 1], busiest_link_kbps_p95: [' kbit/s', 1], busiest_link_kbps_mean: [' kbit/s', 1], per_rover_kbps: [' kbit/s', 2], mean_hops_to_base: ['', 1], reachable_share: [' %', 0, 100] };
export function e53(geometry, auth, hz, rovers, column) {
  if (!e53rows) {
    const [head, ...lines] = readFileSync(join(ROOT, E53_SRC), 'utf8').trim().split(/\r?\n/);
    const keys = head.split(',');
    e53rows = lines.map(l => Object.fromEntries(l.split(',').map((v, i) => [keys[i], v])));
  }
  const hit = e53rows.filter(r => r.geometry === geometry && r.auth === auth && +r.position_hz === +hz && +r.rovers === +rovers);
  if (hit.length !== 1) throw new Error(`${E53_SRC}: ${hit.length} rows for ${geometry} ${auth} ${hz} Hz ${rovers} rovers`);
  const v = hit[0][column];
  if (v === undefined) throw new Error(`${E53_SRC}: no column ${column}`);
  if (column.startsWith('fits_')) { if (v !== 'True' && v !== 'False') throw new Error(`${E53_SRC}: ${column} = ${v}`); return v === 'True' ? 'fits' : 'does not fit'; }
  const [unit, digits, scale = 1] = E53_UNIT[column] || ['', 2];
  return num({ value: +v * scale, unit, digits, flag: 'Modelled', source: `${E53_SRC}: geometry ${geometry}, authentication ${auth}, ${hz} Hz, ${rovers} rovers, column ${column}` });
}
