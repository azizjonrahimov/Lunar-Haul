// The 3D scene of /world/ v2 (F-36), loaded when the visitor enters the 3D view. One simulated year from a scene
// package (scene-data.js) on the shared stage: the 16 km LOLA tile with the 5 m patch round BASE, lit by the
// scenario's sun (hourly azimuth, 1.5° up; off at night) through the horizon map; the sites (habitat at BASE, the pads
// with their berms, solar towers at POWER, markers elsewhere) with labels; the drive routes; rovers on their routes
// with their state as a coloured ring; cargo pallets stacking at each site from the hourly waiting counts; landers
// descending along the B-33 trajectory the package names, with engine glow, the dust sheet and the plume keep-out
// ring; Earth at its hourly elevation and bearing, cut off by the terrain horizon. Vehicles and pallets are drawn at
// true scale or as constant-size icons (at true scale a 2.6 m rover is a dot from 5 km). Rovers that work at night
// show headlight cones in the dark; vehicle labels appear only within 2.5 km of the camera (or for the followed one).
// A second package of the same seed can ride along as ghosts (compare view): its rovers as outlined boxes.
// Routes (F-36d): each leg once as a faint line (its night variant), and only the legs in use now drawn bright in the
// driving rover's state colour, fading back over about two seconds. Rover icons carry a marker pin and a 2 h trail.
// Motion at slow speeds (F-50): each drive eases in and out over 2 simulated minutes, the heading follows the road
// 12 m behind and ahead and turns at most 150° per second on screen, and the wheels roll with the distance driven.
import * as THREE from 'three';
import { createStage } from '../stage/index.js';
import { createLunarTerrain } from '../stage/terrain.js';
import { createLandingDust } from '../stage/effects/dust.js';
import { createGlow, nozzleExit } from '../stage/effects/glow.js';
import { dirFromAzEl } from '../stage/lighting.js';
import { TIERS } from '../stage/tier.js';
import { loadCatalog } from '../catalog.js';
import { buildVehicle, createMaterials } from '../models/index.js';
import { episodeView } from '../lander/trajectories.js';
import { reducedMotion } from '../ui/dom.js';

const BASE = import.meta.env.BASE_URL;
export { STATE_STYLE } from './states.js';
import { STATE_STYLE } from './states.js';
import { OWNER_COLOURS, EXTRA_COLOURS } from './colours.js';
const SITE_MODEL = { BASE: 'habitat', PAD_A: 'pad', PAD_B: 'pad', POWER: 'solar_tower' };

export async function createWorldScene({ canvas, labelsHost, tier, fetchFn = fetch, onStatus = () => {} }) {
  const [stage, catalog] = await Promise.all([createStage({ canvas, labelsHost, preset: 'onsite', tier, onStatus }), loadCatalog(undefined, { fetchFn })]);
  const terrain = await createLunarTerrain({ base: BASE + 'terrain/hero/', renderer: stage.renderer, site: 'BASE', tier, farStride: tier >= 2 ? 2 : 4 });
  await stage.setPreset('onsite', { sun: { az: 135, el: 1.5 }, ground: false });
  stage.setToneMapping('neutral', 2);
  const scene = stage.scene, lighting = stage.lighting, mats = createMaterials(catalog.doc.materials);
  scene.add(terrain.group); terrain.setCraterVariety?.(1);   // F-57: varied crater depths and shapes, as the rover lab (the stamped set read as blotches up close)
  const shade = root => root.traverse(o => { if (o.isMesh && o.material?.isMeshStandardMaterial) terrain.shadeWithHorizon(o.material); });
  const at = (x, y, lift = 0) => { const [X, , Z] = terrain.toScene(x, y, 0); return new THREE.Vector3(X, terrain.surfaceAt(X, Z) + lift, Z); };
  const camera = stage.camera, tmp = new THREE.Vector3();
  // world units per screen pixel at a point, for constant-size icons
  const pxScale = p => { const d = camera.position.distanceTo(p), hgt = 2 * d * Math.tan(camera.fov * Math.PI / 360); return hgt / Math.max(1, stage.size[1]); };

  let pkg = null, sitesG = null, routesL = null, vehicles = [], pallets = new Map(), rings = [], landers = [], traj = null, iconMode = true, followId = null;
  let isNight = false, pkgB = null, ghosts = [], legs = new Map(), legOf = [], activeL = null, lastReal = 0;
  // story views (F-40): legs without an Earth link drawn red, vehicle labels off, highlight rings round named sites
  let noLink = false, vehLabels = true, hiRings = [], noLinkSites = [], noLinkL = null;
  // a leg's key: both directions together, pads without their standoff ("PAD_A@1" in routes, "PAD_A" in comms waits and sites)
  const legKey = leg => leg.split('->').map(n => n.split('@')[0]).sort().join('~');
  const noLinkMat = new THREE.LineBasicMaterial({ color: '#EE6677', transparent: true, opacity: 0.9, depthWrite: false, toneMapped: false });
  const hiMat = new THREE.MeshBasicMaterial({ color: '#f0a54a', transparent: true, opacity: 0.85, side: THREE.DoubleSide, depthWrite: false, toneMapped: false });
  const pinGeo = new THREE.CylinderGeometry(0.06, 0.06, 1, 6).translate(0, 0.5, 0), headGeo = new THREE.SphereGeometry(0.42, 16, 10), TRAIL = 100;
  const MOTION = { ease: 2 / 60, turnM: 12 }, YAW_RATE = 150 * Math.PI / 180;   // F-50: eased drives, smoothed heading, yaw rate per real second
  let trailsOn = true, colourBy = null;   // F-52: 'owner' colours rings, pins and trails by the rover's owner (stories)
  const ownerColour = o => OWNER_COLOURS[o] || EXTRA_COLOURS[Object.keys(OWNER_COLOURS).length % EXTRA_COLOURS.length];
  // headlight cone: apex at the rover's nose, 30 m forward, additive (no lighting cost)
  const coneGeo = new THREE.ConeGeometry(9, 30, 24, 1, true).rotateX(-Math.PI / 2);
  const coneMat = new THREE.MeshBasicMaterial({ color: '#fff1d0', transparent: true, opacity: 0.09, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide, toneMapped: false });
  const ghostGeo = new THREE.BoxGeometry(1, 1, 1), ghostMat = new THREE.MeshBasicMaterial({ color: '#d36ba6', wireframe: true, toneMapped: false });
  const dyn = new THREE.Group(); dyn.name = 'world-dynamic'; scene.add(dyn);

  function clear() {
    stage.labels.clear();
    for (const o of [...dyn.children]) { dyn.remove(o); o.traverse(m => { m.geometry?.dispose(); }); }
    for (const l of landers) { l.dust?.dispose(); l.glow?.dispose(); }
    vehicles = []; pallets = new Map(); rings = []; landers = []; ghosts = []; pkgB = null; noLinkL = null;
  }

  // ---------- one package ----------
  function setPackage(p, trajectories) {
    clear(); pkg = p; traj = trajectories;
    const idx = p.index;
    // F-52: seeded stones and boulders round the base and the pads, for detail near the camera (representative: LOLA
    // cannot resolve them); the pads themselves and the habitat stay clear; fewer on lower tiers
    const rocks = [0, 1200, 2500, 5000][tier] || 2500;
    Object.entries(idx.sites).filter(([name]) => name === 'BASE' || name.startsWith('PAD')).forEach(([, [x, y]], k) => {
      const s = at(x, y); dyn.add(terrain.scatterRocks({ count: rocks, x: s.x, z: s.z, radius: 220, clearM: 40, seed: 11 + k }));
    });
    // sites
    sitesG = new THREE.Group(); dyn.add(sitesG);
    for (const [name, [x, y]] of Object.entries(idx.sites)) {
      const g = new THREE.Group(), pos = at(x, y);
      g.position.copy(pos); sitesG.add(g);
      const model = SITE_MODEL[name];
      if (model) {
        const v = buildVehicle(catalog, mats, model, { lod: 'simple' }); shade(v.root);
        if (model === 'solar_tower') for (const [dx, dz] of [[-12, 0], [0, 10], [12, 0]]) { const c = v.root.clone(); c.position.set(dx, terrain.surfaceAt(pos.x + dx, pos.z + dz) - pos.y, dz); g.add(c); }
        else g.add(v.root);
      } else {
        const m = new THREE.Mesh(new THREE.CylinderGeometry(4, 4, 0.4, 32), new THREE.MeshStandardMaterial({ color: '#c9ced6', roughness: 0.8 }));
        m.position.y = 0.2; shade(m); g.add(m);
      }
      g.userData = { site: name };
      stage.labels.add({ id: 'site-' + name, text: name.replace('_', ' '), object: g, anchor: new THREE.Vector3(0, 6, 0) });
    }
    // drive routes (lifted 1.5 m so they read over the terrain)
    // one line per leg, A->B and B->A together, the night variant when the package has it (the most cautious route)
    legs = new Map();
    p.routes.forEach((r, i) => {
      const key = legKey(r.leg), have = legs.get(key);
      if (!have || (r.lighting === 'night' && have.lighting !== 'night')) legs.set(key, { route: i, lighting: r.lighting, b: 0 });
    });
    legOf = p.routes.map(r => legKey(r.leg));
    const pts = [];
    for (const [key, L] of legs) {
      const r = p.routes[L.route]; L.from = pts.length / 3;
      for (let i = 0; i + 1 < r.n; i++) { const a = at(r.block[4 * i], r.block[4 * i + 1], 1.5), b = at(r.block[4 * i + 4], r.block[4 * i + 5], 1.5); pts.push(a.x, a.y, a.z, b.x, b.y, b.z); }
      L.to = pts.length / 3;
    }
    const rg = new THREE.BufferGeometry(); rg.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
    routesL = new THREE.LineSegments(rg, new THREE.LineBasicMaterial({ color: '#4d7f93', transparent: true, opacity: 0.32 })); routesL.userData.noAO = true; dyn.add(routesL);
    // the active overlay: the same vertices, coloured per leg by brightness x state colour, added on top
    const ag = new THREE.BufferGeometry(); ag.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3)); ag.setAttribute('color', new THREE.Float32BufferAttribute(new Float32Array(pts.length), 3));
    activeL = new THREE.LineSegments(ag, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
    activeL.userData.noAO = true; activeL.renderOrder = 5; dyn.add(activeL);
    // vehicles: simplified kit model + a state ring underneath
    for (const v of idx.vehicles) {
      const model = buildVehicle(catalog, mats, v.cls, { lod: 'simple' }), g = new THREE.Group(), L = Math.max(model.size.x, model.size.z);
      shade(model.root); g.add(model.root);
      const ring = new THREE.Mesh(new THREE.RingGeometry(L * 0.75, L * 0.95, 40).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: '#ffffff', toneMapped: false, transparent: true, opacity: 0.9, side: THREE.DoubleSide }));
      ring.position.y = 0.15; ring.userData.noAO = true; g.add(ring);
      const cone = new THREE.Mesh(coneGeo, coneMat); cone.position.set(0, model.size.y * 0.45, model.size.z / 2 + 15); cone.userData.base = Math.max(0.6, L / 4); cone.visible = false; cone.userData.noAO = true;
      if (v.night_ops) g.add(cone);
      // marker for far views: a pin with a head in the state colour (scaled with the icon), and a trail of the last 3 h
      const pinMat = new THREE.MeshBasicMaterial({ color: '#ffffff', toneMapped: false });
      const pin = new THREE.Mesh(pinGeo, pinMat), head = new THREE.Mesh(headGeo, pinMat);
      pin.scale.set(L * 0.5, L * 2.2, L * 0.5); head.scale.setScalar(L * 0.9); head.position.y = L * 2.2; pin.userData.noAO = head.userData.noAO = true; g.add(pin, head);
      const tg = new THREE.BufferGeometry(); tg.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(TRAIL * 3), 3)); tg.setAttribute('color', new THREE.Float32BufferAttribute(new Float32Array(TRAIL * 3), 3)); tg.setDrawRange(0, 0);
      const trail = new THREE.Line(tg, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
      trail.userData.noAO = true; trail.frustumCulled = false; dyn.add(trail);
      dyn.add(g);
      // F-50: the wheel groups (tyre and hub about the axle) and their radius, rolled by the distance driven
      const wheels = [], wd = model.entry?.dims?.wheel_d_m?.value || 1;
      model.root.traverse(o => { if (o.userData.group === 'wheels') for (const c of o.children) if (c.isGroup) wheels.push(c); });
      vehicles.push({ ...v, group: g, ring, L, model, cone, pin, head, pinMat, trail, hist: [], lastHistT: -1, wheels, wheelR: wd / 2, yaw: null, lastT: null, lastXY: null });
      stage.labels.add({ id: 'veh-' + v.id, text: `${v.cls} ${v.id}`, object: g, anchor: new THREE.Vector3(0, model.size.y + 1, 0) });
    }
    // cargo pallets per site (instanced, up to 48 shown; the text mirror has the exact count)
    const e = catalog.entry('cargo_pallet'), PL = e.dims.length_m.value, PW = e.dims.width_m.value, PH = e.dims.height_m.value;
    const pmat = terrain.shadeWithHorizon(new THREE.MeshStandardMaterial({ color: '#e9ecf0', roughness: 0.6, name: 'cargo pallet' }));
    for (const [name, [x, y]] of Object.entries(idx.sites)) {
      const im = new THREE.InstancedMesh(new THREE.BoxGeometry(PW, PH, PL), pmat, 48), g = new THREE.Group();
      const M = new THREE.Matrix4();
      for (let i = 0; i < 48; i++) { const layer = Math.floor(i / 16), k = i % 16; M.makeTranslation((k % 4) * (PW + 0.3), PH / 2 + layer * PH, Math.floor(k / 4) * (PL + 0.3)); im.setMatrixAt(i, M); }
      im.count = 0; im.castShadow = true; im.receiveShadow = true; g.add(im);
      const off = SITE_MODEL[name] === 'pad' ? 30 : 12, pos = at(x + off, y - off * 0.5); g.position.copy(pos);
      dyn.add(g); pallets.set(name, { g, im });
    }
    // landers: one model per landing, shown from its descent to the next landing at the same pad
    for (const L of idx.landings) {
      const v = buildVehicle(catalog, mats, L.cls), holder = new THREE.Group(); shade(v.root); holder.add(v.root); holder.visible = false; dyn.add(holder);
      const pilot = traj?.pilots.find(p => p.cls === L.trajectory?.cls && p.pilot === L.trajectory?.pilot);
      // the episode the package names (B-47: good landings map to successful episodes, failed ones to failures)
      const ep = pilot?.episodes.find(q => q.pick === L.trajectory.pick && q.seed === L.trajectory.seed) || pilot?.episodes[0];
      const view = ep ? episodeView(ep) : null, [px, py] = idx.sites[L.pad];
      landers.push({ ...L, holder, vehicle: v, view, padPos: at(px, py), dur: view ? view.tEnd / 3600 : 0, glow: null, dust: null, nozzle: nozzleExit(v), box: v.box.clone() });
    }
    for (const [pad] of idx.keepout_windows.map(w => [w[2]]).filter((v, i, a) => a.findIndex(q => q[0] === v[0]) === i)) {
      const [x, y] = idx.sites[pad], c = at(x, y), pts2 = [];
      for (let i = 0; i <= 128; i++) { const a = i / 128 * 2 * Math.PI; pts2.push(new THREE.Vector3(Math.cos(a), 0, Math.sin(a))); }
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts2), new THREE.LineDashedMaterial({ color: '#CCBB44', dashSize: 0.02, gapSize: 0.015 }));
      line.computeLineDistances(); line.visible = false; line.userData = { noAO: true, pad, centre: c }; dyn.add(line); rings.push(line);
    }
    lighting.fit(new THREE.Box3().setFromCenterAndSize(at(idx.sites.BASE[0], idx.sites.BASE[1]), new THREE.Vector3(40, 15, 40)), { groundY: null });
    stage.invalidate();
  }

  // drape a keep-out ring of radius R (m) over the terrain round its pad
  function drape(line, R) {
    if (line.userData.R === R) return;
    const c = line.userData.centre, p = line.geometry.attributes.position;
    for (let i = 0; i < p.count; i++) { const a = i / (p.count - 1) * 2 * Math.PI, x = c.x + R * Math.cos(a), z = c.z + R * Math.sin(a); p.setXYZ(i, x, terrain.surfaceAt(x, z) + 3, z); }
    p.needsUpdate = true; line.geometry.computeBoundingSphere(); line.computeLineDistances(); line.material.dashSize = R * 0.03; line.material.gapSize = R * 0.02; line.userData.R = R;
  }

  // ---------- one moment ----------
  let lastSun = null, lastNight = null, lastHzCam = new THREE.Vector3(Infinity, 0, 0), active = [];
  let lastMotion = 0;
  function setTime(t, ch, chB = null) {
    if (!pkg || !ch) return;
    const nowM = performance.now(), dtReal = lastMotion ? Math.min(0.25, (nowM - lastMotion) / 1000) : 0; lastMotion = nowM;
    const idx = pkg.index, hr = pkg.hourly(ch, t);
    // sun and night
    const night = hr.night > 0.5; isNight = night;
    if (lastSun === null || Math.abs(hr.sun_az_deg - lastSun) > 0.2 || night !== lastNight) {
      lighting.setSun({ az: hr.sun_az_deg, el: 1.5 }); terrain.setSun(hr.sun_az_deg, 1.5);
      if (night !== lastNight) { lighting.setNight(night); terrain.setNight(night); }
      lastSun = hr.sun_az_deg; lastNight = night;
    }
    lighting.sky?.setEarth({ az: (hr.earth_bearing_deg + 360) % 360, el: hr.earth_el_deg, radiusDeg: hr.earth_radius_deg });
    if (camera.position.distanceTo(lastHzCam) > 200) { lastHzCam.copy(camera.position); lighting.sky?.setHorizon(terrain.profileAt(camera.position.x, camera.position.z, Math.max(2, camera.position.y - terrain.surfaceAt(camera.position.x, camera.position.z)))); }
    // rovers
    for (const v of vehicles) {
      const p = pkg.position(ch, v.id, t, MOTION);
      if (!p) { v.group.visible = false; v.yaw = null; continue; }
      v.group.visible = true; v.state = p.state; v.load = p.load; v.pos = p;
      const s = at(p.x, p.y); v.group.position.copy(s);
      // a jump (seek, skip, more than a quarter hour in one frame, or backwards) snaps the heading and leaves the wheels
      const jump = v.lastT === null || t < v.lastT || t - v.lastT > 0.25, target = -p.heading * Math.PI / 180 + Math.PI;
      if (jump || v.yaw === null || t === v.lastT) v.yaw = target;   // no time passed (a redraw while paused): the true heading
      else { const d = Math.atan2(Math.sin(target - v.yaw), Math.cos(target - v.yaw)), m = YAW_RATE * dtReal; v.yaw += Math.max(-m, Math.min(m, d)); }
      v.group.rotation.y = v.yaw;
      if (!jump && v.lastXY && v.wheels.length) {
        const dx = p.x - v.lastXY[0], dy = p.y - v.lastXY[1], h = p.heading * Math.PI / 180, ds = dx * Math.sin(h) + dy * Math.cos(h);
        if (ds) for (const w of v.wheels) w.rotation.x += ds / v.wheelR;
      }
      v.lastT = t; v.lastXY = [p.x, p.y];
      const col = colourBy === 'owner' ? ownerColour(v.owner) : (STATE_STYLE[p.state] || STATE_STYLE.idle)[0];
      v.ring.material.color.set(col);
      v.pinMat.color.set(col); iconFor(v);
      // trail: a point every 0.02 h of simulated time, the last 2 h, fading towards its tail; cleared after a jump
      if (v.lastHistT < 0 || t < v.lastHistT || t - v.lastHistT > 2) v.hist = [];
      if (v.lastHistT < 0 || t - v.lastHistT >= 0.02 || t < v.lastHistT) { v.hist.push(s.clone().setY(s.y + 2)); if (v.hist.length > TRAIL) v.hist.shift(); v.lastHistT = t; }
      { const pa = v.trail.geometry.attributes.position, ca = v.trail.geometry.attributes.color, c3 = new THREE.Color(col), n = v.hist.length;
        for (let i = 0; i < n; i++) { const q = v.hist[i], k = (i + 1) / n * 0.9; pa.setXYZ(i, q.x, q.y, q.z); ca.setXYZ(i, c3.r * k, c3.g * k, c3.b * k); }
        pa.needsUpdate = ca.needsUpdate = true; v.trail.geometry.setDrawRange(0, n); v.trail.visible = trailsOn && n > 1; }
      if (p.driving && p.route >= 0) { const L2 = legs.get(legOf[p.route]); if (L2) { L2.b = 1; L2.col = col; } }
      v.cone.visible = night && v.night_ops && p.state !== 'parked_night';
      stage.labels.setHidden('veh-' + v.id, !vehLabels || (v.id !== followId && camera.position.distanceTo(s) > 2500));
    }
    // legs a rover is waiting to start for want of an Earth link (the package's comms_waits), held red while it waits
    if (noLink && pkg.index.comms_waits) for (const w of pkg.index.comms_waits) if (t >= w[1] && t < w[2]) { const L3 = legs.get(legKey(w[3])); if (L3) { L3.b = 1; L3.col = '#EE6677'; } }
    if (noLinkSites.length) for (const [k, L4] of legs) if (k.split('~').some(n => noLinkSites.includes(n))) { L4.b = 1; L4.col = '#EE6677'; }   // sites a story says never see Earth
    // active legs: bright while a rover drives them, fading back over ~2 s of real time
    { const now = performance.now(), dt = lastReal ? Math.min(0.25, (now - lastReal) / 1000) : 0; lastReal = now;
      const ca = activeL?.geometry.attributes.color, c3 = new THREE.Color(); let any = false;
      if (ca) for (const L of legs.values()) {
        if (L.b <= 0 && !L.drawn) continue;
        c3.set(L.col || '#6fcde9').multiplyScalar(L.b * 1.6);
        for (let i = L.from; i < L.to; i++) ca.setXYZ(i, c3.r, c3.g, c3.b);
        L.drawn = L.b > 0; if (L.b > 0) any = true;
        L.b = Math.max(0, L.b - dt / 2);
      }
      if (ca) { ca.needsUpdate = true; activeL.visible = any; }
      if (any) stage.invalidate(); }
    // the compared package's rovers, as outlined boxes the size of the vehicle (or icons)
    if (pkgB && chB) for (const gh of ghosts) {
      const p = pkgB.position(chB, gh.id, t, MOTION);
      if (!p) { gh.mesh.visible = false; continue; }
      const s2 = at(p.x, p.y, gh.h / 2); gh.mesh.visible = true; gh.mesh.position.copy(s2); gh.mesh.rotation.y = -p.heading * Math.PI / 180;
      const k = iconMode ? Math.max(1, 22 * pxScale(s2) / gh.L) : 1; gh.mesh.scale.set(gh.w * k, gh.h * k, gh.L * k);
    }
    // pallets waiting at each site
    for (const [name, P] of pallets) {
      const n = Math.min(48, Math.round(hr.waiting[name]?.items || 0));
      if (P.im.count !== n) { P.im.count = n; P.im.instanceMatrix.needsUpdate = true; }
      P.g.visible = n > 0;
    }
    iconsForCamera();
    // keep-out rings
    for (const r of rings) r.visible = false;
    for (const [t0, t1, pad, Rkm] of idx.keepout_windows) if (t >= t0 && t <= t1) { const r = rings.find(q => q.userData.pad === pad); if (r) { drape(r, Rkm * 1000); r.visible = true; } }
    // landers: descending, then on the pad until the next landing there
    active = [];
    for (const L of landers) {
      const next = landers.find(q => q.pad === L.pad && q.t_h > L.t_h), start = L.t_h - L.dur;
      const show = t >= start && (!next || t < next.t_h - next.dur);
      L.holder.visible = show;
      if (!show || !L.view) { if (L.dust) { dyn.remove(L.dust.group); L.dust.dispose(); L.dust = null; L.glow?.dispose(); L.glow = null; } continue; }
      const te = Math.min(L.view.tEnd, (t - start) * 3600), [x, y, z] = L.view.pos(te), base = L.padPos;
      const gx = base.x + x, gz = base.z - y;
      L.holder.position.set(gx, terrain.surfaceAt(gx, gz) + z, gz); L.holder.quaternion.fromArray(L.view.quatScene(te));
      // icons: 26 px once down; 16 px while descending, so a lander is seen from the pad shot (its dust stays true scale)
      L.holder.scale.setScalar(iconMode ? Math.max(1, (te >= L.view.tEnd ? 26 : 16) * pxScale(L.holder.position) / L.vehicle.size.y) : 1);
      const descending = te < L.view.tEnd + 10;
      if (descending && !L.dust && t < L.t_h + 0.01) {
        const tl = { t: [], h: [], thrust: [], gx: [], gy: [], gz: [] }, tMax = (traj.plume[L.cls]?.t_max_n || 5000) * L.view.ep.episode.thrust_scale;
        for (let s = 0; ; s = Math.min(L.view.tEnd, s + 0.1)) {
          const [qx, qy, qz] = L.view.pos(s), X = base.x + qx, Z = base.z - qy;
          tl.t.push(s); tl.h.push(qz + L.nozzle.y); tl.thrust.push(L.view.throttle(s) * tMax); tl.gx.push(X); tl.gz.push(Z); tl.gy.push(terrain.surfaceAt(X, Z));
          if (s >= L.view.tEnd) break;
        }
        L.dust = createLandingDust({ timeline: tl, cutoff: L.view.tEnd, keepoutM: 1000, seed: Math.round(L.t_h), n: TIERS[3].particles, thrustN: traj.plume[L.cls]?.t_max_n || 5000 });
        L.dust.setGround(terrain.surfaceAt); L.dust.setCount(TIERS[stage.tier].particles); L.dust.setSun(dirFromAzEl(hr.sun_az_deg, 1.5), night ? 0 : 1); dyn.add(L.dust.group);
        L.glow = createGlow(L.vehicle, L.vehicle.entry.plume_class);
      }
      if (L.dust) { L.dust.setTime(te); L.glow?.setThrottle(L.view.throttle(te)); if (!descending || t > L.t_h + 0.01) { dyn.remove(L.dust.group); L.dust.dispose(); L.dust = null; L.glow?.dispose(); L.glow = null; } }
      if (t >= start && t < L.t_h) active.push(L);
      if (L.dust) { const b = L.box.clone().applyMatrix4(L.holder.matrixWorld); lighting.fit(b, { groundY: z < 60 ? terrain.surfaceAt(gx, gz) : null }); }
    }
    stage.invalidate();
  }

  // ---------- camera shots from the package's sites ----------
  function shots() {
    const S = pkg.index.sites, P = n => at(S[n][0], S[n][1]), all = Object.keys(S).map(P), box = new THREE.Box3().setFromPoints(all), c = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3());
    const span = Math.max(size.x, size.z), base = P('BASE'), pads = P('PAD_A').clone().add(P('PAD_B')).multiplyScalar(0.5), d = stage.director;
    const look = (tgt, dist, el, az) => { const a = az * Math.PI / 180, e = el * Math.PI / 180; return { position: [tgt.x + Math.sin(a) * Math.cos(e) * dist, tgt.y + Math.sin(e) * dist, tgt.z + Math.cos(a) * Math.cos(e) * dist], target: tgt.toArray() }; };
    d.shot('overview', look(c, Math.max(2600, span * 1.2), 38, 200))
      .shot('pads', look(pads, Math.max(2200, P('PAD_A').distanceTo(P('PAD_B')) * 1.3 + 1000), 34, 210))
      .shot('legs', look(c, Math.max(2000, span * 0.95), 22, 160))
      .shot('base', look(base, 700, 24, 215))
      .shot('night', look(base, 1100, 30, 30));
  }

  // where Follow points: cargo (the most loaded rover, else the site with most waiting), rovers (a driving rover),
  // landers (the descending lander, else the next landing's pad), night (the base)
  function followTarget(kind, t, hr) {
    const idx = pkg.index, site = n => at(idx.sites[n][0], idx.sites[n][1]);
    let v = null;
    if (kind === 'cargo') {
      v = vehicles.filter(q => q.group.visible && q.load > 0).sort((a, b) => b.load - a.load)[0];
      if (!v) { const w = Object.entries(hr.waiting).sort((a, b) => b[1].kg - a[1].kg)[0]; followId = null; return w && w[1].kg > 0 ? { pos: site(w[0]), dist: 500, what: `cargo waiting at ${w[0].replace('_', ' ')}` } : { pos: site('BASE'), dist: 700, what: 'the base (no cargo moving)' }; }
    } else if (kind === 'rovers') {
      v = vehicles.find(q => q.id === followId && q.group.visible && q.state === 'driving') || vehicles.find(q => q.group.visible && q.state === 'driving') || vehicles.find(q => q.group.visible);
    } else if (kind === 'landers') {
      followId = null;
      const a = active[0]; if (a) return { pos: a.holder.position.clone(), dist: 260, what: `the ${a.cls} lander coming down` };
      const n = idx.landings.find(L => L.t_h > t); return n ? { pos: site(n.pad), dist: 900, what: `${n.pad.replace('_', ' ')}, where the next lander comes down` } : { pos: site('BASE'), dist: 900, what: 'the base (no landings left this year)' };
    } else if (kind === 'night') { followId = null; return { pos: site('BASE'), dist: 900, what: 'the base' }; }
    if (!v) { followId = null; return null; }
    followId = v.id;
    return { pos: v.group.position.clone(), dist: Math.max(120, v.L * 40), what: `${v.cls} ${v.id}${v.load > 0 ? `, carrying ${Math.round(v.load)} kg` : ''}` };
  }
  // icon sizes and far-view markers depend on the camera, so they are refreshed when it moves as well as each moment
  function iconFor(v) {
    const s = v.group.position;
    v.group.scale.setScalar(iconMode ? Math.max(1, 34 * pxScale(s) / v.L) : 1);
    v.pin.visible = v.head.visible = iconMode && (isNight || camera.position.distanceTo(s) > 400);   // markers for far views, and in the dark
    v.cone.scale.setScalar(v.cone.userData.base / v.group.scale.x);   // the headlight cone lights the ground at true size
  }
  function iconsForCamera() {
    for (const v of vehicles) if (v.group.visible) iconFor(v);
    for (const P of pallets.values()) if (P.g.visible) P.g.scale.setScalar(iconMode ? Math.max(1, 9 * pxScale(P.g.position) / 1.5) : 1);
  }
  stage.director.controls.addEventListener('update', () => { if (pkg) iconsForCamera(); });
  // frame a point from the sun's side (lit faces towards the camera), dist m away, el degrees up, turned by dAz degrees
  function frameAt(pos, dist, el = 28, dAz = 35, instant = false) {
    const az = (lastSun ?? 135) + dAz, d = dirFromAzEl(az, el);
    return stage.director.controls.setLookAt(pos.x + d.x * dist, pos.y + d.y * dist, pos.z + d.z * dist, pos.x, pos.y, pos.z, !(instant || reducedMotion()));
  }
  const activeLegs = () => [...legs.entries()].filter(([, L]) => L.b > 0.95).map(([k]) => k.replace('~', ' and '));
  // F-51 part 4: the rover or lander under a screen point, for "look inside": {cls, what} or null
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
  function pickAt(cx, cy) {
    const r = canvas.getBoundingClientRect(); ndc.set((cx - r.left) / r.width * 2 - 1, -((cy - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const objs = [...vehicles.filter(v => v.group.visible).map(v => v.group), ...landers.filter(L => L.holder.visible).map(L => L.holder)];
    const hit = ray.intersectObjects(objs, true).find(x => x.object.isMesh); if (!hit) return null;
    let o = hit.object; while (o && !objs.includes(o)) o = o.parent;
    const v = vehicles.find(q => q.group === o); if (v) return { cls: v.cls, what: `${v.cls} ${v.id}` };
    const L = landers.find(q => q.holder === o); return L ? { cls: L.cls, what: `the ${L.cls}-class lander` } : null;
  }
  function setCompare(p2) {
    for (const g of ghosts) dyn.remove(g.mesh);
    ghosts = []; pkgB = p2;
    if (!p2) { stage.invalidate(); return; }
    for (const v of p2.index.vehicles) {
      const m = buildVehicle(catalog, mats, v.cls, { lod: 'icon' }), size = m.size, mesh = new THREE.Mesh(ghostGeo, ghostMat);
      mesh.userData.noAO = true; mesh.visible = false; dyn.add(mesh);
      ghosts.push({ id: v.id, mesh, L: Math.max(size.z, 1), w: size.x, h: size.y });
    }
    stage.invalidate();
  }

  return {
    stage, terrain, catalog, STATE_STYLE,
    setPackage, setTime, shots, followTarget, setCompare, frameAt, activeLegs, pickAt,
    // story views: red legs while rovers wait for Earth; vehicle labels on or off; rings round the named sites
    // extra: routes ({n, block}) of legs this package never drives (no rover starts them without Earth), drawn red as well
    setNoLink(v, sites = [], extra = []) {
      noLink = !!v; noLinkSites = sites;
      if (noLinkL) { dyn.remove(noLinkL); noLinkL.geometry.dispose(); noLinkL = null; }
      if (extra.length) {
        const pts = [];
        for (const r of extra) for (let i = 0; i + 1 < r.n; i++) { const a = at(r.block[4 * i], r.block[4 * i + 1], 1.5), b = at(r.block[4 * i + 4], r.block[4 * i + 5], 1.5); pts.push(a.x, a.y, a.z, b.x, b.y, b.z); }
        const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
        noLinkL = new THREE.LineSegments(g, noLinkMat); noLinkL.userData.noAO = true; noLinkL.renderOrder = 5; dyn.add(noLinkL);
      }
      stage.invalidate();
    },
    hasLegs: name => [...legs.keys()].some(k => k.split('~').includes(name)), legKey,
    setVehicleLabels(v) { vehLabels = !!v; stage.invalidate(); },
    setHighlight(names = []) {
      for (const r of hiRings) { dyn.remove(r); r.geometry.dispose(); }
      hiRings = [];
      for (const n of names) {
        if (!pkg?.index.sites[n]) continue;
        const r = new THREE.Mesh(new THREE.RingGeometry(80, 92, 72).rotateX(-Math.PI / 2), hiMat);
        r.position.copy(at(pkg.index.sites[n][0], pkg.index.sites[n][1])).y += 3; r.userData.noAO = true; r.renderOrder = 6;
        dyn.add(r); hiRings.push(r);
      }
      stage.invalidate();
    },
    // the start of the next recorded descent after t (playback stops there so no landing is stepped over)
    nextLandingStart(t) { let m = Infinity; for (const L of landers) { const st = L.t_h - L.dur; if (L.view && st > t + 1e-6 && st < m) m = st; } return m; },
    sitePos: name => at(pkg.index.sites[name][0], pkg.index.sites[name][1]),
    clearFollow() { followId = null; },
    go: (name, instant = false) => stage.director.go(name, { instant: instant || reducedMotion() }),
    setIcons(v) { iconMode = v; if (pkg) iconsForCamera(); stage.invalidate(); },
    get vehicles() { return vehicles; }, get activeLandings() { return active; },
    setRoutes(v) { if (routesL) routesL.visible = v; },
    setColourBy(v) { colourBy = v === 'owner' ? 'owner' : null; stage.invalidate(); },
    owners: () => [...new Set(vehicles.map(v => v.owner))].map(o => [o, ownerColour(o)]),
    setTrails(v) { trailsOn = !!v; for (const q of vehicles) q.trail.visible = trailsOn && q.hist.length > 1; stage.invalidate(); },
    setTier(t) { for (const L of landers) L.dust?.setCount(TIERS[t].particles); },
    dispose() { clear(); stage.dispose(); terrain.dispose(); },
  };
}
