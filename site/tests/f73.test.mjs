// F-73: /protocol/ on LRIP v0.2 (B-100). The figure decodes v0.2's vector, including the 95 % bound in the old spare
// bits, and v0.1's vectors still decode by v0.1's layout; HELLO's declaration; the rates for twenty rovers at 1 Hz,
// v0.1 beside v0.2 and in Proximity-1 frames, from results/E53_bitrate.json and results/E53_table_v02.csv; the
// driving split at v0.2 sizes (B-110). Every number from a file.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { compactLrip, lripDecode, logCode, lrip, e53, e53v1, e53air, e53v02Table } from '../lib/protocol-data.mjs';

const R = p => new URL(`../../${p}`, import.meta.url);
const J = p => JSON.parse(readFileSync(R(p), 'utf8').replace(/\bNaN\b/g, 'null'));
const plain = html => html.replace(/<span class="visually-hidden">[\s\S]*?<\/span>/g, '').replace(/<span class="flag"[^>]*>[^<]*<\/span>/g, '').replace(/<[^>]+>/g, '');
const have = existsSync(R('lunarsim/schemas/lrip-v0.2.json')) && existsSync(R('results/E53_table_v02.csv'));

test('figure 5 on v0.2: the bound in the spare bits, the declaration, v0.1 still decodes', { skip: !have && 'B-100 missing' }, () => {
  const out = compactLrip(J('lunarsim/schemas/lrip-v0.2.json'), J('data/atc/lrip/conformance-v0.2.json'), J('lunarsim/schemas/lrip-v0.1.json'), J('data/atc/lrip/conformance-v0.1.json'));
  assert.equal(out.lrip, '0.2'); assert.equal(out.version, 2);
  const L = out.layout, u = L.fields.find(f => f.name === 'u95_code');
  assert.ok(u && u.log && !L.fields.some(f => f.name === 'spare'), 'the six spare bits now carry the bound');
  assert.equal(lripDecode(out.vector.hex, L)[L.fields.indexOf(u)], out.vector.fields.u95_code);
  assert.equal(out.vector.bytes, J('results/E53_bitrate.json').lrip_v02['sizes_v0.2'].POSITION.mac8, 'POSITION did not grow');
  assert.deepEqual(Object.keys(out.hello.fields).filter(k => /frame|datum|time_scale/.test(k)), ['frame_id', 'datum_id', 'time_scale']);
  assert.equal(out.previous.version, '0.1');
  assert.equal(out.previous.position_bytes, out.vector.bytes);
  assert.deepEqual(logCode('u95 = 0.05 m x 2^(code/4), coded upward; 62: above 1.95 km; 63 unknown'), { base: 0.05, div: 4, above: 62, aboveText: '1.95 km', unknown: 63 });
});

test('problem 5: v0.1 beside v0.2 for twenty rovers at 1 Hz, and in Proximity-1 frames', { skip: !have && 'B-100 missing' }, () => {
  const F = J('results/E53_bitrate.json'), V = F.lrip_v02, txt = s => plain(s);
  assert.ok(txt(e53v1('fleet', 'on', '1.0', 20, 'busiest_link_kbps_p95', 2)).startsWith(F.h13.at_1hz_kbps_p95.toFixed(2)));
  assert.ok(txt(e53('fleet', 'on', '1.0', 20, 'busiest_link_kbps_p95', 2)).startsWith(V.h13_check_v02.at_1hz_kbps_p95.toFixed(2)));
  assert.ok(txt(e53('fleet', 'on', '1.0', 20, 'busiest_link_kbps_p95', 2, 'proximity1')).startsWith(V.framing_row.fleet_auth_1hz_20.busiest_link_kbps_p95.toFixed(2)));
  assert.ok(txt(e53air('v1')).startsWith(F.h13.airtime_1hz_scheduled_kbps.toFixed(2)));
  assert.ok(txt(e53air('v2')).startsWith(V.h13_check_v02.airtime_1hz_scheduled_kbps.toFixed(2)));
  assert.ok(txt(e53air('pf')).startsWith(V.framing_row.airtime_1hz_scheduled_kbps.toFixed(2)));
  assert.equal(e53('fleet', 'on', '1.0', 20, 'fits_nb_scheduled_p95', null, 'proximity1'), V.framing_row.fleet_auth_1hz_20.fits_nb_scheduled_p95 ? 'fits' : 'does not fit');
  assert.equal(e53('fleet', 'on', '1.0', 20, 'fits_nb_slotted_aloha_p95', null, 'proximity1'), V.framing_row.fleet_auth_1hz_20.fits_nb_slotted_aloha_p95 ? 'fits' : 'does not fit');
  assert.match(e53air('v2'), /a calculation on a traffic model/);
  assert.throws(() => e53air('nope'), /unknown/);
  assert.equal(e53v02Table().rows.length, readFileSync(R('results/E53_table_v02.csv'), 'utf8').trim().split(/\r?\n/).length - 1);
});

test('problem 5 text: version, declaration, coverage, driving split labelled v0.1', { skip: !have && 'B-100 missing' }, () => {
  const S = J('lunarsim/schemas/lrip-v0.2.json'), V = J('results/E53_bitrate.json').lrip_v02;
  assert.equal(lrip('version'), '0.2');
  assert.equal(lrip('sent'), 'eleven'); assert.equal(S.traffic_model_coverage.sent_by_E53.length, 11);
  assert.ok(plain(lrip('hello')).startsWith(String(V.sizes_moved.HELLO['v0.2'])));
  assert.ok(plain(lrip('hello_v1')).startsWith(String(V.sizes_moved.HELLO['v0.1'])));
  assert.ok(plain(lrip('hello_every')).startsWith(String(S.messages.find(m => m.name === 'HELLO').declaration_interval_s)));
  assert.match(lrip('not_sent'), /capability manifest/);
  const html = readFileSync(new URL('../protocol/index.html', import.meta.url), 'utf8');
  for (const k of ['e53v1:fleet:on:1.0:20:busiest_link_kbps_p95', 'e53:fleet:on:1.0:20:busiest_link_kbps_p95', 'e53pf:fleet:on:1.0:20:busiest_link_kbps_p95', 'e53air:v1', 'e53air:v2', 'e53air:pf', 'lrip:hello_every'])
    assert.ok(html.includes(`<!--@${k}`), k);
  assert.doesNotMatch(html, /still a v0\.1 figure/);
  for (const k of ['drive_air', 'drive_air_pf', 'drive_aloha', 'drive_aloha_pf', 'si_src', 'si_src_pf', 'si_fit']) assert.ok(html.includes(`<!--@e53d:${k}-->`), k);
  assert.match(html, /no\s+covariance is carried/);
  assert.match(html, /Conformance vectors test the codec, not a radio/);
  assert.doesNotMatch(html, /LRIP v0\.1's (position report does not carry|conformance vector)/);
});

test('problem 5: the driving split at v0.2 sizes (B-110)', { skip: !have && 'B-100 missing' }, async () => {
  const { e53d } = await import('../lib/protocol-data.mjs');
  const D = J('results/E53_bitrate.json').lrip_v02.driving_split, d = fr => D.e53_auth_20_rovers[fr].fleet_driving['1 Hz'];
  assert.ok(plain(e53d('drive_air')).startsWith(d('lrip').scheduled_airtime_p95_kbps.toFixed(2)));
  assert.ok(plain(e53d('drive_air_pf')).startsWith(d('proximity1').scheduled_airtime_p95_kbps.toFixed(2)));
  assert.ok(plain(e53d('drive_aloha')).startsWith(d('lrip').slotted_aloha_airtime_p95_kbps.toFixed(1)));
  assert.ok(plain(e53d('drive_aloha_pf')).startsWith(d('proximity1').slotted_aloha_airtime_p95_kbps.toFixed(1)));
  assert.ok(plain(e53d('si_src')).startsWith(D.status_intent_at_1hz.lrip.sources_20_rovers_kbps.toFixed(2)));
  assert.ok(plain(e53d('si_src_pf')).startsWith((Math.round(D.status_intent_at_1hz.proximity1.sources_20_rovers_kbps * 100) / 100).toFixed(2)));   // 25.985 shows as 25.99
  assert.equal(d('lrip').mean_hops_to_base, d('proximity1').mean_hops_to_base, 'hops do not depend on framing');
  assert.match(e53d('drive_air'), /lrip_v02\.driving_split/);
});
