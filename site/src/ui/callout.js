// Callout labels (dot + leader + pill) over a canvas. The 3D stage projects each part's anchor to pixels and calls
// place(x, y) every frame; the layer writes transforms only when a value changes, and layout() pushes overlapping
// pills apart vertically. Pills are real buttons (focusable, readable) when the callout has an onSelect handler.
import { h } from './dom.js';

const SVGNS = 'http://www.w3.org/2000/svg';
const RISE = 26, RUN = 22, TAIL = 8, PAD = 6;   // leader: diagonal up RISE/RUN px, then a TAIL px shelf into the pill

// callouts(container) -> {el, add({id, text, onSelect, tone}), layout(), clear()}; container must be positioned
export function callouts(container) {
  const svg = document.createElementNS(SVGNS, 'svg');
  svg.setAttribute('aria-hidden', 'true');
  const el = h('div', { class: 'ui-callouts' }); el.append(svg);
  container.append(el);
  const items = new Map();

  function add({ id, text, onSelect, tone }) {
    const dot = h('span', { class: 'ui-callout-dot', 'aria-hidden': 'true' });
    const pill = onSelect
      ? h('button', { class: 'ui-callout-pill', type: 'button', 'data-tone': tone, 'aria-pressed': 'false', onclick: () => onSelect(id) }, text)
      : h('span', { class: 'ui-callout-pill', 'data-tone': tone }, text);
    const halo = document.createElementNS(SVGNS, 'polyline'), line = document.createElementNS(SVGNS, 'polyline');
    halo.setAttribute('class', 'halo');   // dark under-stroke: the leader stays visible over a sunlit hull
    const group = h('div', { class: 'ui-callout' }, dot, pill);
    svg.append(halo, line); el.append(group);
    const c = { id, x: 0, y: 0, side: 1, py: 0, visible: true, w: 0, hgt: 0, key: '' };
    const api = {
      id, pill,
      place(x, y, { side } = {}) {   // anchor in px relative to the container
        c.x = Math.round(x); c.y = Math.round(y);
        if (!c.w) { c.w = pill.offsetWidth; c.hgt = pill.offsetHeight; }
        c.W = el.clientWidth;
        const room = c.W - c.x;   // flip left near the right edge, unless the left has even less room
        c.side = side || (room >= RUN + TAIL + c.w + PAD || room > c.x ? 1 : -1);
        c.py = c.y - RISE;
        draw();
      },
      show(v) { if (c.visible === v) return; c.visible = v; group.hidden = !v; halo.style.display = line.style.display = v ? '' : 'none'; },
      setText(t) { pill.textContent = t; c.w = 0; },
      setPressed(v) { if (onSelect) pill.setAttribute('aria-pressed', String(v)); },
      remove() { group.remove(); halo.remove(); line.remove(); items.delete(id); },
    };
    function draw() {
      const ex = c.x + c.side * RUN;
      const px = Math.max(PAD, Math.min(c.W - c.w - PAD, c.side > 0 ? ex + TAIL : ex - TAIL - c.w));   // keep the pill inside
      const key = `${c.x},${c.y},${c.py},${c.side},${px}`;
      if (key === c.key) return;
      c.key = key;
      dot.style.transform = `translate(${c.x}px, ${c.y}px)`;
      pill.style.transform = `translate(${px}px, ${Math.round(c.py - c.hgt / 2)}px)`;
      const pts = `${c.x},${c.y} ${ex},${c.py} ${c.side > 0 ? px : px + c.w},${c.py}`;
      halo.setAttribute('points', pts); line.setAttribute('points', pts);
    }
    c.draw = draw;
    items.set(id, { c, api });
    return api;
  }

  // Resolve vertical overlaps between visible pills on the same side (greedy, top to bottom), then move any pill that
  // covers another callout's dot to just below that dot.
  function layout() {
    for (const side of [1, -1]) {
      const list = [...items.values()].map(i => i.c).filter(c => c.visible && c.side === side).sort((a, b) => a.py - b.py);
      for (let i = 1; i < list.length; i++) {
        const a = list[i - 1], b = list[i];
        const ax = a.x + side * (RUN + TAIL), bx = b.x + side * (RUN + TAIL);
        const overlapX = Math.abs(ax - bx) < Math.max(a.w, b.w) + PAD;
        const need = a.py + (a.hgt + b.hgt) / 2 + PAD;
        if (overlapX && b.py < need) { b.py = need; b.draw(); }
      }
    }
    const vis = [...items.values()].map(i => i.c).filter(c => c.visible);
    for (const c of vis) {
      const ex = c.x + c.side * RUN, px = Math.max(PAD, Math.min(c.W - c.w - PAD, c.side > 0 ? ex + TAIL : ex - TAIL - c.w));
      for (const o of vis) {
        if (o === c) continue;
        const inside = o.x > px - 6 && o.x < px + c.w + 6 && o.y > c.py - c.hgt / 2 - 6 && o.y < c.py + c.hgt / 2 + 6;
        if (inside) { c.py = o.y + c.hgt / 2 + 9; c.draw(); }
      }
    }
  }
  return { el, add, layout, items: () => [...items.values()].map(i => i.api), clear() { [...items.values()].forEach(i => i.api.remove()); } };
}
