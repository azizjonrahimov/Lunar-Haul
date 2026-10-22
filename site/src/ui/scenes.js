// Scene-switcher chips ("Landers · Rovers · Base"): a toolbar of toggle buttons. Arrow keys move focus without
// switching (a scene switch may load data); Enter or Space switches. The current scene has aria-pressed="true".
import { h } from './dom.js';

// sceneChips({label, scenes: [{value, label, note}], value, onChange}) -> {el, value, set(value)}
export function sceneChips({ label, scenes, value = scenes[0].value, onChange = () => {} }) {
  const btns = scenes.map(s => h('button', { class: 'ui-scene', type: 'button', 'data-value': s.value, tabindex: '-1' },
    s.label, s.note ? h('small', {}, s.note) : null));
  const el = h('div', { class: 'ui-scenes', role: 'toolbar', 'aria-label': label }, btns);
  const api = {
    el, value,
    set(v) {
      api.value = v;
      for (const b of btns) b.setAttribute('aria-pressed', String(b.dataset.value === v));
    },
  };
  const rove = b => { for (const x of btns) x.tabIndex = x === b ? 0 : -1; };
  el.addEventListener('click', e => {
    const b = e.target.closest('.ui-scene'); if (!b) return;
    rove(b);
    if (b.dataset.value !== api.value) { api.set(b.dataset.value); onChange(api.value); }
  });
  el.addEventListener('keydown', e => {
    const i = btns.indexOf(document.activeElement); if (i < 0) return;
    const j = { ArrowRight: i + 1, ArrowDown: i + 1, ArrowLeft: i - 1, ArrowUp: i - 1, Home: 0, End: btns.length - 1 }[e.key];
    if (j === undefined) return;
    e.preventDefault();
    const b = btns[(j + btns.length) % btns.length]; rove(b); b.focus();
  });
  api.set(value);
  rove(btns.find(b => b.dataset.value === value) || btns[0]);
  return api;
}
