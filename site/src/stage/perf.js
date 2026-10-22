// Frame timing and adaptive resolution. FrameStats keeps the last 5 s of frame intervals (and GPU times when the
// EXT_disjoint_timer_query_webgl2 extension is exposed) and reports p50/p95. The resolution monitor steps the pixel
// ratio down when frames run over the tier's target and back up when there is headroom, and stops after repeated
// flip-flops (the pattern of drei's PerformanceMonitor, in plain JS).

const pct = (sorted, p) => sorted.length ? sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))] : NaN;

export class FrameStats {
  constructor(windowMs = 5000) { this.windowMs = windowMs; this.t = []; this.dt = []; this.gpu = []; this.gt = []; }
  push(now, dt) {
    if (dt > 250) return;   // a throttled or hidden window, not a slow GPU: keep it out of the stats and the monitor
    this.t.push(now); this.dt.push(dt);
    while (this.t.length && now - this.t[0] > this.windowMs) { this.t.shift(); this.dt.shift(); }
  }
  pushGpu(now, ms) {
    this.gt.push(now); this.gpu.push(ms);
    while (this.gt.length && now - this.gt[0] > this.windowMs) { this.gt.shift(); this.gpu.shift(); }
  }
  summary() {
    const s = [...this.dt].sort((a, b) => a - b), g = [...this.gpu].sort((a, b) => a - b);
    return { n: s.length, p50: pct(s, 0.5), p90: pct(s, 0.9), p95: pct(s, 0.95), gpuP50: pct(g, 0.5), gpuP95: pct(g, 0.95), gpuN: g.length };
  }
  reset() { this.t = []; this.dt = []; this.gpu = []; this.gt = []; }
}

// GPU time of whatever runs between begin() and end(), read back a few frames later (never blocks)
export class GpuTimer {
  constructor(gl) {
    this.gl = gl; this.ext = gl.getExtension('EXT_disjoint_timer_query_webgl2'); this.pending = []; this.active = null;
  }
  get available() { return !!this.ext; }
  begin() {
    if (!this.ext || this.active || this.pending.length > 4) return;
    this.active = this.gl.createQuery(); this.gl.beginQuery(this.ext.TIME_ELAPSED_EXT, this.active);
  }
  end() { if (!this.active) return; this.gl.endQuery(this.ext.TIME_ELAPSED_EXT); this.pending.push(this.active); this.active = null; }
  poll(cb) {
    const gl = this.gl;
    if (!this.ext) return;
    const disjoint = gl.getParameter(this.ext.GPU_DISJOINT_EXT);
    while (this.pending.length && gl.getQueryParameter(this.pending[0], gl.QUERY_RESULT_AVAILABLE)) {
      const q = this.pending.shift();
      if (!disjoint) cb(gl.getQueryParameter(q, gl.QUERY_RESULT) / 1e6);
      gl.deleteQuery(q);
    }
  }
  dispose() { for (const q of this.pending) this.gl.deleteQuery(q); this.pending = []; }
}

// Pixel ratio inside the tier's pixel budget, never above the device's
export function budgetRatio(cssW, cssH, pixels) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  return Math.max(0.5, Math.min(dpr, Math.sqrt(pixels / Math.max(1, cssW * cssH))));
}

export class ResolutionMonitor {
  constructor({ targetMs, onChange, min = 0.5 }) {
    Object.assign(this, { targetMs, onChange, min, max: 1, ratio: 1, flips: 0, lastDir: 0, since: 0, enabled: true });
  }
  setMax(max) { this.max = max; if (this.ratio > max || !this.enabled) { this.ratio = max; this.onChange(max); } }
  // called about once a second while frames are being drawn continuously
  check(now, s) {
    if (!this.enabled || s.n < 30 || now - this.since < 1000) return;
    this.since = now;
    const slow = (s.gpuN > 10 ? s.gpuP95 : s.p90) > this.targetMs * 1.15;
    const fast = s.gpuN > 10 ? s.gpuP95 < this.targetMs * 0.6 : s.p90 < this.targetMs * 1.02;
    let dir = 0;
    if (slow && this.ratio > this.min) dir = -1;
    else if (fast && this.ratio < this.max && now - (this.lastUp || 0) > 4000) dir = 1;
    if (!dir) return;
    if (this.lastDir && dir !== this.lastDir && ++this.flips >= 4) { this.enabled = false; return; }   // settle, stop hunting
    this.lastDir = dir; if (dir > 0) this.lastUp = now;
    this.ratio = Math.max(this.min, Math.min(this.max, +(this.ratio + dir * 0.15).toFixed(2)));
    this.onChange(this.ratio);
  }
}
