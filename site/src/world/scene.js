// three.js scene for /world: LOLA terrain lit by the grazing polar sun, the site layout, representative vehicles,
// landers, plume keep-out rings and cargo rings. Terrain shadows are baked into a sun-visibility texture (one
// ray-march pass over the heightmap whenever the sun moves > 0.25 deg) so the per-frame cost is a texture lookup.
import {
  WebGLRenderer, Scene, PerspectiveCamera, BufferGeometry, BufferAttribute, Mesh, ShaderMaterial, DataTexture, RedFormat,
  RGBAFormat, FloatType, UnsignedByteType, NearestFilter, LinearFilter, Vector3, Color, GLSL3, WebGLRenderTarget,
  OrthographicCamera, PlaneGeometry, Group, BoxGeometry, CylinderGeometry, MeshBasicMaterial, LineBasicMaterial, LineSegments,
  LineLoop, Line, RingGeometry, DoubleSide, Vector2,
} from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { DESCENT_S, DESCENT_FROM_M } from './state.js';

const SUN_EL_DEG = 1.5, SUN_RADIUS_DEG = 0.267, LUNAR_DAY_H = 29.53 * 24, MESH_N = 400, MAX_LIGHTS = 12;
import { OWNER_COLOURS, EXTRA_COLOURS } from './colours.js';

// world axes: X = east (local x), Y = up (metres), Z = south (= -local y)
const W3 = (x, y, z) => new Vector3(x, z, -y);

const visFrag = /* glsl */`
precision highp float; precision highp sampler2D;
in vec2 vUv; out vec4 outColor;
uniform sampler2D uHeight; uniform ivec2 uTex; uniform float uPost; uniform vec2 uSunDir; uniform float uSunEl; uniform float uSunRad;
float hAt(ivec2 p) { if (p.x < 0 || p.y < 0 || p.x >= uTex.x || p.y >= uTex.y) return -1e9; return texelFetch(uHeight, p, 0).r; }
void main() {
  ivec2 p0 = ivec2(floor(vUv * vec2(uTex)));
  float h0 = texelFetch(uHeight, p0, 0).r + 1.0, d = uPost, maxAng = -1.0;
  for (int i = 0; i < 110; i++) {
    vec2 q = vec2(p0) + 0.5 + uSunDir * (d / uPost);
    float hh = hAt(ivec2(floor(q)));
    if (hh > -1e8) maxAng = max(maxAng, atan(hh - h0, d));
    d *= 1.07;
  }
  outColor = vec4(smoothstep(-uSunRad, uSunRad, uSunEl - maxAng), 0.0, 0.0, 1.0);
}`;
const quadVert = /* glsl */`out vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;

const terrVert = /* glsl */`
out vec2 vUv; out vec3 vPos; uniform vec2 uSize;
void main() { vUv = vec2(position.x / uSize.x, position.z / uSize.y + 1.0); vPos = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const terrFrag = /* glsl */`
precision highp float;
in vec2 vUv; in vec3 vPos; out vec4 outColor;
uniform sampler2D uNormal; uniform sampler2D uVis; uniform vec3 uSun; uniform vec3 uCam; uniform float uDay; uniform float uAmbient;
uniform vec3 uLights[${MAX_LIGHTS}]; uniform vec2 uLightDir[${MAX_LIGHTS}]; uniform int uNLights; uniform float uLightRange;
void main() {
  vec3 n = normalize(texture(uNormal, vUv).xyz * 2.0 - 1.0);
  vec3 v = normalize(uCam - vPos);
  float ci = dot(n, uSun), ce = max(dot(n, v), 0.0);
  float lit = ci > 0.0 ? ci / (ci + ce + 1e-4) : 0.0;
  float c = 0.12 * 3.2 * lit * texture(uVis, vUv).r * uDay + uAmbient;
  for (int i = 0; i < ${MAX_LIGHTS}; i++) {           // headlights: a forward cone on the ground
    if (i >= uNLights) break;
    vec3 d = vPos - uLights[i]; float dist = length(d.xz);
    float cone = smoothstep(0.55, 0.95, dot(normalize(d.xz + 1e-4), uLightDir[i]));
    c += 0.9 * cone * smoothstep(uLightRange, 0.0, dist) + 0.35 * smoothstep(uLightRange * 0.18, 0.0, dist);
  }
  c = pow(c / (1.0 + c), 1.0 / 2.2);
  outColor = vec4(vec3(c) * vec3(1.0, 0.985, 0.96), 1.0);
}`;

function normalMap(t) {
  const { cols: w, rows: h, postM: d } = t, out = new Uint8Array(w * h * 4);
  for (let r = 0; r < h; r++) for (let c = 0; c < w; c++) {
    const dx = (t.at(c + 1, r) - t.at(c - 1, r)) / (2 * d), dz = (t.at(c, r + 1) - t.at(c, r - 1)) / (2 * d);
    const L = Math.hypot(dx, 1, dz), i = 4 * (r * w + c);
    out[i] = Math.round((-dx / L * 0.5 + 0.5) * 255); out[i + 1] = Math.round((1 / L * 0.5 + 0.5) * 255); out[i + 2] = Math.round((-dz / L * 0.5 + 0.5) * 255); out[i + 3] = 255;
  }
  const tex = new DataTexture(out, w, h, RGBAFormat, UnsignedByteType); tex.magFilter = tex.minFilter = LinearFilter; tex.needsUpdate = true; return tex;
}

function terrainGeometry(t) {
  const [W, H] = t.sizeM, n = MESH_N, pos = new Float32Array((n + 1) * (n + 1) * 3);
  for (let j = 0; j <= n; j++) for (let i = 0; i <= n; i++) {
    const x = W * i / n, y = H * (1 - j / n), k = 3 * (j * (n + 1) + i);   // row j = 0 is north
    pos[k] = x; pos[k + 1] = t.height(x, y); pos[k + 2] = -y;
  }
  const idx = new Uint32Array(n * n * 6); let p = 0;
  for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) { const a = j * (n + 1) + i, b = a + 1, c = a + n + 1, d = c + 1; idx[p++] = a; idx[p++] = c; idx[p++] = b; idx[p++] = b; idx[p++] = c; idx[p++] = d; }
  const g = new BufferGeometry(); g.setAttribute('position', new BufferAttribute(pos, 3)); g.setIndex(new BufferAttribute(idx, 1)); return g;
}

const setText = (el, s) => { if (el.textContent !== s) el.textContent = s; };
function label(text, cls) { const el = document.createElement('div'); el.className = 'w-label ' + (cls || ''); el.textContent = text; const o = new CSS2DObject(el); o.center.set(0.5, 1.4); return o; }

function rover(colour, cls) {  // representative parametric stand-in, ~1 unit long; scaled per frame to a constant screen size
  const g = new Group(), m = new MeshBasicMaterial({ color: colour }), dark = new MeshBasicMaterial({ color: 0x222222 });
  const L = cls === 'HAUL' ? 1.5 : cls === 'MICRO' ? 0.6 : 1, body = new Mesh(new BoxGeometry(0.62 * L, 0.32 * L, L), m); body.position.y = 0.42 * L; g.add(body);
  for (const [x, z] of [[-0.36, -0.34], [0.36, -0.34], [-0.36, 0.34], [0.36, 0.34]]) { const w = new Mesh(new CylinderGeometry(0.16 * L, 0.16 * L, 0.12 * L, 10), dark); w.rotation.z = Math.PI / 2; w.position.set(x * L, 0.16 * L, z * L); g.add(w); }
  return { group: g, body, mat: m };
}
function lander() {
  const g = new Group(), m = new MeshBasicMaterial({ color: 0xd9d4c7 }), legM = new MeshBasicMaterial({ color: 0x8a8a8a });
  const body = new Mesh(new CylinderGeometry(0.45, 0.55, 1.1, 14), m); body.position.y = 1.0; g.add(body);
  for (let k = 0; k < 4; k++) { const a = k * Math.PI / 2 + Math.PI / 4, leg = new Mesh(new CylinderGeometry(0.04, 0.04, 0.9, 6), legM); leg.position.set(Math.cos(a) * 0.62, 0.38, Math.sin(a) * 0.62); leg.rotation.z = Math.cos(a) * 0.5; leg.rotation.x = -Math.sin(a) * 0.5; g.add(leg); }
  return g;
}
function drapedCircle(terrain, cx, cy, R, segs = 96) {
  const pts = new Float32Array(segs * 3);
  for (let i = 0; i < segs; i++) { const a = 2 * Math.PI * i / segs, x = cx + R * Math.cos(a), y = cy + R * Math.sin(a), v = W3(x, y, terrain.height(x, y) + 4); pts.set([v.x, v.y, v.z], 3 * i); }
  const g = new BufferGeometry(); g.setAttribute('position', new BufferAttribute(pts, 3)); return g;
}

export function createScene({ canvas, labelHost, terrain, layout, pixelBudget = 5.2e6 }) {
  const renderer = new WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
  renderer.setClearColor(new Color(0x050506));
  const css = new CSS2DRenderer({ element: labelHost });
  const [W, H] = terrain.sizeM, scene = new Scene();
  const camera = new PerspectiveCamera(40, 1, 5, 120000);
  const controls = new OrbitControls(camera, canvas); controls.enableDamping = true; controls.maxPolarAngle = Math.PI * 0.49; controls.minDistance = 150; controls.maxDistance = 40000;

  // --- terrain + baked sun visibility
  const hTex = new DataTexture(terrain.heights, terrain.cols, terrain.rows, RedFormat, FloatType); hTex.magFilter = hTex.minFilter = NearestFilter; hTex.needsUpdate = true;
  const visRT = new WebGLRenderTarget(terrain.cols, terrain.rows, { magFilter: LinearFilter, minFilter: LinearFilter, depthBuffer: false });
  const visMat = new ShaderMaterial({ glslVersion: GLSL3, vertexShader: quadVert, fragmentShader: visFrag, depthTest: false,
    uniforms: { uHeight: { value: hTex }, uTex: { value: [terrain.cols, terrain.rows] }, uPost: { value: terrain.postM }, uSunDir: { value: new Vector2() }, uSunEl: { value: SUN_EL_DEG * Math.PI / 180 }, uSunRad: { value: SUN_RADIUS_DEG * Math.PI / 180 } } });
  const visScene = new Scene(); visScene.add(new Mesh(new PlaneGeometry(2, 2), visMat)); const visCam = new OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const lights = Array.from({ length: MAX_LIGHTS }, () => new Vector3()), lightDir = Array.from({ length: MAX_LIGHTS }, () => new Vector2());
  const sun = new Vector3();
  const terrMat = new ShaderMaterial({ glslVersion: GLSL3, vertexShader: terrVert, fragmentShader: terrFrag,
    uniforms: { uNormal: { value: normalMap(terrain) }, uVis: { value: visRT.texture }, uSize: { value: [W, H] }, uSun: { value: sun }, uCam: { value: camera.position },
      uDay: { value: 1 }, uAmbient: { value: 0 }, uLights: { value: lights }, uLightDir: { value: lightDir }, uNLights: { value: 0 }, uLightRange: { value: 420 } } });
  scene.add(new Mesh(terrainGeometry(terrain), terrMat));
  let bakedAz = null;
  function setSun(azDeg, day) {
    const a = azDeg * Math.PI / 180, el = SUN_EL_DEG * Math.PI / 180;
    sun.set(Math.sin(a) * Math.cos(el), Math.sin(el), -Math.cos(a) * Math.cos(el));
    terrMat.uniforms.uDay.value = day ? 1 : 0; terrMat.uniforms.uAmbient.value = day ? 0 : 0.006;   // night: faint earthshine
    if (bakedAz === null || Math.abs(((azDeg - bakedAz + 540) % 360) - 180) > 0.25) {
      visMat.uniforms.uSunDir.value.set(Math.sin(a), Math.cos(a));   // heightmap texels: +col east, +row south -> north = -row
      visMat.uniforms.uSunDir.value.y = -Math.cos(a);
      renderer.setRenderTarget(visRT); renderer.render(visScene, visCam); renderer.setRenderTarget(null); bakedAz = azDeg;
    }
  }

  // --- layout: legs, sites, pads
  const legPts = []; for (const e of layout.edges) for (let i = 0; i + 1 < e.length; i++) { const a = W3(e[i][0], e[i][1], e[i][2] + 1), b = W3(e[i + 1][0], e[i + 1][1], e[i + 1][2] + 1); legPts.push(a.x, a.y, a.z, b.x, b.y, b.z); }
  const legGeo = new BufferGeometry(); legGeo.setAttribute('position', new BufferAttribute(new Float32Array(legPts), 3));
  scene.add(new LineSegments(legGeo, new LineBasicMaterial({ color: 0x9ec5f4, transparent: true, opacity: 0.45 })));
  const siteObj = {}, ringObj = {};
  for (const name of layout.names) {
    const [x, y] = layout.pos[name], z = layout.z(name), pad = layout.kinds[name] === 'pad';
    const marker = new Mesh(pad ? new BoxGeometry(1.6, 0.25, 1.6) : new CylinderGeometry(0.5, 0.5, 0.25, 20), new MeshBasicMaterial({ color: pad ? 0x66CCEE : name === 'BASE' ? 0xffffff : 0xbbbbbb }));
    const g = new Group(); g.add(marker); g.position.copy(W3(x, y, z + 1)); const lab = label(name.replace('_', ' '), pad ? 'pad' : ''); lab.position.set(0, 2, 0); g.add(lab);
    scene.add(g); siteObj[name] = g;
    const ring = new Mesh(new RingGeometry(0.85, 1, 48), new MeshBasicMaterial({ color: 0xffffff, side: DoubleSide, transparent: true, opacity: 0.9 }));
    ring.rotation.x = -Math.PI / 2; ring.position.copy(W3(x, y, z + 3)); ring.visible = false; scene.add(ring); ringObj[name] = ring;
  }

  // --- vehicles, landers, plume rings (created on setTrace)
  let vehObj = new Map(), landerPool = [], plumePool = [];
  const dyn = new Group(); scene.add(dyn);
  function setTrace(tr) {
    dyn.traverse(o => { if (o.isCSS2DObject) o.element.remove(); });   // CSS2DRenderer leaves removed labels in the DOM
    dyn.clear(); vehObj = new Map(); landerPool = []; plumePool = [];
    const owners = [...new Set(tr.vehicles.map(v => v.owner))];
    tr.vehicles.forEach(v => {
      const col = OWNER_COLOURS[v.owner] || EXTRA_COLOURS[owners.indexOf(v.owner) % EXTRA_COLOURS.length];
      const r = rover(col, v.cls); const lab = label(`${v.cls} ${v.id}`, 'veh'); lab.position.set(0, 1.6, 0); r.group.add(lab);
      dyn.add(r.group); vehObj.set(v.id, { ...r, colour: col });
    });
  }
  function landerObj(i) {
    while (landerPool.length <= i) { const g = lander(), lab = label('', 'lander'); lab.position.set(0, 2.4, 0); g.add(lab); dyn.add(g); landerPool.push({ g, lab }); }
    return landerPool[i];
  }
  function plumeObj(i) {
    while (plumePool.length <= i) { const line = new LineLoop(new BufferGeometry(), new LineBasicMaterial({ color: 0xCCBB44 })); const lab = label('', 'plume'); const holder = new Group(); holder.add(lab); dyn.add(line); dyn.add(holder); plumePool.push({ line, lab, holder, key: null }); }
    return plumePool[i];
  }

  // screen-size scaling: an object of 1 unit spans ~px pixels
  const tmp = new Vector3();
  const pxScale = (p, px) => { const d = camera.position.distanceTo(p), h = 2 * d * Math.tan(camera.fov * Math.PI / 360); return px * h / Math.max(1, renderer.domElement.clientHeight); };

  function update(tr, snap, opts) {
    // sun: one turn per lunar day; night windows switch the sun off
    setSun(((snap.t / LUNAR_DAY_H) * 360 + 135) % 360, !snap.night);
    let nl = 0;
    for (const s of snap.vehicles) {
      const o = vehObj.get(s.id); if (!o) continue;
      const [x, y, z, hd] = layout.along(s.from, s.to, s.f), p = W3(x, y, z);
      if (s.from === s.to) {   // parked or handling: fan vehicles out around the site so they do not overlap
        const here = snap.vehicles.filter(q => q.from === q.to && q.to === s.to), k = here.indexOf(s), n = here.length;
        if (n > 1) { const a = 2 * Math.PI * k / n, r = pxScale(p, 22); p.x += r * Math.cos(a); p.z += r * Math.sin(a); }
      }
      o.group.position.copy(p); if (s.from !== s.to) o.group.rotation.y = -hd + Math.PI;
      o.group.scale.setScalar(pxScale(p, 16));
      o.mat.color.set(s.status === 'stranded-night' ? '#ffffff' : o.colour);
      setText(o.group.children.find(c => c.isCSS2DObject).element, opts.labels ? `${tr.vehicles.find(v => v.id === s.id).cls} ${s.id}${s.loadKg > 0 ? ' · ' + Math.round(s.loadKg) + ' kg' : ''}` : '');
      if (snap.night && nl < MAX_LIGHTS && s.status !== 'parked-night') { lights[nl].copy(p); lightDir[nl].set(Math.sin(hd), -Math.cos(hd)); nl++; }
    }
    terrMat.uniforms.uNLights.value = nl;
    for (const name of layout.names) {
      const w = snap.waiting[name], r = ringObj[name]; r.visible = !!w;
      if (w) { const base = pxScale(r.position, 18 + Math.min(40, 3 * w.n)); r.scale.setScalar(base); }
      siteObj[name].children[0].scale.setScalar(pxScale(siteObj[name].position, 12));
    }
    // landers
    snap.landers.forEach((L, i) => {
      const o = landerObj(i), l = L.landing, padXY = l.xy || layout.pos[l.pad];
      let x = padXY[0], y = padXY[1], alt = 0;
      if (L.phase === 'descent') {
        if (l.descent) { const d = l.descent, tt = d[0][0] + L.fDescent * (d[d.length - 1][0] - d[0][0]); let k = 0; while (k + 1 < d.length && d[k + 1][0] < tt) k++; const a = d[k], b = d[Math.min(k + 1, d.length - 1)], f = b[0] > a[0] ? (tt - a[0]) / (b[0] - a[0]) : 0;
          const ax = a[1] + (b[1] - a[1]) * f, ay = a[2] + (b[2] - a[2]) * f, az = a[3] + (b[3] - a[3]) * f;
          if (Math.abs(ax) < 2000 && Math.abs(ay) < 2000) { x = padXY[0] + ax; y = padXY[1] + ay; } else { x = ax; y = ay; } alt = az; }
        else alt = DESCENT_FROM_M * (1 - L.fDescent);
      }
      const p = W3(x, y, terrain.height(x, y) + alt); o.g.position.copy(p); o.g.scale.setScalar(pxScale(p, 16)); o.g.visible = true;
      setText(o.lab.element, L.phase === 'descent' ? `${l.type} · ${Math.round(alt)} m · T−${Math.max(0, L.secToTouchdown).toFixed(0)} s` : `${l.type} landed${l.miss !== null ? ' · miss ' + Math.round(l.miss) + ' m' : ''}${l.ok ? '' : ' · failed' + (l.failureKind ? ' (' + l.failureKind + ')' : '')}`);
    });
    for (let i = snap.landers.length; i < landerPool.length; i++) landerPool[i].g.visible = false;
    // plume keep-out rings with stand-down countdown
    snap.plume.forEach((pw, i) => {
      const o = plumeObj(i), xy = layout.pos[pw.pad], key = pw.pad + '|' + pw.R_m;
      if (o.key !== key) { o.line.geometry.dispose(); o.line.geometry = drapedCircle(terrain, xy[0], xy[1], pw.R_m); o.key = key; o.holder.position.copy(W3(xy[0], xy[1] + pw.R_m, terrain.height(xy[0], xy[1] + pw.R_m) + 30)); }
      o.line.visible = o.holder.visible = true; setText(o.lab.element, `keep-out ${(pw.R_m / 1000).toFixed(1)} km · stand-down ends in ${(pw.t1 - snap.t).toFixed(1)} h`);
    });
    for (let i = snap.plume.length; i < plumePool.length; i++) { plumePool[i].line.visible = false; plumePool[i].holder.visible = false; }
  }

  // camera presets and follow
  let follow = null, tween = null;
  function frameOn(target, dist, elevDeg = 32, azDeg = 200, animate = true) {
    const a = azDeg * Math.PI / 180, e = elevDeg * Math.PI / 180;
    const to = target.clone().add(new Vector3(Math.sin(a) * Math.cos(e), Math.sin(e), Math.cos(a) * Math.cos(e)).multiplyScalar(dist));
    if (!animate) { camera.position.copy(to); controls.target.copy(target); controls.update(); tween = null; return; }
    tween = { p0: camera.position.clone(), t0: controls.target.clone(), p1: to, t1: target.clone(), s: performance.now(), dur: 900 };
  }
  function preset(name, animate) {
    follow = null; const c = n => W3(layout.pos[n][0], layout.pos[n][1], layout.z(n));
    if (name === 'overview') {   // the whole site layout, from the south-south-west
      const xs = layout.names.map(n => layout.pos[n][0]), ys = layout.names.map(n => layout.pos[n][1]);
      const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2, span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
      frameOn(W3(cx, cy, terrain.height(cx, cy)), Math.max(2500, span * 1.35), 42, 200, animate);
    } else if (name === 'tile') frameOn(W3(W / 2, H / 2, terrain.zMin + (terrain.zMax - terrain.zMin) * 0.4), 19000, 48, 200, animate);
    if (name === 'base') frameOn(c('BASE'), 1800, 30, 210, animate);
    else if (name === 'pads') { const a = c('PAD_A'), b = c('PAD_B'), mid = a.clone().add(b).multiplyScalar(0.5); frameOn(mid, Math.max(1500, a.distanceTo(b) * 1.4), 40, 200, animate); }
    else if (name.startsWith('site:')) frameOn(c(name.slice(5)), 1500, 30, 210, animate);
  }
  function followVehicle(id) { follow = id; }
  function focusFollow() {
    if (follow === null) return; const o = vehObj.get(follow); if (!o) return;
    const d = o.group.position.clone().sub(controls.target); controls.target.add(d); camera.position.add(d);
  }
  controls.addEventListener('start', () => { tween = null; });

  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight; if (!w || !h) return;
    renderer.setPixelRatio(Math.min(devicePixelRatio || 1, Math.sqrt(pixelBudget / (w * h)))); renderer.setSize(w, h, false); css.setSize(w, h);
    camera.aspect = w / h; camera.updateProjectionMatrix();
  }
  function render(now) {
    if (tween) { const f = Math.min(1, (now - tween.s) / tween.dur), e = f < 0.5 ? 2 * f * f : 1 - Math.pow(-2 * f + 2, 2) / 2; camera.position.lerpVectors(tween.p0, tween.p1, e); controls.target.lerpVectors(tween.t0, tween.t1, e); if (f >= 1) tween = null; }
    focusFollow(); controls.update(); renderer.render(scene, camera); css.render(scene, camera);
  }
  return { renderer, camera, controls, setTrace, update, render, resize, preset, followVehicle, isFollowing: () => follow, dispose: () => { controls.dispose(); renderer.dispose(); renderer.forceContextLoss(); labelHost.replaceChildren(); } };
}
