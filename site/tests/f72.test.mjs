// F-72: the second pass of P2 (part 2) and P3 (part 2) on the site. The /results/ cards tell when a key they read changes
// or goes away; R1 with its slope term and the uphill runs (results/E45_uphill.json) on /atc/; what a reservation overlap
// is (results/E50_overlaps.json) on /protocol/; one robot's bid time and the measured memory (results/E48_sizing.json)
// wherever the site sizes the on-robot computation. Every number from a file.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { cardKeyChanges, atcResults, e45up, ITEMS } from '../lib/results-atc.mjs';
import { paperValue } from '../lib/papers.mjs';
import { e50ov } from '../lib/protocol-data.mjs';
import { robotRound } from '../src/atc/e48-robot.js';
import { navStackFigure as navFigure } from '../lib/anatomy-nav.mjs';

const R = p => new URL(`../../${p}`, import.meta.url);
const J = p => JSON.parse(readFileSync(R(p), 'utf8').replace(/\bNaN\b/g, 'null'));
const plain = html => html.replace(/<span class="visually-hidden">[\s\S]*?<\/span>/g, '').replace(/<span class="flag"[^>]*>[^<]*<\/span>/g, '').replace(/<[^>]+>/g, '');

test('cards: every key they read is as it was when the cards were last reread (else run scripts/lock-cards.mjs after rereading)', () => {
  const ch = cardKeyChanges();
  assert.deepEqual(ch.map(c => `${c.id} ${c.key} ${c.was}`), [], ch.map(c => `${c.key}: ${c.text}`).join('\n'));
  assert.throws(() => paperValue('p2', 'P2-NO-SUCH-KEY'), /has no P2-NO-SUCH-KEY/, 'a key that went away fails the build');
  assert.ok(ITEMS.p2.flat().includes('P2-H7-ABSTRACT-SHORT'));
});

test('/atc/: R1 with the slope term, and the uphill runs', { skip: !existsSync(R('results/E45_uphill.json')) && 'B-107 missing' }, () => {
  const D = J('results/E45_uphill.json'), rule = plain(e45up('rule')), res = plain(e45up('result'));
  assert.match(rule, /slope term/); assert.match(rule, /run without the slope term/); assert.match(rule, /flat or downhill, where it is inactive/);
  assert.ok(rule.includes(`${D.b_max} m/s²`));
  if (D.cells.every(c => c.contacts === 0)) assert.match(res, /no contact anywhere/);
  assert.ok(res.includes(`on the Moon from ${D.threshold['moon:following'].first_slope_with_gap_below_d0_deg}°`), res);
  assert.ok(res.includes(`on Mars from ${D.threshold['mars:following'].first_slope_with_gap_below_d0_deg}°`), res);
  const rest = D.cells.filter(c => c.rule === 'slope_term' && c.gap_below_d0 > 0);
  if (rest.length) assert.ok(res.includes(`${(D.d0_m - Math.min(...rest.map(c => c.min_gap_m))).toFixed(2)} m`), 'the remaining shortfall');
  assert.match(e45up('result'), /data-flag="Modelled"/); assert.match(e45up('result'), /data-flag="Assumed"/);
  assert.throws(() => e45up('nope'), /unknown key/);
  assert.match(readFileSync(new URL('../atc/index.html', import.meta.url), 'utf8'), /<!--@e45u:rule-->[\s\S]*<!--@e45u:result-->/);
});

test('/protocol/: an overlap is an event in the accounts, not a safety measure', { skip: !existsSync(R('results/E50_overlaps.json')) && 'B-102 missing' }, () => {
  const X = J('results/E50_overlaps.json').multiples['4'].runs, s = e50ov('lead'), t = plain(s);
  const sh = Object.entries(X).filter(([k]) => k.startsWith('no_margin:')).map(([, r]) => 100 * r.back_to_back.abutting_share_overlapping);
  assert.ok(t.includes(`${Math.round(Math.min(...sh))} to ${Math.round(Math.max(...sh))} %`), t);
  assert.match(t, /not a safety measure/); assert.match(t, /does not change how far ahead/); assert.match(t, /no overlap, with or without a margin/);
  assert.doesNotMatch(t, /violation/i, 'the count is never called a violation');
  assert.match(readFileSync(new URL('../protocol/index.html', import.meta.url), 'utf8'), /<!--@e50ov:lead-->/);
});

test('one robot\'s bid and the measured memory, wherever the site sizes the on-robot computation', () => {
  const S = J('results/E48_sizing.json'), RR = robotRound(S), L = S.per_robot_round.laptop_ms_by_multiple;
  const bid = plain(RR.bid);
  // F-81: the range over every timing pass, smallest to largest, and "above" from every pass
  const TP = S.per_robot_round.timing_passes.by_multiple;
  for (const x of Object.keys(L)) {
    const ps = TP[x].flight_p99_ms_by_pass;
    assert.ok(bid.includes(`${(Math.min(...ps) / 1e3).toFixed(2)} to ${(Math.max(...ps) / 1e3).toFixed(2)} s`), x);
  }
  assert.match(bid, /over three timing passes/);
  assert.equal(RR.above, Object.values(TP).some(r => Math.max(...r.flight_p99_ms_by_pass) > 1000));
  if (RR.above) assert.match(bid, /above (it|the one-second decision)/);
  const mem = Object.values(S.measured_memory.mb_by_multiple).map(m => m.all_at_once_peak);
  assert.equal(plain(RR.mem), `${Math.min(...mem).toFixed(2)} to ${Math.max(...mem).toFixed(2)} MB`);
  // the /results/ P3 card and the /protocol/ navigation computer say it; neither says the memory only by the estimate
  const card = plain(atcResults());
  assert.ok(card.includes(bid), 'P3 card'); assert.ok(card.includes(plain(RR.mem)), 'P3 card memory');
  const nav = plain(navFigure());
  assert.ok(nav.includes(plain(RR.mem)), '/protocol/ navigation computer'); assert.doesNotMatch(nav, /needs about [\d.]+ MB by an estimate/);
  // /atc/ section 3 reads it in the browser from the same helper
  const main = readFileSync(new URL('../src/atc/sizing.js', import.meta.url), 'utf8');   // section 3, loaded near it
  assert.match(main, /robotRound\(S\)/); assert.doesNotMatch(main, /Memory, estimated as the sum/);
});
