// F-56: /protocol/ figures 3 and 5 and problem 5's text read BACKEND's files at build time. LRIP: the golden POSITION
// packet, decoded by the schema's layout, gives back the vector's own field values (so the byte-by-byte figure shows
// exactly what the reference encoder sends). E51: the lunar rows for both oscillators, with H11. E53: one row per
// geometry, authentication, rate and fleet size; "fits" columns come back as words.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { lripLayout, lripDecode, compactLrip, compactE51, e53 } from '../lib/protocol-data.mjs';

const R = p => new URL(`../../${p}`, import.meta.url);
const J = p => JSON.parse(readFileSync(R(p), 'utf8').replace(/\bNaN\b/g, 'null'));
const haveLrip = existsSync(R('lunarsim/schemas/lrip-v0.2.json')) && existsSync(R('data/atc/lrip/conformance-v0.2.json'));   // F-73: v0.2

test('LRIP figure: the golden POSITION packet decodes to its own field values', { skip: !haveLrip && 'LRIP files missing' }, () => {
  const schema = J('lunarsim/schemas/lrip-v0.2.json'), golden = J('data/atc/lrip/conformance-v0.2.json');
  const out = compactLrip(schema, golden), L = out.layout, v = out.vector;
  assert.equal(L.bits, v.bytes * 8);
  const raw = lripDecode(v.hex, L), at = name => raw[L.fields.findIndex(f => f.name === name)];
  for (const f of L.fields.filter(x => x.part === 'pay' && x.name !== 'spare')) {
    const got = f.type === 'flag' ? Boolean(at(f.name)) : +(at(f.name) * f.scale).toFixed(6);
    assert.equal(got, v.fields[f.name], `${f.name}`);
  }
  assert.equal(at('sender_id'), v.sender);
  assert.equal(at('seq'), v.seq);
  assert.equal(at('t_valid') * L.fields.find(f => f.name === 't_valid').scale, v.t_valid_s);
  assert.equal(at('apid'), 0x500 + L.id);
  assert.equal(at('data_length'), v.bytes - 6 - 1);
  assert.equal(at('mac8').length, 64);
  assert.deepEqual(out.sizes.map(s => s.bytes).sort((a, b) => a - b), golden.vectors.filter(x => x.message === 'POSITION').map(x => x.bytes).sort((a, b) => a - b));
  assert.equal(out.sizes.length, 3, 'unauthenticated, 8-byte MAC, broadband profile');
});

test('LRIP decoder: signed fields and a size mismatch', () => {
  const L = { bits: 16, fields: [{ name: 'a', bits: 8, type: 'int' }, { name: 'b', bits: 8, type: 'uint' }] };
  assert.deepEqual(lripDecode('ff7f', L), [-1, 127]);
  assert.throws(() => lripDecode('ff', L), /bits/);
  assert.throws(() => lripLayout({ framing: {}, messages: [] }, 'NOPE'), /no message/);
});

test('E51 for figure 3: lunar rows for both oscillators, H11 kept', { skip: !existsSync(R('results/E51_clocks.json')) && 'E51 missing' }, () => {
  const out = compactE51(J('results/E51_clocks.json'));
  for (const c of ['crystal', 'csac']) assert.ok(out.rows.filter(r => r.class === c).length >= 6, c);
  assert.ok(out.rows.every(r => r.conflict_pairs_checked > 0 && r.one_way_m_p95 >= r.one_way_m_median));
  assert.equal(typeof out.h11.supported, 'boolean');
  assert.ok(out.guard_s > 0 && out.uwb_sigma_m > 0);
});

test('E53 in problem 5: numbers flagged, fits as words, one row only', { skip: !existsSync(R('data/atc/protocol/e53_bitrate.json')) && 'B-99 missing' }, () => {
  assert.match(e53('fleet', 'on', '1.0', 20, 'busiest_link_kbps_p95'), /data-flag="Modelled".*E53_table_v02\.csv/);   // F-73: v0.2
  assert.match(e53('fleet', 'on', '1.0', 20, 'fits_nb_scheduled_p95'), /^(fits|does not fit)$/);
  assert.throws(() => e53('nowhere', 'on', '1.0', 20, 'busiest_link_kbps_p95'), /0 rows/);
  assert.throws(() => e53('fleet', 'on', '1.0', 20, 'no_such_column'), /no column/);
});

test('E52 for figure 2 and problem 2: rows, assumed inputs, H12, the text hook', { skip: !existsSync(R('results/E52_map.json')) && 'E52 missing' }, async () => {
  const { compactE52, e52 } = await import('../lib/protocol-data.mjs');
  const out = compactE52(J('results/E52_map.json'));
  assert.ok(out.route_tiles > 0 && out.full_resend_bytes > 1e6);
  for (const k of ['hazards_per_day', 'hidden_share']) assert.ok(out.assumed.includes(k), k);
  const rates = new Set(out.rows.map(r => r.rate_kbps)), outs = new Set(out.rows.map(r => r.out_h));
  assert.equal(out.rows.length, rates.size * outs.size * 2);
  // hazards first is never later than oldest first, and never later than "everything in"
  for (const r of out.rows.filter(x => x.order === 'hazards_first')) {
    const o = out.rows.find(x => x.order === 'oldest_first' && x.out_h === r.out_h && x.rate_kbps === r.rate_kbps);
    assert.ok(r.t_hazards_current_s <= o.t_hazards_current_s && r.t_hazards_current_s <= r.t_all_s, `${r.out_h} h ${r.rate_kbps} kbit/s`);
  }
  assert.match(e52('hazards_per_day'), /data-flag="Assumed"/);
  assert.match(e52('24_16_hazards_first_bytes_mean'), /> (kB|MB)<.*data-flag="Modelled"/);
  assert.throws(() => e52('nonsense'), /unknown key/);
  assert.throws(() => e52('5_16_hazards_first_bytes_mean'), /no bytes_mean/);
});

test('E54 for problems 4 and 6: every loss x protocol, the ledger lifetimes, H14', { skip: !existsSync(R('results/E54_dtn.json')) && 'E54 missing' }, async () => {
  const { compactE54 } = await import('../lib/protocol-data.mjs');
  const out = compactE54(J('results/E54_dtn.json'), J('results/E54_ledger.json'));
  const losses = new Set(out.rows.map(r => r.loss));
  for (const l of losses) for (const p of ['drop_retry', 'sf', 'sf_ll']) assert.ok(out.rows.find(r => r.loss === l && r.protocol === p), `${l} ${p}`);
  assert.equal(typeof out.h14.supported, 'boolean');
  assert.ok(out.ledger.longest_earth_down_d > 14);
  // a lifetime longer than the longest stretch without Earth loses nothing under store and forward
  for (const r of out.ledger.rows.filter(x => x.protocol === 'sf' && x.lifetime_d > out.ledger.longest_earth_down_d)) assert.equal(r.lost, 0, `${r.lifetime_d} d`);
  assert.throws(() => compactE54({ rows: [] }, { rows: [] }), /h14/);
});

test('E52 and E54: seeds is a count (the files may list the seed numbers)', { skip: !existsSync(R('results/E54_dtn.json')) && 'E54 missing' }, async () => {
  const { compactE52, compactE54 } = await import('../lib/protocol-data.mjs');
  assert.equal(compactE54(J('results/E54_dtn.json'), J('results/E54_ledger.json')).seeds, 30);
  assert.equal(compactE52(J('results/E52_map.json')).seeds, 30);
});

test('E55 for problem 7: detectors on test and out of distribution, consensus cells, the text hook', { skip: !existsSync(R('results/E55_integrity.json')) && 'E55 missing' }, async () => {
  const { compactE55, e55 } = await import('../lib/protocol-data.mjs');
  const out = compactE55(J('results/E55_integrity.json'));
  for (const set of ['test', 'ood']) for (const k of ['3of5@0.001', 'single@0.001', 'e56_chi2_step', 'e56_net']) assert.ok(out.detectors[set][k], `${set} ${k}`);
  // the report's reading: persistence cuts the false alarms of the same threshold, and out of distribution every fixed threshold rises
  const t = out.detectors.test, o = out.detectors.ood;
  assert.ok(t['3of5@0.001'].fa < 1 && t['single@0.001'].fa > 10 * t['3of5@0.001'].fa);
  assert.ok(o['3of5@0.001'].fa > 10 * t['3of5@0.001'].fa && o['single@0.001'].fa > t['single@0.001'].fa);
  // with F at least f the trimmed mean is safe in every cell; with or without the mast
  assert.ok(out.consensus.some(c => c.mast) && out.consensus.some(c => !c.mast));
  for (const c of out.consensus.filter(x => x.F >= x.f)) assert.equal(c.safe, 1, `${c.geometry} N ${c.N} f ${c.f} F ${c.F} mast ${c.mast}`);
  assert.ok(out.forgery['8'].accepted > 0 && out.forgery['8'].bound > 0);
  assert.match(e55('fa_test_3of5@0.001'), /data-flag="Modelled"/);
  assert.match(e55('agreement_max'), / %</);
  assert.throws(() => e55('fa_test_nope'), /no detector/);
  assert.throws(() => e55('what'), /unknown key/);
});

test('E53 "fits" rule on the B-99 file gives the same answers as results/E53_table.csv, row by row', { skip: !(existsSync(R('results/E53_table.csv')) && existsSync(R('data/atc/protocol/e53_bitrate.json'))) && 'E53 files missing' }, async () => {
  const { e53Fits } = await import('../lib/protocol-data.mjs');
  const D = J('data/atc/protocol/e53_bitrate.json'), c = k => D.columns.indexOf(k);
  const [head, ...lines] = readFileSync(R('results/E53_table.csv'), 'utf8').trim().split(/\r?\n/), keys = head.split(',');
  let n = 0;
  for (const l of lines) {
    const r = Object.fromEntries(l.split(',').map((v, i) => [keys[i], v]));
    const row = D.rows.find(q => q[c('geometry')] === r.geometry && q[c('auth')] === r.auth && +q[c('position_hz')] === +r.position_hz && +q[c('rovers')] === +r.rovers);
    if (!row) continue;
    for (const [band, access] of [['nb', 'scheduled'], ['nb', 'slotted_aloha'], ['bb', 'scheduled'], ['bb', 'slotted_aloha']]) {
      const k = `fits_${band}_${access}_p95`; if (!(k in r)) continue;
      assert.equal(e53Fits(D, row, band, access), r[k] === 'True', `${r.geometry} ${r.auth} ${r.position_hz} Hz ${r.rovers}: ${k}`); n++;
    }
  }
  assert.ok(n > 100, `only ${n} comparisons`);
});

test('F-70 hooks: the fix-stop cost, the clock-guard observation, the LRIP sizes', async () => {
  const { e50b, e51, lrip } = await import('../lib/protocol-data.mjs');
  if (existsSync(R('results/E50b_summary.json'))) {
    const D = J('results/E50b_summary.json').metrics.delay_mean_h;
    assert.ok(D.diff_ci95_bootstrap[0] > 0, 'the interval stays above zero');
    assert.match(e50b('delay_diff'), /data-flag="Modelled"/);
    assert.match(e50b('stop_s'), /data-flag="Assumed"/);
    assert.throws(() => e50b('nope'), /unknown key/);
  }
  if (existsSync(R('results/E51_clocks.json'))) {
    assert.match(e51('guard_pairs'), /reservation pairs/);
    assert.match(e51('guard_max_offset'), / s</);
  }
  if (haveLrip) {
    assert.equal(lrip('types'), 'fifteen');
    assert.match(lrip('packet'), />41</);
    assert.match(lrip('framed'), />53</);
  }
});

test('F-70b hooks: the driving split (B-103) and the curved-Moon radio (B-104)', async () => {
  const { e53d, b104 } = await import('../lib/protocol-data.mjs');
  if (existsSync(R('results/E53_bitrate.json')) && J('results/E53_bitrate.json').driving_split) {
    const D = J('results/E53_bitrate.json').driving_split;
    assert.match(e53d('drive_hops'), /data-flag="Modelled"/);
    const S2 = J('results/E53_bitrate.json').lrip_v02.driving_split.status_intent_at_1hz, air = ['lrip', 'proximity1'].flatMap(f => Object.values(S2[f].busiest_link_20_rovers).map(x => x.scheduled_airtime_p95_kbps));
    assert.equal(e53d('si_fit'), air.every(a => a > 16) ? 'is above' : 'is within');   // F-73: v0.2 (B-110), every case
    assert.throws(() => e53d('nope'), /unknown key/);
  }
  if (existsSync(R('results/E48_sizing.json')) && J('results/E48_sizing.json').revision_b104) {
    const W = J('results/E48_sizing.json').revision_b104.per_class.LTV1.worst_hop;
    assert.ok(W.kbps.spherical_ground < W.kbps.flat_ground, 'the curved Moon costs rate');
    assert.match(b104('rate_sph'), /kbit\/s/);
    assert.throws(() => b104('nope'), /unknown key/);
  }
});
