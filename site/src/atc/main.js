// /atc/ (F-54, the parts that need no BACKEND data yet): what Lunar ATC is (three parts, "the AI suggests, the safety
// program decides", what Earth still does, a diagram in the page), what it puts inside each vehicle (laid out for
// B-81's sizing, E48) and a walk-through of the job market. The walk-through's numbers
// are read from B-72's smoke run (results/ATC_regimes_smoke.json, staged to atc/ by prepare-data), never typed here;
// payments and settlement wait for B-76. Section 5, the encounter sandbox (B-78), is src/atc/sandbox.js; its Mars toggle
// follows with B-82.
import { segmented, h } from '../ui/index.js';
import { upgradeFlags } from '../ui/tooltip.js';
import { num, esc, fmt } from '../components/num.js';
import './atc.css';

const BASE = import.meta.env.BASE_URL, $ = id => document.getElementById(id);
const SRC = 'results/ATC_regimes_smoke.json';
const ui = { year: '2028' };

// ---------- 3. Inside each vehicle: B-81's sizing (E48, results/E48_sizing.json), placeholders until it loads ----------
const SZ = 'results/E48_sizing.json';
const CLASSES = [   // [column, 3D viewer id, E48 class]
  ['Phase 1 LTV', 'clv1', 'LTV1'], ['Cargo LTV (FLEX, Eagle)', 'flex', 'CARGO'], ['Small rover (VIPER, MAPP)', 'viper', 'SMALL'], ['Hopper', 'moonfall', 'HOPPER'], ['Lander', 'MK1', null], ['Base computer', 'atc_computer', 'BASE'],
];
// software parts and failure behaviour are the design; every measured or derived value comes from E48
const ROWS = [
  ['Software parts', c => c === 'Base computer' ? 'job market (leader), ledger, failover to board B' : c === 'Lander' ? 'safety program (landing closures), radio unit' : 'safety program, planner, radio unit', 'design'],
  ['Computing per safety check', 'cpu', 'measured'],
  ['Computing per market round', 'auction', 'measured'],
  ['Memory (planner, checks, reservations, ledger copy)', 'mem', 'measured'],
  ['Radio at the worst 5 km hop', 'link', 'derived'],
  ['Messages per robot-hour', 'msgs', 'measured'],
  ['Power', 'power', 'assumed'],
  ['If it fails', c => c === 'Base computer' ? 'board B takes over; if both fail, the robots elect a leader' : 'stops at the next safe point; others treat its last reservation as occupied', 'design'],
];
const sm = (value, unit, digits, source, flag = 'Modelled') => num({ value, unit, digits, flag, source: `${SZ}: ${source}` });
function cell(S, key, k) {
  const C = S.classes[k], p = `classes.${k}`, F = S.flight, hz = S.targets.safety_hz;
  if (key === 'cpu') {
    const t = C.cpu_safety_check_us, base = k === 'BASE', share = x => t.p99 * x * hz / 1e6;
    return `${sm(t.p99, ' µs', 0, `${p}.cpu_safety_check_us.p99`)} on the laptop (p99${base ? `, the reservation check over ${fmt(t.entries, 0)} entries` : ''}); ` +
      (base ? `${sm(t.p99 * F.factor / 1e3, ' ms', 1, `${p}.cpu_safety_check_us.p99 × flight.factor`)} on the flight core`
        : `${sm(share(F.factor), '', 2, `${p}.cpu_safety_check_us.p99 × flight.factor × targets.safety_hz / 1e6`)} of a flight core at ${fmt(hz, 0)} Hz (${fmt(share(F.factor_range[0]), 2)}–${fmt(share(F.factor_range[1]), 2)})`);
  }
  if (key === 'auction') { const a = C.cpu_auction_round_ms; return `median ${sm(a.median, ' ms', 1, `${p}.cpu_auction_round_ms.median`)}, p99 ${sm(a.p99, ' ms', 1, `${p}.cpu_auction_round_ms.p99`)} (laptop)`; }
  if (key === 'mem') return `${sm(C.peak_memory_mb, ' MB', 2, `${p}.peak_memory_mb`)} of ${num({ value: F.memory_mb, unit: ' MB', digits: 0, flag: 'Spec', source: `${SZ}: flight.memory_mb (${F.processor})` })}`;
  if (key === 'link') {
    const L = C.link;
    return `${sm(L.worst_hop_kbps / 1e3, ' Mbit/s', 1, `${p}.link.worst_hop_kbps`)} (${fmt(L.antenna_m, L.antenna_m % 1 ? 1 : 0)} m antenna, ${fmt(L.tx_power_w, L.tx_power_w % 1 ? 2 : 0)} W)` +
      (k === 'BASE' ? '' : `; the mast in direct view at ${sm(L.reachable_share * 100, ' %', 0, `${p}.link.reachable_share`)} of route points`);
  }
  if (key === 'msgs') {
    if (k === 'BASE') return `receives the fleet's: ${sm(S.h10.link_kbps_needed_20_robots, ' kbit/s', 1, 'h10.link_kbps_needed_20_robots')} for ${fmt(S.targets.robots, 0)} robots`;
    const by = S.messages.per_robot_hour_by_type['1'];
    return `${sm(S.messages.per_robot_hour['1'], '', 0, 'messages.per_robot_hour.1')}: status once a second, ${sm(by['auction (bid, award, claim)'], '', 2, 'messages.per_robot_hour_by_type.1')} for the market`;
  }
  if (key === 'power') return num({ value: C.power_w.value, unit: ' W', digits: 0, flag: C.power_w.flag, source: `${SZ}: ${p}.power_w` });
}
function insideTable(S) {
  const head = h('tr', {}, h('th', { scope: 'col' }, 'What'), ...CLASSES.map(([c, id]) => h('th', { scope: 'col' }, c, h('br'), h('a', { class: 'small', href: `${BASE}vehicles/?v=${id}&atc=1${id === 'atc_computer' ? '&view=cutaway' : ''}` }, 'see it in 3D'))));
  const rows = ROWS.map(([label, fn, kind]) => h('tr', {}, h('th', { scope: 'row' }, label), ...CLASSES.map(([c, , k]) => typeof fn === 'function'
    ? h('td', {}, fn(c), ' ', h('span', { class: 'atc-tag atc-design' }, 'our design'))
    : S && k ? h('td', { html: cell(S, fn, k) })
      : h('td', { class: 'atc-pending' }, S ? 'not sized (E48 sized the robots and the base)' : [h('span', { class: 'atc-tag' }, `B-81 · ${kind}`), h('span', { class: 'visually-hidden' }, ' not measured yet')]))));
  $('atc-inside').replaceChildren(h('table', { class: 'atc-table atc-inside-t' }, h('caption', { class: 'visually-hidden' }, 'What Lunar ATC adds to each kind of vehicle'), h('thead', {}, head), h('tbody', {}, rows)),
    S ? null : h('p', { class: 'small muted' }, 'Tags: "our design" is how Lunar ATC is built; "B-81 · measured / derived / assumed" marks a value still to come.'));
  if (S) { sizingNote(S); upgradeFlags($('atc-inside')); }
}
// what the numbers add up to, against the targets written before the measurement (P3's H10)
function sizingNote(S) {
  const H = S.h10, T = S.targets, F = S.flight, L = S.laptop, M = S.messages, fo = S.failover.by_mtbf, lv = Object.keys(fo).sort((a, b) => a - b);
  const pct = (v, d, src) => sm(v * 100, ' %', d, src), jobs = lv.reduce((a, k) => a + fo[k].items_assigned, 0), twice = lv.reduce((a, k) => a + fo[k].jobs_assigned_twice, 0);
  const ledger = Object.entries(S.ledger_mb_per_year);
  $('atc-sizing').innerHTML = `
    <p class="prose">How it was measured: our Python implementation timed on a laptop (${esc(L.processor)}) and scaled to a radiation-hardened
      flight processor (${esc(F.processor)}) by the ratio of their ${esc(L.benchmark_name)} scores, ${sm(F.factor, '×', 1, 'flight.factor')}
      (range ${fmt(F.factor_range[0], 1)}–${fmt(F.factor_range[1], 1)}). Times are scaled; memory is not, since a slower processor needs no more of it.
      Python is slower than flight code would be, so the computing figures are upper bounds.</p>
    <ul class="prose atc-list">
      <li><strong>Computing.</strong> The safety check of the heaviest case (${esc(H.worst_class_safety)}) takes ${sm(H.safety_core_share_flight_per_robot_10hz, '', 2, 'h10.safety_core_share_flight_per_robot_10hz')} of one flight core per robot at ${fmt(T.safety_hz, 0)} Hz; each robot checks only itself.</li>
      <li><strong>Memory.</strong> At most ${sm(H.peak_memory_mb_max_robot, ' MB', 2, 'h10.peak_memory_mb_max_robot')} on a robot, against ${fmt(F.memory_mb, 0)} MB on the flight board.</li>
      <li><strong>Radio.</strong> ${fmt(T.robots, 0)} robots need ${sm(H.link_kbps_needed_20_robots, ' kbit/s', 1, 'h10.link_kbps_needed_20_robots')} together, against a target of ${fmt(T.link_kbps_20_robots, 0)}. The status message once a second is most of it: ${sm(M.bytes_per_type.status, ' B/s', 0, 'messages.bytes_per_type.status (once a second)')} per robot against a target of ${fmt(T.bytes_per_s_per_robot, 0)}. Market messages come to ${sm(H.market_mb_per_day, ' MB', 3, 'h10.market_mb_per_day')} a day. The share of route points in direct view of the mast is a share of places, not of time; relaying through other robots reaches further and was not measured.</li>
      <li><strong>Ledger.</strong> ${ledger.map(([x, v]) => `${sm(v, ' MB', 2, `ledger_mb_per_year.${x}`)} a year at ${x}× today's traffic`).join(', ')}.</li>
      <li><strong>Failover.</strong> With the base computer failing on average every ${lv.map(k => fmt(+k, 0)).join(', ')} hours, the market was without its base computer ${lv.map(k => pct(fo[k].down_share, k === lv[lv.length - 1] ? 2 : 1, `failover.by_mtbf.${k}.down_share`)).join(', ')} of the time,
        and without any leader ${lv.map(k => pct(fo[k].no_leader_share, 3, `failover.by_mtbf.${k}.no_leader_share`)).join(', ')}. ${sm(twice, '', 0, 'Σ failover.by_mtbf.*.jobs_assigned_twice')} of ${sm(jobs, '', 0, 'Σ failover.by_mtbf.*.items_assigned')} jobs were given to two robots.</li>
    </ul>`;
  upgradeFlags($('atc-sizing'));
}

// ---------- 4. The market walk-through, numbers from the smoke run ----------
const REG = {   // the run's decision places, in plain words
  O_ORACLE: 'a perfect pooled market (the yardstick)', 'C_LEADER loss 0.10': 'the market run on the Moon by the base computer, 1 message in 10 lost',
  'B_EARTH strict': 'one pooled dispatcher on Earth that acts only while Earth is in view', 'A_EARTH strict': 'each company alone, dispatched from Earth only while Earth is in view',
};
function render(doc) {
  const Y = doc.years[ui.year], src = `${SRC} (B-72 smoke run, ${ui.year}, ${doc.seeds.length} seeds: mean ± sd)`;
  const v = (reg, key, { pct = false, digits = 1, unit = '' } = {}) => {
    const x = Y[reg]?.[key]; if (!x) return '–';
    const [m, sd] = x, k = pct ? 100 : 1;
    return num({ value: m * k, pm: sd * k, unit: pct ? '%' : unit, digits, flag: 'Modelled', source: `${src}: ${reg} → ${key}` });
  };
  const said = reg => `<em>${esc(REG[reg])}</em>`;
  const steps = [
    { t: 'A job is posted', p: 'A lander comes down with cargo for the base. The job goes on one board that every company’s robots can see: what, from where, to where, how urgent.',
      n: `The board has to be reachable to post anything. With ${said('B_EARTH strict')}, it was out of reach ${v('B_EARTH strict', 'atc_decider_down_share', { pct: true, digits: 0 })} of the time; with ${said('C_LEADER loss 0.10')}, ${v('C_LEADER loss 0.10', 'atc_decider_down_share', { pct: true, digits: 2 })}.` },
    { t: 'Robots offer prices', p: 'Each free robot works out what the job would cost it: the drive there, the load, its battery and the work it already has. A small learned policy nudges the offer where experience says the plain cost is off. Heavy loads can get an offer from a team of two robots, even from different companies.',
      n: `Talking is cheap: with ${said('C_LEADER loss 0.10')}, each robot sent ${v('C_LEADER loss 0.10', 'atc_msgs_per_robot_h')} messages an hour. Cross-company team lifts: ${v('C_LEADER loss 0.10', 'team_lifts')} a year in the shared market, ${v('A_EARTH strict', 'team_lifts', { digits: 0 })} with ${said('A_EARTH strict')}. The learned policy is not in this run yet (task B-74).` },
    { t: 'The cheapest offer wins', p: 'The board gives the job to the lowest offer and tells the robots. The winner’s planner suggests a route; its safety program reserves the road ahead and decides, move by move.',
      n: `How long an urgent load waited, on average: ${v('O_ORACLE', 'atc_urgent_wait_mean_h', { unit: ' h' })} with ${said('O_ORACLE')}, ${v('C_LEADER loss 0.10', 'atc_urgent_wait_mean_h', { unit: ' h' })} with ${said('C_LEADER loss 0.10')}, ${v('B_EARTH strict', 'atc_urgent_wait_mean_h', { unit: ' h' })} with ${said('B_EARTH strict')}, and ${v('A_EARTH strict', 'atc_urgent_wait_mean_h', { unit: ' h' })} with ${said('A_EARTH strict')}.` },
    { t: 'The winner is paid', p: 'When the cargo is delivered, the ledger on the base computer records a payment from the cargo’s owner to the robot’s owner: per item at the second-lowest offer, or at a posted price per tonne-kilometre with the gains of team lifts shared fairly.',
      n: null, wait: 'The payment rules and what each company earns and pays are being simulated (task B-76).' },
    { t: 'Earth settles up later', p: 'Nothing waits for Earth: the robots keep working on the Moon’s ledger. When Earth is back in view, the ledger is sent home, the companies settle the money and an audit checks a sample of the records.',
      n: `Work does not pile up meanwhile: at the end of a blackout, the cargo still waiting was ${v('C_LEADER loss 0.10', 'atc_backlog_end_blackout_t_mean', { unit: ' t' })} with ${said('C_LEADER loss 0.10')}, against ${v('B_EARTH strict', 'atc_backlog_end_blackout_t_mean', { unit: ' t' })} with ${said('B_EARTH strict')}.`, wait: 'The settlement and audit numbers come with task B-76.' },
  ];
  $('atc-steps').replaceChildren(...steps.map((s, i) => h('li', { class: 'atc-step' },
    h('p', { class: 'atc-step-n ui-label' }, `Step ${i + 1}`), h('h3', {}, s.t), h('p', {}, s.p),
    s.n ? h('p', { class: 'atc-num', html: `<span class="ui-label">In the test run</span> ${s.n}` }) : null,
    s.wait ? h('p', { class: 'atc-pending-line' }, h('span', { class: 'atc-tag' }, 'coming'), ' ', s.wait) : null)));
  upgradeFlags($('atc-steps'));
}

insideTable(null);
fetch(BASE + 'atc/E48_sizing.json').then(r => (r.ok && /json/.test(r.headers.get('content-type') || '') ? r.json() : null)).then(S => S && insideTable(S)).catch(() => {});
// section 5, the encounter sandbox (B-78): its chunk loads when the section comes near (a passive scroll check, so a
// jump to #sandbox also triggers it); its 3D view loads only when the visitor starts it;
// the learned correction (F-54 item 3, bid.js) the same way, near the end of section 4
const whenNear = (id, load) => { const go = () => { if ($(id).getBoundingClientRect().top > innerHeight + 600) return; removeEventListener('scroll', go); load(); }; addEventListener('scroll', go, { passive: true }); go(); };
whenNear('atc-bid', () => import('./bid.js').then(m => m.mount()));
whenNear('sandbox', () => import('./sandbox.js').then(s => s.mount()));
try {
  const r = await fetch(BASE + 'atc/ATC_regimes_smoke.json'); if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const doc = await r.json(), years = Object.keys(doc.years);
  ui.year = years[0];
  const load = /-L(\d+)-/.exec(doc.scenario)?.[1], eq = /-3eq-/.test(doc.scenario);   // from the scenario's name, e.g. p5-3eq-L30-T10
  $('atc-run-desc').textContent = `task B-72: ${eq ? 'three equally sized companies' : 'several companies'}${load ? `, cargo rovers about ${load} % busy` : ''}, ${doc.seeds.length} seeds a year, start years ${years.join(' and ')}`;
  $('atc-year').append(segmented({ legend: 'Start year of the simulated base', options: years.map(y => ({ value: y, label: y })), value: ui.year, onChange: y => { ui.year = y; render(doc); } }).el);
  render(doc);
} catch (e) {
  $('atc-steps').replaceChildren(h('li', {}, `The test-run numbers could not load (${e.message}). The steps above still describe the market.`));
  $('atc-run-desc').textContent = 'not loaded';
}
