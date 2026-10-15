# About

LunarSim is a research testbed for one practical question: once cargo has landed near a Moon base, how does it get
from the pad to the place it is needed, and what does that cost? NASA's Moon Base plan lands a few tonnes a year
before 2029, tens of tonnes a year in 2029–2032 and more after that, in items from 10 kg instruments to 15 t
habitats, while the rovers under contract carry 0.8–1.6 t each. NASA's 2026 architecture guide names "a
marketplace for lunar logistics" as a goal without saying what one would do. This project builds the simulation
that lets such questions be answered with numbers instead of adjectives.

## Who

LunarSim is built by Azizjon Rahimov (Roatify Research). The simulation engine, the browser port, the experiments,
the datasets and the paper are developed in the open on GitHub. The current phase adds two learned models, a
landing-descent controller and a rover driving model, to the logistics engine, and this site to let anyone run
the result.

## Why

Three things were missing when the project started. First, a verified, open testbed: a discrete-event model of a
nine-site south-pole base with lander manifests, a fleet owned by several companies, the lunar night, Earth–Moon
control latency, faults and other duties, checked against thirteen analytic and published references. Second,
a concrete definition of a logistics marketplace and a fair comparison with the alternatives (today's bilateral
in-house contracting, pooled greedy dispatch, batched assignment). Third, numbers that NASA's own documents leave
blank: how landing precision, the distance between pads and the base, plume keep-out rules and rover autonomy
change delivery delay and cost. The third is the current work.

## How the site is made

Everything you see is driven by simulation state or by published data. The terrain is NASA's Lunar Orbiter Laser
Altimeter model of the Connecting Ridge near Shackleton crater at 5 m per post, lit by a sun that stays within
1.5° of the horizon. Vehicles are representative, parametric stand-ins built from public dimensions; no official
model of an Artemis-era lander or rover is public. Every number on the site carries a flag: **Measured** (flight
or laboratory data), **Spec** (a published design value or requirement), **Modelled** (produced by a model,
including this simulation) or **Assumed** (our choice, swept in the sensitivity analysis). Hover or focus a number
to see its source.

## Motion and accessibility

The site follows your operating system's "reduce motion" setting (`prefers-reduced-motion`) and never starts
motion you cannot stop:

- **Landing page:** the sun sweeping round the horizon starts paused when reduced motion is on; the
  *Pause sun* button stops it at any time, and it also stops when the view is off screen or the tab is hidden.
- **World:** a replay never starts by itself; under reduced motion the camera presets jump instead of gliding.
- **Lander lab:** under reduced motion an episode is shown at its final frame; *Replay* plays it on request.
- **Rover lab:** under reduced motion the scripted driver's run is computed instantly; driving it yourself runs
  in real time because you chose to.
- Every 3D or canvas view has a text equivalent next to it: a telemetry table, a data table under each figure,
  or the 2D plan view. Controls work with the keyboard (Space and the arrow keys on the World page and in the
  rover lab's drive-it-yourself mode).

## Credits and licences

- Terrain: LOLA 5 m/px south-polar DEMs, NASA Goddard Planetary Geodynamics Data Archive (Barker et al. 2021,
  *Planetary and Space Science* 203, 105119). Credit NASA/GSFC.
- Photographs, where used, are NASA images and are credited in place. NASA does not endorse this project and no
  NASA insignia is used.
- Code: MIT licence. Data produced by the project: CC BY 4.0. Fonts: Source Sans 3 (SIL Open Font License).
  Icons: Lucide (ISC). 3D rendering: three.js (MIT). Charts: Observable Plot (ISC).
- Simulation runs you start on this site run in your browser; nothing you enter leaves the page unless you sign in
  and choose to save a run.

## Contact

Open an issue or a discussion on the GitHub repository (link in the header). For the paper, cite the preprint
listed on the Paper page; a machine-readable citation is in `CITATION.cff`.
