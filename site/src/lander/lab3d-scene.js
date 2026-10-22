// The 3D scene of the lander lab (F-34), loaded when the visitor enters the 3D view. A recorded descent
// (trajectories-v1) replayed at true scale over the 5 m LOLA terrain at pad A on the shared stage: the catalogue
// lander with its attitude from the recorded quaternion, the F-33 engine glow, dust sheet, obscuration layer and
// scour mark (onset per the file), the pad and its 50 m delivery ring, the 500 Monte Carlo touchdowns on the ground,
// and three overlays: guidance (path, velocity and the velocity the guidance field asks for, hover point), thrust
// (thrust and weight as forces) and sensors (the altimeter beam, amber while it drops out). Cameras follow the
// lander: Chase, Side, Pad camera, and Into the sun for the dust.
import * as THREE from 'three';
import { createStage } from '../stage/index.js';
import { createLunarTerrain } from '../stage/terrain.js';
import { createLandingDust } from '../stage/effects/dust.js';
import { createGlow, nozzleExit } from '../stage/effects/glow.js';
import { dirFromAzEl } from '../stage/lighting.js';
import { TIERS } from '../stage/tier.js';
import { loadCatalog } from '../catalog.js';
import { buildVehicle, createMaterials } from '../models/index.js';
import { targetVelocity, VF } from './env.js';
import { CLASSES, G_MOON } from './classes.js';
import { reducedMotion } from '../ui/dom.js';

const BASE = import.meta.env.BASE_URL, KEEPOUT_M = 1000, DEG = Math.PI / 180;
// Monte Carlo touchdowns by outcome (Tol bright; the legend in the page also names them)
export const OUTCOME_COLOURS = { none: '#66CCEE', velocity: '#EE6677', tilt: '#CCBB44', sensor: '#AA3377', offpad: '#BBBBBB' };

export async function createLanderScene({ canvas, labelsHost, tier, fetchFn = fetch, onStatus = () => {} }) {
  const [stage, catalog] = await Promise.all([
    createStage({ canvas, labelsHost, preset: 'onsite', tier, onStatus }),
    loadCatalog(undefined, { fetchFn }),
  ]);
  const terrain = await createLunarTerrain({ base: BASE + 'terrain/hero/', renderer: stage.renderer, site: 'PAD_A', tier });
  await stage.setPreset('onsite', { sun: { az: 135, el: 1.5 }, ground: false });
  stage.setToneMapping('neutral', 2);   // exposed for the regolith, as a descent camera would be: sunlit paint burns out
  const scene = stage.scene, lighting = stage.lighting, mats = createMaterials(catalog.doc.materials);
  scene.add(terrain.group);
  scene.add(terrain.scatterRocks({ count: [0, 1500, 4000, 8000][tier] || 4000, radius: 320, clearM: 22, seed: 11 }));
  const padObj = buildVehicle(catalog, mats, 'pad'), padR = catalog.entry('pad').dims.diameter_m.value / 2;
  padObj.root.position.y = terrain.heightAt(0, 0) - 0.05; scene.add(padObj.root);
  const shade = root => root.traverse(o => { if (o.isMesh && o.material?.isMeshStandardMaterial) terrain.shadeWithHorizon(o.material); });
  shade(padObj.root);

  // ---------- the touchdown box: 50 m delivery ring draped on the ground, a 15 m hover point above the pad ----------
  const ringPts = [];
  for (let i = 0; i <= 128; i++) { const a = i / 128 * 2 * Math.PI, x = 50 * Math.cos(a), z = 50 * Math.sin(a); ringPts.push(new THREE.Vector3(x, terrain.heightAt(x, z) + 0.15, z)); }
  const boxMat = new THREE.LineDashedMaterial({ color: '#6fcde9', dashSize: 2, gapSize: 1.2, transparent: true, opacity: 0.85 });
  const ring = new THREE.Line(new THREE.BufferGeometry().setFromPoints(ringPts), boxMat); ring.computeLineDistances();
  const hoverMark = new THREE.Mesh(new THREE.TorusGeometry(1.2, 0.06, 8, 48).rotateX(Math.PI / 2), new THREE.MeshBasicMaterial({ color: '#6fcde9' }));
  hoverMark.position.set(0, terrain.heightAt(0, 0) + VF.hover_alt_m, 0);
  const boxGroup = new THREE.Group(); boxGroup.add(ring, hoverMark); scene.add(boxGroup);
  for (const o of [ring, hoverMark]) o.userData = { noPick: true, noAO: true };

  // ---------- Monte Carlo touchdowns: one disc per landing that reached the ground ----------
  const discGeo = new THREE.CircleGeometry(0.35, 12).rotateX(-Math.PI / 2);
  const scatter = new THREE.InstancedMesh(discGeo, new THREE.MeshBasicMaterial({ toneMapped: false }), 500);
  scatter.userData = { noPick: true, noAO: true }; scatter.count = 0; scene.add(scatter);
  function setScatter(outcomes) {
    const M = new THREE.Matrix4(), c = new THREE.Color(), counts = {};
    let n = 0;
    for (const e of outcomes?.episodes || []) {
      const k = e.failure_kind || 'none';
      if (k === 'timeout' || k === 'lost') continue;
      const x = e.miss_m[0], z = -e.miss_m[1];
      M.makeTranslation(x, terrain.heightAt(x, z) + 0.2, z); scatter.setMatrixAt(n, M);
      scatter.setColorAt(n, c.set(OUTCOME_COLOURS[k] || '#ffffff').multiplyScalar(0.6)); counts[k] = (counts[k] || 0) + 1; n++;
    }
    scatter.count = n; scatter.instanceMatrix.needsUpdate = true; if (scatter.instanceColor) scatter.instanceColor.needsUpdate = true;
    return { shown: n, counts, timeouts: (outcomes?.episodes || []).filter(e => e.failure_kind === 'timeout' || e.failure_kind === 'lost').length };
  }

  // ---------- overlays ----------
  const guide = new THREE.Group(), thrustG = new THREE.Group(), sensors = new THREE.Group();
  scene.add(guide, thrustG, sensors);
  const pathMat = new THREE.LineBasicMaterial({ color: '#d7e3ef', transparent: true, opacity: 0.55 });
  const path = new THREE.Line(new THREE.BufferGeometry(), pathMat); guide.add(path);
  const arrow = (col, len = 1) => { const a = new THREE.ArrowHelper(new THREE.Vector3(0, 1, 0), new THREE.Vector3(), len, col, 1.2, 0.7); a.traverse(o => { o.userData = { noPick: true, noAO: true }; }); return a; };
  const velArrow = arrow('#ffffff'), wantArrow = arrow('#6fcde9'); guide.add(velArrow, wantArrow);
  const thrustArrow = arrow('#f0a54a'), weightArrow = arrow('#bbbbbb'); thrustG.add(thrustArrow, weightArrow);
  const beamMat = new THREE.LineDashedMaterial({ color: '#6fcde9', dashSize: 0.6, gapSize: 0.4 });
  const beam = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(0, -1, 0)]), beamMat); sensors.add(beam);
  const reading = new THREE.Mesh(new THREE.RingGeometry(0.5, 0.7, 24).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: '#6fcde9', side: THREE.DoubleSide, toneMapped: false })); sensors.add(reading);
  for (const g of [guide, thrustG, sensors]) g.traverse(o => { o.userData.noPick = true; o.userData.noAO = true; });

  // ---------- the lander, its effects and the current episode ----------
  let cur = null;   // {cls, view, holder, vehicle, glow, dust, nozzle, tMax, localBox, approach}
  function setEpisode({ cls, view, seed = 1 }) {
    if (cur) { scene.remove(cur.holder, cur.dust.group); cur.glow?.dispose(); cur.dust.dispose(); cur.holder.traverse(o => o.geometry?.dispose()); }
    const entry = catalog.entry(cls), vehicle = buildVehicle(catalog, mats, cls), holder = new THREE.Group();
    holder.add(vehicle.root); scene.add(holder); shade(vehicle.root);
    const c = CLASSES[cls], tMax = c.t_max_n * view.ep.episode.thrust_scale, nozzle = nozzleExit(vehicle);
    const tl = { t: [], h: [], thrust: [], gx: [], gy: [], gz: [] };
    for (let t = 0; ; t = Math.min(view.tEnd, t + 0.1)) {
      const [x, y, z] = view.pos(t);
      tl.t.push(t); tl.h.push(z + nozzle.y); tl.thrust.push(view.throttle(t) * tMax); tl.gx.push(x); tl.gz.push(-y); tl.gy.push(terrain.heightAt(x, -y));
      if (t >= view.tEnd) break;
    }
    const dust = createLandingDust({ timeline: tl, cutoff: view.tEnd, keepoutM: KEEPOUT_M, seed, n: TIERS[3].particles, thrustN: c.t_max_n });
    dust.setGround(terrain.heightAt); dust.setCount(TIERS[stage.tier].particles); dust.setSun(dirFromAzEl(lighting.sunAzEl.az, 1.5), 1);
    scene.add(dust.group);
    // the flown path (scene frame), for the guidance overlay
    const pts = []; for (let t = 0; t <= view.tEnd; t += 0.5) { const [x, y, z] = view.pos(t); pts.push(new THREE.Vector3(x, terrain.heightAt(x, -y) + z + vehicle.size.y / 2, -y)); }
    path.geometry.dispose(); path.geometry = new THREE.BufferGeometry().setFromPoints(pts);
    const [x0, y0] = view.pos(0), [x1, y1] = view.pos(view.tEnd), ax = x1 - x0, ay = y1 - y0, an = Math.hypot(ax, ay) || 1;
    const blastR = 150 * Math.sqrt(c.t_max_n / 45000);
    cur = { cls, view, entry, holder, vehicle, glow: createGlow(vehicle, entry.plume_class), dust, nozzle, tMax, localBox: vehicle.box.clone(), blastR,
      approach: new THREE.Vector3(ax / an, 0, -ay / an), touchdown: [x1, -y1], mass0: view.ep.episode.m0_kg, mDry: view.ep.episode.m_dry_kg };
    return cur;
  }

  // ---------- light: the sun placed so the default camera sees the lander lit, on an azimuth where the pad is in sun ----------
  // the sun azimuth near the wanted one that lights the most of the pad and the ground under the approach
  function litAzimuthNear(az) {
    const pts = [[0, 0]];
    for (const f of [0.15, 0.3, 0.5, 0.7, 0.9]) { const [x, y] = cur.view.pos(f * cur.view.tEnd); pts.push([x, -y]); }
    const profiles = pts.map(([x, z]) => terrain.profileAt(x, z, 1)), score = a => profiles.reduce((s, p, i) => s + (p[Math.round(a) % 360] < 1.2 ? (i ? 1 : 3) : 0), 0);
    let best = az, bestS = -1;
    for (let d = 0; d <= 90; d += 5) for (const s of [1, -1]) { const a = ((az + s * d) % 360 + 360) % 360, sc = score(a) - d / 200; if (sc > bestS) { bestS = sc; best = a; } }
    return best;
  }
  function setSunAz(az) {
    lighting.apply('onsite', { sun: { az, el: 1.5 }, ground: false }); terrain.setSun(az, 1.5);
    cur?.dust.setSun(dirFromAzEl(az, 1.5), 1);
    stage.invalidate();
    return az;
  }

  // ---------- cameras ----------
  const tmpP = new THREE.Vector3(), tmpT = new THREE.Vector3(), last = new THREE.Vector3(), box = new THREE.Box3();
  let viewMode = 'side', following = true;
  const landerPos = () => cur.holder.position;
  function shot(mode, instant = false) {
    viewMode = mode;
    const p = landerPos(), h = cur.vehicle.size.y, a = cur.approach, side = new THREE.Vector3(-a.z, 0, a.x);
    const sun = dirFromAzEl(lighting.sunAzEl.az, 0); sun.y = 0; sun.normalize();
    const d = 10 * h + 25;
    let pos, tgt = p.clone().add(new THREE.Vector3(0, h * 0.5, 0));
    // a little above the lander, looking down ~25°, so the ground is in the frame even 400 m up
    if (mode === 'chase') pos = p.clone().addScaledVector(a, -d).add(new THREE.Vector3(0, 0.5 * d, 0));
    else if (mode === 'side') pos = p.clone().addScaledVector(side.dot(sun) >= 0 ? side : side.negate(), d).add(new THREE.Vector3(0, 0.45 * d, 0));
    else if (mode === 'sun') pos = p.clone().addScaledVector(sun, -d).add(new THREE.Vector3(0, 0.3 * d, 0));   // high enough to see over the pad's berm
    else {   // pad camera: on the ground at the pad's edge, sun at its back, looking up at the lander
      const x = sun.x * (padR + 8), z = sun.z * (padR + 8);
      pos = new THREE.Vector3(x, terrain.heightAt(x, z) + 1.6, z);
    }
    stage.director.controls.setLookAt(pos.x, pos.y, pos.z, tgt.x, tgt.y, tgt.z, !instant && !reducedMotion());   // cuts under reduced motion
    last.copy(p);
  }
  // follow: keep the camera's offset from the lander (orbiting stays free); the pad camera stays put and turns
  function follow() {
    if (!following || !cur) return;
    const p = landerPos(), c = stage.director.controls;
    if (viewMode === 'pad') { c.getPosition(tmpP); c.setLookAt(tmpP.x, tmpP.y, tmpP.z, p.x, p.y + cur.vehicle.size.y * 0.5, p.z, false); return; }
    const dx = p.x - last.x, dy = p.y - last.y, dz = p.z - last.z;
    if (dx || dy || dz) { c.getPosition(tmpP); c.getTarget(tmpT); c.setLookAt(tmpP.x + dx, tmpP.y + dy, tmpP.z + dz, tmpT.x + dx, tmpT.y + dy, tmpT.z + dz, false); }
    last.copy(p);
  }

  // ---------- one moment of the episode ----------
  const show = { guidance: true, thrust: false, sensors: false };
  const V = new THREE.Vector3(), Q = new THREE.Quaternion();
  function setTime(t) {
    const { view, holder, dust, glow, vehicle, nozzle } = cur;
    const [x, y, z] = view.pos(t), X = x, Z = -y, ground = terrain.heightAt(X, Z);
    holder.position.set(X, ground + z, Z); holder.quaternion.fromArray(view.quatScene(t)); holder.updateMatrixWorld(true);
    const thr = view.throttle(t);
    glow?.setThrottle(thr);
    dust.setTime(t);
    terrain.setScour({ x: cur.touchdown[0], z: cur.touchdown[1], rIn: 0.1 * cur.blastR, rOut: cur.blastR, amount: dust.model.scour(t), seed: 3 });
    // overlays, centred on the vehicle's middle
    const mid = holder.localToWorld(new THREE.Vector3(0, vehicle.size.y / 2, 0));
    guide.visible = show.guidance; thrustG.visible = show.thrust; sensors.visible = show.sensors;
    if (show.guidance) {
      const [vx, vy, vz] = view.vel(t), want = targetVelocity([x, y, z], [vx, vy, vz]);
      for (const [a, v] of [[velArrow, [vx, vz, -vy]], [wantArrow, [want[0], want[2], -want[1]]]]) {
        V.fromArray(v); const len = V.length(); a.visible = len > 0.05 && t < view.tEnd;
        const L = Math.max(1.2, 0.12 * vehicle.size.y * len), hd = Math.min(0.3 * L, 0.35 * vehicle.size.y);   // 12 % of the lander's height per m/s
        if (a.visible) { a.position.copy(mid); a.setDirection(V.normalize()); a.setLength(L, hd, 0.5 * hd); }
      }
    }
    if (show.thrust) {
      const m = cur.mDry + view.prop(t), tw = thr * cur.tMax / (m * G_MOON), d = view.dir(t), s = 3 + vehicle.size.y;
      thrustArrow.visible = thr > 0 && t < view.tEnd;
      thrustArrow.position.copy(mid); thrustArrow.setDirection(V.set(d[0], d[2], -d[1]).normalize()); thrustArrow.setLength(s * tw, 0.12 * s, 0.06 * s);
      weightArrow.position.copy(mid); weightArrow.setDirection(V.set(0, -1, 0)); weightArrow.setLength(s, 0.12 * s, 0.06 * s);
    }
    let drop = false;
    if (show.sensors) {
      const base = holder.position, meas = view.altMeas(t); drop = view.dropout(t);
      const pos = beam.geometry.attributes.position;
      pos.setXYZ(0, base.x, base.y + 0.3, base.z); pos.setXYZ(1, base.x, ground, base.z); pos.needsUpdate = true; beam.computeLineDistances();
      beamMat.color.set(drop ? '#f0a54a' : '#6fcde9'); reading.material.color.set(drop ? '#f0a54a' : '#6fcde9');
      reading.position.set(base.x, base.y - meas, base.z); sensors.visible = t < view.tEnd;
    }
    // the shadow camera hugs the lander; its depth reaches the ground only within 60 m of it (from higher up the shadow
    // falls kilometres away, and a kilometres-deep shadow camera would shade the lander itself with acne)
    box.copy(cur.localBox).applyMatrix4(holder.matrixWorld); lighting.fit(box, { groundY: z < 60 ? ground : null });
    terrain.setHorizonShade(holder, z < 30);   // the horizon map is for the ground; well above it the lander is in sun
    follow();
    stage.invalidate();
    return { altitude: z, ground, dropout: drop };
  }

  return {
    stage, terrain, catalog,
    setEpisode, setTime, setScatter,
    setShow(s) { Object.assign(show, s); },
    setView: (m, instant) => shot(m, instant), get view() { return viewMode; },
    setFollow(v) { following = v; },
    // put the sun where the side camera sees the lander lit (the pad stays in sun); returns the azimuth used
    lightForSide() {
      const a = cur.approach, side = new THREE.Vector3(-a.z, 0, a.x), camAz = Math.atan2(side.x, -side.z) / DEG;   // grid azimuth of the side camera
      return setSunAz(litAzimuthNear((camAz + 30 + 360) % 360));
    },
    setSunAz,
    setTier(t) { cur?.dust.setCount(TIERS[t].particles); },
    // first moment the plume throws dust (null if it never reaches the ground)
    dustOnset() { const m = cur.dust.model; for (let t = 0; t <= cur.view.tEnd; t += 0.1) if (m.emission(t) > 0) return t; return null; },
    sunAz: () => lighting.sunAzEl.az,
    dispose() { stage.dispose(); terrain.dispose(); },
  };
}
