// F-56 / B-97: the real-data boxes, rendered at build time from results/B97_realdata.json.
// <!--@b97:telemetry--> (/network/): the simple detectors on real spacecraft telemetry (NASA's SMAP satellite and the
// MSL Curiosity Mars rover, telemanom's labelled anomalies), thresholds from training data only. Not lunar data, and not
// the network (it needs pair features a single telemetry channel does not have).
// <!--@b97:artemis--> and <!--@b97:geometry--> (/protocol/ problem 1): Artemis II's optical navigation camera, limb fits
// against the mission's SPICE trajectory and attitude (cislunar limb navigation, not surface navigation; the body is
// identified from the geometry), and earth_link.py's sky geometry against SPICE on Orion's trajectory.
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { ROOT } from './pages.mjs';
import { num, fmt, esc } from '../src/components/num.js';

export const B97_SRC = 'results/B97_realdata.json';
const PENDING = '<p class="stub">(pending: results/B97_realdata.json is not there yet)</p>';
let doc = null;
const load = () => (doc ??= existsSync(join(ROOT, B97_SRC)) ? JSON.parse(readFileSync(join(ROOT, B97_SRC), 'utf8')) : false);
const M = (value, unit, digits, what) => num({ value, unit, digits, flag: 'Measured', source: `${B97_SRC}: ${what} (real data)` });
const DET = [['zscore', 'z-score, one step'], ['chi2_step', 'Chi-square, one step'], ['chi2_window_16', 'Chi-square over 16 steps'], ['cusum_k0.5', 'CUSUM']];
const WORD = ['None', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine'];
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const when = utc => { const d = new Date(utc); return `${d.getUTCDate()} ${MON[d.getUTCMonth()]} ${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`; };

export function telemetryRows(D, residual = 'level') {
  return DET.map(([k, label]) => {
    const r = sc => D.telemetry.rows.find(x => x.spacecraft === sc && x.residual === residual && x.detector === k);
    return { k, label, msl: r('MSL'), smap: r('SMAP') };
  }).filter(x => x.msl && x.smap);
}

function telemetry(D) {
  const rows = telemetryRows(D), cell = x => `${x.found} of ${x.events} <span class="muted">(${x.fp_runs} false)</span>`;
  const best = sc => rows.reduce((a, x) => (x[sc].found > a[sc].found ? x : a), rows[0]);
  const z = rows.find(x => x.k === 'zscore') || rows[0], bm = best('msl'), bs = best('smap');
  const diff = telemetryRows(D, 'diff'), bestDiff = sc => Math.max(...diff.map(x => x[sc].found));
  return `<p class="prose">On the telemetry of two spacecraft, NASA's SMAP satellite and the Curiosity rover on Mars (MSL), with the anomalies
    the telemanom release labels, a detector that adds up evidence over time finds more than one that judges each step alone, at the same
    threshold, set per channel at the highest score seen in the training data: ${M(bm.msl.found, '', 0, `MSL, level, ${bm.k}, anomalies found`)} of ${bm.msl.events} anomalies on MSL with
    ${esc(bm.label.toLowerCase())} against ${M(z.msl.found, '', 0, 'MSL, level, z-score, anomalies found')} with the one-step z-score, and
    ${M(bs.smap.found, '', 0, `SMAP, level, ${bs.k}, anomalies found`)} of ${bs.smap.events} on SMAP against ${M(z.smap.found, '', 0, 'SMAP, level, z-score, anomalies found')}.
    It is the same finding as on our simulated rover streams. This is real spacecraft telemetry, not lunar rover data, and only the simple
    detectors run on it: the network needs the ten pair features of two rovers, which a single telemetry channel does not have.</p>
  <div class="nw-scroll"><table class="nw-table"><caption class="small">Anomalies found, with the false alarm runs in brackets, on the telemetry value
    (first ${D.telemetry.channels.length / 2} channels of each spacecraft). On its first difference every detector does worse (at best ${bestDiff('msl')} of
    ${rows[0].msl.events} on MSL and ${bestDiff('smap')} of ${rows[0].smap.events} on SMAP). Measured on real data, from ${B97_SRC}.</caption>
    <thead><tr><th scope="col">Detector</th><th scope="col">Curiosity (MSL)</th><th scope="col">SMAP satellite</th></tr></thead>
    <tbody>${rows.map(x => `<tr><th scope="row">${esc(x.label)}</th><td>${cell(x.msl)}</td><td>${cell(x.smap)}</td></tr>`).join('')}</tbody></table></div>`;
}

export function artemisRows(D) {
  return D.artemis2.images.map(im => ({ when: when(im.utc), body: im.target ? im.target[0] + im.target.slice(1).toLowerCase() : null, fit: im.fit, im }));
}

function artemis(D) {
  const rows = artemisRows(D), used = rows.filter(r => r.body), earth = used.filter(r => r.body === 'Earth').length;
  const errs = used.map(r => 100 * r.im.range_err_rel), dirs = used.map(r => r.im.direction_err_deg_best_signs).filter(v => typeof v === 'number');
  const tr = r => r.body
    // F-78 (review W5): data-labels, so each cell keeps its column name when the table stacks on a phone (protocol.css)
    ? `<tr><th scope="row">${r.when}</th><td data-label="Body, from the geometry">${r.body}</td><td data-label="Distance: image / SPICE">${fmt(r.im.range_km_image, 0)} / ${fmt(r.im.range_km_spice, 0)} km</td><td data-label="Distance error">${r.im.range_err_rel >= 0 ? '+' : ''}${fmt(100 * r.im.range_err_rel, 2)} %</td><td data-label="Direction error">${typeof r.im.direction_err_deg_best_signs === 'number' ? `${fmt(r.im.direction_err_deg_best_signs, 2)}°` : 'no attitude for this frame'}</td></tr>`
    : `<tr><th scope="row">${r.when}</th><td colspan="4" data-label="Not used">${esc(r.fit || 'not used')}</td></tr>`;
  return `<p>Artemis II, a crewed flight around the Moon in April 2026, took pictures with its optical navigation camera. Fitting a circle to the
    edge of each disc gives the spacecraft's distance to the body and the body's direction; we checked both against the mission's own trajectory
    and attitude (SPICE). This is <b>navigation from the limb in space between Earth and Moon, not navigation on the surface</b>.
    ${WORD[earth] ?? fmt(earth, 0)} of the ${(WORD[used.length] ?? fmt(used.length, 0)).toLowerCase()} usable discs are <b>Earth</b>, although the archive labels them Moon: the body was
    identified from the geometry. With no calibration, the distance comes out within ${M(Math.min(...errs), ' %', 2, 'smallest range error')} to
    ${M(Math.max(...errs), ' %', 2, 'largest range error')} and the direction within ${M(Math.max(...dirs), '°', 2, 'largest direction error')}.</p>
  <div class="pr-scroll"><table class="pr-table"><caption class="small">One frame from each flight-day session; ${fmt(D.artemis2.camera.urad_per_px, 0)} µrad per
    pixel. Measured on real data, from ${B97_SRC}.</caption>
    <thead><tr><th scope="col">Frame (UTC)</th><th scope="col">Body, from the geometry</th><th scope="col">Distance: image / SPICE</th><th scope="col">Distance error</th><th scope="col">Direction error</th></tr></thead>
    <tbody>${rows.map(tr).join('')}</tbody></table></div>`;
}

function geometry(D) {
  const G = D.geometry;
  return `<p>Our Earth-link code's sky geometry, run on Orion's trajectory as seen from the base, agrees with SPICE to
    10<sup>${Math.ceil(Math.log10(Math.max(G.max_abs_az_diff_deg, G.max_abs_el_diff_deg)))}</sup> degrees in azimuth and elevation over ${fmt(G.epochs, 0)} hourly epochs
    (Orion stayed below the base's horizon, ${fmt(G.orion_elevation_range_deg[0], 2)}° to ${fmt(G.orion_elevation_range_deg[1], 2)}°). Without the lunar frames
    kernel the base would sit ${M(G.moon_me_vs_iau_moon_shift_at_base_m, ' m', 1, 'shift of the base between the MOON_ME and IAU_MOON frames')} away from where it is.</p>`;
}

export function b97(key) {
  const D = load();
  if (!D) return PENDING;
  if (key === 'telemetry') return telemetry(D);
  if (key === 'artemis') return artemis(D);
  if (key === 'geometry') return geometry(D);
  throw new Error(`${B97_SRC}: unknown box ${key}`);
}
