// F-72 (B-105): one robot's own bid computation in an auction round and the measured memory of the on-robot parts, from
// results/E48_sizing.json (blocks per_robot_round and measured_memory). Pure, shared by /atc/ section 3 (client), the
// /results/ P3 card and /protocol/'s navigation computer (build). A laptop timing of one seed scaled by an assumed factor,
// not flight hardware; memory is what Python allocates for the parts, the interpreter and code not counted.
import { num } from '../components/num.js';
import { dateNum } from '../components/date-num.js';
import { supersededBlock } from '../components/results-file.js';

export const E48_SRC = 'results/E48_sizing.json';
// P3 Section 5.3: the link model assumes one decision a second; a design figure, used only to say "within" or "above"
const DECISION_MS = 1000;


export function robotRound(S) {
  const R = S?.per_robot_round?.laptop_ms_by_multiple, M = S?.measured_memory?.mb_by_multiple;
  if (!R || !M) return null;
  const xs = Object.keys(R).sort((a, b) => a - b), F = S.flight;
  const sm = (value, unit, digits, src, flag = 'Modelled') => num({ value, unit, digits, flag, source: `${E48_SRC}: ${src}` });
  // F-81: every timing pass decides (B-118 N12: three passes of the same month per multiple). A multiple is within the
  // decision when its largest pass at the central factor is, above when its smallest is over it, straddling otherwise; the
  // file's own against_1s_at_central_factor must say the same, or the build stops. The sentence quotes the range over the
  // passes (smallest to largest), as P3 does, and says so.
  const TP = S.per_robot_round.timing_passes?.by_multiple;
  if (!TP) throw new Error(`${E48_SRC}: no per_robot_round.timing_passes.by_multiple; the bid sentence reads every pass`);
  const PS = x => { const v = TP[x]?.flight_p99_ms_by_pass; if (!Array.isArray(v) || !v.length || v.some(y => typeof y !== 'number')) throw new Error(`${E48_SRC}: no timing passes for ${x}x (per_robot_round.timing_passes.by_multiple.${x}.flight_p99_ms_by_pass)`); return v; };
  const lo99 = x => Math.min(...PS(x)), hi99 = x => Math.max(...PS(x));
  const within = xs.filter(x => hi99(x) <= DECISION_MS), above = xs.filter(x => lo99(x) > DECISION_MS), split = xs.filter(x => !within.includes(x) && !above.includes(x));
  for (const x of xs) {
    const mine = within.includes(x) ? 'inside' : above.includes(x) ? 'above' : 'straddling', file = TP[x].against_1s_at_central_factor;
    if (file !== mine) throw new Error(`${E48_SRC}: at ${x}x the passes give ${mine} at the central factor, the file says ${file} (per_robot_round.timing_passes.by_multiple.${x}.against_1s_at_central_factor)`);
  }
  const nPass = PS(xs[0]).length;
  if (xs.some(x => PS(x).length !== nPass)) throw new Error(`${E48_SRC}: the fleet multiples have different numbers of timing passes; the bid sentence gives one`);
  const PASS = { 2: 'both', 3: 'all three' }, NW = { 1: 'one', 2: 'two', 3: 'three' };
  const psrc = (x, which) => `per_robot_round.timing_passes.by_multiple.${x}.flight_p99_ms_by_pass, the ${which} of the ${NW[nPass] || nPass} passes (one seed, laptop × flight.factor)`;
  const p99 = x => (sm(lo99(x) / 1e3, '', 2, '') === sm(hi99(x) / 1e3, '', 2, '') ? sm(hi99(x) / 1e3, ' s', 2, psrc(x, 'largest'))
    : `${sm(lo99(x) / 1e3, '', 2, psrc(x, 'smallest'))} to ${sm(hi99(x) / 1e3, ' s', 2, psrc(x, 'largest'))}`);
  const over = nPass > 1 ? ` over ${NW[nPass] || nPass} timing passes` : '';
  const and = a => (a.length < 2 ? a.join('') : `${a.slice(0, -1).join(', ')} and ${a[a.length - 1]}`);
  const WORD = { 2: 'two', 3: 'three', 4: 'four', 8: 'eight' };
  // ["1"] → "today's fleet"; ["4", "8"] → "four and eight times it"; ["1", "4"] → "today's fleet and four times it"
  const at = list => {
    const many = list.filter(x => +x !== 1).map(x => WORD[x] || x);
    return and([...(list.some(x => +x === 1) ? ["today's fleet"] : []), ...(many.length ? [`${and(many)} times it`] : [])]);
  };
  // every on-robot part held at once (P3 quotes this peak: "0.13 MB at most")
  const memKey = 'all_at_once_peak', mem = xs.map(x => M[x][memKey]);
  const lo = Math.min(...mem), hi = Math.max(...mem), xl = xs[mem.indexOf(lo)], xh = xs[mem.indexOf(hi)];
  const est = S.measured_memory.estimate_mb_for_comparison;
  const memText = `${sm(lo, '', 2, `measured_memory.mb_by_multiple.${xl}.${memKey}`)} to ${sm(hi, ' MB', 2, `measured_memory.mb_by_multiple.${xh}.${memKey}`)}`;
  // F-79 (B-118 N12): the factor range: the multiples whose highest pass at the top of the factor range goes over it
  const top = within.filter(x => (TP[x].flight_p99_ms_over_passes_and_factor_range?.[1] ?? 0) > DECISION_MS);
  const topV = x => sm(TP[x].flight_p99_ms_over_passes_and_factor_range[1] / 1e3, ' s', 2, `per_robot_round.timing_passes.by_multiple.${x}.flight_p99_ms_over_passes_and_factor_range (highest pass at the top of flight.factor_range)`);
  const passWord = nPass > 1 ? ` in ${PASS[nPass] || `all ${nPass}`} passes` : '';
  const topText = top.length ? `, and over it only at the top of the factor range (up to ${and(top.map(topV))} at ${at(top)})` : '';
  // the values published before the code review of 13 Nov 2026 (results key superseded_<date>_..., per_robot_round)
  // F-81: the one block holding them; none, or two after a second supersession, stops the build (the sentence is always printed)
  const oldKey = supersededBlock(S, E48_SRC, b => b.per_robot_round?.laptop_ms_by_multiple).key;
  const OLD = S[oldKey].per_robot_round.laptop_ms_by_multiple;
  if (!xs.every(x => OLD[x])) throw new Error(`${E48_SRC}: ${oldKey} lacks a fleet multiple the /atc/ sentence names (${xs.join(', ')})`);
  const was = `Corrected after a code review on ${dateNum({ iso: S[oldKey].superseded_on, source: `${E48_SRC}: ${oldKey}.superseded_on (the date the values were replaced)` })}, which found part of the timing taken with the memory tracer running: before, ${and(xs.map(x => sm(OLD[x].flight_p99_ms / 1e3, ' s', 2, `${oldKey}.per_robot_round.laptop_ms_by_multiple.${x}.flight_p99_ms (as published before)`)))} at ${at(xs)}.`;
  return {
    // "0.21 to 0.30 s, 0.77 to 0.92 s and 0.77 to 0.94 s at today's fleet and four and eight times it over three timing
    // passes, under the one-second decision at the central factor in all three passes, and over it only at the top of the
    // factor range (up to 1.07 s and 1.10 s ...)"
    bid: !above.length && !split.length ? `${and(within.map(p99))} at ${at(within)}${over}, under the one-second decision at the central factor${passWord}${topText}`
      : [within.length ? `${and(within.map(p99))} at ${at(within)}${over}, under the one-second decision in every pass` : '',
        split.length ? `${and(split.map(p99))} at ${at(split)}${within.length ? '' : over}, under the one-second decision in some passes and above it in others` : '',
        above.length ? `${and(above.map(p99))} at ${at(above)}${within.length || split.length ? '' : over}, above the one-second decision in every pass` : ''].filter(Boolean).join(', and '),
    above: above.length > 0 || split.length > 0,   // some multiple goes over the decision in some pass
    top: top.length > 0,   // some multiple goes over the decision at the top of the factor range
    was,   // the earlier values, named once on a page (F-79)
    factor: sm(F.factor, '×', 1, 'flight.factor (assumed: the ratio of benchmark scores)', 'Assumed'),
    mem: memText,
    estimate: sm(est, ' MB', 2, 'measured_memory.estimate_mb_for_comparison (the sum of the parts at assumed layouts)'),
    // the simulator's whole-fleet dispatch call, scaled (the 1.12 s the site used to show): about one robot's share
    fleetCall: sm(S.per_robot_round.whole_fleet_dispatch_call_ms_pooled.p99 * F.factor / 1e3, ' s', 2, 'per_robot_round.whole_fleet_dispatch_call_ms_pooled.p99 × flight.factor'),
  };
}
