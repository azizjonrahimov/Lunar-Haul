// Wheel dust behind moving rovers: grains thrown back from each wheel's contact patch on ballistic arcs (no air, so
// no lingering cloud). A grain leaves the rim at about the rim speed, which equals the rover's speed, so at a few km/h
// the arcs are short and low (v²/2g < 1 m): small rooster tails that land within a few metres (Modelled; the Apollo
// LRV carried fenders against exactly this spray). Births sit on a fixed time grid and every grain is drawn from
// hash(seed, k), so any time can be shown directly (scrubbing back regenerates only the slots it needs).
import { ballisticPoints } from './particles.js';
import { hash01 } from './rng.js';
import { G_MOON } from './dust-model.js';

const D = Math.PI / 180;

/* createWheelDust({nWheels, seed, ratePerWheel, maxLife}) -> {points, update(t, sourceAt), setSun(dir, light), dispose}
   sourceAt(t) -> {contacts: [[x, y, z], ...] (one per wheel, scene metres), fwd: [x, z] (unit heading), speed (m/s)} */
export function createWheelDust({ nWheels, seed = 1, ratePerWheel = 60, maxLife = 2.5 }) {
  const dt = 1 / (ratePerWheel * nWheels), N = Math.ceil(maxLife / dt) + 8;
  const pts = ballisticPoints({ n: N, sizeM: 0.05, gain: 0.05, fadeIn: 0.05, name: 'wheel-dust' });
  const slotK = new Float64Array(N).fill(-1), o = [0, 0, 0], v = [0, 0, 0];
  function gen(k, slot, sourceAt) {
    const tk = k * dt, src = sourceAt(tk), w = k % nWheels, c = src.contacts[w % src.contacts.length];
    const u = j => hash01(seed, k, j);
    if (!c || src.speed < 0.05) { pts.write(slot, [0, -1e4, 0], [0, 0, 0], tk, 0, 0); return; }
    const phi = (15 + 40 * u(1)) * D, psi = (u(2) - 0.5) * 40 * D, speed = src.speed * (0.5 + 0.6 * u(3));
    const bx = -src.fwd[0], bz = -src.fwd[1], cs = Math.cos(psi), sn = Math.sin(psi);
    const dx = bx * cs - bz * sn, dz = bx * sn + bz * cs, side = (u(4) - 0.5) * 0.5;
    o[0] = c[0] + bx * 0.15 - bz * side; o[1] = c[1] + 0.04; o[2] = c[2] + bz * 0.15 + bx * side;
    v[0] = dx * speed * Math.cos(phi); v[1] = speed * Math.sin(phi); v[2] = dz * speed * Math.cos(phi);
    pts.write(slot, o, v, tk, 2 * v[1] / G_MOON, 0.5 + u(5));
  }
  return {
    points: pts.points, count: N,
    update(t, sourceAt) {
      const k1 = Math.floor(t / dt), k0 = Math.max(0, Math.ceil((t - maxLife) / dt));
      let changed = false;
      for (let k = k0; k <= k1; k++) { const s = k % N; if (slotK[s] === k) continue; slotK[s] = k; gen(k, s, sourceAt); changed = true; }
      if (changed) pts.commit();
      pts.setTime(t);
    },
    setSun(dir, light = 1) { pts.setSun(dir); pts.setGain(0.05 * light); },
    reset() { slotK.fill(-1); },
    dispose: () => pts.dispose(),
  };
}
