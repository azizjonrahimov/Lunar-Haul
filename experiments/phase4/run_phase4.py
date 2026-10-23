"""Phase-4 experiment E21 "Earth in sight" (R-1; plan §10, the R-1 note's hypotheses H1-H6): raw CSVs and summary tables.

Usage:  python experiments/phase4/run_phase4.py e21a [--seeds 20] [--workers 1] [--cells 0-9] [--max-seconds 540]
        python experiments/phase4/run_phase4.py e21b e21c            # B reads the Stage A table
        python experiments/phase4/run_phase4.py e21d --cells 0-7      # stage D (real sun), in chunks
        python experiments/phase4/run_phase4.py e21a2                 # stage A2 (strict operators)
        python experiments/phase4/run_phase4.py e21a --round r2       # round 2 (referee round 1): *_r2.csv files
        python experiments/phase4/run_phase4.py table                 # rebuild results/table_E21*.csv only

Conventions as experiments/phase3/run_phase3.py: a cell is (tag, scenario, mechanism) replicated over seeds with common
random numbers; the raw CSV is resumable (rows keyed by `cell` and `seed` are skipped); `--cells a-b` runs only those
cells of a stage (0-based, inclusive) so LEAD can work in foreground chunks; `--workers 1` (default) runs in this process.
Calendar: replication `seed` simulates one year starting 1 January of 2028 + (seed mod 4) (comms.start_year), so the
link series' ~347-day ripple (H6) is sampled; the start year is a column.

Common settings (as E19): P2, marketplace, terrain connecting_ridge, driving tables driving-v1, classical landing
model, pads at 1 km, Earth-link criterion any_part (lunarsim/comms.py; data/comms/connecting_ridge/earth_link-v1.json).

  e21a  comms {always, dte, dte+relay p = 0.1, 0.2, 0.3, 0.4, 0.5, 0.8, 0.9, 1.0} x autonomy mix {all teleop (4 s RTT), the P2 default
        mix, all supervised-strict, all supervised-strategic, all supervised-strategic+avoid, all autonomous}
                                                                                               -> E21a_comms_autonomy.csv
  e21b  at the knee of the Stage A coverage -> throughput curve (the smallest relay coverage reaching KNEE_SHARE of
        full coverage, all supervised-strict fleet): comms {dte, dte+relay p_knee} x extra rovers +0..3 (supervised
        LTVs) x base mast {none, 10 m} x supervised policy {strict, strategic}                 -> E21b_breakeven.csv
        and the break-even table (relay coverage = one autonomy step = N extra rovers = mast, and the relay price per
        year that equals N rovers' capital cost)                                               -> table_E21_breakeven.csv
  e21c  at three Stage A cells: pads {0.5, 1, 3 km} x criterion {any_part, centre+0.5deg, centre+2deg} (defer 24 h),
        plus defer_wait_h {12, 72, none} at pads 1 km / any_part                                -> E21c_pads_criterion.csv
  e21a2 H5 done properly: the Stage A cells comms {dte, dte+relay 0.1, 0.3, 0.5, 0.8, 1.0} x mix {all teleop (4 s),
        P2 default} again with comms.operators_strict (B-45: operators a hard capacity in the linked modes); the
        lenient twins are the Stage A rows (same scenario, seeds and start years), and "always" is left out (the rule
        has no effect there)                                                                   -> E21a2_operators.csv
  e21d  H6, Earth's 27.21-day elevation cycle against the 29.53-day lunar day (beat ~347 d): comms {dte, dte+relay 0.5}
        x mix {P2 default, all supervised-strict} x sun {night_fraction 0.15, real (Scenario.illumination, B-44:
        criterion half, leg rule most)} x start year 2028-2031 as a cell factor (not seed mod 4), with the delivered
        tonnes per twelfth of the year (delivered_t_m01..m12) for the ripple                    -> E21d_sun.csv
  e21e  (round 2) sensitivities, each against its Stage A twin: relay mean gap 2 h and 24 h and a periodic relay
        (DRM-0 784 min and RC 3.1 ~30 h orbit periods) at p = 0.1 and 0.5 for the strict and teleop fleets;
        intervention rate x0.5 and x2 for strategic and strategic+avoid at DTE and p = 0.5; plume keep-out 1 km /
        0.5 h at DTE (P2 default mix) and p = 0.5 (strict); ISRU with local feedstock (no CONSTR -> ISRU haul) at DTE
        and always for the default, strict and teleop fleets                                     -> E21e_sensitivity.csv
  e21f  (round 2, B-57) the bounded-wait strategic rule on the all-supervised fleet: comms {dte, dte+relay 0.1, 0.5} x
        bound_h {24, 72, 168, 720} x bound_never {refuse, strategic} (supervised_policy strategic+bound), plus plain
        strategic with never_linked "strand" (an intervention on a never-linked sample strands the rover for the rest
        of the year instead of a re-draw) at the same three link regimes; common random numbers with Stage A (same
        seeds and start years); its twins are Stage A's strategic and look-ahead cells. Not in table_E21*.csv
        (analyse_e21.py bounded)                                                                 -> E21f_bounded.csv
  e21g  (round 2, B-59) plain strategic at DTE only with never_linked "rescue": an intervention on a never-linked
        sample is resolved after rescue_h {0, 24, 72, 168, 720} h (the helper's own time not modelled); twins: Stage A
        strategic, strict and look-ahead at DTE (analyse_e21.py rescue)                          -> E21g_rescue.csv
  e21g2 (round 2, B-60) as e21g with rescue_scope "any": every strategic intervention wait longer than rescue_h ends
        after rescue_h (analyse_e21.py rescue --scope any)                                       -> E21g2_rescue_any.csv
Every finished run is appended to its stage file at once; --max-seconds also stops starting runs that would end past
the time budget, so a chunk ends cleanly and the next one resumes.
Round 2 (--round r2): every stage writes results/<stage>_r2.csv and the tables table_E21_r2.csv,
table_E21_breakeven_r2.csv, so round-1 files stay as they were. The engine is unchanged, so a round-2 row equals its
round-1 row in every round-1 column (analyse_e21.py checks it); round 2 adds the B-48 outcome columns (completion and
censored urgent delay, bulk / landed kg) and the new cells: Stage A relay 0.05, 0.6, 0.7; Stage B strategic+avoid on
the full grid and strict / strategic at +0 / +1 rover at p = 0.2 and 0.8; Stage E.
Summary of every stage present: results/table_E21.csv (mean and 95 % CI per cell of delivered t/yr inside the year,
urgent p90 delay, $/landed kg, blackout wait, operator peak, plus the other B-41 metrics).
"""
import argparse
import faulthandler
import math
import os
import sys
import time
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
warnings.filterwarnings("ignore")
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from lunarsim import Simulation  # noqa: E402
from lunarsim.config import split_rtt  # noqa: E402
from lunarsim.entities import VEHICLE_CLASSES  # noqa: E402
from lunarsim.phases import PHASES  # noqa: E402
from experiments.phase3 import fit_law  # noqa: E402
from experiments.phase3.run_phase3 import MECHS, cell_key, phase3  # noqa: E402

N_SEEDS = 20
WORKERS = 1
RESULTS = os.path.join(ROOT, "results")
MECH = "marketplace"
CRITERION = "any_part"
STANDOFF = 1.0
COMMS_LEVELS = (("always", None), ("dte", None), ("dte+relay", 0.1), ("dte+relay", 0.2), ("dte+relay", 0.3),
                ("dte+relay", 0.4), ("dte+relay", 0.5), ("dte+relay", 0.8), ("dte+relay", 0.9), ("dte+relay", 1.0))
# 0.1-0.4 added by LEAD (22 Oct) so the knee of the coverage -> throughput curve is resolved below 0.5
MIXES = ("teleop_4s", "default", "supervised_strict", "supervised_strategic", "supervised_strategic+avoid", "autonomous")
KNEE_SHARE = 0.95                 # Assumed: the knee = smallest coverage with >= 95 % of full-coverage throughput
STAGE_B_COVERAGE = 0.5            # LEAD 22 Oct: stage A showed throughput saturates already at p = 0.1 (the loss is
                                  # reachability of never-linked sites), so the throughput knee is uninformative; stage B
                                  # runs at DTE and at p = 0.5, the middle of the urgent-delay curve
EXTRA_ROVERS = (0, 1, 2, 3)
MASTS = (None, {"site": "BASE", "height_m": 10.0, "range_km": 10.0})
POLICIES = ("strict", "strategic")
E21C_PADS = (0.5, 1.0, 3.0)
E21C_CRITERIA = ("any_part", "centre+0.5deg", "centre+2deg")
E21C_BASE = (("dte", None, "default"), ("dte", None, "teleop_4s"), ("dte+relay", 0.8, "supervised_strict"))
DEFER_DEFAULT_H = 24.0            # lunarsim.comms.DEFAULT_DEFER_WAIT_H (Assumed)
E21C_DEFERS = (12.0, 72.0, None)  # with the default 24 h from the pads x criterion grid; None = never defer
STAGES = {"e21a": "E21a_comms_autonomy", "e21b": "E21b_breakeven", "e21c": "E21c_pads_criterion", "e21d": "E21d_sun",
          "e21a2": "E21a2_operators", "e21e": "E21e_sensitivity"}
STAGE_F = "E21f_bounded"          # B-57; kept out of STAGES so table_E21*.csv stay as they are
STAGE_G = "E21g_rescue"           # B-59; likewise
STAGE_G2 = "E21g2_rescue_any"     # B-60; likewise
STAGE_H = "E21h_helper"           # B-62; likewise
ROUNDS = ("r1", "r2")
R2_LEVELS = (("dte+relay", 0.05), ("dte+relay", 0.6), ("dte+relay", 0.7))       # referee M1 (round 2 only)
R2_B_POLICY = "strategic+avoid"                                                   # referee M6
R2_B_EXTRA_P = (0.2, 0.8)
LCRNS_DRM0_PERIOD_H = 784.0 / 60.0      # Modelled: LCRNS DRM-0, one relay, 784 min orbit (R-1 note)
LCRNS_RC31_PERIOD_H = 30.0              # Modelled: LCRNS Reference Constellation 3.1 ELFO, period about 30 h (R-1 note)
E21A2_COMMS = (("dte", None), ("dte+relay", 0.1), ("dte+relay", 0.3), ("dte+relay", 0.5), ("dte+relay", 0.8),
               ("dte+relay", 1.0))
E21A2_MIXES = ("teleop_4s", "default")
E21D_COMMS = (("dte", None), ("dte+relay", 0.5))
E21D_MIXES = ("default", "supervised_strict")
E21D_SUN = ("night_fraction", "real")
E21D_YEARS = (2028, 2029, 2030, 2031)
N_MONTHS = 12
FACTORS = ["stage", "comms", "coverage", "mix", "policy", "extra_rovers", "mast", "pad_standoff_km", "criterion",
           "defer_wait_h", "sun", "year", "sensitivity"]   # sun / year: stage D (else night_fraction, -1); sensitivity: E
METRICS = ["delivered_t_in_year", "delay_prio1_p90_h", "cost_per_landed_kg_usd", "blackout_wait_vehicle_h",
           "operator_peak_demand", "delay_prio1_mean_h", "sl24_prio1", "delivered_kg", "blackout_wait_teleop_h",
           "blackout_wait_supervised_h", "blackout_jobs_delayed", "blackout_jobs_refused", "blackout_jobs_deferred",
           "blackout_jobs_avoided", "operator_wait_vehicle_h", "operator_waits",
           "prio1_completion_share", "delay_prio1_p90_censored_h", "delay_prio1_mean_censored_h",
           "delay_prio1_p90_censored_is_bound", "completion_share_bulk", "completion_share_landed",
           "delivered_bulk_kg_in_horizon", "delivered_landed_kg_in_horizon",
           "linked_share_by_leg_mean", "operator_hours", "jobs", "utilisation", "backlog_kg"]
EXTRA_ROVER = ("EXTRA", "LTV", "supervised", "A")


# ---------------------------------------------------------------------------
# cells
# ---------------------------------------------------------------------------
def comms_cfg(mode, coverage=None, policy="strict", criterion=CRITERION, mast=None, defer=DEFER_DEFAULT_H):
    c = {"mode": mode, "criterion": criterion, "supervised_policy": policy, "defer_wait_h": defer}
    if mode == "dte+relay":
        c["relay"] = {"coverage": float(coverage), "gap_model": "parametric"}
    if mast:
        c["mast"] = dict(mast)
    return c


def fleet_for(mix, extra=0):
    """(fleet, policy, rtt_s or None) of an autonomy mix on the P2 default fleet (+ extra supervised LTVs)."""
    base = list(PHASES["P2"].fleet)
    if mix == "default":
        fleet, policy, rtt = base, "strict", None
    elif mix == "teleop_4s":
        fleet, policy, rtt = [(o, c, "teleop", s) for (o, c, _, s) in base], "strict", 4.0
    elif mix in ("supervised_strict", "supervised_strategic", "supervised_strategic+avoid"):
        fleet, policy, rtt = [(o, c, "supervised", s) for (o, c, _, s) in base], mix.split("_", 1)[1], None
    elif mix == "autonomous":
        fleet, policy, rtt = [(o, c, "autonomous", s) for (o, c, _, s) in base], "strict", None
    else:
        raise ValueError(f"unknown autonomy mix {mix!r}")
    return fleet + [EXTRA_ROVER] * extra, policy, rtt


def scenario(mix, comms_mode, coverage=None, extra=0, mast=None, standoff=STANDOFF, criterion=CRITERION,
             policy_override=None, defer=DEFER_DEFAULT_H):
    base = PHASES["P2"]
    fleet, policy, rtt = fleet_for(mix, extra)
    policy = policy_override or policy
    kw = {"fleet": fleet, "n_operators": max(base.n_operators, len(fleet) // 2),
          "comms": comms_cfg(comms_mode, coverage, policy, criterion, mast, defer)}
    if rtt is not None:
        kw["one_way_latency_s"], kw["ground_delay_s"] = split_rtt(rtt, base.ground_delay_s)
    sc = phase3(base.with_(**kw), standoff)
    tag = {"exp": "E21", "comms": comms_mode, "coverage": float(coverage) if coverage is not None else np.nan,
           "mix": mix, "policy": policy, "extra_rovers": int(extra), "mast": "BASE 10 m" if mast else "none",
           "pad_standoff_km": float(standoff), "criterion": criterion,
           "defer_wait_h": float(defer) if defer is not None else math.inf, "n_vehicles": len(fleet),
           "n_operators": kw["n_operators"], "rtt_s": float(2 * sc.one_way_latency_s + sc.ground_delay_s)}
    return tag, sc


def e21a_cells(rnd: str = "r1"):
    cells = []
    for mode, p in COMMS_LEVELS + (R2_LEVELS if rnd != "r1" else ()):
        for mix in MIXES:
            tag, sc = scenario(mix, mode, p)
            tag["stage"] = "A"
            cells.append((tag, sc, MECH, *MECHS[MECH]))
    return cells


def knee_coverage(table: pd.DataFrame, mix="supervised_strict", metric="delivered_t_in_year", share=KNEE_SHARE) -> float:
    """Smallest relay coverage (dte = 0) whose mean throughput reaches `share` of full coverage (p = 1)."""
    a = table[(table["stage"] == "A") & (table["mix"] == mix) & (table["comms"] != "always")].copy()
    if a.empty:
        raise ValueError("no Stage A rows for the knee; run e21a first")
    a["p"] = np.where(a["comms"] == "dte", 0.0, a["coverage"])
    curve = a.groupby("p")[metric].mean().sort_index()
    if 1.0 not in curve.index:
        raise ValueError("Stage A lacks the full-coverage cell (dte+relay 1.0)")
    full = curve.loc[1.0]
    ok = curve[curve >= share * full]
    return float(ok.index.min())


def e21b_cells(p_knee: float, rnd: str = "r1"):
    cells = []
    pols = POLICIES + ((R2_B_POLICY,) if rnd != "r1" else ())
    for mode, p in (("dte", None), ("dte+relay", p_knee)):
        if mode == "dte+relay" and p_knee <= 0:
            continue
        for extra in EXTRA_ROVERS:
            for mast in MASTS:
                for pol in pols:
                    tag, sc = scenario("supervised_strict", mode, p, extra=extra, mast=mast, policy_override=pol)
                    tag["stage"] = "B"
                    tag["p_knee"] = float(p_knee)
                    cells.append((tag, sc, MECH, *MECHS[MECH]))
    if rnd != "r1":                                   # a second and third coverage for the rover equivalent (M6)
        for p in R2_B_EXTRA_P:
            for pol in POLICIES:
                for extra in (0, 1):
                    tag, sc = scenario("supervised_strict", "dte+relay", p, extra=extra, policy_override=pol)
                    tag["stage"] = "B"
                    tag["p_knee"] = float(p_knee)
                    cells.append((tag, sc, MECH, *MECHS[MECH]))
    return cells


def e21c_cells():
    cells = []
    for mode, p, mix in E21C_BASE:
        for d in E21C_PADS:
            for crit in E21C_CRITERIA:
                tag, sc = scenario(mix, mode, p, standoff=d, criterion=crit)
                tag["stage"] = "C"
                cells.append((tag, sc, MECH, *MECHS[MECH]))
        for dw in E21C_DEFERS:
            tag, sc = scenario(mix, mode, p, defer=dw)
            tag["stage"] = "C"
            cells.append((tag, sc, MECH, *MECHS[MECH]))
    return cells


def e21e_cells():
    """Round-2 sensitivities (referee M8, M12, M13, M14); each has a Stage A twin with the same comms, mix and seeds."""
    cells = []

    def add(name, mix, mode, p, change):
        tag, sc = scenario(mix, mode, p)
        tag.update(stage="E", sensitivity=name)
        cells.append((tag, change(sc), MECH, *MECHS[MECH]))

    gaps = (("relay_gap_2h", {"gap_model": "parametric", "mean_gap_h": 2.0}),
            ("relay_gap_24h", {"gap_model": "parametric", "mean_gap_h": 24.0}),
            ("relay_periodic_drm0", {"gap_model": "periodic", "period_h": LCRNS_DRM0_PERIOD_H}),
            ("relay_periodic_rc31", {"gap_model": "periodic", "period_h": LCRNS_RC31_PERIOD_H}))
    for p in (0.1, 0.5):
        for mix in ("supervised_strict", "teleop_4s"):
            for name, r in gaps:
                add(name, mix, "dte+relay", p,
                    lambda sc, r=r, p=p: sc.with_(comms=dict(sc.comms, relay={"coverage": float(p), **r})))
    for mode, p in (("dte", None), ("dte+relay", 0.5)):
        for mix in ("supervised_strategic", "supervised_strategic+avoid"):
            for k in (0.5, 2.0):
                add(f"interventions_x{k:g}", mix, mode, p,
                    lambda sc, k=k: sc.with_(comms=dict(sc.comms, intervention_scale=k)))
    plume = {"keepout_km": 1.0, "standdown_h": 0.5, "shelter": "auto"}
    add("plume_1km_0.5h", "default", "dte", None, lambda sc: sc.with_(plume=dict(plume)))
    add("plume_1km_0.5h", "supervised_strict", "dte+relay", 0.5, lambda sc: sc.with_(plume=dict(plume)))
    local = lambda sc: sc.with_(bulk_flows=[b for b in sc.bulk_flows if not (b.origin == "CONSTR" and b.dest == "ISRU")])
    for mode in ("dte", "always"):
        for mix in ("default", "supervised_strict", "teleop_4s"):
            add("isru_local_feedstock", mix, mode, None, local)
    return cells


E21F_COMMS = (("dte", None), ("dte+relay", 0.1), ("dte+relay", 0.5))
E21F_BOUNDS = (24.0, 72.0, 168.0, 720.0)
E21F_NEVER = ("refuse", "strategic")


def e21f_cells():
    """Stage F (B-57): strategic+bound at four bounds and both never-linked rules, and strategic with stranding."""
    cells = []
    for mode, p in E21F_COMMS:
        for bound in E21F_BOUNDS:
            for never in E21F_NEVER:
                tag, sc = scenario("supervised_strategic", mode, p)
                sc = sc.with_(comms=dict(sc.comms, supervised_policy="strategic+bound", bound_h=bound, bound_never=never))
                tag.update(stage="F", mix="supervised_strategic+bound", policy="strategic+bound", bound_h=bound,
                           bound_never=never, never_linked="redraw")
                cells.append((tag, sc, MECH, *MECHS[MECH]))
        tag, sc = scenario("supervised_strategic", mode, p)
        sc = sc.with_(comms=dict(sc.comms, never_linked="strand"))
        tag.update(stage="F", never_linked="strand")
        cells.append((tag, sc, MECH, *MECHS[MECH]))
    return cells


E21G_RESCUE_H = (0.0, 24.0, 72.0, 168.0, 720.0)


def e21g_cells():
    """Stage G (B-59): plain strategic, DTE only, an intervention on a never-linked sample resolved after rescue_h."""
    cells = []
    for h in E21G_RESCUE_H:
        tag, sc = scenario("supervised_strategic", "dte")
        sc = sc.with_(comms=dict(sc.comms, never_linked="rescue", rescue_h=h))
        tag.update(stage="G", never_linked="rescue", rescue_h=h)
        cells.append((tag, sc, MECH, *MECHS[MECH]))
    return cells


def e21g2_cells():
    """Stage G2 (B-60): as Stage G, but every strategic intervention wait longer than rescue_h ends after rescue_h."""
    cells = []
    for h in E21G_RESCUE_H:
        tag, sc = scenario("supervised_strategic", "dte")
        sc = sc.with_(comms=dict(sc.comms, never_linked="rescue", rescue_h=h, rescue_scope="any"))
        tag.update(stage="G2", never_linked="rescue", rescue_h=h, rescue_scope="any")
        cells.append((tag, sc, MECH, *MECHS[MECH]))
    return cells


E21H_SERVICE_H = 1.0              # lunarsim.comms.DEFAULT_HELPER_SERVICE_H (Assumed: one intervention session)
E21H_CELLS = ((1, False, 24.0, 1.0), (1, False, 168.0, 1.0), (2, False, 24.0, 1.0), (1, True, 24.0, 1.0),
              (1, True, 168.0, 1.0), (1, False, 24.0, 2.0))      # (helpers, from the fleet, call threshold h, service h)


def e21h_cells():
    """Stage H (B-62): Stage G2 with the helper's own time: k helpers at BASE drive to the held sample's best parking
    point, wait for its link, serve and drive home (lunarsim/comms.py 'helpers'); dedicated (extra vehicles) or taken
    from the hauling fleet."""
    cells = []
    for k, fleet, h, svc in E21H_CELLS:
        tag, sc = scenario("supervised_strategic", "dte")
        sc = sc.with_(comms=dict(sc.comms, never_linked="rescue", rescue_h=h, rescue_scope="any",
                                 helpers={"n": k, "home": "BASE", "service_h": svc, "from_fleet": fleet}))
        n_fleet = tag["n_vehicles"]
        tag.update(stage="H", never_linked="rescue", rescue_h=h, rescue_scope="any", helpers_n=k,
                   helpers_from_fleet=bool(fleet), helpers_service_h=svc,
                   n_haulers=n_fleet - k if fleet else n_fleet, n_vehicles=n_fleet if fleet else n_fleet + k)
        cells.append((tag, sc, MECH, *MECHS[MECH]))
    return cells


def e21a2_cells():
    cells = []
    for mode, p in E21A2_COMMS:
        for mix in E21A2_MIXES:
            tag, sc = scenario(mix, mode, p)
            sc = sc.with_(comms=dict(sc.comms, operators_strict=True))
            tag.update(stage="A2", operators_strict=True)
            cells.append((tag, sc, MECH, *MECHS[MECH]))
    return cells


def e21d_cells():
    cells = []
    for mode, p in E21D_COMMS:
        for mix in E21D_MIXES:
            for sun in E21D_SUN:
                for yr in E21D_YEARS:
                    tag, sc = scenario(mix, mode, p)
                    if sun == "real":
                        sc = sc.with_(illumination={})              # defaults: criterion half, leg rule most
                    tag.update(stage="D", sun=sun, start_year=yr)
                    cells.append((tag, sc, MECH, *MECHS[MECH]))
    return cells


def monthly_delivered_t(sim, n: int = N_MONTHS) -> dict:
    """Tonnes delivered in each n-th of the year (deliveries inside the horizon)."""
    h = sim.sc.horizon_h
    t = np.array([c.t_delivered for c in sim.all_cargo if c.t_delivered is not None and c.t_delivered <= h])
    m = np.array([c.mass_kg for c in sim.all_cargo if c.t_delivered is not None and c.t_delivered <= h])
    hist, _ = np.histogram(t, bins=n, range=(0.0, h), weights=m)
    return {f"delivered_t_m{i + 1:02d}": float(v) / 1000.0 for i, v in enumerate(hist)}


# ---------------------------------------------------------------------------
# runs
# ---------------------------------------------------------------------------
def start_year(seed: int) -> int:
    return 2028 + int(seed) % 4


KEY_SKIP = ("exp", "n_vehicles", "n_operators", "rtt_s", "p_knee")      # derived columns, not part of a cell's identity


def e21_key(tag, mech_name) -> str:
    return cell_key({k: v for k, v in tag.items() if k not in KEY_SKIP}, mech_name)


def _job(args):
    """One replication: the cell's scenario with the seed's start year (common random numbers otherwise)."""
    tag, sc, mech_name, mech, kw, seed = args
    yr = int(tag["start_year"]) if "start_year" in tag else start_year(seed)     # stage D: the year is a cell factor
    sc = sc.with_(comms=dict(sc.comms, start_year=yr))
    t0 = time.time()
    sim = Simulation(sc, mech, seed=seed, mech_kwargs=dict(kw))
    out = sim.run()
    out["seed"] = seed
    out["start_year"] = yr
    out["run_s"] = round(time.time() - t0, 2)
    if tag.get("stage") == "D":
        out.update(monthly_delivered_t(sim))
    out["landings"] = len(sim.landing_schedule)
    out["delivered_t_in_year"] = out.get("delivered_kg_in_horizon", np.nan) / 1000.0
    out.update(tag)
    out["mechanism"] = mech_name
    out["cell"] = e21_key(tag, mech_name)
    return out


def parse_cells(spec, n):
    if not spec:
        return list(range(n))
    a, _, b = spec.partition("-")
    lo, hi = int(a), int(b or a)
    if not (0 <= lo <= hi < n):
        raise SystemExit(f"--cells {spec}: this stage has cells 0-{n - 1}")
    return list(range(lo, hi + 1))


def append_rows(path, rows):
    """Append rows keeping the file's column order; a new column rewrites the file, read with the exact float parser
    (pandas' default parser can be one ULP off, which would change rows already written)."""
    df = pd.DataFrame(rows)
    if not os.path.exists(path):
        df.to_csv(path, index=False)
        return
    cols = list(pd.read_csv(path, nrows=0).columns)
    if set(df.columns) - set(cols):
        old = pd.read_csv(path, float_precision="round_trip")
        pd.concat([old, df], ignore_index=True, sort=False).to_csv(path, index=False)
    else:
        df.reindex(columns=cols).to_csv(path, mode="a", header=False, index=False)


def run_stage(name, cells, seeds=N_SEEDS, workers=WORKERS, cells_spec=None, results=None, deadline=None):
    """Run the missing (cell, seed) rows of a stage. Every finished run is appended at once (a job that is killed
    keeps its finished rows; rerun to resume). deadline (time.time() value): no run is started that would, at the
    mean run time so far, end after it, and a worker pool still busy 20 s past it is terminated."""
    results = results or RESULTS
    path = os.path.join(results, f"{name}.csv")
    os.makedirs(results, exist_ok=True)
    sel = [cells[i] for i in parse_cells(cells_spec, len(cells))]
    done = set()
    if os.path.exists(path):
        old = pd.read_csv(path, usecols=["cell", "seed"])
        done = set(zip(old["cell"].astype(str), old["seed"].astype(int)))
    jobs = [(t, sc, mn, mf, kw, sd) for (t, sc, mn, mf, kw) in sel for sd in range(seeds)
            if (e21_key(t, mn), sd) not in done]
    n_done = len(done)
    print(f"[{name}] {len(sel)} of {len(cells)} cells x {seeds} seeds: {n_done} rows in the file, {len(jobs)} to run "
          f"on {workers} worker(s)", flush=True)
    t0 = time.time()
    took = []                                              # seconds per finished run

    def can_start():
        return deadline is None or time.time() + (sum(took) / len(took) if took else 0.0) < deadline

    def report(i):
        if i % 10 == 0 or i == len(jobs):
            el = time.time() - t0
            print(f"[{name}] {i}/{len(jobs)} runs, {el:.0f}s, ETA {el / i * (len(jobs) - i):.0f}s", flush=True)

    n_run = 0
    if jobs and workers <= 1:
        for job in jobs:
            if not can_start():
                break
            s = time.time()
            append_rows(path, [_job(job)])
            took.append(time.time() - s)
            n_run += 1
            report(n_run)
    elif jobs:
        from multiprocessing import Pool
        pending, running = list(jobs), []
        with Pool(workers) as pool:
            while pending or running:
                while pending and len(running) < workers and can_start():
                    running.append((pool.apply_async(_job, (pending.pop(0),)), time.time()))
                if not running:
                    break
                for r in [r for r in running if r[0].ready()]:
                    running.remove(r)
                    append_rows(path, [r[0].get()])
                    took.append(time.time() - r[1])
                    n_run += 1
                    report(n_run)
                if deadline is not None and time.time() > deadline + 20.0:
                    pool.terminate()
                    break
                time.sleep(0.2)
    if jobs:
        left = len(jobs) - n_run
        print(f"[{name}] {n_run} runs in {time.time() - t0:.0f}s -> {path}"
              + (f"; {left} left for the next chunk (time budget)" if left else ""), flush=True)
    return pd.read_csv(path)


def sfx(rnd: str) -> str:
    """File-name suffix of a round: '' for round 1, '_r2' for round 2."""
    if rnd not in ROUNDS:
        raise SystemExit(f"--round must be one of {ROUNDS}")
    return "" if rnd == "r1" else f"_{rnd}"


def load_raw(results=None, rnd: str = "r1") -> pd.DataFrame:
    results = results or RESULTS
    frames = [pd.read_csv(os.path.join(results, f"{n}{sfx(rnd)}.csv")) for n in STAGES.values()
              if os.path.exists(os.path.join(results, f"{n}{sfx(rnd)}.csv"))]
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


# ---------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------
def summary_table(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    for f in FACTORS:
        if f not in df.columns:
            df[f] = np.nan
    df["coverage"] = df["coverage"].fillna(-1.0)          # groupby drops NaN keys; -1 = no relay
    df["sun"] = df["sun"].fillna("night_fraction")
    df["sensitivity"] = df["sensitivity"].fillna("none")
    df["year"] = np.where(df["stage"] == "D", df.get("start_year", np.nan), -1)
    t = fit_law.cell_means(df, FACTORS, METRICS + [f"delivered_t_m{i + 1:02d}" for i in range(N_MONTHS)])
    t["coverage"] = t["coverage"].replace(-1.0, np.nan)
    t["year"] = t["year"].replace(-1, np.nan)
    return t


def breakeven_table(table: pd.DataFrame, metric="delivered_t_in_year") -> pd.DataFrame:
    """Gains over DTE only (all supervised, strict, no mast, +0 rovers) and their equivalents:
    the relay coverage with the same gain (interpolated on Stage A), the number of extra rovers with the same gain
    (interpolated on Stage B) and that many rovers' capital cost per year = the break-even relay price."""
    a = table[(table["stage"] == "A") & (table["comms"] != "always")]
    b = table[(table["stage"] == "B") & (table["comms"] == "dte")]
    sup = a[a["mix"] == "supervised_strict"].copy()
    sup["p"] = np.where(sup["comms"] == "dte", 0.0, sup["coverage"])
    relay = sup.groupby("p")[metric].mean().sort_index()
    if 0.0 not in relay.index:
        raise ValueError("Stage A lacks the DTE-only supervised-strict cell")
    base = relay.loc[0.0]
    rov = b[(b["mast"] == "none") & (b["policy"] == "strict")].groupby("extra_rovers")[metric].mean().sort_index()
    cls = VEHICLE_CLASSES[EXTRA_ROVER[1]]
    rover_musd_yr = cls.unit_cost_musd / cls.life_years

    def first_reach(xs, gains, target):
        """Smallest x whose gain reaches `target` on the monotone envelope, interpolated between grid points
        (nan when even the largest x falls short)."""
        g = np.maximum.accumulate(np.asarray(gains, float))
        xs = np.asarray(xs, float)
        if target <= g[0] + 1e-12:
            return float(xs[0])
        k = int(np.argmax(g >= target - 1e-12)) if (g >= target - 1e-12).any() else -1
        if k <= 0:
            return np.nan
        return float(xs[k - 1] + (target - g[k - 1]) / (g[k] - g[k - 1]) * (xs[k] - xs[k - 1]))

    def p_equiv(gain):
        return first_reach(relay.index.to_numpy(), (relay - base).to_numpy(), gain)

    def n_equiv(gain):
        if rov.empty:
            return np.nan
        return first_reach(rov.index.to_numpy(), (rov - rov.iloc[0]).to_numpy(), gain)

    rows = []

    def add(option, value):
        gain = float(value - base)
        n = n_equiv(gain)
        rows.append({"option": option, metric: float(value), "gain_vs_dte": gain, "relay_coverage_equiv": p_equiv(gain),
                     "extra_rovers_equiv": n, "relay_price_musd_per_yr_equiv": n * rover_musd_yr if np.isfinite(n) else np.nan})

    for p, v in relay.items():
        if p > 0:
            add(f"relay coverage {p:g}", v)
    for mix, label in (("supervised_strategic", "autonomy step: supervised strict -> strategic"),
                       ("autonomous", "autonomy step: supervised -> autonomous")):
        s = a[(a["mix"] == mix) & (a["comms"] == "dte")]
        if not s.empty:
            add(label, s[metric].mean())
    for n, v in rov.items():
        if n > 0:
            add(f"+{int(n)} supervised LTV", v)
    m = b[(b["mast"] != "none") & (b["policy"] == "strict") & (b["extra_rovers"] == 0)]
    if not m.empty:
        add("BASE mast 10 m", m[metric].mean())
    out = pd.DataFrame(rows)
    out.attrs["rover_musd_per_yr"] = rover_musd_yr
    return out


def write_tables(results=None, rnd: str = "r1"):
    results = results or RESULTS
    raw = load_raw(results, rnd)
    if raw.empty:
        print("[table] no E21 rows yet")
        return None
    t = summary_table(raw)
    t.to_csv(os.path.join(results, f"table_E21{sfx(rnd)}.csv"), index=False)
    print(f"[table_E21{sfx(rnd)}.csv] {len(t)} cells")
    if (t["stage"] == "B").any():
        be = breakeven_table(t)
        be.to_csv(os.path.join(results, f"table_E21_breakeven{sfx(rnd)}.csv"), index=False)
        print(f"[table_E21_breakeven{sfx(rnd)}.csv] {len(be)} rows (one LTV = {be.attrs['rover_musd_per_yr']:.0f} M$/yr)")
    return t


# ---------------------------------------------------------------------------
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("stages", nargs="*", help="e21a e21b e21c e21d e21a2 e21e e21f e21g e21g2 e21h table (default: e21a)")
    p.add_argument("--round", default="r1", choices=ROUNDS, help="r2 writes *_r2.csv (default r1: the round-1 files)")
    p.add_argument("--seeds", type=int, default=N_SEEDS)
    p.add_argument("--workers", type=int, default=WORKERS)
    p.add_argument("--cells", default=None, help="cell range of the stage, e.g. 0-9 (0-based, inclusive)")
    p.add_argument("--results", default=RESULTS)
    p.add_argument("--max-seconds", type=float, default=540.0,
                   help="stop this process after so many seconds (rows written so far are kept; rerun to resume)")
    a = p.parse_args(argv)
    if a.max_seconds and a.max_seconds > 0:
        faulthandler.dump_traceback_later(a.max_seconds, exit=True)
    names = [s.lower() for s in a.stages] or ["e21a"]
    t0 = time.time()
    # soft budget: stop starting runs 30 s before the hard stop (which stays as the backstop)
    dl = t0 + a.max_seconds - 30.0 if a.max_seconds and a.max_seconds > 60 else None
    go = lambda name, cells: run_stage(name, cells, a.seeds, a.workers, a.cells, a.results, deadline=dl)
    rnd, x = a.round, sfx(a.round)
    for n in names:
        if n == "e21a":
            go(STAGES[n] + x, e21a_cells(rnd))
        elif n == "e21b":
            t = write_tables(a.results, rnd)
            if t is not None and ((t["stage"] == "A") & (t["mix"] == "supervised_strict")).any():
                pk = knee_coverage(t)
                print(f"[e21b] knee of the supervised-strict coverage curve: p = {pk:g} ({KNEE_SHARE:.0%} of full "
                      f"coverage); stage B runs at p = {STAGE_B_COVERAGE:g}")
            go(STAGES[n] + x, e21b_cells(STAGE_B_COVERAGE, rnd))
        elif n == "e21c":
            go(STAGES[n] + x, e21c_cells())
        elif n == "e21d":
            go(STAGES[n] + x, e21d_cells())
        elif n == "e21a2":
            go(STAGES[n] + x, e21a2_cells())
        elif n in ("e21e", "e21f", "e21g", "e21g2", "e21h"):
            if rnd == "r1":
                raise SystemExit(f"stage {n} is a round-2 stage: add --round r2")
            name, cells = {"e21e": (STAGES["e21e"], e21e_cells), "e21f": (STAGE_F, e21f_cells),
                           "e21g": (STAGE_G, e21g_cells), "e21g2": (STAGE_G2, e21g2_cells), "e21h": (STAGE_H, e21h_cells)}[n]
            go(name + x, cells())
        elif n != "table":
            raise SystemExit(f"unknown stage {n!r}; choose from e21a e21b e21c e21d e21a2 e21e e21f e21g e21g2 e21h table")
        write_tables(a.results, rnd)
    rss = None
    try:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from terrain_assets import peak_rss_mb
        rss = peak_rss_mb()
    except Exception:
        pass
    print(f"done {names} in {time.time() - t0:.0f}s" + (f"; peak RSS {rss:.0f} MB" if rss else ""))


if __name__ == "__main__":
    main()
