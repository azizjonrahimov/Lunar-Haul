// Port of lunarsim/rover/expert.py: A* on the 20 m slope + lighting cost grid and a pure-pursuit follower.
// Tie-breaking follows Python's heapq over (f, g, row, col) tuples, so the same route comes out.
import * as R from './physics.js';

const SQRT2 = Math.sqrt(2.0);
const NEIGH = [[-1, -1, SQRT2], [-1, 0, 1.0], [-1, 1, SQRT2], [0, -1, 1.0], [0, 1, 1.0], [1, -1, SQRT2], [1, 0, 1.0], [1, 1, SQRT2]];
const pmod = (a, b) => { const m = a % b; return (m !== 0 && (m < 0) !== (b < 0)) ? m + b : m; };

/* seconds per metre to cross each 20 m cell at 1 m/s nominal: 1 / (slope factor x shadow factor); Infinity = impassable */
export function costGrid(t, sunAz) {
  const n = t.r20 * t.c20, out = new Float64Array(n), sh = sunAz === null || sunAz === undefined || sunAz === R.NIGHT ? null : t.shadowGrid(+sunAz);
  for (let i = 0; i < n; i++) {
    let f = R.slopeSpeedFactor(t.slope20[i]);
    if (sunAz === R.NIGHT) f = f * R.SHADOW_SPEED_FACTOR; else if (sh && sh[i]) f = f * R.SHADOW_SPEED_FACTOR;
    out[i] = f > 0 ? 1.0 / Math.max(f, 1e-12) : Infinity;
  }
  return out;
}

class TupleHeap {   // min-heap ordered like Python tuples (f, g, r, c)
  constructor() { this.a = []; }
  static lt(x, y) { for (let i = 0; i < 4; i++) { if (x[i] < y[i]) return true; if (x[i] > y[i]) return false; } return false; }
  push(e) { const a = this.a; a.push(e); let i = a.length - 1; while (i > 0) { const p = (i - 1) >> 1; if (TupleHeap.lt(a[i], a[p])) { [a[i], a[p]] = [a[p], a[i]]; i = p; } else break; } }
  pop() { const a = this.a, top = a[0], last = a.pop(); if (a.length) { a[0] = last; let i = 0; for (;;) { const l = 2 * i + 1, r = l + 1; let m = i; if (l < a.length && TupleHeap.lt(a[l], a[m])) m = l; if (r < a.length && TupleHeap.lt(a[r], a[m])) m = r; if (m === i) break; [a[i], a[m]] = [a[m], a[i]]; i = m; } } return top; }
  get length() { return this.a.length; }
}

function astarBox(cost, rows, cols, start, goal, px, sunAz, r0, r1, c0, c1) {
  if (!(Number.isFinite(cost[start[0] * cols + start[1]]) && Number.isFinite(cost[goal[0] * cols + goal[1]]))) return null;
  let tack = null, up = null;
  if (sunAz !== null && sunAz !== undefined && sunAz !== R.NIGHT) {
    tack = 1.0 / Math.cos(R.UP_SUN_TACK_DEG * Math.PI / 180);
    up = NEIGH.map(([dr, dc]) => { const hd = pmod(Math.atan2(dc, dr) * 180 / Math.PI, 360), d = Math.abs(pmod(hd - +sunAz + 180, 360) - 180); return d <= R.UP_SUN_HALF_ANGLE_DEG; });
  }
  const W = c1 - c0, [gr, gc] = goal, best = new Map(), came = new Map();
  const sKey = (start[0] - r0) * W + (start[1] - c0); best.set(sKey, 0.0);
  const heap = new TupleHeap(); heap.push([px * Math.hypot(start[0] - gr, start[1] - gc), 0.0, start[0], start[1]]);
  while (heap.length) {
    const [, g, r, c] = heap.pop(); let key = (r - r0) * W + (c - c0);
    if (g > (best.has(key) ? best.get(key) : Infinity)) continue;
    if (r === gr && c === gc) {
      const path = [[r, c]]; while (came.has(key)) { key = came.get(key); path.push([Math.floor(key / W) + r0, key % W + c0]); }
      return path.reverse();
    }
    const cr = cost[r * cols + c];
    for (let k = 0; k < 8; k++) {
      const [dr, dc, stp] = NEIGH[k], nr = r + dr, nc = c + dc;
      if (nr < r0 || nr >= r1 || nc < c0 || nc >= c1) continue;
      const cn = cost[nr * cols + nc]; if (!Number.isFinite(cn)) continue;
      let w = px * stp * 0.5 * (cr + cn); if (tack !== null && up[k]) w *= tack;
      const ng = g + w, nkey = (nr - r0) * W + (nc - c0);
      if (ng < (best.has(nkey) ? best.get(nkey) : Infinity)) { best.set(nkey, ng); came.set(nkey, key); heap.push([ng + px * Math.hypot(nr - gr, nc - gc), ng, nr, nc]); }
    }
  }
  return null;
}
export function astar(cost, rows, cols, start, goal, px, sunAz, marginCells = 150) {
  for (const margin of [marginCells, marginCells * 3, Math.max(rows, cols)]) {
    const r0 = Math.max(0, Math.min(start[0], goal[0]) - margin), r1 = Math.min(rows, Math.max(start[0], goal[0]) + margin + 1);
    const c0 = Math.max(0, Math.min(start[1], goal[1]) - margin), c1 = Math.min(cols, Math.max(start[1], goal[1]) + margin + 1);
    const path = astarBox(cost, rows, cols, start, goal, px, sunAz, r0, r1, c0, c1);
    if (path !== null || (r0 === 0 && c0 === 0 && r1 === rows && c1 === cols)) return path;
  }
  return null;
}
/* route from a to b (local metres) as [[x, y], ...] of 20 m cell centres with the exact end points */
export function plan(t, a, b, sunAz) {
  const cost = costGrid(t, sunAz), [ja, ia] = t.cell(a[0], a[1]), [jb, ib] = t.cell(b[0], b[1]);
  const cells = astar(cost, t.r20, t.c20, [ja, ia], [jb, ib], t.px20, sunAz);
  if (cells === null) return null;
  const pts = cells.map(([r, c]) => [(c + 0.5) * t.px20, (r + 0.5) * t.px20]);
  pts[0] = [a[0], a[1]]; pts[pts.length - 1] = [b[0], b[1]];
  return pts;
}
/* resample a polyline at about step_m spacing, keeping the end points (numpy arithmetic order) */
export function densify(poly, stepM = 5.0) {
  const out = [[poly[0][0], poly[0][1]]];
  for (let s = 0; s + 1 < poly.length; s++) {
    const p = poly[s], q = poly[s + 1], dx = q[0] - p[0], dy = q[1] - p[1], L = Math.hypot(dx, dy), n = Math.max(1, Math.ceil(L / stepM));
    for (let k = 1; k <= n; k++) out.push([p[0] + dx * k / n, p[1] + dy * k / n]);
  }
  return out;
}

export class PurePursuit {
  constructor(path, lookaheadM = 5.0) {
    this.path = densify(path, 1.0);
    this.s = new Float64Array(this.path.length);
    for (let i = 1; i < this.path.length; i++) this.s[i] = this.s[i - 1] + Math.hypot(this.path[i][0] - this.path[i - 1][0], this.path[i][1] - this.path[i - 1][1]);
    this.lookahead = lookaheadM; this.k = 0;
  }
  closest(x, y, window = 200) {
    const lo = this.k, hi = Math.min(this.path.length, this.k + window); let bi = lo, bd = Infinity;
    for (let i = lo; i < hi; i++) { const d = Math.hypot(this.path[i][0] - x, this.path[i][1] - y); if (d < bd) { bd = d; bi = i; } }
    this.k = bi; return bi;
  }
  /* (steer-rate command, throttle) in [-1, 1]; also returns the pursuit target for drawing */
  action(state) {
    const k = this.closest(state.x, state.y), target = this.s[k] + this.lookahead;
    let lo = 0, hi = this.s.length; while (lo < hi) { const m = (lo + hi) >> 1; if (this.s[m] < target) lo = m + 1; else hi = m; }   // searchsorted (left)
    const j = Math.min(this.path.length - 1, lo), [tx, ty] = this.path[j];
    const bearing = Math.atan2(tx - state.x, ty - state.y), alpha = pmod(bearing - state.psi + Math.PI, 2 * Math.PI) - Math.PI;
    const ld = Math.max(1.0, Math.hypot(tx - state.x, ty - state.y)), dmax = R.ROVER.steer_max_deg * Math.PI / 180;
    let deltaCmd = Math.atan2(2.0 * R.ROVER.wheelbase_m * Math.sin(alpha), ld); deltaCmd = Math.max(-dmax, Math.min(dmax, deltaCmd));
    const rate = (deltaCmd - state.delta) / (R.ROVER.steer_rate_dps * Math.PI / 180), throttle = Math.abs(alpha) < 45 * Math.PI / 180 ? 1.0 : 0.3;
    this.target = [tx, ty];
    return [Math.max(-1.0, Math.min(1.0, rate)), throttle];
  }
  done(x, y, tolM = 10.0) { const e = this.path[this.path.length - 1]; return Math.hypot(e[0] - x, e[1] - y) <= tolM; }
}
