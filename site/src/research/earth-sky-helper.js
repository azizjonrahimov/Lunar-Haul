// /research/earth-sky/ (F-43): the newest results, loaded when section 3's result nears the viewport. The end of section
// 3: one real helper rover with its own time counted (results/E21_fit_r2.json → helper, B-62) and why some calls wait over
// a week (results/E21_parking.json, B-61), from rescue.json. Section 4: the dark point's linked hours and dark spells
// 2028-2050 (results/E21_later_years.json, B-63) above the tonnes by start year for the strict fleet, the strategic fleet
// without help and with one helper called after a day (→ later_years), from years.json. The page passes its own helpers
// in, so this chunk imports nothing.

const YA = 2028, YB = 2051, f1 = v => v.toFixed(1), pct = v => Math.round(v * 100);
const LINES = [{ k: 'strict', cls: 'strict', label: 'strict fleet' }, { k: 'strategic', cls: 'none', label: 'no help' }, { k: 'helper_24h', cls: 'help', label: 'one helper' }];
const yearAt = s => { const [d, h] = s.split('T'), [Y, M, D] = d.split('-').map(Number), a = Date.UTC(Y, 0, 1); return Y + (Date.UTC(Y, M - 1, D, +h || 0) - a) / (Date.UTC(Y + 1, 0, 1) - a); };

// mountHelper(rs, {$, num, upgradeFlags, statChip, FIT, T, P, strand}): one helper rover, called after a day (or a week),
// drives to a spot that sees both the held rover and Earth, waits there for Earth and frees the rover; against the same
// rover as one more hauler in the strict fleet. strand: the page's source for the no-help tonnage
export function mountHelper(rs, { $, num, upgradeFlags, statChip, FIT, T, P, strand }) {
  const [hDay, hWeek] = rs.helper, HR = rs.helper_refs, PK = rs.parking;
  const SRC = {
    helper: (c, k) => `${FIT} → helper.cells[label = "${c.label}"].${k} (one extra rover on call, called once a rover has been held ${c.call_threshold_h} h; its driving, parking and service time counted; all supervised, strategic, direct links only; mean of ${c.n} runs)`,
    href: (k, name) => `${FIT} → helper.references["${name}"].mean.delivered_t_in_year (direct links only; mean of ${HR[k].n} runs)`,
    park: k => `${PK.source} → ${PK.path}.${k} (${PK.calls} calls for help, asked as soon as a rover is held)`,
  };
  const worstOf = c => Object.entries(c.share_of_always_linked_by_year).reduce((a, b) => (b[1] < a[1] ? b : a));
  const [dayWorstY, dayWorst] = worstOf(hDay), [weekWorstY, weekWorst] = worstOf(hWeek), extraHauler = HR.strict_plus_one.delivered_t_in_year - HR.strict.delivered_t_in_year;
  const extraSrc = `${SRC.href('strict_plus_one', 'strict + 1 rover')} minus ${SRC.href('strict', 'strict')}`;
  $('es-helper').innerHTML = `A real helper, with its own time counted, fixes 2028 and the other years. One extra rover, called once any rover has been held for a day, drives to a spot that sees both the stuck rover and Earth, waits there for Earth and frees the rover: ` +
    `the fleet then delivers ${T(hDay.delivered_t_in_year, SRC.helper(hDay, 'mean.delivered_t_in_year'))} a year (${T(hDay.by_year['2028'], SRC.helper(hDay, 'by_year.2028.delivered_t_in_year'))} under the 2028 sky), ` +
    (hDay.within_5pct_every_year ? 'within 5 % of' : 'against') + ` the ${T(HR.always.delivered_t_in_year, SRC.href('always', 'always-linked strategic'))} with Earth always in view in every start year (worst ${P(dayWorst, SRC.helper(hDay, `share_of_always_linked_by_year.${dayWorstY}`))}, ${dayWorstY}). ` +
    `The helper spends ${P(hDay.parked_share, SRC.helper(hDay, 'helper.busy_split_share.parked_waiting_for_earth'))} of its working time parked, waiting for its own view of Earth; ` +
    `as one more hauler in the strict fleet, the same rover adds only ${num({ value: extraHauler, unit: 't', flag: 'Modelled', digits: 1, source: extraSrc })}. ` +
    `Called only after a week, the helper lets ${weekWorstY} fall to ${P(weekWorst, SRC.helper(hWeek, `share_of_always_linked_by_year.${weekWorstY}`))} of the always-linked tonnage. ` +
    (PK.held_points_without_parking === 0 ? 'Such a spot exists for every point where rovers were held, yet ' : 'Yet ') +
    `${P(PK.uncovered_share, SRC.park('uncovered_share'))} of calls would still wait more than a week for it to see Earth: for ${P(PK.earth_below_every_horizon_share, SRC.park('earth_below_lowest_candidate_horizon_share'), 1)} of those, ` +
    `Earth is low in its monthly swing, below the horizon of every nearby spot, and takes a median of ${num({ value: PK.h_until_clear_median, unit: 'h', flag: 'Modelled', digits: 0, source: SRC.park('h_until_earth_clears_lowest_horizon_q10_50_90[1]') })} to clear the lowest of them.`;
  upgradeFlags($('es-helper'));
  $('es-rescue-chips').append(
    statChip({ label: 'One helper, called after a day', value: hDay.delivered_t_in_year, unit: 't', digits: 0, flag: 'Modelled', source: SRC.helper(hDay, 'mean.delivered_t_in_year'), tone: 'cool' }).el,
    statChip({ label: "Helper's time spent parked", value: 100 * hDay.parked_share, unit: '%', digits: 0, flag: 'Modelled', source: SRC.helper(hDay, 'helper.busy_split_share.parked_waiting_for_earth') }).el,
    statChip({ label: 'Same rover as one more hauler', text: `+${extraHauler.toFixed(1)} t`, flag: 'Modelled', source: `strict fleet: ${extraSrc}` }).el,
    statChip({ label: 'No help', value: rs.strand.delivered_t_in_year, unit: 't', digits: 0, flag: 'Modelled', source: strand, tone: 'warm' }).el);
}

// mountYears(yr, {$, num, esc, upgradeFlags, spot, width, monthLabel, T, P}) -> draw(); writes the section's text and adds its source to the list
export function mountYears(yr, { $, num, esc, upgradeFlags, spot, width, monthLabel, T, P }) {
  if (yr.sample !== spot.sample) throw new Error(`years.json: route point ${yr.sample}, not ${spot.sample}`);
  const LH = yr.linked_h_by_year, POL = yr.by_policy_year, LINKS = yr.source.links, TONS = yr.source.tonnes;
  const SPELLS = yr.spells.map(s => ({ ...s, a: yearAt(s.start), b: yearAt(s.end), yrs: s.days / 365.25, from: monthLabel(s.start.slice(0, 7)), to: s.censored ? 'past 2050' : monthLabel(s.end.slice(0, 7)) }));
  const STARTS = Object.keys(POL.strict).map(Number).sort((a, b) => a - b), LATER = STARTS.filter(y => y >= 2032);
  const alwaysT = y => yr.always.by_year_2028_2031[y] ?? yr.always.t_2032_2046;
  const runs = [...new Set(STARTS.flatMap(y => LINES.map(l => POL[l.k][y].n)))];

  function draw() {
    const W = width('es-years'), narrow = W < 560, L = 44, R = narrow ? 14 : 20;
    const hA = Math.round(Math.min(150, Math.max(110, W * 0.2))), hB = Math.round(Math.min(260, Math.max(190, W * 0.36))), TA = 24, TB = TA + hA + 40, B = 30, H = TB + hB + B;
    const x = v => L + (v - YA) / (YB - YA) * (W - L - R), px = x(YA + 1) - x(YA), X = v => x(v).toFixed(1);
    const hMax = Math.ceil(Math.max(...Object.values(LH)) / 250) * 250, yA = v => (TA + (1 - v / hMax) * hA).toFixed(1);
    const tMax = Math.ceil(Math.max(...STARTS.flatMap(y => [alwaysT(y), ...LINES.map(l => POL[l.k][y].t)])) / 200) * 200, yB = v => (TB + (1 - v / tMax) * hB).toFixed(1);
    let s = '';
    for (const sp of SPELLS) {
      const a = Math.max(sp.a, YA), b = Math.min(sp.b, YB), tip = `A dark spell at the dark spot: ${sp.from} to ${sp.to}${sp.censored ? ', where the link files end' : ` (${f1(sp.yrs)} years)`}`;
      for (const [t0, h] of [[TA, hA], [TB, hB]]) s += `<rect class="spell" x="${X(a)}" y="${t0}" width="${(x(b) - x(a)).toFixed(1)}" height="${h}"><title>${esc(tip)}</title></rect>`;
      const lab = sp.a < YA ? `since ${sp.from}` : sp.censored ? `${sp.from} →` : narrow ? `${f1(sp.yrs)} years` : `${sp.from} – ${sp.to}`;
      if (lab.length * 6.2 + 8 < x(b) - x(a)) s += `<text class="t spl" x="${((x(a) + x(b)) / 2).toFixed(1)}" y="${TA + 13}" text-anchor="middle">${lab}</text>`;
    }
    // panel A: hours a year with Earth in view at the dark spot
    for (const v of [0, hMax / 2, hMax]) s += `<line class="g" x1="${L}" x2="${W - R}" y1="${yA(v)}" y2="${yA(v)}"/><text class="t" x="${L - 6}" y="${+yA(v) + 4}" text-anchor="end">${v}</text>`;
    s += `<text class="t u" x="${L}" y="${TA - 8}">hours with Earth in view at the dark spot</text>`;
    for (const [k, v] of Object.entries(LH)) {
      const y0 = +k, tip = `${k}: ${v > 0 ? `Earth in view at the dark spot for ${v} h` : 'no hour with Earth in view at the dark spot'}`;
      if (v > 0) s += `<rect class="hbar" x="${X(y0 + 0.15)}" y="${yA(v)}" width="${(px * 0.7).toFixed(1)}" height="${(TA + hA - +yA(v)).toFixed(1)}" rx="2"/>`;
      s += `<rect class="hit" x="${X(y0)}" y="${TA}" width="${px.toFixed(1)}" height="${hA}"><title>${tip}</title></rect>`;
    }
    // panel B: tonnes by start year, with Earth always in view as a dashed step for reference
    for (let v = 0; v <= tMax; v += 200) s += `<line class="g" x1="${L}" x2="${W - R}" y1="${yB(v)}" y2="${yB(v)}"/><text class="t" x="${L - 6}" y="${+yB(v) + 4}" text-anchor="end">${v}</text>`;
    s += `<text class="t u" x="${L}" y="${TB - 8}">t delivered in the year, by start year</text>`;
    s += `<path class="ref" d="${STARTS.map((y, i) => `${i ? 'L' : 'M'}${X(y)},${yB(alwaysT(y))}H${X(y + 1)}`).join('')}"><title>Earth always in view: ${STARTS.map(y => `${y} ${Math.round(alwaysT(y))} t`).join(', ')}</title></path>`;
    // labelled at its right end, above the line: in the later years no fleet delivers more than with Earth always in view
    const last = STARTS.at(-1);
    s += `<text class="lab mut" x="${X(last + 1)}" y="${(+yB(alwaysT(last)) - 8).toFixed(1)}" text-anchor="end">Earth always in view</text>`;
    for (const l of LINES) {
      const pts = STARTS.map(y => [x(y + 0.5), +yB(POL[l.k][y].t), y]);
      s += `<path class="ln ${l.cls}" d="${pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1]}`).join('')}"/>`;
      s += pts.map(([cx, cy, y]) => `<circle class="pt ${l.cls}" cx="${cx.toFixed(1)}" cy="${cy}" r="${l.cls === 'strict' ? 2.5 : narrow ? 3 : 4}"><title>Start year ${y}, ${l.label}: ${Math.round(POL[l.k][y].t)} t (mean of ${POL[l.k][y].n} runs)</title></circle>`).join('');
      const [ex, ey] = pts.at(-1);
      s += `<text class="lab" x="${(ex + 8).toFixed(1)}" y="${(ey + 4).toFixed(1)}">${l.label}</text>`;
    }
    const step = narrow ? 4 : 2;
    for (let y = YA; y < YB; y += step) s += `<text class="t" x="${X(y + 0.5)}" y="${TB + hB + 16}" text-anchor="middle">${y}</text>`;
    const said = `Hours a year with Earth in view at the dark spot: ${Object.entries(LH).map(([k, v]) => `${k} ${v}`).join(', ')}. Dark spells over 180 days: ${SPELLS.map(sp => `${sp.from} to ${sp.to}`).join('; ')}. ` +
      `Tonnes delivered by start year, ${LINES.map(l => `${l.label}: ${STARTS.map(y => `${y} ${Math.round(POL[l.k][y].t)}`).join(', ')}`).join('; ')}.`;
    $('es-years').innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(said)}">${s}</svg>` +
      `<p class="es-legend"><span><i class="hkey"></i>hours with Earth in view at the dark spot</span><span><i class="spellkey"></i>dark spell over 180 days</span>` +
      `<span><i class="lnkey none"></i>no help</span><span><i class="lnkey help"></i>one helper, called after a day</span><span><i class="lnkey strict"></i>strict fleet</span><span><i class="lnkey ref"></i>Earth always in view</span></p>`;
  }

  $('es-years-cap').textContent = `Bars: hours a year in which some of Earth's disc clears the terrain at the dark spot (route point ${yr.sample}) for a 2.5 m antenna, 2028–2050 (${LINKS} → dark_sample_${yr.sample}.linked_h_by_year). ` +
    `Shaded: its dark spells longer than 180 days (→ dark_spells_${yr.sample}_over_180_days); the first began in ${SPELLS[0].from}, before the chart, and the last runs past the end of 2050, where the link files end. ` +
    `Lines: tonnes delivered in the year by start year, direct links only, each point the mean of ${runs.join(' or ')} runs. 2028–2031: the 20-run cells, whose start year is 2028 + seed mod 4 (${TONS} → helper.references, rescue.references.strategic.by_year, helper.cells["dedicated k=1, 24 h"].by_year); ` +
    `${LATER[0]}–${LATER.at(-1)}: seeds 0–4 on the 2032–2050 link files (${TONS} → later_years.by_policy_year). Earth always in view: the same 20 runs by start year, then seeds 0–4 (${Math.round(yr.always.t_2032_2046)} t; ${TONS} → later_years.always_linked_t).`;
  $('es-years-table').innerHTML = `<div class="es-scroll"><table class="es-table"><thead><tr><th scope="col">Year</th><th scope="col">Hours with Earth in view, dark spot</th>${LINES.map(l => `<th scope="col">${l.label[0].toUpperCase() + l.label.slice(1)}, t</th>`).join('')}<th scope="col">One helper against always in view</th><th scope="col">Runs</th></tr></thead><tbody>` +
    Object.keys(LH).map(k => `<tr><th scope="row">${k}</th><td class="mono">${LH[k] > 0 ? `${LH[k]} h` : 'none'}</td>${LINES.map(l => `<td class="mono">${POL[l.k][k] ? Math.round(POL[l.k][k].t) : '–'}</td>`).join('')}` +
      `<td class="mono">${POL.helper_24h[k] ? `${pct(POL.helper_24h[k].share)} %` : '–'}</td><td class="mono">${POL.strict[k] ? POL.strict[k].n : '–'}</td></tr>`).join('') + '</tbody></table></div>' +
    `<table class="es-table"><caption>Dark spells over 180 days at the dark spot</caption><thead><tr><th scope="col">From</th><th scope="col">To</th><th scope="col">Length</th></tr></thead><tbody>` +
    SPELLS.map(sp => `<tr><td>${sp.from}</td><td>${sp.to}</td><td class="mono">${sp.censored ? `over ${f1(sp.yrs)} years (the link files end)` : `${f1(sp.yrs)} years`}</td></tr>`).join('') + '</tbody></table>';

  const done = SPELLS.filter(sp => !sp.censored).map(sp => sp.yrs), ap = yr.period, dark = yr.whole_dark, other = yr.other;
  const allDark = dark.years.every(y => LH[y] === 0), [hwY, hw] = LATER.map(y => [y, POL.helper_24h[y].share]).reduce((a, b) => (b[1] < a[1] ? b : a));
  const yrsN = (value, source) => num({ value, flag: 'Modelled', digits: 2, source }), spellSrc = `${LINKS} → dark_spells_${yr.sample}_over_180_days.spells[*].days, the spells that end before 2051`;
  const perSrc = k => `${LINKS} → period_${yr.sample}.annual.${k} (${ap.method})`, ly = k => `${TONS} → later_years.${k} (strategic, all supervised, direct links only; seeds 0–4 per start year)`;
  $('es-years-text').innerHTML = `The dark spot's long dark spells come back about every ${yrsN(ap.best_yr, perSrc('best_period_yr'))} years (95 % interval ${yrsN(ap.ci95_yr[0], perSrc('ci95_yr'))} to ${yrsN(ap.ci95_yr[1], perSrc('ci95_yr'))}), ` +
    `and each lasts ${num({ value: Math.min(...done), flag: 'Modelled', digits: 1, source: spellSrc })} to ${num({ value: Math.max(...done), flag: 'Modelled', digits: 1, source: spellSrc })} years. ` +
    `Without help the strategic fleet collapses in ${dark.years.length} of the ${LATER.length} start years ${LATER[0]}–${LATER.at(-1)}${allDark ? ', the years in which the dark spot sees no Earth at all' : ''} ` +
    `(${T(dark.mean_t, ly('strategic_whole_dark_years.mean_t'))} a year on average, against ${T(other.mean_t, ly('strategic_other_years.mean_t'))} in the other ${other.years.length}); ` +
    `with one helper called after a day it stays ${yr.helper_years_below_95pct.length === 0 ? 'within 5 % of the tonnage with Earth always in view in every one of them' : 'close to the tonnage with Earth always in view'} ` +
    `(worst ${P(hw, `${TONS} → later_years.by_policy_year.helper_24h.${hwY}.share_of_always_linked (seeds 0–4)`)}, ${hwY}).`;
  upgradeFlags($('es-years-text'));
  $('es-sources').insertAdjacentHTML('beforeend', `<li><code>${esc(LINKS)}</code>: Earth's link at every route point 2028–2050 (SPICE + LOLA): route point ${yr.sample}'s hours by year, its dark spells and their period</li>`);
  return draw;
}
