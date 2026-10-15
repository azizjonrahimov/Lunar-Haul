"""Named scenarios: the three build-up phases and the Phase-2 fleet-size variants.

Moved here from experiments/scenarios.py (which now re-exports this module) so that the
installed package can expand compact scenario files and list the named library without a
repository checkout. The values are unchanged.
"""
from .scenario import Scenario, BulkFlow

OWNERS = ["NASA", "NASA", "NASA", "NASA", "CoA", "CoA", "CoB", "CoC"]

# Phase 1: robotic precursor (pre-2029). A few tonnes a year, two LTV-class rovers.
P1 = Scenario(name="P1", landings_per_year={"CLPS": 4, "MK1": 1, "LARGE": 0}, cargo_owners=OWNERS,
              fleet=[("NASA", "LTV", "supervised", "A"), ("CoA", "LTV", "supervised", "A"),
                     ("CoB", "MICRO", "teleop", "A")],
              bulk_flows=[BulkFlow("CONSTR", "BASE", 30, lot_kg=500)],
              n_operators=2)

# Phase 2: build-out (2029-2032). Tens of tonnes a year incl. one large lander; mixed fleet.
P2 = Scenario(name="P2", landings_per_year={"CLPS": 4, "MK1": 3, "LARGE": 1}, cargo_owners=OWNERS,
              fleet=[("NASA", "LTV", "supervised", "A"), ("NASA", "LTV", "supervised", "A"),
                     ("CoA", "LTV", "supervised", "A"), ("CoA", "HAUL", "supervised", "A"),
                     ("CoB", "MICRO", "teleop", "A"), ("CoC", "LTV", "teleop", "A")],
              bulk_flows=[BulkFlow("CONSTR", "BASE", 300, lot_kg=1000),      # regolith shielding / berms
                          BulkFlow("CONSTR", "ISRU", 200, lot_kg=1000)],     # excavated feedstock to pilot plant
              n_operators=3)

# Phase 3: sustained presence (post-2032). ~100 t/yr with several large landers.
P3 = Scenario(name="P3", landings_per_year={"CLPS": 4, "MK1": 4, "LARGE": 3}, cargo_owners=OWNERS,
              fleet=[("NASA", "LTV", "supervised", "A"), ("NASA", "LTV", "supervised", "A"),
                     ("NASA", "HAUL", "autonomous", "A"),
                     ("CoA", "LTV", "supervised", "A"), ("CoA", "HAUL", "supervised", "A"),
                     ("CoB", "MICRO", "teleop", "A"), ("CoB", "LTV", "autonomous", "A"),
                     ("CoC", "LTV", "teleop", "A"), ("CoC", "HAUL", "autonomous", "A")],
              bulk_flows=[BulkFlow("CONSTR", "BASE", 800, lot_kg=1000),
                          BulkFlow("CONSTR", "ISRU", 600, lot_kg=1000),
                          BulkFlow("PSR", "ISRU", 100, lot_kg=500, priority=2)],  # icy regolith from shadow
              n_operators=4)

PHASES = {"P1": P1, "P2": P2, "P3": P3}

# Phase-2 fleet-size variants (experiment E2). Same table as experiments/run_all.py FLEETS;
# tests/test_formats.py checks that the two stay equal.
_LTV = lambda o, a="supervised", s="A": (o, "LTV", a, s)
_HAUL = lambda o, a="supervised", s="A": (o, "HAUL", a, s)
_MICRO = lambda o, a="teleop", s="A": (o, "MICRO", a, s)
FLEETS = {
    2: [_LTV("NASA"), _LTV("CoA")],
    3: [_LTV("NASA"), _LTV("CoA"), _MICRO("CoB")],
    4: [_LTV("NASA"), _LTV("CoA"), _HAUL("CoA"), _MICRO("CoB")],
    5: [_LTV("NASA"), _LTV("NASA"), _LTV("CoA"), _HAUL("CoA"), _MICRO("CoB")],
    6: [_LTV("NASA"), _LTV("NASA"), _LTV("CoA"), _HAUL("CoA"), _MICRO("CoB"), _LTV("CoC", "teleop")],
    8: [_LTV("NASA"), _LTV("NASA"), _LTV("CoA"), _HAUL("CoA"), _MICRO("CoB"), _LTV("CoC", "teleop"),
        _LTV("CoB", "autonomous"), _HAUL("CoC", "autonomous")],
}
