// Reader for scene packages (lunarsim-scene v1, B-31: data/scenes/<id>/ and the run queue's runs/<id>/scene/): the
// index (scene.json), routes.bin and one chunk per 30 days, all little-endian float32 at the offsets the index gives.
// Mirrors lunarsim.scene.read / position: a vehicle is a gap-free timeline of segments; a stationary segment sits at
// (x0, y0, z0); a drive follows route `route` from fraction f0 to f1 with f linear in time, position = the route
// interpolated at f (np.interp on the f column); route -1 is a straight line from (x0, y0, z0) to (x1, y1, z1).
// Chunks load on demand and stay cached. No three.js, so Node tests can use it. Frame: the terrain pack's local frame
// (x east, y north, metres from the tile's south-west corner; z = LOLA height); heading: grid azimuth, 0 = +y.
export const SCENE_FORMAT = 'lunarsim-scene', SCENE_VERSION = 1;
const LE = new Uint8Array(new Uint16Array([1]).buffer)[0] === 1;

function f32(buf, byteOffset, count) {
  if (LE && byteOffset % 4 === 0) return new Float32Array(buf, byteOffset, count);
  const dv = new DataView(buf, byteOffset, count * 4), out = new Float32Array(count);
  for (let i = 0; i < count; i++) out[i] = dv.getFloat32(4 * i, true);
  return out;
}

// np.interp(x, xp, fp) on a route block (rows x, y, z, f): x clamped to the ends
function interp(block, n, f, col) {
  if (f <= block[3]) return block[col];
  if (f >= block[4 * (n - 1) + 3]) return block[4 * (n - 1) + col];
  let lo = 0, hi = n - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (block[4 * m + 3] <= f) lo = m; else hi = m; }
  const x0 = block[4 * lo + 3], x1 = block[4 * hi + 3], a = block[4 * lo + col], b = block[4 * hi + col];
  return x1 > x0 ? a + (b - a) * (f - x0) / (x1 - x0) : a;
}

/* loadScene(base, {fetchFn}) -> scene; base ends with '/' (e.g. BASE + 'scenes/P2/') */
// F-50: a drive's distance fraction at time fraction g with a trapezoid speed profile: it speeds up over the first a of the
// drive and slows over the last a (a <= 0.5), so it never starts or stops at full speed and still arrives on time
export function easeLeg(g, a) {
  if (!(a > 0)) return g;
  const vp = 1 / (1 - a);
  return g < a ? vp * g * g / (2 * a) : g > 1 - a ? 1 - vp * (1 - g) * (1 - g) / (2 * a) : vp * (g - a / 2);
}

export async function loadScene(base, { fetchFn = fetch } = {}) {
  const get = async (file, how) => { const r = await fetchFn(base + file); if (!r.ok) throw new Error(`${base + file}: HTTP ${r.status}`); return r[how](); };
  const index = await get('scene.json', 'json');
  if (index.format !== SCENE_FORMAT || index.version !== SCENE_VERSION) throw new Error(`not a ${SCENE_FORMAT} v${SCENE_VERSION} package`);
  const rb = await get(index.routes.file, 'arrayBuffer');
  const routes = index.routes.items.map(m => ({ ...m, block: f32(rb, m.offset, 4 * m.n) }));
  const C = Object.fromEntries(index.segment_columns.map((c, i) => [c, i])), H = Object.fromEntries(index.hourly_columns.map((c, i) => [c, i]));
  const nCol = index.segment_columns.length, cache = new Map();

  // chunk k: {t0, t1, seg (rows x cols), rows, hourly, hRows, firstHour, byVeh: Map(veh -> row indices)}
  function chunk(k) {
    if (!cache.has(k)) cache.set(k, get(index.chunks[k].file, 'arrayBuffer').then(buf => {
      const c = index.chunks[k], s = c.segments, h = c.hourly;
      const seg = f32(buf, s.offset, s.rows * s.cols), hourly = f32(buf, h.offset, h.rows * h.cols), byVeh = new Map();
      for (let r = 0; r < s.rows; r++) { const v = seg[r * nCol + C.veh]; if (!byVeh.has(v)) byVeh.set(v, []); byVeh.get(v).push(r); }
      return { t0: c.t0, t1: c.t1, seg, rows: s.rows, hourly, hRows: h.rows, hCols: h.cols, firstHour: h.first_hour, byVeh };
    }));
    return cache.get(k);
  }
  const chunkIndex = t => { const cs = index.chunks; for (let k = 0; k < cs.length; k++) if (t >= cs[k].t0 && t < cs[k].t1) return k; return t < 0 ? 0 : cs.length - 1; };

  // the segment row of vehicle veh at time t in a loaded chunk (t0 <= t < t1), or -1
  function segmentRow(ch, veh, t) {
    for (const r of ch.byVeh.get(veh) || []) { const o = r * nCol; if (ch.seg[o + C.t0] <= t && ch.seg[o + C.t1] > t) return r; }
    return -1;
  }
  const routeHeading = (b, n, f) => {
    let k = 0; while (k < n - 2 && b[4 * (k + 1) + 3] <= f) k++;
    const dx = b[4 * (k + 1)] - b[4 * k], dy = b[4 * (k + 1) + 1] - b[4 * k + 1];
    return ((Math.atan2(dx, dy) * 180 / Math.PI) % 360 + 360) % 360;
  };

  return {
    index, routes, columns: C, hourlyColumns: H, horizon: index.horizon_h, chunk, chunkIndex,
    // load what time t needs (and the next chunk, so playback does not stall)
    async ready(t) { const k = chunkIndex(t); await chunk(k); if (k + 1 < index.chunks.length) chunk(k + 1); return k; },
    /* position(ch, veh, t, {ease, turnM}) -> {x, y, z, state, heading, load, job, driving, route} from a loaded chunk; null if no
       segment. Display options (F-50; the defaults give lunarsim.scene.position exactly): ease (h) eases each drive in and
       out over that long (at most a quarter of the drive at each end; drives never run back to back in a package);
       turnM (m) takes the heading between the route points turnM behind and ahead, so a turn spreads over 2 turnM of road. */
    position(ch, veh, t, { ease = 0, turnM = 0 } = {}) {
      const r = segmentRow(ch, veh, t); if (r < 0) return null;
      const s = ch.seg, o = r * nCol, t0 = s[o + C.t0], t1 = s[o + C.t1], ri = s[o + C.route];
      let g = (t - t0) / Math.max(t1 - t0, 1e-12);
      if (ease > 0 && (ri >= 0 ? s[o + C.f1] !== s[o + C.f0] : s[o + C.x1] !== s[o + C.x0] || s[o + C.y1] !== s[o + C.y0])) g = easeLeg(g, Math.min(0.25, ease / Math.max(t1 - t0, 1e-12)));
      const out = { state: index.states[s[o + C.state]], load: s[o + C.load_kg], job: s[o + C.job], heading: s[o + C.heading_deg], driving: false, route: ri, x: 0, y: 0, z: 0 };
      if (ri >= 0) {
        const R = routes[ri], f = s[o + C.f0] + (s[o + C.f1] - s[o + C.f0]) * g;
        out.x = interp(R.block, R.n, f, 0); out.y = interp(R.block, R.n, f, 1); out.z = interp(R.block, R.n, f, 2);
        out.heading = routeHeading(R.block, R.n, f); out.driving = s[o + C.f1] !== s[o + C.f0];
        if (turnM > 0 && out.driving && R.length_m > 0) {
          const df = turnM / R.length_m * Math.sign(s[o + C.f1] - s[o + C.f0]), dx = interp(R.block, R.n, f + df, 0) - interp(R.block, R.n, f - df, 0), dy = interp(R.block, R.n, f + df, 1) - interp(R.block, R.n, f - df, 1);
          if (dx || dy) out.heading = ((Math.atan2(dx, dy) * 180 / Math.PI) % 360 + 360) % 360;
        }
      } else {
        out.x = s[o + C.x0] + (s[o + C.x1] - s[o + C.x0]) * g; out.y = s[o + C.y0] + (s[o + C.y1] - s[o + C.y0]) * g; out.z = s[o + C.z0] + (s[o + C.z1] - s[o + C.z0]) * g;
        out.driving = s[o + C.x1] !== s[o + C.x0] || s[o + C.y1] !== s[o + C.y0];
      }
      return out;
    },
    /* hourly(ch, t) -> {sun_az_deg, night, earth_el_deg, earth_radius_deg, earth_bearing_deg, waiting: {site: {items, kg}}} */
    hourly(ch, t) {
      const i = Math.max(0, Math.min(ch.hRows - 1, Math.floor(t - ch.firstHour))), row = j => ch.hourly[i * ch.hCols + j], out = { waiting: {} };
      for (const [k, j] of Object.entries(H)) {
        const m = /^waiting_(n|kg)_(.+)$/.exec(k);
        if (m) (out.waiting[m[2]] ??= { items: 0, kg: 0 })[m[1] === 'n' ? 'items' : 'kg'] = row(j); else out[k] = row(j);
      }
      return out;
    },
  };
}
