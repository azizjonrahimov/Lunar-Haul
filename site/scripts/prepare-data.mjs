// Stages data the site reads at run time into site/public/ (git-ignored) before dev and build:
//   terrain/hero/   height_20m.png + meta.json (+ sites.json when present), for the hero and /world
//   world/          site_graph.json (the DES site graph) and samples/*.json (bundled traces)
//   detect-gpu/     detect-gpu's benchmark tables, self-hosted so tiering makes no third-party request
//   catalog/        catalog-v1.json, the vehicle and site catalogue (B-30)
//   terrain/hero/v2/ the B-34 horizon map, normals and 5 m height patches; comms/ Earth's track (R-1)
// Terrain source: data/terrain/connecting_ridge/ (LEAD, B-9); fallback site/.terrain-dev/ (scripts/make_dev_terrain.py).
import { existsSync, mkdirSync, copyFileSync, readFileSync, readdirSync, cpSync, writeFileSync, statSync } from 'node:fs';
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
