// Small DOM helpers shared by the UI components: element builder, ids, reduced-motion check, Lucide icons.
import chevronLeft from 'lucide-static/icons/chevron-left.svg?raw';
import chevronRight from 'lucide-static/icons/chevron-right.svg?raw';
import skipBack from 'lucide-static/icons/skip-back.svg?raw';
import skipForward from 'lucide-static/icons/skip-forward.svg?raw';

let n = 0;
export const uid = p => `${p}-${++n}`;
export const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

// h('button', {class: 'x', type: 'button', onclick: fn}, child, 'text') -> element
export function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'class') el.className = v;
    else if (k === 'html') el.innerHTML = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat()) if (k !== null && k !== undefined && k !== false) el.append(k instanceof Node ? k : String(k));
  return el;
}

const ICONS = { 'chevron-left': chevronLeft, 'chevron-right': chevronRight, 'skip-back': skipBack, 'skip-forward': skipForward };
export function icon(name) {
  const t = document.createElement('template');
  t.innerHTML = ICONS[name].replace(/<!--[\s\S]*?-->/g, '').replace(/class="[^"]*"/, 'class="icon" aria-hidden="true" focusable="false"').replace(/\s(width|height)="24"/g, '');
  return t.content.firstElementChild;
}

// Plain text of an HTML fragment (for live regions: numbers read once, without the flag tooltips' 1 px copies)
export function plainText(html) {
  const t = document.createElement('template'); t.innerHTML = html;
  t.content.querySelectorAll('.visually-hidden').forEach(e => e.remove());
  return t.content.textContent.replace(/\s+/g, ' ').trim();
}
