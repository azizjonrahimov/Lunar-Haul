// Runs fn once the page's first text is on screen (the browser's first-contentful-paint entry), so a page's heavy data
// loads after its text instead of alongside it (F-40: Lighthouse mobile counted /world/trace/'s 3 MB of terrain and the
// lander lab's policies in their LCP). Without paint timing it waits one frame.
export function afterFirstPaint(fn) {
  if (!window.PerformanceObserver?.supportedEntryTypes?.includes('paint')) { requestAnimationFrame(() => setTimeout(fn)); return; }
  const o = new PerformanceObserver(list => {
    if (list.getEntriesByName('first-contentful-paint').length) { o.disconnect(); setTimeout(fn); }
  });
  o.observe({ type: 'paint', buffered: true });
}
