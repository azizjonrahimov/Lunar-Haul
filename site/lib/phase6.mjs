// F-69: Phase 6 at build time.
// <!--@vv6:lead--> on /verification/: the count of recorded Phase 6 checks and the G1 row (every Phase 6 engine option
// off reproduces the Phase 5 run), read from results/vv_phase6.json (B-98).
// familyTable() under the Lunar ATC section of /results/: the confirmatory family of PREREG6 section 4 with Holm
// (results/phase6_family.json): each hypothesis, how it was tested, and what came out. A hypothesis that did not hold
// gets the same weight on the page as one that held: the same chip, in words, with the paper's own summary beside it.
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { ROOT } from './pages.mjs';
import { esc, fmt, num } from '../src/components/num.js';
import { dateNum } from '../src/components/date-num.js';
import { supersededBlock, readingVerdict } from '../src/components/results-file.js';

export const VV6_SRC = 'results/vv_phase6.json', FAMILY_SRC = 'results/phase6_family.json';
const read = rel => (existsSync(join(ROOT, rel)) ? JSON.parse(readFileSync(join(ROOT, rel), 'utf8').replace(/([:[,]\s*)-?(NaN|Infinity)\b/g, '$1null')) : null);

export function vv6(key, D = read(VV6_SRC)) {   // D: the file's contents (a test passes an altered copy)
  if (key !== 'lead') throw new Error(`${VV6_SRC}: unknown key ${key}`);
  if (!D) return 'The Phase 6 checks are not published yet.';
  // F-78 (review W1): the counts come from the rows' own `passed` flags and must agree with the summary; a missing count
  // or a failing G1 stops the build (the sentence says G1 repeats the run of the code before Phase 6)
  const S = D.summary, R = D.rows;
  if (!Array.isArray(R) || !R.length) throw new Error(`${VV6_SRC}: no rows`);
  if (typeof S?.rows !== 'number' || typeof S?.passed !== 'number') throw new Error(`${VV6_SRC}: summary.rows or summary.passed missing`);
  if (R.some(r => typeof r.passed !== 'boolean')) throw new Error(`${VV6_SRC}: a row without a boolean passed`);
  const passed = R.filter(r => r.passed).length;
  if (R.length !== S.rows || passed !== S.passed) throw new Error(`${VV6_SRC}: the rows give ${passed} of ${R.length} passed, the summary ${S.passed} of ${S.rows}`);
  const g1 = R.filter(r => r.id === 'G1');
  if (!g1.length) throw new Error(`${VV6_SRC}: no G1 row`);
  if (!g1.every(r => r.passed)) throw new Error(`${VV6_SRC}: G1 does not pass; the /verification/ sentence says it does`);
  // F-79 (B-118 step 4): G1's main row compares the engine with every option off against a stored run of the code before
  // Phase 6; its scope (one scenario, one seed, the days, the values) is read from the row's basis, and a second G1 row
  // switches one option on to show the comparison can fail. A basis in another form stops the build.
  const main = g1.find(r => r.sub === 'options off');
  if (!main) throw new Error(`${VV6_SRC}: no G1 row with sub "options off"`);
  const b = /^(.+), (\d+) days, seed (\d+): (\d[\d,]*) summary values against (\S+) \(commit (\w+)\)$/.exec(main.basis || '');
  if (!b) throw new Error(`${VV6_SRC}: G1 options-off basis "${main.basis}" is not "<scenario>, <n> days, seed <s>: <n> summary values against <file> (commit <c>)"`);
  const [, scen, days, seed, nv, , commit] = b, nVal = +nv.replace(/,/g, '');
  const on = g1.find(r => r.sub === 'option on changes the run'), o = on && /(\d[\d,]*) of (\d[\d,]*) summary values differ/.exec(on.basis || '');
  if (on && !o) throw new Error(`${VV6_SRC}: G1 option-on basis "${on.basis}" does not say how many summary values differ`);
  if (o && +o[2].replace(/,/g, '') !== nVal) throw new Error(`${VV6_SRC}: G1's two rows compare ${nVal} and ${o[2]} summary values`);
  return `${fmt(passed, 0)} of ${fmt(R.length, 0)} recorded checks pass. Among them G1: with every Phase 6 engine option switched off, the engine `
    + `repeats a run made by the code before Phase 6 (commit ${esc(commit)}) exactly: ${fmt(main.simulated, 0)} of ${fmt(nVal, 0)} summary values differ. `
    + `The check covers one scenario (${esc(scen)}), one seed (seed ${fmt(+seed, 0)}) and ${fmt(+days, 0)} days, ${fmt(nVal, 0)} values`
    + `${o ? `; with one option switched on, ${fmt(+o[1].replace(/,/g, ''), 0)} of them differ, so the check can fail` : ''}.`;
}

// the outcome of one hypothesis from the file's own fields: 'held', 'partly' (some clauses held, some did not) or 'not'
export function outcomeOf(h) {
  const rej = h.holm?.['rejected_at_0.05'];
  if (typeof rej === 'boolean') return rej ? 'held' : 'not';
  const cl = Object.values(h.clauses || {}).filter(c => typeof c.supported === 'boolean');
  if (cl.length) { const k = cl.filter(c => c.supported).length; return k === cl.length ? 'held' : k ? 'partly' : 'not'; }
  if (typeof h.decision === 'string') return /^supported/i.test(h.decision) ? 'held' : /not supported/i.test(h.decision) ? 'not' : 'partly';
  throw new Error(`${FAMILY_SRC}: no outcome for a hypothesis`);
}
// F-70: what the referee round decided (reports/referee_phase6_decisions.md, A1, B1, B2, B4, B8) over the file's verdicts:
// a result fixed by its inputs is a design calculation, a verdict that depends on a reading chosen after the results is
// "depends on the reading", a clause the new lost-link rule makes untestable says so, and H9, H10 are written H9', H10'.
export const DECISIONS_SRC = 'reports/referee_phase6_decisions.md';
export const DECISIONS = {
  H9: { label: 'H9′', clauses: { 'ranging stays inside the budget near the base': 'reading' } },
  H10: { label: 'H10′' },
  H13: { outcome: 'calc', note: 'the load follows from the message sizes and rates, which are inputs, so this is a design calculation rather than a test (decisions A1, B8)' },
  H14: { parts: [['fewer jobs lost under the lost-link rule (exact sign test)', 'holm'], ['no reservation stuck under the rule', 'untestable']],
    note: 'the second clause is not testable as written: a silent holder’s reservation is no longer released; its segment is marked unconfirmed and entered only at caution speed (decisions B1)' },
};
const OUT = { held: 'held', partly: 'held in part', not: 'did not hold', reading: 'depends on the reading', calc: 'design calculation', first: 'held in its first clause', untestable: 'not testable as written' };
const fmtM = v => `${fmt(v, v < 10 ? 1 : 0)} m`;

// F-71 (B-101): H9′'s second clause, "ranging stays inside the budget near the base", under every reading of "near the
// base" (results/E50_near_base.json, fleet at 1x, dead reckoning plus ranging). A simulation on assumed ranging errors.
export const NEAR_SRC = 'results/E50_near_base.json';
const NEAR_KIND = 'a simulation on assumed ranging errors';
const WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];
export function nearBase() {
  const D = read(NEAR_SRC);
  if (!D?.multiples?.['1']?.sets?.['dr+ranging']) throw new Error(`${NEAR_SRC}: no 1x dead reckoning plus ranging set`);
  const M = D.multiples['1'], S = M.sets['dr+ranging'], src = `${NEAR_SRC}: multiples.1`;
  const rows = Object.entries(D.readings).map(([r, label]) => ({
    r, registered: /PREREG6/.test(label),
    label: label.replace(/\s*\((used so far|PREREG6[^)]*)\)/g, '').replace(/\bBASE\b/g, 'base'),
    share: num({ value: 100 * M.share_of_driving[r].mean, unit: ' %', digits: 0, flag: 'Modelled', source: `${src}.share_of_driving.${r}.mean (${NEAR_KIND})` }),
    p95: num({ value: S[r].in_p95_m_mean, unit: ' m', digits: 1, flag: 'Modelled', source: `${src}.sets.dr+ranging.${r}.in_p95_m_mean (${NEAR_KIND})` }),
    inside: S[r].seeds_inside_budget, seeds: S[r].seeds_with_steps, verdict: readingVerdict(S[r]),
  }));
  // F-81: a reading no seed has steps inside is not judged (B-118 N19): never "held", and never the registered one
  const reg = rows.find(x => x.registered), held = rows.filter(x => x.verdict === 'holds');
  if (!reg) throw new Error(`${NEAR_SRC}: no reading marked as PREREG6's words`);
  if (reg.verdict === 'not judged') throw new Error(`${NEAR_SRC}: the registered reading is not judged at 1x (no seed has steps inside it); /protocol/ gives its value`);
  const budget = num({ value: D.budget_m, unit: ' m', digits: 0, flag: 'Spec', source: `${NEAR_SRC}: budget_m (the separation the traffic rules assume)` });
  const seedsSay = x => ({ 'not judged': 'is not judged (no seed has steps inside it)', fails: 'fails in every seed', holds: 'holds in every seed' })[x.verdict] || `holds in ${x.inside} of ${x.seeds} seeds`;
  return { rows, reg, held, budget, seedsSay, count: rows.length, verdict: D.verdict || '' };
}
// <!--@nb:clause2--> on /protocol/ problem 1: the clause in one sentence, every number from the file
export function nb(key) {
  if (key !== 'clause2') throw new Error(`near base: unknown key ${key}`);
  const N = nearBase(), h = N.held[0];
  if (!/depends on the reading/.test(N.verdict)) throw new Error(`${NEAR_SRC}: verdict is no longer "depends on the reading"`);
  const first = h ? `Read as “${esc(h.label)}” (${h.share} of driving), the error’s 95th percentile is ${h.p95} and the clause ${N.seedsSay(h)}` : 'No reading keeps it inside the budget';
  return `Whether ranging keeps the error inside the budget near the base depends on what “near” means. ${first}; read as the registered
          wording, “${esc(N.reg.label)}”, it is ${N.reg.p95} against ${N.budget} and ${N.seedsSay(N.reg)}.${nearLarger(N)} The papers report all ${WORDS[N.count] || N.count}
          readings, so the second clause of H9&prime; depends on the reading (${NEAR_KIND}).`;
}
// F-80 (B-118): the larger fleets the file holds (4x, 8x since the regenerated runs) give the same verdict under every
// reading as 1x, or the build stops; the sentence gives their seeds and the two readings /protocol/ names.
// F-81: a reading no seed has steps inside (seeds_with_steps 0) is not judged, not "fails": it is left out of the
// comparison and named as not judged, and the sentence then says "every reading judged", never "every reading"
export function nearLarger(N, D = read(NEAR_SRC)) {
  const ks = Object.keys(D.multiples).filter(k => k !== '1').sort((a, b) => a - b);
  if (!ks.length) return '';
  const S1 = D.multiples['1'].sets['dr+ranging'], set = k => D.multiples[k].sets['dr+ranging'];
  const say = (k, r) => readingVerdict(set(k)[r]), nj = [];
  for (const k of ks) {
    if (!D.multiples[k].sets?.['dr+ranging']) throw new Error(`${NEAR_SRC}: multiples.${k} has no dead reckoning plus ranging set`);
    for (const r of Object.keys(D.readings)) {
      const a = say(k, r), b = readingVerdict(S1[r]);
      if (a === 'not judged' || b === 'not judged') { if (a === 'not judged') nj.push([k, r]); continue; }
      if (a !== b || a === 'mixed') throw new Error(`${NEAR_SRC}: at ${k}x the reading ${r} ${a}, at 1x it ${b}; the /protocol/ sentence says the verdicts are the same`);
    }
  }
  const src = (k, what) => `${NEAR_SRC}: multiples.${k}.${what} (${NEAR_KIND})`;
  const v = (k, r) => (say(k, r) === 'not judged' ? 'not judged' : num({ value: set(k)[r].in_p95_m_mean, unit: ' m', digits: 1, flag: 'Modelled', source: src(k, `sets.dr+ranging.${r}.in_p95_m_mean`) }));
  const n = k => { const s = D.multiples[k].seeds; if (!Array.isArray(s)) throw new Error(`${NEAR_SRC}: multiples.${k}.seeds is not a list`); return num({ value: s.length, digits: 0, flag: 'Modelled', source: src(k, 'seeds (the seeds run)') }); };
  const list = f => (ks.length > 1 ? `${ks.slice(0, -1).map(f).join(', ')} and ${f(ks[ks.length - 1])}` : f(ks[0]));
  const and = xs => (xs.length > 1 ? `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}` : xs[0]);
  const lab = r => N.rows.find(x => x.r === r)?.label || r;
  const same = nj.length ? `every reading judged gives the verdict of today’s fleet (${and(nj.map(([k, r]) => `“${esc(lab(r))}” at ${WORDS[k] || k} times`))} ${nj.length > 1 ? 'are' : 'is'} not judged: no seed has steps inside ${nj.length > 1 ? 'them' : 'it'})` : 'every reading gives the same verdict';
  const h = N.held[0];
  return ` At ${list(k => WORDS[k] || k)} times the fleet (${list(n)} seeds) ${same}${h ? `: ${list(k => v(k, h.r))} under the first reading,` : ','} ${list(k => v(k, N.reg.r))} under the registered wording.`;
}
const fmtH = v => `${fmt(v, 2).replace(/^-/, '−')} h`, fmtP = v => (v < 0.001 ? '< 0.001' : fmt(v, 2));
// F-70c: a clause decided by its own sampling test (H10′): held when its p is below alpha; the values the file gives
// for it, the fleet sizes read from its gap_<m>x_h keys (4x and 8x since B-90's 8x addendum)
function testedClause(name, c, alpha) {
  const p = typeof c.p === 'number' ? c.p : c.p_one_sided;
  const gaps = Object.keys(c).map(k => /^gap_(\d+)x_h$/.exec(k)).filter(Boolean).map(m => +m[1]).sort((x, y) => x - y);
  let v;
  if (gaps.length) v = 'gap ' + gaps.map(m => `${fmtH(c[`gap_${m}x_h`])} at ${m}x${typeof c[`n_${m}x`] === 'number' ? ` with ${c[`n_${m}x`]} seeds` : ''}`).join(', ');
  else if (typeof c.margin_h === 'number') v = `difference ${fmtH(c.mean_diff_h)} against a margin of ${fmtH(c.margin_h)}`;
  else v = `difference ${fmtH(c.mean_diff_h)}, p ${fmtP(p)}`;
  return [name, p < alpha ? 'held' : 'not', v];
}

export function familyRows(F, D = DECISIONS) {
  // F-78 (review W1): a decision that names a hypothesis or a clause the file does not have stops the build
  for (const [id, dec] of Object.entries(D)) {
    if (!F.hypotheses?.[id]) throw new Error(`${FAMILY_SRC}: no hypothesis ${id}, which ${DECISIONS_SRC} decides`);
    for (const name of Object.keys(dec.clauses || {})) if (!F.hypotheses[id].clauses?.[name]) throw new Error(`${FAMILY_SRC}: ${id} has no clause “${name}”, which ${DECISIONS_SRC} decides`);
  }
  return Object.entries(F.hypotheses).map(([id, h]) => {
    const dec = D[id] || {}, label = dec.label || id, base = outcomeOf(h);
    let outcome = base, parts = null, note = dec.note || '';
    if (dec.outcome) outcome = dec.outcome;
    if (h.clauses && Object.values(h.clauses).some(c => typeof c.supported === 'boolean')) {
      parts = Object.entries(h.clauses).map(([name, c]) => [name, dec.clauses?.[name] || (c.supported ? 'held' : 'not'), typeof c.value_m === 'number' ? fmtM(c.value_m) : '']);
      if (parts.some(([, o]) => o === 'reading')) {
        outcome = 'reading';
        const N = nearBase(), i = parts.findIndex(([, o]) => o === 'reading');
        parts[i] = [parts[i][0], 'reading', '', `<ul class="r-parts r-readings">${N.rows.map(x => `<li>${esc(x.label)}${x.registered ? ' (the registered wording)' : ''}, ${x.share} of driving: ${x.p95}, ${N.seedsSay(x)}</li>`).join('')}</ul>`];
        note = `the near-base clause holds only under ${N.held.length ? N.held.map(x => `the reading “${x.label}”`).join(' and ') : 'no reading'}, chosen after the results; under the registered wording it ${N.seedsSay(N.reg)}; the papers report all ${WORDS[N.count] || N.count} readings (decisions B4)`;
      }
    } else if (h.clauses && Object.values(h.clauses).some(c => typeof (c.p ?? c.p_one_sided) === 'number')) {
      parts = Object.entries(h.clauses).map(([name, c]) => testedClause(name, c, F.alpha ?? 0.05));
      note = h.p_intersection_union !== undefined ? 'the clauses are joined by intersection-union: the hypothesis holds only if every clause does' : note;
    }
    if (dec.parts) {
      parts = dec.parts.map(([name, how]) => [name, how === 'holm' ? base : how, '']);
      outcome = parts[0][1] === 'held' && parts.slice(1).every(([, o]) => o === 'untestable') ? 'first' : outcome;
    }
    return {
      id, label, outcome, parts, note, kind: dec.outcome === 'calc' ? 'design calculation' : /^threshold comparison/i.test(h.test || '') ? 'threshold comparison' : 'sampling test, Holm',
      test: (h.test || '').replace(/^threshold comparison \(no sampling test\):\s*/i, ''), summary: (F.summary?.[id] || h.decision || '').replace(dec.outcome === 'calc' ? /^supported:\s*/i : /$^/, ''),
      p: h.holm && typeof h.holm.p_adjusted === 'number' ? h.holm.p_adjusted : null,
    };
  });
}

export function familyTable() {
  const F = read(FAMILY_SRC);
  if (!F) return '';
  const rows = familyRows(F), p = v => (v < 0.001 ? '< 0.001' : fmt(v, 3));
  const what = r => r.parts
    ? `<ul class="r-parts">${r.parts.map(([n, o, v, sub]) => `<li>${esc(n)}${v && !/^[a-z]/i.test(v) ? ` (${esc(v)})` : ''}: <b>${OUT[o]}</b>${/^[a-z]/i.test(v) ? `; ${esc(v)}` : ''}${sub || ''}</li>`).join('')}</ul>${r.note ? `<p class="muted">${esc(r.note)}.</p>` : ''}`
    : `${esc(r.summary)}${r.note ? `<p class="muted">${esc(r.note)}.</p>` : ''}`;
  const tally = rows.map(r => `${r.label} ${OUT[r.outcome]}`).join('; ');
  return `<section class="r-fam" aria-labelledby="r-fam-h"><h3 id="r-fam-h">Phase 6: what the hypotheses came to</h3>
    <p class="prose small">The confirmatory family registered before the runs (${esc(F.family.replace(/\bH9\b/g, 'H9′').replace(/\bH10\b/g, 'H10′'))}), read as the
      referee round decided (${DECISIONS_SRC}): ${esc(tally)}.</p>
    <div class="r-scroll"><table class="r-table r-fam-table"><caption>Hypotheses of Phase 6, from ${FAMILY_SRC}${F.pending ? `. Still to come: ${esc(F.pending)}` : ''}.</caption>
      <thead><tr><th scope="col">Hypothesis</th><th scope="col">Outcome</th><th scope="col">What the runs showed</th><th scope="col">How it was tested</th><th scope="col">Holm p</th></tr></thead>
      <tbody>${rows.map(r => `<tr><th scope="row">${esc(r.label)}</th><td data-label="Outcome"><span class="r-out r-out-${r.outcome}">${OUT[r.outcome]}</span></td>`
        + `<td class="small" data-label="What the runs showed">${what(r)}</td><td class="small" data-label="How it was tested"><span class="muted">${esc(r.kind)}:</span> ${esc(r.test)}</td><td class="small" data-label="Holm p">${r.p === null ? '–' : p(r.p)}</td></tr>`).join('')}</tbody></table></div>${familyWas(F, rows)}</section>`;
}

// F-80 (B-118 N14/N15): the values the table showed before the code review's fixes, each named once with the flagged date
// (the file's superseded_* block, and the near-base file's for the readings); only a value whose shown text changed is
// named, and the note says whether every outcome stayed as it was.
// F-81: the one superseded_* block of each file (none, or two after a second supersession, stops the build, since the
// /results/ table always prints the note), and a cause per value: the family block keeps every hypothesis, so the
// cause of a value is read from the superseded_* reason of the file that hypothesis comes from (HYP_SRC); a changed value
// whose file has no block, or a reason that names no cause known here (CAUSES), stops the build rather than borrow the
// family block's reason (the positioning fix) for a value it did not move
const HYP_SRC = { H9: 'results/E50_summary.json', H10: 'results/E50_summary.json', H13: 'results/E53_bitrate.json', H14: 'results/E54_dtn.json', H15a: 'results/E56_integrity.json' };
const CAUSES = [[/positioning fix/, 'a fix to the positioning model'], [/dtn\.py fixes/, 'fixes to the lost-link replay']];
function causeOf(file, iso) {
  const D = read(file);
  if (!D) throw new Error(`${file}: missing; the /results/ note names the cause of a value from it`);
  const S = supersededBlock(D, file, b => b.superseded_on === iso && typeof b.reason === 'string');
  const c = CAUSES.find(([re]) => re.test(S.doc.reason));
  if (!c) throw new Error(`${file}: ${S.key}.reason names no cause the /results/ note knows (${S.doc.reason.slice(0, 80)}...)`);
  return c[1];
}
export function familyWas(F, rows = familyRows(F)) {
  const fk = supersededBlock(F, FAMILY_SRC, b => b.hypotheses).key;
  const O = F[fk], oldRows = familyRows({ ...O, summary: F.summary }), cause = {};
  const was = (value, unit, digits, src) => num({ value, unit, digits, flag: 'Modelled', source: `${src} (as published before the fix)` });
  const fsrc = path => `${FAMILY_SRC}: ${fk}.hypotheses.${path}`;
  for (const [id, h] of Object.entries(O.hypotheses)) {
    const now = F.hypotheses[id], label = DECISIONS[id]?.label || id, got = [];
    if (!now) continue;
    for (const [name, c] of Object.entries(h.clauses || {})) {
      const n = now.clauses?.[name];
      if (!n) continue;
      if (typeof c.value_m === 'number' && DECISIONS[id]?.clauses?.[name] !== 'reading' && fmtM(c.value_m) !== fmtM(n.value_m)) got.push(`${was(c.value_m, ' m', c.value_m < 10 ? 1 : 0, fsrc(`${id}.clauses.${name}.value_m`))} for “${esc(name)}”`);
      const gaps = Object.keys(c).map(k => /^gap_(\d+)x_h$/.exec(k)).filter(m => m && +m[1] > 1).map(m => m[1]);
      const gs = gaps.filter(m => typeof n[`gap_${m}x_h`] === 'number' && fmtH(c[`gap_${m}x_h`]) !== fmtH(n[`gap_${m}x_h`]));
      if (gs.length) got.push(`a gap of ${gs.map(m => `${was(c[`gap_${m}x_h`], ' h', 2, fsrc(`${id}.clauses.${name}.gap_${m}x_h`)).replace('>-', '>−')} at ${m}x`).join(' and ')}`);
      if (!gaps.length && typeof c.mean_diff_h === 'number' && typeof c.margin_h !== 'number' && fmtH(c.mean_diff_h) !== fmtH(n.mean_diff_h)) got.push(`a difference of ${was(c.mean_diff_h, ' h', 2, fsrc(`${id}.clauses.${name}.mean_diff_h`))} for “${esc(name)}”`);
    }
    const hp = h.holm?.p_adjusted, np = now.holm?.p_adjusted;
    if (typeof hp === 'number' && typeof np === 'number' && fmt(hp, 3) !== fmt(np, 3) && hp >= 0.001) {
      // a Holm p moves with the hypothesis's own p, or with another's through the step-down order: the cause is named only
      // in the first case
      const own = x => (typeof x.p_intersection_union === 'number' ? x.p_intersection_union : x.p);
      if (own(h) === own(now)) throw new Error(`${FAMILY_SRC}: ${id}'s Holm p changed while its own p did not; the /results/ note cannot name one cause`);
      got.push(`Holm p ${was(hp, '', 3, fsrc(`${id}.holm.p_adjusted`))}`);
    }
    if (got.length) {
      if (!HYP_SRC[id]) throw new Error(`${FAMILY_SRC}: no source file known for ${id}, whose earlier values the /results/ note names`);
      const c = causeOf(HYP_SRC[id], O.superseded_on);
      (cause[c] ||= []).push(`${esc(label)} gave ${got.join(', ')}`);
    }
  }
  // the near-base readings the table lists under H9′ (results/E50_near_base.json, 1x, dead reckoning plus ranging)
  const NB = read(NEAR_SRC), nk = supersededBlock(NB, NEAR_SRC, b => b.multiples?.['1']).key;
  {
    const S = NB[nk].multiples['1'].sets['dr+ranging'], C = NB.multiples['1'].sets['dr+ranging'];
    const ch = Object.keys(NB.readings).filter(r => S[r] && fmt(S[r].in_p95_m_mean, 1) !== fmt(C[r].in_p95_m_mean, 1));
    if (ch.length) (cause[causeOf(NEAR_SRC, O.superseded_on)] ||= []).push(`the readings near the base were ${ch.map(r => `${was(S[r].in_p95_m_mean, ' m', 1, `${NEAR_SRC}: ${nk}.multiples.1.sets.dr+ranging.${r}.in_p95_m_mean`)} (“${esc(NB.readings[r].replace(/\s*\((used so far|PREREG6[^)]*)\)/g, '').replace(/\bBASE\b/g, 'base'))}”)`).join(', ')}`);
    if (NB[nk].superseded_on !== O.superseded_on) throw new Error(`${NEAR_SRC} and ${FAMILY_SRC} were superseded on different dates; the /results/ note gives one`);
  }
  const cs = Object.keys(cause);
  if (!cs.length) return '';
  const changed = rows.filter(r => oldRows.find(o => o.id === r.id)?.outcome !== r.outcome).map(r => r.label);
  const date = dateNum({ iso: O.superseded_on, source: `${FAMILY_SRC}: ${fk}.superseded_on (the date the values were replaced)` });
  // one cause: "(a fix to the positioning model): before, ..."; more: "before a fix to the positioning model, ...; before ..."
  const said = cs.length === 1 ? ` (${cs[0]}): before, ${cause[cs[0]].join('; ')}` : `: ${cs.map(c => `before ${c}, ${cause[c].join('; ')}`).join('; ')}`;
  return `<p class="small muted r-fam-was">Corrected after a code review on ${date}${said}. `
    + `${changed.length ? `The outcome changed for ${esc(changed.join(' and '))}.` : 'Every outcome is as it was.'}</p>`;
}
