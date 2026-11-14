// F-81: /atc/ section 3's measurement note ("How it was measured" and the list under it), from results/E48_sizing.json.
// Pure (no DOM, no Vite), so sizing.js sets it in the page and a Node test reads the text as rendered.
import { num, esc, fmt } from '../components/num.js';
import { robotRound } from './e48-robot.js';

const SZ = 'results/E48_sizing.json';
export const sm = (value, unit, digits, source, flag = 'Modelled') => num({ value, unit, digits, flag, source: `${SZ}: ${source}` });

// F-67: airtime at the measured hop count (E48 airtime.rows)
function air(S, a) {
  const R = S.airtime.rows, i = R.findIndex(x => x.sizes.startsWith('LRIP secured, MAC 8') && String(x.hops).startsWith('measured') && x.access.startsWith(a)), r = R[i];
  return r ? `${sm(r.channel_kbps_needed, ' kbit/s', 2, `airtime.rows[${i}].channel_kbps_needed`)} (${r.fits_16_kbps ? 'fits' : 'does not fit'} the ${fmt(S.airtime.channel_kbps, 0)} kbit/s channel)` : '–';
}
export function sizingHtml(S) {
  const H = S.h10, T = S.targets, F = S.flight, L = S.laptop, M = S.messages, fo = S.failover.by_mtbf, lv = Object.keys(fo).sort((a, b) => a - b);
  const pct = (v, d, src) => sm(v * 100, ' %', d, src), jobs = lv.reduce((a, k) => a + fo[k].items_assigned, 0), twice = lv.reduce((a, k) => a + fo[k].jobs_assigned_twice, 0);
  const ledger = Object.entries(S.ledger_mb_per_year), RR = robotRound(S);   // F-72 (B-105)
  return `
    <p class="prose">How it was measured: our Python implementation timed on a laptop (${esc(L.processor)}) and scaled to a radiation-hardened
      flight processor (${esc(F.processor)}) by the ratio of their ${esc(L.benchmark_name)} scores, ${sm(F.factor, '×', 1, 'flight.factor')}
      (range ${fmt(F.factor_range[0], 1)}–${fmt(F.factor_range[1], 1)}). Times are scaled; memory is not, since a slower processor needs no more of it.
      Python is slower than flight code would be, so the computing figures are upper bounds.</p>
    <ul class="prose atc-list">
      <li><strong>Computing.</strong> The safety check of the heaviest case (${esc(H.worst_class_safety)}) takes ${sm(H.safety_core_share_flight_per_robot_10hz, '', 2, 'h10.safety_core_share_flight_per_robot_10hz')} of one flight core per robot at ${fmt(T.safety_hz, 0)} Hz; each robot checks only itself.${RR ? ` ${RR.above ? 'The bidding does not fit at every fleet size' : RR.top ? 'The bidding fits at the central factor but not across the whole factor range' : 'The bidding fits at every fleet size'}: one robot's own bid computation in a market round, timed on the laptop in one month of one seed and scaled by the same assumed factor (not flight hardware), takes ${RR.bid} (99th percentile). The market-round row above is the simulator's call for the whole fleet (${RR.fleetCall} at the 99th percentile, scaled), about one robot's share, not a vehicle's computation.${RR.was ? ` ${RR.was}` : ''}` : ''}</li>
      <li><strong>Memory.</strong> ${RR ? `Measured at ${RR.mem} for every on-robot part held at once (what Python allocates; the interpreter and the code are not counted), against the estimate of ${RR.estimate} from the sum of the parts` : `About ${sm(H.peak_memory_mb_max_robot, ' MB', 2, 'h10.peak_memory_mb_max_robot (an estimate: the sum of the parts, not a measurement)')} on a robot by an estimate`}, and ${fmt(F.memory_mb, 0)} MB on the flight board.</li>
      <li><strong>Radio.</strong> At LRIP v0.1 sizes, ${fmt(T.robots, 0)} robots need ${sm(H.link_kbps_needed_20_robots_secured_mac8, ' kbit/s', 2, 'h10.link_kbps_needed_20_robots_secured_mac8')} together with every message secured (an 8-byte authentication code). On a shared channel that load costs more airtime: ${air(S, 'scheduled')} on a channel the base schedules, and ${air(S, 'slotted')} with random access. The status message once a second is most of it: ${sm(M.bytes_per_type.status, ' B/s', 0, 'messages.bytes_per_type.status (once a second)')} per robot against a target of ${fmt(T.bytes_per_s_per_robot, 0)}. Market messages come to ${sm(H.market_mb_per_day, ' MB', 3, 'h10.market_mb_per_day')} a day. The share of route points in direct view of the mast is a share of places, not of time; relaying through other robots reaches further and was not measured.</li>
      <li><strong>Ledger.</strong> ${ledger.map(([x, v]) => `${sm(v, ' MB', 2, `ledger_mb_per_year.${x}`)} a year at ${x}× today's traffic`).join(', ')}.</li>
      <li><strong>Failover.</strong> With the base computer failing on average every ${lv.map(k => fmt(+k, 0)).join(', ')} hours, the market was without its base computer ${lv.map(k => pct(fo[k].down_share, k === lv[lv.length - 1] ? 2 : 1, `failover.by_mtbf.${k}.down_share`)).join(', ')} of the time,
        and without any leader ${lv.map(k => pct(fo[k].no_leader_share, 3, `failover.by_mtbf.${k}.no_leader_share`)).join(', ')}. ${sm(twice, '', 0, 'Σ failover.by_mtbf.*.jobs_assigned_twice')} of ${sm(jobs, '', 0, 'Σ failover.by_mtbf.*.items_assigned')} jobs were given to two robots.</li>
    </ul>`;
}

