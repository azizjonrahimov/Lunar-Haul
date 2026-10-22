// Exploded view: each named part slides along its own axis (research §1.3: legs out, tanks up, engine down reads
// better than a radial burst). set(t) places the parts for t in [0, 1]; to(t) animates through the stage's loop
// (about 0.7 s, eased), or jumps under prefers-reduced-motion.
import * as THREE from 'three';
import { reducedMotion } from '../ui/dom.js';

// parts: [{object, axis: Vector3 (parent space), distance: m}]
export function createExplode(parts, { animate, onChange = () => {} } = {}) {
  const base = parts.map(p => p.object.position.clone());
  let t = 0, job = null;
  const ease = x => x < 0.5 ? 4 * x * x * x : 1 - (-2 * x + 2) ** 3 / 2;
  function set(v) {
    t = v;
    parts.forEach((p, i) => p.object.position.copy(base[i]).addScaledVector(p.axis, p.distance * v));
    onChange(t);
  }
  return {
    get t() { return t; },
    set,
    to(target, { duration = 0.7 } = {}) {
      if (job) job.cancelled = true;
      if (reducedMotion() || !animate) { set(target); return Promise.resolve(); }
      const from = t, my = job = { cancelled: false };
      let s = 0;
      return new Promise(res => animate(dt => {
        if (my.cancelled) { res(); return false; }
        s = Math.min(1, s + dt / duration); set(from + (target - from) * ease(s));
        if (s >= 1) { res(); return false; }
        return true;
      }));
    },
  };
}

// axis helper: unit vector from the assembly centre to the part, flattened to the horizontal (for legs)
export const radialAxis = (object, centre) => {
  const p = object.getWorldPosition(new THREE.Vector3()).sub(centre); p.y = 0;
  return p.lengthSq() > 1e-6 ? p.normalize() : new THREE.Vector3(1, 0, 0);
};
