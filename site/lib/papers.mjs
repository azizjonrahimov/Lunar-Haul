// The Phase 5 papers on /paper/ (F-56): title, abstract and keywords read at build time from each paper's built HTML
// (paper/<id>/paper.html, made by paper/<id>/build_<id>.py) and numbers from its values file (paper/<id>/values.json,
// the same values the paper's own build fills in). Nothing is typed into the site: content/paper.md holds
// <!--@paper:p1:abstract--> and <!--@v:p1:KEY--> markers, replaced here. The paper's HTML itself is not bundled.
// A paper not built yet (the files are build outputs) gives "(pending)" rather than failing the site build.
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { inflateSync } from 'node:zlib';
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

// the PDF's page count: its /Type /Page objects in the file and in its deflated streams (Skia writes the page tree into
// compressed streams), checked against the largest /Count of a /Type /Pages node (the root)
function pdfPages(file) {
  const b = readFileSync(file), s = b.toString('latin1'), texts = [s], re = /stream\r?\n/g;
  for (let m; (m = re.exec(s));) {
    const end = s.indexOf('endstream', re.lastIndex); if (end < 0) break;
    try { texts.push(inflateSync(b.subarray(re.lastIndex, end)).toString('latin1')); } catch { /* not a deflated stream */ }
    re.lastIndex = end;
  }
  const leaves = texts.reduce((a, t) => a + (t.match(/\/Type\s*\/Page\b(?!s)/g) || []).length, 0);
  const root = Math.max(0, ...texts.flatMap(t => [...t.matchAll(/\/Type\s*\/Pages\b[^]*?\/Count\s+(\d+)|\/Count\s+(\d+)[^>]*?\/Type\s*\/Pages\b/g)].map(q => +(q[1] || q[2]))));
  if (!leaves || leaves !== root) throw new Error(`${file}: ${leaves} page objects but the page tree counts ${root}`);
  return leaves;
}
// <!--@paper:<id>:pdf--> the link to the paper's one PDF, with its page count and size read from the file
function paperPdf(id) {
  const dir = join(ROOT, 'paper', id), pdfs = existsSync(dir) ? readdirSync(dir).filter(f => f.endsWith('.pdf')) : [];
  if (!pdfs.length) return PENDING;
  if (pdfs.length > 1) throw new Error(`paper/${id}: more than one PDF (${pdfs.join(', ')})`);
  const f = join(dir, pdfs[0]), kb = Math.round(readFileSync(f).length / 1000);
  return `<a href="https://github.com/azizjonrahimov/Lunar-Haul/blob/main/paper/${id}/${pdfs[0]}">PDF, ${pdfPages(f)} pages, ${kb.toLocaleString('en-US')} kB</a>`;
}

// <!--@paper:<id>:title|abstract|keywords|bibtex|pdf-->
export function paperField(id, field) {
  if (field === 'pdf') return paperPdf(id);
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
    // F-71: the dates from the paper's own byline ("Preprint, October 2026, revised November 2026"), not typed here
    const by = /Preprint, ([A-Z][a-z]+) (\d{4})(?:[,;] revised ([A-Z][a-z]+ \d{4}))?/.exec(html);
    if (!by) throw new Error(`paper/${id}: no "Preprint, <month> <year>" in the byline`);
    const note = `Preprint, ${by[1]} ${by[2]}${by[3] ? `, revised ${by[3]}` : ''}`;
    return `<pre><code>@misc{rahimov${by[2]}${id},\n  title  = {${t}},\n  author = {Rahimov, Azizjon},\n  year   = {${by[2]}},\n  note   = {${note}},\n  url    = {https://github.com/azizjonrahimov/Lunar-Haul}\n}</code></pre>`;
  }
  if (field === 'proved') return paperProved(id);
  throw new Error(`unknown paper field ${field}`);
}

// <!--@paper:<id>:proved--> (F-65): the paper's "Proved, tested, assumed" table, found by its heading (h2 to h4; "and"
// and commas optional) as the first <table> after it and before the next heading of the same or a higher level.
// Ids are dropped (the paper's own anchors would clash on /paper/) and the paper's caption kept; the reader is told the
// table is the paper's. Absent table or paper: "(pending)".
export const PROVED_HEADING = /proved,?\s+tested,?\s+(?:and\s+)?assumed/i;
export function provedTable(html, id = 'paper') {
  if (!html) return null;
  const heads = [...html.matchAll(/<h([2-4])\b[^>]*>([\s\S]*?)<\/h\1>/g)];
  const k = heads.findIndex(m => PROVED_HEADING.test(strip(m[2]).replace(/&(?:amp;)?nbsp;|\s+/g, ' ')));
  if (k < 0) return null;
  const level = +heads[k][1], from = heads[k].index + heads[k][0].length;
  const next = heads.slice(k + 1).find(m => +m[1] <= level), region = html.slice(from, next ? next.index : html.length);
  const t = /<table\b[\s\S]*?<\/table>/.exec(region);
  if (!t) return null;
  return finished(id, 'the proved, tested, assumed table', t[0].replace(/\s+id="[^"]*"/g, ''));
}
function paperProved(id) {
  const t = provedTable(load(id).html, id);
  return t ? `<div class="paper-proved">${t}<p class="small muted">From paper/${id}/paper.html when the site is built.</p></div>` : PENDING;
}

// <!--@v:<id>:KEY--> a value as the paper prints it (HTML with its own spaces and minus signs)
export function paperValue(id, key) {
  const { values } = load(id);
  if (!values) return PENDING;
  if (!(key in values)) throw new Error(`paper/${id}/values.json has no ${key}`);
  return finished(id, key, String(values[key]));
}
