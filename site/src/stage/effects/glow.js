// Near-nozzle engine glow (research §1.4): an additive, view-dependent cone a few exit radii long below each bell,
// set by the catalogue's plume_class. In vacuum the jet expands monotonically, so no shock diamonds. Hydrolox is
// almost invisible (NASA Spinoff on hydrogen flames); hypergolic exhaust is described as colourless and transparent
// (Apollo LM), so only faint; for methalox no authoritative description exists, so faint as well (Assumed). The glow
// scales with throttle and is drawn only while the engine fires; sunlit regolith behind it washes it out, as it should.
import * as THREE from 'three';

export const GLOW = {
  methalox: { color: '#8fa6ff', strength: 0.35, flag: 'Assumed', note: 'no published description of a methalox vacuum plume; faint by analogy with the others' },
  hypergolic: { color: '#ffb27a', strength: 0.22, flag: 'Assumed', note: 'Apollo LM exhaust: colourless and transparent on ascent footage (research §1.4, Low)' },
  hydrolox: { color: '#b7a8ff', strength: 0.03, flag: 'Assumed', note: 'a hydrogen flame is nearly invisible in daylight (NASA Spinoff, a terrestrial source applied to vacuum)' },
};

const vert = /* glsl */`
varying float vS; varying vec3 vN; varying vec3 vV;
uniform float uLen;
void main() {
  vS = clamp(-position.y / uLen, 0.0, 1.0);
  vec4 w = modelMatrix * vec4(position, 1.0);
  vN = normalize(mat3(modelMatrix) * normal); vV = normalize(cameraPosition - w.xyz);
  gl_Position = projectionMatrix * viewMatrix * w;
}`;
const frag = /* glsl */`
uniform vec3 uColor; uniform float uStrength; uniform float uThrottle;
varying float vS; varying vec3 vN; varying vec3 vV;
void main() {
  float core = pow(abs(dot(normalize(vN), normalize(vV))), 1.5);   // a gas cone looks brightest along its middle
  float i = uStrength * uThrottle * (1.0 - vS) * (1.0 - vS) * core;
  gl_FragColor = vec4(uColor * i, 1.0);
}`;

// The bells of the named parts: [{mesh, exitY (bell-local), radius}] (lathe bells run from the throat at y = 0 down)
export function findBells(vehicle, partNames) {
  const out = [];
  for (const p of vehicle.parts) if (partNames.includes(p.name)) p.object.traverse(o => {
    if (!o.isMesh) return;
    o.geometry.computeBoundingBox();
    const b = o.geometry.boundingBox;
    out.push({ mesh: o, exitY: b.min.y, radius: Math.max(b.max.x, -b.min.x, b.max.z, -b.min.z) });
  });
  return out;
}

// The parts that fire in the final descent: the main engine, or the HLS-class mid-body landing thrusters
export const landingParts = vehicle => (vehicle.parts.some(p => p.name === 'thrusters') ? ['thrusters'] : ['engine', 'engines']);

// Height of the lowest nozzle exit above the vehicle's base (y = 0) with the vehicle upright, and the exit radius
export function nozzleExit(vehicle, partNames = landingParts(vehicle)) {
  vehicle.root.updateMatrixWorld(true);
  let y = Infinity, r = 0;
  for (const b of findBells(vehicle, partNames)) {
    const p = b.mesh.localToWorld(new THREE.Vector3(0, b.exitY, 0)), inv = vehicle.root.worldToLocal(p.clone());
    if (inv.y < y) { y = inv.y; r = b.radius; }
  }
  return { y: Number.isFinite(y) ? y : 0, radius: r };
}

/* createGlow(vehicle, plumeClass, {partNames}) -> {setThrottle(0..1), visible, dispose} or null for 'none' */
export function createGlow(vehicle, plumeClass, { partNames = landingParts(vehicle) } = {}) {
  const cfg = GLOW[plumeClass];
  if (!cfg) return null;
  const meshes = [];
  for (const b of findBells(vehicle, partNames)) {
    const len = 4 * b.radius;
    const geo = new THREE.CylinderGeometry(b.radius * 0.95, b.radius * 2.2, len, 32, 1, true).translate(0, -len / 2, 0);
    const mat = new THREE.ShaderMaterial({ vertexShader: vert, fragmentShader: frag, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
      uniforms: { uColor: { value: new THREE.Color(cfg.color) }, uStrength: { value: cfg.strength }, uThrottle: { value: 0 }, uLen: { value: len } } });
    const m = new THREE.Mesh(geo, mat);
    m.position.y = b.exitY; m.userData = { noPick: true, noAO: true }; m.renderOrder = 6; m.castShadow = false; m.receiveShadow = false;
    b.mesh.add(m); meshes.push(m);
  }
  let on = true;
  return {
    config: cfg, meshes,
    setThrottle(x) { for (const m of meshes) { m.material.uniforms.uThrottle.value = x; m.visible = on && x > 0.001; } },
    set visible(v) { on = v; for (const m of meshes) m.visible = v && m.material.uniforms.uThrottle.value > 0.001; },
    dispose() { for (const m of meshes) { m.removeFromParent(); m.geometry.dispose(); m.material.dispose(); } },
  };
}
