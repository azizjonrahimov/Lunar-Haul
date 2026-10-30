// Phase 5 checks on /verification/ (F-55): results/vv_phase5.json, written by BACKEND's lunarsim/vv5.py (B-79),
// staged to verify/vv_phase5.json. read(doc) validates the file against BACKEND's names (agreed with LEAD on 30 Oct:
// version 1, {generated, commit, summary, rows}; one row per check and sub-case, keyed by id + sub; grouped by the
// letter of the id as in research_notes/Lunar ATC/verification_plan.md) and returns the groups in page order. A row
// that breaks the schema, or whose "passed" disagrees with its own error and tolerance, becomes an error row, never a
// pass. A skipped row is "not run", never a fail; a bias flag is recorded, not a failure. No DOM, so Node tests can use it.

export const VERSION = 1;
// the plan's id letters, in page order
export const COMPONENTS = [
  ['D', 'Dispatch engine'], ['A', 'Auction and team lifts'], ['R', 'Radio and visibility'], ['S', 'Safety program'],
  ['T', 'Traffic'], ['E', 'Energy and battery'], ['L', 'Learned bidding policy'], ['V', '3D scene and replay'], ['X', 'Cross-cutting'],
];
const KINDS = { V: 'verification', Val: 'validation', Cal: 'reproduces calibration data' };
const MODES = ['rel', 'abs'];

const isNum = v => typeof v === 'number' && Number.isFinite(v);
// 1e-9 -> "1e-9", 0.0123 -> "0.0123", 1234.5 -> "1,234.5"
export function fmtNum(v, unit = '') {
  if (!isNum(v)) return '–';
  const a = Math.abs(v), s = a !== 0 && (a < 1e-3 || a >= 1e7) ? v.toExponential(2).replace(/\.?0+e/, 'e').replace('e+', 'e') : v.toLocaleString('en-GB', { maximumSignificantDigits: 6 });
  return unit ? `${s} ${unit}` : s;
}
export function tolText(c) {
  if (!isNum(c?.tolerance) || !MODES.includes(c.mode)) return '–';
  if (c.tolerance === 0) return 'exact';
  return c.mode === 'rel' ? `≤ ${fmtNum(c.tolerance)} relative` : `≤ ${fmtNum(c.tolerance, c.unit)}`;
}
// the error the tolerance applies to, as vv.Check.finish() computes it
export const errorOf = c => (c.mode === 'abs' ? Math.abs(c.simulated - c.reference) : Math.abs(c.simulated - c.reference) / Math.max(Math.abs(c.reference), 1e-12));

function checkRow(c, seen) {
  if (!c || typeof c !== 'object') return { id: '?', key: '?', group: 'X', name: 'unreadable row', status: 'error', error: 'not an object' };
  const errs = [], skipped = typeof c.skipped === 'string' && c.skipped !== '';
  if (typeof c.id !== 'string' || !/^[A-Z]\d+$/.test(c.id)) errs.push(`id "${c.id}"`);
  if (c.sub != null && typeof c.sub !== 'string') errs.push('sub');
  const key = `${c.id}${c.sub ? ` · ${c.sub}` : ''}`;
  if (seen.has(key)) errs.push('id + sub repeated'); seen.add(key);
  if (typeof c.name !== 'string' || !c.name) errs.push('name');
  if (!(c.kind in KINDS)) errs.push(`kind "${c.kind}"`);
  if (!MODES.includes(c.mode)) errs.push(`mode "${c.mode}"`);
  if (!isNum(c.tolerance) || c.tolerance < 0) errs.push('tolerance');
  if (typeof c.skipped !== 'string') errs.push('skipped');
  if (typeof c.passed !== 'boolean') errs.push('passed');
  if (!skipped) {
    if (!isNum(c.reference)) errs.push('reference');
    if (!isNum(c.simulated)) errs.push('simulated');
    if (!errs.length && (errorOf(c) <= c.tolerance) !== c.passed) errs.push(`"passed" is ${c.passed} but the error ${fmtNum(errorOf(c))} is ${errorOf(c) <= c.tolerance ? 'within' : 'outside'} the tolerance`);
  }
  if (c.ci99 != null && !(Array.isArray(c.ci99) && c.ci99.length === 2 && c.ci99.every(isNum))) errs.push('ci99');
  // the 95 % upper bound exists only for zero events; with events it is null (B-79 batch 3, S1 type 9)
  if (c.exposure != null && !(isNum(c.exposure.n) && (isNum(c.exposure.upper95) || (c.exposure.upper95 === null && c.simulated > 0)))) errs.push('exposure');
  const ci = Array.isArray(c.ci99) && c.ci99.every(isNum) ? c.ci99 : null, ex = c.exposure && isNum(c.exposure.n) ? c.exposure : null;
  const row = {
    id: String(c.id ?? '?'), sub: typeof c.sub === 'string' ? c.sub : '', key, group: /^[A-Z]/.test(c.id ?? '') ? c.id[0] : 'X',
    name: String(c.name ?? ''), kind: c.kind, kindText: KINDS[c.kind] || '', calibration: c.kind === 'Cal',
    meta: [c.kind === 'Cal' ? '' : KINDS[c.kind], c.technique, c.factor, c.priority].filter(x => typeof x === 'string' && x).join(' · '),
    formula: typeof c.basis === 'string' ? c.basis : '', reference: fmtNum(c.reference, c.unit),
    measured: skipped ? '–' : fmtNum(c.simulated, c.unit) + (isNum(c.error) ? `; error ${fmtNum(c.error)}${c.mode === 'rel' ? ' relative' : ''}` : ''),
    ci: ci ? `99 % batch-means interval ${fmtNum(ci[0])} to ${fmtNum(ci[1])}` : '', bias: c.bias_flag === true,
    tolerance: tolText(c) + (ex ? `; ${c.simulated === 0 ? 'zero' : fmtNum(c.simulated)} events in ${fmtNum(ex.n, ex.unit || '')}${isNum(ex.upper95) ? `, 95 % upper bound ${fmtNum(ex.upper95)}` : ''}` : ''),
    // where the tolerance was fixed before the run (optional)
    tolFrom: typeof c.tolerance_source === 'string' ? c.tolerance_source.replace('research_notes/Lunar ATC/verification_plan.md', 'verification plan') : '',
    status: errs.length ? 'error' : skipped ? 'not_run' : c.passed ? 'pass' : 'fail', reason: skipped ? c.skipped : '',
    source: typeof c.source === 'string' ? c.source : '', papers: Array.isArray(c.papers) ? c.papers.join(', ') : '',
    run: isNum(c.runtime_s) ? `${fmtNum(c.runtime_s)} s` : '',
  };
  if (errs.length) row.error = `does not match the agreed format: ${errs.join(', ')}`;
  return row;
}

/* read(doc) -> {ok, error?, generated, commit, groups: [{id, label, rows, pass, fail, notRun, errors, bias}], totals, mismatch} */
export function read(doc) {
  if (!doc || typeof doc !== 'object' || !Array.isArray(doc.rows)) return { ok: false, error: 'not a phase-5 check file (no "rows")', groups: [] };
  if (doc.version !== VERSION) return { ok: false, error: `version ${doc.version}: this page reads version ${VERSION}`, groups: [] };
  const seen = new Set(), rows = doc.rows.map(c => checkRow(c, seen)), names = new Map(COMPONENTS);
  for (const r of rows) if (!names.has(r.group)) names.set(r.group, `Other (${r.group})`);
  const count = (rs, s) => rs.filter(r => r.status === s).length, tally = rs => ({ pass: count(rs, 'pass'), fail: count(rs, 'fail'), notRun: count(rs, 'not_run'), errors: count(rs, 'error'), bias: rs.filter(r => r.bias).length });
  const groups = [...names].map(([id, label]) => { const rs = rows.filter(r => r.group === id); return { id, label, rows: rs, ...tally(rs) }; }).filter(g => g.rows.length);
  const totals = { rows: rows.length, ...tally(rows) };
  // the file's own summary must agree with its rows (a format error counts as neither passed nor failed)
  const S = doc.summary || {}, want = { rows: totals.rows, passed: totals.pass, failed: totals.fail, skipped: totals.notRun, bias_flags: totals.bias };
  const off = Object.entries(want).filter(([k, v]) => S[k] !== v).map(([k, v]) => `${k} ${S[k] ?? 'missing'} (rows give ${v})`);
  return { ok: true, generated: typeof doc.generated === 'string' ? doc.generated : '', commit: typeof doc.commit === 'string' ? doc.commit : '', groups, totals,
    mismatch: totals.errors ? '' : off.join(', ') };
}
