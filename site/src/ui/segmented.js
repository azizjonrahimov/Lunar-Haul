// Segmented pill control: one choice out of 2-5 modes ("Whole / Cutaway / Exploded"). Built on native radio inputs
// in a fieldset, so the browser supplies the radiogroup role, arrow-key movement and form semantics.
import { h, uid } from './dom.js';

// segmented({legend, options: [{value, label}], value, onChange, hideLegend}) -> {el, value, set(value), setDisabled(value, bool)}
export function segmented({ legend, options, value = options[0].value, onChange = () => {}, hideLegend = false, name = uid('seg') }) {
  const inputs = new Map();
  const track = h('div', { class: 'ui-seg-track' }, options.map(o => {
    const input = h('input', { type: 'radio', name, value: o.value, checked: o.value === value, disabled: o.disabled });
    inputs.set(o.value, input);
    return h('label', {}, input, h('span', {}, o.label));
  }));
  const el = h('fieldset', { class: 'ui-seg' }, h('legend', { class: hideLegend ? 'visually-hidden' : 'ui-label' }, legend), track);
  const api = {
    el, value,
    set(v) { const i = inputs.get(v); if (i) { i.checked = true; api.value = v; } },
    setDisabled(v, off) { const i = inputs.get(v); if (i) i.disabled = off; },
  };
  el.addEventListener('change', e => { if (e.target.name === name) { api.value = e.target.value; onChange(api.value); } });
  return api;
}
