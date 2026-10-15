// Where the nine LunarSim sites sit on the terrain, and the drivable legs between them.
// Sites and pads come from the terrain pack's sites.json (LEAD; "Assumed layout on Measured terrain"); pads use the
// trace's standoff set ("1" km for v1 traces). Without sites.json the schematic site graph (km) is centred on the
// tile and the layout is marked provisional. Legs follow the DES site graph (data/site_graph.json): a trace segment
// FROM->TO is drawn along the graph's shortest path, each edge a straight line draped on the terrain.

const LIFT_M = 2;        // draw height above the surface
const STEP_M = 40;       // drape sampling along a leg

export function buildLayout(terrain, sites, graph, standoffKey = '1', traceXY = null) {
  const pos = {}; let provisional = false, standoff = null, source = 'sites.json';
  if (traceXY) {   // a v2 trace states where its sites were (terrain-pack metres): that wins
    for (const [name, xy] of Object.entries(traceXY)) pos[name] = [+xy[0], +xy[1]];
    standoff = standoffKey; source = 'trace';
  } else if (sites && Array.isArray(sites.sites)) {
    for (const s of sites.sites) pos[s.id] = [s.xy_m[0], s.xy_m[1]];
    const sets = sites.pads || {}; standoff = sets[standoffKey] ? standoffKey : (sets['1'] ? '1' : Object.keys(sets)[0]);
    for (const [pad, xy] of Object.entries(sets[standoff] || {})) pos[pad] = [xy[0], xy[1]];
  }
  const kinds = {}; for (const s of graph.sites) kinds[s.name] = s.kind;
  const missing = graph.sites.filter(s => !pos[s.name]);
  if (missing.length) {  // provisional: schematic km layout, BASE at the tile centre
    provisional = true;
    const b = graph.sites.find(s => s.name === 'BASE'), [W, H] = terrain.sizeM;
    for (const s of missing) pos[s.name] = [W / 2 + 1000 * (s.x - b.x), H / 2 + 1000 * (s.y - b.y)];
  }
  const z = name => terrain.height(pos[name][0], pos[name][1]);
  const dist = (a, b) => Math.hypot(pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]);
  const adj = {}; for (const s of graph.sites) adj[s.name] = [];
  for (const e of graph.edges) { adj[e.a].push(e.b); adj[e.b].push(e.a); }

  const edgeCache = {};
  function edgeLine(a, b) {  // draped polyline a->b: [[x, y, z, sCumulative], ...]
    const key = a + '|' + b; if (edgeCache[key]) return edgeCache[key];
    const [x0, y0] = pos[a], [x1, y1] = pos[b], L = dist(a, b), n = Math.max(2, Math.ceil(L / STEP_M) + 1), pts = [];
    for (let i = 0; i < n; i++) { const f = i / (n - 1), x = x0 + (x1 - x0) * f, y = y0 + (y1 - y0) * f; pts.push([x, y, terrain.height(x, y) + LIFT_M, f * L]); }
    return (edgeCache[key] = pts);
  }
  const pathCache = {};
  function route(a, b) {  // Dijkstra over the graph with layout distances -> [names]
    const key = a + '|' + b; if (pathCache[key]) return pathCache[key];
    const d = {}, prev = {}, todo = new Set(Object.keys(adj)); for (const k of todo) d[k] = Infinity; d[a] = 0;
    while (todo.size) {
      let u = null; for (const k of todo) if (u === null || d[k] < d[u]) u = k;
      if (u === b || d[u] === Infinity) break; todo.delete(u);
      for (const v of adj[u]) { const nd = d[u] + dist(u, v); if (nd < d[v]) { d[v] = nd; prev[v] = u; } }
    }
    const path = [b]; while (path[0] !== a && prev[path[0]]) path.unshift(prev[path[0]]);
    if (path[0] !== a) path.unshift(a);  // disconnected: straight line
    return (pathCache[key] = path);
  }
  const legCache = {};
  function leg(a, b) {  // full draped polyline for a trace segment a->b, with cumulative length
    const key = a + '|' + b; if (legCache[key]) return legCache[key];
    if (a === b) return (legCache[key] = { pts: [[pos[a][0], pos[a][1], z(a) + LIFT_M, 0]], length: 0 });
    const names = route(a, b), pts = []; let s0 = 0;
    for (let i = 0; i + 1 < names.length; i++) {
      const e = edgeLine(names[i], names[i + 1]);
      for (let k = i === 0 ? 0 : 1; k < e.length; k++) pts.push([e[k][0], e[k][1], e[k][2], s0 + e[k][3]]);
      s0 += e[e.length - 1][3];
    }
    return (legCache[key] = { pts, length: s0 });
  }
  /* point at fraction f along leg a->b -> [x, y, z, headingRad] */
  function along(a, b, f) {
    const { pts, length } = leg(a, b); if (pts.length === 1) return [pts[0][0], pts[0][1], pts[0][2], 0];
    const s = Math.min(length, Math.max(0, f * length)); let lo = 0, hi = pts.length - 1;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (pts[m][3] <= s) lo = m; else hi = m; }
    const p = pts[lo], q = pts[hi], g = (s - p[3]) / Math.max(1e-9, q[3] - p[3]);
    return [p[0] + (q[0] - p[0]) * g, p[1] + (q[1] - p[1]) * g, p[2] + (q[2] - p[2]) * g, Math.atan2(q[0] - p[0], q[1] - p[1])];
  }
  const edges = graph.edges.map(e => edgeLine(e.a, e.b));
  return { pos, kinds, provisional, standoff, source, z, leg, along, edges, names: graph.sites.map(s => s.name), lift: LIFT_M,
    key: JSON.stringify(graph.sites.map(s => pos[s.name])) };
}
