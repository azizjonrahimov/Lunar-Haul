// F-50: the shared time scale's wording and ?speed= parsing (site/src/ui/speeds.js), the eased drives
// (site/src/world/scene-data.js easeLeg and position options) and "Skip quiet time" (site/src/world/quiet.js) on a real
// scene package (run: node --test "site/tests/*.test.mjs").
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { SPEEDS, speedName, speedText, parseSpeed, nearest, hoursText, simSpan } from '../src/ui/speeds.js';
import { loadScene, easeLeg } from '../src/world/scene-data.js';
import { motionIndex, quietJump } from '../src/world/quiet.js';

test('speed names and the on-screen label', () => {
  assert.equal(speedName(1), 'real time');
  assert.equal(speedName(300), '5 min/s');
  assert.equal(speedName(86400), '1 day/s');
  assert.equal(speedName(259200), '3 days/s');
  assert.equal(speedName(10), '10×');
  assert.equal(speedText(300), '1 s on screen = 5 min on the Moon');
  assert.equal(speedText(3600), '1 s on screen = 1 h on the Moon');
  assert.equal(simSpan(900), '15 min');
  assert.equal(hoursText(6 + 20 / 60), '6 h 20 min');
  assert.equal(hoursText(51), '2 days 3 h');
  assert.equal(hoursText(0.5), '30 min');
});

test('?speed= values', () => {
  assert.equal(parseSpeed('5min'), 300);
  assert.equal(parseSpeed('1h'), 3600);
  assert.equal(parseSpeed('1d'), 86400);
  assert.equal(parseSpeed('3days'), 259200);
  assert.equal(parseSpeed('60x'), 60);
  assert.equal(parseSpeed('300'), 300);
  assert.equal(parseSpeed('real'), 1);
  assert.equal(parseSpeed('fast'), null);
  assert.equal(parseSpeed(''), null);
  assert.equal(nearest(Object.values(SPEEDS), 250), 300);
  assert.equal(nearest([1, 2, 5, 0], 3), 2);
});

test('easeLeg: starts and ends at rest, arrives on time, never faster than 1/(1-a)', () => {
  for (const a of [0.05, 0.12, 0.25]) {
    assert.equal(easeLeg(0, a), 0); assert.ok(Math.abs(easeLeg(1, a) - 1) < 1e-12);
    let prev = 0, vmax = 0;
    for (let i = 1; i <= 1000; i++) { const g = i / 1000, f = easeLeg(g, a), v = (f - prev) * 1000; assert.ok(v >= -1e-9); vmax = Math.max(vmax, v); prev = f; }
    assert.ok(vmax <= 1 / (1 - a) + 1e-6);
    assert.ok((easeLeg(0.001, a) - 0) * 1000 < 0.05);   // slow at the start
  }
  assert.equal(easeLeg(0.3, 0), 0.3);
});

const PKG = fileURLToPath(new URL('../../data/scenes/P2/', import.meta.url));
const fetchFn = async u => { const b = await readFile(u); return { ok: true, json: async () => JSON.parse(b), arrayBuffer: async () => b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) }; };

test('P2: eased positions keep the ends, smoothed headings stay on the road; quiet time is skipped only when nothing drives', { skip: !existsSync(PKG) && 'data/scenes/P2 not present' }, async () => {
  const pkg = await loadScene(PKG, { fetchFn }), chunks = await Promise.all(pkg.index.chunks.map((_, k) => pkg.chunk(k)));
  const C = pkg.columns, n = pkg.index.segment_columns.length, ch = chunks[0], s = ch.seg;
  let checked = 0;
  for (let r = 0; r < ch.rows && checked < 20; r++) {
    const o = r * n; if (s[o + C.route] < 0 || s[o + C.f0] === s[o + C.f1]) continue;
    const veh = s[o + C.veh], t0 = s[o + C.t0], t1 = s[o + C.t1], mid = (t0 + t1) / 2;
    const a = pkg.position(ch, veh, t0 + 1e-6), b = pkg.position(ch, veh, t0 + 1e-6, { ease: 2 / 60 });
    assert.ok(Math.hypot(a.x - b.x, a.y - b.y) < 1, 'same start');
    const m1 = pkg.position(ch, veh, mid), m2 = pkg.position(ch, veh, mid, { ease: 2 / 60, turnM: 12 });
    assert.ok(Math.hypot(m1.x - m2.x, m1.y - m2.y) < 1e-3, 'symmetric profile: same place at mid-drive');
    const d = Math.abs(((m2.heading - m1.heading) % 360 + 540) % 360 - 180);
    assert.ok(d < 90, `smoothed heading within 90° of the segment's (${d})`);
    checked++;
  }
  assert.ok(checked > 0);
  const mi = motionIndex(pkg, chunks);
  assert.ok(mi.intervals.length > 100);
  for (let i = 1; i < mi.intervals.length; i++) assert.ok(mi.intervals[i][0] > mi.intervals[i - 1][1], 'merged and sorted');
  const [a0, a1] = mi.intervals[3], rate = 300 / 3600;
  assert.equal(quietJump((a0 + a1) / 2, rate, mi), null, 'never while a rover drives');
  const gapT = a1 + 1e-3, next = mi.intervals[4][0];
  const j = quietJump(gapT, rate, mi);
  if (next - gapT > 3 * rate) assert.ok(Math.abs(j - (next - rate)) < 1e-9, 'one screen-second before the next drive');
  else assert.equal(j, null);
  assert.equal(quietJump(gapT, rate, mi, gapT + 30 * rate), null, 'not with a landing within a screen-minute');
  // playing the year at 5 min/s: how much is skipped, and no jump lands inside a drive
  let t = 0, skipped = 0, jumps = 0;
  while (t < pkg.horizon - 1) {
    const q = quietJump(t, rate, mi);
    if (q !== null) { assert.ok(!mi.moving(q)); skipped += q - t; jumps++; t = q; }
    t += rate / 60;   // one 60 Hz frame
  }
  console.log(`P2 at 5 min/s: ${jumps} skips, ${(100 * skipped / pkg.horizon).toFixed(0)} % of the year skipped, screen time ${((pkg.horizon - skipped) / rate / 3600).toFixed(1)} h instead of ${(pkg.horizon / rate / 3600).toFixed(1)} h`);
});
