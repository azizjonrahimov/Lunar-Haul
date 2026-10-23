// /lab/lander, 3D section (F-34): "The last 500 metres". Recorded descents (trajectories-v1, B-33) replayed at true
// scale over pad A on the shared stage. This module is the light page side: the loading door, the controls (lander,
// pilot, episode, view, overlays, speed), the SCORE counter driven by the recorded reward terms, phase chips, a
// timeline with event ticks, the story card and a text mirror of every value. The 3D scene (three.js, terrain,
// effects, models) loads only when the visitor presses Enter (lab3d-scene.js). Tier 0 keeps the browser lab below.
import { door, segmented, sceneChips, narrative, counter, timeline, h, reducedMotion, viewPad } from '../ui/index.js';
import { detectTier } from '../stage/tier.js';
import { loadTrajectories, pilotsFor, episodeView, PICKS } from './trajectories.js';
import { TOUCHDOWN } from './classes.js';

const $ = id => document.getElementById(id);
const BASE = import.meta.env.BASE_URL, POL = BASE + 'lab/policies/';
const fmt = (v, d = 1) => (Number.isFinite(v) ? v.toFixed(d) : '–');
const CLASSES = [{ value: 'CLPS', label: 'Small' }, { value: 'MK1', label: 'Medium' }, { value: 'LARGE', label: 'Large' }];
const SHORT = { network: 'Network', classical: 'Classical', memoryless: 'Memoryless', ppo: 'PPO', hover: 'Hover hack' };
const PICK_SHORT = { p10: 'Close', p50: 'Typical', p90: 'Wide', first_failure: 'First failure' };
const FAIL = {
  velocity: 'too fast at contact', tilt: 'tilted or rotating too much at contact', sensor: 'misled by the altimeter (a dropout near the ground)',
  offpad: 'outside the 50 m delivery radius', timeout: 'still in the air when the 150 s limit ran out', lost: 'flew out of range',
};

const params = new URLSearchParams(location.search);
const ui = { cls: CLASSES.some(c => c.value === params.get('lander')) ? params.get('lander') : 'CLPS', kind: params.get('pilot') || 'network', pick: 'p50',
  view: 'side', speed: 2, show: { guidance: true, thrust: false, sensors: false } };
const story = narrative({ label: 'Descent story' }), score = counter({ label: 'Score', digits: 1 });
$('l3-story').append(story.el); $('l3-score').append(score.el);
story.set({ eyebrow: 'The last 500 metres', title: 'A recorded landing, at true scale', html: '<p>Press Enter to load the terrain, the recorded descents and the lander models (about 6 MB).</p>' });
const status = m => { $('l3-status').textContent = m; };

const tierInfo = await detectTier();
const tier = tierInfo.tier;
let sc = null, doc = null, view = null, pilot = null, tl = null;
const outcomes = new Map(), time = { t: 0, playing: false };

if (tier === 0 && !tierInfo.forced) {
  const fb = $('l3-fallback'); fb.hidden = false;
  fb.textContent = `No 3D here (${tierInfo.gpu}). The browser lab below flies the same pilots; its side view and telemetry table show each flight.`;
  $('l3-controls').hidden = true;
} else {
  const gate = door({ title: 'The last 500 metres', subtitle: 'Recorded descents at true scale over pad A, with the engine glow, the dust and the score.',
    skip: { href: '#l3-mirror-h', label: 'Skip to the flight data' }, enterLabel: 'Enter the 3D view', beforeOpen: () => start(gate) });
  $('l3-view').append(gate.el);
  gate.ready();
}

async function start(gate) {
  const fetchFn = label => url => gate.fetch(url, { label });
  const [mod, d] = await Promise.all([import('./lab3d-scene.js'), loadTrajectories(POL + 'trajectories-v1.json', { fetchFn: fetchFn('descent recordings') })]);
  doc = d;
  sc = await mod.createLanderScene({ canvas: $('l3-canvas'), labelsHost: $('l3-labels'), tier: Math.max(1, tier), fetchFn: fetchFn('catalogue'),
    onStatus: s => status(s === 'lost' ? 'The graphics context was lost; it will come back by itself.' : '') });
  if (import.meta.env.DEV) window.__l3 = { sc, ui, time };
  sc.colours = mod.OUTCOME_COLOURS;
  sc.stage.director.bindKeys($('l3-canvas')); $('l3-view').append(viewPad(sc.stage.director));   // F-40: orbit and zoom without a drag
  sc.stage.director.limits({ minDistance: 3, maxDistance: 2500, maxPolar: 95 });
  controls();
  await choose();
}

// ---------- controls ----------
let pilotSeg = null, pickSeg = null, phaseChips = null;
function controls() {
  const r1 = $('l3-row1'), r2 = $('l3-row2');
  r1.append(segmented({ legend: 'Lander', options: CLASSES, value: ui.cls, onChange: v => { ui.cls = v; drawPilots(); choose(); } }).el);
  drawPilots();
  r2.append(segmented({ legend: 'View', options: [{ value: 'chase', label: 'Chase' }, { value: 'side', label: 'Side' }, { value: 'pad', label: 'Pad camera' }, { value: 'sun', label: 'Into the sun' }],
    value: ui.view, onChange: v => { ui.view = v; sc.setView(v); update(true); } }).el);
  const showSet = h('fieldset', { class: 'l3-show' }, h('legend', { class: 'ui-label' }, 'Show'));
  for (const [k, label] of [['guidance', 'Guidance'], ['thrust', 'Thrust'], ['sensors', 'Sensors']]) {
    const input = h('input', { type: 'checkbox', checked: ui.show[k] });
    input.addEventListener('change', () => { ui.show[k] = input.checked; sc.setShow(ui.show); update(true); });
    showSet.append(h('label', { class: 's-check' }, input, ' ' + label));
  }
  r2.append(showSet, segmented({ legend: 'Speed', options: [{ value: '1', label: '1×' }, { value: '2', label: '2×' }, { value: '4', label: '4×' }], value: String(ui.speed), onChange: v => { ui.speed = +v; } }).el);
  const play = h('button', { class: 'ui-btn primary', type: 'button', id: 'l3-play', 'aria-pressed': 'false' }, 'Play');
  play.addEventListener('click', () => setPlaying(!time.playing));
  r2.append(play);
  phaseChips = sceneChips({ label: 'Phase', scenes: [{ value: 'approach', label: 'Approach' }, { value: 'hover', label: 'Hover' }, { value: 'touchdown', label: 'Touchdown' }],
    value: 'approach', onChange: p => { seek(Math.max(0, view.phases[p] - (p === 'approach' ? 0 : 2))); } });
  $('l3-phases').append(phaseChips.el);
}
function drawPilots() {
  const list = pilotsFor(doc, ui.cls);
  if (!list.some(p => p.kind === ui.kind)) ui.kind = list[0].kind;
  pilotSeg?.el.remove(); pickSeg?.el.remove();
  pilotSeg = segmented({ legend: 'Pilot', options: list.map(p => ({ value: p.kind, label: SHORT[p.kind] })), value: ui.kind,
    onChange: v => { ui.kind = v; ui.pick = v === 'hover' ? 'first_failure' : 'p50'; pickSeg.set(ui.pick); choose(); } });
  if (ui.kind === 'hover') ui.pick = 'first_failure';
  pickSeg = segmented({ legend: 'Episode', options: Object.keys(PICKS).map(k => ({ value: k, label: PICK_SHORT[k] })), value: ui.pick, onChange: v => { ui.pick = v; choose(); } });
  $('l3-row1').append(pilotSeg.el, pickSeg.el);
}

function setPlaying(v) {
  time.playing = v;
  const b = $('l3-play'); b.textContent = v ? 'Pause' : time.t >= view.tEnd + 5 ? 'Replay' : 'Play'; b.setAttribute('aria-pressed', String(v));
  if (v) { if (time.t >= view.tEnd + 5) time.t = 0; sc.stage.animate(tick); }
}
function tick(dt) {
  if (!time.playing) return false;
  time.t = Math.min(view.tEnd + 6, time.t + dt * ui.speed);
  update();
  if (time.t >= view.tEnd + 6) { setPlaying(false); score.commit(`Final score ${fmt(view.scoreFinal, 1)}`); }
  return time.playing;
}
function seek(t) { setPlaying(false); time.t = t; update(true); }

// ---------- one episode ----------
async function getOutcomes(p) {
  if (!outcomes.has(p.monte_carlo.file)) outcomes.set(p.monte_carlo.file, fetch(POL + p.monte_carlo.file).then(r => (r.ok ? r.json() : null)).catch(() => null));
  return outcomes.get(p.monte_carlo.file);
}
async function choose() {
  pilot = pilotsFor(doc, ui.cls).find(p => p.kind === ui.kind);
  const ep = pilot.episodes.find(e => e.pick === ui.pick) || pilot.episodes[0];
  view = episodeView(ep);
  sc.setEpisode({ cls: ui.cls, view, seed: 1 });
  const mc = await getOutcomes(pilot), s = sc.setScatter(mc);
  legend(mc, s);
  sc.lightForSide();
  time.t = 0; lastPhase = '';
  sc.setShow(ui.show); update(true); sc.setView(ui.view, true); update(true);
  drawTimeline();
  setPlaying(!reducedMotion());
}
function legend(mc, s) {
  const names = { none: 'landed in the box', velocity: 'too fast', tilt: 'tilt or rotation', sensor: 'altimeter', offpad: 'off the pad' };
  const parts = Object.entries(s.counts).map(([k, n]) => `${n} ${names[k] || k} (${sc.colours[k] ? colourName(k) : ''})`);
  $('l3-mc-legend').textContent = mc ? `On the ground: where ${mc.n} Monte Carlo landings of this pilot touched down: ${parts.join(', ')}; ${s.timeouts} never reached the ground. Discs are 0.7 m across, drawn at true scale.` : '';
}
const colourName = k => ({ none: 'cyan', velocity: 'red', tilt: 'yellow', sensor: 'purple', offpad: 'grey' })[k];

function drawTimeline() {
  const ev = [{ t: view.phases.hover, kind: 'info', label: 'Below 20 m: hover and descend' }, { t: Math.min(view.tEnd, view.phases.touchdown), kind: 'info', label: 'Below 3 m' }];
  const onset = sc.dustOnset();
  if (onset !== null) ev.push({ t: onset, kind: 'info', label: 'Dust starts to fly' });
  let n = 0; for (let k = 1; k < view.nSteps && n < 8; k++) if (view.dropouts[k] && !view.dropouts[k - 1]) { ev.push({ t: k * 0.2, kind: 'strand', label: 'Altimeter dropout' }); n++; }
  const end = view.outcome.failure_kind === 'timeout' ? 'Time limit (150 s)' : view.outcome.ok ? 'Touchdown in the box' : 'Touchdown outside the box';
  ev.push({ t: view.tEnd, kind: 'landing', label: end });
  ev.sort((a, b) => a.t - b.t);
  const el = timeline({ label: 'Time', min: 0, max: Math.ceil(view.tEnd + 6), step: 0.1, value: time.t, format: v => `T+${fmt(v, 1)} s`, events: ev, onInput: v => seek(v) });
  if (tl) tl.el.replaceWith(el.el); else $('l3-time').append(el.el);
  tl = el;
}

// ---------- the moment ----------
let lastMirror = 0, lastPhase = '';
function update(force = false) {
  if (!sc || !view) return;
  const t = time.t, r = sc.setTime(t);
  score.set(view.score(t), { animate: !force });
  const ph = t >= view.tEnd ? 'touchdown' : view.phaseAt(t);
  if (ph !== phaseChips.value) phaseChips.set(ph);
  clock(t);
  narrate(t, ph);
  const now = performance.now();
  if (force || now - lastMirror > 250) { lastMirror = now; mirror(t, r); if (tl && time.playing) tl.set(t); }
}
function clock(t) {
  const limit = 150, hover = ui.kind === 'hover', el = $('l3-clock');
  const s = `T+${fmt(Math.min(t, view.tEnd), 1)} s${hover ? ` of ${limit} s` : ''}`;
  if (el.textContent !== s) el.textContent = s;
  el.classList.toggle('warn', hover && t > limit - 30);
}

function narrate(t, ph) {
  const end = t >= view.tEnd, key = `${ph}|${end}|${ui.kind}`;
  if (key === lastPhase) return; lastPhase = key;
  const o = view.outcome, who = pilot.label.toLowerCase();
  let s;
  if (end && o.failure_kind === 'timeout') s = { eyebrow: 'Out of time', title: ui.kind === 'hover' ? 'Paid to hover, it hovers' : 'Still hovering at 150 s', html: ui.kind === 'hover' ? '<p>This network was trained under the first reward rules, which paid +0.3 for every 0.2 s in the air and at most 10 for landing. Hovering until the 150 s limit paid best, so that is what it learned: reward hacking. The score shown uses today’s rules, under which the hover no longer pays.</p>' : '<p>The law kept slowing down above the ground and the episode hit its 150 s limit. It counts as a failure.</p>' };
  else if (end) s = { eyebrow: 'Touchdown', title: o.ok ? `In the box, ${fmt(Math.hypot(...o.miss_m), 1)} m from the centre` : `Outside the box: ${FAIL[o.failure_kind] || o.failure_kind}`, html: `<p>${box(o)}</p>` };
  else if (ph === 'approach') s = { eyebrow: 'Approach', title: `${pilot.label} flies in`, html: `<p>From about 430 m up and 250 m out, the ${who} heads for a point 15 m above the pad. Turn on <em>Guidance</em> to see the velocity the guidance field asks for (cyan) against what the lander does (white).</p>` };
  else if (ph === 'hover') s = { eyebrow: 'Hover', title: 'Down at a metre per second', html: '<p>Below 20 m the field asks for a slow, steady descent. The altimeter matters now: its noise grows near the ground and it drops out 5 % of the time (turn on <em>Sensors</em>). Once the plume reaches the surface, dust flies in a thin sheet.</p>' };
  else s = { eyebrow: 'Touchdown', title: 'The last metres', html: '<p>The touchdown box: vertical speed at most 2 m/s, horizontal at most 1 m/s, tilt at most 6°, rotation at most 2°/s, within 50 m of the pad centre. The dust layer hides the ground now and vanishes when the engine stops.</p>' };
  story.set(s);
}
function box(o) {
  const vz = Math.abs(o.v_td[2]), vh = Math.hypot(o.v_td[0], o.v_td[1]), ok = (v, lim) => (v <= lim ? 'within' : 'over');
  return `Vertical ${fmt(vz, 2)} m/s (${ok(vz, TOUCHDOWN.vz_max_mps)} ${TOUCHDOWN.vz_max_mps}), horizontal ${fmt(vh, 2)} m/s (${ok(vh, TOUCHDOWN.vh_max_mps)} ${TOUCHDOWN.vh_max_mps}), tilt ${fmt(o.tilt_deg, 1)}° (${ok(o.tilt_deg, TOUCHDOWN.tilt_max_deg)} ${TOUCHDOWN.tilt_max_deg}), rotation ${fmt(o.rate_dps, 1)}°/s (${ok(o.rate_dps, TOUCHDOWN.rate_max_dps)} ${TOUCHDOWN.rate_max_dps}). Final score ${fmt(view.scoreFinal, 1)}.`;
}

function mirror(t, r) {
  const [x, y, z] = view.pos(t), [vx, vy, vz] = view.vel(t), end = t >= view.tEnd, o = view.outcome;
  const rows = [
    ['Pilot', `${pilot.label} (${PICKS[ui.pick].toLowerCase()}, seed ${view.seed})`],
    ['Time', `T+${fmt(Math.min(t, view.tEnd), 1)} s of ${fmt(view.tEnd, 1)} s`],
    ['Phase', end ? 'on the ground' : view.phaseAt(t)],
    ['Altitude', `${fmt(Math.max(0, z), 1)} m`],
    ['Vertical speed', `${fmt(end ? 0 : vz, 2)} m/s`],
    ['Horizontal speed', `${fmt(end ? 0 : Math.hypot(vx, vy), 2)} m/s`],
    ['Distance from the pad centre', `${fmt(Math.hypot(x, y), 1)} m`],
    ['Throttle', `${fmt(100 * view.throttle(t), 0)} %`],
    ['Propellant left', `${fmt(view.prop(t), 1)} kg`],
    ['Altimeter', end ? '–' : `${fmt(view.altMeas(t), 1)} m${view.dropout(t) ? ' (dropout: holding the last reading)' : ''}`],
    ['Score so far', fmt(view.score(t), 1)],
    ['Outcome', end ? (o.ok ? 'landed in the touchdown box' : FAIL[o.failure_kind] || o.failure_kind) : 'in flight'],
  ];
  $('l3-mirror').replaceChildren(...rows.flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, v)]));
}
