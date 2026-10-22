// Big animated counter (the lander lab's SCORE): tabular mono digits, an explicit sign and a ▲/▼ glyph next to the
// red/green colour, a ~400 ms count to each new value (instant under prefers-reduced-motion). Screen readers hear
// only committed values (commit(), e.g. at the end of an episode), never the frames in between.
import { h, reducedMotion } from './dom.js';

const MINUS = '−';

// counter({label, value, digits, unit, unitLabel, signed}) -> {el, value, set(v, {animate}), commit(text)}
export function counter({ label, value = 0, digits = 0, unit = '', unitLabel = unit, signed = true }) {
  const glyph = h('span', { class: 'ui-counter-glyph', 'aria-hidden': 'true' });
  const numEl = h('span', { class: 'ui-counter-num' });
  const live = h('span', { class: 'visually-hidden', 'aria-live': 'polite' });
  const el = h('div', { class: 'ui-counter' },
    h('span', { class: 'ui-label' }, label),
    h('span', { class: 'ui-counter-value' }, signed ? glyph : null, numEl, unit ? h('span', { class: 'ui-counter-unit' }, unit) : null),
    live);

  const text = v => {
    const r = Math.abs(v) < 0.5 * 10 ** -digits ? 0 : v;
    const s = Math.abs(r).toLocaleString('en-GB', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    return signed ? (r > 0 ? '+' : r < 0 ? MINUS : '') + s : (r < 0 ? MINUS : '') + s;
  };
  let shown = value, target = value, from = value, t0 = 0, raf = 0;
  function paint(v) {
    shown = v;
    const s = text(v);
    if (numEl.textContent !== s) numEl.textContent = s;
    if (signed) el.dataset.sign = s.startsWith('+') ? 'pos' : s.startsWith(MINUS) ? 'neg' : 'zero';
  }
  function frame(now) {
    const dur = 400, k = Math.min(1, (now - t0) / dur), e = 1 - (1 - k) ** 3;   // ease-out cubic
    paint(from + (target - from) * e);
    raf = k < 1 ? requestAnimationFrame(frame) : 0;
  }
  const api = {
    el, get value() { return target; },
    set(v, { animate = true } = {}) {
      target = +v;
      cancelAnimationFrame(raf); raf = 0;
      if (!animate || reducedMotion() || document.hidden) return paint(target);
      from = shown; t0 = performance.now(); raf = requestAnimationFrame(frame);
    },
    commit(say) { live.textContent = say || `${label} ${text(target).replace(MINUS, 'minus ')}${unitLabel ? ' ' + unitLabel : ''}`; },
  };
  paint(value);
  return api;
}
