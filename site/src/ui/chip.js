// Stat chip: a label over one number with its unit and provenance flag ("Carries · 1.5 t Modelled"). The number is
// rendered by components/num.js like every other number on the site; the flag becomes a tooltip button.
import { num } from '../components/num.js';
import { h } from './dom.js';
import { upgradeFlags } from './tooltip.js';

// statChip({label, value, unit, flag, source, digits, tone: 'cool' | 'warm'}) -> {el, set(value)}
export function statChip({ label, tone, ...spec }) {
  const val = h('span', { class: 'ui-chip-value' });
  const el = h('div', { class: 'ui-chip', 'data-tone': tone }, h('span', { class: 'ui-label' }, label), val);
  let tips = [], shown;
  function render(value) {
    if (value === shown) return;   // write the DOM only when the number changes
    shown = value;
    tips.forEach(t => t.destroy());
    val.innerHTML = num({ ...spec, value });
    tips = upgradeFlags(val);
  }
  render(spec.value);
  return { el, set: render };
}
