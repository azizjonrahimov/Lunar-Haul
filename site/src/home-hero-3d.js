// Home hero, the 3D part (F-39), loaded by home-hero.js after first paint: on capable tiers the /world/ scene of the gallery's
// second-phase year behind a small door ("Watch it in 3D"), then a slow orbit and the year playing.
import { door, reducedMotion } from './ui/index.js';
import { detectTier } from './stage/tier.js';

const BASE = import.meta.env.BASE_URL;
let root = null;

export async function start(el) {
  root = el;
  if (reducedMotion()) return;   // the still stays
  const info = await detectTier();
  if (info.tier < 2) return;   // tiers 0-1 (detected, or forced with ?tier=) keep the still
  // the visitor starts it: building the scene blocks the page for 1-3 s (Lighthouse desktop TBT 3.1 s when it started by itself)
  const gate = door({ title: 'One year at the base', subtitle: 'The second phase on the real terrain: landers coming down, rovers driving, the low sun.', enterLabel: 'Watch it in 3D', beforeOpen: () => build(gate, Math.min(2, info.tier)) });
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
  // framed like /world/'s first view: the landing pad from the sun's side, then shifted so the pad sits right of the copy
  await sc.frameAt(sc.sitePos(L0 ? L0.pad : 'BASE'), 520, 18, 35, true);
  { const ctl = sc.stage.director.controls, v = sc.stage.camera.position, p = ctl.getPosition(v.clone()), tg = ctl.getTarget(v.clone());   // the controls' state (the camera moves on their next update)
    const fx = tg.x - p.x, fz = tg.z - p.z, fl = Math.hypot(fx, fz) || 1, rx = -fz / fl, rz = fx / fl, s = 120;
    ctl.setLookAt(p.x - rx * s, p.y, p.z - rz * s, tg.x - rx * s, tg.y, tg.z - rz * s, false); }
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
