// F-68: the live side of the /protocol/ cutaways (Fig 1b-1d), loaded with the figures when their section comes into view
// (src/protocol/main.js). Static art comes from lib/anatomy-*.mjs; here: picking parts, the eased "open" of Fig 1b, the
// day run of Fig 1d and the sliding neighbour of Fig 1c. Reduced motion: no tour, no glide; end states are shown directly.
import { flatLoss, capacity } from './radio.js';

const RAD = Math.PI / 180, UNIT = Math.sqrt(1.6);
const iso = ([x, y, z], P) => { const a = P.azimuth * RAD, e = P.elevation * RAD, k = P.scale * UNIT; return [P.origin[0] + (x * Math.sin(a) - y * Math.cos(a)) * k, P.origin[1] + ((x * Math.cos(a) + y * Math.sin(a)) * Math.sin(e) - z * Math.cos(e)) * k]; };
const r1 = v => Math.round(v * 10) / 10;
const still = matchMedia('(prefers-reduced-motion: reduce)');
const ease = t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const nf = (v, d = 1) => v.toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d });

// shared: numbered pins when the figure is narrow; the screen-reader readout
function common(root) {
  const svg = root.querySelector('svg');
  // compact (narrow): the labels give way to pins, and the view crops the two label columns so the drawing grows
  const full = svg.getAttribute('viewBox'), [, , vw, vh] = full.split(' ').map(Number), col = +svg.dataset.col || 0;
  const fit = () => { const narrow = root.getBoundingClientRect().width < 600; root.toggleAttribute('data-compact', narrow); svg.setAttribute('viewBox', narrow && col ? `${col} 0 ${vw - 2 * col} ${vh}` : full); };
  new ResizeObserver(fit).observe(root); fit();
  const corner = root.querySelector('[data-readout]'), live = root.querySelector('.an-live');
  return { svg, read: (text, say = false) => { if (corner) corner.textContent = text; if (say && live) live.textContent = text; } };
}
// an eased 0..1 transition that calls step(t) each frame
function glide(from, to, ms, step, done) {
  if (still.matches) { step(to); done?.(); return; }
  let t0 = 0; const f = now => { t0 ||= now; const u = Math.min(1, (now - t0) / ms); step(from + (to - from) * ease(u)); if (u < 1) requestAnimationFrame(f); else done?.(); };
  requestAnimationFrame(f);
}

function mountNav(root) {
  const { read } = common(root);
  const groups = [...root.querySelectorAll('.nv-part')], items = [...root.querySelectorAll('.nv-item')];
  const marks = [...root.querySelectorAll('.an-label, .an-pin')];
  let current = null, touring = !still.matches, timer = 0, idle = 0, visible = false;
  function show(id, say = false) {
    if (id === current) return;
    current = id;
    for (const g of groups) { const on = g.dataset.part === id || g.dataset.also === id; for (const s of g.querySelectorAll('.iso-solid')) s.toggleAttribute('data-lit', on); }
    for (const m of marks) m.toggleAttribute('data-on', m.dataset.part === id);
    for (const b of items) b.setAttribute('aria-pressed', String(b.dataset.part === id));
    const b = items.find(x => x.dataset.part === id); if (b) read(b.querySelector('.nv-name').textContent, say);
  }
  const order = items.map(b => b.dataset.part);
  const run = () => { clearInterval(timer); timer = touring && visible ? setInterval(() => show(order[(order.indexOf(current) + 1) % order.length]), 2800) : 0; };
  const touch = id => { show(id, true); touring = false; run(); clearTimeout(idle); if (!still.matches) idle = setTimeout(() => { touring = true; run(); }, 8000); };
  for (const b of items) for (const ev of ['click', 'focus', 'pointerenter']) b.addEventListener(ev, () => touch(b.dataset.part));
  for (const g of [...groups, ...marks]) g.addEventListener('pointerenter', () => touch(g.dataset.part));
  // open: every moving group goes to its data-move offset; ghosted panels fade to data-fade
  const movers = [...root.querySelectorAll('[data-move]')].map(el => ({ el, v: el.dataset.move.split(' ').map(Number), fade: el.dataset.fade ? +el.dataset.fade : null }));
  const btn = root.querySelector('.an-open'); let t = 0, opened = false, auto = true;
  const pose = u => { t = u; for (const m of movers) { m.el.setAttribute('transform', `translate(${r1(m.v[0] * u)} ${r1(m.v[1] * u)})`); if (m.fade !== null) m.el.setAttribute('opacity', String(1 - u * (1 - m.fade))); } };
  const set = open => { opened = open; btn.setAttribute('aria-pressed', String(open)); btn.textContent = open ? 'Close the boxes' : 'Open the boxes'; glide(t, open ? 1 : 0, 1100, pose); read(open ? 'Opened: lids lifted, side panels set aside' : 'Closed', true); };
  if (!btn) {   // a variant drawn open, without the control (the /network/ deck)
    new IntersectionObserver(es => { visible = es[es.length - 1].isIntersecting; run(); }, { threshold: 0.35 }).observe(root);
    show(order[0]); return;
  }
  btn.addEventListener('click', () => { auto = false; set(!opened); });
  new IntersectionObserver(es => {
    visible = es[es.length - 1].isIntersecting; run();
    if (visible && auto) { auto = false; setTimeout(() => set(true), still.matches ? 0 : 700); }   // open once on first view
  }, { threshold: 0.35 }).observe(root);
  show(order[0]);
}

function mountClock(root) {
  const { svg, read } = common(root);
  const C = JSON.parse(svg.dataset.clock), P = C.P;
  const needles = Object.fromEntries([...svg.querySelectorAll('.ck-needle')].map(n => [n.dataset.dial, n]));
  const car = svg.querySelector('.ck-car'), marks = svg.querySelector('.ck-marks'), button = svg.querySelector('.ck-button');
  const runBtn = root.querySelector('.ck-run'), every = [...root.querySelectorAll('input[name="ck-every"]')];
  const hx = h => C.hourX[0] + (C.hourX[1] - C.hourX[0]) * h / 24, rulerY = C.rail.y + 15 + 0.8;
  const o = iso([0, 0, 0], P), sx = iso([1, 0, 0], P);
  let t = 0, interval = 3600, running = false, last = 0, lastSync = 0;
  const needle = (id, secs) => {
    const { c: [x, y], scale } = C.dials[id], a = 2 * Math.PI * C.drift[id] * secs / scale;
    const p = q => iso([q[0], q[1], C.DTOP + 0.2], P).map(r1).join(' ');
    return `M${p([x - Math.sin(a) * 3.4, y + Math.cos(a) * 3.4])}L${p([x + Math.sin(a) * (C.DR - 4), y - Math.cos(a) * (C.DR - 4)])}`;
  };
  const drawMarks = () => {
    const n = interval ? Math.floor(86400 / interval) : 0, dots = [];
    for (let i = 1; i <= n; i++) { const [x, y] = iso([hx(i * interval / 3600), rulerY + 5.5, 0.6], P); dots.push(`<circle cx="${r1(x)}" cy="${r1(y)}" r="${n > 30 ? 0.45 : 0.8}"/>`); }
    marks.innerHTML = `<g class="iso-dots" data-tone="hi">${dots.join('')}</g>`;
  };
  function draw() {
    const since = interval ? t % interval : t;
    for (const id of ['tcxo', 'csac']) needles[id].setAttribute('d', needle(id, since));
    const dx = (hx(t / 3600) - hx(0)); car.setAttribute('transform', `translate(${r1((sx[0] - o[0]) * dx)} ${r1((sx[1] - o[1]) * dx)})`);
    const cr = C.drift.tcxo * since, at = C.drift.csac * since;
    read(`t = ${nf(t / 3600, 1)} h · crystal ${nf(cr * 1e3, 2)} ms = ${nf(cr * 299792.458, 0)} km · atomic ${nf(at * 1e6, 2)} µs = ${nf(at * 299792458, 0)} m`);
    const sync = interval ? Math.floor(t / interval) : 0;
    if (sync !== lastSync) { lastSync = sync; button.setAttribute('transform', 'translate(0 1.4)'); setTimeout(() => button.removeAttribute('transform'), 160); }
  }
  function tick(now) {
    if (!running) return;
    const dt = last ? Math.min(0.05, (now - last) / 1000) : 0; last = now;
    t = Math.min(86400, t + dt * 86400 / 16);   // a day in 16 s
    draw();
    if (t >= 86400) { running = false; runBtn.textContent = 'Run again'; runBtn.setAttribute('aria-pressed', 'false'); read(root.querySelector('[data-readout]').textContent, true); return; }
    requestAnimationFrame(tick);
  }
  runBtn.addEventListener('click', () => {
    if (running) { running = false; runBtn.textContent = 'Run a day'; runBtn.setAttribute('aria-pressed', 'false'); return; }
    if (t >= 86400) t = 0;
    lastSync = 0;
    if (still.matches) { t = 86400; draw(); read(root.querySelector('[data-readout]').textContent, true); return; }
    running = true; last = 0; runBtn.textContent = 'Pause'; runBtn.setAttribute('aria-pressed', 'true'); requestAnimationFrame(tick);
  });
  for (const r of every) r.addEventListener('change', () => { interval = +r.value; lastSync = interval ? Math.floor(t / interval) : 0; drawMarks(); draw(); });
  drawMarks(); draw();
}

function mountRadio(root) {
  const { svg, read } = common(root);
  const R = JSON.parse(svg.dataset.radio), P = R.P;
  const car = svg.querySelector('.rd-car'), rays = svg.querySelector('.rd-rays'), direct = svg.querySelector('.rd-direct'), bounce = svg.querySelector('.rd-bounce'), hit = svg.querySelector('.rd-hit');
  const whips = [...svg.querySelectorAll('.rd-whip')], posts = [...svg.querySelectorAll('.rd-post')];
  const slider = root.querySelector('#rd-d'), ants = [...root.querySelectorAll('input[name="rd-ant"]')];
  const xOf = d => R.log0 + R.perDecade * (Math.log10(d) - 1), o = iso([0, 0, 0], P), sx = iso([1, 0, 0], P);
  let ant = 'small';
  function draw(say = false) {
    const d = 10 ** (+slider.value / 1000), hm = R.heights[ant], h = R.boxH + 2 + hm * R.hz, bx = xOf(d) - xOf(10);
    car.setAttribute('transform', `translate(${r1((sx[0] - o[0]) * bx)} ${r1((sx[1] - o[1]) * bx)})`);
    const ta = [R.ax[0], R.ax[1], h], tb = [R.bx0 + bx, R.by, h + R.carZ], s = ta[2] / (ta[2] + tb[2]);
    const g = [ta[0] + (tb[0] - ta[0]) * s, ta[1] + (tb[1] - ta[1]) * s, 0], p = q => iso(q, P).map(r1).join(' ');
    direct.setAttribute('d', `M${p(ta)}L${p(tb)}`); bounce.setAttribute('d', `M${p(ta)}L${p(g)}L${p(tb)}`);
    const gi = iso(g, P); hit.setAttribute('cx', r1(gi[0])); hit.setAttribute('cy', r1(gi[1]));
    const m = R.marks[ant], lost = d > m.hz; rays.toggleAttribute('data-lost', lost);
    const dist = d >= 1000 ? `${nf(d / 1000, 1)} km` : `${nf(d, 0)} m`;
    if (lost) { read(`${dist}: past the ${nf(m.hz / 1000, 1)} km horizon, no direct link`, say); return; }
    const loss = flatLoss(d, hm, hm, 2.4e9), c = capacity(loss, { bw: 1e6, txW: R.tx[ant] });
    read(`${dist} · ${d > m.bp ? 'two-ray' : 'free space'} · loss ${nf(loss, 0)} dB · ${nf(c.kbps, 0)} kbit/s ${c.kbps >= 16 ? '(carries 16)' : '(below 16)'}`, say);
  }
  const setAnt = id => { ant = id; for (const w of whips) w.toggleAttribute('data-off', w.dataset.ant !== id); for (const q of posts) q.toggleAttribute('data-off', q.dataset.ant !== id); draw(true); };
  slider.addEventListener('input', () => draw()); slider.addEventListener('change', () => draw(true));
  for (const a of ants) a.addEventListener('change', () => setAnt(a.value));
  setAnt('small');
}

export function mount(root) {
  const kind = root.dataset.anat;
  if (kind === 'nav') mountNav(root); else if (kind === 'clock') mountClock(root); else if (kind === 'radio') mountRadio(root);
}
