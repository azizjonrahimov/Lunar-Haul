// /lab/rover (F-8): drive a leg of the base on LOLA terrain with the JS port of lunar/Drive-v0 (parity-checked
// against Python): the scripted expert now, you at the keyboard with Earth-Moon latency, and B-13's learned driver
// later through the same controller interface {name, act(obs, env)}.
// F-35: the same drive in 3D above the plan (lab3d.js), and a race: the expert and the network on the same leg and soil.
import './lab.css';
import * as R from './physics.js';
import { RoverTerrain } from './terrain.js';
import { plan } from './expert.js';
import { DriveEnv, expertController, PATCH, ENV_ID, ENV_VERSION } from './env.js';
import { legProfile, driveProfile, SPEED_SIGMA } from './tables.js';
import { num, esc, fmt } from '../components/num.js';

const $ = id => document.getElementById(id);
const BASE = import.meta.env.BASE_URL, TERR = BASE + 'terrain/hero/', LAB = BASE + 'lab/rover/';
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const st = { t: null, sites: null, index: null, hill: null, route: null, routeKey: '', env: null, ctl: null, obs: null, running: false, raf: 0, last: 0, acc: 0, trail: [], events: [], keys: {}, rec: null, sent: [0, 0], legTable: null, prof: null };
const status = m => { $('r-status').textContent = m; };
async function getJson(u) { const r = await fetch(u); if (!r.ok) throw new Error(`${u}: HTTP ${r.status}`); return r.json(); }

// ---------- boot ----------
async function boot() {
  try {
    status('Loading the terrain (5 m heights, 2.9 MB)…');
    st.t = await RoverTerrain.load(TERR, m => status('Loading ' + m));
    st.sites = await getJson(TERR + 'sites.json');
    for (const az of [0, 90, 180, 270]) { try { const r = await fetch(`${LAB}shadow_${az}.bin`); if (r.ok) st.t.setShadowBits(az, new Uint8Array(await r.arrayBuffer())); } catch (e) { /* computed on demand */ } }
    st.index = await getJson(LAB + 'driving-index.json').catch(() => null);
    st.lindex = await getJson(LAB + 'learned-index.json').catch(() => null);   // the learned driver's table (driving-v1-learned.json), when built

  } catch (e) { status(`The rover lab needs the terrain pack's 5 m layer (${e.message}).`); return; }
  $('r-tele-title').insertAdjacentHTML('beforeend', ` <span class="small muted">${ENV_ID}, env v${ENV_VERSION}</span>`);
  fillSelectors(); wire(); renderConstants();
  // the 3D view's page side loads after the lab is ready (its door, HUD and controls; the scene itself waits for Enter)
  import('./lab3d.js').then(m => { v3 = m.mount3d({ st, points, tableKey, level, lighting, status, drive: () => drive(), human: () => $('r-ctrl').value === 'human',
    // run the drive on (the same drive, at once) while pred() holds: the 3D view opens where the leg is sunlit
    skip: (pred, max = 4000) => { let n = 0; if (st.ctl.actAsync || st.env2) return 0; while (!st.done && n < max && pred()) { if (!stepOnce()) break; n++; } drawAll(true); return n; },
    driverName: () => ({ expert: 'The scripted expert', human: 'You', learned: 'The neural network', race: 'The expert' })[$('r-ctrl').value],
    lightingText: () => $('r-light').selectedOptions[0].textContent, levelText: () => $('r-level').selectedOptions[0].textContent.toLowerCase() }); }).catch(e => { $('r3-controls').hidden = true; status(`The 3D view could not load (${e.message}); the plan view below shows the drive.`); });
  await prepare();
}

// ---------- leg selection ----------
function points() {
  const D = $('r-standoff').value, pts = {};
  for (const s of st.sites.sites) pts[s.id] = s.xy_m;
  for (const [pad, xy] of Object.entries(st.sites.pads[D] || {})) pts[pad] = xy;
  return pts;
}
function fillSelectors() {
  $('r-standoff').innerHTML = Object.keys(st.sites.pads).map(k => `<option value="${k}" ${k === '1' ? 'selected' : ''}>${k} km</option>`).join('');
  const names = Object.keys(points()), opt = sel => names.map(n => `<option value="${n}" ${n === sel ? 'selected' : ''}>${n.replace('_', ' ')}</option>`).join('');
  $('r-from').innerHTML = opt('BASE'); $('r-to').innerHTML = opt('PSR');
}
function tableKey(a, b) { const D = $('r-standoff').value, k = n => n.startsWith('PAD_') ? `${n}@${D}` : n; return `${k(a)}->${k(b)}`; }
function level() { const v = $('r-level').value; return v.startsWith('teleop') ? { autonomy: 'teleop', rtt: +v.split(':')[1] } : { autonomy: v, rtt: 0 }; }
function lighting() { const v = $('r-light').value; return v === 'night' ? R.NIGHT : +v; }
function soil() { const v = $('r-soil').value; return v === 'sampled' ? null : +v; }   // null: the env draws phi per drive

/* plan the route for the current leg + lighting (A* on the 20 m cost grid); cached per key */
async function prepare() {
  stop(); const a = $('r-from').value, b = $('r-to').value, sun = lighting();
  if (a === b) { status('Pick two different sites.'); return; }
  const key = `${a}|${b}|${$('r-standoff').value}|${sun}`;
  if (key !== st.routeKey) {
    status('Planning the route (A* over the 20 m slope and lighting grid)…'); await new Promise(r => setTimeout(r, 30));
    const pts = points(), t0 = performance.now(); st.route = plan(st.t, pts[a], pts[b], sun); st.routeKey = key;
    if (!st.route) { status(`No drivable route from ${a} to ${b} with this lighting (every path crosses ground steeper than ${R.ROVER.slope_hard_deg}°).`); return; }
    st.prof = legProfile(st.t, st.route, sun); st.planMs = performance.now() - t0;
    const file = st.index && st.index.legs[tableKey(a, b)]; st.legTable = file ? await getJson(LAB + 'legs/' + file).catch(() => null) : null;
    const lfile = st.lindex && st.lindex.legs[tableKey(a, b)]; st.learnedTable = lfile ? await getJson(LAB + 'learned/' + lfile).catch(() => null) : null;
  }
  reset(); renderComparison(); status(`Route ${a} → ${b}: ${fmt(st.prof.length_m / 1000, 2)} km over ${st.route.length} cells, planned in ${fmt(st.planMs, 0)} ms. Press Drive.`);
}

// ---------- controllers (B-13 hook: anything with {name, act(obs, env)}) ----------
function human() { return { name: 'You (keyboard, commands delayed by the round trip)', act: () => { const k = st.keys; const steer = (k.ArrowLeft ? -1 : 0) + (k.ArrowRight ? 1 : 0); if (k.ArrowUp) st.thr = 1; else if (k.ArrowDown) st.thr = 0; return [steer, st.thr ?? 0.5]; } }; }
// The learned driver (B-13 export): fetched and checked only when chosen; its act is async (onnxruntime-web)
const POL = BASE + 'lab/policies/';
let learnedPromise = null;
function loadLearned() {
  learnedPromise ||= (async () => {
    const t0 = performance.now();
    const [card, chk, bytes] = await Promise.all([getJson(POL + 'rover_bc_s0.json'), getJson(POL + 'rover_bc_s0.check.json').catch(() => null),
      fetch(POL + 'rover_bc_s0.onnx').then(r => { if (!r.ok) throw new Error(`rover_bc_s0.onnx: HTTP ${r.status}`); return r.arrayBuffer(); })]);
    const { OnnxDriver } = await import('./driver.js');
    const drv = await OnnxDriver.load(card, bytes);
    drv.loadMs = performance.now() - t0; drv.check = chk ? await drv.check(chk) : null;
    renderLearned(drv); return drv;
  })().catch(e => { learnedPromise = null; throw e; });
  return learnedPromise;
}
function renderLearned(drv) {
  const t = drv.card.training || {}, c = drv.check, cap = t.dagger_steps_cap;
  $('r-learned').innerHTML = `<p>A convolutional network that imitates the scripted expert from the grid and the five numbers above: trained on ${t.legs ?? '?'} legs, then refined with ${t.dagger_rounds ?? '?'} DAgger round${t.dagger_rounds === 1 ? '' : 's'}${cap ? ` capped at ${Number(cap).toLocaleString('en-GB')} samples each` : ''}, exported to ONNX and run here by onnxruntime-web. The logistics experiments in the paper use the expert's driving tables, not this driver: it is a demonstration of the method and still needs far more help on the road than the expert.</p>
<p class="small ${c && c.ok ? 'pass' : 'fail'}">Browser runtime check: ${c ? `${c.n} stored inputs against the Python onnxruntime outputs: max |Δaction| ${c.maxErr.toExponential(1)} (tolerance ${c.tolerance}) — ${c.ok ? 'matches Python' : 'DOES NOT MATCH'}` : 'no check file'}. Network sha256 checked against its card. Loaded in ${fmt(drv.loadMs / 1000, 1)} s.</p>`;
}
function reset() {
  const lv = level(); st.env = new DriveEnv(st.t);
  st.obs = st.env.reset({ waypoints: st.route, autonomy: lv.autonomy, rttS: lv.rtt, sunAz: lighting(), phi: soil() });
  const c = $('r-ctrl').value;
  st.ctl = c === 'human' ? human() : c === 'learned' && st.learned ? st.learned : expertController(st.env.route); st.thr = 0.5;   // race: the expert drives env, the network env2
  st.trail = [[st.env.state.x, st.env.state.y]]; st.events = []; st.done = null; st.rec = null; st.sent = [0, 0]; st.acc = 0; st.gen = (st.gen || 0) + 1;
  // race: the network drives a second env on the same route, level, lighting and soil
  st.env2 = null; st.done2 = null; st.events2 = []; st.trail2 = [];
  if (c === 'race' && st.learned) {
    st.env2 = new DriveEnv(st.t); st.obs2 = st.env2.reset({ waypoints: st.route, autonomy: lv.autonomy, rttS: lv.rtt, sunAz: lighting(), phi: st.env.phi });
    st.ctl2 = st.learned; st.trail2 = [[st.env2.state.x, st.env2.state.y]];
  }
  v3?.leg();
  drawAll(true);
}
function applyStep(a) {
  st.sent = a;
  const r = st.env.step(a); st.obs = r.obs; st.rec = r.rec;
  if (r.rec.intervention) st.events.push({ x: st.env.state.x, y: st.env.state.y, why: r.rec.intervention, t: st.env.timeS });
  if (st.env.steps % 5 === 0) st.trail.push([st.env.state.x, st.env.state.y]);
  if (r.terminated || r.truncated) { st.done = r.leg; return false; }
  return true;
}
function applyStep2(a) {
  const r = st.env2.step(a); st.obs2 = r.obs;
  if (r.rec.intervention) st.events2.push({ x: st.env2.state.x, y: st.env2.state.y, why: r.rec.intervention, t: st.env2.timeS });
  if (st.env2.steps % 5 === 0) st.trail2.push([st.env2.state.x, st.env2.state.y]);
  if (r.terminated || r.truncated) { st.done2 = r.leg; return false; }
  return true;
}
function stepOnce() { return applyStep(st.ctl.act(st.obs, st.env)); }
/* one step for any controller; undefined if the episode was reset while the network was running */
async function stepAsync() {
  const gen = st.gen; let going = false;
  if (!st.done) { const a = st.ctl.actAsync ? await st.ctl.actAsync(st.obs, st.env) : st.ctl.act(st.obs, st.env); if (gen !== st.gen) return undefined; going = applyStep(a); }
  if (st.env2 && !st.done2) { const a = await st.ctl2.actAsync(st.obs2, st.env2); if (gen !== st.gen) return undefined; going = applyStep2(a) || going; }   // a race runs until both arrive
  return going;
}
async function drive() {
  if (!st.route || st.busy) return; if (st.done || !st.env || st.env.steps === 0) reset();
  const rate = +$('r-speed').value;
  if (rate === 0 || reduced.matches && $('r-ctrl').value !== 'human') {
    const t0 = performance.now(), gen = st.gen; st.busy = true; $('r-drive').disabled = true;
    try { while (gen === st.gen && await stepAsync()) { if (performance.now() - t0 > (st.ctl.actAsync || st.env2 ? 20000 : 4000)) break; } } finally { st.busy = false; $('r-drive').disabled = false; }
    drawAll(true); finish(); return;
  }
  st.running = true; $('r-drive').textContent = 'Pause'; $('r-drive').setAttribute('aria-pressed', 'true'); st.last = 0; if (!st.raf) st.raf = requestAnimationFrame(tick);
}
function stop() { st.running = false; $('r-drive').textContent = 'Drive'; $('r-drive').setAttribute('aria-pressed', 'false'); }
async function tick(now) {
  st.raf = 0; if (!st.running) return;
  const dt = st.last ? Math.min(0.1, (now - st.last) / 1000) : 0; st.last = now; st.acc += dt * +$('r-speed').value;
  let going = true;
  if (st.ctl.actAsync || st.env2) { const gen = st.gen; while (st.acc >= R_DT && going && gen === st.gen) { st.acc -= R_DT; going = (await stepAsync()) !== false; } }
  else while (st.acc >= R_DT && going) { st.acc -= R_DT; going = stepOnce(); }
  if (!st.running) return;
  drawAll(false); if (!going) { stop(); finish(); return; }
  st.raf = requestAnimationFrame(tick);
}
const R_DT = 1.0;
function finish() { renderComparison(); const L = st.done, L2 = st.done2; if (L) status(`${L.reached ? 'Arrived' : 'Stopped (step cap)'}: ${fmt(L.distance_m / 1000, 2)} km in ${hms(L.time_s)}, ${fmt(L.energy_wh, 0)} Wh, ${L.interventions} intervention(s), ${L.stops} stop(s).${L2 ? ` Network: ${L2.reached ? 'arrived' : 'stopped'} in ${hms(L2.time_s)}, ${L2.interventions} intervention(s).` : ''}`); v3?.update(true); }
const hms = s => { const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), ss = Math.floor(s % 60); return `${h}:${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`; };

// ---------- drawing ----------
let lastDom = 0, v3 = null;
function drawAll(force) { planView(); profileView(); v3?.update(force); const now = performance.now(); if (force || now - lastDom > 120) { telemetry(); patchView(); controls(); lastDom = now; } }
function viewBox() {
  const xs = st.route.map(p => p[0]), ys = st.route.map(p => p[1]), m = 300;
  return [Math.min(...xs) - m, Math.max(...xs) + m, Math.min(...ys) - m, Math.max(...ys) + m];
}
function fitCanvas(cv) { const r = cv.getBoundingClientRect(), dpr = Math.min(2, devicePixelRatio || 1); if (cv.width !== Math.round(r.width * dpr)) { cv.width = Math.round(r.width * dpr); cv.height = Math.round(r.height * dpr); } const ctx = cv.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); return [ctx, r.width, r.height]; }
function planView() {
  if (!st.route) return; const [ctx, W, H] = fitCanvas($('r-plan')), [x0, x1, y0, y1] = viewBox(), s = Math.min(W / (x1 - x0), H / (y1 - y0));
  const ox = (W - s * (x1 - x0)) / 2, oy = (H - s * (y1 - y0)) / 2, P = (x, y) => [ox + (x - x0) * s, H - oy - (y - y0) * s];
  ctx.fillStyle = '#060608'; ctx.fillRect(0, 0, W, H);
  { const img = relief(lighting()), px = st.t.px20, rows = st.t.r20, sx = x0 / px, sw = (x1 - x0) / px, sy = rows - y1 / px, sh = (y1 - y0) / px, [dx, dy] = P(x0, y1);
    ctx.imageSmoothingEnabled = true; ctx.drawImage(img, sx, sy, sw, sh, dx, dy, sw * px * s, sh * px * s); }
  ctx.strokeStyle = 'rgba(102,204,238,.9)'; ctx.lineWidth = 4; ctx.beginPath(); st.route.forEach((p, i) => { const [a, b] = P(p[0], p[1]); i ? ctx.lineTo(a, b) : ctx.moveTo(a, b); }); ctx.stroke();
  ctx.strokeStyle = '#CCBB44'; ctx.lineWidth = 2; ctx.beginPath(); st.trail.concat(st.env ? [[st.env.state.x, st.env.state.y]] : []).forEach((p, i) => { const [a, b] = P(p[0], p[1]); i ? ctx.lineTo(a, b) : ctx.moveTo(a, b); }); ctx.stroke();
  if (st.env2) {   // race: the network's path (orange), its interventions (circles) and the rover
    ctx.strokeStyle = '#EE7733'; ctx.lineWidth = 2; ctx.beginPath(); st.trail2.concat([[st.env2.state.x, st.env2.state.y]]).forEach((p, i) => { const [a, b] = P(p[0], p[1]); i ? ctx.lineTo(a, b) : ctx.moveTo(a, b); }); ctx.stroke();
    for (const e of st.events2) { const [a, b] = P(e.x, e.y); ctx.beginPath(); ctx.arc(a, b, 5, 0, 7); ctx.stroke(); }
    const s2 = st.env2.state, [a, b] = P(s2.x, s2.y); ctx.save(); ctx.translate(a, b); ctx.rotate(s2.psi); ctx.fillStyle = '#EE7733'; ctx.beginPath(); ctx.moveTo(0, -9); ctx.lineTo(6, 7); ctx.lineTo(-6, 7); ctx.closePath(); ctx.fill(); ctx.restore();
  }
  for (const e of st.events) { const [a, b] = P(e.x, e.y); ctx.strokeStyle = '#EE6677'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(a - 5, b - 5); ctx.lineTo(a + 5, b + 5); ctx.moveTo(a + 5, b - 5); ctx.lineTo(a - 5, b + 5); ctx.stroke(); }
  const pts = points(); ctx.font = '600 11px ' + getComputedStyle(document.body).fontFamily; ctx.fillStyle = '#fff';
  for (const n of [$('r-from').value, $('r-to').value]) { const [a, b] = P(...pts[n]); ctx.beginPath(); ctx.arc(a, b, 4, 0, 7); ctx.fill(); ctx.fillText(n.replace('_', ' '), a + 7, b - 6); }
  if (st.env) {
    const s0 = st.env.state, [a, b] = P(s0.x, s0.y), tgt = st.ctl && st.ctl.pp && st.ctl.pp.target;
    if (tgt) { const [ta, tb] = P(tgt[0], tgt[1]); ctx.strokeStyle = '#fff'; ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo(a, b); ctx.lineTo(ta, tb); ctx.stroke(); ctx.setLineDash([]); }
    ctx.save(); ctx.translate(a, b); ctx.rotate(s0.psi); ctx.fillStyle = '#EE6677'; ctx.beginPath(); ctx.moveTo(0, -9); ctx.lineTo(6, 7); ctx.lineTo(-6, 7); ctx.closePath(); ctx.fill(); ctx.restore();
  }
  ctx.fillStyle = 'rgba(255,255,255,.8)'; ctx.fillText('500 m', 14, H - 18); ctx.fillRect(14, H - 12, 500 * s, 3);
}
/* shaded relief of the 20 m grid for the chosen sun (incidence at 1.5° elevation, boosted for display) with the
   exact cast-shadow grid the model uses; at night a dim neutral relief. One canvas per lighting, cached. */
const reliefCache = new Map();
function relief(sun) {
  const key = String(sun); if (reliefCache.has(key)) return reliefCache.get(key);
  const t = st.t, rows = t.r20, cols = t.c20, px = t.px20, z = t.z20, cv = document.createElement('canvas'); cv.width = cols; cv.height = rows;
  const ctx = cv.getContext('2d'), im = ctx.createImageData(cols, rows), night = sun === R.NIGHT, az = (night ? 315 : sun) * Math.PI / 180, el = (night ? 45 : 1.5) * Math.PI / 180;
  const sx = Math.sin(az) * Math.cos(el), sy = Math.cos(az) * Math.cos(el), sz = Math.sin(el), sh = night ? null : t.shadowGrid(sun);
  for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) {
    const Z = (jj, ii) => z[Math.min(rows - 1, Math.max(0, jj)) * cols + Math.min(cols - 1, Math.max(0, ii))];
    const dzdx = (Z(j, i + 1) - Z(j, i - 1)) / (2 * px), dzdy = (Z(j + 1, i) - Z(j - 1, i)) / (2 * px), L = Math.hypot(dzdx, dzdy, 1);
    const ns = (-dzdx * sx - dzdy * sy + sz) / L; let v;
    if (night) v = 18 + 50 * Math.max(0, ns);
    else v = sh[j * cols + i] ? 14 : 45 + 190 * Math.min(1, Math.max(0, ns) * 3);
    const k = 4 * ((rows - 1 - j) * cols + i); im.data[k] = v; im.data[k + 1] = v; im.data[k + 2] = v * (night ? 1.15 : 1); im.data[k + 3] = 255;
  }
  ctx.putImageData(im, 0, 0); reliefCache.set(key, cv); return cv;
}
function profileView() {
  if (!st.prof) return; const [ctx, W, H] = fitCanvas($('r-prof')), z = st.prof.z, n = z.length, zmin = Math.min(...z), zmax = Math.max(...z, zmin + 10);
  const X = i => 40 + (W - 50) * i / (n - 1), Y = v => H - 20 - (H - 34) * (v - zmin) / (zmax - zmin);
  ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--bg-2'); ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = 'rgba(120,120,120,.45)'; ctx.beginPath(); ctx.moveTo(X(0), H - 20); z.forEach((v, i) => ctx.lineTo(X(i), Y(v))); ctx.lineTo(X(n - 1), H - 20); ctx.fill();
  const ink = getComputedStyle(document.body).color; ctx.fillStyle = ink; ctx.font = '11px ' + getComputedStyle(document.body).fontFamily;
  ctx.fillText(`${Math.round(zmax)} m`, 2, 12); ctx.fillText(`${Math.round(zmin)} m`, 2, H - 22); ctx.fillText(`${fmt(st.prof.length_m / 1000, 2)} km`, W - 50, H - 4);
  if (st.env) { const k = st.env.pp.k, frac = st.env.pp.s[k] / st.env.pp.s[st.env.pp.s.length - 1], i = frac * (n - 1); ctx.fillStyle = '#EE6677'; ctx.beginPath(); ctx.arc(X(i), Y(z[Math.round(i)]), 5, 0, 7); ctx.fill(); }
}
function telemetry() {
  const e = st.env; if (!e) return; const r = st.rec || { grade: 0, slip: 0, gv: 0 }, lv = level(), cost = R.interventionCostS(lv.rtt);
  const smg = e.timeS > 0 ? e.distM / e.timeS * 3.6 : 0, auto = e.timeS > 0 ? Math.max(0, 1 - e.interventions * cost / e.timeS) : 1, src = `this drive (JS port of ${ENV_ID}, env v${ENV_VERSION})`, M = (v, u, d) => num({ value: v, unit: u, flag: 'Modelled', digits: d, source: src });
  const rows = [['Elapsed', `<span class="mono">${hms(e.timeS)}</span> <span class="muted small">incl. stops and interventions</span>`], ['Distance', M(e.distM / 1000, 'km', 2)],
    ['Speed made good', M(smg, 'km/h', 2)], ['Ground speed now', M(r.gv * 3.6, 'km/h', 2)], ['Grade ahead', M(r.grade, '°', 1)], ['Slip', M(100 * r.slip, '%', 0)], ['Soil friction angle', num({ value: e.phi, unit: '°', flag: R.FLAGS.phi[0], digits: 1, source: R.FLAGS.phi[1] + ($('r-soil').value === 'sampled' ? '; drawn for this drive' : '; chosen above') })],
    ['Energy used', M(e.energyWh, 'Wh', 0)], ['Stops to confirm', M(e.stops, '', 0)], ['Interventions', M(e.interventions, '', 0)],
    ['Autonomy', `${M(100 * auto, '%', 1)} <span class="muted small">1 − interventions × (RTT + ${R.INTERVENTION.recovery_s} s) / elapsed</span>`]];
  if (st.env2) { const e2 = st.env2; rows.push(['Network (race)', `${M(e2.distM / 1000, 'km', 2)} in <span class="mono">${hms(e2.timeS)}</span>, ${e2.interventions} intervention(s)${st.done2 ? (st.done2.reached ? ', arrived' : ', stopped') : ''}`]); }
  $('r-tele').innerHTML = rows.map(([a, b]) => `<tr><th scope="row">${a}</th><td>${b}</td></tr>`).join('');
  $('r-events').textContent = st.events.length ? st.events.slice(-3).map(v => `${hms(v.t)} ${v.why}`).join(' · ') : (r.stopped ? 'Stopped to confirm the next segment.' : '—');
}
function patchView() {
  const e = st.env; if (!e || !st.obs) return; const ch = +$('r-ch').value, [ctx, W, H] = fitCanvas($('r-patch')), cell = Math.min(W, H) / PATCH, n = PATCH * PATCH, p = st.obs.patch;
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H); ctx.font = `${Math.max(6, cell * 0.42)}px ${getComputedStyle(document.body).getPropertyValue('--font-mono')}`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  for (let a = 0; a < PATCH; a++) for (let b = 0; b < PATCH; b++) {
    const v = p[ch * n + a * PATCH + b], y = (PATCH - 1 - a) * cell, x = b * cell;   // forward = up
    const c = ch === 0 ? (v >= 0 ? `rgba(238,102,119,${Math.min(1, v * 2)})` : `rgba(68,119,170,${Math.min(1, -v * 2)})`) : `rgba(204,187,68,${Math.min(1, v)})`;
    ctx.fillStyle = c; ctx.fillRect(x, y, cell - 0.5, cell - 0.5);
    if (cell >= 11) { ctx.fillStyle = 'rgba(255,255,255,.85)'; ctx.fillText(Math.abs(v) < 0.05 ? '0' : v.toFixed(1).replace('0.', '.'), x + cell / 2, y + cell / 2); }
  }
  const ry = (PATCH - 1 - 8) * cell, rx = (PATCH / 2) * cell; ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.strokeRect(rx - cell, ry, cell * 2 - 0.5, cell);
  const sc = st.obs.scalars; $('r-scalars').textContent = ['speed/cap', 'heading err/π', 'dist/100 m', 'sun rel/180°', 'shadow'].map((nm, i) => `${nm} ${sc[i].toFixed(2)}`).join(' · ');
}
function controls() {
  const sent = st.sent || [0, 0], applied = st.rec ? st.rec.action : [0, 0];
  $('r-wheel').style.transform = `rotate(${90 * sent[0]}deg)`; $('r-wheel-applied').style.transform = `rotate(${90 * applied[0]}deg)`;
  $('r-thr').style.strokeDashoffset = String(100 - 100 * Math.max(0, Math.min(1, sent[1]))); $('r-thr-applied').style.strokeDashoffset = String(100 - 100 * Math.max(0, Math.min(1, applied[1])));
  $('r-ctl-text').textContent = `sent: steer ${sent[0].toFixed(2)}, throttle ${sent[1].toFixed(2)} · applied: steer ${applied[0].toFixed(2)}, throttle ${applied[1].toFixed(2)}${level().autonomy === 'teleop' ? ` (${level().rtt} s later)` : ''}`;
}

// ---------- comparison with the driving table ----------
function renderComparison() {
  if (!st.prof) return; const lv = level(), sunKey = $('r-light').value, phi = st.env ? st.env.phi : R.PHI_REF, d = driveProfile(st.prof, lv.autonomy, lv.rtt, lighting(), phi);
  const cell = tab => tab && tab.autonomy[lv.autonomy] && tab.autonomy[lv.autonomy].rtt_s[String(lv.rtt)] && tab.autonomy[lv.autonomy].rtt_s[String(lv.rtt)].lighting[sunKey];
  const T = cell(st.legTable);
  // the learned driver's table replaces the Assumed hazard and the driving time only at the autonomous and supervised
  // levels (teleop keeps the human model), so its column is shown there
  const usesDriver = st.learnedTable && st.lindex && st.lindex.model && st.lindex.model.driver && (st.lindex.model.driver.levels || []).includes(lv.autonomy);
  const TL = usesDriver ? cell(st.learnedTable) : null, DM = usesDriver && st.learnedTable.driver_measured ? st.learnedTable.driver_measured[sunKey] : null;
  const live = st.done, cost = R.interventionCostS(lv.rtt), M = (v, u, dd, s) => num({ value: v, unit: u, flag: 'Modelled', digits: dd, source: s });
  const legKey = tableKey($('r-from').value, $('r-to').value), lvl = `${lv.autonomy}${lv.autonomy === 'teleop' ? ' ' + lv.rtt + ' s' : ''}`;
  const tsrc = `data/driving/driving-v1.json, leg ${legKey}, ${lvl}, lighting ${sunKey}, ${st.index ? st.index.seeds : '?'} runs`;
  const lsrc = `data/driving/driving-v1-learned.json, leg ${legKey}, ${lvl}, lighting ${sunKey}, ${st.lindex ? st.lindex.seeds : '?'} runs; interventions and driving time measured with the learned driver`;
  const lcol = !!TL;
  const row = (lab, tab, ltab, integ, liv) => `<tr><th scope="row">${lab}</th><td class="n">${tab}</td>${lcol ? `<td class="n">${ltab}</td>` : ''}<td class="n">${integ}</td><td class="n">${liv}</td></tr>`;
  $('r-compare').innerHTML = `<div class="r-scroll"><table class="w-table"><tr><th></th><th class="n">Driving table, expert (mean · p90)</th>${lcol ? '<th class="n">Driving table, learned driver (mean · p90)</th>' : ''}<th class="n">Leg integrator, this route</th><th class="n">Live drive</th></tr>` +
    row('Time, excl. interventions', T ? `${M(T.time_h.mean, 'h', 2, tsrc)} · ${fmt(T.time_h.p90, 2)} h` : '<span class="muted">not in the table</span>', TL ? `${M(TL.time_h.mean, 'h', 2, lsrc)} · ${fmt(TL.time_h.p90, 2)} h` : '–', M(d.time_s_nominal / 3600, 'h', 2, `tables.drive_profile port, u_leg = 1, phi ${fmt(phi, 1)}°`), live ? M((live.time_s - live.interventions * cost) / 3600, 'h', 2, 'this drive') : '–') +
    row('Energy (traction)', T ? M(T.energy_kwh.mean, 'kWh', 3, tsrc) : '–', TL ? M(TL.energy_kwh.mean, 'kWh', 3, lsrc) : '–', M(d.energy_wh / 1000, 'kWh', 3, 'tables.drive_profile port'), live ? M(live.energy_wh / 1000, 'kWh', 3, 'this drive') : '–') +
    row('Interventions', T ? `λ = ${fmt(T.interventions.lambda, 2)}` : '–', TL ? `λ = ${fmt(TL.interventions.lambda, 2)}` : '–', `λ = ${fmt(d.lambda, 2)}${d.dig_in_stretches ? ` <span class="muted">(${d.dig_in_stretches} dig-in)</span>` : ''}`, live ? String(live.interventions) : '–') +
    row('Stops to confirm', T ? String(T.stops) : '–', TL ? String(TL.stops) : '–', String(d.stops), live ? String(live.stops) : '–') + `</table></div>` +
    (DM ? `<p class="small">Learned driver on this leg and lighting, measured once in the step-by-step model (autonomous, 4 s round trip): ${M(DM.interventions_per_km, 'interventions per km', 2, lsrc)}, driving time ${M(DM.time_ratio, "× the integrator’s time", 2, lsrc)}${DM.reached ? '' : ' (did not reach the goal, so the table keeps the expert model for this case)'}. The paper's experiments use the expert's table.</p>` : '') +
    `<p class="small muted">The table and the integrator use the same physics along the 5 m-densified route. The integrator column uses this drive's soil (friction angle ${fmt(phi, 1)}°); the table draws the friction angle per run across 37.8–47.8° and adds run-to-run speed scatter (lognormal, σ = ${SPEED_SIGMA}) and draws interventions from an Assumed hazard (Poisson λ)${lcol ? ', which the learned-driver table replaces by the measured rate' : ''}. The live drive integrates the chosen driver's actual path second by second (heading changes, acceleration, the teleop command queue) and triggers interventions only from the env's rules, so its numbers differ by design; for the expert the energy usually agrees within a few per cent.</p>`;
}

function renderConstants() {
  const F = R.FLAGS, flag = k => F[k][0], src = k => F[k][1] || 'Assumed';
  const rows = [['Rover mass', R.ROVER.mass_kg, 'kg', 0, 'mass_kg'], ['Wheelbase', R.ROVER.wheelbase_m, 'm', 1, 'wheelbase_m'], ['Nominal slope limit', R.ROVER.slope_nominal_deg, '°', 0, 'slope_nominal_deg'], ['Hard slope limit', R.ROVER.slope_hard_deg, '°', 0, 'slope_hard_deg'],
    ['Autonomous speed', R.SPEED_CAP_KMH.autonomous, 'km/h', 1, 'autonomous_kmh'], ['Supervised speed', R.SPEED_CAP_KMH.supervised, 'km/h', 1, 'supervised_kmh'],
    ['Teleop speed made good, 0 / 4 / 6 / 8 s', null, '', 0, 'teleop_smg'], ['Camera pan per stop', R.TELEOP_T_LOOK_S, 's', 0, 't_look_s'], ['Effective rolling coefficient', R.C_RR_EFF, '', 3, 'energy'], ['Dig-in slip', 100 * R.DIG_IN_SLIP, '%', 0, 'dig_in'], ['Shadow speed factor', R.SHADOW_SPEED_FACTOR, '×', 2, 'lighting'], ['Intervention recovery', R.INTERVENTION.recovery_s, 's + RTT', 0, 'intervention']];
  $('r-consts').innerHTML = rows.map(([lab, v, u, d, k]) => `<tr><th scope="row">${lab}</th><td>${v === null ? Object.values(R.LITAKER_SMG_KMH).map(x => num({ value: x, unit: '', flag: flag(k), digits: 2, source: src(k) })).join(' / ') + ' km/h' : num({ value: v, unit: u, flag: flag(k), digits: d, source: src(k) })}</td></tr>`).join('') +
    R.SLIP_PHI_DEG.map((phi, c) => `<tr><th scope="row">Slip vs uphill grade, friction angle ${phi}°</th><td class="small">${R.SLIP_TABLE_DEG.map((g, i) => `${g}° → ${Math.round(100 * R.SLIP_CURVES[c][i])} %`).join(', ')} <span class="flag" data-flag="Modelled" title="${esc(src('slip_table'))}">Modelled</span></td></tr>`).join('') +
    `<tr><th scope="row">Soil friction angle</th><td class="small">37.8–47.8°, linear between the curves; downhill and flat use the flat value <span class="flag" data-flag="Assumed" title="${esc(src('phi'))}">Assumed</span></td></tr>`;
}

function wire() {
  for (const id of ['r-from', 'r-to', 'r-standoff', 'r-light']) $(id).addEventListener('change', () => { if (id === 'r-standoff') { const f = $('r-from').value, t = $('r-to').value; fillSelectors(); $('r-from').value = f; $('r-to').value = t; } prepare(); });
  $('r-soil-flag').title = `Modelled. Source: ${R.FLAGS.slip_table[1]}`; $('r-soil-src').textContent = ` (slip curves Modelled. Source: ${R.FLAGS.slip_table[1]})`;
  $('r-ctrl').addEventListener('change', async () => {   // the learned driver is fetched the first time it is chosen
    if (!['learned', 'race'].includes($('r-ctrl').value) || st.learned) return;
    stop(); $('r-drive').disabled = true; status('Loading the learned driver (network and in-browser runtime, about 15 MB the first time)…');
    try { st.learned = await loadLearned(); status(`Learned driver ready (${fmt(st.learned.loadMs / 1000, 1)} s). Press Drive.`); if (st.route && ['learned', 'race'].includes($('r-ctrl').value)) { reset(); renderComparison(); } }
    catch (e) { status(`The learned driver could not be loaded (${e.message}); the scripted expert drives.`); $('r-ctrl').value = 'expert'; if (st.route) reset(); }
    finally { $('r-drive').disabled = false; }
  });
  for (const id of ['r-level', 'r-ctrl', 'r-soil']) $(id).addEventListener('change', () => { stop(); if (st.route) { reset(); renderComparison(); } $('r-keys').hidden = $('r-ctrl').value !== 'human'; if ($('r-ctrl').value === 'human') $('r-speed').value = '1'; });
  $('r-drive').addEventListener('click', () => { if (st.running) stop(); else drive(); });
  $('r-reset').addEventListener('click', () => { stop(); if (st.route) reset(); });
  $('r-ch').addEventListener('change', () => patchView());
  const keyOk = e => !e.target.closest('input, select, textarea') && $('r-ctrl').value === 'human';
  document.addEventListener('keydown', e => { if (!keyOk(e) || !e.key.startsWith('Arrow')) return; e.preventDefault(); st.keys[e.key] = true; });
  document.addEventListener('keyup', e => { if (e.key.startsWith('Arrow')) st.keys[e.key] = false; });
  for (const b of document.querySelectorAll('[data-key]')) { const k = b.dataset.key, on = e => { e.preventDefault(); st.keys[k] = true; }, off = () => { st.keys[k] = false; }; b.addEventListener('pointerdown', on); b.addEventListener('pointerup', off); b.addEventListener('pointerleave', off); }
  new ResizeObserver(() => drawAll(true)).observe($('r-plan'));
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
}

if (import.meta.env.DEV) window.__rover = { st, stepOnce, drawAll };  // dev-only probe for checks
boot();
