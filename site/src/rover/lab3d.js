// /lab/rover, 3D view (F-35): the drive of the lab below on the LOLA terrain at true scale. This module is the light
// page side: the loading door, view chips, the HUD (story card, ground speed, slip, light, Earth link, race), the Show
// toggles, the Earth-link start date and a text version of the view. The scene (three.js, terrain, models) loads only
// when the visitor presses Enter (lab3d-scene.js). The plan view and telemetry below show the same drive at every
// tier; at tier 0 they are the whole lab.
// Earth link (R-1, B-40): data/comms/.../earth_link-v1-samples.json.gz holds hourly direct-to-Earth windows for points
// about 100 m apart along every leg (2028-2031, criterion: any part of Earth's disc above the terrain at 2.5 m), computed on
// the leg's night route (BACKEND adds one set per lighting route later).
import { door, sceneChips, narrative, statChip, timeline, h, reducedMotion } from '../ui/index.js';
import { detectTier } from '../stage/tier.js';
import * as R from './physics.js';
import { DT_S } from './env.js';

const $ = id => document.getElementById(id);
const BASE = import.meta.env.BASE_URL;
const fmt = (v, d = 1) => (Number.isFinite(v) ? v.toFixed(d) : '–');
const VIEWS = [{ value: 'chase', label: 'Chase' }, { value: 'cockpit', label: 'Cockpit' }, { value: 'side', label: 'Side' }, { value: 'leg', label: 'Whole leg' }];
const T0 = Date.UTC(2028, 0, 1), HOURS = 35064;
const date = hr => new Date(T0 + hr * 3600e3).toLocaleString('en-GB', { timeZone: 'UTC', weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) + ' UTC';
const inH = hrs => (!Number.isFinite(hrs) ? 'beyond 2031' : hrs < 1 ? 'under an hour' : hrs < 48 ? `${Math.round(hrs)} h` : `${fmt(hrs / 24, 1)} days`);
const hms = s => { const h0 = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), ss = Math.floor(s % 60); return `${h0}:${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`; };
const WHY = {
  'left the corridor': 'It strayed more than 25 m from the planned route.',
  'slope above 20°': 'The ground under it is steeper than the 20° hard limit.',
  stalled: 'Its wheels made no progress for 30 s (dig-in or a stall).',
  'rough ground': 'Its 20 m cell is rougher than 0.5 m (the 5 m heights about their plane).',
};

/* where the command sent now takes effect: the queued teleop commands run through the model's own step (exact except
   for stops to confirm and interventions, which the prediction cannot know). Pure: never touches the env's route index. */
export function ghostState(env) {
  if (!env?.queue?.length) return null;
  let s = { ...env.state };
  for (const a of env.queue) {
    s = R.step(s, a[0], a[1], env.vCap(s.x, s.y, s.psi), DT_S);
    const zA = env.t.height(s.x, s.y), zB = env.t.height(s.x + Math.sin(s.psi), s.y + Math.cos(s.psi));
    s = R.advance(s, s.v * (1 - R.slip(Math.atan(zB - zA) * 180 / Math.PI, env.phi)), DT_S);
  }
  return s;
}

// Earth-link windows: delta code [s0, l0, g1, l1, ...] -> flat [start, end, start, end, ...] hour indices
function decodeWindows(code) { const out = new Int32Array(code.length); let t = 0; for (let i = 0; i < code.length; i++) { t += code[i]; out[i] = t; } return out; }
function linkedAt(w, hr) { let lo = 0, hi = w.length / 2 - 1; while (lo <= hi) { const m = (lo + hi) >> 1; if (hr < w[2 * m]) hi = m - 1; else if (hr >= w[2 * m + 1]) lo = m + 1; else return true; } return false; }
function nextUp(w, hr) { for (let i = 0; i < w.length; i += 2) if (w[i] > hr) return w[i] - hr; return Infinity; }

function textChip(label) {
  const v = h('span', { class: 'ui-chip-value r3-chip-text' }), el = h('div', { class: 'ui-chip' }, h('span', { class: 'ui-label' }, label), v);
  let shown = null;
  return { el, set(t, tone = '') { if (t !== shown) { shown = t; v.textContent = t; } el.dataset.tone = tone; el.hidden = t === null; } };
}

export function mount3d(api) {
  const { st } = api;
  const ui = { view: 'chase', show: { ghost: true, glare: true, earth: true } };
  let sc = null, earth = null, track = null, samples = null, h0 = 0, tl = null, entered = false, speedTouched = false;
  const story = narrative({ label: 'Drive story' });
  const speed = statChip({ label: 'Ground speed', value: 0, unit: 'km/h', flag: 'Modelled', digits: 1, source: 'this drive (JS port of lunar/Drive-v0)' });
  const slip = statChip({ label: 'Wheel slip', value: 0, unit: '%', flag: 'Modelled', digits: 0, source: 'slip curve for this drive’s soil (Modelled; the constants table below gives the source)' });
  const meter = h('div', { class: 'r3-meter', role: 'presentation' }, h('span', { class: 'r3-meter-fill' }), h('span', { class: 'r3-meter-mark', title: 'dig-in at 80 %' }));
  slip.el.append(meter);
  const light = textChip('Light'), link = textChip('Earth from here'), race = textChip('Race');
  $('r3-story').append(story.el); $('r3-chips').append(speed.el, slip.el, light.el, link.el, race.el);
  link.set(null); race.set(null);
  story.set({ eyebrow: 'Rover lab in 3D', title: 'Drive the leg on the real terrain', html: '<p>Press Enter to load the terrain, the rover and the Earth-link samples (about 3.5 MB). The drive is the same one the plan view below shows.</p>' });
  $('r-speed').addEventListener('change', () => { speedTouched = true; });

  (async () => {
    const tierInfo = await detectTier(), tier = tierInfo.tier;
    if (tier === 0 && !tierInfo.forced) {
      const fb = $('r3-fallback'); fb.hidden = false;
      fb.textContent = `No 3D here (${tierInfo.gpu}). The plan view and the telemetry below show the same drive.`;
      $('r3-controls').hidden = true; return;
    }
    const gate = door({ title: 'Drive a leg of the base', subtitle: 'The rover on the real terrain at true scale: chase and cockpit views, the command delay, the low sun and where Earth drops out of sight.',
      skip: { href: '#r-tele-title', label: 'Skip to the telemetry' }, enterLabel: 'Enter the 3D view', beforeOpen: () => start(gate, tier) });
    $('r3-view').append(gate.el);
    gate.ready();
  })();

  async function start(gate, tier) {
    const fetchFn = label => url => gate.fetch(url, { label });
    const [mod, ej, tk] = await Promise.all([import('./lab3d-scene.js'),
      gunzipJson(BASE + 'comms/earth_link-v1-samples.json.gz', fetchFn('Earth-link samples')).catch(() => null),
      import('../stage/sky.js').then(m => m.loadEarthTrack(BASE + 'comms/earth_track-v1.json.gz')).catch(() => null)]);   // sky.js brings three: load it with the scene
    earth = ej; track = tk;
    sc = await mod.createRoverScene({ canvas: $('r3-canvas'), labelsHost: $('r3-labels'), tier: Math.max(1, tier), fetchFn: fetchFn('catalogue'),
      onStatus: s => { if (s === 'lost') api.status('The graphics context was lost; it will come back by itself.'); } });
    if (import.meta.env.DEV) window.__r3 = { sc, ui, st };
    sc.stage.director.limits({ minDistance: 2, maxDistance: 9000, maxPolar: 95 });
    // orbit keys on the canvas, except the arrows while you drive (they steer)
    const proxy = new EventTarget(); sc.stage.director.bindKeys(proxy);
    $('r3-canvas').addEventListener('keydown', e => {
      if (api.human() && e.key.startsWith('Arrow')) return;
      const ev = new KeyboardEvent('keydown', { key: e.key, shiftKey: e.shiftKey, cancelable: true }); proxy.dispatchEvent(ev); if (ev.defaultPrevented) e.preventDefault();
    });
    controls();
    entered = true;
    if (!speedTouched && $('r-speed').value === '60') $('r-speed').value = '10';   // 10x reads at chase distance; the plan view keeps up
    leg();
    // open on a sunlit stretch: the first route point lit both in the model (its 20 m shadow grid) and in the view (the
    // horizon map, which also sees terrain beyond the tile); the drive runs on at once to it, if it is in the first 70 %
    if (api.lighting() !== R.NIGHT && !api.human()) {
      for (let i = 0; i < 60 && sc.sunlitAt(st.env.state.x, st.env.state.y) === null; i++) await new Promise(r => setTimeout(r, 100));   // the horizon map for this sun
      const path = st.env.pp.path, s = st.env.pp.s, total = s[s.length - 1];
      const lit = q => !st.env.inShadow(q[0], q[1]) && (sc.sunlitAt(q[0], q[1]) ?? 1) >= 0.5;
      let k = 0; while (k < path.length && !lit(path[k])) k++;
      const n = k > 0 && k < path.length && s[k] < 0.7 * total ? api.skip(() => progress(st.env) < s[k] + 5) : 0;
      if (n && !st.done) {
        sc.setView(ui.view, true); update(true);
        api.status(`The first ${fmt(progress(st.env) / 1000, 2)} km of this leg run in the shadow of the terrain (${hms(st.env.timeS)} of the drive); the view joins where the sun reaches the rover. Back to start drives it from the beginning.`);
      }
    }
    if (!reducedMotion() && !api.human()) api.drive();
  }
  async function gunzipJson(url, fetchFn) {
    const r = await fetchFn(url); if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
    let buf = new Uint8Array(await r.arrayBuffer());
    if (buf[0] === 0x1f && buf[1] === 0x8b) buf = new Uint8Array(await new Response(new Blob([buf]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer());
    return JSON.parse(new TextDecoder().decode(buf));
  }

  // ---------- controls under the view ----------
  let viewChips = null;
  function controls() {
    viewChips = sceneChips({ label: 'View', scenes: VIEWS, value: ui.view, onChange: v => { ui.view = v; sc.setView(v); lastKey = ''; update(true); } });
    $('r3-views').append(viewChips.el);
    const showSet = h('fieldset', { class: 'r3-show' }, h('legend', { class: 'ui-label' }, 'Show'));
    for (const [k, label] of [['ghost', 'Ghost rover (command delay)'], ['glare', 'Glare cone'], ['earth', 'Earth link along the leg']]) {
      const input = h('input', { type: 'checkbox', checked: ui.show[k] });
      input.addEventListener('change', () => { ui.show[k] = input.checked; sc.setShow(ui.show); $('r3-earth').hidden = !ui.show.earth || !samples; lastKey = ''; update(true); });
      showSet.append(h('label', { class: 's-check' }, input, ' ' + label));
    }
    $('r3-row').append(showSet);
  }
  function drawTimeline() {
    $('r3-earth').hidden = !ui.show.earth || !samples;
    if (!samples) return;
    const el = timeline({ label: 'The drive starts', min: 0, max: HOURS - 1, step: 1, value: h0, format: v => date(v), onInput: v => { h0 = Math.round(v); lastKey = ''; update(true); } });
    if (tl) tl.el.replaceWith(el.el); else $('r3-earth').append(el.el);
    tl = el;
  }

  // ---------- a new leg or a new drive (reset) ----------
  function leg() {
    if (!sc || !st.env) return;
    const pts = api.points(), a = $('r-from').value, b = $('r-to').value, race2 = !!st.env2;
    sc.setLeg({ path: st.env.pp.path, from: a, to: b, fromXY: pts[a], toXY: pts[b] });
    sc.setSun(api.lighting());
    sc.setRoverLabel(0, race2 ? 'Expert' : ({ expert: 'Expert', human: 'You', learned: 'Network' })[$('r-ctrl').value] || 'Rover');
    // Earth-link samples of this leg (absent for a leg the comms file does not list)
    const ids = earth?.legs[api.tableKey(a, b)];
    samples = ids ? ids.map(i => { const s = earth.samples[i]; return { x: s.xy_m[0], y: s.xy_m[1], w: decodeWindows(earth.series[s.w[0]]), linked: true }; }) : null;
    if (samples) {
      // first hour of 2028 when the start is linked but somewhere along the leg is not: where the story is
      const s0 = samples[0].w; h0 = 0;
      for (let hr = 0; hr < 8760; hr++) if (linkedAt(s0, hr) && samples.some(s => !linkedAt(s.w, hr))) { h0 = hr; break; }
      samples.forEach(s => { s.linked = linkedAt(s.w, h0); });
      let d = 0; samples.forEach((s, i) => { if (i) d += Math.hypot(s.x - samples[i - 1].x, s.y - samples[i - 1].y); s.km = d / 1000; });
      const path = st.env.pp.path;
      samples.off = samples.reduce((m, s) => m + Math.min(...path.map(q => Math.hypot(q[0] - s.x, q[1] - s.y))), 0) / samples.length;
    }
    sc.setEarth(samples); sc.setShow(ui.show);
    drawTimeline();
    lastPins = [0, 0]; lastHour = -1; lastKey = '';
    update(true);
    sc.setView(ui.view, true);
    update(true);
  }

  // ---------- every frame of the drive ----------
  let lastDom = 0, lastPins = [0, 0], lastHour = -1, lastKey = '', lastStoryAt = 0;
  function update(force = false) {
    if (!sc || !st.env) return;
    const e = st.env, e2 = st.env2, teleop = e.autonomy === 'teleop' && e.rtt > 0;
    sc.update({ states: [e.state, e2 ? e2.state : null], ghost: teleop && ui.show.ghost && !st.done ? ghostState(e) : null, trails: [st.trail, st.trail2 || []], sunlit: !e.inShadow(e.state.x, e.state.y) });
    if (st.events.length !== lastPins[0]) { sc.setPins(0, st.events); lastPins[0] = st.events.length; }
    if (e2 && st.events2.length !== lastPins[1]) { sc.setPins(1, st.events2); lastPins[1] = st.events2.length; }
    // the Earth-link posts follow the drive's clock: the start date plus the elapsed time
    const hr = samples ? Math.min(HOURS - 1, Math.floor(h0 + e.timeS / 3600)) : -1;
    if (samples && hr !== lastHour) {
      lastHour = hr; samples.forEach(s => { s.linked = linkedAt(s.w, hr); }); sc.setEarthState(samples.map(s => s.linked));
      if (track) sc.setEarthSky(track.at(hr));
    }
    const now = performance.now();
    if (force || now - lastDom > 150) { lastDom = now; hud(hr); narrate(hr, now, force); mirror(hr); }
  }
  function here(hr) {   // the Earth-link sample nearest the rover
    if (!samples) return null;
    const s0 = st.env.state; let best = null, bd = Infinity;
    for (const s of samples) { const d = Math.hypot(s.x - s0.x, s.y - s0.y); if (d < bd) { bd = d; best = s; } }
    return bd < 400 ? { ...best, wait: best.linked ? 0 : nextUp(best.w, hr) } : null;
  }
  function lightState() {
    const e = st.env, sun = api.lighting();
    if (sun === R.NIGHT) return { key: 'night', text: 'Night: headlights', tone: 'warm' };
    if (e.inShadow(e.state.x, e.state.y)) return { key: 'shadow', text: `In shadow (speed × ${R.SHADOW_SPEED_FACTOR})`, tone: 'warm' };
    const d = Math.abs((((e.state.psi * 180 / Math.PI - sun) % 360) + 540) % 360 - 180);
    if (d <= R.UP_SUN_HALF_ANGLE_DEG) return { key: 'glare', text: `Into the sun (speed × ${fmt(Math.cos(R.UP_SUN_TACK_DEG * Math.PI / 180), 2)})`, tone: 'warm', d };
    return { key: 'sun', text: `Sun ${Math.round(d)}° off the nose`, tone: '', d };
  }
  function progress(env) { return env.pp.s[env.pp.k]; }   // read-only: closest() would move the env's route index
  function hud(hr) {
    const r = !st.done && st.rec ? st.rec : { gv: 0, slip: 0 }, sl = Math.round(100 * r.slip);
    speed.set(+(r.gv * 3.6).toFixed(1)); slip.set(sl);
    meter.style.setProperty('--slip', `${Math.min(100, sl)}%`); meter.dataset.level = r.slip >= R.DIG_IN_SLIP ? 'dig' : r.slip >= 0.3 ? 'high' : '';
    const L = lightState(); light.set(L.text, L.tone);
    const p = here(hr);
    link.set(ui.show.earth && p ? (p.linked ? 'In sight' : `Behind the terrain (back in ${inH(p.wait)})`) : null, p && !p.linked ? 'warm' : 'cool');
    if (st.env2) {
      const gap = progress(st.env) - progress(st.env2);
      race.set(st.done && st.done2 ? `Expert ${hms(st.done.time_s)}, network ${hms(st.done2.time_s)}` : `Network ${Math.abs(gap) < 5 ? 'level' : `${Math.round(Math.abs(gap))} m ${gap > 0 ? 'behind' : 'ahead'}`}`);
    } else race.set(null);
  }

  // ---------- the story card: the moment's main thing, at most every 2.5 s unless something happens ----------
  function narrate(hr, now, force) {
    const e = st.env, lv = api.level(), last = st.events[st.events.length - 1], L = lightState(), p = here(hr), r = st.rec || { slip: 0, grade: 0 };
    let key, s;
    if (st.done && (!st.env2 || st.done2)) key = 'done';
    else if (e.steps === 0) key = 'ready';
    else if (last && e.timeS - last.t < 90) key = 'int' + st.events.length;
    else if (ui.show.earth && p && !p.linked && lv.autonomy === 'teleop') key = 'earth' + Math.round(p.km * 10);
    else if (r.slip >= 0.3) key = 'slip';
    else if (L.key !== 'sun') key = L.key;
    else key = (st.env2 ? 'race' : 'drive-' + lv.autonomy) + '|' + ui.view;
    const urgent = key === 'done' || key.startsWith('int') || key === 'ready';
    if (key === lastKey || (!force && !urgent && now - lastStoryAt < 2500)) return;
    lastKey = key; lastStoryAt = now;
    const a = $('r-from').value.replace('_', ' '), b = $('r-to').value.replace('_', ' '), km = fmt(st.prof?.length_m / 1000, 2);
    if (key === 'done') {
      const d = st.done, d2 = st.done2;
      s = { eyebrow: d.reached ? 'Arrived' : 'Stopped', title: `${a} to ${b}: ${hms(d.time_s)}`, html: `<p>${fmt(d.distance_m / 1000, 2)} km, ${fmt(d.energy_wh, 0)} Wh, ${d.interventions} intervention${d.interventions === 1 ? '' : 's'} and ${d.stops} stop${d.stops === 1 ? '' : 's'} to confirm.${d2 ? ` The network: ${d2.reached ? 'arrived' : 'stopped'} in ${hms(d2.time_s)} with ${d2.interventions} intervention${d2.interventions === 1 ? '' : 's'}; ${d.time_s <= d2.time_s ? 'the expert wins' : 'the network wins'}.` : ''} Pins on the ground mark each intervention.</p>` };
    } else if (key === 'ready') {
      s = { eyebrow: 'Ready', title: `${a} to ${b}: ${km} km`, html: `<p>The cyan ribbon is the planned route for ${api.lightingText()}. ${st.env2 ? 'The scripted expert (yellow ring) races the neural network (orange) on the same leg and soil.' : `${api.driverName()} drives, ${api.levelText()}.`} Press Drive above.</p>` };
    } else if (key.startsWith('int')) {
      s = { eyebrow: `Intervention ${st.events.length}`, title: last.why[0].toUpperCase() + last.why.slice(1), html: `<p>${WHY[last.why] || ''} A person on Earth takes over and drives it past the hazard: ${e.rtt} s round trip plus ${R.INTERVENTION.recovery_s} s added to the clock. The red pin marks the spot.</p>` };
    } else if (key.startsWith('earth')) {
      s = { eyebrow: 'Earth link', title: 'Earth is behind the terrain here', html: `<p>On ${date(hr)} a rover driven from Earth loses its link ${fmt(p.km, 1)} km into the leg (red posts: no part of Earth's disc above the terrain at the 2.5 m antenna). Here it would wait ${inH(p.wait)} for Earth to rise again. The lab's drive goes on so you can see the whole leg.</p>` };
    } else if (key === 'slip') {
      s = { eyebrow: 'Wheel slip', title: `${Math.round(100 * r.slip)} % slip`, html: `<p>On a ${fmt(r.grade, 1)}° grade in soil with a ${fmt(e.phi, 1)}° friction angle the wheels turn faster than the rover moves. At 80 % it digs in, and 30 s without progress calls an intervention.</p>` };
    } else if (key === 'glare') {
      s = { eyebrow: 'Low sun', title: 'Driving into the sun', html: `<p>The sun sits 1.5° above the horizon. Within 45° of its bearing (the orange wedge) the cameras are dazzled, so the model has the rover tack: speed × cos 25° = 0.91. Shadows run about 100 m behind every rock and rover.</p>` };
    } else if (key === 'shadow') {
      s = { eyebrow: 'Shadow', title: 'In the shadow of the terrain', html: `<p>The ridge blocks the sun here (the model's 20 m shadow grid), so the rover drives on its own lights at half speed.</p>` };
    } else if (key === 'night') {
      s = { eyebrow: 'Night', title: 'Headlights only', html: '<p>No sun: the rover sees only what its headlights light, so the model holds it to half speed all the way.</p>' };
    } else if (key.startsWith('race')) {
      s = { eyebrow: 'Race', title: 'Expert against network', html: '<p>Same leg, soil and lighting. The yellow ring is the scripted expert (route planner and path follower); the orange one is the neural network that learned to drive from it. Each pin is an intervention, and each costs over five minutes.</p>' };
    } else if (ui.view === 'side') {
      s = { eyebrow: 'Long shadows', title: 'A 100 m shadow', html: `<p>With the sun 1.5° up, the 2.6 m rover's shadow stretches about ${Math.round(2.6 / Math.tan(1.5 * Math.PI / 180))} m across the ground, and every boulder casts one too. Crater floors can stay dark for months.</p>` };
    } else if (lv.autonomy === 'teleop') {
      s = { eyebrow: 'Driven from Earth', title: lv.rtt ? `Every command acts ${lv.rtt} s later` : 'No delay', html: `<p>${lv.rtt ? `The pale rover ahead is where the command sent now takes effect, ${lv.rtt} s down the road. ` : ''}The operator stops every so often to pan the cameras (30 s plus two round trips) before driving on.</p>` };
    } else if (lv.autonomy === 'supervised') {
      s = { eyebrow: 'Supervised', title: 'Drives itself, a person checks', html: `<p>Up to ${R.SPEED_CAP_KMH.supervised} km/h, stopping every ${R.SUPERVISED_STOP.every_m} m for ${R.SUPERVISED_STOP.stop_s} s while someone on Earth confirms the next stretch.</p>` };
    } else {
      s = { eyebrow: 'Autonomous', title: 'No delay, no stops', html: `<p>Up to ${R.SPEED_CAP_KMH.autonomous} km/h, slowed by slope, glare and shadow. Only an intervention brings a person in.</p>` };
    }
    story.set(s);
  }

  // ---------- text version of the view ----------
  function mirror(hr) {
    const e = st.env, L = lightState(), g = st.done ? null : ghostState(e), total = e.pp.s[e.pp.s.length - 1], p = here(hr);
    const rows = [
      ['View', VIEWS.find(v => v.value === ui.view).label],
      ['Along the leg', `${fmt(progress(e) / 1000, 2)} of ${fmt(total / 1000, 2)} km`],
      ['Light', L.text],
      ['Command delay', g && ui.show.ghost ? `the command sent now acts ${fmt(Math.hypot(g.x - e.state.x, g.y - e.state.y), 1)} m ahead, ${e.rtt} s later` : e.autonomy === 'teleop' && e.rtt ? (st.done ? 'arrived' : 'stopped') : 'none at this control level'],
    ];
    if (samples && ui.show.earth) {
      const n = samples.filter(s => s.linked).length, lost = samples.find(s => !s.linked);
      rows.push(['Earth link along the leg', `${date(hr)}: ${n} of ${samples.length} points see Earth${lost ? `; first loss ${fmt(lost.km, 2)} km in` : ''} (computed along the leg's night route${samples.off > 40 ? `, on average ${Math.round(samples.off)} m from the route planned for this lighting` : ''})`]);
      if (p) rows.push(['Earth from the rover', p.linked ? 'in sight' : `behind the terrain, back in ${inH(p.wait)}`]);
    } else if (ui.show.earth && earth) rows.push(['Earth link along the leg', 'no samples for this leg']);
    rows.push(['Interventions', st.events.length ? st.events.map((v, i) => `${i + 1}. ${hms(v.t)} ${v.why}`).join('; ') : 'none yet']);
    if (st.env2) rows.push(['Network', `${fmt(progress(st.env2) / 1000, 2)} km, ${st.env2.interventions} intervention${st.env2.interventions === 1 ? '' : 's'}${st.done2 ? `, ${st.done2.reached ? 'arrived' : 'stopped'} in ${hms(st.done2.time_s)}` : ''}`]);
    $('r3-mirror').replaceChildren(...rows.flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, v)]));
  }

  return { leg, update, get entered() { return entered; } };
}
