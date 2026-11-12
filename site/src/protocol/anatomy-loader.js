// F-68/F-61: the cutaway slots (.an-slot[data-anat]) on /protocol/ and /network/: when a slot nears the screen, fetch its
// fragment (protocol/anatomy/<id>.html), the cutaways' stylesheet and the live chunk, then mount. Without JS, or if a
// fetch fails, the slot shows its standalone still (the <noscript> image).
import { upgradeFlags } from '../ui/tooltip.js';

const BASE = import.meta.env.BASE_URL;
let sheet = null;
const loadSheet = () => sheet ||= new Promise(res => { const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = `${BASE}protocol/anatomy/anatomy.css`; l.onload = res; l.onerror = res; document.head.append(l); });

export function mountSlots(root = document) {
  const slots = [...root.querySelectorAll('.an-slot[data-anat]')];
  if (!slots.length) return;
  const io = new IntersectionObserver(entries => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      io.unobserve(e.target);
      const slot = e.target, id = slot.dataset.anat;
      Promise.all([fetch(`${BASE}protocol/anatomy/${id}.html`).then(r => { if (!r.ok) throw new Error(r.status); return r.text(); }), import('./anatomy-live.js'), loadSheet()])
        .then(([html, live]) => {
          const t = document.createElement('template'); t.innerHTML = html;
          const fig = t.content.firstElementChild; slot.append(fig);
          upgradeFlags(fig); live.mount(fig);
        })
        .catch(() => { const img = slot.querySelector('noscript'); if (img) slot.insertAdjacentHTML('beforeend', img.textContent); });
    }
  }, { rootMargin: '400px 0px' });
  for (const s of slots) io.observe(s);
}
