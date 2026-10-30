// /atc/ section 4 (F-54 item 3): the learned correction to each robot's offer, run in the browser from
// data/policies/atc_bid_linear_v1.json (staged to lab/policies/ by prepare-data) and checked against Python's runtime
// (lunarsim/atc/learned.py Policy) on the file's 50 check vectors. The weights are read from the file and described
// as P1 Section 5.6 does: a positive weight lowers the offer, and so favours the item; sizes in hours per unit of the
// feature as the file scales it. The linear model is the method (LEAD, 27 Oct); the MLP file stays the record.
import { segmented, h } from '../ui/index.js';
import { fmt } from '../components/num.js';
import { AtcBidPolicy, checkBid, FEATURES, TARGET_H } from './bid-policy.js';

const BASE = import.meta.env.BASE_URL, $ = id => document.getElementById(id);
const FILE = 'atc_bid_linear_v1';
// ---------- what each feature is, in plain words, and its unit as the file scales it ----------
// unit(scale): the feature's unit as the policy file scales it (x_norm = x / scale)
const PLAIN = {
  job_h: ['Planned hours of the job', s => `${s} h of planned job`],
  age_d: ['Time the item has already waited', s => (s === 1 ? 'day' : `${s} days`)],
  prio: ['Priority (urgent −1, normal 0, deferrable +1)', s => (s === 1 ? 'step' : `${s} steps`)],
  mass_frac: ['Load as a share of the robot’s capacity', () => 'full load'],
  approach_h: ['Hours to drive to the pad', s => (s === 1 ? 'hour' : `${s} h`)],
  battery: ['Battery state of charge', () => 'full battery'],
  dark_or_low: ['Time until dark or an empty battery (counted up to 2 weeks)', () => '2 weeks'],
  link_base: ['In radio reach of the base computer', () => 'yes rather than no'],
  heard: ['Robots it hears directly', () => '8 robots'],
  queue: ['Claims it already holds', () => '5 claims'],
  bundle_n: ['Items in the bundle', () => '10 items'],
  slack_d: ['Slack to the item’s target time', s => `${s} days`],
  landing: ['Time until the next landing at the pad (counted up to 2 weeks)', () => '2 weeks'],
};
const unitOf = (f, scale) => PLAIN[f][1](scale);

// ---------- the weights, as a diverging bar list ----------
function weights(policy) {
  const w = policy.layers[0].w[0], rows = FEATURES.map((f, i) => ({ f, w: w[i], unit: unitOf(f, policy.scale[i]) })).sort((a, b) => Math.abs(b.w) - Math.abs(a.w));
  const max = Math.max(...rows.map(r => Math.abs(r.w)));
  return h('div', { class: 'atc-bidw', role: 'table', 'aria-label': 'Weights of the learned correction, largest first' },
    h('div', { class: 'atc-bidw-row atc-bidw-head', role: 'row' },
      h('span', { role: 'columnheader' }, 'What the robot knows'), h('span', { role: 'columnheader', class: 'atc-bidw-axis' }, h('span', {}, '← raises the offer'), h('span', {}, 'lowers it, favours the item →')),
      h('span', { role: 'columnheader', class: 'n' }, 'Hours per')),
    rows.map(r => h('div', { class: 'atc-bidw-row', role: 'row', title: `${PLAIN[r.f][0]}: ${r.w > 0 ? 'lowers' : 'raises'} the offer by ${fmt(Math.abs(r.w), 2)} h per ${r.unit}` },
      h('span', { role: 'rowheader' }, PLAIN[r.f][0]),
      h('span', { role: 'cell', class: 'atc-bidw-track', 'aria-hidden': 'true' },
        h('i', { class: r.w > 0 ? 'down' : 'up', style: `width:${(Math.abs(r.w) / max * 50).toFixed(2)}%` })),
      h('span', { role: 'cell', class: 'n' }, `${r.w > 0 ? '+' : '−'}${fmt(Math.abs(r.w), 2)} h`, h('span', { class: 'muted small' }, ` per ${r.unit}`)))));
}

// ---------- try it: one robot and one item, in plain units ----------
const S = { prio: 1, job: 4, waited: 6, load: 50, approach: 1, battery: 80, heard: 3 };
const FIXED = { dark_or_low: 1, link_base: 1, queue: 1 / 5, bundle_n: 1 / 10, landing: 1 };   // no dark or landing within 2 weeks, in reach of the base, 1 claim, 1 item
function featuresOf(s) {
  const x = { job_h: s.job, age_d: s.waited / 24, prio: s.prio - 2, mass_frac: s.load / 100, approach_h: s.approach, battery: s.battery / 100,
    heard: s.heard / 8, slack_d: (TARGET_H[s.prio] - s.waited - s.job) / 24, ...FIXED };
  return FEATURES.map(f => x[f]);
}
function tryIt(policy) {
  const out = h('p', { class: 'atc-bid-out', 'aria-live': 'polite' });
  const draw = () => {
    const g = policy.correction(featuresOf(S)), slack = TARGET_H[S.prio] - S.waited - S.job;
    out.replaceChildren(h('span', { class: 'ui-label' }, 'The learned correction '),
      h('strong', {}, `${g >= 0 ? 'lowers' : 'raises'} this robot’s offer by ${fmt(Math.abs(g), 2)} h`),
      ` of the item’s urgency price, ${g >= 0 ? 'so it is more likely to win the item' : 'so it is less likely to win the item'}. Slack to the target time: ${fmt(slack, 0)} h.`);
  };
  const slider = (key, label, min, max, step, unit) => {
    const val = h('output', {}, `${S[key]}${unit}`);
    return h('label', { class: 'atc-bid-sl' }, h('span', { class: 'ui-label' }, label, ' ', val),
      h('input', { type: 'range', min: String(min), max: String(max), step: String(step), value: String(S[key]), oninput: e => { S[key] = +e.target.value; val.textContent = `${S[key]}${unit}`; draw(); } }));
  };
  const prio = segmented({ legend: 'Priority', options: [{ value: '1', label: 'Urgent' }, { value: '2', label: 'Normal' }, { value: '3', label: 'Deferrable' }], value: String(S.prio), onChange: v => { S.prio = +v; draw(); } });
  draw();
  return h('div', { class: 'atc-bid-try' }, h('div', { class: 'atc-bid-ctl' }, prio.el,
    slider('job', 'Planned job', 0.5, 24, 0.5, ' h'), slider('waited', 'Item has waited', 0, 96, 1, ' h'), slider('load', 'Load', 0, 100, 5, ' % of capacity'),
    slider('approach', 'Drive to the pad', 0, 10, 0.25, ' h'), slider('battery', 'Battery', 0, 100, 5, ' %'), slider('heard', 'Robots heard directly', 0, 8, 1, '')),
    out, h('p', { class: 'small muted' }, 'Held fixed here: no dark period, empty battery or landing within two weeks; in radio reach of the base; one claim held; a bundle of one item. The slack follows from the priority’s target time (24 h urgent, 168 h normal, 720 h deferrable) less the time waited and the planned job, as the robot computes it.'));
}

export async function mount() {
  const box = $('atc-bid');
  try {
    const [doc, chk] = await Promise.all([`${FILE}.json`, `${FILE}.check.json`].map(async f => { const r = await fetch(`${BASE}lab/policies/${f}`); if (!r.ok) throw new Error(`${f}: HTTP ${r.status}`); return r.json(); }));
    const policy = new AtcBidPolicy(doc), c = checkBid(policy, chk), cem = doc.training?.cem;
    box.replaceChildren(
      h('p', { class: 'prose' }, `Each robot works out its offer from its costs. A learned correction then moves the offer by a number of hours’ worth of the item’s urgency price: it is ${policy.layers[0].w[0].length} weights, one per thing the robot knows locally, added up (a linear model; file ${FILE}.json). A positive weight lowers the offer, and so favours the item, as the feature grows; a negative one raises it. Each weight is in hours per unit of its feature, as the file scales it.`),
      weights(policy),
      h('p', { class: 'small muted' }, `How it was made, from the file: ${doc.training.algo.replace(/O_ORACLE/g, 'the full-information pooled marketplace')}${cem ? `; ${cem.generations} generations of ${cem.population} candidates, ${cem.parameters_searched} numbers searched` : ''}. What it does to urgent waits is reported in paper P1 (Section 5.6), not on this page.`),
      h('h4', {}, 'Try it'),
      tryIt(policy),
      h('p', { class: `small ${c.ok ? 'muted' : 'atc-neg'}` }, `Runs in your browser. Checked just now against Python’s runtime on the file’s ${c.n} check inputs: ${c.ok ? 'all match' : 'MISMATCH'}, largest difference ${c.maxErr ? c.maxErr.toExponential(1) : '0'} h (allowed ${c.tolerance.toExponential(0)}).`));
  } catch (e) {
    box.replaceChildren(h('p', {}, `The learned correction could not load (${e.message}).`));
  }
}
