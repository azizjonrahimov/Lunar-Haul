"""Assemble paper P3 ("The vehicles, the network and the market"): fill every {{P3-...}} placeholder, insert the
tables, write paper/p3/paper.html and render the PDF with headless Chrome.

    python paper/p3/build_p3.py [--no-pdf] [--allow-pending]

Sources (read-only): lunarsim/atc/vehicles-p5.json (the vehicle catalogue with flags and sources), one p5 scenario
(the fleet and the load factor), results/ATC_mesh.json (B-70's mesh summary), lunarsim/atc/regimes.py, messages.py,
radio.py and auction.py (the Assumed defaults), the two policy files (the learned bids' sizes), paper/atc/PREREG.md
(dated changes), paper/p3/NOTES.md (references), and the experiment files once they exist: results/E46_cells.csv,
results/E46_pairs.csv, results/E46_fit.json (B-76 REVISED; file names proposed in PLACEHOLDERS.md, not yet promised)
and results/E48_sizing.json (B-81). Until an experiment file exists every key that depends on it is pending and, with
--allow-pending, prints as a visible [[PENDING ...]] marker.

Sentences whose wording depends on the outcome (the H5 and H10 verdicts, every results paragraph, the discussion
clauses) are composed here from the data, with their direction words chosen from the numbers; every fixed phrase in
the parts that asserts a direction is checked against the data before the build goes on, and a failed check lists
every broken claim and stops. The build fails if any placeholder is left unfilled, if a filled value contains nan or
inf, if a placeholder in the parts is not documented in PLACEHOLDERS.md, or if the title is over 20 words.
"""
import argparse
import html
import json
import math
import os
import re
import subprocess
import sys
from typing import Any, Callable, Dict, List

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RES = os.path.join(ROOT, "results")
sys.path.insert(0, ROOT)
from lunarsim.atc import auction as AUC  # noqa: E402
from lunarsim.atc import messages as MSG  # noqa: E402
from lunarsim.atc import radio as RADIO  # noqa: E402
from lunarsim.atc import regimes as REG  # noqa: E402

PARTS = ["part1_front.html", "part2_related.html", "part3_methods.html", "part4_results.html", "part5_back.html"]
PDF = os.path.join(HERE, "vehicles_network_market_p3.pdf")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
MINUS, NB, PCT = "&minus;", "&nbsp;", "&#8239;%"
WORDS = {0: "no", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine"}

CATALOGUE = os.path.join(ROOT, "lunarsim", "atc", "vehicles-p5.json")
SCENARIO = os.path.join(ROOT, "data", "scenarios", "p5", "p5-3eq-L30-T10.json")     # the fleet of E46's equal cells
POLICY_LIN = os.path.join(ROOT, "data", "policies", "atc_bid_linear_v1.json")
POLICY_MLP = os.path.join(ROOT, "data", "policies", "atc_bid_v1.json")
PREREG = os.path.join(ROOT, "paper", "atc", "PREREG.md")
E46_CELLS, E46_PAIRS, E46_FIT = (os.path.join(RES, f) for f in ("E46_cells.csv", "E46_pairs.csv", "E46_fit.json"))
E48 = os.path.join(RES, "E48_sizing.json")
RULES = ("none", "second", "posted")          # payment rules of B-76 REVISED, in the order of the text
RULE_NAME = {"none": "no payments", "second": "the per-item second price", "posted": "the posted price with Shapley sharing"}
SPLITS = ("3eq", "3uneq")
SPLIT_NAME = {"3eq": "equal shares", "3uneq": "50/35/15 shares"}
CLASSES = ("LTV1", "CARGO", "SMALL", "HOPPER", "BASE")   # E48 classes, in the order of Table 3
CLASS_NAME = {"LTV1": "crew rover", "CARGO": "cargo rover", "SMALL": "small rover", "HOPPER": "hopper",
              "BASE": "base computer"}


# ---------------------------------------------------------------------------------------------------------
# formatting
# ---------------------------------------------------------------------------------------------------------
def _fin(x):
    x = float(x)
    if not math.isfinite(x):
        raise ValueError(f"non-finite value {x} reached a number format")
    return x


def num(x, nd=0, sign=False):
    x = _fin(x)
    s = f"{abs(x):,.{nd}f}"
    zero = float(s.replace(",", "")) == 0
    return (MINUS if (x < 0 and not zero) else ("+" if sign and not zero else "")) + s


def unit(x, u, nd=0, sign=False):
    return f"{num(x, nd, sign)}{NB}{u}"


def pc(x, nd=1, sign=False):
    """x is a share (0-1), printed in percent."""
    return f"{num(100 * _fin(x), nd, sign)}{PCT}"


def ci(lo, hi, nd=1, u=""):
    uu = f"{NB}{u}" if u else ""
    return f"[{num(lo, nd)}, {num(hi, nd)}{uu}]"


def cnt(x):
    return num(x, 0)


def words(n):
    return WORDS.get(int(n), f"{int(n):,}")


class Pending(Exception):
    pass


def _need(path, what):
    if not os.path.exists(path):
        raise Pending(f"{what} ({os.path.relpath(path, ROOT)}) has not landed")


def _get(d, *keys):
    """Walk a nested dict; a missing key is a Pending (the file exists but lacks the field), named precisely."""
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            raise Pending(f"field {'.'.join(map(str, keys))} missing from the file")
        d = d[k]
    return d


# ---------------------------------------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------------------------------------
class R:
    def __init__(self):
        jl = lambda f: json.load(open(f, encoding="utf-8"))
        self.cat = jl(CATALOGUE)
        self.scn = jl(SCENARIO)
        self.mesh = jl(os.path.join(RES, "ATC_mesh.json"))
        self.lin = jl(POLICY_LIN)
        self.mlp = jl(POLICY_MLP)
        self.prereg = open(PREREG, encoding="utf-8").read()
        self.e48 = jl(E48) if os.path.exists(E48) else None
        self.e46c = pd.read_csv(E46_CELLS) if os.path.exists(E46_CELLS) else None
        self.e46p = pd.read_csv(E46_PAIRS) if os.path.exists(E46_PAIRS) else None
        self.e46f = jl(E46_FIT) if os.path.exists(E46_FIT) else None

    # --- catalogue -------------------------------------------------------------------------------------------
    def param(self, cls, key):
        return self.cat["classes"][cls]["params"][key]

    def fleet(self):
        """(owner, class id) per vehicle of the scenario's fleet."""
        return [(row[0], row[1]) for row in self.scn["fleet"]]

    # --- E48 ---------------------------------------------------------------------------------------------------
    def s48(self, *keys):
        if self.e48 is None:
            raise Pending("E48 (B-81, results/E48_sizing.json) has not run")
        return _get(self.e48, *keys)

    # --- E46 ---------------------------------------------------------------------------------------------------
    def f46(self, *keys):
        if self.e46f is None:
            raise Pending("E46 (B-76, results/E46_fit.json) has not run")
        return _get(self.e46f, *keys)

    def cell46(self, rule, split, k=1.0, q=0):
        if self.e46c is None:
            raise Pending("E46 (B-76, results/E46_cells.csv) has not run")
        c = self.e46c
        g = c[(c["rule"] == rule) & (c["split"] == split) & (np.isclose(c["k"], k)) & (np.isclose(c["q"], q))]
        if len(g) == 0:
            raise Pending(f"E46 cell {rule} {split} k={k} q={q} has no runs yet")
        if len(g) > 1:
            raise KeyError(f"E46 cell {rule} {split} k={k} q={q}: {len(g)} rows")
        return g.iloc[0].to_dict()

    def pair46(self, comparison, metric):
        if self.e46p is None:
            raise Pending("E46 (B-76, results/E46_pairs.csv) has not run")
        g = self.e46p[(self.e46p["comparison"] == comparison) & (self.e46p["metric"] == metric)]
        if len(g) != 1:
            raise KeyError(f"E46 pairs row {comparison!r} on {metric}: {len(g)} rows")
        row = g.iloc[0].to_dict()
        if int(row["n"]) == 0 or not np.isfinite(row["mean"]):
            raise Pending(f"{comparison} has no paired runs yet")
        return row


# ---------------------------------------------------------------------------------------------------------
# values
# ---------------------------------------------------------------------------------------------------------
def values(r: R, allow_pending: bool):
    V: Dict[str, str] = {}
    pending: List[str] = []
    broken: List[str] = []

    def check(cond, claim):
        if not cond:
            broken.append(claim)

    def fill(key, fn: Callable[[], str], tag):
        try:
            V[key] = fn()
        except Pending as e:
            if not allow_pending:
                raise SystemExit(f"{key}: pending ({e}); rerun with --allow-pending to build a draft")
            pending.append(f"{key}: {e}")
            V[key] = f'<span class="pending">[[PENDING {tag}]]</span>'

    # --- the vehicles (3.2) ---------------------------------------------------------------------------------------
    classes = r.cat["classes"]
    fleet = r.fleet()
    in_fleet = sorted({c for _, c in fleet}, key=list(classes).index)
    V["P3-N-CLASSES"] = words(len(classes))
    V["P3-N-CLASSES-FLEET"] = words(len(in_fleet)).capitalize()
    V["P3-N-FLEET"] = words(len(fleet))
    V["P3-N-OWNERS"] = words(len({o for o, _ in fleet}))
    check(len(in_fleet) == len(classes) - 1 and "HOPPER_MICRONOVA" not in in_fleet,
          "the Micro-Nova is the one catalogue class in no simulated fleet")
    V["P3-K30"] = f"{_fin(r.scn['p5']['k']):.3f}"
    V["P3-CLV1-PAYLOAD-KG"] = unit(r.param("LTV1_CLV1", "capacity_kg")["value"], "kg")
    V["P3-CLV1-RANGE-KM"] = unit(r.param("LTV1_CLV1", "range_km_per_charge")["value"], "km")
    check(r.param("LTV1_CLV1", "capacity_kg")["value"] == r.param("LTV1_PEGASUS", "capacity_kg")["value"],
          "both Phase-1 rovers carry the same stated payload")
    caps = {c: float(r.param(c, "capacity_kg")["value"]) for c in in_fleet}
    V["P3-CAP-MAX-SINGLE-KG"] = unit(max(caps.values()), "kg")
    lifters = sorted((caps[c] for c in in_fleet if r.param(c, "can_team_lift")["value"]), reverse=True)
    check(len(lifters) >= 2, "at least two fleet classes can join a team lift")
    V["P3-CAP-MAX-PAIR-KG"] = unit(lifters[0] + lifters[1], "kg")
    V["P3-CAP-FLEET-SUM-KG"] = unit(sum(caps[c] for _, c in fleet), "kg")
    check(lifters[0] + lifters[1] > max(caps.values()), "a pair lifts more than the largest single vehicle")
    V["P3-N-COALITION-RUNS"] = words(2 ** len({o for o, _ in fleet}))

    # --- the network (3.3) ------------------------------------------------------------------------------------------
    m = r.mesh
    V["P3-MESH-N-POINTS"] = cnt(m["n_points"])
    los = m["los_by_distance_band"]
    V["P3-MESH-LOS-25-0TO05"] = pc(los["2.5-2.5"]["0-0.5 km"]["los_0m"], 1)
    V["P3-MESH-LOS-25-2TO5"] = pc(los["2.5-2.5"]["2-5 km"]["los_0m"], 1)
    V["P3-MESH-LOS-10-2TO5"] = pc(los["1.0-1.0"]["2-5 km"]["los_0m"], 1)
    check(los["2.5-2.5"]["0-0.5 km"]["los_0m"] > los["2.5-2.5"]["2-5 km"]["los_0m"] > los["1.0-1.0"]["2-5 km"]["los_0m"],
          "line of sight falls with distance and with antenna height (abstract, 3.3)")
    md = m["mast_direct"]["rover_2.5m"]
    direct = (m["n_points"] - md["n_no_direct_los"]) / m["n_points"]
    V["P3-MESH-MAST-DIRECT-SHARE"] = pc(direct, 1)
    wk = md["within_km"]
    bands = sorted(wk, key=lambda s: float(s.split()[0]))
    grow = [b for i, b in enumerate(bands) if i == 0 or wk[b]["n"] > wk[bands[i - 1]]["n"]]
    V["P3-MESH-MAST-DIRECT-MAX-KM"] = f"{float(grow[-1].split()[0]):g}{NB}km"
    check(abs(wk[bands[-1]]["share_of_points"] - direct) < 0.002, "the mast's direct share agrees with the band table")
    check(0.10 < direct < 0.30, "the mast sees 10-30 % of the points directly (comparison with the viewsheds of [16])")
    conn = m["connectivity"]["rover_2.5m"]
    V["P3-MESH-COMPONENTS-2KM"] = words(conn["2 km"]["components"])
    check(conn["2 km"]["components"] == 1 and conn["5 km"]["components"] == 1, "rovers form one network from 2 km range")
    rng_km = RADIO.DEFAULT_D_MAX_M / 1000.0
    key = f"{rng_km:g} km"
    check(key in conn, "the radio range of radio.py is one of the mesh summary's ranges")
    V["P3-RADIO-RANGE-KM"] = f"{rng_km:g}{NB}km"
    V["P3-MESH-REACH-1HOP"] = pc(conn[key]["reach_base_share"]["1 hop"], 1)
    V["P3-MESH-REACH-2HOPS"] = pc(conn[key]["reach_base_share"]["2 hops"], 1)
    V["P3-MESH-MAX-HOPS-5KM"] = words(conn[key]["max_hops"])
    V["P3-MESH-MEDIAN-HOPS-5KM"] = words(conn[key]["median_hops"])
    check(conn[key]["reach_base_share"]["never"] == 0, "every rover point reaches the mast at the default range")
    small = m["connectivity"]["small_1.0m"]
    V["P3-MESH-SMALL-ISOLATED"] = words(m["isolated"]["small_1.0m"]["n"])
    V["P3-MESH-SMALL-MAX-HOPS"] = words(small[key]["max_hops"])
    check(m["isolated"]["small_1.0m"]["n"] > 0 and m["isolated"]["rover_2.5m"]["n"] == 0,
          "small robots, not rovers, leave isolated points")

    # --- the Assumed defaults of the code (3.3, 3.4, 3.5) ----------------------------------------------------------
    D = REG.DEFAULTS
    V["P3-HOP-LATENCY-MS"] = unit(MSG.HOP_LATENCY_S * 1000, "ms")
    V["P3-MEAN-BURST"] = cnt(MSG.MEAN_BURST)
    V["P3-BASE-MTBF-H"] = unit(D["base_mtbf_h"], "h")
    V["P3-BASE-REPAIR-H"] = unit(D["base_repair_h"], "h")
    V["P3-REELECT-MIN"] = unit(D["reelect_h"] * 60, "min")
    V["P3-TIMEOUT-H"] = unit(AUC.TIMEOUT_H, "h")

    # the same counts as build_p1.py: the linear model's weights (one per observation, bias apart), the network's
    # weights and biases together
    lin_w = np.asarray(r.lin["layers"][0]["w"]).ravel()
    check(len(r.lin["layers"]) == 1 and len(lin_w) == len(r.lin["obs"]["names"]), "the linear policy has one weight per observation")
    V["P3-LIN-N-WEIGHTS"] = cnt(len(lin_w))
    mlp_n = sum(np.asarray(L["w"]).size + np.asarray(L["b"]).size for L in r.mlp["layers"])
    V["P3-MLP-N-PARAMS"] = f"{mlp_n:,}"
    check(mlp_n > 50 * len(lin_w), "the network has far more parameters than the linear model")

    # --- pre-registration: changes after this draft that name E46 or E48 (4.6) ------------------------------------
    changes = re.findall(r"^### (Change \d+, .+?)$", r.prereg, re.M)
    later = [c for c in changes if re.search(r"\bE4[68]\b|\bH5\b|\bH10\b|first-price", c) and
             not c.startswith("Change 1,")]
    V["P3-CHANGES-SENTENCE"] = ("No other choice was made after looking at data." if not later else
                                "Later dated changes of [59] that touch this paper: " +
                                "; ".join(html.escape(c) for c in later) + ".")

    # --- checks (3.6, 5.8) -------------------------------------------------------------------------------------------
    fill("P3-CHECKS-SENTENCE", lambda: (_ for _ in ()).throw(Pending("B-79 batch 3 (payments, failover checks) has not landed")),
         "B-79")
    fill("P3-FAILED-CHECKS-SENTENCE", lambda: (_ for _ in ()).throw(Pending("the check outcomes come from results/vv_phase5.json (B-79)")),
         "B-79")

    # --- E48 -----------------------------------------------------------------------------------------------------------
    def e48_scaled():
        """Scaled values against capacities; the direction words come from here."""
        fl, tg = r.s48("flight"), r.s48("targets")
        f, (flo, fhi) = float(fl["factor"]), fl["factor_range"]
        robots, hz = int(tg["robots"]), float(tg["safety_hz"])
        out = {"factor": f, "range": (float(flo), float(fhi)), "processor": fl["processor"], "laptop": r.s48("laptop", "processor")}
        worst_cpu, worst_cls = 0.0, None
        for c in CLASSES:
            cl = r.s48("classes", c)
            if c == "BASE":
                continue
            share = _fin(cl["cpu_safety_check_us"]["p99"]) * 1e-6 * f * hz     # one core, one robot, at the safety rate
            if share > worst_cpu:
                worst_cpu, worst_cls = share, c
        out["cpu_share_worst"], out["cpu_class_worst"] = worst_cpu, worst_cls
        out["mem_worst_mb"] = max(_fin(r.s48("classes", c)["peak_memory_mb"]) for c in CLASSES if c != "BASE") * 1.0
        out["mem_capacity_mb"] = _fin(fl["memory_mb"])
        bph = r.s48("messages", "bytes_per_robot_hour")
        out["kbps_20"] = _fin(bph["1"]) * robots * 8 / 3600.0 / 1000.0
        out["kbps_target"] = _fin(tg["link_kbps_20_robots"])
        out["bps_robot"] = _fin(bph["1"]) / 3600.0
        out["bps_target"] = _fin(tg["bytes_per_s_per_robot"])
        out["fits"] = {"cpu": worst_cpu < 1.0, "memory": out["mem_worst_mb"] * f <= out["mem_capacity_mb"],
                       "link": out["kbps_20"] <= out["kbps_target"]}
        return out

    def h10_sentence():
        s = e48_scaled()
        fits = s["fits"]
        parts = [f"the safety check at {num(s['cpu_share_worst'] * 100, 1)}{PCT} of one core of the reference processor at the worst class "
                 f"(the {CLASS_NAME[s['cpu_class_worst']]})",
                 f"the on-robot part at {unit(s['mem_worst_mb'] * s['factor'], 'MB', 1)} of {unit(s['mem_capacity_mb'], 'MB')}",
                 f"and the radio traffic at {num(s['kbps_20'], 2)}{NB}kbit/s for 20 robots against the {num(s['kbps_target'], 0)}{NB}kbit/s target"]
        verdict = ("H10, exploratory, holds on every count: " if all(fits.values()) else
                   "H10, exploratory, does not hold on every count (" + ", ".join(k for k, v in fits.items() if not v) + " over the limit): ")
        return verdict + ", ".join(parts) + f", with the scaling factor at {num(s['factor'], 1)} (range {num(s['range'][0], 1)}&ndash;{num(s['range'][1], 1)})."
    fill("P3-H10-VERDICT-SENTENCE", h10_sentence, "E48")

    def e48_cpu():
        s = e48_scaled()
        bits = []
        for c in CLASSES:
            cl = r.s48("classes", c)
            if c == "BASE":
                a = cl["cpu_auction_round_ms"]
                bits.append(f"the base computer's auction round took {unit(a['median'], 'ms', 2)} at the median and {unit(a['p99'], 'ms', 1)} "
                            f"at the 99th percentile over {cnt(a['n'])} rounds at today's fleet")
                continue
            sc, a = cl["cpu_safety_check_us"], cl["cpu_auction_round_ms"]
            bits.append(f"on the {CLASS_NAME[c]} a safety check took {unit(sc['median'], '&micro;s', 1)} at the median and "
                        f"{unit(sc['p99'], '&micro;s', 1)} at the 99th percentile over {cnt(sc['n'])} calls, an auction round "
                        f"{unit(a['median'], 'ms', 2)} and {unit(a['p99'], 'ms', 1)}, and the on-robot part peaked at {unit(cl['peak_memory_mb'], 'MB', 1)}")
        return (f"Measured on {html.escape(s['laptop'])} and scaled to the {html.escape(s['processor'])} by a factor of {num(s['factor'], 1)} "
                f"(range {num(s['range'][0], 1)}&ndash;{num(s['range'][1], 1)}, Assumed): " + "; ".join(bits) + ".")
    fill("P3-E48-RESULTS-CPU", e48_cpu, "E48")

    def e48_messages():
        s = e48_scaled()
        bt = r.s48("messages", "bytes_per_type")
        mph, bph = r.s48("messages", "per_robot_hour"), r.s48("messages", "bytes_per_robot_hour")
        led = r.s48("ledger_mb_per_year")
        types = "; ".join(f"{html.escape(k)} {unit(v, 'B')}" for k, v in bt.items())
        return (f"As serialised, the message types weigh: {types}. The runs generated {num(mph['1'], 1)} messages and "
                f"{unit(bph['1'], 'B', 0)} per robot-hour at today's fleet, {num(mph['4'], 1)} and {unit(bph['4'], 'B', 0)} at four times, "
                f"and {num(mph['8'], 1)} and {unit(bph['8'], 'B', 0)} at eight times; at today's fleet that is {num(s['bps_robot'], 1)}{NB}B/s per robot "
                f"against the {num(s['bps_target'], 0)}{NB}B/s target and {num(s['kbps_20'], 2)}{NB}kbit/s for 20 robots against {num(s['kbps_target'], 0)}{NB}kbit/s. "
                f"The ledger held {unit(led['1'], 'MB', 1)} after a year at today's fleet, {unit(led['4'], 'MB', 1)} at four times and {unit(led['8'], 'MB', 1)} at eight.")
    fill("P3-E48-RESULTS-MESSAGES", e48_messages, "E48")

    def e48_link():
        bits = []
        for c in CLASSES:
            lk = r.s48("classes", c, "link")
            bits.append(f"the {CLASS_NAME[c]} (antenna {unit(lk['antenna_m'], 'm', 1)}, {num(lk['freq_ghz'], 1)}{NB}GHz, {unit(lk['tx_power_w'], 'W', 1)}) "
                        f"had {num(lk['worst_hop_kbps'], 1)}{NB}kbit/s at its worst hop, a latency budget of {unit(lk['latency_budget_ms'], 'ms')} "
                        f"for a decision within 1{NB}s, and was reachable from the mast {pc(lk['reachable_share'], 1)} of the time")
        return "Per class, under the models of Section 3.3: " + "; ".join(bits) + "."
    fill("P3-E48-RESULTS-LINK", e48_link, "E48")

    def e48_failover():
        fo = r.s48("failover")
        levels = [str(x) for x in fo["mtbf_levels_h"]]
        bits, twice = [], 0
        for lv in levels:
            b = fo["by_mtbf"][lv]
            twice += int(b["jobs_assigned_twice"])
            bits.append(f"at an MTBF of {unit(float(lv), 'h')} the base computer was down {pc(b['down_share'], 2)} of the time, the fleet had no leader "
                        f"{pc(b['no_leader_share'], 2)} of the time, re-election took {unit(b['reelect_s'], 's', 0)} and the ledger merged {cnt(b['merges'])} times")
        check(twice == 0, "no job was assigned twice after a merge (3.4, 3.6)")
        return "; ".join(bits).capitalize() + f". After every merge the ledger held {words(twice)} job assigned twice."
    fill("P3-E48-RESULTS-FAILOVER", e48_failover, "E48")

    def e48_design():
        ru = r.s48("runs")
        return (f"{cnt(ru['n'])} runs were instrumented, at {', '.join(str(x) for x in ru['multiples'])} times today's fleet.")
    fill("P3-E48-DESIGN-SENTENCE", e48_design, "E48")
    fill("P3-E48-COMPUTE-SENTENCE", lambda: f"The instrumented runs of E48 took {unit(r.s48('runs', 'run_s_mean'), 's', 0)} each on average and "
         f"{unit(r.s48('runs', 'cpu_h'), 'h', 1)} of processor time in all.", "E48")

    def e48_clause(kind):
        s = e48_scaled()
        fits_all = all(s["fits"].values())
        ok = "fits" if fits_all else "does not fit"
        if kind == "abstract":
            return (f"Scaled by a factor of {num(s['factor'], 1)}, the on-vehicle software {ok} the reference flight processor: the safety check "
                    f"takes {num(s['cpu_share_worst'] * 100, 1)}{PCT} of one core at the worst class and the radio traffic is {num(s['kbps_20'], 2)}{NB}kbit/s for 20 robots.")
        if kind == "intro":
            return (f"Lunar ATC {ok} the vehicles of Section 3.2 as implemented: at the worst class the safety check takes "
                    f"{num(s['cpu_share_worst'] * 100, 1)}{PCT} of one core of the reference processor, the on-robot part {unit(s['mem_worst_mb'] * s['factor'], 'MB', 1)}, "
                    f"and 20 robots generate {num(s['kbps_20'], 2)}{NB}kbit/s against a 16{NB}kbit/s-class link (Sections 5.1 to 5.3).")
        if kind == "discussion":
            return (f"the on-vehicle software {ok} the reference processor and the link class with the stated factor; the class nearest a limit is the "
                    f"{CLASS_NAME[s['cpu_class_worst']]}.")
        if kind == "comparison":
            bph = r.s48("messages", "bytes_per_robot_hour")
            ratio = 13800.0 / max(_fin(bph["1"]) / 3600.0, 1e-9)
            return (f"The radio traffic of Lunar ATC, {num(s['bps_robot'], 1)}{NB}B/s per robot, is {num(ratio, 0)} times smaller than the "
                    f"13.8{NB}kB/s the two-rover convoy controller of [25] used, because a market exchanges decisions and a convoy exchanges state.")
        if kind == "conclusion":
            return (f"Scaled to flight hardware, the software {ok} the reference processor and a 16{NB}kbit/s-class link for 20 robots.")
        if kind == "limitation":
            return (f"The factor used is {num(s['factor'], 1)} (range {num(s['range'][0], 1)}&ndash;{num(s['range'][1], 1)}), from "
                    f"{html.escape(s['laptop'])} to the {html.escape(s['processor'])}.")
        raise KeyError(kind)
    for kind, key in (("abstract", "P3-E48-ABSTRACT-CLAUSE"), ("intro", "P3-E48-INTRO-CLAUSE"), ("discussion", "P3-E48-DISCUSSION-CLAUSE"),
                      ("comparison", "P3-E48-COMPARISON-CLAUSE"), ("conclusion", "P3-E48-CONCLUSION-CLAUSE"),
                      ("limitation", "P3-E48-LIMITATION-SENTENCE")):
        fill(key, lambda kind=kind: e48_clause(kind), "E48")

    def e48_status():
        r.s48("runs")                      # pending while the file is absent; lists missing fields once it exists
        missing = []
        for c in CLASSES:
            for fld in ("cpu_safety_check_us", "cpu_auction_round_ms", "peak_memory_mb", "link"):
                if c == "BASE" and fld in ("cpu_safety_check_us", "link"):
                    continue
                try:
                    r.s48("classes", c, fld)
                except Pending:
                    missing.append(f"{fld} for the {CLASS_NAME[c]}")
        for fld in (("messages", "bytes_per_type"), ("messages", "per_robot_hour"), ("ledger_mb_per_year",), ("failover",)):
            try:
                r.s48(*fld)
            except Pending:
                missing.append(".".join(fld))
        return "Every measurement of Section 4.2 was made." if not missing else \
            "E48 did not make these measurements of Section 4.2: " + "; ".join(html.escape(x) for x in missing) + "."
    fill("P3-E48-STATUS-SENTENCE", e48_status, "E48")

    # --- E46 -----------------------------------------------------------------------------------------------------------
    fill("P3-E46-N-RUNS", lambda: cnt(r.f46("n_rows")), "E46")

    def e46_design():
        d = r.f46("design")
        return (f"{cnt(r.f46('n_rows'))} runs in {cnt(r.f46('n_cells'))} cells, with {cnt(len(d['seeds']))} seeds per cell"
                + (", including a first-price cell added as a dated change of [59]" if "first" in d["rules"] else
                   ", with no first-price cell (Section 4.1)") + ".")
    fill("P3-E46-DESIGN-SENTENCE", e46_design, "E46")
    fill("P3-E46-COMPUTE-SENTENCE", lambda: f"A simulated year of E46 took {unit(r.f46('run_s_mean'), 's', 0)} on average and the experiment "
         f"{unit(r.f46('cpu_h'), 'h', 1)} of processor time.", "E46")

    def sign_word(x, pos="a surplus", neg="a deficit", zero="a balanced budget"):
        return pos if x > 0 else (neg if x < 0 else zero)

    def e46_rules():
        bits = []
        for rule in RULES:
            for split in SPLITS:
                c = r.cell46(rule, split)
                bits.append(f"under {RULE_NAME[rule]} with {SPLIT_NAME[split]} the market lost {pc(c['efficiency_loss_vs_oracle'], 1)} of the oracle's urgent wait, "
                            f"the operator ran {sign_word(c['budget_per_year'])} of {unit(abs(c['budget_per_year']), 'units', 0)} a year, "
                            f"{unit(c['settled_earth'], 'units', 0)} were settled on Earth and {unit(c['open_end'], 'units', 0)} left open at the year's end")
        none_eq = r.cell46("none", "3eq")
        check(abs(none_eq["efficiency_loss_vs_oracle"]) < 1e-9 or none_eq.get("identical_to_pooled", 0) == 1,
              "the none rule is the pooled regime of [60] (3.6)")
        return "; ".join(bits).capitalize() + " (Table 7)."
    fill("P3-E46-RESULTS-RULES", e46_rules, "E46")

    def e46_ir():
        bits, viol = [], 0
        for rule in RULES:
            for split in SPLITS:
                c = r.cell46(rule, split)
                viol += int(c["ir_violations"])
                owners = []
                for o in "ABC":
                    p = r.pair46(f"IR: {rule} - alone, {split}, owner {o}", "profit")
                    owners.append(f"owner {o} {unit(p['mean'], 'units', 0, sign=True)} {ci(p['lo'], p['hi'], 0)}")
                bits.append(f"under {RULE_NAME[rule]} with {SPLIT_NAME[split]}: " + ", ".join(owners))
        return ("Each owner's market profit less its alone profit on the same seeds was, " + "; ".join(bits) +
                f". The market made an owner worse off than alone in {cnt(viol)} owner-seed pairs over every rule and split (Table 8).")
    fill("P3-E46-RESULTS-IR", e46_ir, "E46")

    def e46_manip():
        bits = []
        for rule in [x for x in ("first", "second", "posted") if x in r.f46("max_gain")]:
            g = r.f46("max_gain", rule)
            name = "first price" if rule == "first" else RULE_NAME[rule]
            bits.append(f"under {name} the largest gain from scaling was {unit(g['gain'], 'units', 0, sign=True)} {ci(g['lo'], g['hi'], 0)} "
                        f"for owner {html.escape(str(g['owner']))} at k = {num(g['k'], 2)}, and that deviation changed the fleet's urgent wait by "
                        f"{unit(g['system_cost_h'], 'h', 2, sign=True)} {ci(g['lo_cost'], g['hi_cost'], 2)}")
        return "; ".join(bits).capitalize() + "."
    fill("P3-E46-RESULTS-MANIP", e46_manip, "E46")

    def e46_audits():
        bits = []
        au = r.f46("audits")
        for rule in [x for x in ("first", "second", "posted") if x in au]:
            name = "first price" if rule == "first" else RULE_NAME[rule]
            qs = ", ".join(f"at q = {q}{PCT} {pc(au[rule][q]['recovered_share'], 0)} of the gain, leaving {unit(au[rule][q]['net_gain'], 'units', 0, sign=True)} net of penalties"
                           for q in ("0", "5", "20"))
            bits.append(f"under {name} the audits recovered {qs}")
        return "; ".join(bits).capitalize() + "."
    fill("P3-E46-RESULTS-AUDITS", e46_audits, "E46")

    def h5_sentence(kind="full"):
        h = r.f46("H5")
        c1, c2, c3 = h["clause1"], h["clause2"], h["clause3"]
        w = lambda c: ("not tested" if not c.get("tested", True) else ("supported" if c["supported"] else "not supported"))
        s1, s2, s3 = w(c1), w(c2), w(c3)
        if kind == "full":
            return (f"H5 clause by clause: that first-price bids reward shading is {s1}; that the per-item second price reduces the largest gain is {s2}; "
                    f"that the posted price with Shapley sharing leaves no owner worse off than alone in any tested coalition is {s3}"
                    f" (smallest lower bound {unit(c3['min_lower'], 'units', 0, sign=True)}).")
        if kind == "abstract":
            return (f"Posted prices with Shapley sharing {'left' if c3['supported'] else 'did not leave'} every owner at least as well off as alone; "
                    f"the first-price clauses of H5 were {s1 if s1 == 'not tested' else ('supported' if c1['supported'] else 'not supported')}.")
        if kind == "intro":
            return (f"H5's Shapley clause is {s3} and its first-price clauses are {s1} (Section 5.7).")
        raise KeyError(kind)
    fill("P3-H5-VERDICT-SENTENCE", h5_sentence, "E46")
    fill("P3-H5-ABSTRACT-CLAUSE", lambda: h5_sentence("abstract"), "E46")
    fill("P3-H5-INTRO-CLAUSE", lambda: h5_sentence("intro"), "E46")

    def e46_clause(kind):
        h = r.f46("H5")
        ir_ok = [rule for rule in RULES if all(int(r.cell46(rule, s)["ir_violations"]) == 0 for s in SPLITS)]
        budgets = {rule: r.cell46(rule, "3eq")["budget_per_year"] for rule in RULES}
        mg = r.f46("max_gain")
        if kind == "abstract":
            return (f"{', '.join(RULE_NAME[x] for x in ir_ok).capitalize() if ir_ok else 'No rule'} left every owner at least as well off as alone; "
                    f"the largest gain from scaling bids was {unit(max(g['gain'] for g in mg.values()), 'units', 0, sign=True)}.")
        if kind == "intro":
            return (f"In the market, {', '.join(RULE_NAME[x] for x in ir_ok) if ir_ok else 'no rule'} made every owner at least as well off as alone "
                    f"in both splits; the operator ran {sign_word(budgets['second'])} under the second price and {sign_word(budgets['posted'])} under the posted price (Sections 5.5 to 5.7).")
        if kind == "discussion":
            return (f"{', '.join(RULE_NAME[x] for x in ir_ok).capitalize() if ir_ok else 'no rule'} left every owner at least as well off as alone; "
                    f"the operator ran {sign_word(budgets['second'])} under the second price and {sign_word(budgets['posted'])} under the posted price; "
                    f"the largest gain from scaling was {unit(max(g['gain'] for g in mg.values()), 'units', 0, sign=True)} and the audits at 20{PCT} "
                    f"{'removed' if all(r.f46('audits', k, '20')['net_gain'] <= 0 for k in mg) else 'did not remove'} it.")
        if kind == "comparison":
            small = r.pair46("IR: posted - alone, 3uneq, owner C", "profit")
            return (f"The smallest owner of the 50/35/15 split {'gained' if small['lo'] > 0 else ('lost' if small['hi'] < 0 else 'neither gained nor lost')} "
                    f"under the posted price with Shapley sharing ({unit(small['mean'], 'units', 0, sign=True)} {ci(small['lo'], small['hi'], 0)}), "
                    f"where Kondor's smallest operator paid the largest fleet penalty [39]; the operator's budget under the second price was "
                    f"{sign_word(budgets['second'])}, as the theory of truthful mechanisms predicts [29, 30].")
        if kind == "implication":
            return (f"{', '.join(RULE_NAME[x] for x in ir_ok) if ir_ok else 'no rule'} kept every owner in; the budget was {sign_word(budgets['posted'])} "
                    f"under the posted price and {sign_word(budgets['second'])} under the second price.")
        if kind == "conclusion":
            return (f"Under {', '.join(RULE_NAME[x] for x in ir_ok) if ir_ok else 'no rule'} every owner was at least as well off as alone, and the largest "
                    f"gain from scaling bids was {unit(max(g['gain'] for g in mg.values()), 'units', 0, sign=True)}.")
        raise KeyError(kind)
    for kind, key in (("abstract", "P3-E46-ABSTRACT-CLAUSE"), ("intro", "P3-E46-INTRO-CLAUSE"), ("discussion", "P3-E46-DISCUSSION-CLAUSE"),
                      ("comparison", "P3-E46-COMPARISON-CLAUSE"), ("implication", "P3-E46-IMPLICATION-CLAUSE"),
                      ("conclusion", "P3-E46-CONCLUSION-CLAUSE")):
        fill(key, lambda kind=kind: e46_clause(kind), "E46")

    def e46_status():
        short = r.f46("short_cells")
        return "Every cell of E46 ran all its seeds." if not short else \
            "; ".join(f"the cell {html.escape(s['label'])} has {cnt(s['have'])} of {cnt(s['n'])} seeds" for s in short).capitalize() + "."
    fill("P3-E46-STATUS-SENTENCE", e46_status, "E46")

    V["P3-REFERENCES"] = references()
    T = {"vehicles": table_vehicles(r, in_fleet)}
    for name, tag, caption in (("E48_sizing", "E48", "Table 5, sizing per vehicle class"), ("E48_link", "E48", "Table 6, link budget per class"),
                               ("E46_rules", "E46", "Table 7, cell means of E46 per rule and split"), ("E46_owners", "E46", "Table 8, each owner against alone")):
        try:
            T[name] = {"E48_sizing": table_e48_sizing, "E48_link": table_e48_link, "E46_rules": table_e46_rules,
                       "E46_owners": table_e46_owners}[name](r)
        except Pending as e:
            if not allow_pending:
                raise SystemExit(f"TABLE:{name} pending ({e}); rerun with --allow-pending to build a draft")
            pending.append(f"TABLE:{name}: {e}")
            T[name] = f'<p class="pending">[[PENDING {tag}: {caption}]]</p>'
    if broken:
        raise SystemExit("claims contradicted by the data:\n  " + "\n  ".join(broken))
    return V, T, pending


# ---------------------------------------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------------------------------------
def _tab(caption, head, rows, cls="", note=""):
    out = [f'<table class="{cls}">', f"<caption>{caption}</caption>",
           "<thead><tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead>", "<tbody>"]
    out += ["<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows]
    out += ["</tbody></table>"] + ([f'<p class="tabnote">{note}</p>'] if note else [])
    return "\n".join(out)


def table_vehicles(r: R, in_fleet):
    """Table 2 from the catalogue: value and flag per cell, so a typed number can never disagree with the file."""
    owners = {}
    for o, c in r.fleet():
        owners.setdefault(c, []).append(o)

    def cell(cls, key, nd=0, u=""):
        p = r.cat["classes"][cls]["params"].get(key)
        if p is None:
            return "&ndash;"
        v = p["value"]
        if isinstance(v, bool):
            s = "Yes" if v else "No"
        else:
            s = num(v, nd) + (f"{NB}{u}" if u else "")
        flag = p["flag"] + ("" if p.get("confidence", "-") in ("-", None) else f" ({p['confidence']})")
        return f"{s}, {flag}"
    rows = []
    for cls, c in r.cat["classes"].items():
        own = ", ".join(sorted(set(owners.get(cls, [])))) or "&ndash; (in no fleet)"
        n = len(owners.get(cls, []))
        name = html.escape(c["name"]) + (f" &times; {n}" if n > 1 else "")
        energy = cell(cls, "energy_wh_per_km", 1, "Wh/km") if r.param(cls, "energy_wh_per_km")["value"] else \
            f"propellant: {cell(cls, 'km_budget', 0, 'km')} in {cell(cls, 'active_days', 0, 'd')}"
        batt = cell(cls, "battery_wh", 0, "Wh") + (f"; {cell(cls, 'range_km_per_charge', 0, 'km')} per charge" if "range_km_per_charge" in c["params"] else "")
        rows.append([name, html.escape(c["status"]), own, cell(cls, "mass_kg", 0, "kg"), cell(cls, "capacity_kg", 0, "kg"),
                     cell(cls, "top_speed_kmh", 1, "km/h"), cell(cls, "speed_kmh", 1, "km/h"), energy, batt,
                     cell(cls, "night_ops"), cell(cls, "can_team_lift")])
    return _tab("Table 2. The vehicle classes of the catalogue (lunarsim/atc/vehicles-p5.json), read by the build script. Each cell gives "
                "the value the simulation uses and its flag: Spec (a published figure or company claim, with the research note's confidence "
                "High / Medium / Low), Modelled (derived from published figures by a stated rule, for example the modelled speed as 0.6 of the "
                "published top speed and the energy per kilometre from the traction model of [57]) or Assumed (no source; swept). The full "
                "source string of every value is in the file.",
                ["Class", "Status", "Owner", "Mass", "Payload", "Top speed", "Modelled speed", "Energy", "Battery", "Works at night",
                 "Can join a team lift"], rows, cls="wide")


def table_e48_sizing(r: R):
    rows = []
    for c in CLASSES:
        cl = r.s48("classes", c)
        sc = cl.get("cpu_safety_check_us")
        a = cl["cpu_auction_round_ms"]
        rows.append([CLASS_NAME[c].capitalize(), f"{num(sc['median'], 1)} / {num(sc['p99'], 1)}" if sc else "&ndash;",
                     f"{num(a['median'], 2)} / {num(a['p99'], 1)}", num(cl["peak_memory_mb"], 1),
                     f"{num(cl['power_w']['value'], 1)}, {html.escape(cl['power_w']['flag'])}" if "power_w" in cl else "&ndash;"])
    f = r.s48("flight")
    return _tab(f"Table 5. Sizing per vehicle class, measured on our implementation ({html.escape(r.s48('laptop', 'processor'))}) and, where "
                f"stated, scaled to the {html.escape(f['processor'])} by {num(f['factor'], 1)} (Assumed, range {num(f['factor_range'][0], 1)}"
                f"&ndash;{num(f['factor_range'][1], 1)}). CPU per safety check in microseconds and per auction round in milliseconds, median / "
                f"99th percentile; peak memory of the on-robot part in MB; power with its flag.",
                ["Class", "Safety check (&micro;s)", "Auction round (ms)", "Peak memory (MB)", "Power (W)"], rows, cls="wide")


def table_e48_link(r: R):
    rows = []
    for c in CLASSES:
        lk = r.s48("classes", c, "link")
        rows.append([CLASS_NAME[c].capitalize(), num(lk["antenna_m"], 1), num(lk["freq_ghz"], 1), num(lk["tx_power_w"], 1),
                     num(lk["worst_hop_kbps"], 1), num(lk["latency_budget_ms"], 0), pc(lk["reachable_share"], 1)])
    return _tab("Table 6. Link budget per vehicle class under the models of Section 3.3: antenna height (m), frequency (GHz), transmit power (W), "
                "data rate at the worst hop (kbit/s), latency budget for a decision within 1 s (ms) and the share of the time the class is "
                "reachable from the mast over a run.",
                ["Class", "Antenna (m)", "Frequency (GHz)", "Power (W)", "Worst hop (kbit/s)", "Latency budget (ms)", "Reachable"], rows, cls="wide")


def table_e46_rules(r: R):
    rows = []
    for rule in RULES:
        for split in SPLITS:
            c = r.cell46(rule, split)
            rows.append([RULE_NAME[rule].capitalize(), SPLIT_NAME[split], int(c["n"]), num(c["urgent_wait_mean_h"], 1),
                         pc(c["efficiency_loss_vs_oracle"], 1), num(c["budget_per_year"], 0, sign=True), num(c["earnings_total"], 0),
                         num(c["payments_total"], 0), num(c["settled_earth"], 0), num(c["open_end"], 0), int(c["ir_violations"])])
    return _tab("Table 7. Cell means of E46 per payment rule and share split, honest bids, no audits. Urgent wait is the mean wait of urgent "
                "cargo (h); efficiency loss is the difference from the oracle of [60] as a share of its mean; budget is the operator's surplus "
                "(+) or deficit (&minus;) per year; earnings, payments, settled and open are yearly totals in the market's cost units; IR "
                "violations count the owner-seed pairs in which the market left an owner worse off than alone.",
                ["Rule", "Split", "Runs", "Urgent wait (h)", "Efficiency loss", "Budget", "Earnings", "Payments", "Settled on Earth",
                 "Open at year end", "IR violations"], rows, cls="wide")


def table_e46_owners(r: R):
    rows = []
    for rule in RULES:
        for split in SPLITS:
            for o in "ABC":
                p = r.pair46(f"IR: {rule} - alone, {split}, owner {o}", "profit")
                rows.append([RULE_NAME[rule].capitalize(), SPLIT_NAME[split], o, int(p["n"]), num(p["b_mean"], 0),
                             num(p["mean"], 0, sign=True), ci(p["lo"], p["hi"], 0)])
    return _tab("Table 8. Each owner's profit in the market against working alone on the same seeds: the alone profit, the paired "
                "difference (market minus alone) and its 95 % bootstrap interval, in the market's cost units per year.",
                ["Rule", "Split", "Owner", "n", "Alone profit", "Difference", "95 % CI"], rows, cls="wide")


def references():
    notes = open(os.path.join(HERE, "NOTES.md"), encoding="utf-8").read()
    out = ['<ol class="refs">']
    for m in re.finditer(r"^\[(\d+)\]\s+(.+?)(?=\n\n|\n\[\d+\]|\n## |\Z)", notes, re.S | re.M):
        txt = html.escape(" ".join(m.group(2).split()))
        txt = re.sub(r"\s*\((VCI|MOA|TAS|P1|P2|PWG)[^)]*\)\s*$", "", txt)
        txt = re.sub(r"\*(.+?)\*", r"<i>\1</i>", txt)
        txt = re.sub(r"(https?://[^\s<]+)", lambda u: f'<a href="{u.group(1)}">{u.group(1)}</a>', txt)
        out.append(f'<li value="{m.group(1)}">{txt}</li>')
    if len(out) < 2:
        raise SystemExit("no references found in NOTES.md")
    return "\n".join(out + ["</ol>"])


# ---------------------------------------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------------------------------------
def build(no_pdf: bool, allow_pending: bool):
    r = R()
    V, T, pending = values(r, allow_pending)
    bad = {k: v for k, v in V.items() if re.search(r"\b(nan|inf|NaN|None)\b", v)}
    if bad:
        raise SystemExit(f"non-finite values: {bad}")
    doc = "\n".join(open(os.path.join(HERE, p), encoding="utf-8").read() for p in PARTS)
    for name, body in T.items():
        marker = f"<!-- TABLE:{name} -->"
        if marker not in doc:
            raise SystemExit(f"{marker} marker missing from the parts")
        doc = doc.replace(marker, body)
    stripped = re.sub(r"<!--.*?-->", "", doc, flags=re.S)
    used = set(re.findall(r"\{\{(P3-[A-Z0-9.-]+)\}\}", stripped))
    doc = re.sub(r"\{\{(P3-[A-Z0-9.-]+)\}\}", lambda x: V[x.group(1)] if x.group(1) in V else x.group(0), doc)
    left = sorted(set(re.findall(r"\{\{P3-[^}]*\}\}", re.sub(r"<!--.*?-->", "", doc, flags=re.S))))
    if left:
        raise SystemExit(f"unfilled placeholders: {left}")
    body = re.sub(r"<[^>]+>", " ", re.sub(r"<!--.*?-->", "", doc, flags=re.S))
    if re.search(r"\b(nan|NaN|inf)\b", body):
        raise SystemExit("nan/inf in the assembled text: " + re.search(r".{40}\b(nan|NaN|inf)\b.{40}", body).group(0))
    listed = open(os.path.join(HERE, "PLACEHOLDERS.md"), encoding="utf-8").read()
    listed_keys = set(re.findall(r"(?<![A-Za-z0-9-])P3-[A-Z0-9.-]+(?![A-Za-z0-9-])", listed))
    listed_keys = {k.rstrip(".-") for k in listed_keys}
    undocumented = sorted(k for k in used if k not in listed_keys)
    if undocumented:
        raise SystemExit(f"placeholders in the parts but not in PLACEHOLDERS.md: {undocumented}")
    unused = sorted(k for k in V if k not in used and k != "P3-REFERENCES")
    if unused:
        print("note: values not used in the text:", ", ".join(unused))
    checks = sorted(set(re.findall(r"\[\[CHECK:[^\]]*\]\]", body)))
    if checks:
        print(f"note: {len(checks)} [[CHECK]] items remain in the text")
    m = re.search(r'<div class="abstract"[^>]*>(.*?)<p class="kw">', doc, re.S)
    if not m:
        raise SystemExit("abstract block not found")
    abs_text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S)))
    n_abs = len(abs_text.replace("Abstract.", "").split())
    if not 250 <= n_abs <= 300:
        msg = f"abstract has {n_abs} words; the target is 250-300"
        if pending:
            print("note:", msg, "(pending markers change the count)")
        else:
            raise SystemExit(msg)
    else:
        print(f"abstract: {n_abs} words")
    m = re.search(r'<h2 id="p3-sec-conclusion">.*?</h2>(.*?)<h2', doc, re.S)
    n_con = len(html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S))).split())
    if not 150 <= n_con <= 250:
        msg = f"conclusion has {n_con} words; the target is 150-250"
        if pending:
            print("note:", msg, "(pending markers change the count)")
        else:
            raise SystemExit(msg)
    else:
        print(f"conclusion: {n_con} words")
    title = re.search(r"<title>(.*?)</title>", doc, re.S).group(1)
    if len(title.split()) > 20:
        raise SystemExit(f"title has {len(title.split())} words; the limit is 20")
    kw = re.search(r'<p class="kw"><b>Keywords:</b>(.*?)</p>', doc, re.S).group(1)
    n_kw = len([k for k in kw.split(",") if k.strip()])
    if not 4 <= n_kw <= 6:
        raise SystemExit(f"{n_kw} keywords; the target is 4-6")
    out = os.path.join(HERE, "paper.html")
    open(out, "w", encoding="utf-8", newline="\n").write(doc)
    json.dump({k: v for k, v in V.items() if k != "P3-REFERENCES"},
              open(os.path.join(HERE, "values.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("wrote", out, f"({len(V)} values, {len(used)} placeholders used, {len(pending)} pending)")
    for p in pending:
        print("  pending:", p)
    if not no_pdf and os.path.exists(CHROME):
        cmd = [CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--allow-file-access-from-files",
               f"--print-to-pdf={PDF}", "file:///" + out.replace("\\", "/")]
        rc = subprocess.run(cmd, capture_output=True, timeout=180).returncode
        print("chrome exit", rc, "pdf", os.path.exists(PDF), os.path.getsize(PDF) if os.path.exists(PDF) else 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pdf", action="store_true", help="skip the Chrome render")
    ap.add_argument("--allow-pending", action="store_true",
                    help="fill keys whose experiment has not run with a visible [[PENDING]] marker")
    a = ap.parse_args()
    build(a.no_pdf, a.allow_pending)
