// F-56: helpers for /protocol/ figure 1 (E50's one-month trace, protocol/e50-trace.json from lib/protocol-data.mjs);
// pure, so tests/protocol-e50.test.mjs can check them in node
// the runs of half hours in which a vehicle moved, and the middle of the longest (the figure's first moment)
export const e50Runs = v => { const out = []; let a = -1; for (let i = 0; i <= v.bins; i++) { const m = v.moving[i] === '1'; if (m && a < 0) a = i; if (!m && a >= 0) { out.push([a, i]); a = -1; } } return out; };
export const e50Middle = v => { const [a, b] = e50Runs(v).reduce((best, x) => (x[1] - x[0] > best[1] - best[0] ? x : best), [0, 0]); return Math.floor((a + b) / 2); };
// the share (0-100) of the half hours a vehicle moved in which a layer set's bound is over the budget
export const e50Over = (v, s, budget) => { let n = 0, o = 0; for (let k = 0; k < v.bins; k++) if (v.moving[k] === '1') { n++; if (s.b95_m[k] > budget) o++; } return n ? 100 * o / n : 0; };
export const e50Series = (v, k) => { const s = v.sets[k]; return s.same_as ? v.sets[s.same_as] : s; };

