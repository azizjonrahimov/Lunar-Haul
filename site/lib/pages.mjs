// Build-time HTML for every page: shared header/footer, Lucide icons, markdown content, headline numbers.
// Used by the Vite plugin in vite.config.js (transformIndexHtml); nothing here ships to the browser.
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { marked } from 'marked';
import { num, esc } from '../src/components/num.js';

export const SITE = join(import.meta.dirname, '..');
export const ROOT = join(SITE, '..');
export const REPO = 'https://github.com/azizjonrahimov/lunar-logistics-research';

// ---------- icons (Lucide, ISC) ----------
const iconCache = {};
export function icon(name, cls = 'icon') {
  if (!iconCache[name]) {
    const svg = readFileSync(join(SITE, 'node_modules', 'lucide-static', 'icons', `${name}.svg`), 'utf8');
    iconCache[name] = svg.replace(/<!--[\s\S]*?-->/g, '').replace(/\s*\n\s*/g, ' ').trim()
      .replace(/class="[^"]*"/, '').replace(/\s(width|height)="24"/g, '');
  }
  return iconCache[name].replace('<svg', `<svg class="${cls}" aria-hidden="true" focusable="false"`);
}

// ---------- navigation ----------
export const NAV = [
  ['world/', 'World'], ['results/', 'Results'], ['lab/lander/', 'Lander lab'], ['lab/rover/', 'Rover lab'], ['simulator/', 'Simulator'],
  ['method/', 'Method'], ['paper/', 'Paper'], ['data/', 'Data'], ['about/', 'About'],
];
export const FOOT = [['verification/', 'Verification'], ['changelog/', 'Changelog'], ['account/', 'Account'], ['simulator/', 'Simulator (v2)']];

export function header(base, path) {
  const here = path.replace(/^\//, '').replace(/index\.html$/, '');
  const items = NAV.map(([href, label]) => `<li><a href="${base}${href}"${here === href ? ' aria-current="page"' : ''}>${label}</a></li>`).join('');
  return `<a class="skip" href="#main">Skip to content</a>
<header class="site-header"><div class="wrap bar">
  <a class="brand" href="${base}"${here === '' ? ' aria-current="page"' : ''}>LunarHaul <span>· lunar surface logistics</span></a>
  <button class="theme-btn menu-btn" type="button" aria-expanded="false" aria-controls="site-nav" data-menu>${icon('menu')}<span class="visually-hidden">Menu</span></button>
  <nav aria-label="Main"><ul class="nav" id="site-nav">${items}</ul></nav>
  <button class="theme-btn" type="button" data-theme-toggle title="Switch light/dark theme">${icon('sun', 'icon i-light')}${icon('moon', 'icon i-dark')}<span class="visually-hidden">Switch light or dark theme</span></button>
</div></header>`;
}

export function footer(base) {
  const links = FOOT.map(([href, label]) => `<a href="${base}${href}">${label}</a>`).join(' · ');
  return `<footer class="site-footer"><div class="wrap cols">
  <div>
    <p class="tagline">Representative vehicle models · NASA data, credited</p>
    <p>Terrain: Lunar Orbiter Laser Altimeter (LOLA) digital elevation models from NASA Goddard's Planetary Geodesy Data Archive (PGDA). Vehicles and landers are parametric, representative models, not any company's design. No NASA insignia are used.</p>
  </div>
  <div>
    <p>${links}</p>
    <p><a href="${REPO}">Source code</a> · MIT licence · <a href="${base}paper/">Cite</a></p>
  </div>
</div></footer>`;
}

// ---------- markdown pages ----------
export function markdown(name) {
  const p = join(SITE, 'content', `${name}.md`);
  if (!existsSync(p)) return `<p class="stub">Content file content/${esc(name)}.md is missing.</p>`;
  const src = readFileSync(p, 'utf8').replace(/^---[\s\S]*?---\s*/, '');  // drop optional front matter
  return marked.parse(src, { gfm: true });
}

// ---------- headline numbers ----------
// results/table_main.csv is the paper's main table (experiments/make_figures.py): one row per phase x mechanism,
// cells "mean ± 95% CI half-width" over the 30 E1 seeds. The landing page shows three Phase-2 cells.
export function csv(text) {
  const rows = []; let row = [], cell = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; } else if (c === '"') q = false; else cell += c; }
    else if (c === '"') q = true; else if (c === ',') { row.push(cell); cell = ''; }
    else if (c === '\n' || c === '\r') { if (c === '\r' && text[i + 1] === '\n') i++; row.push(cell); rows.push(row); row = []; cell = ''; }
    else cell += c;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  const [head, ...body] = rows.filter(r => r.length > 1 || r[0]);
  return body.map(r => Object.fromEntries(head.map((h, i) => [h.trim(), (r[i] ?? '').trim()])));
}

const MAIN = 'results/table_main.csv';
export function headlineItems() {
  const rows = csv(readFileSync(join(ROOT, MAIN), 'utf8'));
  const cell = (phase, mech, col) => {
    const r = rows.find(x => x.phase === phase && x.mechanism === mech);
    const m = r && String(r[col] || '').match(/^\s*([-+0-9.eE]+)\s*±\s*([-+0-9.eE]+)\s*$/);
    if (!m) throw new Error(`${MAIN}: no "mean ± ci" cell for ${phase} / ${mech} / ${col}`);
    return { mean: +m[1], ci: +m[2], source: `${MAIN}, ${phase} · ${mech} · ${col}: mean ± 95% CI over 30 seeds (experiment E1)` };
  };
  const MK = 'Marketplace (ours)', IN = 'In-house fleets';
  const d = cell('P2', MK, 'delay_prio1_mean_h'), di = cell('P2', IN, 'delay_prio1_mean_h');
  const s = cell('P2', MK, 'sl24_prio1'), si = cell('P2', IN, 'sl24_prio1');
  const c = cell('P2', MK, 'cost_per_kg_usd'), ci = cell('P2', IN, 'cost_per_kg_usd');
  return { file: MAIN, items: [
    { label: 'Mean delay of urgent cargo, pooled marketplace', value: d.mean, pm: d.ci, unit: 'h', flag: 'Modelled', digits: 1, source: d.source,
      context: `In-house fleets: ${di.mean.toFixed(1)} ± ${di.ci} h.` },
    { label: 'Urgent cargo delivered within 24 h, marketplace', value: 100 * s.mean, pm: 100 * s.ci, unit: '%', flag: 'Modelled', digits: 1, source: s.source,
      context: `In-house fleets: ${(100 * si.mean).toFixed(1)} ± ${(100 * si.ci).toFixed(1)} %.` },
    { label: 'Surface transport cost per kilogram moved, marketplace', value: c.mean, pm: c.ci, unit: 'USD/kg', flag: 'Modelled', digits: 0, source: c.source,
      context: `In-house fleets: ${ci.mean.toFixed(0)} ± ${ci.ci} USD/kg. Fleet amortisation plus operator time.` },
  ] };
}

// ---------- figures (static SVG at build time; site/src/components/figure.js adds the downloads) ----------
const FLAG_TIP = { Modelled: 'Modelled: produced by the LunarHaul simulation' };
export function figure(id) {
  if (id !== 'delay-by-rule') throw new Error(`unknown figure ${id}`);
  const rows = csv(readFileSync(join(ROOT, MAIN), 'utf8')).filter(r => r.phase === 'P2').map(r => {
    const m = String(r.delay_prio1_mean_h).match(/^\s*([-+0-9.eE]+)\s*±\s*([-+0-9.eE]+)/);
    return { phase: 'P2', mechanism: r.mechanism, delay_prio1_mean_h: +m[1], ci95_h: +m[2] };
  });
  const W = 640, rowH = 34, top = 8, left = 196, right = 70, H = top + rows.length * rowH + 34;
  const max = Math.max(...rows.map(r => r.delay_prio1_mean_h + r.ci95_h)), xMax = Math.ceil(max / 5) * 5;
  const x = v => left + (W - left - right) * v / xMax;
  const ticks = Array.from({ length: xMax / 5 + 1 }, (_, i) => i * 5);
  const bars = rows.map((r, i) => {
    const y = top + i * rowH, cy = y + rowH / 2, mk = /Marketplace/.test(r.mechanism);
    return `<g><text class="lab" x="${left - 10}" y="${cy}" text-anchor="end" dominant-baseline="middle">${esc(r.mechanism)}</text>
<rect class="${mk ? 'bar hi' : 'bar'}" x="${left}" y="${y + 7}" width="${(x(r.delay_prio1_mean_h) - left).toFixed(1)}" height="${rowH - 14}"/>
<line class="ci" x1="${x(Math.max(0, r.delay_prio1_mean_h - r.ci95_h)).toFixed(1)}" x2="${x(r.delay_prio1_mean_h + r.ci95_h).toFixed(1)}" y1="${cy}" y2="${cy}"/>
<text class="val" x="${(x(r.delay_prio1_mean_h + r.ci95_h) + 6).toFixed(1)}" y="${cy}" dominant-baseline="middle">${r.delay_prio1_mean_h.toFixed(1)} h</text></g>`;
  }).join('');
  const axis = ticks.map(t => `<line class="grid" x1="${x(t)}" x2="${x(t)}" y1="${top}" y2="${H - 26}"/><text class="tick" x="${x(t)}" y="${H - 12}" text-anchor="middle">${t}</text>`).join('');
  const svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-labelledby="fig-delay-title" aria-describedby="fig-delay-cap"><title id="fig-delay-title">Mean delay of urgent cargo by dispatch rule, Phase 2</title>${axis}${bars}</svg>`;
  const table = `<div class="visually-hidden"><table><caption>Mean delay of urgent cargo by dispatch rule, Phase 2 (hours, ±95% CI)</caption><tr><th>Rule</th><th>Mean (h)</th><th>±95% CI (h)</th></tr>${rows.map(r => `<tr><td>${esc(r.mechanism)}</td><td>${r.delay_prio1_mean_h}</td><td>${r.ci95_h}</td></tr>`).join('')}</table></div>`;   // a table ignores a 1 px width, so the wrapper hides it
  return `<figure class="fig fig-delay" data-figure="delay-by-rule" data-flag="Modelled"><div class="fig-body">${svg}</div>${table}
<figcaption id="fig-delay-cap">Mean delay of urgent (priority-1) cargo from release to delivery, Phase-2 base, hours; whiskers are 95% confidence intervals over 30 seeds. "Unconstrained fleet" is a bound with unlimited vehicles, not a rule. <span class="flag" data-flag="Modelled" title="${esc(FLAG_TIP.Modelled)}. Source: ${MAIN}">Modelled</span> Source: <code>${MAIN}</code>.</figcaption>
<script type="application/json" data-rows>${JSON.stringify(rows)}</script></figure>`;
}

export function headline() {
  const { file, items } = headlineItems();
  return `<ul class="headline">${items.map(it => `<li><span class="label">${esc(it.label)}</span>
  <span class="big">${num(it)}</span><span class="ctx">${esc(it.context)}</span></li>`).join('')}</ul>
<p class="small muted">Read at build time from <code>${esc(file)}</code>. Every number carries its flag; hover a flag for its source (screen readers read it out).</p>`;
}
