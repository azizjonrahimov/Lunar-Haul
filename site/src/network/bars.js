// F-61: the network against its baselines (network/e56.json, from results/table_E56.csv): recall per fault type on the
// test set at 1 false alarm per pair-day as grouped bars (categorical slots 1-5 in fixed order, validated with the
// dataviz validator on the site's surfaces), a table view of the same numbers with delays, and the out-of-distribution
// table. One axis; a legend; direct labels on the "all" group only; a title on every bar for hover.
import { h } from '../ui/index.js';
// F-78 (review W6): the site's formatter (components/num.js), which also guards against "-0.00"
import { fmt as fmtN } from '../components/num.js';

const COL = { light: ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4'], dark: ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181'] };
const dark = () => { const c = getComputedStyle(document.body).backgroundColor.match(/\d+/g) || [255, 255, 255]; return (+c[0] + +c[1] + +c[2]) / 3 < 128; };
const fmt = (v, d = 2) => fmtN(v, d);
const FAULT_LABEL = { jump: 'jump', drift: 'slow drift', frozen: 'frozen report', frame: 'frame error', noise: 'noise inflation', all: 'all faults' };

export function mountBars(host, E) {
  const dets = E.detectors, faults = E.faults, T = E.sets.test, O = E.sets.ood;
  const legend = h('ul', { class: 'nw-legend-list' });
  const svgWrap = h('div', { class: 'nw-bars' });
  host.append(legend, svgWrap);
  function draw() {
    const col = COL[dark() ? 'dark' : 'light'];
    legend.replaceChildren(...dets.map(([, name], i) => h('li', {}, h('span', { class: 'nw-sw', style: `background:${col[i]}` }), name)));
    // the drawing is as wide as its box (text stays 12 px); short fault names when narrow
    const W = Math.round(Math.max(340, Math.min(760, svgWrap.getBoundingClientRect().width || 640))), narrow = W < 520;
    const H = narrow ? 260 : 300, L = 40, B = 34, top = 14, gw = (W - L - 8) / faults.length, bw = Math.max(4, Math.min(14, (gw - 14) / dets.length - 2));
    const y = v => top + (1 - v) * (H - top - B);
    let s = `<svg viewBox="0 0 ${W} ${H}" class="nw-bars-svg" role="img" aria-label="Recall per fault type on the test set at 1 false alarm per pair-day, five detectors; the table below gives the numbers">`;
    for (const g of [0, 0.25, 0.5, 0.75, 1]) s += `<line x1="${L}" x2="${W - 8}" y1="${y(g)}" y2="${y(g)}" class="nw-gridline"/><text x="${L - 6}" y="${y(g) + 4}" class="nw-tick" text-anchor="end">${fmt(g, 2)}</text>`;
    faults.forEach((f, fi) => {
      const gx = L + fi * gw + (gw - dets.length * (bw + 2)) / 2;
      dets.forEach(([d, name], di) => {
        const r = T[d]?.[f]; if (!r) return;
        const x = gx + di * (bw + 2), v = r.recall, top0 = y(v), hgt = y(0) - top0;
        // a bar with a rounded data end (4 px) anchored to the baseline, and its 95 % interval as a thin whisker
        s += `<path d="M${x} ${y(0)}V${top0 + 3}Q${x} ${top0} ${x + 3} ${top0}H${x + bw - 3}Q${x + bw} ${top0} ${x + bw} ${top0 + 3}V${y(0)}Z" fill="${col[di]}"><title>${name}, ${FAULT_LABEL[f]}: recall ${fmt(v)} (95 % ${fmt(r.recall_ci_lo)} to ${fmt(r.recall_ci_hi)}), median delay ${fmt(r.delay_median_s, 0)} s</title></path>`;
        if (r.recall_ci_lo !== null) s += `<line x1="${x + bw / 2}" x2="${x + bw / 2}" y1="${y(r.recall_ci_hi)}" y2="${y(r.recall_ci_lo)}" class="nw-ci"/>`;
        if (f === 'all' && (d === 'net' || d === 'logreg')) s += `<text x="${x + bw / 2}" y="${top0 - 5}" class="nw-val" text-anchor="middle">${fmt(v)}</text>`;
        void hgt;
      });
      s += `<text x="${L + fi * gw + gw / 2}" y="${H - 12}" class="nw-cat" text-anchor="middle">${narrow ? f : FAULT_LABEL[f]}</text>`;
    });
    svgWrap.innerHTML = s + `<line x1="${L}" x2="${W - 8}" y1="${y(0)}" y2="${y(0)}" class="nw-axis"/></svg>`;
  }
  // the table view (the chart's numbers, with delays), and the out-of-distribution table
  const row = (d, name, set) => h('tr', {}, h('th', { scope: 'row' }, name), ...faults.map(f => { const r = set[d]?.[f]; return h('td', { class: 'n' }, r ? `${fmt(r.recall)} · ${fmt(r.delay_median_s, 0)} s` : '–'); }), h('td', { class: 'n' }, fmt(set[d]?.all?.fa_per_pair_day, 2)));
  const head = h('tr', {}, h('th', { scope: 'col' }, 'Detector'), ...faults.map(f => h('th', { scope: 'col', class: 'n' }, FAULT_LABEL[f])), h('th', { scope: 'col', class: 'n' }, 'false alarms per pair-day'));
  host.append(h('details', { class: 'nw-table-view' }, h('summary', {}, 'Table view: recall · median delay of the faults found'),
    h('div', { class: 'nw-scroll' }, h('table', { class: 'nw-table' }, h('caption', { class: 'visually-hidden' }, 'Test set, 1 false alarm per pair-day'), h('thead', {}, head), h('tbody', {}, dets.map(([d, n]) => row(d, n, T)))))));
  host.append(h('h3', { class: 'nw-h3' }, 'Out of distribution: noisier ranging, worse dead reckoning, smaller faults'),
    h('div', { class: 'nw-scroll' }, h('table', { class: 'nw-table' }, h('caption', { class: 'visually-hidden' }, 'False alarms and recall, test against out of distribution, same thresholds'),
      h('thead', {}, h('tr', {}, ...['Detector', 'false alarms per pair-day, test', 'out of distribution', 'recall on small jumps', 'on slow drifts'].map((t, i) => h('th', { scope: 'col', class: i ? 'n' : '' }, t)))),
      h('tbody', {}, dets.map(([d, n]) => h('tr', {}, h('th', { scope: 'row' }, n), h('td', { class: 'n' }, fmt(T[d]?.all?.fa_per_pair_day, 2)), h('td', { class: 'n' }, fmt(O[d]?.all?.fa_per_pair_day, O[d]?.all?.fa_per_pair_day > 100 ? 0 : 1)), h('td', { class: 'n' }, fmt(O[d]?.jump?.recall)), h('td', { class: 'n' }, fmt(O[d]?.drift?.recall))))))));
  draw();
  let lastW = 0; new ResizeObserver(() => { const w = Math.round(svgWrap.getBoundingClientRect().width); if (Math.abs(w - lastW) > 8) { lastW = w; draw(); } }).observe(svgWrap);
  new MutationObserver(draw).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
}
