// Stages data the site reads at run time into site/public/ (git-ignored) before dev and build:
//   terrain/hero/   height_20m.png + meta.json (+ sites.json when present), for the hero and /world
//   world/          site_graph.json (the DES site graph) and samples/*.json (bundled traces)
//   detect-gpu/     detect-gpu's benchmark tables, self-hosted so tiering makes no third-party request
//   catalog/        catalog-v1.json, the vehicle and site catalogue (B-30)
//   terrain/hero/v2/ the B-34 horizon map, normals and 5 m height patches; comms/ Earth's track and the leg link samples (R-1)
//   scenes/         lunarsim-scene packages (B-31) and gallery.json (B-36), for /world/
//   story-data/     resolved guided stories (B-35), for /stories/
// Terrain source: data/terrain/connecting_ridge/ (LEAD, B-9); fallback site/.terrain-dev/ (scripts/make_dev_terrain.py).
import { existsSync, mkdirSync, copyFileSync, readFileSync, readdirSync, cpSync, writeFileSync, statSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SITE = join(dirname(fileURLToPath(import.meta.url)), '..');
const ROOT = join(SITE, '..');
const PUB = join(SITE, 'public');
const FILES = ['height_20m.png', 'meta.json'];
const CANDIDATES = [join(ROOT, 'data', 'terrain', 'connecting_ridge'), join(SITE, '.terrain-dev')];

const src = CANDIDATES.find(d => FILES.every(f => existsSync(join(d, f))));
if (!src) {
  console.error('prepare-data: no terrain pack. Expected data/terrain/connecting_ridge/ or run\n' +
    '  .venv\\Scripts\\python site\\scripts\\make_dev_terrain.py');
  process.exit(1);
}
const out = join(PUB, 'terrain', 'hero');
mkdirSync(out, { recursive: true });
for (const f of FILES.concat(existsSync(join(src, 'sites.json')) ? ['sites.json'] : [])) copyFileSync(join(src, f), join(out, f));
const meta = JSON.parse(readFileSync(join(out, 'meta.json'), 'utf8'));
console.log(`prepare-data: terrain "${meta.name}" (${meta.site_id}) from ${src}${meta.dev_standin ? ' [dev stand-in]' : ''}${existsSync(join(out, 'sites.json')) ? ', with sites.json' : ', no sites.json (provisional layout)'}`);

const world = join(PUB, 'world', 'samples');
mkdirSync(world, { recursive: true });
copyFileSync(join(ROOT, 'data', 'site_graph.json'), join(PUB, 'world', 'site_graph.json'));
const traces = join(ROOT, 'data', 'sample_traces');
for (const f of readdirSync(traces).filter(f => f.endsWith('.json'))) copyFileSync(join(traces, f), join(world, f));

cpSync(join(SITE, 'node_modules', 'detect-gpu', 'dist', 'benchmarks'), join(PUB, 'detect-gpu', 'benchmarks'), { recursive: true });

// lander lab: policy cards (+ .check.json) and landing-outcome tables, plus an index the page reads first
const pol = join(ROOT, 'data', 'policies'), labOut = join(PUB, 'lab', 'policies');
mkdirSync(labOut, { recursive: true });
const polFiles = existsSync(pol) ? readdirSync(pol).filter(f => f.endsWith('.json')) : [];
for (const f of polFiles) copyFileSync(join(pol, f), join(labOut, f));
// rover lab: the learned driver's network (its card and check file are among the .json above); the page fetches it,
// and Vite's hashed onnxruntime-web .wasm asset, only when the learned driver is chosen
const onnx = existsSync(pol) ? readdirSync(pol).filter(f => f.endsWith('.onnx')) : [];
for (const f of onnx) copyFileSync(join(pol, f), join(labOut, f));
console.log(`prepare-data: onnx ${onnx.join(', ') || 'none'}`);
const index = { policies: polFiles.filter(f => /^lander_.*\.json$/.test(f) && !f.endsWith('.check.json')).map(f => f.replace(/\.json$/, '')),
  outcomes: polFiles.filter(f => /^outcomes_.*\.json$/.test(f)).map(f => f.replace(/^outcomes_|\.json$/g, '')) };
writeFileSync(join(labOut, 'index.json'), JSON.stringify(index, null, 1));
console.log(`prepare-data: lab policies ${index.policies.join(', ') || 'none'}; outcome tables ${index.outcomes.join(', ') || 'none'}`);

// verification page: the recorded Phase 4 checks (data/verification/verification-v1.json, phase4[])
const verRec = join(ROOT, 'data', 'verification', 'verification-v1.json');
if (existsSync(verRec)) { mkdirSync(join(PUB, 'verify'), { recursive: true }); copyFileSync(verRec, join(PUB, 'verify', 'verification-v1.json')); }
// verification page: BACKEND's lander parity fixture (tests/fixtures/lander_parity.json)
const fixture = join(ROOT, 'tests', 'fixtures', 'lander_parity.json');
if (existsSync(fixture)) { mkdirSync(join(PUB, 'verify'), { recursive: true }); copyFileSync(fixture, join(PUB, 'verify', 'lander_parity.json')); }
const driverFixture = join(ROOT, 'tests', 'fixtures', 'rover_driver_parity.json');   // learned rover driver (B-18)
if (existsSync(driverFixture)) { mkdirSync(join(PUB, 'verify'), { recursive: true }); copyFileSync(driverFixture, join(PUB, 'verify', 'rover_driver_parity.json')); }

// rover lab: the 5 m layers, one small file per driving-table leg, and the four daylight shadow grids precomputed
// with the page's own port of terrain.cast_shadow (bit-packed, row 0 = south), so the page does not spend ~5 s on them
const roverOut = join(PUB, 'lab', 'rover');
mkdirSync(join(roverOut, 'legs'), { recursive: true });
for (const f of ['height_5m.png', 'slope_20m.png', 'hillshade_20m.png']) if (existsSync(join(src, f))) copyFileSync(join(src, f), join(out, f));
// one small file per leg plus an index: the expert's driving-v1.json and, when it exists, the learned driver's table
function sliceTable(src, dir, indexName, label) {
  if (!existsSync(src)) return;
  const d = JSON.parse(readFileSync(src, 'utf8')), file = k => k.replace('->', '__').replace(/@/g, '_at_').replace(/[^\w.-]/g, '_') + '.json';
  mkdirSync(join(roverOut, dir), { recursive: true });
  for (const [k, leg] of Object.entries(d.legs)) writeFileSync(join(roverOut, dir, file(k)), JSON.stringify(leg));
  const { legs, ...head } = d;
  writeFileSync(join(roverOut, indexName), JSON.stringify({ ...head, legs: Object.fromEntries(Object.keys(legs).map(k => [k, file(k)])) }));
  console.log(`prepare-data: ${label} ${Object.keys(legs).length} legs sliced`);
}
sliceTable(join(ROOT, 'data', 'driving', 'driving-v1.json'), 'legs', 'driving-index.json', 'driving table');
sliceTable(join(ROOT, 'data', 'driving', 'driving-v1-learned.json'), 'learned', 'learned-index.json', 'learned-driver table');
// F-40: every leg's route for every lighting (B-32, data/driving/routes-v1.json), one small file per leg, so the lab need not
// run A* when it loads (about 1 s of main thread). The file's geometry is the planner's polyline subdivided to <= 10 m;
// it is reduced here to the points the lab's plan() returns: the end points and the 20 m cell centres between them.
const routesSrc = join(ROOT, 'data', 'driving', 'routes-v1.json');
if (existsSync(routesSrc)) {
  const RJ = JSON.parse(readFileSync(routesSrc, 'utf8')), q = RJ.encoding.xy_z_s_unit_m, file = k => k.replace('->', '__').replace(/@/g, '_at_').replace(/[^\w.-]/g, '_') + '.json';
  const decode = g => { let x = g.x0, y = g.y0; const pts = [[x * q, y * q]]; for (let i = 0; i < g.dx.length; i++) { x += g.dx[i]; y += g.dy[i]; pts.push([x * q, y * q]); } return pts; };
  // B-32 merged straight runs before subdividing, so the cell centres inside a run are rebuilt: the turning points are cell
  // centres (or the end points), and a straight run between two centres steps 20 m along an axis or a diagonal
  const centre = v => Math.abs((((v % 20) + 20) % 20) - 10) < 0.06, isC = pt => centre(pt[0]) && centre(pt[1]);
  const turns = pts => {
    const T = pts.filter((pt, i) => {
      if (i === 0 || i === pts.length - 1) return true;
      const ax = pt[0] - pts[i - 1][0], ay = pt[1] - pts[i - 1][1], bx = pts[i + 1][0] - pt[0], by = pts[i + 1][1] - pt[1];
      return Math.abs(Math.atan2(ax * by - ay * bx, ax * bx + ay * by)) > 0.02 || (isC(pt) && !isC(pts[i - 1]) && i === 1);
    });
    const out = [T[0]];
    for (let k = 1; k < T.length; k++) {
      const P = T[k - 1], Q = T[k], dx = Q[0] - P[0], dy = Q[1] - P[1];
      if (isC(P) && isC(Q)) { const n = Math.round(Math.max(Math.abs(dx), Math.abs(dy)) / 20); for (let j = 1; j < n; j++) out.push([P[0] + dx * j / n, P[1] + dy * j / n]); }
      out.push(Q);
    }
    return out.map(([x, y]) => [Math.round(x * 10) / 10, Math.round(y * 10) / 10]);
  };
  mkdirSync(join(roverOut, 'routes'), { recursive: true });
  for (const [k, byLight] of Object.entries(RJ.legs)) writeFileSync(join(roverOut, 'routes', file(k)), JSON.stringify(Object.fromEntries(Object.entries(byLight).map(([l, r]) => [l, turns(decode(RJ.geoms[r.geom]))]))));
  writeFileSync(join(roverOut, 'routes-index.json'), JSON.stringify({ source: 'data/driving/routes-v1.json (B-32)', generated: RJ.generated, legs: Object.fromEntries(Object.keys(RJ.legs).map(k => [k, file(k)])) }));
  console.log(`prepare-data: rover routes, ${Object.keys(RJ.legs).length} legs x ${RJ.lighting.length} lightings`);
}
if (existsSync(join(src, 'height_5m.png')) && !meta.dev_standin) {
  const { RoverTerrain } = await import('../src/rover/terrain.js'), { decodePngGray } = await import('../src/terrain.js');
  const ld = (f, dd) => { const b = readFileSync(join(src, f)); return decodePngGray(b.buffer.slice(b.byteOffset, b.byteOffset + b.length), dd); };
  const stamp = join(roverOut, 'shadow.stamp'), key = `${statSync(join(src, 'height_20m.png')).mtimeMs}|${meta.site_id}`;
  if (!existsSync(stamp) || readFileSync(stamp, 'utf8') !== key) {
    const t0 = Date.now(), t = new RoverTerrain(meta, await ld('height_5m.png', 16), await ld('height_20m.png', 16), await ld('slope_20m.png', 8));
    for (const az of [0, 90, 180, 270]) {
      const g = t.shadowGrid(az), bits = new Uint8Array(Math.ceil(g.length / 8));
      for (let i = 0; i < g.length; i++) if (g[i]) bits[i >> 3] |= 1 << (i & 7);
      writeFileSync(join(roverOut, `shadow_${az}.bin`), bits);
    }
    writeFileSync(stamp, key);
    console.log(`prepare-data: rover shadow grids computed in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
  }
}
// /verification/ phase 5 (F-55): B-79's recorded Python checks, when the file exists
const vv5 = join(ROOT, 'results', 'vv_phase5.json');
if (existsSync(vv5)) { mkdirSync(join(PUB, 'verify'), { recursive: true }); copyFileSync(vv5, join(PUB, 'verify', 'vv_phase5.json')); console.log('prepare-data: phase-5 checks staged'); }

// /atc/ (F-54): B-72's smoke run of the decision places, read by the market walk-through
const atcSmoke = join(ROOT, 'results', 'ATC_regimes_smoke.json');
if (existsSync(atcSmoke)) { mkdirSync(join(PUB, 'atc'), { recursive: true }); copyFileSync(atcSmoke, join(PUB, 'atc', 'ATC_regimes_smoke.json')); console.log('prepare-data: ATC smoke run staged'); }

// /results: figure PNGs (PDFs link to the repository) and the small summary tables; whatever exists is staged
const figs = join(ROOT, 'figures'), resOut = join(PUB, 'results');
mkdirSync(join(resOut, 'figures'), { recursive: true }); mkdirSync(join(resOut, 'data'), { recursive: true });
const pngs = existsSync(figs) ? readdirSync(figs).filter(f => /^fig\d+_[\w-]+\.png$/.test(f)) : [];
for (const f of pngs) copyFileSync(join(figs, f), join(resOut, 'figures', f));
const tables = ['table_E15.csv', 'table_E16.csv'].filter(f => existsSync(join(ROOT, 'results', f)));
for (const f of tables) copyFileSync(join(ROOT, 'results', f), join(resOut, 'data', f));
console.log(`prepare-data: results page: ${pngs.length} figures, tables ${tables.join(', ') || 'none'}`);
console.log('prepare-data: world samples, site graph and detect-gpu benchmarks staged');

// Phase 4: the vehicle and site catalogue (B-30), the one source of every vehicle number and 3D dimension on screen
const catalog = join(ROOT, 'lunarsim', 'catalog-v1.json');
if (existsSync(catalog)) {
  mkdirSync(join(PUB, 'catalog'), { recursive: true });
  copyFileSync(catalog, join(PUB, 'catalog', 'catalog-v1.json'));
  console.log(`prepare-data: catalogue ${JSON.parse(readFileSync(catalog, 'utf8')).entries.length} entries`);
} else console.warn('prepare-data: lunarsim/catalog-v1.json missing; pages that need the catalogue will say so');

// Phase 4 (B-34): terrain assets v2 (horizon map, 20 m and 5 m normals, 5 m height patches) for /world/ and the stage's
// lunar terrain; files listed in its manifest
const v2 = join(src, 'v2');
if (existsSync(join(v2, 'manifest.json'))) {
  const out2 = join(PUB, 'terrain', 'hero', 'v2'), man = JSON.parse(readFileSync(join(v2, 'manifest.json'), 'utf8'));
  mkdirSync(out2, { recursive: true });
  copyFileSync(join(v2, 'manifest.json'), join(out2, 'manifest.json'));
  const files = man.files.filter(f => ['horizon', 'normals', 'height'].includes(f.role)).map(f => f.file);
  for (const f of files) copyFileSync(join(v2, f), join(out2, f));
  console.log(`prepare-data: terrain v2, ${files.length} files (horizon map, normals, 5 m heights)`);
}

// R-1 (B-40): Earth's hourly position seen from BASE (SPICE), for the sky on on-site 3D views; gzip, decoded in the page
const earth = join(ROOT, 'data', 'comms', 'connecting_ridge', 'earth_track-v1.json.gz');
if (existsSync(earth)) { mkdirSync(join(PUB, 'comms'), { recursive: true }); copyFileSync(earth, join(PUB, 'comms', 'earth_track-v1.json.gz')); console.log('prepare-data: Earth track staged'); }
// F-41: /research/earth-sky/ reads why the strategic cell differs by start year (B-55)
const syears = join(ROOT, 'results', 'E21_strategic_years.json');
if (existsSync(syears)) { mkdirSync(join(PUB, 'research', 'earth-sky'), { recursive: true }); copyFileSync(syears, join(PUB, 'research', 'earth-sky', 'strategic-years.json')); console.log('prepare-data: strategic years staged'); }
// F-41: deliveries in the year by start year with direct links only, for the strict and the strategic fleet (E21 round 2)
const e21years = join(ROOT, 'results', 'table_E21_years_r2.csv');
if (existsSync(e21years)) {
  const [head, ...rows] = readFileSync(e21years, 'utf8').trim().split(String.fromCharCode(10)).map(l => l.trim().split(','));
  const c = k => head.indexOf(k), byMix = {};
  for (const r of rows) if (r[c('comms')] === 'dte' && r[c('metric')] === 'delivered_t_in_year' && (r[c('mix')] === 'supervised_strict' || r[c('mix')] === 'supervised_strategic')) (byMix[r[c('mix')]] ||= {})[r[c('start_year')]] = { mean: +r[c('mean')], n: +r[c('n')] };
  mkdirSync(join(PUB, 'research', 'earth-sky'), { recursive: true });
  writeFileSync(join(PUB, 'research', 'earth-sky', 'deliveries-by-year.json'), JSON.stringify({ source: 'results/table_E21_years_r2.csv', comms: 'dte', metric: 'delivered_t_in_year', by_mix: byMix }));
  console.log('prepare-data: E21 deliveries by start year staged');
}
// F-41 part 2: the skylines at BASE and at the dark route sample, and the haul road's monthly link (B-58)
const skylines = join(ROOT, 'data', 'comms', 'connecting_ridge', 'horizons_dark_sample.json');
if (existsSync(skylines)) { mkdirSync(join(PUB, 'comms'), { recursive: true }); copyFileSync(skylines, join(PUB, 'comms', 'horizons_dark_sample.json')); console.log('prepare-data: skylines at the dark sample staged'); }
// F-41 part 2: the strategic rule when help at a never-linked point is late (E21 Stage G rescue) or never comes (Stage F
// strand), with the strict reference; F-43: one real helper rover (Stage H) with its references, and why some calls wait
// over a week (E21_parking.json); only what /research/earth-sky/ shows
const fit = join(ROOT, 'results', 'E21_fit_r2.json'), parking = join(ROOT, 'results', 'E21_parking.json');
if (existsSync(fit) && existsSync(parking)) {
  const j = JSON.parse(readFileSync(fit, 'utf8')), strand = j.bounded?.cells?.find(c => c.link === 'DTE' && c.variant === 'strategic, strand on never-linked');
  const pick = m => ({ delivered_t_in_year: m.delivered_t_in_year, prio1_completion_share: m.prio1_completion_share });
  const t2028 = by => by?.['2028']?.delivered_t_in_year ?? by?.['2028'];
  const tByYear = by => Object.fromEntries(Object.entries(by).map(([y, v]) => [y, v.delivered_t_in_year ?? v]));
  const cell = label => j.helper?.cells?.find(c => c.label === label), day = cell('dedicated k=1, 24 h'), week = cell('dedicated k=1, 168 h');
  const ref = k => ({ n: j.helper.references[k].n, delivered_t_in_year: j.helper.references[k].mean.delivered_t_in_year, by_year: j.helper.references[k].by_year });
  const pk = JSON.parse(readFileSync(parking, 'utf8')), unc = pk.uncovered_calls['0|all'];
  if (j.rescue?.levels && strand && day && week) {
    mkdirSync(join(PUB, 'research', 'earth-sky'), { recursive: true });
    writeFileSync(join(PUB, 'research', 'earth-sky', 'rescue.json'), JSON.stringify({ source: 'results/E21_fit_r2.json', link: 'DTE',
      rescue: j.rescue.levels.map(l => ({ rescue_h: l.rescue_h, n: l.n, ...pick(l.mean), t_2028: t2028(l.by_year) })),
      strand: { path: 'bounded.cells', variant: strand.variant, n: strand.n, ...pick(strand.mean), t_2028: t2028(strand.by_year) },
      strict: { n: j.rescue.references.strict.n, ...pick(j.rescue.references.strict.mean) },
      helper: [day, week].map(c => ({ label: c.label, n: c.n, call_threshold_h: c.call_threshold_h, delivered_t_in_year: c.mean.delivered_t_in_year, by_year: tByYear(c.by_year),
        share_of_always_linked_by_year: c.share_of_always_linked_by_year, within_5pct_every_year: c.within_5pct_of_always_linked_every_year,
        parked_share: c.helper.busy_split_share.parked_waiting_for_earth, helps_per_run: c.helper.helps_per_run })),
      helper_refs: { strict: ref('strict'), strict_plus_one: ref('strict + 1 rover'), always: ref('always-linked strategic') },
      parking: { source: 'results/E21_parking.json', path: 'uncovered_calls["0|all"]', calls: unc.calls, uncovered_share: unc.uncovered_share,
        earth_below_every_horizon_share: unc.earth_below_lowest_candidate_horizon_share, h_until_clear_median: unc.h_until_earth_clears_lowest_horizon_q10_50_90[1],
        held_points_without_parking: pk.candidates.samples_without_working_route_point + pk.candidates.samples_without_working_grid_point } }));
    console.log('prepare-data: rescue times and the helper staged');
  }
}
// F-43: the years ahead. The dark spot's linked hours and dark spells 2028-2050 (E21_later_years.json) and the tonnes by
// start year for strict, strategic and one helper called after a day: 2028-2031 from Stage A / H (20 seeds, start year
// 2028 + seed mod 4, so 5 runs a year), 2032-2046 from Stage J (seeds 0-4); only what /research/earth-sky/ shows
const later = join(ROOT, 'results', 'E21_later_years.json');
if (existsSync(fit) && existsSync(later)) {
  const j = JSON.parse(readFileSync(fit, 'utf8')), L = JSON.parse(readFileSync(later, 'utf8')), ly = j.later_years, day = j.helper?.cells?.find(c => c.label === 'dedicated k=1, 24 h');
  const early = { strict: j.helper.references.strict.by_year, strategic: j.rescue.references.strategic.by_year, helper_24h: Object.fromEntries(Object.entries(day.by_year).map(([y, v]) => [y, v.delivered_t_in_year])) };
  const per = n => n / 4;   // the E21 year rule: start year 2028 + seed mod 4
  const nEarly = { strict: per(j.helper.references.strict.n), strategic: per(j.rescue.references.strategic.n), helper_24h: per(day.n) };
  const by = Object.fromEntries(['strict', 'strategic', 'helper_24h'].map(p => [p, {
    ...Object.fromEntries(Object.entries(early[p]).map(([y, t]) => [y, { t, n: nEarly[p], ...(p === 'helper_24h' ? { share: day.share_of_always_linked_by_year[y] } : {}) }])),
    ...Object.fromEntries(Object.entries(ly.by_policy_year[p]).map(([y, v]) => [y, { t: v.mean_t, n: v.n, ...(p === 'helper_24h' ? { share: v.share_of_always_linked } : {}) }])) }]));
  const ap = L.period_188.annual;
  mkdirSync(join(PUB, 'research', 'earth-sky'), { recursive: true });
  writeFileSync(join(PUB, 'research', 'earth-sky', 'years.json'), JSON.stringify({ source: { links: 'results/E21_later_years.json', tonnes: 'results/E21_fit_r2.json' },
    sample: 188, linked_h_by_year: L.dark_sample_188.linked_h_by_year, spells: L.dark_spells_188_over_180_days.spells,
    period: { best_yr: ap.best_period_yr, ci95_yr: ap.ci95_yr, method: ap.method },
    always: { by_year_2028_2031: j.helper.references['always-linked strategic'].by_year, t_2032_2046: ly.always_linked_t },
    by_policy_year: by, whole_dark: ly.strategic_whole_dark_years, other: ly.strategic_other_years, helper_years_below_95pct: ly.years_below_95pct_of_always_linked.helper_24h }));
  console.log('prepare-data: later years staged');
}
// F-35: hourly direct-to-Earth windows of points along every leg, for the rover lab's Earth-link posts; F-40: version 2
// (B-52, the lite file) adds the samples along each lighting's route (routes[leg][lighting]); v1 is no longer staged
const links = join(ROOT, 'data', 'comms', 'connecting_ridge', 'earth_link-v2-samples-lite.json.gz');
rmSync(join(PUB, 'comms', 'earth_link-v1-samples.json.gz'), { force: true });
if (existsSync(links)) { mkdirSync(join(PUB, 'comms'), { recursive: true }); copyFileSync(links, join(PUB, 'comms', 'earth_link-v2-samples-lite.json.gz')); console.log('prepare-data: Earth-link samples staged'); }

// F-38: resolved guided stories (B-35) for /stories/
const stories = join(ROOT, 'data', 'stories', 'resolved');
if (existsSync(join(stories, 'index.json'))) { cpSync(stories, join(PUB, 'story-data'), { recursive: true }); console.log('prepare-data: stories staged'); }

// F-36: scene packages (B-31) and the scenario gallery (B-36) for /world/; every package folder under data/scenes/
const scenes = join(ROOT, 'data', 'scenes');
if (existsSync(join(scenes, 'gallery.json'))) {
  cpSync(scenes, join(PUB, 'scenes'), { recursive: true, filter: f => !/\.md$/.test(f) });
  console.log(`prepare-data: scenes, ${readdirSync(scenes).filter(d => existsSync(join(scenes, d, 'scene.json'))).length} packages + gallery.json`);
}
