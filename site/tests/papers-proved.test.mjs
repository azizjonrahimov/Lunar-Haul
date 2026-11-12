// F-65 preparation: /paper/ has an anchor per paper (#p1, #p2, #p3) that /protocol/ and /network/ link to, and shows
// each paper's "Proved, tested, assumed" table read from its built paper.html (pending until the paper has one).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { provedTable, paperField } from '../lib/papers.mjs';
import { markdown } from '../lib/pages.mjs';

const T = '<table id="x-tab"><caption>Table 9. What is proved.</caption><tr><th>Claim</th><td id="c1">Proved</td></tr></table>';

test('proved table: found by its heading, ids dropped, caption kept', () => {
  const html = `<h2 id="a">5. Results</h2><p>x</p>${T.replace('9', '1')}<h3 id="pta">6.1 Proved, tested, assumed</h3><p>Read this.</p>${T}<h2>7. Discussion</h2>`;
  const t = provedTable(html);
  assert.match(t, /^<table><caption>Table 9\. What is proved\.<\/caption>/);
  assert.doesNotMatch(t, /id="/);
  // wording variants and a non-breaking space in the heading
  assert.ok(provedTable(`<h4>Proved,&nbsp;tested and assumed</h4>${T}`));
  assert.ok(provedTable(`<h2>What is proved, tested, and assumed</h2>${T}`));
});

test('proved table: absent heading, or no table before the next heading, gives null', () => {
  assert.equal(provedTable('<h2>Results</h2>' + T), null);
  assert.equal(provedTable('<h3>Proved, tested, assumed</h3><p>soon</p><h3>Next</h3>' + T), null);
  assert.equal(provedTable(null), null);
});

test('the three papers: the field is a table or "(pending)", never an error', () => {
  for (const id of ['p1', 'p2', 'p3']) {
    const out = paperField(id, 'proved');
    assert.ok(/^<div class="paper-proved"><table/.test(out) || /\(pending\)/.test(out), `${id}: ${out.slice(0, 80)}`);
  }
});

test('/paper/ anchors exist and every paper link on /protocol/ and /network/ points at one', () => {
  const html = markdown('paper');
  const ids = new Set([...html.matchAll(/<h3 id="(p\d)">/g)].map(m => m[1]));
  assert.deepEqual([...ids].sort(), ['p1', 'p2', 'p3']);
  for (const id of ids) assert.match(html, new RegExp(`<!--@paper:${id}:proved-->`));
  for (const page of ['protocol', 'network']) {
    const src = readFileSync(new URL(`../${page}/index.html`, import.meta.url), 'utf8');
    const targets = [...src.matchAll(/paper\/#(p\d)"/g)].map(m => m[1]);
    assert.ok(targets.length, `${page}: no paper links`);
    for (const t of targets) assert.ok(ids.has(t), `${page}: #${t} has no anchor`);
    assert.doesNotMatch(src, /href="<!--@base-->paper\/"/, `${page}: a paper link without an anchor`);
  }
});
