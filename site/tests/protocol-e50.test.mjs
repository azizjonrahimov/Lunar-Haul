// F-56: /protocol/ figure 1 reads E50's one-month trace. The build's reduction (lib/protocol-data.mjs) keeps every
// bin of every layer set, marks a set identical to an earlier one, and the figure's helpers (src/protocol/e50.js)
// find the driving stretches and the share of them over the budget.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { compactE50, E50_SETS } from '../lib/protocol-data.mjs';
import { e50Runs, e50Middle, e50Over, e50Series } from '../src/protocol/e50.js';

const SRC = new URL('../../results/E50_trace.json', import.meta.url);

test('E50 trace: reduced for the figure without losing a bin', { skip: !existsSync(SRC) && 'results/E50_trace.json missing' }, () => {
  const raw = JSON.parse(readFileSync(SRC, 'utf8')), out = compactE50(raw);
  assert.equal(out.format, 'lunarsim-e50-trace-site');
  assert.equal(out.budget_m, raw.budget_m);
  assert.deepEqual(Object.keys(out.vehicles).sort(), Object.keys(raw.vehicles).sort());
  for (const [id, v] of Object.entries(out.vehicles)) {
    const r = raw.vehicles[id];
    assert.equal(v.moving.length, r.xy_m.length);
    for (const k of E50_SETS) {
      const s = e50Series(v, k);
      assert.deepEqual(s.err_m, r.sets[k].err_m, `${id} ${k}: err_m`);
      assert.deepEqual(s.b95_m, r.sets[k].b95_m, `${id} ${k}: b95_m`);
    }
    // the layers help: with every layer the error while driving is far below dead reckoning's
    const med = a => a.slice().sort((x, y) => x - y)[a.length >> 1];
    const drv = k => e50Series(v, k).err_m.filter((_, i) => v.moving[i] === '1');
    assert.ok(med(drv('dr+ranging+fixes')) < med(drv('dr')) / 10, `${id}: layers do not cut the error`);
  }
});

test('E50 helpers: driving runs, the first moment, the share over budget', () => {
  const v = { bins: 8, moving: '01100111', sets: { a: { err_m: [], b95_m: [9, 9, 1, 9, 9, 1, 9, 9] }, b: { same_as: 'a' } } };
  assert.deepEqual(e50Runs(v), [[1, 3], [5, 8]]);
  assert.equal(e50Middle(v), 6);
  assert.equal(e50Over(v, v.sets.a, 5), 60);   // moving bins 1, 2, 5, 6, 7: bounds 9, 1, 1, 9, 9
  assert.equal(e50Series(v, 'b'), v.sets.a);
});

test('E50 reduction refuses a different format or a short series', () => {
  assert.throws(() => compactE50({ format: 'x', version: 1, vehicles: {} }), /format/);
  const sets = Object.fromEntries(E50_SETS.map(k => [k, { err_m: [1, 2], b95_m: [1, 2] }]));
  sets.dr = { err_m: [1], b95_m: [1, 2] };
  assert.throws(() => compactE50({ format: 'lunarsim-e50-trace', version: 1, vehicles: { 1: { drive_h: 1, xy_m: [[0, 0], [1, 1]], sets } } }), /bins/);
});
