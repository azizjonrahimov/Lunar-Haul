// F-34: the recorded descents (trajectories-v1, B-33) against the browser's physics port (run: node --test site/tests/).
// The browser env cannot redraw numpy's random starts and sensor noise from a seed, so each 0.2 s guidance step is
// replayed through site/src/lander/physics.js from the recorded state, throttle and thrust direction, and the
// predicted position is compared with pos_m. The file rounds velocities to 1e-4 m/s, which alone allows
// 0.2 s x 5e-5 m/s = 1e-5 m per step; with position, direction and throttle rounding the bound is 2.5e-5 m. A 1e-6 m
// check needs the actions at full precision (requested from BACKEND; see the F-34 report).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import * as P from '../src/lander/physics.js';
import { CLASSES } from '../src/lander/classes.js';
import { episodeView, pilotsFor } from '../src/lander/trajectories.js';

const FILE = fileURLToPath(new URL('../../data/policies/trajectories-v1.json', import.meta.url));
const doc = existsSync(FILE) ? JSON.parse(readFileSync(FILE, 'utf8')) : null;
const STEP_BOUND_M = 2.5e-5;

test('every step of every episode follows physics.js within the rounding bound', { skip: !doc && 'trajectories-v1.json missing' }, () => {
  let worst = 0, steps = 0;
  for (const pilot of doc.pilots) {
    const cls = CLASSES[pilot.cls];
    assert.equal(cls.t_max_n, doc.plume[pilot.cls].t_max_n, `${pilot.cls} maximum thrust`);
    for (const ep of pilot.episodes) {
      const ts = ep.episode.thrust_scale, mDry = ep.episode.m_dry_kg;
      for (let k = 0; k + 1 < ep.n_steps && 2 * k + 2 < ep.n_samples - 1; k++) {   // the touchdown step ends mid-step: skipped
        const d = ep.thrust_dir[k], [tx, ty] = P.anglesFromDirection(d[0], d[1], d[2]);
        const m = k === 0 ? ep.episode.m0_kg : mDry + ep.prop_kg[k - 1];
        const s = P.makeState(ep.pos_m[2 * k], ep.vel_mps[2 * k], m, tx, ty);
        const a0 = P.thrustToThrottle(ep.throttle[k] * cls.t_max_n * ts, cls, ts);
        const [next] = P.step(s, [a0, 0, 0], cls, 0.2, ts, 1, mDry);
        for (let j = 0; j < 3; j++) worst = Math.max(worst, Math.abs(next[j] - ep.pos_m[2 * k + 2][j]));
        steps++;
      }
    }
  }
  assert.ok(steps > 10000, `steps checked ${steps}`);
  assert.ok(worst <= STEP_BOUND_M, `worst step difference ${worst.toExponential(2)} m`);
});

test('scores, outcomes and the lab view agree with the file', { skip: !doc && 'trajectories-v1.json missing' }, () => {
  for (const pilot of doc.pilots) for (const ep of pilot.episodes) {
    const v = episodeView(ep), last = ep.pos_m[ep.n_samples - 1];
    const tol = 5e-6 * ep.n_steps + 1e-6;   // terms are stored to 1e-5, the score to 1e-6
    assert.ok(Math.abs(v.scoreFinal - ep.reward.score) < tol, `${pilot.pilot} ${ep.pick}: score ${v.scoreFinal} vs ${ep.reward.score}`);
    assert.equal(v.score(v.tEnd + 5), v.scoreFinal);
    if (ep.outcome.failure_kind !== 'timeout') {
      assert.ok(Math.abs(last[0] - ep.outcome.miss_m[0]) < 1e-5 && Math.abs(last[1] - ep.outcome.miss_m[1]) < 1e-5, 'touchdown point = miss');
      assert.ok(Math.abs(last[2]) < 1e-5, 'touchdown at z = 0');
    }
    assert.deepEqual(v.toScene([1, 2, 3]), [1, 3, -2]);
    assert.ok(v.phases.hover <= v.phases.touchdown && v.phases.touchdown <= v.tEnd);
  }
  const clps = pilotsFor(doc, 'CLPS').map(p => p.kind);
  assert.deepEqual(clps, ['network', 'classical', 'memoryless', 'ppo', 'hover']);
  assert.deepEqual(pilotsFor(doc, 'MK1').map(p => p.kind), ['classical', 'memoryless']);
});
