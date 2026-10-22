// GPU points on analytic ballistic paths (research §1.4). The vertex shader computes each grain's position from its
// origin, launch velocity and birth time, p = p0 + v a + ½ g a² (a = time since birth), so the CPU does no work per
// frame and scrubbing the time back and forth is exact. Grains are lit by the sun with forward scattering
// (Henyey-Greenstein, g = 0.7): under a 1.5° sun a sheet launched at 1–3° glows when the camera looks toward the sun and
// is faint with the sun behind (the honest "hero" effect). Additive blending, so no sorting. Sub-pixel grains dim
// instead of flickering, and grains within a few metres of the camera fade out.
import * as THREE from 'three';
import { G_MOON } from './dust-model.js';

const vertexShader = /* glsl */`
uniform float uTime; uniform float uG; uniform float uSize; uniform float uScale; uniform float uFadeIn; uniform vec3 uSun;
attribute vec4 aVel;    // launch velocity (m/s), birth time (s)
attribute vec2 aLife;   // flight time (s), size factor
varying float vI;
void main() {
  float a = uTime - aVel.w;
  vec3 p = position + aVel.xyz * a; p.y -= 0.5 * uG * a * a;
  vec4 wp = modelMatrix * vec4(p, 1.0), mv = viewMatrix * wp;
  gl_Position = projectionMatrix * mv;
  float alive = step(0.0, a) * step(a, aLife.x);
  float fade = alive * smoothstep(0.0, uFadeIn, a) * (1.0 - smoothstep(0.8, 1.0, a / max(aLife.x, 1e-3)));
  float c = dot(normalize(wp.xyz - cameraPosition), uSun);       // 1 looking straight at the sun
  float hg = 0.51 / pow(1.49 - 1.4 * c, 1.5) / 0.28;            // Henyey-Greenstein g = 0.7, 1 at 90 degrees
  float px = uSize * aLife.y * uScale / max(-mv.z, 1e-3);
  gl_PointSize = clamp(px, 1.0, 6.0);
  vI = fade * hg * min(1.0, px * px) * smoothstep(1.5, 6.0, -mv.z);   // grains passing the lens fade, not blobs
  if (alive < 0.5) gl_Position = vec4(2.0, 2.0, 2.0, 1.0);       // outside the clip volume
}`;
const fragmentShader = /* glsl */`
uniform vec3 uColor; uniform float uGain; varying float vI;
void main() {
  vec2 q = gl_PointCoord * 2.0 - 1.0; float d = dot(q, q);
  if (d > 1.0 || vI <= 0.0) discard;
  gl_FragColor = vec4(uColor * uGain * vI * (1.0 - d), 1.0);
}`;

/* ballisticPoints({n, color, sizeM, gain}) -> {points, setTime(t), setCount(k), setSun(dirWorld), write(i, origin, vel,
   birth, life, size), commit(), material}. Origins in the points' local space (y up). */
export function ballisticPoints({ n, color = '#d6cfc2', sizeM = 0.12, gain = 0.02, fadeIn = 0.12, name = 'dust' }) {
  const g = new THREE.BufferGeometry();
  const origin = new Float32Array(3 * n), vel = new Float32Array(4 * n), life = new Float32Array(2 * n);
  for (let i = 0; i < n; i++) vel[4 * i + 3] = 1e9;   // unborn
  g.setAttribute('position', new THREE.BufferAttribute(origin, 3));
  g.setAttribute('aVel', new THREE.BufferAttribute(vel, 4));
  g.setAttribute('aLife', new THREE.BufferAttribute(life, 2));
  const uniforms = {
    uTime: { value: 0 }, uG: { value: G_MOON }, uSize: { value: sizeM }, uScale: { value: 800 }, uFadeIn: { value: fadeIn },
    uSun: { value: new THREE.Vector3(0, 0.03, -1).normalize() }, uColor: { value: new THREE.Color(color) }, uGain: { value: gain },
  };
  const material = new THREE.ShaderMaterial({ uniforms, vertexShader, fragmentShader, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
  const points = new THREE.Points(g, material);
  points.name = name; points.frustumCulled = false;
  points.userData = { noPick: true, noAO: true };
  const tmp = new THREE.Vector2();
  // point size in metres: pixels per metre at unit depth = buffer height / (2 tan(fov / 2))
  points.onBeforeRender = (renderer, scene, camera) => {
    const rt = renderer.getRenderTarget(), hPx = rt ? rt.height : renderer.getDrawingBufferSize(tmp).y;
    uniforms.uScale.value = hPx / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2));
  };
  let count = n, gainBase = gain;
  g.setDrawRange(0, n);
  return {
    points, material, n,
    setTime(t) { uniforms.uTime.value = t; },
    // draw the first k grains; each one brighter so a smaller tier keeps roughly the same overall glow
    setCount(k) { count = Math.max(0, Math.min(n, k)); g.setDrawRange(0, count); uniforms.uGain.value = gainBase * Math.pow(n / Math.max(1, count), 0.7); },
    setGain(v) { gainBase = v; this.setCount(count); },
    setSun(dir) { uniforms.uSun.value.copy(dir).normalize(); },
    write(i, o, v, birth, flight, size) {
      origin[3 * i] = o[0]; origin[3 * i + 1] = o[1]; origin[3 * i + 2] = o[2];
      vel[4 * i] = v[0]; vel[4 * i + 1] = v[1]; vel[4 * i + 2] = v[2]; vel[4 * i + 3] = birth;
      life[2 * i] = flight; life[2 * i + 1] = size;
    },
    commit() { for (const k of ['position', 'aVel', 'aLife']) g.attributes[k].needsUpdate = true; },
    dispose() { g.dispose(); material.dispose(); },
  };
}
