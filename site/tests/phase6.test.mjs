// F-69: Phase 6 on /verification/ and /results/. The recorded checks read with the Phase 5 reader and the Phase 6 groups;
// the lead names G1 from the file; the hypothesis table gives every outcome, including the ones that failed.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { read, COMPONENTS_6 } from '../src/verify/phase5.js';
import { vv6, familyRows, familyTable, outcomeOf } from '../lib/phase6.mjs';

const R = p => new URL(`../../${p}`, import.meta.url);
const J = p => JSON.parse(readFileSync(R(p), 'utf8'));

test('Phase 6 checks: every row reads, grouped P, M, C, G, the summary agrees', { skip: !existsSync(R('results/vv_phase6.json')) && 'vv_phase6 missing' }, () => {
  const doc = read(J('results/vv_phase6.json'), COMPONENTS_6);
  assert.ok(doc.ok, doc.error);
  assert.deepEqual(doc.groups.map(g => g.id), ['P', 'M', 'C', 'G']);
  assert.ok(!doc.groups.some(g => /^Other/.test(g.label)));
  assert.equal(doc.totals.errors, 0);
  assert.equal(doc.mismatch, '');
  assert.equal(doc.totals.rows, J('results/vv_phase6.json').summary.rows);
  assert.match(vv6('lead'), /G1/);
  assert.match(vv6('lead'), /of \d+ summary values differ/);
});

test('Phase 6 hypotheses: outcomes from the file, failures shown like successes', { skip: !existsSync(R('results/phase6_family.json')) && 'family missing' }, () => {
  const F = J('results/phase6_family.json'), rows = familyRows(F);
  assert.equal(rows.length, Object.keys(F.hypotheses).length);
  for (const r of rows) assert.ok(['held', 'partly', 'not', 'reading', 'calc', 'first'].includes(r.outcome), r.id);
  // F-70: the referee round's decisions over the file's verdicts
  const by = Object.fromEntries(rows.map(r => [r.id, r]));
  assert.equal(by.H9.label, 'H9′'); assert.equal(by.H10.label, 'H10′');
  assert.equal(by.H9.outcome, 'reading');
  assert.ok(by.H9.parts.some(([n, o]) => /near the base/.test(n) && o === 'reading'));
  assert.equal(by.H13.outcome, 'calc'); assert.equal(by.H13.kind, 'design calculation');
  assert.equal(by.H14.outcome, 'first');
  assert.deepEqual(by.H14.parts.map(([, o]) => o), ['held', 'untestable']);
  assert.equal(by.H10.outcome, 'not');
  // F-70c: H10′'s clauses with their own tests; the growing-gap clause read at every fleet size in the file (4x and 8x)
  assert.deepEqual(by.H10.parts.map(([, o]) => o), ['held', 'not', 'not']);
  const gap = by.H10.parts.find(([n]) => /gap grows/.test(n));
  for (const k of Object.keys(F.hypotheses.H10.clauses[gap[0]]).filter(k => /^gap_\d+x_h$/.test(k))) assert.match(gap[2], new RegExp(` at ${k.slice(4, -2)}( |,|$)`), k);
  assert.doesNotMatch(familyTable(), /Still to come/);
  const html = familyTable();
  for (const r of rows) assert.match(html, new RegExp(`<th scope="row">${r.label}</th><td[^>]*><span class="r-out r-out-${r.outcome}">`), r.id);
  assert.doesNotMatch(html, /which hypotheses held/);
  // a Holm decision wins over the text; clauses decide "in part"
  assert.equal(outcomeOf({ holm: { 'rejected_at_0.05': false }, decision: 'supported' }), 'not');
  assert.equal(outcomeOf({ clauses: { a: { supported: true }, b: { supported: false } } }), 'partly');
  assert.equal(outcomeOf({ decision: 'supported: every draw' }), 'held');
  assert.throws(() => outcomeOf({}), /no outcome/);
});
