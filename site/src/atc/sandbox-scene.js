// The encounter sandbox's 3D view (F-54), a lazy chunk started by the visitor: the shared stage (exhibit preset), the
// encounter's roads as ribbons, each vehicle a 4 x 2.3 m box in its owner colour, a ring under it while the safety
// program corrects its move, crew on foot with their 50 m slow zone (R6), a hidden-crew rock while it hides someone,
// the landing zone (grey, amber while closing, red while closed) and, with the safety program off, a marker where the
// first contact happened. Simulation (x, y) maps to three (x, 0, -y); the camera follows the vehicles.
import * as THREE from 'three';
import { createStage, detectTier } from '../stage/index.js';
import { LANE_W, VEH_L, VEH_W } from './encounter.js';

const COLOURS = [0x4477AA, 0xEE6677, 0x228833, 0xCCBB44, 0x66CCEE, 0xAA3377];   // Tol bright, as the readout's swatches
const T_LEAD_S = 1800;   // encounter.py: closure notice before the window opens
const P3 = (x, y, h = 0) => new THREE.Vector3(x, h, -y);

function ribbon(pts, w, y) {
  const pos = [], idx = [];
  pts.forEach((p, i) => {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
    let dx = b[0] - a[0], dy = b[1] - a[1]; const l = Math.hypot(dx, dy) || 1; dx /= l; dy /= l;
    pos.push(p[0] - dy * w / 2, y, -(p[1] + dx * w / 2), p[0] + dy * w / 2, y, -(p[1] - dx * w / 2));
    if (i) { const q = 2 * i; idx.push(q - 2, q - 1, q, q - 1, q + 1, q); }
  });
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx); g.computeVertexNormals();
  return g;
}
const flatRing = (r0, r1, mat, seg = 64) => { const m = new THREE.Mesh(new THREE.RingGeometry(r0, r1, seg), mat); m.rotation.x = -Math.PI / 2; return m; };

export async function createSandboxScene({ canvas, labelsHost }) {
  const { tier } = await detectTier();
  const stage = await createStage({ canvas, labelsHost, preset: 'exhibit', tier });
  stage.director.bindKeys(canvas);
  stage.director.limits({ maxPolar: 84, minDistance: 8, maxDistance: 2500 });
  if (new URLSearchParams(location.search).has('bench')) window.__stage = stage;
  let group = null, doc = null, run = null, cars = [], crew = [], rocks = [], zone = null, mark = null;
  const mats = {
    road: new THREE.MeshStandardMaterial({ color: 0x55585e, roughness: 0.95 }),
    halo: new THREE.MeshBasicMaterial({ color: 0xffb000, transparent: true, opacity: 0.85, side: THREE.DoubleSide }),
    crew: new THREE.MeshStandardMaterial({ color: 0xf2f2f2, roughness: 0.6 }),
    slow: new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.25, side: THREE.DoubleSide }),
    rock: new THREE.MeshStandardMaterial({ color: 0x8a8580, roughness: 1 }),
    zone: new THREE.MeshBasicMaterial({ color: 0x888888, transparent: true, opacity: 0.12, side: THREE.DoubleSide, depthWrite: false }),
    edge: new THREE.MeshBasicMaterial({ color: 0x888888, side: THREE.DoubleSide }),
    mark: new THREE.MeshBasicMaterial({ color: 0xff3030, side: THREE.DoubleSide }),
  };

  function clear() {
    if (!group) return;
    stage.labels.clear(); stage.clearSubject();
    group.traverse(o => { if (o.geometry) o.geometry.dispose(); if (o.material && !Object.values(mats).includes(o.material)) o.material.dispose(); });
    group = null; cars = []; crew = []; rocks = []; zone = null; mark = null;
  }

  function load(d, r) {
    clear();
    doc = d; run = r; group = new THREE.Group();
    const sp = d.spec, seen = new Set();
    for (const p of sp.paths) {
      const key = JSON.stringify(p); if (seen.has(key)) continue; seen.add(key);
      group.add(new THREE.Mesh(ribbon(p, LANE_W * 0.96, 0.02), mats.road));
    }
    if (sp.zone) {
      const [cx, cy] = sp.zone.c, R = sp.zone.r;
      const fill = flatRing(0, R, mats.zone.clone(), 96), edge = flatRing(R - 1.5, R, mats.edge.clone(), 96);
      fill.position.copy(P3(cx, cy, 0.01)); edge.position.copy(P3(cx, cy, 0.03));
      group.add(fill, edge); zone = { fill, edge, events: sp.zone.events };
    }
    for (const [x, y, until] of sp.occluders || []) {
      const m = new THREE.Mesh(new THREE.DodecahedronGeometry(3, 0), mats.rock); m.position.copy(P3(x, y, 2)); m.scale.set(1.3, 0.8, 1.2);
      group.add(m); rocks.push({ m, until });
    }
    for (const c of sp.crew || []) {
      const g = new THREE.Group(), body = new THREE.Mesh(new THREE.CapsuleGeometry(0.35, 1.1, 4, 10), mats.crew);
      body.position.y = 0.9; g.add(body, flatRing(49.4, 50, mats.slow, 96));
      g.visible = false; group.add(g); crew.push(g);
    }
    sp.paths.forEach((_, i) => {
      const g = new THREE.Group(), box = new THREE.Mesh(new THREE.BoxGeometry(VEH_L, 1.5, VEH_W), new THREE.MeshStandardMaterial({ color: COLOURS[i % COLOURS.length], roughness: 0.55 }));
      box.position.y = 0.95; box.castShadow = true;
      const halo = flatRing(2.9, 3.5, mats.halo); halo.position.y = 0.05; halo.visible = false;
      g.add(box, halo); group.add(g); cars.push({ g, halo });
      stage.labels.add({ id: `v${i}`, text: `${i + 1}`, object: g, anchor: new THREE.Vector3(0, 2.4, 0) });
    });
    if (r.contactAt !== null) { mark = flatRing(3.5, 5, mats.mark); mark.position.y = 0.06; mark.visible = false; group.add(mark); mark.userData.pos = contactPoint(r); }
    group.traverse(o => { o.userData.noPick = true; });   // nothing to pick; no hover outline
    stage.setSubject(group);
    // light and floor fitted to where the vehicles go in this replay (every frame), not to roads hundreds of metres long
    const f0 = r.frames[0], c = centroid(f0), span = spread(f0, c), box = new THREE.Box3();
    for (let q = 0; q < r.frames.length; q += 10) for (const b of r.frames[q].bodies) box.expandByPoint(P3(b.c[0], b.c[1]));
    box.expandByScalar(60); box.min.y = 0; box.max.y = 6;
    stage.lighting.fit(box);
    const D = Math.min(260, Math.max(45, span * 2.2 + 30));
    stage.director.controls.setLookAt(c.x - D * 0.35, D * 0.75, c.z + D * 0.7, c.x, 0, c.z, false);
    show(0);
  }
  function live(f) { return f.bodies.map((b, i) => ({ b, i })).filter(({ i }) => !f.done[i]); }
  function centroid(f) {
    const L = live(f).length ? live(f) : f.bodies.map((b, i) => ({ b, i }));
    const v = L.reduce((a, { b }) => a.add(P3(b.c[0], b.c[1])), new THREE.Vector3()).multiplyScalar(1 / L.length);
    return v;
  }
  function spread(f, c) { return Math.max(10, ...f.bodies.map(b => P3(b.c[0], b.c[1]).distanceTo(c))); }
  function contactPoint(r) {
    const f = r.frames.find(x => x.t >= r.contactAt) || r.frames[r.frames.length - 1];
    let best = null, d = Infinity;
    for (let i = 0; i < f.bodies.length; i++) for (let j = i + 1; j < f.bodies.length; j++) {
      const a = f.bodies[i].c, b = f.bodies[j].c, q = Math.hypot(a[0] - b[0], a[1] - b[1]);
      if (q < d) { d = q; best = P3((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0.06); }
    }
    return best;
  }

  function show(k) {
    if (!run) return;
    const f = run.frames[k];
    f.bodies.forEach((b, i) => {
      const { g, halo } = cars[i];
      g.visible = !f.done[i];
      g.position.copy(P3(b.c[0], b.c[1]));
      g.rotation.y = Math.atan2(b.c[3], b.c[2]);
      const x = f.verdicts?.[i];
      // the ring: amber while the safety program corrects the move (or, switched off, would have); red: stopped dead (a fault)
      halo.visible = f.fault[i] || (!!x && x.modified);
      halo.material = f.fault[i] ? mats.mark : mats.halo;
      stage.labels.setHidden(`v${i}`, f.done[i]);
    });
    crew.forEach((g, c) => { const p = f.crew[c]; g.visible = !!p; if (p) g.position.copy(P3(p[0], p[1])); });   // traces store [null] when there is no crew
    for (const r of rocks) r.m.visible = f.t < r.until;
    if (zone) {
      const closed = zone.events.some(e => e[0] <= f.t && f.t < e[1] && !(e[2] <= f.t));
      const notice = zone.events.some(e => !(e[2] <= f.t) && f.t < e[0] && e[0] - f.t <= T_LEAD_S);
      const col = closed ? 0xd03030 : notice ? 0xe0a000 : 0x888888;
      zone.fill.material.color.setHex(col); zone.edge.material.color.setHex(col);
    }
    if (mark) { mark.visible = f.t >= run.contactAt; if (mark.userData.pos) mark.position.copy(mark.userData.pos); }
    // follow: the target moves with the vehicles; the visitor keeps the angle and distance they chose
    const c = centroid(f);
    stage.director.controls.moveTo(c.x, 0, c.z, false);
    stage.invalidate();
  }

  return { load, show, clear: () => { clear(); run = null; stage.invalidate(); }, stage };
}
