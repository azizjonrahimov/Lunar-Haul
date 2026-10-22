// Lighting presets (research §1.6, §2.2). "exhibit": a dark studio stage lit by RoomEnvironment (PMREM) and a soft key
// light, for taking a vehicle apart. "onsite": the lunar south pole: black sky, one hard sun at az/el (el 1.5° by
// default), a dim environment that is only regolith bounce, a regolith ground (or a page's own lunar terrain, see
// terrain.js) and the sky (sky.js: Earth from its track, stars at a long exposure). Night: the sun off, faint earthshine.
// Directions: y up, north = -z, east = +x, azimuth clockwise from north.
import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { createSky } from './sky.js';

const DEG = Math.PI / 180;
export const EARTH_DIAMETER_DEG = 1.9;   // 12,742 km / 384,400 km (research §2.2)

export function dirFromAzEl(az, el) {
  return new THREE.Vector3(Math.sin(az * DEG) * Math.cos(el * DEG), Math.sin(el * DEG), -Math.cos(az * DEG) * Math.cos(el * DEG));
}

// Environment for on-site views: black sky; the lower hemisphere is faint grey regolith bounce, a little brighter
// towards the sun's azimuth (level ground gets sin(1.5°) ~ 2.6 % of the sun and reflects ~12 % of that).
function lunarEnvScene(sunDir) {
  const s = new THREE.Scene();
  const mat = new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false,
    uniforms: { sun: { value: new THREE.Vector2(sunDir.x, sunDir.z).normalize() } },
    vertexShader: 'varying vec3 vDir; void main() { vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: `uniform vec2 sun; varying vec3 vDir;
      void main() {
        float below = smoothstep(0.02, -0.06, vDir.y);
        float toward = max(0.0, dot(normalize(vDir.xz + 1e-5), sun));
        vec3 c = vec3(0.010 + 0.030 * toward * toward) * below;
        gl_FragColor = vec4(c, 1.0);
      }`,
  });
  s.add(new THREE.Mesh(new THREE.SphereGeometry(10, 48, 24), mat));
  return s;
}

// Procedural regolith ground: a gently rolling plane (seeded value noise, +-0.6 m) so slopes facing the low sun catch
// light; flagged representative detail. Size in metres.
function groundMesh(size, segments) {
  const g = new THREE.PlaneGeometry(size, size, segments, segments);
  g.rotateX(-Math.PI / 2);
  const p = g.attributes.position, rnd = (x, z) => { const s = Math.sin(x * 127.1 + z * 311.7) * 43758.5453; return s - Math.floor(s); };
  const noise = (x, z) => {
    const xi = Math.floor(x), zi = Math.floor(z), xf = x - xi, zf = z - zi, u = xf * xf * (3 - 2 * xf), v = zf * zf * (3 - 2 * zf);
    const a = rnd(xi, zi), b = rnd(xi + 1, zi), c = rnd(xi, zi + 1), d = rnd(xi + 1, zi + 1);
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
  };
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), z = p.getZ(i), r = Math.hypot(x, z);
    const h = (noise(x / 18, z / 18) - 0.5) * 1.2 + (noise(x / 5, z / 5) - 0.5) * 0.25;
    p.setY(i, h * Math.min(1, Math.max(0, (r - 8) / 12)));   // flat apron under the subject
  }
  g.computeVertexNormals();
  const m = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ color: new THREE.Color().setRGB(0.12, 0.118, 0.112), roughness: 1, metalness: 0 }));
  m.receiveShadow = true; m.name = 'ground'; m.userData.noPick = true;
  return m;
}

export function createLighting(renderer, scene) {
  const pmrem = new THREE.PMREMGenerator(renderer);
  const group = new THREE.Group(); group.name = 'lighting';
  scene.add(group);
  const sun = new THREE.DirectionalLight(0xffffff, 3); sun.castShadow = true;
  const fill = new THREE.DirectionalLight(0x9fc8ff, 0.6);
  group.add(sun, sun.target, fill);
  let env = null, floor = null, sky = null, preset = 'exhibit', sunAzEl = { az: 135, el: 1.5 }, night = false, ground = true, groundY = null;
  let bounds = new THREE.Box3(new THREE.Vector3(-1, 0, -1), new THREE.Vector3(1, 2, 1));
  const SUN_ONSITE = 10;
  function setEnv(tex) { if (env) env.dispose(); env = tex; scene.environment = tex; }
  function clearExtras() {
    if (floor) { group.remove(floor); floor.geometry.dispose(); floor.material.dispose(); floor = null; }
    if (sky) { group.remove(sky.group); sky.dispose(); sky = null; }
  }
  function applyNight() {
    if (preset !== 'onsite') return;
    sun.intensity = night ? 0 : SUN_ONSITE; sun.castShadow = !night;
    scene.environmentIntensity = night ? 0.06 : 1;   // night: no regolith bounce, only faint earthshine
    sky?.setSun(dirFromAzEl(sunAzEl.az, sunAzEl.el), night ? 0 : SUN_ONSITE);
  }

  const api = {
    sun, get preset() { return preset; }, get sky() { return sky; }, get sunAzEl() { return sunAzEl; }, get night() { return night; },
    // opts: sun {az, el}; ground false when the page brings its own terrain
    apply(name, opts = {}) {
      preset = name; if (opts.sun) sunAzEl = { ...sunAzEl, ...opts.sun }; if (opts.ground !== undefined) ground = opts.ground;
      clearExtras();
      if (name === 'exhibit') {
        scene.background = new THREE.Color('#06090f');
        setEnv(pmrem.fromScene(new RoomEnvironment(), 0.04).texture);
        scene.environmentIntensity = 0.55;
        sun.color.set(0xfff1e0); sun.intensity = 2.4;
        fill.intensity = 0.7; fill.visible = true;
        floor = new THREE.Mesh(new THREE.CircleGeometry(1, 96), new THREE.MeshStandardMaterial({ color: '#141a24', roughness: 0.92, metalness: 0 }));
        floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; floor.name = 'floor'; floor.userData.noPick = true;
      } else {
        scene.background = new THREE.Color(0, 0, 0);
        const d = dirFromAzEl(sunAzEl.az, sunAzEl.el);
        setEnv(pmrem.fromScene(lunarEnvScene(d), 0, 0.1, 100).texture);
        scene.environmentIntensity = 1;
        sun.color.set(0xffffff); sun.intensity = SUN_ONSITE;   // harsh: sunlit hull faces saturate, as in lunar photos; level ground stays dark
        fill.visible = false;
        if (ground) floor = groundMesh(600, 300);
        sky = createSky();
      }
      sun.castShadow = true;
      group.add(...[floor, sky?.group].filter(Boolean));
      applyNight();
      api.fit(bounds);
    },
    setNight(v) { night = !!v; applyNight(); },
    // Aim the sun/key light and fit its shadow camera tightly to the subject (plus its shadow on the ground). On site a
    // page calls this every frame for the focused vehicle; groundY (scene) lets the shadow of a vehicle high above the
    // ground still land inside the shadow camera's depth range.
    fit(box, opts = {}) {
      bounds = box.clone(); if (opts.groundY !== undefined) groundY = opts.groundY;
      const c = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3()), r = Math.max(0.5, size.length() / 2);
      const dir = preset === 'exhibit' ? new THREE.Vector3(-0.55, 0.75, 0.45).normalize() : dirFromAzEl(sunAzEl.az, sunAzEl.el);
      sun.target.position.copy(c);
      sun.position.copy(c).addScaledVector(dir, r + 5);
      fill.position.copy(c).addScaledVector(new THREE.Vector3(0.6, 0.4, -0.7).normalize(), r + 5);
      fill.target = sun.target;
      const cam = sun.shadow.camera, el = Math.asin(dir.y);
      const tall = groundY === null ? size.y : Math.max(size.y, box.max.y - groundY);
      const len = tall / Math.tan(Math.max(el, 0.5 * DEG));   // shadow length along the ground (38 h at 1.5°)
      cam.left = cam.bottom = -r * 1.15; cam.right = cam.top = r * 1.15;
      cam.near = 0.1; cam.far = r * 2 + 5 + len * Math.cos(el) + r;
      cam.updateProjectionMatrix();
      sun.shadow.bias = -0.0004; sun.shadow.normalBias = preset === 'onsite' ? 0.06 : 0.02;
      if (floor && preset === 'exhibit') { floor.scale.setScalar(r * 4); floor.position.set(c.x, box.min.y - 0.001, c.z); }
      return len;
    },
    setShadowSize(n) {
      if (sun.shadow.mapSize.x === n) return;
      sun.shadow.mapSize.set(n, n);
      if (sun.shadow.map) { sun.shadow.map.dispose(); sun.shadow.map = null; }
    },
    // the sky sits "at infinity": it follows the camera, just inside the far plane
    update(camera) { sky?.update(camera); },
    dispose() { clearExtras(); if (env) env.dispose(); pmrem.dispose(); scene.remove(group); sun.shadow.map?.dispose(); },
    rebuild() { api.apply(preset); },   // after a WebGL context restore: PMREM textures are lost
  };
  return api;
}
