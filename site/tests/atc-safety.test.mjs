// F-54: the JS safety program (src/atc/safety.js) against Python's, on B-78's 20 stored encounters, every step and
// every vehicle, with the tolerances of data/atc/encounter_fixtures/index.json; and the replay of B-83's sandbox set.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, access } from 'node:fs/promises';
import { bGuaranteed, rssDmin, vMaxR2, safetyMove } from '../src/atc/safety.js';
import { readFixture, parity, replayTrace } from '../src/atc/encounter.js';

const DIR = new URL('../../data/atc/encounter_fixtures/', import.meta.url);
const have = await access(new URL('index.json', DIR)).then(() => true, () => false);

test('safety program constants and formulas', () => {
  assert.equal(bGuaranteed(0), 0.5);                                         // service braking on the flat
  assert.ok(bGuaranteed(20) < 0);                                            // 20 deg downhill: cannot stop
  assert.equal(vMaxR2(20, 0.45, 1e4, 2.8), 0);                               // so R2 allows no speed
  // RSS gap at 10 km/h behind a stopped leader: v rho + a rho^2/2 + (v + a rho)^2 / 2b + D0
  const v = 10 / 3.6, vr = v + 0.2;
  assert.ok(Math.abs(rssDmin(v, 0, 0.5) - (v + 0.1 + vr * vr / 1.0 + 5)) < 1e-12);
  // a free road: the proposal passes unchanged; a stop line just ahead: braking is substituted
  const free = { v: 2, a_prop: 0.1, dt: 0.1, theta: 0, mu: 0.45, v_class: 2.8, sight: 1e4, gap_lead: Infinity, v_lead: 0, d_stop: Infinity, d_crew: Infinity };
  assert.deepEqual(safetyMove(free), { a: 0.1, modified: false, noSafe: false, rule: 0 });
  const line = safetyMove({ ...free, d_stop: 4 });
  assert.equal(line.rule, 3); assert.ok(line.a < 0 && line.modified);
});

test('parity with Python on the 20 stored encounters', { skip: !have && 'fixtures not in the tree' }, async () => {
  const idx = JSON.parse(await readFile(new URL('index.json', DIR)));
  assert.equal(idx.fixtures.length, 20);
  for (const f of idx.fixtures) {
    const doc = await readFixture(await readFile(new URL(f.file, DIR)));
    const p = parity(doc, idx.tolerance);
    assert.equal(p.checks, f.steps * doc.spec.paths.length, f.file);
    assert.ok(p.pass, `${f.file}: ${JSON.stringify(p.firstFail)}`);
  }
});

const SB = new URL('../../data/atc/encounter_sandbox/', import.meta.url);
const haveSB = await access(new URL('index.json', SB)).then(() => true, () => false);
test("replay of the sandbox set agrees with the simulator's record of each run", { skip: !haveSB && 'sandbox set not in the tree' }, async () => {
  const idx = JSON.parse(await readFile(new URL('index.json', SB)));
  assert.equal(new Set(idx.encounters.map(e => e.type)).size, 12);
  for (const e of idx.encounters) {
    const doc = await readFixture(await readFile(new URL(e.file, SB)));
    for (const which of ['shield_on', 'shield_off']) {
      const r = replayTrace(doc, which), rec = doc[which].outcome.min_sep_m, low = r.frames.at(-1).minSep;
      assert.equal(r.frames.length, doc[which].steps.length + 1);
      if (rec === null) { assert.ok(!Number.isFinite(low) || low > 0, `${e.file} ${which}`); continue; }
      assert.equal(low < 0, rec < 0, `${e.file} ${which}: contact in the frames vs the record`);
      assert.ok(low >= rec - 0.05, `${e.file} ${which}: a stored frame closer (${low}) than the recorded minimum (${rec})`);   // xy stored to 2 decimals
    }
    assert.ok(replayTrace(doc, 'shield_on').contactAt === null, `${e.file}: contact with the safety program on`);
  }
});
