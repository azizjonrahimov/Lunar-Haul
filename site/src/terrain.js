// lunarsim-terrain v1 reader for the browser (PLAN 5.1): meta.json + a uint16 greyscale PNG heightmap.
// <img>/canvas decoding drops PNGs to 8 bits per channel, so the PNG is decoded here (zlib via DecompressionStream).
// Coordinates: local metres, x east from the tile's west edge, y north from its south edge. Row 0 of the image is north.

const PNG_SIG = [137, 80, 78, 71, 13, 10, 26, 10];

async function inflate(bytes) {
  const ds = new DecompressionStream('deflate');  // 'deflate' = zlib-wrapped, which is what PNG IDAT holds
  const buf = await new Response(new Blob([bytes]).stream().pipeThrough(ds)).arrayBuffer();
  return new Uint8Array(buf);
}

/* decodePng16(ArrayBuffer) -> {width, height, data: Uint16Array}. Greyscale (colour type 0), 16-bit, not interlaced. */
export async function decodePng16(buffer) {
  const b = new Uint8Array(buffer), dv = new DataView(buffer);
  if (!PNG_SIG.every((v, i) => b[i] === v)) throw new Error('not a PNG file');
  let off = 8, width = 0, height = 0, depth = 0, ctype = 0, interlace = 0; const idat = [];
  while (off < b.length) {
    const len = dv.getUint32(off), type = String.fromCharCode(b[off + 4], b[off + 5], b[off + 6], b[off + 7]), body = off + 8;
    if (type === 'IHDR') { width = dv.getUint32(body); height = dv.getUint32(body + 4); depth = b[body + 8]; ctype = b[body + 9]; interlace = b[body + 12]; }
    else if (type === 'IDAT') idat.push(b.subarray(body, body + len));
    else if (type === 'IEND') break;
    off = body + len + 4;  // + CRC
  }
  if (depth !== 16 || ctype !== 0) throw new Error(`heightmap must be 16-bit greyscale PNG (got depth ${depth}, colour type ${ctype})`);
  if (interlace) throw new Error('interlaced PNG heightmaps are not supported');
  const total = idat.reduce((s, x) => s + x.length, 0), z = new Uint8Array(total); let p = 0; for (const c of idat) { z.set(c, p); p += c.length; }
  const raw = await inflate(z), bpp = 2, stride = width * bpp;
  if (raw.length < height * (stride + 1)) throw new Error('PNG data is truncated');
  const out = new Uint16Array(width * height), prev = new Uint8Array(stride), cur = new Uint8Array(stride);
  for (let y = 0; y < height; y++) {
    const ft = raw[y * (stride + 1)], row = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    for (let i = 0; i < stride; i++) {
      const a = i >= bpp ? cur[i - bpp] : 0, up = prev[i], c = i >= bpp ? prev[i - bpp] : 0; let v = row[i];
      if (ft === 1) v += a; else if (ft === 2) v += up; else if (ft === 3) v += (a + up) >> 1;
      else if (ft === 4) { const pp = a + up - c, pa = Math.abs(pp - a), pb = Math.abs(pp - up), pc = Math.abs(pp - c); v += (pa <= pb && pa <= pc) ? a : (pb <= pc ? up : c); }
      else if (ft !== 0) throw new Error(`bad PNG filter ${ft} on row ${y}`);
      cur[i] = v & 255;
    }
    for (let x = 0; x < width; x++) out[y * width + x] = (cur[2 * x] << 8) | cur[2 * x + 1];  // big-endian samples
    prev.set(cur);
  }
  return { width, height, data: out };
}

export class Terrain {
  constructor(meta, png) {
    if (meta.format !== 'lunarsim-terrain') throw new Error(`not a lunarsim-terrain meta.json (format ${meta.format})`);
    const { offset_m, scale_m_per_unit } = meta.z_encoding;
    this.meta = meta; this.cols = png.width; this.rows = png.height;
    this.sizeM = meta.size_m; this.postM = this.sizeM[0] / this.cols;
    this.heights = new Float32Array(png.data.length);
    let lo = Infinity, hi = -Infinity;
    for (let i = 0; i < png.data.length; i++) { const z = offset_m + scale_m_per_unit * png.data[i]; this.heights[i] = z; if (z < lo) lo = z; if (z > hi) hi = z; }
    this.zMin = lo; this.zMax = hi;
  }
  /* height at grid post (col, row), clamped */
  at(c, r) { c = Math.min(this.cols - 1, Math.max(0, c)); r = Math.min(this.rows - 1, Math.max(0, r)); return this.heights[r * this.cols + c]; }
  /* bilinear height at local metres (x east, y north) */
  height(x, y) {
    const fc = x / this.postM - 0.5, fr = (this.sizeM[1] - y) / this.postM - 0.5;
    const c0 = Math.floor(fc), r0 = Math.floor(fr), tx = fc - c0, ty = fr - r0;
    return (this.at(c0, r0) * (1 - tx) + this.at(c0 + 1, r0) * tx) * (1 - ty) + (this.at(c0, r0 + 1) * (1 - tx) + this.at(c0 + 1, r0 + 1) * tx) * ty;
  }
  /* slope in degrees at local metres (central differences over one post) */
  slope(x, y) {
    const d = this.postM, gx = (this.height(x + d, y) - this.height(x - d, y)) / (2 * d), gy = (this.height(x, y + d) - this.height(x, y - d)) / (2 * d);
    return Math.atan(Math.hypot(gx, gy)) * 180 / Math.PI;
  }
}

/* loadTerrain('terrain/hero/') -> Terrain; the folder holds meta.json and the height layer (default height_20m.png) */
export async function loadTerrain(folder, layer = 'height_20m') {
  const base = folder.endsWith('/') ? folder : folder + '/';
  const mres = await fetch(base + 'meta.json'); if (!mres.ok) throw new Error(`terrain meta.json: HTTP ${mres.status}`);
  const meta = await mres.json();
  const file = (meta.layers && meta.layers[layer] && meta.layers[layer].file) || `${layer}.png`;
  const pres = await fetch(base + file); if (!pres.ok) throw new Error(`terrain ${file}: HTTP ${pres.status}`);
  return new Terrain(meta, await decodePng16(await pres.arrayBuffer()));
}
