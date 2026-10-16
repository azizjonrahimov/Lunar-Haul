// The learned rover driver (B-13 export, lunarsim-policy v1 kind "cnn") in the browser: onnxruntime-web, WASM backend,
// one thread. The runtime and its 14 MB .wasm are fetched only when the driver is chosen; nothing here runs on page load.
// Inputs are the env's own observation, exactly as lunarsim.rover.onnx_driver feeds it: patch [1,3,32,32] and
// scalars [1,5] float32 (rows forward from 8 cells behind, columns left..right; normalisation in the card).

let ortPromise = null;
/* load onnxruntime-web once */
export function loadOrt() {
  ortPromise ||= import('onnxruntime-web/wasm').then(ort => {
    // the bundled build carries its own JS loader and finds its .wasm via import.meta.url, which Vite emits as a hashed
    // asset of the site (no CDN); one thread, since GitHub Pages cannot send the cross-origin-isolation headers
    ort.env.wasm.numThreads = 1;
    return ort;
  });
  return ortPromise;
}

const hex = buf => [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');

export class OnnxDriver {
  /* await OnnxDriver.load(card, onnxBytes): checks the card, the sha256 of the .onnx, opens the session */
  static async load(card, bytes) {
    if (card.format !== 'lunarsim-policy' || card.kind !== 'cnn') throw new Error(`${card.id}: not a lunarsim-policy cnn card`);
    if (card.onnx_sha256) {
      const sha = hex(await crypto.subtle.digest('SHA-256', bytes));
      if (sha !== card.onnx_sha256) throw new Error(`${card.onnx}: sha256 ${sha.slice(0, 12)}… does not match the card (${card.onnx_sha256.slice(0, 12)}…)`);
    }
    const ort = await loadOrt();
    const session = await ort.InferenceSession.create(new Uint8Array(bytes), { executionProviders: ['wasm'], graphOptimizationLevel: 'all' });
    return new OnnxDriver(card, ort, session);
  }
  constructor(card, ort, session) {
    Object.assign(this, { card, ort, session, id: card.id });
    const P = card.input.patch.shape, S = card.input.scalars.shape;
    this.patchShape = [1, ...P]; this.nPatch = P.reduce((a, b) => a * b, 1); this.nScalars = S[0];
    this.name = `Learned driver (${card.id})`;
  }
  /* batch forward: patch Float32Array(n*3*32*32), scalars Float32Array(n*5) -> Float32Array(n*2) */
  async runBatch(patch, scalars, n) {
    const feeds = { patch: new this.ort.Tensor('float32', patch, [n, ...this.patchShape.slice(1)]), scalars: new this.ort.Tensor('float32', scalars, [n, this.nScalars]) };
    const out = await this.session.run(feeds);
    return out.action.data;
  }
  /* controller interface used by the lab: async, returns [steer_rate_cmd, throttle] in [-1, 1] */
  async actAsync(obs) {
    if (obs.patch.length !== this.nPatch || obs.scalars.length !== this.nScalars) throw new Error(`${this.id}: observation shape does not match the card`);
    const a = await this.runBatch(Float32Array.from(obs.patch), Float32Array.from(obs.scalars), 1);
    return [a[0], a[1]];
  }
  /* the card's stored check vectors (onnxruntime CPU outputs) -> {n, maxErr, tolerance, ok} */
  async check(chk) {
    const n = chk.patch.length, P = new Float32Array(n * this.nPatch), S = new Float32Array(n * this.nScalars);
    chk.patch.forEach((p, i) => P.set(p.flat(2), i * this.nPatch)); chk.scalars.forEach((s, i) => S.set(s, i * this.nScalars));
    const out = await this.runBatch(P, S, n);
    let maxErr = 0; chk.action.forEach((a, i) => a.forEach((v, j) => { maxErr = Math.max(maxErr, Math.abs(out[i * 2 + j] - v)); }));
    const tolerance = chk.tolerance ?? 1e-5;
    return { n, maxErr, tolerance, ok: maxErr <= tolerance };
  }
}
