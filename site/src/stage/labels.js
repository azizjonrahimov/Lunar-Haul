// 3D-anchored callouts: the F-30 callout layer (dot + leader + pill) placed at parts' anchor points every drawn
// frame. A label hides when its anchor is behind the camera, off screen, or occluded by unclipped geometry (a ray
// test every few frames; hits on the clipped side of the cutaway do not count), and layout() pushes overlapping
// pills apart. Pills are buttons when the label has onSelect, so every part can be reached by keyboard.
import * as THREE from 'three';
import { callouts } from '../ui/callout.js';

// a part never hides its own label (anchors may sit inside it: a pipe's centre line, a bell's cavity)
const within = (o, root) => { for (; o; o = o.parent) if (o === root) return true; return false; };

export function createLabels(host, camera, { occluders = () => [], isClipped = () => false } = {}) {
  const layer = callouts(host);
  const items = [], ray = new THREE.Raycaster(), v = new THREE.Vector3(), w = new THREE.Vector3(), dir = new THREE.Vector3(), fw = new THREE.Vector3();
  let frame = 0, enabled = true;

  return {
    layer,
    // add({id, text, object, anchor: Vector3 in the object's space, onSelect, tone})
    add({ id, text, object, anchor = new THREE.Vector3(), onSelect, tone }) {
      const c = layer.add({ id, text, onSelect, tone });
      const it = { id, object, anchor: anchor.clone(), c, occluded: false, hidden: false };
      items.push(it); return c;
    },
    setPressed(id) { for (const it of items) it.c.setPressed(it.id === id); },
    // hide one label whatever its visibility (decluttering: e.g. vehicle labels in far views)
    setHidden(id, v) { const it = items.find(x => x.id === id); if (it) it.hidden = v; },
    show(v) { enabled = v; for (const it of items) it.c.show(v); },
    // force: run the occlusion test now (the stage does this when motion stops, so no stale state is left)
    update(width, height, force = false) {
      if (!enabled || !items.length) return;
      const checkOcclusion = force || frame++ % 4 === 0, targets = checkOcclusion ? occluders() : null;
      camera.getWorldDirection(fw);
      for (const it of items) {
        it.object.updateWorldMatrix(true, false);
        w.copy(it.anchor).applyMatrix4(it.object.matrixWorld);
        v.copy(w).project(camera);
        // behind the camera from camera space (NDC z is reversed with a reversed depth buffer)
        const behind = dir.copy(w).sub(camera.position).dot(fw) <= camera.near, off = Math.abs(v.x) > 1.05 || Math.abs(v.y) > 1.05;
        if (checkOcclusion && !behind && !off) {
          dir.copy(w).sub(camera.position); const dist = dir.length(); dir.divideScalar(dist);
          ray.set(camera.position, dir); ray.far = dist - 0.02;
          it.occluded = ray.intersectObjects(targets, false).some(hit => !isClipped(hit.point) && !hit.object.userData.cutHelper && !within(hit.object, it.object));
        }
        const visible = !it.hidden && !behind && !off && !it.occluded;
        it.c.show(visible);
        if (visible) it.c.place((v.x * 0.5 + 0.5) * width, (-v.y * 0.5 + 0.5) * height);
      }
      layer.layout();
    },
    clear() { layer.clear(); items.length = 0; },
    dispose() { layer.clear(); layer.el.remove(); },
  };
}
