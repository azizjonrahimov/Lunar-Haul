// /design/stage/ (development page, F-31): the shared 3D stage on a procedural test object. Whole / Cutaway /
// Exploded, both lighting presets, tiers 1-3, GTAO vs N8AO, the tone-mapping A/B, a live frame-time readout and a
// 5-second measurement log. Tier 0 (no WebGL2, or detect-gpu tier 0) shows a text fallback instead.
import './stage.css';
import { Vector3 } from 'three';
import { segmented, narrative, h } from '../ui/index.js';
import { createStage, detectTier } from '../stage/index.js';
import { buildTank } from './tank.js';

const $ = id => document.getElementById(id);
const fmt = (v, d = 1) => Number.isFinite(v) ? v.toFixed(d) : '–';

const STORY = {
  whole: { eyebrow: 'Whole', title: 'A test object, not a vehicle', html: '<p>A tank, its feed line, a combustion chamber and a bell nozzle on three legs, drawn procedurally at metre scale. Hover or Tab to a callout to pick a part.</p>' },
  cutaway: { eyebrow: 'Cutaway', title: 'Cut open, with solid sections', html: '<p>Clipping planes remove the front; stencil caps fill each cut part in its own colour, so the tank wall reads as a ring and the liquid oxygen inside appears.</p>' },
  exploded: { eyebrow: 'Exploded', title: 'Taken apart along each part’s axis', html: '<p>The tank rises, the engine slides forward and the legs move out, so every joint shows. The callouts follow the parts.</p>' },
};

const tierInfo = await detectTier();
const story = narrative({ label: 'Stage mode' });
$('s-story').append(story.el);
story.set(STORY.whole);

if (tierInfo.tier === 0 && !tierInfo.forced) {
  const fb = $('s-fallback'); fb.hidden = false;
  fb.textContent = `No 3D here (${tierInfo.gpu}). The parts list below describes the test object.`;
} else start();

async function start() {
  const ui = { view: 'whole', cut: 'plane', preset: 'exhibit', tone: 'neutral', tier: String(Math.max(1, tierInfo.tier)), ao: 'gtao' };
  const status = msg => { $('s-status').textContent = msg; };
  const obj = buildTank();
  let stage, explode;

  async function boot() {
    stage = await createStage({
      canvas: $('s-canvas'), labelsHost: $('s-labels'), preset: ui.preset, tier: +ui.tier, ao: ui.ao, toneMapping: ui.tone,
      onStatus: s => status(s === 'lost' ? 'WebGL context lost: waiting for the browser to restore it.' : 'WebGL context restored.'),
      onPick: select, onHover: () => {},
    });
    if (import.meta.env.DEV) window.__stage = stage;   // console access while developing
    const box = stage.setSubject(obj.root, { cutTargets: obj.cutTargets });
    const c = box.getCenter(new Vector3());
    stage.director.shot('home', { position: [c.x + 9, c.y + 3.5, c.z + 12], target: [c.x, c.y - 0.3, c.z] })
      .shot('cutaway', { position: [c.x + 4.5, c.y + 2, c.z + 17], target: [c.x, c.y - 0.2, c.z] })
      .shot('exploded', { position: [c.x + 14, c.y + 6.5, c.z + 19], target: [c.x, c.y + 0.8, c.z] })
      .shot('onsite', { position: [c.x - 9, c.y + 9, c.z + 22], target: [c.x - 6, c.y - 3, c.z - 8] });
    stage.director.limits({ minDistance: 3, maxDistance: 60, maxPolar: 92 });
    stage.director.bindKeys($('s-canvas'));
    await stage.director.go('home', { instant: true });
    explode = stage.explode(obj.explode);
    for (const [id, p] of Object.entries(obj.parts)) stage.labels.add({ id, text: p.name, object: p.object, anchor: p.anchor, tone: p.tone, onSelect: select });
    stage.setAdaptive($('s-adaptive').checked);
    applyView(true);
  }

  function select(id) {
    stage.labels.setPressed(id);
    const p = obj.parts[id]; if (!p) return;
    story.set({ eyebrow: 'Part', title: p.name, html: `<p>${p.note}.</p>` });
  }

  function applyView(instant = false) {
    const v = ui.view;
    story.set(STORY[v]);
    stage.setCut(v === 'cutaway' ? ui.cut : 'off', { facing: facingFromCamera(), origin: obj.axis });
    explode.to(v === 'exploded' ? 1 : 0);
    stage.director.go(ui.preset === 'onsite' && v === 'whole' ? 'onsite' : v === 'whole' ? 'home' : v, { instant });
  }
  // the cut opens towards the cutaway shot's camera, whatever the current orbit
  const facingFromCamera = () => { const s = stage.director.shots.get('cutaway'); return new Vector3(s.position[0] - s.target[0], 0, s.position[2] - s.target[2]).normalize(); };

  // ---------- controls ----------
  const seg = (legend, options, key, fn, row = 's-row1') => $(row).append(segmented({ legend, options, value: ui[key], onChange: v => { ui[key] = v; fn(v); } }).el);
  seg('View', [{ value: 'whole', label: 'Whole' }, { value: 'cutaway', label: 'Cutaway' }, { value: 'exploded', label: 'Exploded' }], 'view', () => applyView());
  seg('Cut', [{ value: 'plane', label: 'Half' }, { value: 'wedge', label: 'Wedge' }], 'cut', () => { if (ui.view === 'cutaway') applyView(); });
  seg('Light', [{ value: 'exhibit', label: 'Exhibit' }, { value: 'onsite', label: 'On site (1.5° sun)' }], 'preset', v => { stage.setPreset(v); applyView(); });
  seg('Tone mapping', [{ value: 'neutral', label: 'Neutral' }, { value: 'aces', label: 'ACES' }, { value: 'agx', label: 'AgX' }], 'tone', v => stage.setToneMapping(v), 's-row2');
  seg('Tier', [{ value: '1', label: '1' }, { value: '2', label: '2' }, { value: '3', label: '3' }], 'tier', v => stage.setTier(+v), 's-row2');
  seg('Ambient occlusion', [{ value: 'gtao', label: 'GTAO' }, { value: 'n8ao', label: 'N8AO' }], 'ao', async v => { status('Loading…'); await stage.setAO(v); status(''); }, 's-row2');
  $('s-row2').append(h('p', { class: 's-detected small' }, `Detected: tier ${tierInfo.tier} (${tierInfo.gpu}).`));

  const pauseBtn = $('s-pause'), turnBtn = $('s-turn');
  pauseBtn.addEventListener('click', () => { const v = pauseBtn.getAttribute('aria-pressed') !== 'true'; pauseBtn.setAttribute('aria-pressed', String(v)); stage.pause(v); });
  turnBtn.addEventListener('click', () => { const v = turnBtn.getAttribute('aria-pressed') !== 'true'; turnBtn.setAttribute('aria-pressed', String(v)); stage.director.autoRotate(v ? 6 : 0); });
  $('s-adaptive').addEventListener('change', e => stage.setAdaptive(e.target.checked));
  for (const b of document.querySelectorAll('[data-cam]')) b.addEventListener('click', () => {
    const d = stage.director, k = b.dataset.cam;
    ({ left: () => d.nudge(-20), right: () => d.nudge(20), up: () => d.nudge(0, -10), down: () => d.nudge(0, 10), in: () => d.zoom(1.25), out: () => d.zoom(0.8), home: () => applyView() })[k]();
  });
  $('s-lose').addEventListener('click', () => {
    const ext = stage.loseContext(); if (!ext) return status('This browser cannot simulate a context loss.');
    setTimeout(() => ext.restoreContext(), 1500);
  });
  $('s-measure').addEventListener('click', async () => {
    const btn = $('s-measure'); btn.disabled = true; status('Measuring 150 frames…');
    const adaptive = $('s-adaptive').checked; stage.setAdaptive(false);
    await stage.benchmark(30, 5);   // let the GPU clock up first
    const s = await stage.benchmark(150, 10);
    stage.setAdaptive(adaptive);
    const row = [ui.tier, ui.tier === '1' ? 'off' : ui.ao.toUpperCase(), ui.preset, ui.tone, ui.view, s.gpuN, fmt(s.gpuP50, 2), fmt(s.gpuP95, 2), fmt(s.cpuP50, 2), fmt(s.cpuP95, 2),
      `${s.drawingBuffer[0]}×${s.drawingBuffer[1]}`, s.calls];
    const log = $('s-log'); if (log.querySelector('.muted')) log.replaceChildren();
    log.append(h('tr', {}, row.map((v, i) => h('td', { class: i >= 5 ? 'n' : '' }, String(v)))));
    status(s.gpuN ? `Measured: GPU p50 ${fmt(s.gpuP50, 2)} ms, p95 ${fmt(s.gpuP95, 2)} ms per frame.` : 'This browser exposes no GPU timer; CPU times only.');
    btn.disabled = false;
  });

  // live readout, twice a second
  const perf = $('s-perf');
  setInterval(() => {
    if (!stage) return;
    const s = stage.stats.summary(), i = stage.info();
    const rows = [['Frame p50 / p95', s.n ? `${fmt(s.p50)} / ${fmt(s.p95)} ms` : 'idle (draws on demand)'],
      ['GPU p50 / p95', !i.gpuTimer ? 'no timer extension' : s.gpuN ? `${fmt(s.gpuP50, 2)} / ${fmt(s.gpuP95, 2)} ms` : '–'],
      ['Pixels', `${i.drawingBuffer[0]}×${i.drawingBuffer[1]} (ratio ${fmt(i.pixelRatio, 2)})`],
      ['Draw calls', String(i.calls)], ['Tier', `${stage.tier}${stage.tier > 1 ? ' · ' + stage.post.aoKind.toUpperCase() : ''}`],
      ['Depth buffer', i.reversedDepth ? 'reversed' : 'standard']];
    perf.replaceChildren(...rows.flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, v)]));
  }, 500);

  $('s-parts').append(...Object.values(obj.parts).map(p => h('li', {}, h('strong', {}, p.name), ` — ${p.note}.`)));
  try { await boot(); } catch (e) {
    const fb = $('s-fallback'); fb.hidden = false; fb.textContent = `The 3D view could not start (${e.message}). The parts list below describes the test object.`;
  }
}
