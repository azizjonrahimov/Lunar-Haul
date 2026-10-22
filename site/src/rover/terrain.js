// Rover-side terrain queries, a line-by-line port of lunarsim.terrain.Terrain's reader (height, slope, cell,
// contains, roughness20, shadow_grid / cast_shadow). Grids are stored row 0 = SOUTH, as the Python reader stores
// them after flipping the PNGs. Heights are 0.5 m-quantised above an integer offset, so Float32Array is exact.
import { decodePngGray } from '../terrain.js';

export const MOON_RADIUS_M = 1737400.0;    // Spec (IAU mean radius)
export const SUN_ELEVATION_DEG = 1.5;      // Assumed (as lunarsim.terrain)

/* Python's round(): half to even (banker's rounding) */
export function pyRound(x) { const r = Math.round(x); return (Math.abs(x % 1) === 0.5 && r % 2 !== 0) ? r - 1 : r; }
/* Python's float %: result has the sign of the divisor */
export const pyMod = (a, b) => { const m = a % b; return (m !== 0 && (m < 0) !== (b < 0)) ? m + b : m; };

function flipToSouthUp(data, rows, cols, Arr, map = v => v) {
  const out = new Arr(rows * cols);
  for (let r = 0; r < rows; r++) { const src = (rows - 1 - r) * cols, dst = r * cols; for (let c = 0; c < cols; c++) out[dst + c] = map(data[src + c]); }
  return out;
}

export class RoverTerrain {
  constructor(meta, h5, h20, s20) {
    const L = meta.layers, { offset_m: off, scale_m_per_unit: sc } = meta.z_encoding;
    this.meta = meta; this.sizeM = meta.size_m;
    this.px5 = L.height_5m.px_m; this.px20 = L.height_20m.px_m;
    this.r5 = h5.height; this.c5 = h5.width; this.r20 = h20.height; this.c20 = h20.width;
    this.z5 = flipToSouthUp(h5.data, this.r5, this.c5, Float32Array, v => off + sc * v);
    this.z20 = flipToSouthUp(h20.data, this.r20, this.c20, Float32Array, v => off + sc * v);
    this.slope20 = flipToSouthUp(s20.data, s20.height, s20.width, Float64Array);
    this._rough = null; this._shadow = new Map();
  }
  static async load(base, onProgress) {
    const get = async f => { const r = await fetch(base + f); if (!r.ok) throw new Error(`${f}: HTTP ${r.status}`); return r; };
    const meta = await (await get('meta.json')).json(); onProgress && onProgress('heights (5 m, 2.9 MB)…');
    const L = meta.layers, png = async (k, d) => decodePngGray(await (await get(L[k].file)).arrayBuffer(), d);
    const [h5, h20, s20] = await Promise.all([png('height_5m', 16), png('height_20m', 16), png('slope_20m', 8)]);
    return new RoverTerrain(meta, h5, h20, s20);
  }
  /* F-40: the same terrain built in a module worker (terrain-worker.js), its roughness grid included, so the page's main
     thread stays free while it loads; falls back to load() where module workers are unavailable */
  static loadInWorker(base, onProgress) {
    let w;
    try { w = new Worker(new URL('./terrain-worker.js', import.meta.url), { type: 'module' }); } catch (e) { return RoverTerrain.load(base, onProgress); }
    return new Promise((resolve, reject) => {
      w.onmessage = e => {
        const m = e.data;
        if (m.type === 'progress') { onProgress && onProgress(m.message); return; }
        w.terminate();
        if (m.type === 'error') { reject(new Error(m.message)); return; }
        const t = Object.create(RoverTerrain.prototype);
        Object.assign(t, m.fields, { _rough: m.rough, _shadow: new Map() });
        resolve(t);
      };
      w.onerror = e => { w.terminate(); RoverTerrain.load(base, onProgress).then(resolve, reject); e.preventDefault?.(); };   // e.g. no module workers
      w.postMessage({ base: new URL(base, location.href).href });
    });
  }
  /* the plain fields of a built terrain (what loadInWorker() sends across); _rough and _shadow are kept apart */
  fields() {
    const { meta, sizeM, px5, px20, r5, c5, r20, c20, z5, z20, slope20 } = this;
    return { meta, sizeM, px5, px20, r5, c5, r20, c20, z5, z20, slope20 };
  }
  /* _bilinear: cell-centred grid, row 0 = south, clamped at the edges (same arithmetic order as numpy) */
  static bilinear(g, rows, cols, px, x, y) {
    const u = Math.min(Math.max(x / px - 0.5, 0), cols - 1), v = Math.min(Math.max(y / px - 0.5, 0), rows - 1);
    const i0 = cols > 1 ? Math.min(Math.floor(u), cols - 2) : 0, j0 = rows > 1 ? Math.min(Math.floor(v), rows - 2) : 0;
    const fu = u - i0, fv = v - j0, i1 = Math.min(i0 + 1, cols - 1), j1 = Math.min(j0 + 1, rows - 1);
    return ((g[j0 * cols + i0] * (1 - fu) + g[j0 * cols + i1] * fu) * (1 - fv) + (g[j1 * cols + i0] * (1 - fu) + g[j1 * cols + i1] * fu) * fv);
  }
  height(x, y) { return RoverTerrain.bilinear(this.z5, this.r5, this.c5, this.px5, x, y); }
  slope(x, y) { return RoverTerrain.bilinear(this.slope20, this.r20, this.c20, this.px20, x, y); }
  contains(x, y) { return 0 <= x && x <= this.sizeM[0] && 0 <= y && y <= this.sizeM[1]; }
  /* (row from south, column) of the 20 m cell, clamped; numpy astype(int64) truncates toward zero */
  cell(x, y) { return [Math.min(Math.max(Math.trunc(y / this.px20), 0), this.r20 - 1), Math.min(Math.max(Math.trunc(x / this.px20), 0), this.c20 - 1)]; }
  /* roughness proxy per 20 m cell: std of the 5 m heights about their least-squares plane (row 0 = south) */
  roughness20() {
    if (this._rough) return this._rough;
    const k = Math.round(this.px20 / this.px5), R = Math.floor(this.r5 / k), C = Math.floor(this.c5 / k), out = new Float64Array(R * C);
    const u = Array.from({ length: k }, (_, a) => a - (k - 1) / 2), su2 = u.reduce((s, x) => s + x * x, 0) * k, b = new Float64Array(k * k);
    for (let J = 0; J < R; J++) for (let I = 0; I < C; I++) {
      let mean = 0, gy = 0, gx = 0;
      for (let a = 0; a < k; a++) for (let c = 0; c < k; c++) { const z = this.z5[(J * k + a) * this.c5 + I * k + c]; b[a * k + c] = z; mean += z; gy += z * u[a]; gx += z * u[c]; }
      mean /= k * k; gy /= su2; gx /= su2;
      let m2 = 0, m = 0; const res = new Float64Array(k * k);
      for (let a = 0; a < k; a++) for (let c = 0; c < k; c++) { const r = b[a * k + c] - (mean + gy * u[a] + gx * u[c]); res[a * k + c] = r; m += r; }
      m /= k * k; for (let q = 0; q < k * k; q++) m2 += (res[q] - m) ** 2;
      out[J * C + I] = Math.sqrt(m2 / (k * k));
    }
    return (this._rough = out);
  }
  /* install a precomputed mask (prepare-data writes shadow_<az>.bin: 1 bit per cell, row 0 = south, LSB first) */
  setShadowBits(azDeg, bits, elDeg = SUN_ELEVATION_DEG) {
    const n = this.r20 * this.c20, g = new Uint8Array(n); for (let i = 0; i < n; i++) g[i] = (bits[i >> 3] >> (i & 7)) & 1;
    this._shadow.set(`${pyRound(azDeg * 1000) / 1000}|${pyRound(elDeg * 1000) / 1000}`, g);
  }
  /* cast-shadow mask on the 20 m grid (row 0 = south) for one sun azimuth; port of terrain.cast_shadow on z20 */
  shadowGrid(azDeg, elDeg = SUN_ELEVATION_DEG, maxDistM = 20000.0) {
    const key = `${pyRound(azDeg * 1000) / 1000}|${pyRound(elDeg * 1000) / 1000}`;
    if (this._shadow.has(key)) return this._shadow.get(key);
    const rows = this.r20, cols = this.c20, z = this.z20, px = this.px20;       // z is south-up: north-up row r = rows-1-r
    const az = azDeg * Math.PI / 180, el = elDeg * Math.PI / 180, sx = Math.sin(az) * Math.cos(el), sy = Math.cos(az) * Math.cos(el), h = Math.hypot(sx, sy);
    const dx = sx / h, dy = sy / h, tanEl = Math.tan(el), n = Math.trunc(maxDistM / px);
    // Python marches on the north-up grid (row r north-up = row rows-1-r here); same offsets, written south-up directly
    const south = new Uint8Array(rows * cols);
    for (let k = 1; k <= n; k++) {
      const d = k * px, oc = pyRound(k * dx), orow = -pyRound(k * dy);
      if (Math.abs(oc) >= cols || Math.abs(orow) >= rows) break;
      const r0 = Math.max(0, -orow), r1 = Math.min(rows, rows - orow), c0 = Math.max(0, -oc), c1 = Math.min(cols, cols - oc), drop = d * d / (2 * MOON_RADIUS_M), rise = d * tanEl;
      for (let r = r0; r < r1; r++) {
        const dst = (rows - 1 - r) * cols, src = (rows - 1 - (r + orow)) * cols + oc;
        for (let c = c0; c < c1; c++) if (z[src + c] - drop > z[dst + c] + rise) south[dst + c] = 1;
      }
    }
    this._shadow.set(key, south); return south;
  }
}
