// The 2D plan of a scene package (F-36, tier 0: no WebGL2 or a GPU too slow for 3D). The same interface as the 3D scene
// (setPackage, setTime, vehicles, activeLandings, stage.animate), drawn on a 2D canvas over the LOLA hillshade: drive
// routes, sites with their waiting cargo, active keep-out rings, landers on their pads, and rovers coloured by state
// (the same colours as the 3D rings). North is up; the view frames every site.
import { STATE_STYLE } from './states.js';

const BASE = import.meta.env.BASE_URL;
const TILE_M = 16000;   // the hero pack's tile (meta.json size_m); the hillshade covers it at 20 m

export function createPlanScene({ host, canvas: old }) {
  const canvas = document.createElement('canvas');
  canvas.className = old.className; canvas.tabIndex = 0;
  canvas.setAttribute('role', 'img');
  canvas.setAttribute('aria-label', '2D plan of the base: routes, sites (circles) with waiting cargo, landers (triangles) and rovers (squares) coloured by state. The text version below gives the same moment in words.');
  old.replaceWith(canvas);
  const ctx = canvas.getContext('2d'), shade = new Image();
  shade.src = BASE + 'terrain/hero/hillshade_20m.png'; shade.onload = () => draw();
  let pkg = null, t = 0, ch = null, view = { x0: 0, y0: 0, s: 1 }, vehicles = [], active = [];
  const css = getComputedStyle(document.body), ink = css.getPropertyValue('--ink').trim() || '#edf1f7';

  function fit() {
    const r = canvas.getBoundingClientRect(), dpr = Math.min(2, devicePixelRatio || 1);
    canvas.width = Math.round(r.width * dpr); canvas.height = Math.round(r.height * dpr);
    if (!pkg) return;
    const pts = Object.values(pkg.index.sites), xs = pts.map(p => p[0]), ys = pts.map(p => p[1]), pad = 700;
    const x0 = Math.min(...xs) - pad, x1 = Math.max(...xs) + pad, y0 = Math.min(...ys) - pad, y1 = Math.max(...ys) + pad;
    const s = Math.min(canvas.width / (x1 - x0), canvas.height / (y1 - y0));
    view = { s, x0: (x0 + x1) / 2 - canvas.width / s / 2, y1: (y0 + y1) / 2 + canvas.height / s / 2 };
  }
  const P = (x, y) => [(x - view.x0) * view.s, (view.y1 - y) * view.s];

  function draw() {
    if (!pkg || !ch) return;
    const W = canvas.width, H = canvas.height, s = view.s, dpr = Math.min(2, devicePixelRatio || 1), idx = pkg.index;
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
    if (shade.complete && shade.naturalWidth) {   // hillshade: row 0 = north, 16 km square from the tile's south-west corner
      const [ax, ay] = P(0, TILE_M); ctx.globalAlpha = 0.85; ctx.drawImage(shade, ax, ay, TILE_M * s, TILE_M * s); ctx.globalAlpha = 1;
    }
    ctx.lineWidth = 1.5 * dpr; ctx.strokeStyle = 'rgba(111, 205, 233, 0.55)';
    for (const r of pkg.routes) { ctx.beginPath(); for (let i = 0; i < r.n; i++) { const [px, py] = P(r.block[4 * i], r.block[4 * i + 1]); i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); } ctx.stroke(); }
    const hr = pkg.hourly(ch, t);
    ctx.setLineDash([8 * dpr, 6 * dpr]); ctx.strokeStyle = '#CCBB44'; ctx.lineWidth = 2 * dpr;
    for (const [t0, t1, pad, Rkm] of idx.keepout_windows) if (t >= t0 && t <= t1) { const [px, py] = P(...idx.sites[pad]); ctx.beginPath(); ctx.arc(px, py, Rkm * 1000 * s, 0, 2 * Math.PI); ctx.stroke(); }
    ctx.setLineDash([]);
    ctx.font = `${12 * dpr}px "Sora Variable", sans-serif`; ctx.textBaseline = 'middle';
    for (const [name, [x, y]] of Object.entries(idx.sites)) {
      const [px, py] = P(x, y), n = Math.round(hr.waiting[name]?.items || 0);
      ctx.fillStyle = name.startsWith('PAD') ? '#66CCEE' : '#d7dde6'; ctx.beginPath(); ctx.arc(px, py, 5 * dpr, 0, 2 * Math.PI); ctx.fill();
      ctx.fillStyle = ink; ctx.fillText(name.replace('_', ' ') + (n ? `  · ${n} waiting` : ''), px + 9 * dpr, py - 10 * dpr);
    }
    for (const L of idx.landings) if (t >= L.t_h - 0.05) {
      const next = idx.landings.find(q => q.pad === L.pad && q.t_h > L.t_h); if (next && t >= next.t_h - 0.05) continue;
      const [px, py] = P(...idx.sites[L.pad]); ctx.fillStyle = L.ok ? '#fff3c4' : '#EE6677';
      ctx.beginPath(); ctx.moveTo(px, py - 11 * dpr); ctx.lineTo(px - 8 * dpr, py + 6 * dpr); ctx.lineTo(px + 8 * dpr, py + 6 * dpr); ctx.closePath(); ctx.fill();
    }
    if (hr.night > 0.5) { ctx.fillStyle = 'rgba(0, 0, 0, 0.45)'; ctx.fillRect(0, 0, W, H); }   // lunar night: the plan dims
    for (const v of vehicles) {
      if (!v.pos) continue;
      let [px, py] = P(v.pos.x, v.pos.y);
      if (!v.pos.driving) { const a = v.id * 2.39996; px += Math.cos(a) * 13 * dpr; py += Math.sin(a) * 13 * dpr; }   // fan out round a site
      const r = (v.cls === 'HAUL' ? 7 : v.cls === 'MICRO' ? 4.5 : 6) * dpr;
      ctx.fillStyle = (STATE_STYLE[v.state] || STATE_STYLE.idle)[0]; ctx.strokeStyle = '#000'; ctx.lineWidth = 2 * dpr;
      ctx.beginPath(); ctx.rect(px - r, py - r, 2 * r, 2 * r); ctx.fill(); ctx.stroke();   // squares: rovers; circles: sites
    }
    // scale bar
    const bar = 1000 * s, bx = 16 * dpr, by = H - 16 * dpr;
    ctx.strokeStyle = ink; ctx.lineWidth = 2 * dpr; ctx.beginPath(); ctx.moveTo(bx, by); ctx.lineTo(bx + bar, by); ctx.stroke();
    ctx.fillStyle = ink; ctx.fillText('1 km', bx + bar + 6 * dpr, by);
  }

  new ResizeObserver(() => { fit(); draw(); }).observe(canvas);
  let raf = 0; const anims = new Set();
  const loop = now => { raf = 0; const dt = Math.min(0.1, (now - (loop.last || now)) / 1000); loop.last = now; for (const a of anims) if (!a(dt)) anims.delete(a); if (anims.size) raf = requestAnimationFrame(loop); else loop.last = 0; };
  return {
    STATE_STYLE,
    stage: { animate(fn) { anims.add(fn); if (!raf) raf = requestAnimationFrame(loop); }, director: { bindKeys() {}, limits() {}, controls: null } },
    setPackage(p) { pkg = p; vehicles = p.index.vehicles.map(v => ({ ...v })); fit(); },
    setTime(time, chunk) {
      t = time; ch = chunk;
      for (const v of vehicles) { const p = pkg.position(ch, v.id, t, { ease: 2 / 60 }); v.pos = p; v.state = p?.state; v.load = p?.load || 0; }
      active = pkg.index.landings.filter(L => t >= L.t_h - 0.05 && t < L.t_h);
      draw();
    },
    shots() {}, go() { return Promise.resolve(); }, setIcons() {}, setNoLink() {},   // the plan has no route overlay (F-40 red legs are 3D only)
    get vehicles() { return vehicles; }, get activeLandings() { return active; },
  };
}
