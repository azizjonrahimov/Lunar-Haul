// Post-processing chain by tier (plan §5 F-31). The composer's buffers are half-float (no banding in dark scenes)
// and keep a stencil buffer, so the cutaway caps survive. Order: scene (+ AO) -> bloom -> outline -> output (tone
// mapping, sRGB) -> FXAA or SMAA (they expect sRGB input, so they run after OutputPass).
//   tier 1: render, output, FXAA
//   tier 2: + ambient occlusion at half resolution, bloom at half resolution (only parts brighter than 1), outline
//   tier 3: AO and bloom at full resolution, SMAA
// AO: 'gtao' (three r186 GTAOPass, renders its own normal pass) or 'n8ao' (N8AO 2.0.1, renders the scene itself).
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutlinePass } from 'three/addons/postprocessing/OutlinePass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { FXAAPass } from 'three/addons/postprocessing/FXAAPass.js';
import { SMAAPass } from 'three/addons/postprocessing/SMAAPass.js';
import { TIERS } from './tier.js';

// the composer resizes every pass to full size; these passes keep their own scale (half-resolution AO and bloom)
const scaled = (pass, k) => { const set = pass.setSize.bind(pass); pass.setSize = (w, h) => set(Math.round(w * k), Math.round(h * k)); return pass; };

export function createPost(renderer, scene, camera, { reversed, ao = 'gtao' }) {
  let composer = null, passes = {}, tier = 1, aoKind = ao, clipPlanes = [], hideFromAO = () => false, bloomThreshold = 2.5;

  function build() {
    dispose();
    const t = TIERS[tier], size = renderer.getDrawingBufferSize(new THREE.Vector2());
    const rt = new THREE.WebGLRenderTarget(size.x, size.y, { type: THREE.HalfFloatType, stencilBuffer: true, depthBuffer: true });
    composer = new EffectComposer(renderer, rt);
    composer.setPixelRatio(1);   // sizes below are drawing-buffer pixels
    const half = t.ao === 'half' ? 0.5 : 1;
    if (t.ao && aoKind === 'n8ao') {
      passes.n8ao = n8aoPass(scene, camera, size, half, reversed);
      composer.addPass(passes.n8ao);
    } else {
      composer.addPass(passes.render = new RenderPass(scene, camera));
      if (t.ao) {
        const g = new GTAOPass(scene, camera, Math.round(size.x * half), Math.round(size.y * half));
        g.output = GTAOPass.OUTPUT.Default;
        g.updateGtaoMaterial({ radius: 0.6, distanceExponent: 1, thickness: 1, scale: 1, samples: tier === 3 ? 16 : 8, distanceFallOff: 1, screenSpaceRadius: false });
        g.updatePdMaterial({ lumaPhi: 10, depthPhi: 2, normalPhi: 3, radius: 4, rings: 2, samples: tier === 3 ? 16 : 8 });
        g.blendIntensity = 1;
        patchGtao(g, () => clipPlanes, o => hideFromAO(o));
        composer.addPass(passes.gtao = scaled(g, half));
      }
    }
    if (t.bloom) {
      const b = t.bloom === 'half' ? 0.5 : 1;
      composer.addPass(passes.bloom = scaled(new UnrealBloomPass(new THREE.Vector2(size.x * b, size.y * b), 0.6, 0.4, bloomThreshold), b));   // linear-HDR threshold: only emissive hot parts glow, not sunlit paint
    }
    if (t.outline) {
      const o = new OutlinePass(new THREE.Vector2(size.x, size.y), scene, camera);
      Object.assign(o, { edgeStrength: 3, edgeGlow: 0, edgeThickness: 1, pulsePeriod: 0 });
      o.visibleEdgeColor.set('#8fe3ff'); o.hiddenEdgeColor.set('#2b6a80');
      composer.addPass(passes.outline = o);
    }
    composer.addPass(passes.output = new OutputPass());
    composer.addPass(passes.aa = t.aa === 'smaa' ? new SMAAPass() : new FXAAPass());
    composer.setSize(size.x, size.y);
  }

  function dispose() {
    if (!composer) return;
    for (const p of composer.passes) p.dispose?.();
    composer.renderTarget1.dispose(); composer.renderTarget2.dispose();
    composer = null; passes = {};
  }

  return {
    get passes() { return passes; },
    get aoKind() { return aoKind; },
    configure(opts) {
      if (opts.tier !== undefined) tier = Math.max(1, opts.tier);
      if (opts.ao) aoKind = opts.ao;
      build();
    },
    setSize(w, h) { if (!composer) return; composer.setSize(w, h); },
    // cutaway planes and objects to keep out of GTAO's own normal pass (caps, stencil writers)
    setClipping(planes, hide) { clipPlanes = planes; hideFromAO = hide; },
    setBloomThreshold(v) { bloomThreshold = v; if (passes.bloom) passes.bloom.threshold = v; },
    setOutlined(objs) { if (passes.outline) passes.outline.selectedObjects = objs; return !!passes.outline; },
    render(dt) { composer.render(dt); },
    dispose,
  };
}

async function loadN8AO() { return (await import('n8ao')).N8AOPass; }
let N8AOPass = null;
export const preloadN8AO = async () => { N8AOPass = N8AOPass || await loadN8AO(); };

function n8aoPass(scene, camera, size, half, reversed) {
  if (!N8AOPass) throw new Error('N8AO not loaded: await preloadN8AO() first');
  const p = new N8AOPass(scene, camera, size.x, size.y);
  Object.assign(p.configuration, {
    aoRadius: 0.8, distanceFalloff: 0.5, intensity: 2.5, aoSamples: half < 1 ? 8 : 16, denoiseSamples: half < 1 ? 4 : 8,
    denoiseRadius: 8, halfRes: half < 1, gammaCorrection: false, stencil: true,
    depthBufferType: reversed ? 3 : 1,   // N8AO DepthType: 1 Default, 3 Reverse
  });
  return p;
}

// GTAOPass draws its normal/depth buffer with an override material, which ignores the cutaway's clipping planes and
// would draw the stencil caps as whole quads. Give that material the planes and hide caps and stencil writers.
function patchGtao(g, planes, hide) {
  const orig = g._overrideVisibility.bind(g);
  g._overrideVisibility = function () {
    orig();
    const p = planes();
    g.normalMaterial.clippingPlanes = p.length ? p : null;
    g.normalMaterial.clipIntersection = p.length > 1;
    g.scene.traverse(o => { if (o.visible && hide(o)) { o.visible = false; g._visibilityCache.push(o); } });
  };
}
