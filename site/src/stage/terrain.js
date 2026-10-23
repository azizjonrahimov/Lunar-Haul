// Lunar terrain for on-site stage views (F-33; the lander lab lands on it in F-34): the 5 m LOLA patch round a site
// (B-34 LOD 2, 2 x 2 km) set into the 20 m tile (16 km), at true scale, drawn by one custom shader:
//  - Lommel-Seeliger regolith, albedo 0.12 (equal to a Lambert surface of that albedo at normal incidence, so it
//    matches the vehicles' materials): slopes facing the 1.5° sun light up, level ground stays dark, as on /world/;
//    times a back-scattering phase function exp(-1.1 α) (α = sun-surface-camera angle; Assumed, a simple stand-in
//    for Hapke's): ground is bright looking down-sun and dark looking toward the sun, as in lunar surface photos;
//  - terrain shadows from the B-34 horizon map: two sectors round the sun's azimuth on the GPU, a soft edge for the
//    0.53° solar disc; the sun can sit at any azimuth without a re-bake;
//  - vehicle shadows: the shader samples the stage sun's shadow map (research §1.7 option b); lighting.fit keeps that
//    camera tight on the focused vehicle, so a 2.6 m rover's ~100 m shadow gets centimetre texels;
//  - headlights: three's SpotLights, evaluated here as lit cones on the ground (no air, so no visible beams);
//  - the landing scour mark: a darker scoured centre and a brighter, streaky blast zone (Assumed shape and size);
//  - metre-scale detail the 5 m data cannot hold (representative, procedural, seeded): two sparse fields of worn craters (cells 9 m
//    and 2.6 m, 9-12 % filled, depth/diameter ~0.05), clods at 0.12-0.4 m and ±12 % albedo noise, each faded out as it shrinks below a
//    pixel; plus scatterRocks(): seeded instanced rocks and boulders near the site (power-law sizes).
// shadeWithHorizon(material) gives any standard material (rocks, vehicles) the same horizon-map sun shadow.
// Scene frame: origin on the ground at the patch centre (the site); x east, y up, z south (= -north); metres.
import * as THREE from 'three';
import { loadTerrain, decodePngGray } from '../terrain.js';
import { loadTerrainV2, horizonProfile } from '../horizon.js';

const SUN_RADIUS_DEG = 0.267;

const vert = /* glsl */`
#include <common>
#include <shadowmap_pars_vertex>
varying vec3 vWorld; varying vec3 vViewPosition;
void main() {
  #include <beginnormal_vertex>
  #include <defaultnormal_vertex>
  #include <begin_vertex>
  #include <project_vertex>
  vViewPosition = -mvPosition.xyz;
  #include <worldpos_vertex>
  vWorld = (modelMatrix * vec4(transformed, 1.0)).xyz;
  #include <shadowmap_vertex>
}`;

const frag = /* glsl */`
#include <common>
#include <packing>
#include <lights_pars_begin>
#include <shadowmap_pars_fragment>
uniform vec4 uTile;                     // site x, y in the tile (m), tile width, height (m)
uniform sampler2D uN20; uniform sampler2D uN5; uniform vec4 uPatch; uniform float uUsePatch;
uniform sampler2D uHorizon; uniform float uUseHz; uniform float uHzW; uniform float uSunElDeg; uniform float uSunRadDeg;
uniform float uAlbedo; uniform vec3 uAmbient;
uniform vec4 uScour; uniform float uScourAmt; uniform float uScourSeed; uniform float uDetail; uniform float uCraterVar;
varying vec3 vWorld; varying vec3 vViewPosition;
float hh1(vec2 p) { return fract(sin(dot(p, vec2(41.31, 289.17))) * 13758.5453); }
vec2 hh2(vec2 p) { return fract(sin(vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)))) * 43758.5453); }
// value noise with its gradient: (value, d/dx, d/dy)
vec3 noised(vec2 x) {
  vec2 i = floor(x), f = fract(x), u = f * f * (3.0 - 2.0 * f), du = 6.0 * f * (1.0 - f);
  float a = hh1(i), b = hh1(i + vec2(1.0, 0.0)), c = hh1(i + vec2(0.0, 1.0)), d = hh1(i + vec2(1.0, 1.0));
  return vec3(a + (b - a) * u.x + (c - a) * u.y + (a - b - c + d) * u.x * u.y, du * (vec2(b - a, c - a) + (a - b - c + d) * u.yx));
}
// a crater field with cells of s metres: a share of the cells (prob) holds a worn bowl with a low rim, wall slope k
// at the rim (0.25 ~ depth/diameter 0.06, a degraded small crater); returns the slope (dh/dx, dh/dz). vary (0..1, F-35d):
// each crater gets its own depth (worn to fresh), a slight ellipse and a rotation, so close views do not look stamped (the
// same switch turns the 0.4 m clod noise down: on its grid, the low sun lit it as rows of dashes)
vec2 craters(vec2 p, float s, float seed, float prob, float k, float vary) {
  vec2 c = floor(p / s), g = vec2(0.0);
  for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
    vec2 cell = c + vec2(float(i), float(j)), h = hh2(cell + seed);
    if (h.x > prob) continue;
    vec2 d = p - (cell + 0.25 + 0.5 * hh2(cell + seed + 7.0)) * s, v3 = hh2(cell + seed + 13.0);
    float a = 6.2832 * v3.y, ca = cos(a), sa = sin(a);
    vec2 e = vec2(ca * d.x + sa * d.y, -sa * d.x + ca * d.y); e.x /= mix(1.0, 1.0 + 0.35 * v3.x, vary);
    float R = s * (0.16 + 0.26 * h.y) * mix(1.0, 0.7 + 0.6 * fract(v3.x * 7.31), vary), r = length(e), x = r / R, kk = k * mix(1.0, 0.3 + 1.1 * fract(v3.y * 5.77), vary);
    if (x > 1.9) continue;
    float dh = x < 1.0 ? kk * sin(1.5708 * x) : -0.12 * kk * exp(-(x - 1.0) * (x - 1.0) / 0.09) * 2.0 * (x - 1.0) / 0.09;   // bowl, then the rim falling off
    g += dh * vec2(ca * e.x - sa * e.y, sa * e.x + ca * e.y) / max(r, 1e-4);
  }
  return g;
}
float h1(float x) { return fract(sin(x * 127.1 + uScourSeed * 3.7) * 43758.5453); }
float n1(float x) { float i = floor(x), f = fract(x); return mix(h1(i), h1(i + 1.0), f * f * (3.0 - 2.0 * f)); }
void main() {
  vec2 xy = vec2(vWorld.x + uTile.x, uTile.y - vWorld.z);          // tile metres, y north
  vec2 uv = vec2(xy.x / uTile.z, 1.0 - xy.y / uTile.w);             // row 0 = north
  vec3 nt = texture2D(uN20, uv).xyz;
  if (uUsePatch > 0.5) {
    vec2 q = (xy - uPatch.xy) / (uPatch.zw - uPatch.xy);
    if (all(greaterThanEqual(q, vec2(0.0))) && all(lessThanEqual(q, vec2(1.0)))) {
      float e = min(min(q.x, 1.0 - q.x), min(q.y, 1.0 - q.y));
      nt = mix(nt, texture2D(uN5, vec2(q.x, 1.0 - q.y)).xyz, smoothstep(0.0, 0.02, e));
    }
  }
  vec3 nW = normalize(nt * 2.0 - 1.0);
  float detailAlb = 1.0;
  if (uDetail > 0.5) {                                               // metre-scale detail, faded below a pixel
    vec2 p = vWorld.xz; float fw = length(fwidth(p));
    float nearFade = mix(1.0, smoothstep(8.0, 60.0, length(vViewPosition)), uCraterVar);   // fewer small bowls right in front of the camera
    vec2 g = craters(p, 9.0, 3.0, 0.09, 0.18, uCraterVar) * (1.0 - smoothstep(0.6, 2.0, fw)) + craters(p, 2.6, 11.0, mix(0.12, 0.06, uCraterVar), 0.22, uCraterVar) * (1.0 - smoothstep(0.2, 0.6, fw)) * nearFade;
    vec3 c1 = noised(p / 0.4), c2 = noised(p / 0.12);
    g += c1.yz / 0.4 * 0.05 * mix(1.0, 0.3, uCraterVar) * (1.0 - smoothstep(0.04, 0.12, fw)) + c2.yz / 0.12 * 0.012 * (1.0 - smoothstep(0.012, 0.04, fw));
    nW = normalize(nW + vec3(-g.x, 0.0, -g.y));
    detailAlb = 0.88 + 0.12 * noised(p / 3.0).x + 0.12 * noised(p / 0.9).x * (1.0 - smoothstep(0.1, 0.3, fw));
  }
  vec3 n = normalize((viewMatrix * vec4(nW, 0.0)).xyz), v = normalize(vViewPosition);
  float mu = max(dot(n, v), 0.0);
  float alb = uAlbedo * detailAlb;
  if (uScourAmt > 0.0) {                                             // landing scour and blast zone
    vec2 sd = vWorld.xz - uScour.xy; float sr = length(sd);
    if (sr < uScour.w) {
      float a = atan(sd.y, sd.x), streak = n1(a * 25.46) * 0.6 + n1(a * 82.0 + 9.0) * 0.4;
      float inner = 1.0 - smoothstep(uScour.z * 0.5, uScour.z, sr);
      float halo = smoothstep(uScour.z * 0.5, uScour.z, sr) * (1.0 - smoothstep(uScour.z, uScour.w, sr));
      alb *= mix(1.0, 0.8, inner * uScourAmt) * (1.0 + 0.45 * halo * uScourAmt * (0.4 + 0.6 * streak));
    }
  }
  vec3 col = alb * uAmbient;
  #if NUM_DIR_LIGHTS > 0
    DirectionalLight sunL = directionalLights[0];
    float mu0 = dot(n, sunL.direction);
    if (mu0 > 0.0) {
      vec2 hz = texture2D(uHorizon, uv).rg;
      float vis = uUseHz > 0.5 ? smoothstep(-uSunRadDeg, uSunRadDeg, uSunElDeg - mix(hz.r, hz.g, uHzW)) : 1.0;
      float sh = 1.0;
      #if defined( USE_SHADOWMAP ) && NUM_DIR_LIGHT_SHADOWS > 0
        DirectionalLightShadow ds = directionalLightShadows[0];
        sh = getShadow(directionalShadowMap[0], ds.shadowMapSize, ds.shadowIntensity, ds.shadowBias, ds.shadowRadius, vDirectionalShadowCoord[0]);
      #endif
      float phase = exp(-1.1 * acos(clamp(dot(sunL.direction, v), -1.0, 1.0)));
      col += 2.0 * alb * RECIPROCAL_PI * sunL.color * mu0 / (mu0 + mu + 1e-4) * vis * sh * phase;
    }
  #endif
  #if NUM_SPOT_LIGHTS > 0
    for (int i = 0; i < NUM_SPOT_LIGHTS; i++) {
      SpotLight sp = spotLights[i];
      vec3 lv = sp.position + vViewPosition; float d = length(lv); vec3 l = lv / d;
      float att = getSpotAttenuation(sp.coneCos, sp.penumbraCos, dot(l, sp.direction)) * getDistanceAttenuation(d, sp.distance, sp.decay);
      float m0 = max(dot(n, l), 0.0);
      col += 2.0 * alb * RECIPROCAL_PI * sp.color * att * m0 / (m0 + mu + 1e-4);
    }
  #endif
  gl_FragColor = vec4(col, 1.0);
}`;

function grid(nx, ny, posAt, skirt) {
  const nv = nx * ny, ns = skirt ? 2 * (nx + ny) - 4 : 0, pos = new Float32Array(3 * (nv + ns)), idx = [];
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) posAt(i, j, pos, 3 * (j * nx + i));
  for (let j = 0; j + 1 < ny; j++) for (let i = 0; i + 1 < nx; i++) {
    const a = j * nx + i, b = a + 1, c = a + nx, d = c + 1;
    idx.push(a, c, b, b, c, d);
  }
  if (skirt) {   // a curtain down from the patch edge hides cracks against the coarser tile mesh
    const ring = [];
    for (let i = 0; i < nx; i++) ring.push(i);
    for (let j = 1; j < ny; j++) ring.push(j * nx + nx - 1);
    for (let i = nx - 2; i >= 0; i--) ring.push((ny - 1) * nx + i);
    for (let j = ny - 2; j > 0; j--) ring.push(j * nx);
    ring.forEach((v, k) => { pos[3 * (nv + k)] = pos[3 * v]; pos[3 * (nv + k) + 1] = pos[3 * v + 1] - skirt; pos[3 * (nv + k) + 2] = pos[3 * v + 2]; });
    for (let k = 0; k < ring.length; k++) { const a = ring[k], b = ring[(k + 1) % ring.length], c = nv + k, d = nv + (k + 1) % ring.length; idx.push(a, c, b, b, c, d); }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setIndex(pos.length / 3 > 65535 ? new THREE.Uint32BufferAttribute(idx, 1) : new THREE.Uint16BufferAttribute(idx, 1));
  g.computeVertexNormals();
  return g;
}

/* createLunarTerrain({base: BASE + 'terrain/hero/', renderer, site, tier}) -> {group, origin, heightAt(x, z), setSun(az, el),
   setScour(o), profileAt(x, z, eyeM), material, dispose}. Throws when the v2 assets are missing (pages fall back). */
export async function createLunarTerrain({ base, renderer, site = 'PAD_A', tier = 2, farStride = 0, onAssets = () => {} }) {
  const [tile, v2] = await Promise.all([loadTerrain(base), loadTerrainV2(base + 'v2/', { sites: [site] })]);   // only this site's 5 m patch
  const patch = v2.patches.find(p => p.site === site);
  if (!patch || !patch.height) throw new Error(`terrain v2: no 5 m patch for ${site}`);
  const r = await fetch(base + 'v2/' + patch.height.file);
  if (!r.ok) throw new Error(`${patch.height.file}: HTTP ${r.status}`);
  const hp = await decodePngGray(await r.arrayBuffer(), 16), enc = patch.height.encoding;
  const [x0, y0, x1, y1] = patch.bounds, n = hp.width, post = (x1 - x0) / n;
  const h5 = new Float32Array(n * n);
  for (let i = 0; i < n * n; i++) h5[i] = enc.z_offset_m + enc.z_scale_m_per_unit * hp.data[i];
  const at5 = (c, rr) => h5[Math.min(n - 1, Math.max(0, rr)) * n + Math.min(n - 1, Math.max(0, c))];
  const height5 = (x, y) => {
    const fc = (x - x0) / post - 0.5, fr = (y1 - y) / post - 0.5, c0 = Math.floor(fc), r0 = Math.floor(fr), tx = fc - c0, ty = fr - r0;
    return (at5(c0, r0) * (1 - tx) + at5(c0 + 1, r0) * tx) * (1 - ty) + (at5(c0, r0 + 1) * (1 - tx) + at5(c0 + 1, r0 + 1) * tx) * ty;
  };
  const inPatch = (x, y) => x >= x0 && x <= x1 && y >= y0 && y <= y1;
  const heightLocal = (x, y) => (inPatch(x, y) ? height5(x, y) : tile.height(x, y));
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, z0 = height5(cx, cy);
  const [W, H] = tile.sizeM;

  const uniforms = THREE.UniformsUtils.merge([THREE.UniformsLib.lights]);
  Object.assign(uniforms, {
    uTile: { value: new THREE.Vector4(cx, cy, W, H) },
    uN20: { value: v2.normal }, uN5: { value: patch.tex }, uPatch: { value: new THREE.Vector4(x0, y0, x1, y1) }, uUsePatch: { value: 1 },
    uHorizon: { value: v2.tex }, uUseHz: { value: 0 }, uHzW: { value: 0 }, uSunElDeg: { value: 1.5 }, uSunRadDeg: { value: SUN_RADIUS_DEG },
    uAlbedo: { value: 0.12 }, uAmbient: { value: new THREE.Color(0.06, 0.06, 0.063) },   // shadows: bounce from sunlit slopes
    uScour: { value: new THREE.Vector4(0, 0, 5, 50) }, uScourAmt: { value: 0 }, uScourSeed: { value: 1 }, uDetail: { value: 1 },
    uHzOn: { value: 1 }, uCraterVar: { value: 0 },
  });
  const material = new THREE.ShaderMaterial({ vertexShader: vert, fragmentShader: frag, uniforms, lights: true, side: THREE.DoubleSide });
  material.name = 'lunar-terrain';

  const group = new THREE.Group(); group.name = 'lunar-terrain';
  const ps = tier >= 2 ? 1 : 2, np = Math.floor(n / ps);
  const patchGeo = grid(np, np, (i, j, pos, k) => {
    const x = x0 + (i * ps + 0.5) * post, y = y1 - (j * ps + 0.5) * post;
    pos[k] = x - cx; pos[k + 1] = height5(x, y) - z0; pos[k + 2] = cy - y;
  }, 30);
  const fs = farStride || (tier >= 2 ? 4 : 8), nf = Math.floor(tile.cols / fs), fpost = tile.postM * fs;
  const farGeo = grid(nf, nf, (i, j, pos, k) => {
    const x = (i + 0.5) * fpost, y = H - (j + 0.5) * fpost;
    pos[k] = x - cx; pos[k + 1] = tile.height(x, y) - z0 - (inPatch(x, y) ? 40 : 0); pos[k + 2] = cy - y;
  }, 0);
  for (const [g, name] of [[patchGeo, 'terrain-5m'], [farGeo, 'terrain-20m']]) {
    const m = new THREE.Mesh(g, material); m.name = name; m.receiveShadow = true; m.userData.noPick = true; group.add(m);
  }

  let lastSun = [135, 1.5];
  // float textures filter linearly only with OES_texture_float_linear (desktop GPUs have it; some phones do not)
  if (!renderer?.extensions.has('OES_texture_float_linear')) v2.tex.magFilter = v2.tex.minFilter = THREE.NearestFilter;
  function setSun(az, el) {
    lastSun = [az, el];
    uniforms.uSunElDeg.value = el;
    const { k0, k1, w } = v2.sectorsFor(az);
    uniforms.uHzW.value = w;
    if (v2.loaded === `${k0},${k1}`) { uniforms.uUseHz.value = 1; return; }
    uniforms.uUseHz.value = 0;   // lit by the normals alone until these sectors arrive
    v2.load(k0, k1).then(ok => { if (ok) { setSun(...lastSun); onAssets('horizon'); } }).catch(e => onAssets(`horizon map unavailable (${e.message})`));
  }

  // the horizon-map sun shadow for standard materials (rocks, vehicles); chained after any existing patch (the kit's dust).
  // The map holds the horizon 1 m above the ground, so a page switches it off for a vehicle high in the air
  // (material.userData.hzSelf.value = 0; see setHorizonShade).
  const HZ_KEYS = ['uTile', 'uHorizon', 'uUseHz', 'uHzW', 'uSunElDeg', 'uSunRadDeg', 'uHzOn'];
  function shadeWithHorizon(m) {
    if (m.userData.hzPatched) return m;
    const prev = m.onBeforeCompile, key = m.customProgramCacheKey?.() || '';
    m.onBeforeCompile = (shader, r) => {
      prev?.call(m, shader, r);
      for (const k of HZ_KEYS) shader.uniforms[k] = uniforms[k];
      shader.uniforms.uHzSelf = m.userData.hzSelf;
      shader.vertexShader = shader.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vHzW;')
        .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\n{ vec4 q = vec4(transformed, 1.0);\n#ifdef USE_INSTANCING\n  q = instanceMatrix * q;\n#endif\n  vHzW = (modelMatrix * q).xyz; }');
      shader.fragmentShader = shader.fragmentShader
        .replace('#include <common>', '#include <common>\nvarying vec3 vHzW; uniform vec4 uTile; uniform sampler2D uHorizon; uniform float uUseHz, uHzW, uSunElDeg, uSunRadDeg, uHzOn, uHzSelf;')
        .replace('#include <lights_fragment_end>', '#include <lights_fragment_end>\nif (uUseHz * uHzOn * uHzSelf > 0.5) {\n  vec2 xy = vec2(vHzW.x + uTile.x, uTile.y - vHzW.z), hz = texture2D(uHorizon, vec2(xy.x / uTile.z, 1.0 - xy.y / uTile.w)).rg;\n  float vis = smoothstep(-uSunRadDeg, uSunRadDeg, uSunElDeg - mix(hz.r, hz.g, uHzW));\n  reflectedLight.directDiffuse *= vis; reflectedLight.directSpecular *= vis;\n}');
    };
    m.customProgramCacheKey = () => key + '|hz';
    m.userData.hzPatched = true; m.userData.hzSelf = { value: 1 }; m.needsUpdate = true;
    return m;
  }

  // seeded rocks and boulders round a scene point: sizes from a power law (many 0.1-0.3 m stones, a few 1-2 m boulders),
  // a fifth of each buried, none on the cleared pad (representative: LOLA cannot resolve them)
  function scatterRocks({ count = 4000, x = 0, z = 0, radius = 250, clearM = 15, seed = 7 } = {}) {
    let a = seed >>> 0;
    const rnd = () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
    const geo = new THREE.IcosahedronGeometry(1, 1), p = geo.attributes.position;
    for (let i = 0; i < p.count; i++) { const k = 0.75 + 0.5 * rnd(); p.setXYZ(i, p.getX(i) * k, p.getY(i) * k * 0.7, p.getZ(i) * k); }
    geo.computeVertexNormals();
    const mat = shadeWithHorizon(new THREE.MeshStandardMaterial({ color: new THREE.Color(0.15, 0.147, 0.14), roughness: 0.95, metalness: 0, name: 'rock (representative)' }));
    const mesh = new THREE.InstancedMesh(geo, mat, count), M = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), v = new THREE.Vector3(), sc = new THREE.Vector3();
    let n = 0;
    for (let i = 0; i < count * 3 && n < count; i++) {
      const r = radius * Math.sqrt(rnd()), th = 2 * Math.PI * rnd(), px = x + r * Math.cos(th), pz = z + r * Math.sin(th);
      if (r < clearM) continue;
      const d = Math.min(2.0, 0.08 * Math.pow(1 - rnd(), -1 / 2.5));   // diameter, m
      e.set(rnd() * 6.28, rnd() * 6.28, rnd() * 6.28); q.setFromEuler(e);
      sc.set(d / 2 * (0.8 + 0.4 * rnd()), d / 2, d / 2 * (0.8 + 0.4 * rnd()));
      v.set(px, heightLocal(px + cx, cy - pz) - z0 + 0.3 * d / 2, pz);
      mesh.setMatrixAt(n++, M.compose(v, q, sc));
    }
    mesh.count = n; mesh.instanceMatrix.needsUpdate = true; mesh.computeBoundingSphere();
    mesh.castShadow = true; mesh.receiveShadow = true; mesh.name = 'rocks'; mesh.userData = { noPick: true, representative: true };
    return mesh;
  }

  return {
    group, material, site, origin: { x: cx, y: cy, z: z0 }, patchBounds: [x0 - cx, cy - y1, x1 - cx, cy - y0],
    triangles: (patchGeo.index.count + farGeo.index.count) / 3,
    // ground height (scene y) at scene x, z
    heightAt: (x, z) => heightLocal(x + cx, cy - z) - z0,
    // height of the drawn surface (the coarse tile mesh outside the patch), so things placed on it neither float nor sink
    surfaceAt(x, z) {
      const lx = x + cx, ly = cy - z;
      if (inPatch(lx, ly)) return height5(lx, ly) - z0;
      const fc = lx / fpost - 0.5, fr = (H - ly) / fpost - 0.5, c0 = Math.max(0, Math.min(nf - 2, Math.floor(fc))), r0 = Math.max(0, Math.min(nf - 2, Math.floor(fr)));
      const tx = Math.max(0, Math.min(1, fc - c0)), ty = Math.max(0, Math.min(1, fr - r0)), hp = (c, r) => tile.height((c + 0.5) * fpost, H - (r + 0.5) * fpost);
      return (hp(c0, r0) * (1 - tx) + hp(c0 + 1, r0) * tx) * (1 - ty) + (hp(c0, r0 + 1) * (1 - tx) + hp(c0 + 1, r0 + 1) * tx) * ty - z0;
    },
    // scene point of a terrain-pack point (x east, y north, z height)
    toScene: (x, y, z) => [x - cx, z - z0, cy - y],
    setSun,
    // the landing's scour mark: centre (scene x, z), inner and outer radius (m), amount 0..1, pattern seed
    setScour({ x = 0, z = 0, rIn = 5, rOut = 50, amount = 0, seed = 1 } = {}) {
      uniforms.uScour.value.set(x, z, rIn, rOut); uniforms.uScourAmt.value = amount; uniforms.uScourSeed.value = seed % 997;
    },
    setAmbient(c) { uniforms.uAmbient.value.copy(c); },
    setDetail(on) { uniforms.uDetail.value = on ? 1 : 0; },
    // 1: varied crater depth, shape and rotation, and fewer small craters close to the camera (rover chase views)
    setCraterVariety(v) { uniforms.uCraterVar.value = v; },
    // the horizon-map sun visibility (0..1) at scene x, z, as the shader computes it (nearest texel); null until the map
    // for the current sun has loaded
    sunAt(x, z) {
      if (uniforms.uUseHz.value < 0.5) return null;
      const img = v2.tex.image, w2 = img.width, h2 = img.height, u = (x + cx) / W, v = 1 - (cy - z) / H;
      const i = Math.min(w2 - 1, Math.max(0, Math.floor(u * w2))), j = Math.min(h2 - 1, Math.max(0, Math.floor(v * h2))), k = 2 * (j * w2 + i), w = uniforms.uHzW.value;
      const d = uniforms.uSunElDeg.value - (img.data[k] * (1 - w) + img.data[k + 1] * w), r = uniforms.uSunRadDeg.value, t = Math.min(1, Math.max(0, (d + r) / (2 * r)));
      return t * t * (3 - 2 * t);
    },
    // night: the sun is off, so the horizon shadow must not dim headlight light on patched materials
    setNight(on) { uniforms.uHzOn.value = on ? 0 : 1; },
    shadeWithHorizon, scatterRocks,
    // horizon shading on or off for every patched material under an object (off while a lander is high up)
    setHorizonShade(root, on) { root.traverse(o => { const s = o.material?.userData?.hzSelf; if (s) s.value = on ? 1 : 0; }); },
    // horizon elevation (deg) all round a scene point, for the sky's Earth and star cut-off
    profileAt: (x, z, eyeM = 1.5) => horizonProfile(tile, x + cx, cy - z, { eyeM }),
    dispose() { patchGeo.dispose(); farGeo.dispose(); material.dispose(); v2.normal.dispose(); v2.tex.dispose(); for (const p of v2.patches) p.tex.dispose(); },
  };
}

