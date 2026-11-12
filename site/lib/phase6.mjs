// F-69: Phase 6 at build time.
// <!--@vv6:lead--> on /verification/: the count of recorded Phase 6 checks and the G1 row (every Phase 6 engine option
// off reproduces the Phase 5 run), read from results/vv_phase6.json (B-98).
// familyTable() under the Lunar ATC section of /results/: the confirmatory family of PREREG6 section 4 with Holm
// (results/phase6_family.json): each hypothesis, how it was tested, and what came out. A hypothesis that did not hold
// gets the same weight on the page as one that held: the same chip, in words, with the paper's own summary beside it.
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { ROOT } from './pages.mjs';
import { esc, fmt } from '../src/components/num.js';

export const VV6_SRC = 'results/vv_phase6.json', FAMILY_SRC = 'results/phase6_family.json';
const read = rel => (existsSync(join(ROOT, rel)) ? JSON.parse(readFileSync(join(ROOT, rel), 'utf8').replace(/([:[,]\s*)-?(NaN|Infinity)\b/g, '$1null')) : null);

export function vv6(key) {
  const D = read(VV6_SRC);
  if (key !== 'lead') throw new Error(`${VV6_SRC}: unknown key ${key}`);
  if (!D) return 'The Phase 6 checks are not published yet.';
  const S = D.summary || {}, g1 = (D.rows || []).filter(r => r.id === 'G1');
  if (!g1.length) throw new Error(`${VV6_SRC}: no G1 row`);
  const main = g1[0], n = /(\d[\d,]*) summary values/.exec(main.basis || '')?.[1];
  return `${fmt(S.passed ?? 0, 0)} of ${fmt(S.rows ?? 0, 0)} recorded checks pass. Among them G1: with every Phase 6 engine option switched off, the engine `
    + `gives the Phase 5 run back exactly${n ? `: ${fmt(main.simulated, 0)} of ${n} summary values differ` : ''} (${esc((main.basis || '').replace(/:\s*\d[\d,]* summary values compared\s*$/, ''))}), so the new parts change nothing they are not asked to.`;
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
  return Object.entries(F.hypotheses).map(([id, h]) => {
    const dec = D[id] || {}, label = dec.label || id, base = outcomeOf(h);
    let outcome = base, parts = null, note = dec.note || '';
    if (dec.outcome) outcome = dec.outcome;
    if (h.clauses && Object.values(h.clauses).some(c => typeof c.supported === 'boolean')) {
      parts = Object.entries(h.clauses).map(([name, c]) => [name, dec.clauses?.[name] || (c.supported ? 'held' : 'not'), typeof c.value_m === 'number' ? fmtM(c.value_m) : '']);
      if (parts.some(([, o]) => o === 'reading')) {
        outcome = 'reading';
        note = `the near-base clause passes only under the reading “${F.region_rule || 'two or more beacons in line of sight'}”, chosen after the results; the paper reports it under four readings (decisions B4)`;
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
  const E50 = read('results/E50_summary.json'); if (E50?.design?.region_rule) F.region_rule = E50.design.region_rule.replace(/^near base = /, '');
  const rows = familyRows(F), p = v => (v < 0.001 ? '< 0.001' : fmt(v, 3));
  const what = r => r.parts
    ? `<ul class="r-parts">${r.parts.map(([n, o, v]) => `<li>${esc(n)}${v && !/^[a-z]/i.test(v) ? ` (${esc(v)})` : ''}: <b>${OUT[o]}</b>${/^[a-z]/i.test(v) ? `; ${esc(v)}` : ''}</li>`).join('')}</ul>${r.note ? `<p class="muted">${esc(r.note)}.</p>` : ''}`
    : `${esc(r.summary)}${r.note ? `<p class="muted">${esc(r.note)}.</p>` : ''}`;
  const tally = rows.map(r => `${r.label} ${OUT[r.outcome]}`).join('; ');
  return `<section class="r-fam" aria-labelledby="r-fam-h"><h3 id="r-fam-h">Phase 6: what the hypotheses came to</h3>
    <p class="prose small">The confirmatory family registered before the runs (${esc(F.family.replace(/\bH9\b/g, 'H9′').replace(/\bH10\b/g, 'H10′'))}), read as the
      referee round decided (${DECISIONS_SRC}): ${esc(tally)}.</p>
    <div class="r-scroll"><table class="r-table r-fam-table"><caption>Hypotheses of Phase 6, from ${FAMILY_SRC}${F.pending ? `. Still to come: ${esc(F.pending)}` : ''}.</caption>
      <thead><tr><th scope="col">Hypothesis</th><th scope="col">Outcome</th><th scope="col">What the runs showed</th><th scope="col">How it was tested</th><th scope="col">Holm p</th></tr></thead>
      <tbody>${rows.map(r => `<tr><th scope="row">${esc(r.label)}</th><td data-label="Outcome"><span class="r-out r-out-${r.outcome}">${OUT[r.outcome]}</span></td>`
        + `<td class="small" data-label="What the runs showed">${what(r)}</td><td class="small" data-label="How it was tested"><span class="muted">${esc(r.kind)}:</span> ${esc(r.test)}</td><td class="small" data-label="Holm p">${r.p === null ? '–' : p(r.p)}</td></tr>`).join('')}</tbody></table></div></section>`;
}
