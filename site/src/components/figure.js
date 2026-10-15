// Figure: adds SVG / PNG / CSV downloads to every <figure class="fig" data-figure="name"> on the page.
// Expects an <svg> inside .fig-body and the plotted rows as JSON in <script type="application/json" data-rows>.
// Exports inline the computed colours, so a downloaded SVG/PNG looks like the page (theme included).

const STYLE_PROPS = ['fill', 'stroke', 'stroke-width', 'stroke-dasharray', 'opacity', 'font-family', 'font-size', 'font-weight', 'text-anchor', 'dominant-baseline'];

function standaloneSvg(svg) {
  const clone = svg.cloneNode(true), src = svg.querySelectorAll('*'), dst = clone.querySelectorAll('*');
  src.forEach((el, i) => { const cs = getComputedStyle(el); dst[i].setAttribute('style', STYLE_PROPS.map(p => `${p}:${cs.getPropertyValue(p)}`).join(';')); });
  const bg = getComputedStyle(document.body).backgroundColor, vb = svg.viewBox.baseVal;
  const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  rect.setAttribute('x', vb.x); rect.setAttribute('y', vb.y); rect.setAttribute('width', vb.width); rect.setAttribute('height', vb.height); rect.setAttribute('fill', bg);
  clone.insertBefore(rect, clone.firstChild);
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg'); clone.setAttribute('width', vb.width); clone.setAttribute('height', vb.height);
  return new XMLSerializer().serializeToString(clone);
}

function save(blob, name) {
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

export function toCsv(rows) {
  if (!rows.length) return '';
  const keys = Object.keys(rows[0]), q = v => { const s = v === null || v === undefined ? '' : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  return [keys.join(','), ...rows.map(r => keys.map(k => q(r[k])).join(','))].join('\n') + '\n';
}

export function mountFigures(root = document) {
  for (const fig of root.querySelectorAll('figure.fig[data-figure]')) {
    if (fig.querySelector('.fig-tools')) continue;
    const name = fig.dataset.figure, svg = fig.querySelector('.fig-body svg'), rowsEl = fig.querySelector('script[data-rows]');
    const rows = rowsEl ? JSON.parse(rowsEl.textContent) : [];
    const tools = document.createElement('div'); tools.className = 'fig-tools'; tools.setAttribute('role', 'group'); tools.setAttribute('aria-label', 'Download this figure');
    const add = (label, fn) => { const b = document.createElement('button'); b.type = 'button'; b.className = 'btn'; b.textContent = label; b.addEventListener('click', fn); tools.appendChild(b); };
    if (svg) {
      add('SVG', () => save(new Blob([standaloneSvg(svg)], { type: 'image/svg+xml' }), `${name}.svg`));
      add('PNG', () => {
        const vb = svg.viewBox.baseVal, scale = 2, img = new Image();
        img.onload = () => { const c = document.createElement('canvas'); c.width = vb.width * scale; c.height = vb.height * scale; const ctx = c.getContext('2d'); ctx.scale(scale, scale); ctx.drawImage(img, 0, 0); c.toBlob(b => b && save(b, `${name}.png`), 'image/png'); };
        img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(standaloneSvg(svg));
      });
    }
    if (rows.length) add('CSV', () => save(new Blob([toCsv(rows)], { type: 'text/csv' }), `${name}.csv`));
    fig.appendChild(tools);
  }
}
