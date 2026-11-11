// F-60: the /protocol/ link-budget figure runs a JS port of lunarsim/atc/radio.py (src/protocol/radio.js). Check the
// port against the per-class link numbers radio.py wrote into results/E48_sizing.json (B-89): path loss, SNR after the
// margin and capacity at the worst hop, the horizon, and the capacity at the longest visible hop. The file rounds to
// 0.1, so the tolerance is half a unit in the last place.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { horizon, flatLoss, capacity } from '../src/protocol/radio.js';
import { P } from '../src/protocol/params.js';

const F = new URL('../../results/E48_sizing.json', import.meta.url), have = existsSync(F);
const S = have ? JSON.parse(readFileSync(F, 'utf8').replace(/\bNaN\b/g, 'null')) : null;
const near = (a, b, tol, what) => assert.ok(Math.abs(a - b) <= tol, `${what}: ${a} against ${b} (tolerance ${tol})`);

test('radio.js reproduces E48 per-class link numbers (flat ground, 1 MHz, 3 dBi, NF 5 dB, margin 10 dB)', { skip: !have && 'results/E48_sizing.json missing' }, () => {
  let n = 0;
  for (const [k, c] of Object.entries(S.classes)) {
    const L = c.link; if (!L) continue;
    const f = L.freq_ghz * 1e9, opt = { bw: 1e6, txW: L.tx_power_w };
    const loss = flatLoss(L.worst_hop_m, L.antenna_m, L.peer_antenna_m, f), cap = capacity(loss, opt);
    near(loss, L.loss_db_worst_hop, 0.051, `${k} loss`);
    near(cap.snr, L.snr_db_worst_hop, 0.051, `${k} snr`);
    near(cap.kbps, L.worst_hop_kbps_if_visible, 0.051, `${k} kbps if visible`);
    near(horizon(L.antenna_m) + horizon(L.peer_antenna_m), L.mutual_horizon_m, 0.051, `${k} horizon`);
    assert.equal(L.worst_hop_m > L.mutual_horizon_m, L.beyond_horizon_at_worst_hop, `${k} beyond the horizon`);
    if (L.longest_hop_kbps !== undefined) near(capacity(flatLoss(L.longest_hop_m, L.antenna_m, L.peer_antenna_m, f), opt).kbps, L.longest_hop_kbps, 0.051, `${k} longest hop`);
    n++;
  }
  assert.ok(n >= 4, `only ${n} classes checked`);
});

test('the figure uses the same budget values as radio.py', () => {
  assert.equal(P.tx_w.value, 1); assert.equal(P.gain.value, 3); assert.equal(P.nf.value, 5); assert.equal(P.margin.value, 10); assert.equal(P.rate.value, 16);
});
