// Loading door: covers a 3D stage (not the page, so the text paints first) while its files download, with real
// byte progress, an Enter button once ready, and a skip link to the text version. Opening slides the two leaves
// apart, or is instant under prefers-reduced-motion.
import { h, uid, reducedMotion } from './dom.js';

const MB = b => b < 1e6 ? `${Math.max(1, Math.round(b / 1e3))} kB` : `${(b / 1e6).toFixed(1)} MB`;   // size with its unit

// door({title, subtitle, skip: {href, label}, enterLabel, autoEnter, onEnter, beforeOpen}) -> {el, fetch(url, {bytes, label}), ready(), fail(msg), open(), reset()}
// beforeOpen: async work started by Enter (e.g. building the 3D scene); the door stays shut, says so, then opens
// bytes: the expected (decoded) size when known, e.g. from a manifest; otherwise Content-Length is used unless the
// response is content-encoded (then the browser hands over more bytes than the header says and only MB loaded is shown).
export function door({ title, subtitle = '', skip, enterLabel = 'Enter', autoEnter = false, onEnter = () => {}, beforeOpen = null }) {
  const tid = uid('door');
  const fill = h('i');
  const bar = h('div', { class: 'ui-door-bar', role: 'progressbar', 'aria-labelledby': tid, 'aria-valuemin': '0', 'aria-valuemax': '100' }, fill);
  const status = h('p', { class: 'ui-door-status' });
  const enter = h('button', { class: 'ui-btn primary', type: 'button', disabled: true, onclick: () => go() }, enterLabel);
  // F-40: the door covers the view it is appended to, and that view's stage (its parent) holds the HUD drawn over it; while
  // the door is up, everything else in the stage is inert, so no hidden chip or flag takes keyboard focus
  let covered = [];
  function cover(on) {
    for (const c of covered) c.inert = false;
    covered = [];
    const stage = on && el.parentElement?.parentElement; if (!stage) return;
    const walk = node => { for (const c of node.children) { if (c === el) continue; if (c.contains(el)) walk(c); else { c.inert = true; covered.push(c); } } };
    walk(stage);
  }
  async function go() {
    const had = el.contains(document.activeElement);   // before Enter is disabled (which drops focus to the body)
    if (beforeOpen) {
      enter.disabled = true; bar.classList.add('indeterminate'); bar.removeAttribute('aria-valuenow'); status.textContent = 'Starting the 3D view…';
      try { await beforeOpen(); } catch (e) { return api.fail(`The 3D view could not start (${e.message}).`); }
    }
    api.open(had);
  }
  const card = h('div', { class: 'ui-door-card ui-glass' },
    h('p', { class: 'ui-label' }, 'Loading'),
    h('h2', { class: 'ui-title ui-door-title', id: tid }, title),
    subtitle ? h('p', { class: 'ui-door-sub' }, subtitle) : null,
    bar, status,
    h('div', { class: 'ui-door-actions' }, enter, skip ? h('a', { href: skip.href }, skip.label) : null));
  const el = h('div', { class: 'ui-door' }, h('div', { class: 'ui-door-leaf l' }), h('div', { class: 'ui-door-leaf r' }), card);

  const files = new Map();   // url -> {loaded, total, label}
  function update() {
    let loaded = 0, total = 0, known = true, label = '';
    for (const f of files.values()) { loaded += f.loaded; total += f.total; if (!f.total) known = false; if (!f.done) label = f.label; }
    if (known && total) {
      const p = Math.min(100, (loaded / total) * 100);
      fill.style.width = `${p}%`; bar.classList.remove('indeterminate'); bar.setAttribute('aria-valuenow', Math.round(p));
      status.textContent = `${label ? label + ' · ' : ''}${MB(loaded)} of ${MB(total)}`;
    } else {
      bar.classList.add('indeterminate'); bar.removeAttribute('aria-valuenow');
      status.textContent = `${label ? label + ' · ' : ''}${MB(loaded)}`;
    }
  }

  const api = {
    el,
    // fetch with byte counting; resolves to a Response built from the bytes, so .json()/.arrayBuffer() still work
    async fetch(url, { bytes = 0, label = '' } = {}) {
      const f = { loaded: 0, total: bytes, label, done: false }; files.set(url, f); update();
      const r = await fetch(url);
      if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
      const enc = r.headers.get('content-encoding'), len = +r.headers.get('content-length') || 0;
      if (!f.total && len && (!enc || enc === 'identity')) f.total = len;
      if (!r.body) { const b = await r.arrayBuffer(); f.loaded = f.total = b.byteLength; f.done = true; update(); return new Response(b, { headers: r.headers }); }
      const reader = r.body.getReader(), chunks = [];
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value); f.loaded += value.byteLength; update();
      }
      if (f.total && f.loaded > f.total) f.total = f.loaded;
      f.done = true; update();
      return new Response(new Blob(chunks), { headers: r.headers });
    },
    ready() {
      cover(true);
      fill.style.width = '100%'; bar.classList.remove('indeterminate'); bar.setAttribute('aria-valuenow', '100');
      enter.disabled = false;
      status.textContent = `Ready · ${MB([...files.values()].reduce((s, f) => s + f.loaded, 0))} loaded`;
      if (autoEnter) go();
      // F-40: focus moves to Enter only from inside the door; on a fresh page it stays put, so Tab starts at 'Skip to content'
      else if (el.contains(document.activeElement)) enter.focus({ preventScroll: true });
    },
    fail(msg) { bar.classList.remove('indeterminate'); status.textContent = msg; enter.disabled = true; },
    open(had) {
      const wasFocused = had ?? el.contains(document.activeElement);
      // F-40: the view's canvas joins the tab order only now (tabindex=-1 in the page while the door covers it), and keyboard
      // focus on the door goes on to it unless the page took it elsewhere in onEnter
      const done = () => {
        el.hidden = true; el.classList.remove('opening'); cover(false);
        const canvas = el.parentElement?.querySelector('canvas[tabindex]'); if (canvas) canvas.tabIndex = 0;
        onEnter({ focus: wasFocused });
        if (wasFocused && canvas && (document.activeElement === document.body || el.contains(document.activeElement))) canvas.focus({ preventScroll: true });
      };
      if (reducedMotion()) return done();
      el.classList.add('opening');
      setTimeout(done, 720);
    },
    reset() { files.clear(); el.hidden = false; cover(true); enter.disabled = true; fill.style.width = '0'; status.textContent = ''; bar.setAttribute('aria-valuenow', '0'); },
  };
  return api;
}
