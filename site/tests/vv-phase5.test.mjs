// F-55: the verification page's reader for results/vv_phase5.json (site/src/verify/phase5.js) on a sample in the
// format agreed with BACKEND on 27 Oct (lunarsim-vv-phase5 v1, optional "run"; sub-cases as rows D3a, D3b).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { read, fmtNum, tolText, FORMAT } from '../src/verify/phase5.js';

const row = (o) => ({ component: 'engine', name: 'x', kind: 'V', status: 'pass', tolerance: { type: 'rel', value: 1e-9 }, measured: { value: 1, unit: '' }, source: 'plan', ...o });
const doc = {
  format: FORMAT, version: 1, generated: '2026-10-28T10:00:00Z', commit: 'abcdef0123',
  components: [{ id: 'engine', label: 'Dispatch engine' }],
  checks: [
    row({ id: 'D1', name: "Little's law", measured: { value: 0.0000000004, unit: '' }, run: { seeds: [1, 2, 3], wall_s: 2.5 } }),
    row({ id: 'D3a', name: 'P-K at 30 %', tolerance: { type: 'rel', value: 0.02 }, measured: { value: 1.01, unit: 'h', ci95: [0.99, 1.03], n: 30 } }),
    row({ id: 'D3b', name: 'P-K at 60 %', status: 'fail' }),
    row({ id: 'S1', component: 'safety', name: 'separation', tolerance: { type: 'zero_events' }, zero_events: { exposure: 1200000, unit: 'encounters', upper95: 2.5e-6 }, measured: { value: 0, unit: 'violations' } }),
    row({ id: 'E2', component: 'energy', name: 'night drive', kind: 'Cal' }),
    row({ id: 'L1', component: 'learned', name: 'policy parity', status: 'not_run', measured: undefined }),
    row({ id: 'R9', component: 'radio', name: 'bad row', kind: 'X', source: '' }),
  ],
};

test('reads the agreed format: groups in page order, counts, sub-cases as rows', () => {
  const r = read(doc);
  assert.equal(r.ok, true);
  assert.deepEqual(r.groups.map(g => g.id), ['engine', 'radio', 'safety', 'energy', 'learned']);
  const eng = r.groups[0];
  assert.deepEqual(eng.rows.map(x => x.id), ['D1', 'D3a', 'D3b']);
  assert.equal(eng.pass, 2); assert.equal(eng.fail, 1);
  assert.deepEqual(r.totals, { rows: 7, pass: 4, fail: 1, notRun: 1, errors: 1 });
  assert.equal(eng.rows[0].run, '3 seeds, 2.5 s');
  assert.match(eng.rows[1].measured, /95 % CI 0\.99 to 1\.03\), n = 30/);
});

test('calibration rows, zero-event rows, not-run rows and broken rows', () => {
  const r = read(doc), all = r.groups.flatMap(g => g.rows), by = id => all.find(x => x.id === id);
  assert.equal(by('E2').calibration, true); assert.equal(by('E2').kindText, 'reproduces calibration data');
  assert.match(by('S1').tolerance, /zero events; exposure 1,200,000 encounters, 95 % upper bound 2\.5e-6/);
  assert.equal(by('L1').status, 'not_run'); assert.equal(by('L1').measured, 'not run yet');
  assert.equal(by('R9').status, 'error');   // a row that breaks the schema is never a pass
  assert.match(by('R9').error, /kind "X".*source/);
});

test('wrong format or version is refused', () => {
  assert.equal(read({ format: 'other' }).ok, false);
  assert.match(read({ ...doc, version: 2 }).error, /version 2/);
  assert.equal(read(null).ok, false);
});

test('number and tolerance wording', () => {
  assert.equal(fmtNum(1e-9), '1e-9');
  assert.equal(fmtNum(1234.5, 'kg'), '1,234.5 kg');
  assert.equal(fmtNum(null), '–');
  assert.equal(tolText({ type: 'rel', value: 0.02 }), '≤ 0.02 relative');
  assert.equal(tolText({ type: 'exact' }), 'exact');
});
