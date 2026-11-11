// /protocol/ (F-60): eight figures, one per problem group. Each computes in the browser from src/protocol/params.js
// (the research notes' values) until BACKEND's B-99 exports replace them; the link budget is a port of
// lunarsim/atc/radio.py. Hand-written SVG, native controls, a readout that is also the figure's text version.
import { segmented, h, reducedMotion } from '../ui/index.js';
import { upgradeFlags } from '../ui/tooltip.js';
import { num, fmt } from '../components/num.js';
import { P } from './params.js';
import { horizon, flatLoss, capacity } from './radio.js';
import './protocol.css';
import { mountNavStack } from './nav-stack.js';

const NS = 'http://www.w3.org/2000/svg';
const S = (tag, attrs = {}, ...kids) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== null && v !== undefined && v !== false) e.setAttribute(k, v);
  for (const k of kids.flat()) if (k !== null && k !== undefined) e.append(k instanceof Node ? k : document.createTextNode(String(k)));
  return e;
};
const V = k => P[k].value;
// a computed number in a readout: flagged Modelled, its source the figure itself
const M = (value, unit, digits = 1, what = '') => num({ value, unit, digits, flag: 'Modelled', source: `computed in this figure${what ? ': ' + what : ''}, from the research notes' values` });
const widthOf = (el, max = 640) => Math.round(Math.max(300, Math.min(max, el.getBoundingClientRect().width || max)));
const fit = (svg, w, hgt) => svg.setAttribute('viewBox', `0 0 ${w} ${hgt}`);
const onResize = (el, draw) => { let last = 0, raf = 0; new ResizeObserver(() => { const w = Math.round(el.getBoundingClientRect().width); if (w && Math.abs(w - last) > 4) { last = w; cancelAnimationFrame(raf); raf = requestAnimationFrame(draw); } }).observe(el); };
const svgBox = (w, hgt, label) => S('svg', { viewBox: `0 0 ${w} ${hgt}`, class: 'pr-svg', role: 'img', 'aria-label': label });
const readout = () => h('p', { class: 'pr-read' });
const setRead = (el, html) => { el.innerHTML = html; upgradeFlags(el); };
const range = (label, attrs) => {
  const id = `pr-r-${Math.random().toString(36).slice(2, 8)}`;
  const input = h('input', { type: 'range', id, ...attrs });
  return { input, el: h('div', { class: 'pr-range' }, h('label', { for: id, class: 'ui-label' }, label), input) };
};
const check = (label, on) => {
  const input = h('input', { type: 'checkbox', checked: on });
  return { input, el: h('label', { class: 'pr-check' }, input, ' ', label) };
};
// seeded random numbers (mulberry32) so every visitor sees the same run
const rng = seed => () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
const gauss = r => () => Math.sqrt(-2 * Math.log(r() || 1e-12)) * Math.cos(2 * Math.PI * r());
const km = m => m >= 1000 ? `${fmt(m / 1000, m >= 10000 ? 0 : 1)} km` : `${fmt(m, 0)} m`;
const dur = s => s < 90 ? `${fmt(s, s < 10 ? 1 : 0)} s` : s < 5400 ? `${fmt(s / 60, 1)} min` : `${fmt(s / 3600, 1)} h`;

// ---------------------------------------------------------------- 1. positioning: error along a drive
function figPos(host) {
  let W = 640; const H = 300, L = 52, R = 16, T = 14, B = 34, D = 5000;
  const layers = { vo: check('Cameras and star tracker (visual odometry)', true), fix: check('Terrain fixes from orbital maps', true),
    uwb: check('Radio ranging to the base beacons', true), lans: check('LunaNet satellites (2030)', false) };
  const cur = range('Distance driven', { min: 0, max: D, step: 50, value: 3000 });
  const svg = svgBox(W, H, 'Position error against distance driven, on a log scale, for dead reckoning alone and with the chosen layers');
  const out = readout();
  const x = d => L + (W - L - R) * d / D, y = e => T + (H - T - B) * (1 - (Math.log10(Math.max(e, 0.1)) + 1) / 4);   // 0.1 m .. 1 km
  const fuse = (e, f) => 1 / Math.sqrt(1 / (e * e) + 1 / (f * f));
  const lansAvail = d => (d % 1000) < 10 * V('lans_2030');   // the share of each kilometre with a fix (illustration)
  function run(on) {
    const pts = []; let e = V('uwb'), last = 0;
    const rate = (on.vo ? V('dr_vo') : V('dr_wheel')) / 100;
    for (let d = 0; d <= D; d += 10) {
      e += rate * 10;
      if (on.uwb && d <= V('uwb_range')) e = fuse(e, V('uwb'));
      if (on.fix && d - last >= V('fix_every')) { e = fuse(e, V('fix_terrain')); last = d; }
      if (on.lans && d % 100 === 0 && lansAvail(d)) e = fuse(e, V('lans') / 1.96);
      pts.push([d, e]);
    }
    return pts;
  }
  const line = (pts, cls) => S('path', { class: cls, d: pts.map(([d, e], i) => `${i ? 'L' : 'M'}${x(d).toFixed(1)},${y(e).toFixed(1)}`).join('') });
  function draw() {
    const on = Object.fromEntries(Object.entries(layers).map(([k, c]) => [k, c.input.checked]));
    const base = run({}), mine = run(on), d = +cur.input.value, at = p => p[Math.round(d / 10)][1];
    W = widthOf(svg); fit(svg, W, H); svg.replaceChildren();
    for (const e of [0.1, 1, 10, 100, 1000]) svg.append(S('line', { class: 'pr-grid-l', x1: L, x2: W - R, y1: y(e), y2: y(e) }), S('text', { class: 'pr-tick', x: L - 6, y: y(e) + 4, 'text-anchor': 'end' }, e < 1 ? e : km(e)));
    for (let k = 0; k <= 5; k++) svg.append(S('text', { class: 'pr-tick', x: x(k * 1000), y: H - B + 18, 'text-anchor': k ? k === 5 ? 'end' : 'middle' : 'start' }, `${k} km`));
    svg.append(S('line', { class: 'pr-limit', x1: L, x2: W - R, y1: y(V('sigma_nav')), y2: y(V('sigma_nav')) }),
      line(base, 'pr-l-base'), line(mine, 'pr-l-main'),
      S('line', { class: 'pr-cursor', x1: x(d), x2: x(d), y1: T, y2: H - B }),
      S('circle', { class: 'pr-dot', cx: x(d), cy: y(at(mine)), r: 4.5 }));
    const names = Object.entries(layers).filter(([, c]) => c.input.checked).map(([k]) => ({ vo: 'cameras', fix: 'terrain fixes', uwb: 'beacons', lans: 'LunaNet' })[k]);
    setRead(out, `After <b>${km(d)}</b>: ${M(at(mine), ' m', at(mine) < 10 ? 1 : 0, 'one-sigma position error')} with ${names.length ? names.join(', ') : 'no layer'}; wheel odometry alone ${M(at(base), ' m', 0, 'one-sigma error, wheels on loose soil')}. `
      + (at(mine) <= V('sigma_nav') ? 'Inside the error the rules of the road assume.' : 'Above the error the rules of the road assume: the rover’s safety margin must grow.'));
  }
  for (const c of [...Object.values(layers), cur]) c.input.addEventListener('input', draw);
  onResize(svg, draw);
  host.append(h('div', { class: 'pr-ctl' }, h('fieldset', { class: 'pr-checks' }, h('legend', { class: 'ui-label' }, 'Layers'), Object.values(layers).map(c => c.el)), cur.el), svg,
    h('p', { class: 'pr-key small' }, h('span', { class: 'pr-ln pr-ln-main' }), ' with the layers chosen  ', h('span', { class: 'pr-ln pr-ln-base' }), ' wheel odometry alone  ', h('span', { class: 'pr-ln pr-ln-limit' }), ` ${V('sigma_nav')} m, the error the traffic rules assume (log scale)`), out);
  draw();
}

// ---------------------------------------------------------------- 2. map: catching up after time away
function figMap(host) {
  const C = 63, Rw = 62, cell = 9.6, W = C * cell, H = Rw * cell;   // 62 x 63 = 3,906 tiles
  const rates = { 10000: '10 kbit/s', 16000: '16 kbit/s', 1000000: '1 Mbit/s' };
  let rate = 10000;
  const seg = segmented({ legend: 'Link speed', options: Object.entries(rates).map(([v, l]) => ({ value: v, label: l })), value: '10000', onChange: v => { rate = +v; t.input.value = midHaz(); draw(); } });
  const t = range('Time since the link came back', { min: 0, max: 1000, step: 1, value: 1000 });
  const svg = svgBox(W, H + 46, 'The site as a grid of 3,906 tiles; the changed tiles fill in as they arrive, hazards on the route first');
  const out = readout();
  // the 42 changed tiles lie along three haul legs (an illustration of note 02's "tiles the legs cross")
  const r = rng(7), legs = [[[8, 50], [31, 31]], [[31, 31], [55, 12]], [[31, 31], [50, 52]]], tiles = [];
  for (const [[x0, y0], [x1, y1]] of legs) for (let k = 0; k < 14; k++) { const f = (k + r()) / 14; tiles.push([Math.round(x0 + (x1 - x0) * f + (r() - 0.5) * 3), Math.round(y0 + (y1 - y0) * f + (r() - 0.5) * 3)]); }
  const onRoute = i => i < 14;   // the first leg is the returning rover's route: its hazards go first
  const order = tiles.map((p, i) => i).sort((a, b) => onRoute(b) - onRoute(a) || a - b);
  const bytes = { digest: V('digest'), hazard: V('hazard_kb') * 1000, trav: V('trav_kb') * 1000, elev: V('elev_kb') * 1000 };
  const midHaz = () => { const tot = Object.values(bytes).reduce((a, b) => a + b, 0); return Math.round(1000 * (bytes.digest + bytes.hazard * 0.55) / tot); };
  const phases = [['digest', 'Digest of tile versions'], ['hazard', 'Hazards and keep-out zones'], ['trav', 'Traversability'], ['elev', 'Height refinements']];
  function draw() {
    const secs = s => s * 8 / rate, total = Object.values(bytes).reduce((a, b) => a + b, 0), now = secs(total) * t.input.value / 1000;
    let acc = 0; const ends = {}; for (const [k] of phases) { acc += secs(bytes[k]); ends[k] = acc; }
    const hazStart = ends.digest, nHaz = Math.max(0, Math.min(42, Math.floor((now - hazStart) / (ends.hazard - hazStart) * 42)));
    svg.replaceChildren(S('defs', {}, S('pattern', { id: 'pr-tilegrid', width: cell, height: cell, patternUnits: 'userSpaceOnUse' }, S('path', { class: 'pr-tilegrid', d: `M${cell},0V${cell}H0` }))), S('rect', { class: 'pr-tiles', x: 0, y: 0, width: W, height: H }), S('rect', { fill: 'url(#pr-tilegrid)', x: 0, y: 0, width: W, height: H }));
    const done = new Set(order.slice(0, nHaz));
    tiles.forEach(([cx, cy], i) => svg.append(S('rect', { class: done.has(i) ? 'pr-tile-new' : onRoute(i) ? 'pr-tile-route' : 'pr-tile-old', x: cx * cell, y: cy * cell, width: cell - 1, height: cell - 1 })));
    svg.append(S('path', { class: 'pr-route', d: `M${8 * cell},${50 * cell}L${31 * cell},${31 * cell}` }));
    // the transfer bar under the grid
    const bw = W - 8; let xx = 4;
    for (const [k] of phases) { const w = bw * secs(bytes[k]) / secs(total); svg.append(S('rect', { class: `pr-bar pr-bar-${k}`, x: xx, y: H + 12, width: Math.max(1, w - 1), height: 14 })); xx += w; }
    svg.append(S('line', { class: 'pr-cursor', x1: 4 + bw * now / secs(total), x2: 4 + bw * now / secs(total), y1: H + 6, y2: H + 32 }),
      S('text', { class: 'pr-tick', x: 4, y: H + 44 }, 'digest · hazards · traversability · heights (bar widths are bytes)'));
    const phaseNow = phases.find(([k]) => now < ends[k] - 1e-9);
    setRead(out, `At ${rates[rate]}: the digest arrives after ${M(ends.digest, ' s', 1, 'digest bytes / link rate')}, the hazard map is current after ${M(ends.hazard < 90 ? ends.hazard : ends.hazard / 60, ends.hazard < 90 ? ' s' : ' min', ends.hazard < 90 ? 0 : 1, 'digest and hazard tiles / link rate')}, all three layers after ${M(ends.elev / 60, ' min', 1, 'all changed tiles / link rate')}. `
      + `Resending the whole elevation layer would take ${M(V('full_kb') * 8000 / rate / 60, ' min', 1, 'full layer / link rate')}. Now: ${phaseNow ? phaseNow[1].toLowerCase() : 'all changes received'}, ${nHaz} of 42 changed tiles in.`);
  }
  t.input.value = midHaz(); t.input.addEventListener('input', draw);
  host.append(h('div', { class: 'pr-ctl' }, seg.el, t.el), svg, h('p', { class: 'pr-key small' }, h('span', { class: 'pr-sw pr-sw-new' }), ' received  ', h('span', { class: 'pr-sw pr-sw-route' }), ' changed, on the rover’s route  ', h('span', { class: 'pr-sw pr-sw-old' }), ' changed elsewhere'), out);
  draw();
}

// ---------------------------------------------------------------- 3. time: two clocks and a resync
function figTime(host) {
  let W = 640; const H = 220, L = 58, R = 30, T = 14, B = 30;
  const osc = { tcxo: ['Crystal', V('tcxo') * 1e-3 / 86400], csac: ['Chip-scale atomic clock', V('csac') * 1e-6 / 86400] };
  const ivals = [[10, '10 s'], [60, '1 min'], [600, '10 min'], [3600, '1 h'], [86400, '1 day']];
  let o = 'tcxo';
  const seg = segmented({ legend: 'Oscillator', options: Object.entries(osc).map(([v, [l]]) => ({ value: v, label: l })), value: o, onChange: v => { o = v; draw(); } });
  const iv = range('Time between resyncs', { min: 0, max: ivals.length - 1, step: 1, value: 2 });
  const svg = svgBox(W, H, 'Clock offset over four resync intervals: it grows until each resync and drops to zero');
  const needs = h('ul', { class: 'pr-needs' }); const out = readout();
  const unit = s => s >= 1e-3 ? [s * 1e3, ' ms'] : s >= 1e-6 ? [s * 1e6, ' µs'] : [s * 1e9, ' ns'];
  function draw() {
    const [I, Il] = ivals[+iv.input.value], drift = osc[o][1], worst = drift * I, span = 4 * I;
    W = widthOf(svg); fit(svg, W, H);
    const [ws, wu] = unit(worst), x = s => L + (W - L - R) * s / span, y = v => H - B - (H - T - B) * v / worst;
    svg.replaceChildren(S('line', { class: 'pr-grid-l', x1: L, x2: W - R, y1: y(0), y2: y(0) }), S('line', { class: 'pr-grid-l', x1: L, x2: W - R, y1: y(worst), y2: y(worst) }),
      S('text', { class: 'pr-tick', x: L - 6, y: y(0) + 4, 'text-anchor': 'end' }, '0'), S('text', { class: 'pr-tick', x: L - 6, y: y(worst) + 4, 'text-anchor': 'end' }, `${fmt(ws, ws < 10 ? 2 : 0)}${wu}`));
    let d = ''; for (let k = 0; k < 4; k++) d += `M${x(k * I)},${y(0)}L${x((k + 1) * I)},${y(worst)}L${x((k + 1) * I)},${y(0)}`;
    svg.append(S('path', { class: 'pr-l-main', d }));
    for (let k = 1; k <= 4; k++) svg.append(S('text', { class: 'pr-tick', x: x(k * I), y: H - B + 18, 'text-anchor': k === 4 ? 'end' : 'middle' }, W < 420 ? `${k}` : `resync ${k}`));
    const rangeErr = worst * 299792458;
    const list = [[`One-way radio ranging to 1 m`, 1 / 299792458], [`Position time stamps`, V('need_stamp') / 1e3], [`Road reservations`, V('need_resv')]];
    needs.replaceChildren(...list.map(([n, need]) => { const ok = worst <= need, [a, u] = unit(need); return h('li', { class: ok ? 'ok' : 'no' }, h('b', {}, ok ? 'met' : 'not met'), ` ${n}: needs ${fmt(a, a < 10 ? 1 : 0)}${u}`); }));
    setRead(out, `${osc[o][0]}, resync every ${Il}: the worst offset before a resync is ${M(ws, wu, ws < 10 ? 2 : 0, 'drift rate x interval')}, which is ${rangeErr >= 1000 ? M(rangeErr / 1000, ' km', rangeErr < 1e4 ? 1 : 0, 'offset x speed of light') : M(rangeErr, ' m', rangeErr < 10 ? 2 : 0, 'offset x speed of light')} of one-way range error. Two-way ranging cancels the offset and needs no common time.`);
  }
  iv.input.addEventListener('input', draw);
  host.append(h('div', { class: 'pr-ctl' }, seg.el, iv.el), h('div', { class: 'pr-time' }, svg, needs), out);
  draw(); onResize(svg, draw);
}

// ---------------------------------------------------------------- 4. radio: the engine's link budget
function capacityHere(loss, bw) { return capacity(loss, { bw, txW: V('tx_w'), gain: V('gain'), nf: V('nf'), margin: V('margin') }); }
function figRadio(host) {
  let W = 640; const H = 230, G = 170;
  const bands = { bb: ['2.4 GHz broadband', 2.4e9, 1e6], nb: ['0.4 GHz narrow-band', 0.4e9, 25e3] };
  let band = 'bb', ant = '2.5';
  const segB = segmented({ legend: 'Band', options: Object.entries(bands).map(([v, [l]]) => ({ value: v, label: l })), value: band, onChange: v => { band = v; draw(); } });
  const segH = segmented({ legend: 'Antenna height', options: [{ value: '1', label: '1 m (small robot)' }, { value: '2.5', label: '2.5 m (rover)' }], value: ant, onChange: v => { ant = v; draw(); } });
  const dist = range('Distance between the two', { min: 0, max: 1000, step: 1, value: 520 });
  const hill = check('A ridge between them', true), relay = check('A 10 m relay mast on the ridge', false);
  const svg = svgBox(W, H, 'Side view: two antennas, an optional ridge and relay mast, and the radio paths');
  const out = readout();
  const dOf = v => Math.round(100 * 10 ** (v / 1000 * Math.log10(150)));   // 100 m .. 15 km, log
  function hop(d, ha, hb) {
    const [, f, bw] = bands[band], loss = flatLoss(d, ha, hb, f), c = capacityHere(loss, bw), hz = horizon(ha) + horizon(hb);
    return { d, loss, ...c, hz, ok: d <= hz && c.kbps * 1e3 >= V('rate') * 1e3 };
  }
  function draw() {
    const d = dOf(+dist.input.value), hh = +ant, direct = hop(d, hh, hh), blocked = hill.input.checked;
    const useRelay = relay.input.checked && blocked, a = hop(d / 2, hh, 10), okDirect = direct.ok && !blocked, okRelay = useRelay && a.ok;
    W = widthOf(svg); fit(svg, W, H);
    const x0 = 40, x1 = W - 40, xm = (x0 + x1) / 2, ant0 = G - 22, ridgeTop = G - 70;
    svg.replaceChildren(S('path', { class: 'pr-ground', d: `M0,${G} Q${W / 2},${G - 12} ${W},${G} L${W},${H} L0,${H}Z` }));
    if (blocked) svg.append(S('path', { class: 'pr-ridge', d: `M${xm - W / 7},${G - 6} L${xm},${ridgeTop} L${xm + W / 7},${G - 6}Z` }));
    for (const xx of [x0, x1]) svg.append(S('line', { class: 'pr-mast', x1: xx, x2: xx, y1: G - 6, y2: ant0 }), S('circle', { class: 'pr-ant', cx: xx, cy: ant0, r: 5 }));
    svg.append(S('text', { class: 'pr-tick', x: x0, y: G + 22, 'text-anchor': 'middle' }, 'rover A'), S('text', { class: 'pr-tick', x: x1, y: G + 22, 'text-anchor': 'middle' }, 'rover B'),
      S('text', { class: 'pr-tick', x: xm, y: G + 22, 'text-anchor': 'middle' }, km(d)));
    svg.append(S('line', { class: okDirect ? 'pr-link-ok' : 'pr-link-no', x1: x0, y1: ant0, x2: x1, y2: ant0 }));
    if (useRelay) {
      const mt = ridgeTop - 44;
      svg.append(S('line', { class: 'pr-mast', x1: xm, x2: xm, y1: ridgeTop, y2: mt }), S('circle', { class: 'pr-ant', cx: xm, cy: mt, r: 5 }),
        S('path', { class: okRelay ? 'pr-link-ok' : 'pr-link-no', d: `M${x0},${ant0} L${xm},${mt} L${x1},${ant0}` }));
    }
    const why = l => !l.ok && l.d > l.hz ? `beyond the radio horizon (${km(l.hz)})` : !l.ok ? 'too weak for the rate' : 'holds';
    let txt = `Direct, ${km(d)} at ${bands[band][0]}: path loss ${M(direct.loss, ' dB', 0, 'flat-ground law of lunarsim/atc/radio.py')}, signal-to-noise after the margin ${M(direct.snr, ' dB', 0, 'link budget')}, capacity ${M(Math.min(direct.kbps, 99999), ' kbit/s', 0, 'Shannon')} against ${fmt(V('rate'), 0)} needed: `;
    txt += blocked ? '<b>lost</b>: the ridge blocks the line of sight, and the engine counts a blocked path as no link.' : `<b>${why(direct)}</b>.`;
    if (useRelay) txt += ` Through the mast: two hops of ${km(d / 2)}, each ${M(Math.min(a.kbps, 99999), ' kbit/s', 0, 'Shannon, per hop')}: <b>${why(a)}</b>.`;
    else if (blocked) txt += ' Put a relay on the ridge, or store the message and send it later.';
    setRead(out, txt);
  }
  for (const c of [dist, hill, relay]) c.input.addEventListener('input', draw);
  onResize(svg, draw);
  host.append(h('div', { class: 'pr-ctl' }, segB.el, segH.el, dist.el, h('div', { class: 'pr-checks' }, hill.el, relay.el)), svg, out);
  draw();
}

// ---------------------------------------------------------------- 5. the messages: POSITION byte by byte, manifests
function figMsg(host) {
  // example values; the layout is note 03, section C2 (big-endian, bit fields most significant bit first)
  const F = [
    ['SPP version, type, flag', 'head', 5, 0b00001], ['APID (0x500 + POSITION)', 'head', 11, 0x501], ['Sequence flags and count', 'head', 16, (3 << 14) | 42], ['Packet data length', 'head', 16, 41 - 6 - 1],
    ['LRIP version 0.1', 'lrip', 8, 0x01], ['Message type: POSITION', 'lrip', 8, 1], ['Sender id 291', 'lrip', 16, 291], ['Valid at (0.1 s since the epoch)', 'lrip', 32, 123456789],
    ['East: 1,234.56 m', 'pay', 24, 123456], ['North: -2,045.30 m', 'pay', 24, -204530], ['Height: 12.3 m', 'pay', 16, 123], ['Heading: 271.5°', 'pay', 12, 2715], ['Speed: 0.62 m/s', 'pay', 10, 62],
    ['Position error: 1.0 m (1 sigma)', 'pay', 8, 20], ['Source: beacon ranging', 'pay', 3, 3], ['Moving', 'pay', 1, 1], ['Spare', 'pay', 6, 0],
    ['Key index', 'sec', 16, 0x0102], ['Counter (stops replays)', 'sec', 32, 1001], ['Authentication code (owner key; placeholder bytes)', 'mac', 64, null],
  ];
  const bits = [];
  for (const [, , n, v] of F) for (let i = n - 1; i >= 0; i--) bits.push(v === null ? ((i * 7 + bits.length) % 3 === 0 ? 1 : 0) : Number((BigInt.asUintN(n, BigInt(v)) >> BigInt(i)) & 1n));
  const bytes = []; for (let i = 0; i < bits.length; i += 8) bytes.push(bits.slice(i, i + 8).reduce((a, b) => a * 2 + b, 0));
  let pos = 0; const span = F.map(f => { const s = pos; pos += f[2]; return [s, pos]; });
  const PART = { head: 'packet header', lrip: 'protocol header', pay: 'position content', sec: 'security header', mac: 'authentication code' };
  const grid = h('div', { class: 'pr-bytes', role: 'list', 'aria-label': `POSITION report, ${bytes.length} bytes` },
    bytes.map((b, i) => h('span', { class: `pr-byte pr-p-${F[span.findIndex(([s, e]) => i * 8 >= s && i * 8 < e)][1]}`, role: 'listitem', 'data-i': i }, b.toString(16).padStart(2, '0'))));
  const fields = h('div', { class: 'pr-fields', role: 'group', 'aria-label': 'Fields' });
  const out = readout();
  function pick(k) {
    const [s, e] = span[k];
    for (const el of grid.children) { const i = +el.dataset.i; el.classList.toggle('on', i * 8 < e && i * 8 + 8 > s); }
    for (const b of fields.children) b.setAttribute('aria-pressed', String(+b.dataset.k === k));
    setRead(out, `<b>${F[k][0]}</b>: ${F[k][2]} bits of the ${PART[F[k][1]]}, bits ${s} to ${e - 1}. The whole report is ${M(bytes.length, ' bytes', 0, 'sum of the field widths')}, of which ${M(13, ' bytes', 0, '104 payload bits')} are content.`);
  }
  F.forEach((f, k) => fields.append(h('button', { type: 'button', class: `pr-field pr-p-${f[1]}`, 'data-k': k, 'aria-pressed': 'false', onclick: () => pick(k) }, f[0])));
  // the manifests (note 03, C3): which vehicle can take a job?
  const MAN = {
    'Small rover (owner B)': { 'transport.carry': { mass_kg: 200 }, 'relay.store_forward': { buffer_mb: 64 }, 'survey.image': {}, 'team.lift': { share_kg: 90 } },
    'Hopper (owner C)': { 'transport.hop': { mass_kg: 10, range_km: 2 }, 'survey.psr': { dwell_min: 45 }, 'relay.high_point': { height_m: 100 } },
  };
  const JOBS = {
    carry: ['Carry 150 kg', 'transport.carry', p => p.mass_kg >= 150],
    hop: ['8 kg over a crater', 'transport.hop', p => p.mass_kg >= 8 && p.range_km >= 1.5],
    psr: ['Survey in shadow', 'survey.psr', p => p.dwell_min >= 30],
    relay: ['Hold 60 MB', 'relay.store_forward', p => p.buffer_mb >= 60],
  };
  const cards = h('div', { class: 'pr-man' }), mout = readout();
  const segJ = segmented({ legend: 'A job is posted', options: Object.entries(JOBS).map(([v, [l]]) => ({ value: v, label: l })), value: 'carry', onChange: v => match(v) });
  function match(j) {
    const [, cap, test] = JOBS[j];
    cards.replaceChildren(...Object.entries(MAN).map(([name, caps]) => {
      const ok = caps[cap] && test(caps[cap]);
      return h('div', { class: `pr-card ${ok ? 'ok' : 'no'}` }, h('p', { class: 'ui-label' }, name), h('ul', {}, Object.entries(caps).map(([c, p]) => h('li', { class: c === cap ? 'hit' : '' }, h('code', {}, c), Object.keys(p).length ? ` ${Object.entries(p).map(([k, v]) => `${k} ≤ ${v}`).join(', ')}` : ''))), h('p', { class: 'pr-verdict' }, ok ? 'can bid' : 'cannot bid'));
    }));
    const who = Object.entries(MAN).filter(([, caps]) => caps[cap] && test(caps[cap])).map(([n]) => n.split(' (')[0].toLowerCase());
    const LONG = { carry: 'carry 150 kg from the depot to the base', hop: 'take 8 kg 1.5 km across a crater', psr: 'survey a shadowed crater for 30 minutes', relay: 'hold 60 MB of messages for a rover out of range' };
    mout.textContent = `The job (${LONG[j]}) asks for "${cap}". ${who.length ? `Only the ${who.join(' and the ')} lists it with enough capacity, so only it bids.` : 'No vehicle lists it.'} Unknown capabilities are skipped, so a rover never has to understand a hopper's.`;
  }
  host.append(h('p', { class: 'ui-label' }, 'A POSITION report on the air'), grid, h('p', { class: 'pr-key small' }, Object.entries(PART).flatMap(([k, l]) => [h('span', { class: `pr-sw pr-p-${k}` }), ` ${l}  `])), fields, out,
    h('div', { class: 'pr-ctl pr-ctl-gap' }, segJ.el), cards, mout);
  pick(8); match('carry');
}

// ---------------------------------------------------------------- 6. a rover fails: the job changes hands
function figAuction(host) {
  let W = 640; const H = 230, L = 70, R = 14, T0 = 0, T1 = 180;
  const f = range('Rover B stops at', { min: 10, max: 120, step: 1, value: 40 });
  const svg = svgBox(W, H, 'Timeline of rovers A, B and C: the job announced, bids, the award to B, B going silent, the re-auction and C taking over');
  const out = readout();
  const x = t => L + (W - L - R) * (t - T0) / (T1 - T0), lane = { A: 60, B: 110, C: 160 };
  function draw() {
    W = widthOf(svg); fit(svg, W, H);
    const tf = +f.input.value, ts = tf + V('t_suspect'), ti = tf + V('t_isolate'), tw = ti + 4, tc = ti + 6;
    svg.replaceChildren();
    for (let t = 0; t <= T1; t += W < 420 ? 60 : 30) svg.append(S('line', { class: 'pr-grid-l', x1: x(t), x2: x(t), y1: 30, y2: H - 26 }), S('text', { class: 'pr-tick', x: x(t), y: H - 10, 'text-anchor': 'middle' }, `${t} s`));
    for (const [r, yy] of Object.entries(lane)) {
      svg.append(S('text', { class: 'pr-lane-t', x: L - 12, y: yy + 4, 'text-anchor': 'end' }, `rover ${r}`));
      for (let t = 0; t <= T1; t += 2) if (!(r === 'B' && t >= tf)) svg.append(S('line', { class: 'pr-beat', x1: x(t), x2: x(t), y1: yy - 4, y2: yy + 4 }));
    }
    svg.append(S('rect', { class: 'pr-held', x: x(tf), y: lane.B - 10, width: x(T1) - x(tf), height: 20 }));
    const ev = (t, r, label, cls = '', below = false) => svg.append(S('circle', { class: `pr-ev ${cls}`, cx: x(t), cy: lane[r], r: 6 }), S('text', { class: 'pr-ev-t', x: x(t), y: lane[r] + (below ? 22 : -14), 'text-anchor': 'middle' }, label));
    ev(0, 'A', 'job posted'); ev(4, 'B', 'B wins'); ev(tf, 'B', 'silent', 'bad'); ev(ts, 'A', 'suspect', 'warn'); ev(ti, 'C', 're-auction'); ev(tw, 'C', 'C wins', 'good', true);
    svg.append(S('text', { class: 'pr-tick', x: x(T1), y: lane.B + 24, 'text-anchor': 'end' }, 'B’s road reservation stays held'));
    setRead(out, `B stops at ${fmt(tf, 0)} s. Its neighbours miss its heartbeats and suspect it at ${fmt(ts, 0)} s, give it up at ${fmt(ti, 0)} s and re-auction the job under a new epoch; C wins at ${fmt(tw, 0)} s and claims it at ${fmt(tc, 0)} s, ${M(tc - tf, ' s', 0, 'timers of the lost-link rule')} after B went quiet. If the decision waited for Earth, the expected extra delay at our base is ${num(P.earth_wait)}.`);
  }
  f.input.addEventListener('input', draw); onResize(svg, draw);
  host.append(h('div', { class: 'pr-ctl' }, f.el), svg, out);
  draw();
}

// ---------------------------------------------------------------- 7. integrity: a wrong report caught
function figIntegrity(host) {
  let W = 640; const H = 240, L = 46, R = 14, T = 12, B = 30, N = 60, START = 20;
  const Sv = V('uwb') ** 2 + 2 * V('sigma_nav') ** 2, g = V('gamma1');   // range noise + both rovers' navigation error
  let fault = 'drift';
  const seg = segmented({ legend: 'The neighbour’s report', options: [{ value: 'none', label: 'Honest' }, { value: 'drift', label: 'Drifts away slowly' }, { value: 'jump', label: 'Jumps' }], value: fault, onChange: v => { fault = v; mag.input.value = v === 'jump' ? 15 : 5; draw(); } });
  const mag = range('Size of the fault (m per 10 s, or m)', { min: 1, max: 30, step: 1, value: 5 });
  const svg = svgBox(W, H, 'The test statistic for each report, its threshold, and the moment the neighbour is declared suspect');
  const out = readout();
  const x = t => L + (W - L - R) * t / N, y = d => T + (H - T - B) * (1 - Math.log10(Math.max(d, 0.01)) / 4 - 0.5);   // 0.01 .. 1000 on a log scale
  function draw() {
    const nz = gauss(rng(11)), m = +mag.input.value, flags = []; let suspect = null, firstFlag = null;
    W = widthOf(svg); fit(svg, W, H);
    const bias = t => fault === 'none' || t < START ? 0 : fault === 'jump' ? m : m * (t - START) / 10;
    svg.replaceChildren();
    for (const d of [0.01, 1, 100]) svg.append(S('line', { class: 'pr-grid-l', x1: L, x2: W - R, y1: y(d), y2: y(d) }), S('text', { class: 'pr-tick', x: L - 6, y: y(d) + 4, 'text-anchor': 'end' }, d));
    svg.append(S('line', { class: 'pr-limit', x1: L, x2: W - R, y1: y(g), y2: y(g) }), S('text', { class: 'pr-tick pr-limit-t', x: L + 6, y: y(g) - 6 }, `threshold ${fmt(g, 2)}`));
    for (let t = 0; t < N; t++) {
      const v = nz() * Math.sqrt(Sv) + bias(t), d2 = v * v / Sv, flag = d2 > g;
      flags.push(flag); if (flag && firstFlag === null) firstFlag = t;
      if (suspect === null && flags.slice(-5).filter(Boolean).length >= 3) suspect = t;
      svg.append(S('circle', { class: flag ? 'pr-flagged' : 'pr-pass', cx: x(t + 0.5), cy: y(d2), r: 3.4 }));
    }
    for (let t = 0; t <= N; t += W < 420 ? 20 : 10) svg.append(S('text', { class: 'pr-tick', x: x(t), y: H - 10, 'text-anchor': 'middle' }, `${t} s`));
    if (fault !== 'none') svg.append(S('line', { class: 'pr-cursor', x1: x(START), x2: x(START), y1: T, y2: H - B }));
    if (suspect !== null) svg.append(S('rect', { class: 'pr-suspect', x: x(suspect), y: T, width: x(N) - x(suspect), height: H - T - B }), S('text', { class: 'pr-ev-t', x: x(suspect) + 6, y: H - B - 8 }, 'declared suspect'));
    const errAt = suspect !== null ? bias(suspect) : 0;
    setRead(out, fault === 'none'
      ? `An honest neighbour: ${flags.filter(Boolean).length} of ${N} reports cross the threshold in this run (one in a thousand is expected), and ${suspect === null ? 'it is never declared suspect' : `it is declared suspect at ${suspect} s`}.`
      : `The fault starts at ${START} s. ${firstFlag !== null ? `First report over the threshold at ${firstFlag} s` : 'No report crosses the threshold'}; ${suspect !== null ? `declared suspect at ${suspect} s, when its report is ${M(errAt, ' m', 0, 'injected error at that moment')} off` : 'never declared suspect: the error stays inside the noise of a 2 m navigation error'}. The others are then told, and its space is widened.`);
  }
  mag.input.addEventListener('input', draw); onResize(svg, draw);
  host.append(h('div', { class: 'pr-ctl' }, seg.el, mag.el), svg, out);
  draw();
}

// ---------------------------------------------------------------- 8. who has flown what (note 04, section C)
const WHO = [
  ['flown', 'Intuitive Machines', 'USA', 'IM-1 (2024) and IM-2 (Mar 2025) landed and tipped over', 'IM-2 carried a hopper and other makers’ rovers; none deployed', 'claimed'],
  ['flown', 'Firefly', 'USA', 'Blue Ghost 1 landed 2 Mar 2025 and worked 346 h', 'none yet; mission 2 to carry Rashid Rover 2', 'claimed'],
  ['flown', 'ispace', 'Japan', 'Hard landings in 2023 and June 2025', 'one micro-rover per mission (lost)', 'no'],
  ['flown', 'Lunar Outpost', 'USA', 'MAPP rover reached the surface inside IM-2, not deployed', 'one', 'no'],
  ['flown', 'CNSA Chang’e 6', 'China', 'Far-side sample return, May to June 2024', 'lander and a 5 kg mini-rover', 'no'],
  ['flown', 'ISRO Chandrayaan-3', 'India', 'Landed 23 Aug 2023; rover drove 101.4 m', 'lander and one rover, ground-commanded', 'no'],
  ['earth', 'DLR ARCHES', 'Germany', 'Mount Etna, June to July 2022', 'two rovers, a drone and a lander mock-up', 'partly'],
  ['earth', 'CoRob-X (DFKI lead)', 'EU', 'Lanzarote, Jan to Feb 2023', 'three rovers of three makers, one plan, map merging', 'yes, in one project'],
  ['earth', 'ESA Space Resources Challenge', 'Europe', 'LUNA hall, 2025', 'per team', 'no'],
  ['planned', 'NASA / JPL CADRE', 'USA', 'Built 2024; flies on IM-3, Q1 2027 at the earliest', 'three rovers and a base station, one owner', 'no'],
  ['planned', 'NASA LTV Services', 'USA', 'Two crew-rover task orders, May 2026; on the Moon by 2028', 'two rovers of two makers', 'not stated'],
  ['planned', 'NASA VIPER', 'USA', 'On the second Blue Moon Mark 1, 2027 at the earliest', 'one', 'no'],
  ['planned', 'NASA MoonFall, PROMISE', 'USA', '2028 targets', 'about four drones; one rover', 'not stated'],
  ['planned', 'Astrobotic / Voyager', 'USA', 'Griffin-1 no earlier than Jan 2027', 'FLIP and CubeRover on one lander', 'no'],
  ['planned', 'CNSA Chang’e 7', 'China', 'Moved from Aug 2026 to 2027', 'lander, rover and hopper', 'no'],
  ['planned', 'CNSA Chang’e 8 / ILRS', 'China and partners', '2028 to 2029', 'robots from at least four organisations in three countries', 'claimed'],
  ['planned', 'ISRO / JAXA LUPEX', 'India / Japan', '2028 to 2029', 'lander and a 350 kg rover', 'two agencies'],
  ['sim', 'LunarHaul / Lunar ATC', 'this project', 'Simulated only', '8 vehicles of 3 owners, and fleets 8 times larger', 'yes, by design'],
];
function figWho(host) {
  const KIND = { all: 'All', flown: 'Flown to the Moon', earth: 'Tested on Earth', planned: 'Planned', sim: 'Simulated' }, SHORT = { all: 'All', flown: 'Flown', earth: 'Earth tests', planned: 'Planned', sim: 'Simulated' };
  const body = h('tbody'), cap = h('caption', { class: 'visually-hidden' });
  const seg = segmented({ legend: 'Show', options: Object.entries(SHORT).map(([v, l]) => ({ value: v, label: l })), value: 'all', onChange: v => draw(v) });
  function draw(k) {
    const rows = WHO.filter(r => k === 'all' || r[0] === k);
    cap.textContent = `${KIND[k]}: ${rows.length} projects`;
    body.replaceChildren(...rows.map(([kind, name, c, flew, robots, interop]) => h('tr', {}, h('th', { scope: 'row' }, name, h('span', { class: 'pr-country' }, ` · ${c}`)), h('td', { 'data-label': 'What flew, and when' }, h('span', { class: `pr-kind pr-k-${kind}` }, KIND[kind]), ' ', flew), h('td', { 'data-label': 'Robots working together' }, robots), h('td', { 'data-label': 'Works with other makers' }, interop))));
  }
  host.append(h('div', { class: 'pr-ctl' }, seg.el), h('div', { class: 'pr-scroll' }, h('table', { class: 'pr-table' }, cap,
    h('thead', {}, h('tr', {}, ['Project', 'What flew, and when', 'Robots working together', 'Works with other makers'].map(t => h('th', { scope: 'col' }, t)))), body)));
  draw('all');
}

const FIGS = { pos: figPos, map: figMap, time: figTime, radio: figRadio, msg: figMsg, auction: figAuction, integrity: figIntegrity, who: figWho };
for (const host of document.querySelectorAll('.pr-host[data-fig]')) {
  try { FIGS[host.dataset.fig](host); } catch (e) { host.append(h('p', { class: 'stub' }, `This figure could not be drawn (${e.message}).`)); console.error(e); }
}
mountNavStack();
upgradeFlags(document.querySelector('main'));
if (reducedMotion()) document.documentElement.classList.add('pr-still');
