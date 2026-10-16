// Client for the LunarHaul service v2 (service/README.md). Two auth modes:
//  cookie: the page and the API share a registrable domain (app.<domain> / api.<domain>, or localhost and
//          localhost:8800): HttpOnly session cookie, fetch(..., {credentials: 'include'});
//  bearer: any other pairing (e.g. <user>.github.io, which is on the Public Suffix List): the login ends with
//          #login_code=... in the URL, exchanged once at POST /v2/auth/token; the token lives in memory only.
// Every POST carries X-Requested-With: lunarsim (the service's CSRF rule). Server-sent events are read with
// fetch + a stream reader, because EventSource cannot send an Authorization header.

export class ApiError extends Error { constructor(msg, status, code, retryAfter) { super(msg); this.name = 'ApiError'; Object.assign(this, { status, code, retryAfter }); } }

const MULTI_LABEL_SUFFIXES = ['github.io', 'gitlab.io', 'netlify.app', 'pages.dev', 'vercel.app'];
function site(host) {   // rough registrable domain: enough to decide cookie vs bearer
  if (/^\d+\.\d+\.\d+\.\d+$/.test(host) || host === 'localhost' || host.endsWith('.localhost')) return host === 'localhost' || host.endsWith('.localhost') ? 'localhost' : host;
  const labels = host.split('.'), suffix = MULTI_LABEL_SUFFIXES.find(s => host === s || host.endsWith('.' + s));
  return suffix ? labels.slice(-(suffix.split('.').length + 1)).join('.') : labels.slice(-2).join('.');
}
export const sameSite = (a, b) => site(new URL(a).hostname) === site(new URL(b).hostname);

export class ServiceClient {
  constructor(base, pageUrl = location.href) {
    this.base = String(base).replace(/\/+$/, ''); this.token = null;
    this.mode = sameSite(this.base, pageUrl) ? 'cookie' : 'bearer';
  }
  async req(method, path, body, { raw = false, signal } = {}) {
    const h = {}; if (body !== undefined) h['Content-Type'] = 'application/json';
    if (method !== 'GET') h['X-Requested-With'] = 'lunarsim';
    if (this.token) h.Authorization = 'Bearer ' + this.token;
    let res;
    try { res = await fetch(this.base + path, { method, headers: h, body: body === undefined ? undefined : JSON.stringify(body), credentials: this.mode === 'cookie' ? 'include' : 'omit', signal }); }
    catch (e) { if (e.name === 'AbortError') throw e; throw new ApiError(`cannot reach ${this.base}`, 0, 'unreachable'); }
    if (raw) { if (!res.ok) throw new ApiError(`HTTP ${res.status}`, res.status); return res; }
    let data = null; try { data = await res.json(); } catch (e) { /* empty body */ }
    if (!res.ok) throw new ApiError((data && data.error) || `HTTP ${res.status}`, res.status, data && data.code, +res.headers.get('Retry-After') || null);
    return data;
  }
  health() { return this.req('GET', '/v2/health'); }
  version() { return this.req('GET', '/v2/version'); }
  me() { return this.req('GET', '/v2/me'); }
  magic(email, next) { return this.req('POST', '/v2/auth/magic', { email, mode: this.mode, next }); }
  providerUrl(p, next) { return `${this.base}/v2/auth/${p}/start?mode=${this.mode}&next=${encodeURIComponent(next)}`; }
  async exchange(code) { const r = await this.req('POST', '/v2/auth/token', { code }); this.token = r.token; return r; }
  async logout() { try { await this.req('POST', '/v2/logout', {}); } finally { this.token = null; } }
  createRun(body) { return this.req('POST', '/v2/runs', body); }
  run(id) { return this.req('GET', `/v2/runs/${encodeURIComponent(id)}`); }
  runs(params = {}) { const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== '' && v !== null)); return this.req('GET', '/v2/runs' + (q.toString() ? '?' + q : '')); }
  replicate(id) { return this.req('POST', `/v2/runs/${encodeURIComponent(id)}/replicate`, {}); }
  publish(id, pub) { return this.req('POST', `/v2/runs/${encodeURIComponent(id)}/publish`, { public: pub }); }
  async trace(id, seed) { const r = await this.req('GET', `/v2/runs/${encodeURIComponent(id)}/trace${seed === undefined ? '' : '?seed=' + seed}`, undefined, { raw: true }); return r.text(); }
  /* events(id, onEvent({event, id, data}), signal): resolves when the stream ends */
  async events(id, onEvent, signal) {
    const res = await this.req('GET', `/v2/runs/${encodeURIComponent(id)}/events`, undefined, { raw: true, signal });
    const reader = res.body.pipeThrough(new TextDecoderStream()).getReader(); let buf = '';
    for (;;) {
      const { value, done } = await reader.read(); if (done) break; buf += value;
      let k; while ((k = buf.search(/\r?\n\r?\n/)) >= 0) {
        const block = buf.slice(0, k); buf = buf.slice(k).replace(/^\r?\n\r?\n/, '');
        const ev = { event: 'message', id: null, data: '' };
        for (const line of block.split(/\r?\n/)) { if (line.startsWith(':')) continue; const i = line.indexOf(':'), f = i < 0 ? line : line.slice(0, i), v = i < 0 ? '' : line.slice(i + 1).replace(/^ /, ''); if (f === 'event') ev.event = v; else if (f === 'id') ev.id = v; else if (f === 'data') ev.data += (ev.data ? '\n' : '') + v; }
        if (!ev.data && ev.event === 'message') continue;
        try { ev.data = JSON.parse(ev.data); } catch (e) { /* plain text */ }
        if (onEvent(ev) === false) { reader.cancel(); return; }
      }
    }
  }
}
