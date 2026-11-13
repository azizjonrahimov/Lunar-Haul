// F-56 (draft): the /results/ Lunar ATC section reads every number from the papers' values files (and E48), never typed;
// and the fifth story's draft declares every placeholder it uses and carries no typed digits in its prose.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { atcResults, ITEMS } from '../lib/results-atc.mjs';

const have = ['p1', 'p2', 'p3'].every(p => existsSync(new URL(`../../paper/${p}/values.json`, import.meta.url)));

test('Lunar ATC results: every key exists in its values file and renders flagged', { skip: !have && 'paper values not built' }, () => {
  for (const [p, groups] of Object.entries(ITEMS)) {
    const values = JSON.parse(readFileSync(new URL(`../../paper/${p}/values.json`, import.meta.url), 'utf8'));
    for (const k of groups.flat()) assert.ok(k in values, `${p}: no ${k}`);
  }
  const html = atcResults('/');
  assert.doesNotMatch(html, /\(pending\)|\{\{/);
  assert.doesNotMatch(html, /P1-H1-UNDELIVERED-SHARE|99\.5/, 'the withdrawn share is not read');
  assert.match(html, /a relay up <span class="num"><span class="v">[^<]*<\/span><span class=\"flag\" data-flag=\"Assumed\"[^>]*P1-RELAY08-SHARE[\s\S]*? of the time was worse/, 'F-70d: the relay share is read from P1 and flagged as an input');
  assert.ok((html.match(/data-flag="Modelled"/g) || []).length >= 14, 'every number carries a flag');
  // the section's text has no digits outside the flagged numbers, the file names and the paper names (P1 to P3)
  const text = html.replace(/<section class="r-fam"[\s\S]*?<\/section>/, '').replace(/<q class="r-quote"[\s\S]*?<\/q>/g, '')   // quoted paper sentences come from the values file
   .replace(/<span class="num">.*?<\/span><\/span>/g, '')   // the Phase 6 table quotes its file (tests/phase6.test.mjs)
   .replace(/<[^>]+>/g, ' ').replace(/paper\/p\d|E48_sizing|values\.json|\bP[123]\b|99th percentile|LRIP v0\.\d|v0\.\d|Proximity-1|\bE53\b/g, '');   // F-72: the percentile is named, not a typed value
  assert.doesNotMatch(text, /\d/, `typed digits: ${text.match(/.{0,30}\d.{0,30}/)?.[0]}`);
});

test('story draft "A month without Earth": placeholders declared, no typed digits', () => {
  const doc = JSON.parse(readFileSync(new URL('../../data/stories/month-without-earth.json', import.meta.url), 'utf8'));
  const prose = [doc.title, doc.summary, ...doc.steps.flatMap(s => [s.title, s.text, s.visual])].join('\n');
  const used = new Set([...prose.matchAll(/\{\{r:([A-Za-z0-9_]+)\}\}/g)].map(m => m[1]));
  for (const k of used) assert.ok(k in doc.numbers, `undeclared {{r:${k}}}`);
  for (const s of doc.steps) for (const c of s.chips || []) assert.ok(c in doc.numbers, `chip ${c} undeclared`);
  assert.doesNotMatch(prose.replace(/\{\{r:[A-Za-z0-9_]+\}\}/g, ''), /\d/, 'typed digits in the prose');
  assert.equal(doc.status, 'draft');
});
