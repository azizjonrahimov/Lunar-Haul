// Build-time HTML for /results: the Phase-3 figures with figures/phase3_captions.json, the E15 and E16 summary tables
// from results/*.csv, and the v2 figures with their captions from the v2 paper (paper/part*.html). Nothing is
// hard-coded: whatever figures and tables exist when the site is built are shown, and missing ones say so.
// prepare-data.mjs stages the PNGs and the summary CSVs into public/results/; PDFs and raw CSVs link to the repository.
import { readFileSync, existsSync, openSync, readSync, closeSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { num, esc, fmt } from '../src/components/num.js';
import { ROOT, REPO, csv } from './pages.mjs';

const FIG = join(ROOT, 'figures'), RES = join(ROOT, 'results');
const blob = p => `${REPO}/blob/main/${p}`;

/* width and height from a PNG's IHDR (bytes 16-23), so the page reserves the space before the image loads */
function pngSize(file) {
  const fd = openSync(file, 'r'), b = Buffer.alloc(24);
  try { readSync(fd, b, 0, 24, 0); } finally { closeSync(fd); }
  return b.toString('ascii', 12, 16) === 'IHDR' ? [b.readUInt32BE(16), b.readUInt32BE(20)] : [1600, 1000];
}
/* captions come from our own paper HTML and captions JSON: keep simple inline markup, drop everything else */
function inline(html) {
  return String(html).replace(/<(?!\/?(b|i|em|strong|sub|sup|code)>)[^>]*>/g, '').replace(/\s+/g, ' ').trim();
}
/* the figure script's messages may name absolute local paths: show them relative to the repository */
const BS = String.fromCharCode(92);   // backslash
const rel = t => {
  let s = String(t);
  for (const r of [ROOT, ROOT.split(BS).join('/')]) s = s.split(r + BS).join('').split(r + '/').join('').split(r).join('the repository');
  for (const d of ['results', 'figures', 'data']) s = s.split(d + BS).join(d + '/');
  return s;
};
const titleOf = id => id.replace(/^fig\d+_/, '').replace(/_/g, ' ');

function img(base, png, alt) {
  const [w, h] = pngSize(join(FIG, png));
  return `<a class="r-img" href="${base}results/figures/${png}"><img src="${base}results/figures/${png}" alt="${esc(alt)}" width="${w}" height="${h}" loading="lazy" decoding="async"></a>`;
}
function downloads(base, files) {
  return files.map(f => f.endsWith('.png') ? `<a href="${base}results/figures/${f}" download>PNG</a>` : `<a href="${blob('figures/' + f)}">${esc(f.split('.').pop().toUpperCase())} (repository)</a>`).join(' · ');
}

// ---------- Phase-3 figures ----------
function phase3Figures(base) {
  const capPath = join(FIG, 'phase3_captions.json');
  if (!existsSync(capPath)) return '<p class="stub">figures/phase3_captions.json is not there yet: the Phase-3 figures have not been made.</p>';
  const caps = JSON.parse(readFileSync(capPath, 'utf8'));
  return Object.entries(caps).map(([id, c], k) => {
    const files = (c.files || []).filter(f => existsSync(join(FIG, f))), png = files.find(f => f.endsWith('.png'));
    const stale = (c.stale_files || []).filter(f => f.endsWith('.png') && existsSync(join(FIG, f)));
    const status = c.status || (png ? 'produced' : 'missing');
    const note = status === 'produced' ? '' : `<p class="r-note"><span class="pill note">${esc(status)}</span> ${esc(rel(c.reason || 'not produced in the latest figure run'))}</p>`;
    const meta = [c.n ? `<b>n:</b> ${esc(c.n)}` : '', c.ci ? `<b>Intervals:</b> ${esc(c.ci)}` : '', c.flags ? `<b>Flags:</b> ${esc(c.flags)}` : ''].filter(Boolean).join(' · ');
    let body;
    if (status === 'produced' && png) body = img(base, png, c.alt || `Figure ${titleOf(id)}`);
    else if (stale.length) body = `<details class="r-stale"><summary>Show the stale version from an earlier run</summary>${img(base, stale[0], `Stale figure ${titleOf(id)}`)}</details>`;
    else body = '';
    return `<figure class="r-fig" id="${esc(id)}">${body}<figcaption><b>${esc(id.match(/^fig(\d+)/) ? 'Figure ' + +id.match(/^fig(\d+)/)[1] : id)}.</b> ${inline(rel(c.caption || titleOf(id)))}
${note}${meta ? `<p class="small muted">${meta}</p>` : ''}${status === 'produced' && files.length ? `<p class="small">${downloads(base, files)}</p>` : ''}</figcaption></figure>`;
  }).join('\n');
}

// ---------- E15: terminal-descent Monte Carlo ----------
const pct = (v, d = 1) => (v === '' || v === undefined) ? '–' : `${fmt(100 * +v, d)} %`;
// the CSV's variant column says "baseline" for every imitation policy too: name learned rows by the policy id's tag,
// as the lander lab does (lander_<CLASS>_<tag>_s<seed>)
const TAG_LABEL = { bc_v3: 'imitation + DAgger, observation v3', bcml: 'imitation + DAgger, memoryless teacher', bc: 'imitation + DAgger, filtered teacher',
  baseline: 'PPO, reward v2', hover_bonus: 'PPO, hover bonus (env v2)', hover_bonus_v1: 'PPO, hover bonus (env v1)', no_eta: 'PPO, no survival term' };
function controllerLabel(r) {
  const tag = (String(r.policy).match(/^lander_[A-Za-z0-9]+_(.+)_s\d+$/) || [])[1];
  return TAG_LABEL[tag] || `learned (${String(r.variant).replace(/_/g, ' ')})`;
}
function tableE15(base) {
  const p = join(RES, 'table_E15.csv'); if (!existsSync(p)) return '<p class="stub">results/table_E15.csv is not there yet.</p>';
  const rows = csv(readFileSync(p, 'utf8')), src = r => `results/table_E15.csv, ${r.policy}, n = ${r.n} episodes`;
  const M = (r, v, unit, d) => v === '' ? '–' : num({ value: +v, unit, flag: 'Modelled', digits: d, source: src(r) });
  const body = rows.map(r => {
    const fails = ['velocity', 'tilt', 'sensor', 'timeout', 'lost'].map(k => [k, +r['fail_' + k]]).filter(([, v]) => v > 0).map(([k, v]) => `${k} ${v}`).join(', ') || 'none';
    const delta = r.vs ? `${M(r, 100 * +r.d_pass_rate, 'pp', 1)} <span class="muted small">± ${fmt(100 * +r.d_pass_rate_ci95, 1)}</span>` : '<span class="muted small">reference</span>';
    return `<tr><th scope="row">${esc(r.cls)} · ${esc(r.kind === 'classical' ? 'classical law' : controllerLabel(r))}</th><td class="n">${esc(r.n)}</td>
<td class="n">${M(r, 100 * +r.pass_rate, '%', 1)}</td><td class="n">${delta}</td><td class="n">${M(r, r.miss_p50_m, 'm', 1)}</td><td class="n">${M(r, r.miss_p90_m, 'm', 1)}</td>
<td class="n">${M(r, 100 * +r.offpad_50m_share, '%', 1)}</td><td class="n">${M(r, r.prop_used_mean_kg, 'kg', 0)}</td><td class="small">${esc(fails)}</td></tr>`;
  }).join('');
  return `<div class="r-scroll"><table class="w-table r-table"><caption>Experiment E15: terminal-descent Monte Carlo per lander class and controller (${rows.length} rows). Pass = touchdown inside the velocity, tilt and sensor limits; Δ pass rate against the classical law of the same class with its 95 % interval.</caption>
<thead><tr><th scope="col">Class · controller</th><th scope="col" class="n">Episodes</th><th scope="col" class="n">Pass rate</th><th scope="col" class="n">Δ pass rate vs classical</th><th scope="col" class="n">Miss p50</th><th scope="col" class="n">Miss p90</th><th scope="col" class="n">Off the 50 m pad</th><th scope="col" class="n">Propellant</th><th scope="col">Failures (count)</th></tr></thead>
<tbody>${body}</tbody></table></div>
<p class="small muted">Flags: environment Modelled (3-DoF descent parameterised from flown landers), failure limits Spec, learned policies trained in-house (Modelled); sensor noise ${rows.every(r => r.sensor === 'True') ? 'on in every row' : 'as in the sensor column of the CSV'}. <a href="${base}results/data/table_E15.csv" download>table_E15.csv</a> · per-episode outcome tables: <code>data/policies/outcomes_*.json</code> (<a href="${REPO}/tree/main/data/policies">repository</a>).</p>`;
}

// ---------- E16: driving-table validation ----------
function tableE16(base) {
  const p = join(RES, 'table_E16.csv'); if (!existsSync(p)) return '<p class="stub">results/table_E16.csv is not there yet.</p>';
  const rows = csv(readFileSync(p, 'utf8')), src = r => `results/table_E16.csv, ${r.check}, ${r.leg}, ${r.autonomy} ${r.rtt_s} s`;
  const M = (r, v, unit, d, flag = 'Modelled', s = src(r)) => v === '' || v === undefined ? '–' : num({ value: +v, unit, flag, digits: d, source: s });
  const groups = [...new Set(rows.map(r => r.check))];
  const LAB = { speed_made_good_vs_rtt_flat: 'Speed made good against round-trip time, flat ground (calibration)', speed_made_good_vs_rtt_real_leg: 'Speed made good against round-trip time on a real leg', psr_round_trip_energy: 'Energy of a round trip into the permanently shadowed region' };
  const parts = groups.map(g => {
    const rs = rows.filter(r => r.check === g), first = rs[0];
    if (g === 'psr_round_trip_energy') {
      return `<table class="w-table r-table"><caption>${esc(LAB[g] || g)}: ${esc(first.leg)} (${rs.length} rows)</caption><thead><tr><th scope="col">Case</th><th scope="col" class="n">Simulated</th><th scope="col" class="n">Reference band</th><th scope="col">In band</th></tr></thead><tbody>${rs.map(r =>
        `<tr><th scope="row">${esc(r.autonomy)}${r.rtt_s ? `, ${esc(r.rtt_s)} s` : ''}${r.lighting && r.lighting !== 'none' ? `, ${esc(r.lighting)}` : ''}${r.note && new Set(rs.map(x => x.note)).size > 1 ? `<div class="small muted">${esc(r.note)}</div>` : ''}</th><td class="n">${M(r, r.sim_kwh, 'kWh', 2)}</td><td class="n">${r.ref_kwh_lo !== '' ? `${fmt(+r.ref_kwh_lo, 1)}–${fmt(+r.ref_kwh_hi, 1)} kWh` : '–'}</td><td>${r.in_band === 'True' ? '<span class="pill pass">yes</span>' : r.in_band === 'False' ? '<span class="pill fail">no</span>' : '–'}</td></tr>`).join('')}</tbody></table>${first.note && new Set(rs.map(x => x.note)).size === 1 ? `<p class="small muted">${esc(first.note)}</p>` : ''}`;
    }
    return `<table class="w-table r-table"><caption>${esc(LAB[g] || g)}: ${esc(first.leg)}${first.length_m && !/km/.test(first.leg) ? `, ${fmt(+first.length_m / 1000, 2)} km` : ''}${first.max_slope_deg ? `, max slope ${fmt(+first.max_slope_deg, 1)}°` : ''}, lighting ${esc(first.lighting)}</caption>
<thead><tr><th scope="col">Autonomy</th><th scope="col" class="n">Round trip</th><th scope="col" class="n">Simulated</th><th scope="col" class="n">Mean of runs</th><th scope="col" class="n">Ratio to 0 s</th><th scope="col" class="n">Reference</th><th scope="col" class="n">Error</th><th scope="col" class="n">Interventions λ</th><th scope="col" class="n">Stops</th></tr></thead><tbody>${rs.map(r =>
      `<tr><th scope="row">${esc(r.autonomy)}</th><td class="n">${fmt(+r.rtt_s, 0)} s</td><td class="n">${M(r, r.sim_kmh, 'km/h', 2)}</td><td class="n">${M(r, r.sim_kmh_mean_runs, 'km/h', 2)}</td><td class="n">${r.sim_ratio_to_rtt0 === '' ? '–' : fmt(+r.sim_ratio_to_rtt0, 3)}</td>
<td class="n">${r.ref_kmh === '' ? '–' : M(r, r.ref_kmh, 'km/h', 2, 'Measured', 'Litaker et al. 2025, JSC teleoperation simulator (speed made good)')}</td><td class="n">${r.rel_err === '' ? '–' : `${fmt(100 * +r.rel_err, 2)} %`}</td><td class="n">${r.interventions_lambda === '' ? '–' : fmt(+r.interventions_lambda, 2)}</td><td class="n">${r.stops === '' ? '–' : fmt(+r.stops, 0)}</td></tr>`).join('')}</tbody></table>
${first.note ? `<p class="small muted">${esc(first.note)}</p>` : ''}`;
  }).join('\n');
  return `<div class="r-scroll">${parts}</div>
<p class="small muted">Flags: simulated values Modelled (rover model and driving tables, <code>lunarsim.rover</code>); teleoperation references Measured. <a href="${base}results/data/table_E16.csv" download>table_E16.csv</a> · raw runs: <a href="${blob('results/E16_driving_validation.csv')}">E16_driving_validation.csv</a> (repository).</p>`;
}

// ---------- v2 figures ----------
function v2Captions() {
  const caps = {};
  for (const f of ['part2_methods.html', 'part3_results.html', 'part4_back.html']) {
    const p = join(ROOT, 'paper', f); if (!existsSync(p)) continue;
    const html = readFileSync(p, 'utf8');
    for (const m of html.matchAll(/<img[^>]+src="[^"]*?(fig\d+_[\w-]+)\.png"[^>]*>[\s\S]*?<figcaption>([\s\S]*?)<\/figcaption>/g)) caps[m[1]] ||= inline(m[2]);
  }
  return caps;
}
const v2Ids = () => (existsSync(FIG) ? readdirSync(FIG) : []).filter(f => /^fig(0[1-9]|1\d)_[\w-]+\.png$/.test(f)).sort().map(f => f.replace(/\.png$/, ''));
function v2Figures(base, ids) {
  if (!ids.length) return '<p class="stub">No version-2 figures in figures/.</p>';
  // in the paper's order: its figure numbers differ from the file names (fig14_timeline is Figure 5)
  const caps = v2Captions(), no = id => +((caps[id] || '').match(/Figure (\d+)\./) || [0, 99])[1];
  return [...ids].sort((x, y) => no(x) - no(y) || (x < y ? -1 : 1)).map(id => `<figure class="r-fig" id="${esc(id)}">${img(base, id + '.png', `Version 2 figure: ${titleOf(id)}`)}<figcaption>${caps[id] || `<b>${esc(titleOf(id))}</b>`}
<p class="small">${downloads(base, [id + '.png', ...(existsSync(join(FIG, id + '.pdf')) ? [id + '.pdf'] : [])])}</p></figcaption></figure>`).join('\n');
}

export function results(base) {
  const ids = v2Ids();
  return `<section aria-labelledby="h-p3"><h2 id="h-p3">Phase 3: learned landing, real terrain, plume and rover autonomy</h2>
<p class="small muted">Figures as last produced by <code>experiments/phase3/make_figures_phase3.py</code>; captions, sample sizes and flags from <code>figures/phase3_captions.json</code>. They are regenerated after the final runs, under the same names.</p>
${phase3Figures(base)}</section>
<section aria-labelledby="h-e15"><h2 id="h-e15">Lander Monte Carlo (E15)</h2>${tableE15(base)}</section>
<section aria-labelledby="h-e16"><h2 id="h-e16">Driving-table validation (E16)</h2>${tableE16(base)}</section>
<section aria-labelledby="h-v2"><h2 id="h-v2">Version 2 results</h2>
<details class="r-v2"><summary>Show the ${ids.length} figures of the version-2 paper (marketplace dispatch on an abstract site graph)</summary>
<p class="small muted">Captions from the version-2 paper. The engine and these results are unchanged in Phase 3 (<code>lunarsim compare</code> reproduces them).</p>
${v2Figures(base, ids)}</details></section>`;
}
