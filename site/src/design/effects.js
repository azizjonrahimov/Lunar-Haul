// /design/stage/?scene=effects (F-33): lunar light and effects on the shared stage, at PAD_A on the real 5 m terrain.
// A lander's final descent replayed from trajectories-v1 (B-33, the classical pilot's median landing) with its engine
// glow, the dust sheet, the obscuration layer and the scour mark; a HAUL rover driving a loop with wheel dust, a long
// shadow and, at night, headlights; the sky with Earth from its SPICE track and stars at a long exposure. Every effect
// has a switch, the tier switch and the frame-time readout above apply, and "Check determinism" redraws a frame from
// the same seed and compares the pixels.
import * as THREE from 'three';
import { loadCatalog } from '../catalog.js';
import { buildVehicle, createMaterials } from '../models/index.js';
import { createLunarTerrain } from '../stage/terrain.js';
import { createLandingDust } from '../stage/effects/dust.js';
import { createWheelDust } from '../stage/effects/wheel-dust.js';
import { createGlow, nozzleExit, GLOW } from '../stage/effects/glow.js';
import { buildLandingDust, onsetHeight, ONSET_SOURCES } from '../stage/effects/dust-model.js';
import { loadEarthTrack, earthSimple } from '../stage/sky.js';
import { dirFromAzEl } from '../stage/lighting.js';
import { TIERS } from '../stage/tier.js';
import { segmented, h, reducedMotion } from '../ui/index.js';

const BASE = import.meta.env.BASE_URL;
const KEEPOUT_M = 1000;            // the scenario default keep-out radius (gallery "plume 1 km")
const fmt = (v, d = 1) => (Number.isFinite(v) ? v.toFixed(d) : '–');

// One recorded descent as functions of time. Pad frame (x, y horizontal, z up) -> scene (x, z, -y); rows per
// trajectories-v1: positions at 10 Hz then the touchdown instant; per 0.2 s step k: throttle, quaternion (body +z ->
// thrust direction).
function episode(ep) {
  const n = ep.n_samples, ns = ep.n_steps, tEnd = ep.t_end_s;
  const tAt = i => (i < n - 1 ? 0.1 * i : tEnd);
  function pos(t) {
    t = Math.max(0, Math.min(tEnd, t));
    let i = Math.min(n - 2, Math.floor(t / 0.1)); if (tAt(i + 1) < t) i = n - 2;
    const a = ep.pos_m[i], b = ep.pos_m[i + 1], f = (t - tAt(i)) / Math.max(1e-9, tAt(i + 1) - tAt(i));
    return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
  }
  const step = t => Math.max(0, Math.min(ns - 1, Math.floor(t / 0.2)));
  const throttle = t => (t >= tEnd ? 0 : ep.throttle[step(t)]);
  const q = new THREE.Quaternion();
  function quat(t) { const [w, x, y, z] = ep.quat_wxyz[step(Math.min(t, tEnd - 1e-6))]; return q.set(x, z, -y, w).normalize(); }
  return { tEnd, pos, throttle, quat, seed: ep.seed, pick: ep.pick, miss: ep.miss_m, thrustScale: ep.episode.thrust_scale };
}

export async function bootEffects({ stage, story, status, controls, parts, tier }) {
  const params = new URLSearchParams(location.search);
  const ui = { cls: ['CLPS', 'MK1', 'LARGE'].includes(params.get('lander')) ? params.get('lander') : 'CLPS', cam: 'sunward', focus: 'lander',
    light: 'day', night: false, exposure: 'sunlit', seed: Math.max(1, +(params.get('seed') || 1) | 0), sunAz: 135, earthDay: 3,
    fx: { glow: true, sheet: true, layer: true, scour: true, wheels: true, shadows: true, earth: true } };
  status('Loading the 5 m terrain, the descent trajectories, the catalogue and Earth’s track…');
  const [terrain, trajDoc, catalog, track] = await Promise.all([
    createLunarTerrain({ base: BASE + 'terrain/hero/', renderer: stage.renderer, site: 'PAD_A', tier, onAssets: m => { if (m !== 'horizon') status(m); stage.invalidate(); } }),
    fetch(BASE + 'lab/policies/trajectories-v1.json').then(r => (r.ok ? r.json() : Promise.reject(new Error(`trajectories-v1.json: HTTP ${r.status}`)))),
    loadCatalog(),
    loadEarthTrack(BASE + 'comms/earth_track-v1.json.gz').catch(() => null),
  ]);
  const mats = createMaterials(catalog.doc.materials);
  await stage.setPreset('onsite', { sun: { az: ui.sunAz, el: 1.5 }, ground: false });
  const scene = stage.scene, lighting = stage.lighting, sky = lighting.sky;
  scene.add(terrain.group);

  // ---------- the rover: HAUL on a 45 m loop west of the pad ----------
  const haul = buildVehicle(catalog, mats, 'HAUL'), rover = new THREE.Group();
  rover.add(haul.root); scene.add(rover);
  const speed = catalog.entry('HAUL').speed_kmh.value / 3.6, loop = { x: -150, z: 70, r: 45 };
  const L = haul.size.z, Wd = haul.size.x, wheelR = catalog.entry('HAUL').dims.wheel_d_m.value / 2;
  const contactsLocal = haul.parts.filter(p => p.object.userData.group === 'wheels').map(p => {
    const c = new THREE.Box3().setFromObject(p.object).getCenter(new THREE.Vector3()); return c.setY(c.y - wheelR);
  });
  const lamps = []; haul.root.traverse(o => { if (o.isMesh && o.material.name === 'lamp') lamps.push(o); });
  const headlights = lamps.map(m => {
    const p = m.getWorldPosition(new THREE.Vector3()), s = new THREE.SpotLight(0xfff3d6, 0, 90, 24 * Math.PI / 180, 0.45, 1.6);
    s.position.copy(p); s.target.position.copy(p).add(new THREE.Vector3(0, -2.2, 14)); s.castShadow = false;
    haul.root.add(s, s.target); return s;
  });
  const basis = new THREE.Matrix4();
  // pose at time t: on the loop, pitched and rolled to the ground under its corners
  function roverPose(t, out = { p: new THREE.Vector3(), q: new THREE.Quaternion(), fwd: [0, 1] }) {
    const a = t * speed / loop.r, fx = -Math.sin(a), fz = Math.cos(a);
    const x = loop.x + loop.r * Math.cos(a), z = loop.z + loop.r * Math.sin(a), y = terrain.heightAt(x, z);
    const H = (dx, dz) => terrain.heightAt(x + dx, z + dz);
    const f = new THREE.Vector3(fx * L, H(fx * L / 2, fz * L / 2) - H(-fx * L / 2, -fz * L / 2), fz * L).normalize();
    const s = new THREE.Vector3(fz * Wd, H(fz * Wd / 2, -fx * Wd / 2) - H(-fz * Wd / 2, fx * Wd / 2), -fx * Wd).normalize();
    const up = new THREE.Vector3().crossVectors(f, s).normalize(); s.crossVectors(up, f).normalize();
    out.q.setFromRotationMatrix(basis.makeBasis(s, up, f)); out.p.set(x, y, z); out.fwd = [fx, fz];
    return out;
  }
  const tmpPose = { p: new THREE.Vector3(), q: new THREE.Quaternion(), fwd: [0, 1] }, tmpM = new THREE.Matrix4(), tmpV = new THREE.Vector3();
  const roverSource = t => {
    roverPose(t, tmpPose); tmpM.compose(tmpPose.p, tmpPose.q, new THREE.Vector3(1, 1, 1));
    return { contacts: contactsLocal.map(c => tmpV.copy(c).applyMatrix4(tmpM).toArray()), fwd: tmpPose.fwd, speed: ui.fx.wheels ? speed : 0 };
  };
  let wheelDust = createWheelDust({ nWheels: contactsLocal.length, seed: ui.seed, ratePerWheel: [0, 30, 60, 100][tier] || 60 });
  scene.add(wheelDust.points);

  // ---------- the lander and its effects ----------
  let L1 = null;   // {holder, vehicle, ep, glow, dust, nozzle, entry, plume, localBox}
  function buildLander() {
    if (L1) { scene.remove(L1.holder, L1.dust.group); L1.glow?.dispose(); L1.dust.dispose(); L1.holder.traverse(o => { if (o.geometry) o.geometry.dispose(); }); }
    const pilot = trajDoc.pilots.find(p => p.cls === ui.cls && p.pilot === 'classical'), raw = pilot.episodes.find(e => e.pick === 'p50');
    const ep = episode(raw), entry = catalog.entry(ui.cls), vehicle = buildVehicle(catalog, mats, ui.cls), holder = new THREE.Group();
    holder.add(vehicle.root); scene.add(holder);
    const plume = trajDoc.plume[ui.cls], tMax = plume.t_max_n * ep.thrustScale, nozzle = nozzleExit(vehicle);
    // dust timeline at 10 Hz: nozzle height above the ground, thrust, the ground point under the nozzle
    const tl = { t: [], h: [], thrust: [], gx: [], gy: [], gz: [] };
    for (let t = 0; t <= ep.tEnd + 1e-9; t = Math.min(ep.tEnd, t + 0.1)) {
      const [x, y, z] = ep.pos(t), gx = x, gz = -y;
      tl.t.push(t); tl.h.push(z + nozzle.y); tl.thrust.push(ep.throttle(t) * tMax); tl.gx.push(gx); tl.gz.push(gz); tl.gy.push(terrain.heightAt(gx, gz));
      if (t >= ep.tEnd) break;
    }
    const dust = createLandingDust({ timeline: tl, cutoff: ep.tEnd, keepoutM: KEEPOUT_M, seed: ui.seed, n: TIERS[3].particles, thrustN: plume.t_max_n });
    dust.setGround(terrain.heightAt); dust.setCount(TIERS[stage.tier].particles);
    scene.add(dust.group);
    const glow = createGlow(vehicle, entry.plume_class);
    const [tx, , tz] = ep.pos(ep.tEnd);
    L1 = { holder, vehicle, ep, glow, dust, nozzle, entry, plume, tMax, timeline: tl, localBox: vehicle.box.clone(), touchdown: [tx, -tz],
      blastR: 150 * Math.sqrt(plume.t_max_n / 45000) };
    time.t = Math.max(0, ep.tEnd - 22); time.max = ep.tEnd + 8;
    setShots();
  }

  // ---------- time ----------
  // time runs in a stage animation, so the stage's Pause button stops it; under reduced motion it starts paused
  const time = { t: 0, max: 1, playing: !reducedMotion(), rate: 1 };
  const tick = dt => {
    if (!time.playing) return false;
    time.t += dt * time.rate; if (time.t > time.max) time.t = Math.max(0, L1.ep.tEnd - 22);
    update(); return true;
  };
  const play = v => { time.playing = v; if (v) stage.animate(tick); };

  // ---------- per-frame update ----------
  const box = new THREE.Box3(), camGround = new THREE.Vector3(Infinity, 0, 0);
  const sunDir = () => dirFromAzEl(ui.sunAz, 1.5);
  function update() {
    const t = time.t, { ep, holder, dust, glow } = L1;
    const [x, y, z] = ep.pos(t), X = x, Z = -y;
    holder.position.set(X, terrain.heightAt(X, Z) + z, Z); holder.quaternion.copy(ep.quat(t)); holder.updateMatrixWorld(true);
    glow?.setThrottle(ui.fx.glow ? ep.throttle(t) : 0);
    dust.setTime(t);
    terrain.setScour({ x: L1.touchdown[0], z: L1.touchdown[1], rIn: 0.1 * L1.blastR, rOut: L1.blastR, amount: ui.fx.scour ? dust.model.scour(t) : 0, seed: ui.seed });
    roverPose(t, tmpPose); rover.position.copy(tmpPose.p); rover.quaternion.copy(tmpPose.q); rover.updateMatrixWorld(true);
    wheelDust.update(t, roverSource);
    // the shadow camera hugs the focused vehicle (research §1.7)
    const focus = ui.focus === 'lander' ? holder : rover, local = ui.focus === 'lander' ? L1.localBox : haul.box;
    box.copy(local).applyMatrix4(focus.matrixWorld);
    lighting.fit(box, { groundY: terrain.heightAt(focus.position.x, focus.position.z) });
    // the sky's horizon cut-off follows the camera (recomputed after 100 m)
    const cp = stage.camera.position;
    if (Math.hypot(cp.x - camGround.x, cp.z - camGround.z) > 100) {
      camGround.copy(cp);
      sky.setHorizon(terrain.profileAt(cp.x, cp.z, Math.max(1.5, cp.y - terrain.heightAt(cp.x, cp.z))));
    }
    stage.invalidate();
  }

  // ---------- light, sky, exposure ----------
  function applyLight() {
    if (lighting.sunAzEl.az !== ui.sunAz) lighting.apply('onsite', { sun: { az: ui.sunAz, el: 1.5 }, ground: false });   // re-aims the sun, rebuilds the bounce light
    terrain.setSun(ui.sunAz, 1.5);
    lighting.setNight(ui.night);
    const sd = sunDir();
    L1?.dust.setSun(sd, ui.night ? 0 : 1); wheelDust.setSun(sd, ui.night ? 0 : 1);
    terrain.setAmbient(ui.night ? new THREE.Color(0.006, 0.007, 0.009) : new THREE.Color(0.02, 0.02, 0.021));
    for (const s of headlights) s.intensity = ui.night ? 45 : 0;
    stage.setToneMapping(stage.renderer.toneMapping === THREE.ACESFilmicToneMapping ? 'aces' : stage.renderer.toneMapping === THREE.AgXToneMapping ? 'agx' : 'neutral',
      (ui.night ? 10 : 1) * (ui.exposure === 'long' ? 8 : 1));
    applySky();
  }
  const earthAt = d => (track ? track.at(d * 24) : earthSimple(d * 24));
  function applySky() {
    const sk = lighting.sky; if (!sk) return;
    sk.setEarth(earthAt(ui.earthDay)); sk.earth.visible = ui.fx.earth; sk.setStars(ui.exposure === 'long');
    camGround.set(Infinity, 0, 0);
    stage.invalidate();
  }

  // ---------- camera shots round the pad, set by the sun's azimuth ----------
  function setShots() {
    const s = sunDir(), hx = s.x, hz = s.z, k = Math.hypot(hx, hz), ux = hx / k, uz = hz / k;
    const at = (x, z, up) => [x, terrain.heightAt(x, z) + up, z];
    const d = Math.max(45, 12 * (L1?.vehicle.size.y || 4));
    stage.director
      .shot('sunward', { position: at(-ux * d - uz * 0.35 * d, -uz * d + ux * 0.35 * d, 0.25 * d), target: at(0, 0, 0.4 * (L1?.vehicle.size.y || 4)) })
      .shot('sunbehind', { position: at(ux * d, uz * d, 0.25 * d), target: at(0, 0, 0.4 * (L1?.vehicle.size.y || 4)) })
      .shot('wide', { position: at(-ux * 420 + uz * 260, -uz * 420 - ux * 260, 160), target: at(-40, 20, 0) })
      .shot('rover', roverShot());
  }
  // behind and beside the rover where it is now, looking past it along its heading
  function roverShot() {
    const p = roverPose(time.t, { p: new THREE.Vector3(), q: new THREE.Quaternion(), fwd: [0, 1] }), [fx, fz] = p.fwd;
    const cx = p.p.x - fx * 16 + fz * 7, cz = p.p.z - fz * 16 - fx * 7;
    return { position: [cx, terrain.heightAt(cx, cz) + 5, cz], target: [p.p.x + fx * 6, p.p.y + 1, p.p.z + fz * 6] };
  }

  // ---------- controls ----------
  const row = (cls = '') => { const r = h('div', { class: 's-row ' + cls }); controls.append(r); return r; };
  const r1 = row(), r2 = row(), r3 = row('s-buttons'), r4 = row('s-fx');
  const seg = (parent, legend, options, key, fn) => parent.append(segmented({ legend, options, value: String(ui[key]), onChange: v => { ui[key] = v; fn(v); } }).el);
  seg(r1, 'Lander', [{ value: 'CLPS', label: 'Small' }, { value: 'MK1', label: 'Medium' }, { value: 'LARGE', label: 'Large' }], 'cls', () => { buildLander(); applyLight(); update(); narrate(); describe(); });
  seg(r1, 'Camera', [{ value: 'sunward', label: 'Toward the sun' }, { value: 'sunbehind', label: 'Sun behind' }, { value: 'wide', label: 'Wide' }, { value: 'rover', label: 'Rover' }], 'cam', v => { if (v === 'rover') stage.director.shot('rover', roverShot()); stage.director.go(v); narrate(); });
  seg(r1, 'Shadow camera on', [{ value: 'lander', label: 'Lander' }, { value: 'rover', label: 'Rover' }], 'focus', () => update());
  seg(r2, 'Light', [{ value: 'day', label: 'Day (1.5° sun)' }, { value: 'night', label: 'Night' }], 'light', v => { ui.night = v === 'night'; applyLight(); update(); narrate(); });
  seg(r2, 'Exposure', [{ value: 'sunlit', label: 'Sunlit' }, { value: 'long', label: 'Long (stars)' }], 'exposure', () => { applyLight(); narrate(); });
  const slider = (parent, label, min, max, stepV, value, fn, unit) => {
    const id = 's-' + label.toLowerCase().replace(/\W+/g, '-'), out = h('output', { for: id, class: 's-out' });
    const input = h('input', { type: 'range', id, min, max, step: stepV, value });
    const set = () => { out.textContent = unit(+input.value); };
    input.addEventListener('input', () => { fn(+input.value); set(); }); set();
    parent.append(h('label', { class: 's-slider', for: id }, h('span', { class: 'ui-label' }, label), input, out));
    return { input, set };
  };
  slider(r2, 'Sun azimuth', 0, 359, 1, ui.sunAz, v => { ui.sunAz = v; applyLight(); setShots(); update(); describe(); }, v => `${v}°`);
  slider(r2, 'Earth: day of Jan 2028', 0, 30, 0.25, ui.earthDay, v => { ui.earthDay = v; applySky(); describe(); }, v => `${fmt(v, 2)} d`);
  const playBtn = h('button', { class: 'ui-btn', type: 'button', 'aria-pressed': String(time.playing) }, time.playing ? 'Pause time' : 'Play time');
  playBtn.addEventListener('click', () => { play(!time.playing); playBtn.textContent = time.playing ? 'Pause time' : 'Play time'; playBtn.setAttribute('aria-pressed', String(time.playing)); stage.invalidate(); });
  const scrub = slider(r3, 'Time to touchdown', -25, 8, 0.1, -20, v => { time.t = L1.ep.tEnd + v; update(); narrate(); }, v => `${v >= 0 ? '+' : '−'}${fmt(Math.abs(v), 1)} s`);
  const seedIn = h('input', { type: 'number', id: 's-seed', min: 1, max: 99999, step: 1, value: ui.seed, class: 's-num' });
  seedIn.addEventListener('change', () => { ui.seed = Math.max(1, +seedIn.value | 0); rebuildSeed(); });
  const checkBtn = h('button', { class: 'ui-btn', type: 'button' }, 'Check determinism');
  checkBtn.addEventListener('click', () => checkDeterminism(checkBtn));
  r3.append(playBtn, h('label', { class: 's-check', for: 's-seed' }, 'Dust seed', seedIn), checkBtn);
  const FX = [['glow', 'Engine glow'], ['sheet', 'Dust sheet'], ['layer', 'Obscuration layer'], ['scour', 'Scour mark'], ['wheels', 'Wheel dust'], ['shadows', 'Vehicle shadows'], ['earth', 'Earth']];
  const fxBox = h('fieldset', { class: 's-fxset' }, h('legend', { class: 'ui-label' }, 'Effects'));
  for (const [k, label] of FX) {
    const input = h('input', { type: 'checkbox', checked: ui.fx[k] });
    input.addEventListener('change', () => { ui.fx[k] = input.checked; applyFx(); update(); });
    fxBox.append(h('label', { class: 's-check' }, input, ' ' + label));
  }
  r4.append(fxBox);
  function applyFx() {
    L1.dust.show({ sheet: ui.fx.sheet, layer: ui.fx.layer });
    wheelDust.points.visible = ui.fx.wheels;
    for (const m of [L1.holder, rover]) m.traverse(o => { if (o.isMesh && !o.userData.noAO) o.castShadow = ui.fx.shadows; });
    if (lighting.sky) lighting.sky.earth.visible = ui.fx.earth;
  }
  function rebuildSeed() {
    scene.remove(wheelDust.points); wheelDust.dispose();
    wheelDust = createWheelDust({ nWheels: contactsLocal.length, seed: ui.seed, ratePerWheel: [0, 30, 60, 100][tier] || 60 });
    scene.add(wheelDust.points);
    const keepT = time.t; buildLander(); time.t = keepT; applyLight(); applyFx(); update();
  }

  // ---------- the narrative card follows the phase ----------
  function phase(t) {
    const { ep, dust } = L1;
    if (t >= ep.tEnd) return dust.model.alive(t, 2000) > 0 ? 'after' : 'settled';
    return dust.model.emission(t) > 0 ? 'dust' : 'approach';
  }
  let lastPhase = '';
  function narrate(force = true) {
    const p = phase(time.t); if (!force && p === lastPhase) return; lastPhase = p;
    const { plume, entry } = L1, on = onsetHeight(L1.tMax), meas = plume.f33_onset_altitude_m?.value != null;
    const glowTxt = GLOW[entry.plume_class] ? `${entry.plume_class} engine: ${GLOW[entry.plume_class].strength < 0.1 ? 'almost no' : 'a faint'} glow at the nozzle, no shock diamonds in vacuum` : 'no engine glow';
    const text = {
      approach: ['Approach', 'The plume does not reach the ground yet', `Erosion starts when the nozzle is about ${fmt(on, 0)} m up (${meas ? 'Measured, Blue Ghost' : 'Assumed, scaled as √thrust from the Blue Ghost 15 m'}). Until then: ${glowTxt}.`],
      dust: ['Dust', 'A sheet of grains at 1–3° above the ground', 'Each grain flies a ballistic arc (g = 1.62 m/s², no air). The sheet is almost parallel to a 1.5° sun, so it glows when you look toward the sun and nearly vanishes with the sun behind you. The layer near the ground hides the surface in the last seconds.'],
      after: ['Engine off', 'The haze is gone at once', 'With no air to hold it up, the obscuration ends at cut-off. Grains already in flight finish their arcs, out to the 1 km keep-out ring, within seconds.'],
      settled: ['Settled', 'A scour mark is left behind', `The ground under the nozzle is scoured darker and a brighter, streaky blast zone of about ${fmt(L1.blastR, 0)} m surrounds it (shape and size Assumed).`],
    }[p];
    const night = ui.night ? ' Night: the sun is down; only the rover’s headlights light the ground (no air, so no beams), and the dust is dark.' : '';
    const stars = ui.exposure === 'long' ? ' Long exposure: stars appear and every sunlit surface burns out, which is why lunar photos show a black sky.' : '';
    story.set({ eyebrow: text[0], title: text[1], html: `<p>${text[2]}${night}${stars}</p>` });
  }

  // ---------- the text mirror and the numbers ----------
  function describe() {
    const { plume, entry, ep, dust } = L1, e = lighting.sky?.earthPos, on = onsetHeight(L1.tMax), meas = plume.f33_onset_altitude_m?.value != null;
    const shadowLen = h0 => h0 / Math.tan(1.5 * Math.PI / 180);
    const items = [
      ['Descent', `${entry.name}: the classical pilot’s median landing from trajectories-v1 (seed ${ep.seed}, miss ${fmt(ep.miss, 2)} m, ${fmt(ep.tEnd, 1)} s), at true scale over the 5 m LOLA patch round PAD_A.`],
      ['Engine glow', GLOW[entry.plume_class] ? `${entry.plume_class}: ${GLOW[entry.plume_class].note} (${GLOW[entry.plume_class].flag}).` : 'none for this class.'],
      ['Dust onset', `${fmt(on, 1)} m nozzle height at full thrust (${meas ? 'Measured: ' + ONSET_SOURCES.measured : 'Assumed: ' + ONSET_SOURCES.assumed}).`],
      ['Dust sheet', `${dust.model.n.toLocaleString('en')} seeded grains (this tier draws ${TIERS[stage.tier].particles.toLocaleString('en')}), launched at 1–3° (Measured, Apollo photogrammetry), ranges up to the ${KEEPOUT_M / 1000} km keep-out radius (Modelled).`],
      ['Obscuration', `a layer of ${fmt(dust.radius, 0)} m radius following the emission over the last 0.6 s; zero from engine cut-off on.`],
      ['Scour mark', `scoured centre ${fmt(0.1 * L1.blastR, 0)} m, blast zone ${fmt(L1.blastR, 0)} m (Assumed: √thrust from ~150 m for a 45 kN descent engine).`],
      ['Long shadows', `at 1.5° a shadow is 38× the height: ${fmt(shadowLen(entry.dims.height_m.value), 0)} m for this lander, ${fmt(shadowLen(haul.size.y), 0)} m for HAUL. The shadow camera hugs the focused vehicle; terrain shadows come from the horizon map.`],
      ['Rover', `HAUL at ${fmt(speed * 3.6, 0)} km/h (catalogue) on a ${loop.r} m loop: wheel dust in short arcs (rim speed = driving speed), headlights at night.`],
      ['Sun', `azimuth ${ui.sunAz}°, elevation 1.5°; any azimuth is lit from the stored horizon map without a re-bake.`],
      ['Earth', e ? `bearing ${fmt(e.az > 180 ? e.az - 360 : e.az, 1)}°, elevation ${fmt(e.el, 2)}°, radius ${fmt(e.radiusDeg, 2)}° (${e.source}); ${lighting.sky.earthVisible() ? 'above' : 'below'} the terrain horizon seen from the camera.` : '–'],
    ];
    parts.replaceChildren(...items.map(([k, v]) => h('li', {}, h('strong', {}, k), ` — ${v}`)));
  }

  // ---------- determinism: the same seed redraws the same frame ----------
  function frameHash() {
    stage.post.render(0);   // draw now and read the canvas before the browser composites it
    const gl = stage.renderer.getContext(), w = gl.drawingBufferWidth, hh = gl.drawingBufferHeight, px = new Uint8Array(w * hh * 4);
    gl.readPixels(0, 0, w, hh, gl.RGBA, gl.UNSIGNED_BYTE, px);
    let hsh = 0x811c9dc5; for (let i = 0; i < px.length; i++) hsh = Math.imul(hsh ^ px[i], 16777619);
    return (hsh >>> 0).toString(16).padStart(8, '0');
  }
  async function checkDeterminism(btn) {
    btn.disabled = true; const was = time.playing; play(false); stage.pause(true);
    const t = time.t, cfg = { timeline: L1.timeline, cutoff: L1.ep.tEnd, keepoutM: KEEPOUT_M, n: 4000 };
    const a = buildLandingDust({ ...cfg, seed: ui.seed }), b = buildLandingDust({ ...cfg, seed: ui.seed }), c = buildLandingDust({ ...cfg, seed: ui.seed + 1 });
    const same = (p, q) => { const u = [0, 0, 0], v = [0, 0, 0]; for (let i = 0; i < p.n; i++) { const x = p.positionAt(i, t, u), y = q.positionAt(i, t, v); if (x !== y || (x && (u[0] !== v[0] || u[1] !== v[1] || u[2] !== v[2]))) return false; } return true; };
    const cpu = same(a, b), cpuDiff = !same(a, c);
    const h1 = frameHash(); const s0 = ui.seed;
    rebuildSeed(); time.t = t; update(); const h2 = frameHash();
    ui.seed = s0 + 1; rebuildSeed(); time.t = t; update(); const h3 = frameHash();
    ui.seed = s0; rebuildSeed(); time.t = t; update();
    stage.pause(false); play(was);
    status(`Determinism at T${t - L1.ep.tEnd >= 0 ? '+' : '−'}${fmt(Math.abs(t - L1.ep.tEnd), 1)} s: grain positions ${cpu ? 'identical' : 'DIFFERENT'} for seed ${s0} built twice, ${cpuDiff ? 'different' : 'identical'} for seed ${s0 + 1}; frame hash ${h1} then ${h2} (${h1 === h2 ? 'identical' : 'DIFFERENT'}), seed ${s0 + 1}: ${h3}.`);
    btn.disabled = false;
  }

  // ---------- go ----------
  buildLander(); applyLight(); applyFx();
  stage.director.limits({ minDistance: 2, maxDistance: 3000, maxPolar: 96 });
  await stage.director.go('sunward', { instant: true });
  update(); narrate(); describe(); play(time.playing);
  scrub.input.value = String(time.t - L1.ep.tEnd); scrub.set();
  setInterval(() => {
    if (!L1) return;
    narrate(false);
    if (time.playing) { scrub.input.value = String(Math.max(-25, Math.min(8, time.t - L1.ep.tEnd)).toFixed(1)); scrub.set(); }
  }, 250);
  status('');
  return {
    home: () => stage.director.go(ui.cam),
    setTier(t) { L1.dust.setCount(TIERS[t].particles); describe(); update(); },
    readout() {
      const i = L1.dust.info(time.t), e = lighting.sky?.earthPos;
      return [['Dust grains in flight', i.alive.toLocaleString('en')], ['Obscuration', `${fmt(100 * i.obscuration, 0)} %`], ['Scour', `${fmt(100 * i.scour, 0)} %`],
        ['Earth el', e ? `${fmt(e.el, 2)}° ${lighting.sky.earthVisible() ? '(up)' : '(hidden)'}` : '–']];
    },
  };
}
