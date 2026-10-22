// Procedural test object for the stage demo (not a real vehicle): a propellant tank with a wall, the liquid oxygen
// inside, a feed line, a combustion chamber with a hot throat, a bell nozzle and three legs. Every part that the
// cutaway cuts is a closed solid (a lathe of a closed profile), so the stencil caps can fill its section.
// Metres; y up; the floor is y = 0. Walls are drawn 6 cm thick so the cut reads at this size.
import * as THREE from 'three';

const V = (x, y) => new THREE.Vector2(x, y);
const SEG = 72;

// closed lathe: the profile runs from the axis back to the axis (or is a loop), so the revolved surface is watertight.
// Outer surfaces are listed bottom to top, which makes three's front faces point out of the solid.
const lathe = pts => new THREE.LatheGeometry(pts, SEG);

function tankProfile(R, H, D, t) {
  const outer = [], inner = [];
  for (let i = 0; i <= 12; i++) { const a = -Math.PI / 2 + (i / 12) * Math.PI / 2; outer.push(V(R * Math.cos(a), -H + D * Math.sin(a))); }
  for (let i = 0; i <= 12; i++) { const a = (i / 12) * Math.PI / 2; outer.push(V(R * Math.cos(a), H + D * Math.sin(a))); }
  const r = R - t, d = D - t;
  for (let i = 12; i >= 0; i--) { const a = (i / 12) * Math.PI / 2; inner.push(V(r * Math.cos(a), H + d * Math.sin(a))); }
  for (let i = 12; i >= 0; i--) { const a = -Math.PI / 2 + (i / 12) * Math.PI / 2; inner.push(V(r * Math.cos(a), -H + d * Math.sin(a))); }
  outer[0].x = 0; outer[outer.length - 1].x = 0; inner[0].x = 0; inner[inner.length - 1].x = 0;
  return outer.concat(inner);
}

function liquidProfile(R, H, D, level) {   // the lower part of the cavity, up to a flat surface at y = level
  const pts = [V(0, -H - D)];
  for (let i = 1; i <= 12; i++) { const a = -Math.PI / 2 + (i / 12) * Math.PI / 2; pts.push(V(R * Math.cos(a), -H + D * Math.sin(a))); }
  pts.push(V(R, level), V(0, level));
  return pts;
}

function bellProfile(rt, re, len, t) {      // a parabolic-ish bell from the throat (top) to the exit (bottom), as a ring solid
  const outer = [], inner = [];
  for (let i = 0; i <= 16; i++) { const s = i / 16, r = rt + (re - rt) * (1 - (1 - s) ** 2.2); outer.push(V(r + t, -len * s)); inner.unshift(V(r, -len * s)); }
  return outer.concat(inner, [outer[0].clone()]).reverse();   // exit -> throat outside, throat -> exit inside
}

export function buildTank() {
  const root = new THREE.Group(); root.name = 'test-object';
  const mat = (o) => new THREE.MeshStandardMaterial(o);
  const R = 1.4, H = 1.2, D = 0.9, T = 0.06, yc = 5.3;

  const tank = new THREE.Mesh(lathe(tankProfile(R, H, D, T)), mat({ color: '#e7eaee', roughness: 0.55, metalness: 0.05 }));
  tank.position.y = yc; tank.userData = { part: 'tank', capColor: '#aeb7c4' };
  const lox = new THREE.Mesh(lathe(liquidProfile(R - T - 0.01, H, D - T - 0.01, 0.35)), mat({ color: '#93c3e6', roughness: 0.25, metalness: 0 }));
  lox.userData = { part: 'lox', capColor: '#7fb3db' };
  tank.add(lox);

  const yT = 2.1;   // throat height
  const chamber = new THREE.Mesh(lathe([V(0, 0), V(0.17, 0), V(0.32, 0.22), V(0.32, 0.5), V(0.24, 0.6), V(0, 0.62)]),
    mat({ color: '#b87333', roughness: 0.35, metalness: 0.85 }));
  chamber.position.y = yT; chamber.userData = { part: 'chamber', capColor: '#d08a4a' };
  const throat = new THREE.Mesh(new THREE.TorusGeometry(0.185, 0.035, 12, SEG), mat({ color: '#1a0f05', emissive: '#ffb054', emissiveIntensity: 14, roughness: 0.6 }));
  throat.rotation.x = Math.PI / 2; throat.userData = { capColor: '#ffb054' };
  chamber.add(throat);

  const nozzle = new THREE.Mesh(lathe(bellProfile(0.16, 0.85, 1.5, 0.03)), mat({ color: '#3b3f45', roughness: 0.4, metalness: 0.85, side: THREE.FrontSide }));
  nozzle.position.y = yT; nozzle.userData = { part: 'nozzle', capColor: '#6b7078' };

  const curve = new THREE.CatmullRomCurve3([new THREE.Vector3(0, yT + 0.6, 0), new THREE.Vector3(0.25, yT + 0.85, 0.1), new THREE.Vector3(0.55, 2.95, 0.15),
    new THREE.Vector3(0.45, yc - H - D + 0.25, 0.05), new THREE.Vector3(0, yc - H - D + 0.02, 0)]);
  const feed = new THREE.Mesh(new THREE.TubeGeometry(curve, 48, 0.07, 16, false), mat({ color: '#a7adb5', roughness: 0.35, metalness: 0.8 }));
  feed.userData = { part: 'feed' };

  const legs = [0, 1, 2].map(k => {
    const a = k * (2 * Math.PI / 3) + Math.PI / 6, top = new THREE.Vector3(R * 0.95 * Math.cos(a), yc - H - 0.1, R * 0.95 * Math.sin(a));
    const foot = new THREE.Vector3(2.6 * Math.cos(a), 0.06, 2.6 * Math.sin(a)), len = top.distanceTo(foot);
    const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, len, 16), mat({ color: '#c4c9d0', roughness: 0.4, metalness: 0.7 }));
    leg.position.copy(top).add(foot).multiplyScalar(0.5);
    leg.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), foot.clone().sub(top).normalize());
    const pad = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.32, 0.08, 24), leg.material);
    pad.position.copy(foot).sub(leg.position).applyQuaternion(leg.quaternion.clone().invert());
    pad.quaternion.copy(leg.quaternion.clone().invert());
    leg.add(pad);
    leg.userData = { part: 'legs' };
    return leg;
  });

  root.add(tank, chamber, nozzle, feed, ...legs);
  root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });

  return {
    root,
    axis: new THREE.Vector3(0, yc, 0),   // the cut's vertical axis: through the tank, chamber and nozzle
    // outer to inner: inner caps are drawn last and overwrite the outer ones where they overlap
    cutTargets: [tank, lox, nozzle, chamber, throat],
    parts: {
      tank: { name: 'Propellant tank', object: tank, anchor: new THREE.Vector3(R, 0.7, 0), note: 'Closed shell; the wall is the cap ring' },
      lox: { name: 'Liquid oxygen', object: lox, anchor: new THREE.Vector3(0.55, -0.9, 0), note: 'Inside the tank: hidden until cut' },
      feed: { name: 'Feed line', object: feed, anchor: curve.getPoint(0.45), note: 'Open tube, not cut' },
      chamber: { name: 'Combustion chamber', object: chamber, anchor: new THREE.Vector3(0.32, 0.38, 0), tone: 'warm', note: 'Hot throat: bloom on tier 2-3' },
      nozzle: { name: 'Bell nozzle', object: nozzle, anchor: new THREE.Vector3(0.6, -0.95, 0), note: 'Ring solid, cut with caps' },
      legs: { name: 'Legs', object: legs[0], anchor: new THREE.Vector3(0, 0.2, 0), note: 'Three closed cylinders' },
    },
    explode: [
      { object: tank, axis: new THREE.Vector3(0, 1, 0), distance: 1.5 },
      { object: feed, axis: new THREE.Vector3(1, 0.2, 0.3).normalize(), distance: 1.3 },
      { object: chamber, axis: new THREE.Vector3(0, -0.1, 1).normalize(), distance: 0.9 },
      { object: nozzle, axis: new THREE.Vector3(0, -0.2, 1).normalize(), distance: 2.0 },
      ...legs.map(l => { const p = l.position.clone(); p.y = 0; return { object: l, axis: p.normalize(), distance: 0.9 }; }),
    ],
  };
}
