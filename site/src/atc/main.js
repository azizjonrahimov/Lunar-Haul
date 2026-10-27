// /atc/ (F-54, the parts that need no BACKEND data yet): what Lunar ATC is (three parts, "the AI suggests, the safety
// program decides", what Earth still does, a diagram in the page), what it puts inside each vehicle (laid out for
// B-81's sizing table, placeholders until it lands) and a walk-through of the job market. The walk-through's numbers
// are read from B-72's smoke run (results/ATC_regimes_smoke.json, staged to atc/ by prepare-data), never typed here;
// payments and settlement wait for B-76. The encounter sandbox and the Mars toggle follow with B-78 and B-82.
import { segmented, h } from '../ui/index.js';
import { upgradeFlags } from '../ui/tooltip.js';
import { num, esc } from '../components/num.js';
import './atc.css';

const BASE = import.meta.env.BASE_URL, $ = id => document.getElementById(id);
const SRC = 'results/ATC_regimes_smoke.json';
const ui = { year: '2028' };

// ---------- 3. Inside each vehicle: B-81's table, with placeholders until it lands ----------
const CLASSES = [
  ['Phase 1 LTV', 'clv1'], ['Cargo LTV (FLEX, Eagle)', 'flex'], ['Small rover (VIPER, MAPP)', 'viper'], ['Hopper', 'moonfall'], ['Lander', 'MK1'], ['Base computer', 'atc_computer'],
];
// software parts are the design (known now); every measured or derived value comes from B-81
const ROWS = [
  ['Software parts', c => c === 'Base computer' ? 'job market (leader), ledger, failover to board B' : c === 'Lander' ? 'safety program (landing closures), radio unit' : 'safety program, planner, radio unit', 'design'],
  ['Computing per safety check', null, 'measured'],
  ['Computing per market round', null, 'measured'],
  ['Memory (planner, checks, reservations, ledger copy)', null, 'measured'],
  ['Radio: data rate at the worst hop', null, 'derived'],
  ['Messages per robot-hour', null, 'measured'],
  ['Power', null, 'assumed'],
  ['If it fails', c => c === 'Base computer' ? 'board B takes over; if both fail, the robots elect a leader' : 'stops at the next safe point; others treat its last reservation as occupied', 'design'],
];
function insideTable() {
  const head = h('tr', {}, h('th', { scope: 'col' }, 'What'), ...CLASSES.map(([c, id]) => h('th', { scope: 'col' }, c, h('br'), h('a', { class: 'small', href: `${BASE}vehicles/?v=${id}&atc=1${id === 'atc_computer' ? '&view=cutaway' : ''}` }, 'see it in 3D'))));
  const rows = ROWS.map(([label, fn, kind]) => h('tr', {}, h('th', { scope: 'row' }, label), ...CLASSES.map(([c]) => fn
    ? h('td', {}, fn(c), ' ', h('span', { class: 'atc-tag atc-design' }, 'our design'))
    : h('td', { class: 'atc-pending' }, h('span', { class: 'atc-tag' }, `B-81 · ${kind}`), h('span', { class: 'visually-hidden' }, ' not measured yet')))));
  $('atc-inside').replaceChildren(h('table', { class: 'atc-table' }, h('caption', { class: 'visually-hidden' }, 'What Lunar ATC adds to each kind of vehicle'), h('thead', {}, head), h('tbody', {}, rows)),
    h('p', { class: 'small muted' }, 'Tags: "our design" is how Lunar ATC is built; "B-81 · measured / derived / assumed" marks a value still to come and how it will be obtained: measured on our implementation, derived from a measurement with a stated factor, or assumed with a range.'));
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

insideTable();
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
