# Papers

## Lunar ATC: three papers (2026)

Three papers on Lunar ATC, the network that lets robots of different companies share jobs and roads at the south
pole without waiting for Earth. P1 is finished; P2 and P3 are being written.

### P1 · <!--@paper:p1:title-->

Azizjon Rahimov, Roatify Research · preprint, October 2026 ·
[Paper source, data and pre-registration](https://github.com/azizjonrahimov/Lunar-Haul/tree/main/paper/p1) ·
PDF to follow

**Abstract.** <!--@paper:p1:abstract-->

**Keywords:** <!--@paper:p1:keywords-->

#### P1 in numbers

Every number below is read from the paper's values file (`paper/p1/values.json`) when this site is built.

- **Scale.** <!--@v:p1:P1-N-RUNS-ALL--> pre-registered simulated years under <!--@v:p1:P1-N-REGIMES--> decision regimes.
- **Waiting for Earth.** At <!--@v:p1:P1-LOAD-MAIN--> load, a pooled dispatcher on Earth that stops when Earth sets kept urgent cargo waiting <!--@v:p1:P1-H2-STRICT-MINUS-O--> longer than the full-information marketplace (95 % CI <!--@v:p1:P1-H2-STRICT-MINUS-O-CI-->). Planning ahead before each blackout left <!--@v:p1:P1-PLAN-MINUS-O--> of extra wait (95 % CI <!--@v:p1:P1-PLAN-MINUS-O-CI-->).
- **Deciding on the Moon.** The robots' own auction, at message loss <!--@v:p1:P1-LOSS-MAIN-->, kept urgent cargo waiting <!--@v:p1:P1-H3A-DIFF--> than the full-information marketplace (90 % CI <!--@v:p1:P1-H3A-CI90-->): not distinguishable from zero, but too wide to show equivalence.
- **Learned bids.** A learned linear correction to the bids, with <!--@v:p1:P1-LIN-N-WEIGHTS--> weights, cut the urgent wait by <!--@v:p1:P1-H4-LIN-DIFF-30--> against hand-built bids (<!--@v:p1:P1-H4-LIN-PCT-30-->; 95 % CI <!--@v:p1:P1-H4-LIN-CI-30-->). A <!--@v:p1:P1-MLP-N-PARAMS-->-parameter network trained the same way did not: its difference was <!--@v:p1:P1-H4-MLP-DIFF-30--> (95 % CI <!--@v:p1:P1-H4-MLP-CI-30-->). The [Lunar ATC page](../atc/#atc-bid-h) runs the linear correction in your browser.
- **What sharing is worth.** <!--@v:p1:P1-H1-UNDELIVERED-SHARE--> of the gap between owners working alone and the pooled fleet is cargo that owners alone never deliver; lifts by two owners' rovers account for <!--@v:p1:P1-H1-TEAM-SHARE--> of it.

#### Cite P1

<!--@paper:p1:bibtex-->

### P2 · <!--@paper:p2:title-->

In preparation. The safety program it tests can be watched at work in the
[encounter sandbox](../atc/#sandbox).

### P3 · <!--@paper:p3:title-->

In preparation.

## Earlier papers

### Who Hauls the Habitat? A Verified Simulation Testbed, a Pooled Dispatch Marketplace and a Reference Design for Lunar Surface Logistics

Azizjon Rahimov, Roatify Research · version 2, October 2026 · 44 pages ·
[PDF](https://github.com/azizjonrahimov/Lunar-Haul/blob/main/paper/lunar_logistics_marketplace_paper_v2.pdf) ·
[Code and data](https://github.com/azizjonrahimov/Lunar-Haul)

**Abstract.** NASA's Moon Base plan lands about 4 tonnes of cargo at the lunar south pole before 2029, roughly
60 tonnes in 2029–2032 and 150 tonnes after that. Individual items range from 10 kg instruments to 15-tonne
habitats, yet the rovers under contract carry 800–1,600 kg, and NASA's own architecture papers say that no
planned vehicle can relocate a large element. NASA's April 2026 architecture guide names "a marketplace for lunar
logistics" as a goal but does not say what one would do. We study that question with a discrete-event testbed of
surface cargo movement at a nine-site south-pole base, verified against thirteen analytic and published
references and cross-checked against an independent browser implementation on 24 metric cells. We compare four
dispatch rules: bilateral in-house fleets, pooled greedy dispatch, batched optimal assignment, and a pooled
marketplace built on a sequential single-item auction with bundling, consolidation, team lifts, night-aware
acceptance and anticipatory staging. Pooling helps only when the fleet is fragmented: the in-house penalty follows
a simple law in effective vehicles per owner. Any pooled rule reaches a same-day service level with four vehicles
at Phase-2 demand where in-house fleets do not with eight. 1.6 t rovers can move 40 % of the Phase-2 manifest, two
lifting together 55 %, a 10 t hauler 88 %, and only 15 t of capacity all of it. A surface move costs about $300
per kilogram moved, a few percent of the cost of landing it.

**Correction (October 2026).** Version 2's cost per landed kilogram came from an approximation that divided by
delivered mass less the bulk released. With the exact metric (landed cargo delivered, bulk and return flows
excluded; ratio of means over 30 years, seed-bootstrap 95 % interval) the pooled marketplace costs about $5,500 per
landed kilogram rather than about $5,000: $5,525 [4,460, 7,281] at Phase 2 with four vehicles, against $10,019
[8,067, 12,756] for in-house fleets. The cost per kilogram moved is unchanged.

#### Version 3 (in preparation)

**Where the Lander Lands: Landing Precision, Pad Standoff, Plume Keep-Out and Rover Autonomy Priced in Lunar
Surface Logistics.** Azizjon Rahimov, Roatify Research ·
[Version 3 (draft, October 2026, PDF, 75 pages)](https://github.com/azizjonrahimov/Lunar-Haul/blob/main/paper/v3/where_the_lander_lands_v3.pdf) ·
A draft; not yet posted with a DOI.

It puts the base on real LOLA terrain, adds learned landing controllers and a rover driving model to the testbed,
and prices landing dispersion, pad standoff, plume keep-out and rover autonomy in the delay and cost of surface
delivery, a relation NASA's architecture papers describe only qualitatively. At the typical fleet load, each kilometre of pad standoff adds <!--@r:standoff_pct--> to the delay of urgent cargo, most of it in the first kilometre; a plume keep-out radius and a stand-down add no measurable delay; landing dispersion adds <!--@r:dispersion_pct--> per e-fold of the mean miss, through landings off the
pad. The figures and tables are on the [Results](../results/) page as they are produced, and the method is on the
[Method](../method/) page. The final version will be posted here with a DOI.

#### Cite version 3

```
@misc{rahimov2026lunarhaul,
  title   = {Where the Lander Lands: Landing Precision, Pad Standoff, Plume Keep-Out and Rover
             Autonomy Priced in Lunar Surface Logistics},
  author  = {Rahimov, Azizjon},
  year    = {2026},
  version = {3.0.0},
  note    = {Draft, October 2026},
  url     = {https://github.com/azizjonrahimov/Lunar-Haul}
}
```

A machine-readable citation is in `CITATION.cff` in the repository.
