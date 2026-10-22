// WCAG 2.2 contrast from CSS colours: parse any colour the browser understands (custom properties included),
// composite translucent layers in sRGB the way the browser paints them, and compute the contrast ratio.

let ctx;
// rgba(cssColour) -> [r, g, b, a] with r, g, b in 0-255 and a in 0-1
export function rgba(css) {
  ctx = ctx || document.createElement('canvas').getContext('2d');
  ctx.fillStyle = '#000'; ctx.fillStyle = css;
  const s = ctx.fillStyle;
  if (s[0] === '#') return [parseInt(s.slice(1, 3), 16), parseInt(s.slice(3, 5), 16), parseInt(s.slice(5, 7), 16), 1];
  const m = s.match(/[\d.]+/g).map(Number);
  return [m[0], m[1], m[2], m[3] ?? 1];
}

// over(top, bottom): top composited over an opaque bottom
export const over = (t, b) => [0, 1, 2].map(i => t[i] * t[3] + b[i] * (1 - t[3])).concat(1);

const lin = c => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
export const luminance = c => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);

// ratio(fg, bg): fg may be translucent (composited over bg first); bg must be opaque
export function ratio(fg, bg) {
  const a = luminance(over(fg, bg)), b = luminance(bg);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

// tokens(el, names) -> {name: [r, g, b, a]} read from the custom properties in effect on el
export function tokens(el, names) {
  const cs = getComputedStyle(el);
  return Object.fromEntries(names.map(n => [n, rgba(cs.getPropertyValue(`--${n}`).trim())]));
}
