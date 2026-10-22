import { defineConfig } from 'vite';
import { join, extname } from 'node:path';
import { existsSync, readFileSync, statSync } from 'node:fs';
import { header, footer, markdown, headline, figure, icon, resultText, SITE, ROOT } from './lib/pages.mjs';
import { results } from './lib/results.mjs';
import { pipeline } from './lib/pipeline.mjs';
import { tex } from './lib/tex.mjs';

// Public base: '/' locally; CI sets SITE_BASE from actions/configure-pages (/Lunar-Haul/ on GitHub Pages).
const base = process.env.SITE_BASE || '/';
const PAGES = ['', 'world/', 'world/trace/', 'results/', 'lab/lander/', 'lab/rover/', 'method/', 'paper/', 'data/', 'about/', 'account/', 'changelog/', 'verification/', 'vehicles/',
  'design/', 'design/stage/'];   // development pages (noindex, not in the nav)

// <!--@header-->, <!--@footer-->, <!--@md:name-->, <!--@headline-->, <!--@results-->, <!--@pipeline--> and <!--@r:key--> (also inside markdown), <!--@icon:name-->, <!--@tex:name--> (KaTeX at build time), <!--@base--> in page HTML
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
          .replace('<!--@results-->', () => results(base))
          .replace(/<!--@md:([\w-]+)-->/g, (_, n) => markdown(n))
          .replace('<!--@pipeline-->', () => pipeline())
          .replace(/<!--@r:(\w+)-->/g, (_, k) => resultText(k))
          .replace(/<!--@figure:([\w-]+)-->/g, (_, n) => figure(n))
          .replace(/<!--@icon:([\w-]+)-->/g, (_, n) => icon(n))
          .replace(/<!--@tex:([\w-]+)-->/g, (_, n) => tex(n))
          .replace(/<!--@base-->/g, base);
      },
    },
    // dev only: serve the built simulator (web/dist, made by web/build_web.py) under /simulator/
    configureServer(server) {
      const dist = join(ROOT, 'web', 'dist');
      server.middlewares.use((req, res, next) => {
        const m = req.url && req.url.split('?')[0].match(/^\/simulator(\/.*)?$/);
        if (!m) return next();
        if (!m[1]) { res.statusCode = 301; res.setHeader('Location', '/simulator/'); return res.end(); }
        let f = join(dist, decodeURIComponent(m[1]));
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

export default defineConfig({
  base,
  root: SITE,
  resolve: { alias: { '@fonts': join(SITE, 'node_modules', 'source-sans') } },
  plugins: [lunarsimPages()],
  build: {
    outDir: 'dist', emptyOutDir: true, target: 'es2022', assetsInlineLimit: 0, sourcemap: true,
    chunkSizeWarningLimit: 600,  // the hero chunk is three.js (~530 kB min, ~133 kB gz), loaded only where a 3D view is
    rollupOptions: {
      input: { ...Object.fromEntries(PAGES.map(p => [p.replace(/\/$/, '').replace(/\//g, '-') || 'index', join(SITE, p, 'index.html')])),
        '404': join(SITE, '404.html') },   // GitHub Pages serves 404.html for unknown paths
    },
  },
  server: { port: 5173 },
});
