// Runtime for lunarsim-policy v1 MLP files (PLAN 5.2), the browser twin of lunarsim/lander/policy.py.
// Forward pass in float64: h = act(W h + b) per layer; W rows are outputs (torch nn.Linear layout).
// deterministic "mean_clipped" -> clip(mean, low, high); "argmax" -> index of the max.
const ACTS = { tanh: Math.tanh, linear: x => x, relu: x => Math.max(x, 0) };

export class MlpPolicy {
  constructor(doc) {
    if (doc.format !== 'lunarsim-policy' || doc.version !== 1) throw new Error('not a lunarsim-policy v1 document');
    if (doc.kind !== 'mlp') throw new Error(`MlpPolicy reads kind "mlp", got ${doc.kind}`);
    this.doc = doc; this.id = doc.id;
    this.layers = doc.layers.map((L, i) => {
      if (!ACTS[L.act]) throw new Error(`layer ${i}: unknown activation ${L.act}`);
      if (L.w.length !== L.b.length) throw new Error(`layer ${i}: weight/bias size mismatch`);
      return { w: L.w.map(r => Float64Array.from(r)), b: Float64Array.from(L.b), act: ACTS[L.act] };
    });
    this.low = doc.act.low || []; this.high = doc.act.high || []; this.deterministic = doc.deterministic || 'mean_clipped';
    this.obsDim = this.layers[0].w[0].length;
  }
  forward(obs) {
    let h = Float64Array.from(obs);
    for (const { w, b, act } of this.layers) {
      const out = new Float64Array(w.length);
      for (let i = 0; i < w.length; i++) { const row = w[i]; let s = 0; for (let j = 0; j < row.length; j++) s += row[j] * h[j]; out[i] = act(s + b[i]); }
      h = out;
    }
    return h;
  }
  act(obs) {
    const out = this.forward(obs);
    if (this.deterministic === 'argmax') { let k = 0; for (let i = 1; i < out.length; i++) if (out[i] > out[k]) k = i; return k; }
    return Array.from(out, (v, i) => Math.max(this.low[i], Math.min(this.high[i], v)));
  }
}

/* check(policy, checkDoc) -> {n, maxErr, tolerance, ok}: the shared <id>.check.json vectors */
export function checkPolicy(policy, chk) {
  let maxErr = 0;
  chk.obs.forEach((o, k) => { const a = policy.act(o), want = chk.act[k]; (Array.isArray(want) ? want : [want]).forEach((w, i) => { maxErr = Math.max(maxErr, Math.abs((Array.isArray(a) ? a[i] : a) - w)); }); });
  const tolerance = chk.tolerance ?? 1e-6;
  return { n: chk.obs.length, maxErr, tolerance, ok: maxErr <= tolerance };
}
