// Materials for the procedural vehicle kit, from the catalogue's material map (lunarsim/catalog-v1.json "materials":
// linear base colour, metalness, roughness; research notes §2.2). MLI gets a crinkle normal map generated in code
// (no texture download); every material can carry regolith dust on the lowest 40 cm above the ground (world y),
// blended in the shader so one material serves parts at any height.
import * as THREE from 'three';

const DUST_TOP = 0.4;   // m above the ground; the plan asks for the lower 30-50 cm

// A tileable crinkle normal map: sums of rotated sine ridges with value-noise warping, as tangent-space normals.
let crinkle = null;
function crinkleMap() {
  if (crinkle) return crinkle;
  const N = 256, data = new Uint8Array(N * N * 4), hgt = new Float32Array(N * N);
  let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const waves = Array.from({ length: 14 }, () => ({ a: rnd() * Math.PI, f: 2 + Math.floor(rnd() * 9), p: rnd() * 6.28, w: 0.4 + rnd() }));
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    let v = 0;
    for (const s of waves) { const u = (Math.cos(s.a) * x + Math.sin(s.a) * y) / N; v += s.w * Math.abs(Math.sin((u * s.f) * 2 * Math.PI + s.p)); }
    hgt[y * N + x] = v;
  }
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const h = (i, j) => hgt[((j + N) % N) * N + ((i + N) % N)];
    const dx = (h(x + 1, y) - h(x - 1, y)) * 0.6, dy = (h(x, y + 1) - h(x, y - 1)) * 0.6, l = Math.hypot(dx, dy, 1), o = (y * N + x) * 4;
    data[o] = (-dx / l * 0.5 + 0.5) * 255; data[o + 1] = (-dy / l * 0.5 + 0.5) * 255; data[o + 2] = (1 / l * 0.5 + 0.5) * 255; data[o + 3] = 255;
  }
  crinkle = new THREE.DataTexture(data, N, N, THREE.RGBAFormat);
  crinkle.wrapS = crinkle.wrapT = THREE.RepeatWrapping; crinkle.generateMipmaps = true; crinkle.minFilter = THREE.LinearMipmapLinearFilter;
  crinkle.magFilter = THREE.LinearFilter; crinkle.colorSpace = THREE.NoColorSpace; crinkle.needsUpdate = true;
  return crinkle;
}

// Blend toward the dust colour below DUST_TOP (world y), so the lower parts read as dusted
function addDust(mat, dust) {
  mat.onBeforeCompile = shader => {
    shader.uniforms.dustColor = { value: dust };
    shader.vertexShader = shader.vertexShader.replace('#include <common>', '#include <common>\nvarying float vWorldY;')
      .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvWorldY = (modelMatrix * vec4(transformed, 1.0)).y;');
    shader.fragmentShader = shader.fragmentShader.replace('#include <common>', '#include <common>\nvarying float vWorldY;\nuniform vec3 dustColor;')
      .replace('#include <color_fragment>', `#include <color_fragment>
        float dustK = (1.0 - smoothstep(0.0, ${DUST_TOP.toFixed(2)}, vWorldY)) * 0.85;
        diffuseColor.rgb = mix(diffuseColor.rgb, dustColor, dustK);`)
      .replace('#include <roughnessmap_fragment>', '#include <roughnessmap_fragment>\nroughnessFactor = mix(roughnessFactor, 0.95, (1.0 - smoothstep(0.0, 0.4, vWorldY)) * 0.85);')
      .replace('#include <metalnessmap_fragment>', '#include <metalnessmap_fragment>\nmetalnessFactor = mix(metalnessFactor, 0.0, (1.0 - smoothstep(0.0, 0.4, vWorldY)) * 0.85);');
  };
  mat.customProgramCacheKey = () => 'dust';
  return mat;
}

// createMaterials(catalogMaterials) -> {get(id) -> MeshStandardMaterial, dispose()}; each part gets a clone (cutaways
// set clipping planes per material)
export function createMaterials(map) {
  const base = {}, dust = new THREE.Color().setRGB(...map.regolith_dust.base_color_linear.value);
  for (const [id, m] of Object.entries(map)) {
    const mat = new THREE.MeshStandardMaterial({
      color: new THREE.Color().setRGB(...m.base_color_linear.value), metalness: m.metalness.value, roughness: m.roughness.value, name: id,
    });
    if (id.startsWith('mli_')) { mat.normalMap = crinkleMap(); mat.normalScale.set(0.6, 0.6); }
    if (!id.includes('regolith')) addDust(mat, dust);
    base[id] = mat;
  }
  // extra non-catalogue materials used by the generators (named so the properties panel can say so)
  base.dark_metal = addDust(new THREE.MeshStandardMaterial({ color: '#3a3d42', metalness: 0.85, roughness: 0.4, name: 'dark_metal (nozzle, representative)' }), dust);
  base.tyre = addDust(new THREE.MeshStandardMaterial({ color: '#8f9296', metalness: 0.7, roughness: 0.55, name: 'tyre mesh (representative)' }), dust);
  base.lamp = new THREE.MeshStandardMaterial({ color: '#202020', emissive: '#fff3d6', emissiveIntensity: 8, name: 'lamp' });   // above the bloom threshold
  const used = [];
  return {
    get(id) {
      const src = base[id] || base.aluminium, m = src.clone();
      m.onBeforeCompile = src.onBeforeCompile; m.customProgramCacheKey = src.customProgramCacheKey; m.userData.catalogMaterial = id;
      used.push(m); return m;
    },
    dispose() { used.forEach(m => m.dispose()); Object.values(base).forEach(m => m.dispose()); },
  };
}
