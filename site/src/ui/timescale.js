// Shared time scale for every animated page (F-50): named speeds from real time to 3 days a second, a label that
// always says what one second on screen is on the Moon ("1 s on screen = 5 min on the Moon"), ?speed= in the URL
// (5min, 1h, 1d, 60x, real, …), keys [ and ] for slower and faster and space for play/pause, an optional "Skip quiet
// time" box and a short toast for what the page skipped. Speeds are simulated seconds per real second (x).
import './timescale.css';
import { NAMED, speedName, speedText, simSpan, parseSpeed, nearest } from './speeds.js';
export * from './speeds.js';

/* createTimescale({speeds, value, label, onChange(x, how), onPlayPause, skip, keys, active, url, picker}) ->
   {el, x, h, touched, skip, set(x), step(±1), override(x|null, prefix), toast(text), dispose()}
   speeds: x values (0 = instant), slowest first; value: the default; how in onChange: 'user' | 'key' | 'url' | 'page'.
   touched: the visitor (or the URL) chose the speed, so the page's per-shot defaults leave it alone.
   override: the page runs at another speed for a while (a landing); the label says so. active(): keys only then.
   picker: false shows only the label (a view the visitor does not steer, like the home hero). */
export function createTimescale({ speeds = NAMED, value = 300, label = 'Speed', onChange = () => {}, onPlayPause = null, skip = false, keys = true, active = () => true, url = true, id, picker = true } = {}) {
  const fromUrl = url ? parseSpeed(new URLSearchParams(location.search).get('speed')) : null;
  let x = fromUrl !== null ? nearest(speeds, fromUrl) : speeds.includes(value) ? value : nearest(speeds, value), over = null, toastT = 0;
  const sel = document.createElement('select'); if (id) sel.id = id;
  sel.className = 'ts-select';
  for (const v of speeds) sel.append(new Option(speedName(v), String(v)));
  const lab = document.createElement('label'); lab.className = 'ts-pick';
  lab.append(Object.assign(document.createElement('span'), { className: 'ts-name', textContent: label }), sel);
  const text = Object.assign(document.createElement('span'), { className: 'ts-text' });
  const toastEl = Object.assign(document.createElement('span'), { className: 'ts-toast' }); toastEl.setAttribute('role', 'status');
  const el = Object.assign(document.createElement('div'), { className: 'ts' });
  el.append(...(picker ? [lab] : []), text);
  let box = null;
  if (skip) {
    el.classList.add('ts-has-skip');
    box = Object.assign(document.createElement('input'), { type: 'checkbox', checked: skip !== 'off' });
    const l = Object.assign(document.createElement('label'), { className: 'ts-skip', title: 'When nothing moves and no landing is near, jump to the next event' });
    l.append(box, ' Skip quiet time'); el.append(l);
  }
  el.append(toastEl);
  const api = {
    el, touched: fromUrl !== null,
    get x() { return x; }, get h() { return x / 3600; }, get skip() { return !!box?.checked; },
    set(v, how = 'page') { v = speeds.includes(v) ? v : nearest(speeds, v); if (v === x) return; x = v; draw(); onChange(x, how); },
    step(d, how = 'key') { const i = speeds.indexOf(x) + d; if (i < 0 || i >= speeds.length || speeds[i] === 0) return; api.touched = true; api.set(speeds[i], how); writeUrl(); },
    override(v, prefix = 'Landing') { const o = v === null ? null : { v, prefix }; if (JSON.stringify(o) === JSON.stringify(over)) return; over = o; draw(); },
    toast(msg) { toastEl.textContent = msg; toastEl.classList.add('on'); clearTimeout(toastT); toastT = setTimeout(() => toastEl.classList.remove('on'), 3500); },
    dispose() { document.removeEventListener('keydown', onKey); clearTimeout(toastT); },
  };
  function draw() {
    sel.value = String(x);
    text.textContent = over ? `${over.prefix}: ${over.v === 1 ? 'real time, 1 s on screen = 1 s on the Moon' : `slowed to 1 s on screen = ${simSpan(over.v)} on the Moon`}` : speedText(x);
    text.classList.toggle('ts-over', !!over);
  }
  function writeUrl() { if (!url) return; const u = new URL(location.href); u.searchParams.set('speed', String(x)); history.replaceState(history.state, '', u); }
  sel.addEventListener('change', () => { x = +sel.value; api.touched = true; draw(); writeUrl(); onChange(x, 'user'); });
  function onKey(e) {
    if (e.ctrlKey || e.metaKey || e.altKey || !active()) return;
    const t = e.target;
    if (t.closest?.('input, select, textarea, [contenteditable=""], [contenteditable="true"]')) return;
    if (e.key === '[') { e.preventDefault(); api.step(-1); }
    else if (e.key === ']') { e.preventDefault(); api.step(1); }
    else if (e.key === ' ' && onPlayPause && !t.closest?.('button, a, summary, [role="button"], [role="slider"]')) { e.preventDefault(); onPlayPause(); }
  }
  if (keys) document.addEventListener('keydown', onKey);
  draw();
  return api;
}
