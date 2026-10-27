// "Skip quiet time" (F-50): at slow speeds a year has long stretches where no rover drives (nights, waits). The page
// jumps over them to a second before the next drive or landing and says how much it skipped. No three.js, so Node
// tests can use it.

/* motionIndex(pkg, chunks) -> {moving(t), nextStart(t)}: every drive of every vehicle in the loaded chunks, merged
   into sorted [t0, t1) intervals (hours) */
export function motionIndex(pkg, chunks) {
  const C = pkg.columns, n = pkg.index.segment_columns.length, iv = [];
  for (const ch of chunks) {
    const s = ch.seg;
    for (let r = 0; r < ch.rows; r++) {
      const o = r * n, drive = s[o + C.route] >= 0 ? s[o + C.f0] !== s[o + C.f1] : s[o + C.x0] !== s[o + C.x1] || s[o + C.y0] !== s[o + C.y1];
      if (drive) iv.push([s[o + C.t0], s[o + C.t1]]);
    }
  }
  iv.sort((a, b) => a[0] - b[0]);
  const m = [];
  for (const [a, b] of iv) { const L = m[m.length - 1]; if (L && a <= L[1]) L[1] = Math.max(L[1], b); else m.push([a, b]); }
  // the first interval that ends after t
  const find = t => { let lo = 0, hi = m.length; while (lo < hi) { const k = (lo + hi) >> 1; if (m[k][1] <= t) lo = k + 1; else hi = k; } return lo; };
  return {
    intervals: m,
    moving(t) { const k = find(t); return k < m.length && m[k][0] <= t; },
    nextStart(t) { let k = find(t); if (k < m.length && m[k][0] <= t) k++; return k < m.length ? m[k][0] : Infinity; },
  };
}

/* quietJump(t, rateH, index, nextLanding) -> the hour to jump to, or null. rateH: simulated hours per real second.
   Skips only when nothing drives now, no landing starts within the next screen-minute and the next drive or landing
   is more than 3 screen-seconds away; lands one screen-second before it, so the start is seen. */
export function quietJump(t, rateH, index, nextLanding = Infinity, { leadS = 1, minGapS = 3, landingS = 60 } = {}) {
  if (index.moving(t) || nextLanding - t <= landingS * rateH) return null;
  const ev = Math.min(index.nextStart(t), nextLanding);
  if (!Number.isFinite(ev) || ev - t <= minGapS * rateH) return null;
  return ev - leadS * rateH;
}
