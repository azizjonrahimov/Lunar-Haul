// F-61: build-time side of /network/ (E56, task B-96). Numbers for the page text come from results/table_E56.csv and
// results/E56_integrity.json through <!--@nw:key--> (vite.config.js), each flagged Modelled with its source; nothing is
// typed. stage(PUB) copies what the page fetches into public/network/ (prepare-data.mjs).
import { readFileSync, existsSync, mkdirSync, copyFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { checkB99 } from './protocol-data.mjs';
import { num } from '../src/components/num.js';
import { csv, ROOT } from './pages.mjs';

const CSV = join(ROOT, 'results', 'table_E56.csv'), JSONF = join(ROOT, 'results', 'E56_integrity.json');
const LAND = join(ROOT, 'data', 'atc', 'integrity', 'landscape.json');
// F-65: the landscape comes from B-99's copy (data/atc/protocol/b96_landscape.json, checked against its index), which
// must carry the current landscape.json (its source_sha256), so the page and the figure read the same bytes
export const LAND_B99 = 'data/atc/protocol/b96_landscape.json';
function landscapeB99() {
  if (!existsSync(join(ROOT, LAND_B99))) return null;
  const doc = checkB99().files['b96_landscape.json']?.doc;
  if (!doc?.landscape) throw new Error(`${LAND_B99}: no landscape`);
  if (existsSync(LAND)) {
    const sha = createHash('sha256').update(readFileSync(LAND)).digest('hex');
    if (sha !== doc.source_sha256) throw new Error(`${LAND_B99} was made from another landscape.json (source_sha256 ${String(doc.source_sha256).slice(0, 12)}…, the file is ${sha.slice(0, 12)}…): rerun tools/atc/export_protocol.py`);
  }
  return doc.landscape;
}
const POL = join(ROOT, 'data', 'policies', 'integrity_net_v1.json'), CHK = join(ROOT, 'data', 'policies', 'integrity_net_v1.check.json');
export const DETECTORS = [['net', 'Network'], ['chi2_step', 'Chi-square per step'], ['chi2_window', 'Chi-square windowed'], ['cusum', 'CUSUM'], ['logreg', 'Logistic regression']];
export const FAULTS = ['jump', 'drift', 'frozen', 'frame', 'noise', 'all'];

let cache = null;
function load() {
  if (cache) return cache;
  if (!existsSync(CSV) || !existsSync(JSONF)) return (cache = { ok: false });
  const rows = csv(readFileSync(CSV, 'utf8'));
  const E = JSON.parse(readFileSync(JSONF, 'utf8').replace(/\bNaN\b/g, 'null'));
  const L = landscapeB99();
  const r = (set, det, fault, rate = '1/pair-day', cls = 'all') => rows.find(x => x.set === set && x.detector === det && x.fault === fault && x.rate === rate && x.range_class === cls);
  return (cache = { ok: true, rows, E, L, r });
}
const src = (set, det, fault, field) => `results/table_E56.csv: set ${set}, range class all, ${det}, 1 false alarm per pair-day, fault ${fault}, ${field}`;
const M = (value, unit, digits, source) => num({ value, unit, digits, flag: 'Modelled', source });
// F-78 (review W1): a missing row, field or key stops the build and names the file and the key, never a dash
const need = (x, file, key) => { if (typeof x !== 'number' || !Number.isFinite(x)) throw new Error(`network: ${file} has no number at ${key}`); return x; };
const dig = (o, path) => path.split('.').reduce((a, k) => (a == null ? undefined : a[k]), o);

// the page's numbers, by key
export function nw(key) {
  const D = load();
  if (!D.ok) return '<span class="stub">(E56 results not available)</span>';
  const { r, E, L } = D;
  const v = (set, det, fault, field) => {
    const row = r(set, det, fault), at = `set ${set}, detector ${det}, fault ${fault}, rate 1/pair-day, range class all, ${field}`;
    if (!row) throw new Error(`network: results/table_E56.csv has no row for ${at}`);
    if (row[field] === undefined || row[field] === '') throw new Error(`network: results/table_E56.csv has no value for ${at}`);
    return need(+row[field], 'results/table_E56.csv', at);
  };
  const e = path => need(dig(E, path), 'results/E56_integrity.json', path);
  const l = path => { if (!L) throw new Error(`network: ${LAND_B99} is missing (key ${path})`); return need(dig(L, path), LAND_B99, `landscape.${path}`); };
  const rec = (set, det, fault) => M(v(set, det, fault, 'recall'), '', 2, src(set, det, fault, 'recall'));
  const base = ['chi2_step', 'chi2_window', 'cusum', 'logreg'].map(d => v('test', d, 'all', 'recall'));
  const driftBest = Math.max(...DETECTORS.map(([d]) => v('test', d, 'drift', 'recall')));
  const faTest = v('test', 'net', 'all', 'fa_per_pair_day'), faOod = v('ood', 'net', 'all', 'fa_per_pair_day');
  const K = {
    net_all: () => rec('test', 'net', 'all'),
    base_min_all: () => M(Math.min(...base), '', 2, 'results/table_E56.csv: test, the four baselines, fault all, recall (lowest)'),
    base_max_all: () => M(Math.max(...base), '', 2, 'results/table_E56.csv: test, the four baselines, fault all, recall (highest)'),
    net_noise: () => rec('test', 'net', 'noise'), chi2_noise: () => rec('test', 'chi2_step', 'noise'), cusum_noise: () => rec('test', 'cusum', 'noise'),
    net_jump: () => rec('test', 'net', 'jump'), chi2_jump: () => rec('test', 'chi2_step', 'jump'), logreg_jump: () => rec('test', 'logreg', 'jump'),
    net_drift: () => rec('test', 'net', 'drift'),
    drift_best: () => M(driftBest * 100, ' %', 0, 'results/table_E56.csv: test, the best detector on drift, recall'),
    drift_missed: () => M((1 - driftBest) * 100, ' %', 0, 'results/table_E56.csv: 1 minus the best detector\'s recall on drift (test)'),
    net_fa_test: () => M(faTest, ' per pair-day', 2, src('test', 'net', 'all', 'fa_per_pair_day')),
    net_fa_ood: () => M(faOod, ' per pair-day', 1, src('ood', 'net', 'all', 'fa_per_pair_day')),
    fa_ratio: () => M(faOod / faTest, ' times', 0, 'results/table_E56.csv: network false alarms per pair-day, out of distribution / test'),
    ood_net_jump: () => rec('ood', 'net', 'jump'), ood_net_drift: () => rec('ood', 'net', 'drift'),
    ood_cusum_jump: () => rec('ood', 'cusum', 'jump'), ood_cusum_drift: () => rec('ood', 'cusum', 'drift'),
    ood_cusum_fa: () => M(v('ood', 'cusum', 'all', 'fa_per_pair_day'), ' per pair-day', 0, src('ood', 'cusum', 'all', 'fa_per_pair_day')),
    drift_diff: () => M(e('test.h15_net_against.chi2_step.drift.delay_median_diff_s.value'), ' s', 1, 'results/E56_integrity.json: test.h15_net_against.chi2_step.drift.delay_median_diff_s'),
    // the parameter count is labelled with the file it was read from (the results file first, else B-99's landscape)
    params: () => typeof dig(E, 'model.n_params') === 'number'
      ? M(e('model.n_params'), '', 0, 'results/E56_integrity.json: model.n_params')
      : M(l('model.n_params'), '', 0, `${LAND_B99}: landscape.model.n_params`),
    numpy_ms: () => M(e('timing.numpy_reference_ms.median'), ' ms', 2, 'results/E56_integrity.json: timing.numpy_reference_ms.median (laptop CPU, one window)'),
    ev1: () => M(l('pca.explained_variance.0') * 100, ' %', 1, `${LAND_B99}: landscape.pca.explained_variance[0]`),
    ev2: () => M(l('pca.explained_variance.1') * 100, ' %', 1, `${LAND_B99}: landscape.pca.explained_variance[1]`),
    gap_med: () => M(l('pca.self_check.projection_gap_abs.median'), '', 3, `${LAND_B99}: landscape.pca.self_check.projection_gap_abs.median`),
    gap_max: () => M(l('pca.self_check.projection_gap_abs.max'), '', 3, `${LAND_B99}: landscape.pca.self_check.projection_gap_abs.max`),
    lr: () => M(l('optimiser.lr'), '', 3, `${LAND_B99}: landscape.optimiser.lr`),
    epochs: () => M(l('optimiser.epochs'), '', 0, `${LAND_B99}: landscape.optimiser.epochs`),
  };
  if (!K[key]) throw new Error(`network: no number ${key}`);
  return K[key]();
}

// the compact results file the charts read: test and out-of-distribution, 1 false alarm per pair-day, all ranging classes
function e56Compact() {
  const { rows, E } = load(), pick = ['recall', 'recall_ci_lo', 'recall_ci_hi', 'delay_median_s', 'fa_per_pair_day', 'precision_at_1_fault_per_pair_day'];
  const out = { source: 'results/table_E56.csv (range class all, 1 false alarm per pair-day) and results/E56_integrity.json', detectors: DETECTORS, faults: FAULTS, sets: {} };
  for (const set of ['test', 'ood']) {
    out.sets[set] = {};
    for (const [d] of DETECTORS) { out.sets[set][d] = {}; for (const f of FAULTS) { const row = rows.find(x => x.set === set && x.detector === d && x.fault === f && x.rate === '1/pair-day' && x.range_class === 'all'); if (row) out.sets[set][d][f] = Object.fromEntries(pick.map(k => [k, row[k] === '' ? null : +row[k]])); } }
  }
  out.thresholds = JSON.parse(readFileSync(POL, 'utf8')).thresholds;
  return out;
}

export function stage(PUB) {
  if (!load().ok) { console.log('prepare-data: E56 results missing, /network/ shows placeholders'); return; }
  const dir = join(PUB, 'network'); mkdirSync(dir, { recursive: true });
  copyFileSync(POL, join(dir, 'integrity_net_v1.json')); copyFileSync(CHK, join(dir, 'integrity_net_v1.check.json'));
  writeFileSync(join(dir, 'e56.json'), JSON.stringify(e56Compact()));
  console.log('prepare-data: /network/ staged (policy and check, E56 summary; the landscape is B-99’s, in protocol/b99/)');
}
