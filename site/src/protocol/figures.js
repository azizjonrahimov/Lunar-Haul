// /protocol/ (F-60): eight figures, one per problem group (loaded lazily by main.js since F-61). Figure 1 draws E50's
// one-month trace, figure 2 E52's map sync, figure 3 E51's clock results, figure 5 LRIP v0.1's golden POSITION packet and
// the measured panels of problems 4, 6 and 7 E54's message delivery and E55's integrity results (F-56); the others compute in the browser from src/protocol/params.js (the research notes' values)
// until BACKEND's B-99 exports replace them; the link budget is a port of
// lunarsim/atc/radio.py. Hand-written SVG, native controls, a readout that is also the figure's text version.
import { segmented, h, reducedMotion } from '../ui/index.js';
import { upgradeFlags } from '../ui/tooltip.js';
import { num, fmt } from '../components/num.js';
import { P } from './params.js';
import { horizon, flatLoss, capacity } from './radio.js';
import { e50Runs, e50Middle } from './e50.js';
import { lripDecode } from './lrip.js';

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

// ---------------------------------------------------------------- 1. positioning: E50 (B-90), from B-99's figure file
// data/atc/protocol/e50_layers.json (B-99), staged unchanged as protocol/b99/e50_layers.json after the index check: the
// busiest 24 h of the most-driving vehicle at 2 min steps. Log scale, 0.1 m to 1 km; the 5 m budget dashed; driving shaded.
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const whenH = t => { const d = new Date(Date.UTC(2028, 0, 1) + t * 3600e3); return `${d.getUTCDate()} ${MON[d.getUTCMonth()]}, ${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')} UTC`; };
async function figPos(host) {
  // F-65: B-99's e50_layers.json (protocol/b99/, checked against its index): the busiest 24 h of the most-driving vehicle at
  // 2 min steps, per layer set the error and the vehicle's own 95 % bound; and the month over 30 seeds per layer set
  const r = await fetch(`${import.meta.env.BASE_URL}protocol/b99/e50_layers.json`);
  if (!r.ok) throw new Error(`protocol/b99/e50_layers.json: HTTP ${r.status}`);
  const D = await r.json();
  if (D.format !== 'lunarsim-protocol-data' || D.version !== 1 || !D.sets) throw new Error(`e50_layers.json: format ${D.format}`);
  const SRC = 'data/atc/protocol/e50_layers.json', keys = Object.keys(D.sets), BUD = D.budget_m, n = D.t_h.length;
  const v = { bins: n, moving: D.moving.join('') };
  let W = 640, set = keys.includes('dr+ranging+fixes') ? 'dr+ranging+fixes' : keys[0];
  const H = 300, L = 52, R = 16, T = 14, B = 34;
  const label = k => { const s = D.set_labels?.[k] || k; return s[0].toUpperCase() + s.slice(1); };
  const SAY = { dr: 'dead reckoning only', 'dr+ranging': 'dead reckoning and ranging', 'dr+ranging+fixes': 'dead reckoning, ranging and terrain fixes', 'lans@2030': 'every layer, LunaNet as in 2030' }, say = k => SAY[k] || label(k);
  const E = (value, what) => num({ value, unit: ' m', digits: value < 10 ? 1 : 0, flag: 'Modelled', source: `${SRC}: vehicle ${D.vehicle}, ${what}` });
  const segS = segmented({ legend: 'Layers', options: keys.map(k => ({ value: k, label: label(k) })), value: set, onChange: x => { set = x; draw(); } });
  const cur = range('Time in the day', { min: 0, max: n - 1, step: 1, value: e50Middle(v) });
  const svg = svgBox(W, H, 'Position error over the vehicle’s busiest day, on a log scale: dead reckoning alone and with the chosen layers, the vehicle’s own 95 % bound and the 5 m budget');
  const out = readout();
  function draw() {
    const s = D.sets[set], dr = D.sets.dr, i = Math.min(n - 1, +cur.input.value), name = label(set), mo = D.month_1x_30_seeds?.[set];
    W = widthOf(svg); fit(svg, W, H); svg.replaceChildren();
    const x = k => L + (W - L - R) * k / n, y = e => T + (H - T - B) * (1 - (Math.log10(Math.max(e, 0.1)) + 1) / 4);
    const line = (arr, cls) => S('path', { class: cls, d: arr.map((e, k) => `${k ? 'L' : 'M'}${x(k + 0.5).toFixed(1)},${y(e).toFixed(1)}`).join('') });
    for (const [a, b] of e50Runs(v)) svg.append(S('rect', { class: 'pr-drive', x: x(a), y: T, width: Math.max(1, x(b) - x(a)), height: H - T - B }));
    for (const e of [0.1, 1, 10, 100, 1000]) svg.append(S('line', { class: 'pr-grid-l', x1: L, x2: W - R, y1: y(e), y2: y(e) }), S('text', { class: 'pr-tick', x: L - 6, y: y(e) + 4, 'text-anchor': 'end' }, e < 1 ? e : km(e)));
    const every = W < 480 ? 8 : 4;
    for (let hh = 0; hh <= 24; hh += every) { const k = D.t_h.findIndex(t => t >= hh); if (k < 0) continue; svg.append(S('text', { class: 'pr-tick', x: x(k), y: H - B + 18, 'text-anchor': hh ? 'middle' : 'start' }, hh ? `+${hh} h` : whenH(D.t0_h).replace(' UTC', ''))); }
    svg.append(S('line', { class: 'pr-limit', x1: L, x2: W - R, y1: y(BUD), y2: y(BUD) }));
    if (set !== 'dr') svg.append(line(dr.err_m, 'pr-l-base'));
    svg.append(line(s.b95_m, 'pr-l-bound'), line(s.err_m, 'pr-l-main'),
      S('line', { class: 'pr-cursor', x1: x(i + 0.5), x2: x(i + 0.5), y1: T, y2: H - B }),
      S('circle', { class: 'pr-dot', cx: x(i + 0.5), cy: y(s.err_m[i]), r: 4.5 }));
    setRead(out, `<b>${whenH(D.t0_h + D.t_h[i])}</b>, vehicle ${D.vehicle} ${D.moving[i] ? 'driving' : 'parked'}, with ${say(set)}: error ${E(s.err_m[i], `${name}, error`)}, `
      + `its own 95 % bound ${E(s.b95_m[i], `${name}, its 95 % bound`)} (${s.b95_m[i] <= BUD ? 'inside' : 'over'} the ${fmt(BUD, 0)} m budget)`
      + (set !== 'dr' ? `; dead reckoning alone ${E(dr.err_m[i], 'dead reckoning, error')}` : '') + '. '
      + (mo ? `Over the whole month and ${num({ value: 30, unit: ' seeds', digits: 0, flag: 'Modelled', source: `${SRC}: month_1x_30_seeds` })}, with ${say(set)} the error’s 95th percentile is ${num({ value: mo.p95_m, unit: ' m', digits: mo.p95_m < 10 ? 1 : 0, flag: 'Modelled', source: `${SRC}: month_1x_30_seeds.${set}.p95_m` })} (median ${num({ value: mo.median_m, unit: ' m', digits: 1, flag: 'Modelled', source: `${SRC}: month_1x_30_seeds.${set}.median_m` })}) and the bound is over ${fmt(BUD, 0)} m ${num({ value: 100 * mo.share_b95_over_budget, unit: ' %', digits: 0, flag: 'Modelled', source: `${SRC}: month_1x_30_seeds.${set}.share_b95_over_budget` })} of the time.` : ''));
  }
  cur.input.addEventListener('input', draw);
  onResize(svg, draw);
  host.append(h('div', { class: 'pr-ctl' }, segS.el, cur.el), svg,
    h('p', { class: 'pr-key small' }, h('span', { class: 'pr-ln pr-ln-main' }), ' error with the layers chosen  ', h('span', { class: 'pr-ln pr-ln-bound' }), ' the vehicle’s own 95 % bound  ',
      h('span', { class: 'pr-ln pr-ln-base' }), ' dead reckoning alone  ', h('span', { class: 'pr-ln pr-ln-limit' }), ` the ${fmt(BUD, 0)} m budget  `, h('span', { class: 'pr-sw pr-sw-drive' }), ' driving (log scale)'), out);
  draw();
}

// ---------------------------------------------------------------- 2. map: catching up after time away
// E52 (protocol/e52.json from results/E52_map.json, 30 seeds): after hours to days out of contact, the bytes to sync and
// the time until the hazard layer is current, hazards-first against oldest-first, at four link rates; and the hazards a
// rover meets on a stale map, during the outage and after contact. The change rates and the hidden share are Assumed.
const OUT_NAME = { 1: '1 h', 6: '6 h', 24: '1 day', 72: '3 days', 168: '7 days', 336: '14 days' };
const secsText = s => (s < 90 ? `${fmt(s, s < 10 ? 1 : 0)} s` : s < 5400 ? `${fmt(s / 60, s < 600 ? 1 : 0)} min` : `${fmt(s / 3600, 1)} h`);
async function figMap(host) {
  const r = await fetch(`${import.meta.env.BASE_URL}protocol/e52.json`);
  if (!r.ok) throw new Error(`protocol/e52.json: HTTP ${r.status}`);
  const E = await r.json();
  if (E.format !== 'lunarsim-e52-site' || E.version !== 1) throw new Error(`e52.json: format ${E.format}`);
  const outs = [...new Set(E.rows.map(x => x.out_h))].sort((a, b) => a - b), rates = [...new Set(E.rows.map(x => x.rate_kbps))].sort((a, b) => a - b);
  let out = outs.includes(24) ? 24 : outs[0], rate = rates.includes(16) ? 16 : rates[0], W = 640;
  const row = (o, ord, k = rate) => E.rows.find(x => x.out_h === o && x.order === ord && x.rate_kbps === k);
  const segO = segmented({ legend: 'Time out of contact', options: outs.map(o => ({ value: String(o), label: OUT_NAME[o] || `${o} h` })), value: String(out), onChange: v => { out = +v; draw(); } });
  const segR = segmented({ legend: 'Link speed', options: rates.map(k => ({ value: String(k), label: k >= 1000 ? `${fmt(k / 1000, 0)} Mbit/s` : `${k} kbit/s` })), value: String(rate), onChange: v => { rate = +v; draw(); } });
  const svgT = svgBox(W, 120, 'Time until the hazard layer is current, hazards-first against oldest-first, on one axis with the time until every change is in');
  const svgH = svgBox(W, 200, 'Hazards met on a stale map, by time out of contact: during the outage, and after contact for each sync order');
  const read = readout();
  const src = what => `${E.source}: ${OUT_NAME[out] || out + ' h'} out of contact, ${rate} kbit/s, ${what}, mean over ${E.seeds} seeds`;
  const X = (value, unit, digits, what) => num({ value, unit, digits, flag: 'Modelled', source: src(what) });
  const T = (s, what) => (s < 90 ? X(s, ' s', s < 10 ? 1 : 0, what) : s < 5400 ? X(s / 60, ' min', s < 600 ? 1 : 0, what) : X(s / 3600, ' h', 1, what));
  const A = (k, value, unit, digits, what) => num({ value, unit, digits, flag: E.assumed.includes(k) ? 'Assumed' : 'Modelled', source: `${E.source}: parameters.${k}, ${what}` });
  function draw() {
    const hf = row(out, 'hazards_first'), of = row(out, 'oldest_first');
    W = widthOf(svgT);
    // 1. the two orders on one time axis
    fit(svgT, W, 120); svgT.replaceChildren();
    const L = W < 480 ? 92 : 112, R = 14, x = s => L + (W - L - R) * s / hf.t_all_s;
    const ticks = [0, 0.25, 0.5, 0.75, 1].map(f => f * hf.t_all_s);
    for (const t of ticks) svgT.append(S('line', { class: 'pr-grid-l', x1: x(t), x2: x(t), y1: 8, y2: 92 }), S('text', { class: 'pr-tick', x: x(t), y: 110, 'text-anchor': t ? (t === hf.t_all_s ? 'end' : 'middle') : 'start' }, secsText(t)));
    [['Hazards first', hf], ['Oldest first', of]].forEach(([name, q], i) => {
      const y = 18 + i * 40;
      svgT.append(S('text', { class: 'pr-tick pr-lab', x: L - 8, y: y + 15, 'text-anchor': 'end' }, name),
        S('rect', { class: 'pr-sync-all', x: L, y, width: Math.max(1, x(q.t_all_s) - L), height: 22, rx: 3 }),
        S('rect', { class: 'pr-sync-haz', x: L, y, width: Math.max(2, x(q.t_hazards_current_s) - L), height: 22, rx: 3 }));
    });
    // 2. hazards met, by time out of contact (the chosen rate)
    fit(svgH, W, 200); svgH.replaceChildren();
    const L2 = 34, B2 = 26, T2 = 10, H2 = 200, gw = (W - L2 - 8) / outs.length, bw = Math.min(18, (gw - 10) / 3);
    const vals = outs.map(o => [row(o, 'hazards_first').hits_during_outage_mean, row(o, 'hazards_first').hits_after_contact_mean, row(o, 'oldest_first').hits_after_contact_mean]);
    const max = Math.max(1, ...vals.flat()), step = max > 10 ? 5 : max > 4 ? 2 : 1, top = Math.ceil(max / step) * step, y = v => H2 - B2 - (H2 - B2 - T2) * v / top;
    for (let v = 0; v <= top; v += step) svgH.append(S('line', { class: 'pr-grid-l', x1: L2, x2: W - 8, y1: y(v), y2: y(v) }), S('text', { class: 'pr-tick', x: L2 - 6, y: y(v) + 4, 'text-anchor': 'end' }, v));
    outs.forEach((o, i) => {
      const gx = L2 + i * gw, x0 = gx + (gw - 3 * bw - 4) / 2;
      if (o === out) svgH.append(S('rect', { class: 'pr-sel', x: gx + 2, y: T2 - 4, width: gw - 4, height: H2 - B2 - T2 + 4, rx: 4 }));
      vals[i].forEach((v, k) => svgH.append(S('rect', { class: `pr-c${k + 1}`, x: x0 + k * (bw + 2), y: y(v), width: bw, height: Math.max(v > 0 ? 1.5 : 0, y(0) - y(v)), rx: 2 },
        S('title', {}, `${OUT_NAME[o]}: ${['during the outage', 'after contact, hazards first', 'after contact, oldest first'][k]} ${fmt(v, 2)}`))));
      svgH.append(S('text', { class: 'pr-tick', x: gx + gw / 2, y: H2 - 8, 'text-anchor': 'middle' }, W < 480 ? (OUT_NAME[o] || '').replace(' days', ' d').replace(' day', ' d') : OUT_NAME[o]));
    });
    const P = E.parameters;
    setRead(read, `After <b>${OUT_NAME[out]}</b> out of contact, at ${rate >= 1000 ? `${fmt(rate / 1000, 0)} Mbit/s` : `${rate} kbit/s`}, by calculation from the assumed change rates: ${hf.bytes_mean >= 1e6 ? X(hf.bytes_mean / 1e6, ' MB', 2, 'bytes to sync') : X(hf.bytes_mean / 1000, ' kB', hf.bytes_mean < 1e5 ? 1 : 0, 'bytes to sync')} to sync `
      + `(${X(hf.tiles_changed_mean, ' tile versions', 1, 'tile versions changed')}), ${X(100 * hf.share_of_full_resend, ' %', 2, 'share of a full resend')} of a full resend of every layer (${num({ value: E.full_resend_bytes / 1e6, unit: ' MB', digits: 1, flag: 'Modelled', source: `${E.source}: full_resend_bytes` })}). `
      + `The hazard layer is current after ${T(hf.t_hazards_current_s, 'hazard layer current, hazards first')} hazards first, against ${T(of.t_hazards_current_s, 'hazard layer current, oldest first')} oldest first; every change is in after ${T(hf.t_all_s, 'all changes in')}. `
      + `Hazards met on the stale map: ${X(hf.hits_during_outage_mean, '', 2, 'hazards hit during the outage')} during the outage, ${X(hf.hits_after_contact_mean, '', 2, 'hazards hit after contact, hazards first')} after contact hazards first and ${X(of.hits_after_contact_mean, '', 2, 'hazards hit after contact, oldest first')} oldest first. `
      + `The rover's routes cross ${num({ value: E.route_tiles, unit: ' tiles', digits: 0, flag: 'Modelled', source: `${E.source}: route_tiles` })}; new hazards appear ${A('hazards_per_day', P.hazards_per_day, ' a day', 0, 'new hazards a day')} and ${A('hidden_share', 100 * P.hidden_share, ' %', 0, 'share of hazards the rover’s own sensors miss')} of them are invisible to the rover's own sensors.`);
  }
  onResize(svgT, draw);
  host.append(h('div', { class: 'pr-ctl' }, segO.el, segR.el), svgT,
    h('p', { class: 'pr-key small' }, h('span', { class: 'pr-sw pr-sw-haz' }), ' until the hazard layer is current  ', h('span', { class: 'pr-sw pr-sw-all' }), ' until every change is in'),
    h('p', { class: 'ui-label pr-sub' }, 'Hazards met on a stale map'), svgH,
    h('p', { class: 'pr-key small' }, h('span', { class: 'pr-sw pr-c1' }), ' during the outage  ', h('span', { class: 'pr-sw pr-c2' }), ' after contact, hazards first  ', h('span', { class: 'pr-sw pr-c3' }), ' after contact, oldest first (mean per rover)'), read);
  draw();
}

// ---------------------------------------------------------------- 3. time: two clocks and a resync
// The sawtooth is the drift between resyncs at note 01's rates (an illustration); the readout and the needs are E51's
// measured results (protocol/e51.json from results/E51_clocks.json: lunar time scale, July 2028, 30 seeds), which also
// count the resyncs that failed for lack of a link.
async function figTime(host) {
  const r = await fetch(`${import.meta.env.BASE_URL}protocol/e51.json`);
  if (!r.ok) throw new Error(`protocol/e51.json: HTTP ${r.status}`);
  const E = await r.json();
  if (E.format !== 'lunarsim-e51-site' || E.version !== 1) throw new Error(`e51.json: format ${E.format}`);
  let W = 640; const H = 220, L = 58, R = 30, T = 14, B = 30;
  const osc = { crystal: ['Crystal', V('tcxo') * 1e-3 / 86400], csac: ['Chip-scale atomic clock', V('csac') * 1e-6 / 86400] };
  const NAME = { 10: '10 s', 60: '1 min', 600: '10 min', 3600: '1 h', 21600: '6 h', 86400: '1 day', never: 'never' };
  const ivals = [...new Set(E.rows.map(x => x.interval_s))];
  let o = 'crystal';
  const seg = segmented({ legend: 'Oscillator', options: Object.entries(osc).map(([v, [l]]) => ({ value: v, label: l })), value: o, onChange: v => { o = v; draw(); } });
  const iv = range('Time between resyncs', { min: 0, max: ivals.length - 1, step: 1, value: Math.max(0, ivals.indexOf(600)) });
  const svg = svgBox(W, H, 'Clock offset between resyncs at the oscillator’s drift rate: it grows until each resync and drops to zero');
  const needs = h('ul', { class: 'pr-needs' }); const out = readout();
  const unit = s => s >= 1 ? [s, ' s'] : s >= 1e-3 ? [s * 1e3, ' ms'] : s >= 1e-6 ? [s * 1e6, ' µs'] : [s * 1e9, ' ns'];
  const src = what => `${E.source}: ${osc[o][0].toLowerCase()}, resync every ${NAME[ivals[+iv.input.value]] || ivals[+iv.input.value]}, lunar time, ${what}`;
  const X = (value, u, digits, what) => num({ value, unit: u, digits, flag: 'Modelled', source: src(what) });
  const dist = (m, what) => m >= 1000 ? X(m / 1000, ' km', m < 1e4 ? 1 : 0, what) : X(m, ' m', m < 10 ? 2 : 0, what);
  const time = (s, what) => { const [a, u] = unit(s); return X(a, u, a < 10 ? 2 : 0, what); };
  function draw() {
    const I = ivals[+iv.input.value], fin = typeof I === 'number', drift = osc[o][1], span = fin ? 4 * I : 4 * 86400, worst = drift * (fin ? I : span);
    const row = E.rows.find(x => x.class === o && x.interval_s === I);
    W = widthOf(svg); fit(svg, W, H);
    const [ws, wu] = unit(worst), x = s => L + (W - L - R) * s / span, y = v => H - B - (H - T - B) * v / worst;
    svg.replaceChildren(S('line', { class: 'pr-grid-l', x1: L, x2: W - R, y1: y(0), y2: y(0) }), S('line', { class: 'pr-grid-l', x1: L, x2: W - R, y1: y(worst), y2: y(worst) }),
      S('text', { class: 'pr-tick', x: L - 6, y: y(0) + 4, 'text-anchor': 'end' }, '0'), S('text', { class: 'pr-tick', x: L - 6, y: y(worst) + 4, 'text-anchor': 'end' }, `${fmt(ws, ws < 10 ? 2 : 0)}${wu}`));
    let d = '';
    if (fin) for (let k = 0; k < 4; k++) d += `M${x(k * I)},${y(0)}L${x((k + 1) * I)},${y(worst)}L${x((k + 1) * I)},${y(0)}`;
    else d = `M${x(0)},${y(0)}L${x(span)},${y(worst)}`;
    svg.append(S('path', { class: 'pr-l-main', d }));
    for (let k = 1; k <= 4; k++) svg.append(S('text', { class: 'pr-tick', x: x(k * span / 4), y: H - B + 18, 'text-anchor': k === 4 ? 'end' : 'middle' }, fin ? (W < 420 ? `${k}` : `resync ${k}`) : `day ${k}`));
    if (!row) { needs.replaceChildren(); setRead(out, 'E51 has no row for this setting.'); return; }
    const noise = E.uwb_sigma_m, guard = E.guard_s;
    const ow = row.one_way_m_p95, list = [['observed', `road reservations (${fmt(guard, 1)} s guard): ${row['conflicts_guard_0.1']} conflicts in ${fmt(row.conflict_pairs_checked, 0)} pairs`],
      ['calculated', `two-way ranging: ${fmt(row.two_way_single_sided_m_p95, 2)} m, ${row.two_way_single_sided_m_p95 <= noise ? 'within' : 'above'} the ${fmt(noise, 1)} m ranging noise`],
      ['calculated', `one-way ranging: ${ow >= 1000 ? `${fmt(ow / 1000, 0)} km` : `${fmt(ow, 1)} m`}, ${ow <= noise ? 'within' : 'above'} the ranging noise`]];
    needs.replaceChildren(...list.map(([k, t]) => h('li', { class: 'pr-n-' + k }, h('b', {}, k), ` ${t}`)));
    setRead(out, `${osc[o][0]}, resync ${fin ? `every ${NAME[I] || `${I} s`}` : 'never'}: the drift alone reaches ${time(worst, 'drift rate x interval (note 01)')} before each resync (the curve). `
      + `Measured over a month in E51, where ${X(100 * row.sync_fail_share, ' %', 1, 'resyncs that failed for lack of a link')} of resyncs fail for lack of a link: `
      + `from the clock offsets, one-way ranging would be off by ${dist(row.one_way_m_p95, 'one-way ranging error, 95th percentile')} (95th percentile; median ${dist(row.one_way_m_median, 'one-way ranging error, median')}), `
      + `two-way ranging by ${dist(row.two_way_single_sided_m_p95, 'two-way single-sided ranging error, 95th percentile')}; the largest clock offset is ${time(row.max_abs_clock_s, 'largest clock offset')}; `
      + `${X(row['conflicts_guard_0.1'], '', 0, `reservation conflicts at the ${guard} s guard`)} of ${fmt(row.conflict_pairs_checked, 0)} close reservation pairs conflict at the ${fmt(guard, 1)} s guard (${X(row['conflicts_guard_0.01'], '', 0, 'reservation conflicts at the 0.01 s guard')} at 10 ms). `
      + 'Two-way ranging cancels the offset and needs no common time.');
  }
  iv.input.addEventListener('input', draw);
  host.append(h('div', { class: 'pr-ctl' }, seg.el, iv.el), h('div', { class: 'pr-time' }, svg, needs), out);
  draw(); onResize(svg, draw);
}

// ---------------------------------------------------------------- 4b and 6b. E54: what reaches its destination
// E54 (protocol/e54.json from results/E54_dtn.json and E54_ledger.json, 30 seeds, the recorded month with a 14-day
// Earth blackout): drop-and-retry, store-and-forward with custody, and store-and-forward with the lost-link rule, at a
// chosen per-hop loss. data-focus="radio" (problem 4): grants, job-state reports, award delay, and the Earth ledger's
// lifetimes; data-focus="fail" (problem 6): lost jobs, stuck reservations and how stale the base's picture gets.
const PROTO = [['drop_retry', 'Drop and retry'], ['sf', 'Store and forward'], ['sf_ll', '+ lost-link rule']];
// F-65: one seed's month, message by message, from B-99's e54_timeline.json (seed 1, loss 0.25, the 14-day Earth
// blackout): each award, grant and job-state report as a tick at the hour it was sent; red if it expired on the way
function e54Timeline(T) {
  const M = T.messages, n = M.kind.length, days = Math.ceil(Math.max(...M.t_created_h) / 24);
  const svg = svgBox(640, 150, 'One simulated month, message by message: each message a tick at the hour it was sent, red where it was lost, for each delivery rule');
  const KIND = { award: 'job award', grant: 'reservation grant', task_state: 'job-state report' };
  const rows = PROTO.filter(([k]) => Array.isArray(M.delivered_h[k]));
  const lostBy = k => { const c = {}; M.delivered_h[k].forEach((d, i) => { if (d === null) c[M.kind[i]] = (c[M.kind[i]] || 0) + 1; }); return c; };
  function draw() {
    const W = widthOf(svg), L = W < 480 ? 100 : 128, R = 54, T0 = 8, RH = 34, H = T0 + rows.length * RH + 24;
    fit(svg, W, H); svg.replaceChildren();
    const x = t => L + (W - L - R) * t / (days * 24);
    for (let d = 0; d <= days; d += 7) svg.append(S('line', { class: 'pr-grid-l', x1: x(d * 24), x2: x(d * 24), y1: T0, y2: T0 + rows.length * RH }), S('text', { class: 'pr-tick', x: x(d * 24), y: H - 6, 'text-anchor': d ? 'middle' : 'start' }, `day ${d}`));
    rows.forEach(([k, l], j) => {
      const y0 = T0 + j * RH + 6, del = M.delivered_h[k];
      svg.append(S('text', { class: 'pr-tick pr-lab', x: L - 8, y: y0 + 15, 'text-anchor': 'end' }, l));
      let ok = '', bad = '';
      for (let i = 0; i < n; i++) { const xx = x(M.t_created_h[i]).toFixed(1); if (del[i] === null) bad += `M${xx},${y0}v22`; else ok += `M${xx},${y0 + 6}v10`; }
      svg.append(S('path', { class: 'pr-tick-ok', d: ok }), S('path', { class: 'pr-tick-lost', d: bad }));
      const lost = del.filter(d => d === null).length;
      svg.append(S('text', { class: 'pr-tick pr-lab', x: W - R + 6, y: y0 + 15 }, `${lost} lost`));
    });
  }
  onResize(svg, draw);
  const say = rows.map(([k, l]) => { const c = lostBy(k), tot = Object.values(c).reduce((a, b) => a + b, 0); return `${l}: ${tot ? Object.entries(c).map(([kk, v]) => `${v} ${KIND[kk] || kk}${v === 1 ? '' : 's'}`).join(', ') : 'none'}`; }).join('; ');
  const key = h('p', { class: 'pr-key small' }, h('span', { class: 'pr-sw pr-sw-ok' }), ' delivered  ', h('span', { class: 'pr-sw pr-sw-lost' }), ` lost. Lost: ${say}.`);
  draw();
  return [svg, key];
}

async function figDtn(host) {
  const focus = host.dataset.focus === 'fail' ? 'fail' : 'radio';
  // F-78 (review W3): the table and, for the failure figure, the month's timeline are fetched together
  const [r, rt] = await Promise.all([fetch(`${import.meta.env.BASE_URL}protocol/e54.json`),
    focus === 'fail' ? fetch(`${import.meta.env.BASE_URL}protocol/b99/e54_timeline.json`) : null]);
  if (!r.ok) throw new Error(`protocol/e54.json: HTTP ${r.status}`);
  const E = await r.json();
  if (E.format !== 'lunarsim-e54-site' || E.version !== 1) throw new Error(`e54.json: format ${E.format}`);
  let timeline = [];
  if (focus === 'fail') {   // F-65: one seed's month from B-99, under the table
    if (!rt.ok) throw new Error(`protocol/b99/e54_timeline.json: HTTP ${rt.status}`);
    const TL = await rt.json();
    if (TL.format !== 'lunarsim-protocol-data' || !TL.messages) throw new Error(`e54_timeline.json: format ${TL.format}`);
    timeline = [h('p', { class: 'ui-label pr-sub' }, 'One month, message by message'), ...e54Timeline(TL)];
  }
  const losses = [...new Set(E.rows.map(x => x.loss))].sort((a, b) => a - b);
  let loss = losses.includes(0.25) ? 0.25 : losses[0];
  const seg = segmented({ legend: 'Messages lost on each hop', options: losses.map(l => ({ value: String(l), label: `${fmt(100 * l, 0)} %` })), value: String(loss), onChange: v => { loss = +v; draw(); } });
  const pct = s => `${fmt(100 * s, s < 0.01 && s > 0 ? 2 : 1)} %`;
  const share = (n, of, s) => h('span', { class: 'pr-cell' }, h('span', { class: 'pr-mini', style: `--w:${Math.min(100, 100 * s).toFixed(1)}%` }), `${pct(s)} (${fmt(n, 0)} of ${fmt(of, 0)})`);
  const ROWS = focus === 'radio'
    ? [['Reservation grants lost (the vehicle stops before the one-lane road)', q => share(q.grant_lost, q.grant_n, q.grant_lost_share)],
      ['Job-state reports lost', q => share(q.task_state_lost, q.task_state_n, q.task_state_lost_share)],
      ['Job-state reports: mean delay', q => secsText(q.task_state_delay_mean_s)],
      ['Job awards: mean delay', q => secsText(q.award_delay_mean_s)]]
    : [['Jobs lost (the award expired; the job is auctioned again)', q => `${fmt(q.award_lost, 0)} of ${fmt(q.award_n, 0)}`],
      ['Segments of silent vehicles past their timeout (unconfirmed under the rule)', (q, k) => (k === 'sf_ll' ? 'not counted yet' : `${fmt(q.stuck_reservations, 0)} (${fmt(q.stuck_hours, 0)} h)`)],
      ['How old the base’s picture of a vehicle is: mean (worst vehicle)', q => `${secsText(q.aoi_mean_s)} (${secsText(q.aoi_worst_vehicle_s)})`],
      ['Job-state reports lost', q => share(q.task_state_lost, q.task_state_n, q.task_state_lost_share)]];
  const wrap = h('div', { class: 'pr-scroll' }), extra = h('div', { class: 'pr-dtn-extra' }), read = readout();
  function draw() {
    const q = Object.fromEntries(PROTO.map(([k]) => [k, E.rows.find(x => x.loss === loss && x.protocol === k)]));
    wrap.replaceChildren(h('table', { class: 'pr-table' },
      h('caption', { class: 'small' }, `At ${fmt(100 * loss, 0)} % loss per hop, over ${E.seeds} seeds of the recorded month (${fmt(E.jobs_per_seed, 0)} jobs and ${fmt(E.reservations_per_seed, 0)} one-lane reservations a seed). Modelled, from ${E.source}.`),
      h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, ''), ...PROTO.map(([, l]) => h('th', { scope: 'col' }, l)))),
      h('tbody', {}, ROWS.map(([name, f]) => h('tr', {}, h('th', { scope: 'row' }, name), ...PROTO.map(([k, l]) => h('td', { 'data-label': l }, q[k] ? f(q[k], k) : '–')))))));
    if (focus === 'radio') {
      const L = E.ledger, life = [...new Set(L.rows.map(x => x.lifetime_d))].sort((a, b) => a - b);
      const cell = (d, p) => { const x = L.rows.find(y => y.lifetime_d === d && y.loss === loss && y.protocol === p); return x ? `${pct(x.lost_share)} lost` : '–'; };
      extra.replaceChildren(h('p', { class: 'ui-label pr-sub' }, 'The daily ledger bundle to Earth'),
        h('div', { class: 'pr-scroll' }, h('table', { class: 'pr-table' },
          h('caption', { class: 'small' }, `${fmt(L.rows[0]?.bundles ?? 0, 0)} daily bundles, with Earth blacked out from day ${fmt(E.blackout_days[0], 0)} to day ${fmt(E.blackout_days[1], 0)} on top of the base's own gaps in Earth's view: the longest stretch without Earth is ${fmt(L.longest_earth_down_d, 2)} days. Modelled, from ${E.ledger_source}.`),
          h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, 'Bundle lifetime'), h('th', { scope: 'col' }, 'Drop and retry'), h('th', { scope: 'col' }, 'Store and forward'))),
          h('tbody', {}, life.map(d => h('tr', {}, h('th', { scope: 'row' }, `Lifetime ${fmt(d, d % 1 ? 2 : 0)} days${d === 14 ? ' (note 03)' : ''}`), h('td', { 'data-label': 'Drop and retry' }, cell(d, 'drop_retry')), h('td', { 'data-label': 'Store and forward' }, cell(d, 'sf'))))))));
      const q2 = q.drop_retry, q3 = q.sf;
      setRead(read, `When the retry interval is longer than a grant's lifetime, dropping and retrying loses grants at the per-hop loss, a property of the rule: at ${fmt(100 * loss, 0)} % loss, ${num({ value: 100 * q2.grant_lost_share, unit: ' %', digits: 1, flag: 'Modelled', source: `${E.source}: grants lost, drop and retry, loss ${loss}` })} of grants; store and forward with custody loses ${num({ value: 100 * q3.grant_lost_share, unit: ' %', digits: 2, flag: 'Modelled', source: `${E.source}: grants lost, store and forward, loss ${loss}` })}. `
        + `An Earth-bound bundle must outlive the longest stretch without Earth (${num({ value: L.longest_earth_down_d, unit: ' days', digits: 2, flag: 'Modelled', source: `${E.ledger_source}: longest_earth_down_d` })}) or it expires on the way; the ledger table is a calculation from the blackout and the lifetimes.`);
    } else {
      const H = E.h14, a = H.lost_jobs_drop_retry_per_seed, b = H.lost_jobs_sf_ll_per_seed;
      extra.replaceChildren();
      setRead(read, `Hypothesis H14, at 25 % loss with the 14-day blackout: jobs lost per seed ${num({ value: a.mean, unit: '', digits: 2, flag: 'Modelled', source: `${E.source}: h14, drop and retry, mean over ${a.n} seeds (95 % interval ${fmt(a.ci[0], 2)} to ${fmt(a.ci[1], 2)})` })} with drop and retry against ${num({ value: b.mean, unit: '', digits: 0, flag: 'Modelled', source: `${E.source}: h14, store and forward with the lost-link rule, mean over ${b.n} seeds` })} with the lost-link rule: H14's first clause held; its second (no stuck reservation) is not testable as written. `
        + 'A silent vehicle’s reservation is not released: its segment is marked unconfirmed and entered only at caution speed. Driving back to its last link point shortens how long the base goes without hearing from it.');
    }
  }
  host.append(h('div', { class: 'pr-ctl' }, seg.el), wrap, extra, read, ...timeline);
  draw();
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
// the field names of lunarsim/schemas/lrip-v0.1.json in words
const LRIP_NAME = { version: 'Packet version', type: 'Packet type', sec_hdr_flag: 'Secondary header flag', apid: 'APID (0x500 + message type)',
  seq_flags: 'Sequence flags', seq_count: 'Sequence count', data_length: 'Packet data length (bytes after the header, minus 1)',
  ver_major: 'LRIP version, major', ver_minor: 'LRIP version, minor', msg_type: 'Message type', sender_id: 'Sender id', t_valid: 'Valid at (since the LRIP epoch)',
  e: 'East', n: 'North', h: 'Height', heading: 'Heading', speed: 'Speed', sigma_h: 'Position error (one sigma)', nav_src: 'Position source', moving: 'Moving',
  spare: 'Spare', u95_code: '95 % horizontal bound (log code)', spi: 'Key kind and epoch (SPI)', seq: 'Counter (stops replays)', mac8: 'Authentication code (AES-CMAC, 8 bytes)' };
async function figMsg(host) {
  const r = await fetch(`${import.meta.env.BASE_URL}protocol/lrip-position.json`);
  if (!r.ok) throw new Error(`protocol/lrip-position.json: HTTP ${r.status}`);
  const L = await r.json();
  if (L.format !== 'lunarsim-lrip-figure' || L.version !== 2) throw new Error(`lrip-position.json: format ${L.format} version ${L.version}`);
  const F = L.layout.fields, raw = lripDecode(L.vector.hex, L.layout), hex = L.vector.hex;
  const bytes = []; for (let i = 0; i < hex.length; i += 2) bytes.push(hex.slice(i, i + 2));
  let pos = 0; const span = F.map(f => { const s = pos; pos += f.bits; return [s, pos]; });
  const PART = { head: 'packet header', lrip: 'protocol header', pay: 'position content', sec: 'security header', mac: 'authentication code' };
  const G = (value, unit, digits, what) => num({ value, unit, digits, flag: 'Spec', source: `${L.source}: the POSITION conformance vector (profile N, 8-byte MAC), ${what}; layout ${L.schema}` });
  // F-73: v0.2's u95_code, a log code read by the schema's own rule (base × 2^(code/div); two codes reserved)
  const bound = (f, v) => {
    const g = f.log;
    if (v === g.unknown) return `${v} (unknown)`;
    if (v === g.above) return `${v} (above ${g.aboveText})`;
    const m = g.base * 2 ** (v / g.div), big = m >= 1000;
    return `${v}, so ${G(big ? m / 1000 : m, big ? ' km' : ' m', big ? 2 : m < 10 ? 2 : 0, `${LRIP_NAME[f.name]} (${f.note.split(',')[0]})`)}`;
  };
  const valueOf = k => {
    const f = F[k], v = raw[k];
    if (typeof v === 'string') return `<code>${bytes.slice(span[k][0] / 8, span[k][1] / 8).join(' ')}</code>`;
    if (f.log) return bound(f, v);
    if (f.enum) return `${v} (${String(f.enum[v] ?? 'unknown').replace(/_/g, ' ')})`;
    if (f.type === 'flag') return v ? 'yes' : 'no';
    if (f.scale && f.scale !== 1) { const d = Math.max(0, -Math.floor(Math.log10(f.scale) + 1e-9)); return G(v * f.scale, f.unit === 'deg' ? '°' : ` ${f.unit}`, d, LRIP_NAME[f.name] || f.name); }
    return f.name === 'apid' ? `0x${v.toString(16)}` : fmt(v, 0);
  };
  const partOf = i => F[span.findIndex(([s, e]) => i * 8 >= s && i * 8 < e)].part;
  const grid = h('div', { class: 'pr-bytes', role: 'list', 'aria-label': `POSITION report, ${bytes.length} bytes` },
    bytes.map((b, i) => h('span', { class: `pr-byte pr-p-${partOf(i)}`, role: 'listitem', 'data-i': i }, b)));
  const fields = h('div', { class: 'pr-fields', role: 'group', 'aria-label': 'Fields' });
  const out = readout();
  const size = a => L.sizes.find(s => s.profile === a[0] && s.auth === a[1])?.bytes;
  const content = F.filter(f => f.part === 'pay').reduce((a, f) => a + f.bits, 0) / 8;
  function pick(k) {
    const [s, e] = span[k], f = F[k];
    for (const el of grid.children) { const i = +el.dataset.i; el.classList.toggle('on', i * 8 < e && i * 8 + 8 > s); }
    for (const b of fields.children) b.setAttribute('aria-pressed', String(+b.dataset.k === k));
    setRead(out, `<b>${LRIP_NAME[f.name] || f.name}</b>: ${valueOf(k)}. ${f.bits} bits of the ${PART[f.part]}, bits ${s} to ${e - 1}. `
      + `The packet is ${G(bytes.length, ' bytes', 0, 'its length')} before link framing and coding, of which ${G(content, ' bytes', 0, 'the POSITION fields')} are the position itself; `
      + `without authentication it is ${G(size(['N', null]), ' bytes', 0, 'the unauthenticated vector')}, and ${G(size(['B', 'mac8']), ' bytes', 0, 'the broadband-profile vector')} on the broadband profile.`);
  }
  F.forEach((f, k) => { if (f.name !== 'spare') fields.append(h('button', { type: 'button', class: `pr-field pr-p-${f.part}`, 'data-k': k, 'aria-pressed': 'false', onclick: () => pick(k) }, LRIP_NAME[f.name] || f.name)); });
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
  host.append(h('p', { class: 'ui-label' }, `A POSITION packet, before link framing: LRIP v${L.lrip}'s conformance vector, sender ${L.vector.sender}`), grid, h('p', { class: 'pr-key small' }, Object.entries(PART).flatMap(([k, l]) => [h('span', { class: `pr-sw pr-p-${k}` }), ` ${l}  `])), fields, out,
    h('div', { class: 'pr-ctl pr-ctl-gap' }, segJ.el), cards, mout);
  pick(F.findIndex(f => f.name === 'e')); match('carry');
}

// ---------------------------------------------------------------- 5b. E53: how much radio the fleet needs
// E53 at LRIP v0.2 sizes (F-73: protocol/e53-v02.json from results/E53_table_v02.csv, the rows of packets before link
// framing; B-99's v0.1 file had the same shape): the busiest link's load (95th percentile over position draws) against the number of rovers,
// at 0.1, 1 and 10 reports a second, for the fleet's own positions or rovers spread over the routes, with authentication on
// or off; the channel lines are capacity times access efficiency (the file's eta: 0.8 when the base schedules the slots,
// 1/e for random access), the rule E53 uses for "fits".
async function figBitrate(host) {
  const r = await fetch(`${import.meta.env.BASE_URL}protocol/e53-v02.json`);
  if (!r.ok) throw new Error(`protocol/e53-v02.json: HTTP ${r.status}`);
  const D = await r.json();
  if (D.format !== 'lunarsim-protocol-data' || !Array.isArray(D.rows)) throw new Error(`e53-v02.json: format ${D.format}`);
  const FR = D.columns.indexOf('framing');
  if (FR >= 0) D.rows = D.rows.filter(x => x[FR] === 'lrip');   // the figure draws packets before link framing
  const c = k => D.columns.indexOf(k), GE = c('geometry'), AU = c('auth'), HZ = c('position_hz'), N = c('rovers'), P95 = c('busiest_link_kbps_p95');
  if ([GE, AU, HZ, N, P95].some(i => i < 0)) throw new Error('protocol/e53-v02.json: columns');
  let geo = 'fleet', auth = 'on';
  const NB = Object.entries(D.lines_kbps).find(([k]) => /narrow/.test(k))?.[1], BB = Object.entries(D.lines_kbps).find(([k]) => /broad/.test(k))?.[1];
  const segG = segmented({ legend: 'Where the rovers are', options: [{ value: 'fleet', label: 'Where the fleet works' }, { value: 'spread', label: 'Spread over the routes' }], value: geo, onChange: v => { geo = v; draw(); } });
  const segA = segmented({ legend: 'Authentication code', options: [{ value: 'on', label: 'On' }, { value: 'off', label: 'Off' }], value: auth, onChange: v => { auth = v; draw(); } });
  const svg = svgBox(640, 280, 'Load on the busiest radio link against the number of rovers, for three reporting rates, with the narrow-band and broadband channel lines');
  const Ns = [...new Set(D.rows.map(x => x[N]))].sort((a, b) => a - b), rates = [...new Set(D.rows.map(x => x[HZ]))].sort((a, b) => a - b);
  const lines = [[NB * D.eta.slotted_aloha, 'narrow-band, random access'], [NB * D.eta.scheduled, 'narrow-band, base schedules the slots'], [BB * D.eta.scheduled, 'broadband, scheduled']];
  function draw() {
    const W = widthOf(svg), H = 280, L = 48, R = 14, T = 12, B = 34;
    fit(svg, W, H); svg.replaceChildren();
    const x = n => L + (W - L - R) * Math.log2(n / Ns[0]) / Math.log2(Ns[Ns.length - 1] / Ns[0]), LY = [0.5, 2000];
    const y = v => T + (H - T - B) * (1 - (Math.log10(v) - Math.log10(LY[0])) / (Math.log10(LY[1]) - Math.log10(LY[0])));
    for (const v of [1, 10, 100, 1000]) svg.append(S('line', { class: 'pr-grid-l', x1: L, x2: W - R, y1: y(v), y2: y(v) }), S('text', { class: 'pr-tick', x: L - 6, y: y(v) + 4, 'text-anchor': 'end' }, v >= 1000 ? '1 M' : `${v} k`));
    for (const n of Ns) svg.append(S('text', { class: 'pr-tick', x: x(n), y: H - B + 16, 'text-anchor': n === Ns[0] ? 'start' : n === Ns[Ns.length - 1] ? 'end' : 'middle' }, `${n}`));
    lines.forEach(([v, l], i) => svg.append(S('line', { class: `pr-limit pr-cap${i + 1}`, x1: L, x2: W - R, y1: y(v), y2: y(v) }, S('title', {}, `${l}: ${fmt(v, 1)} kbit/s usable`))));
    rates.forEach((hz, i) => {
      const pts = Ns.map(n => D.rows.find(q => q[GE] === geo && q[AU] === auth && q[HZ] === hz && q[N] === n)).filter(Boolean);
      const cls = `pr-c${i + 1}`;
      svg.append(S('path', { class: `pr-curve ${cls}`, d: pts.map((q, k) => `${k ? 'L' : 'M'}${x(q[N]).toFixed(1)},${y(q[P95]).toFixed(1)}`).join('') }));
      for (const q of pts) svg.append(S('circle', { class: cls, cx: x(q[N]), cy: y(q[P95]), r: 3.5 }, S('title', {}, `${q[N]} rovers, ${fmt(hz, hz < 1 ? 1 : 0)} reports a second: ${fmt(q[P95], 1)} kbit/s on the busiest link`)));
    });
  }
  onResize(svg, draw);
  host.append(h('div', { class: 'pr-ctl' }, segG.el, segA.el), svg,
    h('p', { class: 'pr-key small' }, ...rates.flatMap((hz, i) => [h('span', { class: `pr-sw pr-c${i + 1}` }), ` ${fmt(hz, hz < 1 ? 1 : 0)} a second  `])),
    // F-73b: the channel lines are named here, not on the plot, so no label covers a data point
    h('p', { class: 'pr-key small' }, 'Usable capacity (capacity × access efficiency): ', ...lines.flatMap(([v, l], i) => [
      h('span', { class: 'pr-capkey', html: `<svg width="28" height="8" aria-hidden="true"><line class="pr-limit pr-cap${i + 1}" x1="0" x2="28" y1="4" y2="4"/></svg>` }),
      ` ${l}, ${fmt(v, 1)} kbit/s${i < lines.length - 1 ? ';  ' : '.'}`])));
  draw();
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

// ---------------------------------------------------------------- 7b. E55: the integrity rule measured
// E55 (protocol/e55.json from results/E55_integrity.json): the LRIP rule as written against the single test and E56's
// detectors (test or out of distribution); the trimmed-mean consensus by geometry, with and without the base mast, at a
// chosen fleet size; forgeries and replays in the readout.
const E55_DET = [['3of5@0.001', 'The protocol’s rule: 3 of the last 5 reports over γ 10.83'], ['single@0.001', 'The same threshold, one report at a time'],
  ['3of5@0.01', '3 of 5, looser (γ 6.63)'], ['3of5@0.0001', '3 of 5, stricter (γ 15.14)'], ['e56_chi2_step', 'Chi-square calibrated on validation data (E56)'], ['e56_net', 'The learned network (E56)']];
// F-65: the trade-off of B-99's e55_detectors.json: faults found against false alarms per pair-day as the threshold γ
// sweeps, for the 3-of-5 rule and the single test; E56's detectors at their 1-per-pair-day points. Zero false alarms sit on
// the left edge (a log axis has no zero).
function e55Curve(C) {
  const svg = svgBox(640, 280, 'Faults found against false alarms per pair-day as the threshold sweeps, for the protocol’s 3-of-5 rule and the single test, with three other detectors as points');
  const read = h('p', { class: 'pr-key small' });
  const col = C.curve_columns, ix = k => col.indexOf(k), G = ix('gamma'), FA = ix('false_alarms_per_pair_day'), RC = ix('event_recall_all');
  if (G < 0 || FA < 0 || RC < 0) throw new Error('e55_detectors.json: curve columns');
  const LO = 0.01, HI = 2000;
  function draw() {
    const W = widthOf(svg), H = 280, L = 44, R = 14, T = 12, B = 34;
    fit(svg, W, H); svg.replaceChildren();
    const x = f => L + (W - L - R) * (Math.log10(Math.max(f, LO)) - Math.log10(LO)) / (Math.log10(HI) - Math.log10(LO));
    const y = rc => T + (H - T - B) * (1 - (rc - 0.5) / 0.5);
    for (const f of [LO, 0.1, 1, 10, 100, 1000]) svg.append(S('line', { class: 'pr-grid-l', x1: x(f), x2: x(f), y1: T, y2: H - B }), S('text', { class: 'pr-tick', x: x(f), y: H - B + 16, 'text-anchor': f === LO ? 'start' : 'middle' }, f === LO ? '0' : fmt(f, f < 1 ? 1 : 0)));
    for (const rc of [0.5, 0.6, 0.7, 0.8, 0.9, 1]) svg.append(S('line', { class: 'pr-grid-l', x1: L, x2: W - R, y1: y(rc), y2: y(rc) }), S('text', { class: 'pr-tick', x: L - 6, y: y(rc) + 4, 'text-anchor': 'end' }, fmt(rc, 1)));
    svg.append(S('line', { class: 'pr-limit', x1: x(1), x2: x(1), y1: T, y2: H - B }), S('text', { class: 'pr-tick', x: x(1) + 4, y: T + 10 }, '1 a day'));
    [['3of5', 'pr-c1'], ['single', 'pr-c2']].forEach(([k, cls]) => {
      const pts = (C.curves[k] || []).map(r => [x(r[FA]), y(r[RC]), r]);
      svg.append(S('path', { class: `pr-curve ${cls}`, d: pts.map(([a, b], i) => `${i ? 'L' : 'M'}${a.toFixed(1)},${b.toFixed(1)}`).join('') }));
      for (const [a, b, r] of pts) svg.append(S('circle', { class: cls, cx: a, cy: b, r: 3.5 }, S('title', {}, `${k === '3of5' ? '3 of 5' : 'single test'}, γ ${fmt(r[G], 2)}: ${fmt(r[FA], r[FA] < 1 ? 2 : 0)} false alarms per pair-day, ${fmt(r[RC], 2)} of faults found`)));
      const p = (C.curves[k] || []).find(r => Math.abs(r[G] - 10.83) < 0.01);
      if (k === '3of5' && p) svg.append(S('circle', { class: 'pr-ring', cx: x(p[FA]), cy: y(p[RC]), r: 8 }), S('text', { class: 'pr-tick pr-lab', x: x(p[FA]) + 11, y: y(p[RC]) + 14 }, 'the protocol, γ 10.83'));
    });
    const NAME = { chi2_step: 'chi-square', cusum: 'CUSUM', net: 'network' };
    for (const [k, p] of Object.entries(C.e56_at_1_per_pair_day || {})) svg.append(S('circle', { class: 'pr-e56', cx: x(p.fa_per_pair_day), cy: y(p.recall), r: 4.5 }),
      S('text', { class: 'pr-tick pr-lab', x: x(p.fa_per_pair_day) + 8, y: y(p.recall) - 6 }, NAME[k] || k));
  }
  onResize(svg, draw);
  read.append(h('span', { class: 'pr-sw pr-c1' }), ' 3 of the last 5 reports over γ  ', h('span', { class: 'pr-sw pr-c2' }), ' one report at a time  ', h('span', { class: 'pr-sw pr-sw-e56' }), ' E56’s detectors at one false alarm a day.');
  draw();
  return [svg, read];
}

async function figE55(host) {
  const [r, rcv] = await Promise.all([fetch(`${import.meta.env.BASE_URL}protocol/e55.json`), fetch(`${import.meta.env.BASE_URL}protocol/b99/e55_detectors.json`)]);
  if (!r.ok) throw new Error(`protocol/e55.json: HTTP ${r.status}`);
  if (!rcv.ok) throw new Error(`protocol/b99/e55_detectors.json: HTTP ${rcv.status}`);
  const E = await r.json(), C = await rcv.json();
  if (E.format !== 'lunarsim-e55-site' || E.version !== 1) throw new Error(`e55.json: format ${E.format}`);
  if (C.format !== 'lunarsim-protocol-data' || !C.curves) throw new Error(`e55_detectors.json: format ${C.format}`);
  let set = 'test', N = 12;
  const Ns = [...new Set(E.consensus.map(c => c.N))].sort((a, b) => a - b);
  if (!Ns.includes(N)) N = Ns[0];
  const segS = segmented({ legend: 'Streams', options: [{ value: 'test', label: 'Test set' }, { value: 'ood', label: 'Out of distribution' }], value: set, onChange: v => { set = v; draw(); } });
  const segN = segmented({ legend: 'Rovers', options: Ns.map(n => ({ value: String(n), label: String(n) })), value: String(N), onChange: v => { N = +v; draw(); } });
  const det = h('div', { class: 'pr-scroll' }), con = h('div', { class: 'pr-scroll' }), read = readout();
  const fa = v => (v === undefined || v === null ? '–' : fmt(v, v < 1 ? 2 : v < 100 ? 1 : 0));
  const rc = v => (v === undefined || v === null ? '–' : fmt(v, 2));
  const pc = v => (v === undefined || v === null ? '–' : `${fmt(100 * v, 0)} %`);
  function draw() {
    const D = E.detectors[set];
    det.replaceChildren(h('table', { class: 'pr-table' },
      h('caption', { class: 'small' }, `${set === 'test' ? 'Test streams' : 'Out of distribution: noisier ranging, worse dead reckoning, smaller faults; the false-alarm rates differ so much that the recall columns are not comparable'}. Recall is the share of faults found. Modelled, from ${E.source}.`),
      h('thead', {}, h('tr', {}, ...['Detector', 'False alarms per pair-day', 'Faults found', 'Slow drifts', 'Noise inflation'].map(t => h('th', { scope: 'col' }, t)))),
      h('tbody', {}, E55_DET.filter(([k]) => D[k]).map(([k, l]) => h('tr', { class: k === '3of5@0.001' ? 'pr-row-main' : '' }, h('th', { scope: 'row' }, l),
        h('td', { 'data-label': 'False alarms per pair-day' }, fa(D[k].fa)), h('td', { 'data-label': 'Faults found' }, rc(D[k].recall.all)),
        h('td', { 'data-label': 'Slow drifts' }, rc(D[k].recall.drift)), h('td', { 'data-label': 'Noise inflation' }, rc(D[k].recall.noise)))))));
    const cellOf = (g, mast, f, F) => E.consensus.find(c => c.geometry === g && c.mast === mast && c.N === N && c.f === f && c.F === F);
    const rows = [['fleet', false, 'Rovers where the fleet works'], ['fleet', true, '… with the base mast'], ['spread', false, 'Rovers spread over the routes'], ['spread', true, '… with the base mast']];
    con.replaceChildren(h('table', { class: 'pr-table' },
      h('caption', { class: 'small' }, `${N} rovers, liars sending far-off values; the trimmed mean drops the F highest and lowest values it hears. "Safe": every honest value stays inside the honest range. "Agree": the honest values come within 1 % of each other. Modelled, from ${E.source}.`),
      h('thead', {}, h('tr', {}, ...['Where the rovers are', 'Safe, 1 liar (F 1)', 'Safe, 2 liars (F 1)', 'Agree, 1 liar', 'Network connected'].map(t => h('th', { scope: 'col' }, t)))),
      h('tbody', {}, rows.filter(([g, m]) => cellOf(g, m, 1, 1)).map(([g, m, l]) => { const a = cellOf(g, m, 1, 1), b = cellOf(g, m, 2, 1);
        return h('tr', {}, h('th', { scope: 'row' }, l), h('td', { 'data-label': 'Safe, 1 liar (F 1)' }, pc(a?.safe)), h('td', { 'data-label': 'Safe, 2 liars (F 1)' }, pc(b?.safe)),
          h('td', { 'data-label': 'Agree, 1 liar' }, pc(a?.agreement)), h('td', { 'data-label': 'Network connected' }, pc(a?.connected))); }))));
    const F8 = E.forgery['8'], F16 = E.forgery['16'], rp = Object.entries(E.replay);
    const X = (value, digits, what) => num({ value, unit: '', digits, flag: 'Modelled', source: `${E.source}: ${what}` });
    setRead(read, `Forged messages with a truncated authentication code get through about as often as chance says: ${F8 ? `${X(F8.accepted, 0, 'auth.forgery 8 bits, accepted')} of ${fmt(F8.attempts, 0)} with 8 bits (chance: ${fmt(F8.attempts * F8.bound, 0)})` : ''}`
      + `${F16 ? `, ${X(F16.accepted, 0, 'auth.forgery 16 bits, accepted')} of ${fmt(F16.attempts, 0)} with 16 bits (chance: ${fmt(F16.attempts * F16.bound, 1)})` : ''}; the protocol uses 64 bits. `
      + `Replayed messages accepted: ${rp.map(([l, v]) => `${X(v.replays_accepted, 0, `auth.replay at loss ${l}`)} of ${fmt(v.replays, 0)} at ${fmt(100 * l, 0)} % loss`).join(' and ')}.`);
  }
  host.append(h('p', { class: 'ui-label pr-sub' }, 'Faults found against false alarms, as the threshold moves'), ...e55Curve(C),
    h('p', { class: 'ui-label pr-sub' }, 'Spotting a wrong position report'), h('div', { class: 'pr-ctl' }, segS.el), det,
    h('p', { class: 'ui-label pr-sub' }, 'Agreeing on a shared value by averaging among rovers'), h('div', { class: 'pr-ctl' }, segN.el), con, read);
  draw();
}

// ---------------------------------------------------------------- 8. who has flown what (note 04, section C)
// F-70: the survey rows moved to src/protocol/who.data.json (staged as protocol/who.json), out of the lazy chunk
async function figWho(host) {
  const r = await fetch(`${import.meta.env.BASE_URL}protocol/who.json`);
  if (!r.ok) throw new Error(`protocol/who.json: HTTP ${r.status}`);
  const WHO = (await r.json()).rows;
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

const FIGS = { pos: figPos, map: figMap, time: figTime, radio: figRadio, msg: figMsg, auction: figAuction, integrity: figIntegrity, who: figWho, dtn: figDtn, e55: figE55, bitrate: figBitrate };
// draws one figure into its host (main.js calls this as each host nears the screen)
export function mountFigure(host) {
  const fail = e => { host.append(h('p', { class: 'stub' }, `This figure could not be drawn (${e.message}).`)); console.error(e); };
  try { const p = FIGS[host.dataset.fig](host); if (p?.then) p.then(() => upgradeFlags(host), fail); } catch (e) { fail(e); }
  upgradeFlags(host);
  if (reducedMotion()) document.documentElement.classList.add('pr-still');
}
