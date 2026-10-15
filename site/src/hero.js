// Landing-page hero: the LOLA terrain tile under a grazing polar sun (PLAN 5.7).
// Shading: Lommel-Seeliger regolith photometry from a precomputed normal map (three.js cannot recompute normals of a
// displaced plane); shadows: a ray march through the heightfield toward the sun with a 0.53-degree solar disk penumbra.
// No ambient term, so ground the sun cannot see stays black, as permanently shadowed crater floors are.
// Motion: the sun sweeps in azimuth; pause button (WCAG 2.2.2), starts paused under prefers-reduced-motion,
// stops while off-screen or in a hidden tab. Draws only when the sun moves or the canvas resizes.
import {
  WebGLRenderer, Scene, PerspectiveCamera, BufferGeometry, BufferAttribute, Mesh, ShaderMaterial, DataTexture,
  RedFormat, RGBAFormat, FloatType, UnsignedByteType, NearestFilter, LinearFilter, Vector3, Color, GLSL3,
} from 'three';
import { loadTerrain } from './terrain.js';

const SUN_EL_DEG = 1.5;          // NASA SVS 4893: at the pole the Sun is never more than ~1.5 deg above the horizon
const SUN_RADIUS_DEG = 0.267;    // apparent solar radius
const SWEEP_S = 120;             // seconds per full azimuth turn on screen (the real turn takes one lunar day)
const PIXEL_BUDGET = 5.2e6;      // drawing-buffer cap in device pixels
const MESH_N = 500;              // mesh segments per side; shading uses the full-resolution normal map

const vert = /* glsl */`
out vec2 vUv; out vec3 vPos;
uniform vec2 uSize;
void main() {
  vUv = vec2(position.x / uSize.x, position.z / uSize.y);
  vPos = position;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

const frag = /* glsl */`
precision highp float; precision highp sampler2D;
in vec2 vUv; in vec3 vPos; out vec4 outColor;
uniform sampler2D uHeight; uniform sampler2D uNormal;
uniform vec2 uSize; uniform ivec2 uTex; uniform vec3 uSun; uniform vec3 uCam; uniform float uAlbedo; uniform float uSunRad;
float hAt(vec2 uv) {  // nearest post; outside the tile nothing occludes (we have no data there)
  ivec2 p = ivec2(floor(uv * vec2(uTex)));
  if (p.x < 0 || p.y < 0 || p.x >= uTex.x || p.y >= uTex.y) return -1e9;
  return texelFetch(uHeight, p, 0).r;
}
void main() {
  vec3 n = normalize(texture(uNormal, vUv).xyz * 2.0 - 1.0);
  vec3 v = normalize(uCam - vPos);
  float ci = dot(n, uSun), ce = max(dot(n, v), 0.0);
  float lit = ci > 0.0 ? ci / (ci + ce + 1e-4) : 0.0;           // Lommel-Seeliger
  // shadow: march toward the sun; keep the smallest elevation angle of the horizon above the ray origin
  float sunEl = asin(clamp(uSun.y, -1.0, 1.0));
  vec2 dirM = normalize(uSun.xz);                                // metres per metre in (x east, z south)
  vec2 dirUv = dirM / uSize;
  float h0 = vPos.y + 1.0, d = uSize.x / float(uTex.x), maxAng = -1.0;
  for (int i = 0; i < 96; i++) {
    float hh = hAt(vUv + dirUv * d);
    if (hh > -1e8) maxAng = max(maxAng, atan(hh - h0, d));
    d *= 1.078;                                                  // geometric steps: 16 m out to ~22 km
  }
  float vis = smoothstep(-uSunRad, uSunRad, sunEl - maxAng);      // fraction of the solar disk above the horizon
  float c = uAlbedo * lit * vis * 3.2;
  c = pow(c / (1.0 + c), 1.0 / 2.2);                             // simple tone curve + gamma
  outColor = vec4(vec3(c) * vec3(1.0, 0.985, 0.96), 1.0);
}`;

function normalMap(t) {
  const { cols: w, rows: h, postM: d } = t, out = new Uint8Array(w * h * 4);
  for (let r = 0; r < h; r++) for (let c = 0; c < w; c++) {
    const dx = (t.at(c + 1, r) - t.at(c - 1, r)) / (2 * d), dz = (t.at(c, r + 1) - t.at(c, r - 1)) / (2 * d);  // z = south
    const nx = -dx, ny = 1, nz = -dz, L = Math.hypot(nx, ny, nz), i = 4 * (r * w + c);
    out[i] = Math.round((nx / L * 0.5 + 0.5) * 255); out[i + 1] = Math.round((ny / L * 0.5 + 0.5) * 255); out[i + 2] = Math.round((nz / L * 0.5 + 0.5) * 255); out[i + 3] = 255;
  }
  const tex = new DataTexture(out, w, h, RGBAFormat, UnsignedByteType); tex.magFilter = tex.minFilter = LinearFilter; tex.needsUpdate = true;
  return tex;
}

function meshGeometry(t) {
  const [W, H] = t.sizeM, n = MESH_N, pos = new Float32Array((n + 1) * (n + 1) * 3);
  for (let j = 0; j <= n; j++) for (let i = 0; i <= n; i++) {
    const x = W * i / n, z = H * j / n, k = 3 * (j * (n + 1) + i);
    pos[k] = x; pos[k + 1] = t.height(x, H - z); pos[k + 2] = z;     // z grows south; terrain y grows north
  }
  const idx = new Uint32Array(n * n * 6); let p = 0;
  for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) {
    const a = j * (n + 1) + i, b = a + 1, c = a + n + 1, d = c + 1;
    idx[p++] = a; idx[p++] = c; idx[p++] = b; idx[p++] = b; idx[p++] = c; idx[p++] = d;
  }
  const g = new BufferGeometry(); g.setAttribute('position', new BufferAttribute(pos, 3)); g.setIndex(new BufferAttribute(idx, 1));
  return g;
}

export async function startHero({ root, canvas, pauseBtn, slider, readout, terrainUrl, onReady }) {
  const terrain = await loadTerrain(terrainUrl);
  let renderer;
  try { renderer = new WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' }); }
  catch (e) { throw new Error('WebGL2 is not available'); }
  renderer.setClearColor(new Color(0x050506));
  const [W, H] = terrain.sizeM;
  const hTex = new DataTexture(terrain.heights, terrain.cols, terrain.rows, RedFormat, FloatType);
  hTex.magFilter = hTex.minFilter = NearestFilter; hTex.needsUpdate = true;
  const sun = new Vector3(), camera = new PerspectiveCamera(36, 1, 50, 200000);
  const mat = new ShaderMaterial({
    glslVersion: GLSL3, vertexShader: vert, fragmentShader: frag,
    uniforms: { uHeight: { value: hTex }, uNormal: { value: normalMap(terrain) }, uSize: { value: [W, H] }, uTex: { value: [terrain.cols, terrain.rows] },
      uSun: { value: sun }, uCam: { value: camera.position }, uAlbedo: { value: 0.12 }, uSunRad: { value: SUN_RADIUS_DEG * Math.PI / 180 } },
  });
  const scene = new Scene(); scene.add(new Mesh(meshGeometry(terrain), mat));
  // oblique view across the tile from its south edge
  const relief = terrain.zMax - terrain.zMin;
  camera.position.set(W * 0.5, terrain.zMax + relief * 1.6 + 2500, H * 1.32);
  camera.lookAt(W * 0.5, terrain.zMin + relief * 0.25, H * 0.42);

  const reduce = matchMedia('(prefers-reduced-motion: reduce)');
  const state = { az: 135, playing: !reduce.matches, visible: true, last: 0, raf: 0, dirty: true };
  const setSun = az => {
    state.az = ((az % 360) + 360) % 360;
    const el = SUN_EL_DEG * Math.PI / 180, a = state.az * Math.PI / 180;
    sun.set(Math.sin(a) * Math.cos(el), Math.sin(el), -Math.cos(a) * Math.cos(el));   // grid north = -z
    slider.value = String(Math.round(state.az));
    readout.textContent = `sun ${String(Math.round(state.az)).padStart(3, '0')}° grid azimuth · ${SUN_EL_DEG.toFixed(1)}° elevation`;
    state.dirty = true;
  };
  const resize = () => {
    const w = canvas.clientWidth, h = canvas.clientHeight; if (!w || !h) return;
    renderer.setPixelRatio(Math.min(devicePixelRatio || 1, Math.sqrt(PIXEL_BUDGET / (w * h))));
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); state.dirty = true;
  };
  const frame = now => {
    state.raf = 0;
    if (state.playing && state.visible) { if (state.last) setSun(state.az + 360 * (now - state.last) / 1000 / SWEEP_S); state.last = now; }
    if (state.dirty) { renderer.render(scene, camera); state.dirty = false; }
    if (state.playing && state.visible) state.raf = requestAnimationFrame(frame);
  };
  const kick = () => { if (!state.raf) { state.last = 0; state.raf = requestAnimationFrame(frame); } };
  const setPlaying = p => {
    state.playing = p; pauseBtn.setAttribute('aria-pressed', String(!p));
    pauseBtn.querySelector('[data-label]').textContent = p ? 'Pause sun' : 'Play sun';
    root.classList.toggle('paused', !p); kick();
  };
  pauseBtn.addEventListener('click', () => setPlaying(!state.playing));
  slider.addEventListener('input', () => { setSun(+slider.value); kick(); });
  reduce.addEventListener?.('change', e => { if (e.matches) setPlaying(false); });
  new ResizeObserver(() => { resize(); kick(); }).observe(canvas);
  new IntersectionObserver(es => { state.visible = es[0].isIntersecting && !document.hidden; kick(); }).observe(canvas);
  document.addEventListener('visibilitychange', () => { state.visible = !document.hidden; kick(); });
  setSun(state.az); resize(); setPlaying(state.playing);
  if (import.meta.env.DEV) window.__hero = { renderer, scene, camera, mat, setSun, state };  // dev-only probe for checks
  onReady && onReady(terrain);
  return { terrain, setPlaying };
}
