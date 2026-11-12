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
  assert.ok((html.match(/data-flag="Modelled"/g) || []).length >= 14, 'every number carries a flag');
  // the section's text has no digits outside the flagged numbers and the file names
  const text = html.replace(/<span class="num">.*?<\/span><\/span>/g, '').replace(/<[^>]+>/g, ' ').replace(/paper\/p\d|E48_sizing|values\.json/g, '');
  assert.doesNotMatch(text, /\d/, `typed digits: ${text.match(/.{0,30}\d.{0,30}/)?.[0]}`);
});

test('story draft "A month without Earth": placeholders declared, no typed digits', () => {
  const doc = JSON.parse(readFileSync(new URL('../content/drafts/month-without-earth.json', import.meta.url), 'utf8'));
  const prose = [doc.title, doc.summary, ...doc.steps.flatMap(s => [s.title, s.text, s.visual])].join('\n');
  const used = new Set([...prose.matchAll(/\{\{r:([A-Za-z0-9_]+)\}\}/g)].map(m => m[1]));
  for (const k of used) assert.ok(k in doc.numbers, `undeclared {{r:${k}}}`);
  for (const s of doc.steps) for (const c of s.chips || []) assert.ok(c in doc.numbers, `chip ${c} undeclared`);
  assert.doesNotMatch(prose.replace(/\{\{r:[A-Za-z0-9_]+\}\}/g, ''), /\d/, 'typed digits in the prose');
  assert.equal(doc.status, 'draft');
});
