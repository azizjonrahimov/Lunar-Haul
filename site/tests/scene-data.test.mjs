// F-36: the browser's scene-package reader (site/src/world/scene-data.js) against Python's lunarsim.scene.position at
// 30 moments per package (20 random, 10 inside drives), from site/tests/fixtures/scene_positions.json
// (run: node --test "site/tests/*.test.mjs").
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { loadScene } from '../src/world/scene-data.js';

const DATA = fileURLToPath(new URL('../../data/scenes/', import.meta.url));
const fixture = JSON.parse(readFileSync(new URL('./fixtures/scene_positions.json', import.meta.url), 'utf8'));
// fetch() for files on disk: what loadScene needs (ok, json(), arrayBuffer())
const fsFetch = async url => {
  const b = readFileSync(url);
  return { ok: true, json: async () => JSON.parse(b.toString('utf8')), arrayBuffer: async () => b.buffer.slice(b.byteOffset, b.byteOffset + b.length) };
};

for (const [pkg, rows] of Object.entries(fixture.packages)) {
  test(`${pkg}: positions and states equal the Python reader's`, { skip: !existsSync(DATA + pkg) && `data/scenes/${pkg} missing` }, async () => {
    const sc = await loadScene(DATA + pkg + '/', { fetchFn: fsFetch });
    let worst = 0, drives = 0;
    for (const r of rows) {
      const ch = await sc.chunk(sc.chunkIndex(r.t)), p = sc.position(ch, r.veh, r.t);
      assert.ok(p, `${pkg} vehicle ${r.veh} at ${r.t} h: no segment`);
      assert.equal(p.state, r.state, `${pkg} vehicle ${r.veh} at ${r.t} h`);
      worst = Math.max(worst, Math.abs(p.x - r.x), Math.abs(p.y - r.y), Math.abs(p.z - r.z));
      if (r.state === 'driving') drives++;
    }
    assert.ok(drives >= 10, 'drives covered');
    assert.ok(worst < 1e-6, `worst difference ${worst.toExponential(2)} m`);
  });
}

test('hourly series: sun, night, Earth and the waiting counts', { skip: !existsSync(DATA + 'P2') }, async () => {
  const sc = await loadScene(DATA + 'P2/', { fetchFn: fsFetch }), ch = await sc.chunk(0), h = sc.hourly(ch, 100.5);
  assert.ok(h.sun_az_deg >= 0 && h.sun_az_deg < 360);
  assert.ok(h.earth_el_deg > -8 && h.earth_el_deg < 7);
  assert.deepEqual(Object.keys(h.waiting).sort(), Object.keys(sc.index.sites).sort());
  for (const w of Object.values(h.waiting)) assert.ok(w.items >= 0 && w.kg >= 0);
});
