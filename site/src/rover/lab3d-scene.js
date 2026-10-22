// The 3D scene of the rover lab (F-35), loaded when the visitor enters the 3D view. The drive of the lab below (the JS
// port of lunar/Drive-v0) on the LOLA terrain at true scale on the shared stage: the catalogue LTV posed on the ground
// under its wheels, the planned route as a ribbon, the path driven, a ghost rover where the command sent now will act
// (teleop: one round trip later), the glare cone (the model slows the rover within 45° of the low sun), long sun
// shadows, headlights at night, interventions as pins with callouts, the network as a second rover in a race, and
// the Earth-link samples along the leg (R-1) as antenna-high posts, cyan while Earth is in sight, red when it is not.
// Rocks are representative (LOLA cannot resolve them; the driving model sees only the 5 m and 20 m grids).
// Frames: the drive's terrain-pack x east, y north -> scene x east, y up, z south (terrain.toScene).
import * as THREE from 'three';
import { createStage } from '../stage/index.js';
import { createLunarTerrain } from '../stage/terrain.js';
import { dirFromAzEl } from '../stage/lighting.js';
import { loadCatalog } from '../catalog.js';
import { buildVehicle, createMaterials } from '../models/index.js';
import { reducedMotion } from '../ui/dom.js';
import { UP_SUN_HALF_ANGLE_DEG } from './physics.js';

const BASE = import.meta.env.BASE_URL, DEG = Math.PI / 180, UP = new THREE.Vector3(0, 1, 0);
export const COLOURS = { route: '#66CCEE', expert: '#CCBB44', network: '#EE7733', ghost: '#9fe3f5', glare: '#f0a54a', linked: '#66CCEE', lost: '#EE6677', pin: '#EE6677' };
const TRAIL_MAX = 6000, GLARE_R = 40;

export async function createRoverScene({ canvas, labelsHost, tier, fetchFn = fetch, onStatus = () => {} }) {
  const [stage, catalog] = await Promise.all([
    createStage({ canvas, labelsHost, preset: 'onsite', tier, onStatus }),
    loadCatalog(undefined, { fetchFn }),
  ]);
  const terrain = await createLunarTerrain({ base: BASE + 'terrain/hero/', renderer: stage.renderer, site: 'BASE', tier, farStride: [4, 4, 2, 1][tier] ?? 2 });
  await stage.setPreset('onsite', { sun: { az: 90, el: 1.5 }, ground: false });
  stage.setToneMapping('neutral', 2);
  const scene = stage.scene, lighting = stage.lighting, camera = stage.camera, mats = createMaterials(catalog.doc.materials);
  scene.add(terrain.group);
  const shade = root => root.traverse(o => { if (o.isMesh && o.material?.isMeshStandardMaterial) terrain.shadeWithHorizon(o.material); });
  const flat = o => { o.traverse(c => { c.userData.noPick = true; c.userData.noAO = true; }); return o; };
  const S = (x, y) => { const p = terrain.toScene(x, y, 0); return [p[0], p[2]]; };   // pack x, y -> scene x, z
  const ground = (x, z) => terrain.surfaceAt(x, z);
  const fwd = psi => new THREE.Vector3(Math.sin(psi), 0, -Math.cos(psi));            // map azimuth -> scene direction

  // ---------- rovers: the driver's LTV (with headlights) and, in a race, the network's ----------
  const lamps = [];
  function makeRover(colour, withLights) {
    const model = buildVehicle(catalog, mats, 'LTV'), holder = new THREE.Group();
    shade(model.root); holder.add(model.root); scene.add(holder);
    const L = model.size.z, W = model.size.x;
    const ring = new THREE.Mesh(new THREE.RingGeometry(L * 0.62, L * 0.72, 48).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: colour, toneMapped: false, transparent: true, opacity: 0.7, side: THREE.DoubleSide, depthWrite: false }));
    ring.position.y = 0.12; holder.add(flat(ring));
    if (withLights) model.root.traverse(o => {
      if (!o.isMesh || o.material.name !== 'lamp') return;
      const p = o.getWorldPosition(new THREE.Vector3()), s = new THREE.SpotLight(0xfff3d6, 0, 90, 24 * DEG, 0.45, 1.6);
      s.position.copy(p); s.target.position.copy(p).add(new THREE.Vector3(0, -2.2, 14)); s.castShadow = false;
      model.root.add(s, s.target); lamps.push(s);
    });
    const tg = new THREE.BufferGeometry(); tg.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(TRAIL_MAX * 3), 3)); tg.setDrawRange(0, 0);
    const trail = new THREE.Line(tg, new THREE.LineBasicMaterial({ color: colour, transparent: true, opacity: 0.9, toneMapped: false }));
    trail.frustumCulled = false; scene.add(flat(trail));
    return { model, holder, ring, trail, L, W, psiS: null, shown: 0 };
  }
  const rovers = [makeRover(COLOURS.expert, true), makeRover(COLOURS.network, false)];
  rovers[1].holder.visible = rovers[1].trail.visible = false;

  // pose on the drawn ground: pitched and rolled to the heights under its ends and sides
  const basis = new THREE.Matrix4();
  function pose(obj, s, L, W) {
    const [x, z] = S(s.x, s.y), fx = Math.sin(s.psi), fz = -Math.cos(s.psi), H = (dx, dz) => ground(x + dx, z + dz);
    const f = new THREE.Vector3(fx * L, H(fx * L / 2, fz * L / 2) - H(-fx * L / 2, -fz * L / 2), fz * L).normalize();
    const sd = new THREE.Vector3(fz * W, H(fz * W / 2, -fx * W / 2) - H(-fz * W / 2, fx * W / 2), -fx * W).normalize();
    const up = new THREE.Vector3().crossVectors(f, sd).normalize(); sd.crossVectors(up, f).normalize();
    obj.quaternion.setFromRotationMatrix(basis.makeBasis(sd, up, f)); obj.position.set(x, ground(x, z), z); obj.updateMatrixWorld(true);
  }

  // ghost: where the command sent now takes effect (teleop), a translucent rover
  const ghostMat = new THREE.MeshBasicMaterial({ color: COLOURS.ghost, transparent: true, opacity: 0.18, depthWrite: false, toneMapped: false });
  const ghostModel = buildVehicle(catalog, mats, 'LTV', { lod: 'simple' }), ghost = new THREE.Group();
  ghostModel.root.traverse(o => { if (o.isMesh) { o.material = ghostMat; o.castShadow = false; o.receiveShadow = false; } });
  ghost.add(ghostModel.root); ghost.visible = false; scene.add(flat(ghost));
  const ghostLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]), new THREE.LineDashedMaterial({ color: COLOURS.ghost, dashSize: 0.8, gapSize: 0.5, toneMapped: false }));
  ghostLine.frustumCulled = false; ghostLine.visible = false; scene.add(flat(ghostLine));

  // glare cone: the 90° wedge round the sun's bearing; the model slows the rover while it heads inside it in sunlight
  const RINGS = 6, SEGS = 24, glareGeo = new THREE.BufferGeometry();
  glareGeo.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array((1 + RINGS * (SEGS + 1)) * 3), 3));
  { const c = new Float32Array((1 + RINGS * (SEGS + 1)) * 3), g = new THREE.Color(COLOURS.glare); for (let i = 0; i < c.length / 3; i++) { const r = i === 0 ? 0 : Math.floor((i - 1) / (SEGS + 1)) + 1, k = (1 - r / RINGS) ** 1.5; c[3 * i] = g.r * k; c[3 * i + 1] = g.g * k; c[3 * i + 2] = g.b * k; } glareGeo.setAttribute('color', new THREE.Float32BufferAttribute(c, 3)); }
  { const idx = []; for (let r = 0; r < RINGS; r++) for (let k = 0; k < SEGS; k++) { const a = r === 0 ? 0 : 1 + (r - 1) * (SEGS + 1) + k, b = r === 0 ? 0 : a + 1, c = 1 + r * (SEGS + 1) + k, d = c + 1; if (r === 0) idx.push(0, c, d); else idx.push(a, c, b, b, c, d); } glareGeo.setIndex(idx); }
  const glareMat = new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.1, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide, toneMapped: false });
  const glare = new THREE.Mesh(glareGeo, glareMat); glare.frustumCulled = false; glare.renderOrder = 4; scene.add(flat(glare));
  function drapeGlare(p, sunAz) {
    const pos = glareGeo.attributes.position; pos.setXYZ(0, p.x, ground(p.x, p.z) + 0.25, p.z);
    for (let r = 1; r <= RINGS; r++) for (let k = 0; k <= SEGS; k++) {
      const a = (sunAz - UP_SUN_HALF_ANGLE_DEG + 2 * UP_SUN_HALF_ANGLE_DEG * k / SEGS) * DEG, d = GLARE_R * r / RINGS, x = p.x + d * Math.sin(a), z = p.z - d * Math.cos(a);
      pos.setXYZ(1 + (r - 1) * (SEGS + 1) + k, x, ground(x, z) + 0.25, z);
    }
    pos.needsUpdate = true;
  }

  // ---------- the leg: route ribbon and line, end posts, rocks, Earth-link posts, intervention pins ----------
  const legG = new THREE.Group(); scene.add(legG);
  let leg = null;   // {path (scene Vector3s), box, from, to}
  const pins = [[], []], roverLabels = [];
  const postGeo = new THREE.CylinderGeometry(0.09, 0.09, 1, 6).translate(0, 0.5, 0), headGeo = new THREE.SphereGeometry(0.35, 12, 8);
  let earthPosts = null, earthHeads = null, earthDiscs = null;
  function clearLeg() {
    for (const o of [...legG.children]) { legG.remove(o); o.traverse(c => { if (c.geometry && c.geometry !== postGeo && c.geometry !== headGeo) c.geometry.dispose(); }); }
    earthPosts = earthHeads = earthDiscs = null; pins[0] = []; pins[1] = [];
    stage.labels.clear();
  }
  function setLeg({ path, from, to, fromXY, toXY }) {
    clearLeg();
    const P = path.map(([x, y]) => { const [sx, sz] = S(x, y); return new THREE.Vector3(sx, ground(sx, sz), sz); });
    // ribbon 2.4 m wide, a hair above the ground, and a line on top for far views
    const w = 1.2, pos = [], idx = [];
    for (let i = 0; i < P.length; i++) {
      const a = P[Math.max(0, i - 1)], b = P[Math.min(P.length - 1, i + 1)], t = new THREE.Vector3(b.x - a.x, 0, b.z - a.z).normalize(), n = new THREE.Vector3(-t.z, 0, t.x);
      for (const s of [-1, 1]) { const x = P[i].x + s * w * n.x, z = P[i].z + s * w * n.z; pos.push(x, ground(x, z) + 0.12, z); }
      if (i) { const k = 2 * i; idx.push(k - 2, k, k - 1, k - 1, k, k + 1); }
    }
    const rg = new THREE.BufferGeometry(); rg.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); rg.setIndex(idx);
    legG.add(flat(new THREE.Mesh(rg, new THREE.MeshBasicMaterial({ color: COLOURS.route, transparent: true, opacity: 0.3, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4, toneMapped: false }))));
    legG.add(flat(new THREE.Line(new THREE.BufferGeometry().setFromPoints(P.map(p => p.clone().setY(p.y + 0.35))), new THREE.LineBasicMaterial({ color: COLOURS.route, transparent: true, opacity: 0.75, toneMapped: false }))));
    // end posts with labels
    for (const [name, xy] of [[from, fromXY], [to, toXY]]) {
      const [x, z] = S(...xy), g = new THREE.Group(), m = new THREE.MeshBasicMaterial({ color: '#e9eef5', toneMapped: false });
      const post = new THREE.Mesh(postGeo, m); post.scale.set(1, 8, 1); const head = new THREE.Mesh(headGeo, m); head.position.y = 8; g.add(post, head);
      g.position.set(x, ground(x, z), z); legG.add(flat(g));
      stage.labels.add({ id: 'end-' + name, text: name.replace('_', ' '), object: g, anchor: new THREE.Vector3(0, 8.5, 0) });
    }
    rocksAlong(P);
    const box = new THREE.Box3().setFromPoints(P);
    leg = { P, box, from, to };
    for (const r of rovers) { r.psiS = null; r.trail.geometry.setDrawRange(0, 0); r.shown = 0; }
    roverLabels[0] = stage.labels.add({ id: 'rover-0', text: 'Expert', object: rovers[0].holder, anchor: new THREE.Vector3(0, rovers[0].model.size.y + 1.2, 0) });
    roverLabels[1] = stage.labels.add({ id: 'rover-1', text: 'Network', object: rovers[1].holder, anchor: new THREE.Vector3(0, rovers[1].model.size.y + 1.2, 0), tone: 'warm' });
    stage.labels.add({ id: 'ghost', text: 'Your command acts here', object: ghost, anchor: new THREE.Vector3(0, ghostModel.size.y + 0.8, 0) });
    stage.labels.setHidden('rover-1', true); stage.labels.setHidden('ghost', true);
    stage.invalidate();
  }
  // seeded rocks beside the route (never on it): power-law sizes, 4-140 m either side (representative)
  function rocksAlong(P) {
    const count = [0, 2500, 5000, 9000][tier] || 5000; if (!count || P.length < 2) return;
    let a = 20281;
    const rnd = () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
    const geo = new THREE.IcosahedronGeometry(1, 1), gp = geo.attributes.position;
    for (let i = 0; i < gp.count; i++) { const k = 0.75 + 0.5 * rnd(); gp.setXYZ(i, gp.getX(i) * k, gp.getY(i) * k * 0.7, gp.getZ(i) * k); }
    geo.computeVertexNormals();
    const mat = terrain.shadeWithHorizon(new THREE.MeshStandardMaterial({ color: new THREE.Color(0.15, 0.147, 0.14), roughness: 0.95, metalness: 0, name: 'rock (representative)' }));
    const mesh = new THREE.InstancedMesh(geo, mat, count), M = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), v = new THREE.Vector3(), sc = new THREE.Vector3();
    for (let n = 0; n < count; n++) {
      const i = Math.min(P.length - 2, Math.floor(rnd() * (P.length - 1))), A = P[i], B = P[i + 1], f = rnd();
      const tx = B.x - A.x, tz = B.z - A.z, tl = Math.hypot(tx, tz) || 1, off = (4 + 136 * rnd() ** 1.6) * (rnd() < 0.5 ? -1 : 1);
      const x = A.x + tx * f - tz / tl * off, z = A.z + tz * f + tx / tl * off, d = Math.min(1.8, 0.1 * Math.pow(1 - rnd(), -1 / 2.5));
      e.set(rnd() * 6.28, rnd() * 6.28, rnd() * 6.28); q.setFromEuler(e); sc.set(d / 2 * (0.8 + 0.4 * rnd()), d / 2, d / 2 * (0.8 + 0.4 * rnd()));
      mesh.setMatrixAt(n, M.compose(v.set(x, ground(x, z) + 0.15 * d, z), q, sc));
    }
    mesh.instanceMatrix.needsUpdate = true; mesh.computeBoundingSphere(); mesh.castShadow = true; mesh.receiveShadow = true;
    mesh.userData = { noPick: true, representative: true }; legG.add(mesh);
  }

  // Earth-link samples: a 2.5 m post (the antenna height) and a disc per sample, coloured by link state
  function setEarth(samples) {
    if (earthPosts) for (const o of [earthPosts, earthHeads, earthDiscs]) { legG.remove(o); if (o !== earthPosts && o !== earthHeads) o.geometry.dispose(); }
    earthPosts = earthHeads = earthDiscs = null;
    if (!samples?.length) { stage.invalidate(); return; }
    const n = samples.length, mat = new THREE.MeshBasicMaterial({ toneMapped: false }), dmat = new THREE.MeshBasicMaterial({ toneMapped: false, transparent: true, opacity: 0.55, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -6 });
    earthPosts = new THREE.InstancedMesh(postGeo, mat, n); earthHeads = new THREE.InstancedMesh(headGeo, mat, n);
    earthDiscs = new THREE.InstancedMesh(new THREE.CircleGeometry(2.2, 20).rotateX(-Math.PI / 2), dmat, n);
    const M = new THREE.Matrix4();
    samples.forEach((s, i) => {
      const [x, z] = S(s.x, s.y), y = ground(x, z);
      earthPosts.setMatrixAt(i, M.makeScale(1, 2.5, 1).setPosition(x, y, z)); earthHeads.setMatrixAt(i, M.makeScale(0.6, 0.6, 0.6).setPosition(x, y + 2.5, z));
      earthDiscs.setMatrixAt(i, M.makeTranslation(x, y + 0.2, z));
    });
    for (const o of [earthPosts, earthHeads, earthDiscs]) { o.frustumCulled = false; legG.add(flat(o)); }
    setEarthState(samples.map(s => s.linked));
  }
  const cLinked = new THREE.Color(COLOURS.linked), cLost = new THREE.Color(COLOURS.lost);
  function setEarthState(linked) {
    if (!earthPosts) return;
    linked.forEach((on, i) => { for (const o of [earthPosts, earthHeads, earthDiscs]) o.setColorAt(i, on ? cLinked : cLost); });
    for (const o of [earthPosts, earthHeads, earthDiscs]) o.instanceColor.needsUpdate = true;
    stage.invalidate();
  }

  // interventions: a red pin and a callout each; who: 0 = the driver, 1 = the network in a race
  function setPins(who, events) {
    for (let i = pins[who].length; i < events.length && i < 24; i++) {
      const e = events[i], [x, z] = S(e.x, e.y), g = new THREE.Group(), m = new THREE.MeshBasicMaterial({ color: who ? COLOURS.network : COLOURS.pin, toneMapped: false });
      const post = new THREE.Mesh(postGeo, m); post.scale.set(1.6, 6, 1.6); const head = new THREE.Mesh(headGeo, m); head.scale.setScalar(1.6); head.position.y = 6; g.add(post, head);
      g.position.set(x, ground(x, z), z); legG.add(flat(g)); pins[who].push(g);
      stage.labels.add({ id: `pin-${who}-${i}`, text: `${who ? 'Network: ' : ''}intervention ${i + 1}: ${e.why}`, object: g, anchor: new THREE.Vector3(0, 6.6, 0), tone: 'warm' });
    }
    stage.invalidate();
  }

  // ---------- sun, night, sky ----------
  let sunAz = 90, night = false;
  function setSun(v) {
    night = v === 'night';
    if (!night) { sunAz = +v; lighting.setSun({ az: sunAz, el: 1.5 }); terrain.setSun(sunAz, 1.5); }
    lighting.setNight(night); terrain.setNight(night);
    for (const s of lamps) s.intensity = night ? 45 : 0;
    stage.invalidate();
  }
  let lastHz = new THREE.Vector3(Infinity, 0, 0);
  function skyHorizon() {
    if (camera.position.distanceTo(lastHz) < 150) return;
    lastHz.copy(camera.position);
    lighting.sky?.setHorizon(terrain.profileAt(camera.position.x, camera.position.z, Math.max(2, camera.position.y - ground(camera.position.x, camera.position.z))));
  }

  // ---------- cameras: Chase (turns with the rover), Cockpit, Side (across the sun: the long shadow), Whole leg ----------
  const tmpP = new THREE.Vector3(), tmpT = new THREE.Vector3(), last = new THREE.Vector3(), box = new THREE.Box3();
  let view = 'chase', lastPsi = null, lastReal = 0;
  const controls = stage.director.controls, lit = () => (night ? 1 : Math.sign(Math.sin((sunAz * DEG) - (rovers[0].psiS ?? 0))) || 1);
  function shot(mode, instant = false) {
    view = mode;
    const r = rovers[0], p = r.holder.position, psi = r.psiS ?? 0, f = fwd(psi), right = new THREE.Vector3(-f.z, 0, f.x), H = r.model.size.y;
    const sun = dirFromAzEl(sunAz, 0).setY(0).normalize(), across = new THREE.Vector3(-sun.z, 0, sun.x);
    let pos, tgt;
    if (mode === 'chase') {   // behind, a little up, off to the sunlit side so the rover is lit
      pos = p.clone().addScaledVector(f, -16).addScaledVector(right, 6 * lit()).add(new THREE.Vector3(0, 6.5, 0)); tgt = p.clone().addScaledVector(f, 6).add(new THREE.Vector3(0, H * 0.6, 0));
    } else if (mode === 'side') {   // across the sun, looking along the shadow, which runs away from the sun
      pos = p.clone().addScaledVector(across, 30).addScaledVector(sun, 6).add(new THREE.Vector3(0, 9, 0)); tgt = p.clone().addScaledVector(sun, -5);
    } else if (mode === 'leg') {
      const c = leg.box.getCenter(new THREE.Vector3()), s = leg.box.getSize(new THREE.Vector3()), d = Math.max(400, 1.1 * Math.max(s.x, s.z));
      const from = night ? new THREE.Vector3(0.4, 0, 0.9).normalize() : sun;
      pos = c.clone().addScaledVector(from, d * 0.8).add(new THREE.Vector3(0, d * 0.42, 0)); tgt = c;
    } else { cockpit(); return; }
    controls.setLookAt(pos.x, pos.y, pos.z, tgt.x, tgt.y, tgt.z, !instant && !reducedMotion());
    last.copy(p); lastPsi = psi;
  }
  function cockpit() {
    const r = rovers[0], m = r.holder.matrixWorld, eye = new THREE.Vector3(0, 1.7, r.L * 0.5 + 0.2).applyMatrix4(m);   // a camera on the front, 1.7 m up
    const ahead = new THREE.Vector3(0, 0.6, r.L * 0.5 + 40).applyMatrix4(m);
    controls.setLookAt(eye.x, eye.y, eye.z, ahead.x, ahead.y, ahead.z, false);
  }
  // follow: keep the camera's offset from the rover (orbiting stays free); Chase also turns with its smoothed heading
  function follow() {
    if (!leg) return;
    const r = rovers[0], p = r.holder.position;
    if (view === 'cockpit') { cockpit(); return; }
    if (view === 'leg') return;
    controls.getPosition(tmpP); controls.getTarget(tmpT);
    const dx = p.x - last.x, dy = p.y - last.y, dz = p.z - last.z;
    tmpP.x += dx; tmpP.y += dy; tmpP.z += dz; tmpT.x += dx; tmpT.y += dy; tmpT.z += dz;
    if (view === 'chase' && lastPsi !== null && r.psiS !== null) {
      const d = Math.atan2(Math.sin(r.psiS - lastPsi), Math.cos(r.psiS - lastPsi));
      if (d) { tmpP.sub(p).applyAxisAngle(UP, -d).add(p); tmpT.sub(p).applyAxisAngle(UP, -d).add(p); }
    }
    controls.setLookAt(tmpP.x, tmpP.y, tmpP.z, tmpT.x, tmpT.y, tmpT.z, false);
    last.copy(p); lastPsi = r.psiS;
  }

  // ---------- one moment: rover states from the page ----------
  // update({states: [s0, s1|null], ghost: state|null, trails: [[x, y]...] x2, sunlit})
  const show = { ghost: true, glare: true, earth: true };
  function update({ states, ghost: g, trails, sunlit = true }) {
    if (!leg) return;
    const now = performance.now(), dt = lastReal ? Math.min(0.25, (now - lastReal) / 1000) : 0; lastReal = now;
    states.forEach((s, i) => {
      const r = rovers[i];
      r.holder.visible = !!s; r.trail.visible = !!s; stage.labels.setHidden('rover-' + i, !s || (i === 0 && !states[1] && view !== 'leg' && view !== 'side'));
      if (!s) return;
      pose(r.holder, s, r.L, r.W);
      // the camera turns with a smoothed heading (a 60x replay can turn the rover sharply between frames)
      if (r.psiS === null) r.psiS = s.psi; else { const d = Math.atan2(Math.sin(s.psi - r.psiS), Math.cos(s.psi - r.psiS)); r.psiS += d * Math.min(1, dt * 4); }
      const tr = trails[i] || [], pa = r.trail.geometry.attributes.position, n = Math.min(TRAIL_MAX, tr.length + 1);
      for (let k = r.shown > 0 ? r.shown - 1 : 0; k < n; k++) { const q = k < tr.length ? tr[k] : [s.x, s.y], [x, z] = S(q[0], q[1]); pa.setXYZ(k, x, ground(x, z) + 0.3, z); }
      pa.needsUpdate = true; r.trail.geometry.setDrawRange(0, n); r.shown = Math.max(0, n - 1);
    });
    const r0 = rovers[0], p0 = r0.holder.position, inside = view === 'cockpit';
    r0.model.root.visible = r0.ring.visible = !inside;
    ghost.visible = ghostLine.visible = !!(show.ghost && g) && !inside;
    stage.labels.setHidden('ghost', !ghost.visible);
    if (ghost.visible) {
      pose(ghost, g, r0.L, r0.W);
      const gp = ghostLine.geometry.attributes.position; gp.setXYZ(0, p0.x, p0.y + 0.4, p0.z); gp.setXYZ(1, ghost.position.x, ghost.position.y + 0.4, ghost.position.z); gp.needsUpdate = true; ghostLine.computeLineDistances();
    }
    glare.visible = show.glare && !night && sunlit && !!states[0];   // the model applies glare only in sunlight
    if (glare.visible) {
      drapeGlare(p0, sunAz);
      const hd = Math.abs((((states[0].psi / DEG - sunAz) % 360) + 540) % 360 - 180);
      glareMat.opacity = hd <= UP_SUN_HALF_ANGLE_DEG ? 0.03 : 0.01;   // HDR: the regolith is dim next to an additive 1.0
    }
    // shadow camera on the driver's rover: the long shadow of a 2.6 m rover in a 1.5° sun is about 100 m
    box.copy(r0.model.box).applyMatrix4(r0.model.root.matrixWorld); lighting.fit(box, { groundY: null });
    follow(); skyHorizon();
    stage.invalidate();
  }

  return {
    stage, terrain, catalog, rovers,
    setLeg, setPins, setEarth, setEarthState, setSun,
    setShow(s) { Object.assign(show, s); if (earthPosts) for (const o of [earthPosts, earthHeads, earthDiscs]) o.visible = show.earth; stage.invalidate(); },
    setEarthSky(p) { lighting.sky?.setEarth(p); stage.invalidate(); },
    setRoverLabel(i, text) { roverLabels[i]?.setText(text); },
    update, setView: (m, instant) => shot(m, instant), get view() { return view; },
    get night() { return night; },
    dispose() { stage.dispose(); terrain.dispose(); },
  };
}
