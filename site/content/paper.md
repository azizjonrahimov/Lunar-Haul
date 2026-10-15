# Paper

## Who Hauls the Habitat? A Verified Simulation Testbed, a Pooled Dispatch Marketplace and a Reference Design for Lunar Surface Logistics

Azizjon Rahimov, Roatify Research · version 2, October 2026 · 44 pages ·
[PDF](https://github.com/azizjonrahimov/lunar-logistics-research/blob/main/paper/lunar_logistics_marketplace_paper_v2.pdf) ·
[Code and data](https://github.com/azizjonrahimov/lunar-logistics-research)

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

### Version 3 (in preparation)

The next version adds a learned landing controller and a learned rover driver to the testbed, puts the base on
real LOLA terrain, and reports the first quantitative relation between landing dispersion, pad standoff, plume
keep-out rules, rover autonomy and surface delivery cost, a relation NASA's architecture papers describe only
qualitatively. Method and interim results are on the Method page and in the labs; the paper and its figures
will be posted here with a DOI when the experiments are complete.

### Cite

```
@misc{rahimov2026lunarhaul,
  title   = {Who Hauls the Habitat? A Verified Simulation Testbed, a Pooled Dispatch Marketplace
             and a Reference Design for Lunar Surface Logistics},
  author  = {Rahimov, Azizjon},
  year    = {2026},
  version = {2.0.0},
  url     = {https://github.com/azizjonrahimov/lunar-logistics-research}
}
```

A machine-readable citation is in `CITATION.cff` in the repository.
