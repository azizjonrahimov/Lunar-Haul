// Loading door: covers a 3D stage (not the page, so the text paints first) while its files download, with real
// byte progress, an Enter button once ready, and a skip link to the text version. Opening slides the two leaves
// apart, or is instant under prefers-reduced-motion.
import { h, uid, reducedMotion } from './dom.js';

const MB = b => (b / 1e6).toFixed(1);

// door({title, subtitle, skip: {href, label}, enterLabel, autoEnter, onEnter}) -> {el, fetch(url, {bytes, label}), ready(), fail(msg), open(), reset()}
// bytes: the expected (decoded) size when known, e.g. from a manifest; otherwise Content-Length is used unless the
// response is content-encoded (then the browser hands over more bytes than the header says and only MB loaded is shown).
export function door({ title, subtitle = '', skip, enterLabel = 'Enter', autoEnter = false, onEnter = () => {} }) {
  const tid = uid('door');
  const fill = h('i');
  const bar = h('div', { class: 'ui-door-bar', role: 'progressbar', 'aria-labelledby': tid, 'aria-valuemin': '0', 'aria-valuemax': '100' }, fill);
  const status = h('p', { class: 'ui-door-status' });
  const enter = h('button', { class: 'ui-btn primary', type: 'button', disabled: true, onclick: () => api.open() }, enterLabel);
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
      status.textContent = `${label ? label + ' · ' : ''}${MB(loaded)} of ${MB(total)} MB`;
    } else {
      bar.classList.add('indeterminate'); bar.removeAttribute('aria-valuenow');
      status.textContent = `${label ? label + ' · ' : ''}${MB(loaded)} MB`;
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
      fill.style.width = '100%'; bar.classList.remove('indeterminate'); bar.setAttribute('aria-valuenow', '100');
      enter.disabled = false;
      status.textContent = `Ready · ${MB([...files.values()].reduce((s, f) => s + f.loaded, 0))} MB loaded`;
      if (autoEnter) api.open();
      else if (!document.activeElement || document.activeElement === document.body || el.contains(document.activeElement)) enter.focus({ preventScroll: true });
    },
    fail(msg) { bar.classList.remove('indeterminate'); status.textContent = msg; enter.disabled = true; },
    open() {
      const wasFocused = el.contains(document.activeElement);
      const done = () => { el.hidden = true; el.classList.remove('opening'); onEnter({ focus: wasFocused }); };
      if (reducedMotion()) return done();
      el.classList.add('opening');
      setTimeout(done, 720);
    },
    reset() { files.clear(); el.hidden = false; enter.disabled = true; fill.style.width = '0'; status.textContent = ''; bar.setAttribute('aria-valuenow', '0'); },
  };
  return api;
}
