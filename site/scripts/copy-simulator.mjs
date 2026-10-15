// After `vite build`: rebuild the existing simulator (web/build_web.py) and copy web/dist into site/dist/simulator/.
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
const dest = join(SITE, 'dist', 'simulator');
rmSync(dest, { recursive: true, force: true });
cpSync(join(ROOT, 'web', 'dist'), dest, { recursive: true });
console.log('copy-simulator: web/dist ->', dest);
