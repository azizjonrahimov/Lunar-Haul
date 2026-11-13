// F-76: P2 part 4 reports the request-rule variant on all 10,000 fresh type-6 encounters (results/E44_fresh_seeds.json,
// key request_rule_fresh_6). /atc/ says so from the file, exploratory and with the share that ends incomplete; an altered
// file stops the build; /paper/'s hypothesis row comes from paper/p2/paper.html and no longer says "one encounter only".
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const SRC = join(ROOT, 'results/E44_fresh_seeds.json');
const D = existsSync(SRC) ? JSON.parse(readFileSync(SRC, 'utf8').replace(/([:[,]\s*)-?(NaN|Infinity)\b/g, '$1null')) : null;
const have = !!D?.request_rule_fresh_6;
const plain = s => s.replace(/<span class="visually-hidden">.*?<\/span>/g, '').replace(/<span class="flag"[^>]*>\w+<\/span>/g, '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ');
const cnt = n => n.toLocaleString('en-US');

test('/atc/: the request rule on every fresh type-6 encounter, exploratory, with the incomplete share', { skip: !have && 'B-112 missing' }, async () => {
  const { e44fresh } = await import('../lib/results-atc.mjs');
  const V = D.request_rule_fresh_6, a = V.rules_as_written, b = V.request_rule_variant, t = plain(e44fresh('lead'));
  assert.ok(t.includes(`run on all ${cnt(b.n)} fresh type-6 encounters`), t);
  assert.ok(t.includes(`allowed ${b.violations} violations against ${a.violations}`), t);
  assert.match(t, /exploratory and type 6 still fails under the rule as written/);
  assert.ok(t.includes(`${cnt(b.outcomes.incomplete)} (${Math.round(100 * b.outcomes.incomplete / b.n)} %) ended incomplete against ${cnt(a.outcomes.incomplete)}`), t);
  assert.ok(!/one encounter only/.test(t));
});

test('/atc/: a request-rule block that no longer says what the sentence says stops the build', { skip: !have && 'B-112 missing' }, async () => {
  const { reqRule6 } = await import('../lib/results-atc.mjs');
  assert.ok(reqRule6(D).length > 0);
  const bad = [
    [X => { X.request_rule_fresh_6.request_rule_variant.violations = 1; }, /the variant is not clean/],
    [X => { X.request_rule_fresh_6.new_failures_vs_rules_as_written.count = 1; }, /fails under the variant/],
    [X => { X.request_rule_fresh_6.request_rule_variant.outcomes.finished += 1; }, /changes how many encounters finish/],
    [X => { X.request_rule_fresh_6.rules_as_written.n += 1; }, /not the fresh type-6 run/],
  ];
  for (const [f, re] of bad) { const X = structuredClone(D); f(X); assert.throws(() => reqRule6(X), re); }
});

test('/paper/: P2\'s hypothesis row on fresh seeds no longer says the rule ran on one encounter', { skip: !existsSync(join(ROOT, 'paper/p2/paper.html')) && 'P2 missing' }, () => {
  const p = readFileSync(join(ROOT, 'paper/p2/paper.html'), 'utf8');
  assert.ok(!/on that one encounter only/.test(p));
  assert.match(p, /run afterwards on all [\d,]+ fresh type-6 encounters, had no violation; it was chosen after seeing the violation, so this is exploratory/);
});
