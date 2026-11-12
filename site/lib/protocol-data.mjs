// /protocol/ data staged at build time (prepare-data). E50 (B-90) trace for figure 1: results/E50_trace.json
// (lunarsim-e50-trace v1: one month at 1x, seed 1, the two vehicles that drove most; per layer set err_m and b95_m,
// the maximum over each 30 min bin) reduced to what the figure draws: per vehicle the hours driven, a 0/1 string of
// the bins in which it moved (its position changed before the next bin) and, per layer set, err_m and b95_m.
// Layer sets whose two series equal another set's are marked same_as (in 2028 the satellite layer adds nothing).
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { ROOT } from './pages.mjs';

export const E50_SRC = 'results/E50_trace.json';
export const E50_OUT = 'protocol/e50-trace.json';
export const E50_SETS = ['dr', 'dr+ranging', 'dr+ranging+fixes', 'dr+ranging+fixes+lans', 'lans@2030'];

export function compactE50(doc) {
  if (doc.format !== 'lunarsim-e50-trace' || doc.version !== 1) throw new Error(`${E50_SRC}: format ${doc.format} version ${doc.version}`);
  const vehicles = {};
  for (const [id, v] of Object.entries(doc.vehicles)) {
    const n = v.xy_m.length, sets = {};
    for (const k of E50_SETS) {
      const s = v.sets[k];
      if (!s) throw new Error(`${E50_SRC}: vehicle ${id} has no layer set ${k}`);
      if (s.err_m.length !== n || s.b95_m.length !== n) throw new Error(`${E50_SRC}: vehicle ${id} ${k}: ${s.err_m.length} / ${s.b95_m.length} bins, positions ${n}`);
      sets[k] = { err_m: s.err_m, b95_m: s.b95_m };
    }
    for (let i = 1; i < E50_SETS.length; i++) {
      const a = sets[E50_SETS[i]], same = E50_SETS.slice(0, i).find(k => !sets[k].same_as && JSON.stringify([sets[k].err_m, sets[k].b95_m]) === JSON.stringify([a.err_m, a.b95_m]));
      if (same) sets[E50_SETS[i]] = { same_as: same };
    }
    const moving = v.xy_m.map((p, i) => (i + 1 < n && (p[0] !== v.xy_m[i + 1][0] || p[1] !== v.xy_m[i + 1][1]) ? '1' : '0')).join('');
    vehicles[id] = { drive_h: v.drive_h, bins: n, moving, sets };
  }
  return { format: 'lunarsim-e50-trace-site', version: 1, source: E50_SRC, experiment: doc.experiment, mult: doc.mult, seed: doc.seed,
    t0_h: doc.t0_h, bin_min: doc.bin_min, budget_m: doc.budget_m, sets: E50_SETS, vehicles };
}

export function stageE50(PUB) {
  const src = join(ROOT, E50_SRC);
  if (!existsSync(src)) { console.log(`prepare-data: ${E50_SRC} missing; /protocol/ figure 1 says so`); return null; }
  const out = compactE50(JSON.parse(readFileSync(src, 'utf8')));
  mkdirSync(join(PUB, 'protocol'), { recursive: true });
  const text = JSON.stringify(out);
  writeFileSync(join(PUB, E50_OUT), text);
  console.log(`prepare-data: ${E50_OUT} staged (${Math.round(text.length / 1024)} kB, ${Object.keys(out.vehicles).length} vehicles)`);
  return out;
}
