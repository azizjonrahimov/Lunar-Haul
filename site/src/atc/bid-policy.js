// Runtime of the ATC bid policy files (lunar/ATC-bid-v1, kind linear or mlp), the browser twin of
// lunarsim/atc/learned.py Policy: x_norm = (x - offset) / scale, then the layers in float64. No DOM, so the node test
// (tests/atc-bid.test.mjs) and the page (bid.js) run the same code.
export const FEATURES = ['job_h', 'age_d', 'prio', 'mass_frac', 'approach_h', 'battery', 'dark_or_low', 'link_base', 'heard', 'queue', 'bundle_n', 'slack_d', 'landing'];
export const TARGET_H = { 1: 24, 2: 168, 3: 720 };   // learned.py: target hours by priority (urgent, normal, deferrable)
const ACTS = { linear: x => x, tanh: Math.tanh };

export class AtcBidPolicy {
  constructor(doc) {
    if (doc.format !== 'lunarsim-policy' || doc.version !== 1 || doc.env !== 'lunar/ATC-bid-v1') throw new Error('not an ATC bid policy v1');
    if (doc.obs.names.join() !== FEATURES.join()) throw new Error('policy features differ from lunarsim.atc.learned.FEATURES');
    this.doc = doc; this.id = doc.id; this.offset = doc.obs.offset; this.scale = doc.obs.scale;
    this.layers = doc.layers.map((L, i) => { if (!ACTS[L.act]) throw new Error(`layer ${i}: unknown activation ${L.act}`); return { w: L.w, b: L.b, act: ACTS[L.act] }; });
  }
  // g(features), hours: the robot bids bid - urgency_usd_per_h * g
  correction(x) {
    let v = x.map((q, i) => (q - this.offset[i]) / this.scale[i]);
    for (const { w, b, act } of this.layers) v = w.map((row, i) => act(row.reduce((s, wij, j) => s + wij * v[j], 0) + b[i]));
    return v[0];
  }
}
export function checkBid(policy, chk) {
  let maxErr = 0;
  chk.obs.forEach((o, k) => { maxErr = Math.max(maxErr, Math.abs(policy.correction(o) - (Array.isArray(chk.act[k]) ? chk.act[k][0] : chk.act[k]))); });
  return { n: chk.obs.length, maxErr, tolerance: chk.tolerance, ok: maxErr <= chk.tolerance };
}

