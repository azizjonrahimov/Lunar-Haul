"""The "p5" scenario family (B-71): real 2028-2032 vehicle classes, owners, team lifts and load variants.

Scenario.p5 (opt-in; None = v2/v3/R-1 behaviour, byte-identical) switches on, inside the engine (P5State):
- class lookup with sweeps: fleet class ids from lunarsim/atc/vehicles-p5.json, `class_overrides` by parameter name;
- reach: the largest single capacity and the largest pair the fleet can field (pairs only, `team_rule` "sum" = the
  two capacities, "krawciw" = `krawciw_fraction` x the two vehicle masses, Krawciw et al. arXiv 2510.18766).
  Every landed item heavier than the reach goes to a separate list ("needs heavy-lift equipment, outside this
  fleet") and is never offered to the robots; its count and tonnage are in the run summary (LEAD, B-71 Q3);
- team_lift_share: from its own seeded stream (two uniforms per landed item, always drawn, so variants share every
  other draw), that share of the in-reach items gets a new mass U(largest single, largest pair]; all other items
  keep their P2 masses (a return item keeps its drawn ratio to its parent);
- hoppers (class `flies`): straight-line hops, a km budget and an active window from deployment (t = 0), then
  retired; `hopper_refuel` (Assumed variant) refills the budget each synodic month and drops the window;
- daily km budget (Phase-1 LTVs, 6 km/day remote): a token bucket per vehicle; a job that needs more km than the
  bucket holds is lengthened by the time to earn them (applied at commit, like faults).
Builders below write the scenario family (owners 2 / 3 / 3-unequal / 5; loads 10 / 30 / 60 % via a demand
multiplier k calibrated by tools/atc/p5_scenarios.py).
"""
from __future__ import annotations

import itertools
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..scenario import LUNAR_CYCLE_H, BulkFlow, Scenario
from . import vehicles as V

P5_STREAM = 500_009              # seed offset of the p5 mass stream (independent of demand and operations)
KRAWCIW_FRACTION = 0.3           # Spec (Krawciw et al.): 475 kg carried by two 800 kg vehicles
DEFAULTS = {"team_lift_share": 0.10, "team_rule": "sum", "krawciw_fraction": KRAWCIW_FRACTION,
            "class_overrides": {}, "hopper_refuel": False}
HEAVY_NOTE = "needs heavy-lift equipment, outside this fleet"


def cfg(sc: Scenario) -> Dict[str, Any]:
    d = dict(DEFAULTS)
    d.update(sc.p5 or {})
    return d


def vehicle_class(name: str, sc: Optional[Scenario] = None):
    ov = (cfg(sc)["class_overrides"].get(name) if sc is not None and sc.p5 is not None else None)
    return V.build(name, ov) if ov else V.P5_CLASSES[name]


def pair_capacity(a, b, rule: str, frac: float = KRAWCIW_FRACTION) -> float:
    if rule == "sum":
        return a.cls.capacity_kg + b.cls.capacity_kg
    if rule == "krawciw":
        return frac * (getattr(a.cls, "mass_kg", 0.0) + getattr(b.cls, "mass_kg", 0.0))
    raise ValueError(f"unknown team_rule {rule!r}")


class P5State:
    """Per-run p5 rules (built by the engine after the fleet)."""

    def __init__(self, sim):
        self.sim = sim
        c = cfg(sim.sc)
        self.share = float(c["team_lift_share"])
        self.rule, self.frac = str(c["team_rule"]), float(c["krawciw_fraction"])
        self.refuel = bool(c["hopper_refuel"])
        self.rng = np.random.default_rng(int(sim.seed) + P5_STREAM)
        vs = sim.vehicles
        self.single_max = max((v.cls.capacity_kg for v in vs), default=0.0)
        team = [v for v in vs if v.cls.can_team_lift]
        pairs = [(pair_capacity(a, b, self.rule, self.frac), a, b) for a, b in itertools.combinations(team, 2)]
        self.pair_max = max((p[0] for p in pairs), default=0.0)
        self.reach = max(self.single_max, self.pair_max)
        own: Dict[str, float] = {}
        for p, a, b in pairs:
            if a.owner == b.owner:
                own[a.owner] = max(own.get(a.owner, 0.0), p)
        self.same_owner_pair_max = own
        self.heavy: List[Any] = []
        self.team_items: List[Any] = []
        self.redrawn = 0
        self.refused = 0
        self.day_cap_h = 0.0
        self.hopper_km: Dict[int, float] = {}
        self._cycle_km: Dict[Tuple[int, int], float] = {}
        self._tokens: Dict[int, Tuple[float, float]] = {}
        self.retired_at: Dict[int, float] = {}
        for bf in sim.sc.bulk_flows:
            if bf.lot_kg > self.reach:
                raise ValueError(f"p5: bulk lot {bf.lot_kg} kg exceeds the fleet's reach {self.reach} kg")

    # ---------------------------------------------------------------------------------------- demand
    def on_landing(self, items: List[Any]) -> List[Any]:
        """Items within reach (team re-draw applied); the rest go to the heavy-lift list."""
        keep = []
        for c in items:
            u_team, u_mass = self.rng.random(), self.rng.random()
            if c.mass_kg > self.reach:
                c.heavy_lift = True
                self.heavy.append(c)
                continue
            if u_team < self.share and self.pair_max > self.single_max:
                m = self.single_max + (1.0 - u_mass) * (self.pair_max - self.single_max)   # (single, pair]
                if c.return_mass_kg > 0:
                    c.return_mass_kg *= m / c.mass_kg
                c.mass_kg = m
                self.redrawn += 1
            if c.mass_kg > self.single_max:
                self.team_items.append(c)
            keep.append(c)
        return keep

    # ---------------------------------------------------------------------------------------- teams
    def team_for(self, c, cands: List[Any]) -> Optional[List[Any]]:
        """The first pair (largest capacities first, as dispatch._team_for) that can lift c."""
        cands = sorted(cands, key=lambda v: -v.cls.capacity_kg)
        for a, b in itertools.combinations(cands, 2):
            if pair_capacity(a, b, self.rule, self.frac) >= c.mass_kg:
                return [a, b]
        return None

    # ---------------------------------------------------------------------------------------- hoppers
    def km_left(self, v, t: float) -> float:
        b = getattr(v.cls, "km_budget", math.inf)
        if not math.isfinite(b):
            return math.inf
        if self.refuel:
            return b - self._cycle_km.get((v.id, int(t // LUNAR_CYCLE_H)), 0.0)
        return b - self.hopper_km.get(v.id, 0.0)

    def active_until(self, v) -> float:
        return math.inf if self.refuel else getattr(v.cls, "active_h", math.inf)

    def limited(self, v) -> bool:
        return math.isfinite(getattr(v.cls, "km_budget", math.inf)) or math.isfinite(getattr(v.cls, "active_h", math.inf))

    def job_ok(self, job, t0: float, dur: float, km: float) -> bool:
        for v in job.vehicles:
            if not self.limited(v):
                continue
            k = km / len(job.vehicles)
            if k > self.km_left(v, t0) + 1e-9 or t0 + dur > self.active_until(v) + 1e-9:
                return False
        return True

    def note_km(self, v, km: float, t: float) -> None:
        if not self.limited(v):
            return
        self.hopper_km[v.id] = self.hopper_km.get(v.id, 0.0) + km
        key = (v.id, int(t // LUNAR_CYCLE_H))
        self._cycle_km[key] = self._cycle_km.get(key, 0.0) + km
        if not self.refuel and self.km_left(v, t) <= 1e-6:
            self.retire(v, t)

    def retire(self, v, t: float) -> None:
        if v.id not in self.retired_at:
            self.retired_at[v.id] = t
        v.alive = False

    def check_window(self, v, t: float) -> bool:
        """False (and retire) when t is past the vehicle's active window."""
        if t >= self.active_until(v):
            self.retire(v, self.active_until(v))
            return False
        return True

    # ---------------------------------------------------------------------------------------- daily km
    def day_cap_delay(self, job, km: float, t: float) -> float:
        """Hours a job is lengthened so that no vehicle drives more than km_per_day in any day (token bucket)."""
        extra = 0.0
        for v in job.vehicles:
            cap = getattr(v.cls, "km_per_day", math.inf)
            if not math.isfinite(cap):
                continue
            tok, last = self._tokens.get(v.id, (cap, 0.0))
            tok = min(cap, tok + (t - last) * cap / 24.0)
            need = km / len(job.vehicles)
            if need > tok:
                extra = max(extra, (need - tok) * 24.0 / cap)
                tok = 0.0
            else:
                tok -= need
            self._tokens[v.id] = (tok, t)
        self.day_cap_h += extra
        return extra

    # ---------------------------------------------------------------------------------------- summary
    def summary(self) -> Dict[str, float]:
        sim = self.sim
        H = sim.sc.horizon_h
        active = sum(min(H, self.retired_at.get(v.id, H)) for v in sim.vehicles)
        busy = sum(v.hours_busy for v in sim.vehicles)
        cargo = [v for v in sim.vehicles if v.cls.name in CARGO_CLASSES]
        own = self.same_owner_pair_max
        n_team = len(self.team_items)
        same = sum(1 for c in self.team_items if any(m >= c.mass_kg for m in own.values()))
        team_done = [c for c in self.team_items if c.t_delivered is not None]
        return {
            "p5_heavy_items": len(self.heavy), "p5_heavy_t": sum(c.mass_kg for c in self.heavy) / 1000.0,
            "p5_reach_kg": self.reach, "p5_single_max_kg": self.single_max, "p5_pair_max_kg": self.pair_max,
            "p5_team_items": n_team, "p5_team_items_redrawn": self.redrawn,
            "p5_team_items_same_owner_liftable": same,
            "p5_team_items_delivered": len(team_done),
            "p5_utilisation_active": busy / max(active, 1e-9),
            "p5_cargo_util": sum(v.hours_busy for v in cargo) / max(H * len(cargo), 1e-9),
            "p5_vehicle_hours_active": active,
            "p5_hopper_km": sum(self.hopper_km.values()), "p5_hoppers_retired": len(self.retired_at),
            "p5_refused_jobs": self.refused, "p5_day_cap_h": self.day_cap_h,
        }


# -------------------------------------------------------------------------------------------------------------
# scenario family
# -------------------------------------------------------------------------------------------------------------
ROVER_AUTONOMY = "supervised"     # as the R-1 base fleet (E21)
HOPPER_AUTONOMY = "autonomous"    # Assumed: hoppers fly their own hop sequences
CARGO_CLASSES = ("CARGO_FLEX", "CARGO_EAGLE")   # the load variants are defined on these (LEAD, B-71 Q6)
BULK_LOT_KG = 500.0               # Assumed: regolith bins sized for the cargo-class rovers (FLEX 2,000 kg, Eagle 800 kg)

# owner mix -> (fleet as (owner, class), cargo share per owner). The same eight vehicles in every mix.
OWNER_MIXES: Dict[str, Tuple[List[Tuple[str, str]], Dict[str, float]]] = {
    "3eq": ([("A", "LTV1_CLV1"), ("A", "CARGO_FLEX"),
             ("B", "LTV1_PEGASUS"), ("B", "CARGO_EAGLE"),
             ("C", "MAPP_SMALL"), ("C", "HOPPER_MOONFALL"), ("C", "HOPPER_MOONFALL"), ("C", "MAPP_SMALL")],
            {"A": 1 / 3, "B": 1 / 3, "C": 1 / 3}),
    "3uneq": ([("A", "LTV1_CLV1"), ("A", "CARGO_FLEX"),
               ("B", "LTV1_PEGASUS"), ("B", "CARGO_EAGLE"),
               ("C", "MAPP_SMALL"), ("C", "HOPPER_MOONFALL"), ("C", "HOPPER_MOONFALL"), ("C", "MAPP_SMALL")],
              {"A": 0.50, "B": 0.35, "C": 0.15}),
    "2eq": ([("A", "LTV1_CLV1"), ("A", "CARGO_FLEX"), ("A", "MAPP_SMALL"), ("A", "HOPPER_MOONFALL"),
             ("B", "LTV1_PEGASUS"), ("B", "CARGO_EAGLE"), ("B", "MAPP_SMALL"), ("B", "HOPPER_MOONFALL")],
            {"A": 0.5, "B": 0.5}),
    "5eq": ([("A", "LTV1_CLV1"), ("A", "CARGO_FLEX"),
             ("B", "LTV1_PEGASUS"), ("B", "CARGO_EAGLE"),
             ("C", "MAPP_SMALL"), ("C", "HOPPER_MOONFALL"),
             ("D", "MAPP_SMALL"), ("E", "HOPPER_MOONFALL")],
            {"A": 0.2, "B": 0.2, "C": 0.2, "D": 0.2, "E": 0.2}),
}
LOADS = {"10": 0.10, "30": 0.30, "60": 0.60}
TEAM_SHARES = (0.0, 0.10, 0.25)


def owner_pool(shares: Dict[str, float], n: int = 60) -> List[str]:
    """cargo_owners list (the engine draws an owner uniformly from it) with the given shares; 60 entries hold
    halves, thirds, fifths and 50/35/15 exactly."""
    counts = {o: round(s * n) for o, s in shares.items()}
    if sum(counts.values()) != n or any(abs(counts[o] - s * n) > 1e-9 for o, s in shares.items()):
        raise ValueError(f"owner shares {shares} do not divide {n} entries")
    return [o for o in sorted(counts) for _ in range(counts[o])]


def build(owners: str = "3eq", k: float = 1.0, team_lift_share: float = 0.10, name: Optional[str] = None,
          bulk_lot_kg: float = BULK_LOT_KG, **p5_extra) -> Scenario:
    """A p5 scenario: P2's landings (rates x k), P2's bulk flows split by owner share (tonnes x k, 500 kg lots), the
    owner mix's fleet, the Phase-3 terrain fields as R-1 uses them (Connecting Ridge, 1 km pads, driving-v1,
    classical landings), no Earth-link rule (B-72 adds the decision places)."""
    from ..phases import PHASES
    base = PHASES["P2"]
    fleet_spec, shares = OWNER_MIXES[owners]
    fleet = [(o, c, HOPPER_AUTONOMY if c.startswith("HOPPER_") else ROVER_AUTONOMY, "A") for o, c in fleet_spec]
    bulk = [BulkFlow(b.origin, b.dest, b.tonnes_per_year * k * s, lot_kg=float(bulk_lot_kg), owner=o, priority=b.priority,
                     start_h=b.start_h)
            for b in base.bulk_flows for o, s in sorted(shares.items())]
    p5 = dict(DEFAULTS, team_lift_share=float(team_lift_share), owners=owners, k=float(k), **p5_extra)
    return base.with_(
        name=name or f"p5-{owners}-k{k:g}-team{team_lift_share:g}",
        landings_per_year={lt: r * k for lt, r in base.landings_per_year.items()},
        cargo_owners=owner_pool(shares), bulk_flows=bulk, fleet=fleet,
        n_operators=max(base.n_operators, len(fleet) // 2),
        terrain="connecting_ridge", pad_standoff_km="1", autonomy_model="driving-v1",
        landing_model={"policy": "classical", "sigma_scale": 1.0, "pad_radius_m": 50.0, "failure_policy": "lose"},
        p5=p5)
