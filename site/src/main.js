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

mountFigures();

