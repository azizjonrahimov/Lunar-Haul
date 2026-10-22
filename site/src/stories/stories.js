// /stories/ (F-38): guided stories (explorable explanations) from data/stories/resolved/ (B-35, lunarsim-story-resolved
// v1). Without ?s= the page lists the published stories; with ?s=<id> it plays one: each step has its text with every
// number as a stat chip (value, flag and source from the resolved file), a text twin of the view (the step's visual),
// Back / Next, a step bar and the arrow keys. The 3D stage (stage.js) loads only when the visitor presses Enter and
// follows the steps: world scenes from the gallery or the lander lab's recorded descents. Reduced motion: cuts.
import { door, statChip, h, reducedMotion } from '../ui/index.js';
import { detectTier } from '../stage/tier.js';
import { esc } from '../components/num.js';

const $ = id => document.getElementById(id);
const BASE = import.meta.env.BASE_URL, DATA = BASE + 'story-data/';
const params = new URLSearchParams(location.search), sid = params.get('s');
async function getJson(u) { const r = await fetch(u); if (!r.ok) throw new Error(`${u}: HTTP ${r.status}`); return r.json(); }
const status = m => { $('st-status').textContent = m; };

// text with {{r:key}} numbers emphasised (the chips below carry their flags and sources)
const withNumbers = (s, numbers) => esc(s).replace(/\{\{r:(\w+)\}\}/g, (_, k) => numbers[k] ? `<b class="st-num">${esc(numbers[k].text)}</b>` : '–');
const keysIn = s => [...s.matchAll(/\{\{r:(\w+)\}\}/g)].map(m => m[1]);

const index = await getJson(DATA + 'index.json').catch(e => { $('st-list').textContent = `The stories could not load (${e.message}).`; return null; });
if (index && !sid) await list(index);
else if (index) await play(index.stories.find(s => s.id === sid && s.status === 'published'));

// ---------- the list ----------
async function list(ix) {
  const pub = ix.stories.filter(s => s.status === 'published');
  const docs = await Promise.all(pub.map(s => getJson(DATA + s.file).catch(() => null)));
  $('st-list').replaceChildren(...pub.map((s, i) => {
    const d = docs[i];
    return h('article', { class: 'ui-glass st-card' },
      h('p', { class: 'ui-label' }, `${s.steps} steps · ${d?.scene?.startsWith('lander') ? 'lander lab' : 'the base in 3D'}`),
      h('h2', { class: 'st-card-title' }, h('a', { href: `?s=${encodeURIComponent(s.id)}` }, s.title)),
      d ? h('p', { class: 'st-card-sum', html: withNumbers(d.summary, d.numbers) }) : null);
  }));
}

// ---------- one story ----------
async function play(entry) {
  if (!entry) { $('st-list').textContent = 'No published story with that name. '; $('st-list').append(h('a', { href: './' }, 'All stories')); return; }
  const doc = await getJson(DATA + entry.file);
  document.title = `${doc.title} · Stories · LunarHaul`;
  $('st-head').hidden = true; $('st-list').hidden = true; $('st-player').hidden = false;
  $('st-title').textContent = doc.title; $('st-summary').innerHTML = withNumbers(doc.summary, doc.numbers);
  const steps = doc.steps;
  let i = Math.max(0, Math.min(steps.length - 1, (+params.get('step') || 1) - 1)), stage = null, applying = 0;
  // step bar
  const bar = $('st-bar');
  bar.replaceChildren(...steps.map((s, k) => { const b = h('button', { class: 'st-dot', type: 'button', 'aria-label': `Step ${k + 1}: ${s.title}` }, String(k + 1)); b.addEventListener('click', () => go(k)); return b; }));
  $('st-prev').addEventListener('click', () => go(i - 1));
  $('st-next').addEventListener('click', () => go(i + 1));
  document.addEventListener('keydown', e => {
    if (e.target.closest('input, select, textarea, canvas') || e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.key === 'ArrowRight') { e.preventDefault(); go(i + 1); } else if (e.key === 'ArrowLeft') { e.preventDefault(); go(i - 1); }
  });
  sources(doc);
  render();
  start3d(doc);

  function go(k) {
    if (k < 0 || k >= steps.length || k === i) return;
    i = k; render();
    const u = new URL(location.href); u.searchParams.set('step', String(i + 1)); history.replaceState(null, '', u);
    $('st-text').focus({ preventScroll: true });
  }
  function render() {
    const s = steps[i];
    $('st-count').textContent = `Step ${i + 1} of ${steps.length}`;
    $('st-step-title').textContent = s.title;
    $('st-text').innerHTML = `<p>${withNumbers(s.text, doc.numbers)}</p>`;
    $('st-visual').textContent = s.visual_plain || s.visual || '';
    // every number of the step as a stat chip: its chips first, then the others its text quotes
    const keys = [...new Set([...(s.chips || []), ...keysIn(s.text)])].filter(k => doc.numbers[k]);
    $('st-chips').replaceChildren(...keys.map(k => { const n = doc.numbers[k]; return statChip({ label: n.label || k.replace(/_/g, ' '), text: n.text, flag: n.flag, source: n.source, tone: (s.chips || []).includes(k) ? 'cool' : undefined }).el; }));
    [...bar.children].forEach((b, k) => { if (k === i) b.setAttribute('aria-current', 'step'); else b.removeAttribute('aria-current'); });
    $('st-prev').disabled = i === 0; $('st-next').disabled = i === steps.length - 1;
    $('st-next').textContent = i === steps.length - 1 ? 'The end' : 'Next';
    applyStage();
  }
  async function applyStage() {
    if (!stage) return;
    const gen = ++applying;
    try { status(''); await stage.apply(steps[i], doc); }
    catch (e) { if (gen === applying) status(`The 3D view could not show this step (${e.message}); the text says what it shows.`); }
  }
  async function start3d(d) {
    const tierInfo = await detectTier(), tier = tierInfo.tier;
    if (tier === 0 && !tierInfo.forced) { const fb = $('st-fallback'); fb.hidden = false; fb.textContent = `No 3D here (${tierInfo.gpu}). Each step's text says what the view would show.`; return; }
    const kind = d.scene.startsWith('lander') ? 'lander' : 'world';
    const gate = door({ title: d.title, subtitle: kind === 'lander' ? 'Recorded descents over pad A at true scale.' : 'The base on the real terrain, one simulated year.', skip: { href: '#st-panel', label: 'Skip to the text' },
      enterLabel: 'Enter the 3D view', beforeOpen: async () => {
        const fetchFn = label => url => gate.fetch(url, { label });
        const mod = await import('./stage.js');
        stage = await mod.createStoryStage({ kind, canvas: $('st-canvas'), labelsHost: $('st-labels'), tier: Math.max(1, tier), fetchFn,
          onStatus: s => { if (s === 'lost') status('The graphics context was lost; it will come back by itself.'); } });
        if (import.meta.env.DEV) window.__st = { stage, doc: d, get step() { return i; } };
        await stage.apply(steps[i], d, { instant: true });
      } });
    $('st-view').append(gate.el);
    gate.ready();
  }
}

function sources(doc) {
  const src = doc.sources || {}, items = Array.isArray(src) ? src : Object.entries(src).map(([k, v]) => (typeof v === 'string' && /^[0-9a-f]{64}$/.test(v) ? `${k} (sha256 ${v.slice(0, 12)}…)` : `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`));
  $('st-sources').replaceChildren(...items.map(t => h('li', {}, typeof t === 'string' ? t : JSON.stringify(t))));
  $('st-sources-box').hidden = !items.length;
}
if (reducedMotion()) document.documentElement.classList.add('st-reduced');
