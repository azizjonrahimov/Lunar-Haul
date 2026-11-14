// F-72 (B-105): one robot's own bid computation in an auction round and the measured memory of the on-robot parts, from
// results/E48_sizing.json (blocks per_robot_round and measured_memory). Pure, shared by /atc/ section 3 (client), the
// /results/ P3 card and /protocol/'s navigation computer (build). A laptop timing of one seed scaled by an assumed factor,
// not flight hardware; memory is what Python allocates for the parts, the interpreter and code not counted.
import { num } from '../components/num.js';
import { dateNum } from '../components/date-num.js';

export const E48_SRC = 'results/E48_sizing.json';
// P3 Section 5.3: the link model assumes one decision a second; a design figure, used only to say "within" or "above"
const DECISION_MS = 1000;


export function robotRound(S) {
  const R = S?.per_robot_round?.laptop_ms_by_multiple, M = S?.measured_memory?.mb_by_multiple;
  if (!R || !M) return null;
  const xs = Object.keys(R).sort((a, b) => a - b), F = S.flight;
  const sm = (value, unit, digits, src, flag = 'Modelled') => num({ value, unit, digits, flag, source: `${E48_SRC}: ${src}` });
  const p99 = x => sm(R[x].flight_p99_ms / 1e3, ' s', 2, `per_robot_round.laptop_ms_by_multiple.${x}.flight_p99_ms (one seed, laptop × flight.factor)`);
  const within = xs.filter(x => R[x].flight_p99_ms <= DECISION_MS), above = xs.filter(x => R[x].flight_p99_ms > DECISION_MS);
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
  // F-79 (B-118 N12): the timing passes and the factor range: under the decision at the central factor in every pass, and
  // the multiples whose highest pass at the top of the factor range goes over it
  const TP = S.per_robot_round.timing_passes?.by_multiple || {}, passes = xs.map(x => TP[x]?.flight_p99_ms_by_pass?.length || 1);
  const nPass = Math.min(...passes), PASS = { 1: 'the', 2: 'both', 3: 'all three' };
  const top = within.filter(x => (TP[x]?.flight_p99_ms_over_passes_and_factor_range?.[1] ?? R[x].flight_p99_ms_range?.[1] ?? 0) > DECISION_MS);
  const topV = x => sm((TP[x]?.flight_p99_ms_over_passes_and_factor_range?.[1] ?? R[x].flight_p99_ms_range[1]) / 1e3, ' s', 2,
    TP[x] ? `per_robot_round.timing_passes.by_multiple.${x}.flight_p99_ms_over_passes_and_factor_range (highest pass at the top of flight.factor_range)` : `per_robot_round.laptop_ms_by_multiple.${x}.flight_p99_ms_range`);
  const passWord = nPass > 1 ? ` in ${PASS[nPass] || nPass} timing passes` : '';
  const topText = top.length ? `, and over it only at the top of the factor range (up to ${and(top.map(topV))} at ${at(top)})` : '';
  // the values published before the code review of 13 Nov 2026 (results key superseded_<date>_..., per_robot_round)
  const oldKey = Object.keys(S).find(k => /^superseded_/.test(k) && S[k]?.per_robot_round?.laptop_ms_by_multiple);
  const OLD = oldKey && S[oldKey].per_robot_round.laptop_ms_by_multiple;
  const was = OLD && xs.every(x => OLD[x]) ? `Corrected after a code review on ${dateNum({ iso: S[oldKey].superseded_on, source: `${E48_SRC}: ${oldKey}.superseded_on (the date the values were replaced)` })}, which found part of the timing taken with the memory tracer running: before, ${and(xs.map(x => sm(OLD[x].flight_p99_ms / 1e3, ' s', 2, `${oldKey}.per_robot_round.laptop_ms_by_multiple.${x}.flight_p99_ms (as published before)`)))} at ${at(xs)}.` : '';
  return {
    // "0.21 s, 0.92 s and 0.94 s at today's fleet and four and eight times it, under the one-second decision at the central
    // factor in all three timing passes, and over it only at the top of the factor range (up to 1.07 s and 1.10 s ...)"
    bid: !above.length ? `${and(within.map(p99))} at ${at(within)}, under the one-second decision at the central factor${passWord}${topText}`
      : !within.length ? `${and(above.map(p99))} at ${at(above)}, above the one-second decision`
        : `${and(within.map(p99))} at ${at(within)}, within the one-second decision, and ${and(above.map(p99))} at ${at(above)}, above it`,
    above: above.length > 0,
    top: top.length > 0,   // some multiple goes over the decision at the top of the factor range
    was,   // the earlier values, named once on a page (F-79)
    factor: sm(F.factor, '×', 1, 'flight.factor (assumed: the ratio of benchmark scores)', 'Assumed'),
    mem: memText,
    estimate: sm(est, ' MB', 2, 'measured_memory.estimate_mb_for_comparison (the sum of the parts at assumed layouts)'),
    // the simulator's whole-fleet dispatch call, scaled (the 1.12 s the site used to show): about one robot's share
    fleetCall: sm(S.per_robot_round.whole_fleet_dispatch_call_ms_pooled.p99 * F.factor / 1e3, ' s', 2, 'per_robot_round.whole_fleet_dispatch_call_ms_pooled.p99 × flight.factor'),
  };
}
