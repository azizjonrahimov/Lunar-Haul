// F-61: the browser port of the integrity network (src/network/tcn.js) against the ten check windows of the float64
// reference runtime (data/policies/integrity_net_v1.check.json), tolerance from the file (1e-6).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { forward } from '../src/network/tcn.js';

const P = new URL('../../data/policies/integrity_net_v1.json', import.meta.url), C = new URL('../../data/policies/integrity_net_v1.check.json', import.meta.url);
const have = existsSync(P) && existsSync(C);

test('tcn.js reproduces every check window of integrity_net_v1', { skip: !have && 'policy files missing' }, () => {
  const pol = JSON.parse(readFileSync(P, 'utf8')), chk = JSON.parse(readFileSync(C, 'utf8'));
  assert.equal(chk.obs.length, chk.expected.length);
  assert.ok(chk.obs.length >= 10);
  chk.obs.forEach((win, i) => {
    const { logit, acts } = forward(pol, win);
    assert.ok(Math.abs(logit - chk.expected[i]) <= chk.tolerance, `window ${i} (${chk.what[i]}): ${logit} against ${chk.expected[i]}`);
    assert.equal(acts.length, pol.layers.length + 1);
    assert.equal(acts[acts.length - 1][0].length, 1);   // the stack's receptive field is exactly the window
  });
});
