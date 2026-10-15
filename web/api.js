'use strict';
/* Client for the optional local Python engine, `lunarsim serve` (PLAN §4.5). No DOM: app.js owns the UI.
   Nothing here runs until the user presses Connect, so a page without a server makes no requests at all. */

class ApiError extends Error { constructor(msg, status) { super(msg); this.name = 'ApiError'; this.status = status; } }

const PY_API = {
  base: null, info: null,  // set by connect(); base is null while not connected
  MAX_SEEDS: 100,          // server limit per request
  // Page served by `lunarsim serve --static` (port 8765): same origin. Otherwise the default local address.
  defaultBase() { try { if (location.protocol.startsWith('http') && location.port === '8765') return location.origin; } catch (e) {} return 'http://127.0.0.1:8765'; },
  normalise(base) { const b = String(base || '').trim().replace(/\/+$/, ''); if (!/^https?:\/\/[^\s/]+$/i.test(b)) throw new ApiError('enter a base URL such as http://127.0.0.1:8765 (scheme, host and port only)'); return b; },

  async call(path, body, { base = this.base, timeoutMs = 120000 } = {}) {
    if (!base) throw new ApiError('not connected');
    const ctl = typeof AbortController === 'function' ? new AbortController() : null, timer = ctl && setTimeout(() => ctl.abort(), timeoutMs);
    let res;
    try {
      res = await fetch(base + path, body === undefined ? { signal: ctl && ctl.signal } :
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: ctl && ctl.signal });
    } catch (e) {
      throw new ApiError(e && e.name === 'AbortError' ? `no answer from ${base} within ${Math.round(timeoutMs / 1000)} s` : `cannot reach ${base} (is \`lunarsim serve\` running?)`, 0);
    } finally { if (timer) clearTimeout(timer); }
    let data = null; try { data = await res.json(); } catch (e) { /* non-JSON body */ }
    if (!res.ok) throw new ApiError((data && data.error) || `HTTP ${res.status} from ${path}`, res.status);
    if (data === null) throw new ApiError(`${path} did not return JSON`, res.status);
    return data;
  },

  async connect(base) {
    const b = this.normalise(base);
    const h = await this.call('/api/health', undefined, { base: b, timeoutMs: 5000 });
    if (!h || h.ok !== true) throw new ApiError(`${b}/api/health did not report ok`);
    this.base = b; this.info = h; return h;
  },
  disconnect() { this.base = null; this.info = null; },
  get connected() { return this.base !== null; },

  run(scenario, mechanism, seeds, opts) { return this.call('/api/run', { scenario, mechanism, seeds, opts: opts || {} }); },
  compare(scenario, seeds, opts) { return this.call('/api/compare', { scenario, seeds, opts: opts || {} }, { timeoutMs: 300000 }); },
  trace(scenario, mechanism, seed, opts) { return this.call('/api/trace', { scenario, mechanism, seed, opts: opts || {} }); },
};
