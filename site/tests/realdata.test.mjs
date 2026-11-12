// F-56 / B-97: the real-data boxes say what the data are and carry the report's reading. Telemetry: real spacecraft
// (SMAP, MSL), detectors that add up evidence find at least as many anomalies as one-step ones. Artemis II: limb
// navigation between Earth and Moon (not on the surface), the body taken from the geometry, two of five discs Earth.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { b97, telemetryRows, artemisRows } from '../lib/realdata.mjs';

const SRC = new URL('../../results/B97_realdata.json', import.meta.url);
const have = existsSync(SRC);

test('telemetry box: real spacecraft, four detectors, accumulating ones find at least as many', { skip: !have && 'B-97 missing' }, () => {
  const D = JSON.parse(readFileSync(SRC, 'utf8')), rows = telemetryRows(D);
  assert.equal(rows.length, 4);
  for (const sc of ['msl', 'smap']) {
    const one = Math.max(...rows.filter(r => r.k === 'zscore' || r.k === 'chi2_step').map(r => r[sc].found));
    const acc = Math.max(...rows.filter(r => r.k === 'chi2_window_16' || r.k === 'cusum_k0.5').map(r => r[sc].found));
    assert.ok(acc >= one, sc);
  }
  const html = b97('telemetry');
  assert.match(html, /SMAP satellite/);
  assert.match(html, /Curiosity/);
  assert.match(html, /not lunar rover data/);
  assert.match(html, /data-flag="Measured"/);
});

test('Artemis II box: limb navigation in space, the body from the geometry, Earth discs named', { skip: !have && 'B-97 missing' }, () => {
  const D = JSON.parse(readFileSync(SRC, 'utf8')), rows = artemisRows(D);
  const used = rows.filter(r => r.body), earth = used.filter(r => r.body === 'Earth');
  assert.equal(used.length, 5);
  assert.equal(earth.length, 2);
  assert.ok(rows.some(r => !r.body && /unusable/.test(r.fit)));
  const html = b97('artemis');
  assert.match(html, /not navigation on the surface/);
  assert.match(html, /Two of the five usable discs are <b>Earth<\/b>, although the archive labels them Moon/);
  assert.match(html, /data-flag="Measured"/);
  assert.match(b97('geometry'), /10<sup>-1[0-9]<\/sup> degrees/);
  assert.throws(() => b97('nope'), /unknown box/);
});
