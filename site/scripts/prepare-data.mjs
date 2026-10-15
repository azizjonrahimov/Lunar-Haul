// Stages data the site reads at run time into site/public/ (git-ignored) before dev and build:
//   terrain/hero/   height_20m.png + meta.json (+ sites.json when present), for the hero and /world
//   world/          site_graph.json (the DES site graph) and samples/*.json (bundled traces)
//   detect-gpu/     detect-gpu's benchmark tables, self-hosted so tiering makes no third-party request
// Terrain source: data/terrain/connecting_ridge/ (LEAD, B-9); fallback site/.terrain-dev/ (scripts/make_dev_terrain.py).
import { existsSync, mkdirSync, copyFileSync, readFileSync, readdirSync, cpSync } from 'node:fs';
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
console.log('prepare-data: world samples, site graph and detect-gpu benchmarks staged');
