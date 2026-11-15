// F-74, F-82 (B-122): the site follows P1's final pass (section 5.6). The registered test (16.5 %) stays the headline; the
// evaluation on the engine with the dispatch fixed point and its guard runs are read from results/ATC_learned_eval_fixpoint.json,
// the earlier bulk-cargo value from results/ATC_learned_eval_rerun.json (the engine without it); the sentences say what the
// intervals say, and the site never says the gain is free for other cargo. /paper/ no longer reads the withdrawn share.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';

const R = p => new URL(`../../${p}`, import.meta.url);
const FP = 'results/ATC_learned_eval_fixpoint.json', OLD = 'results/ATC_learned_eval_rerun.json';
const have = existsSync(R(FP)) && existsSync(R(OLD)) && existsSync(R('paper/p1/values.json'));
const J = p => JSON.parse(readFileSync(R(p), 'utf8'));
const plain = s => s.replace(/<span class="visually-hidden">.*?<\/span>/g, '').replace(/<span class="flag"[^>]*>\w+<\/span>/g, '').replace(/<[^>]+>/g, '').replace(/&#8239;|&nbsp;/g, ' ').replace(/&minus;/g, '-').replace(/\s+/g, ' ');

test('P1 card: the registered test, then the fixed-point evaluation and the guard runs, every number from the files', { skip: !have && 'B-122 missing' }, async () => {
  const { atcResults, p1learned, LR_SRC } = await import('../lib/results-atc.mjs');
  const { fmt } = await import('../src/components/num.js');   // the page's own rounding (toFixed rounds 4.715 down)
  const f = x => fmt(x, 2).replace('−', '-');
  assert.equal(LR_SRC, FP);
  const D = J(FP), O = J(OLD), html = atcResults('/');
  const card = html.match(/<article class="r-atc-card" aria-labelledby="r-atc-p1">[\s\S]*?<\/article>/)[0], text = plain(card);
  assert.match(text, /cut the urgent wait by 16\.5\s%\. The separate evaluation of the learned bids, run on the engine of that test \(with the dispatch fixed point\)/, 'the registered test stays the headline, the evaluation follows');
  assert.doesNotMatch(text, /corrected engine|not clean/, 'the old engine wording and the old guard verdict are gone');
  for (const l of [30, 60]) assert.ok(text.includes(`${(-100 * D.eval[l].linear.vs_hand_share).toFixed(1)} %`), `linear at ${l}`);
  assert.match(text, /the network still not distinguishable from hand-built bids/);
  assert.match(text, /trained on an engine without the fixed point and not retrained/);
  const B = D.guards[30].delay_mean_bulk.linear_minus_hand, U = D.guards[30].atc_urgent_wait_mean_cens_h.linear_minus_hand;
  const OB = O.guards[30].delay_mean_bulk.linear_minus_hand;
  assert.ok(text.includes(`urgent wait fell by ${f(-U.mean)} h (interval ${f(U.ci95[0])} h to ${f(U.ci95[1])} h)`));
  assert.ok(text.includes(`could not be told from zero (${f(B.mean)} h, interval ${f(B.ci95[0])} h to ${f(B.ci95[1])} h)`));
  assert.ok(text.includes(`bulk cargo waiting ${f(OB.mean)} h longer at 30 % load (interval ${f(OB.ci95[0])} h to ${f(OB.ci95[1])} h)`));
  assert.match(text, /at neither load did any measure of other cargo get worse/);
  assert.doesNotMatch(text, /free|no cost|costs nothing|92\.9|training range/i);
  assert.ok(card.includes(`<code>${LR_SRC}</code>`), 'the card names the evaluation file');
  assert.equal((card.match(/data-src|data-flag/g) || []).length > 20, true);
  assert.equal(p1learned('rerun', D, O), p1learned('rerun'));
});

test('P1 learned bids: a file that moves an interval across zero, or a guard metric that gets worse, stops the build', { skip: !have && 'B-122 missing' }, async () => {
  const { p1learned } = await import('../lib/results-atc.mjs');
  const D = J(FP), O = J(OLD), copy = () => structuredClone(D);
  let d = copy(); d.guards[30].delay_mean_bulk.linear_minus_hand.ci95 = [0.02, 0.44];
  assert.throws(() => p1learned('guard', d, O), /delay_mean_bulk got worse/);
  d = copy(); d.guards[60].delivered_kg.linear_minus_hand.ci95 = [-900, -10];
  assert.throws(() => p1learned('guard', d, O), /delivered_kg got worse/);
  d = copy(); d.guards[30].atc_urgent_wait_mean_cens_h.linear_minus_hand.ci95 = [-3.9, 0.2];
  assert.throws(() => p1learned('guard', d, O), /urgent gain is not below zero/);
  d = copy(); d.guards[60].delay_mean_bulk.linear_minus_hand.ci95 = [-9, 0.5];
  assert.throws(() => p1learned('guard', d, O), /delay_mean_bulk is not below zero/);
  d = copy(); d.eval[60].mlp.vs_hand_h.ci95 = [1, 13];
  assert.throws(() => p1learned('rerun', d, O), /network's difference at 60 % excludes zero/);
  d = copy(); d.eval[30].linear.vs_hand_h.ci95 = [-4, 0.1];
  assert.throws(() => p1learned('rerun', d, O), /gain at 30 % is not below zero/);
  d = copy(); d.engine = 'default path';
  assert.throws(() => p1learned('rerun', d, O), /did not say|does not say it ran with PREREG change 5/);
  const o = structuredClone(O); delete o.engine_note_b122;
  assert.throws(() => p1learned('rerun', D, o), /engine_note_b122/);
  assert.throws(() => p1learned('ood', D, O), /unknown key/);
});

test('/paper/: the learned bids follow the rerun; the withdrawn share is gone', { skip: !have && 'B-106 missing' }, () => {
  const md = readFileSync(new URL('../content/paper.md', import.meta.url), 'utf8');
  assert.doesNotMatch(md, /P1-H1-UNDELIVERED-SHARE/, 'P1 no longer states the 99.5 % share');
  const learned = md.match(/- \*\*Learned bids\.\*\*.*/)[0];
  assert.ok(learned.indexOf('<!--@v:p1:P1-H4-LIN-PCT-30-->') < learned.indexOf('<!--@p1l:rerun-->'), 'the registered test first');
  assert.ok(learned.includes('<!--@p1l:guard-->'));
  for (const k of ['P1-H1-DELIV-DIFF', 'P1-H1-DELIV-DIFF-CI', 'P1-H1-DIFF-30', 'P1-H1-TEAM-SHARE']) assert.ok(md.includes(`<!--@v:p1:${k}-->`), k);
  assert.doesNotMatch(md, /\bfree for\b/i);
});
