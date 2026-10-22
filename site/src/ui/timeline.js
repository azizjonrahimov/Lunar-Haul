// Timeline: a native range input (keyboard, screen-reader value text) drawn over shaded bands (lunar night) and
// event ticks (landings, nightfall, strandings), with previous/next-event buttons and a legend. Each tick kind
// has its own shape, so the colour is never the only cue (WCAG 1.4.1).
import { h, uid, icon } from './dom.js';

export const TICK_KINDS = { landing: 'Landing', night: 'Nightfall', strand: 'Stranding', info: 'Event' };

// timeline({label, min, max, step, value, format, events: [{t, kind, label}], bands: [{from, to}], bandLabel, onInput})
//   -> {el, value, set(v), setEvents(events), setBands(bands)}
export function timeline({ label, min = 0, max = 100, step = 'any', value = min, format = v => String(v), events = [], bands = [],
  bandLabel = 'Night', onInput = () => {} }) {
  const id = uid('tl');
  const out = h('output', { class: 'ui-tl-value', for: id });
  const input = h('input', { type: 'range', id, min, max, step, value });
  const bandEl = h('div', { class: 'ui-tl-bands', 'aria-hidden': 'true' });
  const tickEl = h('div', { class: 'ui-tl-ticks', 'aria-hidden': 'true' });
  const prev = h('button', { class: 'ui-iconbtn', type: 'button', 'aria-label': 'Previous event', onclick: () => jump(-1) }, icon('skip-back'));
  const next = h('button', { class: 'ui-iconbtn', type: 'button', 'aria-label': 'Next event', onclick: () => jump(1) }, icon('skip-forward'));
  const evText = h('span', { 'aria-live': 'polite' });
  const legend = h('ul', { class: 'ui-tl-legend', 'aria-label': 'Timeline key' });
  const el = h('div', { class: 'ui-timeline' },
    h('div', { class: 'ui-tl-head' }, h('label', { class: 'ui-label', for: id }, label), out),
    h('div', { class: 'ui-tl-track' }, bandEl, tickEl, input),
    h('div', { class: 'ui-tl-foot' }, prev, next, evText, legend));

  const api = { el, value: +value, set, setEvents, setBands };
  const pct = t => `${((t - min) / (max - min)) * 100}%`;
  let shownText = '';
  function set(v) {
    api.value = Math.min(max, Math.max(min, +v));
    if (+input.value !== api.value) input.value = api.value;
    input.style.setProperty('--p', pct(api.value));
    const t = format(api.value);
    if (t !== shownText) { shownText = t; out.textContent = t; input.setAttribute('aria-valuetext', t); }   // only on change
  }
  function setEvents(list) {
    events = [...list].sort((a, b) => a.t - b.t);
    tickEl.replaceChildren(...events.map(e => h('span', { class: 'ui-tl-tick', 'data-kind': e.kind, style: `left:${pct(e.t)}`, title: e.label })));
    drawLegend();
  }
  function setBands(list) {
    bands = list;
    bandEl.replaceChildren(...bands.map(b => h('span', { class: 'ui-tl-band', style: `left:${pct(b.from)};width:calc(${pct(b.to)} - ${pct(b.from)})` })));
    drawLegend();
  }
  function drawLegend() {
    const kinds = [...new Set(events.map(e => e.kind))];
    legend.replaceChildren(...kinds.map(k => h('li', {}, h('span', { class: 'ui-tl-tick', 'data-kind': k }), TICK_KINDS[k] || k)),
      ...(bands.length ? [h('li', {}, h('span', { class: 'ui-tl-band' }), bandLabel)] : []));
    prev.disabled = next.disabled = !events.length;
  }
  function jump(dir) {
    const eps = 1e-9, e = dir > 0 ? events.find(x => x.t > api.value + eps) : [...events].reverse().find(x => x.t < api.value - eps);
    if (!e) return;
    set(e.t); evText.textContent = `${TICK_KINDS[e.kind] || e.kind}: ${e.label}, ${format(e.t)}`;
    onInput(api.value, e);
  }
  input.addEventListener('input', () => { set(input.value); evText.textContent = ''; onInput(api.value, null); });
  setEvents(events); setBands(bands); set(value);
  return api;
}
