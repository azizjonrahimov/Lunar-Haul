// F-75: the site follows P1's new title (52e7fd7) and P2's revised abstract and conclusion (60dea9d). The P2 card quotes
// the changed keys from values.json; /atc/ counts the ring's deadlocks per exit rule from the part files, and the counts are
// the ones P2's conclusion prints; no site source still carries P1's old title.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const J = p => JSON.parse(readFileSync(join(ROOT, p), 'utf8').replace(/([:[,]\s*)-?(NaN|Infinity)\b/g, '$1null'));
const cnt = n => n.toLocaleString('en-US');
const have = ['results/E44_bounds.json', 'results/E47_bounds.json', 'paper/p2/values.json'].every(p => existsSync(join(ROOT, p)));

test('the ring by exit rule: every driven encounter and deadlock accounted for, and the counts P2 prints', { skip: !have && 'E44/E47 or P2 values missing' }, async () => {
  const { ringByRule } = await import('../lib/ring.mjs');
  const V = J('paper/p2/values.json');
  const moon = ringByRule(ROOT, 'E44', J('results/E44_bounds.json')), mars = ringByRule(ROOT, 'E47', J('results/E47_bounds.json'));
  const a = moon.as_written, v = moon.variant;
  assert.ok(V['P2-CONCLUSION-SAFETY-SHORT'].includes(`${cnt(a.deadlock)} of ${cnt(a.judged)} encounters`), 'P2 conclusion: rule as written');
  assert.ok(V['P2-CONCLUSION-SAFETY-SHORT'].includes(`${cnt(v.deadlock)} of ${cnt(v.judged)}`), 'P2 conclusion: variant');
  assert.ok(a.deadlock > 0 && a.deadlock < v.deadlock, 'more deadlocks under the variant');
  assert.ok(V['P2-E47-RESULTS-PARAGRAPH'].includes(`${cnt(mars.as_written.deadlock)} of the ${cnt(mars.as_written.judged)} encounters`), 'P2 Mars paragraph');
  assert.ok(V['P2-E47-RESULTS-PARAGRAPH'].includes(`${cnt(mars.variant.deadlock)} of ${cnt(mars.variant.judged)}`), 'P2 Mars paragraph, variant');
  // an altered bounds file stops the build
  const B = J('results/E44_bounds.json'); B.types['5'].outcomes.deadlock += 1;
  assert.throws(() => ringByRule(ROOT, 'E44', B), /type 5 gives/);
});

test('/atc/: the type-5 finding states both rules with their denominators, from the part files', { skip: !have && 'E44/E47 missing' }, async () => {
  const { ringSentence, ringByRule } = await import('../lib/ring.mjs');
  const plain = s => s.replace(/<span class="visually-hidden">.*?<\/span>/g, '').replace(/<span class="flag"[^>]*>\w+<\/span>/g, '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ');
  for (const [b, mars] of [['E44', false], ['E47', true]]) {
    const R = ringByRule(ROOT, b, J(`results/${b}_bounds.json`)), t = plain(ringSentence(b));
    assert.ok(t.includes(`${cnt(R.as_written.deadlock)} of ${cnt(R.as_written.judged)}`) && t.includes(`${cnt(R.variant.deadlock)} of ${cnt(R.variant.judged)}`), t);
    assert.match(t, /under the rule as written and in .* with a variant keeping one bay slot free; the Deadlocks column adds both\./);
    assert.equal(/on Mars/.test(t), mars);
  }
  const page = readFileSync(join(ROOT, 'site/atc/index.html'), 'utf8');
  assert.match(page, /<template id="atc-ring-moon"><!--@ring:E44--><\/template><template id="atc-ring-mars"><!--@ring:E47--><\/template>/);
});

test('P2 card quotes the revised abstract keys; no site source carries P1\'s old title', { skip: !have && 'P2 values missing' }, async () => {
  const { atcResults } = await import('../lib/results-atc.mjs');
  const html = atcResults('/'), V = J('paper/p2/values.json');
  for (const k of ['P2-H7-ABSTRACT-SHORT', 'P2-P6-ABSTRACT-CLAUSE']) assert.ok(html.includes(V[k]), k);
  assert.ok(html.includes('a slope term removed this when following'));
  const old = new RegExp(['Learned Bidding', 'Among'].join(' '), 'i'), bad = [];
  const walk = d => { for (const f of readdirSync(d)) { const p = join(d, f); if (statSync(p).isDirectory()) { if (!/node_modules|^dist$|^public$/.test(f)) walk(p); } else if (/\.(md|mjs|js|html|json|bib|txt)$/.test(f) && old.test(readFileSync(p, 'utf8'))) bad.push(p); } };
  walk(join(ROOT, 'site'));
  assert.deepEqual(bad, []);
});
