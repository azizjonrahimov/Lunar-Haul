// F-61: the integrity network (E56) in the browser: a port of lunarsim.nn.model.Policy (float64 numpy reference). One
// window [W][10] of raw features, oldest step first -> one logit, plus every layer's activations for the page.
// Layer rule (the policy file's layer_note): w[out][in][tap]; valid convolution, tap j reads step t + j * dilation; a
// residual layer adds its input at the same (latest) steps to its ReLU output; the last layer gives the logit.
export function squash(window, transform) {
  return window.map(row => row.map((x, j) => { const { fn, pre, post } = transform[j], v = x / pre; return (fn === 'slog1p' ? Math.sign(v) * Math.log1p(Math.abs(v)) : v) / post; }));
}

// returns { logit, acts: [h0 = squashed input as [ch][t], h1, ...] }
export function forward(policy, window) {
  const W = policy.obs.window_steps, x = squash(window.slice(-W), policy.obs.transform);
  let h = x[0].map((_, c) => x.map(row => row[c]));   // [channel][time]
  const acts = [h];
  for (const L of policy.layers) {
    const w = L.w, b = L.b, d = L.dilation, k = w[0][0].length, T = h[0].length, tOut = T - (k - 1) * d;
    const y = w.map((wo, o) => {
      const out = new Float64Array(tOut).fill(b[o]);
      for (let i = 0; i < wo.length; i++) { const wi = wo[i], hi = h[i]; for (let j = 0; j < k; j++) { const c = wi[j], off = j * d; for (let t = 0; t < tOut; t++) out[t] += c * hi[off + t]; } }
      if (L.act === 'relu') for (let t = 0; t < tOut; t++) if (out[t] < 0) out[t] = 0;
      return out;
    });
    h = L.residual ? y.map((row, o) => row.map((v, t) => v + h[o][T - tOut + t])) : y.map(row => Array.from(row));
    acts.push(h);
  }
  return { logit: h[0][h[0].length - 1], acts };
}

export const prob = logit => 1 / (1 + Math.exp(-logit));
