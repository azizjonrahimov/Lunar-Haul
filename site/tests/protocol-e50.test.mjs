// F-65: /protocol/ and /network/ read B-99's figure files (data/atc/protocol/), staged only when every file matches its
// index (bytes and sha256). Figure 1 reads e50_layers.json; its helpers (src/protocol/e50.js) find the driving stretches.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, readdirSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { checkB99 } from '../lib/protocol-data.mjs';
import { e50Runs, e50Middle, e50Over, e50Series } from '../src/protocol/e50.js';

const DIR = new URL('../../data/atc/protocol/', import.meta.url);
const have = existsSync(new URL('index.json', DIR));

test('B-99 files: every one matches the index; a changed byte or a missing file stops the build', { skip: !have && 'B-99 missing' }, () => {
  const { files, index } = checkB99();
  assert.deepEqual(Object.keys(files).sort(), Object.keys(index.files).sort());
  const tmp = mkdtempSync(join(tmpdir(), 'b99-'));
  try {
    for (const f of readdirSync(DIR)) writeFileSync(join(tmp, f), readFileSync(new URL(f, DIR)));
    const name = Object.keys(index.files)[0], p = join(tmp, name), buf = readFileSync(p);
    buf[buf.length - 2] = buf[buf.length - 2] === 0x20 ? 0x0a : 0x20;   // same size, other bytes
    writeFileSync(p, buf);
    assert.throws(() => checkB99(tmp), /sha256/);
    writeFileSync(p, Buffer.concat([buf, Buffer.from(' ')]));
    assert.throws(() => checkB99(tmp), /bytes/);
    rmSync(p);
    assert.throws(() => checkB99(tmp), /missing/);
  } finally { rmSync(tmp, { recursive: true, force: true }); }
});

test('e50_layers for figure 1: one series per step, the month over 30 seeds, the layers help', { skip: !have && 'B-99 missing' }, () => {
  const D = checkB99().files['e50_layers.json'].doc, n = D.t_h.length;
  assert.equal(D.moving.length, n);
  for (const [k, s] of Object.entries(D.sets)) { assert.equal(s.err_m.length, n, k); assert.equal(s.b95_m.length, n, k); assert.ok(D.month_1x_30_seeds[k], k); }
  const M = D.month_1x_30_seeds;
  assert.ok(M['dr+ranging+fixes'].p95_m < M['dr+ranging'].p95_m && M['dr+ranging'].p95_m < M.dr.p95_m);
  assert.ok(D.budget_m > 0);
});

test('E50 helpers: driving runs, the first moment, the share over budget', () => {
  const v = { bins: 8, moving: '01100111', sets: { a: { err_m: [], b95_m: [9, 9, 1, 9, 9, 1, 9, 9] }, b: { same_as: 'a' } } };
  assert.deepEqual(e50Runs(v), [[1, 3], [5, 8]]);
  assert.equal(e50Middle(v), 6);
  assert.equal(e50Over(v, v.sets.a, 5), 60);
  assert.equal(e50Series(v, 'b'), v.sets.a);
});
