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

// ---------- Scenario JSON: lunarsim-scenario v1 (PLAN §4.2) ----------
const SCENARIO_FORMAT = 'lunarsim-scenario', SCENARIO_VERSION = 1;
const COMPACT_KEYS = ['format', 'version', 'form', 'name', 'phase', 'bulk_t_per_year', 'fleet', 'night_fraction', 'rtt_s', 'n_operators', 'other_duty_share', 'mtbf_mult', 'common_standard_share', 'marketplace'];
// page control <- scenario field (both forms use the same names for these)
const SCENARIO_SLIDERS = [['night', 'night_fraction'], ['nOps', 'n_operators'], ['duty', 'other_duty_share'], ['mtbf', 'mtbf_mult'], ['std', 'common_standard_share']];
// marketplace flags: the page writes team_lift / night_aware; PLAN's short names team / night are accepted on import
const MARKET_FLAGS = ['bundling', 'consolidate', 'team_lift', 'night_aware', 'anticipate', 'backhaul', 'priority'], MARKET_ALIASES = { team: 'team_lift', night: 'night_aware' };
const UI_OWNERS = ['NASA', 'CoA', 'CoB', 'CoC'], UI_CLASSES = ['LTV', 'HAUL', 'MICRO'], UI_AUTONOMY = ['teleop', 'supervised', 'autonomous'];
// Full-form fields the page's engine fixes at these values (makeScenario in sim.js); any other value is reported as approximated.
const FULL_FIXED = { horizon_h: 8760, night_speed_mult: 0.6, supervised_fanout: 4, failures: true, other_duty_block_h: 48, operator_cost_per_h: 1000, urgency_usd_per_h: 2000, delivered_value_per_kg: 1e6 };
const FULL_KNOWN = ['format', 'version', 'form', 'name', 'landings_per_year', 'cargo_owners', 'bulk_flows', 'fleet', 'night_fraction', 'one_way_latency_s', 'ground_delay_s', 'n_operators', 'other_duty_share', 'mtbf_mult', 'common_standard_share', 'vot_usd_per_h', 'seed'].concat(Object.keys(FULL_FIXED));

function scenarioForm(json) { return json.form !== undefined ? json.form : (json.phase !== undefined ? 'compact' : 'full'); }

/* scenarioToUi(json|string) -> { form, ui, notes }
   ui holds only the controls the file sets: { name, phase, bulk, fleet:[{owner, cls, autonomy, std}], night, rtt, nOps, duty, mtbf, std, market:{flag: bool} }.
   notes lists, in words, everything that was approximated or ignored. Throws FormatError for files it cannot use at all. */
function scenarioToUi(json) {
  const fail = m => { throw new FormatError(m); };
  if (typeof json === 'string') { try { json = JSON.parse(json); } catch (e) { fail('not valid JSON (' + e.message + ')'); } }
  if (!json || typeof json !== 'object' || Array.isArray(json)) fail('expected a JSON object');
  if (json.format !== undefined && json.format !== SCENARIO_FORMAT) fail(`format is "${json.format}", expected "${SCENARIO_FORMAT}"`);
  if (json.version !== undefined && json.version !== SCENARIO_VERSION) fail(`unsupported ${SCENARIO_FORMAT} version ${json.version} (this page reads v${SCENARIO_VERSION})`);
  const form = scenarioForm(json); if (form !== 'compact' && form !== 'full') fail(`unknown form "${form}" (expected "compact" or "full")`);
  const ui = {}, notes = [];
  const num = (k, x) => { if (typeof x !== 'number' || !Number.isFinite(x)) fail(`"${k}" must be a number, got ${JSON.stringify(x)}`); return x; };
  if (json.name !== undefined) ui.name = String(json.name);
  if (json.fleet !== undefined) ui.fleet = readFleet(json.fleet, notes, fail);
  for (const [u, k] of SCENARIO_SLIDERS) if (json[k] !== undefined) ui[u] = num(k, json[k]);

  if (form === 'compact') {
    const extra = Object.keys(json).filter(k => !COMPACT_KEYS.includes(k)); if (extra.length) notes.push(`ignored unknown field(s): ${extra.join(', ')}`);
    if (json.phase !== undefined) { if (!PHASES[json.phase]) fail(`unknown phase "${json.phase}" (expected ${Object.keys(PHASES).join(', ')})`); ui.phase = json.phase; }
    if (json.bulk_t_per_year !== undefined) ui.bulk = num('bulk_t_per_year', json.bulk_t_per_year);
    if (json.rtt_s !== undefined) ui.rtt = num('rtt_s', json.rtt_s);
    if (json.marketplace !== undefined) {
      if (!json.marketplace || typeof json.marketplace !== 'object' || Array.isArray(json.marketplace)) fail('"marketplace" must be an object of flags');
      ui.market = {}; const unknown = [];
      for (const [k, v] of Object.entries(json.marketplace)) { const key = MARKET_ALIASES[k] || k; if (MARKET_FLAGS.includes(key)) ui.market[key] = !!v; else unknown.push(k); }
      if (unknown.length) notes.push(`ignored unknown marketplace flag(s): ${unknown.join(', ')}`);
    }
    return { form, ui, notes };
  }

  // full form -> page controls
  const extra = Object.keys(json).filter(k => !FULL_KNOWN.includes(k)); if (extra.length) notes.push(`ignored field(s) the page has no control for: ${extra.join(', ')}`);
  const land = json.landings_per_year;
  if (land !== undefined) {
    if (!land || typeof land !== 'object' || Array.isArray(land)) fail('"landings_per_year" must be an object');
    const same = (a, b) => Object.keys(a).every(k => k in LANDERS) && Object.keys(LANDERS).every(k => +(a[k] || 0) === +(b[k] || 0));
    const match = Object.keys(PHASES).find(p => same(land, PHASES[p].landings));
    if (match) ui.phase = match;
    else { ui.phase = 'P2'; notes.push(`demand not representable in the page; nearest phase used (P2): landings_per_year ${JSON.stringify(land)} vs P2 ${JSON.stringify(PHASES.P2.landings)}`); }
  }
  if (json.bulk_flows !== undefined) {
    if (!Array.isArray(json.bulk_flows)) fail('"bulk_flows" must be an array');
    const flows = json.bulk_flows.map((b, i) => { if (!b || typeof b !== 'object') fail(`bulk_flows[${i}] is not an object`); num(`bulk_flows[${i}].tonnes_per_year`, b.tonnes_per_year); return b; });
    ui.bulk = flows.reduce((s, b) => s + b.tonnes_per_year, 0);
    // The page rebuilds flows from the total: phase routes scaled to it, owner NASA, from t=0 (makeScenario). Same flows?
    const phName = ui.phase || 'P2', ph = PHASES[phName], scale = ui.bulk / Math.max(1e-9, ph.bulk.reduce((s, b) => s + b[2], 0));
    const want = ui.bulk > 0 ? ph.bulk.map(b => ({ origin: b[0], dest: b[1], t: b[2] * scale, lot: b[3], prio: b[4] || 3 })) : [];
    const got = flows.filter(b => b.tonnes_per_year > 0).map(b => ({ origin: b.origin, dest: b.dest, t: b.tonnes_per_year, lot: b.lot_kg, prio: b.priority === undefined ? 3 : b.priority }));
    const key = f => f.origin + '>' + f.dest + '>' + f.lot + '>' + f.prio, ws = want.slice().sort((a, b) => key(a) < key(b) ? -1 : 1), gs = got.slice().sort((a, b) => key(a) < key(b) ? -1 : 1);
    const sameFlows = ws.length === gs.length && ws.every((w, i) => key(w) === key(gs[i]) && Math.abs(w.t - gs[i].t) <= 1e-6 * Math.max(1, w.t));
    const odd = flows.some(b => (b.owner !== undefined && b.owner !== 'NASA') || (b.start_h !== undefined && +b.start_h !== 0));
    if (!sameFlows || odd) notes.push(`bulk flows approximated: only the total ${ui.bulk} t/yr is kept, split over the ${phName} routes (${ph.bulk.map(b => b[0] + '→' + b[1]).join(', ')}; owner NASA; from t=0). The file has ${flows.map(b => `${b.origin}→${b.dest} ${b.tonnes_per_year} t/yr${b.owner && b.owner !== 'NASA' ? ' (' + b.owner + ')' : ''}${b.start_h ? ' from ' + b.start_h + ' h' : ''}`).join(', ') || 'none'}`);
  }
  if (json.one_way_latency_s !== undefined || json.ground_delay_s !== undefined) {
    const ow = json.one_way_latency_s === undefined ? 1.3 : num('one_way_latency_s', json.one_way_latency_s), gd = json.ground_delay_s === undefined ? 2.4 : num('ground_delay_s', json.ground_delay_s);
    ui.rtt = 2 * ow + gd;
  }
  if (json.cargo_owners !== undefined && JSON.stringify(json.cargo_owners) !== JSON.stringify(OWNERS)) notes.push(`custom cargo_owners ignored; the page uses ${OWNERS.join(', ')}`);
  for (const [k, v] of Object.entries(FULL_FIXED)) if (json[k] !== undefined && json[k] !== v) notes.push(`${k} = ${JSON.stringify(json[k])} not representable; the page uses ${JSON.stringify(v)}`);
  if (json.vot_usd_per_h !== undefined) { const v = json.vot_usd_per_h || {}; if (+v[1] !== 5000 || +v[2] !== 1000 || +v[3] !== 100) notes.push(`vot_usd_per_h ${JSON.stringify(v)} not representable; the page uses {"1":5000,"2":1000,"3":100}`); }
  return { form, ui, notes };
}

function readFleet(fleet, notes, fail) {
  if (!Array.isArray(fleet)) fail('"fleet" must be an array');
  const out = [];
  fleet.forEach((v, i) => {
    let f;
    if (Array.isArray(v)) { if (v.length < 3) fail(`fleet[${i}] needs at least [owner, class, autonomy]`); f = { owner: v[0], cls: v[1], autonomy: v[2], std: v[3] || 'A' }; }
    else if (v && typeof v === 'object') f = { owner: v.owner, cls: v.cls, autonomy: v.autonomy, std: v.std || 'A' };
    else fail(`fleet[${i}] is neither an array nor an object`);
    if (!UI_CLASSES.includes(f.cls)) { notes.push(`fleet[${i}] dropped: unknown vehicle class "${f.cls}"`); return; }
    if (!UI_AUTONOMY.includes(f.autonomy)) { notes.push(`fleet[${i}] dropped: unknown autonomy "${f.autonomy}"`); return; }
    if (!UI_OWNERS.includes(f.owner)) notes.push(`fleet[${i}] owner "${f.owner}" is kept for runs but the fleet editor can only show ${UI_OWNERS.join(', ')}`);
    if (f.std !== 'A') notes.push(`fleet[${i}] interface standard "${f.std}" is kept but not editable in the page`);
    out.push({ owner: String(f.owner), cls: f.cls, autonomy: f.autonomy, std: String(f.std) });
  });
  return out;
}

/* uiToScenario(ui) -> lunarsim-scenario v1, compact form. ui has every control set (the shape scenarioToUi returns). */
function uiToScenario(ui) {
  const market = {}; for (const k of MARKET_FLAGS) market[k] = !!(ui.market || {})[k];
  return { format: SCENARIO_FORMAT, version: SCENARIO_VERSION, form: 'compact', name: ui.name || 'lunarsim-live', phase: ui.phase, bulk_t_per_year: ui.bulk,
    fleet: ui.fleet.map(f => ({ owner: f.owner, cls: f.cls, autonomy: f.autonomy, std: f.std || 'A' })),
    night_fraction: ui.night, rtt_s: ui.rtt, n_operators: ui.nOps, other_duty_share: ui.duty, mtbf_mult: ui.mtbf, common_standard_share: ui.std, marketplace: market };
}
