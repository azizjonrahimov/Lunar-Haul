// F-81: the three /network/ figures redraw when the theme changes, whether the reader picks it (the data-theme attribute
// the site's toggle sets) or the system switches its colour scheme (prefers-color-scheme, followed while no theme is picked)
export function onTheme(draw) {
  new MutationObserver(draw).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', draw);
}
