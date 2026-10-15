# Method

This page says what is simulated, what is learned, what is assumed, and how we check it. Numbers quoted here
carry the same flags as the rest of the site: **Measured**, **Spec**, **Modelled**, **Assumed**.

## The logistics engine (v2, verified)

A discrete-event model of cargo movement at a nine-site base near the lunar south pole: two landing pads, a
cargo depot, the habitat zone, a power plant, a construction site, an oxygen-from-regolith pilot plant, a science
site and a permanently shadowed crater. Landers of three classes (CLPS-class 100–500 kg, Blue Moon MK1-class 2–3 t,
large landers 12–30 t) arrive as Poisson processes and release manifests drawn from NASA's published cargo
classes. A fleet of rovers owned by several organisations (1.5 t LTV-class, a 10 t hauler, a 0.3 t micro-rover)
moves the items under one of four dispatch rules: bilateral in-house contracting (each cargo owner bound to one
carrier), pooled greedy dispatch, batched minimum-cost assignment, and a pooled marketplace built on a sequential
auction with bundling, consolidation of bulk lots, team lifts for oversize items, night-aware acceptance and
anticipatory staging before published landings. The engine models the lunar night, Earth–Moon control latency
(speeds fitted to NASA's teleoperation trials), vehicle faults, vehicles' other duties, regolith bulk flows and
the return flow of samples and waste.

Thirteen verification checks compare the engine with analytic formulas, published measurements and conservation
identities; all pass within 1 % (the M/G/1 queue check within 0.5 %). A line-by-line JavaScript port runs in the
browser and agrees with the Python engine on 24 metric cells within combined 95 % confidence intervals; the
Verification page runs both checks live.

## Terrain

The base is placed on real terrain: NASA's Lunar Orbiter Laser Altimeter DEM of the Connecting Ridge between
Shackleton and de Gerlache craters at 5 m per post (PGDA Site01, 16 × 16 km; median vertical error 0.3–0.5 m,
Measured). The nine sites sit on cells whose pad-scale slope (the tilt of the mean surface over a 100 m disk) is
at most 5°, the science site at most 8°, and the "PSR" site is in cast shadow at all four reference sun azimuths.
Landing pads are placed at 0.5, 1, 2, 3 and 5 km from the base on the best-lit flat ground; at 0.5 and 1 km one of
the two pads (PAD A) has a clear line of sight to the base; the other pad and every pad from 2 km on are hidden by
the terrain, which matters for plume ejecta.
Shadows and lines of sight are computed with the Moon's curvature and a sun 1.5° above the horizon.

## The learned lander (Phase 3)

A terminal-descent environment in Gymnasium: a 3-DoF point mass with a throttleable engine and tilt-rate
commands, lunar gravity 1.62 m/s², mass flow by specific impulse, starting from NASA's SPLICE gate (500 m slant
range, −15 m/s vertical, 30 m/s horizontal, Spec) with dispersed initial conditions and randomised mass, thrust
and specific impulse. Below 30 m the altimeter can be biased, noisy or drop out, because every tip-over or crash
since 2023 traces to the altitude-sensing chain. A landing succeeds inside the SPLICE touchdown box (vertical
≤ 2.0 m/s, horizontal ≤ 1.0 m/s, tilt ≤ 6°, rates ≤ 2°/s, Spec); landed tilt beyond 12° is a tip-over. Three
lander classes are parameterised from flown or specified vehicles; where a value is unpublished (Blue Moon MK1's
throttle floor and descent mass, for instance) it is flagged Assumed and swept.

Two controllers fly it: a classical closed-loop law (gravity turn with ZEM/ZEV terminal guidance) and a policy
trained by proximal policy optimisation with a velocity-field reward of the kind used in the published Mars
landing work, plus deliberately broken variants (no survival term, a hover bonus) that reproduce the failure
modes the reinforcement-learning tutorial warns about. Each controller is run through thousands of dispersed
landings; the resulting distributions of miss distance, touchdown state, propellant and time near the ground are
what the logistics engine samples at every landing.

## The learned rover (Phase 3)

A driving environment on the same terrain: a kinematic bicycle whose speed is capped by autonomy level (Earth
teleoperation with 0–8 s round-trip delay, supervised autonomy, full autonomy), slip taken from a lunar-gravity
slope–slip relation validated against NASA Glenn single-wheel tests (Modelled), energy calibrated to the Apollo
Lunar Roving Vehicle's 57–60 Wh/km (Measured, scaled to a 1.6 t rover: Assumed), and lighting penalties from
NASA's polar-lighting driving study. Teleoperation is modelled as command delay plus stop-to-confirm halts,
calibrated so the speed made good reproduces the JSC measurements (3.24, 2.56, 2.03 and 1.76 km/h at 0, 4, 6 and
8 s) within 1.3 %. A scripted expert (A* over a slope-and-lighting cost grid with pure-pursuit tracking) drives
every leg between sites; a behavioural-cloning network trained on the expert's heightmap views replaces it, and
its interventions are counted and charged at the round-trip delay plus recovery time rather than the 6 s of the
original road-driving metric. The per-leg time, energy and intervention distributions by autonomy level,
latency and lighting are what the logistics engine samples for every trip.

## Plume keep-out

NASA states that no safe standoff distance has been defined for landers and that plume predictions remain
"largely qualitative". We therefore do not predict ejecta; we sweep a keep-out radius (0.2–3 km) and a stand-down
time around each landing, during which no job may start or end at the pad and vehicles inside the radius move to
a sheltered site, and we report the logistics cost of each choice.

## What we measure

Delay of urgent cargo (mean and 90th percentile), the share delivered within 24 h, immovable mass, stranded
vehicles, fleet utilisation, energy, operator hours and system cost per kilogram moved and per landed kilogram,
over thirty or more seeded years per cell with confidence intervals, and precision runs to a 1–2 % half-width for
the headline cells. The Phase 3 experiments sweep landing dispersion, pad standoff, keep-out radius and stand-down
time, autonomy level and fleet size, and fit the relation between them and delivery cost.

## What is not modelled

No plume physics (only keep-out geometry and timing); no crew; no construction scheduling; one base; vehicles as
representative classes rather than specific products. Earth-tested slip relations are known to be optimistic in
lunar gravity, and no measured interventions-per-kilometre exist for any planetary rover; both are stated where
they enter the numbers.
