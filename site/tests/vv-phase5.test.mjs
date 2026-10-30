// F-55: the verification page's reader for results/vv_phase5.json (site/src/verify/phase5.js) on a sample in
// BACKEND's names (lunarsim/vv5.py, agreed 30 Oct: version 1, {generated, commit, summary, rows}; id + sub per row).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { read, fmtNum, tolText, errorOf } from '../src/verify/phase5.js';

const row = (o) => {
  const r = { id: 'D1', sub: '', name: 'x', reference: 1, simulated: 1, tolerance: 1e-9, mode: 'rel', unit: '', basis: 'b', source: 's', skipped: '',
    technique: 'analytic', factor: 'code verification', kind: 'V', priority: 'P1', papers: ['P1'], ci99: null, bias_flag: null, exposure: null, runtime_s: 0.5, ...o };
  if (!('passed' in o)) r.passed = !r.skipped && errorOf(r) <= r.tolerance;
  r.error = errorOf(r); r.rel_error = Math.abs(r.simulated - r.reference) / Math.max(Math.abs(r.reference), 1e-12);
  return r;
};
const rows = [
  row({ id: 'D2', sub: 'rho 0.3', name: 'P-K mean wait', reference: 1, simulated: 1.01, tolerance: 0.02, unit: 'h', ci99: [0.99, 1.03], bias_flag: false }),
  row({ id: 'D2', sub: 'rho 0.6', name: 'P-K mean wait', reference: 1, simulated: 1.015, tolerance: 0.02, unit: 'h', ci99: [1.005, 1.03], bias_flag: true }),
  row({ id: 'D9', name: 'Hungarian vs brute force', reference: 5, simulated: 6, tolerance: 1e-9 }),
  row({ id: 'S1', name: 'separation', reference: 0, simulated: 0, tolerance: 0, mode: 'abs', unit: 'violations', exposure: { n: 1200000, unit: 'encounters', upper95: 2.5e-6 } }),
  row({ id: 'E3', sub: 'flat 700 kg', name: 'traction', kind: 'Cal' }),
  row({ id: 'L1', name: 'policy parity', simulated: NaN, skipped: 'needs the GPU build' }),
  row({ id: 'R1', name: 'bad row', kind: 'X' }),
  row({ id: 'R2', name: 'wrong flag', reference: 10, simulated: 12, tolerance: 0.01, passed: true }),
].map(r => (Number.isNaN(r.simulated) ? { ...r, simulated: null, error: null, rel_error: null } : r));
const doc = { version: 1, generated: '2026-10-30T10:00:00Z', commit: 'abcdef0123', summary: { rows: 8, passed: 4, failed: 1, skipped: 1, bias_flags: 1 }, rows };

test('reads BACKEND\'s names: groups by id letter in page order, sub-cases as rows, counts', () => {
  const r = read(doc);
  assert.equal(r.ok, true);
  assert.deepEqual(r.groups.map(g => g.id), ['D', 'R', 'S', 'E', 'L']);
  const eng = r.groups[0];
  assert.deepEqual(eng.rows.map(x => x.key), ['D2 · rho 0.3', 'D2 · rho 0.6', 'D9']);
  assert.equal(eng.pass, 2); assert.equal(eng.fail, 1); assert.equal(eng.bias, 1);
  assert.deepEqual(r.totals, { rows: 8, pass: 4, fail: 1, notRun: 1, errors: 2, bias: 1 });
  assert.match(eng.rows[1].ci, /99 % batch-means interval 1\.005 to 1\.03/);
  assert.equal(eng.rows[1].bias, true); assert.equal(eng.rows[1].status, 'pass');   // a bias flag is recorded, not a failure
});

test('calibration, zero-event, skipped and broken rows', () => {
  const r = read(doc), all = r.groups.flatMap(g => g.rows), by = k => all.find(x => x.key === k);
  assert.equal(by('E3 · flat 700 kg').calibration, true);
  assert.match(by('S1').tolerance, /^exact; zero events in 1,200,000 encounters, 95 % upper bound 2\.5e-6/);
  assert.equal(by('S1').tolFrom, '');
  assert.equal(read({ ...doc, rows: [{ ...rows[0], tolerance_source: 'research_notes/Lunar ATC/verification_plan.md section 3, row D2' }] }).groups[0].rows[0].tolFrom, 'verification plan section 3, row D2');
  assert.equal(by('L1').status, 'not_run'); assert.equal(by('L1').reason, 'needs the GPU build');
  assert.equal(by('R1').status, 'error'); assert.match(by('R1').error, /kind "X"/);
  assert.equal(by('R2').status, 'error'); assert.match(by('R2').error, /"passed" is true but the error 0\.2 is outside/);
});

test('the summary is checked against the rows; duplicates and wrong versions are refused', () => {
  const clean = rows.filter(x => !['R1', 'R2'].includes(x.id)), ok = { ...doc, rows: clean, summary: { rows: 6, passed: 4, failed: 1, skipped: 1, bias_flags: 1 } };
  assert.equal(read(ok).mismatch, '');
  assert.match(read({ ...ok, summary: { ...ok.summary, passed: 5 } }).mismatch, /passed 5 \(rows give 4\)/);
  const dup = read({ ...ok, rows: [...clean, clean[0]] });
  assert.match(dup.groups[0].rows.at(-1).error, /id \+ sub repeated/);
  assert.match(read({ ...doc, version: 2 }).error, /version 2/);
  assert.equal(read({ checks: [] }).ok, false);
  assert.equal(read(null).ok, false);
});

test('number and tolerance wording', () => {
  assert.equal(fmtNum(1e-9), '1e-9');
  assert.equal(fmtNum(1234.5, 'kg'), '1,234.5 kg');
  assert.equal(fmtNum(null), '–');
  assert.equal(tolText({ tolerance: 0.02, mode: 'rel' }), '≤ 0.02 relative');
  assert.equal(tolText({ tolerance: 5, mode: 'abs', unit: 'm' }), '≤ 5 m');
  assert.equal(tolText({ tolerance: 0, mode: 'abs' }), 'exact');
});
