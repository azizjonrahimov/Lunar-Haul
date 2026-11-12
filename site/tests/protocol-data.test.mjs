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
const haveLrip = existsSync(R('lunarsim/schemas/lrip-v0.1.json')) && existsSync(R('data/atc/lrip/conformance-v0.1.json'));

test('LRIP figure: the golden POSITION packet decodes to its own field values', { skip: !haveLrip && 'LRIP files missing' }, () => {
  const schema = J('lunarsim/schemas/lrip-v0.1.json'), golden = J('data/atc/lrip/conformance-v0.1.json');
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
  assert.deepEqual(out.sizes.map(s => s.bytes).sort((a, b) => a - b), [27, 41, 52]);
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

test('E53 in problem 5: numbers flagged, fits as words, one row only', { skip: !existsSync(R('results/E53_table.csv')) && 'E53 missing' }, () => {
  assert.match(e53('fleet', 'on', '1.0', 20, 'one_hop_sum_kbps'), /data-flag="Modelled".*E53_table\.csv/);
  assert.match(e53('fleet', 'on', '1.0', 20, 'fits_nb_scheduled_p95'), /^(fits|does not fit)$/);
  assert.throws(() => e53('nowhere', 'on', '1.0', 20, 'one_hop_sum_kbps'), /0 rows/);
  assert.throws(() => e53('fleet', 'on', '1.0', 20, 'no_such_column'), /no column/);
});
