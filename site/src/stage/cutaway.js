// Cutaway with solid caps (three's webgl_clipping_stencil method, research §1.2). Each target mesh must be closed
// (watertight). For every target and plane: two stencil-only copies of the mesh (back faces +1, front faces -1),
// clipped by that plane alone, then a cap quad on the plane drawn where the stencil is non-zero, in the part's cap
// colour. 'plane' removes one half-space; 'wedge' removes the region inside two planes (clipIntersection), so caps
// are trimmed by the other plane turned round. Targets are drawn sorted outer first, so inner caps overwrite outer.
import * as THREE from 'three';

export function createCutaway(scene) {
  const group = new THREE.Group(); group.name = 'cutaway-caps';
  scene.add(group);
  let targets = [], planes = [], intersect = false, helpers = [], capGeo = null, radius = 5, centre = new THREE.Vector3();

  function clear() {
    for (const h of helpers) { h.removeFromParent(); h.material.dispose(); }
    helpers = []; capGeo?.dispose(); capGeo = null;
    for (const m of targets) { m.material.clippingPlanes = null; m.material.clipIntersection = false; m.material.needsUpdate = true; m.renderOrder = 0; }
  }

  function build() {
    clear();
    if (!planes.length) return;
    capGeo = new THREE.PlaneGeometry(radius * 2.4, radius * 2.4);
    targets.forEach((mesh, k) => {
      const base = 10 + k * 10;
      mesh.material.clippingPlanes = planes; mesh.material.clipIntersection = intersect; mesh.material.clipShadows = true;
      mesh.material.needsUpdate = true; mesh.renderOrder = 1000;
      planes.forEach((plane, i) => {
        for (const [side, op] of [[THREE.BackSide, THREE.IncrementWrapStencilOp], [THREE.FrontSide, THREE.DecrementWrapStencilOp]]) {
          const m = new THREE.MeshBasicMaterial({ side, colorWrite: false, depthWrite: false, depthTest: false, clippingPlanes: [plane],
            stencilWrite: true, stencilFunc: THREE.AlwaysStencilFunc, stencilFail: op, stencilZFail: op, stencilZPass: op });
          const w = new THREE.Mesh(mesh.geometry, m);
          w.renderOrder = base + i * 3 + 1; w.userData = { cutHelper: true, noPick: true };
          mesh.add(w); helpers.push(w);   // child of the part: follows it when exploded
        }
        const others = planes.filter(p => p !== plane).map(p => intersect ? p.clone().negate() : p);
        const src = mesh.material, col = mesh.userData.capColor ? new THREE.Color(mesh.userData.capColor) : src.color.clone().offsetHSL(0, -0.1, 0.12);
        const capMat = new THREE.MeshStandardMaterial({ color: col, metalness: 0.1, roughness: 0.6, side: THREE.DoubleSide, clippingPlanes: others,
          stencilWrite: true, stencilRef: 0, stencilFunc: THREE.NotEqualStencilFunc,
          stencilFail: THREE.ReplaceStencilOp, stencilZFail: THREE.ReplaceStencilOp, stencilZPass: THREE.ReplaceStencilOp });
        const cap = new THREE.Mesh(capGeo, capMat);
        cap.renderOrder = base + i * 3 + 2; cap.userData = { cutHelper: true, noPick: true, plane };
        cap.onAfterRender = r => r.clearStencil();   // leftovers trimmed by the other plane must not leak into the next part
        group.add(cap); helpers.push(cap);
      });
    });
    place();
  }

  function place() {
    for (const h of helpers) {
      const p = h.userData.plane; if (!p) continue;
      p.projectPoint(centre, h.position);
      h.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), p.normal.clone().negate());
      h.updateMatrixWorld();
    }
  }

  return {
    group,
    get planes() { return planes; },
    get intersect() { return intersect; },
    // targets: closed meshes, ordered outer to inner; bounds: the subject's box (sizes the caps)
    setTargets(list, box) {
      clear(); targets = list;
      if (box) { box.getCenter(centre); radius = box.getSize(new THREE.Vector3()).length() / 2; }
      build();
    },
    // mode 'off' | 'plane' | 'wedge'; facing: the horizontal direction the cut opens towards (unit Vector3);
    // origin: a point on the cut's vertical axis (default: the subject's box centre, which may be off the part's axis);
    // dir (F-51, 'plane' only): any direction the cut opens towards, e.g. up for a horizontal cut through a rover
    set(mode, { facing = new THREE.Vector3(0, 0, 1), halfAngle = 45, origin, dir } = {}) {
      const f = mode === 'plane' && dir ? dir.clone().normalize() : new THREE.Vector3(facing.x, 0, facing.z).normalize(), up = new THREE.Vector3(0, 1, 0), o = origin || centre;
      if (mode === 'plane') {
        planes = [new THREE.Plane().setFromNormalAndCoplanarPoint(f.clone().negate(), o)]; intersect = false;
      } else if (mode === 'wedge') {
        const a = THREE.MathUtils.degToRad(90 - halfAngle);
        // each plane contains the vertical axis; a point is removed when it is on the negative side of both
        const n1 = f.clone().applyAxisAngle(up, a).negate(), n2 = f.clone().applyAxisAngle(up, -a).negate();
        planes = [new THREE.Plane().setFromNormalAndCoplanarPoint(n1, o), new THREE.Plane().setFromNormalAndCoplanarPoint(n2, o)];
        intersect = true;
      } else { planes = []; intersect = false; }
      build();
      return planes;
    },
    isClipped(point) {
      if (!planes.length) return false;
      const neg = planes.map(p => p.distanceToPoint(point) < 0);
      return intersect ? neg.every(Boolean) : neg.some(Boolean);
    },
    dispose() { clear(); scene.remove(group); },
  };
}
