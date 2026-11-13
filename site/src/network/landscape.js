// F-61: the loss landscape of the integrity network (data/atc/integrity/landscape.json, staged as network/landscape.json):
// the validation loss on a 42 x 42 grid in the PCA plane of the training path, drawn as a shaded surface on a 2D canvas
// (no WebGL needed) or as a contour map (SVG), with the path Adam took and a scrubber over its 24 checkpoints.
// Colour: one sequential hue (blue), low loss at the step nearest the surface (dataviz rules); the path in orange.
import { segmented, h } from '../ui/index.js';
// F-78 (review W6): the site's formatter (components/num.js), which also guards against "-0.00"
import { fmt } from '../components/num.js';

const RAMP = ['#cde2fb', '#b7d3f6', '#9ec5f4', '#86b6ef', '#6da7ec', '#5598e7', '#3987e5', '#2a78d6', '#256abf', '#1c5cab', '#184f95', '#104281', '#0d366b'];
const PATH_LIGHT = '#eb6834', PATH_DARK = '#d95926';
const dark = () => { const c = getComputedStyle(document.body).backgroundColor.match(/\d+/g) || [255, 255, 255]; return (+c[0] + +c[1] + +c[2]) / 3 < 128; };
const hex = s => [1, 3, 5].map(i => parseInt(s.slice(i, i + 2), 16));
const mix = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t));
// value in 0..1 -> ramp colour; in dark mode the ramp runs the other way (low values recede into the dark surface)
const rampAt = (u, dk) => { const R = dk ? [...RAMP].reverse() : RAMP, x = Math.max(0, Math.min(1, u)) * (R.length - 1), i = Math.min(R.length - 2, Math.floor(x)); return mix(hex(R[i]), hex(R[i + 1]), x - i); };

export function mountLandscape(host, L) {
  const P = L.pca, xs = P.x, ys = P.y, Z = P.val, n = xs.length, m = ys.length;
  let zmin = Infinity, zmax = -Infinity; for (const row of Z) for (const v of row) { zmin = Math.min(zmin, v); zmax = Math.max(zmax, v); }
  const lmin = Math.log(zmin), lmax = Math.log(zmax), norm = v => (Math.log(v) - lmin) / (lmax - lmin);   // log scale
  // grid coordinates -> unit square; a point in PCA coordinates -> fractional grid index
  const fx = x => (x - xs[0]) / (xs[n - 1] - xs[0]), fy = y => (y - ys[0]) / (ys[m - 1] - ys[0]);
  const path = P.path;
  let view = 'surface', az = 218, idx = path.length - 1, playing = 0;

  const canvas = h('canvas', { class: 'nw-canvas', tabindex: '0', role: 'img', 'aria-label': 'Loss surface. Drag or use the left and right arrow keys to turn it.' });
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('class', 'nw-contour'); svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', 'Contour map of the loss in the plane of the training path, with the path');
  const scrub = h('input', { type: 'range', min: 0, max: path.length - 1, step: 1, value: idx, id: 'nw-scrub', 'aria-describedby': 'nw-read' });
  const play = h('button', { type: 'button', class: 'ui-btn' }, 'Play the path');
  const read = h('p', { class: 'nw-read', id: 'nw-read', 'aria-live': 'polite' });
  const seg = segmented({ legend: 'View', options: [{ value: 'surface', label: 'Surface (3D)' }, { value: 'contour', label: 'Contour (2D)' }], value: view, onChange: v => { view = v; draw(); } });
  const legend = h('div', { class: 'nw-legend' });
  host.append(h('div', { class: 'nw-ctl' }, seg.el, h('div', { class: 'nw-scrub' }, h('label', { for: 'nw-scrub', class: 'ui-label' }, 'Training step'), scrub), play), h('div', { class: 'nw-stage' }, canvas, svg), legend, read);

  function project(gx, gy, z, W, H) {   // gx, gy in 0..1, z = normalised loss
    const a = az * Math.PI / 180, e = 32 * Math.PI / 180, s = Math.min(W * 0.58, H * 0.92);
    const u = gx - 0.5, v = gy - 0.5, hz = z * 0.3;
    const X = u * Math.cos(a) - v * Math.sin(a), Y = u * Math.sin(a) + v * Math.cos(a);
    return [W / 2 + s * X, H * 0.64 + s * (Y * Math.sin(e) - hz * Math.cos(e)), Y];
  }
  // F-78 (review W3): the quads' corners and shading are fixed; their colours are worked out once per theme, the canvas is
  // resized only when its size changes, and a drag or key press draws at most once per frame
  const QUADS = [];
  for (let j = 0; j < m - 1; j++) for (let i = 0; i < n - 1; i++) {
    const zc = (Z[j][i] + Z[j][i + 1] + Z[j + 1][i + 1] + Z[j + 1][i]) / 4;
    // light shading from the slope (form only; the colour carries the loss)
    const dzx = (Z[j][i + 1] + Z[j + 1][i + 1] - Z[j][i] - Z[j + 1][i]) / 2, dzy = (Z[j + 1][i] + Z[j + 1][i + 1] - Z[j][i] - Z[j][i + 1]) / 2;
    QUADS.push({ g: [[i, j], [i + 1, j], [i + 1, j + 1], [i, j + 1]], zc, shade: 1 - Math.max(-0.12, Math.min(0.12, (dzx * 0.7 - dzy * 0.7) / zc * 3)) });
  }
  let colDark = null, cols = null, size = '', raf = 0;
  const colours = dk => {
    if (colDark !== dk) { colDark = dk; cols = QUADS.map(q => `rgb(${rampAt(norm(q.zc), dk).map(v => Math.min(255, Math.round(v * q.shade)))})`); }
    return cols;
  };
  const later = () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; drawSurface(); }); };
  function drawSurface() {
    const dpr = Math.min(1.5, devicePixelRatio || 1), W = canvas.clientWidth, H = canvas.clientHeight;
    if (`${W}x${H}x${dpr}` !== size) { size = `${W}x${H}x${dpr}`; canvas.width = W * dpr; canvas.height = H * dpr; }
    const c = canvas.getContext('2d'); c.setTransform(dpr, 0, 0, dpr, 0, 0); c.clearRect(0, 0, W, H);
    const dk = dark(), col = colours(dk);
    const quads = QUADS.map((q, k) => { const pts = q.g.map(([a, b]) => project(a / (n - 1), b / (m - 1), norm(Z[b][a]), W, H)); return { pts, d: (pts[0][2] + pts[1][2] + pts[2][2] + pts[3][2]) / 4, col: col[k] }; });
    quads.sort((a, b) => a.d - b.d);
    const grid = dk ? 'rgba(17,18,20,0.35)' : 'rgba(255,255,255,0.45)';
    for (const q of quads) {
      c.beginPath(); q.pts.forEach(([x, y], k) => k ? c.lineTo(x, y) : c.moveTo(x, y)); c.closePath();
      c.fillStyle = q.col; c.fill(); c.strokeStyle = grid; c.lineWidth = 0.5; c.stroke();
    }
    // the path on the plane: its checkpoints at their loss on the plane, the current one ringed
    const pp = path.map(p => project(fx(p.x), fy(p.y), norm(p.val_loss_on_plane) + 0.01, W, H)), pc = dk ? PATH_DARK : PATH_LIGHT;
    c.lineWidth = 2; c.strokeStyle = pc; c.lineJoin = 'round'; c.beginPath(); pp.slice(0, idx + 1).forEach(([x, y], k) => k ? c.lineTo(x, y) : c.moveTo(x, y)); c.stroke();
    c.setLineDash([3, 4]); c.globalAlpha = 0.5; c.beginPath(); pp.slice(idx).forEach(([x, y], k) => k ? c.lineTo(x, y) : c.moveTo(x, y)); c.stroke(); c.setLineDash([]); c.globalAlpha = 1;
    const [cx, cy] = pp[idx]; c.fillStyle = pc; c.beginPath(); c.arc(cx, cy, 5, 0, 2 * Math.PI); c.fill();
    c.lineWidth = 2; c.strokeStyle = dk ? '#111214' : '#ffffff'; c.stroke();
    const end = pp[pp.length - 1]; c.fillStyle = dk ? '#eef1f5' : '#1d2127'; c.beginPath(); c.arc(end[0], end[1], 3, 0, 2 * Math.PI); c.fill();
  }
  // marching squares at evenly spaced levels -> SVG paths, plus the path
  function drawContour() {
    // F-78 (review W5): drawn at the width it is shown at, so its 12 px labels stay 12 px on a phone
    const W = Math.max(300, Math.round(svg.clientWidth || host.clientWidth || 600)), H = Math.round(Math.min(W * 0.7, 480)), padL = 52, padB = 40, pw = W - padL - 12, ph = H - padB - 12, dk = dark(), levels = 12;
    const X = gx => padL + gx * pw, Y = gy => 12 + (1 - gy) * ph;
    const segs = Array.from({ length: levels }, () => []);
    for (let lv = 0; lv < levels; lv++) {
      const t = Math.exp(lmin + (lmax - lmin) * (lv + 0.5) / levels);   // log-spaced levels
      for (let j = 0; j < m - 1; j++) for (let i = 0; i < n - 1; i++) {
        const v = [Z[j][i], Z[j][i + 1], Z[j + 1][i + 1], Z[j + 1][i]], p = [[i, j], [i + 1, j], [i + 1, j + 1], [i, j + 1]], cut = [];
        for (let e = 0; e < 4; e++) { const a = v[e], b = v[(e + 1) % 4]; if ((a < t) !== (b < t)) { const f = (t - a) / (b - a), A = p[e], B = p[(e + 1) % 4]; cut.push([(A[0] + (B[0] - A[0]) * f) / (n - 1), (A[1] + (B[1] - A[1]) * f) / (m - 1)]); } }
        if (cut.length >= 2) segs[lv].push(`M${X(cut[0][0]).toFixed(1)} ${Y(cut[0][1]).toFixed(1)}L${X(cut[1][0]).toFixed(1)} ${Y(cut[1][1]).toFixed(1)}`);
        if (cut.length === 4) segs[lv].push(`M${X(cut[2][0]).toFixed(1)} ${Y(cut[2][1]).toFixed(1)}L${X(cut[3][0]).toFixed(1)} ${Y(cut[3][1]).toFixed(1)}`);
      }
    }
    const pc = dk ? PATH_DARK : PATH_LIGHT, pts = path.map(p => [X(fx(p.x)), Y(fy(p.y))]);
    const tick = (v, d) => fmt(v, d);
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.innerHTML = `<rect x="${padL}" y="12" width="${pw}" height="${ph}" class="nw-frame"/>`
      + segs.map((s, lv) => `<path d="${s.join('')}" fill="none" stroke="rgb(${rampAt((lv + 0.5) / levels, dk)})" stroke-width="1.4"/>`).join('')
      + `<path d="M${pts.slice(0, idx + 1).map(p => p.map(v => v.toFixed(1)).join(' ')).join('L')}" fill="none" stroke="${pc}" stroke-width="2" stroke-linejoin="round"/>`
      + `<path d="M${pts.slice(idx).map(p => p.map(v => v.toFixed(1)).join(' ')).join('L')}" fill="none" stroke="${pc}" stroke-width="2" stroke-dasharray="3 4" opacity=".5"/>`
      + `<circle cx="${pts[idx][0].toFixed(1)}" cy="${pts[idx][1].toFixed(1)}" r="5" fill="${pc}" stroke="${dk ? '#111214' : '#fff'}" stroke-width="2"/>`
      + `<text class="nw-ax" x="${padL + pw / 2}" y="${H - 6}" text-anchor="middle">direction 1 of the path (${fmt(P.explained_variance[0] * 100, 1)} % of its variance)</text>`
      + `<text class="nw-ax" x="12" y="${12 + ph / 2}" text-anchor="middle" transform="rotate(-90 12 ${12 + ph / 2})">direction 2 (${fmt(P.explained_variance[1] * 100, 1)} %)</text>`
      + `<text class="nw-tick" x="${padL}" y="${12 + ph + 14}" text-anchor="start">${tick(xs[0], 1)}</text><text class="nw-tick" x="${padL + pw}" y="${12 + ph + 14}" text-anchor="end">${tick(xs[n - 1], 1)}</text>`
      + `<text class="nw-tick" x="${padL - 6}" y="${12 + ph}" text-anchor="end">${tick(ys[0], 1)}</text><text class="nw-tick" x="${padL - 6}" y="20" text-anchor="end">${tick(ys[m - 1], 1)}</text>`;
  }
  function draw() {
    canvas.hidden = view !== 'surface'; svg.style.display = view === 'contour' ? 'block' : 'none';
    if (view === 'surface') drawSurface(); else drawContour();
    const p = path[idx];
    read.textContent = `Epoch ${fmt(p.epoch, p.epoch < 1 && p.epoch > 0 ? 2 : 0)} (step ${p.step}): validation loss ${fmt(p.val_loss, 3)}; on the drawn plane ${fmt(p.val_loss_on_plane, 3)}, so ${fmt(p.out_of_plane, 3)} of the path is off the plane here.${idx === path.length - 1 ? ' This is the final model, at the centre of the plane.' : ''}`;
    const dk = dark();
    legend.innerHTML = `<span class="nw-key-bar" style="background:linear-gradient(90deg,${(dk ? [...RAMP].reverse() : RAMP).join(',')})"></span><span>validation loss ${fmt(zmin, 2)} to ${fmt(zmax, 2)} (height and colour on a log scale)</span><span class="nw-key-path" style="background:${dk ? PATH_DARK : PATH_LIGHT}"></span><span>Adam's path, ${path.length} checkpoints</span>`;
  }
  scrub.addEventListener('input', () => { idx = +scrub.value; draw(); });
  play.addEventListener('click', () => {
    if (playing) { clearInterval(playing); playing = 0; play.textContent = 'Play the path'; return; }
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) { idx = path.length - 1; scrub.value = idx; draw(); return; }
    idx = 0; play.textContent = 'Stop';
    playing = setInterval(() => { scrub.value = idx; draw(); if (++idx >= path.length) { clearInterval(playing); playing = 0; idx = path.length - 1; play.textContent = 'Play the path'; } }, 450);
  });
  // turn the surface: drag, or arrow keys on the canvas
  let drag = null;
  canvas.addEventListener('pointerdown', e => { drag = { x: e.clientX, az }; canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener('pointermove', e => { if (!drag) return; az = drag.az - (e.clientX - drag.x) * 0.5; later(); });
  canvas.addEventListener('pointerup', () => { drag = null; });
  canvas.addEventListener('keydown', e => { if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); az += e.key === 'ArrowLeft' ? 10 : -10; later(); } });
  let shownW = 0;
  new ResizeObserver(() => {
    const w = host.clientWidth; if (w === shownW) return; shownW = w;   // only on a real change of width
    if (view === 'surface') later(); else drawContour();
  }).observe(host);
  new MutationObserver(draw).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  // no 2D canvas (tier 0): the contour map
  if (!canvas.getContext || !canvas.getContext('2d')) { view = 'contour'; seg.set('contour'); }
  draw();
}
