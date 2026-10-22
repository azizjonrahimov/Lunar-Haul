// The version-3 pipeline diagram (F-15): how the terrain, the lander, the rover and the plume model feed the logistics
// engine. One declarative spec, two hand-placed layouts (wide for desktops and the paper, tall for phones), real
// <text> (no text as paths), Tol colours per model lane. pipeline(base) is inlined into /method at build time;
// scripts/export_pipeline.mjs writes the standalone SVG and a 200-dpi PNG to figures/v3_fig02_pipeline.*.
import { esc } from '../src/components/num.js';

// lane: a = landing (Tol blue), b = driving (Tol green), c = plume (Tol red); dual = runs in Python and in the browser
const NODES = {
  tile:    { title: 'LOLA DEM tile', text: 'NASA PGDA Site01, 5 m posts, 16 × 16 km' },
  pack:    { title: 'Terrain pack', text: 'heights, slopes, shadows, sites, pads, sight lines' },
  lander:  { lane: 'a', dual: true, title: 'Lander environment', text: '3-DoF terminal descent from a dispersed SPLICE gate, altimeter faults' },
  rover:   { lane: 'b', dual: true, title: 'Rover environment', text: 'bicycle model on the 5 m terrain, slip by soil, latency, lighting' },
  plume:   { lane: 'c', title: 'Plume module', text: 'keep-out radius R and stand-down time T, both swept' },
  landers: { lane: 'a', title: 'Landing controllers', text: 'classical ZEM/ZEV law, imitation + DAgger, PPO' },
  drivers: { lane: 'b', title: 'Drivers', text: 'A* + pure-pursuit expert, learned CNN driver (imitation + DAgger)' },
  outcome: { lane: 'a', title: 'Landing outcome tables', text: 'per class and controller: miss, touchdown state, propellant' },
  driving: { lane: 'b', title: 'Driving tables', text: 'per leg, autonomy, latency and lighting: time, energy, interventions' },
  engine:  { dual: true, title: 'Logistics engine', text: 'discrete-event, four dispatch rules; samples a landing outcome at every landing and a driving draw on every trip' },
  metrics: { title: 'Metrics', text: 'delay, cost per kg, trace v2' },
  exps:    { title: 'Experiments', text: 'E15–E20, seeded, with 95 % intervals' },
  law:     { title: 'Fitted law', text: 'delivery cost vs dispersion, standoff and autonomy' },
};
const EDGES = [['tile', 'pack'], ['pack', 'lander'], ['pack', 'rover'], ['pack', 'plume'], ['lander', 'landers'], ['rover', 'drivers'],
  ['landers', 'outcome'], ['drivers', 'driving'], ['outcome', 'engine'], ['driving', 'engine'], ['plume', 'engine'],
  ['engine', 'metrics'], ['metrics', 'exps'], ['exps', 'law']];

// layouts: x, y (top), w per node; h is computed from the wrapped text unless given. dir = edge direction.
const T = 13, D = 11.5, CW_T = 0.56 * T, CW_D = 0.5 * D, PAD = 8, LH_D = 14.5;
const LAYOUTS = {
  wide: { W: 1080, dir: 'h', legendY: 392, nodes: {
    tile: [8, 0, 112], pack: [140, 0, 120],
    lander: [282, 0, 152], rover: [282, 0, 152], plume: [282, 0, 152],
    landers: [456, 0, 152], drivers: [456, 0, 152],
    outcome: [630, 0, 150], driving: [630, 0, 150],
    engine: [802, 34, 140, 324], metrics: [964, 0, 108], exps: [964, 0, 108], law: [964, 0, 108] },
    rows: { a: 88, b: 200, c: 312 }, laneOf: { tile: 'b', pack: 'b', lander: 'a', landers: 'a', outcome: 'a', rover: 'b', drivers: 'b', driving: 'b', plume: 'c', metrics: 'a', exps: 'b', law: 'c' } },
  tall: { W: 380, dir: 'v', nodes: {
    tile: [70, 8, 240], pack: [70, 0, 240],
    lander: [4, 0, 120], rover: [130, 0, 120], plume: [256, 0, 120],
    landers: [4, 0, 120], drivers: [130, 0, 120],
    outcome: [4, 0, 120], driving: [130, 0, 120],
    engine: [40, 0, 300], metrics: [70, 0, 240], exps: [70, 0, 240], law: [70, 0, 240] },
    order: [['tile'], ['pack'], ['lander', 'rover', 'plume'], ['landers', 'drivers'], ['outcome', 'driving'], ['engine'], ['metrics'], ['exps'], ['law']], gap: 30 },
};

function wrap(text, maxChars) {
  const out = []; let line = '';
  // split at ordinary spaces only, so units written with no-break spaces stay on one line
  for (const w of String(text).split(/ +/)) { if (line && (line + ' ' + w).length > maxChars) { out.push(line); line = w; } else line = line ? line + ' ' + w : w; }
  if (line) out.push(line); return out;
}
function place(name) {
  const L = LAYOUTS[name], boxes = {};
  for (const [id, [x, y, w, hFix]] of Object.entries(L.nodes)) {
    const n = NODES[id], tl = wrap(n.title, Math.floor((w - 2 * PAD) / CW_T)), dl = wrap(n.text, Math.floor((w - 2 * PAD) / CW_D));
    const hText = PAD + tl.length * (T + 3) + dl.length * LH_D + PAD - 2;
    boxes[id] = { id, x, y, w, h: Math.max(hFix || 0, hText), tl, dl, n };
  }
  if (L.dir === 'h') {   // centre each node on its lane row; the engine is placed explicitly
    for (const b of Object.values(boxes)) if (b.id !== 'engine') b.y = L.rows[L.laneOf[b.id]] - b.h / 2;
  } else {               // rows top to bottom, each row as tall as its tallest node
    let y = 8;
    for (const row of L.order) { const h = Math.max(...row.map(id => boxes[id].h)); for (const id of row) boxes[id].y = y; y += h + L.gap; }
    L.H = y - L.gap + 8 + 64;
    L.legendY = y - L.gap + 22;
  }
  if (!L.H) L.H = L.legendY + 30;
  return { L, boxes };
}

function edgePath(L, a, b) {
  if (L.dir === 'h') {
    const sx = a.x + a.w, sy = a.y + a.h / 2, dx = b.x;
    let dy = b.y + b.h / 2;
    if (b.id === 'engine') dy = sy;                            // straight into the tall engine box at the lane's height
    if (a.id === 'engine') return `M${a.x + a.w},${b.y + b.h / 2}H${dx - 1}`;
    if (a.x === b.x) return `M${a.x + a.w / 2},${a.y + a.h}V${b.y - 1}`;   // stacked in one column
    const mx = Math.round((sx + dx) / 2);
    return sy === dy ? `M${sx},${sy}H${dx - 1}` : `M${sx},${sy}H${mx}V${dy}H${dx - 1}`;
  }
  const sx = a.x + a.w / 2, sy = a.y + a.h;
  let dx = b.x + b.w / 2; const dy = b.y;
  if (b.id === 'engine') dx = sx;                              // each lane drops straight into the wide engine box
  const my = a.id === 'pack' ? Math.round(sy + 14) : Math.round(dy - 14);
  return sx === dx ? `M${sx},${sy}V${dy - 1}` : `M${sx},${sy}V${my}H${dx}V${dy - 1}`;
}

function svg(name, { id = 'pl', standalone = false } = {}) {
  const { L, boxes } = place(name), mk = `${id}-${name}-arrow`;
  const lane = { a: 'la', b: 'lb', c: 'lc' };
  const nodes = Object.values(boxes).map(b => {
    const cls = ['pn', b.n.lane ? lane[b.n.lane] : 'l0', b.n.dual ? 'dual' : ''].filter(Boolean).join(' ');
    let y = b.y + PAD + T - 1;
    const t = b.tl.map(s => { const e = `<text class="pt" x="${b.x + PAD}" y="${y}">${esc(s)}</text>`; y += T + 3; return e; }).join('');
    y += 1;
    const d = b.dl.map(s => { const e = `<text class="pd" x="${b.x + PAD}" y="${y}">${esc(s)}</text>`; y += LH_D; return e; }).join('');
    return `<g class="${cls}"><rect x="${b.x}" y="${b.y}" width="${b.w}" height="${b.h}" rx="5"/>${t}${d}</g>`;
  }).join('');
  const edges = EDGES.map(([s, d]) => `<path class="pe" d="${edgePath(L, boxes[s], boxes[d])}" marker-end="url(#${mk})"/>`).join('');
  const lx = name === 'wide' ? 282 : 8, ly = L.legendY;
  const lines = wrap('Python ⇄ browser, one physics: dashed boxes run in both from the same files and are cross-checked on the Verification page. Blue: landing · green: driving · red: plume.', Math.floor((L.W - lx - 34 - 8) / CW_D));
  const legend = `<g class="plg"><rect class="dual-key" x="${lx}" y="${ly - 11}" width="26" height="14" rx="3"/>${lines.map((t, k) => `<text class="pd" x="${lx + 34}" y="${ly + k * LH_D}">${esc(t)}</text>`).join('')}</g>`;
  const H = Math.max(L.H, Math.ceil(ly + (lines.length - 1) * LH_D + 10));
  const style = standalone ? `<style>
.pn rect { fill: #fff; stroke: rgba(0,0,0,.45); stroke-width: 1; } .la rect { stroke: #4477AA; fill: #ecf1f6; } .lb rect { stroke: #228833; fill: #e9f3ea; } .lc rect { stroke: #EE6677; fill: #fdf0f1; }
.dual rect, .dual-key { stroke-dasharray: 5 3; stroke-width: 1.4; } .dual-key { fill: none; stroke: rgba(0,0,0,.6); }
.pt { font: 600 ${T}px 'Source Sans 3 Variable', 'Source Sans 3', 'Source Sans Pro', Arial, sans-serif; fill: rgba(0,0,0,.85); } .pd { font: 400 ${D}px 'Source Sans 3 Variable', 'Source Sans 3', 'Source Sans Pro', Arial, sans-serif; fill: rgba(0,0,0,.62); }
.pe { fill: none; stroke: rgba(0,0,0,.5); stroke-width: 1; } .pa { fill: rgba(0,0,0,.5); }
</style>` : '';
  return `<svg ${standalone ? 'xmlns="http://www.w3.org/2000/svg" ' : ''}class="pipeline-svg pipeline-${name}" viewBox="0 0 ${L.W} ${H}" width="${L.W}" height="${H}"${standalone ? '' : ' aria-hidden="true" focusable="false"'}>${style}
<defs><marker id="${mk}" viewBox="0 0 8 8" refX="7.5" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path class="pa" d="M0,0.5L8,4L0,7.5z"/></marker></defs>
${edges}${nodes}${legend}</svg>`;
}

// the text equivalent (also the reading order of the figure)
const STEPS = [
  'NASA\'s LOLA elevation tile of the Connecting Ridge (PGDA Site01, 5 m posts) is turned into a terrain pack: heights, slopes, cast shadows, the nine sites, the pads and lines of sight.',
  'The terrain pack feeds three models. (a) Landing: the lander environment (3-DoF terminal descent from a dispersed SPLICE gate, with altimeter faults) is flown by the classical ZEM/ZEV law, an imitation-learned clone refined by DAgger, and PPO policies; their Monte Carlo runs become landing outcome tables per lander class and controller.',
  '(b) Driving: the rover environment (a bicycle model on the 5 m terrain with soil-dependent slip, control latency and lighting) is driven by an A* and pure-pursuit expert and by a learned CNN driver; their drives become driving tables per leg, autonomy level, latency and lighting.',
  '(c) Plume: the keep-out radius R and stand-down time T around each landing are swept.',
  'The discrete-event logistics engine runs the four dispatch rules, drawing a landing outcome at every landing and a driving draw on every trip, and applying the keep-out windows.',
  'It writes the metrics (delay, cost per kilogram) and a trace; the experiments E15 to E20 run it over seeded years with 95 % intervals; and a law relating delivery cost to dispersion, standoff and autonomy is fitted to them.',
  'The lander environment, the rover environment and the engine run both in Python and in the browser from the same files; the two are cross-checked on the Verification page.',
];
export const CAPTION = 'How the three models feed the logistics engine. The terrain pack built from NASA\'s laser-altimeter tile is read by the lander and rover environments and by the engine; the learned and classical controllers turn the environments into outcome and driving tables that the engine samples at every landing and every trip, alongside the swept plume keep-out. Dashed boxes run in Python and, from the same files, in the browser.';

export function pipeline() {
  return `<figure class="pipeline" aria-labelledby="pipeline-cap">
<div class="pipeline-body">${svg('wide')}${svg('tall')}</div>
<figcaption id="pipeline-cap"><b>The pipeline.</b> ${esc(CAPTION)}</figcaption>
<ol class="visually-hidden" aria-label="The pipeline, step by step">${STEPS.map(s => `<li>${esc(s)}</li>`).join('')}</ol>
</figure>`;
}
export function standaloneSvg(name = 'wide') {
  return `<?xml version="1.0" encoding="UTF-8"?>\n<!-- LunarHaul v3, Figure 2: pipeline. Generated by site/scripts/export_pipeline.mjs from site/lib/pipeline.mjs. -->\n${svg(name, { id: 'fig2', standalone: true })}\n`;
}
