// /protocol/ data staged at build time (prepare-data) and read for the page text: LRIP (figure 5), E51 (figure 3), E52
// (figure 2), E53 (problem 5's text), E54 (problems 4 and 6), E55 (problem 7) and B-99's figure files (checkB99, stageB99).
import { readFileSync, writeFileSync, mkdirSync, existsSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { ROOT } from './pages.mjs';
import { lripDecode } from '../src/protocol/lrip.js';
import { num, fmt } from '../src/components/num.js';
import { dateNum } from '../src/components/date-num.js';
export { lripDecode };

// F-56 / B-93, F-73 / B-100: /protocol/ figure 5 shows a real LRIP POSITION report: the golden vector POSITION / profile N /
// mac8 of the current conformance file (v0.2), laid out by its schema (Space Packet primary header, LRIP header, the
// message's fields, the security header, the 8-byte MAC). The other POSITION vectors give the sizes without
// authentication and on the broadband profile. v0.1's vector is decoded by v0.1's layout too ("v0.1 stays decodable").
// Conformance vectors test the codec, not a radio.
export const LRIP_SCHEMA = 'lunarsim/schemas/lrip-v0.2.json';
export const LRIP_GOLDEN = 'data/atc/lrip/conformance-v0.2.json';
export const LRIP_SCHEMA_V1 = 'lunarsim/schemas/lrip-v0.1.json';
export const LRIP_GOLDEN_V1 = 'data/atc/lrip/conformance-v0.1.json';
export const LRIP_OUT = 'protocol/lrip-position.json';

// a log-coded field (v0.2's u95_code): "u95 = 0.05 m x 2^(code/4) … 62: above 1.95 km; 63 unknown", read from the schema
export function logCode(note) {
  const m = /=\s*([\d.]+)\s*m\s*x\s*2\^\(code\/(\d+)\)/.exec(note || '');
  if (!m) return null;
  const above = /(\d+):\s*above\s+([^;]+)/.exec(note), unknown = /(\d+)\s+unknown/.exec(note);
  return { base: +m[1], div: +m[2], above: above ? +above[1] : null, aboveText: above ? above[2].trim() : null, unknown: unknown ? +unknown[1] : null };
}
export function lripLayout(schema, message = 'POSITION', trailer = 'mac8', src = LRIP_SCHEMA) {
  const fr = schema.framing, msg = schema.messages.find(m => m.name === message);
  if (!msg) throw new Error(`${src}: no message ${message}`);
  const F = [];
  for (const [name, bits] of fr.space_packet.fields) F.push({ part: 'head', name, bits });
  for (const [name, bits] of fr.lrip_header.fields) F.push({ part: 'lrip', name, bits, ...(name === 't_valid' ? { scale: fr.lrip_header.t_valid_unit_s, unit: 's' } : {}) });
  for (const [name, type, bits, scale, unit, meta] of msg.fields) {
    const log = logCode(unit);
    F.push({ part: 'pay', name, bits, type, scale, unit: log ? 'm' : unit.split(' ')[0], note: unit, ...(log ? { log } : {}), ...(meta?.since ? { since: meta.since } : {}),
      ...(type.startsWith('enum:') ? { enum: schema.enums[type.slice(5)] } : {}) });
  }
  for (const [name, bits] of fr.security_header.fields) F.push({ part: 'sec', name, bits });
  F.push({ part: 'mac', name: trailer, bits: 8 * fr.trailer[trailer] });
  return { message: msg.name, id: msg.id, fields: F, bits: F.reduce((a, f) => a + f.bits, 0) };
}
const vec = (golden, message, src) => {
  const v = golden.vectors.find(x => x.message === message && x.profile === 'N' && x.auth === 'mac8');
  if (!v) throw new Error(`${src}: no ${message} vector for profile N with mac8`);
  return v;
};
export function compactLrip(schema, golden, schemaV1 = null, goldenV1 = null) {
  const pos = golden.vectors.filter(v => v.message === 'POSITION');
  const main = vec(golden, 'POSITION', LRIP_GOLDEN), layout = lripLayout(schema);
  lripDecode(main.hex, layout);   // throws if the sizes disagree
  const hello = vec(golden, 'HELLO', LRIP_GOLDEN), helloLayout = lripLayout(schema, 'HELLO');
  lripDecode(hello.hex, helloLayout);
  let previous = null;
  if (schemaV1 && goldenV1) {   // v0.1 stays decodable: its own POSITION and HELLO vectors by its own layouts
    const p1 = vec(goldenV1, 'POSITION', LRIP_GOLDEN_V1), h1 = vec(goldenV1, 'HELLO', LRIP_GOLDEN_V1);
    lripDecode(p1.hex, lripLayout(schemaV1, 'POSITION', 'mac8', LRIP_SCHEMA_V1)); lripDecode(h1.hex, lripLayout(schemaV1, 'HELLO', 'mac8', LRIP_SCHEMA_V1));
    previous = { version: `${schemaV1.ver_major}.${schemaV1.ver_minor}`, source: LRIP_GOLDEN_V1, position_bytes: p1.bytes, hello_bytes: h1.bytes };
  }
  return { format: 'lunarsim-lrip-figure', version: 2, lrip: `${schema.ver_major}.${schema.ver_minor}`, source: LRIP_GOLDEN, schema: LRIP_SCHEMA, layout,
    vector: { hex: main.hex, bytes: main.bytes, sender: main.sender, seq: main.seq, t_valid_s: main.t_valid_s, fields: main.fields },
    sizes: pos.map(v => ({ profile: v.profile, auth: v.auth, bytes: v.bytes })),
    hello: { bytes: hello.bytes, fields: hello.fields, every_s: schema.messages.find(m => m.name === 'HELLO').declaration_interval_s,
      enums: Object.fromEntries(['frame', 'datum', 'time_scale'].map(k => [k, schema.enums[k]])) },
    previous };
}

export function stageLrip(PUB) {
  const s = join(ROOT, LRIP_SCHEMA), g = join(ROOT, LRIP_GOLDEN);
  if (!existsSync(s) || !existsSync(g)) { console.log(`prepare-data: ${LRIP_GOLDEN} or the schema missing; /protocol/ figure 5 says so`); return null; }
  const rd = p => JSON.parse(readFileSync(join(ROOT, p), 'utf8'));
  const out = compactLrip(rd(LRIP_SCHEMA), rd(LRIP_GOLDEN), rd(LRIP_SCHEMA_V1), rd(LRIP_GOLDEN_V1));
  mkdirSync(join(PUB, 'protocol'), { recursive: true });
  writeFileSync(join(PUB, LRIP_OUT), JSON.stringify(out));
  console.log(`prepare-data: ${LRIP_OUT} staged (LRIP v${out.lrip}, ${out.vector.bytes}-byte POSITION report, ${out.layout.fields.length} fields; v${out.previous?.version} decodes)`);
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
  // F-78 (review W1): the constants figure 3 reads are required, not dropped by optional chaining
  const need = (v, key) => { if (typeof v !== 'number' || !Number.isFinite(v)) throw new Error(`${E51_SRC}: no number at ${key}`); return v; };
  return { format: 'lunarsim-e51-site', version: 1, source: E51_SRC, experiment: doc.experiment, guard_s: need(doc.constants?.guard_s, 'constants.guard_s'),
    uwb_sigma_m: need(doc.design?.uwb_sigma_m, 'design.uwb_sigma_m'), contact_share: need(doc.contact_share_mean, 'contact_share_mean'), h11: doc.h11, rows };
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

// F-65 / B-99: E53 numbers in /protocol/ problem 5's text, at build time, from B-99's e53_bitrate.json (the file the
// bit-rate figure draws): <!--@e53:geometry:auth:position_hz:rovers:column--> gives a flagged number; a fits_<nb|bb>_<access>
// column gives "fits" or "does not fit" by E53's rule, the busiest link's 95th-percentile load against the channel's
// capacity times its access efficiency (tests/protocol-data.test.mjs checks the rule against results/E53_table.csv).
export const E53_SRC = 'data/atc/protocol/e53_bitrate.json';   // LRIP v0.1 (B-99)
export const E53_V02_TABLE = 'results/E53_table_v02.csv', E53_FULL = 'results/E53_bitrate.json', E53_V02_OUT = 'protocol/e53-v02.json';
let e53doc = null, e53v2 = null, e53full2 = null;
const E53_UNIT = { busiest_link_kbps_p95: [' kbit/s', 1], busiest_link_kbps_mean: [' kbit/s', 1], per_rover_kbps: [' kbit/s', 2], mean_hops_to_base: ['', 1], reachable_share: [' %', 0, 100] };
export function e53Fits(D, row, band, access) {
  const line = Object.entries(D.lines_kbps).find(([k]) => (band === 'nb' ? /narrow/ : /broad/).test(k))?.[1], eta = D.eta[access];
  if (!(line > 0) || !(eta > 0)) throw new Error(`${E53_SRC}: no line or efficiency for ${band} ${access}`);
  return row[D.columns.indexOf('busiest_link_kbps_p95')] <= line * eta;
}
// F-73 (B-100): E53 at LRIP v0.2 sizes, results/E53_table_v02.csv (framing "lrip": packets before link framing;
// "proximity1": every packet in a Proximity-1 frame), in the shape of B-99's file, with the channels and access
// efficiencies of results/E53_bitrate.json. A calculation on a traffic model.
function e53v02full() { return (e53full2 ||= JSON.parse(readFileSync(join(ROOT, E53_FULL), 'utf8').replace(/\bNaN\b/g, 'null'))); }
export function e53v02() { const v = e53v02full().lrip_v02; if (!v) throw new Error(`${E53_FULL}: no lrip_v02`); return v; }
export function e53v02Table() {
  if (e53v2) return e53v2;
  const [head, ...lines] = readFileSync(join(ROOT, E53_V02_TABLE), 'utf8').trim().split(/\r?\n/).map(l => l.split(','));
  const F = e53v02full(), val = x => (x === 'True' ? true : x === 'False' ? false : x !== '' && Number.isFinite(+x) ? +x : x);
  e53v2 = { format: 'lunarsim-protocol-data', version: 1, experiment: 'E53 at LRIP v0.2 (B-100)', source: E53_V02_TABLE, lrip: '0.2',
    columns: head, rows: lines.map(l => l.map(val)), lines_kbps: F.channels_kbps, eta: F.eta };
  return e53v2;
}
function e53row(D, src, geometry, auth, hz, rovers, framing) {
  const c = k => D.columns.indexOf(k);
  const hit = D.rows.filter(r => r[c('geometry')] === geometry && r[c('auth')] === auth && +r[c('position_hz')] === +hz && +r[c('rovers')] === +rovers && (framing == null || r[c('framing')] === framing));
  if (hit.length !== 1) throw new Error(`${src}: ${hit.length} rows for ${framing || ''} ${geometry} ${auth} ${hz} Hz ${rovers} rovers`);
  return hit[0];
}
function e53cell(D, src, row, column, label, digits) {
  const c = k => D.columns.indexOf(k);
  const m = /^fits_(nb|bb)_(scheduled|slotted_aloha)(?:_p95)?$/.exec(column);
  if (m) { const k = `fits_${m[1]}_${m[2]}_p95`; return (c(k) >= 0 ? row[c(k)] === true : e53Fits(D, row, m[1], m[2])) ? 'fits' : 'does not fit'; }
  if (c(column) < 0) throw new Error(`${src}: no column ${column}`);
  const [unit, d, scale = 1] = E53_UNIT[column] || ['', 2];
  return num({ value: +row[c(column)] * scale, unit, digits: digits ?? d, flag: 'Modelled', source: `${src}: ${label}, ${column} (a calculation on a traffic model)` });
}
// <!--@e53:geometry:auth:hz:rovers:column[:digits]--> at LRIP v0.2 sizes; <!--@e53pf:…--> the same in Proximity-1 frames;
// <!--@e53v1:…--> at v0.1 sizes (B-99's file). A fits_<nb|bb>_<access> column gives "fits" or "does not fit".
export function e53(geometry, auth, hz, rovers, column, digits, framing = 'lrip') {
  const D = e53v02Table(), row = e53row(D, E53_V02_TABLE, geometry, auth, hz, rovers, framing);
  return e53cell(D, E53_V02_TABLE, row, column, `${framing === 'proximity1' ? 'LRIP v0.2 in Proximity-1 frames' : 'LRIP v0.2'}, geometry ${geometry}, authentication ${auth}, ${hz} Hz, ${rovers} rovers`, digits == null ? undefined : +digits);
}
export function e53v1(geometry, auth, hz, rovers, column, digits) {
  e53doc ||= JSON.parse(readFileSync(join(ROOT, E53_SRC), 'utf8'));
  const row = e53row(e53doc, E53_SRC, geometry, auth, hz, rovers, null);
  return e53cell(e53doc, E53_SRC, row, column, `LRIP v0.1, geometry ${geometry}, authentication ${auth}, ${hz} Hz, ${rovers} rovers`, digits == null ? undefined : +digits);
}
// <!--@e53air:v1|v2|pf--> scheduled airtime for twenty authenticated rovers at 1 Hz (each version's H13 check; the framed row)
export function e53air(which) {
  const F = e53v02full(), V = e53v02();
  const [value, what] = which === 'v1' ? [F.h13.airtime_1hz_scheduled_kbps, 'h13.airtime_1hz_scheduled_kbps (LRIP v0.1)']
    : which === 'v2' ? [V.h13_check_v02.airtime_1hz_scheduled_kbps, 'lrip_v02.h13_check_v02.airtime_1hz_scheduled_kbps']
      : which === 'pf' ? [V.framing_row.airtime_1hz_scheduled_kbps, 'lrip_v02.framing_row.airtime_1hz_scheduled_kbps (Proximity-1 frames)'] : [];
  if (typeof value !== 'number') throw new Error(`e53air: unknown or missing ${which}`);
  return num({ value, unit: ' kbit/s', digits: 2, flag: 'Modelled', source: `${E53_FULL}: ${what} (a calculation on a traffic model)` });
}
// the bit-rate figure's file: the v0.2 table's load column only (the /protocol/ data budget)
export function stageE53v02(PUB) {
  if (!existsSync(join(ROOT, E53_V02_TABLE))) { console.log(`prepare-data: ${E53_V02_TABLE} missing; /protocol/ figure 5b says so`); return null; }
  const D = e53v02Table(), keep = ['framing', 'geometry', 'auth', 'position_hz', 'rovers', 'busiest_link_kbps_p95'], ix = keep.map(k => D.columns.indexOf(k));
  return stageJson(PUB, { ...D, columns: keep, rows: D.rows.map(r => ix.map(i => r[i])) }, E53_V02_OUT, `${D.rows.length} rows at LRIP v0.2 sizes`);
}

// F-79: a results file keeps the values it published before a correction under superseded_<date>_<task>; the page names
// each earlier value once. superseded(doc, file, field) finds the block holding <field>; dateText gives its superseded_on
// as "13 November 2026" in the flagged markup of a number (dateNum), so no date reaches a page as typed digits.
export function superseded(doc, file, field) {
  const key = Object.keys(doc).find(k => /^superseded_/.test(k) && doc[k] && field in doc[k]);
  if (!key) throw new Error(`${file}: no superseded_* block with ${field}`);
  return { key, doc: doc[key] };
}
export function dateText(S, file) {
  return dateNum({ iso: S.doc.superseded_on, source: `${file}: ${S.key}.superseded_on (the date the values were replaced)` });
}
// seconds for the page text: one decimal under 90 s, then minutes, then hours
export function secs(v) { return v < 90 ? { value: v, unit: ' s', digits: 1 } : v < 5400 ? { value: v / 60, unit: ' min', digits: 1 } : { value: v / 3600, unit: ' h', digits: 1 }; }

// F-56 / B-92: /protocol/ figure 2 reads E52 (results/E52_map.json): bytes and time to sync after 1 h to 14 days out of
// contact, hazards-first against oldest-first, at four link rates; hazards hit during the outage and after contact.
// The route tiles (60) and the full resend (185.5 MB) are computed; the change rates and the hidden share are Assumed.
export const E52_SRC = 'results/E52_map.json';
export const E52_OUT = 'protocol/e52.json';
export const E52_ASSUMED = ['hazards_per_day', 'keepouts_per_day', 'road_edges_per_day', 'hidden_share'];
export function compactE52(doc) {
  if (!Array.isArray(doc.rows) || !doc.full_resend_bytes || !doc.route_tiles) throw new Error(`${E52_SRC}: rows, full_resend_bytes or route_tiles missing`);
  const keep = ['out_h', 'order', 'rate_kbps', 'bytes_mean', 'share_of_full_resend', 'tiles_changed_mean', 't_hazards_current_s', 't_all_s', 'hits_during_outage_mean', 'hits_after_contact_mean'];
  return { format: 'lunarsim-e52-site', version: 1, source: E52_SRC, experiment: doc.experiment, seeds: Array.isArray(doc.seeds) ? doc.seeds.length : doc.seeds, route_tiles: doc.route_tiles,
    full_resend_bytes: doc.full_resend_bytes, parameters: doc.parameters, assumed: E52_ASSUMED.filter(k => k in (doc.parameters || {})), h12: doc.h12,
    rows: doc.rows.map(r => Object.fromEntries(keep.map(k => [k, r[k]]))) };
}

// F-56 / B-94: the measured panels under /protocol/ figures 4 and 6 read E54 (results/E54_dtn.json and
// results/E54_ledger.json): drop-and-retry, store-and-forward and store-and-forward with the lost-link rule at per-hop
// loss 0.10 / 0.25 / 0.40 over the recorded month with a 14-day Earth blackout; and the Earth-ledger lifetimes.
export const E54_SRC = 'results/E54_dtn.json', E54_LEDGER = 'results/E54_ledger.json';
export const E54_OUT = 'protocol/e54.json';
export function compactE54(dtn, ledger) {
  if (!Array.isArray(dtn.rows) || !dtn.h14) throw new Error(`${E54_SRC}: no rows or no h14`);
  if (!Array.isArray(ledger?.rows)) throw new Error(`${E54_LEDGER}: no rows`);
  // F-79 (B-118): one award per vehicle of a job, so awards = jobs + the extra vehicles of team jobs; the lost-link returns
  const AJ = dtn.awards_and_jobs;
  for (const k of ['jobs_per_seed', 'awards_per_seed', 'team_jobs_per_seed']) if (typeof AJ?.[k] !== 'number') throw new Error(`${E54_SRC}: no awards_and_jobs.${k}`);
  if (typeof dtn.lost_link_returns_per_seed !== 'number') throw new Error(`${E54_SRC}: no lost_link_returns_per_seed`);
  return { format: 'lunarsim-e54-site', version: 1, source: E54_SRC, ledger_source: E54_LEDGER, experiment: dtn.experiment, seeds: Array.isArray(dtn.seeds) ? dtn.seeds.length : dtn.seeds,   // the file lists the seed numbers
    jobs_per_seed: dtn.jobs_per_seed, reservations_per_seed: dtn.reservations_per_seed, blackout_days: dtn.blackout_days, earth_up_share: dtn.earth_up_share,
    awards_and_jobs: { jobs_per_seed: AJ.jobs_per_seed, awards_per_seed: AJ.awards_per_seed, team_jobs_per_seed: AJ.team_jobs_per_seed },
    returns_per_seed: dtn.lost_link_returns_per_seed,
    h14: dtn.h14, rows: dtn.rows, ledger: { longest_earth_down_d: ledger.longest_earth_down_d, rows: ledger.rows } };
}

function stageJson(PUB, out, rel, what) {
  mkdirSync(join(PUB, 'protocol'), { recursive: true });
  writeFileSync(join(PUB, rel), JSON.stringify(out));
  console.log(`prepare-data: ${rel} staged (${what})`);
  return out;
}
const readJson = rel => JSON.parse(readFileSync(join(ROOT, rel), 'utf8').replace(/\bNaN\b/g, 'null'));
export function stageE52(PUB) {
  if (!existsSync(join(ROOT, E52_SRC))) { console.log(`prepare-data: ${E52_SRC} missing; /protocol/ figure 2 says so`); return null; }
  const out = compactE52(readJson(E52_SRC));
  return stageJson(PUB, out, E52_OUT, `${out.rows.length} rows`);
}
export function stageE54(PUB) {
  if (!existsSync(join(ROOT, E54_SRC)) || !existsSync(join(ROOT, E54_LEDGER))) { console.log(`prepare-data: ${E54_SRC} or ${E54_LEDGER} missing; /protocol/ problems 4 and 6 say so`); return null; }
  const out = compactE54(readJson(E54_SRC), readJson(E54_LEDGER));
  return stageJson(PUB, out, E54_OUT, `${out.rows.length} rows, ${out.ledger.rows.length} ledger rows`);
}

// F-56 / B-92: E52 numbers in /protocol/ problem 2's text, at build time. <!--@e52:key--> with key one of
//   route_tiles, full_resend (MB), and <out_h>_<rate>_<order>_<column> for a table row, e.g. 24_16_hazards_first_bytes_mean
//   (bytes are given in kB or MB, times in s or min, shares in %), or hazards_per_day / hidden_share (Assumed).
let e52doc = null;
export function e52(key) {
  e52doc ||= JSON.parse(readFileSync(join(ROOT, E52_SRC), 'utf8'));
  const D = e52doc, src = `${E52_SRC}: `;
  if (key === 'route_tiles') return num({ value: D.route_tiles, unit: ' tiles', digits: 0, flag: 'Modelled', source: src + 'route_tiles' });
  if (key === 'full_resend') return num({ value: D.full_resend_bytes / 1e6, unit: ' MB', digits: 1, flag: 'Modelled', source: src + 'full_resend_bytes' });
  if (key === 'hazards_per_day') return num({ value: D.parameters.hazards_per_day, unit: ' a day', digits: 0, flag: 'Assumed', source: src + 'parameters.hazards_per_day' });
  if (key === 'hidden_share') return num({ value: 100 * D.parameters.hidden_share, unit: ' %', digits: 0, flag: 'Assumed', source: src + 'parameters.hidden_share' });
  // F-79 (B-118 N1): the largest stale-map hit count after contact over every outage and link rate, now (hits_after_max_<order>)
  // and as published before the code review (was_hits_after_max_<order>, from superseded_<date>_..., named once on the page)
  let mm;
  if ((mm = /^(was_)?hits_after_max_(hazards_first|oldest_first)$/.exec(key))) {
    const old = !!mm[1], S = old ? superseded(D, E52_SRC, 'rows') : null, rows = old ? S.doc.rows : D.rows;
    const xs = rows.filter(r => r.order === mm[2]).map(r => r.hits_after_contact_mean);
    if (!xs.length || xs.some(x => typeof x !== 'number')) throw new Error(`${E52_SRC}: no hits_after_contact_mean for ${mm[2]}${old ? ` in ${S.key}` : ''}`);
    return num({ value: Math.max(...xs), unit: '', digits: 2, flag: 'Modelled', source: `${src}${old ? `${S.key}.` : ''}rows, ${mm[2].replace('_', ' ')}, hits_after_contact_mean, the largest over every outage and link rate (mean over ${D.seeds.length || D.seeds} seeds)${old ? ', as published before the code review' : ''}` });
  }
  if (key === 'superseded_on') return dateText(superseded(D, E52_SRC, 'rows'), E52_SRC);
  const m = /^(\d+)_(\d+)_(hazards_first|oldest_first)_(\w+)$/.exec(key);
  if (!m) throw new Error(`${E52_SRC}: unknown key ${key}`);
  const [, out, rate, order, col] = m, hit = D.rows.filter(r => r.out_h === +out && r.rate_kbps === +rate && r.order === order);
  if (hit.length !== 1 || !(col in hit[0])) throw new Error(`${E52_SRC}: no ${col} for ${out} h, ${rate} kbit/s, ${order}`);
  const v = hit[0][col], s = `${src}${out} h out of contact, ${rate} kbit/s, ${order.replace('_', ' ')}, ${col}, mean over ${D.seeds} seeds`;
  if (/bytes/.test(col)) return v >= 1e6 ? num({ value: v / 1e6, unit: ' MB', digits: 2, flag: 'Modelled', source: s }) : num({ value: v / 1e3, unit: ' kB', digits: v >= 1e5 ? 0 : 1, flag: 'Modelled', source: s });
  if (/^t_/.test(col)) return v >= 90 ? num({ value: v / 60, unit: ' min', digits: v >= 600 ? 0 : 1, flag: 'Modelled', source: s }) : num({ value: v, unit: ' s', digits: v < 10 ? 1 : 0, flag: 'Modelled', source: s });
  if (/share/.test(col)) return num({ value: 100 * v, unit: ' %', digits: 2, flag: 'Modelled', source: s });
  return num({ value: v, unit: '', digits: 2, flag: 'Modelled', source: s });
}

// F-79 (B-118 step 2): E54 numbers in /protocol/ problems 4 and 6's text, at build time. <!--@e54:key--> with key
//   [was:]<protocol>:<field>@<loss> for a row of results/E54_dtn.json (was: the row as published before the code review,
//   from its superseded_* block), e.g. sf_ll:aoi_mean_s@0.25; or returns / was:returns (lost-link returns a seed), jobs,
//   awards, team_jobs (awards_and_jobs, a seed) and superseded_on. Fields ending _s are times, _share shares, the rest counts.
let e54doc = null;
export function e54(key) {
  e54doc ||= readJson(E54_SRC);
  const D = e54doc, flag = (o, what) => num({ ...o, flag: 'Modelled', source: `${E54_SRC}: ${what}` });
  const old = key.startsWith('was:'), k = old ? key.slice(4) : key, S = old ? superseded(D, E54_SRC, 'rows') : null, doc = old ? S.doc : D;
  const pre = old ? `${S.key}.` : '', post = old ? ', as published before the code review' : '';
  let m;
  if ((m = /^(drop_retry|sf|sf_ll):(\w+)@([\d.]+)$/.exec(k))) {
    const [, proto, field, loss] = m, hit = doc.rows.filter(r => r.protocol === proto && r.loss === +loss);
    if (hit.length !== 1 || typeof hit[0][field] !== 'number') throw new Error(`${E54_SRC}: no ${pre}rows ${field} for ${proto} at loss ${loss}`);
    const v = hit[0][field], what = `${pre}rows, ${proto}, loss ${loss}, ${field}, over ${hit[0].seeds} seeds${post}`;
    if (/_s$/.test(field)) return flag(secs(v), what);
    if (/_share$/.test(field)) return flag({ value: 100 * v, unit: ' %', digits: 1 }, what);
    return flag({ value: v, unit: '', digits: 0 }, what);
  }
  if ((m = /^loss@([\d.]+)$/.exec(k)) && !old) {   // a loss level the rows hold, as a percentage (a setting, not a result)
    if (!D.rows.some(r => r.loss === +m[1])) throw new Error(`${E54_SRC}: no rows at loss ${m[1]}`);
    return `${fmt(100 * m[1], 0)} %`;
  }
  if (k === 'returns') { if (typeof doc.lost_link_returns_per_seed !== 'number') throw new Error(`${E54_SRC}: no ${pre}lost_link_returns_per_seed`); return flag({ value: doc.lost_link_returns_per_seed, unit: '', digits: 1 }, `${pre}lost_link_returns_per_seed${post}`); }
  if (old) throw new Error(`${E54_SRC}: unknown key ${key}`);
  const AJ = { jobs: 'jobs_per_seed', awards: 'awards_per_seed', team_jobs: 'team_jobs_per_seed' };
  if (AJ[k]) { const v = D.awards_and_jobs?.[AJ[k]]; if (typeof v !== 'number') throw new Error(`${E54_SRC}: no awards_and_jobs.${AJ[k]}`); return flag({ value: v, unit: '', digits: k === 'jobs' ? 1 : 2 }, `awards_and_jobs.${AJ[k]}`); }
  if (k === 'superseded_on') return dateText(superseded(D, E54_SRC, 'rows'), E54_SRC);
  throw new Error(`${E54_SRC}: unknown key ${key}`);
}

// F-56 / B-95: /protocol/ problem 7 reads E55 (results/E55_integrity.json): the LRIP integrity rule as written (z^2 > gamma,
// suspect at 3 of the last 5) against the single test and E56's calibrated chi-square and network, false alarms per
// pair-day and recall per fault type on the test and out-of-distribution streams; W-MSR consensus by geometry, N, liars
// f and F, with and without the base mast; forgeries accepted against 2^-t; replays.
export const E55_SRC = 'results/E55_integrity.json';
export const E55_OUT = 'protocol/e55.json';
const TYPES = ['jump', 'drift', 'frozen', 'frame', 'noise', 'all'];
export function compactE55(doc) {
  const I = doc.integrity, C = doc.consensus?.cells, M = doc.consensus_with_base_mast?.cells;
  if (!I?.sets || !Array.isArray(C)) throw new Error(`${E55_SRC}: integrity sets or consensus cells missing`);
  const det = {};
  for (const set of ['test', 'ood']) {
    det[set] = {};
    for (const [k, v] of Object.entries(I.sets[set] || {})) {
      if (k.startsWith('_')) continue;
      det[set][k] = { gamma: v.gamma, fa: v.fa_per_pair_day, recall: Object.fromEntries(TYPES.map(t => [t, v.per_type[t]?.recall])) };
    }
    for (const [k, v] of Object.entries(I.e56_reference?.[set] || {})) {
      if (k !== 'chi2_step' && k !== 'net') continue;
      det[set][`e56_${k}`] = { fa: v.fa_per_pair_day.mean, recall: Object.fromEntries(TYPES.map(t => [t, v.events[t]?.recall?.mean])) };
    }
  }
  const cell = x => ({ geometry: x.geometry, mast: !!x.mast, N: x.N, f: x.f, F: x.F, runs: x.runs, safe: x.safe_share, agreement: x.agreement_share, connected: x.connected_share, degree: x.degree_condition_share });
  const auth = doc.auth || {};
  return { format: 'lunarsim-e55-site', version: 1, source: E55_SRC, experiment: doc.experiment, rule: I.rule, detectors: det,
    consensus: [...C.map(cell), ...(M || []).map(x => ({ ...cell(x), mast: true }))],
    forgery: Object.fromEntries(Object.entries(auth.forgery || {}).map(([t, v]) => [t, v.attempts ? { attempts: v.attempts, accepted: v.accepted, bound: v['bound_2^-t'] } : { per_attempt: v.per_attempt }])),
    replay: auth.replay || {}, replay_recent: replayRecent(doc) };
}
// F-79 (B-118 N9): the second replay trial, messages sent in the last 60 s, with the accepted replays split
function replayRecent(doc) {
  const L = doc.replay_recent?.loss;
  if (!L) throw new Error(`${E55_SRC}: no replay_recent.loss`);
  const keep = ['replays', 'replays_with_age_le_10s', 'replays_accepted', 'accepted_missed_original_inside_window', 'accepted_other'];
  return Object.fromEntries(Object.entries(L).map(([l, v]) => {
    for (const k of keep) if (typeof v[k] !== 'number') throw new Error(`${E55_SRC}: no replay_recent.loss.${l}.${k}`);
    if (v.accepted_missed_original_inside_window + v.accepted_other !== v.replays_accepted) throw new Error(`${E55_SRC}: replay_recent at loss ${l}: the accepted replays do not add up`);
    return [l, Object.fromEntries(keep.map(k => [k, v[k]]))];
  }));
}
export function stageE55(PUB) {
  if (!existsSync(join(ROOT, E55_SRC))) { console.log(`prepare-data: ${E55_SRC} missing; /protocol/ problem 7 says so`); return null; }
  const out = compactE55(readJson(E55_SRC));
  return stageJson(PUB, out, E55_OUT, `${Object.keys(out.detectors.test).length} detectors, ${out.consensus.length} consensus cells`);
}

// <!--@e55:key--> numbers for problem 7's text: fa_<set>_<detector> (false alarms per pair-day), recall_<set>_<detector>_<type>,
// agreement_max / agreement_max_mast (the most often the honest rovers converge, over every cell with F >= f, in %).
let e55doc = null;
export function e55(key) {
  e55doc ||= compactE55(readJson(E55_SRC));
  const D = e55doc, flag = (value, unit, digits, what) => num({ value, unit, digits, flag: 'Modelled', source: `${E55_SRC}: ${what}` });
  let m;
  if ((m = /^fa_(test|ood)_(.+)$/.exec(key))) {
    const d = D.detectors[m[1]][m[2]]; if (!d) throw new Error(`${E55_SRC}: no detector ${m[2]} on ${m[1]}`);
    return flag(d.fa, '', d.fa < 1 ? 2 : d.fa < 100 ? 1 : 0, `${m[2]}, ${m[1]} set, false alarms per pair-day`);
  }
  if ((m = /^recall_(test|ood)_(.+)_(jump|drift|frozen|frame|noise|all)$/.exec(key))) {
    const d = D.detectors[m[1]][m[2]]; if (!d) throw new Error(`${E55_SRC}: no detector ${m[2]} on ${m[1]}`);
    return flag(d.recall[m[3]], '', 2, `${m[2]}, ${m[1]} set, recall on ${m[3]} faults`);
  }
  // F-79: replay_<field>@<loss> from the recent-replay trial (replays, replays_accepted, accepted_missed_original_inside_window, accepted_other)
  if ((m = /^replay_(\w+)@([\d.]+)$/.exec(key))) {
    if (m[1] === 'loss') { if (!D.replay_recent[m[2]]) throw new Error(`${E55_SRC}: no replay_recent.loss.${m[2]}`); return `${fmt(100 * m[2], 0)} %`; }   // the loss level (a setting)
    const v = D.replay_recent[m[2]]?.[m[1]];
    if (typeof v !== 'number') throw new Error(`${E55_SRC}: no replay_recent.loss.${m[2]}.${m[1]}`);
    return flag(v, '', 0, `replay_recent.loss.${m[2]}.${m[1]} (a replay a second of a message sent in the last 60 s)`);
  }
  if (key === 'agreement_max' || key === 'agreement_max_mast') {
    const mast = key.endsWith('mast'), cells = D.consensus.filter(c => c.mast === mast && c.F >= c.f);
    if (!cells.length) throw new Error(`${E55_SRC}: no consensus cells${mast ? ' with the mast' : ''}`);
    return flag(100 * Math.max(...cells.map(c => c.agreement)), ' %', 0, `consensus${mast ? ' with the base mast' : ''}, the largest share of runs in which the honest rovers agree, over every cell with F at least f`);
  }
  throw new Error(`${E55_SRC}: unknown key ${key}`);
}

// F-65 / B-99: BACKEND's site data for /protocol/ and /network/ (data/atc/protocol/, format lunarsim-protocol-data v1),
// checked against its index (bytes and sha256 per file, as for the trace pair) and staged unchanged to
// public/protocol/b99/. A size or sha256 mismatch, or a file the index lists that is missing, stops the build.
export const B99_DIR = 'data/atc/protocol', B99_OUT = 'protocol/b99';
// F-78 (review W2): checked against the index but not staged: read at build only (problem 5's text); the bit-rate figure
// draws protocol/e53-v02.json
export const B99_BUILD_ONLY = new Set(['e53_bitrate.json']);
export function checkB99(dir = join(ROOT, B99_DIR)) {
  const ix = JSON.parse(readFileSync(join(dir, 'index.json'), 'utf8'));
  if (ix.format !== 'lunarsim-protocol-data-index' || ix.version !== 1) throw new Error(`${B99_DIR}/index.json: format ${ix.format} version ${ix.version}`);
  const out = {};
  for (const [name, want] of Object.entries(ix.files)) {
    const p = join(dir, name);
    if (!existsSync(p)) throw new Error(`${B99_DIR}/${name}: listed in the index but missing`);
    const buf = readFileSync(p), sha = createHash('sha256').update(buf).digest('hex');
    if (buf.length !== want.bytes) throw new Error(`${B99_DIR}/${name}: ${buf.length} bytes, the index says ${want.bytes}`);
    if (sha !== want.sha256) throw new Error(`${B99_DIR}/${name}: sha256 ${sha.slice(0, 12)}…, the index says ${want.sha256.slice(0, 12)}…`);
    const doc = JSON.parse(buf.toString('utf8'));
    if (doc.format !== 'lunarsim-protocol-data' || doc.version !== 1) throw new Error(`${B99_DIR}/${name}: format ${doc.format} version ${doc.version}`);
    out[name] = { buf, doc };
  }
  return { index: ix, files: out };
}
export function stageB99(PUB) {
  if (!existsSync(join(ROOT, B99_DIR, 'index.json'))) { console.log(`prepare-data: ${B99_DIR} missing; the B-99 figures say so`); return null; }
  const { index, files } = checkB99();
  mkdirSync(join(PUB, B99_OUT), { recursive: true });
  const staged = Object.entries(files).filter(([name]) => !B99_BUILD_ONLY.has(name));
  for (const name of B99_BUILD_ONLY) rmSync(join(PUB, B99_OUT, name), { force: true });   // a copy staged by an older build
  for (const [name, f] of staged) writeFileSync(join(PUB, B99_OUT, name), f.buf);
  writeFileSync(join(PUB, B99_OUT, 'index.json'), JSON.stringify(index));
  console.log(`prepare-data: ${staged.length} B-99 files staged to ${B99_OUT}/ (sizes and sha256 match the index; ${[...B99_BUILD_ONLY].join(', ')} read at build only)`);
  return files;
}

// F-70 / B-90b: the cost of stopping for terrain fixes, from results/E50b_summary.json (the fix stops inside the engine):
// <!--@e50b:key--> with key delay_without, delay_with, delay_diff, delay_pct, delay_lo, delay_hi (hours, %) or stop_s.
export const E50B_SRC = 'results/E50b_summary.json';
let e50bdoc = null;
export function e50b(key) {
  e50bdoc ||= JSON.parse(readFileSync(join(ROOT, E50B_SRC), 'utf8').replace(/\bNaN\b/g, 'null'));
  const D = e50bdoc, m = D.metrics?.delay_mean_h;
  if (!m) throw new Error(`${E50B_SRC}: no metrics.delay_mean_h`);
  const src = what => `${E50B_SRC}: ${what}, mean over ${m.n_seeds} seeds`, f = (value, unit, digits, what) => num({ value, unit, digits, flag: 'Modelled', source: src(what) });
  const V = {
    delay_without: () => f(m.without_stop_time, ' h', 2, 'delay per delivery without stop time'),
    delay_with: () => f(m.with_stop_time, ' h', 2, 'delay per delivery with the terrain-fix stops'),
    delay_diff: () => f(m.diff_mean, ' h', 2, 'difference, with minus without'),
    delay_pct: () => f(100 * m.diff_mean / m.without_stop_time, ' %', 1, 'difference relative to without'),
    delay_lo: () => f(m.diff_ci95_bootstrap[0], ' h', 2, '95 % bootstrap interval of the difference, low end'),
    delay_hi: () => f(m.diff_ci95_bootstrap[1], ' h', 2, '95 % bootstrap interval of the difference, high end'),
    stop_s: () => num({ value: D.design.stop_s, unit: ' s', digits: 0, flag: 'Assumed', source: `${E50B_SRC}: design.stop_s` }),
  };
  if (!V[key]) throw new Error(`${E50B_SRC}: unknown key ${key}`);
  return V[key]();
}

// F-70 / B-91: the clock-guard observation in /protocol/ problem 3, from results/E51_clocks.json (decisions B7: stated as
// observed). <!--@e51:guard_pairs--> the close reservation pairs checked; <!--@e51:guard_max_offset--> the largest clock offset
// among the lunar-time rows with no conflict at the 0.1 s guard.
let e51doc = null;
export function e51(key) {
  e51doc ||= compactE51(JSON.parse(readFileSync(join(ROOT, E51_SRC), 'utf8').replace(/\bNaN\b/g, 'null')));
  const ok = e51doc.rows.filter(r => r['conflicts_guard_0.1'] === 0 && typeof r.max_abs_clock_s === 'number');
  if (!ok.length) throw new Error(`${E51_SRC}: no row without a conflict at the guard`);
  const worst = ok.reduce((a, r) => (r.max_abs_clock_s > a.max_abs_clock_s ? r : a));
  if (key === 'guard_pairs') return num({ value: worst.conflict_pairs_checked, unit: ' reservation pairs', digits: 0, flag: 'Modelled', source: `${E51_SRC}: rows.conflict_pairs_checked (${worst.class}, resync ${worst.interval_s} s)` });
  if (key === 'guard_max_offset') return num({ value: worst.max_abs_clock_s, unit: ' s', digits: 3, flag: 'Modelled', source: `${E51_SRC}: rows.max_abs_clock_s, the largest among the rows with no conflict at the ${e51doc.guard_s} s guard (${worst.class}, resync ${worst.interval_s} s)` });
  throw new Error(`${E51_SRC}: unknown key ${key}`);
}

// F-70 / B-93: LRIP sizes in /protocol/ problem 5's text, from the schema and the golden vectors (decisions B3: the
// 41 B packet is before link framing and coding). <!--@lrip:types--> the message types of v0.1 (in words),
// <!--@lrip:packet--> the POSITION packet, <!--@lrip:framed--> the same in a Proximity-1 frame.
const WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty'];
// F-73 (B-100): v0.2. <!--@lrip:version-->, <!--@lrip:hello_v1--> / <!--@lrip:hello--> the HELLO packet before and with the
// declaration, <!--@lrip:hello_every--> how often it must be sent, <!--@lrip:manifest_add--> what the declaration adds to a
// manifest, <!--@lrip:sent--> / <!--@lrip:not_sent--> the types in and out of E53's traffic model. Conformance vectors test
// the codec, not a radio.
export function lrip(key) {
  const rd = p => JSON.parse(readFileSync(join(ROOT, p), 'utf8'));
  const schema = rd(LRIP_SCHEMA), golden = rd(LRIP_GOLDEN);
  const pos = vec(golden, 'POSITION', LRIP_GOLDEN), frame = schema.framing?.proximity1_frame_bytes, cov = schema.traffic_model_coverage;
  const spec = (value, unit, src) => num({ value, unit, digits: 0, flag: 'Spec', source: src });
  const V = {
    types: () => WORDS[schema.messages.length] ?? String(schema.messages.length),
    version: () => `${schema.ver_major}.${schema.ver_minor}`,
    packet: () => spec(pos.bytes, ' B', `${LRIP_GOLDEN}: the POSITION vector (profile N, 8-byte MAC), before link framing and coding`),
    framed: () => {
      if (typeof frame !== 'number') throw new Error(`${LRIP_SCHEMA}: no framing.proximity1_frame_bytes`);
      return spec(pos.bytes + frame, ' B', `${LRIP_GOLDEN} POSITION packet plus ${LRIP_SCHEMA} framing.proximity1_frame_bytes (${frame} B)`);
    },
    hello_v1: () => spec(vec(rd(LRIP_GOLDEN_V1), 'HELLO', LRIP_GOLDEN_V1).bytes, ' B', `${LRIP_GOLDEN_V1}: the HELLO vector (profile N, 8-byte MAC)`),
    hello: () => spec(vec(golden, 'HELLO', LRIP_GOLDEN).bytes, ' B', `${LRIP_GOLDEN}: the HELLO vector (profile N, 8-byte MAC), with the declaration`),
    hello_every: () => spec(schema.messages.find(m => m.name === 'HELLO').declaration_interval_s, ' s', `${LRIP_SCHEMA}: HELLO.declaration_interval_s`),
    manifest_add: () => {
      const d = [...new Set(Object.values(e53v02()['manifest_bytes_v0.2']).map(m => m.compact_cbor - m['compact_cbor_v0.1']))];
      if (d.length !== 1) throw new Error(`${E53_FULL}: the manifests grew by different amounts (${d.join(', ')} B)`);
      return spec(d[0], ' B', `${E53_FULL}: lrip_v02.manifest_bytes_v0.2, compact_cbor minus compact_cbor_v0.1`);
    },
    sent: () => WORDS[cov.sent_by_E53.length] ?? String(cov.sent_by_E53.length),
    not_sent: () => cov.not_sent_by_E53.map(t => t.toLowerCase().replace(/^cap_/, 'capability_').replace(/_/g, ' ')).join(', '),
  };
  if (!V[key]) throw new Error(`lrip: unknown key ${key}`);
  return V[key]();
}

// F-70b / B-103, F-73 / B-110: the driving split of E53 at LRIP v0.2 sizes: <!--@e53d:key--> with key parked_share,
// drive_hops, drive_reach, drive_air / drive_air_pf (scheduled airtime on driving steps, 1 Hz; _pf in Proximity-1 frames),
// drive_aloha / drive_aloha_pf (slotted random access), si_src / si_src_pf (STATUS and INTENT also at 1 Hz: what twenty
// rovers' sources offer), channel (the narrow-band channel) or si_fit (the airtime against it, in every case).
let e53full = null;
export function e53d(key) {
  e53full ||= JSON.parse(readFileSync(join(ROOT, 'results', 'E53_bitrate.json'), 'utf8').replace(/\bNaN\b/g, 'null'));
  // F-73 (B-110): at LRIP v0.2 sizes, lrip_v02.driving_split, packets before link framing ("lrip") and in Proximity-1
  // frames ("proximity1"); the hops and the share with a path do not depend on the version. A calculation on a traffic model.
  const D = e53full.lrip_v02?.driving_split, src = 'results/E53_bitrate.json: lrip_v02.driving_split.';
  if (!D) throw new Error('results/E53_bitrate.json: no lrip_v02.driving_split');
  const drv = fr => D.e53_auth_20_rovers?.[fr]?.fleet_driving?.['1 Hz'], si = fr => D.status_intent_at_1hz?.[fr];
  const nb = Object.entries(e53full.channels_kbps).find(([k]) => /narrow/.test(k))?.[1];
  const f = (value, unit, digits, what) => num({ value, unit, digits, flag: 'Modelled', source: `${src}${what} (a calculation on a traffic model)` });
  const air = (fr, k, d) => f(drv(fr)[k], ' kbit/s', d, `e53_auth_20_rovers.${fr}.fleet_driving.1 Hz.${k}`);
  // every airtime with STATUS and INTENT at 1 Hz, both framings, the fleet and its driving steps
  const siAir = ['lrip', 'proximity1'].flatMap(fr => Object.values(si(fr).busiest_link_20_rovers).map(x => x.scheduled_airtime_p95_kbps));
  const V = {
    parked_share: () => f(100 * (1 - D.pool_driving_share), ' %', 0, 'pool_driving_share (one minus)'),
    drive_hops: () => f(drv('lrip').mean_hops_to_base, '', 2, 'e53_auth_20_rovers.lrip.fleet_driving.1 Hz.mean_hops_to_base'),
    drive_reach: () => f(100 * drv('lrip').reachable_share, ' %', 0, 'e53_auth_20_rovers.lrip.fleet_driving.1 Hz.reachable_share'),
    drive_air: () => air('lrip', 'scheduled_airtime_p95_kbps', 2),
    drive_air_pf: () => air('proximity1', 'scheduled_airtime_p95_kbps', 2),
    drive_aloha: () => air('lrip', 'slotted_aloha_airtime_p95_kbps', 1),
    drive_aloha_pf: () => air('proximity1', 'slotted_aloha_airtime_p95_kbps', 1),
    si_src: () => f(si('lrip').sources_20_rovers_kbps, ' kbit/s', 2, 'status_intent_at_1hz.lrip.sources_20_rovers_kbps'),
    si_src_pf: () => f(si('proximity1').sources_20_rovers_kbps, ' kbit/s', 2, 'status_intent_at_1hz.proximity1.sources_20_rovers_kbps'),
    channel: () => num({ value: nb, unit: ' kbit/s', digits: 0, flag: 'Assumed', source: 'results/E53_bitrate.json: channels_kbps (the narrow-band channel)' }),
    // the page says "… the channel in every case": stop the build if the cases disagree
    si_fit: () => { if (siAir.every(a => a > nb)) return 'is above'; if (siAir.every(a => a <= nb)) return 'is within'; throw new Error(`${src}status_intent_at_1hz: some airtimes above the channel and some within; /protocol/ says "in every case"`); },
  };
  if (!V[key]) throw new Error(`E53 driving split: unknown key ${key}`);
  return V[key]();
}

// F-70b / B-104: the radio over a curved Moon (results/E48_sizing.json revision_b104, ITU-R P.526; decisions B10):
// <!--@b104:key--> for the big rovers' worst hop (LTV1): antenna, hop, loss_diff, rate_flat, rate_sph, target, range_flat, range_sph,
// carry ("no longer carries" / "still carries": the target rate at the worst hop, F-71).
let b104doc = null;
export function b104(key, cls = 'LTV1') {
  b104doc ||= JSON.parse(readFileSync(join(ROOT, 'results', 'E48_sizing.json'), 'utf8').replace(/\bNaN\b/g, 'null')).revision_b104;
  if (!b104doc) throw new Error('results/E48_sizing.json: no revision_b104');
  const C = b104doc.per_class[cls], W = C.worst_hop, src = `results/E48_sizing.json: revision_b104.per_class.${cls}.`;
  const tgt = Math.max(...Object.keys(C.range_m_for_kbps_spherical).map(Number));
  const f = (value, unit, digits, what, flag = 'Modelled') => num({ value, unit, digits, flag, source: src + what });
  const V = {
    antenna: () => f(C.antenna_m, ' m', 1, 'antenna_m', 'Assumed'),
    hop: () => f(W.d_m / 1000, ' km', 0, 'worst_hop.d_m', 'Assumed'),
    loss_diff: () => f(W.spherical_minus_flat_db, ' dB', 0, 'worst_hop.spherical_minus_flat_db'),
    rate_flat: () => f(W.kbps.flat_ground, ' kbit/s', 0, 'worst_hop.kbps.flat_ground'),
    rate_sph: () => f(W.kbps.spherical_ground, ' kbit/s', 0, 'worst_hop.kbps.spherical_ground'),
    target: () => f(tgt / 1000, ' Mbit/s', 0, 'range_m_for_kbps_spherical (the highest rate listed)', 'Assumed'),
    range_flat: () => f(C.range_m_for_kbps_flat[String(tgt)] / 1000, ' km', 2, `range_m_for_kbps_flat.${tgt}`),
    range_sph: () => f(C.range_m_for_kbps_spherical[String(tgt)] / 1000, ' km', 2, `range_m_for_kbps_spherical.${tgt}`),
    // F-71: whether the worst hop still carries the highest listed rate over a curved Moon, for the crew and the cargo
    // rover alike (P3 states it for both); the two must agree or the build stops
    carry: () => {
      const says = k => { const R = b104doc.per_class[k]; return R.range_m_for_kbps_spherical[String(tgt)] < R.worst_hop.d_m ? 'no longer carries' : 'still carries'; };
      if (says('LTV1') !== says('CARGO')) throw new Error('revision_b104: the crew and cargo rovers differ at the worst hop');
      return says(cls);
    },
  };
  if (!V[key]) throw new Error(`revision_b104: unknown key ${key}`);
  return V[key]();
}

// F-72 (B-102): <!--@e50ov:lead--> on /protocol/ problem 1: what a reservation overlap is (results/E50_overlaps.json). The
// count is fixed by how waiting windows are filed (back to back), not by the position error, so it is said not to be a
// safety measure; the closeness numbers (gap at entry, nothing within 5 m) carry the safety statement. A simulation.
export const OV_SRC = 'results/E50_overlaps.json';
export function e50ov(key) {
  if (key !== 'lead') throw new Error(`${OV_SRC}: unknown key ${key}`);
  const D = JSON.parse(readFileSync(join(ROOT, OV_SRC), 'utf8')), X = D.multiples['4'], runs = Object.entries(X.runs);
  const m = (value, unit, digits, what) => num({ value, unit, digits, flag: 'Modelled', source: `${OV_SRC}: multiples.4.runs.${what} (a simulation)` });
  const bare = runs.filter(([k]) => k.startsWith('no_margin:')), lay = X.runs['with_margin:layered'];
  const sh = bare.map(([k, r]) => [k, r.back_to_back.abutting_share_overlapping]), lo = sh.reduce((a, b) => (b[1] < a[1] ? b : a)), hi = sh.reduce((a, b) => (b[1] > a[1] ? b : a));
  const gp = bare.map(([k, r]) => [k, r.gap_at_entry_m.median]), glo = gp.reduce((a, b) => (b[1] < a[1] ? b : a)), ghi = gp.reduce((a, b) => (b[1] > a[1] ? b : a));
  const all = Object.values(D.multiples).flatMap(M => Object.values(M.runs));
  if (all.some(r => r.counts_per_seed.gap_under_d0_5m > 0 || r.counts_per_seed.gap_under_r1_dmin > 0)) throw new Error(`${OV_SRC}: an overlap came within 5 m or R1's gap; the /protocol/ sentence says none did`);
  const pairs = bare[0][1].back_to_back.abutting_pairs_per_seed;
  return `The margin also changes how often two reservations of the same road overlap in time, and that count is not a safety measure: windows filed back to back overlapped in ${m(100 * lo[1], '', 0, `${lo[0]}.back_to_back.abutting_share_overlapping`)} to ${m(100 * hi[1], ' %', 0, `${hi[0]}.back_to_back.abutting_share_overlapping`)} of cases at four times the fleet (${m(pairs, '', 0, `${bare[0][0]}.back_to_back.abutting_pairs_per_seed`)} such pairs a seed) whatever the position error. `
    + `The margin separates the windows, so the count falls, but it does not change how far ahead the first vehicle was when the second entered (medians of ${m(glo[1], '', 0, `${glo[0]}.gap_at_entry_m.median`)} to ${m(ghi[1], ' m', 0, `${ghi[0]}.gap_at_entry_m.median`)} without a margin, ${m(lay.gap_at_entry_m.median, ' m', 0, 'with_margin:layered.gap_at_entry_m.median')} with the layered one, set by the lengths of the segments), and no overlap, with or without a margin, at either fleet size, brought two vehicles inside the static margin or the keep-distance rule's gap (a simulation, task B-102).`;
}

// F-73 (B-100): where a page gives the radio load at LRIP v0.1 sizes (E48's airtime on /atc/ and the P3 card), the v0.2
// figures beside it, from E53 (a calculation on a traffic model): <!--@lrip2:note-->
export function lrip2(key) {
  if (key !== 'note') throw new Error(`lrip2: unknown key ${key}`);
  return `At LRIP v0.2 sizes, whose heartbeat now declares frame, datum and time scale, E53's calculation on a traffic model gives twenty rovers reporting once a second ${e53('fleet', 'on', '1.0', 20, 'busiest_link_kbps_p95', 2)} on the busiest link (${e53v1('fleet', 'on', '1.0', 20, 'busiest_link_kbps_p95', 2)} at v0.1 sizes) and ${e53air('v2')} of scheduled airtime (${e53air('v1')}); in Proximity-1 frames ${e53air('pf')}, which ${e53('fleet', 'on', '1.0', 20, 'fits_nb_scheduled_p95', null, 'proximity1')} the narrow-band channel when scheduled and ${e53('fleet', 'on', '1.0', 20, 'fits_nb_slotted_aloha_p95', null, 'proximity1')} it with slotted random access.`;
}
