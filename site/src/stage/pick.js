// Hover and pick: a ray from the pointer finds the named part under it (the nearest ancestor with userData.part),
// skipping geometry the cutaway has removed. The part is outlined by OutlinePass on tier >= 2, or tinted through
// its emissive colour on tier 1. Clicks call onPick(partName); the callout buttons give the same for keyboards.
import * as THREE from 'three';

export function createPicker(canvas, camera, { targets, isClipped, outline, onHover = () => {}, onPick = () => {}, invalidate }) {
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2(), tint = new THREE.Color('#2a6f86');
  let hovered = null, pending = null, raf = 0;
  const saved = new Map();

  const partOf = o => { while (o && !o.userData.part) o = o.parent; return o; };
  function hit(e) {
    const r = canvas.getBoundingClientRect();
    ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const h = ray.intersectObjects(targets(), false).find(x => !x.object.userData.cutHelper && !isClipped(x.point));
    return h ? partOf(h.object) : null;
  }
  // part: a part Group, a list of them (a group such as the legs, from the page's part list) or null
  function highlight(part) {
    if (part === hovered || (Array.isArray(part) && Array.isArray(hovered) && part.length === hovered.length && part.every((q, i) => q === hovered[i]))) return;
    for (const [m, c] of saved) m.emissive.copy(c);
    saved.clear();
    hovered = part;
    const meshes = [], list = Array.isArray(part) ? part : part ? [part] : [];
    for (const q of list) q.traverse(o => { if (o.isMesh && !o.userData.cutHelper) meshes.push(o); });
    part = list[0] || null;
    if (!outline(meshes)) for (const m of meshes) {
      const mat = m.material; if (!mat.emissive || saved.has(mat)) continue;
      saved.set(mat, mat.emissive.clone()); mat.emissive.add(tint);
    }
    canvas.style.cursor = part ? 'pointer' : '';
    onHover(part?.userData.part || null);
    invalidate();
  }
  const move = e => { pending = e; if (!raf) raf = requestAnimationFrame(() => { raf = 0; highlight(hit(pending)); }); };
  const leave = () => highlight(null);
  let down = null;
  const pdown = e => { down = [e.clientX, e.clientY]; };
  const click = e => { if (down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) < 5) { const p = hit(e); if (p) onPick(p.userData.part); } };   // not after a drag
  canvas.addEventListener('pointermove', move); canvas.addEventListener('pointerleave', leave);
  canvas.addEventListener('pointerdown', pdown); canvas.addEventListener('click', click);
  return {
    highlight,
    dispose() {
      highlight(null); cancelAnimationFrame(raf);
      canvas.removeEventListener('pointermove', move); canvas.removeEventListener('pointerleave', leave);
      canvas.removeEventListener('pointerdown', pdown); canvas.removeEventListener('click', click);
    },
  };
}
