// /atc/ section 5 (F-54): the safety program at work. Loaded when the section comes near (main.js); the 3D view is a
// further chunk (sandbox-scene.js) that starts only on the visitor's request. Every count is read from the staged
// files: atc/E44_summary.json (results/E44_bounds.json), atc/sandbox/ (B-83: one recorded encounter per type, each
// with and without the safety program) and atc/encounters/index.json (B-78's 20 stored encounters with the parity
// computed at build time by src/atc/encounter.js). Nothing here is typed in.
import { segmented, h, viewPad } from '../ui/index.js';
import { upgradeFlags } from '../ui/tooltip.js';
import { num, fmt } from '../components/num.js';
import { readFixture, parity, replayTrace, delayAt, PLANNERS } from './encounter.js';
import { B_MAX, D0_M } from './safety.js';

const BASE = import.meta.env.BASE_URL, $ = id => document.getElementById(id);
const SRC_E44 = 'results/E44_bounds.json';
export const OWNER = ['var(--tol-blue)', 'var(--tol-red)', 'var(--tol-green)', 'var(--tol-yellow)', 'var(--tol-cyan)', 'var(--tol-purple)'];
const TYPE_TEXT = {
  1: 'Following: the vehicle ahead brakes as hard as it can (flat, or 10, 15 or 20° downhill)',
  2: 'Head-on on a one-lane road, with or without a passing bay',
  3: 'Overtaking on a two-lane stretch that narrows to one lane',
  4: 'Crossing and merging at a junction, up to four ways at once',
  5: 'A ring of one-lane roads where each vehicle waits for the next',
  6: 'A landing zone closes: a vehicle inside, routes through it, delays and wave-offs',
  7: 'Crew on foot step out from behind a rock, or walk toward a stopped robot',
  8: 'The radio drops out mid-negotiation: 10–50 % of messages lost, or cut off',
  9: 'A vehicle misbehaves: wheel slip, drifting off its lane, or a dead stop on a one-lane road',
  10: 'Slow haulers and faster LTVs of different companies, with one adversarial planner',
  11: 'A crowded landing-pad apron: 2, 4 and 8 times the normal fleet',
  12: 'Planner fuzzing: random and adversarial proposals on a mixed road layout',
};
// the three types whose result is a property of the rules, as P2 reports it (labelled as findings, not bugs)
const FINDING = {
  9: `The keep-distance rule (R1) sizes the gap for a vehicle ahead that brakes at most at ${B_MAX} m/s². A vehicle that stops dead, a fault rather than a manoeuvre, is outside that model, so a follower already inside a one-lane road can lose its margin. A margin for a dead stop would close the case at a cost in road capacity; it has not been run.`,
  6: 'A crossing that lies on a landing zone’s boundary can be held by a vehicle stopped at the zone line, and a vehicle leaving the closing zone through that crossing is then blocked. R3 keeps a vehicle out of a one-lane road it cannot leave into a bay, but no rule yet keeps it out of a junction whose far side is a hold point.',
  5: 'On a ring of one-lane roads with bays of limited size, the rule “enter only with a free bay at the exit” can still lock up, each vehicle waiting for the next. This was noted before the main run; the logistics model avoids it only because its bays are unlimited.',
};
const RULE_TEXT = {
  1: 'R1 keep distance', 2: 'R2 speed limit', 3: 'stop line (no reservation yet, a closed zone, a full slot or a vehicle off its lane)',
  5: 'R5 keep moving out of a closing landing zone', 6: 'R6 crew on foot',
};
const VIOL_TEXT = {
  viol_contact: 'contact', viol_gap: `gap to the vehicle ahead below the ${D0_M} m margin`, viol_zone: 'inside a closed landing zone',
  viol_crew: 'too close to crew while moving', viol_r3: 'in a one-lane road or reserved spot without the grant, or meeting head-on in one', viol_slots: 'an over-full pad or junction',
};
const PLANNER_TEXT = { nominal: 'nominal', random: 'random (fuzzer)', adversarial: 'adversarial' };

let E44 = null, FIX = null, SB = null, scene = null, cur = null, k = 0, playing = false, speed = 5, last = 0, raf = 0, lastDom = 0, clock = 0;
const ui = { type: 1, file: null, mode: 'on' };
const docs = new Map(), runs = new Map();
const m = (value, unit, digits, source) => num({ value, unit, digits, flag: 'Modelled', source });

// ---------- E44 in one table ----------
function e44Table() {
  const T = E44.types, keys = Object.keys(T).sort((a, b) => a - b), src = q => `${SRC_E44}: types.${q}`;
  const sum = f => keys.reduce((a, q) => a + f(T[q]), 0);
  const clean = keys.filter(q => T[q].violations === 0).length;
  const viol = keys.filter(q => T[q].violations > 0);
  $('atc-e44-lead').innerHTML = `Of ${m(sum(t => t.n), '', 0, `${SRC_E44}: Σ n`)} simulated encounters, ${m(sum(t => t.n_driven), '', 0, `${SRC_E44}: Σ n_driven`)} were driven
    (the rest were slopes no vehicle could hold). ${clean} of the ${keys.length} types had no violation at all.
    ${viol.map(q => `Type ${q} had ${m(T[q].violations, '', 0, `${src(q)}.violations`)} encounters with a violation (${m(T[q].violations_by_kind.viol_contact, '', 0, `${src(q)}.violations_by_kind.viol_contact`)} with contact)`).join('; ')}.`;
  const rows = keys.map(q => {
    const t = T[q], f = FINDING[q];
    return h('tr', { class: f ? 'atc-finding-row' : '' },
      h('th', { scope: 'row' }, h('button', { type: 'button', class: 'atc-linkbtn', 'aria-label': `Play type ${q} below`, onclick: () => { choose(+q); $('atc-sb').scrollIntoView({ block: 'start' }); } }, `${q}`)),
      h('td', {}, TYPE_TEXT[q], f ? h('span', { class: 'atc-tag atc-find' }, 'finding') : null),
      h('td', { class: 'n', html: m(t.n_driven, '', 0, `${src(q)}.n_driven`) }),
      h('td', { class: 'n', html: m(t.violations, '', 0, `${src(q)}.violations`) }),
      h('td', { class: 'n', html: m(t.outcomes.deadlock, '', 0, `${src(q)}.outcomes.deadlock`) }),
      h('td', { class: 'n', html: m(t.min_margin_m, ' m', 1, `${src(q)}.min_margin_m`) }),
      h('td', { class: 'n', html: m(t.emergency_brake_rate * 100, ' %', 1, `${src(q)}.emergency_brake_rate`) }),
      h('td', { class: 'n', html: m(t.bonferroni_bound * 1e3, '‰', 2, `${src(q)}.bonferroni_bound`) }));
  });
  $('atc-e44').replaceChildren(h('table', { class: 'atc-table atc-e44-t' },
    h('caption', { class: 'visually-hidden' }, 'The twelve encounter types of E44 and what the safety program allowed'),
    h('thead', {}, h('tr', {}, ...['Type', 'What happens', 'Driven', 'With a violation', 'Deadlocks', 'Smallest clearance', 'Emergency brake', 'Violation risk, 95 % bound'].map(x => h('th', { scope: 'col' }, x)))),
    h('tbody', {}, rows)));
  $('atc-findings').replaceChildren(...Object.entries(FINDING).sort((a, b) => a[0] - b[0]).map(([q, txt]) => h('li', {}, h('strong', {}, `Type ${q}: `), txt)));
  upgradeFlags($('atc-e44')); upgradeFlags($('atc-e44-lead'));
}

// ---------- loading ----------
async function fetchDoc(path, key) {
  if (!docs.has(key)) {
    const r = await fetch(BASE + path); if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const doc = await readFixture(await r.arrayBuffer()); doc.file = key; docs.set(key, doc);
  }
  return docs.get(key);
}
// keep at most a few decoded files (a long encounter is several MB once parsed)
function trim(keep) { for (const q of [...docs.keys()]) if (docs.size > 3 && q !== keep) { docs.delete(q); for (const w of ['on', 'off']) runs.delete(`${q}:${w}`); } }
function runOf(doc, mode) {
  const key = `${doc.file}:${mode}`;
  if (!runs.has(key)) {
    const r = replayTrace(doc, mode === 'on' ? 'shield_on' : 'shield_off'), prev = new Array(doc.spec.paths.length).fill(0), log = [];
    for (const f of r.frames) f.verdicts?.forEach((x, i) => {
      const fired = !f.done[i] && x.modified ? x.rule : 0;
      if (fired && fired !== prev[i]) log.push({ t: f.t, i, rule: fired, a: x.a, prop: x.prop });
      prev[i] = fired;
    });
    r.log = log; runs.set(key, r);
  }
  return runs.get(key);
}

// ---------- choosing ----------
let encSeg = null, safetySeg;
async function choose(type, file) {
  const list = SB.encounters.filter(e => e.type === type);
  const e = list.find(x => x.file === file) || list[0];
  ui.type = type; ui.file = e?.file;
  $('atc-sb-type').value = String(type);
  // a second encounter of the same type (type 6): a choice between them
  $('atc-sb-enc').replaceChildren();
  if (list.length > 1) {
    encSeg = segmented({ legend: 'Encounter', options: list.map((x, i) => ({ value: x.file, label: String.fromCharCode(65 + i) })), value: e.file, onChange: f => choose(type, f) });
    $('atc-sb-enc').append(encSeg.el);
  }
  if (!e) { cur = null; stop(); $('atc-sb-note').textContent = `No recorded encounter of type ${type}.`; drawReadout(); scene?.clear(); return; }
  $('atc-sb-note').textContent = 'Loading the recorded encounter…';
  const doc = await fetchDoc(`atc/sandbox/${e.file}`, e.file);
  if (ui.file !== e.file) return;   // a newer choice won
  trim(e.file);
  $('atc-sb-note').replaceChildren(h('strong', {}, `What it shows: ${e.shows}. `),
    `Recorded by the simulator from the same start twice, once with the safety program and once with every proposal applied as made; switch between them with “Safety program”. `,
    h('span', { class: 'muted' }, `From E44 batch ${doc.e44.batch}, encounter ${doc.e44.idx}${doc.reproduces_e44_row ? ' (the recording reproduces its E44 result)' : ''}; ${e.file}.`));
  cur = { e, doc, run: runOf(doc, ui.mode) };
  k = 0; stop(); $('atc-sb-t').max = String(cur.run.frames.length - 1);   // k first: stop() redraws the readout
  scene?.load(cur.doc, cur.run);
  show(0);
}
function setMode(mode) {
  ui.mode = mode;
  if (!cur) return;
  const t = cur.run.frames[k].t;
  cur.run = runOf(cur.doc, mode);
  $('atc-sb-t').max = String(cur.run.frames.length - 1);
  scene?.load(cur.doc, cur.run);
  show(frameAt(t));   // the same moment in the other run
}
const frameAt = t => { const F = cur.run.frames; let j = 0; while (j < F.length - 1 && F[j + 1].t <= t) j++; return j; };

// ---------- playback ----------
function show(i, dom = true) {
  if (!cur) return;
  k = Math.max(0, Math.min(i, cur.run.frames.length - 1));
  scene?.show(k);
  if (dom) { $('atc-sb-t').value = String(k); drawReadout(); }
}
function tick(now) {
  raf = 0;
  if (!playing || !cur) return;
  const dt = last ? Math.min(0.25, (now - last) / 1000) : 0; last = now;
  // the clock runs on its own: a display frame is shorter than a stored step, so stepping from the shown frame stalls
  clock = Math.max(clock, cur.run.frames[k].t) + dt * speed;
  const n = cur.run.frames.length - 1;
  let j = k; while (j < n && cur.run.frames[j + 1].t <= clock) j++;
  if (j >= n) { show(n); stop(); return; }
  const dom = now - lastDom > 100; if (dom) lastDom = now;   // the readout at 10 Hz, the scene every frame
  show(j, dom);
  raf = requestAnimationFrame(tick);
}
function play() {
  if (!cur) return;
  if (k >= cur.run.frames.length - 1) show(0);
  playing = true; last = 0; clock = cur.run.frames[k].t; $('atc-sb-play').textContent = 'Pause'; $('atc-sb-play').setAttribute('aria-pressed', 'true');
  if (!raf) raf = requestAnimationFrame(tick);
}
function stop() {
  playing = false; if (raf) cancelAnimationFrame(raf); raf = 0;
  const b = $('atc-sb-play'); if (b) { b.textContent = 'Play'; b.setAttribute('aria-pressed', 'false'); }
  if (cur) drawReadout();
}

// ---------- the readout ----------
const kmh = v => fmt(v * 3.6, 1), acc = a => (a > 0 ? '+' : '') + fmt(a, 2);
// the simulator's record of the whole run (Outcome), in words; deadlock as E44 counts it (not where a random planner runs)
function record(doc, run) {
  const o = run.outcome, src = `atc/sandbox/${doc.file}: ${run.which}.outcome`;
  const kinds = Object.entries(o.violations_by_kind).filter(([, n]) => n > 0).map(([q]) => VIOL_TEXT[q] || q);
  const fuzzer = doc.spec.planner.includes(1);
  const end = o.deadlock ? (fuzzer ? 'stalled (E44 counts no deadlock where a random planner runs)' : `deadlock: the vehicles stalled, each waiting for another${FINDING[doc.type] ? ' (a finding, above)' : ''}`)
    : o.blocked_by_fault ? 'blocked by the vehicle that stopped dead' : o.finished ? 'every vehicle reached its goal' : 'the time limit';
  return h('div', { class: 'atc-sb-rec' }, h('p', { class: 'ui-label' }, run.which === 'shield_on' ? 'The simulator’s record of this run, with the safety program' : 'The simulator’s record of this run, without the safety program'),
    h('ul', {},
      h('li', { html: `Closest approach between vehicles: ${o.min_sep_m === null ? 'never near each other' : m(Math.max(o.min_sep_m, 0), ' m', 1, `${src}.min_sep_m`) + (o.min_sep_m < 0 ? ' (they touched)' : '')}${o.min_crew_m === null ? '' : `; to crew: ${m(o.min_crew_m, ' m', 1, `${src}.min_crew_m`)}`}` }),
      h('li', { class: kinds.length ? 'atc-neg' : '' }, kinds.length ? `Rules broken: ${kinds.join('; ')}${doc.type === 9 && run.which === 'shield_on' ? ' (the type-9 finding, above)' : ''}.` : 'No rule broken.'),
      h('li', { html: `Ended at ${m(o.t_end, ' s', 1, `${src}.t_end`)}: ${end}${o.delay_s === null || run.which !== 'shield_on' ? '' : `; mean time lost ${m(o.delay_s, ' s', 1, `${src}.delay_s`)}`}.` })));
}
function drawReadout() {
  const box = $('atc-sb-read');
  if (!cur) { box.replaceChildren(); $('atc-sb-time').textContent = ''; return; }
  const r = cur.run, f = r.frames[k], sp = cur.doc.spec, on = r.mode === 'on', T = r.frames[r.frames.length - 1].t;
  $('atc-sb-time').textContent = `${fmt(f.t, 1)} s of ${fmt(T, 1)} s`;
  const contact = r.contactAt !== null && r.contactAt <= f.t;
  const sum = h('p', { class: 'atc-sb-sum' },
    h('span', {}, h('span', { class: 'ui-label' }, 'Now '), Number.isFinite(f.sep) ? `the nearest two vehicles are ${fmt(Math.max(f.sep, 0), 1)} m apart` : 'no two vehicles on the road together'),
    Number.isFinite(f.crewGap) ? h('span', {}, `; crew ${fmt(Math.max(f.crewGap, 0), 1)} m from the nearest vehicle`) : null,
    h('span', {}, h('span', { class: 'ui-label' }, on ? ' · moves corrected so far ' : ' · moves it would have corrected '), fmt(f.n, 0)),
    contact ? h('strong', { class: 'atc-neg' }, ` · vehicles touched at ${fmt(r.contactAt, 1)} s`) : null);
  const rows = sp.paths.map((_, i) => {
    const x = f.verdicts?.[i], gone = f.done[i];
    const fired = x && x.modified ? RULE_TEXT[x.rule] || '—' : '—';
    return h('tr', { class: gone ? 'muted' : '' },
      h('th', { scope: 'row' }, h('span', { class: 'atc-sw', style: `background:${OWNER[i % OWNER.length]}` }), `Vehicle ${i + 1}`),
      h('td', {}, PLANNER_TEXT[PLANNERS[sp.planner[i]]] || '—'),
      h('td', { class: 'n' }, kmh(sp.v_class[i])),
      h('td', { class: 'n' }, gone ? 'finished' : f.fault[i] ? 'stopped dead' : kmh(f.v[i])),
      h('td', { class: 'n' }, x && !gone ? acc(x.prop) : '—'),
      h('td', { class: 'n' }, x && !gone ? acc(on ? x.a : x.prop) : '—'),
      h('td', {}, gone ? '' : fired),
      on ? h('td', { class: 'n' }, fmt(delayAt(cur.doc, f, i, r.tDone[i]), 1)) : null);
  });
  const head = ['Vehicle', 'Planner', 'Speed limit, km/h', 'Speed, km/h', 'Planner asks, m/s²', on ? 'Safety program gives, m/s²' : 'Applied (no safety program), m/s²', on ? 'Rule that fired' : 'Rule it would have enforced', on ? 'Time lost, s' : null].filter(Boolean);
  const log = r.log.filter(e => e.t <= f.t).slice(-5).reverse();
  box.replaceChildren(sum,
    h('div', { class: 'atc-table-wrap' }, h('table', { class: 'atc-table atc-sb-t' }, h('caption', { class: 'visually-hidden' }, 'Each vehicle at this moment'),
      h('thead', {}, h('tr', {}, ...head.map(x => h('th', { scope: 'col' }, x)))), h('tbody', {}, rows))),
    h('div', { class: 'atc-sb-cols' },
      h('div', { class: 'atc-sb-log' }, h('p', { class: 'ui-label' }, on ? 'What the safety program did, latest first' : 'Where the safety program would have stepped in, latest first'),
        log.length ? h('ul', {}, log.map(e => h('li', {}, `${fmt(e.t, 1)} s · vehicle ${e.i + 1} · ${RULE_TEXT[e.rule] || 'rule'}: asked ${acc(e.prop)}${on ? `, given ${acc(e.a)}` : ''} m/s²`)))
          : h('p', { class: 'small muted' }, 'Nothing yet: every proposal so far kept every rule.')),
      record(cur.doc, r)),
    h('p', { class: 'small muted' }, `${on ? 'Time lost: the time behind a vehicle that drove its speed limit from the start. ' : ''}Long runs are stored thinned (every ${cur.e.stride}th step here; the first corrections are always kept), so “now” is the nearest stored moment; the record is the simulator’s, over every step.`));
  upgradeFlags(box);
}

// ---------- parity ----------
function parityBox() {
  const P = FIX.parity, t = FIX.tolerance;
  $('atc-parity').replaceChildren(h('h3', {}, 'Does the browser run the same safety program?'),
    h('p', { class: 'prose' }, `The safety program on this page is a port of the Python one (lunarsim/atc/safety.py) to JavaScript. It is checked against Python on all ${P.fixtures} stored test encounters (B-78), every step and every vehicle: ${fmt(P.checks, 0)} checks, each giving the same acceleration (largest difference ${P.maxDa ? P.maxDa.toExponential(0) : '0'} m/s², allowed ${t.a.toExponential(0)}) and, one step on, the same position and speed (largest differences ${P.maxDs.toExponential(1)} m and ${P.maxDv.toExponential(1)} m/s, allowed ${t.s.toExponential(0)}). ${P.fails ? `It FAILS in ${P.fails} encounters.` : 'It passes in all of them.'} Checked when this site was built (${P.built.slice(0, 10)}) by the same file your browser runs.`),
    h('p', {}, h('button', { type: 'button', class: 'ui-btn', id: 'atc-parity-all', onclick: checkAll }, `Check all ${P.fixtures} here, in your browser`),
      h('span', { class: 'small muted' }, ` downloads ${fmt(FIX.fixtures.reduce((a, f) => a + f.kb, 0) / 1024, 1)} MB`)),
    h('div', { id: 'atc-parity-out', 'aria-live': 'polite' }));
}
async function checkAll() {
  const out = $('atc-parity-out'), btn = $('atc-parity-all'); btn.disabled = true;
  const rows = [];
  for (const f of FIX.fixtures) {
    out.textContent = `Checking ${f.file}…`;
    try {
      const r = await fetch(`${BASE}atc/encounters/${f.file}`); if (!r.ok) throw new Error(`HTTP ${r.status}`);
      rows.push([f, parity(await readFixture(await r.arrayBuffer()), FIX.tolerance)]);   // decoded, checked, dropped: one at a time
    } catch (e) { rows.push([f, { pass: false, err: e.message }]); }
  }
  const bad = rows.filter(([, p]) => !p.pass).length;
  out.replaceChildren(h('p', {}, h('strong', {}, bad ? `${bad} of ${rows.length} encounters FAIL in your browser.` : `All ${rows.length} pass in your browser.`)),
    h('div', { class: 'atc-table-wrap' }, h('table', { class: 'atc-table' }, h('caption', { class: 'visually-hidden' }, 'Parity per stored encounter'),
      h('thead', {}, h('tr', {}, ...['Encounter', 'Type', 'Planner', 'Checks', 'Largest Δ acceleration', 'Result'].map(x => h('th', { scope: 'col' }, x)))),
      h('tbody', {}, rows.map(([f, p]) => h('tr', {}, h('td', {}, f.file.replace('.json.gz', '')), h('td', { class: 'n' }, String(f.type)), h('td', {}, f.planner),
        h('td', { class: 'n' }, p.checks ? fmt(p.checks, 0) : '—'), h('td', { class: 'n' }, p.maxDa !== undefined ? (p.maxDa ? p.maxDa.toExponential(0) : '0') : '—'), h('td', {}, p.pass ? 'pass' : `FAIL${p.err ? ` (${p.err})` : ''}`)))))));
  btn.disabled = false;
}

// ---------- controls ----------
function controls() {
  const types = Object.keys(E44.types).map(Number).sort((a, b) => a - b);
  const sel = h('select', { id: 'atc-sb-type', onchange: e => choose(+e.target.value) },
    types.map(q => h('option', { value: String(q) }, `${q} · ${TYPE_TEXT[q]}${SB.encounters.some(e => e.type === q) ? '' : ' (no recording)'}`)));
  safetySeg = segmented({ legend: 'Safety program', options: [{ value: 'on', label: 'On' }, { value: 'off', label: 'Off' }], value: ui.mode, onChange: setMode });
  const speedSeg = segmented({ legend: 'Speed', options: [{ value: '1', label: '1×' }, { value: '5', label: '5×' }, { value: '20', label: '20×' }], value: String(speed), onChange: v => { speed = +v; } });
  $('atc-sb-controls').replaceChildren(h('label', { class: 'atc-sb-pick' }, h('span', { class: 'ui-label' }, 'Encounter type'), sel), h('div', { id: 'atc-sb-enc' }), safetySeg.el);
  $('atc-sb-bar').replaceChildren(
    h('button', { type: 'button', class: 'ui-btn primary', id: 'atc-sb-play', 'aria-pressed': 'false', onclick: () => (playing ? stop() : play()) }, 'Play'),
    h('label', { class: 'atc-sb-scrub' }, h('span', { class: 'visually-hidden' }, 'Time in the encounter'),
      h('input', { type: 'range', id: 'atc-sb-t', min: '0', max: '600', step: '1', value: '0', oninput: e => { stop(); show(+e.target.value); } })),
    h('span', { id: 'atc-sb-time', class: 'small', 'aria-live': 'off' }), speedSeg.el);
}

// ---------- the 3D view, on request ----------
async function start3D() {
  const btn = $('atc-sb-start'); btn.disabled = true; btn.textContent = 'Starting the 3D view…';
  try {
    const { createSandboxScene } = await import('./sandbox-scene.js');
    scene = await createSandboxScene({ canvas: $('atc-sb-canvas'), labelsHost: $('atc-sb-labels') });
    $('atc-sb-door').hidden = true; $('atc-sb-canvas').hidden = false;
    $('atc-sb-canvas').parentElement.append(viewPad(scene.stage.director));   // F-40: orbit and zoom without a drag
    if (cur) { scene.load(cur.doc, cur.run); scene.show(k); }
  } catch (e) {
    btn.disabled = false; btn.textContent = 'Start the 3D view';
    $('atc-sb-door').append(h('p', { class: 'small atc-neg' }, `The 3D view could not start (${e.message}). The numbers beside it still work.`));
  }
}

export async function mount() {
  try {
    [E44, SB, FIX] = await Promise.all(['atc/E44_summary.json', 'atc/sandbox/index.json', 'atc/encounters/index.json'].map(async p => { const r = await fetch(BASE + p); if (!r.ok) throw new Error(`${p}: HTTP ${r.status}`); return r.json(); }));
  } catch (e) {
    $('atc-e44').replaceChildren(h('p', {}, `The encounter results could not load (${e.message}).`)); return;
  }
  e44Table(); controls(); parityBox();
  $('atc-sb-start').disabled = false;
  $('atc-sb-start').addEventListener('click', start3D);
  await choose(ui.type);
}
