// The procedural vehicle kit (F-32a). One entry point:
//   buildVehicle(catalog, mats, id, {lod: 'full' | 'simple' | 'icon'}) -> {root, parts, cutTargets, explode, flows,
//     triangles, box, size, representative, entry}
// Everything is built at true scale from the catalogue (lunarsim/catalog-v1.json, loaded by src/catalog.js);
// buildLOD() stacks the three levels in a THREE.LOD (full near, simplified mid, icon far, as /world/ shows today).
import * as THREE from 'three';
import { clps, mk1, large } from './landers.js';
import { ltv, haul, micro, lrv } from './rovers.js';
import { habitat, pad, solarTower, commsMast, cargoPallet, astronaut } from './base.js';
export { createMaterials } from './materials.js';
export { astronaut };

export const GENERATORS = {
  CLPS: clps, MK1: mk1, LARGE: large, LTV: ltv, HAUL: haul, MICRO: micro,
  habitat, pad, solar_tower: solarTower, comms_mast: commsMast, cargo_pallet: cargoPallet, apollo_lrv: lrv,
};
export const GROUPS = { landers: ['CLPS', 'MK1', 'LARGE'], rovers: ['LTV', 'HAUL', 'MICRO'], base: ['habitat', 'pad', 'solar_tower', 'comms_mast', 'cargo_pallet'] };

export function buildVehicle(catalog, mats, id, { lod = 'full', count } = {}) {
  const entry = catalog.entry(id), gen = GENERATORS[id];
  if (!gen) throw new Error(`vehicle kit: no generator for ${id}`);
  if (lod === 'icon') return icon(gen(entry, mats, { lod: 'simple' }), entry);
  const v = gen(entry, mats, { lod, count });
  v.entry = entry;
  v.root.userData.representative = !!entry.representative || v.representative;
  return v;
}

// far level: one box at the vehicle's true bounds, unlit, like today's /world/ icons (the page may scale it)
function icon(simple, entry) {
  const size = simple.size, c = simple.box.getCenter(new THREE.Vector3());
  simple.root.traverse(o => { if (o.isMesh) o.geometry.dispose(); });
  const m = new THREE.Mesh(new THREE.BoxGeometry(size.x, size.y, size.z), new THREE.MeshBasicMaterial({ color: '#d9dee6' }));
  m.position.copy(c);
  const root = new THREE.Group(); root.add(m); root.userData.icon = true;
  return { root, parts: [], cutTargets: [], explode: [], flows: {}, triangles: 12, box: simple.box, size, entry, representative: true };
}

// THREE.LOD with full / simple / icon; switch distances scale with the vehicle's size
export function buildLOD(catalog, mats, id) {
  const full = buildVehicle(catalog, mats, id), simple = buildVehicle(catalog, mats, id, { lod: 'simple' }), far = buildVehicle(catalog, mats, id, { lod: 'icon' });
  const s = Math.max(full.size.x, full.size.y, full.size.z), lodObj = new THREE.LOD();
  lodObj.addLevel(full.root, 0); lodObj.addLevel(simple.root, s * 25); lodObj.addLevel(far.root, s * 150);
  return { lod: lodObj, full, simple, far };
}
