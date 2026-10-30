// F-53: Lunar ATC with and without the network, on one seed and one clock. B-80's trace pair (data/atc/trace_pair,
// staged unchanged to world/atc/): the month of 2028 the base sees Earth least, the status quo (each owner's control
// room on Earth) beside Lunar ATC (the robots' own auction over the mesh, shared road reservations). Two plan views
// in the sites.json frame, the clock shared; under each, four counters from the events. The window totals are
// recounted from the events by the file's own definitions and checked against its summary (a mismatch line if not).
// Loaded after a click or with ?view=atc (a lazy chunk; budgets.json variant ?view=atc).
import { h } from '../ui/index.js';
import { createTimescale, hoursText } from '../ui/timescale.js';
import { OWNER_COLOURS, themedVar } from './colours.js';

const NS = 'http://www.w3.org/2000/svg';
const OWN = { A: OWNER_COLOURS.CoA, B: OWNER_COLOURS.CoB, C: themedVar(OWNER_COLOURS.CoC) };
const KIND = { drive: 'driving', reposition: 'driving empty', work: 'loading or unloading', wait_segment: 'held before a one-lane road',
  wait_apron: 'waiting for a pad slot', hand: 'waiting for Earth to settle a road conflict', crew_slow: 'slowed for crew', idle: 'idle' };
const COUNTERS = [['urgent_items_waiting', 'Urgent items waiting over 24 h', 0], ['idle_robot_hours', 'Hours robots sat idle', 1],
  ['messages_per_hour', 'Radio messages per hour', 2], ['earth_hand_hours', 'Hours of road conflicts settled by hand via Earth', 2]];
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const fmt = (v, d = 0) => v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const clock = t => { const d = new Date(Date.UTC(2028, 0, 1) + t * 3600e3); return `${d.getUTCDate()} ${MON[d.getUTCMonth()]} ${d.getUTCFullYear()}, ${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')} UTC`; };
const s = (tag, attrs = {}) => { const el = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v); return el; };
const clip = (a, b, t0, t1) => Math.max(0, Math.min(b, t1) - Math.max(a, t0));
const last = (arr, t, key = r => r[0]) => { let lo = 0, hi = arr.length - 1, k = -1; while (lo <= hi) { const m = (lo + hi) >> 1; if (key(arr[m]) <= t) { k = m; lo = m + 1; } else hi = m - 1; } return k; };

// a .json.gz as served raw (checked by size and sha256 against the index) or already unpacked by the server
async function readRun(dir, m) {
  const r = await fetch(dir + m.file); if (!r.ok) throw new Error(`${m.file}: HTTP ${r.status}`);
  let u8 = new Uint8Array(await r.arrayBuffer()), check;
  if (u8[0] === 0x1f && u8[1] === 0x8b) {
    if (u8.length !== m.bytes) throw new Error(`${m.file}: ${u8.length} bytes, the index says ${m.bytes}`);
    const sha = crypto.subtle && [...new Uint8Array(await crypto.subtle.digest('SHA-256', u8))].map(b => b.toString(16).padStart(2, '0')).join('');
    if (sha && sha !== m.sha256) throw new Error(`${m.file}: sha256 differs from the index`);
    check = `${fmt(u8.length)} bytes${sha ? ', sha256 as in the index' : ''}`;
    u8 = new Uint8Array(await new Response(new Blob([u8]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer());
  } else {
    if (u8.length !== m.bytes_json) throw new Error(`${m.file}: ${u8.length} bytes unpacked, the index says ${m.bytes_json}`);
    check = `served unpacked, ${fmt(u8.length)} bytes as in the index`;
  }
  return { d: JSON.parse(new TextDecoder().decode(u8)), check };
}

// one run, ready to ask "where is everything at hour t"
function prep(d) {
  const [t0, t1] = d.window_h, W = t1 - t0, S = d.sites, E = d.roads.edges, ids = d.fleet.map(f => f[0]);
  const legs = ids.map(id => (d.legs[id] || []).slice().sort((a, b) => a[0] - b[0]));
  const along = (e, f) => { const p = E[e], x = f * (p.length - 1), i = Math.max(0, Math.min(p.length - 2, Math.floor(x))), u = x - i; return [p[i][0] + (p[i + 1][0] - p[i][0]) * u, p[i][1] + (p[i + 1][1] - p[i][1]) * u]; };
  const pieces = {};   // resource id -> SVG path of its one-lane pieces
  for (const [e, p] of Object.entries(E)) { const r = d.roads.res[e] || []; for (let i = 1; i < p.length; i++) if (r[i] !== -1 && r[i] === r[i - 1]) pieces[r[i]] = (pieces[r[i]] || '') + `M${p[i - 1][0]} ${-p[i - 1][1]}L${p[i][0]} ${-p[i][1]}`; }
  function where(v, t) {
    const L = legs[v], k = last(L, t);
    if (!L.length) return null;
    if (k < 0) { const l = L[0]; return { at: l[7] ? along(l[7][0], l[7][1]) : S[l[2]], kind: 'idle' }; }
    const l = L[k], e = l[7];
    if (t < l[1]) return { at: e ? along(e[0], e[1] + (e[2] - e[1]) * (t - l[0]) / Math.max(1e-9, l[1] - l[0])) : S[l[2]], kind: l[4], load: l[5], moving: !!e && e[1] !== e[2] };
    return { at: e ? along(e[0], e[2]) : S[l[3]], kind: 'idle' };
  }
  const merged = legs.map(L => { const out = []; for (const [a, b] of L.map(l => [Math.max(l[0], t0), Math.min(l[1], t1)]).filter(([a, b]) => b > a)) { const c = out[out.length - 1]; if (c && a <= c[1]) c[1] = Math.max(c[1], b); else out.push([a, b]); } return out; });
  const hand = legs.flat().filter(l => l[4] === 'hand');
  const radio = []; let cur = new Map();
  const key = l => l.map(String).sort().join();
  for (const r of d.radio) {
    if (r.length === 4) { cur = new Map(r[1].map(l => [key(l), l])); radio.push({ t: r[0], links: [...cur.values()], lost: [], hops: r[2], up: r[3] }); continue; }
    for (const l of r[2]) cur.delete(key(l)); for (const l of r[1]) cur.set(key(l), l);
    radio.push({ t: r[0], links: [...cur.values()], lost: r[2], hops: r[3], up: r[4] });
  }
  // the counters up to hour t: urgent items waiting now, and idle hours, messages per hour and hand hours so far
  const at = t => {
    const busy = merged.reduce((a, iv) => a + iv.reduce((b, [x, y]) => b + clip(x, y, t0, t), 0), 0), span = Math.max(t - t0, 1e-9);
    return { urgent_items_waiting: d.items.filter(it => it[4] === 1 && it[7] <= t && (it[8] ?? Infinity) > t).length,
      idle_robot_hours: ids.length * (t - t0) - busy, messages_per_hour: d.msgs.filter(m => m[0] < t).reduce((a, m) => a + m[1], 0) / span,
      earth_hand_hours: hand.reduce((a, l) => a + clip(l[0], l[1], t0, t), 0) };
  };
  // the window totals by the file's own definitions (fields.summary)
  const totals = { ...at(t1), messages_per_hour: d.msgs.reduce((a, m) => a + m[1], 0) / W,
    urgent_items_waiting: d.items.filter(it => it[4] === 1 && t0 <= it[7] && it[7] <= t1 && (it[8] ?? t1) - it[7] > 24).length };
  return { d, t0, t1, ids, legs, where, pieces, radio, at, totals, still: ids.filter((_, v) => !legs[v].length) };
}

function describe(dec, fleet) {
  const [, kind, x] = dec, veh = v => (v || []).map(i => `${fleet[i][2].replace(/_/g, ' ')} ${i}`).join(' and ');
  if (kind === 'award') return `Auction won by ${veh(x.vehicles)}${x.note === 'team' ? ' (a team lift)' : ''} for ${x.items.length} item${x.items.length === 1 ? '' : 's'}`;
  if (kind === 'assignment') return `Owner ${x.owner}’s control room on Earth sent ${veh(x.vehicles)} for ${x.items.length} item${x.items.length === 1 ? '' : 's'}`;
  if (kind === 'hand_referral') return `${veh([x.vehicle])} waited ${fmt(x.wait_h, 1)} h for Earth to settle a conflict on road ${x.resource}`;
  if (kind === 'rally') return `Team meeting at ${x.site.replace('_', ' ')} for ${veh(x.vehicles)} (gives up after ${fmt(x.timeout_h, 1)} h)`;
  return `${kind.replace(/_/g, ' ')}${typeof x === 'number' ? ` (${x})` : ''}`;
}

function panel(R, title) {
  const d = R.d, xs = Object.values(d.sites).map(p => p[0]).concat(Object.values(d.roads.edges).flat().map(p => p[0]));
  const ys = Object.values(d.sites).map(p => p[1]).concat(Object.values(d.roads.edges).flat().map(p => p[1])), pad = 250;
  const x0 = Math.min(...xs) - pad, y1 = Math.max(...ys) + pad, w = Math.max(...xs) + pad - x0, hgt = y1 - Math.min(...ys) + pad;
  const svg = s('svg', { viewBox: `${x0} ${-y1} ${w} ${hgt}`, class: 'ap-map', role: 'img', 'aria-label': `Plan of the base: ${title}` });
  const g = n => svg.appendChild(s('g', { class: n }));
  const roads = g('ap-roads'), res = g('ap-res'), zones = g('ap-zones'), links = g('ap-links'), team = g('ap-team'), sites = g('ap-sites'), vehs = g('ap-vehs');
  for (const p of Object.values(d.roads.edges)) roads.append(s('path', { d: p.map((q, i) => `${i ? 'L' : 'M'}${q[0]} ${-q[1]}`).join('') }));
  for (const p of Object.values(R.pieces)) roads.append(s('path', { d: p, class: 'one-lane' }));
  for (const [x, y] of d.roads.bays) roads.append(s('circle', { cx: x, cy: -y, r: 22, class: 'bay' }));
  for (const [n, [x, y]] of Object.entries(d.sites)) {
    sites.append(s('circle', { cx: x, cy: -y, r: n === 'BASE' ? 45 : 30 }));
    sites.append(Object.assign(s('text', { x: x + 60, y: -y - 50 }), { textContent: n.replace('_', ' ') }));
  }
  const dots = R.ids.map(v => vehs.appendChild(s('circle', { r: 55, fill: OWN[d.fleet[v][1]] || 'var(--ink)' })));
  const pos = v => (v === 'BASE' ? d.nodes.BASE : R.cur[v]?.at);
  const earth = h('span', { class: 'ap-earth' }), closed = h('span', { class: 'ap-earth ap-closed', hidden: true }), line = h('p', { class: 'ap-dec small' }), dl = h('dl', { class: 'w2-dl ap-cnt' }), now = h('p', { class: 'ap-now small muted' });
  const el = h('figure', { class: 'ap-run' }, h('figcaption', {}, h('strong', {}, title), h('span', { class: 'ap-chips' }, closed, earth)), svg, line, now, dl);
  function draw(t) {
    R.cur = R.ids.map(v => R.where(v, t));
    R.cur.forEach((c, v) => {
      const dot = dots[v]; if (!c) { dot.setAttribute('display', 'none'); return; }
      const off = c.moving ? [0, 0] : [Math.cos(v * 0.8) * 70, Math.sin(v * 0.8) * 70];
      dot.removeAttribute('display'); dot.setAttribute('cx', c.at[0] + off[0]); dot.setAttribute('cy', -c.at[1] - off[1]); dot.setAttribute('class', `k-${c.kind}`);
    });
    res.replaceChildren(...d.reservations.filter(r => r[1] <= t && t < r[2]).map(r => String(r[0]).startsWith('apron:')
      ? s('circle', { cx: d.sites[r[0].slice(6)][0], cy: -d.sites[r[0].slice(6)][1], r: 110, stroke: OWN[r[4]], class: 'apron' })
      : s('path', { d: R.pieces[r[0]] || '', stroke: OWN[r[4]] })));
    const zs = [], shut = [];
    for (const [a, b, pad, km] of d.closures) if (a <= t && t < b) { const [x, y] = d.sites[pad]; zs.push(s('circle', { cx: x, cy: -y, r: km * 1000, class: 'closure' })); shut.push(`${pad.replace('_', ' ')} closed for a landing, opens in ${hoursText(b - t)}`); }
    closed.textContent = shut.join('; '); closed.hidden = !shut.length;
    for (const [a, b, site, km] of d.crew) if (a <= t && t < b) { const [x, y] = d.sites[site]; zs.push(s('circle', { cx: x, cy: -y, r: Math.max(km * 1000, 90), class: 'crew' })); }
    for (const [tr, kind, x] of d.decisions) if (kind === 'rally' && tr <= t && t < tr + x.timeout_h && d.sites[x.site]) { const [sx, sy] = d.sites[x.site]; zs.push(s('circle', { cx: sx, cy: -sy, r: 160, class: 'rally' })); }
    zones.replaceChildren(...zs);
    const rk = last(R.radio, t, r => r.t), rs = R.radio[Math.max(0, rk)] || { t: 0, links: [], lost: [], hops: [] }, seg = (a, b, cls) => { const p = pos(a), q = pos(b); return p && q ? s('line', { x1: p[0], y1: -p[1], x2: q[0], y2: -q[1], class: cls }) : null; };
    links.replaceChildren(...rs.links.map(([a, b]) => seg(a, b, 'up')).concat(rk >= 0 && t - rs.t < 1 ? rs.lost.map(([a, b]) => seg(a, b, 'lost')) : []).filter(Boolean));
    team.replaceChildren(...d.jobs.filter(j => j[5] === 'team' && j[1] <= t && t < j[2] && j[3].length > 1).map(j => seg(j[3][0], j[3][1], 'team')).filter(Boolean));
    const ew = d.earth.find(([a, b]) => a <= t && t < b), next = d.earth.find(([a]) => a > t);
    earth.textContent = ew ? 'Earth in view' : next ? `Earth hidden for ${hoursText(next[0] - t)} more` : 'Earth hidden';
    earth.className = `ap-earth ${ew ? 'up' : 'down'}`;
    const k = last(d.decisions, t); line.textContent = k >= 0 ? `${clock(d.decisions[k][0]).replace(' 2028', '')}: ${describe(d.decisions[k], d.fleet)}` : 'No decision yet this month.';
    const by = {}; R.cur.forEach(c => { if (c) by[c.kind] = (by[c.kind] || 0) + 1; });
    const cut = rs.hops.filter(x => x < 0).length;
    now.textContent = `Now: ${Object.entries(by).map(([k2, n]) => `${n} ${KIND[k2] || k2}`).join(', ')}; ${cut} of ${rs.hops.length} out of radio reach of the base${R.still.length ? `; not moved this month: ${R.still.map(v => `${d.fleet[v][2].replace(/_/g, ' ')} ${v}`).join(', ')}` : ''}.`;
    const c = R.at(t);
    dl.replaceChildren(...COUNTERS.flatMap(([kk, label, dg]) => [h('dt', {}, kk === 'urgent_items_waiting' ? 'Urgent items waiting now' : `${label}, so far`), h('dd', {}, fmt(c[kk], dg))]));
  }
  return { el, draw };
}

export async function mount(root, BASE) {
  const dir = BASE + 'world/atc/';
  const ir = await fetch(dir + 'index.json'); if (!ir.ok || !/json/.test(ir.headers.get('content-type') || '')) throw new Error(`world/atc/index.json: HTTP ${ir.status}`);
  const ix = await ir.json(); if (ix.format !== 'lunarsim-atc-trace' || ix.version !== 1) throw new Error(`index.json: format ${ix.format} version ${ix.version}`);
  const order = ['without', 'with'], got = await Promise.all(order.map(n => readRun(dir, ix.runs[n])));
  const R = got.map(g => prep(g.d)), [t0, t1] = [ix.window.t0_h, ix.window.t1_h];
  const P = [panel(R[0], 'Without the network: control rooms on Earth'), panel(R[1], 'With the network: Lunar ATC')];
  let t = t0, playing = false, prev = 0;
  const range = h('input', { type: 'range', min: t0, max: t1, step: 0.1, value: t0, class: 'ap-range', 'aria-label': 'Time in the month' });
  const when = h('span', { class: 'ap-clock' }), play = h('button', { type: 'button', class: 'ui-btn primary' }, 'Play');
  const ts = createTimescale({ speeds: [900, 3600, 21600, 86400], value: 21600, keys: false, url: false });
  const set = v => { t = Math.min(t1, Math.max(t0, v)); range.value = t; when.textContent = clock(t); P.forEach(p => p.draw(t)); };
  const loop = now => { if (!playing) return; set(t + (now - prev) / 1000 * ts.h); prev = now; if (t >= t1) { playing = false; play.textContent = 'Play'; } else requestAnimationFrame(loop); };
  play.addEventListener('click', () => { playing = !playing; play.textContent = playing ? 'Pause' : 'Play'; if (playing) { if (t >= t1) set(t0); prev = performance.now(); requestAnimationFrame(loop); } });
  range.addEventListener('input', () => set(+range.value));
  // the window totals: recounted here from the events, beside the file's own summary
  const S = order.map(n => ix.runs[n].summary), bad = [];
  const rows = COUNTERS.map(([k, label, dg]) => h('tr', {}, h('th', { scope: 'row' }, label), ...R.flatMap((r, i) => {
    const mine = r.totals[k], ok = Math.abs(mine - S[i][k]) <= (dg ? 0.5 * 10 ** -dg + 1e-9 : 0);
    if (!ok) bad.push(`${order[i]}: ${label.toLowerCase()} recounts to ${fmt(mine, dg)}, the file says ${fmt(S[i][k], dg)}`);
    return [h('td', { class: 'n' }, fmt(mine, dg))];
  })));
  root.replaceChildren(
    h('div', { class: 'ap-ctl ui-glass' }, play, ts.el, range, when),
    h('div', { class: 'ap-pair' }, ...P.map(p => p.el)),
    h('p', { class: 'small muted' }, 'Owner colours: A red, B green, C yellow. Thick coloured road: a one-lane piece held by that owner’s robot; dashed: one-lane road; small rings: passing bays. Thin lines: radio links (dashed: just lost). A yellow ring round a pad: closed for a landing; a dashed ring: a crew walk; a large ring: a team-lift meeting point.'),
    h('table', { class: 'w2-table ap-tot' }, h('caption', {}, `${ix.window.name} ${ix.year}, the whole month: recounted from the events`),
      h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, ''), ...order.map(n => h('th', { scope: 'col' }, n === 'with' ? 'With the network' : 'Without')))), h('tbody', {}, rows)),
    bad.length ? h('p', { class: 'ap-bad', role: 'alert' }, `These do not match the file’s own totals: ${bad.join('; ')}.`) : h('p', { class: 'small' }, 'Every total above equals the window total the file states (meta summary).'),
    h('p', { class: 'small muted' }, `Same seed (${ix.seed}), same cargo and landings, ${ix.window.name} ${ix.year} (the base sees Earth ${fmt(ix.window.base_dte_share * 100, 1)} % of that month, the least of the year). Files: ${order.map((n, i) => `${ix.runs[n].file} (${got[i].check})`).join('; ')}; built at commit ${ix.commit.slice(0, 7)}. Positions are along each road leg, linear in time.`));
  set(t0);
}
