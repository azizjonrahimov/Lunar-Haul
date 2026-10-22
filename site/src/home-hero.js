// Home hero (F-39). First paint is a still of the base (the LCP image, and the whole hero at tier 0-1, with Save-Data or
// under reduced motion). On capable tiers, once the page is idle, the /world/ scene of the gallery's second-phase year
// (package P2, shared rovers) is offered on a small door card; pressed, it loads and opens on a slow orbit of the base under
// the low sun while landers come down and rovers drive. The view takes no input (the page scrolls through it); a Pause
// button stops it (WCAG 2.2.2), and it stops off screen and in hidden tabs.
// its CSS (home-hero.css) is inlined into index.html at build time (<!--@hero-css-->)

const root = document.querySelector('[data-hero4]');
// the 3D part (door, tier check, scene) is a lazy chunk, fetched after first paint and only without Save-Data or reduced motion
if (root && !navigator.connection?.saveData && !matchMedia('(prefers-reduced-motion: reduce)').matches)
  (window.requestIdleCallback || (f => setTimeout(f, 400)))(() => import('./home-hero-3d.js').then(m => m.start(root)), { timeout: 2500 });

