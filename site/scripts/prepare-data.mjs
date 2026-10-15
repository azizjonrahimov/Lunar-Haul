// Stages data the site reads at run time into site/public/ (git-ignored) before dev and build:
//   terrain/hero/   height_20m.png + meta.json (+ sites.json when present), for the hero and /world
//   world/          site_graph.json (the DES site graph) and samples/*.json (bundled traces)
//   detect-gpu/     detect-gpu's benchmark tables, self-hosted so tiering makes no third-party request
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
// trace v2 test fixture from B-12 (P2-4-vehicles, 2,500 h, all Phase-3 features on) until a v2 sample lands in data/sample_traces
const v2 = join(ROOT, 'tests', 'fixtures', 'trace_v2_sample.json');
if (existsSync(v2)) copyFileSync(v2, join(world, 'v2_fixture.json'));

cpSync(join(SITE, 'node_modules', 'detect-gpu', 'dist', 'benchmarks'), join(PUB, 'detect-gpu', 'benchmarks'), { recursive: true });

// lander lab: policy cards (+ .check.json) and landing-outcome tables, plus an index the page reads first
const pol = join(ROOT, 'data', 'policies'), labOut = join(PUB, 'lab', 'policies');
mkdirSync(labOut, { recursive: true });
const polFiles = existsSync(pol) ? readdirSync(pol).filter(f => f.endsWith('.json')) : [];
for (const f of polFiles) copyFileSync(join(pol, f), join(labOut, f));
const index = { policies: polFiles.filter(f => /^lander_.*\.json$/.test(f) && !f.endsWith('.check.json')).map(f => f.replace(/\.json$/, '')),
  outcomes: polFiles.filter(f => /^outcomes_.*\.json$/.test(f)).map(f => f.replace(/^outcomes_|\.json$/g, '')) };
writeFileSync(join(labOut, 'index.json'), JSON.stringify(index, null, 1));
console.log(`prepare-data: lab policies ${index.policies.join(', ') || 'none'}; outcome tables ${index.outcomes.join(', ') || 'none'}`);

// verification page: BACKEND's lander parity fixture (tests/fixtures/lander_parity.json)
const fixture = join(ROOT, 'tests', 'fixtures', 'lander_parity.json');
if (existsSync(fixture)) { mkdirSync(join(PUB, 'verify'), { recursive: true }); copyFileSync(fixture, join(PUB, 'verify', 'lander_parity.json')); }

// rover lab: the 5 m layers, one small file per driving-table leg, and the four daylight shadow grids precomputed
// with the page's own port of terrain.cast_shadow (bit-packed, row 0 = south), so the page does not spend ~5 s on them
const roverOut = join(PUB, 'lab', 'rover');
mkdirSync(join(roverOut, 'legs'), { recursive: true });
for (const f of ['height_5m.png', 'slope_20m.png', 'hillshade_20m.png']) if (existsSync(join(src, f))) copyFileSync(join(src, f), join(out, f));
const drivingPath = join(ROOT, 'data', 'driving', 'driving-v1.json');
if (existsSync(drivingPath)) {
  const d = JSON.parse(readFileSync(drivingPath, 'utf8')), file = k => k.replace('->', '__').replace(/@/g, '_at_').replace(/[^\w.-]/g, '_') + '.json';
  for (const [k, leg] of Object.entries(d.legs)) writeFileSync(join(roverOut, 'legs', file(k)), JSON.stringify(leg));
  const { legs, ...head } = d;
  writeFileSync(join(roverOut, 'driving-index.json'), JSON.stringify({ ...head, legs: Object.fromEntries(Object.keys(legs).map(k => [k, file(k)])) }));
  console.log(`prepare-data: driving table ${Object.keys(legs).length} legs sliced`);
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
console.log('prepare-data: world samples, site graph and detect-gpu benchmarks staged');
