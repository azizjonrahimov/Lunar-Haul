// Home hero (F-39). First paint is a still of the base (the LCP image, and the whole hero at tier 0-1, with Save-Data or
// under reduced motion). On capable tiers, once the page is idle, the /world/ scene of the gallery's second-phase year
// (package P2, shared rovers) loads behind a small loading door that opens by itself: a slow orbit of the base under
// the low sun while landers come down and rovers drive. The view takes no input (the page scrolls through it); a Pause
// button stops it (WCAG 2.2.2), and it stops off screen and in hidden tabs.
import './home-hero.css';
import { door, reducedMotion } from './ui/index.js';
import { detectTier } from './stage/tier.js';

const BASE = import.meta.env.BASE_URL;
const root = document.querySelector('[data-hero4]');
if (root) start();

async function start() {
  if (navigator.connection?.saveData || reducedMotion()) return;   // the still stays
  const info = await detectTier();
  if (info.tier < 2 && !info.forced) return;
  await new Promise(r => (window.requestIdleCallback ? requestIdleCallback(r, { timeout: 2500 }) : setTimeout(r, 400)));   // after first paint
  const gate = door({ title: 'One year at the base', subtitle: 'The second phase on the real terrain: landers, rovers and the low sun.', autoEnter: true, beforeOpen: () => build(gate, Math.min(2, info.tier)) });
  root.querySelector('.hero-view').append(gate.el);
  gate.ready();
}

async function build(gate, tier) {
  const fetchFn = label => url => gate.fetch(url, { label });
  const [{ createWorldScene }, { loadScene }] = await Promise.all([import('./world/v2-scene.js'), import('./world/scene-data.js')]);
  const canvas = root.querySelector('.hero-canvas');
  const sc = await createWorldScene({ canvas, labelsHost: root.querySelector('.hero-labels'), tier, fetchFn: fetchFn('the 3D scene') });
  const pkg = await loadScene(`${BASE}scenes/P2/`, { fetchFn: fetchFn('one simulated year') });
  const chunks = await Promise.all(pkg.index.chunks.map((_, k) => pkg.chunk(k)));
  pkg.index.landings.sort((a, b) => a.t_h - b.t_h);
  sc.setPackage(pkg, null); sc.shots(); sc.stage.labels.show(false); sc.setIcons(false);   // true scale: no markers in a cinematic view
  const idx = pkg.index, night = t => idx.nights.some(([a, b]) => t >= a && t < b);
  const set = t => { time = Math.max(0, Math.min(idx.horizon_h - 0.01, t)); sc.setTime(time, chunks[pkg.chunkIndex(time)]); };
  // a lit, busy moment: a little before the first landing in daylight
  const L0 = idx.landings.find(L => L.ok && !night(L.t_h)) || idx.landings[0];
  let time = 0; set(L0 ? L0.t_h - 0.15 : 0);
  await sc.frameAt(sc.sitePos('BASE'), 750, 16, 35, true);
  sc.stage.director.autoRotate(1.2);   // a full turn in five minutes
  // the year plays at 0.4 h a second, slowed through each descent so no frame steps over a landing
  sc.stage.animate(dt => {
    let next = time + dt * (sc.activeLandings.length ? 0.01 : 0.4);
    if (!sc.activeLandings.length && sc.nextLandingStart) { const s0 = sc.nextLandingStart(time); if (s0 <= next) next = s0 + 1e-4; }
    set(next >= idx.horizon_h - 0.02 ? 0 : next);
    return true;
  });
  canvas.classList.add('on');
  // pause: the button, off screen, a hidden tab
  const btn = root.querySelector('.hero-pause'); let user = false;
  const apply = () => sc.stage.pause(user || hidden || offscreen);
  let hidden = document.hidden, offscreen = false;
  btn.hidden = false;
  btn.addEventListener('click', () => { user = !user; btn.textContent = user ? 'Play' : 'Pause'; btn.setAttribute('aria-pressed', String(user)); apply(); });
  document.addEventListener('visibilitychange', () => { hidden = document.hidden; apply(); });
  new IntersectionObserver(([e]) => { offscreen = !e.isIntersecting; apply(); }, { threshold: 0.05 }).observe(root);
  if (import.meta.env.DEV) window.__hero = { sc, get time() { return time; } };
}
