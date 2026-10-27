// The shared 3D stage (plan §5 F-31): one module every Phase 4 3D page uses.
//   const stage = await createStage({canvas, labelsHost, preset: 'exhibit' | 'onsite', tier, ao, sun: {az, el}})
// Renderer: three r186 WebGLRenderer, stencil on (cutaway caps), reversed depth buffer when EXT_clip_control exists,
// colour management on, tone mapping Neutral / ACES / AgX. Renders on demand: a frame is drawn only when the camera,
// an animation or a caller asks for one; the loop sleeps otherwise. Frame intervals and GPU times are collected while
// frames run back to back; an adaptive pixel-ratio monitor holds the tier's frame-time target. The WebGL context can
// be lost and restored (GPU reset, tab in the background on phones): the loop stops, then lighting and buffers rebuild.
import * as THREE from 'three';
import { createLighting } from './lighting.js';
import { createPost, preloadN8AO } from './post.js';
import { createDirector } from './director.js';
import { createLabels } from './labels.js';
import { createCutaway } from './cutaway.js';
import { createExplode } from './explode.js';
import { createPicker } from './pick.js';
import { FrameStats, GpuTimer, ResolutionMonitor, budgetRatio } from './perf.js';
import { TIERS } from './tier.js';

export const TONE = { neutral: THREE.NeutralToneMapping, aces: THREE.ACESFilmicToneMapping, agx: THREE.AgXToneMapping };

export async function createStage({ canvas, labelsHost, preset = 'exhibit', tier = 2, ao = 'gtao', sun = { az: 135, el: 1.5 },
  toneMapping = 'neutral', onStatus = () => {}, onPick = () => {}, onHover = () => {} }) {
  const gl = canvas.getContext('webgl2', { antialias: false, alpha: false, depth: true, stencil: true, powerPreference: 'high-performance' });
  if (!gl) throw new Error('WebGL2 is not available');
  if (/[?&]gpumem/.test(location.search)) window.__gpumem = (await import('./gpumem.js')).trackGpuMemory(gl, canvas);   // F-40: GPU memory, measured on request
  const reversed = !!gl.getExtension('EXT_clip_control');
  const renderer = new THREE.WebGLRenderer({ canvas, context: gl, antialias: false, stencil: true, reversedDepthBuffer: reversed, powerPreference: 'high-performance' });
  renderer.localClippingEnabled = true;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFShadowMap;   // r186: PCFSoft was removed
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.info.autoReset = false;   // the composer renders several times a frame; counts are reset per frame below

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, 0.05, 5000);
  camera.position.set(9, 5, 12);
  if (ao === 'n8ao') await preloadN8AO();

  let raf = 0, needs = true, continuous = 0, last = 0, prevDrawn = 0, paused = false, lost = false, disposed = false, compiling = 0;
  let subject = null, w = 1, h = 1, picker = null;
  const animations = new Set(), stats = new FrameStats(5000), gpu = new GpuTimer(gl);
  const invalidate = () => { needs = true; wake(); };
  const wake = () => { if (!raf && !lost && !disposed) raf = requestAnimationFrame(frame); };   // raf is -1 while a frame runs

  const lighting = createLighting(renderer, scene);
  const post = createPost(renderer, scene, camera, { reversed, ao });
  const director = createDirector(camera, canvas, { onWake: wake });
  const cutaway = createCutaway(scene);
  const labels = createLabels(labelsHost, camera, { occluders: () => pickTargets(), isClipped: p => cutaway.isClipped(p) });
  const monitor = new ResolutionMonitor({ targetMs: TIERS[Math.max(1, tier)].frameMs, onChange: r => { renderer.setPixelRatio(r); resize(true); } });
  post.setClipping([], o => !!o.userData.cutHelper);

  let pickList = [];
  function pickTargets() { return pickList; }
  function collectPickables() {
    pickList = [];
    subject?.traverse(o => { if (o.isMesh && !o.userData.noPick && !o.userData.cutHelper) pickList.push(o); });
  }

  // ---------- size, pixel budget, near plane ----------
  function resize(keepRatio = false) {
    const r = canvas.parentElement.getBoundingClientRect();
    w = Math.max(1, Math.round(r.width)); h = Math.max(1, Math.round(r.height));
    const max = budgetRatio(w, h, TIERS[Math.max(1, tier)].pixels);
    monitor.max = max;
    if (!keepRatio) { monitor.ratio = Math.min(monitor.ratio, max); renderer.setPixelRatio(monitor.ratio); }
    renderer.setSize(w, h, false);
    camera.aspect = w / h; camera.updateProjectionMatrix();
    const db = renderer.getDrawingBufferSize(new THREE.Vector2());
    post.setSize(db.x, db.y);
    invalidate();
  }
  const ro = new ResizeObserver(() => resize());
  ro.observe(canvas.parentElement);

  function fitNearFar() {
    const d = director.controls.distance;
    // reversed depth keeps precision at any near; otherwise keep far/near under ~1e5
    camera.near = reversed ? 0.02 : Math.min(1, Math.max(0.02, d * 0.005));
    camera.far = Math.max(200, d * 40, lighting.preset === 'onsite' ? 4000 : 0);
    camera.updateProjectionMatrix();
  }

  // ---------- the loop ----------
  function frame(now) {
    raf = -1;   // events fired during this frame (camera updates) must not queue a second frame
    if (lost || disposed) { raf = 0; return; }
    const dt = last ? Math.min(0.1, (now - last) / 1000) : 1 / 60; last = now;
    let moving = director.update(dt);
    if (!paused) for (const a of animations) if (!a(dt, now)) animations.delete(a);
    moving = moving || animations.size > 0 || director.autoRotating;
    const busy = moving || continuous > now;
    if (compiling) { raf = requestAnimationFrame(frame); return; }   // new shaders compile in parallel; keep the last frame
    if (busy || needs) {
      fitNearFar(); lighting.update(camera);
      renderer.info.reset(); gpu.begin(); post.render(dt); gpu.end();
      gpu.poll(ms => stats.pushGpu(now, ms));
      labels.update(w, h);
      if (prevDrawn) { stats.push(now, now - prevDrawn); monitor.check(now, stats.summary()); }
      prevDrawn = busy ? now : 0;
      needs = false;
    }
    if (busy || needs || (animations.size && !paused)) raf = requestAnimationFrame(frame);
    else { raf = 0; last = 0; prevDrawn = 0; labels.update(w, h, true); setTimeout(() => gpu.poll(ms => stats.pushGpu(performance.now(), ms)), 50); }
  }

  // Changes that add shader programs (a cut adds clipping variants of every material) are compiled with
  // KHR_parallel_shader_compile before the next frame draws, instead of stalling the page for up to ~1.5 s.
  async function compiled(change) {
    change();
    compiling++;
    // capped at 3 s: three polls each program's completion status, and one replaced mid-wait can never report ready
    try { await Promise.race([renderer.compileAsync(scene, camera), new Promise(r => setTimeout(r, 3000))]); } catch (e) { /* compile on draw */ }
    compiling--; invalidate();
  }

  // ---------- context loss ----------
  const onLost = e => { e.preventDefault(); lost = true; cancelAnimationFrame(raf); raf = 0; onStatus('lost'); };
  const onRestored = () => { lost = false; lighting.rebuild(); post.configure({}); resize(); onStatus('restored'); };
  canvas.addEventListener('webglcontextlost', onLost);
  canvas.addEventListener('webglcontextrestored', onRestored);

  // ---------- configuration ----------
  function setTier(t) {
    tier = Math.max(1, Math.min(3, t));
    const cfg = TIERS[tier];
    lighting.setShadowSize(cfg.shadow);
    monitor.targetMs = cfg.frameMs; monitor.flips = 0; monitor.lastDir = 0; monitor.ratio = Infinity;   // start each tier at its full budget
    post.configure({ tier });
    picker?.highlight(null);
    settle();
    resize();
  }
  // after a rebuild the first frames compile shaders: keep them out of the stats and the resolution monitor
  function settle() { stats.reset(); monitor.since = performance.now() + 1500; }
  async function setAO(kind) { if (kind === 'n8ao') await preloadN8AO(); post.configure({ ao: kind }); settle(); resize(); }
  function setToneMapping(name, exposure = 1) { renderer.toneMapping = TONE[name] ?? THREE.NeutralToneMapping; renderer.toneMappingExposure = exposure; invalidate(); }
  // bloom threshold per preset: the on-site sun is ~4x the studio key, so sunlit white paint reaches ~8 in linear HDR
  const BLOOM = { exhibit: 5, onsite: 12 };   // above sunlit paint and stainless; emissive parts are brighter
  function setPreset(name, opts = {}) { return compiled(() => { lighting.apply(name, opts); post.setBloomThreshold(BLOOM[name]); if (subject) lighting.fit(new THREE.Box3().setFromObject(subject)); }); }

  lighting.apply(preset, { sun }); post.setBloomThreshold(BLOOM[preset]);
  setToneMapping(toneMapping);
  monitor.ratio = Infinity;
  setTier(tier);

  const api = {
    scene, camera, renderer, director, labels, cutaway, lighting, post, stats,
    get tier() { return tier; }, get paused() { return paused; }, get reversedDepth() { return reversed; },
    get gpuTimer() { return gpu.available; }, get pixelRatio() { return renderer.getPixelRatio(); }, get size() { return [w, h]; },
    setTier, setAO, setToneMapping, setPreset,
    renderOnce: invalidate, invalidate,
    // the hero object: frames the shadow camera, the cut, the pick targets and the 'home' shot
    setSubject(obj, { cutTargets = [] } = {}) {
      subject = obj; scene.add(obj);
      const box = new THREE.Box3().setFromObject(obj);
      lighting.fit(box);
      cutaway.setTargets(cutTargets, box);
      collectPickables();
      picker?.dispose();
      picker = createPicker(canvas, camera, { targets: pickTargets, isClipped: p => cutaway.isClipped(p), outline: objs => post.setOutlined(objs), onPick, onHover, invalidate });
      compiled(() => {});   // first frame waits for the subject's shaders instead of freezing the page
      return box;
    },
    // remove the hero object (when the page switches vehicles): geometry and materials are disposed
    clearSubject() {
      if (!subject) return;
      cutaway.setTargets([]); post.setClipping([], o => !!o.userData.cutHelper); labels.clear(); picker?.dispose(); picker = null;
      scene.remove(subject);
      subject.traverse(o => { if (o.geometry) o.geometry.dispose(); if (o.material) [].concat(o.material).forEach(m => m.dispose()); });
      subject = null; pickList = []; invalidate();
    },
    // F-51: outline the named part, or every part of a group (userData.group), as a hover does; null clears
    highlightPart(name) {
      const list = [];
      if (name && subject) subject.traverse(o => { if (o.userData.part && (o.userData.part === name || o.userData.group === name)) list.push(o); });
      picker?.highlight(list.length ? list : null);
    },
    setCut(mode, opts) { return compiled(() => { const planes = cutaway.set(mode, opts); post.setClipping(planes, o => !!o.userData.cutHelper); }); },
    explode(parts) { return createExplode(parts, { animate: fn => api.animate(fn), onChange: invalidate }); },
    // animate(fn): fn(dt, now) is called every frame until it returns false; frozen while paused
    animate(fn) { animations.add(fn); wake(); return () => animations.delete(fn); },
    pause(v) { paused = v; director.pause(v); if (!v) wake(); invalidate(); },
    setAdaptive(v) { monitor.enabled = v; monitor.flips = 0; monitor.lastDir = 0; if (!v) { monitor.ratio = Infinity; resize(); } },
    // draw frames back to back for ms (the camera may stand still) and resolve with the frame-time summary
    measure(ms = 5000) {
      stats.reset(); continuous = performance.now() + ms; prevDrawn = 0; wake();
      return new Promise(res => setTimeout(() => setTimeout(() => res({ ...stats.summary(), pixelRatio: renderer.getPixelRatio(), size: [w, h] }), 120), ms));
    },
    // Cost per frame independent of the display's refresh and of rAF throttling (a background window): draw n frames
    // one per task, each inside a GPU timer query (EXT_disjoint_timer_query_webgl2), and time the CPU side too. In a
    // real frame CPU and GPU overlap, so the frame time is about max(cpu, gpu). Resolves with p50/p95 of both.
    async benchmark(n = 150, warmup = 15) {
      const ext = gl.getExtension('EXT_disjoint_timer_query_webgl2'), queries = [], cpu = [];
      for (let i = 0; i < n + warmup; i++) {
        const t0 = performance.now(), qy = ext && i >= warmup ? gl.createQuery() : null;
        if (qy) gl.beginQuery(ext.TIME_ELAPSED_EXT, qy);
        fitNearFar(); lighting.update(camera); renderer.info.reset(); post.render(1 / 60);
        if (qy) { gl.endQuery(ext.TIME_ELAPSED_EXT); queries.push(qy); }
        if (i >= warmup) cpu.push(performance.now() - t0);
        gl.flush(); await new Promise(r => setTimeout(r, 0));   // submit each frame on its own, as a real frame would be
      }
      const gpuMs = [];
      for (let tries = 0; queries.length && tries < 100; tries++) {
        await new Promise(r => setTimeout(r, 20));
        if (gl.getParameter(ext.GPU_DISJOINT_EXT)) { queries.forEach(x => gl.deleteQuery(x)); queries.length = 0; break; }
        while (queries.length && gl.getQueryParameter(queries[0], gl.QUERY_RESULT_AVAILABLE)) {
          const x = queries.shift(); gpuMs.push(gl.getQueryParameter(x, gl.QUERY_RESULT) / 1e6); gl.deleteQuery(x);
        }
      }
      const q = (a, p) => { if (!a.length) return NaN; const s = [...a].sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor(p * s.length))]; };
      labels.update(w, h);
      return { n, gpuN: gpuMs.length, gpuP50: q(gpuMs, 0.5), gpuP95: q(gpuMs, 0.95), cpuP50: q(cpu, 0.5), cpuP95: q(cpu, 0.95), calls: renderer.info.render.calls,
        drawingBuffer: renderer.getDrawingBufferSize(new THREE.Vector2()).toArray() };
    },
    info() {
      const i = renderer.info;
      return { calls: i.render.calls, triangles: i.render.triangles, textures: i.memory.textures, geometries: i.memory.geometries,
        reversedDepth: reversed, gpuTimer: gpu.available, compiling, pixelRatio: renderer.getPixelRatio(), drawingBuffer: renderer.getDrawingBufferSize(new THREE.Vector2()).toArray() };
    },
    loseContext() { const ext = gl.getExtension('WEBGL_lose_context'); ext?.loseContext(); return ext; },
    dispose() {
      disposed = true; cancelAnimationFrame(raf); ro.disconnect();
      canvas.removeEventListener('webglcontextlost', onLost); canvas.removeEventListener('webglcontextrestored', onRestored);
      picker?.dispose(); labels.dispose(); director.dispose(); cutaway.dispose(); post.dispose(); lighting.dispose(); gpu.dispose();
      scene.traverse(o => {
        if (o.geometry) o.geometry.dispose();
        if (o.material) for (const m of [].concat(o.material)) { for (const v of Object.values(m)) if (v?.isTexture) v.dispose(); m.dispose(); }
      });
      renderer.dispose();
    },
  };
  if (new URLSearchParams(location.search).has('bench')) window.__stage = api;   // F-52: ?bench exposes the stage for frame-time checks on the production build
  return api;
}
