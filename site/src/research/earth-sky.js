// /research/earth-sky/ (F-41): why 2028 is different (R-1 round 2, B-55). Three light SVG figures, each with a table twin:
// (1) Earth's path in the base's sky by month and year (data/comms/connecting_ridge/earth_track-v1.json.gz, SPICE) with
// the patch of sky where the dark route point saw Earth; (2) the monthly link calendar of that point and three sites;
// (3) the stranded share of the fleet by month, 2028 against 2030, and the tonnage by start year
// (results/E21_strategic_years.json). Every number is read from those files. No claim about which rover rule is best.
import { statChip, segmented } from '../ui/index.js';
import { upgradeFlags } from '../ui/tooltip.js';
import { num, esc } from '../components/num.js';
import './earth-sky.css';

const BASE = import.meta.env.BASE_URL, $ = id => document.getElementById(id);
const TRACK = 'data/comms/connecting_ridge/earth_track-v1.json.gz', SY = 'results/E21_strategic_years.json', YR = 'results/table_E21_years_r2.csv';
const YEARS = [2028, 2029, 2030, 2031], MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const ui = { year: 2028, month: 1 };
const f1 = v => v.toFixed(1), pct = v => Math.round(v * 100);
const monthLabel = s => { const [y, m] = s.split('-'); return `${MON[+m - 1]} ${y}`; };

// a .json.gz as served raw (GitHub Pages) or already decoded by the server (Content-Encoding: gzip, vite preview)
async function gunzipJson(url) {
  const r = await fetch(url); if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  let buf = new Uint8Array(await r.arrayBuffer());
  if (buf[0] === 0x1f && buf[1] === 0x8b) buf = new Uint8Array(await new Response(new Blob([buf]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer());
  return JSON.parse(new TextDecoder().decode(buf));
}

let track = null, sy = null, dy = null;
try {
  [track, sy, dy] = await Promise.all([gunzipJson(BASE + 'comms/earth_track-v1.json.gz'), fetch(BASE + 'research/earth-sky/strategic-years.json').then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
    fetch(BASE + 'research/earth-sky/deliveries-by-year.json').then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })]);
} catch (e) { $('es-lead').textContent = `The data could not load (${e.message}).`; throw e; }

// ---------- the numbers ----------
const spot = sy.stranding_2028_top_samples[0], sky = sy.sky.samples[String(spot.sample)], months = sy.calendar.months;
const firstLink = spot.monthly_linked_2028_2031.findIndex(v => v > 0);
const darkFrom = monthLabel(months[0]), darkTo = monthLabel(months[firstLink - 1]);
const s28 = sy.stranding['2028'], shareAtSpot = spot.stranded_rover_hours / (s28.stranded_rover_hours_per_run * s28.runs);
const leg = sy.stranding_2028_top_legs[0].leg, [legA, legB] = leg.split('->');
const t = y => sy.e21_by_start_year[String(y)].delivered_t_in_year;
// the strict fleet (drives only while linked) with the same direct links, by start year: its range over the four skies
const strict = YEARS.map(y => dy.by_mix.supervised_strict[String(y)].mean), sLo = Math.min(...strict), sHi = Math.max(...strict);
const SRC = {
  dark: `${SY} → stranding_2028_top_samples[0].monthly_linked_2028_2031 (route point ${spot.sample}); SPICE + LOLA link series (earth_link-v1)`,
  share: `${SY} → stranding_2028_top_samples[0].stranded_rover_hours / (stranding.2028.stranded_rover_hours_per_run × runs)`,
  tons: y => `${SY} → e21_by_start_year.${y}.delivered_t_in_year (all supervised, strategic, direct links only; mean of ${sy.e21_by_start_year[String(y)].n} runs)`,
  strict: `${YR}, rows comms = dte, mix = supervised_strict, metric = delivered_t_in_year, start years 2028-2031 (means of ${dy.by_mix.supervised_strict['2028'].n} runs each)`,
};
$('es-lead').innerHTML = `The dark spot, route point ${spot.sample} on the haul between ${esc(legA)} and ${esc(legB)}, saw Earth at no hour from ${darkFrom} to ${darkTo}. ` +
  `In 2028 rovers waiting there held ${num({ value: 100 * shareAtSpot, unit: '%', flag: 'Modelled', digits: 0, source: SRC.share })} of the fleet's stranded rover-hours. ` +
  `With direct links only, rovers allowed to drive out of Earth's sight delivered ${num({ value: t(2028), unit: 't', flag: 'Modelled', digits: 0, source: SRC.tons(2028) })} in a year under the 2028 sky, against ${num({ value: t(2030), unit: 't', flag: 'Modelled', digits: 0, source: SRC.tons(2030) })} under the 2030 sky; ` +
  `rovers that drive only while linked delivered ${num({ value: sLo, unit: 't', flag: 'Modelled', digits: 0, source: SRC.strict })} to ${num({ value: sHi, unit: 't', flag: 'Modelled', digits: 0, source: SRC.strict })} whatever the year.`;
upgradeFlags($('es-lead'));
$('es-chips').append(
  statChip({ label: 'No link at the dark spot', text: `${darkFrom} – ${darkTo}`, flag: 'Modelled', source: SRC.dark, tone: 'warm' }).el,
  statChip({ label: "Its share of 2028's stranded rover-hours", value: 100 * shareAtSpot, unit: '%', digits: 0, flag: 'Modelled', source: SRC.share }).el,
  statChip({ label: 'Strategic fleet, 2028 sky', value: t(2028), unit: 't', digits: 0, flag: 'Modelled', source: SRC.tons(2028), tone: 'warm' }).el,
  statChip({ label: 'Strategic fleet, 2030 sky', value: t(2030), unit: 't', digits: 0, flag: 'Modelled', source: SRC.tons(2030), tone: 'cool' }).el,
  statChip({ label: 'Strict fleet, any of the four skies', text: `${Math.round(sLo)}–${Math.round(sHi)} t`, flag: 'Modelled', source: SRC.strict }).el);

// ---------- 1. Earth's path in the sky ----------
const t0 = Date.UTC(2028, 0, 1), hourOf = (y, m) => (Date.UTC(y, m - 1, 1) - t0) / 3.6e6;
const box = { b0: sky.bearing_deg_when_linked[0], b1: sky.bearing_deg_when_linked[2], e0: sky.elevation_deg_when_linked[0], e1: sky.elevation_deg_when_linked[1] };
function monthPath(y, m) {
  const a = hourOf(y, m), b = hourOf(m === 12 ? y + 1 : y, m === 12 ? 1 : m + 1), pts = [];
  let top = { e: -99, b: 0 }, inBox = 0, above = 0;
  for (let i = a; i < b; i++) {
    const e = track.elevation_cdeg[i] / 100, g = track.grid_bearing_cdeg[i] / 100;
    pts.push(e >= 0 ? [g, e] : null);
    if (e > top.e) top = { e, b: g };
    if (e >= 0) above++;
    if (g >= box.b0 && g <= box.b1 && e >= box.e0 && e <= box.e1) inBox++;
  }
  return { pts, top, inBox, above: above / (b - a) };
}
$('es-year').append(segmented({ legend: 'Year to bring forward', options: YEARS.map(y => ({ value: String(y), label: String(y) })), value: String(ui.year),
  onChange: v => { ui.year = +v; drawSky(); } }).el);
$('es-month').addEventListener('input', e => { ui.month = +e.target.value; $('es-month-out').textContent = MON[ui.month - 1]; drawSky(); });

function axes({ W, H, L, R, T, B, x, y, xt, yt, xl, yl }) {
  let s = '';
  for (const v of xt) s += `<line class="g" x1="${x(v)}" x2="${x(v)}" y1="${T}" y2="${H - B}"/><text class="t" x="${x(v)}" y="${H - B + 14}" text-anchor="middle">${v}</text>`;
  for (const v of yt) s += `<line class="g" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text class="t" x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${v}</text>`;
  if (xl) s += `<text class="t u" x="${(L + W - R) / 2}" y="${H - 6}" text-anchor="middle">${xl}</text>`;
  if (yl) s += `<text class="t u" x="12" y="${(T + H - B) / 2}" text-anchor="middle" transform="rotate(-90 12 ${(T + H - B) / 2})">${yl}</text>`;
  return s;
}
const width = id => Math.max(300, Math.round($(id).clientWidth) || 600);
function drawSky() {
  const W = width('es-sky'), H = Math.round(Math.min(420, Math.max(260, W * 0.52))), L = 44, R = 14, T = 14, B = 44;
  const x = v => (L + (v + 9) / 18 * (W - L - R)).toFixed(1), y = v => (T + (1 - v / 7) * (H - T - B)).toFixed(1);
  const paths = YEARS.map(yr => ({ yr, ...monthPath(yr, ui.month) }));
  const line = pts => { let d = '', pen = false; for (const p of pts) { if (!p) { pen = false; continue; } d += `${pen ? 'L' : 'M'}${x(p[0])},${y(p[1])}`; pen = true; } return d; };
  const order = [...paths.filter(p => p.yr !== ui.year), ...paths.filter(p => p.yr === ui.year)];
  let svg = axes({ W, H, L, R, T, B, x, y, xt: [-9, -6, -3, 0, 3, 6, 9], yt: [0, 1, 2, 3, 4, 5, 6, 7], xl: 'grid bearing (°): ← west of grid north · east →', yl: 'height above the horizontal (°)' });
  svg += `<line class="north" x1="${x(0)}" x2="${x(0)}" y1="${T}" y2="${H - B}"/>`;
  svg += `<rect class="box" x="${x(box.b0)}" y="${y(box.e1)}" width="${(x(box.b1) - x(box.b0)).toFixed(1)}" height="${(y(box.e0) - y(box.e1)).toFixed(1)}"/>` +
    `<text class="lab" x="${x(box.b1)}" y="${(+y(box.e0) + 15).toFixed(1)}" text-anchor="end">the dark spot has seen Earth only here</text>`;
  // direct labels at each year's highest point, nudged up when two would overlap
  const labs = paths.filter(p => p.top.e >= 0).map(p => ({ yr: p.yr, x: +x(p.top.b), y: +y(p.top.e) - 5 })).sort((a, b) => a.x - b.x);
  for (let i = 1; i < labs.length; i++) for (let j = 0; j < i; j++) if (Math.abs(labs[i].x - labs[j].x) < 34 && Math.abs(labs[i].y - labs[j].y) < 13) labs[i].y = labs[j].y - 13;
  const labAt = Object.fromEntries(labs.map(l => [l.yr, l]));
  for (const p of order) {
    const on = p.yr === ui.year;
    svg += `<path class="trk y${p.yr}${on ? ' on' : ''}" d="${line(p.pts)}"><title>${p.yr}, ${MON[ui.month - 1]}: highest ${f1(p.top.e)}° at bearing ${f1(p.top.b)}°${p.inBox ? `; ${p.inBox} h in the patch` : '; never in the patch'}</title></path>`;
    if (labAt[p.yr]) svg += `<text class="dl y${p.yr}${on ? ' on' : ''}" x="${labAt[p.yr].x.toFixed(1)}" y="${labAt[p.yr].y.toFixed(1)}" text-anchor="middle">${p.yr}</text>`;
  }
  const me = paths.find(p => p.yr === ui.year);
  $('es-sky').innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Earth's path in the base's sky, ${MON[ui.month - 1]} of each year 2028 to 2031. ${esc(paths.map(p => `${p.yr}: highest ${f1(p.top.e)} degrees at bearing ${f1(p.top.b)}, ${p.inBox ? 'enters' : 'never enters'} the patch where the dark spot has seen Earth`).join('; '))}.">${svg}</svg>` +
    `<p class="es-legend">${YEARS.map(yr => `<span><i class="y${yr}"></i>${yr}</span>`).join('')}<span><i class="boxkey"></i>where the dark spot saw Earth (2029–31)</span></p>`;
  $('es-sky-cap').textContent = `${MON[ui.month - 1]} ${ui.year}: Earth climbs to ${f1(me.top.e)}° at a bearing of ${f1(me.top.b)}° and ${me.inBox ? 'enters' : 'stays out of'} the patch of sky where the dark spot has seen Earth. Being in the patch is needed, not enough: the terrain's outline decides (it follows from BACKEND). ` +
    `Earth's centre seen from BASE at ground level (SPICE, ${TRACK}); the patch spans the bearings ${f1(box.b0)}° to ${f1(box.b1)}° and heights ${box.e0}° to ${box.e1}° of every hour the spot saw Earth (${SY} → sky.samples.${spot.sample}).`;
  $('es-sky-table').innerHTML = `<table class="es-table"><caption>${MON[ui.month - 1]}, each year (from the hourly track)</caption><thead><tr><th scope="col">Year</th><th scope="col">Highest</th><th scope="col">Bearing there</th><th scope="col">Hours above the horizontal</th><th scope="col">Hours in that patch</th></tr></thead><tbody>` +
    paths.map(p => `<tr><th scope="row">${p.yr}</th><td class="mono">${f1(p.top.e)}°</td><td class="mono">${f1(p.top.b)}°</td><td class="mono">${pct(p.above)} %</td><td>${p.inBox ? `${p.inBox} h` : 'never'}</td></tr>`).join('') + '</tbody></table>';
}

// ---------- 2. the calendar ----------
const PLACES = [{ key: 'spot', label: `Dark spot (point ${spot.sample})`, v: spot.monthly_linked_2028_2031 }, ...['BASE', 'CONSTR', 'ISRU'].map(k => ({ key: k, label: k, v: sy.calendar.places_linked_fraction[k] }))];
const VMAX = Math.max(...PLACES.flatMap(p => p.v));
function drawCal() {
  const W = width('es-cal'), cols = W >= 760 ? 2 : 1, gap = 24, pw = Math.floor((W - gap * (cols - 1)) / cols), c = Math.min(26, Math.floor((pw - 40) / 12)), h = c;
  const one = p => {
    let s = '';
    MON.forEach((m, i) => { s += `<text class="t" x="${40 + i * c + c / 2}" y="12" text-anchor="middle">${m[0]}</text>`; });
    YEARS.forEach((yr, r) => {
      s += `<text class="t" x="34" y="${20 + r * h + h / 2 + 4}" text-anchor="end">${yr}</text>`;
      MON.forEach((m, i) => {
        const v = p.v[r * 12 + i], k = Math.sqrt(v / VMAX) * 100;
        s += `<rect class="${v > 0 ? 'cell' : 'cell none'}" x="${40 + i * c + 1}" y="${20 + r * h + 1}" width="${c - 2}" height="${h - 2}"${v > 0 ? ` style="fill: color-mix(in oklab, var(--cal-hi) ${k.toFixed(0)}%, var(--cal-lo))"` : ''}><title>${esc(p.label)}, ${m} ${yr}: ${v > 0 ? pct(v) + ' % of hours linked' : 'no link'}</title></rect>`;
      });
    });
    const H = 20 + 4 * h + 4;
    return `<figure class="es-cal1"><figcaption class="es-cal-name">${esc(p.label)}</figcaption><svg viewBox="0 0 ${40 + 12 * c} ${H}" width="${40 + 12 * c}" height="${H}" role="img" aria-label="${esc(p.label)}: months with no link: ${p.v.filter(v => v === 0).length} of 48.">${s}</svg></figure>`;
  };
  $('es-cal').innerHTML = `<div class="es-cal-grid" style="--cols:${cols}">${PLACES.map(one).join('')}</div>` +
    `<p class="es-legend"><span><i class="cal0"></i>no link</span>${[0.05, 0.2, 0.4, VMAX].map(v => `<span><i style="background: color-mix(in oklab, var(--cal-hi) ${(Math.sqrt(v / VMAX) * 100).toFixed(0)}%, var(--cal-lo))"></i>${pct(v)} %</span>`).join('')}</p>`;
  $('es-cal-cap').textContent = `Share of each month's hours with some of Earth's disc above the terrain for a 2.5 m antenna (${SY} → calendar.places_linked_fraction and stranding_2028_top_samples[0].monthly_linked_2028_2031). ISRU never sees Earth. The leg ${leg} as a whole will be added with BACKEND's next export.`;
  $('es-cal-table').innerHTML = `<div class="es-scroll"><table class="es-table"><thead><tr><th scope="col">Month</th>${PLACES.map(p => `<th scope="col">${esc(p.label)}</th>`).join('')}</tr></thead><tbody>` +
    months.map((m, i) => `<tr><th scope="row">${monthLabel(m)}</th>${PLACES.map(p => `<td class="mono">${p.v[i] > 0 ? pct(p.v[i]) + ' %' : 'none'}</td>`).join('')}</tr>`).join('') + '</tbody></table></div>';
}

// ---------- 3. the fleet ----------
const SHARE = { 2028: sy.stranding['2028'].stranded_fleet_share_by_month, 2030: sy.stranding['2030'].stranded_fleet_share_by_month };
function drawFleet() {
  const W = width('es-fleet'), H = Math.round(Math.min(320, Math.max(220, W * 0.6))), L = 40, R = 40, T = 12, B = 34;
  const x = i => (L + i / 11 * (W - L - R)).toFixed(1), y = v => (T + (1 - v) * (H - T - B)).toFixed(1);
  let s = axes({ W, H, L, R, T, B, x: i => x(i), y, xt: [], yt: [], xl: '', yl: '' });
  for (const v of [0, 0.25, 0.5, 0.75, 1]) s += `<line class="g" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text class="t" x="${L - 6}" y="${+y(v) + 4}" text-anchor="end">${v * 100}%</text>`;
  MON.forEach((m, i) => { if (i % (W < 420 ? 2 : 1) === 0) s += `<text class="t" x="${x(i)}" y="${H - B + 14}" text-anchor="middle">${m}</text>`; });
  for (const yr of [2028, 2030]) {
    const v = SHARE[yr];
    s += `<path class="trk on y${yr}" d="${v.map((q, i) => `${i ? 'L' : 'M'}${x(i)},${y(q)}`).join('')}"/>` +
      v.map((q, i) => `<circle class="pt y${yr}" cx="${x(i)}" cy="${y(q)}" r="4"><title>${yr} sky, ${MON[i]}: ${pct(q)} % of the fleet stuck more than a day</title></circle>`).join('') +
      `<text class="dl on y${yr}" x="${+x(11) + 6}" y="${+y(v[11]) + 4}">${yr}</text>`;
  }
  $('es-fleet').innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Share of the rover fleet stuck waiting more than a day, by month. 2028 sky: ${SHARE[2028].map(pct).join(', ')} percent. 2030 sky: ${SHARE[2030].map(pct).join(', ')} percent.">${s}</svg>`;
  $('es-fleet-cap').textContent = `Share of the fleet stranded (an intervention wait over 24 h), by month; mean of ${sy.stranding['2028'].runs} seeds with the same demand (${SY} → stranding.<year>.stranded_fleet_share_by_month).`;
  // tonnage by start year
  const W2 = width('es-tons'), H2 = H, L2 = 44, R2 = 10, T2 = 26, max = Math.ceil(Math.max(...YEARS.map(t)) / 100) * 100, bw = (W2 - L2 - R2) / YEARS.length;
  const y2 = v => (T2 + (1 - v / max) * (H2 - T2 - B)).toFixed(1);
  let s2 = '';
  for (let v = 0; v <= max; v += 200) s2 += `<line class="g" x1="${L2}" x2="${W2 - R2}" y1="${y2(v)}" y2="${y2(v)}"/><text class="t" x="${L2 - 6}" y="${+y2(v) + 4}" text-anchor="end">${v}</text>`;
  // the strict fleet's range behind the bars, labelled in the clear space above the shortest bar
  s2 += `<rect class="band" x="${L2}" y="${y2(sHi)}" width="${W2 - L2 - R2}" height="${Math.max(2, +y2(sLo) - +y2(sHi)).toFixed(1)}"><title>Strict fleet: ${Math.round(sLo)} to ${Math.round(sHi)} t in each of the four years</title></rect>`;
  YEARS.forEach((yr, i) => {
    const v = t(yr), bx = L2 + i * bw + bw * 0.2, top = +y2(v);
    s2 += `<rect class="bar y${yr}" x="${bx.toFixed(1)}" y="${top}" width="${(bw * 0.6).toFixed(1)}" height="${(H2 - B - top).toFixed(1)}" rx="3"><title>${yr} sky: ${Math.round(v)} t delivered</title></rect>` +
      `<text class="v" x="${(bx + bw * 0.3).toFixed(1)}" y="${top - 5}" text-anchor="middle">${Math.round(v)}</text><text class="t" x="${(bx + bw * 0.3).toFixed(1)}" y="${H2 - B + 14}" text-anchor="middle">${yr}</text>`;
  });
  { const low = YEARS.reduce((a, yr, i) => (t(yr) < t(YEARS[a]) ? i : a), 0);
    s2 += `<text class="lab" x="${(L2 + low * bw + bw * 0.08).toFixed(1)}" y="${(+y2(sHi) - 6).toFixed(1)}">strict fleet, every year</text>`; }
  s2 += `<text class="t u" x="${L2}" y="12">t delivered in the year (strategic fleet)</text>`;
  $('es-tons').innerHTML = `<svg viewBox="0 0 ${W2} ${H2}" role="img" aria-label="Tonnes delivered in the year by the strategic fleet, by the year of the sky: ${YEARS.map(yr => `${yr} ${Math.round(t(yr))}`).join(', ')}. The strict fleet delivered ${Math.round(sLo)} to ${Math.round(sHi)} t in every year.">${s2}</svg>`;
  $('es-tons-cap').textContent = `Tonnes delivered in the year by the year of the sky, direct links only. Bars: all supervised rovers on the strategic rule (mean of ${sy.e21_by_start_year['2028'].n} runs; ${SY} → e21_by_start_year). Band: the strict fleet, which drives only while linked (${YR}).`;
  $('es-fleet-table').innerHTML = `<div class="es-scroll"><table class="es-table"><thead><tr><th scope="col">Month</th><th scope="col">Stranded share, 2028 sky</th><th scope="col">Stranded share, 2030 sky</th></tr></thead><tbody>` +
    MON.map((m, i) => `<tr><th scope="row">${m}</th><td class="mono">${pct(SHARE[2028][i])} %</td><td class="mono">${pct(SHARE[2030][i])} %</td></tr>`).join('') + '</tbody></table></div>' +
    `<table class="es-table"><thead><tr><th scope="col">Sky of the year</th><th scope="col">Strategic fleet</th><th scope="col">Strict fleet</th></tr></thead><tbody>${YEARS.map((yr, i) => `<tr><th scope="row">${yr}</th><td class="mono">${Math.round(t(yr))} t</td><td class="mono">${Math.round(strict[i])} t</td></tr>`).join('')}</tbody></table>`;
}

$('es-sources').innerHTML = [
  [TRACK, "Earth's centre seen from BASE, hourly 2028–2031 (SPICE: MOON_ME, LT+S; tools/comms/earth_link.py)"],
  [SY, `why the strategic cell differs by start year: link calendar, stranding, the swap of sky years (${esc(sy.generated.tool)}, ${sy.generated.seeds} seeds)`],
  ['results/E21_strategic_years_monthly.csv', 'the same calendar as a table'],
].map(([f, d]) => `<li><code>${esc(f)}</code>: ${d}</li>`).join('');

const draw = () => { drawSky(); drawCal(); drawFleet(); };
draw();
let raf = 0; new ResizeObserver(() => { cancelAnimationFrame(raf); raf = requestAnimationFrame(draw); }).observe($('main'));
