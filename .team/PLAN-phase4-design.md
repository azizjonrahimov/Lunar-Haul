# Phase 4 plan: a professional, 3D interactive LunarHaul

Status: **APPROVED 22 October 2026.** The owner said: start with the foundations (M1) and continue step by
step; take LEAD's recommendation on every open decision; host the backend inside the GitHub repository
(section 4, B-37); and add research that can find something new (section 10). Written 22 October 2026 by LEAD.

Goal in one line: the simulation should look and feel like the reference reels (cinematic 3D you can take
apart, guided by a story, numbers live on screen) while every number stays sourced and reproducible.

---

## 1. What the four reels teach (only what helps our simulation)

| Reel | What it shows | What we take from it |
|---|---|---|
| **The AI Skool: "Inside the Raptor 3"** (live page: airsup.ai/rocket-engine, by Konstantin Saifoulline) | A real-time 3D Raptor 3 engine on a test stand in a dark hangar. Cutaway, exploded view, flow of oxygen/methane/fire, throttle and altitude change the plume, part callouts, a narrative card that rewrites itself per mode, stat chips (thrust, chamber pressure, mass flow), a second scene (turbopump) one click away. | **The interaction model**: one hero object per scene; a few segmented "mode" buttons (Whole / Cutaway / Exploded; Follow: All / Oxygen / Methane / Fire); every mode moves the camera, highlights parts and rewrites the text; numbers update live. **The craft**: procedural geometry (no downloaded models), clipping-plane cutaway with solid caps, a noise-based plume shader, ambient occlusion + bloom + filmic tone mapping, glass panels, two typefaces (geometric sans + mono), a loading "door". Plain three.js + Vite: **the same stack we already use.** |
| **Hari (@harixganesh): "Land a rocket with AI"** | A stylised 3D lander at golden hour, a big SCORE board counting from −71 to +40 as it learns, then a hand-drawn chalk "whiteboard" explaining gravity vs thrust, reward shaping (+ closer, + slowing down, +100 safe landing), a neural network, and a code card. | **The score counter** as the emotional centre of the lander lab (we already log the reward; make it big and animated). **The chalkboard explainer** style for the "why" sections (reward shaping, the hover hack), separate from the realistic 3D. |
| **FAANG Prep: "Can you solve this SpaceX interview question?"** | Falcon 9 lands at the pad on light missions, on a drone ship on heavy ones: why? Navy grid floor, white booster with grid fins, violet trajectory lines, boxed mono tags (LIGHT MISSION), equations, gauges, an altitude ruler, four colour-coded answer cards A–D, captions with highlighted keywords. | **Compare as a quiz**: our "compare rules" view can show the four job rules as four cards on the same simulated year, each with its own small 3D/plot tile and one highlighted number. **Diagrammatic 3D**: trajectories as glowing lines over a grid, tags and gauges anchored in the scene. |
| **Adam Yang (@adam.aero): free engineering tools** | SimScale CFD streamlines with a rainbow colour legend, XFLR5 polars, OpenRocket's 2D rocket with CG/CP markers and a component tree, Onshape CAD. | **Engineering-tool conventions** people trust: a component tree next to the 3D model, a colour legend on every field plot, CG/CP-style markers, a properties panel. Our model inspector should feel like that. |

What does **not** transfer: a sea-level plume with shock diamonds is wrong on the Moon. With no air to
recompress the jet there is no diamond train; a hydrogen flame (Blue Moon's BE-7) is nearly invisible; what
landing footage actually shows is **dust**: a sheet thrown out 1–3° above the ground (Apollo photogrammetry),
Apollo 12 "essentially blind" for the last ~40 ft, plume–surface interaction starting ~15 m up on Blue Ghost
(SCALPSS, March 2025). Black sky, one hard low sun (≤ 1.5° at the south pole) casting shadows ~38× an object's
height, Earth low on the horizon and hidden about half of each month: the realism we show must be lunar, not
Earth-test-stand. Sources and grades: `research_notes/LunarHaul 3D interactive design/design_research.md` §1.4, §2.2.

## 2. Where we are now (honest gap list)

- `/world/`: real LOLA terrain with baked sun shadows (good), but vehicles are boxes and cylinders, landers
  appear without a descent, rovers slide in straight lines between sites, no post-processing, no story.
- `/lab/lander/`: a 2D canvas side view; the score exists but is a small number; reward rules are a table.
- `/lab/rover/`: a 2D plan view on a hillshade; no 3D, no sense of the low sun or the delay.
- `/simulator/`: the v2 page (own styling, SVG charts); not on the site's design system; labels are now plain.
- Design system: light-first reading site (Source Sans 3, Tol colours). No dark "instrument" look for 3D pages.
- Backend: the Python engine, trace v2, driving tables, landing-outcome tables and a FastAPI service exist,
  but nothing exports what a 3D replay needs (real rover paths, descent trajectories, a compact streamable scene).

## 3. Design direction

1. **One hero per scene, modes not menus.** Each 3D page has one subject and 2–4 segmented controls; every
   mode change re-frames the camera, highlights parts and rewrites a short narrative card.
2. **Numbers on screen come from data files**, never typed into HTML: stat chips and story text read the
   results tables and the vehicle catalogue (build fails if a number has no source).
3. **Lunar realism for the world, chalkboard for the why.** Realistic lighting and plumes in 3D; hand-drawn
   style only in explainers.
4. **Our own identity, not a copy.** We reuse techniques (all standard three.js), not airsup's code, logo,
   colours or layout one-for-one.
5. **Every 3D view has a text twin** (tables we already keep), keyboard control and a reduced-motion mode.
6. **Performance tiers are a feature**: tier 0 → 2D fallback, tier 1 → no AO/bloom, tier 2–3 → full pipeline.
   Today the airsup page froze Chrome on this 8 GB laptop; ours must not.

Visual language (proposal, to be tuned in F-30): dark "instrument" theme for 3D pages (near-black blue
background, glass panels with blur and a 1 px light border, 16–18 px radius), cool cyan for data and
guidance, warm amber for thrust and heat, Tol bright for categories (owners, rules), a geometric display face
for headings and a monospace face for every number. Reading pages (paper, method) keep the light theme.
Contrast fix learnt from the reference: its translucent panels fail WCAG AA over a bright scene (muted text
3.1:1 over sunlit regolith), so our panels are at least 85 % opaque wherever small text sits on them.

Technical baseline (from the research): stay on three.js r186 `WebGLRenderer` (the manual still calls
WebGPURenderer experimental, and it has no `ShaderMaterial`/`EffectComposer`, which our terrain and effects
need). Everything the reference uses ships in r186: GTAO/SAO, UnrealBloom, OutputPass, SMAA, RoomEnvironment,
the stencil-cap clipping example. Models are **procedural at true scale**: no official or Creative Commons
models exist for Blue Moon, HLS, Nova-C, Griffin, the LTVs or VIPER (only paid or editorial-only ones).

---

## 4. BACKEND plan (Python engine, data files, service)

Each step: what, why, done when, effort (agent-days), depends on.

**B-30 Vehicle and site catalogue (single source of truth).**
`lunarsim/catalog-v1.json` (package data, the source of truth; DONE 22 Oct, 2b74fac) + `lunarsim/catalog.py` + JSON Schema: every lander and rover class and base
element with real dimensions (height, diameter, leg span, wheelbase, wheel size), masses, capacity, speeds,
paint/foil colours, each value flagged Spec / Assumed / Modelled with a URL. The engine reads capacities and
speeds from it (results must not change: baseline md5 identical); the site reads dimensions for the 3D models.
Starting values (research §2.1): CLPS class ≈ Nova-C (3.9 m tall, 1.6–2 m across, 6 legs, methalox) or
Griffin-like (4 legs, hypergolic); MK1 class 8.05 m tall × 3.08 m (hydrolox; legs unpublished → representative);
large cargo ≈ Starship HLS 52 m × 9 m (legs unpublished → representative); LTV ≈ Astrolab CLV-1/FLEX deployed
~4 × 2.3 × 2.6 m, 4 wheels; MICRO at VIPER scale 1.7 × 1.7 × 2.5 m, 0.5 m wheels; HAUL has no real counterpart
(ATHLETE-like concept, labelled "concept"); Apollo LRV as the scale reference. Each also gets its propellant
class (sets how visible its plume is). Done when: schema test, engine baseline unchanged, every value has a
flag and source. 1–1.5 d. Depends: research notes.

**B-31 Scene package format `lunarsim-scene v1` (what a 3D replay needs, nothing more).**
Writer `lunarsim/scene.py` turning a trace v2 into a compact, chunked package (30-day chunks): per-vehicle
keyframes on terrain (x, y, z, heading, load, state), landing events with a trajectory id, keep-out windows,
cargo counts per site per hour, night intervals, sun azimuth. Float32 arrays + a small JSON index.
Done when: JS reader round-trips it; replay metrics equal the trace's; a sample year is under 2 MB gzipped. 2–3 d. Depends: B-32, B-33.

**B-32 Real rover paths.** Export the driven polyline of every leg (expert, and learned for comparison),
decimated to ~5 m, with time stamps and intervention points, so 3D rovers follow the real route over the
terrain instead of straight lines. Heavy compute: foreground chunks only (memory rule). 1–2 d.

**B-33 Descent trajectories for 3D.** For each lander class × pilot (network, classical, PPO), export a few
representative episodes (median, p10/p90 miss, one failure) at 10 Hz: position, attitude, throttle,
propellant; plus the plume–surface numbers already in the keep-out model. Parity test against the JS env.
1 d.

**B-34 Terrain asset pipeline v2.** From the LOLA DEM: 2–3 levels of detail, a normal map, sun-visibility
for a set of sun azimuths (the sun circles the horizon once per lunar day) packed for the GPU, and a
procedural regolith detail texture; compressed (KTX2 where supported) with a manifest and sha256s.
Done when: the world page loads the base area at full detail in < 3 s on a mid laptop. 2–3 d.

**B-35 Story data and the number check.** `data/stories/*.json`: each story is a list of steps (title, text
with `{{r:key}}` placeholders, camera shot, highlighted objects, mode switches). A build-time validator
resolves every placeholder from `results/*.csv` or the catalogue and fails on any unsourced number.
Schema agreed with FRONTEND. 1–2 d.

**B-36 Static scenario gallery.** Precompute 12–20 curated scenarios (phase × job rule × pad distance ×
night) as scene packages + summary metrics, so the 3D site needs no server. Watch repository size. 1 d + compute.

**B-37 The backend inside the GitHub repository (owner decision, 22 Oct).** GitHub cannot run an always-on
server (Pages serves static files only: ≤ 1 GB site, soft 100 GB/month), but GitHub Actions can compute on
demand (jobs up to 6 h; free on standard runners for public repositories). So the hosted backend becomes:
(1) **static results** on Pages (B-36 gallery, scene packages, tables); (2) **a run queue on GitHub Actions**: a
visitor fills an issue form (scenario, job rule, seeds ≤ 30) → a workflow validates it, runs `lunarsim` with the
same provenance the service records, posts the summary as a comment, and publishes the scene package and
trace to the site's `runs/<id>/` (or as release assets when large) → the site opens `/world/?run=<id>`;
(3) the existing FastAPI `service/` stays in the repo, tested, for the day a VPS is wanted. Guard rails: issue
form only (no tokens in the browser), label-gated by LEAD for new submitters, seeds and scenario size capped,
one run at a time (concurrency group). Done when: an issue with a scenario produces a published run that the
world page replays, end to end, with provenance. 2–3 d.

**B-38 CI gates and delivery.** The pages workflow fails on: JS or data over the per-page budget, schema errors
in any data file, JS-vs-Python parity failures for the new formats, Lighthouse below target on three pages.
Large per-step logs (lander and rover) move from JSON to columnar Float32 files once over ~200 KB. Measured on
the live site today: GitHub Pages sends `max-age=600` even for hashed files and gzip only, so keep downloads
few and small; ONNX Runtime (3.7 MB) loads only on the lab pages. Agree a trigger (for example ~50 GB/month
or a need for immutable caching) for moving static hosting to Cloudflare Pages or the VPS. 1–2 d.

**B-39 Verification rows.** Add checks to the verification page: scene package reproduces trace metrics;
trajectory export matches the environment; catalogue numbers equal engine constants. 0.5 d.

Backend total: about 12–17 agent-days.

## 5. FRONTEND plan (site, 3D, UI/UX)

**F-30 Design system v2 ("instrument" theme).** Tokens (dark theme for 3D pages; light kept for reading),
type (display + mono), and components: segmented pill control, stat chip, narrative card, callout label
(dot + leader + pill), scene-switcher chips, timeline with event ticks, loading door with progress, big
animated counter, glass panel, tooltip. A dev-only gallery page `/design/`. WCAG AA contrast checked over
glass on the darkest and brightest scene backgrounds. 2–3 d.

**F-31 Shared 3D stage (`site/src/stage/`).** One module every 3D page uses: renderer setup (stencil on,
reversed depth buffer where supported so metre-scale close-ups and kilometre views coexist), two lighting
presets — **Exhibit** (studio environment, ambient occlusion, bloom on hot parts) and **On site** (1.5° sun,
black sky, dim lunar environment, neutral tone mapping); post-processing per GPU tier (AO → bloom → output →
SMAA), an adaptive-resolution monitor to hold frame rate, render-on-demand when nothing moves, a camera
director on camera-controls (MIT; named shots, smooth moves, orbit limits), the label system (callouts that
hide when occluded and avoid overlaps), hover/pick outlines, a cutaway helper (clipping planes with solid
caps, optional wedge), an exploded-view helper, one pause control, reduced motion (cuts instead of flights),
WebGL context-loss recovery. 2–4 d.

**F-32 Procedural vehicle kit + the vehicle exhibit page (the Raptor pattern for our fleet).** Built from the
B-30 catalogue at true scale, each with named parts, explode axes and closed meshes (for solid cut caps), and
three levels of detail (today's constant-size icons as the far level): CLPS-class lander, Blue Moon MK1-class
lander, a tall Starship-HLS-class cargo lander; LTV, HAUL (concept) and MICRO rovers; habitat module, landing
pad with berm, solar towers, comms mast, standard cargo pallets (instanced). Materials: gold and silver foil
with crinkle normals, white thermal paint, aluminium, dark solar cells, regolith dust on the lower parts;
models labelled "representative". New page `/vehicles/`: Whole / Cutaway / Exploded; Follow chips
Propellant · Power · Cargo with animated flow along feed lines; stat chips with our model's numbers and their
sources ("Carries 1.5 t · 6 km/h · parks at night"); narrative card per mode; callout pills; scene chips
Landers · Rovers · Base; a component tree and properties panel (OpenRocket style); loading door. 6–8 d.
Depends: F-31, B-30.

**F-33 Lunar effects.** (1) A faint near-nozzle glow set by propellant class (almost none for hydrolox), no
shock diamonds; (2) a deterministic dust sheet: seeded particles on ballistic paths (g = 1.62 m/s², no drag)
launched at 1–3°, starting below an onset height that scales with thrust (~15 m for Blue Ghost-class
thrusters), its reach tied to the keep-out data; (3) a ground-hugging obscuration layer that peaks in the last
seconds and vanishes at engine cut-off (no air holds dust up); (4) a scour mark left on the terrain. Plus wheel
dust, headlight cones at night, long shadows (a tight shadow camera on the focused vehicle; the custom terrain
shader samples that shadow map), Earth as a 1.9° disc near the horizon from an ephemeris (hidden when below
the terrain), stars off at sunlit exposure. Under a 1.5° sun the dust sheet is almost parallel to the light and
glows when the camera faces the sun: our honest "hero" effect. 2–3 d. Depends: F-31.

**F-34 Lander lab in 3D ("The last 500 metres").** 3D replay of the real episode at true scale over LOLA
terrain; phase modes Approach / Hover / Touchdown; a big SCORE counter driven by the real reward terms (red
and green, with sign; Hari reel); controls: Pilot [Network | Classical], Lander [Small | Medium | Large],
View [Chase | Side | Pad camera], Show [Guidance | Thrust | Sensors] (velocity-field arrows, thrust vector,
altimeter beam); the touchdown box in 3D; the 500-landing scatter drawn on the pad; a chalkboard card with
the thrust, gravity and reward equations (KaTeX, rendered at build time) for reward shaping and the hover
hack. The 2D canvas stays as the tier-0 fallback and the accessible mirror. 4–5 d. Depends: F-32, F-33, B-33.

**F-35 Rover lab in 3D.** Drive on terrain with chase and cockpit cameras; a "ghost" rover showing where
your delayed command will take effect; the low-sun glare cone and long shadows; slip indicator;
interventions as 3D markers with callouts; expert vs network race on the same leg. 3–4 d. Depends: F-32, B-32.

**F-36 World v2 (the flagship).** Loading door then a fly-in; scene chips (Overview, Pads & keep-out, Rover
legs, Base, Night); a true-scale / icon toggle (at true scale a 2.6 m rover is invisible from 5 km, so icons
stay the default far view); Earth near the horizon tied to a "comms: relay only" chip when it sets; rover legs
as flow ribbons sized by tonnes per hour; rovers on real paths; landers descending with plume, dust sheet and keep-out rings; cargo
pallets stacking at sites; a timeline with event ticks (landings, nightfall, strandings); live stat chips
(delivered, waiting, trips, urgent 90 % wait so far); a narrative card for the current event; Follow
[Cargo | Rovers | Landers | Night]; split screen to compare two job rules on the same year. 5–6 d.
Depends: F-31…F-33, B-31, B-36.

**F-37 Simulator v3 on the design system.** Same engine files (`sim.js`, `worker.js` untouched); glass
panels, segmented controls, the plain labels; results as stat chips and Observable Plot charts like the rest
of the site; Compare as four answer-style cards (SpaceX reel); a "Watch this year in 3D" button. The v2 page
stays at `/simulator/v2/` for one release. 3–4 d. Depends: F-30.

**F-38 Guided stories (explorable explanations).** Three stories driven by B-35 data, each a sequence of
steps that move the 3D camera, switch modes and show sourced numbers: "How far should the pads be?"
(standoff cost per km), "Why sharing rovers cuts the wait" (job rules), "Learned vs classical landing"
(landing success by pilot). Scroll or Next/Back; every step has a text-only twin. 3–4 d. Depends: F-36, B-35.

**F-39 Landing page hero.** Loading door, a slow cinematic orbit of the base under the low sun, three big
counters from the results, entry chips to World, Labs, Simulator and Stories. 1–2 d. Depends: F-36.

**F-40 Quality pass.** Measure the GPU tiers on real hardware (this RTX 3050 laptop, an Intel integrated-GPU
laptop, one phone) and tune AO, bloom, shadows and particles until tier 1 holds ≥ 30 fps and tier 2 ≥ 60 fps
at the default view (no published AO timings exist for integrated GPUs, so this must be measured before AO is
on for tiers 1–2). A DOM mirror for every scene (telemetry table, part list, current mode text), keyboard
camera presets and on-screen orbit/zoom buttons (WCAG 2.5.7), polite live regions with final values only,
NVDA/VoiceOver checks, contrast, Lighthouse targets (≥ 85 performance on 3D pages on desktop, ≥ 95 on reading
pages, LCP ≤ 2.5 s on the landing page on mobile), GPU memory budget per tier, a screenshot set for visual
regression, zero console errors, URL-hash deep links ("copy link to this moment"). Continuous, plus 3–4 d.

Frontend total: about 33–43 agent-days. A shorter core path (F-30…F-34 + F-36 + F-40 with B-30, B-32, B-33,
B-34, B-38) is about 26–33 days and already delivers the "wow": the vehicle exhibit, the 3D landing lab and
the upgraded world.

## 6. Order, milestones and review gates

| Milestone | Steps | Owner reviews |
|---|---|---|
| M1 Foundations | B-30, B-34 (start), F-30, F-31 | design-system page + one demo scene with the full pipeline |
| M2 Vehicles and effects | F-32, F-33, B-33 | `/vehicles/`: every vehicle, whole / cutaway / exploded, follow the flow |
| M3 Labs in 3D | F-34, F-35, B-32 | lander and rover labs |
| M4 World and simulator | F-36, F-37, B-31, B-36, B-37 if hosted | the flagship world and simulator v3 |
| M5 Stories and release | F-38, F-39, F-40, B-35, B-38, B-39 | release 3.1: site, changelog, paper note |

BACKEND and FRONTEND run in parallel; each milestone ends with LEAD review (diff, tests, baseline identity,
pages in a browser) and a push. Calendar estimate with the three sessions: 4–6 weeks.

## 7. Risks and constraints

- **Memory and GPU.** 8 GB RAM shared by three sessions; heavy exports run in foreground chunks; 3D pages
  must stay within tier budgets (the airsup page froze Chrome here today).
- **Repository and Pages size.** Terrain, scene packages and trajectories must fit the size budget; large
  files may need GitHub Releases or a CDN.
- **Accuracy of depictions.** No public CAD exists for most of these vehicles; models are "representative,
  real dimensions where published", and say so on screen.
- **Not a clone.** Techniques yes; airsup's code, branding and exact look no.

## 8. Decisions for the owner

1. Go-ahead, and which milestone first (recommended: M1 then M2; the vehicle exhibit page is the fastest visible win).
2. Dark "instrument" theme for 3D pages, light for reading pages: OK?
3. Realistic lunar look for 3D and chalkboard style for explainers (recommended), or a stylised toy look like Hari's?
4. Typefaces: keep Source Sans 3 and add a display + mono pair (recommended), or switch fully (Outfit and DM Mono are OFL-licensed and allowed).
5. Where the published shape is unknown (MK1 and HLS landing legs, the LTV's final look): model a labelled
   "representative" shape now (recommended), or wait for flight imagery (MK1 Pathfinder no earlier than Q1 2027)?
6. Hosting for the service (only B-37 depends on it) and a trigger for moving static files off GitHub Pages.

Decided by LEAD unless the owner objects: stay on WebGL (not WebGPU) for this phase; tone mapping chosen by an
A/B on real scenes (Neutral vs ACES vs AgX); terrain shadows from vehicles by sampling the shadow map in the
existing terrain shader after a one-hour spike.

**Owner's answers (22 Oct):** 1 start with M1, then step by step · 2 dark "instrument" theme on the 3D pages,
light (with the existing dark toggle) on reading pages · 3 realistic lunar 3D + chalkboard explainers ·
4 keep Source Sans 3 for reading text; add **Sora** (display) and **JetBrains Mono** (numbers), both OFL, served
unmodified from npm packages (FRONTEND may A/B Sora against Space Grotesk in F-30 and report) · 5 build
labelled "representative" shapes where the real one is unpublished · 6 backend hosted through the GitHub
repository (B-37).

## 9. File ownership (Phase 4)

| Owner | May edit |
|---|---|
| **BACKEND** | `lunarsim/**` (new: `catalog.py`, `scene.py`, `comms.py`, exporters; engine changes only behind opt-in Scenario fields, results byte-identical with them off), `service/**`, `experiments/phase4/**` (new), `tests/**`, `tools/**` (new: asset and data pipelines), `.github/ISSUE_TEMPLATE/**` and `.github/workflows/run-*.yml` (B-37 only; report, LEAD reviews before merge) |
| **FRONTEND** | `site/**` (new: `site/src/stage/`, `site/src/ui/`, `site/vehicles/`, `site/design/`), `web/**` (`web/sim.js` engine frozen) |
| **LEAD** | `data/**` (generated with BACKEND tools, committed by LEAD), `results/**`, `figures/**`, `paper/**`, `research_notes/**`, `reports/**`, `README.md`, `.github/workflows/pages.yml` and `ci.yml`, `CITATION.cff`, `.team/PLAN*.md`, `.team/inbox-*.md`, `.team/prompts/**` |
| Shared, append-only | `.team/reports.md` |

Workers never run git add/commit/push. LEAD commits per task after review.

## 10. Research that can find something new (owner request, 22 Oct)

Honest assessment: the redesign alone makes the results clearer and more convincing, but it does not discover
anything. What can: the geometry the 3D world needs (horizons, Earth's position, long shadows) opens questions our
engine has never asked.

**R-1 "Earth in sight" (main thread).** At the south pole Earth stays within about ±7° of the horizon and is below
it roughly half of each month; local terrain hides it more. A rover driven from Earth cannot be driven without a
link; supervised autonomy needs some contact. Question: *how much hauling capacity and delivery time does a
south-pole base lose to direct-to-Earth blackout windows at its real (terrain-masked) sites, and when is a lunar
relay, more autonomy, or more rovers the cheapest fix?* Method: Earth's elevation at each site over a year from an
ephemeris, terrain horizon masks (B-34, extended beyond the 16 km tile), comms windows as an opt-in engine feature
(like the night stand-down), then a suite across autonomy mixes, relay availability and phases, read as a law with
confidence intervals like E20. Prior-art check: running (`research_notes/Lunar communications and visibility/`);
the claim of novelty waits for it.

**R-2 "Long shadows" (secondary).** At a 1.5° sun a 52 m lander casts a ~2 km shadow that sweeps around once per
lunar day; tall solar towers shade each other. Does pad placement relative to arrays and routes cost power or
driving time? Same ray-casting tools; a small study, kept only if the numbers are not negligible.

BACKEND and LEAD tasks for R-1 (ephemeris and horizon pipeline, the engine's comms windows, the suite) are written
after the prior-art check; the 3D world shows the result (Earth disc, "comms: relay only" chip, F-36).
