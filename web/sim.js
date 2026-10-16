'use strict';
/* =========================================================================
   LunarSim engine (browser port of the Python package `lunarsim`).
   This file has no DOM dependencies: it runs on the main thread and inside
   web/worker.js. Mirrors lunarsim/world.py, entities.py, scenario.py,
   engine.py, dispatch.py, assign.py and vv.py in the research repository.
   ========================================================================= */
// ---------- RNG: sfc32 seeded by seed; uniform, exponential, poisson, choice ----------
function makeRng(seed) {
  let a = 0x9E3779B9 ^ seed, b = 0x243F6A88 ^ (seed * 7919), c = 0xB7E15162 ^ (seed * 104729), d = 1 + (seed >>> 0);
  function next() {
    a >>>= 0; b >>>= 0; c >>>= 0; d >>>= 0;
    let t = (a + b) | 0; a = b ^ (b >>> 9); b = (c + (c << 3)) | 0; c = (c << 21) | (c >>> 11); d = (d + 1) | 0; t = (t + d) | 0; c = (c + t) | 0;
    return (t >>> 0) / 4294967296;
  }
  for (let i = 0; i < 20; i++) next();
  const rng = {
    random: next,
    uniform: (lo, hi) => lo + (hi - lo) * next(),
    exponential: (mean) => -Math.log(1 - next()) * mean,
    poisson: (lam) => { if (lam <= 0) return 0; if (lam > 60) { const n = Math.round(lam + Math.sqrt(lam) * rng.normal()); return Math.max(0, n); } let L = Math.exp(-lam), k = 0, p = 1; do { k++; p *= next(); } while (p > L); return k - 1; },
    normal: () => { const u = 1 - next(), v = next(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); },
    choice: (arr) => arr[Math.min(arr.length - 1, Math.floor(next() * arr.length))],
    weighted: (keys, weights) => { const s = weights.reduce((x, y) => x + y, 0); let r = next() * s; for (let i = 0; i < keys.length; i++) { r -= weights[i]; if (r <= 0) return keys[i]; } return keys[keys.length - 1]; },
  };
  return rng;
}

// ---------- World ----------
const SLOPE = { flat: [1.0, 1.0], moderate: [0.75, 1.35], steep: [0.5, 1.9] };
const SITES = [
  { name: 'PAD_A', x: 0.0, y: 0.0, kind: 'pad' }, { name: 'PAD_B', x: 1.2, y: -0.9, kind: 'pad' },
  { name: 'DEPOT', x: 1.1, y: 0.7, kind: 'depot' }, { name: 'BASE', x: 1.4, y: 1.0, kind: 'base' },
  { name: 'POWER', x: 1.9, y: 1.6, kind: 'power' }, { name: 'CONSTR', x: 1.0, y: 1.5, kind: 'construction' },
  { name: 'ISRU', x: 2.6, y: 0.9, kind: 'isru' }, { name: 'SCI_1', x: 3.2, y: 2.3, kind: 'science' }, { name: 'PSR', x: 4.6, y: 3.0, kind: 'psr' },
];
const EDGES = [['PAD_A', 'DEPOT', 'flat'], ['PAD_B', 'DEPOT', 'moderate'], ['PAD_A', 'PAD_B', 'flat'], ['DEPOT', 'BASE', 'flat'], ['BASE', 'POWER', 'moderate'],
  ['BASE', 'CONSTR', 'flat'], ['DEPOT', 'ISRU', 'moderate'], ['BASE', 'ISRU', 'moderate'], ['POWER', 'SCI_1', 'steep'], ['ISRU', 'SCI_1', 'moderate'],
  ['SCI_1', 'PSR', 'steep'], ['ISRU', 'PSR', 'steep']];
class World {
  constructor(tort = 1.3) {
    this.sites = {}; SITES.forEach(s => this.sites[s.name] = s); this.names = SITES.map(s => s.name);
    this.edges = {};
    for (const [a, b, sl] of EDGES) { const d = this.euclid(a, b) * tort; const [sp, en] = SLOPE[sl]; const e = { dist: d, slope: sl, speedMult: sp, energyMult: en, timeCost: d / sp }; this.edges[a + '|' + b] = e; this.edges[b + '|' + a] = e; }
    this.pads = SITES.filter(s => s.kind === 'pad').map(s => s.name);
    this.cache = {}; this.paths = {}; this.allPairs();
  }
  euclid(a, b) { const s = this.sites[a], t = this.sites[b]; return Math.hypot(s.x - t.x, s.y - t.y); }
  allPairs() {
    const n = this.names.length, idx = {}; this.names.forEach((nm, i) => idx[nm] = i);
    const cost = Array.from({ length: n }, () => Array(n).fill(Infinity)), nxt = Array.from({ length: n }, () => Array(n).fill(-1));
    for (let i = 0; i < n; i++) { cost[i][i] = 0; nxt[i][i] = i; }
    for (const key in this.edges) { const [a, b] = key.split('|'); const e = this.edges[key]; const i = idx[a], j = idx[b]; if (e.timeCost < cost[i][j]) { cost[i][j] = e.timeCost; nxt[i][j] = j; } }
    for (let k = 0; k < n; k++) for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) { const c = cost[i][k] + cost[k][j]; if (c < cost[i][j]) { cost[i][j] = c; nxt[i][j] = nxt[i][k]; } }
    for (const a of this.names) for (const b of this.names) {
      const i = idx[a], j = idx[b]; const path = [a]; let cur = i; while (cur !== j) { cur = nxt[cur][j]; path.push(this.names[cur]); }
      let dist = 0, eq = 0, en = 0; for (let k = 0; k + 1 < path.length; k++) { const e = this.edges[path[k] + '|' + path[k + 1]]; dist += e.dist; eq += e.timeCost; en += e.dist * e.energyMult; }
      this.cache[a + '|' + b] = [dist, eq, en]; this.paths[a + '|' + b] = path;
    }
  }
  distance(a, b) { return this.cache[a + '|' + b][0]; }
  equivFlat(a, b) { return this.cache[a + '|' + b][1]; }
  energyKm(a, b) { return this.cache[a + '|' + b][2]; }
  path(a, b) { return this.paths[a + '|' + b]; }
}
const WORLD = new World();

// ---------- Vehicle classes, landers, cargo classes ----------
const VCLASS = {
  LTV: { name: 'LTV', cap: 1500, speed: 6.0, emptyMult: 1.2, whKm: 350, battery: 40000, chargeKw: 5, nightOps: false, team: true, costM: 450, lifeH: 10 * 8760 * 0.25, lifeYr: 10, mtbf: 500, mttr: 24, loadH: 0.5, unloadH: 0.5 },
  HAUL: { name: 'HAUL', cap: 10000, speed: 4.0, emptyMult: 1.2, whKm: 900, battery: 120000, chargeKw: 10, nightOps: true, team: true, costM: 600, lifeH: 10 * 8760 * 0.25, lifeYr: 10, mtbf: 400, mttr: 36, loadH: 1.5, unloadH: 1.5 },
  MICRO: { name: 'MICRO', cap: 300, speed: 3.0, emptyMult: 1.3, whKm: 120, battery: 8000, chargeKw: 1, nightOps: false, team: false, costM: 60, lifeH: 5 * 8760 * 0.25, lifeYr: 5, mtbf: 300, mttr: 12, loadH: 0.3, unloadH: 0.3 },
};
const LANDERS = { CLPS: { name: 'CLPS', payload: [100, 500], offload: [6, 24], maxItem: 500 }, MK1: { name: 'MK1', payload: [2000, 3000], offload: [12, 36], maxItem: 2000 }, LARGE: { name: 'LARGE', payload: [12000, 30000], offload: [24, 72], maxItem: 15000 } };
const CARGO_CLASSES = [
  ['consumables', [60, 400], { BASE: 0.8, DEPOT: 0.2 }, 1, 0.34], ['science', [10, 150], { SCI_1: 0.5, PSR: 0.3, BASE: 0.2 }, 2, 0.20],
  ['equipment', [300, 2000], { CONSTR: 0.4, ISRU: 0.3, POWER: 0.2, BASE: 0.1 }, 2, 0.26], ['infrastructure', [2000, 6000], { POWER: 0.4, ISRU: 0.3, CONSTR: 0.3 }, 2, 0.14],
  ['element', [6000, 15000], { BASE: 0.6, POWER: 0.4 }, 3, 0.06]];
const HOURS_PER_DAY = 24, CYCLE = 29.53 * 24, RETURN_PROB = 0.30, RETURN_LAG = [5 * 24, 30 * 24];
const TELEOP_TABLE = [[0, 3.24], [4, 2.56], [6, 2.03], [8, 1.76]], TELEOP_K = 0.10, AUTO_REF = 6.0, SUPERVISED_MULT = 0.9, TELEOP_HANDLING_K = 0.25;
const WEAR_SHARE = 0.5, TEAM_SPEED = 0.5, TEAM_SETUP = 1.0;
const OWNERS = ['NASA', 'NASA', 'NASA', 'NASA', 'CoA', 'CoA', 'CoB', 'CoC'];
const PHASES = {
  P1: { landings: { CLPS: 4, MK1: 1, LARGE: 0 }, bulk: [['CONSTR', 'BASE', 30, 500]], nOps: 2 },
  P2: { landings: { CLPS: 4, MK1: 3, LARGE: 1 }, bulk: [['CONSTR', 'BASE', 300, 1000], ['CONSTR', 'ISRU', 200, 1000]], nOps: 3 },
  P3: { landings: { CLPS: 4, MK1: 4, LARGE: 3 }, bulk: [['CONSTR', 'BASE', 800, 1000], ['CONSTR', 'ISRU', 600, 1000], ['PSR', 'ISRU', 100, 500, 2]], nOps: 4 },
};
const LTV = (o, a = 'supervised') => ({ owner: o, cls: 'LTV', autonomy: a, std: 'A' });
const HAUL = (o, a = 'supervised') => ({ owner: o, cls: 'HAUL', autonomy: a, std: 'A' });
const MICRO = (o, a = 'teleop') => ({ owner: o, cls: 'MICRO', autonomy: a, std: 'A' });
const PRESETS = {
  2: [LTV('NASA'), LTV('CoA')], 3: [LTV('NASA'), LTV('CoA'), MICRO('CoB')], 4: [LTV('NASA'), LTV('CoA'), HAUL('CoA'), MICRO('CoB')],
  5: [LTV('NASA'), LTV('NASA'), LTV('CoA'), HAUL('CoA'), MICRO('CoB')], 6: [LTV('NASA'), LTV('NASA'), LTV('CoA'), HAUL('CoA'), MICRO('CoB'), LTV('CoC', 'teleop')],
  8: [LTV('NASA'), LTV('NASA'), LTV('CoA'), HAUL('CoA'), MICRO('CoB'), LTV('CoC', 'teleop'), LTV('CoB', 'autonomous'), HAUL('CoC', 'autonomous')],
  9: [LTV('NASA'), LTV('NASA'), HAUL('NASA', 'autonomous'), LTV('CoA'), HAUL('CoA'), MICRO('CoB'), LTV('CoB', 'autonomous'), LTV('CoC', 'teleop'), HAUL('CoC', 'autonomous')],
};
function teleopSpeed(rtt) {
  const xs = TELEOP_TABLE.map(p => p[0]), ys = TELEOP_TABLE.map(p => p[1]);
  if (rtt <= xs[xs.length - 1]) { for (let i = 0; i + 1 < xs.length; i++) if (rtt <= xs[i + 1]) { const f = (rtt - xs[i]) / (xs[i + 1] - xs[i]); return ys[i] + f * (ys[i + 1] - ys[i]); } return ys[0]; }
  return ys[ys.length - 1] * (1 + TELEOP_K * xs[xs.length - 1]) / (1 + TELEOP_K * rtt);
}

// ---------- Binary heap of events ----------
class Heap { constructor() { this.a = []; this.seq = 0; } push(t, kind, payload) { const e = { t, s: this.seq++, kind, payload }; const a = this.a; a.push(e); let i = a.length - 1; while (i > 0) { const p = (i - 1) >> 1; if (this.lt(a[i], a[p])) { [a[i], a[p]] = [a[p], a[i]]; i = p; } else break; } }
  lt(x, y) { return x.t < y.t || (x.t === y.t && x.s < y.s); }
  pop() { const a = this.a; if (!a.length) return null; const top = a[0], last = a.pop(); if (a.length) { a[0] = last; let i = 0; for (;;) { const l = 2 * i + 1, r = l + 1; let m = i; if (l < a.length && this.lt(a[l], a[m])) m = l; if (r < a.length && this.lt(a[r], a[m])) m = r; if (m === i) break; [a[i], a[m]] = [a[m], a[i]]; i = m; } } return top; }
  get length() { return this.a.length; } }

// ---------- Hungarian (shortest augmenting path), port of lunarsim/assign.py ----------
function hungarian(cost) {
  let n = cost.length, m = n ? cost[0].length : 0, transposed = false;
  if (n > m) { cost = cost[0].map((_, j) => cost.map(r => r[j])); [n, m] = [m, n]; transposed = true; }
  const INF = Infinity, u = Array(n + 1).fill(0), v = Array(m + 1).fill(0), p = Array(m + 1).fill(0), way = Array(m + 1).fill(0);
  for (let i = 1; i <= n; i++) { p[0] = i; let j0 = 0; const minv = Array(m + 1).fill(INF), used = Array(m + 1).fill(false);
    for (;;) { used[j0] = true; const i0 = p[j0]; let delta = INF, j1 = 0;
      for (let j = 1; j <= m; j++) if (!used[j]) { const cur = cost[i0 - 1][j - 1] - u[i0] - v[j]; if (cur < minv[j]) { minv[j] = cur; way[j] = j0; } if (minv[j] < delta) { delta = minv[j]; j1 = j; } }
      for (let j = 0; j <= m; j++) { if (used[j]) { u[p[j]] += delta; v[j] -= delta; } else minv[j] -= delta; }
      j0 = j1; if (p[j0] === 0) break; }
    for (;;) { const j1 = way[j0]; p[j0] = p[j1]; j0 = j1; if (j0 === 0) break; } }
  const rows = [], cols = []; for (let j = 1; j <= m; j++) if (p[j] !== 0) { rows.push(p[j] - 1); cols.push(j - 1); }
  return transposed ? [cols, rows] : [rows, cols];
}

// ---------- Scenario ----------
function makeScenario(opts) {
  const ph = PHASES[opts.phase];
  const bulkScale = opts.bulkT / Math.max(1e-9, ph.bulk.reduce((s, b) => s + b[2], 0));
  return {
    horizon: 365 * 24, landings: ph.landings, owners: OWNERS,
    bulk: opts.bulkT > 0 ? ph.bulk.map(b => ({ origin: b[0], dest: b[1], tpy: b[2] * bulkScale, lot: b[3], owner: 'NASA', prio: b[4] || 3 })) : [],
    fleet: opts.fleet, night: opts.night, nightSpeed: 0.6, rtt: opts.rtt, nOps: opts.nOps, fanout: 4, failures: true, mtbfMult: opts.mtbf,
    duty: opts.duty, dutyBlock: 48, commonStd: opts.std, opCost: 1000, urgency: 2000, vot: { 1: 5000, 2: 1000, 3: 100 },
  };
}

// ---------- Simulation (port of engine.py) ----------
class Simulation {
  constructor(sc, mechanism, seed, mopts = {}) {
    this.sc = sc; this.world = WORLD; this.rng = makeRng(seed); this.rngOps = makeRng(seed + 100003); this.mech = mechanism; this.mopts = mopts;
    this.t = 0; this.events = new Heap(); this.waiting = []; this.pending = []; this.allCargo = []; this.vehicles = []; this.opJobs = []; this.carrierOf = {}; this.cid = 0;
    this.trace = mopts.trace ? [] : null; this.landingSchedule = []; this.repositions = 0; this.kmRepos = 0;
    this.m = { landed: 0, ready: 0, delivered: 0, deliveredItems: 0, bulk: 0, stranded: 0, strandedItems: 0, backlog: 0, delays: [], dprio: [], dcls: [], dmass: [], km: 0, kmEmpty: 0, energy: 0, busy: 0, opHours: 0, faults: 0, nightStr: 0, teamLifts: 0, bundled: 0, backhaulKg: 0, jobs: 0, revenue: {}, fleetCost: 0, opCost: 0, unmetOps: 0 };
    this.buildFleet(); this.scheduleDemand(); this.batch = mopts.batch_h || 0; if (this.batch > 0) this.events.push(this.batch, 'TICK', null);
  }
  buildFleet() {
    const owners = [];
    this.sc.fleet.forEach((f, i) => { const cls = VCLASS[f.cls]; const v = { id: i, owner: f.owner, cls, location: 'DEPOT', standards: new Set(f.std.split('|')), autonomy: f.autonomy, busyUntil: 0, battery: cls.battery, kmTotal: 0, kmEmpty: 0, hDriving: 0, hBusy: 0, hFailed: 0, hDuty: 0, hOperator: 0, jobs: 0, revenue: 0, nextFault: this.rngOps.exponential(cls.mtbf * this.sc.mtbfMult), alive: true, dutyPending: false, reposTarget: null }; this.vehicles.push(v); owners.push(f.owner); });
    const carriers = [...new Set(owners)].sort(); let k = 0;
    const all = [...new Set([...this.sc.owners, ...this.sc.bulk.map(b => b.owner)])].sort();
    for (const o of all) { if (carriers.includes(o)) this.carrierOf[o] = o; else { this.carrierOf[o] = carriers[k % carriers.length]; k++; } }
  }
  scheduleDemand() {
    const sc = this.sc, years = sc.horizon / (365 * 24), out = [];
    // fixed LANDERS order (CLPS, MK1, LARGE) like Python's LANDER_TYPES, so the draws do not depend on the scenario's key order
    const unknown = Object.keys(sc.landings).filter(k => !(k in LANDERS)); if (unknown.length) throw new Error('unknown lander types ' + unknown.join(', '));
    for (const name of Object.keys(LANDERS)) { if (!(name in sc.landings)) continue; const n = this.rng.poisson(sc.landings[name] * years); const times = []; for (let i = 0; i < n; i++) times.push(this.rng.uniform(0, sc.horizon)); times.sort((a, b) => a - b); for (const t of times) out.push([t, LANDERS[name], this.rng.choice(this.world.pads)]); }
    out.sort((a, b) => a[0] - b[0]); this.landingSchedule = out;
    for (const [t, lt, pad] of out) { this.events.push(t, 'LANDING', [lt, pad]); this.events.push(Math.max(0, t - 48), 'WAKE', null); this.events.push(Math.max(0, t - 12), 'WAKE', null); }
    if (sc.duty > 0) for (const v of this.vehicles) { const gap = sc.dutyBlock * (1 - sc.duty) / sc.duty; let t = this.rngOps.exponential(gap); while (t < sc.horizon) { this.events.push(t, 'DUTY', v); t += sc.dutyBlock + this.rngOps.exponential(gap); } }
    if (sc.night > 0) { let t = this.nightEnd(0); while (t < sc.horizon) { this.events.push(t + 1e-6, 'NIGHT_END', null); t += CYCLE; } }
    for (const bf of sc.bulk) { const nLots = Math.round(bf.tpy * 1000 / bf.lot * sc.horizon / (365 * 24)); if (nLots <= 0) continue; const times = []; for (let i = 0; i < nLots; i++) times.push(i * sc.horizon / nLots + this.rng.uniform(-0.5, 0.5) * sc.horizon / nLots); times.sort((a, b) => a - b);
      for (const tr of times) { this.cid++; const c = this.newCargo(this.cid, bf.owner, bf.lot, bf.origin, bf.dest, tr, tr, bf.prio, 'A', 'bulk'); this.events.push(Math.max(0, tr), 'BULK', c); } }
  }
  newCargo(id, owner, mass, origin, dest, tLanded, tReady, prio, std, cls) { return { id, owner, mass, origin, dest, tLanded, tReady, prio, std, cls, tPicked: null, tDelivered: null, stranded: false, carrier: null, team: 1, retMass: 0, retLag: 0 }; }
  isNight(t) { if (this.sc.night <= 0) return false; const ph = (t % CYCLE) / CYCLE; return ph >= 1 - this.sc.night; }
  nextNightStart(t) { const cyc = Math.floor(t / CYCLE); let s = (cyc + 1 - this.sc.night) * CYCLE; if (s <= t) s += CYCLE; return s; }
  nightEnd(t) { if (this.sc.night <= 0) return Infinity; if (this.isNight(t)) return (Math.floor(t / CYCLE) + 1) * CYCLE; return this.nextNightStart(t) + this.sc.night * CYCLE; }
  speedMult(v) { if (v.autonomy === 'teleop') return teleopSpeed(this.sc.rtt) / AUTO_REF; if (v.autonomy === 'supervised') return SUPERVISED_MULT; return 1; }
  handlingMult(v) { if (v.autonomy === 'teleop') return 1 + TELEOP_HANDLING_K * this.sc.rtt; if (v.autonomy === 'supervised') return 1.1; return 1; }
  opDemand(v) { if (v.autonomy === 'teleop') return 1; if (v.autonomy === 'supervised') return 1 / this.sc.fanout; return 0.05; }
  travelH(v, a, b, loaded, team, t) { const eq = this.world.equivFlat(a, b); let sp = v.cls.speed * (loaded ? 1 : v.cls.emptyMult) * this.speedMult(v); if (team) sp *= TEAM_SPEED; if (this.isNight(t) && v.cls.nightOps) sp *= this.sc.nightSpeed; return eq / Math.max(sp, 1e-6); }
  jobPlan(job, t0) {
    const team = job.vehicles.length > 1, pad = job.items.length ? job.items[0].origin : job.backhaul[0].origin; let durMax = 0, km = 0, kmE = 0, e = 0; this.lastSegs = {};
    for (const v of job.vehicles) { let t = t0; const segs = []; const d0 = this.world.distance(v.location, pad); let h = this.travelH(v, v.location, pad, false, false, t); let en = this.world.energyKm(v.location, pad) * v.cls.whKm; segs.push([v.location, pad, t, t + h, 0]); t += h; if (team) t += TEAM_SETUP;
      const hm = this.handlingMult(v); const tl = v.cls.loadH * hm * Math.max(1, job.items.length); segs.push([pad, pad, t, t + tl, 0]); t += tl;
      let prev = pad, kmv = d0; const loadKg = job.items.reduce((s, c) => s + c.mass, 0) / job.vehicles.length; let onboard = loadKg;
      for (const stop of job.route) { const dk = this.world.distance(prev, stop); h = this.travelH(v, prev, stop, true, team, t); segs.push([prev, stop, t, t + h, onboard]); t += h; en += this.world.energyKm(prev, stop) * v.cls.whKm * (1 + 0.6 * loadKg / Math.max(v.cls.cap, 1)); const nAt = job.items.filter(c => c.dest === stop); const tu = v.cls.unloadH * hm * nAt.length; segs.push([stop, stop, t, t + tu, onboard]); t += tu; onboard -= nAt.reduce((s, c) => s + c.mass, 0) / job.vehicles.length; kmv += dk; prev = stop; }
      if (job.backhaul.length) { const tl2 = v.cls.loadH * hm * job.backhaul.length; segs.push([prev, prev, t, t + tl2, 0]); t += tl2; const dest = job.backhaul[0].dest; const dk = this.world.distance(prev, dest); h = this.travelH(v, prev, dest, true, false, t); const bh = job.backhaul.reduce((s, c) => s + c.mass, 0); segs.push([prev, dest, t, t + h, bh]); t += h; en += this.world.energyKm(prev, dest) * v.cls.whKm * 1.3; const tu = v.cls.unloadH * hm * job.backhaul.length; segs.push([dest, dest, t, t + tu, bh]); t += tu; kmv += dk; prev = dest; }
      durMax = Math.max(durMax, t - t0); km += kmv; kmE += d0; e += en; this.lastSegs[v.id] = segs; }
    return [durMax, km, kmE, e];
  }
  jobCost(job, dur) { let c = 0; for (const v of job.vehicles) { c += dur * WEAR_SHARE * (v.cls.costM * 1e6 / v.cls.lifeH); c += dur * this.opDemand(v) * this.sc.opCost; } return c; }
  startDuty(v) { v.dutyPending = false; v.busyUntil = this.t + this.sc.dutyBlock; v.hDuty += this.sc.dutyBlock; this.events.push(v.busyUntil, 'FREE', null); }
  freeVehicles() { const out = []; for (const v of this.vehicles) { if (!v.alive || v.busyUntil > this.t + 1e-9) continue; if (v.dutyPending) { this.startDuty(v); continue; } if (this.isNight(this.t) && !v.cls.nightOps) continue; out.push(v); } return out; }
  opsAvailable() { this.opJobs = this.opJobs.filter(([e]) => e > this.t); return this.sc.nOps - this.opJobs.reduce((s, [, d]) => s + d, 0); }
  upcomingLandings(w) { return this.landingSchedule.filter(([t]) => this.t < t && t <= this.t + w); }
  scheduleReposition(v, pad, depart) { if (v.reposTarget !== null) return; v.reposTarget = pad; this.events.push(Math.max(this.t, depart), 'REPOS', [v, pad]); }
  reposition(v, pad) { const h = this.travelH(v, v.location, pad, false, false, this.t), d = this.world.distance(v.location, pad); if (!v.cls.nightOps && this.t + h > this.nextNightStart(this.t)) return false; const tEnd = this.t + h;
    if (this.trace) this.trace.push({ kind: 'reposition', veh: v.id, team: [v.id], t0: this.t, t1: tEnd, segments: [[v.location, pad, this.t, tEnd, 0]], items: [] });
    v.busyUntil = tEnd; v.location = pad; v.kmTotal += d; v.kmEmpty += d; v.hDriving += h; v.hBusy += h; this.repositions++; this.kmRepos += d; this.m.km += d; this.m.kmEmpty += d; this.m.busy += h; this.events.push(tEnd, 'FREE', null); return true; }
  run() {
    const H = this.sc.horizon;
    while (this.events.length) { const ev = this.events.pop(); if (ev.t > H) break; this.advanceTo(ev.t); const k = ev.kind;
      if (k === 'LANDING') this.landing(ev.payload[0], ev.payload[1]);
      else if (k === 'READY') { const c = ev.payload; this.pending.splice(this.pending.indexOf(c), 1); this.waiting.push(c); this.m.ready += c.mass; }
      else if (k === 'TICK') this.events.push(ev.t + this.batch, 'TICK', null);
      else if (k === 'REPOS') { const [v, pad] = ev.payload; v.reposTarget = null; let started = false; if (v.busyUntil <= this.t && !v.dutyPending && v.location !== pad && !(this.isNight(this.t) && !v.cls.nightOps)) started = this.reposition(v, pad); if (!started) continue; }
      else if (k === 'DUTY') { const v = ev.payload; if (v.busyUntil <= this.t) this.startDuty(v); else v.dutyPending = true; continue; }
      else if (k === 'BULK') { const c = ev.payload; this.allCargo.push(c); this.waiting.push(c); this.m.ready += c.mass; this.m.bulk += c.mass; this.markStranded([c]); }
      if (this.batch > 0 && k !== 'TICK') continue;
      this.dispatch(); }
    this.advanceTo(H); this.finalise(); return this.summary();
  }
  advanceTo(t) { const dt = t - this.t; if (dt > 0) for (const v of this.vehicles) if (v.busyUntil <= this.t) v.battery = Math.min(v.cls.battery, v.battery + v.cls.chargeKw * 1000 * dt); this.t = t; }
  landing(lt, pad) { const items = this.sampleManifest(lt, pad, this.t); for (const c of items) { this.allCargo.push(c); this.pending.push(c); this.m.landed += c.mass; this.events.push(c.tReady, 'READY', c); } this.markStranded(items); }
  sampleManifest(lt, pad, tLand) {
    const rng = this.rng, total = rng.uniform(lt.payload[0], lt.payload[1]); const shares = CARGO_CLASSES.map(c => c[4]); const items = []; let massSoFar = 0, guard = 0;
    while (massSoFar < total && guard < 500) { guard++; const k = rng.weighted([0, 1, 2, 3, 4], shares); let [label, [lo, hi0], dests, prio] = CARGO_CLASSES[k]; const hi = Math.min(hi0, lt.maxItem); if (hi <= lo) continue; let m = rng.uniform(lo, hi);
      if (massSoFar + m > total * 1.15) { m = Math.max(20, total - massSoFar); label = 'consumables'; prio = 1; dests = { BASE: 0.8, DEPOT: 0.2 }; }
      const keys = Object.keys(dests); const dest = rng.weighted(keys, keys.map(k2 => dests[k2])); const std = rng.random() < this.sc.commonStd ? 'A' : 'B'; const owner = rng.choice(this.sc.owners); const tReady = tLand + rng.uniform(lt.offload[0], lt.offload[1]) + 0.25 * items.length;
      const c = this.newCargo(this.cid, owner, m, pad, dest, tLand, tReady, prio, std, label); if (rng.random() < RETURN_PROB) { c.retMass = Math.max(10, m * rng.uniform(0.2, 0.6)); c.retLag = rng.uniform(RETURN_LAG[0], RETURN_LAG[1]); } items.push(c); this.cid++; massSoFar += m; }
    return items;
  }
  markStranded(items) { const teamCaps = this.vehicles.filter(v => v.cls.team).map(v => v.cls.cap).sort((a, b) => b - a); const singleMax = Math.max(0, ...this.vehicles.map(v => v.cls.cap)); const teamMax = teamCaps.slice(0, 3).reduce((s, x) => s + x, 0); const allowTeam = this.mopts.team_lift !== undefined ? this.mopts.team_lift : !!this.mech.supportsTeam;
    for (const c of items) { const limit = Math.max(singleMax, allowTeam ? teamMax : 0); const compat = this.vehicles.some(v => v.standards.has(c.std)); if (c.mass > limit || !compat) c.stranded = true; } }
  dispatch() { const cands = this.waiting.filter(c => !c.stranded); const free = this.freeVehicles(); if (!free.length) return; if (!cands.length && !this.mech.anticipates) return; const jobs = this.mech(this, cands, free, this.mopts); for (const j of jobs) this.startJob(j); }
  startJob(job) {
    const demand = job.vehicles.reduce((s, v) => s + this.opDemand(v), 0); const avail = this.opsAvailable();
    if (demand > avail + 1e-9) { if (this.opJobs.length) { const tFree = Math.min(...this.opJobs.map(([e]) => e)); for (const v of job.vehicles) v.busyUntil = Math.max(v.busyUntil, tFree); this.events.push(tFree, 'FREE', null); this.m.unmetOps++; } return; }
    let [dur, km, kmE, eWh] = this.jobPlan(job, this.t);
    for (const v of job.vehicles) { const need = eWh / job.vehicles.length; if (need > v.battery) { dur += (need - v.battery) / (v.cls.chargeKw * 1000); v.battery = v.cls.battery; } v.battery = Math.max(0, v.battery - need); }
    const driving = dur;
    for (const v of job.vehicles) if (this.sc.failures && v.hDriving + driving > v.nextFault) { dur += v.cls.mttr; v.hFailed += v.cls.mttr; v.nextFault = v.hDriving + driving + this.rngOps.exponential(v.cls.mtbf * this.sc.mtbfMult); this.m.faults++; }
    let tEnd = this.t + dur;
    if (this.sc.night > 0) for (const v of job.vehicles) if (!v.cls.nightOps) { const ns = this.nextNightStart(this.t); if (tEnd > ns) { dur += this.sc.night * CYCLE; this.m.nightStr++; break; } }
    tEnd = this.t + dur; const last = job.backhaul.length ? job.backhaul[0].dest : job.route[job.route.length - 1];
    if (this.trace) { let segs = this.lastSegs[job.vehicles[0].id] || []; const planEnd = segs.length ? segs[segs.length - 1][3] : this.t; if (tEnd - planEnd > 1e-9) segs = segs.concat([[last, last, planEnd, tEnd, 0]]); this.trace.push({ kind: job.vehicles.length > 1 ? 'team' : (job.note || 'job'), veh: job.vehicles[0].id, team: job.vehicles.map(u => u.id), t0: this.t, t1: tEnd, segments: segs, items: job.items.concat(job.backhaul).map(c => [c.id, c.mass, c.prio, c.cls, c.dest]) }); }
    for (const v of job.vehicles) { v.reposTarget = null; v.busyUntil = tEnd; v.location = last; v.kmTotal += km / job.vehicles.length; v.kmEmpty += kmE / job.vehicles.length; v.hDriving += driving; v.hBusy += dur; v.hOperator += dur * this.opDemand(v); v.jobs++; }
    const price = this.jobCost(job, dur); for (const v of job.vehicles) { const sh = price / job.vehicles.length / 1e6; v.revenue += sh; this.m.revenue[v.owner] = (this.m.revenue[v.owner] || 0) + sh; }
    this.opJobs.push([tEnd, demand]);
    for (const c of job.items) { this.waiting.splice(this.waiting.indexOf(c), 1); c.tPicked = this.t; c.carrier = job.vehicles[0].id; c.team = job.vehicles.length; const idx = job.route.indexOf(c.dest); const frac = (idx + 1) / (job.route.length + (job.backhaul.length ? 1 : 0)); c.tDelivered = this.t + dur * frac; this.events.push(c.tDelivered, 'FREE', null); this.recordDelivery(c); }
    for (const c of job.backhaul) { this.waiting.splice(this.waiting.indexOf(c), 1); c.tPicked = this.t; c.carrier = job.vehicles[0].id; c.tDelivered = tEnd; this.recordDelivery(c); this.m.backhaulKg += c.mass; }
    if (job.vehicles.length > 1) this.m.teamLifts++; if (job.items.length > 1) this.m.bundled++; this.m.jobs++; this.m.km += km; this.m.kmEmpty += kmE; this.m.energy += eWh / 1000; this.m.busy += dur * job.vehicles.length; this.m.opHours += dur * demand; this.events.push(tEnd, 'FREE', null);
  }
  recordDelivery(c) { const m = this.m; m.delivered += c.mass; m.deliveredItems++; m.delays.push(c.tDelivered - c.tReady); m.dprio.push(c.prio); m.dcls.push(c.cls); m.dmass.push(c.mass);
    if (this.world.pads.includes(c.origin) && c.cls !== 'return' && c.retMass > 0) { const tr = c.tDelivered + c.retLag; if (tr < this.sc.horizon) { this.cid++; const rc = this.newCargo(this.cid, c.owner, c.retMass, c.dest, c.origin, tr, tr, 3, c.std, 'return'); this.allCargo.push(rc); this.pending.push(rc); this.events.push(tr, 'READY', rc); } } }
  finalise() { const m = this.m; for (const c of this.waiting) { if (c.stranded) { m.stranded += c.mass; m.strandedItems++; } else m.backlog += c.mass; } for (const v of this.vehicles) m.fleetCost += v.cls.costM * this.sc.horizon / (v.cls.lifeYr * 365 * 24); m.opCost = m.opHours * this.sc.opCost / 1e6; }
  summary() {
    const m = this.m, d = m.delays, pr = m.dprio; const p1 = d.filter((_, i) => pr[i] === 1); const pct = (arr, q) => { if (!arr.length) return NaN; const s = [...arr].sort((a, b) => a - b); const k = (s.length - 1) * q; const lo = Math.floor(k), hi = Math.ceil(k); return s[lo] + (s[hi] - s[lo]) * (k - lo); }; const mean = arr => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : NaN;
    const byCls = {}; for (const lab of ['consumables', 'science', 'equipment', 'infrastructure', 'element', 'bulk', 'return']) byCls[lab] = mean(d.filter((_, i) => m.dcls[i] === lab));
    const rev = Object.values(m.revenue); const gini = (() => { const x = [...rev].sort((a, b) => a - b), n = x.length, s = x.reduce((a, b) => a + b, 0); if (!n || s <= 0) return 0; let cum = 0, acc = 0; for (const xi of x) { cum += xi; acc += cum; } return (n + 1 - 2 * acc / cum) / n; })();
    const H = this.sc.horizon, totalCost = m.fleetCost + m.opCost;
    return { landed_kg: m.landed, ready_kg: m.ready, delivered_kg: m.delivered, delivered_share: m.delivered / Math.max(m.ready, 1e-9), stranded_kg: m.stranded, immovable_share: m.stranded / Math.max(m.landed, 1e-9), backlog_kg: m.backlog,
      delay_prio1_mean_h: mean(p1), delay_prio1_p90_h: pct(p1, 0.9), sl24_prio1: p1.length ? p1.filter(x => x <= 24).length / p1.length : NaN, delay_mean_h: mean(d), delay_by_class: byCls,
      jobs: m.jobs, bundled_jobs: m.bundled, team_lifts: m.teamLifts, night_strandings: m.nightStr, faults: m.faults, utilisation: m.busy / Math.max(1e-9, H * this.vehicles.length), empty_km_share: m.kmEmpty / Math.max(m.km, 1e-9), km_total: m.km,
      operator_hours: m.opHours, fleet_cost_musd: m.fleetCost, operator_cost_musd: m.opCost, cost_per_kg_usd: 1e6 * totalCost / Math.max(m.delivered, 1e-9), cost_per_landed_kg_usd: 1e6 * totalCost / Math.max(m.delivered - m.bulk, 1e-9), revenue_gini: gini, repositions: this.repositions, backhaul_kg: m.backhaulKg, bulk_kg: m.bulk, unmet_operator_waits: m.unmetOps };
  }
  exportTrace(meta = {}) { const nights = []; if (this.sc.night > 0) { let t = 0; while (t < this.sc.horizon) { const ns = this.nextNightStart(t), ne = ns + this.sc.night * CYCLE; nights.push([ns, Math.min(ne, this.sc.horizon)]); t = ne + 1e-6; } }
    // lunarsim-trace v1 (PLAN §4.1): same shape as Python's trace_export(); cargo as rows looked up by column name
    const mechName = meta.mechanism || Object.keys(MECHS).find(k => MECHS[k] === this.mech) || null;
    return { format: 'lunarsim-trace', version: 1, engine: 'js', scenario: meta.scenario || this.sc.name || null, mechanism: mechName, seed: meta.seed !== undefined ? meta.seed : null, horizon_h: this.sc.horizon,
      nights, landings: this.landingSchedule.map(([t, lt, pad]) => [t, lt.name, pad]),
      vehicles: this.vehicles.map(v => ({ id: v.id, owner: v.owner, cls: v.cls.name, autonomy: v.autonomy, capacity: v.cls.cap, night_ops: v.cls.nightOps })), jobs: this.trace || [],
      cargo_columns: ['id', 'owner', 'mass_kg', 'origin', 'dest', 't_ready', 't_picked', 't_delivered', 'priority', 'cls', 'stranded', 't_landed'],
      cargo: this.allCargo.map(c => [c.id, c.owner, c.mass, c.origin, c.dest, c.tReady, c.tPicked, c.tDelivered, c.prio, c.cls, c.stranded ? 1 : 0, c.tLanded === undefined ? null : c.tLanded]) }; }
}

// ---------- Dispatch mechanisms (port of dispatch.py) ----------
const feasible = (v, c) => v.standards.has(c.std) && c.mass <= v.cls.cap;
const Job = (vehicles, items, route, note = '') => ({ vehicles, items, route, backhaul: [], note });
function greedy(sim, waiting, free, pooled) { const jobs = [], used = new Set(); const order = [...waiting].sort((a, b) => a.tReady - b.tReady);
  for (const c of order) { let best = null, bh = Infinity; for (const v of free) { if (used.has(v.id) || !feasible(v, c)) continue; if (!pooled && (sim.carrierOf[c.owner] || c.owner) !== v.owner) continue; const h = sim.travelH(v, v.location, c.origin, false, false, sim.t); if (h < bh) { best = v; bh = h; } } if (best) { used.add(best.id); jobs.push(Job([best], [c], [c.dest], 'greedy')); } } return jobs; }
function inhouse(sim, w, f) { return greedy(sim, w, f, false); }
function pooledGreedy(sim, w, f) { return greedy(sim, w, f, true); }
function centralAssign(sim, waiting, free) { if (!waiting.length || !free.length) return []; const BIG = 1e6; const cost = free.map(v => waiting.map(c => feasible(v, c) ? sim.jobPlan(Job([v], [c], [c.dest]), sim.t)[0] - 0.05 * (sim.t - c.tReady) : BIG)); const [rows, cols] = hungarian(cost); const jobs = []; rows.forEach((i, k) => { const j = cols[k]; if (cost[i][j] < BIG / 2) jobs.push(Job([free[i]], [waiting[j]], [waiting[j].dest], 'hungarian')); }); return jobs; }
centralAssign.batch_h = 1.0;
const PRIO_W = { 1: 6, 2: 2, 3: 0 }, AGE_W = 0.08, MAX_POOL = 40, FILL = 0.7, MAX_WAIT = 24, ANT_WINDOW = 48, ANT_MARGIN = 1;
function bid(sim, v, bundle, route, priority) { const job = Job([v], bundle, route); const hours = sim.jobPlan(job, sim.t)[0]; let tot = sim.jobCost(job, hours); for (const c of bundle) { const idx = route.indexOf(c.dest); tot += (sim.sc.vot[c.prio] || 100) * hours * (idx + 1) / route.length; } if (priority) for (const c of bundle) tot -= (PRIO_W[c.prio] + AGE_W * (sim.t - c.tReady)) * sim.sc.urgency; return tot; }
function permutations(arr) { if (arr.length <= 1) return [arr]; const out = []; arr.forEach((x, i) => { for (const p of permutations(arr.filter((_, j) => j !== i))) out.push([x, ...p]); }); return out; }
function bestRoute(sim, origin, dests) { const uniq = [...new Set(dests)]; if (uniq.length <= 1) return uniq; let best = null, bl = Infinity; for (const perm of permutations(uniq)) { let L = sim.world.equivFlat(origin, perm[0]); for (let i = 0; i + 1 < perm.length; i++) L += sim.world.equivFlat(perm[i], perm[i + 1]); if (L < bl) { bl = L; best = perm; } } return best; }
function tryBundle(sim, v, seed, pool, maxItems, priority) { let bundle = [seed], route = [seed.dest]; let base = sim.jobPlan(Job([v], bundle, route), sim.t)[0]; const cands = pool.filter(c => c !== seed && c.origin === seed.origin && v.standards.has(c.std)).sort((a, b) => ((a.dest !== seed.dest) - (b.dest !== seed.dest)) || (a.prio - b.prio) || (a.tReady - b.tReady));
  for (const c of cands) { if (bundle.length >= maxItems) break; if (bundle.reduce((s, x) => s + x.mass, 0) + c.mass > v.cls.cap) continue; const nr = bestRoute(sim, seed.origin, route.concat([c.dest])); if (nr.length > 4) continue; const nh = sim.jobPlan(Job([v], bundle.concat([c]), nr), sim.t)[0]; const sep = sim.jobPlan(Job([v], [c], [c.dest]), sim.t)[0]; if (nh - base < 0.8 * sep) { bundle.push(c); route = nr; base = nh; } }
  return [bundle, route, bid(sim, v, bundle, route, priority)]; }
function nightOk(sim, v, job) { if (v.cls.nightOps) return true; return sim.t + sim.jobPlan(job, sim.t)[0] <= sim.nextNightStart(sim.t); }
function teamFor(sim, c, free, used) { const cands = free.filter(v => !used.has(v.id) && v.cls.team && v.standards.has(c.std)).sort((a, b) => b.cls.cap - a.cls.cap); for (const k of [2, 3]) { const combos = (arr, k2, start = 0, acc = []) => { if (acc.length === k2) return [acc]; let out = []; for (let i = start; i < arr.length; i++) out = out.concat(combos(arr, k2, i + 1, acc.concat([arr[i]]))); return out; }; for (const combo of combos(cands, k)) if (combo.reduce((s, v) => s + v.cls.cap, 0) >= c.mass) return combo; } return null; }
function anticipate(sim, free, used) { for (const [tLand, lt, pad] of sim.upcomingLandings(ANT_WINDOW)) { if (sim.vehicles.some(v => (v.location === pad && v.busyUntil <= sim.t) || v.reposTarget === pad)) continue; const tFirst = tLand + lt.offload[0]; const cands = free.filter(v => !used.has(v.id) && v.reposTarget === null && v.location !== pad); if (!cands.length) continue; let v = cands[0], bh = Infinity; for (const u of cands) { const h = sim.travelH(u, u.location, pad, false, false, sim.t); if (h < bh) { bh = h; v = u; } } const depart = Math.max(sim.t, tFirst - ANT_MARGIN - bh); if (!v.cls.nightOps && depart + bh > sim.nextNightStart(depart)) continue; sim.scheduleReposition(v, pad, depart); used.add(v.id); } }
function marketplace(sim, waiting, free, o = {}) {
  const bundling = o.bundling !== false, teamLift = o.team_lift !== false, backhaul = o.backhaul !== false, nightAware = o.night_aware !== false, priority = o.priority !== false, consolidate = o.consolidate !== false, antic = o.anticipate !== false, maxItems = 10;
  const jobs = [], used = new Set(); let pool = [...waiting];
  if (consolidate && bundling) { const bulk = pool.filter(c => c.cls === 'bulk' && c.prio >= 3); if (bulk.length) { const lanes = {}; for (const c of bulk) (lanes[c.origin + '>' + c.dest] = lanes[c.origin + '>' + c.dest] || []).push(c); const capRef = Math.max(0, ...free.filter(v => bulk.some(c => feasible(v, c))).map(v => v.cls.cap));
    for (const key in lanes) { const lots = lanes[key]; const mass = lots.reduce((s, c) => s + c.mass, 0); const age = sim.t - Math.min(...lots.map(c => c.tReady)); if (capRef > 0 && mass < FILL * capRef && age < MAX_WAIT) { for (const c of lots) pool.splice(pool.indexOf(c), 1); sim.events.push(sim.t + (MAX_WAIT - age) + 1e-6, 'WAKE', null); } } } }
  if (teamLift) { const singleMax = Math.max(0, ...free.map(v => v.cls.cap)); const oversize = pool.filter(c => c.mass > singleMax).sort((a, b) => (a.prio - b.prio) || (a.tReady - b.tReady)); for (const c of oversize) { const team = teamFor(sim, c, free, used); if (!team) continue; const job = Job(team, [c], [c.dest], 'team'); if (nightAware && !team.every(v => nightOk(sim, v, job))) continue; team.forEach(v => used.add(v.id)); jobs.push(job); pool.splice(pool.indexOf(c), 1); } }
  if (pool.length > MAX_POOL) { pool.sort((a, b) => (a.prio - b.prio) || (a.tReady - b.tReady)); pool = pool.slice(0, MAX_POOL); }
  for (;;) { const vehicles = free.filter(v => !used.has(v.id)); if (!vehicles.length || !pool.length) break; let best = null;
    for (const v of vehicles) for (const c of pool) { if (!feasible(v, c)) continue; let bundle, route, b; if (bundling) [bundle, route, b] = tryBundle(sim, v, c, pool, maxItems, priority); else { bundle = [c]; route = [c.dest]; b = bid(sim, v, bundle, route, priority); } if (!best || b < best[0]) best = [b, v, bundle, route]; }
    if (!best) break; const [, v, bundle, route] = best; const job = Job([v], bundle, route, 'auction'); if (nightAware && !nightOk(sim, v, job)) { used.add(v.id); continue; }
    if (backhaul) { const last = route[route.length - 1]; const ret = pool.filter(c => c.origin === last && !bundle.includes(c) && v.standards.has(c.std) && sim.world.pads.includes(c.dest)).sort((a, b) => a.tReady - b.tReady); let bh = [], m = 0; for (const c of ret) if (m + c.mass <= v.cls.cap) { bh.push(c); m += c.mass; } if (bh.length) { const pad = bh[0].dest; job.backhaul = bh.filter(c => c.dest === pad); } }
    used.add(v.id); jobs.push(job); for (const c of bundle.concat(job.backhaul)) pool.splice(pool.indexOf(c), 1); }
  if (antic) anticipate(sim, free, used); return jobs;
}
marketplace.supportsTeam = true; marketplace.anticipates = true;
const MECHS = { inhouse, pooled_greedy: pooledGreedy, central_assign: centralAssign, marketplace };
const MECH_LABEL = { inhouse: 'In-house fleets', pooled_greedy: 'Pooled greedy', central_assign: 'Batched assignment', marketplace: 'Marketplace' };
const MECH_COLOR = { inhouse: 'var(--s2)', pooled_greedy: 'var(--s4)', central_assign: 'var(--s6)', marketplace: 'var(--s1)' };

function runOne(sc, mechName, seed, opts = {}) { const mech = MECHS[mechName]; const mo = Object.assign({}, opts); if (mech.batch_h) mo.batch_h = mech.batch_h; if (mechName !== 'marketplace') { mo.team_lift = undefined; } const sim = new Simulation(sc, mech, seed, mo); const s = sim.run(); s.seed = seed; return [s, sim]; }

// ---------- Statistics ----------
const mean = a => { const x = a.filter(v => Number.isFinite(v)); return x.length ? x.reduce((p, q) => p + q, 0) / x.length : NaN; };
const ci95 = a => { const x = a.filter(v => Number.isFinite(v)); if (x.length < 2) return 0; const m = mean(x); const sd = Math.sqrt(x.reduce((s, v) => s + (v - m) ** 2, 0) / (x.length - 1)); return 1.96 * sd / Math.sqrt(x.length); };
function tQuantile(p, df) { // Cornish-Fisher style approximation of Student t quantile, adequate for df >= 10
  const z = normQuantile(p); const g1 = (z ** 3 + z) / 4, g2 = (5 * z ** 5 + 16 * z ** 3 + 3 * z) / 96, g3 = (3 * z ** 7 + 19 * z ** 5 + 17 * z ** 3 - 15 * z) / 384; return z + g1 / df + g2 / df ** 2 + g3 / df ** 3; }
function normQuantile(p) { const a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00], b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01], c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00], d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]; const pl = 0.02425, ph = 1 - pl; let q, r; if (p < pl) { q = Math.sqrt(-2 * Math.log(p)); return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); } if (p <= ph) { q = p - 0.5; r = q * q; return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1); } q = Math.sqrt(-2 * Math.log(1 - p)); return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
const ci99 = a => { const x = a.filter(v => Number.isFinite(v)); if (x.length < 2) return Infinity; const m = mean(x); const sd = Math.sqrt(x.reduce((s, v) => s + (v - m) ** 2, 0) / (x.length - 1)); return tQuantile(0.995, x.length - 1) * sd / Math.sqrt(x.length); };


function verificationChecks() { const checks = []; const push = (name, ref, sim, tol, unit, basis) => { const err = Math.abs(sim - ref) / Math.max(Math.abs(ref), 1e-12); checks.push({ name, ref, sim, tol, unit, basis, passed: err <= tol, err }); };
  const base = makeScenario({ phase: 'P2', bulkT: 0, fleet: [LTV('A', 'autonomous')], night: 0.15, rtt: 5, nOps: 2, duty: 0, mtbf: 1, std: 1 }); base.landings = { CLPS: 0, MK1: 0, LARGE: 0 }; base.failures = false;
  const s0 = new Simulation(base, pooledGreedy, 0); const v = s0.vehicles[0];
  push('Travel time on a flat two-edge path (PAD_A→BASE)', WORLD.distance('PAD_A', 'BASE') / v.cls.speed, s0.travelH(v, 'PAD_A', 'BASE', true, false, 0), 1e-9, 'h', 'distance / speed');
  push('Steep-edge travel time doubles (SCI_1→PSR)', WORLD.distance('SCI_1', 'PSR') / (0.5 * v.cls.speed), s0.travelH(v, 'SCI_1', 'PSR', true, false, 0), 1e-9, 'h', 'slope class steep halves speed');
  for (const [rtt, obs] of TELEOP_TABLE) push(`Teleoperated speed at ${rtt} s RTT`, obs, teleopSpeed(rtt), 0.01, 'km/h', 'NASA JSC LTV trials');
  let dark = 0; const N = 50000; for (let i = 0; i < N; i++) if (s0.isNight(i / N * 10 * CYCLE)) dark++; push('Dark share of time', 0.15, dark / N, 0.005, 'fraction', 'night_fraction parameter over 10 cycles');
  const sc2 = makeScenario({ phase: 'P2', bulkT: 300, fleet: PRESETS[4], night: 0.15, rtt: 5, nOps: 3, duty: 0.3, mtbf: 1, std: 1 }); for (const [mn, fn] of [['marketplace', marketplace], ['pooled greedy', pooledGreedy]]) { const sim = new Simulation(sc2, fn, 3); sim.run(); push(`Mass conservation (${mn})`, sim.m.ready, sim.m.delivered + sim.m.stranded + sim.m.backlog, 1e-9, 'kg', 'ready = delivered + stranded + backlog'); }
  const sc3 = makeScenario({ phase: 'P2', bulkT: 0, fleet: [LTV('NASA', 'autonomous'), LTV('NASA', 'autonomous')], night: 0.15, rtt: 5, nOps: 2, duty: 0, mtbf: 1, std: 1 }); sc3.landings = { CLPS: 0, MK1: 0, LARGE: 6 }; sc3.failures = false; const sim3 = new Simulation(sc3, marketplace, 5); sim3.run(); const heavy = sim3.allCargo.filter(c => c.mass > 3000 && c.cls !== 'return'); push('Items above team capacity (2 × 1,500 kg) never delivered', 0, heavy.filter(c => c.tDelivered !== null).length, 0, 'items', `${heavy.length} heavy items in six large landings`);
  const sc4 = makeScenario({ phase: 'P2', bulkT: 500, fleet: [LTV('NASA'), HAUL('CoA')], night: 0.15, rtt: 5, nOps: 3, duty: 0.3, mtbf: 1, std: 1 }); const sigs = [inhouse, pooledGreedy, centralAssign, marketplace].map(fn => { const mo = fn.batch_h ? { batch_h: fn.batch_h } : {}; const sim = new Simulation(sc4, fn, 11, mo); sim.run(); return JSON.stringify(sim.allCargo.filter(c => c.cls !== 'return' && c.cls !== 'bulk').map(c => [c.tLanded.toFixed(6), c.mass.toFixed(6), c.dest]).sort()); }); push('Same landed manifest for every rule (seed 11)', 1, sigs.every(s => s === sigs[0]) ? 1 : 0, 0, 'bool', 'common random numbers');
  const sc5 = makeScenario({ phase: 'P2', bulkT: 0, fleet: [LTV('NASA'), HAUL('CoA'), MICRO('CoB')], night: 0.15, rtt: 5, nOps: 3, duty: 0.3, mtbf: 1, std: 1 }); sc5.landings = { CLPS: 1, MK1: 0, LARGE: 0 }; const sim5 = new Simulation(sc5, pooledGreedy, 1); const out5 = sim5.run(); push('Annual fleet amortisation', 450 / 10 + 600 / 10 + 60 / 5, out5.fleet_cost_musd, 1e-9, '$M', 'sum of unit cost / calendar life');
  const a1 = runOne(sc2, 'marketplace', 4)[0], a2 = runOne(sc2, 'marketplace', 4)[0]; push('Determinism: identical results for the same seed', a1.delivered_kg + a1.jobs, a2.delivered_kg + a2.jobs, 0, 'kg+trips', 'two runs, seed 4');
  return checks; }

// ---------- Worker protocol ----------
// {type:'run', scenario, mechanism, seeds:[...], opts, trace:boolean} -> progress + result (trace: lunarsim-trace v1 of the first seed, or null)
// {type:'verify'} -> checks
if (typeof importScripts === 'function') {  // only inside a web worker
  self.onmessage = (e) => {
    const msg = e.data;
    if (msg.type === 'run') {
      const out = []; let firstTrace = null; const t0 = Date.now();
      msg.seeds.forEach((seed, i) => {
        const o = Object.assign({}, msg.opts || {}, i === 0 && msg.trace ? { trace: true } : {});
        const [s, sim] = runOne(msg.scenario, msg.mechanism, seed, o);
        out.push(s);
        if (i === 0 && msg.trace) firstTrace = sim.exportTrace({ scenario: msg.scenario.name, mechanism: msg.mechanism, seed });
        if ((i + 1) % 5 === 0 || i === msg.seeds.length - 1) self.postMessage({ type: 'progress', id: msg.id, done: i + 1, total: msg.seeds.length });
      });
      self.postMessage({ type: 'result', id: msg.id, runs: out, trace: firstTrace, ms: Date.now() - t0 });
    } else if (msg.type === 'verify') {
      self.postMessage({ type: 'verify', id: msg.id, checks: verificationChecks() });
    }
  };
}
