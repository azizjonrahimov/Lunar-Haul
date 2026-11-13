// F-56: the Lunar ATC section of /results/ (<!--@results-atc-->): the three papers' headline numbers, read at build time
// from paper/<id>/values.json (the papers' own values files; pre-formatted strings) and, for P3's computing and radio
// numbers that its values file does not carry, results/E48_sizing.json. Nothing is typed.
import { readFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join } from 'node:path';
import { paperValue, paperField } from './papers.mjs';
import { num, esc, FLAGS } from '../src/components/num.js';
import { ROOT } from './pages.mjs';
import { familyTable } from './phase6.mjs';
import { robotRound } from '../src/atc/e48-robot.js';
import { lrip2 } from './protocol-data.mjs';

// a pre-formatted value from a paper's values file, flagged like every number on the site: Modelled unless the value
// is a setting of the experiment (F-70d: the relay's 80 % availability is an input, so Assumed)
export function pv(id, key, flag = 'Modelled') {
  const v = paperValue(id, key);
  if (/pending/.test(v)) return v;
  const tip = `${FLAGS[flag]}. Source: paper/${id}/values.json, ${key}`;
  return `<span class="num"><span class="v">${v}</span><span class="flag" data-flag="${flag}" title="${esc(tip)}">${flag}</span><span class="visually-hidden"> (${esc(tip)})</span></span>`;
}

// the sentences: [paper, list of HTML items]; every number through pv() or E48
export const ITEMS = {
  p1: [
    ['P1-N-RUNS-ALL', 'P1-N-RUNS-DISTINCT-MAX', 'P1-E40-N-DISTINCT', 'P1-E40-N-RUNS', 'P1-N-REGIMES'],
    ['P1-H2-STRICT-MINUS-O', 'P1-PLAN-MINUS-O'],
    ['P1-LOSS-MAIN', 'P1-H3A-DIFF', 'P1-H3A-CI90'],
    ['P1-H4-MLP-DIFF-30', 'P1-H4-MLP-CI-30', 'P1-H4-LIN-PCT-30'],
    ['P1-RELAY08-SHARE', 'P1-AUCTION-MINUS-RELAY08', 'P1-AUCTION-MINUS-RELAY08-CI'],
    // the 99.5 % share (P1-H1-UNDELIVERED-SHARE) is withdrawn by the revised P1: not read
  ],
  p2: [['P2-E44-N-ENCOUNTERS', 'P2-N-RUNS-E43'], ['P2-H7-ABSTRACT-SHORT'], ['P2-H8-X1-PCT', 'P2-H8-X4-PCT'], ['P2-UNC-X1-RATIO'], ['P2-P6-ABSTRACT-CLAUSE']],
  p3: [['P3-N-OWNERS', 'P3-E46-N-RUNS'], ['P3-MESH-MAST-DIRECT-SHARE']],
};

// F-72: every key a card reads, and the text it had when the cards were last checked against it (lib/card-keys.lock.json,
// sha-256 prefixes, written by scripts/lock-cards.mjs). A key that went away fails the build (paperValue); one whose text
// changed is named in the build log and fails tests/f72.test.mjs until someone has reread the card and refreshed the lock.
export const CARD_LOCK = join(ROOT, 'site', 'lib', 'card-keys.lock.json');
export const cardHashes = () => Object.fromEntries(Object.entries(ITEMS).flatMap(([id, groups]) => groups.flat()
  .map(key => [`${id}:${key}`, createHash('sha256').update(paperValue(id, key)).digest('hex').slice(0, 16)])));
export function cardKeyChanges() {
  const lock = existsSync(CARD_LOCK) ? JSON.parse(readFileSync(CARD_LOCK, 'utf8')) : {}, now = cardHashes();
  return Object.entries(now).filter(([k, h]) => lock[k] !== h).map(([k]) => {
    const [id, key] = k.split(':');
    return { id, key, was: lock[k] ? 'changed' : 'not in the lock', text: paperValue(id, key).replace(/<[^>]+>|&[a-z#0-9]+;/g, ' ').replace(/\s+/g, ' ').slice(0, 160) };
  });
}

function e48() { const p = join(ROOT, 'results', 'E48_sizing.json'); return existsSync(p) ? JSON.parse(readFileSync(p, 'utf8').replace(/\bNaN\b/g, 'null')) : null; }

// a sentence the paper itself writes (a values-file key holding prose): quoted as it stands, its numbers included
export function quote(id, key) { return `<q class="r-quote" data-src="paper/${id}/values.json ${key}">${paperValue(id, key)}</q>`; }

export function atcResults(base = '/') {
  for (const c of cardKeyChanges()) console.warn(`[results cards] paper/${c.id}/values.json ${c.key} ${c.was} since the cards were checked; reread the card, then run node scripts/lock-cards.mjs: "${c.text}"`);
  const v = pv, E = e48(), SZ = 'results/E48_sizing.json';
  const e = (value, unit, digits, src) => num({ value, unit, digits, flag: 'Modelled', source: `${SZ}: ${src}` });
  const air = a => E?.airtime?.rows?.find(r => r.sizes.startsWith('LRIP secured, MAC 8') && String(r.hops).startsWith('measured') && r.access.startsWith(a));
  const card = (id, items) => `<article class="r-atc-card" aria-labelledby="r-atc-${id}"><p class="r-atc-k">${id.toUpperCase()}</p>`
    + `<h3 class="r-atc-h" id="r-atc-${id}">${paperField(id, 'title')}</h3><ul>${items.map(t => `<li>${t}</li>`).join('')}</ul>`
    + `<p class="small muted r-atc-src">Read from <code>paper/${id}/values.json</code>${id === 'p3' ? ' and <code>results/E48_sizing.json</code>' : ''} when the site is built.</p></article>`;
  const p1 = [
    `${v('p1', 'P1-N-RUNS-ALL')} simulated years in three experiments, at most ${v('p1', 'P1-N-RUNS-DISTINCT-MAX')} of them distinct (${v('p1', 'P1-E40-N-DISTINCT')} distinct of ${v('p1', 'P1-E40-N-RUNS')} in the main experiment), under ${v('p1', 'P1-N-REGIMES')} decision regimes.`,
    `A shared dispatcher on Earth that stops when Earth sets kept urgent cargo waiting for pickup ${v('p1', 'P1-H2-STRICT-MINUS-O')} longer than one that never stops; planning ahead before each blackout left ${v('p1', 'P1-PLAN-MINUS-O')} of that.`,
    `The robots' own auction, at message loss ${v('p1', 'P1-LOSS-MAIN')}, kept urgent cargo waiting for pickup ${v('p1', 'P1-H3A-DIFF')} than the full-information marketplace; its interval, ${v('p1', 'P1-H3A-CI90')}, includes zero, so the runs cannot tell the two apart.`,
    `The registered learned bid, a small network, did not beat hand-built bids (difference ${v('p1', 'P1-H4-MLP-DIFF-30')}, interval ${v('p1', 'P1-H4-MLP-CI-30')}); a linear correction registered as secondary cut the urgent wait by ${v('p1', 'P1-H4-LIN-PCT-30')}.`,
    `An always-up relay matched the marketplace run for run; only a relay up ${v('p1', 'P1-RELAY08-SHARE', 'Assumed')} of the time was worse than the auction, by ${v('p1', 'P1-AUCTION-MINUS-RELAY08')} (${v('p1', 'P1-AUCTION-MINUS-RELAY08-CI')}).`,
  ];
  const p2 = [
    `The rules were checked on ${v('p2', 'P2-E44-N-ENCOUNTERS')} encounters and priced in ${v('p2', 'P2-N-RUNS-E43')} runs of the logistics model.`,
    quote('p2', 'P2-H7-ABSTRACT-SHORT'),
    `At today's fleet they add ${v('p2', 'P2-H8-X1-PCT')} to the delay per delivery; at four times the fleet, ${v('p2', 'P2-H8-X4-PCT')}.`,
    `Referring every road conflict to Earth instead, at the assumed staff time per conflict, raises the delay per delivery ${v('p2', 'P2-UNC-X1-RATIO')}-fold.`,
    quote('p2', 'P2-P6-ABSTRACT-CLAUSE'),
  ];
  const sched = air('scheduled'), slot = air('slotted');
  const p3 = [
    `The market was priced for ${v('p3', 'P3-N-OWNERS')} owners over ${v('p3', 'P3-E46-N-RUNS')} simulated years.`,
    E ? `By a scaled estimate (laptop timing times the flight processor's slowdown), the heaviest safety check takes ${e(E.h10.safety_core_share_flight_per_robot_10hz * 100, ' %', 1, 'h10.safety_core_share_flight_per_robot_10hz')} of one core.` : 'E48 not available.',
    E && robotRound(E) ? `One robot's bid in a market round, timed on a laptop in one month of one seed and scaled by an assumed factor (not flight hardware), takes ${robotRound(E).bid} (99th percentile); the on-robot data were measured at ${robotRound(E).mem} against the ${robotRound(E).estimate} estimate, the interpreter and the code not counted.` : '',
    sched && slot ? `By calculation from LRIP v0.1's message sizes and rates, twenty robots' authenticated traffic needs ${e(sched.channel_kbps_needed, ' kbit/s', 2, 'airtime (scheduled, measured hops)')} of airtime on a channel the base schedules, and ${e(slot.channel_kbps_needed, ' kbit/s', 2, 'airtime (slotted random access, measured hops)')} with random access, against a ${e(E.airtime.channel_kbps, ' kbit/s', 0, 'airtime.channel_kbps')} channel.` : '',
    lrip2('note'),   // F-73: the v0.2 load beside E48's v0.1 airtime
    `The base's mast is in direct view at ${v('p3', 'P3-MESH-MAST-DIRECT-SHARE')} of route points; the rest goes through the mesh.`,
  ].filter(Boolean);
  return `<section class="r-atc" aria-labelledby="h-atc"><h2 id="h-atc">Lunar ATC: the three papers in numbers</h2>`
    + `<p class="prose">Headline results of the three Lunar ATC papers, read from the papers' own values files when the site is built. More on <a href="${base}atc/">the Lunar ATC page</a>, <a href="${base}world/?view=atc">a month with and without the network</a> and <a href="${base}paper/">the papers</a>.</p>`
    + `<div class="r-atc-grid">${card('p1', p1)}${card('p2', p2)}${card('p3', p3)}</div>${familyTable()}</section>`;   // F-69: the Phase 6 hypotheses under the cards
}

// F-71 (B-108): <!--@e44f:lead--> on /atc/ section 5: encounter types rerun on fresh seeds (results/E44_fresh_seeds.json),
// random draws the defect search never saw. Every number from the file; a simulation.
const FRESH_SRC = 'results/E44_fresh_seeds.json';
const KIND = { viol_contact: 'contact', viol_gap: 'a gap below the margin', viol_zone: 'a vehicle still inside a closed landing zone at closure',
  viol_crew: 'a vehicle too close to crew', viol_r3: 'two vehicles inside a one-lane road', viol_slots: 'an over-full pad or junction' };
const WORD = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve'];
export function e44fresh(key) {
  if (key !== 'lead') throw new Error(`E44 fresh seeds: unknown key ${key}`);
  const D = JSON.parse(readFileSync(join(ROOT, FRESH_SRC), 'utf8')), T = D.types, ids = Object.keys(T).sort((a, b) => a - b);
  const m = (value, what, unit = '', digits = 0) => num({ value, unit, digits, flag: 'Modelled', source: `${FRESH_SRC}: ${what} (a simulation)` });
  const and = xs => (xs.length < 2 ? xs.join('') : `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}`);
  const clean = ids.filter(t => T[t].fresh_seeds.violations === 0), bad = ids.filter(t => T[t].fresh_seeds.violations > 0);
  const n = t => m(T[t].fresh_seeds.n, `types.${t}.fresh_seeds.n`);
  let s = `On fresh seeds (task B-108: random draws never used before, for the ${WORD[ids.length] || ids.length} types whose main-run bounds were computed on the seeds where defects were found and fixed), `;
  if (clean.length) s += `type${clean.length > 1 ? 's' : ''} ${and(clean)} again had no violation in ${new Set(clean.map(t => T[t].fresh_seeds.n)).size === 1 ? n(clean[0]) : and(clean.map(n))} encounters${clean.length > 1 ? ' each' : ''}`;
  if (bad.length) s += `${clean.length ? '; ' : ''}` + bad.map(t => {
    const F = T[t].fresh_seeds, kinds = Object.entries(F.violations_by_kind || {}).filter(([, v]) => v > 0).map(([k]) => KIND[k] || k);
    const wb = typeof F.bound_weighted === 'number' ? `, a 95 % upper bound of ${m(100 * F.bound_weighted, `types.${t}.fresh_seeds.bound_weighted`, ' %', 2)} per encounter (weighted)` : '';
    return `type ${t} had ${m(F.violations, `types.${t}.fresh_seeds.violations`)} in ${n(t)}: ${and(kinds)}${wb}`;
  }).join('; ');
  return s.replace(/, $/, '') + '.';
}

// F-72 (B-107): <!--@e45u:rule--> and <!--@e45u:result--> on /atc/ section 5: the keep-distance rule (R1) as P2 now
// proposes it, with the slope term, and the uphill runs (results/E45_uphill.json) that led to it. Every number from the
// file; a simulation. The twelve encounter types were run without the slope term (flat or downhill, where it is inactive).
const UP_SRC = 'results/E45_uphill.json';
export function e45up(key) {
  const D = JSON.parse(readFileSync(join(ROOT, UP_SRC), 'utf8')), C = D.cells, T = D.threshold;
  const sim = (value, what, unit = '', digits = 0) => num({ value, unit, digits, flag: 'Modelled', source: `${UP_SRC}: ${what} (a simulation)` });
  const set = (value, what, unit = '', digits = 0) => num({ value, unit, digits, flag: 'Assumed', source: `${UP_SRC}: ${what} (a setting of the experiment)` });
  const rule = (value, what, unit, digits) => num({ value, unit, digits, flag: 'Spec', source: `${UP_SRC}: ${what} (a setting of the proposed rule)` });
  if (key === 'rule') return `The keep-distance rule (R1) sets the gap to the vehicle ahead from the follower's response time and own braking and from the leader's braking, plus a static margin of ${rule(D.d0_m, 'd0_m', ' m', 0)}. As P2 now proposes it, the leader's braking is the larger of ${rule(D.b_max, 'b_max', ' m/s²', 1)} and what the leader can guarantee on the grade (the slope term): uphill, gravity lets a leader stop harder than that. The twelve encounter types above were run without the slope term; all are flat or downhill, where it is inactive.`;
  if (key !== 'result') throw new Error(`E45 uphill: unknown key ${key}`);
  const contacts = C.reduce((a, c) => a + c.contacts, 0), lag = Math.max(...C.map(c => c.delay_s)), slopes = [...new Set(C.map(c => c.slope_deg))].sort((a, b) => a - b);
  const sloped = C.filter(c => c.rule === 'slope_term'), follow = sloped.filter(c => c.geom === 'following');
  if (follow.some(c => c.gap_below_d0 > 0)) throw new Error(`${UP_SRC}: the slope term leaves a shortfall when following; the /atc/ sentence says it removes every one`);
  const rest = sloped.filter(c => c.gap_below_d0 > 0);
  const short = rest.length ? Math.max(...rest.map(c => D.d0_m - c.min_gap_m)) : 0;
  const restWhere = [...new Set(rest.map(c => `${c.planet === 'mars' ? 'Mars' : 'Moon'} ${c.geom === 'one_lane' ? 'convoy on a one-lane road' : 'following'}${c.delay_s > 0 ? ' with the lag' : ''}`))];
  const thr = (k, pl) => { const v = T[k]?.first_slope_with_gap_below_d0_deg; return typeof v === 'number' ? `${pl} from ${sim(v, `threshold.${k}.first_slope_with_gap_below_d0_deg`, '°', v % 1 ? 1 : 0)}` : null; };
  const where = [thr('moon:following', 'on the Moon'), thr('mars:following', 'on Mars')].filter(Boolean);
  return `Uphill, a separate simulation (task B-107: following and one-lane convoys on the Moon and Mars at ${set(slopes[0], 'cells.slope_deg (lowest)', '°', 0)} to ${set(slopes[slopes.length - 1], 'cells.slope_deg (highest)', '°', 1)}, ${set(D.n_per_cell, 'n_per_cell')} encounters per case, followers at the rule's limit) found ${contacts === 0 ? 'no contact anywhere' : `${sim(contacts, 'Σ cells.contacts')} contacts`}; with the rule as it was and a ${set(lag, 'cells.delay_s (the actuation lag)', ' s', 0)} actuation lag, a braking leader took followers inside the margin when following ${where.join(' and ')}. `
    + `The slope term removes every shortfall when following, on both bodies${rest.length ? `; the ${restWhere.join(' and ')} keeps shortfalls of at most ${sim(short, 'max over the slope_term cells with a shortfall of d0_m − min_gap_m', ' m', 2)}, traced to the lag model and not patched` : ''}.`;
}
