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
};

// confidence -> what the part list shows
export const published = conf => conf === 'High';

/* KIT[id]: {
     title, cut: {dir: 'side' | 'down', at: 0..1 of the height (down cuts)}, shell: [part names drawn see-through in X-ray],
     dims: [{label, text, part?: part name to measure (default: the whole vehicle), axis: 'x' | 'y' | 'z', src, conf}],
     parts: {partName | groupName: {what, size, src: [source keys], conf}} } */
export const KIT = {
  CLPS: {
    title: 'Nova-C class lander',
    cut: { dir: 'side' }, shell: ['body'],
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
    cut: { dir: 'side' }, shell: ['hull'],
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
    cut: { dir: 'side' }, shell: ['hull'],
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
    cut: { dir: 'down', at: 0.48 }, shell: ['chassis'],
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
    cut: { dir: 'down', at: 0.5 }, shell: ['bed'],
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
    cut: { dir: 'down', at: 0.3 }, shell: ['body'],
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
