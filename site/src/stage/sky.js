// The sky over on-site views (research §2.2). Black. Earth as a disc of its true apparent size (radius from the track,
// ~0.95°), lit by the sun so its phase is right, placed from Earth's hourly SPICE track seen from BASE (R-1, B-40) when
// the page loads it, else from a simple libration ephemeris; cut off below the terrain's horizon profile, so it sets
// behind ridges as it does for a rover. Stars only at a long exposure: any exposure that suits sunlit regolith hides
// them. Everything sits "at infinity": the sky follows the camera, just inside the far plane.
// Directions: y up, grid north = -z, east = +x, azimuth clockwise from north (as lighting.js).
import * as THREE from 'three';
import { dirFromAzEl, EARTH_DIAMETER_DEG } from './lighting.js';
import { mulberry32 } from './effects/rng.js';

const D = Math.PI / 180;
// horizon test shared by Earth and the stars: direction from the camera -> grid azimuth and elevation (degrees)
const HORIZON_GLSL = /* glsl */`
uniform sampler2D uHz; uniform float uUseHz;
float belowHorizon(vec3 dir) {
  if (uUseHz < 0.5) return 0.0;
  float az = atan(dir.x, -dir.z) / 6.2831853; az = fract(az);
  float el = degrees(asin(clamp(dir.y, -1.0, 1.0)));
  return step(el, texture2D(uHz, vec2(az, 0.5)).r);
}`;

const earthVert = /* glsl */`
varying vec3 vObj; varying vec3 vW;
void main() { vObj = position; vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const earthFrag = /* glsl */`
${HORIZON_GLSL}
uniform vec3 uSun; uniform float uSunE; varying vec3 vObj; varying vec3 vW;
float h3(vec3 p) { return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
float n3(vec3 p) { vec3 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(h3(i), h3(i + vec3(1, 0, 0)), f.x), mix(h3(i + vec3(0, 1, 0)), h3(i + vec3(1, 1, 0)), f.x), f.y),
             mix(mix(h3(i + vec3(0, 0, 1)), h3(i + vec3(1, 0, 1)), f.x), mix(h3(i + vec3(0, 1, 1)), h3(i + vec3(1, 1, 1)), f.x), f.y), f.z); }
void main() {
  if (belowHorizon(normalize(vW - cameraPosition)) > 0.5) discard;
  vec3 n = normalize(vObj);
  float land = smoothstep(0.55, 0.62, n3(n * 2.3) * 0.7 + n3(n * 5.1) * 0.3);
  float cloud = smoothstep(0.5, 0.75, n3(n * 4.0 + 3.0) * 0.6 + n3(n * 11.0) * 0.4);
  vec3 alb = mix(mix(vec3(0.04, 0.09, 0.22), vec3(0.20, 0.18, 0.12), land), vec3(0.75), cloud);   // mean ~0.3 (Bond albedo)
  float mu = max(dot(n, uSun), 0.0);
  gl_FragColor = vec4(alb * uSunE * mu / 3.14159, 1.0);
}`;

const starVert = /* glsl */`
${HORIZON_GLSL}
attribute float aMag; attribute vec3 aCol; varying vec3 vC;
void main() {
  vec4 w = modelMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * viewMatrix * w;
  float b = pow(10.0, -0.4 * (aMag - 1.0));
  gl_PointSize = 1.5 + 2.0 * b;
  vC = aCol * (0.15 + 2.5 * b);
  if (belowHorizon(normalize(w.xyz - cameraPosition)) > 0.5) gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
}`;
const starFrag = /* glsl */`
varying vec3 vC; void main() { vec2 q = gl_PointCoord * 2.0 - 1.0; float d = dot(q, q); if (d > 1.0) discard; gl_FragColor = vec4(vC * (1.0 - d), 1.0); }`;

// Earth from BASE, simple model for when no track is loaded: libration in latitude (amplitude 6.7°, draconic month)
// moves its elevation, libration in longitude (7.9°, anomalistic month) its bearing; phases arbitrary (Modelled,
// placeholder). The track gives elevation -7.5..6.2° and bearing -8.1..8.0° at BASE.
export function earthSimple(hours) {
  const d = hours / 24;
  return { az: (360 + 7.9 * Math.sin(2 * Math.PI * d / 27.5546)) % 360, el: -0.6 + 6.7 * Math.sin(2 * Math.PI * d / 27.2122), radiusDeg: EARTH_DIAMETER_DEG / 2, source: 'simple libration model (placeholder)' };
}

// Earth track (lunarsim-earth-track v1, hourly from 2028-01-01 UTC, centidegrees): fetch and gunzip in the page
export async function loadEarthTrack(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  let buf = new Uint8Array(await r.arrayBuffer());
  if (buf[0] === 0x1f && buf[1] === 0x8b) buf = new Uint8Array(await new Response(new Blob([buf]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer());
  const j = JSON.parse(new TextDecoder().decode(buf));
  if (j.format !== 'lunarsim-earth-track') throw new Error('not a lunarsim-earth-track file');
  const n = j.time.n, step = j.time.step_h;
  const lerp = (arr, h) => { const x = Math.max(0, Math.min(n - 1.001, h / step)), i = Math.floor(x), f = x - i; return (arr[i] + (arr[i + 1] - arr[i]) * f) / 100; };
  return {
    meta: { site: j.site, start: j.time.start_utc, hours: n * step, note: j.note },
    // hours since the track's start -> {az (grid bearing, deg), el (deg), radiusDeg}
    at: h => ({ az: (lerp(j.grid_bearing_cdeg, h) + 360) % 360, el: lerp(j.elevation_cdeg, h), radiusDeg: lerp(j.radius_cdeg, h), source: `SPICE track from ${j.site} (R-1)` }),
  };
}

export function createSky({ stars = 3000, seed = 20281 } = {}) {
  const group = new THREE.Group(); group.name = 'sky'; group.userData.noPick = true;
  const hzData = new Float32Array(360).fill(-90), hzTex = new THREE.DataTexture(hzData, 360, 1, THREE.RedFormat, THREE.FloatType);
  hzTex.wrapS = THREE.RepeatWrapping; hzTex.magFilter = hzTex.minFilter = THREE.LinearFilter; hzTex.needsUpdate = true;
  const shared = { uHz: { value: hzTex }, uUseHz: { value: 0 } };
  const sunDir = new THREE.Vector3(0, 0.03, -1).normalize();

  const earthMat = new THREE.ShaderMaterial({ vertexShader: earthVert, fragmentShader: earthFrag, uniforms: { ...shared, uSun: { value: sunDir }, uSunE: { value: 10 } } });
  const earth = new THREE.Mesh(new THREE.SphereGeometry(1, 48, 24), earthMat); earth.name = 'earth'; earth.userData = { noPick: true, noAO: true };
  earth.renderOrder = -2;
  group.add(earth);

  // stars: seeded directions, magnitudes 0.5-6.5 (counts rise ~3x per magnitude), a spread of colour temperatures
  const rnd = mulberry32(seed), pos = new Float32Array(3 * stars), mag = new Float32Array(stars), col = new Float32Array(3 * stars);
  for (let i = 0; i < stars; i++) {
    const z = 2 * rnd() - 1, a = 2 * Math.PI * rnd(), r = Math.sqrt(1 - z * z);
    pos.set([r * Math.cos(a), z, r * Math.sin(a)], 3 * i);
    mag[i] = 6.5 - 6 * Math.pow(rnd(), 2.2);
    const t = rnd(); col.set(t < 0.15 ? [0.75, 0.85, 1] : t < 0.75 ? [1, 0.97, 0.92] : [1, 0.82, 0.62], 3 * i);
  }
  const sg = new THREE.BufferGeometry();
  sg.setAttribute('position', new THREE.BufferAttribute(pos, 3)); sg.setAttribute('aMag', new THREE.BufferAttribute(mag, 1)); sg.setAttribute('aCol', new THREE.BufferAttribute(col, 3));
  const starPts = new THREE.Points(sg, new THREE.ShaderMaterial({ vertexShader: starVert, fragmentShader: starFrag, uniforms: shared, depthWrite: false, transparent: true, blending: THREE.AdditiveBlending }));
  starPts.visible = false; starPts.frustumCulled = false; starPts.userData = { noPick: true, noAO: true }; starPts.renderOrder = -3;
  group.add(starPts);

  let earthAzEl = earthSimple(0);
  return {
    group, earth, stars: starPts,
    get earthPos() { return earthAzEl; },
    setEarth(p) { earthAzEl = { ...earthAzEl, ...p }; },
    setSun(dir, intensity = 10) { sunDir.copy(dir).normalize(); earthMat.uniforms.uSunE.value = intensity; },
    // horizon elevation (degrees) per degree of azimuth, from horizonProfile(); null switches the cut-off off
    setHorizon(profile) {
      if (!profile) { shared.uUseHz.value = 0; return; }
      for (let k = 0; k < 360; k++) hzData[k] = profile[Math.floor(k * profile.length / 360)];
      hzTex.needsUpdate = true; shared.uUseHz.value = 1;
    },
    // is Earth's upper limb above the horizon profile at its bearing?
    earthVisible() {
      if (!shared.uUseHz.value) return earthAzEl.el + earthAzEl.radiusDeg > 0;
      return earthAzEl.el + earthAzEl.radiusDeg > hzData[Math.round(earthAzEl.az) % 360];
    },
    setStars(v) { starPts.visible = v; },
    update(camera) {
      const R = camera.far * 0.9;
      group.position.copy(camera.position);
      starPts.scale.setScalar(R * 1.02);
      earth.position.copy(dirFromAzEl(earthAzEl.az, earthAzEl.el)).multiplyScalar(R);
      earth.scale.setScalar(R * Math.tan(earthAzEl.radiusDeg * D));
    },
    dispose() { earth.geometry.dispose(); earthMat.dispose(); sg.dispose(); starPts.material.dispose(); hzTex.dispose(); },
  };
}
