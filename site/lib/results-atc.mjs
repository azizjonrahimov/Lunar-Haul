// F-56: the Lunar ATC section of /results/ (<!--@results-atc-->): the three papers' headline numbers, read at build time
// from paper/<id>/values.json (the papers' own values files; pre-formatted strings) and, for P3's computing and radio
// numbers that its values file does not carry, results/E48_sizing.json, and for P1's learned-bid rerun,
// results/ATC_learned_eval_fixpoint.json (F-74, F-82). Nothing is typed.
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

// F-74, F-82 (B-122): P1's learned-bid evaluation on the engine of the registered test, with the dispatch fixed point
// (results/ATC_learned_eval_fixpoint.json; P1 section 5.6). The 12 Nov rerun (results/ATC_learned_eval_rerun.json) ran
// without the fixed point; it is read only for the earlier bulk-cargo value that the guard sentence names. The headline stays
// the registered E40 test (P1-H4-*, from values.json). The sentences say what the intervals say: a file that moves an interval
// across zero, or a guard metric that gets worse, fails the build.
export const LR_SRC = 'results/ATC_learned_eval_fixpoint.json';
export const LR_OLD = 'results/ATC_learned_eval_rerun.json';
const WORSE_IF_LOWER = new Set(['delivered_kg']);   // every other guard metric is a wait, a delay, a backlog or a count of starved items
export function p1learned(key, D = JSON.parse(readFileSync(join(ROOT, LR_SRC), 'utf8')), O = JSON.parse(readFileSync(join(ROOT, LR_OLD), 'utf8'))) {   // D, O: the files, or a test's copies
  const E = D.eval, G = D.guards;
  const loads = Object.keys(E).map(Number).sort((a, b) => a - b), [lo, hi] = [loads[0], loads[loads.length - 1]];
  const gl = Object.keys(G).map(Number).sort((a, b) => a - b);
  if (gl.join() !== loads.join()) throw new Error(`${LR_SRC}: guard loads ${gl} differ from evaluation loads ${loads}`);
  const fail = m => { throw new Error(`${LR_SRC}: ${m}; the P1 sentences on /results/ and /paper/ no longer hold`); };
  if (!/change 5 on/i.test(String(D.engine))) fail('the file does not say it ran with PREREG change 5 (the dispatch fixed point)');
  if (!/WITHOUT PREREG change 5/.test(String(O.engine_note_b122 || ''))) throw new Error(`${LR_OLD}: no engine_note_b122 saying it ran without the fixed point`);
  const below = c => c[1] < 0, above = c => c[0] > 0, zero = c => c[0] <= 0 && c[1] >= 0;
  const g = (l, m) => G[l][m].linear_minus_hand;
  for (const l of loads) {
    if (!below(E[l].linear.vs_hand_h.ci95)) fail(`the linear correction's gain at ${l} % is not below zero`);
    if (!zero(E[l].mlp.vs_hand_h.ci95)) fail(`the network's difference at ${l} % excludes zero`);
    for (const m of Object.keys(G[l])) if ((WORSE_IF_LOWER.has(m) ? below : above)(g(l, m).ci95)) fail(`at ${l} % the guard's ${m} got worse`);
  }
  const OTHER = ['atc_urgent_wait_mean_cens_h', 'delay_prio2_mean_h', 'delay_mean_bulk', 'tonne_days_waiting'];
  for (const m of OTHER) if (!below(g(hi, m).ci95)) fail(`at ${hi} % the guard's ${m} is not below zero`);
  if (!below(g(lo, 'atc_urgent_wait_mean_cens_h').ci95)) fail(`at ${lo} % the guard's urgent gain is not below zero`);
  if (!zero(g(lo, 'delay_mean_bulk').ci95)) fail(`at ${lo} % the guard's bulk delay excludes zero`);
  const OB = O.guards[lo].delay_mean_bulk.linear_minus_hand;
  if (!above(OB.ci95)) throw new Error(`${LR_OLD}: the earlier bulk delay at ${lo} % is not above zero; the guard sentence no longer holds`);
  const nE = new Set(loads.flatMap(l => ['linear', 'mlp'].map(p => E[l][p].vs_hand_h.n))), nG = new Set(gl.flatMap(l => OTHER.map(m => g(l, m).n)));
  if (nE.size !== 1 || nG.size !== 1) fail('seed counts differ between cells');
  const set = (value, what, unit = '') => num({ value, unit, digits: 0, flag: 'Assumed', source: `${LR_SRC}: ${what} (a setting of the evaluation)` });
  const load = l => set(l, `eval/guards key ${l}`, ' %');
  const pct = (l, p) => num({ value: -100 * E[l][p].vs_hand_share, unit: ' %', digits: 1, flag: 'Modelled', source: `${LR_SRC}: eval.${l}.${p}.vs_hand_share (a cut, so shown without its minus sign)` });
  const hr = (x, what, src = LR_SRC) => num({ value: x, unit: ' h', digits: 2, flag: 'Modelled', source: `${src}: ${what}` });
  const ci = (c, what, src = LR_SRC) => `${hr(c[0], `${what}.ci95[0]`, src)} to ${hr(c[1], `${what}.ci95[1]`, src)}`;
  const U = g(lo, 'atc_urgent_wait_mean_cens_h'), B = g(lo, 'delay_mean_bulk');
  const uw = `guards.${lo}.atc_urgent_wait_mean_cens_h.linear_minus_hand`, bw = `guards.${lo}.delay_mean_bulk.linear_minus_hand`;
  if (key === 'rerun') return `The separate evaluation of the learned bids, run on the engine of that test (with the dispatch fixed point) on its ${set([...nE][0], 'eval.*.vs_hand_h.n')} seeds, found the linear correction cutting the urgent wait by ${pct(lo, 'linear')} at ${load(lo)} load and by ${pct(hi, 'linear')} at ${load(hi)}, in agreement with that test, and the network still not distinguishable from hand-built bids. The bids were trained on an engine without the fixed point and not retrained.`;
  if (key === 'guard') return `Whether other cargo pays for the gain was checked on ${set([...nG][0], 'guards.*.*.linear_minus_hand.n')} further runs per load: at neither load did any measure of other cargo get worse. At ${load(hi)} load urgent, normal-priority and bulk cargo all waited less. At ${load(lo)} load the urgent wait fell by ${hr(-U.mean, `${uw}.mean (sign dropped: a fall)`)} (interval ${ci(U.ci95, uw)}) and the change for bulk cargo could not be told from zero (${hr(B.mean, `${bw}.mean`)}, interval ${ci(B.ci95, bw)}). An earlier rerun on an engine without the fixed point had bulk cargo waiting ${hr(OB.mean, `guards.${lo}.delay_mean_bulk.linear_minus_hand.mean`, LR_OLD)} longer at ${load(lo)} load (interval ${ci(OB.ci95, `guards.${lo}.delay_mean_bulk.linear_minus_hand`, LR_OLD)}).`;
  throw new Error(`P1 learned bids: unknown key ${key}`);
}

// F-81: committed, so a missing file stops the build (no "not available" on a green build)
const noRound = () => { throw new Error('results/E48_sizing.json: no per_robot_round or measured_memory; the /results/ P3 card reads them'); };
function e48() { const p = join(ROOT, 'results', 'E48_sizing.json'); if (!existsSync(p)) throw new Error('results/E48_sizing.json missing; the /results/ P3 card reads it'); return JSON.parse(readFileSync(p, 'utf8').replace(/\bNaN\b/g, 'null')); }

// a sentence the paper itself writes (a values-file key holding prose): quoted as it stands, its numbers included
export function quote(id, key) { return `<q class="r-quote" data-src="paper/${id}/values.json ${key}">${paperValue(id, key)}</q>`; }

export function atcResults(base = '/') {
  for (const c of cardKeyChanges()) console.warn(`[results cards] paper/${c.id}/values.json ${c.key} ${c.was} since the cards were checked; reread the card, then run node scripts/lock-cards.mjs: "${c.text}"`);
  const v = pv, E = e48(), SZ = 'results/E48_sizing.json';
  const e = (value, unit, digits, src) => num({ value, unit, digits, flag: 'Modelled', source: `${SZ}: ${src}` });
  const air = a => E?.airtime?.rows?.find(r => r.sizes.startsWith('LRIP secured, MAC 8') && String(r.hops).startsWith('measured') && r.access.startsWith(a));
  const card = (id, items) => `<article class="r-atc-card" aria-labelledby="r-atc-${id}"><p class="r-atc-k">${id.toUpperCase()}</p>`
    + `<h3 class="r-atc-h" id="r-atc-${id}">${paperField(id, 'title')}</h3><ul>${items.map(t => `<li>${t}</li>`).join('')}</ul>`
    + `<p class="small muted r-atc-src">Read from <code>paper/${id}/values.json</code>${id === 'p3' ? ' and <code>results/E48_sizing.json</code>' : id === 'p1' ? ` and <code>${LR_SRC}</code>` : ''} when the site is built.</p></article>`;
  const p1 = [
    `${v('p1', 'P1-N-RUNS-ALL')} simulated years in three experiments, at most ${v('p1', 'P1-N-RUNS-DISTINCT-MAX')} of them distinct (${v('p1', 'P1-E40-N-DISTINCT')} distinct of ${v('p1', 'P1-E40-N-RUNS')} in the main experiment), under ${v('p1', 'P1-N-REGIMES')} decision regimes.`,
    `A shared dispatcher on Earth that stops when Earth sets kept urgent cargo waiting for pickup ${v('p1', 'P1-H2-STRICT-MINUS-O')} longer than one that never stops; planning ahead before each blackout left ${v('p1', 'P1-PLAN-MINUS-O')} of that.`,
    `The robots' own auction, at message loss ${v('p1', 'P1-LOSS-MAIN')}, kept urgent cargo waiting for pickup ${v('p1', 'P1-H3A-DIFF')} than the full-information marketplace; its interval, ${v('p1', 'P1-H3A-CI90')}, includes zero, so the runs cannot tell the two apart.`,
    `The registered learned bid, a small network, did not beat hand-built bids (difference ${v('p1', 'P1-H4-MLP-DIFF-30')}, interval ${v('p1', 'P1-H4-MLP-CI-30')}); a linear correction registered as secondary cut the urgent wait by ${v('p1', 'P1-H4-LIN-PCT-30')}. ${p1learned('rerun')}`,
    p1learned('guard'),   // F-74: P1 section 5.6, from the rerun file
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
    `By a scaled estimate (laptop timing times the flight processor's slowdown), the heaviest safety check takes ${e(E.h10.safety_core_share_flight_per_robot_10hz * 100, ' %', 1, 'h10.safety_core_share_flight_per_robot_10hz')} of one core.`,
    (robotRound(E) || noRound()) ? `One robot's bid in a market round, timed on a laptop in one month of one seed and scaled by an assumed factor (not flight hardware), takes ${robotRound(E).bid} (99th percentile); the on-robot data were measured at ${robotRound(E).mem} against the ${robotRound(E).estimate} estimate, the interpreter and the code not counted.${robotRound(E).was ? ` ${robotRound(E).was}` : ''}` : '',
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
  return s.replace(/, $/, '') + '.' + reqRule6(D, m);
}

// F-76 (B-112): the request-rule variant on all the fresh type-6 encounters (key request_rule_fresh_6), as P2 part 4 gives
// it: exploratory, the type-6 verdict unchanged, and most of these encounters incomplete under either rule. The build stops
// if the file no longer says what the sentence says.
export function reqRule6(D, m = x => String(x.value ?? x)) {
  const V = D.request_rule_fresh_6;
  if (!V) return '';
  const K = 'request_rule_fresh_6', a = V.rules_as_written, b = V.request_rule_variant, f6 = D.types['6'].fresh_seeds;
  const fail = w => { throw new Error(`${FRESH_SRC}: ${K}: ${w}; the /atc/ sentence on the request rule no longer holds`); };
  if (a.n !== f6.n || a.violations !== f6.violations || a.outcomes.incomplete !== f6.outcomes.incomplete) fail('its rule-as-written block is not the fresh type-6 run');
  if (b.n !== a.n || !V.paired_same_specs) fail('the variant did not run on the same encounters');
  if (b.violations !== 0 || a.violations < 1) fail('the variant is not clean against a violating rule as written');
  if (V.new_failures_vs_rules_as_written.count !== 0) fail('an encounter that finished under the rule as written fails under the variant');
  if (b.outcomes.finished !== a.outcomes.finished) fail('the variant changes how many encounters finish');
  const o = (x, k, w) => m(x.outcomes[k], `${K}.${w}.outcomes.${k}`);
  return ` A request rule chosen after that violation was seen, under which a vehicle requests a resource only when no hold point it cannot pass lies before it, was then run on all ${m(b.n, `${K}.request_rule_variant.n`)} fresh type-6 encounters with the same specifications: it allowed ${m(b.violations, `${K}.request_rule_variant.violations`)} violations against ${m(a.violations, `${K}.rules_as_written.violations`)}, and no encounter that finished under the rule as written failed under it. Because it was chosen after the fact, the result is exploratory and type 6 still fails under the rule as written. It did not make more encounters finish: ${o(b, 'finished', 'request_rule_variant')} finished under either rule, and ${o(b, 'incomplete', 'request_rule_variant')} (${m(100 * b.outcomes.incomplete / b.n, `${K}.request_rule_variant.outcomes.incomplete / n`, ' %', 0)}) ended incomplete against ${o(a, 'incomplete', 'rules_as_written')}.`;
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
