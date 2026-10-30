// The Phase 5 papers on /paper/ (F-56): title, abstract and keywords read at build time from each paper's built HTML
// (paper/<id>/paper.html, made by paper/<id>/build_<id>.py) and numbers from its values file (paper/<id>/values.json,
// the same values the paper's own build fills in). Nothing is typed into the site: content/paper.md holds
// <!--@paper:p1:abstract--> and <!--@v:p1:KEY--> markers, replaced here. The paper's HTML itself is not bundled.
// A paper not built yet (the files are build outputs) gives "(pending)" rather than failing the site build.
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { ROOT } from './pages.mjs';

const PENDING = '<span class="stub">(pending)</span>';
const cache = new Map();
function load(id) {
  if (!cache.has(id)) {
    const dir = join(ROOT, 'paper', id), html = join(dir, 'paper.html'), values = join(dir, 'values.json');
    cache.set(id, { html: existsSync(html) ? readFileSync(html, 'utf8') : null, values: existsSync(values) ? JSON.parse(readFileSync(values, 'utf8')) : null });
  }
  return cache.get(id);
}
const one = (re, s) => { const m = re.exec(s); return m ? m[1].trim() : null; };
const strip = s => s.replace(/<[^>]+>/g, '');
// the built HTML must be finished: no unfilled {{KEY}} and no "pending" marks in what the site quotes
function finished(id, part, s) {
  if (/\{\{[\w-]+\}\}|class="pending"/.test(s)) throw new Error(`paper/${id}/paper.html: ${part} still has pending values`);
  return s;
}

// <!--@paper:<id>:title|abstract|keywords|bibtex-->
export function paperField(id, field) {
  const { html } = load(id);
  if (!html) return PENDING;
  const title = one(new RegExp(`<h1 id="${id}-title">([\\s\\S]*?)</h1>`), html);
  if (field === 'title') return title ? finished(id, 'title', title) : PENDING;
  if (field === 'abstract') {
    const box = one(new RegExp(`<div class="abstract" id="${id}-abstract">([\\s\\S]*?)</div>`), html);
    const p = box && one(/<p>([\s\S]*?)<\/p>/, box);
    return p ? finished(id, 'abstract', p.replace(/<!--[\s\S]*?-->\s*/g, '').replace(/^<b>Abstract\.<\/b>\s*/, '')) : PENDING;   // the paper's build notes stay out
  }
  if (field === 'keywords') {
    const kw = one(/<p class="kw">([\s\S]*?)<\/p>/, html);
    return kw ? kw.replace(/^<b>Keywords:<\/b>\s*/, '') : PENDING;
  }
  if (field === 'bibtex') {
    if (!title) return PENDING;
    const t = strip(title).replace(/&amp;/g, '&');
    return `<pre><code>@misc{rahimov2026${id},\n  title  = {${t}},\n  author = {Rahimov, Azizjon},\n  year   = {2026},\n  note   = {Preprint, October 2026},\n  url    = {https://github.com/azizjonrahimov/Lunar-Haul}\n}</code></pre>`;
  }
  throw new Error(`unknown paper field ${field}`);
}

// <!--@v:<id>:KEY--> a value as the paper prints it (HTML with its own spaces and minus signs)
export function paperValue(id, key) {
  const { values } = load(id);
  if (!values) return PENDING;
  if (!(key in values)) throw new Error(`paper/${id}/values.json has no ${key}`);
  return finished(id, key, String(values[key]));
}
