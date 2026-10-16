// Writes the paper's Figure 2 from the same spec as the /method diagram (lib/pipeline.mjs):
//   figures/v3_fig02_pipeline.svg   standalone, light theme, real <text> (font: Source Sans 3, then Arial)
//   figures/v3_fig02_pipeline.png   200 dpi (viewBox units are CSS px at 96 dpi), rendered by headless Chrome
// Usage: node site/scripts/export_pipeline.mjs   (Chrome from $CHROME, else the usual install paths)
import { spawn } from 'node:child_process';
import { existsSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { pathToFileURL } from 'node:url';
import { standaloneSvg } from '../lib/pipeline.mjs';
import { SITE, ROOT } from '../lib/pages.mjs';

const DPI = 200, OUT = join(ROOT, 'figures', 'v3_fig02_pipeline');

/* insert a pHYs chunk (pixels per metre) after IHDR so the PNG says its resolution; Chrome's screenshots carry none */
function withDpi(png, dpi) {
  const crcTable = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
  const crc = buf => { let c = 0xffffffff; for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  const ppm = Math.round(dpi / 0.0254), data = Buffer.alloc(9); data.writeUInt32BE(ppm, 0); data.writeUInt32BE(ppm, 4); data[8] = 1;
  const body = Buffer.concat([Buffer.from('pHYs'), data]), chunk = Buffer.alloc(4 + body.length + 4);
  chunk.writeUInt32BE(9, 0); body.copy(chunk, 4); chunk.writeUInt32BE(crc(body), 4 + body.length);
  const ihdrEnd = 8 + 4 + 4 + png.readUInt32BE(8) + 4;
  return Buffer.concat([png.subarray(0, ihdrEnd), chunk, png.subarray(ihdrEnd)]);
}
const svg = standaloneSvg('wide');
writeFileSync(OUT + '.svg', svg);
console.log('wrote', OUT + '.svg');

const CHROME = [process.env.CHROME, 'C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'].find(p => p && existsSync(p));
if (!CHROME) { console.error('export_pipeline: no Chrome found (set CHROME=...); the SVG was written, the PNG was not'); process.exit(1); }

const tmp = mkdtempSync(join(tmpdir(), 'pipeline-')), page = join(tmp, 'fig.html');
const font = pathToFileURL(join(SITE, 'node_modules', 'source-sans', 'WOFF2', 'VF', 'SourceSans3VF-Upright.ttf.woff2')).href;
writeFileSync(page, `<!doctype html><meta charset="utf-8"><style>@font-face { font-family: 'Source Sans 3'; font-weight: 200 900; src: url('${font}') format('woff2'); }
html, body { margin: 0; background: #fff; } svg { display: block; }</style>${svg.replace(/^<\?xml[^>]*>\s*/, '')}`);

const port = 9335, ch = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${join(tmp, 'profile')}`, '--no-first-run', '--hide-scrollbars', '--allow-file-access-from-files', 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
try {
  let tgt; for (let i = 0; i < 60 && !tgt; i++) { await sleep(250); try { tgt = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(t => t.type === 'page'); } catch (e) { /* not up yet */ } }
  if (!tgt) throw new Error('Chrome did not start');
  const ws = new WebSocket(tgt.webSocketDebuggerUrl); await new Promise(r => ws.onopen = r);
  let id = 0; const pend = {}; ws.onmessage = e => { const m = JSON.parse(e.data); if (pend[m.id]) { pend[m.id](m); delete pend[m.id]; } };
  const cmd = (method, params = {}) => new Promise(r => { pend[++id] = r; ws.send(JSON.stringify({ id, method, params })); });
  const [, w, h] = svg.match(/viewBox="0 0 (\d+) (\d+)"/).map(Number);
  await cmd('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: DPI / 96, mobile: false });
  await cmd('Page.navigate', { url: pathToFileURL(page).href }); await sleep(1500);
  const fonts = (await cmd('Runtime.evaluate', { returnByValue: true, awaitPromise: true, expression: "document.fonts.ready.then(() => document.fonts.check(\"600 13px 'Source Sans 3'\"))" })).result.result.value;
  const shot = await cmd('Page.captureScreenshot', { format: 'png', clip: { x: 0, y: 0, width: w, height: h, scale: 1 } });
  writeFileSync(OUT + '.png', withDpi(Buffer.from(shot.result.data, 'base64'), DPI));
  console.log(`wrote ${OUT}.png (${Math.round(w * DPI / 96)} × ${Math.round(h * DPI / 96)} px, ${DPI} dpi; Source Sans 3 ${fonts ? 'loaded' : 'NOT loaded, fallback font used'})`);
  ws.close();
} finally { ch.kill(); await sleep(500); try { rmSync(tmp, { recursive: true, force: true }); } catch (e) { /* Chrome may still hold the profile */ } }
