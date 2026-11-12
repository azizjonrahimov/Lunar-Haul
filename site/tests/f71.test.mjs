// F-71: the site brought to the second pass of P2 and P3. H9′ clause 2 under every reading of "near the base"
// (results/E50_near_base.json), the curved-Moon hop stated as P3 states it, encounter types on fresh seeds
// (results/E44_fresh_seeds.json), the BibTeX dates from each paper's byline. Every number from a file.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { nearBase, nb, familyRows, familyTable } from '../lib/phase6.mjs';
import { b104 } from '../lib/protocol-data.mjs';
import { e44fresh } from '../lib/results-atc.mjs';
import { paperField } from '../lib/papers.mjs';

const R = p => new URL(`../../${p}`, import.meta.url);
const J = p => JSON.parse(readFileSync(R(p), 'utf8'));
const plain = html => html.replace(/<span class="flag"[\s\S]*?<\/span><\/span>/g, '').replace(/<[^>]+>/g, '');

test('H9′ clause 2: every reading, the registered wording, the verdict', { skip: !existsSync(R('results/E50_near_base.json')) && 'B-101 missing' }, () => {
  const D = J('results/E50_near_base.json'), N = nearBase(), S = D.multiples['1'].sets['dr+ranging'];
  assert.equal(N.rows.length, Object.keys(D.readings).length);
  assert.equal(N.rows.filter(x => x.registered).length, 1, 'one registered wording');
  for (const x of N.rows) {
    assert.equal(x.inside, S[x.r].seeds_inside_budget, x.r);
    assert.match(x.p95, /data-flag="Modelled"/); assert.match(x.p95, /simulation on assumed ranging errors/);
  }
  const s = nb('clause2'), t = plain(s);
  assert.match(t, /registered\s+wording/);
  assert.match(t, new RegExp(N.reg.inside === 0 ? 'fails in every seed' : 'holds in'));
  assert.match(t, /depends on the reading/);
  assert.match(t, /a simulation on assumed ranging errors/);
  const bare = s.replace(/<span class="num">[\s\S]*?<span class="visually-hidden">[\s\S]*?<\/span><\/span>/g, '').replace(/<[^>]+>/g, '')
    .replace(/“[^”]*”/g, '').replace(/95th percentile|H9/g, '');
  assert.doesNotMatch(bare, /\d/, 'every digit outside the quoted reading names comes from a flagged number');
  // the /results/ table lists every reading under the clause, and no longer the old "four readings"
  const H9 = familyRows(J('results/phase6_family.json')).find(r => r.id === 'H9');
  const part = H9.parts.find(([, o]) => o === 'reading');
  assert.equal((part[3].match(/<li>/g) || []).length, N.rows.length);
  assert.match(H9.note, /registered wording it (fails in every seed|holds)/);
  assert.doesNotMatch(familyTable(), /four readings/);
});

test('curved Moon: the crew and cargo rovers’ worst hop, said as P3 says it', { skip: !existsSync(R('results/E48_sizing.json')) && 'E48 missing' }, () => {
  const B = J('results/E48_sizing.json').revision_b104.per_class;
  const tgt = Math.max(...Object.keys(B.LTV1.range_m_for_kbps_spherical).map(Number));
  const short = B.LTV1.range_m_for_kbps_spherical[String(tgt)] < B.LTV1.worst_hop.d_m;
  assert.equal(b104('carry'), short ? 'no longer carries' : 'still carries');
  const html = readFileSync(new URL('../protocol/index.html', import.meta.url), 'utf8');
  assert.match(html, /By calculation over a curved Moon/);
  assert.match(html, /worst hop <!--@b104:carry-->/);
});

test('fresh seeds on /atc/: clean types, the violating one with its kind and weighted bound', { skip: !existsSync(R('results/E44_fresh_seeds.json')) && 'B-108 missing' }, () => {
  const T = J('results/E44_fresh_seeds.json').types, s = e44fresh('lead'), t = plain(s);
  for (const [id, v] of Object.entries(T)) assert.match(t, new RegExp(`\\b${id}\\b`), `type ${id} named`);
  const bad = Object.entries(T).filter(([, v]) => v.fresh_seeds.violations > 0);
  if (bad.some(([, v]) => v.fresh_seeds.violations_by_kind?.viol_zone)) assert.match(t, /inside a closed landing zone at closure/);
  if (bad.some(([, v]) => typeof v.fresh_seeds.bound_weighted === 'number')) assert.match(s, /fresh_seeds\.bound_weighted/);
  assert.match(s, /data-flag="Modelled"/);
  assert.throws(() => e44fresh('nope'), /unknown key/);
});

test('BibTeX: the dates come from each paper’s byline', () => {
  for (const id of ['p1', 'p2', 'p3']) {
    const html = readFileSync(R(`paper/${id}/paper.html`), 'utf8'), bib = paperField(id, 'bibtex');
    const by = /Preprint, ([A-Z][a-z]+ \d{4})(?:[,;] revised ([A-Z][a-z]+ \d{4}))?/.exec(html);
    assert.ok(by, id);
    assert.match(bib, new RegExp(`note {3}= \\{Preprint, ${by[1]}${by[2] ? `, revised ${by[2]}` : ''}\\}`), id);
  }
});
