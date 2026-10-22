// Terrain assets v2 for /world/ and the stage's lunar terrain (B-34, data/terrain/connecting_ridge/v2/, staged to terrain/hero/v2/):
// - the 20 m normal map and the 5 m normal patches round BASE and PAD_A (frame x east, y north, z up -> scene
//   (nx, nz, -ny)), as RGBA8 textures in the existing shader's encoding;
// - the horizon map: 64 sectors of horizon elevation per 20 m post (16 RGBA16 files, 4 sectors each). Only the two
//   sectors either side of the sun's azimuth are on the GPU (one RG float texture, ~5 MB), so the sun can sit at any
//   azimuth without a re-bake; files load on demand and the last few stay decoded.
import { DataTexture, RGBAFormat, RGFormat, UnsignedByteType, FloatType, LinearFilter } from 'three';
import { decodePng } from './terrain.js';

const SECTOR_DEG = 5.625, KEEP_FILES = 3;

async function png(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return decodePng(await r.arrayBuffer());
}

// RGB8 normals (x east, y north, z up) -> RGBA8 in scene frame (x east, y up, z south) as the terrain shader expects
function normalTexture(p) {
  const n = p.width * p.height, out = new Uint8Array(n * 4);
  for (let i = 0; i < n; i++) {
    out[4 * i] = p.data[3 * i]; out[4 * i + 1] = p.data[3 * i + 2]; out[4 * i + 2] = 255 - p.data[3 * i + 1]; out[4 * i + 3] = 255;
  }
  const t = new DataTexture(out, p.width, p.height, RGBAFormat, UnsignedByteType);
  t.magFilter = t.minFilter = LinearFilter; t.needsUpdate = true;
  return t;
}

export async function loadTerrainV2(base) {
  const manifest = await (await fetch(base + 'manifest.json')).json();
  if (manifest.format !== 'lunarsim-terrain-assets' || manifest.version !== 1) throw new Error('terrain v2: unexpected manifest');
  const files = manifest.files, byRole = r => files.filter(f => f.role === r);
  const n20 = byRole('normals').find(f => f.px_m === 20);
  const patches = await Promise.all(byRole('normals').filter(f => f.site).map(async f => ({ site: f.site, bounds: f.bounds_m, tex: normalTexture(await png(base + f.file)),
    height: byRole('height').find(g => g.site === f.site) || null })));
  const normal = normalTexture(await png(base + n20.file));
  const hz = byRole('horizon').sort((a, b) => a.sectors[0] - b.sectors[0]);
  const enc = hz[0].encoding.value;   // "angle_deg = 0.05 * v - 90; v = 0 means no terrain in the tile"
  const step = +(/=\s*([\d.]+)\s*\*\s*v/.exec(enc) || [0, 0.05])[1], off = +(/v\s*-\s*([\d.]+)/.exec(enc) || [0, 90])[1];
  const W = hz[0].shape[1], H = hz[0].shape[0];
  const decoded = new Map(), pending = new Map();
  const fileOf = k => hz.find(f => f.sectors.includes(k));
  async function file(f) {
    if (decoded.has(f.file)) { const d = decoded.get(f.file); decoded.delete(f.file); decoded.set(f.file, d); return d; }   // LRU touch
    if (!pending.has(f.file)) pending.set(f.file, png(base + f.file).then(p => { pending.delete(f.file); decoded.set(f.file, p.data); while (decoded.size > KEEP_FILES) decoded.delete(decoded.keys().next().value); return p.data; }));
    return pending.get(f.file);
  }
  const data = new Float32Array(W * H * 2), tex = new DataTexture(data, W, H, RGFormat, FloatType);
  tex.magFilter = tex.minFilter = LinearFilter;   // float linear filtering: OES_texture_float_linear (desktop GPUs); the page checks
  let loaded = null, want = null;
  return {
    manifest, normal, patches, tex, step, offset: off,
    sectorsFor(az) { const a = ((az % 360) + 360) % 360, k0 = Math.floor(a / SECTOR_DEG) % 64; return { k0, k1: (k0 + 1) % 64, w: (a - k0 * SECTOR_DEG) / SECTOR_DEG }; },
    get loaded() { return loaded; },
    // put sectors k0, k1 on the GPU (degrees; -90 where the ray left the tile: no terrain, so lit)
    async load(k0, k1) {
      const key = `${k0},${k1}`; if (loaded === key) return true;
      want = key;
      const [a, b] = await Promise.all([file(fileOf(k0)), file(fileOf(k1))]), ca = k0 % 4, cb = k1 % 4;
      if (want !== key) return false;   // the sun moved on while these files loaded
      for (let i = 0, n = W * H; i < n; i++) { data[2 * i] = step * a[4 * i + ca] - off; data[2 * i + 1] = step * b[4 * i + cb] - off; }
      tex.needsUpdate = true; loaded = key; return true;
    },
  };
}

// Horizon elevation (degrees) all round a viewpoint, from the 20 m heights: n azimuths (grid: 0 = +y north, 90 = +x
// east), the eye eyeM above the ground, Moon curvature included. The ray schedule follows B-34's horizon map (20 m
// steps to 4 km, then 0.5 % longer each step) and, like it, stops at the 16 km tile edge. ~10 ms for 360 rays.
export function horizonProfile(terrain, x, y, { eyeM = 1.5, n = 360, moonR = 1737400 } = {}) {
  const out = new Float32Array(n), [W, H] = terrain.sizeM, z0 = terrain.height(x, y) + eyeM;
  for (let k = 0; k < n; k++) {
    const a = k / n * 2 * Math.PI, dx = Math.sin(a), dy = Math.cos(a);
    let d = 20, best = -90;
    while (true) {
      const px = x + dx * d, py = y + dy * d;
      if (px < 0 || py < 0 || px > W || py > H) break;
      const ang = Math.atan2(terrain.height(px, py) - z0 - d * d / (2 * moonR), d) * 180 / Math.PI;
      if (ang > best) best = ang;
      d = d < 4000 ? d + 20 : d * 1.005;
    }
    out[k] = best;
  }
  return out;
}
