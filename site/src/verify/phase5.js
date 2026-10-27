// Phase 5 checks on /verification/ (F-55): results/vv_phase5.json, written by BACKEND's run_phase5_checks() (B-79),
// staged to verify/vv_phase5.json. read(doc) validates the file against the schema proposed to BACKEND on 27 Oct
// (format lunarsim-vv-phase5 v1; confirmed by BACKEND with an optional "run" {seeds, wall_s}; sub-cases are rows, D3a, D3b)
// and returns the components in page order with their rows; a row that breaks the
// schema becomes an error row, never a pass. No DOM, so Node tests can use it.

export const FORMAT = 'lunarsim-vv-phase5', VERSION = 1;
// the page order and plain names (the file's own components list may rename them or add more)
export const COMPONENTS = [
  ['engine', 'Dispatch engine'], ['auction', 'Auction and team lifts'], ['radio', 'Radio and visibility'], ['safety', 'Safety program'],
  ['traffic', 'Traffic'], ['energy', 'Energy and battery'], ['learned', 'Learned bidding policy'], ['replay', '3D scene and replay'], ['cross', 'Cross-cutting'],
];
const KINDS = { V: 'verification', Val: 'validation', Cal: 'reproduces calibration data' };
const TOL = ['rel', 'abs', 'exact', 'zero_events', 'pvalue'], STATUS = ['pass', 'fail', 'not_run'];

const isNum = v => typeof v === 'number' && Number.isFinite(v);
// 1e-9 -> "1e-9", 0.0123 -> "0.0123", 1234.5 -> "1,234.5"
export function fmtNum(v, unit = '') {
  if (!isNum(v)) return '–';
  const a = Math.abs(v), s = a !== 0 && (a < 1e-3 || a >= 1e7) ? v.toExponential(2).replace(/\.?0+e/, 'e').replace('e+', 'e') : v.toLocaleString('en-GB', { maximumSignificantDigits: 6 });
  return unit ? `${s} ${unit}` : s;
}
export function tolText(t) {
  if (!t) return '–';
  return { rel: () => `≤ ${fmtNum(t.value)} relative`, abs: () => `≤ ${fmtNum(t.value)}`, exact: () => 'exact', zero_events: () => 'zero events', pvalue: () => `p ≥ ${fmtNum(t.value)}` }[t.type]?.() ?? '–';
}

// one row -> {ok, row} or {ok: false, row with error}
function checkRow(c, components) {
  const errs = [];
  if (!c || typeof c !== 'object') return { id: '?', component: 'cross', name: 'unreadable row', status: 'error', error: 'not an object' };
  if (typeof c.id !== 'string' || !c.id) errs.push('id');
  if (!components.has(c.component)) errs.push(`component "${c.component}"`);
  if (typeof c.name !== 'string') errs.push('name');
  if (!(c.kind in KINDS)) errs.push(`kind "${c.kind}"`);
  if (!STATUS.includes(c.status)) errs.push(`status "${c.status}"`);
  if (!c.tolerance || !TOL.includes(c.tolerance.type)) errs.push('tolerance.type');
  if (c.tolerance && ['rel', 'abs', 'pvalue'].includes(c.tolerance.type) && !isNum(c.tolerance.value)) errs.push('tolerance.value');
  if (c.tolerance?.type === 'zero_events' && !(c.zero_events && isNum(c.zero_events.exposure) && isNum(c.zero_events.upper95))) errs.push('zero_events');
  if (c.status !== 'not_run' && c.measured?.value === undefined) errs.push('measured');
  if (typeof c.source !== 'string' || !c.source) errs.push('source');
  const row = {
    id: String(c.id ?? '?'), component: components.has(c.component) ? c.component : 'cross', name: String(c.name ?? ''), kind: c.kind, kindText: KINDS[c.kind] || '',
    calibration: c.kind === 'Cal', technique: c.technique || '', credibility: c.credibility || '', formula: c.formula || '',
    reference: c.reference?.text || fmtNum(c.reference?.value, c.reference?.unit),
    measured: c.status === 'not_run' ? 'not run yet' : fmtNum(c.measured?.value, c.measured?.unit) + (Array.isArray(c.measured?.ci95) ? ` (95 % CI ${fmtNum(c.measured.ci95[0])} to ${fmtNum(c.measured.ci95[1])})` : '') + (isNum(c.measured?.n) ? `, n = ${c.measured.n}` : ''),
    tolerance: tolText(c.tolerance) + (c.zero_events ? `; exposure ${fmtNum(c.zero_events.exposure, c.zero_events.unit)}, 95 % upper bound ${fmtNum(c.zero_events.upper95)}` : ''),
    status: errs.length ? 'error' : c.status, source: c.source || '', paper: c.paper || null, test: c.test || '', batch: c.batch ?? null,
    // optional (BACKEND, 27 Oct): what the check cost to run
    run: c.run ? [Array.isArray(c.run.seeds) ? `${c.run.seeds.length} seed${c.run.seeds.length === 1 ? '' : 's'}` : '', isNum(c.run.wall_s) ? `${fmtNum(c.run.wall_s)} s` : ''].filter(Boolean).join(', ') : '',
  };
  if (errs.length) row.error = `does not match the agreed format: ${errs.join(', ')}`;
  return row;
}

/* read(doc) -> {ok, error?, generated, commit, groups: [{id, label, rows, pass, fail, notRun, errors}], totals} */
export function read(doc) {
  if (!doc || doc.format !== FORMAT) return { ok: false, error: `not a ${FORMAT} file`, groups: [] };
  if (doc.version !== VERSION) return { ok: false, error: `version ${doc.version}: this page reads version ${VERSION}`, groups: [] };
  const names = new Map(COMPONENTS);
  for (const c of doc.components || []) if (c && typeof c.id === 'string') names.set(c.id, c.label || names.get(c.id) || c.id);
  const rows = (Array.isArray(doc.checks) ? doc.checks : []).map(c => checkRow(c, names));
  const order = [...COMPONENTS.map(([id]) => id), ...[...names.keys()].filter(id => !COMPONENTS.some(([k]) => k === id))];
  const count = (rs, s) => rs.filter(r => r.status === s).length;
  const groups = order.map(id => { const rs = rows.filter(r => r.component === id); return { id, label: names.get(id), rows: rs, pass: count(rs, 'pass'), fail: count(rs, 'fail'), notRun: count(rs, 'not_run'), errors: count(rs, 'error') }; })
    .filter(g => g.rows.length);
  const totals = { rows: rows.length, pass: count(rows, 'pass'), fail: count(rows, 'fail'), notRun: count(rows, 'not_run'), errors: count(rows, 'error') };
  return { ok: true, generated: doc.generated || '', commit: doc.commit || '', groups, totals };
}
