// /lab/lander (F-7): the terminal-descent environment in the browser with the trained policy or the classical law.
// Episodes run on the JS port (env.js / physics.js, parity-checked against Python), are computed up front and then
// played back; the score counter, reward re-scoring and Monte Carlo panel all read logged quantities only.
import './lab.css';
import * as Plot from '@observablehq/plot';
import * as P from './physics.js';
import { CLASSES, GATE, TOUCHDOWN, TIPOVER_DEG, TIPOVER_SOURCE } from './classes.js';
import { DescentEnv, REWARD_VARIANTS, DT_S, MAX_STEPS } from './env.js';
import { classicalAction } from './classical.js';
import { MlpPolicy, checkPolicy } from '../policy.js';
import { loadTerrain } from '../terrain.js';
import { num, esc, fmt } from '../components/num.js';
import { mountFigures } from '../components/figure.js';

const $ = id => document.getElementById(id);
const BASE = import.meta.env.BASE_URL, POL = BASE + 'lab/policies/';
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const TOL = { policy: '#4477AA', classical: '#EE6677' };
const st = { index: null, policies: {}, checks: {}, terrain: null, pad: null, ep: null, ghost: null, frame: 0, playing: false, last: 0, raf: 0, outcomes: {} };

async function getJson(url) { const r = await fetch(url); if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`); return r.json(); }
const status = m => { $('l-status').textContent = m; };

// ---------- boot ----------
async function boot() {
  try { st.index = await getJson(POL + 'index.json'); } catch (e) { status(`Could not load the policy index (${e.message}).`); return; }
  for (const id of st.index.policies) {
    try {
      const [doc, chk] = await Promise.all([getJson(POL + id + '.json'), getJson(POL + id + '.check.json').catch(() => null)]);
      st.policies[id] = new MlpPolicy(doc); st.checks[id] = chk ? checkPolicy(st.policies[id], chk) : null;
    } catch (e) { status(`Policy ${id} could not be read: ${e.message}`); }
  }
  try {   // terrain profile under the side view (context only; the env uses a flat ground plane with a sampled slope)
    st.terrain = await loadTerrain(BASE + 'terrain/hero/');
    const sites = await getJson(BASE + 'terrain/hero/sites.json').catch(() => null);
    st.pad = sites && sites.pads && sites.pads['1'] ? sites.pads['1'].PAD_A : [st.terrain.sizeM[0] / 2, st.terrain.sizeM[1] / 2];
  } catch (e) { st.terrain = null; }
  wire(); renderPolicyCards(); renderClassOptions(); renderConstants(); renderRewardPanel(); await renderMonteCarlo();
  run();
}

// ---------- controllers ----------
function policyFor(cls) { const ps = Object.values(st.policies).filter(p => (p.doc.training || {}).cls === cls); return ps.find(p => p.doc.training.reward_variant === 'baseline') || ps.find(p => p.doc.training.reward_variant !== 'hover_bonus') || null; }
function hoverPolicy() { return Object.values(st.policies).find(p => (p.doc.training || {}).reward_variant === 'hover_bonus') || null; }
function renderClassOptions() {
  const cls = $('l-class').value, pol = policyFor(cls), sel = $('l-ctrl');
  sel.innerHTML = (pol ? `<option value="policy">Trained policy (${esc(pol.id)})</option>` : '') + '<option value="classical">Classical ZEM/ZEV law</option>';
  $('l-ctrl-note').textContent = pol ? '' : `No trained policy for ${cls} yet; the classical law flies it.`;
  const hp = hoverPolicy(); $('l-hover').disabled = !hp;
  $('l-hover-note').textContent = hp ? `Loads ${hp.id}, trained with η = ${REWARD_VARIANTS.hover_bonus.eta} per step alive.` : 'Hover-bonus policy not trained yet (LEAD trains it); the button activates when its file is published.';
}

/* runEpisode -> {frames:[{state, thrust, tf, reward, cum, obs}], recs, outcome, env, seed, ctrl} */
function runEpisode(cls, ctrl, seed, opts, policy, variant = 'baseline') {
  const env = new DescentEnv({ cls, variant, randomize: opts.randomize, sensor: opts.sensor });
  let obs = env.reset(seed), cum = 0;
  const frames = [{ state: Float64Array.from(env.state), thrust: env.thrustN, tf: env.thrustN / (env.cls.t_max_n * env.thrustScale), reward: 0, cum: 0, action: [0, 0, 0] }], recs = [];
  for (let k = 0; k < MAX_STEPS + 1; k++) {
    const a = ctrl === 'classical' ? Array.from(classicalAction(env)) : policy.act(obs);
    const r = env.step(a); obs = r.obs; cum += r.reward; recs.push(r.rec);
    frames.push({ state: Float64Array.from(env.state), thrust: r.thrust, tf: r.rec.tf, reward: r.reward, cum, action: a });
    if (r.terminated || r.truncated) return { frames, recs, outcome: r.outcome, env, seed, ctrl, cls, policyId: policy ? policy.id : null };
  }
  throw new Error('episode did not terminate');
}

function run(policyOverride) {
  const cls = $('l-class').value, ctrl = policyOverride ? 'policy' : $('l-ctrl').value, seed = Math.max(0, Math.floor(+$('l-seed').value) || 0);
  const opts = { randomize: $('l-rand').checked, sensor: $('l-sensor').checked };
  const pol = policyOverride || policyFor(cls);
  try {
    st.ep = runEpisode(cls, ctrl, seed, opts, pol, policyOverride ? 'hover_bonus' : 'baseline');
    const other = ctrl === 'policy' ? 'classical' : (pol ? 'policy' : null);
    st.ghost = other ? runEpisode(cls, other, seed, opts, pol) : null;
  } catch (e) { status(`Episode failed: ${e.message}`); return; }
  st.ep.variant = policyOverride ? 'hover_bonus' : 'baseline';   // into or out of the hover demo: show its reward; otherwise keep the user's sliders
  if ($('rw-preset').value !== st.ep.variant && (policyOverride || $('rw-preset').value === 'hover_bonus')) { $('rw-preset').value = st.ep.variant; $('rw-preset').dispatchEvent(new Event('change')); }
  const o = st.ep.outcome;
  status(`${cls} · ${ctrl === 'policy' ? st.ep.policyId : 'classical law'} · episode ${seed}${opts.randomize ? '' : ' (no dispersion)'}${opts.sensor ? '' : ' (perfect sensors)'}: ${o.ok ? 'landed in the SPLICE box' : 'failed: ' + o.failure_kind}, miss ${fmt(Math.hypot(...o.miss_m), 1)} m, ${st.ep.frames.length - 1} steps.` +
    (st.ghost ? ` Same seed with the ${st.ghost.ctrl === 'policy' ? 'policy' : 'classical law'}: ${st.ghost.outcome.ok ? 'in the box' : st.ghost.outcome.failure_kind}, miss ${fmt(Math.hypot(...st.ghost.outcome.miss_m), 1)} m.` : ''));
  st.frame = reduced.matches || $('l-speed').value === '0' ? st.ep.frames.length - 1 : 0;
  setPlaying(st.frame < st.ep.frames.length - 1); rescore(); draw();
}

// ---------- playback ----------
function setPlaying(p) { st.playing = p; $('l-play').textContent = p ? 'Pause' : 'Replay'; $('l-play').setAttribute('aria-pressed', String(p)); if (p) { st.last = 0; if (!st.raf) st.raf = requestAnimationFrame(tick); } }
function tick(now) {
  st.raf = 0; if (!st.playing || !st.ep) return;
  const dt = st.last ? Math.min(0.1, (now - st.last) / 1000) : 0; st.last = now;
  st.frame = Math.min(st.ep.frames.length - 1, st.frame + dt * (+$('l-speed').value || 1) / DT_S);
  if (st.frame >= st.ep.frames.length - 1) { setPlaying(false); draw(); return; } draw();
  st.raf = requestAnimationFrame(tick);
}

// ---------- drawing: side view + telemetry + score ----------
function sideView(ep, k, ghost) {
  const cv = $('l-side'), dpr = Math.min(2, devicePixelRatio || 1), r = cv.getBoundingClientRect(), W = r.width, H = r.height;
  if (cv.width !== Math.round(W * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
  const ctx = cv.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const css = n => getComputedStyle(cv).getPropertyValue(n).trim();
  const psi = ep.env.approach, e = [Math.cos(psi), Math.sin(psi)];
  const along = s => s[P.X] * e[0] + s[P.Y] * e[1];
  const all = ep.frames.concat(ghost ? ghost.frames : []), ds = all.map(f => along(f.state));   // fit both paths
  const maxD = Math.max(50, ...ds.map(d => -d)), overD = Math.max(60, ...ds), maxZ = Math.max(80, ...all.map(f => f.state[P.Z]));
  const x0 = -maxD * 1.08, x1 = Math.max(maxD * 0.25, overD * 1.1), zTop = maxZ * 1.15, zBot = -maxZ * 0.12;
  const sx = W / (x1 - x0), sz = (H - 24) / (zTop - zBot), s = Math.min(sx, sz * 1.0);
  const X = d => 10 + (d - x0) * sx, Z = z => H - 18 - (z - zBot) * sz;
  ctx.fillStyle = '#060608'; ctx.fillRect(0, 0, W, H);
  // terrain profile along the approach azimuth through the pad, heights relative to the pad (context only)
  if (st.terrain) {
    const [px, py] = st.pad, h0 = st.terrain.height(px, py); ctx.beginPath(); ctx.moveTo(X(x0), H);
    for (let i = 0; i <= 200; i++) { const d = x0 + (x1 - x0) * i / 200, hh = st.terrain.height(px + d * e[0], py + d * e[1]) - h0; ctx.lineTo(X(d), Z(hh)); }
    ctx.lineTo(X(x1), H); ctx.closePath(); ctx.fillStyle = '#2a2b2f'; ctx.fill();
  }
  ctx.strokeStyle = 'rgba(255,255,255,.35)'; ctx.beginPath(); ctx.moveTo(X(x0), Z(0)); ctx.lineTo(X(x1), Z(0)); ctx.stroke();
  // SPLICE delivery radius on the ground
  ctx.fillStyle = 'rgba(34,136,51,.85)'; ctx.fillRect(X(-TOUCHDOWN.delivery_radius_m), Z(0) - 3, (2 * TOUCHDOWN.delivery_radius_m) * sx, 6);
  ctx.fillStyle = css('--ink-2') || '#aaa'; ctx.font = '11px ' + (css('--font-sans') || 'sans-serif');
  ctx.fillText(`SPLICE box ±${TOUCHDOWN.delivery_radius_m} m`, X(-TOUCHDOWN.delivery_radius_m), Z(0) + 16);
  const path = (frames, upto, col, dash) => { ctx.strokeStyle = col; ctx.setLineDash(dash); ctx.lineWidth = 2; ctx.beginPath(); frames.slice(0, upto + 1).forEach((f, i) => { const xx = X(along(f.state)), zz = Z(f.state[P.Z]); i ? ctx.lineTo(xx, zz) : ctx.moveTo(xx, zz); }); ctx.stroke(); ctx.setLineDash([]); };
  if (ghost) path(ghost.frames, ghost.frames.length - 1, TOL[ghost.ctrl] + '99', [5, 5]);
  const kk = Math.floor(k), f = ep.frames[kk];
  path(ep.frames, kk, TOL[ep.ctrl], []);
  // lander glyph: body tilted with the in-plane thrust angle, flame length ~ throttle
  const lx = X(along(f.state)), lz = Z(f.state[P.Z]), [ux, uy, uz] = P.thrustDirection(f.state[P.TX], f.state[P.TY]), uin = ux * e[0] + uy * e[1], ang = Math.atan2(uin, uz);
  ctx.save(); ctx.translate(lx, lz); ctx.rotate(ang);
  const fl = 6 + 22 * Math.max(0, f.tf); ctx.fillStyle = 'rgba(255,190,90,.9)'; ctx.beginPath(); ctx.moveTo(-3, 6); ctx.lineTo(3, 6); ctx.lineTo(0, 6 + fl); ctx.closePath(); ctx.fill();
  ctx.fillStyle = '#e8e4da'; ctx.fillRect(-6, -8, 12, 14); ctx.strokeStyle = '#e8e4da'; ctx.beginPath(); ctx.moveTo(-6, 6); ctx.lineTo(-10, 12); ctx.moveTo(6, 6); ctx.lineTo(10, 12); ctx.stroke(); ctx.restore();
  ctx.fillStyle = css('--ink-2') || '#aaa'; ctx.fillText('downrange along the approach (m) →', W - 220, H - 4);
  ctx.fillText(`gate ${GATE.altitude_m} m up, ${(ep.cls === 'LARGE' ? 400 : GATE.downrange_m)} m out`, 14, 16);
}

function telemetry(ep, k) {
  const f = ep.frames[Math.floor(k)], s = f.state, t = Math.floor(k) * DT_S, src = `this ${ep.cls} episode (JS port of lunar/Descent-v0, seed ${ep.seed})`;
  const prop = Math.max(0, s[P.M] - ep.env.mDry), M = (v, u, d) => num({ value: v, unit: u, flag: 'Modelled', digits: d, source: src });
  const rows = [['T+', `<span class="mono">${t.toFixed(1)} s</span>`], ['Altitude', M(s[P.Z], 'm', 1)], ['Vertical speed', M(s[P.VZ], 'm/s', 2)],
    ['Horizontal speed', M(Math.hypot(s[P.VX], s[P.VY]), 'm/s', 2)], ['Throttle', M(100 * f.tf, '% of max', 0)], ['Propellant left', M(prop, 'kg', 1)],
    ['Distance to target', M(Math.hypot(s[P.X], s[P.Y]), 'm', 1)], ['Tilt', M(P.tiltDeg(s[P.TX], s[P.TY]), '°', 1)]];
  $('l-tele').innerHTML = rows.map(([a, b]) => `<tr><th scope="row">${a}</th><td>${b}</td></tr>`).join('');
  const done = Math.floor(k) >= ep.frames.length - 1, ok = done && ep.outcome.ok, score = f.cum;
  const el = $('l-score'); el.textContent = (score >= 0 ? '+' : '−') + Math.abs(score).toFixed(1);
  el.classList.toggle('neg', score < 0 && !ok); el.classList.toggle('ok', ok);
  $('l-score-note').textContent = done ? (ok ? `Touchdown inside the SPLICE box: miss ${fmt(Math.hypot(...ep.outcome.miss_m), 1)} m, ${fmt(Math.abs(ep.outcome.v_td[2]), 2)} m/s down.` : `Failed: ${ep.outcome.failure_kind}.`) + ` Score = sum of the ${ep.variant} reward.` : `Score = running sum of the ${ep.variant} reward${ep.variant === 'hover_bonus' ? ', which pays η = 0.3 for every step in the air' : ''} (the reward this policy was trained on).`;
}
let lastTele = 0;
function draw() {   // canvas every frame; the DOM telemetry at most 10 times a second (and always when playback stops)
  if (!st.ep) return; sideView(st.ep, st.frame, st.ghost);
  const now = performance.now(); if (!st.playing || now - lastTele > 100) { telemetry(st.ep, st.frame); lastTele = now; }
}

// ---------- reward rules: re-score the last episode with different weights ----------
const TERMS = [
  ['alpha', 'α · velocity-field error', -0.2, 0, 0.005, 'per step: |v − v_target| (m/s)'], ['beta', 'β · thrust', -1, 0, 0.01, 'per step: thrust / max thrust'],
  ['eta', 'η · staying alive', 0, 0.5, 0.005, 'per step: 1'], ['delta', 'δ · tilt below 30 m', -0.2, 0, 0.005, 'per step below 30 m: max(0, tilt − 6°) / 6'],
  ['zeta', 'ζ · attitude rate below 30 m', -0.05, 0, 0.001, 'per step below 30 m: rate (°/s)'], ['low_time', 'time below 30 m', -0.1, 0, 0.005, 'per step below 30 m: 1'],
  ['low_thrust', 'thrust² below 10 m (plume)', -0.5, 0, 0.01, 'per step below 10 m: (thrust / max)²'], ['kappa', 'κ · landing bonus', 0, 50, 0.5, 'once: 0.5 + 0.5·e^(−miss/10 m) if in the box'],
  ['crash', 'crash penalty', -5, 0, 0.05, 'once: m/s outside the velocity box'], ['lost', 'lost penalty', -50, 0, 0.5, 'once: left the 3 km box'],
];
function termSums(ep) {   // Σ of each term's multiplier over the episode; total reward = Σ_k weight_k · S_k
  const S = Object.fromEntries(TERMS.map(t => [t[0], 0]));
  for (const r of ep.recs) {
    S.alpha += r.vErr; S.beta += r.tf; S.eta += 1;
    if (r.z < 30) { S.delta += Math.max(0, r.tiltDeg - TOUCHDOWN.tilt_max_deg) / 6; S.zeta += r.rateDps; S.low_time += 1; if (r.z < 10) S.low_thrust += r.tf * r.tf; }
    if (r.terminal === 'touchdown') {
      if (r.out.touchdown_ok) S.kappa += 0.5 + 0.5 * Math.exp(-Math.hypot(...r.out.miss_m) / 10);
      else S.crash += Math.max(0, Math.abs(r.out.v_td[2]) - TOUCHDOWN.vz_max_mps) + Math.max(0, Math.hypot(r.out.v_td[0], r.out.v_td[1]) - TOUCHDOWN.vh_max_mps);
    } else if (r.terminal === 'lost') S.lost += 1;
  }
  return S;
}
function weights() { return Object.fromEntries(TERMS.map(t => [t[0], +$('rw-' + t[0]).value])); }
function renderRewardPanel() {
  $('l-rw').innerHTML = TERMS.map(([k, lab, lo, hi, step, what]) => `<div class="rw-row"><label for="rw-${k}">${lab} <span class="muted small">${esc(what)}</span></label>
    <input id="rw-${k}" type="range" min="${lo}" max="${hi}" step="${step}" value="${REWARD_VARIANTS.baseline[k]}"><output id="rw-${k}-v" class="mono"></output></div>`).join('');
  for (const [k] of TERMS) $('rw-' + k).addEventListener('input', rescore);
  $('rw-preset').innerHTML = Object.keys(REWARD_VARIANTS).map(v => `<option value="${v}">${v}</option>`).join('');
  $('rw-preset').addEventListener('change', e => { const v = REWARD_VARIANTS[e.target.value]; for (const [k] of TERMS) $('rw-' + k).value = v[k]; rescore(); });
}
function rescore() {
  if (!st.ep) return; const w = weights(), S = termSums(st.ep), base = REWARD_VARIANTS.baseline;
  for (const [k] of TERMS) $(`rw-${k}-v`).textContent = (+w[k]).toString();
  const total = TERMS.reduce((s, [k]) => s + w[k] * S[k], 0), orig = TERMS.reduce((s, [k]) => s + base[k] * S[k], 0), logged = st.ep.frames[st.ep.frames.length - 1].cum;
  $('rw-out').innerHTML = `<table class="w-table"><tr><th>Term</th><th class="n">Σ multiplier</th><th class="n">× weight</th><th class="n">= contribution</th></tr>` +
    TERMS.map(([k, lab]) => `<tr><td>${lab}</td><td class="n">${fmt(S[k], 2)}</td><td class="n">${w[k]}</td><td class="n">${fmt(w[k] * S[k], 2)}</td></tr>`).join('') +
    `<tr><th>Episode score with these weights</th><td></td><td></td><td class="n"><b>${fmt(total, 2)}</b></td></tr></table>` +
    `<p class="small muted">Baseline weights give ${fmt(orig, 2)} (logged during the run: ${fmt(logged, 2)}; the two agree because the score is linear in the weights).</p>`;
  const hoverPay = w.eta * MAX_STEPS, landMax = w.kappa;
  $('rw-hover').textContent = `Staying airborne until the ${MAX_STEPS}-step cap earns η × ${MAX_STEPS} = ${fmt(hoverPay, 1)} from η alone; the best landing bonus is κ = ${fmt(landMax, 1)}. ` +
    (hoverPay > landMax ? 'With these weights hovering out the clock pays more than landing: a policy trained on them learns to hover (reward hacking).' : 'With these weights landing pays more than hovering.');
}

// ---------- Monte Carlo panel (outcome tables written by lunarsim.lander.evaluate) ----------
function wilson(k, n, z = 1.96) { if (!n) return [NaN, NaN]; const p = k / n, d = 1 + z * z / n, c = p + z * z / (2 * n), h = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return [(c - h) / d, (c + h) / d]; }
async function renderMonteCarlo() {
  const cls = $('l-class').value, ids = st.index.outcomes.filter(id => id === `classical_${cls}` || id.startsWith(`lander_${cls}_`));
  const tables = [];
  for (const id of ids) { try { st.outcomes[id] = st.outcomes[id] || await getJson(POL + `outcomes_${id}.json`); tables.push(st.outcomes[id]); } catch (e) { /* listed but missing */ } }
  const host = $('l-mc');
  if (!tables.length) { host.innerHTML = `<p class="muted">No outcome tables for ${cls} yet.</p>`; return; }
  const label = t => t.policy.startsWith('classical') ? 'Classical law' : `Policy ${t.policy}`, colour = t => t.policy.startsWith('classical') ? TOL.classical : TOL.policy;
  const rows = tables.flatMap(t => t.episodes.map(e => ({ controller: label(t), seed: e.seed, miss_x_m: e.miss_m[0], miss_y_m: e.miss_m[1], miss_r_m: Math.hypot(...e.miss_m), ok: e.ok, failure_kind: e.failure_kind || 'none', vz_td: e.v_td[2] })));
  const R = 60, inside = rows.filter(r => Math.abs(r.miss_x_m) <= R && Math.abs(r.miss_y_m) <= R), outN = rows.length - inside.length;
  const circle = Array.from({ length: 73 }, (_, i) => ({ x: 50 * Math.cos(i * Math.PI / 36), y: 50 * Math.sin(i * Math.PI / 36) }));
  const scatter = Plot.plot({ width: 420, height: 420, aspectRatio: 1, x: { domain: [-R, R], label: 'miss east (m) →' }, y: { domain: [-R, R], label: '↑ miss north (m)' },
    color: { domain: tables.map(label), range: tables.map(colour), legend: false }, style: { background: 'transparent' },
    marks: [Plot.line(circle, { x: 'x', y: 'y', stroke: 'currentColor', strokeOpacity: 0.4, strokeDasharray: '4,3' }), Plot.ruleX([0], { strokeOpacity: 0.15 }), Plot.ruleY([0], { strokeOpacity: 0.15 }),
      Plot.dot(inside, { x: 'miss_x_m', y: 'miss_y_m', stroke: 'controller', symbol: d => d.ok ? 'circle' : 'times', r: 2.6, strokeOpacity: 0.75 })] });
  const rates = tables.map(t => { const n = t.episodes.length, k = t.episodes.filter(e => e.ok).length, [lo, hi] = wilson(k, n); return { controller: label(t), n, passed: k, pass_rate: k / n, ci_lo: lo, ci_hi: hi }; });
  const passPlot = Plot.plot({ width: 460, height: 60 + 46 * rates.length, marginLeft: 190, marginRight: 120, x: { domain: [0, 1], label: 'touchdown-box pass rate (95% Wilson CI) →', tickFormat: '%' },
    y: { label: null }, style: { background: 'transparent' },
    marks: [Plot.ruleY(rates, { y: 'controller', x1: 'ci_lo', x2: 'ci_hi', stroke: d => d.controller.startsWith('Classical') ? TOL.classical : TOL.policy, strokeWidth: 3 }),
      Plot.dot(rates, { y: 'controller', x: 'pass_rate', fill: d => d.controller.startsWith('Classical') ? TOL.classical : TOL.policy, r: 5 }),
      Plot.text(rates, { y: 'controller', x: 'ci_hi', text: d => `${(100 * d.pass_rate).toFixed(1)} % (${d.passed}/${d.n})`, dx: 8, textAnchor: 'start' })] });
  const failures = tables.map(t => `<tr><td>${esc(label(t))}</td>${['none', 'velocity', 'tilt', 'sensor', 'offpad', 'timeout', 'lost'].map(k => `<td class="n">${t.summary.failure_counts[k === 'none' ? 'none' : k] || 0}</td>`).join('')}</tr>`).join('');
  host.innerHTML = '';
  const fig = (name, svgEl, data, caption, summary) => {
    svgEl.querySelectorAll('g[aria-label]').forEach(g => g.removeAttribute('aria-label'));   // Plot labels plain <g>s, which ARIA forbids
    svgEl.setAttribute('role', 'img'); svgEl.setAttribute('aria-label', summary);
    const f = document.createElement('figure'); f.className = 'fig'; f.dataset.figure = name; f.dataset.flag = 'Modelled';
    const body = document.createElement('div'); body.className = 'fig-body'; body.appendChild(svgEl); f.appendChild(body);
    const cap = document.createElement('figcaption'); cap.innerHTML = caption; f.appendChild(cap);
    const sc = document.createElement('script'); sc.type = 'application/json'; sc.dataset.rows = ''; sc.textContent = JSON.stringify(data); f.appendChild(sc); host.appendChild(f); };
  const svgOf = el => el.tagName.toLowerCase() === 'svg' ? el : el.querySelector('svg');
  const src = tables.map(t => `outcomes_${t.policy}.json (n = ${t.n}, seeds ${t.seed0}…, sensor model ${t.sensor ? 'on' : 'off'})`).join('; ');
  fig(`landing-dispersion-${cls}`, svgOf(scatter), rows, `Touchdown miss distance for ${cls}, every Monte Carlo episode (${tables.map(t => `<span style="color:${colour(t)}">●</span> ${esc(label(t))}`).join(", ")}; ○ in the box, × failed); dashed circle = SPLICE 50 m delivery radius. ${outN ? `${outN} episodes beyond ±${R} m are not drawn but are in the CSV.` : ''} <span class="flag" data-flag="Modelled" title="Modelled: LunarSim landing-outcome tables">Modelled</span> Source: ${esc(src)}.`, `Scatter of touchdown miss distances for ${cls}: ${tables.map(t => `${label(t)}, median ${t.summary.components.miss_r_m.p50.toFixed(1)} m`).join("; ")}. The CSV download has every episode.`);
  fig(`landing-pass-rate-${cls}`, svgOf(passPlot), rates, `Share of episodes that meet every SPLICE touchdown limit (|v_z| ≤ 2 m/s, v_h ≤ 1 m/s, tilt ≤ 6°, rate ≤ 2°/s, landed tilt ≤ ${TIPOVER_DEG}°, miss ≤ 50 m), with 95% Wilson intervals. Same initial conditions and sensor model for every controller. <span class="flag" data-flag="Modelled" title="Modelled">Modelled</span>`, `Pass rates: ${rates.map(r => `${r.controller} ${(100 * r.pass_rate).toFixed(1)} % (${r.passed} of ${r.n})`).join("; ")}.`);
  host.insertAdjacentHTML('beforeend', `<div class="l-fail"><table class="w-table small"><caption class="small muted">Failure counts by kind</caption><tr><th>Controller</th><th class="n">ok</th><th class="n">velocity</th><th class="n">tilt</th><th class="n">sensor</th><th class="n">off-pad</th><th class="n">timeout</th><th class="n">lost</th></tr>${failures}</table></div>`);
  mountFigures(host);
}

// ---------- policy cards and constants ----------
function renderPolicyCards() {
  const ids = Object.keys(st.policies);
  $('l-cards').innerHTML = ids.length ? ids.map(id => {
    const p = st.policies[id], t = p.doc.training || {}, fe = t.final_eval || {}, chk = st.checks[id], mc = st.index.outcomes.includes(id);
    return `<div class="card-lite"><h3>${esc(id)}</h3><p class="small">${esc(t.algo || '')} · ${(t.steps || 0).toLocaleString('en-GB')} steps · reward <b>${esc(t.reward_variant || '?')}</b> · class ${esc(t.cls || '?')} · network ${p.layers.map(l => l.w.length).join('–')} (${p.obsDim} inputs) · training seed ${t.seed ?? '?'}</p>
      <p class="small">End-of-training check: ${fe.pass_rate !== undefined ? num({ value: 100 * fe.pass_rate, unit: `% in the box (${fe.episodes} episodes)`, flag: 'Modelled', digits: 0, source: `${id}.json training.final_eval` }) : '–'}${mc ? ' · Monte Carlo below' : ''}</p>
      <p class="small ${chk && chk.ok ? 'pass' : 'fail'}">Browser runtime check: ${chk ? `${chk.n} vectors, max |Δaction| ${chk.maxErr.toExponential(1)} (tolerance ${chk.tolerance}) — ${chk.ok ? 'matches Python' : 'DOES NOT MATCH'}` : 'no check file'}</p></div>`;
  }).join('') : '<p class="muted">No trained policies published yet.</p>';
}
function renderConstants() {
  const cls = CLASSES[$('l-class').value], keys = [['m_gate_kg', 'Mass at the gate', 'kg', 0], ['prop_gate_kg', 'Propellant at the gate', 'kg', 0], ['t_max_n', 'Maximum thrust', 'N', 0], ['t_min_n', 'Throttle floor', 'N', 0], ['isp_s', 'Specific impulse', 's', 0], ['tilt_max_deg', 'Maximum tilt', '°', 0], ['tilt_rate_max_dps', 'Slew-rate limit', '°/s', 0]];
  const flag = f => String(f).split(' ')[0];
  $('l-consts').innerHTML = keys.map(([k, lab, u, d]) => `<tr><th scope="row">${lab}</th><td>${num({ value: cls[k], unit: u, flag: flag(cls.flags[k]), digits: d, source: cls.sources[k] })}${/conflicting/.test(cls.flags[k]) ? ' <span class="small muted">(sources conflict)</span>' : ''}</td></tr>`).join('') +
    `<tr><th scope="row">Touchdown box</th><td>${num({ value: TOUCHDOWN.vz_max_mps, unit: 'm/s down', flag: 'Spec', digits: 1, source: TOUCHDOWN.source })}, ${num({ value: TOUCHDOWN.vh_max_mps, unit: 'm/s across', flag: 'Spec', digits: 1, source: TOUCHDOWN.source })}, ${num({ value: TOUCHDOWN.delivery_radius_m, unit: 'm radius', flag: 'Spec', digits: 0, source: TOUCHDOWN.source })}</td></tr>` +
    `<tr><th scope="row">Tip-over limit</th><td>${num({ value: TIPOVER_DEG, unit: '°', flag: 'Spec', digits: 0, source: TIPOVER_SOURCE })}</td></tr>`;
}

function wire() {
  $('l-run').addEventListener('click', () => run());
  $('l-play').addEventListener('click', () => { if (!st.ep) return; if (!st.playing && st.frame >= st.ep.frames.length - 1) st.frame = 0; setPlaying(!st.playing); });
  $('l-class').addEventListener('change', () => { renderClassOptions(); renderConstants(); renderMonteCarlo(); run(); });
  $('l-hover').addEventListener('click', () => { const hp = hoverPolicy(); if (hp) run(hp); });
  $('l-random').addEventListener('click', () => { $('l-seed').value = String(Math.floor(Math.random() * 100000)); run(); });
  new ResizeObserver(() => draw()).observe($('l-side'));
  document.addEventListener('visibilitychange', () => { if (document.hidden) setPlaying(false); });
}

if (import.meta.env.DEV) window.__lab = { st, runEpisode, termSums, draw };  // dev-only probe for checks
boot();
