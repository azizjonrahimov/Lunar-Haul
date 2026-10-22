// /account (F-9): sign-in, your runs on the LunarHaul service, replication badges, publishing, and the public
// gallery / leaderboard. Nothing on the rest of the site depends on this page or on the service being up.
import './account.css';
import { ServiceClient, ApiError } from './api.js';
import { num, esc, fmt } from '../components/num.js';

const $ = id => document.getElementById(id);
const BASE = import.meta.env.BASE_URL;
const store = { get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } } };
const SCENARIOS = ['P2-default', 'P1-default', 'P3-default', 'P2-2-vehicles', 'P2-3-vehicles', 'P2-4-vehicles', 'P2-5-vehicles', 'P2-6-vehicles', 'P2-8-vehicles'];
const MECHS = { marketplace: 'Marketplace', central_assign: 'Batched assignment', pooled_greedy: 'Pooled greedy', inhouse: 'In-house fleets' };
const METRICS = { delay_prio1_mean_h: ['urgent mean delay', 'h', 2], sl24_prio1: ['urgent within 24 h', '', 3], cost_per_kg_usd: ['cost per kg', 'USD/kg', 0], delivered_share: ['delivered share', '', 3] };
let api = null, me = null, version = null;

function defaultBase() {
  const env = import.meta.env.VITE_API_BASE; if (env) return env;
  return ['localhost', '127.0.0.1'].includes(location.hostname) ? `http://${location.hostname}:8800` : '';
}
const status = (m, cls = '') => { const el = $('a-status'); el.textContent = m; el.className = 'status-line ' + cls; };
const errText = e => e instanceof ApiError ? (e.code === 'quota_exceeded' || e.code === 'queue_full' ? `${e.message} (try again in ${Math.ceil((e.retryAfter || 0) / 60)} min)` : e.message) : String(e.message || e);

// ---------- connect ----------
async function connect() {
  const base = $('a-base').value.trim(); version = null; me = null;
  if (!base) { status('No service address is configured for this site yet. Enter one (for example http://localhost:8800 for a local service).'); render(); return; }
  try { new URL(base); } catch (e) { status('That is not a valid address (include http:// or https://).', 'bad'); return; }
  const keepToken = api && api.base === base.replace(/\/+$/, '') ? api.token : null;
  api = new ServiceClient(base); api.token = keepToken; store.set('lunarsim.serviceBase', base);
  status('Connecting…');
  try { version = await api.version(); }
  catch (e) { status(`Service not reachable at ${base} (${errText(e)}). The rest of the site works without it.`, 'bad'); render(); return; }
  const code = (location.hash.match(/login_code=([^&]+)/) || [])[1];
  if (code) { history.replaceState(null, '', location.pathname + location.search); try { await api.exchange(decodeURIComponent(code)); } catch (e) { status('The sign-in link expired or was already used: ' + errText(e), 'bad'); } }
  // Ask /me only when a session may exist (a 401 for every anonymous visitor would be logged as a console error):
  // a bearer token in memory, or the flag set when a sign-in was started or succeeded in this browser.
  if (api.token || store.get('lunarsim.maybeSignedIn') === '1') {
    try { me = await api.me(); store.set('lunarsim.maybeSignedIn', me && me.user ? '1' : '0'); } catch (e) { me = null; store.set('lunarsim.maybeSignedIn', '0'); }
  }
  status(`Connected to ${api.base}: engine ${version.engine_version}${version.git_dirty ? ' (uncommitted changes: runs will not rank)' : ''}, ${api.mode === 'cookie' ? 'session cookie' : 'bearer token kept in this tab'}.`, 'ok');
  render(); listMine(); gallery();
}

// ---------- rendering ----------
function render() {
  const on = !!version;
  $('a-signin').hidden = !on || !!(me && me.user); $('a-signed').hidden = !(on && me && me.user); $('a-new').hidden = !on; $('a-mine-sec').hidden = !on; $('a-gal-sec').hidden = !on;
  if (on && version.auth) {
    $('a-orcid').disabled = !version.auth.orcid; $('a-github').disabled = !version.auth.github; $('a-magic-form').hidden = !version.auth.magic_link;
    $('a-provider-note').textContent = (!version.auth.orcid || !version.auth.github) ? `Not configured on this service: ${['orcid', 'github'].filter(p => !version.auth[p]).map(p => p === 'orcid' ? 'ORCID' : 'GitHub').join(', ')}.` : '';
  }
  if (me && me.user) {
    const u = me.user, q = me.quota || {};
    $('a-who').innerHTML = `Signed in as <b>${esc(u.name || u.email || u.orcid || u.id)}</b>${u.orcid ? ` · ORCID ${esc(u.orcid)}` : ''}${u.email && u.name ? ` · ${esc(u.email)}` : ''}. Today: ${fmt(q.used_cpu_s, 0)} of ${fmt(q.limit_cpu_s, 0)} CPU-seconds.`;
  }
  $('a-public').disabled = !(me && me.user); $('a-public-note').textContent = me && me.user ? '' : '(sign in to publish)';
}
const pill = (cls, text, title = '') => `<span class="pill ${cls}" ${title ? `title="${esc(title)}"` : ''}>${esc(text)}</span>`;
function badges(r) {
  const out = [pill(r.status === 'done' ? 'pass' : r.status === 'failed' ? 'fail' : 'note', r.status)];
  if (r.replicated === true) out.push(pill('pass', 'replicated ✓', 'A re-run with identical inputs produced the same output_sha'));
  else if (r.replicated === false) out.push(pill('fail', 'replication differs', 'A re-run produced a different output_sha'));
  if (r.ranked) out.push(pill('pass', 'ranked', 'clean tagged release')); else if (r.provenance && r.provenance.git_dirty) out.push(pill('note', 'unranked: uncommitted code'));
  if (r.public) out.push(pill('note', 'public'));
  return out.join(' ');
}
function metricCells(r) {
  const m = (r.summary && r.summary.metrics) || {};
  return Object.entries(METRICS).map(([k, [lab, u, d]]) => `<td class="n">${m[k] ? num({ value: m[k].mean, unit: u, flag: 'Modelled', digits: d, source: `run ${r.run_id}, ${m[k].n} seeds, ${lab}` }) : '–'}</td>`).join('');
}
function runRow(r, own) {
  const id = r.run_id;
  return `<tr data-id="${esc(id)}"><td><a class="mono small" href="#run=${esc(id)}" data-open="${esc(id)}">${esc(id.slice(-8))}</a><div class="small muted">${esc(r.created || '')}</div></td>
    <td>${esc(r.scenario_name || r.scenario || '–')}<div class="small muted">${esc(MECHS[r.mechanism] || r.mechanism)} · ${(r.seeds || []).length} seeds</div></td>
    <td>${badges(r)}</td>${metricCells(r)}
    <td class="a-actions"><button class="btn" type="button" data-act="world" data-id="${esc(id)}" ${r.status !== 'done' ? 'disabled' : ''}>Open in World</button>
      <button class="btn" type="button" data-act="replicate" data-id="${esc(id)}" ${r.status !== 'done' ? 'disabled' : ''}>Replicate</button>
      ${own && me && me.user && r.status === 'done' && !r.anonymous ? `<button class="btn" type="button" data-act="publish" data-pub="${r.public ? 0 : 1}" data-id="${esc(id)}">${r.public ? 'Unpublish' : 'Publish'}</button>` : ''}</td></tr>`;
}
const tableHead = `<thead><tr><th>Run</th><th>Scenario</th><th>Status</th>${Object.values(METRICS).map(([l, u]) => `<th class="n">${esc(l)}${u ? ` (${esc(u)})` : ''}</th>`).join('')}<th></th></tr></thead>`;

async function listMine() {
  const host = $('a-mine');
  const anon = JSON.parse(store.get('lunarsim.anonRuns') || '[]');
  let rows = [];
  try {
    if (me && me.user) rows = (await api.runs({ limit: 50 })).runs;
    const extra = await Promise.all(anon.filter(id => !rows.some(r => r.run_id === id)).slice(0, 20).map(id => api.run(id).catch(() => null)));
    rows = rows.concat(extra.filter(Boolean));
  } catch (e) { host.innerHTML = `<p class="small bad">${esc(errText(e))}</p>`; return; }
  host.innerHTML = rows.length ? `<div class="a-scroll"><table class="w-table">${tableHead}<tbody>${rows.map(r => runRow(r, true)).join('')}</tbody></table></div>` : '<p class="small muted">No runs yet. Start one above.</p>';
}
async function gallery() {
  const host = $('a-gal'), metric = $('a-metric').value, ranked = $('a-ranked').checked ? 1 : undefined;
  try {
    const r = await api.runs({ public: 1, metric, order: metric === 'sl24_prio1' || metric === 'delivered_share' ? 'desc' : 'asc', ranked, limit: 50 });
    host.innerHTML = (r.runs.length ? `<div class="a-scroll"><table class="w-table">${tableHead}<tbody>${r.runs.map(x => runRow(x, false)).join('')}</tbody></table></div>` : '<p class="small muted">No public runs match.</p>') + `<p class="small muted">${esc(r.ranked_rule || '')}</p>`;
  } catch (e) { host.innerHTML = `<p class="small bad">${esc(errText(e))}</p>`; }
}

// ---------- new run with live progress ----------
async function submit(ev) {
  ev.preventDefault();
  if (!api || !version) { status('Connect to a service first.', 'bad'); return; }
  const n = Math.max(1, Math.min(version.limits.max_seeds, Math.floor(+$('a-seeds').value) || 1)), options = {};
  if ($('a-terrain').checked) { options.terrain = 'connecting_ridge'; options.pad_standoff_km = +$('a-standoff').value; }
  if ($('a-landing').value) options.landing_model = $('a-landing').value;
  if ($('a-plume').checked) options.plume = { keepout_km: +$('a-keepout').value, standdown_h: +$('a-standdown').value };
  if ($('a-autonomy').checked) options.autonomy_model = 'driving-v1';
  const body = { scenario: $('a-scenario').value, mechanism: $('a-mech').value, seeds: Array.from({ length: n }, (_, i) => i), options, public: $('a-public').checked && !!(me && me.user) };
  $('a-go').disabled = true; $('a-prog').hidden = false; $('a-prog').value = 0; status('Submitting…');
  try {
    const r = await api.createRun(body);
    if (!(me && me.user)) { const a = JSON.parse(store.get('lunarsim.anonRuns') || '[]'); a.unshift(r.run_id); store.set('lunarsim.anonRuns', JSON.stringify(a.slice(0, 20))); }
    status(`Queued ${r.run_id} (estimate ${fmt(r.estimate_cpu_s, 1)} CPU-s; today ${fmt(r.quota.used_cpu_s, 0)} of ${fmt(r.quota.limit_cpu_s, 0)}).`);
    await api.events(r.run_id, e => {
      if (e.event === 'queued') $('a-live').textContent = `queued, position ${e.data.position}`;
      else if (e.event === 'running') $('a-live').textContent = `running on ${e.data.worker} (engine ${e.data.engine_version})`;
      else if (e.event === 'progress') { $('a-prog').value = e.data.done / e.data.total; $('a-live').textContent = `seed ${e.data.seed} done (${e.data.done}/${e.data.total}, ${e.data.ms} ms), trace sha ${String(e.data.trace_sha).slice(0, 12)}…`; }
      else if (e.event === 'done') { $('a-live').textContent = `done · output sha ${String(e.data.output_sha || '').slice(0, 16)}…`; return false; }
      else if (e.event === 'failed') { $('a-live').textContent = `failed: ${e.data.error || ''}`; return false; }
    });
    status(`Run ${r.run_id} finished.`, 'ok'); listMine(); if (body.public) gallery();
  } catch (e) { status('Could not start the run: ' + errText(e), 'bad'); }
  $('a-go').disabled = false; $('a-prog').hidden = true;
}

// ---------- actions ----------
async function action(btn) {
  const id = btn.dataset.id, act = btn.dataset.act; btn.disabled = true;
  try {
    if (act === 'world') {
      const text = await api.trace(id); store.set('lunarsim.worldTrace', text);
      location.href = `${BASE}world/trace/?from=service&run=${encodeURIComponent(id)}`; return;
    }
    if (act === 'replicate') {
      const r = await api.replicate(id); status(`Replicating as ${r.run_id}…`);
      if (!(me && me.user)) { const a = JSON.parse(store.get('lunarsim.anonRuns') || '[]'); a.unshift(r.run_id); store.set('lunarsim.anonRuns', JSON.stringify(a.slice(0, 20))); }
      await api.events(r.run_id, e => e.event === 'done' || e.event === 'failed' ? false : undefined);
      const child = await api.run(r.run_id), parent = await api.run(id);
      status(child.replicated === true ? `Replicated: the re-run ${r.run_id} produced the same output_sha (${String(child.output_sha).slice(0, 12)}…).` : child.replicated === false ? `The re-run produced a different output: ${String(child.output_sha).slice(0, 12)}… vs ${String(parent.output_sha).slice(0, 12)}….` : 'Replication finished; no verdict recorded.', child.replicated === false ? 'bad' : 'ok');
      listMine(); gallery();
    }
    if (act === 'publish') { await api.publish(id, btn.dataset.pub === '1'); status(btn.dataset.pub === '1' ? 'Published to the gallery.' : 'Removed from the gallery.', 'ok'); listMine(); gallery(); }
  } catch (e) { status(errText(e), 'bad'); }
  btn.disabled = false;
}

function wire() {
  $('a-base').value = store.get('lunarsim.serviceBase') || defaultBase();
  $('a-connect').addEventListener('click', connect);
  $('a-base').addEventListener('keydown', e => { if (e.key === 'Enter') connect(); });
  $('a-scenario').innerHTML = SCENARIOS.map(s => `<option>${s}</option>`).join('');
  $('a-mech').innerHTML = Object.entries(MECHS).map(([k, v]) => `<option value="${k}">${v}</option>`).join('');
  $('a-metric').innerHTML = Object.entries(METRICS).map(([k, [l]]) => `<option value="${k}">${l}</option>`).join('');
  $('a-form').addEventListener('submit', submit);
  $('a-metric').addEventListener('change', gallery); $('a-ranked').addEventListener('change', gallery);
  $('a-magic-form').addEventListener('submit', async e => { e.preventDefault(); const email = $('a-email').value.trim(); if (!email) return;
    try { await api.magic(email, location.pathname); store.set('lunarsim.maybeSignedIn', '1'); status(`If ${email} can sign in, a link is on its way. Open it in this browser.`, 'ok'); } catch (err) { status(errText(err), 'bad'); } });
  for (const p of ['orcid', 'github']) $('a-' + p).addEventListener('click', () => { store.set('lunarsim.maybeSignedIn', '1'); location.href = api.providerUrl(p, location.pathname); });
  $('a-logout').addEventListener('click', async () => { try { await api.logout(); } catch (e) { /* already out */ } me = null; store.set('lunarsim.maybeSignedIn', '0'); render(); listMine(); status('Signed out.'); });
  document.addEventListener('click', e => { const b = e.target.closest('button[data-act]'); if (b) action(b); });
}
wire();
if ($('a-base').value) connect(); else { status('No service address is configured for this site yet. Runs in the simulator and the labs work without one.'); render(); }
