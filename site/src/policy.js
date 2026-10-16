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
    this.obsNames = (doc.obs && doc.obs.names) || null;   // the env picks its observation version from these (obs v2: 15, v3: 19)
    if (this.obsNames && this.obsNames.length !== this.obsDim) throw new Error(`obs.names has ${this.obsNames.length} entries but the network takes ${this.obsDim}`);
  }
  forward(obs) {
    if (obs.length !== this.obsDim) throw new Error(`${this.id}: observation has ${obs.length} values, the network takes ${this.obsDim}`);
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

/* check(policy, checkDoc) -> {n, maxErr, tolerance, ok, sb3?}: the shared <id>.check.json vectors.
   Current files: `act` = float64 numpy-runtime actions (tolerance 1e-6) and `sb3_act` = Stable-Baselines3's float32
   actions (tolerance 1e-4). Older files have only `act` (then SB3's float32 output) at their stated tolerance. */
function maxDiff(policy, obs, want) {
  let m = 0;
  obs.forEach((o, k) => { const a = policy.act(o), w = want[k]; (Array.isArray(w) ? w : [w]).forEach((x, i) => { m = Math.max(m, Math.abs((Array.isArray(a) ? a[i] : a) - x)); }); });
  return m;
}
export function checkPolicy(policy, chk) {
  const tolerance = chk.tolerance ?? 1e-6, maxErr = maxDiff(policy, chk.obs, chk.act);
  const out = { n: chk.obs.length, maxErr, tolerance, ok: maxErr <= tolerance, against: chk.sb3_act ? 'numpy float64 runtime' : 'Stable-Baselines3 (float32)' };
  if (chk.sb3_act) { const t = chk.sb3_tolerance ?? 1e-4, e = maxDiff(policy, chk.obs, chk.sb3_act); out.sb3 = { maxErr: e, tolerance: t, ok: e <= t }; out.ok = out.ok && out.sb3.ok; }
  return out;
}
