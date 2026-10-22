// Narrative card: the short story text that rewrites itself per mode or step (eyebrow, title, text, step dots).
// Screen readers hear only the settled text: a polite live region is filled 500 ms after the last change.
import { h, icon, plainText } from './dom.js';
import { upgradeFlags } from './tooltip.js';

// narrative({steps: [{eyebrow, title, html}], index, onStep, level, label}) -> {el, go(i), set({eyebrow, title, html}), index}
// With one step (or none) the dots and arrows are left out and set() drives the card.
export function narrative({ steps = [], index = 0, onStep = () => {}, level = 2, label = 'Story' } = {}) {
  const eyebrow = h('p', { class: 'ui-label' });
  const title = h(`h${level}`, { class: 'ui-title ui-story-title' });
  const text = h('div', { class: 'ui-story-text' });
  const live = h('p', { class: 'visually-hidden', 'aria-live': 'polite' });
  const el = h('section', { class: 'ui-glass ui-story', 'aria-label': label }, eyebrow, title, text);   // stable landmark name
  let tips = [], timer = 0, dots = [], prev, next;

  if (steps.length > 1) {
    prev = h('button', { class: 'ui-iconbtn', type: 'button', 'aria-label': 'Previous step', onclick: () => api.go(api.index - 1, true) }, icon('chevron-left'));
    next = h('button', { class: 'ui-iconbtn', type: 'button', 'aria-label': 'Next step', onclick: () => api.go(api.index + 1, true) }, icon('chevron-right'));
    const list = h('ol', { class: 'ui-dots', 'aria-label': `${label} steps` }, steps.map((s, i) => {
      const b = h('button', { type: 'button', 'aria-label': `Step ${i + 1} of ${steps.length}: ${s.title}`, onclick: () => api.go(i, true) });
      dots.push(b); return h('li', {}, b);
    }));
    el.append(h('div', { class: 'ui-story-nav' }, prev, list, next));
  }
  el.append(live);

  function show({ eyebrow: e = '', title: t = '', html = '' }, announce) {
    eyebrow.textContent = e; eyebrow.hidden = !e;
    title.textContent = t;
    tips.forEach(x => x.destroy());
    text.innerHTML = html; tips = upgradeFlags(text);
    clearTimeout(timer);
    if (announce) timer = setTimeout(() => { live.textContent = `${t}. ${plainText(html)}`; }, 500);
  }
  const api = {
    el, index,
    go(i, fromUser = false) {
      if (!steps.length) return;
      api.index = Math.max(0, Math.min(steps.length - 1, i));
      show(steps[api.index], true);
      dots.forEach((d, k) => { if (k === api.index) d.setAttribute('aria-current', 'step'); else d.removeAttribute('aria-current'); });
      if (prev) {
        const f = document.activeElement;
        prev.disabled = api.index === 0; next.disabled = api.index === steps.length - 1;
        if (f && f.disabled) (f === prev ? next : prev).focus();   // a button that just went disabled would drop focus
      }
      if (fromUser) onStep(api.index);
    },
    set(content) { show(content, true); },
  };
  if (steps.length) { api.go(index); clearTimeout(timer); }   // first render is not announced
  return api;
}
