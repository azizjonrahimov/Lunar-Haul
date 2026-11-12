// F-61: inside the integrity network: one of the ten reference windows run through the browser port (tcn.js), each
// layer's activations as a strip (channels x time; each layer is shorter by 2 x its dilation, so the strips show the
// receptive field closing to the last second), the logit against the two alarm thresholds, and the parity check of all
// ten windows against the float64 reference (data/policies/integrity_net_v1.check.json, 1e-6).
import { segmented, h } from '../ui/index.js';
import { forward, prob } from './tcn.js';

const SEQ = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b'];
const DIV = { neg: '#2a78d6', pos: '#eb6834', mid: [214, 214, 210] };   // diverging: blue / orange, neutral grey midpoint
const hex = s => [1, 3, 5].map(i => parseInt(s.slice(i, i + 2), 16));
const lerp = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t));
const seqAt = u => { const x = Math.max(0, Math.min(1, u)) * (SEQ.length - 1), i = Math.min(SEQ.length - 2, Math.floor(x)); return lerp(hex(SEQ[i]), hex(SEQ[i + 1]), x - i); };
const divAt = u => u < 0 ? lerp(DIV.mid, hex(DIV.neg), Math.min(1, -u)) : lerp(DIV.mid, hex(DIV.pos), Math.min(1, u));
const fmt = (v, d) => v.toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d });
const FEATURE_LABEL = { z: 'range innovation z', range_m: 'measured range', rep_speed_mps: "B's reported speed", rep_dheading_rad: "B's heading change", rep_sigma_m: "B's claimed error", own_sigma_m: 'own claimed error', lq_degraded: 'link degraded', own_fix_age_s: 'time since own fix', range_valid: 'range valid', range_class_long: 'long-range radio' };

function strip(rows, colour, scale) {   // rows: [channel][time]
  const c = document.createElement('canvas'), T = rows[0].length, C = rows.length;
  c.width = T; c.height = C; c.className = 'nw-strip';
  const ctx = c.getContext('2d'), img = ctx.createImageData(T, C);
  for (let ch = 0; ch < C; ch++) for (let t = 0; t < T; t++) { const [r, g, b] = colour(rows[ch][t] / scale), k = 4 * (ch * T + t); img.data[k] = r; img.data[k + 1] = g; img.data[k + 2] = b; img.data[k + 3] = 255; }
  ctx.putImageData(img, 0, 0);
  return c;
}

export function mountInside(host, pol, chk) {
  // parity first: every reference window through the port
  const errs = chk.obs.map((w, i) => Math.abs(forward(pol, w).logit - chk.expected[i])), pass = errs.filter(e => e <= chk.tolerance).length;
  const types = ['jump', 'drift', 'frozen', 'frame', 'noise'];
  let type = 'jump', when = 'in';
  const seg = segmented({ legend: 'Fault', options: types.map(t => ({ value: t, label: t })), value: type, onChange: v => { type = v; draw(); } });
  const seg2 = segmented({ legend: 'Window', options: [{ value: 'before', label: 'before the fault' }, { value: 'in', label: 'inside the fault' }], value: when, onChange: v => { when = v; draw(); } });
  const body = h('div', { class: 'nw-layers' }), out = h('div', { class: 'nw-out' });
  const badge = h('p', { class: `nw-badge ${pass === chk.obs.length ? 'ok' : 'bad'}` }, `${pass} of ${chk.obs.length} reference windows match the Python runtime within ${chk.tolerance} (largest difference ${errs.reduce((a, b) => Math.max(a, b), 0).toExponential(1)})`);
  host.append(badge, h('div', { class: 'nw-ctl' }, seg.el, seg2.el), body, out);
  const T = pol.thresholds, feat = pol.obs.names;

  function draw() {
    const i = chk.what.findIndex(w => w.startsWith(type + ':') && w.includes(when === 'in' ? 'in the fault' : 'before the fault'));
    const { logit, acts } = forward(pol, chk.obs[i]);
    body.replaceChildren();
    // inputs (squashed, signed): diverging scale
    const inp = strip(acts[0], u => divAt(u), 1);
    body.append(h('div', { class: 'nw-row' }, h('div', { class: 'nw-row-h' }, h('b', {}, 'Inputs'), h('span', {}, `${feat.length} per second × ${acts[0][0].length} s`)), h('div', { class: 'nw-row-c' }, inp,
      h('ul', { class: 'nw-feats' }, feat.map(f => h('li', {}, FEATURE_LABEL[f] || f))))));
    pol.layers.forEach((L, k) => {
      const a = acts[k + 1], last = k === pol.layers.length - 1;
      if (last) return;
      let mx = 0; for (const r of a) for (const v of r) mx = Math.max(mx, v);
      const s = strip(a, u => seqAt(u), mx || 1);
      s.style.width = `${(a[0].length / acts[0][0].length) * 100}%`;
      body.append(h('div', { class: 'nw-row' }, h('div', { class: 'nw-row-h' }, h('b', {}, `Layer ${k + 1}`), h('span', {}, `${a.length} channels, dilation ${L.dilation}${L.residual ? ', + residual' : ''} · ${a[0].length} s left`)), h('div', { class: 'nw-row-c nw-right' }, s)));
    });
    const p = prob(logit), day = T.logit_for_1_false_alarm_per_pair_day, hour = T.logit_for_1_false_alarm_per_pair_hour;
    out.innerHTML = `<p><b>Output</b> for the last second of the window: logit ${fmt(logit, 2)}, probability ${fmt(p * 100, p > 0.999 || p < 0.001 ? 3 : 1)} % that B's reports are faulty.</p>`
      + `<p>Alarm at the strict setting (1 false alarm per pair-day, logit above ${fmt(day, 2)}): <b>${logit > day ? 'yes' : 'no'}</b>. At the loose setting (1 per pair-hour, above ${fmt(hour, 2)}): <b>${logit > hour ? 'yes' : 'no'}</b>.</p>`
      + `<p class="small muted">${chk.what[i].replace(/\(.*\)/, '').trim()}; a validation window, not test data.</p>`;
  }
  draw();
}
