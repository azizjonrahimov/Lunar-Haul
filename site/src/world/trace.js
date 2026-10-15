// lunarsim-trace reader for /world: v1 (PLAN 4.1, also legacy files without a header) and v2 (PLAN 5.5).
// Same normalisation as web/formats.js readTrace, plus the v2 fields. Pure; throws TraceError with a readable message.

export class TraceError extends Error { constructor(m) { super(m); this.name = 'TraceError'; } }

const DEFAULT_COLUMNS = ['id', 'owner', 'mass_kg', 'origin', 'dest', 't_ready', 't_picked', 't_delivered', 'priority', 'cls', 'stranded'];
const REQUIRED = ['id', 'mass_kg', 'origin', 'dest', 't_ready', 't_picked', 't_delivered', 'priority', 'cls', 'stranded'];

/* readTrace(json|string, siteNames:Set) -> model
   { meta:{engine, scenario, mechanism, seed, version, legacy, terrain}, horizon, nights:[[a,b]],
     landings:[{t, type, pad, xy, miss, tilt, ok, descent}], plumeWindows:[{t0,t1,pad,R_m}], shelters,
     vehicles:[{id, owner, cls, autonomy, autonomyLevel, cap, nightOps}],
     jobs:[{kind, veh, team, t0, t1, segments:[[from,to,s0,s1,kg]], items, energy, interventions}],  (sorted by t0)
     cargo:[{id, owner, mass, origin, dest, tReady, tPicked, tDelivered, prio, cls, stranded}], summary } */
export function readTrace(json, siteNames) {
  const fail = m => { throw new TraceError(m); };
  if (typeof json === 'string') { try { json = JSON.parse(json); } catch (e) { fail('not valid JSON (' + e.message + ')'); } }
  if (!json || typeof json !== 'object' || Array.isArray(json)) fail('expected a JSON object');
  if (json.format !== undefined && json.format !== 'lunarsim-trace') fail(`format is "${json.format}", expected "lunarsim-trace"`);
  const version = json.version === undefined ? 1 : json.version;
  if (version !== 1 && version !== 2) fail(`unsupported lunarsim-trace version ${version} (this page reads v1 and v2)`);
  const horizon = json.horizon_h;
  if (typeof horizon !== 'number' || !(horizon > 0)) fail('missing or invalid "horizon_h"');
  for (const k of ['nights', 'landings', 'vehicles', 'jobs', 'cargo']) if (!Array.isArray(json[k])) fail(`missing array "${k}"`);
  const site = (n, w) => { if (siteNames && !siteNames.has(n)) fail(`unknown site "${n}" in ${w}`); return n; };
  const num = (x, w) => { if (typeof x !== 'number' || !Number.isFinite(x)) fail(`expected a number in ${w}, got ${JSON.stringify(x)}`); return x; };
  const numOrNull = (x, w) => (x === null || x === undefined) ? null : num(x, w);

  const nights = json.nights.map((n, i) => { if (!Array.isArray(n) || n.length < 2) fail(`nights[${i}] is not [t_start, t_end]`); return [num(n[0], `nights[${i}]`), num(n[1], `nights[${i}]`)]; });
  const landings = json.landings.map((l, i) => {
    const w = `landings[${i}]`;
    if (Array.isArray(l)) { if (l.length < 3) fail(`${w} is not [t, lander, pad]`); return { t: num(l[0], w), type: String(l[1]), pad: site(l[2], w), xy: null, miss: null, tilt: null, ok: true, descent: null }; }
    if (!l || typeof l !== 'object') fail(`${w} is neither a row nor an object`);
    const descent = Array.isArray(l.descent) && l.descent.length ? l.descent.map((d, k) => { if (!Array.isArray(d) || d.length < 4) fail(`${w}.descent[${k}] needs [t,x,y,z,...]`); return d.map(Number); }) : null;
    // miss_m: B-12 writes the horizontal miss as [dx, dy] metres; a plain number (magnitude) is accepted too
    const missXY = Array.isArray(l.miss_m) ? [num(l.miss_m[0], `${w}.miss_m[0]`), num(l.miss_m[1], `${w}.miss_m[1]`)] : null;
    const miss = missXY ? Math.hypot(missXY[0], missXY[1]) : numOrNull(l.miss_m, `${w}.miss_m`);
    return { t: num(l.t, `${w}.t`), type: String(l.type), pad: site(l.pad, w), xy: Array.isArray(l.xy_m) ? l.xy_m.map(Number) : null,
      miss, missXY, tilt: numOrNull(l.tilt_deg, `${w}.tilt_deg`), ok: l.ok !== false, failureKind: l.failure_kind || null,
      cargoKg: numOrNull(l.cargo_kg, `${w}.cargo_kg`), descent };
  }).sort((a, b) => a.t - b.t);
  const plumeWindows = (Array.isArray(json.plume_windows) ? json.plume_windows : []).map((p, i) => {
    const w = `plume_windows[${i}]`; if (!Array.isArray(p) || p.length < 4) fail(`${w} is not [t0, t1, pad, R]`);
    return { t0: num(p[0], w), t1: num(p[1], w), pad: site(p[2], w), R_m: 1000 * num(p[3], w) };  // R in km (Scenario plume.keepout_km)
  }).sort((a, b) => a.t0 - b.t0);
  const vehicles = json.vehicles.map((v, i) => {
    if (!v || typeof v !== 'object') fail(`vehicles[${i}] is not an object`);
    return { id: num(v.id, `vehicles[${i}].id`), owner: String(v.owner), cls: String(v.cls), autonomy: v.autonomy || null,
      autonomyLevel: v.autonomy_level === undefined ? null : v.autonomy_level, cap: v.capacity !== undefined ? v.capacity : (v.cap ?? null), nightOps: !!v.night_ops };
  });
  const vids = new Set(vehicles.map(v => v.id));
  const jobs = json.jobs.map((j, i) => {
    const w = `jobs[${i}]`;
    if (!j || typeof j !== 'object' || !Array.isArray(j.segments)) fail(`${w} has no "segments" array`);
    const team = Array.isArray(j.team) ? j.team : [j.veh];
    for (const id of team) if (!vids.has(id)) fail(`${w} refers to unknown vehicle ${id}`);
    const segments = j.segments.map((s, k) => { if (!Array.isArray(s) || s.length < 5) fail(`${w}.segments[${k}] is not [from, to, t0, t1, kg]`); return [site(s[0], w), site(s[1], w), num(s[2], w), num(s[3], w), num(s[4], w)]; });
    return { kind: j.kind || 'job', veh: j.veh, team, t0: num(j.t0, `${w}.t0`), t1: num(j.t1, `${w}.t1`), segments, items: Array.isArray(j.items) ? j.items : [],
      energy: numOrNull(j.energy_kwh, `${w}.energy_kwh`), interventions: numOrNull(j.interventions, `${w}.interventions`) };
  }).map((j, i) => [j, i]).sort((a, b) => (a[0].t0 - b[0].t0) || (a[1] - b[1])).map(x => x[0]);

  const cols = json.cargo_columns === undefined ? DEFAULT_COLUMNS : json.cargo_columns;
  if (!Array.isArray(cols)) fail('"cargo_columns" is not an array');
  const ix = {}; cols.forEach((c, i) => { ix[c] = i; });
  const missing = REQUIRED.filter(c => ix[c] === undefined); if (missing.length) fail('cargo_columns lacks ' + missing.join(', '));
  const cargo = json.cargo.map((r, i) => {
    const w = `cargo[${i}]`; if (!Array.isArray(r) || r.length < cols.length) fail(`${w} does not match cargo_columns`);
    const g = c => r[ix[c]];
    return { id: g('id'), owner: ix.owner === undefined ? null : g('owner'), mass: num(g('mass_kg'), `${w}.mass_kg`), origin: site(g('origin'), w), dest: site(g('dest'), w),
      tReady: num(g('t_ready'), `${w}.t_ready`), tPicked: numOrNull(g('t_picked'), `${w}.t_picked`), tDelivered: numOrNull(g('t_delivered'), `${w}.t_delivered`),
      prio: num(g('priority'), `${w}.priority`), cls: String(g('cls')), stranded: !!g('stranded') };
  });
  return {
    meta: { version, legacy: json.format === undefined, engine: json.engine || (json.format === undefined ? 'python' : null), scenario: json.scenario || null,
      mechanism: json.mechanism || null, seed: json.seed ?? null, terrain: json.terrain || null, standoffKm: json.pad_standoff_km ?? null },
    siteXY: json.site_xy_m && typeof json.site_xy_m === 'object' ? json.site_xy_m : null,   // v2: site positions in terrain-pack metres
    horizon, nights, landings, plumeWindows, shelters: Array.isArray(json.shelters) ? json.shelters : [], vehicles, jobs, cargo,
    summary: json.summary || null, world: json.world || null,
  };
}
