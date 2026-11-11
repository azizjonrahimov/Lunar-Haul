// F-62: the navigation-stack cutaway on /protocol/ (static SVG from lib/anatomy-nav.mjs). One part is lit at a time:
// picked in the list (click, focus, hover) or by hovering the drawing; when nobody touches it, a slow tour visits each
// part while the figure is on screen. Reduced motion: no tour, the first part stays lit.
import './anatomy.css';

export function mountNavStack(root = document.querySelector('.iso.nv')) {
  if (!root) return;
  const groups = [...root.querySelectorAll('.nv-part')], items = [...root.querySelectorAll('.nv-item')];
  const read = root.querySelector('[data-corner="readout"]'), still = matchMedia('(prefers-reduced-motion: reduce)');
  let current = null, touring = !still.matches, visible = false, timer = 0, idle = 0;
  function show(id) {
    if (id === current) return;
    current = id;
    for (const g of groups) {
      const on = g.dataset.part === id || g.dataset.also === id;
      for (const s of g.querySelectorAll('.iso-solid')) s.toggleAttribute('data-lit', on);
    }
    for (const b of items) b.setAttribute('aria-pressed', String(b.dataset.part === id));
    const b = items.find(x => x.dataset.part === id);
    if (read && b) read.textContent = b.querySelector('.nv-name').textContent;
  }
  const order = items.map(b => b.dataset.part);
  const step = () => { if (touring && visible) show(order[(order.indexOf(current) + 1) % order.length]); };
  const run = () => { clearInterval(timer); timer = touring && visible ? setInterval(step, 2800) : 0; };
  const touch = id => {
    show(id); touring = false; run();
    clearTimeout(idle); if (!still.matches) idle = setTimeout(() => { touring = true; run(); }, 8000);
  };
  for (const b of items) {
    b.addEventListener('click', () => touch(b.dataset.part));
    b.addEventListener('focus', () => touch(b.dataset.part));
    b.addEventListener('pointerenter', () => touch(b.dataset.part));
  }
  for (const g of groups) g.addEventListener('pointerenter', () => touch(g.dataset.part));
  new IntersectionObserver(es => { visible = es[es.length - 1].isIntersecting; run(); }).observe(root);
  show(order[0]);
}
