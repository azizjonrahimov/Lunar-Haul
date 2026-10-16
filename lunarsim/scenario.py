"""Scenario definitions: demand (landers and cargo), fleet, environment, economics.

Every number here is a default that experiments override. Sourcing is in
notes/02 and notes/04 and in the paper's parameter table.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple
import numpy as np

from .entities import VEHICLE_CLASSES

HOURS_PER_DAY = 24.0
LUNAR_CYCLE_H = 29.53 * HOURS_PER_DAY  # synodic month
RETURN_ITEM_PROB = 0.30                # share of outbound items that generate a return item
RETURN_LAG_H = (5 * 24, 30 * 24)       # days after delivery when the return item is ready


# Cargo classes: (label, mass range kg, destination weights, priority, share of items)
# Destination keys refer to world sites. Shares are per-item frequencies for a
# "build-out phase" manifest; the lander type scales how many items arrive.
CARGO_CLASSES = [
    # label, (min_kg, max_kg), dest_weights, priority, item_share
    ("consumables", (60, 400),   {"BASE": 0.8, "DEPOT": 0.2}, 1, 0.34),
    ("science",     (10, 150),   {"SCI_1": 0.5, "PSR": 0.3, "BASE": 0.2}, 2, 0.20),
    ("equipment",   (300, 2000), {"CONSTR": 0.4, "ISRU": 0.3, "POWER": 0.2, "BASE": 0.1}, 2, 0.26),
    ("infrastructure", (2000, 6000), {"POWER": 0.4, "ISRU": 0.3, "CONSTR": 0.3}, 2, 0.14),
    ("element",     (6000, 15000), {"BASE": 0.6, "POWER": 0.4}, 3, 0.06),
]


@dataclass
class LanderType:
    name: str
    payload_kg: Tuple[float, float]   # total cargo mass range per landing
    offload_h: Tuple[float, float]    # hours between touchdown and first item ready
    self_offload: bool                # lander has its own crane/ramp
    max_item_kg: float                # largest single item this lander can carry


LANDER_TYPES = {
    # CLPS-class (Firefly Blue Ghost, IM Nova-C, Astrobotic Griffin): ~0.1–0.5 t
    "CLPS": LanderType("CLPS", (100, 500), (6, 24), True, 500),
    # Blue Moon MK1 class: ~3 t to the surface
    "MK1": LanderType("MK1", (2000, 3000), (12, 36), True, 2000),
    # Large cargo lander (Starship HLS cargo / Blue Moon MK2 cargo): tens of tonnes
    "LARGE": LanderType("LARGE", (12000, 30000), (24, 72), True, 15000),
}


@dataclass
class BulkFlow:
    """A recurring surface flow released in fixed lots (e.g. regolith bins)."""
    origin: str
    dest: str
    tonnes_per_year: float
    lot_kg: float = 1000.0
    owner: str = "NASA"
    priority: int = 3
    start_h: float = 0.0


@dataclass
class Scenario:
    name: str = "base"
    horizon_h: float = 365 * HOURS_PER_DAY
    # demand: list of (lander_type, landings per year)
    landings_per_year: Dict[str, float] = field(default_factory=lambda: {"CLPS": 4, "MK1": 2, "LARGE": 0})
    cargo_owners: List[str] = field(default_factory=lambda: ["NASA", "NASA", "NASA", "CoA", "CoB"])
    bulk_flows: List["BulkFlow"] = field(default_factory=list)
    # fleet: list of (owner, class, autonomy, standards)
    fleet: List[Tuple[str, str, str, str]] = field(default_factory=lambda: [
        ("NASA", "LTV", "supervised", "A"),
        ("CoA", "LTV", "supervised", "A"),
        ("CoB", "MICRO", "teleop", "A"),
    ])
    # environment
    night_fraction: float = 0.15        # dark share of each cycle (Shackleton rim ~90-94% lit; 120+ h darkness design target)
    night_speed_mult: float = 0.6       # speed of night-capable vehicles in the dark
    one_way_latency_s: float = 1.3      # Earth-Moon one-way light time
    ground_delay_s: float = 2.4         # extra round-trip delay from relays/ground processing (NASA: up to ~10 s one-way worst case)
    n_operators: int = 2                # Earth operators available at any time
    supervised_fanout: int = 4          # vehicles per operator under supervised autonomy
    failures: bool = True
    mtbf_mult: float = 1.0              # scales every vehicle class's MTBF (robustness sweeps)
    # share of each vehicle's time committed to its owner's other work (crew drives,
    # science traverses, excavation) and therefore unavailable for cargo jobs
    other_duty_share: float = 0.3
    other_duty_block_h: float = 48.0
    # cargo standards: share of cargo that uses the common standard "A"
    common_standard_share: float = 1.0
    # economics (USD)
    operator_cost_per_h: float = 1000.0   # loaded cost of one console position incl. ground systems
    urgency_usd_per_h: float = 2000.0      # value of one hour of urgency credit in the auction
    # shipper's value of delivery time by priority class (USD per hour of completion time)
    vot_usd_per_h: Dict[int, float] = field(default_factory=lambda: {1: 5000.0, 2: 1000.0, 3: 100.0})
    delivered_value_per_kg: float = 1.0e6  # replacement cost of landed cargo (CLPS-era)
    seed: int = 0
    # Phase 3, all opt-in (None = v2 behaviour, byte-identical results); see lunarsim/phase3.py and PLAN §5.3-§5.5
    terrain: Optional[str] = None            # terrain pack id, e.g. "connecting_ridge" (site positions, LOS)
    pad_standoff_km: Optional[str] = None    # key into sites.json "pads" (default "1" when terrain is set)
    landing_model: Optional[dict] = None     # {policy, sigma_scale, pad_radius_m, failure_policy, dir}
    plume: Optional[dict] = None             # {keepout_km, standdown_h, shelter: "auto"}
    autonomy_model: Optional[str] = None     # "driving-v1" or a path to a lunarsim-driving table

    def with_(self, **kw) -> "Scenario":
        return replace(self, **kw)


def make_scenario(name: str = "base", **kw) -> Scenario:
    return Scenario(name=name, **kw)


# ---------------------------------------------------------------------------
# Demand generation
# ---------------------------------------------------------------------------

def sample_cargo_manifest(rng: np.random.Generator, lander: LanderType, owner_pool: List[str],
                          world_pads: List[str], t_land: float, common_share: float,
                          id_start: int, pad: Optional[str] = None):
    """Draw a manifest for one landing. Items are drawn by class share until the
    lander's payload mass is used up; items heavier than the lander can carry are
    re-drawn. The landing pad is given (it is part of the published schedule) or
    drawn here."""
    from .entities import Cargo
    total = rng.uniform(*lander.payload_kg)
    labels = [c[0] for c in CARGO_CLASSES]
    shares = np.array([c[4] for c in CARGO_CLASSES])
    shares = shares / shares.sum()
    if pad is None:
        pad = rng.choice(world_pads)
    items = []
    mass_so_far = 0.0
    cid = id_start
    guard = 0
    while mass_so_far < total and guard < 500:
        guard += 1
        k = rng.choice(len(labels), p=shares)
        label, (lo, hi), dests, prio, _ = CARGO_CLASSES[k]
        hi = min(hi, lander.max_item_kg)
        if hi <= lo:
            continue
        m = float(rng.uniform(lo, hi))
        if mass_so_far + m > total * 1.15:
            # fill the remaining mass with a smaller crate
            m = max(20.0, total - mass_so_far)
            label, prio, dests = "consumables", 1, {"BASE": 0.8, "DEPOT": 0.2}
        dest = rng.choice(list(dests.keys()), p=np.array(list(dests.values())) / sum(dests.values()))
        std = "A" if rng.random() < common_share else "B"
        owner = rng.choice(owner_pool)
        t_ready = t_land + rng.uniform(*lander.offload_h) + 0.25 * len(items)
        c = Cargo(cid, owner, m, pad, dest, t_land, t_ready, int(prio), std, label)
        # Return flow (trash, samples, empty containers) is drawn here so that it is
        # identical across mechanisms for a given seed (common random numbers).
        if rng.random() < RETURN_ITEM_PROB:
            c.return_mass_kg = max(10.0, m * rng.uniform(0.2, 0.6))
            c.return_lag_h = rng.uniform(*RETURN_LAG_H)
        items.append(c)
        cid += 1
        mass_so_far += m
    return items, cid


def sample_landings(rng: np.random.Generator, sc: Scenario, pads: List[str]) -> List[Tuple[float, LanderType, str]]:
    """Landing schedule: (time, lander type, pad). Each lander type arrives as a
    Poisson process with the given annual rate. The schedule is known to the
    dispatcher in advance (landings are published months ahead), which the
    anticipatory component of the marketplace uses.

    Draw order is canonical: lander types are drawn in LANDER_TYPES declaration order (CLPS, MK1, LARGE), never in
    the scenario dict's key order, so any key order in a scenario file gives the same year for the same seed. This
    equals the phases' insertion order, so v2 results are unchanged."""
    unknown = sorted(set(sc.landings_per_year) - set(LANDER_TYPES))
    if unknown:
        raise ValueError(f"unknown lander types in landings_per_year: {unknown}; known: {list(LANDER_TYPES)}")
    out = []
    years = sc.horizon_h / (365 * HOURS_PER_DAY)
    for lt_name in LANDER_TYPES:
        if lt_name not in sc.landings_per_year:
            continue
        rate = sc.landings_per_year[lt_name]
        n = rng.poisson(rate * years)
        times = np.sort(rng.uniform(0, sc.horizon_h, n))
        lt = LANDER_TYPES[lt_name]
        for t in times:
            out.append((float(t), lt, str(rng.choice(pads))))
    out.sort(key=lambda x: x[0])
    return out
