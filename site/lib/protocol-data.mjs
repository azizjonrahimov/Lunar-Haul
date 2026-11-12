// /protocol/ data staged at build time (prepare-data) and read for the page text: LRIP (figure 5), E51 (figure 3), E52
// (figure 2), E53 (problem 5's text), E54 (problems 4 and 6), E55 (problem 7) and B-99's figure files (checkB99, stageB99).
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { ROOT } from './pages.mjs';
import { lripDecode } from '../src/protocol/lrip.js';
import { num } from '../src/components/num.js';
export { lripDecode };

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

// F-65 / B-99: E53 numbers in /protocol/ problem 5's text, at build time, from B-99's e53_bitrate.json (the file the
// bit-rate figure draws): <!--@e53:geometry:auth:position_hz:rovers:column--> gives a flagged number; a fits_<nb|bb>_<access>
// column gives "fits" or "does not fit" by E53's rule, the busiest link's 95th-percentile load against the channel's
// capacity times its access efficiency (tests/protocol-data.test.mjs checks the rule against results/E53_table.csv).
export const E53_SRC = 'data/atc/protocol/e53_bitrate.json';
let e53doc = null;
const E53_UNIT = { busiest_link_kbps_p95: [' kbit/s', 1], busiest_link_kbps_mean: [' kbit/s', 1], per_rover_kbps: [' kbit/s', 2], mean_hops_to_base: ['', 1], reachable_share: [' %', 0, 100] };
export function e53Fits(D, row, band, access) {
  const line = Object.entries(D.lines_kbps).find(([k]) => (band === 'nb' ? /narrow/ : /broad/).test(k))?.[1], eta = D.eta[access];
  if (!(line > 0) || !(eta > 0)) throw new Error(`${E53_SRC}: no line or efficiency for ${band} ${access}`);
  return row[D.columns.indexOf('busiest_link_kbps_p95')] <= line * eta;
}
export function e53(geometry, auth, hz, rovers, column) {
  e53doc ||= JSON.parse(readFileSync(join(ROOT, E53_SRC), 'utf8'));
  const D = e53doc, c = k => D.columns.indexOf(k);
  const hit = D.rows.filter(r => r[c('geometry')] === geometry && r[c('auth')] === auth && +r[c('position_hz')] === +hz && +r[c('rovers')] === +rovers);
  if (hit.length !== 1) throw new Error(`${E53_SRC}: ${hit.length} rows for ${geometry} ${auth} ${hz} Hz ${rovers} rovers`);
  const m = /^fits_(nb|bb)_(scheduled|slotted_aloha)(?:_p95)?$/.exec(column);
  if (m) return e53Fits(D, hit[0], m[1], m[2]) ? 'fits' : 'does not fit';
  if (c(column) < 0) throw new Error(`${E53_SRC}: no column ${column}`);
  const [unit, digits, scale = 1] = E53_UNIT[column] || ['', 2];
  return num({ value: +hit[0][c(column)] * scale, unit, digits, flag: 'Modelled', source: `${E53_SRC}: geometry ${geometry}, authentication ${auth}, ${hz} Hz, ${rovers} rovers, ${column}` });
}

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
  return { format: 'lunarsim-e54-site', version: 1, source: E54_SRC, ledger_source: E54_LEDGER, experiment: dtn.experiment, seeds: Array.isArray(dtn.seeds) ? dtn.seeds.length : dtn.seeds,   // the file lists the seed numbers
    jobs_per_seed: dtn.jobs_per_seed, reservations_per_seed: dtn.reservations_per_seed, blackout_days: dtn.blackout_days, earth_up_share: dtn.earth_up_share,
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
    replay: auth.replay || {} };
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
  for (const [name, f] of Object.entries(files)) writeFileSync(join(PUB, B99_OUT, name), f.buf);
  writeFileSync(join(PUB, B99_OUT, 'index.json'), JSON.stringify(index));
  console.log(`prepare-data: ${Object.keys(files).length} B-99 files staged to ${B99_OUT}/ (sizes and sha256 match the index)`);
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
export function lrip(key) {
  const schema = JSON.parse(readFileSync(join(ROOT, LRIP_SCHEMA), 'utf8')), golden = JSON.parse(readFileSync(join(ROOT, LRIP_GOLDEN), 'utf8'));
  const pos = golden.vectors.find(v => v.message === 'POSITION' && v.profile === 'N' && v.auth === 'mac8');
  if (!pos) throw new Error(`${LRIP_GOLDEN}: no POSITION vector for profile N with mac8`);
  const frame = schema.framing?.proximity1_frame_bytes;
  if (key === 'types') return WORDS[schema.messages.length] ?? String(schema.messages.length);
  if (key === 'packet') return num({ value: pos.bytes, unit: ' B', digits: 0, flag: 'Spec', source: `${LRIP_GOLDEN}: the POSITION vector (profile N, 8-byte MAC), before link framing and coding` });
  if (key === 'framed') {
    if (typeof frame !== 'number') throw new Error(`${LRIP_SCHEMA}: no framing.proximity1_frame_bytes`);
    return num({ value: pos.bytes + frame, unit: ' B', digits: 0, flag: 'Spec', source: `${LRIP_GOLDEN} POSITION packet plus ${LRIP_SCHEMA} framing.proximity1_frame_bytes (${frame} B)` });
  }
  throw new Error(`lrip: unknown key ${key}`);
}

// F-70b / B-103: the driving split of E53 (results/E53_bitrate.json driving_split; decisions B9): <!--@e53d:key--> with key
// parked_share, drive_hops, drive_reach, drive_p95 (busiest link, 1 Hz, driving), si_air (STATUS and INTENT also at 1 Hz:
// scheduled airtime for twenty rovers), channel (the narrow-band channel) or si_fit ("fits" / "does not fit").
let e53full = null;
export function e53d(key) {
  e53full ||= JSON.parse(readFileSync(join(ROOT, 'results', 'E53_bitrate.json'), 'utf8').replace(/\bNaN\b/g, 'null'));
  const D = e53full.driving_split, src = 'results/E53_bitrate.json: driving_split.';
  if (!D) throw new Error('results/E53_bitrate.json: no driving_split');
  const drv = D.e53_auth_20_rovers?.fleet_driving?.['1 Hz'], si = D.status_intent_at_1hz;
  const nb = Object.entries(e53full.channels_kbps).find(([k]) => /narrow/.test(k))?.[1];
  const f = (value, unit, digits, what) => num({ value, unit, digits, flag: 'Modelled', source: src + what });
  const V = {
    parked_share: () => f(100 * (1 - D.pool_driving_share), ' %', 0, 'pool_driving_share (one minus)'),
    drive_hops: () => f(drv.mean_hops_to_base, '', 2, 'e53_auth_20_rovers.fleet_driving.1 Hz.mean_hops_to_base'),
    drive_reach: () => f(100 * drv.reachable_share, ' %', 0, 'e53_auth_20_rovers.fleet_driving.1 Hz.reachable_share'),
    drive_p95: () => f(drv.busiest_link_kbps_p95, ' kbit/s', 1, 'e53_auth_20_rovers.fleet_driving.1 Hz.busiest_link_kbps_p95'),
    si_air: () => f(si.scheduled_airtime_p95_kbps.fleet, ' kbit/s', 1, 'status_intent_at_1hz.scheduled_airtime_p95_kbps.fleet'),
    channel: () => num({ value: nb, unit: ' kbit/s', digits: 0, flag: 'Assumed', source: 'results/E53_bitrate.json: channels_kbps (the narrow-band channel)' }),
    si_fit: () => (si.scheduled_airtime_p95_kbps.fleet <= nb ? 'fits' : 'does not fit'),
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
