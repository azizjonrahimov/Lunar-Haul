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
  for (const r of rows) assert.ok(['held', 'partly', 'not'].includes(r.outcome), r.id);
  const html = familyTable();
  for (const r of rows) assert.match(html, new RegExp(`<th scope="row">${r.id}</th><td[^>]*><span class="r-out r-out-${r.outcome}">`), r.id);
  // a Holm decision wins over the text; clauses decide "in part"
  assert.equal(outcomeOf({ holm: { 'rejected_at_0.05': false }, decision: 'supported' }), 'not');
  assert.equal(outcomeOf({ clauses: { a: { supported: true }, b: { supported: false } } }), 'partly');
  assert.equal(outcomeOf({ decision: 'supported: every draw' }), 'held');
  assert.throws(() => outcomeOf({}), /no outcome/);
});
