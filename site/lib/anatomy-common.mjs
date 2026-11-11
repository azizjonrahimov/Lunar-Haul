// F-68: shared pieces of the /protocol/ cutaways (Fig 1b-1d), built at build time with the anatomy kit (vendor/anatomy,
// MIT): the projection fitted into the middle of a wider card (label columns either side), labels with leader lines
// (pins on narrow screens), moving groups for the "open" view, the part list, the plate, and a standalone still.
import * as k from '../vendor/anatomy/iso-kit.mjs';
import { esc } from '../src/components/num.js';

export { k };
export const W = 760;   // card width in SVG units; the drawing sits in the middle, labels in the side columns
export const COL = 150; // width of each label column

// fit the drawing into the middle (W - 2 COL) and move it right by COL
export function project(points, height, opts = {}) {
  const P = k.fitProjection(points, W - 2 * COL, height, opts);
  return { ...P, origin: [P.origin[0] + COL, P.origin[1]] };
}

export function tools(P) {
  const at = p => k.iso(p, P);
  return {
    at,
    S: (paths, o) => k.solidSvg(paths, o),
    L: (d, o) => k.lineSvg(d, o),
    D: (pts, o) => k.dotsSvg(pts, o),
    depth: ([x, y, z = 0]) => k.depthOf([x, y, z], P),
    byDepth: pts => [...pts].sort((a, b) => k.depthOf([a[0], a[1], 0], P) - k.depthOf([b[0], b[1], 0], P)),
    // a world vector as a screen offset, for a group that moves when the figure opens
    move: v => k.axisVector(P, v).map(x => Math.round(x * 100) / 100).join(' '),
    // a circle in a vertical plane facing +y
    faceCircle: (cx, y, cz, r, n = 28) => k.pathOf(Array.from({ length: n }, (_, i) => { const t = 2 * Math.PI * i / n; return at([cx + r * Math.cos(t), y, cz + r * Math.sin(t)]); }), true),
  };
}

// labels: [{ id, anchor: [x, y, z] world, title, value }] -> leader lines into two columns, plus numbered pins.
// The leader starts on a dot on the part, runs to the column edge and ends on the label's box, so no line floats.
export function labels(P, items, height) {
  const at = p => k.iso(p, P);
  const pts = items.map((it, i) => ({ ...it, n: i + 1, a: at(it.anchor) }));
  const mid = W / 2, out = [], pins = [];
  for (const side of ['left', 'right']) {
    const col = pts.filter(p => (side === 'left') === (p.a[0] < mid)).sort((a, b) => a.a[1] - b.a[1]);
    if (!col.length) continue;
    const top = 40, bottom = height - 40, gap = Math.max(36, Math.min(70, (bottom - top) / col.length));
    // place each label near its anchor's height, keep them gap apart, then clamp into the card
    let y = top;
    const ys = col.map(p => { y = Math.max(y, Math.min(p.a[1], bottom)); const v = y; y += gap; return v; });
    const over = ys.length ? ys[ys.length - 1] - bottom : 0;
    if (over > 0) for (let i = ys.length - 1; i >= 0; i--) ys[i] = Math.max(top + i * gap, ys[i] - over);
    col.forEach((p, i) => {
      const ly = ys[i], bx = side === 'left' ? 8 : W - COL + 8, bw = COL - 16, edge = side === 'left' ? bx + bw : bx;
      const elbow = side === 'left' ? edge + 14 : edge - 14;
      out.push(`<g class="an-label" data-part="${p.id}">`
        + `<path class="an-leader" d="M${r1(p.a[0])} ${r1(p.a[1])}L${r1(elbow)} ${r1(ly)}L${r1(edge)} ${r1(ly)}"/>`
        + `<circle class="an-anchor" cx="${r1(p.a[0])}" cy="${r1(p.a[1])}" r="1.6"/>`
        + `<rect class="an-box" x="${bx}" y="${r1(ly - 14)}" width="${bw}" height="28" rx="3"/>`
        + `<text class="an-title" x="${bx + 7}" y="${r1(ly - 2.5)}">${esc(p.title)}</text>`
        + `<text class="an-value" x="${bx + 7}" y="${r1(ly + 9.5)}">${esc(p.value)}</text></g>`);
    });
  }
  for (const p of pts) pins.push(`<g class="an-pin" data-part="${p.id}"><circle cx="${r1(p.a[0])}" cy="${r1(p.a[1])}" r="7"/><text x="${r1(p.a[0])}" y="${r1(p.a[1] + 3.2)}">${p.n}</text></g>`);
  return `<g class="an-labels">${out.join('')}</g><g class="an-pins">${pins.join('')}</g>`;
}
const r1 = v => Math.round(v * 10) / 10;

// the key to the numbered pins, for a figure without a part list (the page shows it only when the figure is compact)
export const pinKey = items => `<ol class="an-pinkey">${items.map(it => `<li><b>${esc(it.title)}</b> ${esc(it.value)}</li>`).join('')}</ol>`;

// the part list under (or beside) the plate: name, whose number, what it does, the numbers with flags (HTML)
export function partList(rows, aria) {
  return `<ol class="nv-list" aria-label="${esc(aria)}">${rows.map(([id, name, what, numbers, whose], i) =>
    `<li><button type="button" class="nv-item" data-part="${id}" aria-pressed="false"><span class="nv-n" aria-hidden="true">${i + 1}</span><span class="nv-name">${esc(name)}</span> <span class="nv-whose" data-whose="${whose.startsWith('our') ? 'ours' : whose.startsWith('published board') ? 'mixed' : 'published'}">${esc(whose)}</span></button><span class="nv-what">${esc(what)} ${numbers}.</span></li>`).join('')}</ol>`;
}

// the card: Fig, title, hint, readout, legend; controls (HTML) sit under the plate
// the caption may hold flagged numbers (HTML): the kit escapes captions, so it goes in through a placeholder. The plate's
// corners are aria-hidden in the kit, so a polite live region under the plate carries the readout for screen readers.
export function plate({ fig, title, hint, readout, keys, caption, svg, controls = '', list = '', kind }) {
  const body = `<div class="iso-stage an-stage">${svg.replace('<svg', `<svg data-col="${COL}"`)}</div>`;   // the page crops the label columns away when compact
  const html = k.plateHtml({ fig, title, hint, readout, keys, caption: '@@CAPTION@@', body }).replace('@@CAPTION@@', caption);
  return `<div class="iso an" data-anat="${kind}">${html}<p class="visually-hidden an-live" aria-live="polite"></p>${controls ? `<div class="an-controls">${controls}</div>` : ''}${list}</div>`;
}

// the theme tokens for the cutaways (stronger shade separation than the kit's defaults; LEAD, F-68), used by the
// site stylesheet and embedded in the standalone still
export const LIGHT_TOKENS = `--anatomy-page:#e9ecef;--anatomy-card:#e4e8ec;--anatomy-text:#45494f;--anatomy-strong:#16191d;--anatomy-muted:#5b6168;
--anatomy-paper:#e4e8ec;--anatomy-face:#ffffff;--anatomy-top:#fbfcfd;
--anatomy-shade-0:#a9b0b9;--anatomy-shade-1:#c0c6cd;--anatomy-shade-2:#d4d9de;--anatomy-shade-3:#e6e9ed;
--anatomy-lit-top:#ffffff;--anatomy-lit-shade:#e9edf1;
--anatomy-hi:#1d2127;--anatomy-mid:#5f6670;--anatomy-lo:#8c939c;--anatomy-faint:#b9bfc6;--anatomy-lit:#000000;
--anatomy-halo:#3c444e;--anatomy-halo-opacity:.42;--anatomy-dot:#2a2f36;`;
export const DARK_TOKENS = `--anatomy-page:#0c0e11;--anatomy-card:#0f1216;--anatomy-text:#b6bcc4;--anatomy-strong:#eef1f5;--anatomy-muted:#9aa2ad;
--anatomy-paper:#0f1216;--anatomy-face:#2a3038;--anatomy-top:#4a535e;
--anatomy-shade-0:#1d2228;--anatomy-shade-1:#262c33;--anatomy-shade-2:#30363e;--anatomy-shade-3:#3a414a;
--anatomy-lit-top:#5d6774;--anatomy-lit-shade:#3f4751;
--anatomy-hi:#eef1f5;--anatomy-mid:#9aa2ad;--anatomy-lo:#5d6673;--anatomy-faint:#363d46;--anatomy-lit:#ffffff;
--anatomy-halo:#000000;--anatomy-halo-opacity:.85;--anatomy-dot:#e6e9ee;`;

// subsystem accents from the site's Tol palette, mixed into the faces (restrained)
export const ACCENT_CSS = `.an [data-sys="nav"]{--acc:#4477AA}.an [data-sys="clock"]{--acc:#CCBB44}.an [data-sys="cpu"]{--acc:#AA3377}.an [data-sys="radio"]{--acc:#228833}
.an [data-sys] .iso-top{fill:color-mix(in srgb,var(--acc) 20%,var(--anatomy-top))}
.an [data-sys] .iso-shade[data-shade="0"]{fill:color-mix(in srgb,var(--acc) 16%,var(--anatomy-shade-0))}
.an [data-sys] .iso-shade[data-shade="1"]{fill:color-mix(in srgb,var(--acc) 16%,var(--anatomy-shade-1))}
.an [data-sys] .iso-shade[data-shade="2"]{fill:color-mix(in srgb,var(--acc) 16%,var(--anatomy-shade-2))}
.an [data-sys] .iso-shade[data-shade="3"]{fill:color-mix(in srgb,var(--acc) 16%,var(--anatomy-shade-3))}
.an-leader{fill:none;stroke:var(--anatomy-mid);stroke-width:.7;vector-effect:non-scaling-stroke}
.an-anchor{fill:var(--anatomy-hi);stroke:none}
.an-box{fill:var(--anatomy-card);stroke:var(--anatomy-mid);stroke-width:.7;vector-effect:non-scaling-stroke}
.an-title{font:600 8.6px/1 ui-monospace,Menlo,Consolas,monospace;letter-spacing:.06em;text-transform:uppercase;fill:var(--anatomy-muted)}
.an-value{font:600 9.6px/1 ui-monospace,Menlo,Consolas,monospace;fill:var(--anatomy-strong)}
.an-pins{display:none}
.an-pin circle{fill:var(--anatomy-card);stroke:var(--anatomy-hi);stroke-width:.8;vector-effect:non-scaling-stroke}
.an-pin text{font:700 8px/1 ui-monospace,Menlo,Consolas,monospace;fill:var(--anatomy-strong);text-anchor:middle}
.rd-ray{fill:none;stroke:var(--anatomy-lit);stroke-width:1.1;stroke-linecap:round;vector-effect:non-scaling-stroke}
.rd-bounce{stroke-dasharray:4 3;opacity:.75}
.rd-hit{fill:var(--anatomy-lit)}
[data-lost] .rd-direct{stroke:#d1453b;stroke-dasharray:5 4}
[data-lost] .rd-bounce,[data-lost] .rd-hit{opacity:0}`;

// a standalone light still (the no-JS fallback): the kit's CSS, the light tokens, the accents; the moving groups carry
// their open-state transform as an attribute (a CSS transform would override it)
export function still(svgInner, width, height, label) {
  const css = `${k.ISO_CSS}.iso{${LIGHT_TOKENS}}${ACCENT_CSS}`;
  return `<svg xmlns="http://www.w3.org/2000/svg" class="iso-svg iso an" data-theme="light" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(label)}"><rect width="${width}" height="${height}" fill="#e4e8ec"/><style>${css}</style>${svgInner}</svg>`;
}
