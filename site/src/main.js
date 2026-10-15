// Shared page script: styles, theme toggle, mobile menu; loads the hero only on pages that have one.
import './styles/tokens.css';
import './styles/base.css';
import { mountFigures } from './components/figure.js';

const store = { get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } } };

// theme: explicit choice in data-theme (set early by the inline head script), else the system preference
const dark = () => document.documentElement.dataset.theme ? document.documentElement.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
for (const b of document.querySelectorAll('[data-theme-toggle]')) {
  const sync = () => b.setAttribute('aria-pressed', String(dark()));
  b.addEventListener('click', () => { const t = dark() ? 'light' : 'dark'; document.documentElement.dataset.theme = t; store.set('lunarsim.theme', t); sync(); });
  sync();
}
for (const b of document.querySelectorAll('[data-menu]')) {
  const nav = document.getElementById(b.getAttribute('aria-controls'));
  b.addEventListener('click', () => { const open = !nav.classList.contains('open'); nav.classList.toggle('open', open); b.setAttribute('aria-expanded', String(open)); });
}

mountFigures();

const hero = document.querySelector('[data-hero]');
if (hero) {
  const status = hero.querySelector('[data-hero-status]');
  import('./hero.js').then(({ startHero }) => startHero({
    root: hero, canvas: hero.querySelector('canvas'), pauseBtn: hero.querySelector('[data-hero-pause]'),
    slider: hero.querySelector('[data-hero-az]'), readout: hero.querySelector('[data-hero-sun]'),
    terrainUrl: hero.dataset.terrain,
    onReady: t => { hero.classList.add('has-webgl'); const cap = document.querySelector('[data-hero-terrain]'); if (cap) cap.textContent = describe(t); },
  })).catch(err => { if (status) status.textContent = `The 3D view could not start here (${err.message}). The description below says what it shows.`; });
}
function describe(t) {
  const m = t.meta, km = (t.sizeM[0] / 1000).toFixed(0);
  return `${m.source.product}, ${km} × ${km} km, ${t.postM.toFixed(0)} m posts, heights ${Math.round(t.zMin)} to ${Math.round(t.zMax)} m${m.dev_standin ? ' (development stand-in pack)' : ''}. ${m.source.credit}.`;
}
