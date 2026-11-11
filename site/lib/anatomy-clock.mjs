// F-68: Fig 1d, a crystal against a chip-scale atomic clock (anatomy kit, vendor/anatomy, MIT). Two dial gauges stand on
// their oscillator modules; a carriage runs along a 24-hour rail at the front; a resync console at the right is cabled to
// both modules. The page script runs a day: the carriage moves, each needle turns by its clock's offset (drift x time since
// the last resync), and at each resync both snap back to zero. Drift values from note 01 (src/protocol/params.js).
import { k, W, project, tools, labels, plate, still, pinKey } from './anatomy-common.mjs';
import { num, fmt } from '../src/components/num.js';
import { P as PRM } from '../src/protocol/params.js';

const H = 400;
const PLATE = { x: -150, y: -80, w: 300, d: 160, r: 8 }, PH = 10, FH = 6;
const DIALS = { tcxo: { c: [-62, -28], scale: 20e-3, unit: 'ms' }, csac: { c: [58, -28], scale: 20e-6, unit: 'µs' } };   // one needle turn = 20 ms / 20 µs
const DR = 22, DZ = 84, DH = 10, DTOP = DZ + DH;
const RAIL = { from: -120, to: 108, y: 48 }, CAR = { w: 26, d: 24 }, CON = [128, 8];

const P = project([...k.boxCorners(PLATE, -PH - FH, 0), [-62 - DR, -28, DTOP + 4], [58 + DR, -28, DTOP + 4], [CON[0], CON[1], 30]], H, { pad: 20, azimuth: 42 });
const { at, S, L, D, byDepth } = tools(P);

function base() {
  const out = [`<path class="iso-halo" d="${k.haloOf(PLATE, -PH - FH, PH, P)}"/>`];
  for (const [x, y] of byDepth(k.corners(PLATE, 24))) {
    out.push(S(k.cylinder(x, y, 8, -PH - FH, 1.8, P, 28), { tone: 'lo' }), S(k.cylinder(x, y, 6, -PH - FH + 1.8, FH - 1.8, P, 28), { tone: 'mid' }));
  }
  out.push(S(k.slabOf(PLATE, -PH, PH, P, 8, 1.6), { tone: 'mid' }), L(k.planOutline(k.insetPlan(PLATE, 5), 0, P), { tone: 'lo' }));
  const screws = k.corners(PLATE, 11);
  out.push(L(screws.map(([x, y]) => k.ring(x, y, 2.4, 0, P, 16)).join(''), { tone: 'lo' }), D(screws.map(([x, y]) => at([x, y, 0])), { size: 0.5 }));
  const lp = { x: 92, y: PLATE.y + PLATE.d - 18, w: 44, d: 10, r: 1 };
  out.push(S(k.slabOf(lp, 0, 0.8, P, 4), { tone: 'lo' }), L(k.planOutline(k.insetPlan(lp, 1.6), 0.8, P), { tone: 'faint' }));
  out.push(k.faceTextSvg(k.topMatrix([lp.x + 4, lp.y + 6.2], 0.8, P, 'x'), 'TWO CLOCKS', { size: 3, tone: 'mid' }));
  return out.join('');
}

// the 24-hour rail: two rails, end stops, a ruler strip with an hour tick each 9.5 units (a major every 6 h)
function rail() {
  const out = [], len = RAIL.to - RAIL.from;
  for (const y of [RAIL.y - 10, RAIL.y + 7]) out.push(S(k.slabOf({ x: RAIL.from, y, w: len, d: 4, r: 1 }, 0, 3, P, 3, 0.4), { tone: 'mid' }));
  for (const x of [RAIL.from - 5, RAIL.to]) {
    out.push(S(k.slabOf({ x, y: RAIL.y - 13, w: 5, d: 26, r: 1.2 }, 0, 7, P, 3, 0.5), { tone: 'mid' }));
    out.push(D([at([x + 2.5, RAIL.y - 9, 7]), at([x + 2.5, RAIL.y + 9, 7])], { size: 0.45 }));
  }
  const strip = { x: RAIL.from, y: RAIL.y + 15, w: len, d: 7, r: 1 };
  out.push(S(k.slabOf(strip, 0, 0.6, P, 3), { tone: 'lo', crease: 'none' }));
  const t = k.topTicks(strip.x + 4, strip.x + strip.w - 4, (strip.w - 8) / 24, 6, strip.y + 0.8, 0.6, [2, 3.8], P);
  out.push(L(t.minor, { tone: 'lo' }), L(t.major, { tone: 'mid' }));
  out.push(`<g class="ck-marks"></g>`);   // resync marks, drawn by the page script for the chosen interval
  return out.join('');
}
export const hourX = h => RAIL.from + 4 + (RAIL.to - RAIL.from - 8) * h / 24;

function carriage() {
  const x0 = hourX(0), out = [`<path class="iso-halo" d="${k.haloOf({ x: x0 - CAR.w / 2 + 3, y: RAIL.y - CAR.d / 2 + 3, w: CAR.w - 6, d: CAR.d - 6, r: 2 }, 3, 0.1, P)}" style="filter:blur(4px)"/>`];
  const c = { x: x0 - CAR.w / 2, y: RAIL.y - CAR.d / 2, w: CAR.w, d: CAR.d, r: 2.5 };
  out.push(S(k.slabOf(c, 3, 6, P, 4, 0.6), { tone: 'hi', crease: 'lo', lit: true }));
  out.push(D([[c.x + 4, c.y + c.d - 2.5], [c.x + c.w - 4, c.y + c.d - 2.5]].map(([x, y]) => at([x, y, 9])), { size: 0.4 }));
  // the pointer on the carriage, down to the ruler
  out.push(S(k.slabOf({ x: x0 - 1, y: c.y + c.d, w: 2, d: 6, r: 0.4 }, 4, 3, P, 2), { tone: 'hi', lit: true }));
  return `<g class="ck-car" data-x0="${x0}">${out.join('')}</g>`;
}

// an oscillator module, a post and a face-up dial gauge; the needle is drawn by the page script
// the needle at `secs` since the last resync (also the page script's formula)
export function needle(id, secs) {
  const { c: [x, y], scale } = DIALS[id], drift = id === 'tcxo' ? PRM.tcxo.value * 1e-3 / 86400 : PRM.csac.value * 1e-6 / 86400;
  const a = 2 * Math.PI * drift * secs / scale;
  return k.lineOnTop([x - Math.sin(a) * 3.4, y + Math.cos(a) * 3.4], [x + Math.sin(a) * (DR - 4), y - Math.cos(a) * (DR - 4)], DTOP + 0.2, P);
}
function gauge(id, still = false) {
  const { c: [x, y], unit } = DIALS[id], out = [];
  const mod = { x: x - 22, y: y - 18, w: 44, d: 36, r: 3 };
  out.push(S(k.slabOf(mod, 0, 16, P, 4, 1), { tone: 'hi', crease: 'lo', inner: L(k.sideSeam(mod, 5, P, 4), { tone: 'faint' }) }));
  out.push(L(k.planOutline(k.insetPlan(mod, 3), 16, P, 3), { tone: 'faint' }), D(k.corners(mod, 3).map(([a, b]) => at([a, b, 16])), { size: 0.45 }));
  // the oscillator itself on the module's lid: a round crystal can, or the atomic clock's square package
  if (id === 'tcxo') out.push(S(k.cylinder(x + 12, y + 8, 5, 16, 4, P, 24, 0.4), { tone: 'hi', crease: 'lo' }), L(k.ring(x + 12, y + 8, 3, 20, P, 20), { tone: 'lo' }));
  else out.push(S(k.slabOf({ x: x + 5, y: y + 2, w: 14, d: 12, r: 1.2 }, 16, 5, P, 3, 0.5), { tone: 'hi', crease: 'lo' }), D(k.corners({ x: x + 5, y: y + 2, w: 14, d: 12 }, 1.6).map(([a, b]) => at([a, b, 21])), { size: 0.35 }));
  out.push(S(k.slabOf({ x: x + 14, y: mod.y + mod.d, w: 6, d: 3, r: 0.6 }, 4, 6, P, 2, 0.3), { tone: 'mid' }));
  out.push(S(k.cylinder(x, y, 6, 16, 4, P, 28, 0.4), { tone: 'mid' }));
  out.push(S(k.cylinder(x, y, 3.2, 20, DZ - 20, P, 24), { tone: 'mid', crease: 'none' }));
  out.push(L([44, 64].map(z => k.sideArc(x, y, 3.2, z, P, 16)).join(''), { tone: 'faint' }));
  out.push(S(k.cylinder(x, y, DR, DZ, DH, P, 64, 0.8), { tone: 'hi', crease: 'lo' }));
  out.push(L(k.knurl(x, y, DR, DTOP - 3.4, DTOP, 84, P, 0.3), { tone: 'lo' }), L(k.sideArc(x, y, DR, DTOP - 3.4, P, 40), { tone: 'faint' }));
  out.push(L(k.ring(x, y, DR - 2.2, DTOP, P, 64), { tone: 'lo' }));
  const ticks = k.radialTicks(x, y, DR - 3, 40, 5, DTOP, [1.3, 2.8], P);
  out.push(L(ticks.minor, { tone: 'lo' }), L(ticks.major, { tone: 'mid' }));
  out.push(k.faceTextSvg(k.topMatrix([x, y + 9], DTOP, P, 'x'), `20 ${unit}`, { size: 2.6, tone: 'lo', anchor: 'middle' }));
  out.push(L(k.ring(x, y, 1.6, DTOP, P, 16), { tone: 'mid' }));
  out.push(`<path class="iso-line ck-needle" data-tone="lit" data-dial="${id}" data-free="start" style="stroke-width:1.2" d="${needle(id, still ? 0.25 * 86400 : 0)}"/>`);
  return out.join('');
}

function consoleBox() {
  const [x, y] = CON, b = { x: x - 12, y: y - 14, w: 24, d: 28, r: 2.5 }, out = [];
  out.push(S(k.slabOf(b, 0, 16, P, 4, 0.8), { tone: 'hi', crease: 'lo' }), L(k.planOutline(k.insetPlan(b, 3), 16, P, 3), { tone: 'faint' }));
  out.push(S(k.cylinder(x, y + 3, 6, 16, 2, P, 28, 0.4), { tone: 'mid' }));
  out.push(`<g class="ck-button">${S(k.cylinder(x, y + 3, 4.4, 18, 3, P, 28, 0.4), { tone: 'hi', crease: 'lo' })}</g>`);
  out.push(D([at([x, y - 9, 16])], { size: 0.6, tone: 'hi' }));
  return out.join('');
}

function cables() {
  const Wr = pts => k.wireSvg(at(pts[0]), at(pts[pts.length - 1]), { via: pts.slice(1, -1).map(at), tone: 'mid', size: 1 });
  const z = 0.6, [t, c] = [DIALS.tcxo.c, DIALS.csac.c];
  // from the console's far side to the connector on each module's front face (x + 17, front + 3)
  return Wr([[CON[0] - 12, 2, z], [c[0] + 17, 2, z], [c[0] + 17, c[1] + 21, z]])
    + Wr([[CON[0] - 12, 12, z], [t[0] + 17, 12, z], [t[0] + 17, t[1] + 21, z]]);
}

const ITEMS = () => [
  { id: 'tcxo', anchor: [DIALS.tcxo.c[0] - DR, DIALS.tcxo.c[1], DTOP - 5], title: 'Crystal clock', value: `drifts ${tx('tcxo')}` },
  { id: 'csac', anchor: [DIALS.csac.c[0] + DR, DIALS.csac.c[1], DTOP - 5], title: 'Atomic clock', value: `drifts ${tx('csac')}` },
  { id: 'range', anchor: [DIALS.tcxo.c[0] - 22, DIALS.tcxo.c[1], 8], title: 'One-way ranging', value: `1 ns = ${tx('ns_m')}` },
  { id: 'resync', anchor: [CON[0] + 12, CON[1], 9], title: 'Resync, two-way', value: 'link delay cancels' },
  { id: 'day', anchor: [RAIL.to, RAIL.y, 5], title: 'Day rail', value: '0 to 24 h' },
];
const LABEL = 'Two dial gauges on a bench, each on its own oscillator module: a crystal on the left and a chip-scale atomic clock on the right. A carriage runs along a 24-hour rail at the front, and a resync console at the right is cabled to both modules. Each needle shows its clock\'s offset since the last resync.';
const tx = key => `${fmt(PRM[key].value, PRM[key].digits)}${PRM[key].unit}`.replace(' a day', '/day');
function drawing(still = false) {
  const lab = labels(P, ITEMS(), H);
  return [base(), cables(), rail(), `<g data-sys="clock" data-part="tcxo">${gauge('tcxo', still)}</g>`, `<g data-sys="clock" data-part="csac">${gauge('csac', still)}</g>`, `<g data-sys="cpu" data-part="resync">${consoleBox()}</g>`, `<g data-sys="nav">${carriage()}</g>`, lab].join('');
}
// what the page script needs to draw needles, marks and the carriage
const data = () => JSON.stringify({ P: { origin: P.origin, scale: P.scale, azimuth: P.azimuth, elevation: P.elevation }, dials: DIALS, DR, DTOP, rail: RAIL, hourX: [hourX(0), hourX(24)],
  drift: { tcxo: PRM.tcxo.value * 1e-3 / 86400, csac: PRM.csac.value * 1e-6 / 86400 } });

export function clockFigure() {
  const svg = k.figureSvg({ width: W, height: H, label: LABEL, body: drawing() });
  const ints = [['600', '10 min'], ['3600', '1 h'], ['21600', '6 h'], ['0', 'never']];
  const controls = `<button type="button" class="ui-btn ck-run" aria-pressed="false">Run a day</button>`
    + `<fieldset class="ui-seg ck-every"><legend class="ui-label">Resync every</legend><div class="ui-seg-track">${ints.map(([v, l]) => `<label><input type="radio" name="ck-every" value="${v}"${v === '3600' ? ' checked' : ''}><span>${l}</span></label>`).join('')}</div></fieldset>`;
  return plate({ kind: 'clock', fig: 'Fig 1d', title: 'Two clocks', hint: 'Run a day', readout: 't = 0 h',
    keys: [{ mark: 'lit', label: 'Needles and the day carriage' }, { mark: 'raised', label: 'One needle turn is 20 ms on the crystal, 20 µs on the atomic clock' }],
    caption: `Drift from note 01: the crystal ${num(PRM.tcxo)} (measured on the Moon by LuGRE), the chip-scale atomic clock ${num(PRM.csac)} (data sheet). One nanosecond of clock error is ${num(PRM.ns_m)} of one-way range; two-way ranging needs no common time.`,
    svg: svg.replace('<svg', `<svg data-clock='${data()}'`), controls, list: pinKey(ITEMS()) });
}
export const clockStill = () => still(drawing(true), W, H, LABEL);
