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

// the outcome of one hypothesis: 'held', 'partly' (some clauses held, some did not) or 'not', from the file's own fields
export function outcomeOf(h) {
  const rej = h.holm?.['rejected_at_0.05'];
  if (typeof rej === 'boolean') return rej ? 'held' : 'not';
  const cl = Object.values(h.clauses || {}).filter(c => typeof c.supported === 'boolean');
  if (cl.length) { const k = cl.filter(c => c.supported).length; return k === cl.length ? 'held' : k ? 'partly' : 'not'; }
  if (typeof h.decision === 'string') return /^supported/i.test(h.decision) ? 'held' : /not supported/i.test(h.decision) ? 'not' : 'partly';
  throw new Error(`${FAMILY_SRC}: no outcome for a hypothesis`);
}
const OUT = { held: 'held', partly: 'held in part', not: 'did not hold' };

export function familyRows(F) {
  return Object.entries(F.hypotheses).map(([id, h]) => ({
    id, outcome: outcomeOf(h), kind: /^threshold comparison/i.test(h.test || '') ? 'threshold comparison' : 'sampling test, Holm',
    test: (h.test || '').replace(/^threshold comparison \(no sampling test\):\s*/i, ''), summary: F.summary?.[id] || h.decision || '',
    p: h.holm && typeof h.holm.p_adjusted === 'number' ? h.holm.p_adjusted : null,
  }));
}

export function familyTable() {
  const F = read(FAMILY_SRC);
  if (!F) return '';
  const rows = familyRows(F), n = k => rows.filter(r => r.outcome === k).length;
  const p = v => (v < 0.001 ? '< 0.001' : fmt(v, 3));
  return `<section class="r-fam" aria-labelledby="r-fam-h"><h3 id="r-fam-h">Phase 6: which hypotheses held</h3>
    <p class="prose small">The confirmatory family registered before the runs (${esc(F.family)}). Of ${rows.length} hypotheses,
      ${n('held')} held, ${n('partly')} held in part and ${n('not')} did not.</p>
    <div class="r-scroll"><table class="r-table r-fam-table"><caption>Hypotheses of Phase 6, from ${FAMILY_SRC}${F.pending ? `. Still to come: ${esc(F.pending)}` : ''}.</caption>
      <thead><tr><th scope="col">Hypothesis</th><th scope="col">Outcome</th><th scope="col">What the runs showed</th><th scope="col">How it was tested</th><th scope="col">Holm p</th></tr></thead>
      <tbody>${rows.map(r => `<tr><th scope="row">${esc(r.id)}</th><td data-label="Outcome"><span class="r-out r-out-${r.outcome}">${OUT[r.outcome]}</span></td>`
        + `<td class="small" data-label="What the runs showed">${esc(r.summary)}</td><td class="small" data-label="How it was tested"><span class="muted">${esc(r.kind)}:</span> ${esc(r.test)}</td><td class="small" data-label="Holm p">${r.p === null ? '–' : p(r.p)}</td></tr>`).join('')}</tbody></table></div></section>`;
}
