// F-56: /paper/ reads the Phase 5 papers' title, abstract and keywords from paper/<id>/paper.html and their numbers
// from paper/<id>/values.json at build time (lib/papers.mjs); nothing is typed into the site.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { paperField, paperValue } from '../lib/papers.mjs';

const P1 = new URL('../../paper/p1/', import.meta.url), have = existsSync(new URL('values.json', P1)) && existsSync(new URL('paper.html', P1));

test('P1: title, abstract, keywords and citation come from the built paper', { skip: !have && 'paper/p1 not built' }, () => {
  for (const f of ['title', 'abstract', 'keywords', 'bibtex']) assert.doesNotMatch(paperField('p1', f), /\(pending\)|\{\{/, f);
  assert.doesNotMatch(paperField('p1', 'abstract'), /^<b>Abstract/);
  assert.match(paperField('p1', 'bibtex'), /title {2}= \{Working Together Without Earth/);
});

test('P1: every value the paper page quotes exists in values.json', { skip: !have && 'paper/p1 not built' }, () => {
  const md = readFileSync(new URL('../content/paper.md', import.meta.url), 'utf8');
  const keys = [...md.matchAll(/<!--@v:p1:([\w-]+)-->/g)].map(m => m[1]);
  assert.ok(keys.length >= 10);
  const values = JSON.parse(readFileSync(new URL('values.json', P1), 'utf8'));
  for (const k of keys) assert.equal(paperValue('p1', k), String(values[k]), k);
  assert.throws(() => paperValue('p1', 'P1-NO-SUCH-KEY'), /has no P1-NO-SUCH-KEY/);
});

test('a paper that is not built gives (pending), not a failed build', () => {
  assert.match(paperField('p9', 'title'), /\(pending\)/);
  assert.match(paperValue('p9', 'ANY'), /\(pending\)/);
});

const R1 = new URL('../../paper/r1/paper.html', import.meta.url);
test('R-1: title, abstract and keywords from the built paper, without its build notes', { skip: !existsSync(R1) && 'paper/r1 not built' }, () => {
  for (const f of ['title', 'abstract', 'keywords', 'bibtex']) assert.doesNotMatch(paperField('r1', f), /\(pending\)|\{\{|<!--/, f);
  assert.match(paperField('r1', 'title'), /^What Earth's Horizon Costs/);
});

test('every PDF that /paper/ links to is in the repository', () => {
  const md = readFileSync(new URL('../content/paper.md', import.meta.url), 'utf8');
  const pdfs = [...md.matchAll(/Lunar-Haul\/blob\/main\/([^)\s]+\.pdf)\)/g)].map(x => x[1]);
  // the Phase 5 papers' links come from <!--@paper:<id>:pdf-->, with the page count and size read from the file
  const marked = [...md.matchAll(/<!--@paper:(\w+):pdf-->/g)].map(x => x[1]);
  assert.ok(pdfs.length + marked.length >= 4, `${pdfs.length + marked.length} PDF links`);
  for (const p of pdfs) assert.ok(existsSync(new URL(`../../${p}`, import.meta.url)), p);
  for (const id of marked) {
    const a = paperField(id, 'pdf');
    if (/\(pending\)/.test(a)) continue;
    const m = /blob\/main\/(paper\/\w+\/[^"]+\.pdf)">PDF, (\d+) pages, ([\d,]+) kB</.exec(a);
    assert.ok(m, a); assert.ok(existsSync(new URL(`../../${m[1]}`, import.meta.url)), m[1]); assert.ok(+m[2] > 0, id);
  }
});
