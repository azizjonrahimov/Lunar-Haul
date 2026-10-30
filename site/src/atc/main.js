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
    { t: 'The winner is paid', p: 'When the cargo is delivered, the ledger on the base computer records the payments. The cargo’s owner pays a price per tonne-kilometre set on Earth. The robot’s owner is paid by one of three rules: its own offer (first price), the best offer it beat (second price), or the same posted price, with the gains of working together shared by Shapley value. The base operator covers any difference.',
      n: null, e: MK && `The posted price, set on Earth to recover the cost: ${Object.entries(MK.tariff_usd_per_tkm).map(([s, t]) => `${mk(t, ' USD', 0, `tariff_usd_per_tkm.${s}`)} per tonne-km with ${esc(MK.design.splits[s])}`).join(', ')}. What each rule cost the operator is in the table below.`,
      wait: 'The payment rules and what each company earns and pays are being simulated (task B-76).' },
    { t: 'Earth settles up later', p: 'Nothing waits for Earth: the robots keep working on the Moon’s ledger. When Earth is back in view, the ledger is sent home, the companies settle the money and an audit checks a sample of the records.',
      n: `Work does not pile up meanwhile: at the end of a blackout, the cargo still waiting was ${v('C_LEADER loss 0.10', 'atc_backlog_end_blackout_t_mean', { unit: ' t' })} with ${said('C_LEADER loss 0.10')}, against ${v('B_EARTH strict', 'atc_backlog_end_blackout_t_mean', { unit: ' t' })} with ${said('B_EARTH strict')}.`,
      e: MK && settleLine(), wait: 'The settlement and audit numbers come with task B-76.' },
  ];
  $('atc-steps').replaceChildren(...steps.map((s, i) => h('li', { class: 'atc-step' },
    h('p', { class: 'atc-step-n ui-label' }, `Step ${i + 1}`), h('h3', {}, s.t), h('p', {}, s.p),
    s.e ? h('p', { class: 'atc-num', html: `<span class="ui-label">In the market experiment (E46)</span> ${s.e}` }) : null,
    s.n ? h('p', { class: 'atc-num', html: `<span class="ui-label">In the test run</span> ${s.n}` }) : null,
    s.wait && !s.e ? h('p', { class: 'atc-pending-line' }, h('span', { class: 'atc-tag' }, 'coming'), ' ', s.wait) : null)));
  upgradeFlags($('atc-steps'));
}

// ---------- 4b. The market experiment (E46, B-76; P3's H5), from atc/E46_summary.json ----------
const MKS = 'results/E46_fit.json', MKC = 'results/E46_cells.csv';
let MK = null, smoke = null;
const mk = (value, unit, digits, source, file = MKS) => num({ value, unit, digits, flag: 'Modelled', source: `${file}: ${source}` });
const musd = (v, src, d = 2) => mk(v / 1e6, '', d, `${src} / 1e6`);
const ci = (x, src, d = 1) => `${musd(x.mean, `${src}.mean`, d)} (${musd(x.lo, `${src}.lo`, d)} to ${musd(x.hi, `${src}.hi`, d)})`;
const RULE = { none: 'No payments', first: 'First price', second: 'Second price', posted: 'Posted price' };
const paidHonest = () => MK.honest.filter(c => c.rule !== 'none');
const cellSrc = c => `${c.rule} ${c.split}, k 1, q 0`;
function settleLine() {
  const P = paidHonest(), lo = P.reduce((a, c) => (c.settled_earth_musd < a.settled_earth_musd ? c : a)), hi = P.reduce((a, c) => (c.settled_earth_musd > a.settled_earth_musd ? c : a));
  const open = Math.max(...P.map(c => c.open_end_musd));
  const W = MK.settled_with_transfers, sp = MK.design.splits;
  return `With honest offers, the cash that had to change hands through Earth in a year was ${mk(lo.settled_earth_musd, '', 1, `settled_earth_musd (${cellSrc(lo)})`, MKC)} to ${mk(hi.settled_earth_musd, ' M USD', 1, `settled_earth_musd (${cellSrc(hi)})`, MKC)} across the three paying rules and both splits. ` +
    (W ? `Under the posted price, including the Shapley transfers: ${Object.keys(W).map(s => `${ci(W[s], `settled_with_transfers.${s}`)} M USD with ${esc(sp[s])}`).join(', ')}. ` : '') +
    `Owed but not yet settled when the year ended: ${open < 0.01 ? 'under 0.01 M USD in every case' : mk(open, ' M USD', 2, 'max open_end_musd', MKC)}. With no payments, nothing moves.`;
}
// a clause's verdict from its intervals by PREREG change 7, checked against the file's own flag
const VERDICT = { clause1: c => c.lo > 0, clause2: c => c.diff_mean < 0 && c.diff_hi < 0, clause3: c => c.min_upper >= 0 };
function verdict(q, c) {
  const ok = VERDICT[q](c), word = ok ? 'supported' : 'not supported';
  return `<span class="atc-tag atc-verdict${ok ? ' atc-yes' : ''}">${word}</span>${ok === c.supported ? '' : ` <span class="atc-err">(the file says ${c.supported ? 'supported' : 'not supported'})</span>`}`;
}
// why first and second price run a deficit with honest offers (budget and second_price in the fit)
function opNote(D, S) {
  const B = MK.budget.first, P = MK.second_price, pc = (s, k) => mk(P[s][k] * 100, ' %', 0, `second_price.${s}.${k} × 100`);
  return ` Under first price, carriers were paid their honest offers, their true cost, against what shippers paid: ${S.map(s => `${musd(B[s].payouts_mean, `budget.first.${s}.payouts_mean`, 1)} against ${musd(B[s].receipts_mean, `budget.first.${s}.receipts_mean`, 1)} M USD with ${esc(D.splits[s])}`).join(', ')}.
      The price set on Earth fell short of the cost it was meant to recover (a calibration gap).${P ? ` Under second price, a carrier is never paid below its own offer, and ${S.map(s => pc(s, 'reserve_share')).join(' and ')} of jobs
      had too few competing robots to set a price, so the posted price set it (${S.map(s => pc(s, 'with_alternative_share')).join(' and ')} had enough).` : ''}`;
}
// each company under a paying rule against the same market with no payments (paired by seed), and the posted price's
// Shapley transfers; a case counts on one side only when its whole interval is
function noneTables(D, S) {
  const V = MK.vs_none, T = MK.transfers, own = D.owners, cols = S.map(s => `<th scope="col">${esc(D.splits[s])}</th>`).join('');
  const side = own.map(o => { const c = Object.values(V).flatMap(r => S.map(s => r[s][o])); return `company ${esc(o)} above in ${c.filter(x => x.lo > 0).length} and below in ${c.filter(x => x.hi < 0).length}`; });
  return `
    <p class="prose">A company’s profit alone is dominated by its cargo’s delay cost at its own value of time, so every pooled rule clears it by a wide margin.
      The harder comparison is the same pooled market with no payments. Of the ${Object.keys(V).length * S.length} cases (paying rule and split), ${side.join(', ')}.</p>
    <div class="atc-table-wrap"><table class="atc-table atc-mk-t">
      <caption>Each company’s profit under the rule less its profit with no payments, paired by seed (M USD a year, mean and 95 % interval)</caption>
      <thead><tr><th scope="col">Rule</th><th scope="col">Company</th>${cols}</tr></thead>
      <tbody>${Object.keys(V).map(r => own.map((o, i) => `<tr>${i ? '' : `<th scope="row" rowspan="${own.length}">${RULE[r] || esc(r)}</th>`}<td>${esc(o)}</td>${S.map(s => `<td class="n">${ci(V[r][s][o], `vs_none.${r}.${s}.${o}`)}</td>`).join('')}</tr>`).join('')).join('')}</tbody>
    </table></div>
    <div class="atc-table-wrap"><table class="atc-table atc-mk-t">
      <caption>Posted price: the Shapley transfers (plus: the company receives) and the money settled through Earth with them (M USD a year)</caption>
      <thead><tr><th scope="col">Company</th>${cols}</tr></thead>
      <tbody>${own.map(o => `<tr><th scope="row">${esc(o)}</th>${S.map(s => `<td class="n">${ci(T[s][o], `transfers.${s}.${o}`)}</td>`).join('')}</tr>`).join('')}
        <tr><th scope="row">Settled, including the Shapley transfers</th>${S.map(s => `<td class="n">${ci(MK.settled_with_transfers[s], `settled_with_transfers.${s}`)}</td>`).join('')}</tr></tbody>
    </table></div>`;
}
function marketPart() {
  const D = MK.design, S = Object.keys(D.splits), H = MK.H5, iv = (c, s, q, lo, hi) => `${musd(c[lo], `H5.${s}.${q}.${lo}`)} to ${musd(c[hi], `H5.${s}.${q}.${hi}`)}`;
  const claim = {
    clause1: ['Under first price, a company gains by scaling its offers', (c, s) => `${musd(c.gain, `H5.${s}.clause1.gain`)} M USD a year (${iv(c, s, 'clause1', 'lo', 'hi')}), company ${esc(c.owner)} at k ${c.k}`],
    clause2: ['Second price shrinks that gain', (c, s) => `${musd(c.diff_mean, `H5.${s}.clause2.diff_mean`)} M USD a year (${iv(c, s, 'clause2', 'diff_lo', 'diff_hi')}), second less first, paired by seed`],
    clause3: ['Posted price with Shapley sharing leaves no company worse off than alone', (c, s) => `smallest bounds over every company in every coalition: lower ${musd(c.min_lower, `H5.${s}.clause3.min_lower`, 1)}, upper ${musd(c.min_upper, `H5.${s}.clause3.min_upper`, 1)} M USD a year`],
  };
  const hon = (r, s) => MK.honest.find(c => c.rule === r && c.split === s), rules = D.rules.filter(r => hon(r, S[0]));
  const eff = S.map(s => [...new Set(MK.honest.filter(c => c.split === s).map(c => c.efficiency_loss_pct))]), same = eff.every(e => e.length === 1);
  const coal = S.map(s => H[s].clause3.rows), cr = coal[0];
  $('atc-e46').innerHTML = `
    <p class="prose">Experiment E46 tested P3’s hypothesis H5, written down before the run: ${fmt(D.seeds, 0)} simulated years for each case,
      three companies with ${S.map(s => esc(D.splits[s])).join(' or ')}, and the payment rules above. To test cheating, one company scaled
      its offers by k = ${D.k_levels.join(', ')}, with ${D.q_levels.map(q => fmt(q * 100, 0)).join(', ')} % of records audited
      and a fine of ${fmt(MK.audit_penalty_multiple, 0)} times the misstatement. Intervals are 95 % bootstrap intervals over the seeds.</p>
    <div class="atc-table-wrap"><table class="atc-table atc-mk-t">
      <caption>H5, clause by clause (USD a year)</caption>
      <thead><tr><th scope="col">Clause</th>${S.map(s => `<th scope="col">${esc(D.splits[s])}</th>`).join('')}</tr></thead>
      <tbody>${Object.entries(claim).map(([q, [t, f]], i) => `<tr><th scope="row">${i + 1}. ${t}</th>${S.map(s => `<td>${f(H[s][q], s)}<br>${verdict(q, H[s][q])}</td>`).join('')}</tr>`).join('')}</tbody>
    </table></div>
    <p class="small muted">The page recomputes each verdict from the intervals, by the rules registered before the run: clause 1 holds if its interval lies
      above zero; clause 2 if the difference and its upper bound are below zero; clause 3 if the smallest upper bound is not below zero.
      Under the posted price a company’s result is its Shapley value of the shared cost, not cash.</p>
    <div class="atc-table-wrap"><table class="atc-table atc-mk-t">
      <caption>With honest offers, per payment rule (M USD a year)</caption>
      <thead><tr><th scope="col" rowspan="2">Rule</th><th scope="colgroup" colspan="${S.length}">Operator’s balance</th><th scope="colgroup" colspan="${S.length}">Settled through Earth in cash</th></tr>
        <tr>${[0, 1].map(() => S.map(s => `<th scope="col">${esc(D.splits[s])}</th>`).join('')).join('')}</tr></thead>
      <tbody>${rules.map(r => `<tr><th scope="row">${RULE[r] || esc(r)}</th>${['operator_budget_musd', 'settled_earth_musd'].map(k => S.map(s => { const c = hon(r, s); return `<td class="n">${mk(c[k] === 0 ? 0 : c[k], '', 2, `${k} (${cellSrc(c)})`, MKC)}</td>`; }).join('')).join('')}</tr>`).join('')}</tbody>
    </table></div>
    <ul class="prose atc-list">
      <li><strong>The operator’s balance.</strong> Shippers pay the posted price under every paying rule, so a minus means the operator paid carriers
        more than it collected. Under the posted price it is zero by construction: the same price goes in and out.${MK.budget ? opNote(D, S) : ''}</li>
      <li><strong>Efficiency.</strong> Against a perfect pooled market (the oracle), the market’s system cost (the carriers’ true cost plus the cost of delay) was higher by
        ${S.map((s, i) => `${mk(eff[i][0], ' %', 1, `efficiency_loss_pct (${cellSrc(hon(rules[0], s))})`, MKC)} with ${esc(D.splits[s])}`).join(' and ')}${same ? ', the same under every rule: payments are worked out afterwards, on one allocation' : ' (it varies by rule; see the cells table)'}.</li>
      <li><strong>${MK.cells.ir_violations ? 'Some companies worse off.' : 'No company worse off.'}</strong> Over all ${mk(MK.cells.n, '', 0, 'rows', MKC)} cases (every rule, split, k and audit rate),
        a company made less on average than working alone ${mk(MK.cells.ir_violations, '', 0, 'Σ ir_violations', MKC)} times.</li>
    </ul>${MK.vs_none ? noneTables(D, S) : ''}
    <details class="atc-mk-more"><summary>Every company in every coalition (clause 3)</summary>
      <div class="atc-table-wrap"><table class="atc-table atc-mk-t">
        <caption class="small">Shapley value in the coalition less profit alone, M USD a year, mean and 95 % interval</caption>
        <thead><tr><th scope="col">Coalition</th><th scope="col">Company</th>${S.map(s => `<th scope="col">${esc(D.splits[s])}</th>`).join('')}</tr></thead>
        <tbody>${cr.map((r, i) => `<tr><td>${esc(r.coalition)}</td><td>${esc(r.owner)}</td>${S.map((s, j) => { const x = coal[j].find(y => y.coalition === r.coalition && y.owner === r.owner), src = `H5.${s}.clause3.rows[${coal[j].indexOf(x)}]`;
          return x ? `<td class="n">${ci(x, src)}</td>` : '<td>–</td>'; }).join('')}</tr>`).join('')}</tbody>
      </table></div></details>`;
  upgradeFlags($('atc-e46'));
  $('atc-e46-sec').hidden = false;
}
fetch(BASE + 'atc/E46_summary.json').then(r => (r.ok && /json/.test(r.headers.get('content-type') || '') ? r.json() : null))
  .then(d => { if (d) { MK = d; marketPart(); if (smoke) render(smoke); } }).catch(() => {});

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
  const doc = smoke = await r.json(), years = Object.keys(doc.years);
  ui.year = years[0];
  const load = /-L(\d+)-/.exec(doc.scenario)?.[1], eq = /-3eq-/.test(doc.scenario);   // from the scenario's name, e.g. p5-3eq-L30-T10
  $('atc-run-desc').textContent = `task B-72: ${eq ? 'three equally sized companies' : 'several companies'}${load ? `, cargo rovers about ${load} % busy` : ''}, ${doc.seeds.length} seeds a year, start years ${years.join(' and ')}`;
  $('atc-year').append(segmented({ legend: 'Start year of the simulated base', options: years.map(y => ({ value: y, label: y })), value: ui.year, onChange: y => { ui.year = y; render(doc); } }).el);
  render(doc);
} catch (e) {
  $('atc-steps').replaceChildren(h('li', {}, `The test-run numbers could not load (${e.message}). The steps above still describe the market.`));
  $('atc-run-desc').textContent = 'not loaded';
}
