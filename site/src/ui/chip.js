// Stat chip: a label over one number with its unit and provenance flag ("Carries · 1.5 t Modelled"). The number is
// rendered by components/num.js like every other number on the site; the flag becomes a tooltip button.
import { num, esc, FLAGS } from '../components/num.js';
import { h } from './dom.js';
import { upgradeFlags } from './tooltip.js';

// statChip({label, value, unit, flag, source, digits, tone: 'cool' | 'warm'}) -> {el, set(value)}
// or statChip({label, text, flag, source}) for a worded value ("parks in the dark"), flagged like a number
export function statChip({ label, tone, ...spec }) {
  const val = h('span', { class: 'ui-chip-value' });
  const el = h('div', { class: 'ui-chip', 'data-tone': tone }, h('span', { class: 'ui-label' }, label), val);
  let tips = [], shown = NaN;   // NaN equals nothing, so the first render always happens (text chips have no value)
  function render(value) {
    if (value === shown) return;   // write the DOM only when the number changes
    shown = value;
    tips.forEach(t => t.destroy());
    val.innerHTML = spec.text !== undefined ? textValue(spec) : num({ ...spec, value });
    tips = upgradeFlags(val);
  }
  render(spec.value);
  return { el, set: render };
}

// the same markup as num() for a worded value, so the flag, its tooltip and the screen-reader copy behave alike
function textValue({ text, flag, source = '' }) {
  if (!FLAGS[flag]) throw new Error(`statChip: flag must be one of ${Object.keys(FLAGS).join(', ')} (got ${flag})`);
  const tip = `${FLAGS[flag]}.${source ? ' Source: ' + source : ''}`;
  return `<span class="num"><span class="v ui-chip-text">${esc(text)}</span><span class="flag" data-flag="${flag}" title="${esc(tip)}">${flag}</span>` +
    `<span class="visually-hidden"> (${esc(tip)})</span></span>`;
}
