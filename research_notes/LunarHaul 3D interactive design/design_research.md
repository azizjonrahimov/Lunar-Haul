# LunarHaul 3D interactive design: research notes

Compiled 2026-10-22 for the redesign plan. The owner wants the site's simulation to look and feel as professional as a set of reference reels, with interactive 3D models of the landers, rovers and the base. The main reference is airsup's "Inside the Raptor 3" page (https://airsup.ai/rocket-engine), analysed earlier. No code was changed for these notes.

**Method.** About 75 web searches and page fetches, plus three local checks: the installed three.js r186 source in `site/node_modules/three`, the current `site/` code and build output, and HTTP header measurements against the live site (https://azizjonrahimov.github.io/Lunar-Haul/) on 2026-10-22. These notes build on the earlier notes in `research_notes/Lunar landing and rover autonomy logistics/` and do not repeat them: `web_visualisation_design.md` (stack, palettes, Distill measures, detect-gpu, pixel budget), `terrain_data_3d_assets.md` (LOLA data, NASA 3D Resources, CSM), `plume_ejecta_base_layout.md` (ejecta physics), `lander_descent_numbers.md` and `rover_autonomy_driving.md` (vehicle numbers), and `backend_database_hosting.md`. Earlier facts used again here are cited to their original URL.

**Confidence grades.**
- **High:** official documentation, source code, peer-reviewed or agency papers, or something I measured.
- **Medium:** a reputable secondary source, or a single primary source read only through a summary.
- **Low:** a forum or hobby source, a search snippet, or my own inference with weak support.

Lines marked *Inference* are my own reasoning, not a sourced fact.

---

## Summary of findings

1. **Stay on WebGLRenderer for this redesign; do not adopt WebGPURenderer/TSL yet.**
   - The three.js manual says WebGLRenderer "is still maintained and the recommended choice for pure WebGL 2 applications".
   - It says WebGPURenderer is "still in an experimental state".
   - It says `ShaderMaterial`, `onBeforeCompile` and `EffectComposer` are not supported under WebGPURenderer.
   - Our terrain is a custom GLSL `ShaderMaterial`, and the whole Raptor-style effect stack is `EffectComposer`-based. Migrating would mean a rewrite with no visual gain.
2. **Everything the Raptor page uses ships as a WebGL add-on in the installed r186:** `GTAOPass`, `SAOPass`, `UnrealBloomPass`, `OutputPass`, `SMAAPass`, `RoomEnvironment`/PMREM, `CSM`, the new `SunLight` with two-cascade shadows, and the official stencil-cap clipping example.
   - Cutaways are cheap: each clipping plane costs two stencil-only redraws of the mesh plus one cap quad.
   - Ambient occlusion (AO) is the expensive item. N8AO (CC0) with its half-resolution mode is the best-documented option for low-end GPUs.
3. **A Moon plume must not look like the Raptor's sea-level plume.**
   - In vacuum the jet is highly underexpanded and spreads wide.
   - Shock diamonds depend on ambient pressure.
   - Hydrogen flames are nearly invisible.
   - What landing footage shows is dust: a thin radial sheet 1–3° above the ground. Apollo 12 landed "essentially blind" for the last ~40 ft. On Blue Ghost, the plume started acting on the surface ~15 m up, and the dust settled once the thrusters shut off.
   - The visual effort therefore belongs on the ground (ejecta sheet, scour, obscuration), with only a faint glow near the nozzle.
4. **The 1.5° polar sun makes each vehicle cast a shadow about 38 times its height**, with a long blurred tip:
   - a Starship-class lander (52 m) casts ~2 km;
   - Blue Moon MK1 (8 m) casts ~300 m;
   - an LTV-class rover (2.6 m) casts ~100 m.

   The existing baked terrain-visibility texture handles terrain shadowing terrain. Vehicle shadows need a tightly fitted shadow camera on the focused vehicle. Because three.js shadows only reach built-in lit materials, the custom terrain shader must also sample that shadow map itself.
5. **True-scale close-ups (an 0.8 m wheel beside 20 km of terrain) need better depth precision** than today's camera (near plane 5 m, vehicles scaled to a constant screen size). r186 offers `reversedDepthBuffer`, which needs `EXT_clip_control`. It is faster and more accurate than `logarithmicDepthBuffer`, which disables the early depth test.
6. **No official or Creative Commons 3D models exist** for Blue Moon, Starship HLS, Nova-C, Griffin, the LTVs or VIPER. Only paid marketplace models turned up, some marked "editorial use only".
   - The clean route is procedural, true-scale models built from published dimensions and labelled "representative".
   - glTF with meshopt and KTX2 compression is only worth it for NASA public-domain models we may want to show, such as the Apollo LM.
7. **Dimensions with usable sources:**
   - Blue Moon MK1: 8.05 m tall, 3.08 m diameter, one BE-7 hydrolox engine of about 40–44 kN.
   - Nova-C: hexagonal body 3.9 m tall and 1.6–2 m across, six legs, methalox VR900 engine.
   - Griffin: 4.5 m wide, four legs, hypergolic propellants.
   - Starship HLS: 52 m tall, 9 m diameter, six Raptors, methane–oxygen landing thrusters mid-body, an elevator, and a band of solar panels.
   - Apollo LRV: 3.1 m long, 2.3 m wheelbase, 81.8 cm wheels.
   - VIPER: 1.7 × 1.7 × 2.5 m.

   Gaps: MK1 leg layout, HLS leg layout, and Pegasus/CLV-1 detail.
8. **The reference's glass panels fail WCAG text contrast once a bright scene sits behind them** (my calculation). With #0c1426 at 62 % opacity:
   - "muted" #93a0b6 falls to 4.1:1 over mid-grey and 3.1:1 over sunlit regolith, against a 4.5:1 requirement;
   - "faint" #5d6a80 fails on every background;
   - "ink" stays at 4.6:1 or better, even over white.
9. **Evidence favours the Raptor page's mode-button "stepper" over scroll-driven storytelling.** McKenna et al. (2017) found no engagement difference between steppers and scrollers. Zhi et al., as reported by Distill (2020), found better comprehension with slideshow layouts.
10. **Library licences:**
    - Outfit and DM Mono: SIL OFL (verified).
    - KaTeX: MIT, and it can pre-render equations at build time with no client JavaScript.
    - camera-controls: MIT, with promise-based camera transitions.
    - GSAP: free including all plugins since 30 Apr 2025, but under a proprietary "no charge" licence, not an open-source one.
11. **Hosting.** GitHub Pages, measured today:
    - every file, including content-hashed assets, is served with `Cache-Control: max-age=600`;
    - gzip only, even when brotli is requested;
    - byte-range requests work (HTTP 206), and CORS is open (`*`);
    - the ONNX Runtime wasm is 14.2 MB raw and 3.7 MB on the wire;
    - limits are 1 GB per site and a 100 GB/month soft bandwidth cap.

    Everything except running new scenarios can stay static. The existing `/v2` API (Server-Sent Events plus content-addressed traces) already covers "run a scenario and stream it to the view", so no WebSocket is needed.

---

## Q1. three.js r18x techniques and their cost on low/mid GPUs

### 1.1 Renderer: WebGLRenderer vs WebGPURenderer + TSL (state in r186)
- The installed version is r186 (`REVISION = '186'` in `site/node_modules/three/src/constants.js`). — local source — **High**
- **Release history and r186 changes.** Recent releases: r183 (20 Feb), r184 (16 Apr), r185 (1 Jul), r186 (September 2026). r186 adds cascaded shadow maps via `SunLight`, `compile()` support for node materials and a DirectRenderPipeline, removes the PCFSoftShadowMap code, and makes `Renderer.dispose()` async. — [three.js releases](https://github.com/mrdoob/three.js/releases); r186 release date per [CGWorld](https://cgworld.jp/flashnews/01-202610-Threejs-r186.html) — **Medium** (release pages summarised; years not shown on the releases page)
- In r186, `WebGLShadowMap` warns "PCFSoftShadowMap has been removed. Using PCFShadowMap instead." Any code asking for `PCFSoftShadowMap` silently gets `PCFShadowMap`. — local source `src/renderers/webgl/WebGLShadowMap.js` — **High**
- **What the three.js manual says:**
  - WebGLRenderer "is still maintained and the recommended choice for pure WebGL 2 applications", but "there are no plans to add larger new features to the renderer since the project's focus is now on `WebGPURenderer`".
  - WebGPURenderer "is still in an experimental state", and "depending on your application and scene setup, you will encounter missing features or a better performance with `WebGLRenderer`".
  - `ShaderMaterial`, `RawShaderMaterial` and `onBeforeCompile()` "are not supported in `WebGPURenderer`", nor is "`EffectComposer` with its effect passes".
  - WebGPURenderer falls back to WebGL 2 automatically, and `forceWebGL: true` forces that fallback.
  - Initialisation is asynchronous (`await renderer.init()` or `setAnimationLoop`).

  — [three.js manual: WebGPURenderer](https://threejs.org/manual/pages/webgpurenderer.html) — **High**
- **Browser support for WebGPU:**
  - Safari 26 on macOS, iOS, iPadOS and visionOS.
  - Firefox 141 on Windows and 145 on Apple-silicon macOS; Linux, Android and Intel Macs were still pending as of Nov 2025.
  - Chrome 121+ on Android 12+ with Qualcomm or ARM GPUs.

  — [web.dev, WebGPU supported in major browsers](https://web.dev/blog/webgpu-supported-major-browsers); [Khronos SIGGRAPH 2026 update](https://www.khronos.org/developers/linkto/webgl-and-webgpu-sigg26) — **Medium**
- `ClippingGroup`, which puts clipping into the scene graph, works only with WebGPURenderer. A forum user reported meshes inside a ClippingGroup that were not clipped. — [ClippingGroup docs](https://threejs.org/docs/pages/ClippingGroup.html); [forum report](https://discourse.threejs.org/t/clipping-plane-in-webgpu-bug-help/89669) — **Medium**
- A developer who migrated a large app reports that rewriting every ShaderMaterial in TSL and every post-processing pass "took a few months". — [three.js forum](https://discourse.threejs.org/t/is-there-a-migration-guide-on-webglrenderer-to-webgpurenderer/69005) — **Low**
- *Inference:* every LunarHaul shader is GLSL: terrain, sun-visibility bake, headlight cones. The planned Raptor-style chain (GTAO or N8AO, bloom, OutputPass, stencil caps) is all EffectComposer/WebGL. N8AO states it is "not yet compatible with WebGPU". Adopting WebGPU now costs weeks and buys nothing visible. Pin three at 0.186.x for the redesign and re-evaluate at a later release.

### 1.2 Cutaways: clipping planes and stencil caps
- **How the official `webgl_clipping_stencil` example works:**
  - For each plane, two copies of the mesh are drawn with `colorWrite = false`, `depthWrite = false` and `depthTest = false`. The back faces increment the stencil and the front faces decrement it.
  - A cap `PlaneGeometry` with a real material then draws where `stencil != 0` (`NotEqualStencilFunc`). It is clipped by the other planes and cleared afterwards with `renderer.clearStencil()` in `onAfterRender`.
  - `renderOrder` sequences the passes: groups at 1, 2, 3, caps at i + 1.1, and the clipped mesh last at 6.
  - Setup needs `new WebGLRenderer({ stencil: true })` and `renderer.localClippingEnabled = true`.

  Cost: three draws per plane (two stencil-only draws of the mesh, one cap). — [three.js example source](https://github.com/mrdoob/three.js/blob/dev/examples/webgl_clipping_stencil.html) — **High**
- In r186, WebGLRenderer's `stencil` option defaults to `false`, `localClippingEnabled` defaults to `false`, and MSAA (`antialias`) defaults to `false`. — [WebGLRenderer docs](https://threejs.org/docs/pages/WebGLRenderer.html) — **High**
- *Inference:* the stencil method only works on closed, watertight meshes. Procedural parts must not use `openEnded` cylinders or other open shells; nested tanks must each be closed.
- *Inference:* the cheaper trick seen on the Raptor page is to render back faces of a clipped mesh in a flat "cut" colour (`side: BackSide`). It needs one extra draw per mesh and no stencil, but shows interior back faces rather than a true section. It is good enough for tanks and hulls; use stencil caps where the section shape matters, such as tank walls with insulation.
- *Inference:* a two-plane wedge cut (Raptor's "wedge") uses `clipIntersection = true` on the material so only the region inside both planes is removed.

### 1.3 Exploded views
- No library is needed. The common method: compute the assembly's bounding-box centre, take the direction from it to each part, and offset each part by `direction × t × distance` from a slider value `t`. CAD-style explodes, which slide parts along their own axes and constraints, are harder; an alternative is to author the explode as a keyframed animation in Blender. — [three.js forum thread](https://discourse.threejs.org/t/how-can-i-split-a-glb-model-into-all-parts-in-react-three-fiber/32084) — **Low** (forum)
- *Inference:* procedural geometry makes this easy, because each part is created with a known local origin and an explode axis can be stored per part. Examples: legs out radially, tanks up along +Y, engine down. This is more readable than a radial explode.

### 1.4 Plumes on the Moon: what they actually look like, and how to render them
**Physics and appearance**
- Rocket exhaust entering near-vacuum forms a "highly underexpanded free jet". NASA TN D-2327 (1964) compares the boundary contours of such jets. NASA's 2026 plume–surface interaction (PSI) test programme labels its simulant plumes "Highly Under-Expanded Plume" and tests them at 0.75 Torr (100 Pa) in the 60-ft Langley vacuum sphere. — [NASA TN D-2327](https://ntrs.nasa.gov/citations/19640013118); [Korzun, Broslawski & Chambers, NASA PSI, IPPW 2026](https://ntrs.nasa.gov/api/citations/20260004959/downloads/NASAPSI_IPPW2026_v0.pdf) — **High**
- Shock diamonds form when the jet's exit pressure differs from the ambient air pressure, which then recompresses the flow. The article describes the effect for engines "operated in an atmosphere". — [Wikipedia: Shock diamond](https://en.wikipedia.org/wiki/Shock_diamond) — **Medium**
- *Inference:* with no ambient pressure to recompress the jet, a lunar plume has no diamond train. It expands monotonically and fades with distance.
- **Visibility by propellant:**
  - **Hydrolox** (Blue Moon's BE-7): a hydrogen flame "is nearly invisible during daylight hours" (NASA Spinoff, a terrestrial context). — [NASA Spinoff, "Making Visible the Invisible"](https://spinoff.nasa.gov/node/10136) — **High** for H₂ flames in daylight; **Medium** applied to a vacuum plume
  - **Hypergolic** (Apollo LM Aerozine 50/N₂O₄; Griffin's hydrazine derivative/MON-3): the exhaust is described as colourless and transparent, with no visible flame on Apollo ascent footage. — [moonhoaxdebunked.com §6.12](https://www.moonhoaxdebunked.com/2017/07/612-why-is-there-no-exhaust-from-lms.html) — **Low** (no NASA source found)
  - **Methalox** (Nova-C VR900, Starship Raptor and its GOX/GCH₄ landing thrusters): I found no authoritative description of a methalox vacuum plume's visible appearance. — **Low**, open question
  - Radiatively cooled nozzle extensions (niobium alloys and the like) shed heat by radiation and glow red in flight footage. — [Korean Society of Propulsion Engineers paper on radiative cooling](https://koreascience.kr/article/CFKO201132164220305.pdf); [forum discussion of the Merlin Vacuum glow](https://orbiter-forum.com/goto/post?id=276431) — **Low**
- **What landing imagery shows: dust.**
  - Apollo descent-video photogrammetry measured a dust ejection angle of 1–3° above horizontal. — [Immer, Lane, Metzger & Clements, NTRS 20130012063](https://ntrs.nasa.gov/citations/20130012063) — **High**
  - The Apollo 12 mission report says the landing "was essentially blind for approximately the last 40 feet". — [Metzger, Immer & Lane, arXiv 2104.06248](https://arxiv.org/pdf/2104.06248) — **High**
  - NASA's PSI deck lists "Visual Obscuration During Apollo 16 Landing" and "Near total obscuration of Perseverance rover during touchdown". — [NASA PSI, IPPW 2026](https://ntrs.nasa.gov/api/citations/20260004959/downloads/NASAPSI_IPPW2026_v0.pdf) — **High**
- **Blue Ghost / SCALPSS 1.1 (2 Mar 2025).** Four short-focal-length cameras imaged at 8 frames per second. The sequence starts ~28 m up. The reaction-control thruster plumes start acting on the surface at ~15 m, and then increasingly kick up "dust, soil and rocks". "After touchdown, the thrusters shut off and the dust settles." — [NASA: SCALPSS on Blue Ghost](https://www.nasa.gov/general/nasa-cameras-on-blue-ghost-capture-first-of-its-kind-moon-landing-footage/) — **High**
- Johns Hopkins researchers (Rui Ni's group) attribute the streaky patterns in landing dust to the Görtler instability: curved exhaust flow over the surface creates rotating vortices. — [JHU Hub, 21 Jul 2025](https://hub.jhu.edu/2025/07/21/lunar-landing-dust-debris) — **Medium** (page returned 403; read through a search summary)
- Starship HLS is reported to switch to "high-thrust landing engines located in the mid-body section" within ~100 m of the surface, burning gaseous oxygen and methane, to keep Raptor exhaust off the regolith. — [Wikipedia: Starship HLS](https://en.wikipedia.org/wiki/Starship_HLS) — **Medium** (no SpaceX primary source)
- *Inference: the rendering recipe.*
  1. **Near-field glow:** an additive, depth-faded cone or shell a few nozzle diameters long, with very low intensity. It is almost zero for hydrolox, faint for hypergolic and methalox. Optional red nozzle-extension glow.
  2. **Ejecta sheet:** GPU particles on analytic ballistic paths, p(t) = p₀ + v·t + ½·g·t² with g = 1.62 m/s² and no drag. Launch them radially at 1–3° with speeds drawn per particle from a seeded random generator, so a replay is identical every time. Start them when altitude falls below an onset height that scales with thrust (~15 m for Blue Ghost-class reaction-control thrusters).
  3. **Obscuration:** a ground-hugging translucent layer whose opacity peaks in the final seconds and drops to zero immediately at cutoff (no air to hold dust up).
  4. **Scour and blast decal:** a radial albedo change left on the terrain.

  Under a 1.5° sun the 1–3° sheet is almost parallel to the light, so the dust will look bright when the camera is looking toward the sun. That is a physically motivated "hero" effect.
- **Cost of raymarching instead.** Raymarched volumes scale with pixels × steps. Documented mitigations:
  - render at 0.5× resolution ("not a lot of differences between 1x and 0.5x");
  - offset ray starts with blue noise, plus a temporal component, to hide banding;
  - use fewer light-march steps and fewer noise (fBm) octaves.

  — [Maxime Heckel, Real-time cloudscapes with volumetric raymarching](https://blog.maximeheckel.com/posts/real-time-cloudscapes-with-volumetric-raymarching/) — **Medium** (no measured timings)

  *Inference:* a full-screen raymarched plume, as on the Raptor page, is the wrong spend for a vacuum plume that should be nearly invisible. Use particles (a few thousand on Tier 1, tens of thousands on Tier 3) and keep any raymarch for the dust cloud at half resolution on Tier 2–3 only.

### 1.5 Post-processing: AO, bloom, output, tone mapping
- **What r186 ships locally:** `GTAOPass`, `SAOPass`, `SSAOPass`, `UnrealBloomPass`, `OutputPass`, `SMAAPass`, `TAARenderPass`, `OutlinePass`, `SSRPass`. Tone-mapping constants: `ACESFilmicToneMapping`, `AgXToneMapping`, `NeutralToneMapping`. — local `site/node_modules/three/examples/jsm/postprocessing/`, `src/constants.js` — **High**
- **GTAOPass:**
  - Higher quality than `SSAOPass`, "but it costs more GPU time" (docs). Use `OUTPUT.Denoise` for the final output.
  - The official example chains RenderPass → GTAOPass → OutputPass with defaults radius 0.25, 16 samples, Poisson denoise with 16 samples and 2 rings.
  - `setSceneClipBox()` limits AO to a bounding box.

  — [GTAOPass docs](https://threejs.org/docs/pages/GTAOPass.html); [webgl_postprocessing_gtao source](https://github.com/mrdoob/three.js/blob/dev/examples/webgl_postprocessing_gtao.html) — **High**
- `SAOPass` is likewise described as better quality than `SSAOPass` but more expensive. — [SAOPass docs](https://threejs.org/docs/pages/SAOPass.html) — **Medium** (seen through a search summary)
- **N8AO:**
  - Licence CC0.
  - Quality presets (AO samples / denoise samples): Performance 8/4, Low 16/4, Medium 16/8, High 64/8, Ultra 64/16. The README recommends Performance for "Mobile, Low-end iGPUs and laptops".
  - `halfRes` gives a "2x-4x" speedup, with depth-aware upsampling costing "around 1ms".
  - Works with three's EffectComposer (`N8AOPass` replaces `RenderPass`) and with pmndrs postprocessing. SMAA is recommended because hardware MSAA does not work with AO.
  - "not yet compatible with WebGPU".

  — [N8python/n8ao](https://github.com/N8python/n8ao) — **High** (author's claims, no independent benchmark)
- A forum practitioner prefers N8AO through pmndrs postprocessing ("night and day performance difference") and says it looks clean at 6 samples, where the old SSAO needed more than 20. — [three.js forum](https://discourse.threejs.org/t/best-ssao-that-is-on-par-with-sketchfab-quality-performance/54284) — **Low**
- No published millisecond benchmarks of GTAO vs SAO vs N8AO on integrated GPUs were found; this needs our own measurement. — **Medium** (absence of evidence)
- **pmndrs postprocessing:**
  - Its `EffectPass` "automatically organizes and merges any given combination of effects", avoiding the cost of chaining passes.
  - Uses a single full-screen triangle.
  - Recommends `WebGLRenderer({ powerPreference: 'high-performance', antialias: false, stencil: false, depth: false })` and `HalfFloatType` frame buffers to avoid banding in dark scenes.
  - Zlib licence.
  - Note the conflict: our stencil-cap cutaways need `stencil: true` on the main buffer.

  — [pmndrs/postprocessing](https://github.com/pmndrs/postprocessing) — **High**
- `UnrealBloomPass` builds a mip chain and blurs each level with a different radius. Tone mapping must be enabled. Its cost scales with the `resolution` argument. — [UnrealBloomPass docs](https://threejs.org/docs/pages/UnrealBloomPass.html) — **High**
- `OutputPass` applies the renderer's tone mapping and colour-space conversion and "should be included at the end of each pass chain". Passes that expect sRGB input, such as FXAA, go after it. — [OutputPass docs](https://threejs.org/docs/pages/OutputPass.html) — **High**
- **Tone-mapping operators:**
  - **Khronos PBR Neutral** (three's `NeutralToneMapping`): no hue shifts; base colours in 0.08–0.8 reproduced exactly; compresses only highlights; invertible. — [KhronosGroup/ToneMapping PBR_Neutral](https://github.com/KhronosGroup/ToneMapping/blob/main/PBR_Neutral/README.md) — **High**
  - **AgX** is expected to look less saturated than ACES out of the box. — [three.js forum on AgX](https://discourse.threejs.org/t/is-agx-tonemapping-implemented-correctly/60609) — **Low**
  - **ACES Filmic** shifts hue and reduces saturation. — [three.js forum on ACES](https://discourse.threejs.org/t/acesfilmictonemapping-leading-to-low-contrast-textures/15484) — **Low**
- *Inference:*
  - On-site lunar views: use **Neutral**, so regolith albedo, white paint and gold multi-layer insulation (MLI) keep their hues under a hard white sun.
  - Exhibit and hangar views: the Raptor look (ACES at exposure ~0.86) is acceptable.
  - Decide with an A/B screenshot pair on real content, not from the curves.

### 1.6 Environment lighting: RoomEnvironment and PMREM vs lunar reality
- `RoomEnvironment` is "a scene with a basic room setup" fed to `PMREMGenerator.fromScene()`. The result is assigned to `scene.environment` for image-based lighting. It is based on model-viewer's EnvironmentScene. — [RoomEnvironment docs](https://threejs.org/docs/pages/RoomEnvironment.html) — **High**
- *Inference:* a studio room is the right environment for an "exhibit" view (vehicle on a dark stage, like the Raptor page) and the wrong one on the Moon.
  - On-site lighting is one hard directional sun at ≤1.5° elevation, a black sky, and weak fill.
  - The fill is bounce light from sunlit slopes. Level ground receives only sin(1.5°) ≈ 2.6 % of normal-incidence sunlight and reflects ~10 % of that, so shadowed sides of vehicles should be very dark.
  - For on-site views, build a tiny custom PMREM: a black upper hemisphere and a dim grey lower hemisphere, brightened toward the sun's azimuth.
- The Moon's surface brightens sharply near zero phase angle (the opposition effect). The coherent-backscatter peak is ~1.2° wide for highlands in red light and up to 3.9° for maria in blue light. — [Opposition effect of the Moon from LROC WAC data](https://dspace.nau.edu.ua/handle/NAU/56081) — **Medium**
- *Inference:* looking down-sun at the pole, regolith will look brighter than the current Lommel–Seeliger terrain shader predicts. A small backscatter term would add realism at almost no cost.

### 1.7 Shadows under a 1.5° grazing sun over km-scale terrain
- **SunLight in r186:**
  - New `SunLight` add-on with `SunLightShadow`: two cascaded shadow maps fitted to slices of the view frustum, a 10 % blend between cascades, and a default `mapSize` of 1024² per cascade; `camera.left/right/top/bottom` are ignored.
  - WebGLRenderer supports it: `WebGLLights` and `WebGLProgram` handle `SunLight` and `NUM_SUN_LIGHTS`.
  - WebGPU requires `renderer.library.addLight(SunLightNode, SunLight)`.

  — local `examples/jsm/lights/SunLight.js`, `SunLightShadow.js`, `src/renderers/webgl/WebGLLights.js`; [SunLight docs](https://threejs.org/docs/pages/SunLight.html) — **High**
- The older `CSM` add-on also ships. It injects its shader via `material.onBeforeCompile`, so it only affects materials it has patched. — local `examples/jsm/csm/CSM.js` — **High**
- *Inference:* neither SunLight shadows nor CSM reach our custom terrain `ShaderMaterial`. Two options:
  - **(a)** port the terrain to `MeshStandardMaterial` and inject the baked sun-visibility texture through `onBeforeCompile`, so built-in shadows work;
  - **(b)** keep the custom shader and sample a manually rendered vehicle shadow map in it.

  Option (b) is smaller.
- **Shadow geometry** (*Inference*, computed): at elevation e = 1.5°, shadow length = h / tan(1.5°) = 38.2 h. With the 0.267° solar radius already used in `scene.js`, the shadow tip smears from h / tan(1.767°) = 32.4 h to h / tan(1.233°) = 46.5 h. The lateral penumbra grows by ~0.0093 m per metre of distance from the top of the object.

  | Object (height) | Central shadow length | Tip smear | Lateral penumbra at the tip |
  |---|---|---|---|
  | Starship HLS class (52 m) | 1.99 km | 1.69–2.42 km | ~18 m |
  | Blue Moon MK1 (8.05 m) | 307 m | 261–374 m | ~3 m |
  | Nova-C (3.94 m) | 150 m | 128–183 m | ~1.4 m |
  | LTV class (2.6 m) | 99 m | 84–121 m | ~0.9 m |
  | Apollo LRV (1.14 m) | 44 m | 37–53 m | ~0.4 m |

- *Inference:* one shadow map cannot serve both a 2 km HLS shadow and a rover's wheels. A 2048² map covering the HLS shadow (~2.5 km) gives ~1.2 m texels. Covering a focused rover and its shadow (~150 m) gives ~7 cm texels. Plan:
  - fit the shadow camera tightly to the focused vehicle plus its shadow;
  - keep terrain-on-terrain shadows in the existing baked visibility texture;
  - for unfocused vehicles far away, draw a cheap projected "shadow strip" decal of the computed length and direction.
- Forum guidance confirms the levers: a tighter shadow frustum concentrates texels, and too large a far plane causes precision stripes; tune `bias` and `normalBias`. — [three.js forum 48732](https://discourse.threejs.org/t/how-to-deal-with-choppy-shadows-light-bias-is-not-an-issue/48732) — **Medium**

### 1.8 Depth precision for metre-to-kilometre scenes
- **WebGLRenderer depth options:**
  - `logarithmicDepthBuffer` "uses `gl_FragDepth` if available which disables the Early Fragment Test optimization and can cause a decrease in performance".
  - `reversedDepthBuffer` "Requires the `EXT_clip_control` extension. This is a more faster and accurate version than logarithmic depth buffer". Check `renderer.capabilities.reversedDepthBuffer` at runtime.

  — [WebGLRenderer docs](https://threejs.org/docs/pages/WebGLRenderer.html) — **High**
- *Inference:* today's camera uses near = 5 m and far = 120 km, and vehicles are scaled to a constant screen size (`scene.js`). True-scale close-ups need near ≈ 0.05–0.2 m. Use `reversedDepthBuffer` where available. Elsewhere, adapt the near/far planes to the camera's distance from its target, or fall back to `logarithmicDepthBuffer` on Tier 2–3.

### 1.9 Instancing, BatchedMesh, LOD
- `BatchedMesh` draws many objects with one material but different geometries in a single multi-draw call. It supports per-object frustum culling and sorting. Its limitations: reserved space is fixed, negative scale is not supported, and bounds are opt-in. — [BatchedMesh docs](https://threejs.org/docs/pages/BatchedMesh.html) — **High**
- Official examples exist for `webgl_lod`, `webgl_instancing_performance`, `webgl_lines_fat` and `webgl_shadowmap_csm`. — [three.js examples/files.json](https://threejs.org/examples/files.json) — **High**
- *Inference:*
  - `InstancedMesh` for many identical things: boulders, rover wheels across a fleet, cargo crates, pad markers, ejecta particles.
  - `BatchedMesh` for the base: many module shapes sharing one material.
  - `LOD` with two or three levels per vehicle (full detail under ~200 m, a simple silhouette under ~2 km, an icon beyond). The current constant-screen-size icons become the far level.

### 1.10 Labels and leader lines: CSS2D vs in-canvas
- **Forum evidence on DOM-label cost:**
  - One user reported CSS2DRenderer using over 80 % CPU while idle with many labels. — [three.js forum](https://discourse.threejs.org/t/does-css2drenderer-ignore-automatrixupdate-false/67064)
  - With ~50 HTML labels in Chrome, frame rate dropped below 5 fps. — [three.js forum](https://discourse.threejs.org/t/many-html-elements-from-three-js-fiber-drei-causes-low-framerate-in-chrome/28540)
  - troika SDF text added more than 300 draw calls; instanced atlas labels scale further but pixelate when zoomed. — [three.js forum](https://discourse.threejs.org/t/how-to-create-lots-of-optimized-2d-text-labels/66927)
  - Hide labels that are off-screen or behind the camera. — [three.js forum](https://discourse.threejs.org/t/css2drenderer-labels-goes-outside-the-scene-on-rotation/90642)

  **Low** (anecdotal; no controlled benchmark)
- *Inference:* keep CSS2D for the Raptor-style callout pills, roughly 5–20 visible at once. They are real DOM, so they can take focus and be read by screen readers, which in-canvas text cannot.
  - Draw leader lines in-canvas with `Line2` fat lines (constant pixel width), anchored to a part's world point and ending at the pill.
  - Write `textContent` only on change, as the existing `setText()` already does.
  - Cull labels by visibility and occlusion.
  - Use instanced in-canvas text only for many simultaneous labels, such as a fleet overview.

### 1.11 Camera choreography and tweening
- **camera-controls** (MIT):
  - `setLookAt(…, enableTransition)`, `fitToBox`/`fitToSphere` with padding, and `smoothTime` (default 0.25 s, SmoothDamp easing).
  - Transitions return promises.
  - `setBoundary(box3)`, `setOrbitPoint`, rest/sleep events, and JSON save/load of camera state.
  - Install with `CameraControls.install({ THREE })`. `update(delta)` returns true when a redraw is needed.

  — [yomotsu/camera-controls](https://github.com/yomotsu/camera-controls) — **High**
- **GSAP**, including formerly paid plugins, is free for commercial use under Webflow's "Standard 'No Charge' License" effective 30 Apr 2025. Use is prohibited in no-code visual animation builders that compete with Webflow. — [Webflow blog](https://webflow.com/blog/gsap-becomes-free); [GSAP standard licence](https://gsap.com/community/standard-license/) — **Medium**
- *Inference:* camera-controls covers the per-mode re-framing seen on the Raptor page; GSAP is not needed for that. Its "sleep" event is a natural hook to stop rendering when nothing moves, which saves battery. Under `prefers-reduced-motion`, cut directly to the new view (`enableTransition = false`).

### 1.12 Animated flow along pipes and paths
- Common techniques:
  - scroll a repeating texture's UV offset along a `TubeGeometry`, whose v coordinate runs along the length;
  - use an arrow texture with transparency;
  - or store a 0–1 path parameter per vertex and compare it to a time uniform in the fragment shader.

  — [Babylon.js forum](https://forum.babylonjs.com/t/how-to-implement-a-shader-with-light-flow-effect-along-a-specific-path-tube-mesh/24688); [Codrops tubes tutorial](https://tympanus.net/codrops/2017/05/09/infinite-tubes-with-three-js/) — **Low/Medium**
- *Inference:* for the base view, draw rover legs as flat ribbons draped on the terrain, with a shader dash moving at a speed proportional to cargo flow (t/h) and coloured by owner. Inside a lander cutaway, use the same shader on propellant feed lines, like Raptor's "Follow Oxygen/Methane". Under reduced motion, freeze the dashes and show the number instead.

### 1.13 Frame budgets, quality tiers, reduced motion
- At 60 Hz a frame has 16.7 ms and at 30 fps 33.3 ms (arithmetic).
- **detect-gpu tiers:** Tier 0 = no WebGL or <15 fps (needs a fallback), Tier 1 ≥15 fps, Tier 2 ≥30 fps, Tier 3 ≥60 fps. Its upstream benchmark data stopped updating in Dec 2025. — [pmndrs/detect-gpu](https://github.com/pmndrs/detect-gpu) — **High**
- *Inference:* GPUs released in 2026 will be unknown to detect-gpu, so a runtime check is needed as well.
- drei's `PerformanceMonitor` pattern:
  - average fps over samples against refresh-rate-based bounds;
  - call `onDecline`/`onIncline` to step device-pixel-ratio down or up;
  - stop after too many flip-flops (`onFallback`).

  It is a React Three Fiber component, but the logic is ~40 lines to copy into vanilla code. — [drei PerformanceMonitor](https://drei.docs.pmnd.rs/performances/performance-monitor) — **Medium**
- The earlier notes' pixel budget still applies: cap the drawing buffer at about 5.2 MP and derive the pixel ratio from it, and keep the light count constant to avoid shader recompiles. — [Codrops, "Sixty Frames for the Record"](https://tympanus.net/codrops/?p=119712), as summarised in `web_visualisation_design.md` — **Medium**
- **`prefers-reduced-motion`:** values `no-preference` and `reduce`; Baseline widely available since January 2020; set by the OS ("Reduce motion" on macOS and iOS, "Animation effects" on Windows 11, "Remove animations" on Android). It notes that "scaling or panning large objects can be vestibular motion triggers". — [MDN prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion) — **High**
- **WCAG 2.2.2 Pause, Stop, Hide (Level A):** moving content that starts automatically, lasts more than 5 seconds and runs in parallel with other content needs a way to pause, stop or hide it. — [W3C Understanding 2.2.2](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html) — **High**
- *Inference — proposed tier table (to be checked on real devices):*

  | Tier | Typical device | Pixel budget | AO | Bloom | Shadows | Plume particles | Other |
  |---|---|---|---|---|---|---|---|
  | 0 | no WebGL2 / <15 fps | — | — | — | — | — | 2D plan or side view (exists) |
  | 1 | Intel UHD/Iris, older phones | ~1.5–2 MP | off | off or half-res | focused vehicle only, 1024² | ≤5k | no MSAA, FXAA or SMAA |
  | 2 | RTX 3050 laptop, Apple M1–M2, recent phones | ~3–3.5 MP | N8AO Low, half-res | half-res | 2048² focus | ≤30k | SMAA |
  | 3 | desktop dGPU | ≤5.2 MP | GTAO or N8AO Medium | full | 2×2048² SunLight cascades | ≤100k | dust raymarch at 0.5× |

### 1.14 The current site, measured (2026-10-22)
- Built assets:
  - `three.module` is 531 KB raw and 133 KB gzip on the wire;
  - `ort-wasm-simd-threaded` (ONNX Runtime) is 14.24 MB raw and 3.72 MB gzip;
  - the `lab-lander` chunk is 295 KB;
  - the two Source Sans 3 variable woff2 files are 170 KB and 138 KB;
  - `dist/` is 50 MB, including source maps, which are deployed (`three.module…js.map` returns 200, 2.8 MB).

  — local `site/dist/assets`; curl against the live site — **High** (measured)
- Vehicles are `MeshBasicMaterial` boxes and cylinders, so unlit, scaled per frame to a constant screen size. Labels use `CSS2DRenderer`. `OrbitControls` is set to `minDistance = 150 m`. The camera has near = 5 m, far = 120 km. The renderer is created without `stencil`. — `site/src/world/scene.js` — **High**

---

## Q2. Reference geometry and appearance for procedural models

### 2.1 Vehicles (true-scale numbers for the procedural kit)

| Our class | Reference vehicle | Size | Legs or wheels | Engine and propellant (plume class) | Notes | Source, confidence |
|---|---|---|---|---|---|---|
| CLPS lander (2 t at gate) | Intuitive Machines Nova-C | Hexagonal cylinder; 3.938 m tall (infobox says 3 m); 2 m diameter (NASA paper: 1.6 m) | 6 landing legs | VR900, 3,100 N, gimballed, pressure-fed, LOX/LCH₄ (methalox) | 3 solar panels (top deck plus two body panels); IM-1 broke a leg and came to rest at ~30°; IM-2 fell on its side | [Wikipedia: Nova-C](https://en.wikipedia.org/wiki/Intuitive_Machines_Nova-C) **Medium**; [NASA NDL paper](https://ntrs.nasa.gov/api/citations/20250007036/downloads/aasimndl.pdf) **High** |
| CLPS lander (alternative look) | Astrobotic Griffin | Image labels "4.5M" (width) and "2.0M" (height, by context); 15 ft wide per press | 4 legs | Current page: 7 main engines + 4 attitude-control clusters; 2022 user guide: 5 × 3,114 N pulsed + 12 × 111 N, hypergolic M20/MON-3 | Aluminium frame, isogrid payload deck, optional egress ramps; 625 kg payload; Griffin-1 carries Astrolab's FLIP rover to Nobile crater, late 2026 | [Astrobotic Griffin page](https://www.astrobotic.com/lunar-delivery/landers/griffin-lander/) **Medium**; [Astrobotic user guide 2022](https://www.astrobotic.com/wp-content/uploads/2022/01/PUGLanders_011222.pdf) **High**; [FLIP on Griffin-1](https://www.astrobotic.com/astrolabs-flip-rover-joins-astrobotics-griffin-1-to-the-moon/) **Medium** |
| Blue Moon MK1 class (~9 t at gate) | Blue Moon MK1 | "roughly cylindrical", 8.05 m tall, 3.08 m primary outer diameter | Not published (no source found) | 1 × BE-7, LH₂/LOX (hydrolox, nearly invisible), ~40–44 kN | Solar panels, fuel cells and batteries; hot- and cold-gas thrusters; wet mass < 21,350 kg; Pathfinder MK1 "Endurance" NET Q1 2027 to the south pole, 100 m landing accuracy | [Gunter's Space Page](https://space.skyrocket.de/doc_sdat/blue-moon.htm) **Medium**; [Wikipedia: Pathfinder Mission 1](https://en.wikipedia.org/wiki/Blue_Moon_Pathfinder_Mission_1) **Medium** |
| 60 t large cargo lander | Starship HLS | 52 m tall (NASA IAC 2025), 9 m diameter; NASA OIG: 171 ft tall, crew ride an elevator ~115 ft down | Not published in text (Musk 2021: "Lunar landing legs don't add much") | 3 Raptor + 3 Raptor Vacuum, LCH₄/LOX; mid-body GOX/GCH₄ landing thrusters within ~100 m of the surface | No heat shield or flaps; "a band of solar panels around the circumference"; airlock below the crew cabin; elevator from the deck to the surface; HLS-specific insulating tiles | [Wikipedia: Starship HLS](https://en.wikipedia.org/wiki/Starship_HLS) **Medium**; [NASA astronauts practise with HLS airlock and elevator](https://www.nasa.gov/directorates/esdmd/artemis-campaign-development-division/human-landing-system-program/nasa-astronauts-practice-next-giant-leap-for-artemis) **Medium**; [SpacePolicyOnline on the OIG report](https://spacepolicyonline.com/?p=87371) **Medium** |
| (scale reference) Blue Moon MK2 | Blue Moon MK2 | ~16 m tall | — | 3 × BE-7 | Artemis V crew lander | [Creech, NASA IAC 2025](https://ntrs.nasa.gov/api/citations/20250008728/downloads/25%2008%2026%20IAC_Creech%20BP-1.pdf) **High** |
| LTV (1.5 t, 6 km/h) | Astrolab CLV-1 (from FLEX) | Stowed ~2 × 2.3 × 2.2 m; deployed ~4 × 2.3 × 2.6 m; 950 kg | 4 wheels (FLEX: crab steering keeps the solar array on the Sun) | Electric | FLEX top-deck payload up to 2,000 kg (another figure: 1,600 kg) plus up to 3 m³ slung underneath; standing crew deck; robotic arm | [Astrolab 26 May 2026](https://www.astrolab.space/2026/05/26/nasa-selects-astrolab-to-provide-lunar-rover-for-artemis-astronauts-return-to-the-moon/) **Medium**; [astrolab.space](https://www.astrolab.space) **Medium** |
| LTV (alternative) | Lunar Outpost Pegasus | No public spec sheet; "less than half the size" of Eagle; two crew side by side | Goodyear tyres | Electric | Successor to Eagle (2.4 t cargo including crew, 16 mph) | [Payload Space](https://payloadspace.com/lunar-outpost-closes-30m-series-b-unveils-new-rover/) **Low**; Eagle figures via [National Geographic](https://www.nationalgeographic.com/science/article/moon-rover-space-innovation-nasa-artemis) **Medium** |
| LTV (alternative) | Intuitive Machines Moon RACER | 4.3 × 2.6 × 3.7 m | — | Electric | Up to 15 km/h, ~20° slopes, 30 cm obstacles; not selected in May 2026 | [collectSPACE](https://www.collectspace.com/news/news-110724a-intuitive-machines-racer-lunar-terrain-vehicle-reveal.html) **Medium** |
| MICRO (0.3 t, 3 km/h) | VIPER (scale) | 1.7 × 1.7 × 2.5 m; 447 kg roving | 4 wheels, 50 cm diameter, 2.5 cm grousers | Electric | Now planned for 2027 on New Glenn | [Bluethmann, LSIC 2024](https://ntrs.nasa.gov/api/citations/20240013903/downloads/LSIC_2024-Tech%20Infusion_Panel-VIPER_Mob-HW.pdf) **High**; [Wikipedia: VIPER](https://en.wikipedia.org/wiki/VIPER_(rover)) **Medium** |
| HAUL (10 t, works at night) | No flown or built analogue; nearest concept is JPL ATHLETE / Tri-ATHLETE | 1st gen 2.75 m wide, ~2 m standing height, ~850 kg; 2nd gen stands up to just over 4 m, 450 kg payload in Earth gravity | 6 wheel-on-legs (6 joints per limb + wheel); two Tri-ATHLETE halves dock to a cargo pallet | Electric | Designed to offload cargo from a 3.2 m-high lander deck | [JPL ATHLETE](https://robotics.jpl.nasa.gov/how-we-do-it/systems/the-athlete-rover/) **Medium**; [Heverly et al. 2010](https://www-robotics.jpl.nasa.gov/media/documents/Heverly_2010_AMS_Tri-ATHLETE.pdf) **Medium** |
| (scale reference) | Apollo LRV | Frame 3.1 m long; 2.3 m wheelbase; max height 1.14 m; 36 cm ground clearance loaded; 210 kg | 4 wheels, 81.8 cm diameter, 23 cm wide; woven zinc-coated steel-strand tyres with titanium chevrons over 50 % of the contact area | Silver-zinc batteries | Aluminium 2219 tube frame | [NSSDC LRV](https://nssdc.gsfc.nasa.gov/planetary/lunar/apollo_lrv.html) **High** |

*Inference:* HAUL has no real counterpart, so its model should look deliberately generic and carry a "concept" label. A good fit is a low flat-bed with 6 large wheels, a cargo pallet interface (as on ATHLETE), radiators and headlights for night work, and no solar mast.

### 2.2 Materials and colours
- **MLI:** "multi-layer insulation" made of polyimide or polyester films "coated with very thin layers of aluminum". The gold look comes from "the yellowish-gold color of the polyimide on the outside", in "a single layer of aluminized polyimide with the silver aluminum side facing in". — [NOAA NESDIS, "As Good As Gold"](https://www.nesdis.noaa.gov/node/87) — **High**
- *Inference:*
  - Gold MLI: `MeshPhysicalMaterial`, metalness ~1, amber base colour, roughness 0.3–0.5, plus a normal map of crinkles. The crinkle normals make it read correctly under a single hard light.
  - Silver MLI: the same with a neutral base colour.
  - White painted areas: dielectric, roughness ~0.6.
  - Solar cells: very dark blue, low roughness.
  - Lower parts dusted with regolith colour.
- **Regolith albedo:**
  - Moon geometric albedo 0.12; Bond albedo 0.11. — [NSSDC Moon fact sheet](https://nssdc.gsfc.nasa.gov/planetary/factsheet/moonfact.html) — **High**
  - At full Moon, maria have albedos of 5–8 % and highlands 9–12 %. — [NASA Remote Sensing Tutorial mirror](https://wgbis.ces.iisc.ac.in/envis/Remote/section193.htm) — **Medium**
  - Albedo figures depend on wavelength, phase angle and definition (normal, geometric or Bond). — [USGS: The Moon in Heiligenschein](https://pubs.usgs.gov/publication/70012591) — **Medium**
  - *Inference:* the south pole is highlands, so use a linear base colour of ~0.10–0.13 with a very slight warm tint. Do not use "enhanced colour" mosaics as colour truth: LROC WAC colour products are built from 689, 415 and 321 nm bands (the last ultraviolet). — [LROC Hapke maps post](https://lroc.im-ldi.com/posts/801) — **High**
  - Returned samples range from dark charcoal to light grey, with exceptions such as the Apollo 17 orange glass ("It's orange!"). — [ZME Science](https://zmescience.com/other/feature-post/the-real-color-of-the-moon-and-why-its-probably-not-what-you-think) — **Low**
- **Sun and sky:**
  - At the pole the Sun "glides around the horizon, never more than a few degrees above or below it". — [NASA SVS 5228](https://svs.gsfc.nasa.gov/5228) — **High**
  - Elsewhere it is "never more than 1.5°". — [NASA SVS 4893](https://svs.gsfc.nasa.gov/4893) — **High**
  - *Inference:* the sky is black. Stars should be off, or very faint behind an "exposure" toggle, because any exposure suited to sunlit regolith hides them.
- **Earth in the sky:**
  - Earth "bobs up and down, never veering far from 0° longitude". — [NASA SVS 5228](https://svs.gsfc.nasa.gov/5228) — **High**
  - Libration in latitude reaches 6°50′. — [Wikipedia: Libration](https://en.wikipedia.org/wiki/Libration) — **Medium**
  - *Inference:* at the pole, Earth's elevation ≈ the sub-Earth latitude, so Earth stays within about ±7° of the horizon and is below the geometric horizon roughly half of each month.
  - An ICSSC 2023 paper says Earth is not visible from the south pole for nominally 14 days per month. — [NTRS 20230013361](https://ntrs.nasa.gov/api/citations/20230013361/downloads/ICSSC-2023_LSR_paper%20rev7k.pdf) — **Medium**
  - NASA: "At the South Pole of the Moon, the Earth sits low on the horizon, sometimes out of sight all together." — [NASA Glenn, lunar surface propagation](https://www.nasa.gov/glenn/glenn-expertise-space-exploration/scan/lunar-surface-propagation/) — **Medium** (via search summary)
  - Earth's apparent diameter from the Moon is ~1.9°, about four times the Moon's from Earth. — [Wikipedia: Earth phase](https://en.wikipedia.org/wiki/Earth_phase) — **Medium**; consistent with 12,742 km / 384,400 km = 1.90° (my arithmetic).
  - *Inference:* this is a strong, true, story-relevant visual. Earth near the horizon, and hidden for half the month, explains why the base needs relay satellites and why teleoperation latency matters.

### 2.3 Ready-made 3D assets and licences
- **NASA material:**
  - Generally not subject to US copyright; credit NASA; do not imply endorsement.
  - The "NASA Insignia, Logotype, identifiers, and imagery are not in the public domain".
  - The exemption covers "material used to render 3-dimensional models, including texture maps and polygon data".

  — [NASA images and media usage guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/) — **High**
- NASA 3D Resources (science.nasa.gov/3d-resources, GitHub mirror nasa/NASA-3D-Resources) has an Apollo LM (3DS, ~100k polygons), LRO, Gateway, SLS and RASSOR, but no LRV, VIPER, Artemis lander or LTV. Searches in this session found no new official VIPER or LRV glb. — [NASA 3D Resources](https://science.nasa.gov/3d-resources/); [nasa/NASA-3D-Resources](https://github.com/nasa/NASA-3D-Resources); see `terrain_data_3d_assets.md` KQ3 — **High** (earlier listing) / **Medium** (absence this session)
- **Marketplace models:**
  - Blue Moon HLS on CGTrader: $50, royalty-free. — [CGTrader](https://www.cgtrader.com/3d-models/space/spaceship/blue-moon-lunar-lander)
  - Blue Moon MK1 on RenderHub: "Editorial Use Only Restriction". — [RenderHub](https://www.renderhub.com/gemreer/blue-moon-mk1-lunar-lander-game-ready)
  - Starship HLS on Superhive: $249, "Creative Commons" without a specific variant. — [Superhive](https://superhivemarket.com/products/spacex-starship-hls--interior--rigged-3d-model)
  - VIPER on TurboSquid: $69, "Editorial Uses Only". — [TurboSquid](https://www.turbosquid.com/3d-models/viper-nasa-moon-exploration-rover-silver-2531640)
  - A CC0 Blender LRV was posted on Blender Artists; its author calls it "at best only a good likeness". — [Blender Artists](https://blenderartists.org/t/nasa-lunar-rover-scene-file/1610886)
  - No CC BY Sketchfab model of HLS or Blue Moon was found.

  **Medium**
- **glTF compression tooling:**
  - `gltf-transform` CLI: `optimize` (all steps, e.g. `--compress draco --texture-compress webp`), `draco`, `meshopt` (geometry and animation), `simplify`, `etc1s` and `uastc` (KTX2/Basis), `webp`, `resize`, `instance`, `dedup`, `prune`. — [glTF Transform CLI](https://gltf-transform.dev/cli) — **High**
  - `gltfpack`: meshopt codecs designed to compress further under gzip; `-tc` writes KTX2/BasisU; three.js r122+ needs `GLTFLoader.setMeshoptDecoder`. — [meshoptimizer gltfpack](https://meshoptimizer.org/gltf/) — **High**
  - KTX2/Basis: ETC1S gives "significantly smaller transmission and GPU memory sizes than JPEG and PNG"; UASTC trades size for quality. — [Khronos KTX](https://www.khronos.org/ktx/) — **High**
- **Trade-off: procedural geometry vs glTF assets** (*Inference*):
  - Procedural: zero download beyond a few KB of code; exact parametric dimensions from the table above, which keeps the "every number is sourced" rule; part hierarchy and explode axes for free; easy closed meshes for stencil caps; no licence or trademark risk; style matches the Raptor reference, which is itself procedural. Cost: it takes modelling effort in code, and fine detail (MLI crinkles, bolts, cabling) must come from normal maps or decals.
  - glTF: fast to get a detailed look, but every model here is either unavailable, paid, editorial-only or trademark-laden. On GitHub Pages each asset also pays the 10-minute revalidation, and KTX2/meshopt adds decoder wasm (Basis transcoder, meshopt decoder) to the page weight.
  - Use procedural for all LunarHaul vehicles. Consider glTF only for the NASA Apollo LM as a 1969 scale reference.

---

## Q3. UI/UX patterns for professional scientific interactive visualisation

### 3.1 Explorable explanations and guided narratives
- Bret Victor (2011, with a 2024 postscript) separates:
  - reactive documents, where readers change the model's assumptions and see the conclusions update;
  - explorable examples;
  - contextual information.

  He warns "Most interactive widgets dump the user in a sandbox". The 2024 postscript says he meant "a written argument whose assertions are backed by explorable computational models", not any article with interactive graphics. — [worrydream.com, Explorable Explanations](http://worrydream.com/ExplorableExplanations/) — **High**
- Nicky Case's explorables (e.g., The Evolution of Trust) are released into the public domain under a CC0 waiver. The explorabl.es hub frames them as "learning through play". — [ncase.me](https://ncase.me/); [explorabl.es](https://explorabl.es/) — **High**
- **Distill review of interactive articles** (Hohman, Conlen, Heer & Chau, 2020):
  - Benefits: connecting people to data, playful live models, prediction prompts with feedback, segmenting, and details on demand.
  - Caveats: "not everything needs to be interactive"; authoring is "closer to building a website than writing a blog post"; accessibility is "an open challenge"; "There is limited empirical evaluation of the effectiveness of interactive articles".
  - Zhi et al. found comprehension "was better in slideshow layouts than in vertical scroll-based layouts"; McKenna et al. found no significant engagement difference.

  — [Distill: Communicating with Interactive Articles](https://distill.pub/2020/communicating-with-interactive-articles/) — **High**
- McKenna et al., EuroVis 2017, a crowdsourced study with 240 participants: visuals and navigation feedback affected engagement; discrete versus continuous control did not appear to matter. — [Utah VDL: Visual Narrative Flow](https://vdl.sci.utah.edu/publications/2017_eurovis_narrative-flow/) — **Medium** (read through a summary)
- Practitioner critique (eagereyes, Robert Kosara, 2016): scrolling is a poor fit for step-based stories, and readers lose a sense of length. — [The Scrollytelling Scourge](https://eagereyes.org/blog/2016/the-scrollytelling-scourge) — **Medium**
- **NASA Eyes on the Solar System:**
  - Runs in the browser; covers 126 missions from 1949 to 2049; lets users "modulate perspective and lighting"; offers guided "interactive journeys" such as Voyager's Grand Tour. — [JPL news 2022](https://www.jpl.nasa.gov/news/explore-the-solar-system-with-nasas-new-and-improved-3d-eyes/) — **High**
  - The app itself could not be fetched as text (JavaScript-only), so its current panel names were not verified. — **Low**
- *Inference — the pattern to copy from the Raptor page:*
  - a small set of discrete modes (segmented pill controls);
  - a left narrative card whose text changes with the mode;
  - camera re-framing per mode;
  - stat chips with units;
  - callouts anchored to parts.

  This is a stepper with free exploration around it, which suits a research site better than scrollytelling. Every mode should end on a real model number with its source, to satisfy Victor's "assertions backed by explorable models".

### 3.2 Big animated counters, equations and reel motifs
- **Screen-reader behaviour for changing numbers** (MDN):
  - use `aria-live="polite"` for most updates; `assertive` "should only be used for time-sensitive/critical notifications";
  - `role="timer"` and `role="marquee"` default to `aria-live="off"`, so changes are announced only when focus is inside the element;
  - create live regions in the initial markup and update them later.

  — [MDN ARIA live regions](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions) — **High**
- `font-variant-numeric: tabular-nums` selects equal-width figures (OpenType `tnum`), which stops digits jittering while a counter runs. — [MDN font-variant-numeric](https://developer.mozilla.org/en-US/docs/Web/CSS/font-variant-numeric) — **High**
- WCAG 1.4.1 (Use of Color): colour must not be the only means of conveying information. — [W3C Understanding 1.4.1](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html) — **High**
- KaTeX is MIT-licensed and can "pre-render expressions using Node.js and send them as plain HTML". If all rendering is server-side, "there is no need to include the JavaScript on the client"; only the CSS and fonts are needed. — [KaTeX](https://github.com/KaTeX/KaTeX) — **High**
- *Inference:*
  - **SCORE counter** (Hari's reel): animate the count only when the value changes, over about 400 ms. Always show the sign and a ▲/▼ glyph alongside the red/green. Announce only the final value of each episode through a polite live region. Under reduced motion, snap to the value.
  - **Word-by-word captions** (SpaceX reel): these are a video device. On a web page, use static narrative text with highlighted keywords.
  - **Boxed monospace tags** ("LIGHT MISSION" in the reel): map to our real categories, e.g. "CLPS CLASS · 2 t AT GATE", "NIGHT OPS", "PLUME KEEP-OUT 1.2 km".
  - **Rainbow streamlines** (SimScale CFD reel): look "pro" but misrepresent data. Use a perceptually uniform map such as Crameri's batlow for any field. — [Crameri scientific colour maps](https://www.fabiocrameri.ch/colourmaps/) — **High**

### 3.3 Colour, contrast and the dark glass panels
- **WCAG 2.2 contrast thresholds:**
  - 1.4.3 Contrast (Minimum), AA: text needs 4.5:1, or 3:1 for large text (≥ 18 pt, or 14 pt bold; roughly 24 px or 18.5 px bold).
  - Thresholds do not round: 4.499:1 fails.
  - Background images that do not give enough contrast are failure F83.

  — [W3C Understanding 1.4.3](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) — **High**
- 1.4.11 Non-text Contrast, AA: UI components, the parts of graphics "required to understand the content", and focus indicators need 3:1 against adjacent colours. — [W3C Understanding 1.4.11](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) — **High**
- **New in WCAG 2.2:**
  - 2.4.11 Focus Not Obscured (Minimum), AA: a focused element must not be fully hidden by author content, which matters for floating glass panels.
  - 2.5.7 Dragging Movements, AA: anything done by dragging must also be possible with a single pointer, so orbit/pan/zoom need buttons too.
  - 2.5.8 Target Size (Minimum), AA: 24 × 24 CSS px.

  — [W3C: What's new in WCAG 2.2](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/) — **High**
- **Computed contrast for the reference tokens** — **High** (calculation). WCAG relative-luminance formula; sRGB alpha compositing of panel #0c1426 at α = 0x9e/255 = 0.62 over the scene colour behind it. Backdrop blur averages the scene, so a large bright region is the realistic worst case. The 20-line Node script used for this sat in the session scratchpad and is not kept in the repository; the method above is enough to reproduce it.

  | Behind the text | ink #eef3fb | muted #93a0b6 | faint #5d6a80 | cool #7fd8ff | warm #ffae4a |
  |---|---|---|---|---|---|
  | page #030509 (no panel) | 18.3 | 7.7 | 3.7 | 12.8 | 11.1 |
  | glass over dark scene #202020 | 15.9 | 6.7 | 3.2 | 11.1 | 9.6 |
  | glass over mid-grey #808080 | 9.8 | **4.1** | **2.0** | 6.8 | 5.9 |
  | glass over lit regolith #b0b0b0 | 7.3 | **3.1** | **1.5** | 5.1 | **4.4** |
  | glass over white (lander, bloom) #ffffff | 4.6 | **2.0** | **1.1** | **3.2** | **2.8** |

  Bold marks a value below 4.5:1 for body text.
- **Okabe-Ito and Tol Bright contrast against #030509** (my calculation):
  - Okabe-Ito blue #0072B2: 3.9:1.
  - Tol Bright purple: 3.4:1; Tol Bright blue: 4.3:1.

  These are fine for lines and markers (3:1) but too dark for small text on a near-black page.
  - Colour choice rules: avoid red–green pairs; show differences in both colour and shape; label directly. — [Okabe & Ito, Color Universal Design](https://jfly.uni-koeln.de/color/) — **High**
  - *Inference:* the reference's cool #7fd8ff and warm #ffae4a sit on the blue–orange axis, which is safe for colour-blind readers. Keep them as the two-category accent pair, for example propellant vs oxidiser, or day vs night.

### 3.4 Keyboard and screen-reader access to a WebGL scene
- **Community practice and its limits:**
  - Label the canvas and mirror its meaningful content in visually hidden but accessible DOM. — [three.js forum: Accessibility for 3D websites](https://discourse.threejs.org/t/accessibility-for-3d-websites/87092) — **Low**
  - `@react-three/a11y` puts semantic DOM elements over the canvas and announces through a polite live region. — [react-three-a11y docs](https://docsearch.algolia.com/mcp/docs/repo/pmndrs/react-three-a11y) — **Medium**
  - A W3C thread notes that canvas fallback content "isn't really fit for purpose for most production use cases", and an accessibility engineer warns that live regions have drawbacks for braille and speech-recognition users. — [public-webapps-github, Jun 2025](https://lists.w3.org/Archives/Public/public-webapps-github/2025Jun/0274.html) — **Low/Medium**
- *Inference:* the PLAN already requires a DOM telemetry table and a 2D plan view that mirror the canvas. Keep both, and extend them:
  - mode pills and callouts as real `<button>`s;
  - camera presets reachable by keyboard (e.g. 1–5) and as buttons, which also satisfies 2.5.7;
  - Esc to stop camera motion;
  - visible focus rings at 3:1;
  - no glass panel covering a focused control.

### 3.5 Fonts
- **Outfit:** "licensed under the SIL Open Font License, Version 1.1", released by Outfit.io. — [Outfitio/Outfit-Fonts](https://github.com/Outfitio/Outfit-Fonts) — **High**
- **DM Mono:** "All fonts are licensed under the SIL Open Font License"; made by Colophon Foundry with creative direction from DeepMind; three weights with italics. — [googlefonts/dm-mono](https://github.com/googlefonts/dm-mono) — **High**
- *Inference:*
  - Both fonts can be self-hosted as woff2, which avoids third-party requests.
  - Before subsetting, check each OFL file for a Reserved Font Name; if one exists, a modified (subset) font must be renamed. See the open questions.
  - The site already self-hosts Source Sans 3 (OFL, 308 KB for two variable files). Switching to Outfit + DM Mono is a brand decision, not a licence one.
  - DM Mono's figures are monospaced by design, so stat chips stay stable.

### 3.6 Loading screens and performance budgets
- **Core Web Vitals** "good" thresholds at the 75th percentile of page loads: LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1. — [web.dev Web Vitals](https://web.dev/articles/vitals) — **High**
- **Alex Russell's 2024 budgets** for first load at 75th-percentile devices and networks:
  - JavaScript-heavy stacks: 365 KiB of JS (730 KiB total) for 3 s; 650 KiB of JS (1.3 MiB total) for 5 s.
  - Markup-centric stacks: 75–100 KiB of JS.

  — [The Performance Inequality Gap, 2024](https://infrequently.org/2024/01/performance-inequality-gap-2024/) — **High**
- *Inference:*
  - three core (133 KB gzip) plus scene code fits the 5 s JS-heavy budget.
  - The 3.7 MB ONNX Runtime wasm does not. Load it only on the lab pages, after first paint, behind the "door" loading screen, with a real byte-progress bar from `fetch` streaming.
  - The 3D canvas is unlikely to be the LCP element if the title and narrative text render first in HTML. Keep the door screen as an overlay that does not block text paint.
- **GPU memory** (*Inference*, arithmetic):
  - an RGBA8 texture with mipmaps costs w·h·4·1.33 bytes: 4096² ≈ 89 MB, 2048² ≈ 22 MB;
  - a 2048² 32-bit shadow map ≈ 17 MB per cascade;
  - iOS limits a canvas to 4096 × 4096 px. — [MDN canvas](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/canvas) — **High**
  - Keep the Tier 1 total under ~150 MB: one 2048² normal map, one 1024² shadow map, and no 4K render targets.

---

## Q4. Backend needs, sized for a one-person research project

### 4.1 What can stay static (most of it)
- **GitHub Pages limits:** published sites ≤ 1 GB; "soft bandwidth limit of 100 GB per month"; deployments time out after 10 minutes; HTTP 429 on rate limits; no e-commerce or SaaS as the main purpose. — [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits) — **High**
- **Measured on the live site, 2026-10-22:**
  - `Cache-Control: max-age=600` on HTML and on content-hashed assets alike;
  - `ETag` and `Last-Modified` present;
  - `Content-Encoding: gzip` even when `br` is offered;
  - `Accept-Ranges: bytes` with `206 Partial Content` for a Range request;
  - `Access-Control-Allow-Origin: *` and `Strict-Transport-Security: max-age=31556952`;
  - served through a Varnish cache (`Via: 1.1 varnish`).

  — curl — **High** (measured)
- Static data today: sample traces of 38 KB–810 KB as JSON (event-based jobs and segments, not per-frame); terrain hero pack 3.5 MB (PNG height and slope layers); lab policies and rover tables 16 MB. — local `site/public` — **High**
- *Inference:*
  - **Static:** all precomputed showcase runs, terrain packs, ONNX policies, vehicle generators, narrative content and pre-rendered KaTeX.
  - **Needs the API:** new user-defined runs, saved runs, replication badges.
  - The service in `service/` already does that.
  - Bandwidth check: at ~3.7 MB per cold lab visit, 100 GB/month is ~27,000 cold lab loads. 10-minute revalidation turns repeat visits into cheap 304 responses, not full downloads.

### 4.2 Deterministic replay and trace delivery
- Fixed-timestep simulation with render interpolation: the renderer "produces time", the simulation "consumes it" in fixed steps, and the renderer blends between the previous and current states with an alpha. — [Glenn Fiedler, Fix Your Timestep! (2004)](https://gafferongames.com/post/fix_your_timestep/) — **High**
- The service already records engine version, git sha, seeds and scenario sha, stores traces content-addressed by sha with `ETag` and immutable caching, and offers `POST /runs/{id}/replicate`, which compares output shas. — `service/README.md` — **High**
- *Inference:* replay is already a pure function of (trace, t). The 3D view only needs interpolation:
  - vehicles along leg segments by time;
  - lander states from the per-step descent log;
  - particles regenerated from (seed, landing id).

  No per-frame state needs storing. For per-step logs (lander at ~10 Hz × ~600 s × ~20 channels ≈ 120k floats ≈ 0.5 MB as Float32), use columnar typed-array binaries (`.f32` plus a JSON header) rather than JSON. They decode instantly and gzip well.
- *Inference — no chunked streaming needed.* Traces are under ~1 MB, so whole-file fetches are fine. If they grow (a 10-year horizon, many vehicles), split by time window into files named by content hash, or use one file read with Range requests, which GitHub Pages already serves.

### 4.3 Terrain tiles and LOD
- **Martini** (Mapbox, ISC licence) builds right-triangulated irregular network (RTIN) meshes from a (2^k+1)² heightmap at a requested error, e.g. 10 m, "in milliseconds". — [mapbox/martini](https://github.com/mapbox/martini) — **High**
- **PMTiles** is "a single-file archive format for pyramids of tiled data". Readers "use HTTP Range Requests to fetch only the relevant tile or metadata", and any server that supports range requests works. — [PMTiles docs](https://docs.protomaps.com/pmtiles/) — **High**
- The NASA-AMMOS 3DTilesRendererJS route and Cesium Moon were covered in `terrain_data_3d_assets.md` KQ5. — **High**
- *Inference:*
  - Keep the 400² overview mesh.
  - Add one high-resolution "site patch" per pad and base: a 257² or 513² Martini mesh from the 5 m DEM, at 1–2 m spacing.
  - Add procedural small craters and instanced boulders, flagged "representative detail below 5 m".
  - PMTiles only pays off if we ship many tiles or several sites.

### 4.4 Asset pipeline and caching: GitHub Pages vs a small VPS
- **Cloudflare Pages:**
  - a `_headers` file (up to 100 rules, 2,000 characters per line) can set `Cache-Control: public, max-age=31556952, immutable` on hashed assets;
  - free plan: 500 builds/month, 20,000 files, 25 MiB per file.

  — [Cloudflare Pages headers](https://developers.cloudflare.com/pages/configuration/headers/); [Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits/) — **High**
- Caddy's `file_server precompressed` serves `.br`, `.zst` or `.gz` sidecar files with the correct `Content-Encoding`. Default search order: br, zstd, gzip. — [Caddy file_server](https://caddyserver.com/docs/caddyfile/directives/file_server) — **High**
- *Inference:*
  - Keep GitHub Pages as the main host. Its 10-minute cache and gzip-only delivery cost little once the ONNX wasm is lazy-loaded.
  - If bandwidth or caching becomes a problem, move static hosting to Cloudflare Pages (immutable headers, brotli).
  - Or, since a Hetzner VPS is already planned for the API, serve the heavy immutable assets (wasm, policies, terrain) from Caddy with precompressed brotli and `immutable`.

  Do not split the site across hosts until a measurement says so.

### 4.5 An API to run a scenario and stream results into the 3D view
- **SSE:**
  - one-way, server to client;
  - auto-reconnects (`retry` sets the delay, `id` sets the last event id);
  - over HTTP/1.1 limited to 6 connections per browser per domain across all tabs, which Chrome and Firefox mark "Won't fix"; over HTTP/2 the limit is negotiated (default 100 streams).

  — [MDN, Using server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) — **High**
- *Inference:*
  - The existing flow fits a 3D view: `POST /v2/runs` → `GET /v2/runs/{id}/events` (SSE: queued, running, progress per seed, done) → `GET /v2/runs/{id}/trace?seed=N`, which is immutable by sha.
  - The 3D page can show a progress ring while waiting, then animate the finished trace.
  - WebSocket adds nothing here: there is no client-to-server streaming.
  - Serve the API over HTTP/2 (Caddy does by default) to avoid the 6-connection limit.

### 4.6 Saved scenarios and shared links
- `CompressionStream` (gzip, deflate) is Baseline "widely available" since May 2023 and works in workers. — [MDN CompressionStream](https://developer.mozilla.org/en-US/docs/Web/API/CompressionStream) — **High**
- *Inference:*
  - Small view state goes in the URL hash with no backend: run id or sample, time t, mode, focused vehicle, camera preset, e.g. `/world#run=01J…&t=812.5&focus=HAUL-2&view=pads`.
  - Custom scenarios that are too large for a URL go through `POST /v2/runs` and are shared by run id; the gallery and `publish` already exist.
  - A "copy link to this moment" button gives the shared-links feature at near-zero cost.

---

## Recommendations for LunarHaul

Rough effort is in focused developer-days, including tests, for one person. The order is my judgement of value per effort.

### P0. Foundations (≈ 8–10 days in total)

1. **Pin the renderer.** Keep `WebGLRenderer` and three 0.186.x for the redesign, and record the decision with the manual quotes from §1.1. Re-evaluate WebGPU when the manual drops "experimental" and our AO library supports it. *0 days.*
2. **Design tokens and glass panels with contrast fixes.**
   - Adopt the reference system: #030509 page, glass panels, 18 px radius, pills, monospace chips, cool #7fd8ff / warm #ffae4a accents.
   - Raise panel opacity to ≥ 0.85 wherever "muted" text sits on it, or lighten "muted" until it passes 4.5:1 over white-behind-glass. Using the §3.3 table, opacity is the easier lever.
   - Use "faint" only for ≥ 24 px text or decoration.
   - Use tabular numbers, 24 px targets, 3:1 focus rings, and no panel covering a focused control.
   - Font choice is an owner decision: Outfit + DM Mono (both OFL), or keep Source Sans 3.

   *1–1.5 days.*
3. **A shared stage module** (`site/src/stage/`) used by every 3D page:
   - renderer options (`stencil: true`; `reversedDepthBuffer` with a capability check; `powerPreference`);
   - the pixel budget plus an adaptive DPR monitor;
   - detect-gpu tiers (§1.13 table);
   - EffectComposer chain per tier (RenderPass/N8AO → bloom → OutputPass → SMAA);
   - two lighting presets: **Exhibit** (RoomEnvironment PMREM, AO, bloom on emissive parts) and **On site** (1.5° sun, black sky, custom dim lunar PMREM, Neutral tone mapping);
   - camera-controls with per-mode `setLookAt`; render-on-demand using camera-controls' sleep event;
   - one pause control and reduced-motion handling for all motion.

   *2–3 days.*
4. **Procedural vehicle kit.**
   - True-scale generators for Nova-C-like and Griffin-like CLPS landers, MK1-like, HLS-like, LTV (CLV-1/FLEX-like), MICRO (VIPER-scale) and HAUL (concept). Also pads, keep-out rings and base modules.
   - Use the dimensions in §2.1, cite them in code comments, and label models "representative".
   - Named part hierarchy with explode axes; closed meshes for stencil caps.
   - Materials from §2.2: gold and silver MLI with crinkle normal maps, white paint, aluminium, dark solar cells, dusted lower parts.
   - Three LODs, with today's constant-screen-size icons as the far level.

   *4–6 days.*

### P1. Signature scenes in the Raptor pattern (≈ 10–14 days)

5. **Vehicle exhibit page** (`/vehicles`, new).
   - One stage per vehicle with Exhibit lighting.
   - Modes: Whole / Cutaway (stencil caps; wedge option) / Exploded.
   - "Follow" chips: Propellant · Power · Cargo, using animated flow along feed lines.
   - Stat chips with our model's parameters and their sources, e.g. "Payload 1.5 t · 6 km/h · parks at night".
   - Left narrative card per mode; callout pills with leader lines; scene-switcher chips (Landers · Rovers · Base); door loading screen.

   *4–5 days.*
6. **3D descent lab** (upgrade of `/lab/lander`; keep the 2D side view as Tier 0 and as the accessible mirror).
   - Replay the ONNX policy at true scale over LOLA terrain.
   - Phase modes: Approach / Hover / Touchdown.
   - A plume per propellant class (faint near-nozzle glow), plus a deterministic ballistic ejecta sheet (1–3°, onset by altitude), a short obscuration layer and a scour decal (§1.4).
   - A SCORE counter driven by the real reward terms (red/green with sign and arrow).
   - Pre-rendered KaTeX for the thrust, gravity and reward equations, in a "whiteboard" card that echoes Hari's chalk explainer.

   *4–5 days.*
7. **On-site base world** (upgrade of `/world`).
   - A true-scale / icon toggle.
   - Shadows on the focused vehicle with the computed long-shadow geometry; terrain samples the vehicle shadow map (§1.7, option b).
   - Earth disc near the horizon from an ephemeris, hidden when below terrain, linked to a "comms: relay only" chip.
   - Keep-out rings and stand-down timing.
   - Rover legs as flow ribbons sized by tonnes per hour.
   - Modes: Overview / Pads & keep-out / Rover legs / Night.

   *3–4 days.*

### P2. Performance and accessibility pass (≈ 5 days)

8. **Measure the tier table on real hardware.** Use the RTX 3050 laptop, an Intel iGPU laptop and one phone, with `EXT_disjoint_timer_query_webgl2` where available or frame-time logs otherwise. Tune AO, bloom, shadow and particle settings until Tier 1 holds ≥ 30 fps and Tier 2 ≥ 60 fps at the default view. *2 days.*
9. **Accessibility.**
   - DOM mirror for every scene: telemetry table, part list for callouts, current mode text.
   - Keyboard camera presets plus on-screen orbit and zoom buttons (WCAG 2.5.7).
   - A live-region policy: polite, final values only.
   - Checks with NVDA and VoiceOver.

   *2 days.*
10. **Loading.**
    - Lazy-load ONNX Runtime only on lab pages, after first paint.
    - Door screen with a real byte-progress bar; preload hints for the terrain pack.
    - Check LCP ≤ 2.5 s on the landing page with Lighthouse mobile.

    *1 day.*

### P3. Static and backend glue (≈ 3–4 days)

11. **Deep links and run hand-off.**
    - URL-hash view state and "copy link to this moment".
    - An "Open in 3D" link from `/account` and the gallery to `/world?run=<id>`, which subscribes to SSE while the run is queued or running.

    *1–1.5 days.*
12. **Per-step binary logs.** Columnar Float32 files for lander and rover step logs, replacing JSON where logs exceed ~200 KB. *1 day.*
13. **Hosting.** Stay on GitHub Pages and log monthly bandwidth. If it passes ~50 GB/month, or immutable caching and brotli matter, move static hosting to Cloudflare Pages (`_headers`) or serve the heavy assets from the planned Caddy VPS with precompressed brotli. *0 days now; ~1 day if triggered.*
14. **Terrain site patches.** Martini meshes at 1–2 m around pads and base, with flagged procedural micro-detail. *1–1.5 days.*

**Total:** ≈ 26–33 developer-days for P0–P3. The visible "wow" comes mostly from items 3–7.

---

## Open questions

1. **Theme direction (owner).** PLAN §5.7 specifies a Distill-like light and dark design with Source Sans 3. The reference is dark glass with Outfit and DM Mono. Proposal: dark glass on the 3D pages (world, labs, vehicles), and keep Distill measures on text pages (method, paper) in both themes. Needs the owner's yes or no.
2. **True scale vs legibility (owner).** Should true scale be the default in `/world`? At true scale a 2.6 m rover is invisible from 5 km, so the default probably has to stay icons with a true-scale toggle.
3. **Blue Moon MK1 legs and outline.** No public drawing or text source for leg count, leg geometry or engine-bay layout was found; Blue Origin's page returned HTTP 429. Model a generic four-leg layout labelled representative, or wait for Pathfinder imagery (NET Q1 2027)?
4. **Starship HLS legs.** Leg count and geometry are not in any source read. Same question.
5. **Pegasus and CLV-1 detail.** No public dimensions for Pegasus; only stowed and deployed boxes for CLV-1. Is a CLV-1/FLEX-like look acceptable as "the LTV"?
6. **Methalox vacuum plume appearance.** No authoritative description found for Raptor, VR900 or GOX/GCH₄ thrusters in vacuum. Keep the generic "faint glow" for all classes until footage or a paper is found.
7. **Griffin details.** The engine count conflicts (7 on the current page vs 5 + 12 in the 2022 guide). Height is ~2 m by image label only.
8. **Reserved Font Names.** Does the Outfit or DM Mono OFL file declare one? If so, subset files must be renamed. Check the OFL.txt files.
9. **AO cost on our scenes.** No published millisecond comparison of GTAO, SAO and N8AO on integrated GPUs exists. Recommendation 8 must measure it before AO is turned on for Tier 1–2.
10. **Terrain shadows from vehicles.** Option (a), porting the terrain to `MeshStandardMaterial` with `onBeforeCompile`, unlocks SunLight cascades. Option (b), a manual shadow sample in the custom shader, is smaller. Decide during item 7, after a 1-hour spike.
11. **detect-gpu staleness.** Benchmarks stopped in Dec 2025. Keep self-hosted benchmarks plus the adaptive DPR monitor, or drop detect-gpu for a short runtime probe (render a test frame and time it)?
12. **Tone mapping.** Choose between ACES (the reference look) and Neutral (colour fidelity) after an A/B on real scenes. AgX is a third candidate.
13. **Hosting trigger.** Agree a bandwidth or caching threshold for moving static hosting off GitHub Pages, and whether the owner wants a custom domain, which a move to Cloudflare would make easy.
