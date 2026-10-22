// The landing dust on screen (research §1.4, numbers from dust-model.js): the ejecta sheet as ballistic GPU points and
// a ground-hugging obscuration layer (three stacked, terrain-following discs with radial streaks that flow outward),
// both lit by the sun with forward scattering. The layer's opacity is the model's obscuration(t): it peaks in the
// last seconds and is zero from engine cut-off on, while grains already in flight finish their arcs.
import * as THREE from 'three';
import { buildLandingDust, onsetHeight } from './dust-model.js';
import { ballisticPoints } from './particles.js';

const layerVert = /* glsl */`
varying vec3 vW; varying vec2 vL;
void main() { vL = position.xz; vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const layerFrag = /* glsl */`
uniform float uOpacity; uniform float uR; uniform float uTime; uniform float uSeed; uniform float uLight; uniform float uWeight;
uniform vec3 uSun; uniform vec3 uColor;
varying vec3 vW; varying vec2 vL;
float h1(float x) { return fract(sin(x * 127.1 + uSeed * 3.7) * 43758.5453); }
float n1(float x) { float i = floor(x), f = fract(x); return mix(h1(i), h1(i + 1.0), f * f * (3.0 - 2.0 * f)); }
void main() {
  float r = length(vL) / uR, a = atan(vL.y, vL.x);
  if (r > 1.0) discard;
  float radial = smoothstep(0.02, 0.12, r) * (1.0 - smoothstep(0.45, 1.0, r));
  float streak = 0.45 + 0.55 * n1(a * 6.366 * 4.0) * (0.6 + 0.4 * n1(a * 6.366 * 13.0 + 7.0));   // 40 and ~130 streaks round the circle
  float flow = 0.7 + 0.3 * n1(r * 9.0 - uTime * 6.0 + a * 2.0);                                      // texture moving outward
  float alpha = uOpacity * uWeight * radial * streak * flow;
  float c = dot(normalize(vW - cameraPosition), uSun);
  float hg = 0.51 / pow(1.49 - 1.4 * c, 1.5) / 0.28;
  gl_FragColor = vec4(uColor * uLight * (0.25 + 0.75 * min(hg, 6.0)), clamp(alpha, 0.0, 0.85));
}`;

/* createLandingDust({timeline, cutoff, keepoutM, seed, n, thrustN}) -> {group, model, setTime(t), setCount(k), setSun(dir,
   intensity), setGround(fn), show({sheet, layer}), info(t), dispose}. timeline: see dust-model.js (scene metres). */
export function createLandingDust({ timeline, cutoff, keepoutM = 1000, seed = 1, n = 30000, thrustN = 5000 }) {
  const model = buildLandingDust({ timeline, cutoff, keepoutM, seed, n });
  const group = new THREE.Group(); group.name = 'landing-dust';
  const sheet = ballisticPoints({ n, sizeM: 0.14, gain: 0.006, name: 'dust-sheet' });
  const o = [0, 0, 0], v = [0, 0, 0];
  for (let i = 0; i < n; i++) {
    o[0] = model.origin[3 * i]; o[1] = model.origin[3 * i + 1] + 0.05; o[2] = model.origin[3 * i + 2];
    v[0] = model.vel[3 * i]; v[1] = model.vel[3 * i + 1]; v[2] = model.vel[3 * i + 2];
    sheet.write(i, o, v, model.birth[i], model.life[i], model.size[i]);
  }
  sheet.commit();
  group.add(sheet.points);

  // obscuration layer: radius from the onset height (the dense near field), ~45 m for CLPS, capped at 200 m
  const R = Math.min(200, Math.max(20, 3 * onsetHeight(thrustN)));
  const SEG = 72, RINGS = 18, layers = [];
  const geo = new THREE.BufferGeometry(), pos = new Float32Array((RINGS * SEG + 1) * 3), idx = [];
  for (let r = 0; r < RINGS; r++) for (let s = 0; s < SEG; s++) {
    const k = 1 + r * SEG + s, a = s / SEG * 2 * Math.PI, rr = R * ((r + 1) / RINGS) ** 1.3;
    pos[3 * k] = rr * Math.cos(a); pos[3 * k + 2] = rr * Math.sin(a);
    const s1 = (s + 1) % SEG;
    if (r === 0) idx.push(0, 1 + s1, k);
    else { const p0 = 1 + (r - 1) * SEG; idx.push(p0 + s, p0 + s1, k, p0 + s1, 1 + r * SEG + s1, k); }
  }
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3)); geo.setIndex(idx);
  const base = new Float32Array(pos.length);   // terrain height under each vertex, relative to the centre
  for (const [h, scale, w] of [[0.35, 1, 0.55], [1.0, 0.8, 0.35], [2.0, 0.55, 0.22]]) {
    const m = new THREE.ShaderMaterial({ vertexShader: layerVert, fragmentShader: layerFrag, transparent: true, depthWrite: false, side: THREE.DoubleSide,
      uniforms: { uOpacity: { value: 0 }, uR: { value: R * scale }, uTime: { value: 0 }, uSeed: { value: seed % 997 }, uLight: { value: 1 }, uWeight: { value: w },
        uSun: { value: sheet.material.uniforms.uSun.value }, uColor: { value: new THREE.Color('#b9b2a5').multiplyScalar(0.2) } } });
    const mesh = new THREE.Mesh(geo, m); mesh.userData = { noPick: true, noAO: true, lift: h };
    mesh.renderOrder = 5; layers.push(mesh); group.add(mesh);
  }
  let ground = null, centre = new THREE.Vector3(Infinity, 0, 0);
  const at = (arr, t) => { const T = timeline.t; if (t <= T[0]) return arr[0]; if (t >= T[T.length - 1]) return arr[T.length - 1]; let i = 0; while (T[i + 1] < t) i++; const f = (t - T[i]) / (T[i + 1] - T[i]); return arr[i] + (arr[i + 1] - arr[i]) * f; };
  // drape the discs over the terrain round the current centre (re-done when the centre moves > 0.5 m)
  function drape(cx, cy, cz) {
    if (centre.distanceToSquared(new THREE.Vector3(cx, cy, cz)) < 0.25) return;
    centre.set(cx, cy, cz);
    for (let k = 0; k < pos.length / 3; k++) base[k] = ground ? ground(cx + pos[3 * k], cz + pos[3 * k + 2]) - cy : 0;
    for (let k = 0; k < pos.length / 3; k++) pos[3 * k + 1] = base[k];
    geo.attributes.position.needsUpdate = true; geo.computeBoundingSphere();
  }
  let showLayer = true;
  return {
    group, model, radius: R, onsetM: onsetHeight(thrustN),
    setTime(t) {
      sheet.setTime(t);
      const cx = at(timeline.gx, Math.min(t, cutoff)), cy = at(timeline.gy, Math.min(t, cutoff)), cz = at(timeline.gz, Math.min(t, cutoff));
      drape(cx, cy, cz);
      const op = model.obscuration(t);
      for (const L of layers) {
        L.position.set(cx, cy + L.userData.lift, cz);
        L.material.uniforms.uOpacity.value = op; L.material.uniforms.uTime.value = t;
        L.visible = showLayer && op > 0.002;
      }
    },
    setCount: k => sheet.setCount(k),
    setSun(dir, light = 1) { sheet.setSun(dir); for (const L of layers) L.material.uniforms.uLight.value = light; sheet.setGain(0.006 * light); },
    setGround(fn) { ground = fn; centre.set(Infinity, 0, 0); },
    show({ sheet: s = true, layer = true } = {}) { sheet.points.visible = s; showLayer = layer; },
    info: t => ({ alive: model.alive(t, sheet.points.geometry.drawRange.count), obscuration: model.obscuration(t), scour: model.scour(t), emission: model.emission(t) }),
    dispose() { sheet.dispose(); geo.dispose(); for (const L of layers) L.material.dispose(); },
  };
}
