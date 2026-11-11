// F-68: Fig 1c, the radio link between two rovers (anatomy kit, vendor/anatomy, MIT). A long bench with a log-distance
// ruler (10 m to 10 km): radio A (cut open: front end and antenna feed) at the left end, radio B on a carriage on two rails.
// Posts stand at the two-ray breakpoint and at the radio horizon for 1 m and for 2.5 m antennas (results/E48_sizing.json).
// The page script slides B, redraws the direct and the ground-bounce rays, and reads the link from the engine's budget
// (src/protocol/radio.js, the same port the link-budget figure uses and a node test checks against E48).
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { k, W, project, tools, labels, plate, still, pinKey } from './anatomy-common.mjs';
import { num, fmt } from '../src/components/num.js';
import { ROOT } from './pages.mjs';
import { horizon, breakpoint } from '../src/protocol/radio.js';

const H = 380;
const PLATE = { x: -190, y: -42, w: 380, d: 84, r: 8 }, PH = 10, FH = 6;
const LOG0 = -120, PER_DECADE = 92;                    // x of 10 m, and the length of one decade on the ruler
export const xOf = d => LOG0 + PER_DECADE * (Math.log10(d) - 1);
const A = { x: -172, y: -14 }, BOX = { w: 30, d: 26, h: 18 };   // radio A's box corner; B's box centred on its carriage
const RAIL_Y = [-14, 10], HZ = 40;                      // world units of mast per metre of antenna height (exaggerated)
const HEIGHTS = { small: 1.0, ltv: 2.5 };

const E48 = () => { const p = join(ROOT, 'results', 'E48_sizing.json'); return existsSync(p) ? JSON.parse(readFileSync(p, 'utf8').replace(/\bNaN\b/g, 'null')) : null; };
const S48 = E48();
const CL = { small: S48?.classes?.SMALL?.link, ltv: S48?.classes?.LTV1?.link };
const F = 2.4e9;
// breakpoint and horizon per antenna height: from E48 when it has them, else from the same formulas
const marks = id => ({ bp: CL[id]?.breakpoint_m ?? breakpoint(HEIGHTS[id], HEIGHTS[id], F), hz: CL[id]?.mutual_horizon_m ?? 2 * horizon(HEIGHTS[id]) });

const P = project([...k.boxCorners(PLATE, -PH - FH, 0), [A.x, A.y, BOX.h + 2.5 * HZ + 6], [xOf(10000), 0, BOX.h + 2.5 * HZ + 6]], H, { pad: 16, azimuth: 30 });
const { at, S, L, D, byDepth } = tools(P);

function base() {
  const out = [`<path class="iso-halo" d="${k.haloOf(PLATE, -PH - FH, PH, P)}"/>`];
  for (const [x, y] of byDepth(k.corners(PLATE, 22))) out.push(S(k.cylinder(x, y, 7, -PH - FH, 1.8, P, 28), { tone: 'lo' }), S(k.cylinder(x, y, 5.4, -PH - FH + 1.8, FH - 1.8, P, 28), { tone: 'mid' }));
  out.push(S(k.slabOf(PLATE, -PH, PH, P, 8, 1.6), { tone: 'mid' }), L(k.planOutline(k.insetPlan(PLATE, 5), 0, P), { tone: 'lo' }));
  const screws = k.corners(PLATE, 10);
  out.push(L(screws.map(([x, y]) => k.ring(x, y, 2.2, 0, P, 16)).join(''), { tone: 'lo' }), D(screws.map(([x, y]) => at([x, y, 0])), { size: 0.5 }));
  // the log ruler: a tick at each 1-2-5 step, a major at each decade, the decades engraved
  const strip = { x: LOG0 - 6, y: PLATE.y + PLATE.d - 14, w: xOf(10000) - LOG0 + 12, d: 8, r: 1 };
  out.push(S(k.slabOf(strip, 0, 0.6, P, 3), { tone: 'lo', crease: 'none' }));
  const minor = [], major = [], e = strip.y + 0.8;
  for (let dec = 10; dec <= 10000; dec *= 10) for (const m of [1, 2, 5]) { const d = dec * m; if (d > 10000) continue; (m === 1 ? major : minor).push(k.lineOnTop([xOf(d), e], [xOf(d), e + (m === 1 ? 4 : 2.2)], 0.6, P)); }
  out.push(L(minor.join(''), { tone: 'lo' }), L(major.join(''), { tone: 'mid' }));
  for (const [d, t] of [[10, '10 m'], [100, '100 m'], [1000, '1 km'], [10000, '10 km']]) out.push(k.faceTextSvg(k.topMatrix([xOf(d) + 1.2, e + 6.4], 0.6, P, 'x'), t, { size: 2.6, tone: 'mid' }));
  // two rails for B's carriage, from 10 m to 10 km, with end stops
  for (const y of RAIL_Y) out.push(S(k.slabOf({ x: LOG0 - 4, y, w: xOf(10000) - LOG0 + 8, d: 4, r: 1 }, 0, 3, P, 3, 0.4), { tone: 'mid' }));
  for (const x of [LOG0 - 9, xOf(10000) + 4]) out.push(S(k.slabOf({ x, y: RAIL_Y[0] - 3, w: 5, d: RAIL_Y[1] - RAIL_Y[0] + 10, r: 1.2 }, 0, 7, P, 3, 0.5), { tone: 'mid' }));
  return out.join('');
}

// a post with a flag at distance d (breakpoint or horizon), for one antenna height
function post(d, id, kind) {
  const x = xOf(d), y = PLATE.y + 10, h = kind === 'hz' ? 34 : 24, out = [];
  out.push(S(k.cylinder(x, y, 3.4, 0, 2, P, 20, 0.3), { tone: 'mid' }), S(k.cylinder(x, y, 1.3, 2, h, P, 14), { tone: 'hi', crease: 'none' }));
  out.push(S(k.slabOf({ x: x, y: y - 0.6, w: 9, d: 1.2, r: 0.2 }, h - 4, 6, P, 2), { tone: 'hi', crease: 'lo' }));
  return `<g class="rd-post" data-ant="${id}" data-kind="${kind}" data-sys="${kind === 'hz' ? 'cpu' : 'radio'}">${out.join('')}</g>`;
}

// a radio box with its whips (one per antenna height; the page shows the chosen one). open: walls cut, front end shown
function unit(x0, y0, open) {
  const b = { x: x0, y: y0, w: BOX.w, d: BOX.d, r: 2.5 }, out = [], c = [x0 + 8, y0 + 8], t = 2.2;
  if (open) {
    out.push(S(k.slabOf(b, 0, 2.5, P, 4, 0.4), { tone: 'lo' }));
    out.push(S(k.slabOf({ x: b.x, y: b.y, w: b.w, d: t, r: 0.6 }, 2.5, BOX.h - 2.5, P, 2, 0.3), { tone: 'mid' }), S(k.slabOf({ x: b.x, y: b.y + t, w: t, d: b.d - t, r: 0.6 }, 2.5, BOX.h - 2.5, P, 2, 0.3), { tone: 'mid' }));
    // the front end: board, power amplifier, low-noise amplifier, filter can, and the feed to the antenna
    out.push(S(k.slabOf(k.insetPlan(b, 3), 2.5, 1, P, 3), { tone: 'lo' }));
    out.push(S(k.slabOf({ x: b.x + 14, y: b.y + 6, w: 6, d: 6, r: 0.6 }, 3.5, 2.4, P, 2), { tone: 'hi', crease: 'lo' }), S(k.slabOf({ x: b.x + 14, y: b.y + 15, w: 6, d: 6, r: 0.6 }, 3.5, 2.4, P, 2), { tone: 'hi', crease: 'lo' }));
    out.push(S(k.slabOf({ x: b.x + 22, y: b.y + 7, w: 5, d: 13, r: 0.8 }, 3.5, 4, P, 2, 0.3), { tone: 'mid' }));
    out.push(S(k.cylinder(c[0], c[1], 2.6, 3.5, BOX.h - 3.5, P, 18, 0.3), { tone: 'mid' }));
    out.push(S(k.slabOf({ x: b.x + b.w - t, y: b.y + t, w: t, d: b.d - t, r: 0.6 }, 2.5, 5, P, 2, 0.3), { tone: 'mid' }), S(k.slabOf({ x: b.x, y: b.y + b.d - t, w: b.w, d: t, r: 0.6 }, 2.5, 5, P, 2, 0.3), { tone: 'mid' }));
    out.push(S(k.cylinder(c[0], c[1], 3.4, BOX.h, 2, P, 22, 0.3), { tone: 'mid' }));
  } else {
    out.push(S(k.slabOf(b, 0, BOX.h, P, 4, 0.8), { tone: 'hi', crease: 'lo', inner: L(k.sideSeam(b, 5, P, 4), { tone: 'faint' }) }));
    out.push(L(k.planOutline(k.insetPlan(b, 3), BOX.h, P, 3), { tone: 'faint' }), D(k.corners(b, 2.6).map(([x, y]) => at([x, y, BOX.h])), { size: 0.45 }));
    out.push(S(k.cylinder(c[0], c[1], 3.4, BOX.h, 2, P, 22, 0.3), { tone: 'mid' }));
  }
  for (const [id, hm] of Object.entries(HEIGHTS)) {
    const top = BOX.h + 2 + hm * HZ;
    out.push(`<g class="rd-whip" data-ant="${id}">${S(k.cylinder(c[0], c[1], 1, BOX.h + 2, hm * HZ, P, 14), { tone: 'hi', crease: 'none' })}${S(k.cylinder(c[0], c[1], 1.8, top - 1, 2, P, 16, 0.3), { tone: 'hi', crease: 'lo' })}</g>`);
  }
  return out.join('');
}

function carriage(off = [0, 0]) {
  const x0 = xOf(10) - 18, cy = (RAIL_Y[0] + RAIL_Y[1] + 4) / 2, out = [];
  const cplan = { x: x0, y: cy - 18, w: 36, d: 36, r: 3 };
  out.push(`<path class="iso-halo" d="${k.haloOf(k.insetPlan(cplan, 3), 3, 0.1, P)}" style="filter:blur(4px)"/>`);
  out.push(S(k.slabOf(cplan, 3, 4, P, 4, 0.5), { tone: 'mid' }));
  out.push(D([[cplan.x + 4, cplan.y + cplan.d - 2.5], [cplan.x + cplan.w - 4, cplan.y + cplan.d - 2.5]].map(([x, y]) => at([x, y, 7])), { size: 0.4 }));
  out.push(`<g transform="translate(${k.axisVector(P, [0, 0, 7]).join(' ')})">${unit(x0 + 3, cy - 13, false)}</g>`);
  return `<g class="rd-car" data-sys="radio" data-part="b" transform="translate(${off.map(v => v.toFixed(2)).join(' ')})">${out.join('')}</g>`;
}

const ITEMS = () => {
  const ms = { small: marks('small'), ltv: marks('ltv') };
  return [
  { id: 'a', anchor: [A.x + BOX.w, A.y + 10, 10], title: 'Radio front end', value: CL.small ? `${fmt(CL.small.tx_power_w, 2)} W, NF 5 dB` : 'NF 5 dB' },
  { id: 'bp', anchor: [xOf(ms.small.bp), PLATE.y + 10, 20], title: 'Breakpoint, 1 · 2.5 m', value: `${kmTxt(ms.small.bp)} · ${kmTxt(ms.ltv.bp)}` },
  { id: 'hz', anchor: [xOf(ms.small.hz), PLATE.y + 10, 30], title: 'Horizon, 1 · 2.5 m', value: `${kmTxt(ms.small.hz)} · ${kmTxt(ms.ltv.hz)}` },
  { id: 'b', anchor: [xOf(10000) + 4, 0, 7], title: 'Neighbour on a rail', value: 'drag the distance' },
];
};
const LABEL = 'A long bench with a distance ruler from 10 metres to 10 kilometres on a log scale. Radio A, cut open to show its front end, stands at the left end; radio B rides a carriage on two rails. Posts mark the two-ray breakpoint and the radio horizon for 1 m and 2.5 m antennas. Two rays join the antenna tips: the direct one, and one that bounces off the ground.';
// the two rays for B at distance d (the page script repeats this): tips, the bounce point where the angles of incidence and
// reflection meet on flat ground (A's share of the run is hA / (hA + hB)), and whether B is past the horizon
export function rays(d, ant) {
  const h = BOX.h + 2 + HEIGHTS[ant] * HZ, bx = xOf(d) - xOf(10), ta = [A.x + 8, A.y + 8, h], tb = [xOf(10) - 18 + 3 + 8 + bx, (RAIL_Y[0] + RAIL_Y[1] + 4) / 2 - 13 + 8, h + 7];
  const s = ta[2] / (ta[2] + tb[2]), g = [ta[0] + (tb[0] - ta[0]) * s, ta[1] + (tb[1] - ta[1]) * s, 0];
  const p = q => at(q).map(v => Math.round(v * 10) / 10).join(' ');
  return { direct: `M${p(ta)}L${p(tb)}`, bounce: `M${p(ta)}L${p(g)}L${p(tb)}`, hit: at(g), car: k.axisVector(P, [bx, 0, 0]), lost: d > marks(ant).hz };
}
const kmTxt = m => m >= 1000 ? `${fmt(m / 1000, 1)} km` : `${fmt(m, 0)} m`;
function drawing(state = { ant: 'small', d: 2000 }) {
  const R = rays(state.d, state.ant);
  const ms = { small: marks('small'), ltv: marks('ltv') };
  const list = ['small', 'ltv'].flatMap(id => [[ms[id].bp, id, 'bp'], [ms[id].hz, id, 'hz']]).sort((a, b) => a[0] - b[0]);
  const lab = labels(P, ITEMS(), H);
  return [base(), ...list.map(([d, id, kind]) => post(d, id, kind)), `<g data-sys="radio" data-part="a">${unit(A.x, A.y, true)}</g>`, carriage(R.car),
    `<g class="rd-rays"${R.lost ? ' data-lost=""' : ''}><path class="rd-ray rd-bounce" d="${R.bounce}"/><path class="rd-ray rd-direct" d="${R.direct}"/><circle class="rd-hit" r="1.8" cx="${R.hit[0].toFixed(1)}" cy="${R.hit[1].toFixed(1)}"/></g>`, lab].join('');
}
const data = () => JSON.stringify({ P: { origin: P.origin, scale: P.scale, azimuth: P.azimuth, elevation: P.elevation }, log0: LOG0, perDecade: PER_DECADE, ax: [A.x + 8, A.y + 8], bx0: xOf(10) - 18 + 3 + 8, by: (RAIL_Y[0] + RAIL_Y[1] + 4) / 2 - 13 + 8, carZ: 7,
  boxH: BOX.h, hz: HZ, heights: HEIGHTS, marks: { small: marks('small'), ltv: marks('ltv') }, tx: { small: CL.small?.tx_power_w ?? 0.25, ltv: CL.ltv?.tx_power_w ?? 1 } });

export function radioFigure() {
  const svg = k.figureSvg({ width: W, height: H, label: LABEL, body: drawing() });
  const controls = `<div class="pr-range rd-range"><label class="ui-label" for="rd-d">Distance between the two</label><input type="range" id="rd-d" min="1000" max="4000" step="1" value="3301"></div>`
    + `<fieldset class="ui-seg rd-ant"><legend class="ui-label">Antennas</legend><div class="ui-seg-track"><label><input type="radio" name="rd-ant" value="small" checked><span>1 m (small robot)</span></label><label><input type="radio" name="rd-ant" value="ltv"><span>2.5 m (rover)</span></label></div></fieldset>`;
  return plate({ kind: 'radio', fig: 'Fig 1c', title: 'Two radios', hint: 'Drag the distance', readout: '2.0 km',
    keys: [{ mark: 'lit', label: 'The rays: direct, and off the ground' }, { mark: 'raised', label: 'Mast heights are exaggerated; the ruler is logarithmic' }],
    caption: `The engine's flat-ground law: free space up to the breakpoint, then the two-ray law, and no link past the smooth-Moon horizon. Breakpoints, horizons and powers from results/E48_sizing.json (1 m antennas at ${CL.small ? num({ value: CL.small.tx_power_w, unit: ' W', digits: 2, flag: 'Assumed', source: 'results/E48_sizing.json: classes.SMALL.link.tx_power_w' }) : '0.25 W'}, 2.5 m at ${CL.ltv ? num({ value: CL.ltv.tx_power_w, unit: ' W', digits: 0, flag: 'Assumed', source: 'results/E48_sizing.json: classes.LTV1.link.tx_power_w' }) : '1 W'}).`,
    svg: svg.replace('<svg', `<svg data-radio='${data()}'`), controls, list: pinKey(ITEMS()) });
}
export const radioStill = () => still(drawing(), W, H, LABEL).replace(/<g class="rd-whip" data-ant="ltv">/g, '<g class="rd-whip" data-ant="ltv" display="none">')
  .replace(/<g class="rd-post" data-ant="ltv"/g, '<g class="rd-post" data-ant="ltv" opacity="0.3"');
