// Tooltip (WCAG 1.4.13): opens on hover, keyboard focus or tap; stays while the pointer is over it; Esc closes it
// without moving focus. The trigger gets aria-describedby, so screen readers read the text as a description.
// upgradeFlags() turns the title-only provenance flags from components/num.js into such tooltip buttons.
import { FLAGS } from '../components/num.js';

let uid = 0, openTip = null;
const GAP = 8, EDGE = 8;

addEventListener('keydown', e => { if (e.key === 'Escape' && openTip) openTip.hide(); });
addEventListener('pointerdown', e => { if (openTip && !openTip.owns(e.target)) openTip.hide(); }, { capture: true });   // tap outside

export function tooltip(trigger, content, { placement = 'top' } = {}) {
  const tip = document.createElement('div');
  tip.className = 'ui-tip'; tip.id = `ui-tip-${++uid}`; tip.setAttribute('role', 'tooltip'); tip.hidden = true;
  if (trigger.closest('.instrument')) tip.classList.add('instrument');   // the tip lives in <body>; keep the theme
  setContent(content);
  document.body.appendChild(tip);
  trigger.setAttribute('aria-describedby', [trigger.getAttribute('aria-describedby'), tip.id].filter(Boolean).join(' '));

  let timer = 0, pinned = false;
  const api = { el: tip, show, hide, set: setContent, destroy, owns: n => trigger.contains(n) || tip.contains(n) };
  function setContent(c) { if (c instanceof Node) tip.replaceChildren(c); else tip.textContent = c; }
  function show() {
    clearTimeout(timer);
    if (openTip && openTip !== api) openTip.hide();
    tip.hidden = false; openTip = api; position();
  }
  function hide() { clearTimeout(timer); tip.hidden = true; pinned = false; if (openTip === api) openTip = null; }
  const later = () => { clearTimeout(timer); timer = setTimeout(() => { if (!pinned) hide(); }, 150); };
  function position() {
    const r = trigger.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
    let top = placement === 'bottom' || r.top - h - GAP < EDGE ? r.bottom + GAP : r.top - h - GAP;
    if (top + h > innerHeight - EDGE) top = Math.max(EDGE, r.top - h - GAP);
    const left = Math.min(Math.max(EDGE, r.left + r.width / 2 - w / 2), innerWidth - w - EDGE);
    tip.style.transform = `translate(${Math.round(left)}px, ${Math.round(top)}px)`;
  }
  const onScroll = () => { if (!tip.hidden) position(); };
  const handlers = [
    ['pointerenter', e => { if (e.pointerType !== 'touch') show(); }], ['pointerleave', later],
    ['focus', show], ['blur', () => { if (!tip.matches(':hover')) hide(); }],
    ['click', () => { if (tip.hidden || !pinned) { pinned = true; show(); } else hide(); }],
  ];
  for (const [ev, fn] of handlers) trigger.addEventListener(ev, fn);
  tip.addEventListener('pointerenter', () => clearTimeout(timer));
  tip.addEventListener('pointerleave', later);
  addEventListener('scroll', onScroll, { passive: true, capture: true });
  function destroy() {
    hide(); tip.remove(); removeEventListener('scroll', onScroll, { capture: true });
    for (const [ev, fn] of handlers) trigger.removeEventListener(ev, fn);
  }
  return api;
}

// Replace each <span class="flag" title="..."> under root with a <button class="flag"> carrying a tooltip. The
// 1 px screen-reader copy that num() adds after the flag is dropped, since the button's description now says it.
export function upgradeFlags(root) {
  const tips = [];
  for (const span of root.querySelectorAll('span.flag[title]')) {
    const btn = document.createElement('button');
    btn.type = 'button'; btn.className = 'flag'; btn.dataset.flag = span.dataset.flag; btn.textContent = span.textContent;
    const text = span.getAttribute('title') || FLAGS[span.dataset.flag] || '';
    const sr = span.nextElementSibling;
    if (sr && sr.classList.contains('visually-hidden')) sr.remove();
    span.replaceWith(btn);
    tips.push(tooltip(btn, text));
  }
  return tips;
}
