// Shared page script: styles, theme toggle, mobile menu. (The home hero has its own module since F-39: src/home-hero.js.)
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

// F-66: the Labs and About menus (disclosure buttons): open on click / Enter / Space, close on Escape (focus back on
// the button), on a click outside, and when focus leaves the menu; one open at a time
const menus = [...document.querySelectorAll('.nav-menu')];
const closeMenu = (m, refocus = false) => {
  if (!m.classList.contains('open')) return;
  m.classList.remove('open');
  const b = m.querySelector('.nav-menu-btn'); b.setAttribute('aria-expanded', 'false'); if (refocus) b.focus();
};
for (const m of menus) {
  const b = m.querySelector('.nav-menu-btn');
  b.addEventListener('click', () => {
    const open = !m.classList.contains('open');
    for (const o of menus) if (o !== m) closeMenu(o);
    m.classList.toggle('open', open); b.setAttribute('aria-expanded', String(open));
  });
  m.addEventListener('keydown', e => { if (e.key === 'Escape' && m.classList.contains('open')) { e.preventDefault(); e.stopPropagation(); closeMenu(m, true); } });
  m.addEventListener('focusout', e => { if (e.relatedTarget && !m.contains(e.relatedTarget)) closeMenu(m); });
}
if (menus.length) document.addEventListener('click', e => { for (const m of menus) if (!m.contains(e.target)) closeMenu(m); });

mountFigures();

