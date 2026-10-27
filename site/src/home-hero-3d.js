// Home hero, the 3D part (F-39), loaded by home-hero.js after first paint: on capable tiers the /world/ scene of the gallery's
// second-phase year behind a small door ("Watch it in 3D"), then a slow orbit and the year playing at 5 min a second
// (F-50: the close shot's speed, shown by the shared time-scale label), quiet stretches skipped.
import { door, reducedMotion } from './ui/index.js';
import { detectTier } from './stage/tier.js';
import { createTimescale, hoursText } from './ui/timescale.js';

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
  const [{ createWorldScene }, { loadScene }, { motionIndex, quietJump }] = await Promise.all([import('./world/v2-scene.js'), import('./world/scene-data.js'), import('./world/quiet.js')]);
  const canvas = root.querySelector('.hero-canvas');
  const sc = await createWorldScene({ canvas, labelsHost: root.querySelector('.hero-labels'), tier, fetchFn: fetchFn('the 3D scene') });
  const pkg = await loadScene(`${BASE}scenes/P2/`, { fetchFn: fetchFn('one simulated year') });
  const chunks = await Promise.all(pkg.index.chunks.map((_, k) => pkg.chunk(k)));
  pkg.index.landings.sort((a, b) => a.t_h - b.t_h);
  const motion = motionIndex(pkg, chunks), ts = createTimescale({ value: 300, picker: false, keys: false, url: false });
  ts.el.classList.add('hero-speed'); root.querySelector('.hero-pause').after(ts.el);
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
  // the year plays at 5 min a second, slowed to 36 s a second through each descent so no frame steps over a landing
  sc.stage.animate(dt => {
    const landing = sc.activeLandings.length > 0, rate = landing ? 0.01 : ts.h;
    ts.override(landing ? 36 : null);
    let next = time + dt * rate;
    const s0 = !landing && sc.nextLandingStart ? sc.nextLandingStart(time) : Infinity;
    if (s0 <= next) next = s0 + 1e-4;
    else if (!landing) { const j = quietJump(time, rate, motion, s0); if (j !== null && j > next) { ts.toast(`Skipped ${hoursText(j - time)}, nothing moving`); next = j; } }
    set(next >= idx.horizon_h - 0.02 ? 0 : next);
    return true;
  });
  canvas.classList.add('on');
  // pause: the button, off screen, a hidden tab
  // F-40: under reduced motion the year opens paused (the button says Play), as /world/ does
  const btn = root.querySelector('.hero-pause'); let user = reducedMotion();
  const apply = () => sc.stage.pause(user || hidden || offscreen), label = () => { btn.textContent = user ? 'Play' : 'Pause'; btn.setAttribute('aria-pressed', String(user)); };
  let hidden = document.hidden, offscreen = false;
  btn.hidden = false; label(); apply();
  btn.addEventListener('click', () => { user = !user; label(); apply(); });
  document.addEventListener('visibilitychange', () => { hidden = document.hidden; apply(); });
  new IntersectionObserver(([e]) => { offscreen = !e.isIntersecting; apply(); }, { threshold: 0.05 }).observe(root);
  if (import.meta.env.DEV) window.__hero = { sc, get time() { return time; } };
}
