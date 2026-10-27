// Drawing data for /vehicles/ (F-51): what each part is, its published size, source and confidence, the key dimensions
// drawn as measured lines, the preset cut and which parts form the shell (X-ray). From research_notes/Lunar ATC/
// vehicles_comms_internals.md, Table B and sections 1 and 3. The simulation's numbers stay in the catalogue
// (lunarsim/catalog-v1.json); this file only says how to draw and label the models. Confidence as in the notes:
// High is shown as "published"; anything else (Medium, Low, Computed) is drawn but labelled "schematic".

export const SOURCES = {
  gunter: { label: "Gunter's Space Page: Blue Moon (15 Apr 2026)", url: 'https://space.skyrocket.de/doc_sdat/blue-moon.htm' },
  spacecom: { label: 'Space.com: Blue Moon explained (2019)', url: 'https://www.space.com/blue-origin-blue-moon-lander-explained.html' },
  pug: { label: 'Astrobotic payload user’s guide (2021)', url: 'https://science.nasa.gov/wp-content/uploads/2023/11/astrobotic-lunar-landers-pug.pdf' },
  griffin: { label: 'Astrobotic: Griffin lander', url: 'https://www.astrobotic.com/lunar-delivery/landers/griffin-lander/' },
  gm1: { label: 'Astrobotic: Griffin Mission One update', url: 'https://www.astrobotic.com/griffin-1-mission-update/' },
  novac: { label: 'Wikipedia: Intuitive Machines Nova-C', url: 'https://en.wikipedia.org/wiki/Intuitive_Machines_Nova-C' },
  bgFirefly: { label: 'Firefly: Blue Ghost', url: 'https://fireflyspace.com/blue-ghost' },
  bgNsf: { label: 'NASASpaceflight: Blue Ghost launch (Jan 2025)', url: 'https://www.nasaspaceflight.com/2025/01/blue-ghost-hakuto-r-launch/' },
  bgWiki: { label: 'Wikipedia: Firefly Blue Ghost', url: 'https://en.wikipedia.org/wiki/Firefly_Aerospace_Blue_Ghost' },
  hls: { label: 'Wikipedia: Starship HLS', url: 'https://en.wikipedia.org/wiki/Starship_HLS' },
  nasaMay26: { label: 'NASA: Moon Base rovers and landers (26 May 2026)', url: 'https://www.nasa.gov/news-release/nasa-provides-update-on-moon-base-rovers-landers-missions/' },
  nasaOct26: { label: 'NASA: Moon Base rovers progress (Oct 2026)', url: 'https://www.nasa.gov/missions/moon-base/nasa-provides-progress-update-on-moon-base-rovers/' },
  viper: { label: 'NASA, Bluethmann: VIPER mobility hardware (Nov 2024)', url: 'https://ntrs.nasa.gov/api/citations/20240013903/downloads/LSIC_2024-Tech%20Infusion_Panel-VIPER_Mob-HW.pdf' },
  lrv: { label: 'NSSDC: Apollo Lunar Roving Vehicle', url: 'https://nssdc.gsfc.nasa.gov/planetary/lunar/apollo_lrv.html' },
  astrolab: { label: 'Astrolab: FLEX', url: 'https://www.astrolab.space' },
  eagle: { label: 'Lunar Outpost: Eagle (2025)', url: 'https://www.lunaroutpost.com/post/lunar-outpost-to-unveil-latest-lunar-terrain-vehicle-at-space-symposium-2025' },
  pegasus: { label: 'Payload Space: Lunar Outpost Pegasus (May 2026)', url: 'https://payloadspace.com/lunar-outpost-closes-30m-series-b-unveils-new-rover/' },
  loRovers: { label: 'Lunar Outpost: rovers', url: 'https://lunaroutpost.com/rovers' },
  moonfall: { label: 'Satnews: Firefly MoonFall subcontract (May 2026)', url: 'https://satnews.com/2026/05/27/firefly-aerospace-wins-75-million-nasa-jpl-moonfall-subcontract-to-deliver-drones-to-the-moons-south-pole/' },
  microNova: { label: 'LPSC 2024 abstract 1931: Micro-Nova', url: 'https://www.hou.usra.edu/meetings/lpsc2024/pdf/1931.pdf' },
  microNovaIm: { label: 'Intuitive Machines: Micro-Nova', url: 'https://www.intuitivemachines.com/micro-nova' },
  centaur: { label: 'Wikipedia: Centaur (rocket stage)', url: 'https://en.wikipedia.org/wiki/Centaur_(rocket_stage)' },
  // computed or assumed here, no outside page: the part list says so instead of linking
  computed: { label: 'Computed from published propellant masses (project research notes, §3)', url: null },
  assumed: { label: 'Assumed for the drawing: no published layout', url: null },
  design: { label: 'Lunar ATC: our design, not the maker’s (sizes until B-81 measures them)', url: null },
};

// confidence -> what the part list shows: High "published", Design (Lunar ATC) "our design", the rest "schematic"
export const published = conf => conf === 'High';
export const tagOf = conf => conf === 'High' ? 'published' : conf === 'Design' ? 'our design' : 'schematic';

// the "Lunar ATC inside" layer every rover and lander can show: what our design adds, placed on the KIT entry's atc part
export const ATC_LAYER = {
  atc_computer: { label: 'Lunar ATC computer (our design)', what: 'Runs the safety program (the rules of the road) and the planner on two boards, so either can take over.', size: '0.30 × 0.12 × 0.22 m (drawing)', src: ['design'], conf: 'Design' },
  atc_radio: { label: 'Lunar ATC radio unit (our design)', what: 'Links the vehicle to the other robots and the base on its own antenna, with or without Earth in view.', size: '0.18 × 0.06 × 0.12 m, 0.3 m antenna (drawing)', src: ['design'], conf: 'Design' },
};

/* KIT[id]: {
     title, short, load (models of their own: a lazy chunk exporting build(mats) and, from part 3, kit with the rest),
     cut: {dir: 'side' | 'down', at: 0..1 of the height (down cuts)}, shell: [part names drawn see-through in X-ray],
     atc: the part the Lunar ATC layer sits on (default: the top of the vehicle),
     dims: [{label, text, part?: part name to measure (default: the whole vehicle), axis: 'x' | 'y' | 'z', src, conf}],
     parts: {partName | groupName: {what, size, src: [source keys], conf}}, story: {whole, cutaway, exploded} } */
const own = (title, short, load) => ({ title, short, load });
export const KIT = {
  // ---- part 3: models whose texts travel in their own chunk (the module's kit) ----
  clv1: own('Astrolab CLV-1 (Phase 1 LTV)', 'CLV-1', () => import('../models/kit/kit-clv1.js')),
  pegasus: own('Lunar Outpost Pegasus (Phase 1 LTV)', 'Pegasus', () => import('../models/kit/kit-pegasus.js')),
  flex: own('Astrolab FLEX cargo rover', 'FLEX', () => import('../models/kit/kit-flex.js')),
  eagle: own('Lunar Outpost Eagle', 'Eagle', () => import('../models/kit/kit-eagle.js')),
  viper: own('NASA VIPER', 'VIPER', () => import('../models/kit/kit-viper.js')),
  lrv: own('Apollo Lunar Roving Vehicle (1971)', 'Apollo LRV', () => import('../models/kit/kit-lrv.js')),
  mapp: own('Lunar Outpost MAPP', 'MAPP', () => import('../models/kit/kit-mapp.js')),
  moonfall: own('NASA/JPL MoonFall hopper', 'MoonFall', () => import('../models/kit/kit-moonfall.js')),
  micro_nova: own('Intuitive Machines Micro-Nova', 'Micro-Nova', () => import('../models/kit/kit-micro-nova.js')),
  atc_computer: own('Lunar ATC base computer (our design)', 'Base computer', () => import('../models/kit/kit-atc-computer.js')),
  atc_radio: own('Lunar ATC radio unit (our design)', 'Radio unit', () => import('../models/kit/kit-atc-radio.js')),
  CLPS: {
    title: 'Nova-C class lander',
    cut: { dir: 'side' }, shell: ['body'], atc: 'solar',
    dims: [
      { label: 'Height', text: '3.94 m (4.3 m by IM)', axis: 'y', src: ['novac'], conf: 'Medium' },
      { label: 'Body width', text: '1.57-2 m', part: 'body', axis: 'x', src: ['novac'], conf: 'Medium' },
    ],
    parts: {
      body: { what: 'Six spines from the top deck to the engine deck carry the loads; every face opens for plumbing access.', size: '3.94-4.3 m tall, 1.57-2 m wide', src: ['novac'], conf: 'Medium' },
      tanks: { what: 'Liquid oxygen (845 kg) and methane (422 kg) for the one engine; drawn side by side above the engine deck.', size: 'LOX 0.74 m³, CH4 1.0 m³', src: ['computed', 'novac'], conf: 'Computed' },
      solar: { what: 'One panel on the top deck (plus two body panels, not drawn) gives about 200 W on the surface.', size: '200 W', src: ['novac'], conf: 'Medium' },
      engine: { what: 'One gimballed VR900 methane-oxygen engine at the bottom centre does the whole descent.', size: '3.1 kN', src: ['novac'], conf: 'Medium' },
      legs: { what: 'Six legs spread the landing load and keep the engine bell clear of the ground.', size: '6 legs', src: ['novac'], conf: 'High' },
    },
  },
  MK1: {
    title: 'Blue Moon MK1',
    cut: { dir: 'side' }, shell: ['hull'], atc: 'deck',
    dims: [
      { label: 'Height', text: '8.05 m', axis: 'y', src: ['gunter'], conf: 'High' },
      { label: 'Diameter', text: '3.08 m', part: 'hull', axis: 'x', src: ['gunter'], conf: 'High' },
    ],
    parts: {
      hull: { what: 'A vertical cylinder that holds the tanks; only this outer envelope is published.', size: '8.05 m × 3.08 m', src: ['gunter'], conf: 'High' },
      lh2: { what: 'Liquid hydrogen is light, so its tank fills most of the cylinder.', size: '~29 m³ (≈4.4 m of length)', src: ['computed'], conf: 'Low' },
      lox: { what: 'Liquid oxygen, about five times the hydrogen’s mass in a third of its volume, sits below.', size: '~9.9 m³ (≈1.5 m)', src: ['computed'], conf: 'Low' },
      engine: { what: 'One BE-7 burns hydrogen and oxygen with a nearly invisible flame.', size: '~40-44.5 kN', src: ['gunter'], conf: 'High' },
      solar: { what: 'Solar cells, with batteries and fuel cells, power the lander.', size: 'not published', src: ['gunter'], conf: 'High' },
      legs: { what: 'Four legs; their real shape is unpublished, so these are drawn at the Apollo LM footprint ratio.', size: 'not published', src: ['assumed'], conf: 'Low' },
      deck: { what: 'An open deck on top carries up to 3 t of cargo, unpressurised.', size: '3 t', src: ['gunter'], conf: 'High' },
    },
  },
  LARGE: {
    title: 'Starship HLS (cargo)',
    cut: { dir: 'side' }, shell: ['hull'], atc: 'airlock',
    dims: [
      { label: 'Height', text: '52 m', axis: 'y', src: ['hls'], conf: 'Medium' },
      { label: 'Diameter', text: '9 m', part: 'hull', axis: 'x', src: ['hls'], conf: 'Medium' },
    ],
    parts: {
      hull: { what: 'A stainless-steel hull, 9 m across, that is also the tank wall.', size: '52 m × 9 m', src: ['hls'], conf: 'Medium' },
      lox: { what: 'The oxygen tank in the aft hull, below a common dome.', size: '1,170 t, ~1,025 m³, ~16 m of barrel', src: ['hls', 'computed'], conf: 'Medium' },
      ch4: { what: 'The methane tank forward of the oxygen, sharing the common dome.', size: '330 t, ~780 m³, ~12 m', src: ['hls', 'computed'], conf: 'Medium' },
      solar: { what: 'A band of solar panels round the hull powers the ship on the surface.', size: 'not published', src: ['hls'], conf: 'Medium' },
      airlock: { what: 'The crew cabin and airlock near the top; an elevator runs down the outside of the hull to the ground.', size: 'not published', src: ['hls', 'nasaOct26'], conf: 'High' },
      thrusters: { what: 'Landing thrusters high on the body fire near the ground, keeping the main engines’ blast off the surface.', size: 'not published', src: ['hls'], conf: 'Medium' },
      engines: { what: 'Three sea-level and three vacuum Raptors in a shielded aft bay.', size: '6 engines', src: ['hls'], conf: 'Medium' },
      legs: { what: 'Six legs; their real shape is unpublished, so these are drawn at the catalogue’s leg span.', size: 'not published', src: ['assumed'], conf: 'Low' },
    },
  },
  LTV: {
    title: 'Phase 1 LTV (CLV-1 / FLEX class)',
    cut: { dir: 'down', at: 0.48 }, shell: ['chassis'], atc: 'battery',
    dims: [
      { label: 'Length', text: '4.0 m (catalogue)', axis: 'z', src: ['assumed'], conf: 'Low' },
      { label: 'Wheel', text: '0.93 m', part: 'wheels', axis: 'y', src: ['assumed'], conf: 'Low' },
    ],
    parts: {
      chassis: { what: 'The deck that carries crew, tools and cargo; FLEX has two top-deck payload interfaces.', size: '2,000 kg payload (FLEX)', src: ['astrolab'], conf: 'High' },
      battery: { what: 'Battery and avionics in an insulated warm box low in the centre, for a low centre of mass and warmth at night.', size: 'kWh unpublished; 10 km a charge', src: ['nasaOct26', 'viper'], conf: 'Low' },
      wheels: { what: 'Four wheels with in-hub motors; Astrolab uses flexible airless tyres, Pegasus spring-mesh ones.', size: '4 wheels', src: ['nasaOct26'], conf: 'High' },
      solar: { what: 'Solar panels; at the pole the sun is low, so real LTVs carry them on their sides.', size: 'not published', src: ['nasaOct26'], conf: 'High' },
      arm: { what: 'A six-axis robotic arm on a deck corner loads and unloads cargo (FLEX; Pegasus has none).', size: '6 axes', src: ['astrolab'], conf: 'High' },
      cargo: { what: 'A cargo box on the deck; FLEX can also carry 3 m³ in an underslung bay between the wheels.', size: 'up to 3 m³ underslung', src: ['astrolab'], conf: 'High' },
    },
  },
  HAUL: {
    title: 'Heavy hauler (concept)',
    cut: { dir: 'down', at: 0.5 }, shell: ['bed'], atc: 'battery',
    dims: [{ label: 'Length', text: '7 m (concept)', axis: 'z', src: ['assumed'], conf: 'Low' }],
    parts: {
      bed: { what: 'A low flat bed for 10 t of cargo; no such vehicle is flown or contracted, so the whole shape is a concept.', size: '7 × 4 m', src: ['assumed'], conf: 'Low' },
      rails: { what: 'Rails that lock standard pallets to the bed.', size: 'concept', src: ['assumed'], conf: 'Low' },
      battery: { what: 'A battery and night-power pack sized to keep working through the lunar night.', size: 'concept', src: ['assumed'], conf: 'Low' },
      radiators: { what: 'Radiators shed the heat of the night-power pack.', size: 'concept', src: ['assumed'], conf: 'Low' },
      lights: { what: 'Headlights for driving in the dark.', size: 'concept', src: ['assumed'], conf: 'Low' },
      wheels: { what: 'Six 1.5 m wheels spread the load on soft regolith.', size: '1.5 m', src: ['assumed'], conf: 'Low' },
      cargo: { what: 'A standard cargo pallet.', size: 'catalogue pallet', src: ['assumed'], conf: 'Low' },
    },
  },
  MICRO: {
    title: 'Small rover (VIPER class)',
    cut: { dir: 'down', at: 0.3 }, shell: ['body'], atc: 'battery',
    dims: [
      { label: 'Height', text: '2.5 m', axis: 'y', src: ['viper'], conf: 'High' },
      { label: 'Width', text: '1.7 m', axis: 'x', src: ['viper'], conf: 'High' },
    ],
    parts: {
      body: { what: 'The chassis; its warm box holds the flight avionics, IMU and motor controllers.', size: '1.7 × 1.7 × 2.5 m', src: ['viper'], conf: 'High' },
      battery: { what: 'Two internal batteries store the energy for driving through shadow.', size: '5.42 kWh total', src: ['viper'], conf: 'High' },
      solar: { what: 'Solar arrays on the sides catch the low polar sun.', size: '320-450 W', src: ['viper'], conf: 'High' },
      mast: { what: 'A mast with the navigation cameras and lights at 2.0 m and the high-gain antenna at 2.3 m.', size: '2.0-2.3 m', src: ['viper'], conf: 'High' },
      wheels: { what: 'Four wheel modules with steering and active suspension.', size: '50 cm, 7-43 cm clearance', src: ['viper'], conf: 'High' },
    },
  },
  // ---- part 2: models of their own (site/src/models/kit/, one lazy chunk each); story: the text per view ----
  griffin: {
    title: 'Astrobotic Griffin', short: 'Griffin', load: () => import('../models/kit/kit-griffin.js'),
    story: {
      whole: 'Astrobotic’s Griffin, now built by Voyager: a square bus that carries more than 455 kg of cargo, first to Nobile Crater. Its outer size is unpublished, so the envelope here is schematic.',
      cutaway: 'The cut shows the launch-vehicle adapter cone with the main engines inside it, and the fuel and oxidiser tanks spaced round it.',
      exploded: 'Tanks out and up, engines down out of the cone, legs out: the 2021 payload user’s guide layout.',
    },
    cut: { dir: 'side' }, shell: ['bus', 'cone', 'solar'], atc: 'avionics',
    dims: [
      { label: 'Bus', text: 'about 3 m as drawn', part: 'bus', axis: 'x', src: ['assumed'], conf: 'Low' },
      { label: 'Deck height', text: 'about 2 m as drawn', part: 'bus', axis: 'y', src: ['assumed'], conf: 'Low' },
    ],
    parts: {
      bus: { what: 'Deck panels and four radiator panels; the lander’s avionics mount on their undersides.', size: 'not published', src: ['pug'], conf: 'Low' },
      cone: { what: 'The launch-vehicle adapter at the bottom centre; the main engines sit inside it.', size: 'not published', src: ['pug'], conf: 'High' },
      engines: { what: 'Pulsed main engines inside the cone: five 3.1 kN engines in 2021, seven in the Mission One design.', size: '5 × 3.1 kN (2021)', src: ['pug', 'griffin'], conf: 'High' },
      fuel: { what: 'Two fuel tanks (an MMH-type fuel), spaced evenly round the cone.', size: '2 tanks (4 COPV tanks in GM1)', src: ['pug', 'gm1'], conf: 'High' },
      oxidiser: { what: 'Two oxidiser tanks (MON-3) between the fuel tanks.', size: '2 tanks', src: ['pug'], conf: 'High' },
      avionics: { what: 'Flight computers and radios on the undersides of the radiator panels that form the decks.', size: 'not published', src: ['pug'], conf: 'High' },
      payload: { what: 'Payloads bolt on above the deck (sky view) or below it (near the surface), on M5 inserts every 75 mm.', size: '~0.5 m² per side', src: ['pug'], conf: 'High' },
      solar: { what: 'Side-mounted solar panels, the polar configuration for a sun that stays low.', size: 'not published', src: ['pug'], conf: 'High' },
      antennas: { what: 'Low-gain antennas plus an actuated medium/high-gain dish; a 2.4 GHz WLAN links the payloads.', size: 'not published', src: ['pug'], conf: 'High' },
      acs: { what: 'Twelve 111 N attitude thrusters in four clusters of three turn and steady the lander.', size: '12 × 111 N', src: ['pug'], conf: 'High' },
      legs: { what: 'Four landing legs.', size: '4 legs', src: ['griffin'], conf: 'High' },
    },
  },
  blue_ghost: {
    title: 'Firefly Blue Ghost', short: 'Blue Ghost', load: () => import('../models/kit/kit-blue-ghost.js'),
    story: {
      whole: 'Firefly’s Blue Ghost: 2 m tall and 3.5 m across, 150 kg of cargo. Mission 1 landed in Mare Crisium on 2 March 2025 and worked about 14 days, into the night.',
      cutaway: 'A box frame of 49 composite struts with three decks: the top one looks at the sky, the middle one carries rovers, the bottom one reaches the surface. The tank layout is unpublished, so the tanks are schematic.',
      exploded: 'Decks up, engine down, legs and solar panels out.',
    },
    cut: { dir: 'side' }, shell: ['body', 'solar'], atc: 'decks',
    dims: [
      { label: 'Height', text: '2 m', axis: 'y', src: ['bgFirefly', 'bgNsf'], conf: 'High' },
      { label: 'Width', text: '3.5 m', axis: 'x', src: ['bgFirefly', 'bgNsf'], conf: 'High' },
    ],
    parts: {
      body: { what: 'A box-shaped body of 49 composite struts.', size: '2 m tall × 3.5 m wide (with legs)', src: ['bgNsf', 'bgFirefly'], conf: 'High' },
      decks: { what: 'Three decks: the top one with a view of the sky, the middle one with rover mounts, the bottom one with access to the surface.', size: '3 decks', src: ['bgNsf'], conf: 'High' },
      tanks: { what: 'Propellant for the main engine and thrusters; their number and place are not published.', size: 'not published', src: ['assumed'], conf: 'Low' },
      engine: { what: 'One LEROS 4-ET main engine at the bottom centre.', size: 'more than 1 kN', src: ['bgNsf', 'bgWiki'], conf: 'High' },
      rcs: { what: 'Eight Spectre thrusters and twelve cold-gas thrusters steer the descent.', size: '8 + 12', src: ['bgNsf'], conf: 'High' },
      antennas: { what: 'One X-band and three S-band antennas talk to Earth.', size: '1 + 3', src: ['bgWiki'], conf: 'Medium' },
      solar: { what: 'Three solar panels give about 400 W.', size: '~400 W', src: ['bgNsf'], conf: 'High' },
      legs: { what: 'Four composite legs; honeycomb crush cores absorb the landing.', size: '4 legs', src: ['bgNsf'], conf: 'High' },
    },
  },
  centaur_v: {
    title: 'ULA Centaur V upper stage', short: 'Centaur V', load: () => import('../models/kit/kit-centaur-v.js'),
    story: {
      whole: 'Centaur V, the hydrogen-oxygen upper stage of ULA’s Vulcan: 5.4 m across and 12.6 m tall (the long version). It pushes landers and payloads out of Earth orbit.',
      cutaway: 'Liquid hydrogen fills the big forward tank; liquid oxygen, much denser, the short aft one. A common bulkhead (two steel skins round a fibreglass honeycomb) is all that separates them.',
      exploded: 'Hydrogen tank up, oxygen tank and engines down, the avionics adapter off the top.',
    },
    cut: { dir: 'side' }, shell: ['skin'], atc: 'avionics',
    dims: [
      { label: 'Height', text: '12.6 m (CV-HE)', axis: 'y', src: ['centaur'], conf: 'High' },
      { label: 'Diameter', text: '5.4 m', part: 'skin', axis: 'x', src: ['centaur'], conf: 'High' },
    ],
    parts: {
      skin: { what: 'Stainless-steel “balloon” tanks with 0.51 mm walls, held in shape by their own pressure.', size: '5.4 m × 12.6 m', src: ['centaur'], conf: 'High' },
      lh2: { what: 'Liquid hydrogen, forward: light, so it takes most of the volume.', size: '~111 m³ (~4.9 m of barrel)', src: ['computed', 'centaur'], conf: 'Medium' },
      bulkhead: { what: 'The common bulkhead between the tanks: two steel skins round a fibreglass honeycomb core.', size: 'one bulkhead', src: ['centaur'], conf: 'High' },
      lox: { what: 'Liquid oxygen, aft: about six times the hydrogen’s mass in a third of its volume.', size: '~40 m³ (~1.8 m)', src: ['computed', 'centaur'], conf: 'Medium' },
      avionics: { what: 'Flight computers and batteries on the forward adapter.', size: 'not published', src: ['centaur'], conf: 'Medium' },
      engines: { what: 'Two RL10 engines burn the hydrogen and oxygen.', size: '2 × (2.46 × 1.57 m)', src: ['centaur'], conf: 'High' },
    },
  },
  apollo_lrv: {
    title: 'Apollo LRV (1971)',
    cut: { dir: 'down', at: 0.5 }, shell: [],
    dims: [
      { label: 'Length', text: '3.1 m', axis: 'z', src: ['lrv'], conf: 'High' },
      { label: 'Height', text: '1.14 m', axis: 'y', src: ['lrv'], conf: 'High' },
    ],
    parts: {
      frame: { what: 'The 1971 rover: a three-part folding chassis, four wire-mesh wheels with hub motors, two seats.', size: '3.1 m long, 2.3 m wheelbase', src: ['lrv'], conf: 'High' },
    },
  },
};
