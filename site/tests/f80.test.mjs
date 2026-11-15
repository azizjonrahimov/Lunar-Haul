// F-80: the site follows E50 regenerated with the positioning fix (B-118 N14/N15) at 1x, 4x and 8x. /protocol/ problem 1
// gives the overlap count at every fleet size and the near-base verdicts at 4x and 8x; the values published before the
// fix are named once, with the flagged date, on /protocol/ and under the /results/ hypothesis table. Every number from a file.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { e50ov } from '../lib/protocol-data.mjs';
import { nb, familyWas, familyTable } from '../lib/phase6.mjs';

const R = p => new URL(`../../${p}`, import.meta.url);
const J = p => JSON.parse(readFileSync(R(p), 'utf8').replace(/\bNaN\b/g, 'null'));
const plain = html => html.replace(/<span class="visually-hidden">[\s\S]*?<\/span>/g, '').replace(/<span class="flag"[^>]*>[^<]*<\/span>/g, '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ');
// the text with every flagged number taken out: what is left must hold no digit but labels (95 %, H9, B-102, 4x, 8x)
const bare = html => html.replace(/<span class="num">[\s\S]*?<span class="visually-hidden">[\s\S]*?<\/span><\/span>/g, '').replace(/<[^>]+>/g, '')
  .replace(/“[^”]*”/g, '').replace(/95 %|95th percentile|H9|H10|B-102|\b\d+x\b/g, '');
const sup = (doc, field) => doc[Object.keys(doc).find(k => /^superseded_/.test(k) && doc[k]?.[field])];
const f1 = v => v.toFixed(1), date = iso => { const [y, m, d] = iso.split('-').map(Number); return `${d} ${new Date(Date.UTC(y, m - 1, d)).toLocaleString('en-GB', { month: 'long', timeZone: 'UTC' })} ${y}`; };

test('/protocol/ overlaps: the layered margin lowers the count at every fleet size the file holds', () => {
  const D = J('results/E50_overlaps.json'), t = plain(e50ov('lead')), ks = Object.keys(D.multiples);
  assert.ok(ks.includes('8'), 'the 8x overlaps are in the file');
  assert.match(t, new RegExp(`at any of the ${['', '', 'two', 'three', 'four'][ks.length]} fleet sizes`));
  assert.doesNotMatch(t, /either fleet size/);
  for (const k of ks) {
    const v = D.multiples[k].runs['with_margin:layered'].overlaps_per_seed;
    assert.ok(t.includes(v ? v < 10 ? f1(v) : String(Math.round(v)) : '0'), `${k}x layered count ${v}`);
  }
  assert.match(t, /eight times the fleet/);
  assert.doesNotMatch(t, /violation/i, 'the count is never called a violation');
  assert.doesNotMatch(bare(e50ov('lead')), /\d/, 'every digit comes from a flagged number');
});

test('/protocol/ near the base: 4x and 8x give the verdicts of 1x', () => {
  const D = J('results/E50_near_base.json'), t = plain(nb('clause2'));
  assert.match(t, /At four and eight times the fleet/);
  for (const k of ['4', '8']) for (const r of ['a', 'e']) assert.ok(t.includes(`${f1(D.multiples[k].sets['dr+ranging'][r].in_p95_m_mean)} m`), `${k}x reading ${r}`);
});

test('/protocol/ problem 1: the values before the positioning fix, named once with the flagged date', () => {
  const NB = J('results/E50_near_base.json'), OV = J('results/E50_overlaps.json'), B = J('results/E50b_summary.json');
  const sNB = sup(NB, 'multiples'), sOV = sup(OV, 'multiples'), sB = sup(B, 'metrics'), s = e50ov('was'), t = plain(s);
  assert.ok(t.startsWith(`Corrected after a code review on ${date(sOV.superseded_on)}`), t);
  assert.match(s, new RegExp(`<span class="v">${date(sOV.superseded_on)}</span><span class="flag" data-flag="Modelled"`), 'the date is flagged');
  assert.ok(t.includes(`${f1(sNB.multiples['1'].sets['dr+ranging'].a.in_p95_m_mean)} m under the first reading`));
  assert.ok(t.includes(`${f1(sNB.multiples['1'].sets['dr+ranging'].e.in_p95_m_mean)} m under the registered wording`));
  assert.ok(t.includes(`${sB.metrics.delay_mean_h.diff_mean.toFixed(2)} h`));
  assert.match(t, /eight times the fleet was not run then/);
  assert.doesNotMatch(bare(s), /\d/, 'every digit comes from a flagged number');
  assert.equal((readFileSync(new URL('../protocol/index.html', import.meta.url), 'utf8').match(/<!--@e50ov:was-->/g) || []).length, 1, 'named once on the page');
});

test('/results/ hypotheses: the earlier values under the table, only those whose shown text changed', () => {
  const F = J('results/phase6_family.json'), O = sup(F, 'hypotheses'), s = familyWas(F), t = plain(s);
  assert.match(t, /^Corrected after a code review on \d+ \w+ \d{4} \(a fix to the positioning model\)/);
  assert.ok(t.includes(`${O.hypotheses.H10.clauses['the gap grows with the fleet (4x and 8x)'].gap_4x_h.toFixed(2).replace('-', '−')} h at 4x`), t);
  assert.ok(t.includes(`Holm p ${O.hypotheses.H10.holm.p_adjusted.toFixed(3)}`), t);
  assert.match(t, /Every outcome is as it was\./);
  assert.doesNotMatch(t, /for “absolute fixes keep it inside/, 'a value shown the same (15 m) is not named');
  assert.doesNotMatch(t, /for “ranging stays inside/, 'the near-base clause is shown by its readings, not by one value');
  assert.ok(familyTable().includes('r-fam-was'));
  assert.doesNotMatch(bare(s), /\d/, 'every digit comes from a flagged number');
  // an outcome that changed is said, not hidden
  const G = structuredClone(F), key = Object.keys(G).find(k => G[k] === O || (G[k]?.hypotheses && /^superseded_/.test(k)));
  G[key].hypotheses.H10.holm['rejected_at_0.05'] = true;
  assert.match(plain(familyWas(G)), /The outcome changed for H10′\./);
});
