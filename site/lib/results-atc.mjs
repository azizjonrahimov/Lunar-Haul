// F-56: the Lunar ATC section of /results/ (<!--@results-atc-->): the three papers' headline numbers, read at build time
// from paper/<id>/values.json (the papers' own values files; pre-formatted strings) and, for P3's computing and radio
// numbers that its values file does not carry, results/E48_sizing.json. Nothing is typed.
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { paperValue, paperField } from './papers.mjs';
import { num, esc } from '../src/components/num.js';
import { ROOT } from './pages.mjs';
import { familyTable } from './phase6.mjs';

// a pre-formatted value from a paper's values file, flagged like every number on the site
export function pv(id, key) {
  const v = paperValue(id, key);
  if (/pending/.test(v)) return v;
  const tip = `Modelled: produced by the LunarHaul simulation. Source: paper/${id}/values.json, ${key}`;
  return `<span class="num"><span class="v">${v}</span><span class="flag" data-flag="Modelled" title="${esc(tip)}">Modelled</span><span class="visually-hidden"> (${esc(tip)})</span></span>`;
}

// the sentences: [paper, list of HTML items]; every number through pv() or E48
export const ITEMS = {
  p1: [
    ['P1-N-RUNS-ALL', 'P1-N-REGIMES'],
    ['P1-H2-STRICT-MINUS-O', 'P1-PLAN-MINUS-O'],
    ['P1-LOSS-MAIN', 'P1-H3A-DIFF', 'P1-H3A-CI90'],
    ['P1-H4-LIN-PCT-30'],
    ['P1-H1-UNDELIVERED-SHARE'],
  ],
  p2: [['P2-E44-N-ENCOUNTERS', 'P2-N-RUNS-E43'], ['P2-H8-X1-PCT', 'P2-H8-X4-PCT'], ['P2-UNC-X1-RATIO'], ['P2-DEADLOCKS-TOTAL']],
  p3: [['P3-N-OWNERS', 'P3-E46-N-RUNS'], ['P3-MESH-MAST-DIRECT-SHARE']],
};

function e48() { const p = join(ROOT, 'results', 'E48_sizing.json'); return existsSync(p) ? JSON.parse(readFileSync(p, 'utf8').replace(/\bNaN\b/g, 'null')) : null; }

export function atcResults(base = '/') {
  const v = pv, E = e48(), SZ = 'results/E48_sizing.json';
  const e = (value, unit, digits, src) => num({ value, unit, digits, flag: 'Modelled', source: `${SZ}: ${src}` });
  const air = a => E?.airtime?.rows?.find(r => r.sizes.startsWith('LRIP secured, MAC 8') && String(r.hops).startsWith('measured') && r.access.startsWith(a));
  const card = (id, items) => `<article class="r-atc-card" aria-labelledby="r-atc-${id}"><p class="r-atc-k">${id.toUpperCase()}</p>`
    + `<h3 class="r-atc-h" id="r-atc-${id}">${paperField(id, 'title')}</h3><ul>${items.map(t => `<li>${t}</li>`).join('')}</ul>`
    + `<p class="small muted r-atc-src">Read from <code>paper/${id}/values.json</code>${id === 'p3' ? ' and <code>results/E48_sizing.json</code>' : ''} when the site is built.</p></article>`;
  const p1 = [
    `${v('p1', 'P1-N-RUNS-ALL')} pre-registered simulated years under ${v('p1', 'P1-N-REGIMES')} decision regimes.`,
    `A shared dispatcher on Earth that stops when Earth sets kept urgent cargo waiting ${v('p1', 'P1-H2-STRICT-MINUS-O')} longer than one that never stops; planning ahead before each blackout left ${v('p1', 'P1-PLAN-MINUS-O')} of that.`,
    `The robots' own auction, at message loss ${v('p1', 'P1-LOSS-MAIN')}, kept urgent cargo waiting ${v('p1', 'P1-H3A-DIFF')} than the full-information marketplace; its interval, ${v('p1', 'P1-H3A-CI90')}, includes zero, so the runs cannot tell the two apart.`,
    `A learned correction to the bids cut the urgent wait by ${v('p1', 'P1-H4-LIN-PCT-30')}.`,
    `${v('p1', 'P1-H1-UNDELIVERED-SHARE')} of the value of sharing is cargo that owners working alone never deliver.`,
  ];
  const p2 = [
    `The rules were checked on ${v('p2', 'P2-E44-N-ENCOUNTERS')} encounters and priced in ${v('p2', 'P2-N-RUNS-E43')} runs of the logistics model.`,
    `At today's fleet they add ${v('p2', 'P2-H8-X1-PCT')} to the delay per delivery; at four times the fleet, ${v('p2', 'P2-H8-X4-PCT')}.`,
    `Referring every road conflict to Earth instead raises the delay per delivery ${v('p2', 'P2-UNC-X1-RATIO')}-fold.`,
    `There were ${v('p2', 'P2-DEADLOCKS-TOTAL')} deadlocks at today's fleet.`,
  ];
  const sched = air('scheduled'), slot = air('slotted');
  const p3 = [
    `The market was priced for ${v('p3', 'P3-N-OWNERS')} owners over ${v('p3', 'P3-E46-N-RUNS')} simulated years.`,
    E ? `Scaled to the reference flight processor, the heaviest safety check takes ${e(E.h10.safety_core_share_flight_per_robot_10hz * 100, ' %', 1, 'h10.safety_core_share_flight_per_robot_10hz')} of one core.` : 'E48 not available.',
    sched && slot ? `Twenty robots' authenticated traffic needs ${e(sched.channel_kbps_needed, ' kbit/s', 2, 'airtime (scheduled, measured hops)')} of airtime on a channel the base schedules, and ${e(slot.channel_kbps_needed, ' kbit/s', 2, 'airtime (slotted random access, measured hops)')} with random access, against a ${e(E.airtime.channel_kbps, ' kbit/s', 0, 'airtime.channel_kbps')} channel.` : '',
    `The base's mast is in direct view at ${v('p3', 'P3-MESH-MAST-DIRECT-SHARE')} of route points; the rest goes through the mesh.`,
  ].filter(Boolean);
  return `<section class="r-atc" aria-labelledby="h-atc"><h2 id="h-atc">Lunar ATC: the three papers in numbers</h2>`
    + `<p class="prose">Headline results of the three Lunar ATC papers, read from the papers' own values files when the site is built. More on <a href="${base}atc/">the Lunar ATC page</a>, <a href="${base}world/?view=atc">a month with and without the network</a> and <a href="${base}paper/">the papers</a>.</p>`
    + `<div class="r-atc-grid">${card('p1', p1)}${card('p2', p2)}${card('p3', p3)}</div>${familyTable()}</section>`;   // F-69: the Phase 6 hypotheses under the cards
}
