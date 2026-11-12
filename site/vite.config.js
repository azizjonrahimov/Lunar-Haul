import { defineConfig } from 'vite';
import { join, extname } from 'node:path';
import { existsSync, readFileSync, statSync } from 'node:fs';
import { header, footer, markdown, headline, figure, icon, resultText, heroCounters, SITE, ROOT } from './lib/pages.mjs';
import { results } from './lib/results.mjs';
import { pipeline } from './lib/pipeline.mjs';
import { tex } from './lib/tex.mjs';
import { paperField, paperValue } from './lib/papers.mjs';
import { P as PROTOCOL } from './src/protocol/params.js';
import { nw } from './lib/network.mjs';
import { atcResults } from './lib/results-atc.mjs';
import { e52, e53, e55 } from './lib/protocol-data.mjs';
import { b97 } from './lib/realdata.mjs';
import { num } from './src/components/num.js';

// Public base: '/' locally; CI sets SITE_BASE from actions/configure-pages (/Lunar-Haul/ on GitHub Pages).
const base = process.env.SITE_BASE || '/';
const PAGES = ['', 'world/', 'world/trace/', 'results/', 'lab/lander/', 'lab/rover/', 'method/', 'paper/', 'data/', 'about/', 'account/', 'changelog/', 'verification/', 'vehicles/', 'simulator/', 'stories/', 'research/earth-sky/', 'atc/', 'lab/', 'protocol/', 'network/',
  'design/', 'design/stage/'];   // development pages (noindex, not in the nav)

// <!--@header-->, <!--@footer-->, <!--@md:name-->, <!--@paper:id:field--> and <!--@v:id:KEY--> (lib/papers.mjs), <!--@headline-->, <!--@results-->, <!--@pipeline--> and <!--@r:key--> (also inside markdown), <!--@icon:name-->, <!--@tex:name--> (KaTeX at build time), <!--@base--> in page HTML
function lunarsimPages() {
  return {
    name: 'lunarsim-pages',
    transformIndexHtml: {
      order: 'pre',
      handler(html, ctx) {
        return html
          .replace('<!--@header-->', () => header(base, ctx.path))
          .replace('<!--@footer-->', () => footer(base))
          .replace('<!--@headline-->', () => headline())
          .replace('<!--@hero-counters-->', () => heroCounters())
          .replace('<!--@hero-css-->', () => `<style>${readFileSync(join(SITE, 'src', 'home-hero.css'), 'utf8')}</style>`)   // inlined: one render-blocking request fewer on the home page
          .replace('<!--@results-atc-->', () => atcResults(base))   // F-56: the Lunar ATC papers' headline numbers (lib/results-atc.mjs)
          .replace('<!--@results-->', () => results(base))
          .replace(/<!--@md:([\w-]+)-->/g, (_, n) => markdown(n))
          .replace(/<!--@paper:(\w+):(\w+)-->/g, (_, id, f) => paperField(id, f))   // F-56: the Phase 5 papers, from paper/<id>/
          .replace(/<!--@v:(\w+):([\w-]+)-->/g, (_, id, k) => paperValue(id, k))
          .replace('<!--@pipeline-->', () => pipeline())
          .replace(/<!--@r:(\w+)-->/g, (_, k) => resultText(k))
          .replace(/<!--@nw:(\w+)-->/g, (_, k) => nw(k))   // F-61: /network/ numbers (lib/network.mjs)
          .replace(/<!--@e52:(\w+)-->/g, (_, k) => e52(k))   // F-56: E52 in /protocol/ problem 2 (lib/protocol-data.mjs)
          .replace(/<!--@b97:(\w+)-->/g, (_, k) => b97(k))   // F-56: B-97's real-data boxes (lib/realdata.mjs)
          .replace(/<!--@e55:([\w@.]+)-->/g, (_, k) => e55(k))   // F-56: E55 in /protocol/ problem 7 (lib/protocol-data.mjs)
          .replace(/<!--@e53:(\w+):(\w+):([\d.]+):(\d+):(\w+)-->/g, (_, g, au, hz, n, col) => e53(g, au, hz, n, col))   // F-56: E53 in /protocol/ problem 5 (lib/protocol-data.mjs)
          .replace(/<!--@pn:(\w+)-->/g, (_, k) => { if (!PROTOCOL[k]) throw new Error(`protocol: no parameter ${k}`); return num(PROTOCOL[k]); })   // F-60: /protocol/ numbers, src/protocol/params.js
          .replace(/<!--@figure:([\w-]+)-->/g, (_, n) => figure(n))
          .replace(/<!--@icon:([\w-]+)-->/g, (_, n) => icon(n))
          .replace(/<!--@tex:([\w-]+)-->/g, (_, n) => tex(n))
          .replace(/<!--@base-->/g, base);
      },
    },
    // dev only: serve the built v2 simulator (web/dist, made by web/build_web.py) under /simulator/v2/, and its engine files
    // (sim.js, worker.js, formats.js, api.js, ref.js, samples/) under /simulator/engine/ for the v3 page at /simulator/ (F-37)
    configureServer(server) {
      const dist = join(ROOT, 'web', 'dist');
      server.middlewares.use((req, res, next) => {
        const m = req.url && req.url.split('?')[0].match(/^\/simulator\/(v2|engine)(\/.*)?$/);
        if (!m) return next();
        if (!m[2]) { res.statusCode = 301; res.setHeader('Location', `/simulator/${m[1]}/`); return res.end(); }
        let f = join(dist, decodeURIComponent(m[2]));
        if (!f.startsWith(dist)) { res.statusCode = 403; return res.end(); }
        if (existsSync(f) && statSync(f).isDirectory()) f = join(f, 'index.html');
        if (!existsSync(f)) { res.statusCode = 404; return res.end('Simulator not built: run python web/build_web.py'); }
        const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json', '.css': 'text/css' };
        res.setHeader('Content-Type', types[extname(f)] || 'application/octet-stream');
        res.end(readFileSync(f));
      });
    },
  };
}

// F-40: preload the body face's Latin subset on every built page (its hashed name is only known once the bundle exists)
function preloadBodyFont() {
  return {
    name: 'lunarsim-preload-font',
    transformIndexHtml: {
      order: 'post',
      handler(html, ctx) {
        const f = ctx.bundle && Object.keys(ctx.bundle).find(n => /source-sans-3-latin-wght-normal-[^/]*\.woff2$/.test(n));
        return f ? html.replace('</head>', `<link rel="preload" href="${base}${f}" as="font" type="font/woff2" crossorigin>\n</head>`) : html;
      },
    },
  };
}

export default defineConfig({
  base,
  root: SITE,
  resolve: { alias: { '@fonts': join(SITE, 'node_modules', 'source-sans') } },
  plugins: [lunarsimPages(), preloadBodyFont()],
  build: {
    outDir: 'dist', emptyOutDir: true, target: 'es2022', assetsInlineLimit: 0, sourcemap: true,
    chunkSizeWarningLimit: 600,  // the hero chunk is three.js (~530 kB min, ~133 kB gz), loaded only where a 3D view is
    rollupOptions: {
      input: { ...Object.fromEntries(PAGES.map(p => [p.replace(/\/$/, '').replace(/\//g, '-') || 'index', join(SITE, p, 'index.html')])),
        '404': join(SITE, '404.html') },   // GitHub Pages serves 404.html for unknown paths
      // F-40: a chunk made from one module under src/<dir>/ is named <dir>-<name> (rover-lab3d-scene, stories-stage), so
      // the budgets' lazy globs (tools/ci/budgets.json) match one chunk each; shared and vendor chunks keep their names
      output: { chunkFileNames: c => { const d = c.facadeModuleId && /[\\/]src[\\/]([^\\/]+)[\\/][^\\/]+$/.exec(c.facadeModuleId); return `assets/${d ? d[1] + '-' : ''}[name]-[hash].js`; } },
    },
  },
  server: { port: 5173 },
});
