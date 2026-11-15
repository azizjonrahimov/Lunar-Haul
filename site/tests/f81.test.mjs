// F-81: fixes from the review of phase6-followup. A "before" sentence takes the one superseded_* block of its file (none,
// or two after a second supersession, stops the build); a reading with no seeds is not judged, never "fails"; the
// /results/ correction note names a cause per value from the files' own reasons; dateNum stops on a bad date or flag.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { supersededBlock, readingVerdict } from '../src/components/results-file.js';
import { dateNum } from '../src/components/date-num.js';
import { superseded } from '../lib/protocol-data.mjs';
import { nearBase, nearLarger, familyWas } from '../lib/phase6.mjs';
import { robotRound } from '../src/atc/e48-robot.js';

const J = p => JSON.parse(readFileSync(new URL(`../../${p}`, import.meta.url), 'utf8').replace(/([:[,]\s*)-?(NaN|Infinity)\b/g, '$1null'));
const plain = html => html.replace(/<span class="visually-hidden">[\s\S]*?<\/span>/g, '').replace(/<span class="flag"[^>]*>[^<]*<\/span>/g, '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ');
const supKey = doc => Object.keys(doc).find(k => /^superseded_/.test(k));
// a second supersession: the same block again under a later key; and a file with no block at all
const twice = doc => { const X = structuredClone(doc), k = supKey(X); X[k.replace(/\d{4}-\d{2}-\d{2}/, '2026-12-01')] = structuredClone(X[k]); return X; };
const none = doc => { const X = structuredClone(doc); for (const k of Object.keys(X)) if (/^superseded_/.test(k)) delete X[k]; return X; };

test('supersededBlock: exactly one block holding the field, else the build stops naming the file and the keys', () => {
  const D = { a: 1, superseded_2026_x: { rows: [1], superseded_on: '2026-11-13' }, superseded_2026_y: { other: 1 } };
  const two = { ...D, superseded_2026_z: { rows: [2] } };
  assert.equal(supersededBlock(D, 'f.json', b => 'rows' in b).key, 'superseded_2026_x');
  assert.throws(() => supersededBlock(two, 'f.json', b => 'rows' in b), /f\.json: 2 superseded_\* blocks .*\(superseded_2026_x, superseded_2026_z\)/);
  assert.throws(() => supersededBlock({ a: 1 }, 'f.json', b => 'rows' in b), /f\.json: no superseded_\* block .*\(the file has none\)/);
  assert.throws(() => supersededBlock(D, 'f.json', b => 'nope' in b), /f\.json: no superseded_\* block .*superseded_2026_x, superseded_2026_y/);
  assert.equal(supersededBlock(two, 'f.json', b => 'rows' in b, 'superseded_2026_z').doc.rows[0], 2, 'an explicit key picks one');
  assert.throws(() => superseded(two, 'f.json', 'rows'), /2 superseded_\* blocks/, 'the /protocol/ reader');
});

test('/results/ note and /atc/ bid: a missing block or a second supersession stops the build', () => {
  const F = J('results/phase6_family.json');
  assert.ok(familyWas(F).includes('r-fam-was'));
  assert.throws(() => familyWas(none(F)), /phase6_family\.json: no superseded_\* block/);
  assert.throws(() => familyWas(twice(F)), /phase6_family\.json: 2 superseded_\* blocks/);
  const S = J('results/E48_sizing.json');
  assert.ok(robotRound(S).was);
  assert.throws(() => robotRound(none(S)), /E48_sizing\.json: no superseded_\* block/);
  assert.throws(() => robotRound(twice(S)), /E48_sizing\.json: 2 superseded_\* blocks/);
});

test('a reading with no seeds is not judged: never "fails", never "held", and the sentence no longer says "every reading"', () => {
  assert.equal(readingVerdict({ seeds_with_steps: 0, seeds_inside_budget: 0 }), 'not judged');
  assert.equal(readingVerdict({ seeds_with_steps: 5, seeds_inside_budget: 0 }), 'fails');
  assert.equal(readingVerdict({ seeds_with_steps: 5, seeds_inside_budget: 5 }), 'holds');
  assert.equal(readingVerdict({ seeds_with_steps: 5, seeds_inside_budget: 2 }), 'mixed');
  const N = nearBase(), D = J('results/E50_near_base.json');
  assert.match(plain(nearLarger(N, D)), /every reading gives the same verdict/);
  // a synthetic reading: at 8x no seed drove inside "within 1 km of the base mast"
  const X = structuredClone(D), r = Object.keys(X.readings).find(k => /1 km/.test(X.readings[k]));
  X.multiples['8'].sets['dr+ranging'][r] = { ...X.multiples['8'].sets['dr+ranging'][r], seeds_with_steps: 0, seeds_inside_budget: 0, in_p95_m_mean: null };
  const t = plain(nearLarger(N, X));
  assert.doesNotMatch(t, /every reading gives the same verdict/);
  assert.match(t, /every reading judged gives the verdict of today’s fleet \(“within 1 km of the base mast” at eight times is not judged: no seed has steps inside it\)/);
  assert.match(t, /\(10 and 5 seeds\)/, 'the seeds are the seeds run, not the seeds with steps');
  // a named reading not judged at 8x: its value says so instead of a number
  const Y = structuredClone(D);
  Y.multiples['8'].sets['dr+ranging'][N.reg.r] = { ...Y.multiples['8'].sets['dr+ranging'][N.reg.r], seeds_with_steps: 0, seeds_inside_budget: 0, in_p95_m_mean: null };
  assert.match(plain(nearLarger(N, Y)), / and not judged under the registered wording/);
  // a judged reading whose verdict changes still stops the build
  const Z = structuredClone(D), z = Z.multiples['8'].sets['dr+ranging'][N.reg.r];
  z.seeds_inside_budget = z.seeds_with_steps;
  assert.throws(() => nearLarger(N, Z), new RegExp(`at 8x the reading ${N.reg.r} holds, at 1x it fails`));
});

test('/results/ note: the cause of each earlier value comes from the reason of the file it comes from', () => {
  const F = J('results/phase6_family.json'), k = supKey(F), t = plain(familyWas(F));
  const B = J('results/E50_summary.json');
  assert.match(B[supKey(B)].reason, /positioning fix/, 'E50 says the positioning fix');
  assert.match(t, /\(a fix to the positioning model\): before, H9′ gave/);
  for (const id of ['H14', 'H15a']) assert.doesNotMatch(t, new RegExp(`${id} gave`), `${id} holds the same values in the block, so the note does not name it`);
  // an earlier H14 value that differs is not put under the positioning fix: its cause is E54's own reason
  const G = structuredClone(F); G[k].hypotheses.H14.p = 0.0029; G[k].hypotheses.H14.holm.p_adjusted = 0.0058;
  assert.match(plain(familyWas(G)), /: before a fix to the positioning model, H9′ gave .*; before fixes to the lost-link replay, H14 gave Holm p 0\.006\./);
  // H15a's file keeps no superseded block: a changed H15a value stops the build rather than borrow a cause
  const H = structuredClone(F); H[k].hypotheses.H15a.p = 0.002; H[k].hypotheses.H15a.holm.p_adjusted = 0.004;
  assert.throws(() => familyWas(H), /E56_integrity\.json: no superseded_\* block/);
  // a Holm p that moved while the hypothesis's own p did not: no single cause, so the build stops
  const K = structuredClone(F); K[k].hypotheses.H14.holm.p_adjusted = 0.0058;
  assert.throws(() => familyWas(K), /H14's Holm p changed while its own p did not/);
});

test('dateNum stops the build on a date that is not YYYY-MM-DD and on an unknown flag', () => {
  assert.match(dateNum({ iso: '2026-11-13' }), /13 November 2026/);
  for (const iso of ['13/11/2026', '2026-11-13T00:00', '2026-1-13', '2026-13-01', '2026-02-31', '', undefined, 20261113]) {
    assert.throws(() => dateNum({ iso, source: 'x.json: d' }), /is not a date \(YYYY-MM-DD\)/, String(iso));
  }
  assert.throws(() => dateNum({ iso: '2026-11-13', flag: 'Guessed' }), /dateNum: flag must be one of .*\(got Guessed\)/);
});

test('one robot\'s bid: every timing pass decides, the file\'s own verdict must agree, and the sentence says it quotes the range', () => {
  const S = J('results/E48_sizing.json'), TP = S.per_robot_round.timing_passes.by_multiple, t = plain(robotRound(S).bid);
  for (const [x, r] of Object.entries(TP)) {
    const ps = r.flight_p99_ms_by_pass;
    assert.ok(t.includes(`${(Math.min(...ps) / 1e3).toFixed(2)} to ${(Math.max(...ps) / 1e3).toFixed(2)} s`), `${x}x range over the passes`);
  }
  assert.match(t, /over three timing passes, under the one-second decision at the central factor in all three passes/);
  // the file says straddling where every pass is under: the build stops
  const A = structuredClone(S); A.per_robot_round.timing_passes.by_multiple['1'].against_1s_at_central_factor = 'straddling';
  assert.throws(() => robotRound(A), /at 1x the passes give inside at the central factor, the file says straddling/);
  // one pass over the decision at 4x: straddling in the passes and in the file, and the sentence says so
  const B = structuredClone(S), b4 = B.per_robot_round.timing_passes.by_multiple['4'];
  b4.flight_p99_ms_by_pass = [1010, 833, 770.2]; b4.against_1s_at_central_factor = 'straddling';
  const RB = robotRound(B);
  assert.equal(RB.above, true);
  assert.match(plain(RB.bid), /0\.77 to 1\.01 s at four times it, under the one-second decision in some passes and above it in others/);
  // different numbers of passes: the sentence gives one, so the build stops
  const C = structuredClone(S); C.per_robot_round.timing_passes.by_multiple['8'].flight_p99_ms_by_pass.pop();
  assert.throws(() => robotRound(C), /different numbers of timing passes/);
});

test('/protocol/ staged e54.json and e55.json: version 2 with the fields the client reads, and the client asks for 2', async () => {
  const { compactE54, compactE55 } = await import('../lib/protocol-data.mjs');
  const a = compactE54(J('results/E54_dtn.json'), J('results/E54_ledger.json')), b = compactE55(J('results/E55_integrity.json'));
  assert.equal(a.version, 2); assert.equal(typeof a.awards_and_jobs.jobs_per_seed, 'number');
  assert.equal(b.version, 2); assert.ok(Object.keys(b.replay_recent).length);
  const fig = readFileSync(new URL('../src/protocol/figures.js', import.meta.url), 'utf8');
  for (const [name, v] of [['e54', a.version], ['e55', b.version]]) assert.ok(fig.includes(`'lunarsim-${name}-site' || E.version !== ${v})`), `${name}: the client checks version ${v}`);
});
