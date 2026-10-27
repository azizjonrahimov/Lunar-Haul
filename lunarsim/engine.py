"""Discrete-event engine.

Time is in hours. The engine owns the clock, the event heap, the cargo pool
and the fleet; a dispatch mechanism (see dispatch.py) is called whenever the
state changes (or at fixed ticks for batched mechanisms) and returns jobs.
The engine then prices each job's duration honestly: empty approach, loading,
loaded travel with slope and night factors, teleoperation slowdown, operator
availability, random faults, and a night hibernation penalty when a vehicle
that cannot work in the dark is caught out.
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from .entities import Cargo, Vehicle, VEHICLE_CLASSES
from .scenario import (Scenario, LUNAR_CYCLE_H, sample_landings, sample_cargo_manifest,
                       HOURS_PER_DAY)
from .world import World, build_default_world

# Teleoperation slowdown. NASA JSC LTV teleoperation trials (Litaker et al., NASA
# TM-20240001217) report average speeds of 3.24 / 2.56 / 2.03 / 1.76 km/h at 0 / 4 / 6 / 8 s
# round-trip latency. Inside the measured range we interpolate the table exactly; beyond
# 8 s we extrapolate with the move-and-wait law v = v8 (1 + 8 k) / (1 + k RTT), k = 1/T_move
# with a 10 s command segment, which reproduces Mars-rover command-cycle speeds of a few
# tens of metres per hour at 20-minute delays. Speeds are relative to the 6 km/h autonomous
# average assumed for a 10 km/h-class rover.
TELEOP_TABLE = ((0.0, 3.24), (4.0, 2.56), (6.0, 2.03), (8.0, 1.76))
TELEOP_K = 0.10
AUTONOMOUS_REF_KMH = 6.0
TELEOP_BASE_MULT = TELEOP_TABLE[0][1] / AUTONOMOUS_REF_KMH   # kept for backward compatibility
SUPERVISED_MULT = 0.9


def teleop_speed_kmh(rtt_s: float) -> float:
    """Average teleoperated driving speed as a function of round-trip latency."""
    xs = [p[0] for p in TELEOP_TABLE]
    ys = [p[1] for p in TELEOP_TABLE]
    if rtt_s <= xs[-1]:
        return float(np.interp(rtt_s, xs, ys))
    return ys[-1] * (1.0 + TELEOP_K * xs[-1]) / (1.0 + TELEOP_K * rtt_s)
# Manipulation under delay: completion time 139% at 1.5 s and 174% at 3 s RTT in the
# lunar-excavator teleoperation study (Seo, Gupta & Ham), i.e. about +25% per second.
TELEOP_HANDLING_K = 0.25
WEAR_SHARE = 0.5         # share of a vehicle's life consumption that is usage-driven (assumption)
TEAM_SPEED_MULT = 0.5    # a coupled team drives at half speed
TEAM_SETUP_H = 1.0       # hours to rendezvous and couple a team lift
# Phase 3 (used only when the opt-in Scenario fields are set; see lunarsim/phase3.py)
OFFPAD_SPEED_FACTOR = 0.5        # Assumed: rough unprepared ground between an off-pad lander and its pad
OFFPAD_ENERGY_FACTOR = 2.0       # Assumed
INTERVENTION_RECOVERY_S = 300.0  # Assumed, as lunarsim.rover.physics.INTERVENTION["recovery_s"]


@dataclass
class Job:
    vehicles: List[Vehicle]
    items: List[Cargo]              # outbound items (all share origin pad)
    route: List[str]                # destination sequence after the pad
    backhaul: List[Cargo] = field(default_factory=list)  # items picked at last stop, dest = pad
    note: str = ""


@dataclass
class Metrics:
    landed_kg: float = 0.0
    ready_kg: float = 0.0
    delivered_kg: float = 0.0
    delivered_items: int = 0
    delivered_tkm: float = 0.0
    delivered_nonbulk_kg: float = 0.0     # B-16: delivered landed cargo (not bulk surface flows, not return items)
    bulk_kg: float = 0.0
    stranded_kg: float = 0.0
    stranded_items: int = 0
    backlog_kg: float = 0.0
    delays_h: List[float] = field(default_factory=list)
    delay_mass: List[float] = field(default_factory=list)
    delay_prio: List[int] = field(default_factory=list)
    delay_cls: List[str] = field(default_factory=list)
    tonne_days_waiting: float = 0.0
    km_total: float = 0.0
    km_empty: float = 0.0
    energy_kwh: float = 0.0
    veh_hours_busy: float = 0.0
    veh_hours_avail: float = 0.0
    operator_hours: float = 0.0
    faults: int = 0
    night_strandings: int = 0
    team_lifts: int = 0
    bundled_jobs: int = 0
    backhaul_kg: float = 0.0
    jobs: int = 0
    revenue_by_owner: Dict[str, float] = field(default_factory=dict)
    fleet_cost_musd: float = 0.0
    operator_cost_musd: float = 0.0
    unmet_operator_waits: int = 0
    repositions: int = 0
    km_reposition: float = 0.0
    # Phase 3 (reported only when a Phase-3 Scenario field is set, so v2 summaries keep their keys)
    phase3: bool = False
    plume_standdowns: int = 0
    standdown_vehicle_h: float = 0.0       # = standdown_hold_h + standdown_drive_h
    standdown_hold_h: float = 0.0          # B-12e: jobs held at the boundary (vehicle-hours)
    standdown_drive_h: float = 0.0         # B-12e: evacuation and return drives (vehicle-hours)
    landing_misses_m: List[float] = field(default_factory=list)
    offpad_landings: int = 0
    failed_landings: int = 0
    cargo_lost_kg: float = 0.0
    km_offpad_extra: float = 0.0
    interventions: int = 0
    intervention_h: float = 0.0
    prop_residual_kg: List[float] = field(default_factory=list)
    comms: Optional[object] = None          # Phase 4: the CommsModel when Scenario.comms is set (adds its columns)
    cargo: Optional[object] = None          # B-48: the run's cargo list, for the comms outcome metrics

    def summary(self) -> Dict[str, float]:
        d = np.array(self.delays_h) if self.delays_h else np.array([np.nan])
        m = np.array(self.delay_mass) if self.delay_mass else np.array([1.0])
        pr = np.array(self.delay_prio) if self.delay_prio else np.array([0])
        p1 = d[pr == 1] if (pr == 1).any() else np.array([np.nan])
        total_cost = self.fleet_cost_musd + self.operator_cost_musd
        rev = np.array(list(self.revenue_by_owner.values())) if self.revenue_by_owner else np.array([0.0])
        gini = _gini(rev)
        out = {}
        cls_arr = np.array(self.delay_cls) if self.delay_cls else np.array([""])
        for lab in ("consumables", "science", "equipment", "infrastructure", "element", "bulk", "return"):
            sel = d[cls_arr == lab] if (cls_arr == lab).any() else np.array([np.nan])
            out[f"delay_mean_{lab}"] = float(np.nanmean(sel))
            out[f"delay_p90_{lab}"] = float(np.nanpercentile(sel, 90)) if not np.isnan(sel).all() else np.nan
        p2 = d[pr == 2] if (pr == 2).any() else np.array([np.nan])
        out["delay_prio2_mean_h"] = float(np.nanmean(p2))
        out["delay_prio1_p90_h"] = float(np.nanpercentile(p1, 90)) if not np.isnan(p1).all() else np.nan
        out["sl24_prio1"] = float(np.mean(p1 <= 24.0)) if not np.isnan(p1).all() else np.nan
        out["sl48_prio12"] = float(np.mean(d[pr <= 2] <= 48.0)) if (pr <= 2).any() else np.nan
        out.update({
            "landed_kg": self.landed_kg,
            "ready_kg": self.ready_kg,
            "delivered_kg": self.delivered_kg,
            "delivered_items": self.delivered_items,
            "delivered_share": self.delivered_kg / max(self.ready_kg, 1e-9),
            "stranded_kg": self.stranded_kg,
            "stranded_share": self.stranded_kg / max(self.ready_kg, 1e-9),
            "backlog_kg": self.backlog_kg,
            "delay_mean_h": float(np.nanmean(d)),
            "delay_median_h": float(np.nanmedian(d)),
            "delay_p90_h": float(np.nanpercentile(d, 90)) if len(d) and not np.isnan(d).all() else np.nan,
            "delay_mass_weighted_h": float(np.nansum(d * m) / max(np.nansum(m), 1e-9)),
            "delay_prio1_mean_h": float(np.nanmean(p1)),
            "tonne_days_waiting": self.tonne_days_waiting,
            "km_total": self.km_total,
            "km_empty": self.km_empty,
            "empty_km_share": self.km_empty / max(self.km_total, 1e-9),
            "energy_kwh": self.energy_kwh,
            "utilisation": self.veh_hours_busy / max(self.veh_hours_avail, 1e-9),
            "operator_hours": self.operator_hours,
            "faults": self.faults,
            "night_strandings": self.night_strandings,
            "team_lifts": self.team_lifts,
            "bundled_jobs": self.bundled_jobs,
            "backhaul_kg": self.backhaul_kg,
            "jobs": self.jobs,
            "fleet_cost_musd": self.fleet_cost_musd,
            "operator_cost_musd": self.operator_cost_musd,
            "cost_per_kg_usd": 1e6 * total_cost / max(self.delivered_kg, 1e-9),
            "cost_per_tkm_usd": 1e6 * total_cost / max(self.delivered_tkm, 1e-9),
            "delivered_tkm": self.delivered_tkm,
            "bulk_kg": self.bulk_kg,
            "revenue_gini": gini,
            "unmet_operator_waits": self.unmet_operator_waits,
            "repositions": self.repositions,
            "km_reposition": self.km_reposition,
            # B-16 (appended after the v2 columns): cost per kilogram of LANDED cargo delivered, i.e. bulk surface
            # flows and return items excluded from the denominator
            "delivered_nonbulk_kg": self.delivered_nonbulk_kg,
            "cost_per_landed_kg_usd": 1e6 * total_cost / self.delivered_nonbulk_kg if self.delivered_nonbulk_kg > 0 else np.nan,
        })
        if self.phase3:
            out.update({
                "plume_standdowns": self.plume_standdowns,
                "standdown_vehicle_h": self.standdown_vehicle_h,
                "standdown_hold_h": self.standdown_hold_h,
                "standdown_drive_h": self.standdown_drive_h,
                "landing_miss_m_mean": float(np.mean(self.landing_misses_m)) if self.landing_misses_m else np.nan,
                "offpad_landings": self.offpad_landings,
                "failed_landings": self.failed_landings,
                "cargo_lost_kg": self.cargo_lost_kg,
                "km_offpad_extra": self.km_offpad_extra,
                "interventions": self.interventions,
                "intervention_h": self.intervention_h,
                "prop_residual_kg_mean": float(np.mean(self.prop_residual_kg)) if self.prop_residual_kg else np.nan,
            })
        if self.comms is not None:
            out.update(self.comms.summary(self.cargo))
        return out


def _gini(x: np.ndarray) -> float:
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() <= 0:
        return 0.0
    cum = np.cumsum(x)
    return float((n + 1 - 2 * np.sum(cum) / cum[-1]) / n)


class Simulation:
    def __init__(self, sc: Scenario, mechanism: Callable, world: Optional[World] = None,
                 seed: Optional[int] = None, mech_kwargs: Optional[dict] = None):
        self.sc = sc
        self.world = world or build_default_world()
        s = sc.seed if seed is None else seed
        self.seed = s                                   # recorded for trace_export(); not used by the engine
        self.rng = np.random.default_rng(s)            # demand stream (common random numbers)
        self.rng_ops = np.random.default_rng(s + 100_003)  # operations stream (faults)
        self.mechanism = mechanism
        self.mech_kwargs = mech_kwargs or {}
        self.t = 0.0
        self.events: List[Tuple[float, int, str, object]] = []
        self._seq = 0
        self.waiting: List[Cargo] = []        # ready, not yet picked up
        self.pending: List[Cargo] = []        # landed, not yet offloaded
        self.all_cargo: List[Cargo] = []
        self.vehicles: List[Vehicle] = []
        self.metrics = Metrics()
        self.rtt_s = 2 * sc.one_way_latency_s + sc.ground_delay_s
        self.op_jobs: List[Tuple[float, float]] = []  # (end_time, operator demand)
        self.carrier_of: Dict[str, str] = {}
        self._cid = 0
        self.record_trace = bool(self.mech_kwargs.pop("trace", False))
        self.trace: List[dict] = []            # per-job movement records for the live viewer
        self.landing_schedule: List[Tuple[float, object, str]] = []
        self.repositions = 0
        self.km_reposition = 0.0
        self._last_segments: Dict[int, list] = {}
        self.p3 = any(getattr(sc, k, None) is not None
                      for k in ("terrain", "pad_standoff_km", "landing_model", "plume", "autonomy_model"))
        self.sites = self.drive = self.landing = self.plume = None
        self.p3_landings: List[dict] = []
        self._last_interventions = 0
        self._last_segk: Dict[int, list] = {}  # per segment intervention counts of the last plan (driving tables)
        if self.p3:
            self._init_phase3()
        self.comms = None
        if sc.comms is not None:            # Phase 4 (R-1): opt-in Earth-link rules; own random streams
            from .comms import CommsModel
            from .phase3 import _find
            standoff = str(sc.pad_standoff_km) if sc.pad_standoff_km is not None else "1"
            self.comms = CommsModel(sc.comms, standoff, s, sc.horizon_h, self.world.pads, find=_find)
            self.comms.set_leg_km(self.world.distance_km)
            self.metrics.comms = self.comms
            self.metrics.cargo = self.all_cargo
        self.illum = None
        if sc.illumination is not None:     # Phase 4 (B-44): opt-in real sun per site and leg; see lunarsim/illumination.py
            from .illumination import Illumination
            from .phase3 import _find
            standoff = str(sc.pad_standoff_km) if sc.pad_standoff_km is not None else "1"
            cy = int(sc.comms["start_year"]) if sc.comms and "start_year" in sc.comms else None
            self.illum = Illumination(sc.illumination, standoff, sc.horizon_h, self.world.pads, comms_start_year=cy,
                                      find=_find)
        self._build_fleet()
        self.p5 = None
        if sc.p5 is not None:               # Phase 5 (B-71), opt-in: real vehicle classes, reach, team share, hoppers
            from .atc.p5 import P5State
            self.p5 = P5State(self)
        self._schedule_demand()
        self.batch_h = self.mech_kwargs.get("batch_h", 0.0)
        if self.batch_h > 0:
            self._push(self.batch_h, "TICK", None)

    # ------------------------------------------------------------------ setup
    def _init_phase3(self):
        """Opt-in Phase-3 models (lunarsim/phase3.py). Never called when every Phase-3 field is None."""
        from . import phase3 as P3
        sc = self.sc
        self.metrics.phase3 = True
        standoff = str(sc.pad_standoff_km) if sc.pad_standoff_km is not None else "1"
        self.sites = P3.SiteMap(self.world, sc.terrain, standoff)
        if sc.autonomy_model is not None:
            self.drive = P3.DrivingModel(sc.autonomy_model, standoff, VEHICLE_CLASSES)
        if sc.landing_model is not None:
            self.landing = P3.LandingModel(sc.landing_model)
        if sc.plume is not None:
            self.plume = P3.PlumeModel(sc.plume, self.sites, self.world)

    def _build_fleet(self):
        owners_with_fleet = []
        fleet = list(self.sc.fleet)
        hp = self.comms.helpers if self.comms is not None else None
        if hp is not None and hp["from_fleet"]:     # B-62: the helpers leave the hauling fleet (last ones of their class)
            idx = [i for i, f in enumerate(fleet) if f[1] == hp["class"]]
            if len(idx) < hp["n"]:
                raise ValueError(f"comms helpers from_fleet: the fleet has {len(idx)} {hp['class']} vehicles, needs {hp['n']}")
            drop = set(idx[-hp["n"]:])
            fleet = [f for i, f in enumerate(fleet) if i not in drop]
        for i, (owner, cls, autonomy, stds) in enumerate(fleet):
            v = Vehicle(i, owner, self._vclass(cls), "DEPOT", set(stds.split("|")), autonomy)
            v.next_fault_h = self.rng_ops.exponential(v.cls.mtbf_h * self.sc.mtbf_mult)
            self.vehicles.append(v)
            owners_with_fleet.append(owner)
        # Bilateral contracting (status quo): each cargo owner is served by one carrier.
        # Owners with their own fleet use it; others are assigned round-robin to a carrier.
        carriers = sorted(set(owners_with_fleet))
        k = 0
        owners = list(self.sc.cargo_owners) + [bf.owner for bf in self.sc.bulk_flows]
        for o in sorted(set(owners)):
            if o in carriers:
                self.carrier_of[o] = o
            else:
                self.carrier_of[o] = carriers[k % len(carriers)]
                k += 1

    def _vclass(self, cls: str):
        """VEHICLE_CLASSES first; then the Phase 5 table (lunarsim/atc/vehicles-p5.json, with the scenario's sweeps)."""
        if cls in VEHICLE_CLASSES:
            return VEHICLE_CLASSES[cls]
        from .atc import p5 as P5
        return P5.vehicle_class(cls, self.sc)

    def _fly_km(self, a: str, b: str) -> float:
        """Straight-line km between two sites (a hopper's flight)."""
        if self.sites is not None:
            (xa, ya), (xb, yb) = self.sites.xy_km[a], self.sites.xy_km[b]
            return math.hypot(xb - xa, yb - ya)
        return self.world._euclid(a, b)

    def _leg_km(self, v: Vehicle, a: str, b: str) -> float:
        return self._fly_km(a, b) if getattr(v.cls, "flies", False) else self.world.distance_km(a, b)

    def _schedule_demand(self):
        self.landing_schedule = sample_landings(self.rng, self.sc, self.world.pads)
        for t_land, lt, pad in self.landing_schedule:
            self._push(t_land, "LANDING", (lt, pad))
            if self.plume is not None:
                self.plume.add(t_land, pad)
                self._push(max(0.0, t_land - self.plume.T), "PLUME", pad)
                if self.plume.return_after:
                    self._push(t_land + self.plume.T, "PLUME_END", pad)
            # a wake-up before each landing lets anticipatory mechanisms stage a vehicle
            self._push(max(0.0, t_land - 48.0), "WAKE", None)
            self._push(max(0.0, t_land - 12.0), "WAKE", None)
        # owner's other duties: random blocks during which a vehicle is not for hire
        if self.sc.other_duty_share > 0:
            for v in self.vehicles:
                t = self.rng_ops.exponential(self.sc.other_duty_block_h * (1 - self.sc.other_duty_share) / self.sc.other_duty_share)
                while t < self.sc.horizon_h:
                    self._push(t, "DUTY", v)
                    t += self.sc.other_duty_block_h + self.rng_ops.exponential(
                        self.sc.other_duty_block_h * (1 - self.sc.other_duty_share) / self.sc.other_duty_share)
        # wake up at the end of every lunar night so parked vehicles get dispatched
        if self.illum is not None:
            for t in self.illum.light_returns(list(self.world.sites), self.sc.horizon_h):
                self._push(t + 1e-6, "NIGHT_END", None)
        elif self.sc.night_fraction > 0:
            t = self.night_end(0.0)
            while t < self.sc.horizon_h:
                self._push(t + 1e-6, "NIGHT_END", None)
                t += LUNAR_CYCLE_H
        # recurring surface flows (regolith for shielding/berms, ISRU feedstock, ice)
        for bf in self.sc.bulk_flows:
            n_lots = int(round(bf.tonnes_per_year * 1000.0 / bf.lot_kg * self.sc.horizon_h / (365 * HOURS_PER_DAY)))
            if n_lots <= 0:
                continue
            # lots are released evenly in time with jitter; items are tagged "bulk"
            base_times = np.linspace(bf.start_h, self.sc.horizon_h, n_lots, endpoint=False)
            jitter = self.rng.uniform(-0.5, 0.5, n_lots) * (self.sc.horizon_h - bf.start_h) / n_lots
            for t_r in np.sort(base_times + jitter):
                self._cid += 1
                c = Cargo(self._cid, bf.owner, bf.lot_kg, bf.origin, bf.dest, float(t_r), float(t_r),
                          bf.priority, "A", "bulk")
                self._push(float(t_r), "BULK", c)

    def _push(self, t: float, kind: str, payload):
        self._seq += 1
        heapq.heappush(self.events, (t, self._seq, kind, payload))

    # ----------------------------------------------------------- environment
    def is_night(self, t: float) -> bool:
        phase = (t % LUNAR_CYCLE_H) / LUNAR_CYCLE_H
        return phase >= (1.0 - self.sc.night_fraction)

    def next_night_start(self, t: float) -> float:
        cyc = math.floor(t / LUNAR_CYCLE_H)
        start = (cyc + 1.0 - self.sc.night_fraction) * LUNAR_CYCLE_H
        if start <= t:
            start += LUNAR_CYCLE_H
        return start

    def night_end(self, t: float) -> float:
        """End of the night that contains t, or of the next night if t is in daylight."""
        if self.sc.night_fraction <= 0:
            return float("inf")
        if self.is_night(t):
            return (math.floor(t / LUNAR_CYCLE_H) + 1) * LUNAR_CYCLE_H
        return self.next_night_start(t) + self.sc.night_fraction * LUNAR_CYCLE_H

    def dark(self, t: float, a: Optional[str] = None, b: Optional[str] = None) -> bool:
        """Dark for a vehicle at site a (or on leg a -> b) at t: Scenario.illumination when set, else the v2 night."""
        if self.illum is None or a is None:
            return self.is_night(t)
        return self.illum.dark(t, a, b)

    def next_dark(self, t: float, a: Optional[str] = None, b: Optional[str] = None) -> float:
        """When the dark next catches a vehicle at a / on a -> b (t if dark now); v2: the next night start."""
        if self.illum is None or a is None:
            return self.next_night_start(t)
        return self.illum.next_dark(t, a, b)

    def autonomy_speed_mult(self, v: Vehicle) -> float:
        if v.autonomy == "teleop":
            return teleop_speed_kmh(self.rtt_s) / AUTONOMOUS_REF_KMH
        if v.autonomy == "supervised":
            return SUPERVISED_MULT
        return 1.0

    def handling_mult(self, v: Vehicle) -> float:
        """Load/unload time multiplier for remotely operated manipulation."""
        if v.autonomy == "teleop":
            return 1.0 + TELEOP_HANDLING_K * self.rtt_s
        if v.autonomy == "supervised":
            return 1.1
        return 1.0

    def operator_demand(self, v: Vehicle) -> float:
        if v.autonomy == "teleop":
            return 1.0
        if v.autonomy == "supervised":
            return 1.0 / self.sc.supervised_fanout
        return 0.05  # autonomous vehicles still need occasional attention

    # ------------------------------------------------------------- job maths
    def travel_h(self, v: Vehicle, a: str, b: str, loaded: bool, team: bool, t: float) -> float:
        if getattr(v.cls, "flies", False):          # Phase 5 hoppers: straight-line hops, no roads or driving tables
            return self._fly_km(a, b) / max(v.cls.speed_kmh, 1e-6)
        if self.drive is not None:
            leg = self._p3_leg(v, a, b, loaded, team, t, False)
            if leg is not None:
                return leg[0]
        eq = self.world.equiv_flat_km(a, b)
        speed = v.cls.speed_kmh * (1.0 if loaded else v.cls.empty_speed_mult)
        speed *= self.autonomy_speed_mult(v)
        if team:
            speed *= TEAM_SPEED_MULT
        if self.dark(t, a, b) and v.cls.night_ops:
            speed *= self.sc.night_speed_mult
        return eq / max(speed, 1e-6)

    def _p3_leg(self, v: Vehicle, a: str, b: str, loaded: bool, team: bool, t: float, realize: bool):
        """(hours, energy_wh, km, interventions) of one leg from the driving tables, or None if the table lacks
        the leg (the caller then uses the v2 model). Planning (realize=False) uses the lognormal means and no
        interventions; a committed job (realize=True) draws time, energy and interventions from the ops stream."""
        if a == b:
            return 0.0, 0.0, 0.0, 0
        if getattr(v.cls, "flies", False):
            km = self._fly_km(a, b)
            return km / max(v.cls.speed_kmh, 1e-6), 0.0, km, 0
        light = self.drive.light_bin(t, self.dark(t, a, b) if self.illum is not None
                                     else (self.sc.night_fraction > 0 and self.is_night(t)))
        e = self.drive.entry(a, b, self.world.pads, v.autonomy, self.drive.rtt_bin(self.rtt_s), light)
        if e is None:
            return None
        f = self.drive.ref_speed / v.cls.speed_kmh
        if not loaded:
            f /= v.cls.empty_speed_mult
        if team:
            f /= TEAM_SPEED_MULT
        we = v.cls.energy_wh_per_km / self.drive.table_wh_per_km
        if not realize:
            return e["mean_h"] * f, e["mean_kwh"] * 1000.0 * we, e["km"], 0
        h = float(self.rng_ops.lognormal(e["mu_t"], e["s_t"])) * f
        k = int(self.rng_ops.poisson(e["lam"]))
        h += k * (self.rtt_s + INTERVENTION_RECOVERY_S) / 3600.0
        return h, float(self.rng_ops.lognormal(e["mu_e"], e["s_e"])) * 1000.0 * we, e["km"], k

    def _offpad_km(self, job: Job) -> float:
        return max((getattr(c, "offpad_km", 0.0) for c in job.items), default=0.0)

    def _job_plan_p3(self, job: Job, t_start: float, realize: bool) -> Tuple[float, float, float, float, bool]:
        """job_plan with terrain legs from the driving tables (same structure and load factors as v2)."""
        team = len(job.vehicles) > 1
        pad = job.items[0].origin if job.items else job.backhaul[0].origin
        dur_max = 0.0
        km_sum = km_empty_sum = e_sum = 0.0
        self._last_segments = {}
        self._last_segk = {}
        self._last_interventions = 0
        off = self._offpad_km(job) if self.landing is not None else 0.0

        def leg(v, a, b, loaded, tm, t):
            r = self._p3_leg(v, a, b, loaded, tm, t, realize)
            if r is None:                                   # leg missing from the table: v2 model
                h = self.travel_h(v, a, b, loaded, tm, t) if self.drive is None else self._v2_travel_h(v, a, b, loaded, tm, t)
                return h, self.world.energy_km(a, b) * v.cls.energy_wh_per_km, self.world.distance_km(a, b), 0
            return r

        for v in job.vehicles:
            t = t_start
            segs = []
            segk = []                                          # interventions per segment (Phase 4 comms)
            h, e, d0, k = leg(v, v.location, pad, False, False, t)
            self._last_interventions += k
            segs.append([v.location, pad, t, t + h, 0.0])
            segk.append(k)
            t += h
            if off > 0:
                h_off = 2.0 * off / max(v.cls.speed_kmh * self.autonomy_speed_mult(v) * OFFPAD_SPEED_FACTOR, 1e-6)
                segs.append([pad, pad, t, t + h_off, 0.0])
                segk.append(0)
                t += h_off
                e += 2.0 * off * v.cls.energy_wh_per_km * OFFPAD_ENERGY_FACTOR
                d0 += 2.0 * off
            if team:
                t += TEAM_SETUP_H
            hm = self.handling_mult(v)
            t_load = v.cls.load_h * hm * max(1, len(job.items))
            segs.append([pad, pad, t, t + t_load, 0.0])
            segk.append(0)
            t += t_load
            prev = pad
            km = d0
            load_kg = sum(c.mass_kg for c in job.items) / len(job.vehicles)
            onboard = load_kg
            for stop in job.route:
                h, el, dk, k = leg(v, prev, stop, True, team, t)
                self._last_interventions += k
                segs.append([prev, stop, t, t + h, onboard])
                segk.append(k)
                t += h
                e += el * (1.0 + 0.6 * load_kg / max(v.cls.capacity_kg, 1))
                t_un = v.cls.unload_h * hm * sum(1 for c in job.items if c.dest == stop)
                segs.append([stop, stop, t, t + t_un, onboard])
                segk.append(0)
                t += t_un
                onboard -= sum(c.mass_kg for c in job.items if c.dest == stop) / len(job.vehicles)
                km += dk
                prev = stop
            if job.backhaul:
                t_l = v.cls.load_h * hm * len(job.backhaul)
                segs.append([prev, prev, t, t + t_l, 0.0])
                segk.append(0)
                t += t_l
                dest = job.backhaul[0].dest
                h, el, dk, k = leg(v, prev, dest, True, False, t)
                self._last_interventions += k
                bh_kg = sum(c.mass_kg for c in job.backhaul)
                segs.append([prev, dest, t, t + h, bh_kg])
                segk.append(k)
                t += h
                e += el * 1.3
                t_un = v.cls.unload_h * hm * len(job.backhaul)
                segs.append([dest, dest, t, t + t_un, bh_kg])
                segk.append(0)
                t += t_un
                km += dk
                prev = dest
            dur_max = max(dur_max, t - t_start)
            km_sum += km
            km_empty_sum += d0
            e_sum += e
            self._last_segments[v.id] = segs
            self._last_segk[v.id] = segk
        return dur_max, km_sum, km_empty_sum, e_sum, False

    def _v2_travel_h(self, v, a, b, loaded, team, t):
        eq = self.world.equiv_flat_km(a, b)
        speed = v.cls.speed_kmh * (1.0 if loaded else v.cls.empty_speed_mult)
        speed *= self.autonomy_speed_mult(v)
        if team:
            speed *= TEAM_SPEED_MULT
        if self.dark(t, a, b) and v.cls.night_ops:
            speed *= self.sc.night_speed_mult
        return eq / max(speed, 1e-6)

    def job_plan(self, job: Job, t_start: float, realize: bool = False) -> Tuple[float, float, float, float, bool]:
        """_job_plan, with the Earth-link waits of Scenario.comms inserted when that rule is on (Phase 4);
        the duration is inf when a needed link never comes."""
        if self.comms is not None and self.comms.active:
            r = self.comms.plan(self, job, t_start, realize)
        else:
            r = self._job_plan(job, t_start, realize)
        if self.p5 is not None and math.isfinite(r[0]) and not self.p5.job_ok(job, t_start, r[0], r[1]):
            return (math.inf,) + tuple(r[1:])     # Phase 5: beyond a hopper's km budget or active window
        return r

    def _job_plan(self, job: Job, t_start: float, realize: bool = False) -> Tuple[float, float, float, float, bool]:
        """Return (duration_h, km, km_empty, energy_wh, needs_night) for the job
        if it starts at t_start. Duration is the slowest vehicle's duration.
        Does not include operator waits, faults, or night hibernation.
        realize=True (committed jobs, Phase-3 driving tables only) draws the random leg outcomes."""
        if self.drive is not None:
            return self._job_plan_p3(job, t_start, realize)
        off = self._offpad_km(job) if self.landing is not None else 0.0
        team = len(job.vehicles) > 1
        pad = job.items[0].origin if job.items else job.backhaul[0].origin
        dur_max = 0.0
        km_sum = km_empty_sum = e_sum = 0.0
        self._last_segments = {}
        for v in job.vehicles:
            t = t_start
            segs = []
            # empty approach
            d0 = self._leg_km(v, v.location, pad)
            h = self.travel_h(v, v.location, pad, False, False, t)
            e = self.world.energy_km(v.location, pad) * v.cls.energy_wh_per_km
            segs.append([v.location, pad, t, t + h, 0.0])
            t += h
            if off > 0:                     # Phase 3: fetch cargo from an off-pad lander (not reached in v2)
                h_off = 2.0 * off / max(v.cls.speed_kmh * self.autonomy_speed_mult(v) * OFFPAD_SPEED_FACTOR, 1e-6)
                segs.append([pad, pad, t, t + h_off, 0.0])
                t += h_off
                e += 2.0 * off * v.cls.energy_wh_per_km * OFFPAD_ENERGY_FACTOR
                d0 += 2.0 * off
            if team:
                t += TEAM_SETUP_H
            # loading
            hm = self.handling_mult(v)
            t_load = v.cls.load_h * hm * max(1, len(job.items))
            segs.append([pad, pad, t, t + t_load, 0.0])
            t += t_load
            # loaded legs
            prev = pad
            km = d0
            load_kg = sum(c.mass_kg for c in job.items) / len(job.vehicles)
            onboard = load_kg
            for stop in job.route:
                dk = self._leg_km(v, prev, stop)
                h = self.travel_h(v, prev, stop, True, team, t)
                segs.append([prev, stop, t, t + h, onboard])
                t += h
                e += self.world.energy_km(prev, stop) * v.cls.energy_wh_per_km * (1.0 + 0.6 * load_kg / max(v.cls.capacity_kg, 1))
                t_un = v.cls.unload_h * hm * sum(1 for c in job.items if c.dest == stop)
                segs.append([stop, stop, t, t + t_un, onboard])
                t += t_un
                onboard -= sum(c.mass_kg for c in job.items if c.dest == stop) / len(job.vehicles)
                km += dk
                prev = stop
            if job.backhaul:
                t_l = v.cls.load_h * hm * len(job.backhaul)
                segs.append([prev, prev, t, t + t_l, 0.0])
                t += t_l
                dest = job.backhaul[0].dest
                dk = self._leg_km(v, prev, dest)
                h = self.travel_h(v, prev, dest, True, False, t)
                bh_kg = sum(c.mass_kg for c in job.backhaul)
                segs.append([prev, dest, t, t + h, bh_kg])
                t += h
                e += self.world.energy_km(prev, dest) * v.cls.energy_wh_per_km * 1.3
                t_un = v.cls.unload_h * hm * len(job.backhaul)
                segs.append([dest, dest, t, t + t_un, bh_kg])
                t += t_un
                km += dk
                prev = dest
            dur = t - t_start
            dur_max = max(dur_max, dur)
            km_sum += km
            km_empty_sum += d0
            e_sum += e
            self._last_segments[v.id] = segs
        return dur_max, km_sum, km_empty_sum, e_sum, False

    def job_cost_usd(self, job: Job, dur_h: float) -> float:
        """Variable cost of a job as a carrier would price it: usage-driven wear
        (a share of the vehicle's per-operating-hour cost) plus operator time."""
        c = 0.0
        for v in job.vehicles:
            c += dur_h * WEAR_SHARE * (v.cls.unit_cost_musd * 1e6 / v.cls.life_hours)
            c += dur_h * self.operator_demand(v) * self.sc.operator_cost_per_h
        return c

    def hours_until_vehicle_free(self, v: Vehicle) -> float:
        return max(0.0, v.busy_until - self.t)

    def _start_duty(self, v: Vehicle):
        v.duty_pending = False
        v.busy_until = self.t + self.sc.other_duty_block_h
        v.hours_duty += self.sc.other_duty_block_h
        self._push(v.busy_until, "FREE", None)

    def free_vehicles(self) -> List[Vehicle]:
        out = []
        for v in self.vehicles:
            if not v.alive or v.busy_until > self.t + 1e-9:
                continue
            if self.p5 is not None and not self.p5.check_window(v, self.t):
                continue
            if v.duty_pending:
                self._start_duty(v)
                continue
            if self.dark(self.t, v.location) and not v.cls.night_ops:
                continue
            out.append(v)
        return out

    def operators_available(self) -> float:
        if self.comms is not None and self.comms.active:      # Phase 4: only demand linked right now counts
            return self.sc.n_operators - self.comms.demand_at(self.t)
        self.op_jobs = [(e, d) for (e, d) in self.op_jobs if e > self.t]
        return self.sc.n_operators - sum(d for _, d in self.op_jobs)

    # ---------------------------------------------------------------- events
    def run(self) -> Dict[str, float]:
        H = self.sc.horizon_h
        while self.events:
            t, _, kind, payload = heapq.heappop(self.events)
            if t > H:
                break
            self._advance_to(t)
            if kind == "LANDING":
                self._landing(*payload)
            elif kind == "READY":
                c: Cargo = payload
                self.pending.remove(c)
                self.waiting.append(c)
                self.metrics.ready_kg += c.mass_kg
            elif kind == "FREE":
                pass  # vehicle state already updated; dispatch below
            elif kind == "TICK":
                self._push(t + self.batch_h, "TICK", None)
            elif kind == "NIGHT_END":
                pass
            elif kind == "WAKE":
                pass
            elif kind == "REPOS":
                v, pad = payload
                v.repos_target = None
                started = False
                if (v.busy_until <= self.t and not v.duty_pending and v.location != pad
                        and not (self.dark(self.t, v.location) and not v.cls.night_ops)):
                    started = self._reposition(v, pad)
                if not started:
                    continue
            elif kind == "PLUME":
                self._plume_start(payload)
            elif kind == "PLUME_END":
                self._plume_end(payload)
            elif kind == "DUTY":
                v: Vehicle = payload
                if v.busy_until <= self.t:          # idle: the duty block starts now
                    self._start_duty(v)
                else:                               # busy: it starts the moment the job ends
                    v.duty_pending = True
                continue
            elif kind == "BULK":
                c: Cargo = payload
                self.all_cargo.append(c)
                self.waiting.append(c)
                self.metrics.ready_kg += c.mass_kg
                self.metrics.bulk_kg += c.mass_kg
                self._mark_stranded([c])
            if self.batch_h > 0 and kind != "TICK":
                continue
            self._dispatch()
        self._advance_to(H)
        self._finalise()
        out = self.metrics.summary()
        if self.p5 is not None:
            out.update(self.p5.summary())
        return out

    def _advance_to(self, t: float):
        # accumulate waiting tonne-days
        dt = t - self.t
        if dt > 0:
            kg = sum(c.mass_kg for c in self.waiting if not c.stranded)
            self.metrics.tonne_days_waiting += kg / 1000.0 * dt / HOURS_PER_DAY
            # vehicles idle recharge
            for v in self.vehicles:
                if v.busy_until <= self.t:
                    v.battery_wh = min(v.cls.battery_wh, v.battery_wh + v.cls.charge_kw * 1000 * dt)
        self.t = t

    def _landing(self, lt, pad):
        items, self._cid = sample_cargo_manifest(self.rng, lt, self.sc.cargo_owners,
                                                 self.world.pads, self.t,
                                                 self.sc.common_standard_share, self._cid, pad=pad)
        if self.p5 is not None:             # Phase 5: heavy-lift list, team-share re-draw
            items = self.p5.on_landing(items)
        if self.p3:
            self._landing_p3(lt, pad, items)
            return
        for c in items:
            self.all_cargo.append(c)
            self.pending.append(c)
            self.metrics.landed_kg += c.mass_kg
            self._push(c.t_ready, "READY", c)
        self._mark_stranded(items)

    def _landing_p3(self, lt, pad, items: List[Cargo]):
        """Landing with the Phase-3 outcome model: miss offset, off-pad fetch distance, failed landings."""
        m = self.metrics
        rec = self.landing.sample(lt.name, self.rng_ops) if self.landing is not None else None
        px, py = self.sites.xy_km[pad]
        miss = rec["miss_m"] if rec else [0.0, 0.0]
        out = {"t": self.t, "type": lt.name, "pad": pad, "xy_m": [1000.0 * px + miss[0], 1000.0 * py + miss[1]],
               "miss_m": [round(miss[0], 3), round(miss[1], 3)], "tilt_deg": rec["tilt_deg"] if rec else None,
               "ok": rec["ok"] if rec else True, "failure_kind": rec["failure_kind"] if rec else None,
               "cargo_kg": round(sum(c.mass_kg for c in items), 1)}
        self.p3_landings.append(out)
        lost = False
        if rec is not None:
            m.landing_misses_m.append(rec["miss_r_m"])
            from .lander.classes import CLASSES as LC
            if rec.get("prop_used_kg") is not None and lt.name in LC:
                m.prop_residual_kg.append(LC[lt.name].prop_gate_kg - rec["prop_used_kg"])
            if rec["failed"]:
                m.failed_landings += 1
                lost = self.landing.failure_policy == "lose"
            elif rec["offpad"]:
                m.offpad_landings += 1
        for c in items:
            self.all_cargo.append(c)
            m.landed_kg += c.mass_kg
            if lost:
                c.lost = True
                m.cargo_lost_kg += c.mass_kg
                continue
            if rec is not None and rec["failed"]:
                c.t_ready += float(self.landing.failure_policy["recover_h"])
            if rec is not None and rec["offpad"]:
                c.offpad_km = rec["miss_r_m"] / 1000.0
            self.pending.append(c)
            self._push(c.t_ready, "READY", c)
        self._mark_stranded([c for c in items if not getattr(c, "lost", False)])

    # ---- plume keep-out (Phase 3) ----
    def pad_blocked(self, site: str, t: Optional[float] = None) -> bool:
        """True if site is a pad inside an active keep-out window at time t (default now)."""
        return (self.plume is not None and site in self.world.pads
                and self.plume.active(site, self.t if t is None else t) is not None)

    def _plume_start(self, pad: str):
        """Window opens: idle vehicles within the keep-out radius drive to the pad's shelter."""
        shelter = self.plume.shelter(pad)
        if shelter is None:
            return
        for v in self.vehicles:
            if (not v.alive or v.busy_until > self.t + 1e-9 or v.location == shelter
                    or not self.plume.inside(v.location, pad)):
                continue
            if self.dark(self.t, v.location) and not v.cls.night_ops:
                continue
            h = self.travel_h(v, v.location, shelter, False, False, self.t)
            origin = v.location
            if self._reposition(v, shelter):
                self.metrics.plume_standdowns += 1
                self.metrics.standdown_vehicle_h += h
                self.metrics.standdown_drive_h += h
                self.plume.evacuated.setdefault(pad, []).append((v.id, origin))

    def _plume_end(self, pad: str):
        """Window closes: evacuated vehicles still idle at the shelter return to their pre-evacuation site."""
        shelter = self.plume.shelter(pad)
        back = self.plume.evacuated.pop(pad, [])
        for vid, origin in back:
            v = self.vehicles[vid]
            if (not v.alive or v.busy_until > self.t + 1e-9 or v.location != shelter or origin == shelter
                    or (self.dark(self.t, v.location) and not v.cls.night_ops)):
                continue
            h = self.travel_h(v, v.location, origin, False, False, self.t)
            if self._reposition(v, origin):
                self.metrics.standdown_vehicle_h += h
                self.metrics.standdown_drive_h += h

    def _plume_hold(self, job: Job) -> float:
        """Hours the job must wait so that no vehicle starts or ends work at a pad inside a keep-out window."""
        wait = 0.0
        for segs in self._last_segments.values():
            for a, b, t0, t1, _ in segs:
                for site, tt in ((a, t0), (b, t1)):
                    if site in self.world.pads:
                        w = self.plume.overlapping(site, tt - 1e-9, tt + 1e-9)
                        if w is not None:
                            wait = max(wait, w[1] - tt)
        return wait

    def _mark_stranded(self, items: List[Cargo]):
        """Items no vehicle or team in the whole fleet could ever move."""
        if self.p5 is not None:             # Phase 5: pairs only, under the scenario's team rule
            allow = self.mech_kwargs.get("team_lift", getattr(self.mechanism, "supports_team", False))
            lim = self.p5.reach if allow else self.p5.single_max
            for c in items:
                if c.mass_kg > lim or not any(c.standard in v.standards for v in self.vehicles):
                    c.stranded = True
            return
        team_ok = sorted((v.cls.capacity_kg for v in self.vehicles if v.cls.can_team_lift), reverse=True)
        single_max = max((v.cls.capacity_kg for v in self.vehicles), default=0.0)
        team_max = sum(team_ok[:3])
        allow_team = self.mech_kwargs.get("team_lift", getattr(self.mechanism, "supports_team", False))
        for c in items:
            limit = max(single_max, team_max if allow_team else 0.0)
            compatible_any = any(c.standard in v.standards for v in self.vehicles)
            if c.mass_kg > limit or not compatible_any:
                c.stranded = True

    def upcoming_landings(self, within_h: float) -> List[Tuple[float, object, str]]:
        """Published landings between now and now + within_h (known in advance)."""
        return [(t, lt, pad) for (t, lt, pad) in self.landing_schedule if self.t < t <= self.t + within_h]

    def schedule_reposition(self, v: Vehicle, pad: str, depart_t: float):
        """Ask a free vehicle to drive empty to a pad at depart_t (anticipatory staging)."""
        if v.repos_target is not None:
            return
        if self.plume is not None and self.plume.upcoming(pad, depart_t, 48.0):
            site = self.plume.staging_site(pad)        # Phase 3: stage at the keep-out boundary (nearest site outside R)
            v.staged_for = pad
            if site is None or site == v.location:
                return
            pad = site
        v.repos_target = pad
        self._push(max(self.t, depart_t), "REPOS", (v, pad))

    def _reposition(self, v: Vehicle, pad: str):
        h = self.travel_h(v, v.location, pad, False, False, self.t)
        d = self._leg_km(v, v.location, pad)
        if self.p5 is not None and self.p5.limited(v) and (d > self.p5.km_left(v, self.t) + 1e-9
                                                           or self.t + h > self.p5.active_until(v)):
            return False
        segs_c = None
        if self.comms is not None and self.comms.active and self.comms.needs_link(v.autonomy):
            segs_c, waits_c = self.comms.reposition(v, v.location, pad, self.t, h)
            if segs_c is None:
                return False                # the link never comes on this leg
            if waits_c:
                h = segs_c[-1][3] - self.t
        if not v.cls.night_ops and self.t + h > self.next_dark(self.t, v.location, pad):
            return False
        t_end = self.t + h
        if segs_c is not None:
            self.comms.book_waits(v, waits_c)
        if self.record_trace:
            self.trace.append({"kind": "reposition", "veh": v.id, "team": [v.id], "t0": self.t, "t1": t_end,
                               "segments": segs_c if segs_c is not None else [[v.location, pad, self.t, t_end, 0.0]],
                               "items": []})
        v.busy_until = t_end
        v.location = pad
        v.km_total += d
        v.km_empty += d
        if self.p5 is not None:
            self.p5.note_km(v, d, self.t)
        v.hours_driving += h
        v.hours_busy += h
        self.repositions += 1
        self.km_reposition += d
        self.metrics.km_total += d
        self.metrics.km_empty += d
        self.metrics.veh_hours_busy += h
        self._push(t_end, "FREE", None)
        return True

    def _dispatch(self):
        candidates = [c for c in self.waiting if not c.stranded]
        if self.plume is not None:      # Phase 3: no pickup at, or delivery to, a pad inside a keep-out window
            candidates = [c for c in candidates if not (self.pad_blocked(c.origin) or self.pad_blocked(c.dest))]
        if self.comms is not None and self.comms.active:      # Phase 4: items no vehicle could ever deliver
            candidates = self.comms.filter_candidates(self, candidates)
        free = self.free_vehicles()
        if not free:
            return
        if not candidates and not getattr(self.mechanism, "anticipates", False):
            return
        self._dispatch_serial = getattr(self, "_dispatch_serial", 0) + 1   # dispatch's per-call plan memo (B-57)
        jobs: List[Job] = self.mechanism(self, candidates, free, **self.mech_kwargs)
        for job in jobs:
            self._start_job(job)
        if self.comms is not None and self.comms.active:      # Phase 4: re-dispatch when a deferred link returns
            for tw in self.comms.pop_wakes(self.t):
                self._push(tw, "WAKE", None)

    def _start_job(self, job: Job):
        # operator check
        demand = sum(self.operator_demand(v) for v in job.vehicles)
        avail = self.operators_available()
        if demand > avail + 1e-9:
            if self.comms is not None and self.comms.active:
                t_free = self.comms.next_demand_drop(self.t)
                if t_free is not None:
                    for v in job.vehicles:
                        v.busy_until = max(v.busy_until, t_free)
                    self._push(t_free, "FREE", None)
                    self.metrics.unmet_operator_waits += 1
                return
            # wait until the earliest operator job ends
            if self.op_jobs:
                t_free = min(e for e, _ in self.op_jobs)
                for v in job.vehicles:
                    v.busy_until = max(v.busy_until, t_free)
                self._push(t_free, "FREE", None)
                self.metrics.unmet_operator_waits += 1
            return
        comms_on = self.comms is not None and self.comms.active
        if not self.p3:
            if comms_on:                    # committed job: the strategic interventions are drawn
                dur, km, km_empty, e_wh, _ = self.job_plan(job, self.t, realize=True)
            else:
                dur, km, km_empty, e_wh, _ = self.job_plan(job, self.t)
            if self.p5 is not None and not math.isfinite(dur):
                self.p5.refused += 1
                return
        else:
            dur, km, km_empty, e_wh, _ = self.job_plan(job, self.t, realize=True)
            hold = 0.0
            if self.plume is not None:
                for _ in range(5):                   # hold at the boundary until no pad visit falls in a window
                    w = self._plume_hold(job)
                    if w <= 1e-9:
                        break
                    hold += w
                    dur, km, km_empty, e_wh, _ = self.job_plan(job, self.t + hold, realize=True)
                if hold > 0:
                    for vid, segs in self._last_segments.items():
                        loc = segs[0][0] if segs else job.vehicles[0].location
                        self._last_segments[vid] = [[loc, loc, self.t, self.t + hold, 0.0]] + segs
                    dur += hold
                    self.metrics.plume_standdowns += 1
                    self.metrics.standdown_vehicle_h += hold * len(job.vehicles)
                    self.metrics.standdown_hold_h += hold * len(job.vehicles)
            if comms_on and not math.isfinite(dur):
                self.comms.jobs_refused += 1    # a needed Earth link never comes on this job's legs
                return
            if self.p5 is not None and not math.isfinite(dur):
                self.p5.refused += 1            # Phase 5: beyond a hopper's budget or window
                return
            off = self._offpad_km(job) if self.landing is not None else 0.0
            self.metrics.km_offpad_extra += 2.0 * off * len(job.vehicles)
            self.metrics.interventions += self._last_interventions
            self.metrics.intervention_h += self._last_interventions * (self.rtt_s + INTERVENTION_RECOVERY_S) / 3600.0
            job_interventions = self._last_interventions
        if comms_on and not math.isfinite(dur):
            self.comms.jobs_refused += 1
            return
        # battery: if the trip needs more than is in the pack, charge first
        for v in job.vehicles:
            need = e_wh / len(job.vehicles)
            if need > v.battery_wh:
                dur += (need - v.battery_wh) / (v.cls.charge_kw * 1000.0)
                v.battery_wh = v.cls.battery_wh
            v.battery_wh = max(0.0, v.battery_wh - need)
        driving_h = dur
        if self.p5 is not None:             # Phase 5: daily km budget (Phase-1 LTVs remote, 6 km/day)
            dur += self.p5.day_cap_delay(job, km, self.t)
        # faults
        for v in job.vehicles:
            if self.sc.failures and v.hours_driving + driving_h > v.next_fault_h:
                dur += v.cls.mttr_h
                v.hours_failed += v.cls.mttr_h
                v.next_fault_h = v.hours_driving + driving_h + self.rng_ops.exponential(v.cls.mtbf_h * self.sc.mtbf_mult)
                self.metrics.faults += 1
        # night: a vehicle that cannot work in the dark and is caught out hibernates
        t_end = self.t + dur
        if self.illum is not None:          # caught by the dark on a leg or at a stop: wait there until it is lit
            for v in job.vehicles:
                if not v.cls.night_ops:
                    hit = self.illum.first_dark(self._last_segments.get(v.id) or [])
                    if hit is not None and hit[0] < t_end - 1e-9:
                        dur += min(hit[1], max(self.sc.horizon_h, t_end)) - hit[0]
                        self.metrics.night_strandings += 1
                        break
        elif self.sc.night_fraction > 0:
            for v in job.vehicles:
                if not v.cls.night_ops:
                    ns = self.next_night_start(self.t)
                    if t_end > ns:
                        dur += self.sc.night_fraction * LUNAR_CYCLE_H
                        self.metrics.night_strandings += 1
                        break
        t_end = self.t + dur
        op_linked_h = None
        if comms_on:
            op_linked_h = self.comms.commit(self, job, self.t, t_end)
        elif self.comms is not None:        # mode "always": record operator demand only
            self.comms.log_job_passive(self.t, t_end, demand)
        last_stop = job.backhaul[0].dest if job.backhaul else job.route[-1]
        if self.record_trace:
            segs = self._last_segments.get(job.vehicles[0].id, [])
            plan_end = segs[-1][3] if segs else self.t
            extra = t_end - plan_end
            if extra > 1e-9:  # fault recovery or night hibernation at the last stop
                segs = segs + [[last_stop, last_stop, plan_end, t_end, 0.0]]
            rec = {"kind": "team" if len(job.vehicles) > 1 else (job.note or "job"),
                   "veh": job.vehicles[0].id, "team": [u.id for u in job.vehicles],
                   "t0": self.t, "t1": t_end, "segments": segs,
                   "items": [[c.id, round(c.mass_kg, 1), c.priority, c.cls, c.dest] for c in job.items + job.backhaul]}
            if self.p3:
                rec["interventions"] = job_interventions
                rec["energy_kwh"] = round(e_wh / 1000.0, 4)
            self.trace.append(rec)
        for v in job.vehicles:
            v.repos_target = None
            if self.p3:
                v.staged_for = None
            v.busy_until = t_end
            v.location = last_stop
            v.km_total += km / len(job.vehicles)
            v.km_empty += km_empty / len(job.vehicles)
            v.hours_driving += driving_h
            v.hours_busy += dur
            v.hours_operator += dur * self.operator_demand(v)
            v.jobs += 1
            if self.p5 is not None:
                self.p5.note_km(v, km / len(job.vehicles), self.t)
        price = self.job_cost_usd(job, dur)
        for v in job.vehicles:
            share = price / len(job.vehicles) / 1e6
            v.revenue_musd += share
            self.metrics.revenue_by_owner[v.owner] = self.metrics.revenue_by_owner.get(v.owner, 0.0) + share
        self.op_jobs.append((t_end, demand))
        for c in job.items:
            self.waiting.remove(c)
            c.t_picked = self.t
            c.carrier = job.vehicles[0].id
            c.team_size = len(job.vehicles)
            # delivery time: when the vehicle reaches that stop (approximate by job end
            # for the last stop; proportional for earlier stops)
            idx = job.route.index(c.dest)
            frac = (idx + 1) / (len(job.route) + (1 if job.backhaul else 0))
            c.t_delivered = self.t + dur * frac
            self._push(c.t_delivered, "FREE", None)
            self._record_delivery(c)
        for c in job.backhaul:
            self.waiting.remove(c)
            c.t_picked = self.t
            c.carrier = job.vehicles[0].id
            c.t_delivered = t_end
            self._record_delivery(c)
            self.metrics.backhaul_kg += c.mass_kg
        if self.comms is not None:
            self.comms.note_deliveries(job.items + job.backhaul)
        if len(job.vehicles) > 1:
            self.metrics.team_lifts += 1
        if len(job.items) > 1:
            self.metrics.bundled_jobs += 1
        self.metrics.jobs += 1
        self.metrics.km_total += km
        self.metrics.km_empty += km_empty
        self.metrics.energy_kwh += e_wh / 1000.0
        self.metrics.veh_hours_busy += dur * len(job.vehicles)
        self.metrics.operator_hours += dur * demand if op_linked_h is None else op_linked_h
        self._push(t_end, "FREE", None)

    def _record_delivery(self, c: Cargo):
        m = self.metrics
        m.delivered_kg += c.mass_kg
        if c.cls not in ("bulk", "return"):
            m.delivered_nonbulk_kg += c.mass_kg
        m.delivered_tkm += c.mass_kg / 1000.0 * self.world.distance_km(c.origin, c.dest)
        m.delivered_items += 1
        m.delays_h.append(c.t_delivered - c.t_ready)
        m.delay_mass.append(c.mass_kg)
        m.delay_prio.append(c.priority)
        m.delay_cls.append(c.cls)
        # return cargo: a share of delivered outbound mass comes back to a pad later
        if c.origin in self.world.pads and c.cls != "return" and c.return_mass_kg > 0:
            t_r = c.t_delivered + c.return_lag_h
            if t_r < self.sc.horizon_h:
                self._cid += 1
                rc = Cargo(self._cid, c.owner, c.return_mass_kg, c.dest, c.origin,
                           t_r, t_r, 3, c.standard, "return")
                self.all_cargo.append(rc)
                self.pending.append(rc)
                self._push(rc.t_ready, "READY", rc)

    def _finalise(self):
        m = self.metrics
        for c in self.waiting:
            if c.stranded:
                m.stranded_kg += c.mass_kg
                m.stranded_items += 1
            else:
                m.backlog_kg += c.mass_kg
        H = self.sc.horizon_h
        for v in self.vehicles:
            m.veh_hours_avail += H
            m.fleet_cost_musd += v.cls.unit_cost_musd * H / (v.cls.life_years * 365 * HOURS_PER_DAY)
        m.operator_cost_musd += m.operator_hours * self.sc.operator_cost_per_h / 1e6
        m.repositions = self.repositions
        m.km_reposition = self.km_reposition
        if self.comms is not None:
            self.comms.finalise()

    # ------------------------------------------------------------- export
    def _trace_v2(self, nights, clean, mechanism):
        return _trace_v2_body(self, nights, clean, mechanism)

    def trace_export(self, mechanism: Optional[str] = None) -> dict:
        """Everything the live viewer needs to replay this run, as lunarsim-trace v1.

        See lunarsim/schemas/trace-v1.schema.json. `mechanism` overrides the name
        recorded in the header (default: the dispatch function's __name__).
        """
        nights = [] if self.illum is None else self.illum.dark_windows("BASE", self.sc.horizon_h)
        t = 0.0
        while self.illum is None and self.sc.night_fraction > 0 and t < self.sc.horizon_h:
            ns = self.next_night_start(t)
            ne = ns + self.sc.night_fraction * LUNAR_CYCLE_H
            nights.append([ns, min(ne, self.sc.horizon_h)])
            t = ne + 1e-6
        clean = {}
        for k, v in self.metrics.summary().items():
            clean[k] = None if (isinstance(v, float) and np.isnan(v)) else (float(v) if isinstance(v, (np.floating, float)) else int(v) if isinstance(v, (np.integer,)) else v)
        if mechanism is None:
            mechanism = getattr(self.mechanism, "__name__", str(self.mechanism))
        if self.p3:
            return self._trace_v2(nights, clean, mechanism)
        return {
            "format": "lunarsim-trace",
            "version": 1,
            "engine": "python",
            "scenario": self.sc.name,
            "mechanism": mechanism,
            "seed": int(self.seed),
            "world": self.world.to_dict(),
            "horizon_h": self.sc.horizon_h,
            "nights": nights,
            "landings": [[t, lt.name, pad] for (t, lt, pad) in self.landing_schedule],
            "vehicles": [{"id": v.id, "owner": v.owner, "cls": v.cls.name, "autonomy": v.autonomy,
                          "capacity": v.cls.capacity_kg, "night_ops": v.cls.night_ops} for v in self.vehicles],
            "jobs": self.trace,
            "cargo_columns": ["id", "owner", "mass_kg", "origin", "dest", "t_ready", "t_picked",
                              "t_delivered", "priority", "cls", "stranded"],
            "cargo": [[c.id, c.owner, round(c.mass_kg, 1), c.origin, c.dest, round(c.t_ready, 2),
                       None if c.t_picked is None else round(c.t_picked, 2),
                       None if c.t_delivered is None else round(c.t_delivered, 2), c.priority, c.cls, int(c.stranded)]
                      for c in self.all_cargo],
            "summary": clean,
        }


def _trace_v2_body(sim: "Simulation", nights, clean, mechanism) -> dict:
    """lunarsim-trace v2 (PLAN §5.5): v1 plus landing outcomes, keep-out windows, shelters, terrain."""
    plume = sim.plume
    shelters = []
    if plume is not None:
        for pad in sim.world.pads:
            s = plume.shelter(pad)
            shelters.append({"pad": pad, "site": s,
                             "los_blocked": None if s is None else sim.sites.line_of_sight_blocked(pad, s)})
    out = {
        "format": "lunarsim-trace", "version": 2, "engine": "python", "scenario": sim.sc.name,
        "mechanism": mechanism, "seed": int(sim.seed), "terrain": sim.sc.terrain,
        "pad_standoff_km": sim.sites.standoff if sim.sc.terrain else None,
        "world": sim.world.to_dict(),
        "site_xy_m": {k: [round(1000.0 * x, 1), round(1000.0 * y, 1)] for k, (x, y) in sim.sites.xy_km.items()},
        "horizon_h": sim.sc.horizon_h, "nights": nights,
        "landings": sim.p3_landings,
        "plume_windows": [[t0, t1, pad, plume.R] for (t0, t1, pad) in plume.windows] if plume else [],
        "shelters": shelters,
        "vehicles": [{"id": v.id, "owner": v.owner, "cls": v.cls.name, "autonomy": v.autonomy,
                      "autonomy_level": v.autonomy, "capacity": v.cls.capacity_kg, "night_ops": v.cls.night_ops}
                     for v in sim.vehicles],
        "jobs": sim.trace,
        "cargo_columns": ["id", "owner", "mass_kg", "origin", "dest", "t_ready", "t_picked", "t_delivered",
                          "priority", "cls", "stranded", "lost"],
        "cargo": [[c.id, c.owner, round(c.mass_kg, 1), c.origin, c.dest, round(c.t_ready, 2),
                   None if c.t_picked is None else round(c.t_picked, 2),
                   None if c.t_delivered is None else round(c.t_delivered, 2), c.priority, c.cls, int(c.stranded),
                   int(getattr(c, "lost", False))] for c in sim.all_cargo],
        "summary": clean,
    }
    if sim.comms is not None:               # Phase 4: link settings and every "waiting for Earth" interval
        cm = sim.comms
        out["comms"] = {"mode": cm.mode, "criterion": cm.criterion, "link_mode": cm.link_mode,
                        "supervised_policy": cm.policy, "start_h": cm.start_h,
                        "missing_legs": sorted(cm.missing_legs)}
        out["comms_waits"] = cm.waits       # [vehicle id, t0, t1, site or leg, "start" | "midway" | "intervention"]
    return out


def run(sc: Scenario, mechanism: Callable, seed: int, **mech_kwargs) -> Dict[str, float]:
    sim = Simulation(sc, mechanism, seed=seed, mech_kwargs=mech_kwargs)
    out = sim.run()
    out["seed"] = seed
    return out
