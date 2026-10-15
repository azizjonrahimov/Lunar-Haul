'use strict';
/* LunarSim interchange formats (PLAN §4). Pure functions, no DOM: usable from the console and from app.js.
   Loaded after sim.js (uses SITES for site-name validation) and before app.js. */

// ---------- Trace JSON: lunarsim-trace v1 ----------
const TRACE_FORMAT = 'lunarsim-trace', TRACE_VERSION = 1;
// Column order of legacy Python traces, which carry no `cargo_columns`. Readers look columns up by name.
const TRACE_DEFAULT_COLUMNS = ['id', 'owner', 'mass_kg', 'origin', 'dest', 't_ready', 't_picked', 't_delivered', 'priority', 'cls', 'stranded'];
const TRACE_REQUIRED_COLUMNS = ['id', 'mass_kg', 'origin', 'dest', 't_ready', 't_picked', 't_delivered', 'priority', 'cls', 'stranded'];

class FormatError extends Error { constructor(msg) { super(msg); this.name = 'FormatError'; } }

/* readTrace(json) -> replay model
   Accepts lunarsim-trace v1 with or without the header keys (legacy Python files are treated as v1).
   Model: { meta:{format, version, engine, scenario, mechanism, seed, legacy}, horizon, nights, landings,
            vehicles:[{id, owner, cls, autonomy, cap, nightOps}], jobs (sorted by t0),
            cargo:[{id, owner, mass, origin, dest, tReady, tPicked, tDelivered, prio, cls, stranded, tLanded}],
            summary, raw } — the shape the Replay tab and the timeline chart draw from. Throws FormatError. */
function readTrace(json) {
  const fail = m => { throw new FormatError(m); };
  if (typeof json === 'string') { try { json = JSON.parse(json); } catch (e) { fail('not valid JSON (' + e.message + ')'); } }
  if (!json || typeof json !== 'object' || Array.isArray(json)) fail('expected a JSON object');
  if (json.format !== undefined && json.format !== TRACE_FORMAT) fail(`format is "${json.format}", expected "${TRACE_FORMAT}"`);
  if (json.version !== undefined && json.version !== TRACE_VERSION) fail(`unsupported ${TRACE_FORMAT} version ${json.version} (this page reads v${TRACE_VERSION})`);
  const horizon = json.horizon_h;
  if (typeof horizon !== 'number' || !(horizon > 0)) fail('missing or invalid "horizon_h"');
  for (const k of ['nights', 'landings', 'vehicles', 'jobs', 'cargo']) if (!Array.isArray(json[k])) fail(`missing array "${k}"`);
  const known = new Set(SITES.map(s => s.name)), site = (name, where) => { if (!known.has(name)) fail(`unknown site "${name}" in ${where}`); return name; };
  const num = (x, where) => { if (typeof x !== 'number' || !Number.isFinite(x)) fail(`expected a number in ${where}, got ${JSON.stringify(x)}`); return x; };
  const numOrNull = (x, where) => (x === null || x === undefined) ? null : num(x, where);

  const nights = json.nights.map((n, i) => { if (!Array.isArray(n) || n.length < 2) fail(`nights[${i}] is not [t_start, t_end]`); return [num(n[0], `nights[${i}]`), num(n[1], `nights[${i}]`)]; });
  const landings = json.landings.map((l, i) => { if (!Array.isArray(l) || l.length < 3) fail(`landings[${i}] is not [t, lander, pad]`); return [num(l[0], `landings[${i}]`), String(l[1]), site(l[2], `landings[${i}]`)]; });
  const vehicles = json.vehicles.map((v, i) => {
    if (!v || typeof v !== 'object') fail(`vehicles[${i}] is not an object`);
    const cap = v.capacity !== undefined ? v.capacity : v.cap;
    return { id: num(v.id, `vehicles[${i}].id`), owner: String(v.owner), cls: String(v.cls), autonomy: v.autonomy || null, cap: numOrNull(cap, `vehicles[${i}].capacity`), nightOps: !!v.night_ops };
  });
  const vids = new Set(vehicles.map(v => v.id));
  const jobs = json.jobs.map((j, i) => {
    const w = `jobs[${i}]`;
    if (!j || typeof j !== 'object' || !Array.isArray(j.segments)) fail(`${w} has no "segments" array`);
    const team = Array.isArray(j.team) ? j.team : [j.veh];
    for (const id of team) if (!vids.has(id)) fail(`${w} refers to unknown vehicle ${id}`);
    const segments = j.segments.map((s, k) => { if (!Array.isArray(s) || s.length < 5) fail(`${w}.segments[${k}] is not [from, to, t_start, t_end, load_kg]`);
      return [site(s[0], w), site(s[1], w), num(s[2], w), num(s[3], w), num(s[4], w)]; });
    return { kind: j.kind || 'job', veh: j.veh, team, t0: num(j.t0, `${w}.t0`), t1: num(j.t1, `${w}.t1`), segments, items: Array.isArray(j.items) ? j.items : [] };
  }).map((j, i) => [j, i]).sort((a, b) => (a[0].t0 - b[0].t0) || (a[1] - b[1])).map(x => x[0]);  // stable by start time: vehiclePos() scans in order

  const cols = json.cargo_columns === undefined ? TRACE_DEFAULT_COLUMNS : json.cargo_columns;
  if (!Array.isArray(cols)) fail('"cargo_columns" is not an array');
  const ix = {}; cols.forEach((c, i) => { ix[c] = i; });
  const missing = TRACE_REQUIRED_COLUMNS.filter(c => ix[c] === undefined); if (missing.length) fail('cargo_columns lacks ' + missing.join(', '));
  const cargo = json.cargo.map((r, i) => {
    const w = `cargo[${i}]`;
    if (!Array.isArray(r)) fail(`${w} is not a row (cargo must be arrays matching cargo_columns)`);
    if (r.length < cols.length) fail(`${w} has ${r.length} values for ${cols.length} columns`);
    const g = c => ix[c] === undefined ? undefined : r[ix[c]];
    return { id: g('id'), owner: g('owner') === undefined ? null : g('owner'), mass: num(g('mass_kg'), `${w}.mass_kg`), origin: site(g('origin'), w), dest: site(g('dest'), w),
      tReady: num(g('t_ready'), `${w}.t_ready`), tPicked: numOrNull(g('t_picked'), `${w}.t_picked`), tDelivered: numOrNull(g('t_delivered'), `${w}.t_delivered`),
      prio: num(g('priority'), `${w}.priority`), cls: String(g('cls')), stranded: !!g('stranded'), tLanded: numOrNull(g('t_landed'), `${w}.t_landed`) };
  });
  const meta = { format: TRACE_FORMAT, version: TRACE_VERSION, legacy: json.format === undefined,
    engine: json.engine || (json.format === undefined ? 'python' : null), scenario: json.scenario || null, mechanism: json.mechanism || null,
    seed: json.seed === undefined ? null : json.seed };
  return { meta, horizon, nights, landings, vehicles, jobs, cargo, summary: json.summary || null, raw: json };
}

/* traceToJson(model) -> lunarsim-trace v1 object for export: the file as read (or as the engine produced it), with the
   header keys filled in so a legacy Python file comes out versioned. */
function traceToJson(model) {
  const raw = model.raw, m = model.meta;
  return Object.assign({ format: TRACE_FORMAT, version: TRACE_VERSION, engine: m.engine, scenario: m.scenario, mechanism: m.mechanism, seed: m.seed }, raw, { format: TRACE_FORMAT, version: TRACE_VERSION });
}
