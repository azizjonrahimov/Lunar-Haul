// F-54 item 3: the browser runtime of the ATC bid policies (src/atc/bid-policy.js) against Python's float64 runtime
// (lunarsim/atc/learned.py Policy) on each file's check vectors, and the weights P1 Section 5.6 describes.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { AtcBidPolicy, checkBid } from '../src/atc/bid-policy.js';

const P = f => new URL(`../../data/policies/${f}`, import.meta.url);
const load = async f => JSON.parse(await readFile(P(f)));

for (const id of ['atc_bid_linear_v1', 'atc_bid_v1']) {
  test(`${id}: matches Python on its check vectors`, async () => {
    const pol = new AtcBidPolicy(await load(`${id}.json`)), c = checkBid(pol, await load(`${id}.check.json`));
    assert.equal(c.n, 50);
    assert.ok(c.ok, `max error ${c.maxErr} > ${c.tolerance}`);
  });
}

test('linear weights: the three largest each way, with the signs and sizes P1 reports', async () => {
  const doc = await load('atc_bid_linear_v1.json'), w = doc.layers[0].w[0], names = doc.obs.names;
  const ranked = names.map((n, i) => [n, w[i]]).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const top = sign => ranked.filter(([, x]) => Math.sign(x) === sign).slice(0, 3).map(([n, x]) => `${n} ${x.toFixed(2)}`);
  // P1-LIN-WEIGHTS-SENTENCE: lower the bid for job +1.93, load +1.28, heard +1.04; raise it for slack -1.96,
  // approach -1.41, battery -1.39 (three per direction: age_d, -1.10, is larger than heard overall)
  assert.deepEqual(top(1), ['job_h 1.93', 'mass_frac 1.28', 'heard 1.04']);
  assert.deepEqual(top(-1), ['slack_d -1.96', 'approach_h -1.41', 'battery -1.39']);
  assert.equal(doc.layers[0].b[0], 0);
});
