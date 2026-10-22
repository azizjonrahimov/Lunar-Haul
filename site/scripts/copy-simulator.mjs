// After `vite build`: rebuild the simulator (web/build_web.py), copy web/dist into site/dist/simulator/v2/ (the v2 page, kept
// for one release) and its engine files into site/dist/simulator/engine/ (read by the v3 page that Vite builds at /simulator/).
// Python: $PYTHON, else the repo's .venv, else `python` on PATH (CI).
import { existsSync, cpSync, rmSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SITE = join(dirname(fileURLToPath(import.meta.url)), '..');
const ROOT = join(SITE, '..');
const venv = process.platform === 'win32' ? join(ROOT, '.venv', 'Scripts', 'python.exe') : join(ROOT, '.venv', 'bin', 'python');
const python = process.env.PYTHON || (existsSync(venv) ? venv : 'python');

execFileSync(python, [join(ROOT, 'web', 'build_web.py')], { stdio: 'inherit', cwd: ROOT });
const dest = join(SITE, 'dist', 'simulator', 'v2'), engine = join(SITE, 'dist', 'simulator', 'engine');
for (const d of [dest, engine]) rmSync(d, { recursive: true, force: true });
cpSync(join(ROOT, 'web', 'dist'), dest, { recursive: true });
cpSync(join(ROOT, 'web', 'dist'), engine, { recursive: true, filter: f => !/index\.html$|app\.js$/.test(f) });
console.log('copy-simulator: web/dist ->', dest, 'and the engine files ->', engine);
