// Building blocks for the procedural vehicle kit. Every solid here is closed (watertight), so the stage's cutaway
// can cap it: cylinders keep their end caps, lathes run from the axis back to the axis or close their loop.
// A "part" is a named Group with an explode axis and distance, a label and a representative flag; the builder
// collects parts, cut targets (closed meshes, outer first) and flow paths for the Follow modes.
import * as THREE from 'three';

const Y = new THREE.Vector3(0, 1, 0);
export const V2 = (x, y) => new THREE.Vector2(x, y);
export const V3 = (x, y, z) => new THREE.Vector3(x, y, z);

// lathe of a profile listed bottom to top on the outside (front faces out of the solid)
export const lathe = (pts, seg = 48) => new THREE.LatheGeometry(pts, seg);

// a closed shell (hollow cylinder with domed ends, wall t), profile from the bottom pole round to the inside
export function shellProfile(r, y0, y1, dome0, dome1, t, n = 10) {
  const out = [], inn = [];
  for (let i = 0; i <= n; i++) { const a = -Math.PI / 2 + (i / n) * Math.PI / 2; out.push(V2(r * Math.cos(a), y0 + dome0 * Math.sin(a))); }
  for (let i = 0; i <= n; i++) { const a = (i / n) * Math.PI / 2; out.push(V2(r * Math.cos(a), y1 + dome1 * Math.sin(a))); }
  const ri = r - t;
  for (let i = n; i >= 0; i--) { const a = (i / n) * Math.PI / 2; inn.push(V2(ri * Math.cos(a), y1 + Math.max(0, dome1 - t) * Math.sin(a))); }
  for (let i = n; i >= 0; i--) { const a = -Math.PI / 2 + (i / n) * Math.PI / 2; inn.push(V2(ri * Math.cos(a), y0 + Math.max(0, dome0 - t) * Math.sin(a))); }
  for (const p of [out[0], out[out.length - 1], inn[0], inn[inn.length - 1]]) p.x = 0;
  return out.concat(inn);
}

// a solid capsule-ended tank (no wall), radius r, cylinder from y0 to y1, domes of height d
export function tankProfile(r, y0, y1, d, n = 10) {
  const pts = [];
  for (let i = 0; i <= n; i++) { const a = -Math.PI / 2 + (i / n) * Math.PI / 2; pts.push(V2(r * Math.cos(a), y0 + d * Math.sin(a))); }
  for (let i = 0; i <= n; i++) { const a = (i / n) * Math.PI / 2; pts.push(V2(r * Math.cos(a), y1 + d * Math.sin(a))); }
  pts[0].x = 0; pts[pts.length - 1].x = 0;
  return pts;
}

// a bell nozzle as a ring solid: throat radius rt at y = 0, exit radius re at y = -len, wall t
export function bellProfile(rt, re, len, t, n = 14) {
  const outer = [], inner = [];
  for (let i = 0; i <= n; i++) { const s = i / n, r = rt + (re - rt) * (1 - (1 - s) ** 2.2); outer.push(V2(r + t, -len * s)); inner.unshift(V2(r, -len * s)); }
  return outer.concat(inner, [outer[0].clone()]).reverse();
}

// a closed ring of rectangular section (berm, solar band): inner radius r0, outer r1, from y0 to y1 (a trapezoid if crest given)
export function ringProfile(r0, r1, y0, y1, crest0 = r0, crest1 = r1) {
  return [V2(r0, y0), V2(r1, y0), V2(crest1, y1), V2(crest0, y1), V2(r0, y0)];
}

// a cylinder between two points (closed), for struts and legs
export function strut(a, b, r, seg = 10) {
  const len = a.distanceTo(b), g = new THREE.CylinderGeometry(r, r, len, seg);
  const q = new THREE.Quaternion().setFromUnitVectors(Y, b.clone().sub(a).normalize());
  g.applyQuaternion(q); const m = a.clone().add(b).multiplyScalar(0.5); g.translate(m.x, m.y, m.z);
  return g;
}

export function builder(mats, { lod = 'full' } = {}) {
  const root = new THREE.Group(), parts = [], cut = [], flows = { propellant: [], power: [], cargo: [] };
  const full = lod === 'full';
  const api = {
    root, parts, flows, full,
    seg: (n) => full ? n : Math.max(6, Math.round(n / 3)),
    // part(name, label, {axis, distance, representative, note}) -> Group added to root
    part(name, label, { axis = Y, distance = 0, representative = false, note = '' } = {}) {
      const g = new THREE.Group(); g.name = name;
      g.userData = { part: name, label, representative, note };
      root.add(g);
      parts.push({ name, label, object: g, axis: axis.clone().normalize(), distance, representative, note });
      return g;
    },
    // mesh(group, geometry, materialId, {cut, capColor, pos, rot}) -> Mesh; cut: closed and worth a section
    mesh(group, geo, matId, { cut: isCut = false, capColor, pos, rot, scale } = {}) {
      const m = new THREE.Mesh(geo, mats.get(matId));
      if (pos) m.position.copy(pos); if (rot) m.rotation.set(rot.x || 0, rot.y || 0, rot.z || 0); if (scale) m.scale.copy(scale);
      m.castShadow = true; m.receiveShadow = true;
      if (capColor) m.userData.capColor = capColor;
      if (isCut) cut.push(m);
      group.add(m); return m;
    },
    flow(kind, points) { flows[kind].push(new THREE.CatmullRomCurve3(points)); },
    finish(info) {
      root.updateMatrixWorld(true);
      let tris = 0;
      root.traverse(o => { if (o.isMesh) { const g = o.geometry, n = g.index ? g.index.count : g.attributes.position.count; tris += (o.isInstancedMesh ? o.count : 1) * n / 3; } });
      // cut targets outer first: bigger bounding volume first, so inner caps overwrite outer ones
      const vol = m => { const s = new THREE.Box3().setFromObject(m).getSize(new THREE.Vector3()); return s.x * s.y * s.z; };
      cut.sort((a, b) => vol(b) - vol(a));
      const box = new THREE.Box3().setFromObject(root);
      // label anchor: on the part's outer side (its box edge, away from the vehicle's axis, or towards the default
      // camera for parts on the axis), so shells are not hidden by what they contain; stored in the part's space
      const vc = box.getCenter(new THREE.Vector3()), cam = new THREE.Vector3(Math.sin(0.6), 0, Math.cos(0.6));
      for (const p of parts) {
        const b = new THREE.Box3().setFromObject(p.object), bc = b.getCenter(new THREE.Vector3()), bs = b.getSize(new THREE.Vector3());
        const dir = bc.clone().sub(vc).setY(0);
        if (dir.length() < 0.05 * box.getSize(new THREE.Vector3()).length()) dir.copy(cam); else dir.normalize();
        const reach = (Math.abs(dir.x) * bs.x + Math.abs(dir.z) * bs.z) / 2 * 0.98;
        p.anchor = p.object.worldToLocal(bc.addScaledVector(dir, reach));
      }
      return { root, parts, cutTargets: cut, flows, triangles: Math.round(tris), box, size: box.getSize(new THREE.Vector3()),
        explode: parts.filter(p => p.distance).map(p => ({ object: p.object, axis: p.axis, distance: p.distance })),
        representative: parts.some(p => p.representative), ...info };
    },
  };
  return api;
}

// radial unit vector (horizontal) for angle a, and a point at radius r, height y
export const radial = a => V3(Math.cos(a), 0, Math.sin(a));
export const at = (a, r, y) => V3(r * Math.cos(a), y, r * Math.sin(a));
