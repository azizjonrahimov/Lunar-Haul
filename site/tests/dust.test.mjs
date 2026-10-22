// F-33: the landing dust is deterministic and follows its stated physics (run: node --test site/tests/).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildLandingDust, onsetHeight, G_MOON } from '../src/stage/effects/dust-model.js';

// a CLPS-like final descent: 40 m to the ground in 20 s at 4 kN, cut-off at touchdown, drifting 3 m east
function timeline() {
  const t = [], h = [], thrust = [], gx = [], gy = [], gz = [];
  for (let i = 0; i <= 260; i++) {
    const x = i * 0.1; t.push(x); h.push(Math.max(0, 40 - 2 * x)); thrust.push(x <= 20 ? 4000 : 0);
    gx.push(0.15 * Math.min(x, 20)); gy.push(1.5); gz.push(0);
  }
  return { t, h, thrust, gx, gy, gz };
}
const build = (seed, n = 5000) => buildLandingDust({ timeline: timeline(), cutoff: 20, keepoutM: 1000, seed, n });

test('the same seed gives the same particles; another seed does not', () => {
  const a = build(7), b = build(7), c = build(8);
  for (const k of ['birth', 'origin', 'vel', 'life', 'size']) assert.deepEqual(a[k], b[k], k);
  assert.notDeepEqual(a.origin, c.origin);
  const pa = [0, 0, 0], pb = [0, 0, 0];
  for (const x of [12.3, 18.9, 21.4]) for (let i = 0; i < a.n; i += 97) {
    assert.equal(a.positionAt(i, x, pa), b.positionAt(i, x, pb));
    assert.deepEqual(pa, pb);
  }
});

test('births only below the onset height and before cut-off', () => {
  const d = build(3), tOn = (40 - onsetHeight(4000)) / 2;   // the nozzle crosses the onset height here
  for (let i = 0; i < d.n; i++) { assert.ok(d.birth[i] >= tOn - 1e-3 && d.birth[i] <= 20 + 1e-3, `birth ${d.birth[i]}`); }
  assert.equal(onsetHeight(5000), 15);
  assert.ok(Math.abs(onsetHeight(44000) - 15 * Math.sqrt(8.8)) < 1e-9);
});

test('ballistic paths: launch 1-3 deg, g = 1.62, land within the keep-out radius', () => {
  const d = build(11), p = [0, 0, 0];
  for (let i = 0; i < d.n; i++) {
    const vx = d.vel[3 * i], vy = d.vel[3 * i + 1], vz = d.vel[3 * i + 2], th = Math.atan2(vy, Math.hypot(vx, vz)) * 180 / Math.PI;
    assert.ok(th >= 1 - 1e-4 && th <= 3 + 1e-4, `angle ${th}`);
    const range = Math.hypot(vx, vz) * d.life[i];
    assert.ok(range <= 1000 + 1e-2 && range >= 20 - 1e-2, `range ${range}`);
    assert.ok(Math.abs(2 * vy / G_MOON - d.life[i]) < 1e-3);
    assert.ok(d.positionAt(i, d.birth[i] + d.life[i] / 2, p));
    assert.ok(Math.abs(p[1] - d.origin[3 * i + 1] - vy * vy / (2 * G_MOON)) < 1e-3, 'apex height v²/2g');
  }
});

test('obscuration peaks in the last seconds and is zero from cut-off; scour grows to 1', () => {
  const d = build(5);
  assert.equal(d.obscuration(20), 0); assert.equal(d.obscuration(22), 0);
  assert.ok(d.obscuration(19.9) > 0.8, `just before cut-off ${d.obscuration(19.9)}`);
  assert.ok(d.obscuration(15) < d.obscuration(19), 'rises towards touchdown');
  assert.equal(d.scour(0), 0); assert.ok(Math.abs(d.scour(25) - 1) < 1e-9);
  assert.ok(d.alive(21) > 0 && d.alive(40) === 0, 'grains still in flight just after cut-off, none later');
});
