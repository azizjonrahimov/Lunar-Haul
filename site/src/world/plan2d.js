// 2D plan view of the same state: the Tier-0 fallback (no WebGL or a weak GPU) and the overview inset.
// Draws the layout's bounding box plus a margin, so it zooms on the base rather than the whole 16 km tile.
import { OWNER_COLOURS, themed } from './colours.js';

export function createPlan(canvas, layout) {
  const ctx = canvas.getContext('2d');
  const xs = layout.names.map(n => layout.pos[n][0]), ys = layout.names.map(n => layout.pos[n][1]);
  const pad = 400, minX = Math.min(...xs) - pad, maxX = Math.max(...xs) + pad, minY = Math.min(...ys) - pad, maxY = Math.max(...ys) + pad;
  let W = 0, H = 0, s = 1, ox = 0, oy = 0;
  const css = k => getComputedStyle(canvas).getPropertyValue(k).trim();
  function resize() {
    const r = canvas.getBoundingClientRect(), dpr = Math.min(2, devicePixelRatio || 1);
    W = Math.max(1, r.width); H = Math.max(1, r.height); canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    s = Math.min(W / (maxX - minX), H / (maxY - minY)); ox = (W - s * (maxX - minX)) / 2; oy = (H - s * (maxY - minY)) / 2;
  }
  const P = (x, y) => [ox + s * (x - minX), H - oy - s * (y - minY)];
  function draw(tr, snap) {
    if (!W) resize();
    const ink = css('--ink') || '#222', ink2 = css('--ink-2') || '#666', bg = css('--bg-2') || '#eee';
    ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
    if (snap.night) { ctx.fillStyle = 'rgba(10,12,30,0.35)'; ctx.fillRect(0, 0, W, H); }
    const cyan = css('--tol-cyan') || '#66CCEE', yellow = css('--tol-yellow') || '#CCBB44';   // theme tokens: 3:1 on the light plan too
    ctx.lineWidth = 2; ctx.strokeStyle = cyan; ctx.globalAlpha = 0.6;
    for (const e of layout.edges) { ctx.beginPath(); e.forEach((p, i) => { const [x, y] = P(p[0], p[1]); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); ctx.stroke(); }
    ctx.globalAlpha = 1;
    for (const pw of snap.plume) { const [x, y] = P(...layout.pos[pw.pad]); ctx.strokeStyle = yellow; ctx.setLineDash([6, 4]); ctx.beginPath(); ctx.arc(x, y, pw.R_m * s, 0, 2 * Math.PI); ctx.stroke(); ctx.setLineDash([]); }
    ctx.font = '600 11px ' + (css('--font-sans') || 'sans-serif');
    for (const n of layout.names) {
      const [x, y] = P(...layout.pos[n]), w = snap.waiting[n], isPad = layout.kinds[n] === 'pad';
      if (w) { ctx.strokeStyle = ink; ctx.lineWidth = 2.5; ctx.beginPath(); ctx.arc(x, y, 9 + Math.min(18, 2 * w.n), 0, 2 * Math.PI); ctx.stroke(); }
      ctx.fillStyle = isPad ? cyan : n === 'BASE' ? ink : ink2; ctx.beginPath(); isPad ? ctx.rect(x - 5, y - 5, 10, 10) : ctx.arc(x, y, 4.5, 0, 2 * Math.PI); ctx.fill();
      ctx.fillStyle = ink; ctx.fillText(n.replace('_', ' ') + (w ? ` · ${w.n}` : ''), x + 8, y - 6);
    }
    for (const L of snap.landers) { const xy = L.landing.xy || layout.pos[L.landing.pad], [x, y] = P(...xy); ctx.strokeStyle = ink; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(x, y, 7, 0, 2 * Math.PI); ctx.stroke(); }
    snap.vehicles.forEach(v => {
      const [lx, ly] = layout.along(v.from, v.to, v.f), [x, y] = P(lx, ly), veh = tr.vehicles.find(q => q.id === v.id), off = ((v.id % 3) - 1) * 4;
      ctx.fillStyle = themed(OWNER_COLOURS[veh.owner] || '#AA3377', css); ctx.strokeStyle = ink; ctx.lineWidth = v.status === 'stranded-night' ? 2.5 : 1;
      ctx.beginPath(); ctx.arc(x + off, y + off, veh.cls === 'HAUL' ? 6 : veh.cls === 'MICRO' ? 3.5 : 4.8, 0, 2 * Math.PI); ctx.fill(); ctx.stroke();
    });
    if (snap.night) { ctx.fillStyle = ink; ctx.font = '600 12px ' + (css('--font-sans') || 'sans-serif'); ctx.fillText('Lunar night', 12, 20); }
    const km = 1000 * s, [bx, by] = [W - 12 - km, H - 14]; ctx.strokeStyle = ink; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(bx, by); ctx.lineTo(bx + km, by); ctx.stroke(); ctx.fillStyle = ink; ctx.fillText('1 km', bx, by - 5);
  }
  return { resize, draw };
}
