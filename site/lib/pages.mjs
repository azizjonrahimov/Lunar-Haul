// Build-time HTML for every page: shared header/footer, Lucide icons, markdown content, headline numbers.
// Used by the Vite plugin in vite.config.js (transformIndexHtml); nothing here ships to the browser.
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { marked } from 'marked';
import { num, esc } from '../src/components/num.js';

export const SITE = join(import.meta.dirname, '..');
export const ROOT = join(SITE, '..');
export const REPO = 'https://github.com/azizjonrahimov/Lunar-Haul';

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

// ---------- Phase-3 results (read at build time; any missing file leaves its values null) ----------
// E20: pooled OLS of ln(urgent mean delay) on standoff, keep-out, stand-down, dispersion and controls over every
// simulated year of E17 + E18 (results/table_E20.csv); % per unit = 100 (e^b - 1), interval = the percentile bootstrap
// over seeds mapped the same way. Lander: the outcome tables of the learned and classical CLPS controllers.
const E20 = 'results/table_E20.csv', OUT = id => `data/policies/outcomes_${id}.json`;
const BEST_LANDER = ['lander_CLPS_bc_v3_s0', 'lander_CLPS_bcml_s0'], CLASSICAL = 'classical_CLPS';
function wilson(p, n, z = 1.96) { const d = 1 + z * z / n, c = p + z * z / (2 * n), h = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return [(c - h) / d, (c + h) / d]; }
let _r3 = null;
export function results3() {
  if (_r3) return _r3;
  const r = { fit: null, lander: null };
  if (existsSync(join(ROOT, E20))) {
    const rows = csv(readFileSync(join(ROOT, E20), 'utf8')).filter(x => x.response === 'log_delay_prio1_mean_h' && x.subset === 'pooled');
    const term = t => { const x = rows.find(y => y.term === t); if (!x) return null; const pct = b => 100 * (Math.exp(+b) - 1);
      return { pct: pct(x.coef), lo: pct(x.ci_lo), hi: pct(x.ci_hi), n: +x.n, seeds: +x.n_seeds, r2: +x.r2, source: `${E20}, pooled fit of ln(urgent mean delay), term ${t}: 100(e^b − 1) with a 95% bootstrap interval over seeds; n = ${(+x.n).toLocaleString('en-GB')} simulated years, ${x.n_seeds} seeds (experiment E20)` }; };
    // since 533589f the utilisation covariate is centred (util_center): main effects are read at the typical fleet load
    const f = { standoff: term('standoff'), keepout: term('keepout'), standdown: term('standdown'), dispersion: term('log_miss'),
      utilCenter: rows.length && rows[0].util_center !== undefined && rows[0].util_center !== '' ? +rows[0].util_center : null };
    if (f.standoff && f.keepout && f.standdown && f.dispersion) r.fit = f;
  }
  const outcome = id => { const p = join(ROOT, OUT(id)); if (!existsSync(p)) return null; const t = JSON.parse(readFileSync(p, 'utf8')), s = t.summary || {};
    const n = s.n ?? t.n, pr = s.pass_rate; if (!n || pr === undefined) return null; const [lo, hi] = wilson(pr, n);
    return { id, pct: 100 * pr, lo: 100 * lo, hi: 100 * hi, n, source: `${OUT(id)}: share of ${n} dispersed CLPS landings (altimeter model on, seeds from ${t.seed0}) inside the SPLICE touchdown box, Wilson 95% interval (experiment E15)` }; };
  const best = BEST_LANDER.map(outcome).find(Boolean), classical = outcome(CLASSICAL);
  if (best && classical) r.lander = { best, classical };
  const e16 = join(ROOT, 'results', 'table_E16.csv');   // teleop calibration: largest |error| of the flat-ground speed made good vs JSC
  if (existsSync(e16)) { const fl = csv(readFileSync(e16, 'utf8')).filter(x => x.check === 'speed_made_good_vs_rtt_flat' && x.rel_err !== ''); if (fl.length) r.teleopErr = 100 * Math.max(...fl.map(x => Math.abs(+x.rel_err))); }
  return (_r3 = r);
}
const ci = t => `${pctS(t.lo)} to ${pctS(t.hi)} %`;   // 95% interval as text, with a real minus sign
const pct1 = v => v.toFixed(1), pctS = v => (v < 0 ? '−' : '') + Math.abs(v).toFixed(1);   // the copy says 'adds', so no plus sign
/* <!--@r:key--> in page copy: the same build-time values as plain text (the headline above carries the flags) */
export function resultText(key) {
  const r = results3(), f = r.fit, l = r.lander;
  const map = {
    standoff_pct: f && `${pctS(f.standoff.pct)} %`, keepout_pct: f && `${pctS(f.keepout.pct)} %`, standdown_pct: f && `${pctS(f.standdown.pct)} %`,
    dispersion_pct: f && `${pctS(f.dispersion.pct)} %`, util_center: f && f.utilCenter !== null && `${(100 * f.utilCenter).toFixed(1)} %`,
    keepout_ci: f && ci(f.keepout), standdown_ci: f && ci(f.standdown), standoff_ci: f && ci(f.standoff), dispersion_ci: f && ci(f.dispersion),
    fit_n: f && f.standoff.n.toLocaleString('en-GB'), lander_best: l && `${pct1(l.best.pct)} %`, lander_classical: l && `${pct1(l.classical.pct)} %`,
    lander_n: l && String(l.best.n), teleop_err: r.teleopErr !== undefined && `${r.teleopErr.toFixed(1)} %`,
  };
  if (!(key in map)) throw new Error(`unknown result key ${key}`);
  return map[key] ? esc(map[key]) : '<span class="stub">(pending)</span>';
}

export function headline() {
  const r = results3(), items = [], files = new Set();
  const v2 = headlineItems();   // version-2 cells: the fallback while a Phase-3 source is missing
  if (r.fit) {
    // copy for the law read at the typical fleet load (E20 after 533589f); the concave-slope figures are the paper's
    // piecewise reading of the same data (writer's notes, LEAD 03:09), not a column of the table
    const s = r.fit.standoff, k = r.fit.keepout, d = r.fit.standdown, m = r.fit.dispersion;
    items.push({ label: 'Added delay of urgent cargo per kilometre of pad standoff', html: num({ value: s.pct, unit: '% per km', flag: 'Modelled', digits: 1, source: s.source }),
      ctx: `95% interval ${ci(s)}, at the typical fleet load, every fleet and dispatch rule. The relation is concave: a log-delay slope of about 0.52 per km below 1 km and 0.10–0.19 per km beyond 2 km.` });
    items.push({ label: 'A plume keep-out radius and a stand-down add no measurable delay at these loads', html: num({ value: k.pct, unit: '% per km', flag: 'Modelled', digits: 1, source: k.source }),
      ctxHtml: `95% interval ${esc(ci(k))}; stand-down ${num({ value: d.pct, unit: '% per hour', flag: 'Modelled', digits: 1, source: d.source })}, interval ${esc(ci(d))}. The fleets, at 2–8 % utilisation, absorb the evacuations; a cost appears only in the lightest-loaded night cells at 2–3 km radii.` });
    items.push({ label: 'Added delay per e-fold of the mean landing miss', html: num({ value: m.pct, unit: '%', flag: 'Modelled', digits: 1, source: m.source }),
      ctx: `95% interval ${ci(m)}. It acts through landings off the pad: a 100 m pad absorbs today's 50 m accuracy, a 25 m pad does not.` });
    files.add(E20);
  } else {
    for (const it of v2.items.slice(0, 2)) items.push({ label: it.label, html: num(it), ctx: it.context });
    files.add(v2.file);
  }
  if (r.lander && !r.fit) {   // with the fitted law the trio is standoff, keep-out, dispersion; the lander result stays in the copy
    const b = r.lander.best, c = r.lander.classical;
    items.push({ label: 'Best learned lander inside the touchdown box', html: num({ value: b.pct, unit: '%', flag: 'Modelled', digits: 1, source: b.source }),
      ctxHtml: `Classical guidance law: ${num({ value: c.pct, unit: '%', flag: 'Modelled', digits: 1, source: c.source })}; ${b.n} dispersed landings each. Imitation of the law, given the altimeter's recent history.` });
    files.add(OUT(r.lander.best.id)); files.add(OUT(CLASSICAL));
  } else {
    if (!r.fit) { const it = v2.items[2]; items.push({ label: it.label, html: num(it), ctx: it.context }); files.add(v2.file); }
  }
  const load = r.fit && r.fit.utilCenter !== null ? ` (${(100 * r.fit.utilCenter).toFixed(1)} % mean utilisation)` : '';
  const intro = r.fit
    ? `From version 3: one fit over every simulated year of the pad-standoff, landing-dispersion and plume keep-out experiments (${r.fit.standoff.n.toLocaleString('en-GB')} years, ${r.fit.standoff.seeds} seeds), read at the typical fleet load${load}. Each number is the change in the mean delay of urgent cargo, with its 95% interval and its source.`
    : `Version 3's experiment tables are not in this build yet; ${r.lander ? 'the lander result is from version 3 and ' : ''}the other numbers are the version-2 Phase-2 base (2029–32 demand, six vehicles owned by four organisations), means over 30 simulated years with 95% confidence half-widths.`;
  return `<p class="prose">${esc(intro)}</p>
<ul class="headline">${items.map(it => `<li><span class="label">${esc(it.label)}</span>
  <span class="big">${it.html}</span><span class="ctx">${it.ctxHtml || esc(it.ctx)}</span></li>`).join('')}</ul>
<p class="small muted">Read at build time from ${[...files].map(f => `<code>${esc(f)}</code>`).join(', ')}. Every number carries its flag; hover a flag for its source (screen readers read it out).</p>`;
}
