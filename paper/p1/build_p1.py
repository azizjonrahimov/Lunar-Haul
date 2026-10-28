"""Assemble paper P1 ("Working together without Earth"): fill every {{P1-...}} placeholder from the phase-5 results,
insert the tables and the figure, write paper/p1/paper.html and render the PDF with headless Chrome.

    python paper/p1/build_p1.py [--no-pdf] [--allow-pending]

Sources (read-only): results/table_E40_pairs.csv (paired differences; one row per comparison, load and block, with
`valid` marking the row the decision uses: block v1 when both regimes are Earth-independent, PREREG change 4, all
runs otherwise), table_E40_regimes.csv (cell means), E40_fit.json (hypotheses, Holm, E42 cells, visibility),
ATC_learned_eval.json and data/policies/atc_bid_{linear_,}v1.json (the learned bids), ATC_oracle_diag.json,
E40_rerun_check.json, ATC_mesh.json, ATC_auction_bounds.json, ATC_p5_load.json, the raw E4x_runs*.csv (run counts
and run times), paper/p1/dev_notes.json (development-run numbers with their source) and paper/p1/NOTES.md (references).

Every comparison label the text relies on is listed once in LABELS, so a renamed row in the analysis is fixed here.
Rows are found by label, load and block, never by position; a missing row names itself in the error.

Sentences whose wording depends on the outcome (H3a's equivalence test, the light-load learning test, the team-lift
meetings) are composed here from the data, and every fixed phrase in the parts that asserts a direction ("supported",
"recovers most", "fails", "all fell") is checked against the data before the build goes on; a failed check lists
every broken claim and stops.

E41 has not run yet. Keys that depend on it (and on the 60 % cells of E40) are filled with a visible
[[PENDING ...]] marker only with --allow-pending; without the flag the build fails, as build_r1 would.

The build fails if any placeholder is left unfilled or if a filled value contains nan or inf.
"""
import argparse
import glob
import html
import json
import math
import os
import re
import subprocess
import sys
from typing import Any, Dict, List

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RES = os.path.join(ROOT, "results")
sys.path.insert(0, ROOT)
from experiments.phase5 import run_phase5 as RP  # noqa: E402  (cell lists and the run-file union; nothing runs)

PARTS = ["part1_front.html", "part2_related.html", "part3_methods.html", "part4_results.html", "part5_back.html"]
PDF = os.path.join(HERE, "working_together_without_earth_p1.pdf")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
MINUS, NB, PCT = "&minus;", "&nbsp;", "&#8239;%"
WORDS = {0: "none", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
         10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen",
         17: "seventeen", 18: "eighteen", 19: "nineteen"}
LOAD_MAIN, LOAD_LIGHT, LOAD_HEAVY = 30, 10, 60

# Every row label and fit key the text relies on. Rename here when the analysis renames a row.
LABELS = {
    "H1": "H1: B_EARTH_RELAY 1.0 - A_EARTH full coverage",
    "H1_delivered_only": "H1 (reported): delivered-only urgent wait",
    "H2_pooled": "H2: B_EARTH strict - O_ORACLE, pooled years",
    "H2_year": "H2: B_EARTH strict - O_ORACLE, {year}",
    "H2_plan": "H2 (reported): B_EARTH plan_ahead - O_ORACLE",
    "H2_relay08": "H2 (reported): B_EARTH_RELAY 0.8 - O_ORACLE",
    "H2_old_yardstick": "H2 (not tested): A_EARTH strict - O_ORACLE (original yardstick)",
    "H2_A_delivered_only": "H2 (not tested): A_EARTH strict - O_ORACLE, delivered-only (conditions on delivery)",
    "H3a": "H3a: C_AUCTION - O_ORACLE (TOST +-10 % of O)",
    "H4_LIN": "H4: C_LEARNED_LIN - C_AUCTION",
    "H4_MLP": "H4: C_LEARNED_MLP - C_AUCTION",
    "H6": "H6: cross-owner - same owner, team {team}, loss {loss}",
    "H6_team_items": "H6 (reported): team items, team {team}, loss {loss}",
    "H1_split": "H1 split (E42): C_AUCTION same owner - A_EARTH own teams, team {team}, loss 0.1",
    # the split agreed with BACKEND (B-75): "dispatch part" = single-robot jobs pooled across owners plus the pooled
    # dispatcher; "capacity part" = lifts by pairs of different owners' rovers
    "H1_pool": "H1 dispatch part: C_AUCTION same-owner teams - A_EARTH full coverage",
    "H1_team": "H1 capacity part: C_AUCTION cross-owner - C_AUCTION same-owner teams",
    "H1_owner": "H1 (reported): owner {owner}",
    "leader_minus_O": "C_LEADER - O_ORACLE",
    "auction_minus_O": "C_AUCTION - O_ORACLE",
    "lin_minus_O": "C_LEARNED_LIN - O_ORACLE",
    "mlp_minus_O": "C_LEARNED_MLP - O_ORACLE",
    "hopper_O": "O_ORACLE hopper_refuel - O_ORACLE",
    # regime labels (table_E40_regimes.csv `label`)
    "A_strict": "A_EARTH strict", "A_plan": "A_EARTH plan_ahead", "A_moon": "A_MOON", "A_full": "A_EARTH full coverage",
    "B_strict": "B_EARTH strict", "B_plan": "B_EARTH plan_ahead", "relay08": "B_EARTH_RELAY 0.8",
    "relay10": "B_EARTH_RELAY 1.0", "leader": "C_LEADER", "auction": "C_AUCTION", "lin": "C_LEARNED_LIN",
    "mlp": "C_LEARNED_MLP", "O": "O_ORACLE",
    # E40_fit.json keys
    "holm": "holm_30pct", "holm_H1": "H1", "holm_H2": "H2", "holm_H4_LIN": "H4_LIN", "holm_H4_MLP": "H4_MLP",
    "holm_H6": "H6",
    # E42 cells (E40_fit.json "E42"."cells" and hypotheses.H6.meetings)
    "E42_meet": "C_AUCTION team 25 any loss {loss}",
    "E42_meet_nocommit": "C_AUCTION team 25 any loss {loss} no commit",
    "E42_meet_timeout": "C_AUCTION team 25 any loss {loss} timeout {to}",
    "E42_meet_arb": "C_AUCTION team 25 any loss {loss} arbitrated (exploratory)",
    # E41 cell labels (run_phase5.e41_cells), used once E41 exists
    "E41_rally_on": "C_AUCTION loss 0.1", "E41_rally_off": "C_AUCTION rally off",
}
# Regime groups the prose of Section 5.1 orders (checked, not assumed)
EARTH_LOSING = ["B_strict", "B_plan", "relay08"]
BOTTOM = ["relay10", "leader", "auction", "lin", "mlp", "O"]
FEATURE_WORDS = {"job_h": "the planned hours of the job", "age_d": "the item's age", "prio": "its priority",
                 "mass_frac": "the load as a share of capacity", "approach_h": "the hours to drive to the pad",
                 "battery": "the battery's state of charge", "dark_or_low": "the hours until dark or a low battery",
                 "link_base": "being in the mast's part of the network", "heard": "the number of robots heard",
                 "queue": "the claims the robot holds", "bundle_n": "the items in the bundle",
                 "slack_d": "the slack to the item's target time", "landing": "the hours until the next landing"}


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
    neg = x < 0 and float(s.replace(",", "")) != 0
    return (MINUS if neg else ("+" if sign and float(s.replace(",", "")) != 0 else "")) + s


def h_(x, nd=1, sign=False):
    return f"{num(x, nd, sign)}{NB}h"


def t_(x, nd=0, sign=False):
    return f"{num(x, nd, sign)}{NB}t"


def pc(x, nd=1, sign=False):
    """x already in percent."""
    return f"{num(x, nd, sign)}{PCT}"


def sh(x, nd=0):
    """A share (0-1) as a percentage."""
    return pc(100 * _fin(x), nd)


def ci_h(lo, hi, nd=1):
    """An interval as 'a to b h' (PLACEHOLDERS.md format)."""
    return f"{num(lo, nd)} to {num(hi, nd)}{NB}h"


def ci_abs(r, nd=1):
    """The interval of a negative difference quoted as a size ('cut by X, CI a to b'): flipped and positive."""
    return ci_h(-_fin(r["hi"]), -_fin(r["lo"]), nd)


def pfmt(p):
    p = _fin(p)
    if p < 0.001:
        return "&lt;&nbsp;0.001"
    return f"{p:.3f}" if p < 0.05 else f"{p:.2f}"


def p_eq(p):
    """A p-value after the word p: '= 0.001' or '< 0.001'."""
    s = pfmt(p)
    return s if s.startswith("&lt;") else "=&nbsp;" + s


def words(n):
    return WORDS.get(int(n), f"{int(n):,}")


def listing(items):
    items = [str(i) for i in items]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def rng_txt(vals, fmt):
    lo, hi = min(vals), max(vals)
    a, b = fmt(lo), fmt(hi)
    return a if a == b else f"{a} to {b}"


def seeds_in(text):
    """The seed list written into a CEM 'fitness' or 'selection' string: 'seeds [1000, 1002, ...]'."""
    m = re.search(r"seeds \[([\d,\s]+)\]", text)
    if not m:
        raise ValueError(f"no seed list in {text!r}")
    return [int(s) for s in m.group(1).split(",")]


class Pending(Exception):
    pass


# ---------------------------------------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------------------------------------
class R:
    def __init__(self):
        rd = lambda f: pd.read_csv(os.path.join(RES, f))
        jl = lambda f: json.load(open(os.path.join(RES, f), encoding="utf-8"))
        self.p = rd("table_E40_pairs.csv")
        self.r = rd("table_E40_regimes.csv")
        self.f = jl("E40_fit.json")
        self.L = jl("ATC_learned_eval.json")
        self.mesh = jl("ATC_mesh.json")
        self.bounds = jl("ATC_auction_bounds.json")
        self.load = jl("ATC_p5_load.json")
        self.diag = jl("ATC_oracle_diag.json")
        self.rerun = jl("E40_rerun_check.json")
        self.lin = json.load(open(os.path.join(ROOT, "data/policies/atc_bid_linear_v1.json"), encoding="utf-8"))
        self.mlp = json.load(open(os.path.join(ROOT, "data/policies/atc_bid_v1.json"), encoding="utf-8"))
        self.dev = json.load(open(os.path.join(HERE, "dev_notes.json"), encoding="utf-8"))
        self.runs = {}                                     # exp -> raw run rows (union of the part files)
        for exp in ("E40", "E41", "E42"):
            files = RP.run_files(exp)
            if not files:
                continue
            # read the files directly, not through load_runs: only counts, labels and run times are needed here, and
            # a file that a rerun is still replacing may hold a key twice (one copy is kept and the count printed)
            d = pd.concat([pd.read_csv(f, usecols=lambda c: c in ("cell", "label", "seed", "start_year", "run_s",
                                                                   "delivered_kg", "atc_urgent_wait_mean_cens_h"))
                           for f in files], ignore_index=True)
            dup = int(d.duplicated(["cell", "seed", "start_year"]).sum())
            if dup:
                print(f"note: {exp}: {dup} duplicate keys across run files dropped for the counts (a rerun in flight?)")
                d = d.drop_duplicates(["cell", "seed", "start_year"], keep="last")
            if "label" not in d:
                d["label"] = d["cell"].str.extract(r"label=([^;]+)")[0]
            self.runs[exp] = d
        self.e41 = {os.path.basename(f): pd.read_csv(f) for f in glob.glob(os.path.join(RES, "table_E41_*.csv"))}

    def pair(self, key, load, block=None, **fmt):
        """The pairs row for a label (LABELS key or literal), a load and a block; by default the `valid` row."""
        label = LABELS.get(key, key).format(**fmt)
        d = self.p[(self.p["comparison"] == label) & (self.p["load"] == load)]
        d = d[d["block"] == block] if block else d[d["valid"].astype(bool)]
        if len(d) != 1:
            raise KeyError(f"pairs row {label!r} at load {load} block {block or 'valid'}: {len(d)} rows "
                           f"(labels present: {sorted(self.p['comparison'].unique())[:8]} ...)")
        row = d.iloc[0].to_dict()
        if int(row["n"]) == 0 or not np.isfinite(row["mean"]):
            raise Pending(f"{label} at {load} % has no runs yet")
        return row

    def reg(self, key, load):
        label = LABELS.get(key, key)
        d = self.r[(self.r["label"] == label) & (self.r["load"] == load)]
        if len(d) != 1:
            raise KeyError(f"regimes row {label!r} at load {load}: {len(d)} rows")
        return d.iloc[0].to_dict()

    def fit(self, *path):
        node = self.f
        for k in path:
            k = LABELS[k] if k.startswith("holm") else k       # only the fit's own keys are aliased in LABELS
            if k not in node:
                raise KeyError(f"E40_fit.json has no {'/'.join(str(p) for p in path)} (missing {k!r})")
            node = node[k]
        return node

    def e42_cell(self, key, **fmt):
        cells = self.fit("E42", "cells")
        label = LABELS[key].format(**fmt)
        if label not in cells:
            raise KeyError(f"E42 cell {label!r} not in E40_fit.json (have {sorted(cells)[:6]} ...)")
        return cells[label]

    def runs_of(self, exp, label):
        d = self.runs.get(exp)
        if d is None:
            raise Pending(f"{exp} has not run")
        g = d[d["label"] == label]
        if len(g) == 0:
            raise Pending(f"{exp} cell {label!r} has no runs yet")
        return g


# ---------------------------------------------------------------------------------------------------------
# values
# ---------------------------------------------------------------------------------------------------------
def values(r: R, allow_pending: bool):
    V: Dict[str, str] = {}
    pending: List[str] = []
    broken: List[str] = []

    def check(cond, claim):
        """A fixed phrase in the text asserts `claim`; record it if the data contradict it."""
        if not cond:
            broken.append(claim)

    def fill(key, fn, tag):
        """Fill a key from fn(); a Pending result becomes a visible marker only with --allow-pending."""
        try:
            V[key] = fn()
        except Pending as e:
            if not allow_pending:
                raise SystemExit(f"{key}: pending ({e}); rerun with --allow-pending to build a draft")
            pending.append(f"{key}: {e}")
            V[key] = f'<span class="pending">[[PENDING {tag}]]</span>'

    # --- design -------------------------------------------------------------------------------------------
    V["P1-LOAD-MAIN"] = pc(LOAD_MAIN, 0)
    V["P1-LOSS-MAIN"] = f"{RP.LOSS:g}"
    labels = {l.replace(" hopper_refuel", "") for l in r.r["label"]}
    V["P1-N-REGIMES"] = words(len(labels))
    n_cells = {exp: len(RP.EXPS[exp]()) for exp in RP.EXPS}
    n_runs = {exp: len(r.runs[exp]) if exp in r.runs else 0 for exp in RP.EXPS}
    for exp in ("E40", "E42"):
        V[f"P1-{exp}-N-CELLS"] = f"{n_cells[exp]}"
        V[f"P1-{exp}-N-RUNS"] = f"{n_runs[exp]:,}"
    V["P1-E41-N-CELLS"] = f"{n_cells['E41']}"
    fill("P1-E41-N-RUNS", lambda: f"{r.runs_of('E41', LABELS['E41_rally_on'])['run_s'].size and n_runs['E41']:,}",
         "E41")
    V["P1-N-RUNS-ALL"] = f"{sum(n_runs.values()):,}"
    cal = r.load["calibration"]["variants"]
    for lv in ("10", "30", "60"):
        k = cal[lv]["k"]
        scen = json.load(open(os.path.join(ROOT, f"data/scenarios/p5/p5-3eq-L{lv}-T10.json"), encoding="utf-8"))
        ks = {float(m) for m in re.findall(r'"k":\s*([0-9.]+)', json.dumps(scen))}
        if ks and not any(abs(x - k) < 1e-9 for x in ks):
            raise ValueError(f"load {lv}: k = {k} in ATC_p5_load.json but {ks} in the scenario file")
        V[f"P1-K-{lv}"] = f"{k:.3f}"

    # --- Earth visibility and the mesh ---------------------------------------------------------------------
    vis = r.fit("hypotheses", "H2", str(LOAD_MAIN), "visibility")
    V["P1-VIS-MIN"], V["P1-VIS-MAX"] = sh(min(vis.values()), 1), sh(max(vis.values()), 1)
    low = r.fit("hypotheses", "H2", str(LOAD_MAIN), "low_visibility_years")
    check(all(vis[str(y)] < 0.6 for y in low) and all(vis[y] >= 0.6 for y in vis if int(y) not in low),
          "low-visibility years are exactly those below 60 %")
    V["P1-H2-N-LOWVIS-YEARS"] = words(len(low))
    V["P1-H2-LOWVIS-YEARS"] = listing(low)
    band = r.mesh["los_by_distance_band"]["2.5-2.5"]["2-5 km"]["los_0m"]
    V["P1-MESH-LOS-25-2TO5"] = pc(100 * band, 2)
    md = r.mesh["mast_direct"]["rover_2.5m"]["within_km"]
    n_far = md["10 km"]["n"]
    reach = min((float(k.split()[0]) for k, v in md.items() if v["n"] == n_far), default=None)
    check(reach is not None, "the mast's direct line of sight has a farthest band")
    V["P1-MESH-MAST-MAX-KM"] = f"{reach:g}{NB}km"
    conn = r.mesh["connectivity"]["rover_2.5m"]
    check(conn["2 km"]["components"] == 1 and conn["5 km"]["components"] == 1, "rovers form one network from 2 km")
    V["P1-MESH-MAX-HOPS-5KM"] = f"{conn['5 km']['max_hops']}"
    V["P1-MESH-SMALL-ISOLATED"] = words(r.mesh["isolated"]["small_1.0m"]["n"])

    # --- Section 5.1: the regime table and its ordering --------------------------------------------------
    M = "atc_urgent_wait_mean_cens_h"
    reg30 = {k: r.reg(k, LOAD_MAIN) for k in ("A_strict", "A_plan", "A_moon", "A_full") + tuple(EARTH_LOSING) +
             tuple(BOTTOM)}
    a_vals = [reg30[k][M] for k in ("A_strict", "A_plan", "A_moon", "A_full")]
    mid = {k: reg30[k][M] for k in EARTH_LOSING}
    bot = {k: reg30[k][M] for k in BOTTOM}
    check(min(a_vals) > max(mid.values()) > max(bot.values()), "owners alone wait longest, Earth-losing pooled next")
    check(min(mid, key=mid.get) == "relay08" and max(mid, key=mid.get) == "B_strict",
          "the middle group runs from relay 0.8 to strict")
    check(min(bot, key=bot.get) == "lin" and max(bot, key=bot.get) == "leader",
          "the bottom group runs from learned linear bids to the elected leader")
    V["P1-A-URGENT-RANGE-30"] = rng_txt(a_vals, lambda x: num(x, 0)) + NB + "h"
    V["P1-RELAY08-URGENT-30"], V["P1-B-STRICT-URGENT-30"] = h_(mid["relay08"]), h_(mid["B_strict"])
    V["P1-LIN-URGENT-30"], V["P1-LEADER-URGENT-30"] = h_(bot["lin"]), h_(bot["leader"])
    V["P1-O-URGENT-30"] = h_(bot["O"])
    V["P1-B-STRICT-URGENT-10"] = h_(r.reg("B_strict", LOAD_LIGHT)[M])
    pooled_t = [reg30[k]["delivered_kg"] / 1000 for k in EARTH_LOSING + BOTTOM]
    a_t = [reg30[k]["delivered_kg"] / 1000 for k in ("A_strict", "A_plan", "A_moon", "A_full")]
    check((max(pooled_t) - min(pooled_t)) / np.mean(pooled_t) < 0.02, "tonnes are almost the same among pooled regimes")
    check(max(a_t) < min(pooled_t), "owners alone deliver much less")
    V["P1-POOLED-T-RANGE-30"] = rng_txt(pooled_t, lambda x: num(x, 0)) + NB + "t"
    V["P1-A-T-RANGE-30"] = rng_txt(a_t, lambda x: num(x, 0)) + NB + "t"
    V["P1-CARGO-UTIL-30"] = sh(reg30["O"]["p5_cargo_util"], 0)
    V["P1-UTIL-FLEET-30"] = sh(reg30["O"]["utilisation"], 1)
    pooled10 = [r.reg(k, LOAD_LIGHT)[M] for k in EARTH_LOSING + BOTTOM if k != "B_strict"]
    V["P1-POOLED-SPREAD-10"] = h_(max(pooled10) - min(pooled10))
    check(r.reg("B_strict", LOAD_LIGHT)[M] > max(pooled10), "the strict dispatcher is the exception at light load")

    # --- H1 ------------------------------------------------------------------------------------------------
    h1 = r.pair("H1", LOAD_MAIN)
    check(h1["block"] == "v1", "H1 uses the v1 block (both regimes Earth-independent)")
    check(h1["hi"] < 0 and bool(r.fit("hypotheses", "H1", str(LOAD_MAIN), "supported")), "H1 is supported")
    V["P1-H1-DIFF-30"] = h_(-h1["mean"], 0)
    V["P1-H1-DIFF-30-CI"] = ci_abs(h1, 0)
    V["P1-H1-N-30"] = f"{int(h1['n'])}"
    holm = r.fit("holm", "adjusted_p")
    V["P1-H1-PHOLM"] = p_eq(holm[LABELS["holm_H1"]])
    V["P1-A-BACKLOG-T-30"] = t_(reg30["A_strict"]["backlog_kg"] / 1000)
    ad = r.pair("H2_A_delivered_only", LOAD_MAIN)
    check(ad["lo"] > 0, "owners alone wait longer even on delivered items")
    V["P1-A-DELIV-MINUS-O-30"] = h_(ad["mean"], 0)
    # the share of the censored gap that lies in items owners alone had not delivered by year end: one minus the
    # delivered-only paired difference over the censored one (both "H1 (reported)" rows, v1)
    h1d = r.pair("H1_delivered_only", LOAD_MAIN)
    undel = 1 - abs(h1d["mean"]) / abs(h1["mean"])
    check(undel > 0.9, "almost the whole H1 gap is cargo owners alone never delivered")
    V["P1-H1-UNDELIVERED-SHARE"] = sh(undel, 0)
    # the split agreed with BACKEND (B-75): lifts by pairs of different owners' rovers against single-robot jobs
    # pooled across owners together with the pooled dispatcher; the two parts sum to the E40 gap
    team, pool = r.pair("H1_team", LOAD_MAIN), r.pair("H1_pool", LOAD_MAIN)
    split = r.fit("hypotheses", "H1", "split_30")
    check(team["hi"] < 0 and pool["hi"] < 0, "both parts of the H1 split exclude zero")
    check(abs(split["sum_of_parts"] - h1["mean"]) < 0.05 * abs(h1["mean"]), "the two H1 parts sum to the gap within 5 %")
    check(pool["mean"] < team["mean"], "single-robot pooling with the dispatcher is the larger part of the H1 gap")
    V["P1-H1-TEAM-DIFF"], V["P1-H1-TEAM-DIFF-CI"] = h_(-team["mean"], 0), ci_abs(team, 0)
    V["P1-H1-POOL-DIFF"], V["P1-H1-POOL-DIFF-CI"] = h_(-pool["mean"], 0), ci_abs(pool, 0)
    V["P1-H1-TEAM-SHARE"], V["P1-H1-POOL-SHARE"] = sh(split["share_capacity"], 0), sh(split["share_dispatch"], 0)
    own = {o: r.pair("H1_owner", LOAD_MAIN, owner=o) for o in "ABC"}
    check(own["C"]["mean"] < own["B"]["mean"] < own["A"]["mean"] < 0, "owner C gains most from pooling, then B, then A")
    for o in "ABC":
        V[f"P1-H1-OWNER-{o}-DIFF"] = h_(-own[o]["mean"], 0)

    # --- H2 ------------------------------------------------------------------------------------------------
    h2 = r.pair("H2_pooled", LOAD_MAIN)
    yrs = {y: r.pair("H2_year", LOAD_MAIN, year=y) for y in low}
    margin = _fin(r.fit("hypotheses", "H2", str(LOAD_MAIN), "pooled")["threshold"])
    check(h2["lo"] > margin and all(v["lo"] > margin for v in yrs.values()) and
          bool(r.fit("hypotheses", "H2", str(LOAD_MAIN), "supported")), "H2 clears its margin pooled and in every year")
    V["P1-H2-STRICT-MINUS-O"] = h_(h2["mean"])
    V["P1-H2-STRICT-MINUS-O-CI"] = ci_h(h2["lo"], h2["hi"])
    V["P1-H2-N"] = f"{int(h2['n'])}"
    V["P1-H2-MARGIN"] = h_(margin)
    ratio = reg30["B_strict"][M] / reg30["O"][M]
    check(ratio > 1, "strict waits longer than the marketplace")
    V["P1-H2-STRICT-OVER-O-RATIO"] = f"{ratio:.1f}"
    ymeans = [v["mean"] for v in yrs.values()]
    V["P1-H2-YEAR-MIN"], V["P1-H2-YEAR-MAX"] = h_(min(ymeans), 0), h_(max(ymeans), 0)
    V["P1-H2-PHOLM"] = p_eq(holm[LABELS["holm_H2"]])
    V["P1-H2-OLD-YARDSTICK-HALF"] = h_(r.fit("hypotheses", "H2", str(LOAD_MAIN), "original_yardstick_half_A_minus_O"), 0)
    plan, relay = r.pair("H2_plan", LOAD_MAIN), r.pair("H2_relay08", LOAD_MAIN)
    check(plan["mean"] < 0.5 * h2["mean"], "planning ahead recovers most of the strict loss")
    rel_fit = r.fit("hypotheses", "H2", str(LOAD_MAIN), "plan_ahead_and_relay_0.8")[LABELS["relay08"]]
    check(not rel_fit["within_10pct_tost"] and relay["lo"] > 0, "the 80 % relay misses its equivalence margin")
    V["P1-PLAN-MINUS-O"], V["P1-PLAN-MINUS-O-CI"] = h_(plan["mean"]), ci_h(plan["lo"], plan["hi"])
    V["P1-RELAY08-MINUS-O"], V["P1-RELAY08-MINUS-O-CI"] = h_(relay["mean"]), ci_h(relay["lo"], relay["hi"])
    bo = "atc_backlog_end_blackout_t_mean"
    check(reg30["B_strict"][bo] > reg30["O"][bo], "the blackout backlog is larger under strict fallback")
    V["P1-B-STRICT-BACKLOG-30"], V["P1-O-BACKLOG-30"] = t_(reg30["B_strict"][bo], 1), t_(reg30["O"][bo], 1)
    w24 = "atc_urgent_within24_share"
    check(reg30["O"][w24] > reg30["B_strict"][w24], "the within-a-day share falls under strict fallback")
    V["P1-O-WITHIN24-30"], V["P1-B-STRICT-WITHIN24-30"] = sh(reg30["O"][w24]), sh(reg30["B_strict"][w24])

    # --- H3a and the leader --------------------------------------------------------------------------------
    h3 = r.pair("H3a", LOAD_MAIN)
    f3 = r.fit("hypotheses", "H3a")
    m3 = _fin(f3["margin"])
    check(h3["block"] == "v1", "H3a uses the v1 block")
    equiv = -m3 < h3["lo90"] and h3["hi90"] < m3
    check(equiv == bool(f3["tost_equivalent"]), "the H3a TOST verdict in E40_fit.json matches the interval")
    V["P1-H3A-DIFF"] = h_(h3["mean"], 2, sign=True)
    V["P1-H3A-PCT"] = pc(100 * h3["share_of_b"], 1, sign=True)
    V["P1-H3A-PCT-ABS"] = pc(abs(100 * h3["share_of_b"]), 1)
    V["P1-H3A-CI90"] = ci_h(h3["lo90"], h3["hi90"])
    V["P1-H3A-N"] = f"{int(h3['n'])}"
    pct90 = (100 * h3["lo90"] / h3["b_mean"], 100 * h3["hi90"] / h3["b_mean"])
    if equiv:
        V["P1-H3A-SENTENCE"] = "it did."
        V["P1-H3A-VERDICT"] = ("The 90&#8239;% interval lies inside the margin, so equivalence is shown and H3a is "
                               "supported.")
        clause = f"came within {pc(abs(100 * h3['share_of_b']), 1)} of the full-information marketplace"
    elif h3["lo"] < 0 < h3["hi"]:
        V["P1-H3A-SENTENCE"] = (f"the test could not show it. The difference was {h_(h3['mean'], 2, sign=True)} with a "
                                f"90&#8239;% interval of {ci_h(h3['lo90'], h3['hi90'])}, which reaches past the margin "
                                f"of &plusmn;{h_(m3)} on at least one side, so the auction may be better or worse "
                                f"than the marketplace by more than 10&#8239;%, and the data cannot tell.")
        V["P1-H3A-VERDICT"] = ("The 90&#8239;% interval is not inside that margin, so equivalence is not shown and "
                               "H3a is not supported as stated; the interval includes zero, so the auction is shown "
                               "neither better nor worse than the marketplace.")
        clause = (f"kept urgent cargo waiting {pc(abs(100 * h3['share_of_b']), 1)} "
                  f"{'less' if h3['mean'] < 0 else 'longer'} than the full-information marketplace, a difference "
                  f"whose 90&#8239;% interval ({pc(pct90[0], 0, sign=True)} to {pc(pct90[1], 0, sign=True)}) "
                  f"includes zero")
    else:
        side = "better" if h3["hi"] < 0 else "worse"
        V["P1-H3A-SENTENCE"] = (f"it fell short of showing that: the auction was {side} than the marketplace by "
                                f"{h_(abs(h3['mean']), 2)} ({ci_h(h3['lo90'], h3['hi90'])}, 90&#8239;%), and the "
                                f"interval reaches past the &plusmn;{h_(m3)} margin on that side.")
        V["P1-H3A-VERDICT"] = (f"The 90&#8239;% interval is not inside that margin, so equivalence is not shown and "
                               f"H3a is not supported as stated; the interval excludes zero, so the auction is "
                               f"{side} than the marketplace.")
        clause = (f"kept urgent cargo waiting {pc(abs(100 * h3['share_of_b']), 1)} "
                  f"{'less' if h3['mean'] < 0 else 'longer'} than the full-information marketplace")
    V["P1-H3A-INTRO-CLAUSE"] = clause
    V["P1-H3A-ABSTRACT-CLAUSE"] = ("matched the full-information marketplace" if h3["lo"] < 0 < h3["hi"] else
                                   f"was {'better' if h3['hi'] < 0 else 'worse'} than the full-information marketplace "
                                   f"by {pc(abs(100 * h3['share_of_b']), 1)}")
    check(h3["mean"] <= 0 and h3["hi"] <= m3, "deciding on the Moon recovers all of the strict dispatcher's loss")
    check(h3["lo"] < 0 < h3["hi"], "the auction-marketplace difference is not distinguishable from zero")
    check(abs(h3["mean"]) < 0.1 * h2["mean"] and abs(h3["hi"]) < 0.1 * h2["mean"],
          "the auction's difference from the marketplace is a small fraction of the strict dispatcher's loss (6.1)")
    check(relay["mean"] < h2["mean"] and relay["lo"] > margin,
          "the relay's loss is small next to the strict dispatcher's and still above a tenth of O's mean (6.1)")
    ld = r.pair("leader_minus_O", LOAD_MAIN)
    V["P1-LEADER-MINUS-O"], V["P1-LEADER-MINUS-O-CI"] = h_(ld["mean"], 2, sign=True), ci_h(ld["lo"], ld["hi"])
    spread = max(abs(r.pair(k, LOAD_MAIN)["mean"]) for k in ("leader_minus_O", "auction_minus_O", "lin_minus_O"))
    check(spread < 10, "the pooled regimes that differ only in their dispatcher sit within a few hours of one another (6.1)")

    # --- H4 ------------------------------------------------------------------------------------------------
    f4 = r.fit("hypotheses", "H4")
    lin30, lin10 = r.pair("H4_LIN", LOAD_MAIN), r.pair("H4_LIN", LOAD_LIGHT)
    mlp30, mlp10 = r.pair("H4_MLP", LOAD_MAIN), r.pair("H4_MLP", LOAD_LIGHT)
    check(lin30["hi"] < 0 and bool(f4[LABELS["lin"]][str(LOAD_MAIN)]["beats_hand"]), "H4 (linear) is supported")
    check(not f4[LABELS["lin"]][str(LOAD_LIGHT)]["tost_equivalent"], "H4's light-load equivalence fails (linear)")
    check(mlp30["hi"] >= 0 and mlp10["hi"] >= 0, "the network did not beat the hand-built bids at 10 or 30 %")
    check(mlp30["lo"] < 0 < mlp30["hi"] and mlp10["lo"] < 0 < mlp10["hi"], "neither network interval excludes zero")
    V["P1-H4-LIN-DIFF-30"], V["P1-H4-LIN-DIFF-10"] = h_(-lin30["mean"]), h_(-lin10["mean"])
    V["P1-H4-LIN-PCT-30"] = pc(-100 * lin30["share_of_b"], 1)
    V["P1-H4-LIN-PCT-30-ABS"] = pc(abs(100 * lin30["share_of_b"]), 1)
    V["P1-H4-LIN-PCT-10"] = pc(-100 * lin10["share_of_b"], 1)
    V["P1-H4-LIN-CI-30"], V["P1-H4-LIN-CI-10"] = ci_abs(lin30), ci_abs(lin10)
    V["P1-H4-MLP-DIFF-30"], V["P1-H4-MLP-DIFF-10"] = h_(mlp30["mean"], 2, sign=True), h_(mlp10["mean"], 2, sign=True)
    V["P1-H4-MLP-CI-30"], V["P1-H4-MLP-CI-10"] = ci_h(mlp30["lo"], mlp30["hi"]), ci_h(mlp10["lo"], mlp10["hi"])
    V["P1-H4-N"] = f"{int(lin30['n'])}"
    V["P1-H4-LIN-PHOLM"] = p_eq(holm[LABELS["holm_H4_LIN"]])
    if lin10["hi"] < 0:
        V["P1-H4-LIGHT-CLAUSE"] = "and the linear model helped there too"
    elif lin10["lo"] < 0 < lin10["hi"]:
        V["P1-H4-LIGHT-CLAUSE"] = ("and there the data could show neither a gain nor its absence: the "
                                   f"interval ({ci_h(lin10['lo'], lin10['hi'])}) includes zero and reaches past the "
                                   "&plusmn;2&#8239;% margin")
    else:
        V["P1-H4-LIGHT-CLAUSE"] = "and there the linear model was worse than the hand-built bids"
    g = r.L["guards"][str(LOAD_HEAVY)]
    for k in ("delay_prio2_mean_h", "delay_mean_bulk", "delay_mean_h", "tonne_days_waiting"):
        check(g[k]["linear"] < g[k]["hand"], f"guard {k} fell with the learned bids at 60 %")
    check(abs(g["delivered_kg"]["linear"] / g["delivered_kg"]["hand"] - 1) < 0.005, "tonnes delivered did not change")
    V["P1-GUARD-TONNEDAYS-PCT"] = pc(100 * (g["tonne_days_waiting"]["linear"] / g["tonne_days_waiting"]["hand"] - 1), 0,
                                     sign=True)
    ood = r.L["ood"]
    diffs = {k: v["linear"]["vs_hand_h"] for k, v in ood.items()}
    check(all(d["mean"] < 0 for d in diffs.values()), "the linear model kept the same sign in every OOD cell")
    V["P1-OOD-N-CELLS"] = words(len(diffs))
    V["P1-OOD-N-SIG"] = words(sum(d["ci95"][1] < 0 for d in diffs.values()))
    # the linear weights in plain words: the output is a bid correction in hours (positive = bids lower = favoured)
    w = np.asarray(r.lin["layers"][0]["w"], float).reshape(-1)
    names, scale = r.lin["obs"]["names"], r.lin["obs"]["scale"]
    if len(w) != len(names):
        raise ValueError("linear policy: weights and feature names differ in length")
    order = np.argsort(-np.abs(w))
    fav = [i for i in order if w[i] > 0][:3]
    dis = [i for i in order if w[i] < 0][:3]
    unit = lambda i: f"{num(w[i], 2, sign=True)}{NB}h per unit" + (f" ({names[i]} scaled by 1/{scale[i]:g})"
                                                                     if scale[i] != 1 else "")
    V["P1-LIN-WEIGHTS-SENTENCE"] = (
        "The largest weights lower the bid, and so favour the item, for " +
        listing(f"{FEATURE_WORDS[names[i]]} ({unit(i)})" for i in fav) +
        ", and raise it for " + listing(f"{FEATURE_WORDS[names[i]]} ({unit(i)})" for i in dis) +
        "; the remaining weights are smaller than these.")

    # --- the learned models and their training ------------------------------------------------------------
    im = r.L["imitation"]
    V["P1-IMIT-AGREE"] = sh(im["hand_agreement_val"], 1)
    m = re.search(r"\((\d+) of (\d+) at 30 % load, (\d+) of (\d+) at 60 %", im["finding"])
    if not m:
        raise ValueError("imitation finding does not state the disagreement counts")
    V["P1-IMIT-DISAGREE-30"], V["P1-IMIT-DISAGREE-60"] = f"{m.group(1)} of {m.group(2)}", f"{m.group(3)} of {m.group(4)}"
    V["P1-IMIT-N-ROUNDS"], V["P1-IMIT-N-ROWS"] = f"{im['groups']:,}", f"{im['rows']:,}"
    pol = r.L["policies"]
    cl, cm = pol["linear"]["cem"], pol["mlp"]["cem"]
    V["P1-TRAIN-WALL-H"] = f"{(cl['wall_s'] + cm['wall_s']) / 3600:.1f}{NB}h"
    V["P1-N-FEATURES"] = words(len(names))
    if r.mlp["obs"]["names"] != names:
        raise ValueError("the MLP and the linear policy use different features")
    V["P1-LIN-N-WEIGHTS"] = f"{len(w)}"
    check(cl["parameters_searched"] == len(w), "the linear search covered all its weights")
    n_params = sum(np.asarray(L["w"]).size + np.asarray(L["b"]).size for L in r.mlp["layers"])
    hidden = {np.asarray(L["w"]).shape[0] for L in r.mlp["layers"][:-1]}
    if len(hidden) != 1:
        raise ValueError(f"MLP hidden layers differ in width: {hidden}")
    V["P1-MLP-N-PARAMS"], V["P1-MLP-HIDDEN"] = f"{n_params:,}", f"{hidden.pop()}"
    V["P1-CEM-LIN-GENS"], V["P1-CEM-LIN-POP"] = f"{cl['generations']}", f"{cl['population']}"
    V["P1-CEM-MLP-GENS"], V["P1-CEM-MLP-POP"] = f"{cm['generations']}", f"{cm['population']}"
    V["P1-CEM-MLP-N-SEARCHED"] = f"{cm['parameters_searched']}"
    tr, tu = seeds_in(cl["fitness"]), seeds_in(cl["selection"])
    if (tr, tu) != (seeds_in(cm["fitness"]), seeds_in(cm["selection"])):
        raise ValueError("the two CEM runs used different seeds")
    check(all(1000 <= s < 2000 for s in tr) and all(s >= 2000 for s in tu), "training and tuning seeds never touch 1-30")
    V["P1-CEM-N-TRAIN-SEEDS"], V["P1-CEM-N-TUNE-SEEDS"] = words(len(tr)), words(len(tu))
    check(cm["selected_generation"] == 0 and cl["selected_generation"] == cl["generations"] - 1,
          "the network's best came first, the linear model's last")
    check(cm["population"] * cm["generations"] / cm["parameters_searched"] <
          cl["population"] * cl["generations"] / cl["parameters_searched"],
          "the network was searched with fewer candidates per weight")

    # --- sensitivities, checks, runtime --------------------------------------------------------------------
    hp = r.pair("hopper_O", LOAD_MAIN)
    check(hp["lo"] < 0 < hp["hi"], "hopper refuelling changed nothing that matters")
    V["P1-HOPPER-O-DIFF"], V["P1-HOPPER-O-CI"] = h_(hp["mean"], 2, sign=True), ci_h(hp["lo"], hp["hi"])
    b = r.bounds
    V["P1-BOUNDS-N"] = f"{b['instances']}"
    V["P1-BOUNDS-SSI-MAX"] = f"{_fin(b['ssi_vs_hungarian']['ratio_max']):.3f}"
    V["P1-BOUNDS-CBBA-MIN"] = sh(min(v["score_share_min"] for v in b["cbba_lite_vs_optimum"].values()), 1)
    dev = r.dev
    V["P1-RALLY-OFF-DEV-T"] = t_(dev["rally_dev_run"]["leader_delivered_t_without_rule"])
    V["P1-RALLY-ON-DEV-T"] = t_(dev["rally_dev_run"]["leader_delivered_t_with_rule"])
    V["P1-CHECK-N-ROWS"] = f"{dev['regression_check']['rows_rerun_identical']}"
    V["P1-CHECK-N-TESTS"] = f"{dev['regression_check']['pytest_tests']}"
    V["P1-PEAK-MB"] = f"{dev['runtime']['peak_memory_mb']}{NB}MB"
    run_s = pd.concat([d["run_s"] for d in r.runs.values()])
    hi_s = float(run_s.max())
    V["P1-RUNTIME-RANGE"] = (f"{num(run_s.min(), 1)}{NB}s to " +
                             (f"{num(hi_s / 3600, 1)}{NB}h" if hi_s >= 3600 else f"{num(hi_s, 0)}{NB}s"))
    npc = r.fit("n_per_cell")
    v1_counts = {k: v for k, v in npc.items() if k.endswith("|v1")}
    check(all(v == 30 for k, v in v1_counts.items() if not k.startswith(f"{LOAD_HEAVY}|")),
          "every cell at 10 and 30 % holds exactly the 30 v1 seeds")
    short60 = {k: v for k, v in v1_counts.items() if k.startswith(f"{LOAD_HEAVY}|") and v != 30}
    if short60:      # the 60 % block is LEAD's background job; until it completes the draft is pending, not wrong
        if not allow_pending:
            raise SystemExit(f"E40 60 % cells incomplete: {short60}")
        pending.append(f"E40 60 % cells incomplete: {short60}")
    V["P1-SEEDS-ADDED"] = ("No seeds were added: every cell holds the 30 seeds of the design"
                           + (" (and the 50 runs of the second block where it applies)" if any(
                               k.endswith("|v3") for k in npc) else "") + ".")
    check(not r.rerun["flagged"], "the rerun after the ordering fix changed no cell")

    # --- E41 (pending until it runs) -------------------------------------------------------------------------
    def rally(label, col, fmt):
        g = r.runs_of("E41", LABELS[label])
        return fmt(g[col].mean())
    fill("P1-E41-RALLY-ON-URGENT", lambda: rally("E41_rally_on", M, h_), "E41")
    fill("P1-E41-RALLY-OFF-URGENT", lambda: rally("E41_rally_off", M, h_), "E41")
    fill("P1-E41-RALLY-ON-T", lambda: rally("E41_rally_on", "delivered_kg", lambda x: t_(x / 1000)), "E41")
    fill("P1-E41-RALLY-OFF-T", lambda: rally("E41_rally_off", "delivered_kg", lambda x: t_(x / 1000)), "E41")
    for key in ("P1-E41-LOSS-SENTENCE", "P1-E41-DEPTH-SENTENCE", "P1-E41-RANGE-SENTENCE"):
        fill(key, lambda: (_ for _ in ()).throw(Pending("E41 prose is written from table_E41_*.csv once it exists")),
             "E41")

    # --- H6 (E42) ------------------------------------------------------------------------------------------
    f6 = r.fit("hypotheses", "H6")
    check(bool(f6["supported"]), "H6 is supported")
    parts = []
    for team in ("10", "25"):
        ti = r.pair("H6_team_items", LOAD_MAIN, team=team, loss="0.1")
        parts.append(f"from {sh(ti['b_mean'])} to {sh(ti['b_mean'] + ti['mean'])} at team share 0.{team} "
                     f"(paired difference {num(100 * ti['mean'], 0, sign=True)} percentage points, 95&#8239;% CI "
                     f"{num(100 * ti['lo'], 0)} to {num(100 * ti['hi'], 0)}, n = {int(ti['n'])})")
        check(ti["lo"] > 0, f"cross-owner pairs raise the share of team items delivered at team share 0.{team}")
    all_items = [r.pair("H6", LOAD_MAIN, team=t, loss="0.1") for t in ("10", "25")]
    check(all(a["lo"] > 0 for a in all_items), "cross-owner pairs raise the share of all items delivered")
    held = all(r.pair("H6", LOAD_MAIN, team=t, loss=l)["lo"] > 0 for t in ("10", "25") for l in ("0.25", "0.4"))
    V["P1-H6-SHARE-SENTENCE"] = (
        "Allowing pairs of different owners raised the share of team items delivered " + " and ".join(parts) +
        " at message loss 0.10, and the share of all items delivered by " +
        listing(f"{num(100 * a['mean'], 1, sign=True)} percentage points ({num(100 * a['lo'], 1)} to "
                f"{num(100 * a['hi'], 1)})" for a in all_items) +
        f". H6's first part is supported (Holm-adjusted p {p_eq(holm[LABELS['holm_H6']])}). The gain "
        + ("held" if held else "did not hold in every cell") + " at loss 0.25 and 0.40 (Table 8).")
    mt = f6["meetings"]
    def meet(key, **fmt):
        label = LABELS[key].format(**fmt)
        if label not in mt:
            raise KeyError(f"meetings cell {label!r} not in E40_fit.json")
        return mt[label]
    fm = "atc_failed_meetings"
    base = {l: meet("E42_meet", loss=l)[fm] for l in ("0.1", "0.25", "0.4")}
    noc = {l: meet("E42_meet_nocommit", loss=l)[fm] for l in ("0.25", "0.4")}
    rises = base["0.1"] < base["0.25"] < base["0.4"]
    def compare(a, b):
        if abs(a - b) <= 0.1 * max(a, b, 1e-9):
            return "about as many"
        return "fewer" if a < b else "more"
    arb = {l: meet("E42_meet_arb", loss=l)[fm] for l in ("0.25", "0.4")}
    to = {t: meet("E42_meet_timeout", loss="0.25", to=t)["atc_meeting_wait_h"] for t in ("0.5", "2")}
    to1 = meet("E42_meet", loss="0.25")["atc_meeting_wait_h"]
    V["P1-H6-MEETINGS-SENTENCE"] = (
        f"Failed meetings {'rose' if rises else 'did not rise steadily'} with message loss: at team share 0.25 the "
        f"auction with the commit step and a 1&nbsp;h timeout had on average {num(base['0.1'], 1)} failed meetings "
        f"per year at loss 0.10, {num(base['0.25'], 1)} at 0.25 and {num(base['0.4'], 1)} at 0.40. Without the "
        f"commit step it had {compare(noc['0.25'], base['0.25'])} at loss 0.25 ({num(noc['0.25'], 1)}) and "
        f"{compare(noc['0.4'], base['0.4'])} at 0.40 ({num(noc['0.4'], 1)}), so the second part of H6, that failed "
        f"meetings rise without a commit step, is "
        + ("supported" if all(noc[l] > 1.1 * base[l] for l in noc) else "not supported") +
        f" (cell means, no interval). The timeout trades waiting for failures: at loss 0.25 the hours robots spent "
        f"waiting at meeting points were {num(to['0.5'], 1)} with a 0.5&nbsp;h timeout, {num(to1, 1)} with 1&nbsp;h "
        f"and {num(to['2'], 1)} with 2&nbsp;h. The exploratory variant in which the base computer arbitrates each "
        f"meeting had {num(arb['0.25'], 1)} and {num(arb['0.4'], 1)} failed meetings at loss 0.25 and 0.40.")
    check(to["0.5"] < to1 < to["2"], "meeting wait grows with the timeout")
    # one clause for the abstract, 6.1 and the conclusion: the team-share-0.10 lift in team items and the commit step's
    # effect, with the same rule as the meetings sentence (supported if failures without the step exceed 1.1x)
    t10 = r.pair("H6_team_items", LOAD_MAIN, team="10", loss="0.1")
    commit_helped = all(noc[l] > 1.1 * base[l] for l in noc)
    V["P1-H6-ABSTRACT-CLAUSE"] = (
        f"Letting robots of different owners lift heavy crates together raised the share of team items delivered "
        f"from {sh(t10['b_mean'])} to {sh(t10['b_mean'] + t10['mean'])}, and a commit step before each meeting "
        f"{'reduced' if commit_helped else 'did not reduce'} failed meetings under message loss")

    # --- tables and the figure ---------------------------------------------------------------------------
    V["P1-TABLE-REGIMES"] = table_regimes(r)
    V["P1-TABLE-OOD"] = table_ood(r)
    V["P1-FIG-H2-YEARS"] = fig_h2_years(r, yrs, vis, margin)
    V["P1-REFERENCES"] = references()
    T = {"pairs": table_pairs(r, holm), "e42": table_e42(r)}
    if broken:
        raise SystemExit("the text asserts what the data contradict:\n  " + "\n  ".join(broken))
    return V, T, pending


# ---------------------------------------------------------------------------------------------------------
# tables and the figure
# ---------------------------------------------------------------------------------------------------------
def _tab(caption, head, rows, cls="", note=""):
    out = [f'<p class="tabcap">{caption}</p>', f'<table class="{cls}">' if cls else "<table>",
           "<tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr>"]
    out += ["<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows]
    out.append("</table>")
    if note:
        out.append(f'<p class="tabnote">{note}</p>')
    return "\n".join(out)


def table_regimes(r: R):
    """Table 5: every E40 cell at each load (the 60 % block shows how many runs it has so far)."""
    rows = []
    M = "atc_urgent_wait_mean_cens_h"
    for load in (LOAD_LIGHT, LOAD_MAIN, LOAD_HEAVY):
        d = r.r[r.r["load"] == load].sort_values(M, ascending=False)
        if len(d) == 0:
            continue
        for _, c in d.iterrows():
            lab = html.escape(c["label"]) + ("&dagger;" if bool(c["earth_independent"]) else "")
            n = f"{int(c['n_v1'])}" if bool(c["earth_independent"]) else f"{int(c['n'])}"
            rows.append([f"{load}" if not rows or rows[-1][0] != f"{load}" else "", lab, n, num(c[M], 1),
                         num(c["atc_urgent_wait_p95_cens_h"], 0), sh(c["atc_urgent_within24_share"]),
                         num(c["delivered_kg"] / 1000, 0), num(c["backlog_kg"] / 1000, 0),
                         sh(c["utilisation"], 1)])
    return _tab("<b>Table 5.</b> Each decision regime at each load: mean urgent wait (h, censored at the horizon), "
                "its 95th percentile, the share of urgent items delivered within a day, tonnes delivered and left in "
                "the backlog at the end of the year, and whole-fleet utilisation. Cell means over the runs listed.",
                ["Load (%)", "Regime", "Runs", "Urgent wait (h)", "p95 (h)", "Within 24 h", "Delivered (t)",
                 "Backlog (t)", "Fleet busy"], rows, cls="wide",
                note="&dagger; Earth-independent regime: a seed gives the same run in every start year, so only the "
                     "30 runs of the v1 block are counted (PREREG change 4). The 60&#8239;% block is partial where "
                     "it shows fewer runs than the design.")


def table_ood(r: R):
    rows = []
    for cell, v in r.L["ood"].items():
        d = v["linear"]["vs_hand_h"]
        rows.append([html.escape(cell), num(v["hand"]["urgent_mean_h"], 1), num(v["linear"]["urgent_mean_h"], 1),
                     f"{num(d['mean'], 2, sign=True)} [{num(d['ci95'][0], 2)}, {num(d['ci95'][1], 2)}]", f"{d['n']}"])
    return _tab("<b>Table 6.</b> The linear bids outside their training range: mean urgent wait (h) with hand-built "
                "and learned bids, and the paired difference with its 95&#8239;% interval, on seeds the model never "
                "saw.", ["Cell", "Hand-built (h)", "Learned (h)", "Difference (h)", "n"], rows)


def table_pairs(r: R, holm):
    """Table 7: the confirmatory family at the middle load with raw and Holm-adjusted p."""
    fam = [("H1", r.pair("H1", LOAD_MAIN), LABELS["holm_H1"], -1),
           ("H2", r.pair("H2_pooled", LOAD_MAIN), LABELS["holm_H2"], +1),
           ("H4, linear", r.pair("H4_LIN", LOAD_MAIN), LABELS["holm_H4_LIN"], -1),
           ("H4, network", r.pair("H4_MLP", LOAD_MAIN), LABELS["holm_H4_MLP"], -1),
           ("H6", r.fit("hypotheses", "H6", "test"), LABELS["holm_H6"], +1)]
    rows = []
    for name, row, hk, sign in fam:
        adj = holm[hk]
        ok = adj < 0.05 and np.sign(row["mean"]) == sign
        unit = "" if row["metric"] == "delivered_share" else NB + "h"
        val = (f"{num(100 * row['mean'], 1, sign=True)} pp [{num(100 * row['lo'], 1)}, {num(100 * row['hi'], 1)}]"
               if not unit else f"{num(row['mean'], 1, sign=True)}{unit} [{num(row['lo'], 1)}, {num(row['hi'], 1)}]")
        rows.append([name, html.escape(row["comparison"]), row["block"], f"{int(row['n'])}", val,
                     pfmt(row["p"]), pfmt(adj),
                     "supported" if ok else ("wrong direction" if adj < 0.05 else "not supported")])
    return _tab("<b>Table 7.</b> The confirmatory family at the middle load: paired mean difference with its "
                "95&#8239;% bootstrap interval, the two-sided bootstrap p and Holm's adjusted p. H3a is an "
                "equivalence claim and is tested in Section 5.4.",
                ["Hypothesis", "Comparison", "Block", "n", "Difference [95&#8239;% CI]", "p", "Holm p", "Outcome"],
                rows, cls="wide")


def table_e42(r: R):
    cells = r.fit("E42", "cells")
    rows = []
    for label, c in cells.items():
        rows.append([html.escape(label), f"{c['n']}", num(c["atc_urgent_wait_mean_cens_h"], 1),
                     num(c["delivered_kg"] / 1000, 0),
                     f"{num(c['p5_team_items_delivered'], 1)} of {num(c['p5_team_items'], 1)}",
                     num(c["atc_failed_meetings"], 1), num(c["atc_team_no_agreement"], 1),
                     num(c["atc_meeting_wait_h"], 1)])
    return _tab("<b>Table 8.</b> Every E42 cell at the middle load: mean urgent wait (h), tonnes delivered, team "
                "items delivered out of those offered, failed meetings, meetings with no agreement and the hours "
                "robots waited at meeting points, all per simulated year.",
                ["Cell", "n", "Urgent wait (h)", "Delivered (t)", "Team items", "Failed meetings", "No agreement",
                 "Meeting wait (h)"], rows, cls="wide")


def fig_h2_years(r: R, yrs, vis, margin):
    """Figure 1 as inline SVG: the per-year B strict minus marketplace difference with its interval, and the
    base's Earth visibility under each year."""
    years = sorted(yrs)
    W, H, L, B = 640, 300, 56, 60
    top = max(v["hi"] for v in yrs.values()) * 1.1
    y = lambda v: H - B - (H - B - 20) * v / top
    step = (W - L - 20) / len(years)
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" role="img" '
         f'aria-label="Per-year difference in urgent wait, strict dispatcher on Earth minus the marketplace">',
         f'<line x1="{L}" y1="{y(0):.1f}" x2="{W - 20}" y2="{y(0):.1f}" stroke="#777"/>',
         f'<line x1="{L}" y1="{y(margin):.1f}" x2="{W - 20}" y2="{y(margin):.1f}" stroke="#999" stroke-dasharray="4 3"/>',
         f'<text x="{W - 22}" y="{y(margin) - 4:.1f}" font-size="10" text-anchor="end" fill="#555">10&#8239;% of the '
         f'marketplace mean</text>']
    for t in np.linspace(0, top, 5)[1:]:
        s.append(f'<text x="{L - 6}" y="{y(t) + 3:.1f}" font-size="10" text-anchor="end" fill="#555">{t:.0f}</text>')
    for i, yr in enumerate(years):
        v = yrs[yr]
        x = L + step * (i + 0.5)
        s += [f'<rect x="{x - step * 0.25:.1f}" y="{y(v["mean"]):.1f}" width="{step * 0.5:.1f}" '
              f'height="{y(0) - y(v["mean"]):.1f}" fill="#4a6fa5"/>',
              f'<line x1="{x:.1f}" y1="{y(v["lo"]):.1f}" x2="{x:.1f}" y2="{y(v["hi"]):.1f}" stroke="#222"/>',
              f'<text x="{x:.1f}" y="{H - B + 14}" font-size="11" text-anchor="middle">{yr}</text>',
              f'<text x="{x:.1f}" y="{H - B + 28}" font-size="10" text-anchor="middle" fill="#555">'
              f'{100 * vis[str(yr)]:.1f}&#8239;% in view</text>',
              f'<text x="{x:.1f}" y="{H - B + 41}" font-size="10" text-anchor="middle" fill="#555">n = {int(v["n"])}</text>']
    s.append(f'<text x="14" y="{(H - B) / 2:.0f}" font-size="10" fill="#555" transform="rotate(-90 14 {(H - B) / 2:.0f})" '
             f'text-anchor="middle">difference in mean urgent wait (h)</text>')
    s.append("</svg>")
    return ('<figure id="p1-fig-h2-years">' + "\n".join(s) +
            "<figcaption><b>Figure 1.</b> The strict dispatcher on Earth minus the full-information marketplace, "
            "mean urgent wait per start year with base visibility below 60&#8239;%, with 95&#8239;% bootstrap "
            "intervals and the pre-registered margin.</figcaption></figure>")


def references():
    notes = open(os.path.join(HERE, "NOTES.md"), encoding="utf-8").read()
    out = ['<ol class="refs">']
    for m in re.finditer(r"^\[(\d+)\]\s+(.+?)(?=\n\n|\n\[\d+\]|\Z)", notes, re.S | re.M):
        txt = html.escape(" ".join(m.group(2).split()))
        txt = re.sub(r"\s*\((MOA|VCI|PWG|R1|added by LEAD)[^)]*\)\s*$", "", txt)       # the note's grade, not for print
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
    for name, tab in T.items():
        marker = f"<!-- TABLE:{name} -->"
        if marker not in doc:
            raise SystemExit(f"{marker} marker missing from the parts")
        doc = doc.replace(marker, tab)
    used = set(re.findall(r"\{\{(P1-[A-Z0-9.-]+)\}\}", re.sub(r"<!--.*?-->", "", doc, flags=re.S)))
    doc = re.sub(r"\{\{(P1-[A-Z0-9.-]+)\}\}", lambda x: V[x.group(1)] if x.group(1) in V else x.group(0), doc)
    left = sorted(set(re.findall(r"\{\{P1-[^}]*\}\}", re.sub(r"<!--.*?-->", "", doc, flags=re.S))))
    if left:
        raise SystemExit(f"unfilled placeholders: {left}")
    body = re.sub(r"<[^>]+>", " ", re.sub(r"<!--.*?-->", "", doc, flags=re.S))
    if re.search(r"\b(nan|NaN|inf)\b", body):
        raise SystemExit("nan/inf in the assembled text: " + re.search(r".{40}\b(nan|NaN|inf)\b.{40}", body).group(0))
    listed = set(re.findall(r"\bP1-[A-Z0-9][A-Z0-9.-]*[A-Z0-9]\b", open(os.path.join(HERE, "PLACEHOLDERS.md"), encoding="utf-8").read()))
    if used - listed:
        raise SystemExit(f"placeholders in the parts but not in PLACEHOLDERS.md: {sorted(used - listed)}")
    unused = sorted(k for k in V if k not in used)
    if unused:
        print("note: values not used in the text:", ", ".join(unused))
    # the abstract has four parts and 250-300 words (writing guide §7); with pending markers the count is only noted
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
    # the conclusion has 150-250 words
    m = re.search(r'<h2 id="p1-sec-conclusion">.*?</h2>(.*?)<h2', doc, re.S)
    n_con = len(html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S))).split())
    if not 150 <= n_con <= 250:
        raise SystemExit(f"conclusion has {n_con} words; the target is 150-250")
    print(f"conclusion: {n_con} words")
    out = os.path.join(HERE, "paper.html")
    open(out, "w", encoding="utf-8", newline="\n").write(doc)
    json.dump({k: v for k, v in V.items() if not k.startswith("P1-TABLE") and k not in ("P1-REFERENCES", "P1-FIG-H2-YEARS")},
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
