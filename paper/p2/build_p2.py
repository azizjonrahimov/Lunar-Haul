"""Assemble paper P2 ("Rules of the road on the Moon and Mars"): fill every {{P2-...}} placeholder from the phase-5
results, insert the tables and the figure, write paper/p2/paper.html and render the PDF with headless Chrome.

    python paper/p2/build_p2.py [--no-pdf] [--allow-pending]

Sources (read-only): results/table_E43_cells.csv and table_E43_pairs.csv and E43_fit.json (analyse_e43_pairs.py),
results/ATC_roads_corridor.json (the corridor analysis), data/scenarios/p5/E43-design.json (the design with its dated
changes), the raw E43 run files (counts and run times), and paper/p2/NOTES.md (references). E44, E45 and E47 files
(B-78, B-82) are read once they exist; until then their keys are pending.

Every comparison label the text relies on is listed once in LABELS. Rows are found by label, never by position.
Sentences whose wording depends on the outcome (the H8 verdict, the 8x clauses) are composed here from the data, and
every fixed phrase in the parts that asserts a direction is checked against the data before the build goes on; a
failed check lists every broken claim and stops. The build fails if any placeholder is left unfilled, if a filled
value contains nan or inf, or if a placeholder in the parts is not documented in PLACEHOLDERS.md.
"""
import argparse
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
from experiments.phase5 import run_phase5 as RP  # noqa: E402

PARTS = ["part1_front.html", "part2_related.html", "part3_methods.html", "part4_results.html", "part5_back.html"]
PDF = os.path.join(HERE, "rules_of_the_road_p2.pdf")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
MINUS, NB, PCT = "&minus;", "&nbsp;", "&#8239;%"
WORDS = {0: "no", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
         10: "ten", 11: "eleven", 12: "twelve"}
# E44 design (PREREG change 6): encounters generated per type
E44_N_DEFAULT = 10_000
E44_N = {1: 100_000, 7: 100_000}
T12 = {1: "following", 2: "head-on on a one-lane segment", 3: "overtaking", 4: "the junction", 5: "the ring",
       6: "the landing closure", 7: "crew", 8: "radio dropout", 9: "the nonconforming vehicle",
       10: "mixed owners and classes", 11: "charger and pad contention", 12: "planner fuzzing"}
KIND = {"viol_contact": "contacts", "viol_gap": "below the required gap", "viol_zone": "inside a closed zone",
        "viol_crew": "too close to crew", "viol_r3": "opposite directions in one segment",
        "viol_slots": "over a bay's slots"}


def sci(x):
    """A probability bound in scientific notation with one decimal: 3.0 x 10^-5."""
    x = _fin(x)
    if x <= 0:
        raise ValueError("a bound must be positive")
    e = math.floor(math.log10(x))
    m = x / 10 ** e
    if round(m, 1) >= 10:
        m, e = m / 10, e + 1
    return f"{m:.1f}{NB}&times;{NB}10<sup>{MINUS if e < 0 else ''}{abs(e)}</sup>"
PRIMARY = "delay_mean_h"
MARGIN = 0.05

LABELS = {
    "H8": "H8: atc - none, x{m}",
    "unc_none": "uncoordinated - none, x{m}, {y}",
    "unc_atc": "uncoordinated - atc, x{m}, {y}",
    "share_atc": "atc x1 share {s} - none x1",
    "share_unc": "uncoordinated x1 share {s} - none x1",
    "bay_atc": "atc x1 bay {b} - atc x1",
    "r7_atc": "atc x1 r7 - atc x1",
    # cell labels (table_E43_cells.csv `label`)
    "none": "none x{m}", "atc": "atc x{m}", "unc": "uncoordinated x{m}",
    "atc_share": "atc x1 share {s}", "unc_share": "uncoordinated x1 share {s}", "atc_bay": "atc x1 bay {b}",
    "atc_r7": "atc x1 r7",
}


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


def h_(x, nd=1, sign=False):
    return f"{num(x, nd, sign)}{NB}h"


def pc(x, nd=1, sign=False):
    """x is a share (0-1), printed in percent."""
    return f"{num(100 * _fin(x), nd, sign)}{PCT}"


def ci(lo, hi, nd=1, unit="h"):
    u = f"{NB}{unit}" if unit else ""
    return f"[{num(lo, nd)}, {num(hi, nd)}{u}]"


def cnt(x, nd=0):
    return num(x, nd)


def words(n):
    return WORDS.get(int(n), f"{int(n):,}")


class Pending(Exception):
    pass


# ---------------------------------------------------------------------------------------------------------
# B-79: the phase-5 verification checks (results/vv_phase5.json, the schema agreed with FRONTEND on 30 Oct)
# ---------------------------------------------------------------------------------------------------------
VV5 = os.path.join(RES, "vv_phase5.json")


def vv5_load(tag, check):
    """The rows tagged to this paper, after the file's summary is recounted from its rows and every row's passed flag
    is recomputed from its error and tolerance (the site's verification page makes the same two checks)."""
    path = os.environ.get("P_VV_PHASE5", VV5)
    if not os.path.exists(path):
        raise Pending("results/vv_phase5.json (B-79) has not landed")
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    allr = d.get("rows", [])
    s = d.get("summary", {})
    ran = [x for x in allr if not x.get("skipped")]
    check(int(s.get("rows", -1)) == len(allr), "vv_phase5.json: the summary's row count equals the rows")
    check(int(s.get("passed", -1)) == sum(1 for x in ran if x.get("passed")), "vv_phase5.json: the summary's passed count equals the rows")
    check(int(s.get("failed", -1)) == sum(1 for x in ran if not x.get("passed")), "vv_phase5.json: the summary's failed count equals the rows")
    check(int(s.get("skipped", -1)) == len(allr) - len(ran), "vv_phase5.json: the summary's skipped count equals the rows")
    check(len({(x.get("id"), x.get("sub")) for x in allr}) == len(allr), "vv_phase5.json: id plus sub is unique")
    for x in ran:
        tol, err = x.get("tolerance"), (x.get("rel_error") if x.get("mode") == "rel" else x.get("error"))
        if tol is not None and err is not None:
            check(bool(x.get("passed")) == (abs(float(err)) <= float(tol)), f"check {x.get('id')} {x.get('sub')}: the passed flag agrees with its error and tolerance")
    rows = [x for x in allr if tag in (x.get("papers") or [])]
    if not rows:
        raise Pending(f"no check in results/vv_phase5.json is tagged {tag} yet (later B-79 batches)")
    return d, rows


def _vv5_err(x):
    v = x.get("rel_error") if x.get("mode") == "rel" else x.get("error")
    return "n/a" if v is None else f"{abs(float(v)):.2g}"


def vv5_checks_sentence(tag, results_section, check):
    d, rows = vv5_load(tag, check)
    kinds = {k: sum(1 for x in rows if x.get("kind") == k) for k in ("V", "Val", "Cal")}
    tech = {}
    for x in rows:
        tech[x.get("technique", "unstated")] = tech.get(x.get("technique", "unstated"), 0) + 1
    tech_txt = ", ".join(f"{html.escape(str(k))} ({cnt(v)})" for k, v in sorted(tech.items(), key=lambda kv: (-kv[1], str(kv[0]))))
    commit = str(d.get("commit") or "")
    parts = []
    if kinds["V"]:
        parts.append(f"{words(kinds['V'])} verification{'s' if kinds['V'] != 1 else ''} that the code does what the model says")
    if kinds["Val"]:
        parts.append(f"{words(kinds['Val'])} validation{'s' if kinds['Val'] != 1 else ''} against references outside the model")
    if kinds["Cal"]:
        parts.append(f"{words(kinds['Cal'])} calibration reproduction{'s' if kinds['Cal'] != 1 else ''}")
    return (f"In addition, {cnt(len(rows))} checks of the engine's phase-5 verification suite (<code>lunarsim/vv5.py</code>, results in "
            f"<code>results/vv_phase5.json</code> and on the live site's verification page) bear on this paper: " + ", ".join(parts) +
            f", by Sargent's technique {tech_txt}. Deterministic identities are held to 10<sup>&minus;9</sup> relative or exact; stochastic checks "
            f"pass when the error is within a tolerance set in advance, and a 99&#8239;% batch-means interval that misses the reference is recorded "
            f"as a bias flag, not a failure" + (f"; the checks ran at commit <code>{html.escape(commit[:7])}</code>" if commit else "") +
            f". Their outcomes are in Section {results_section}.")


def vv5_failed_sentence(tag, methods_section, check):
    d, rows = vv5_load(tag, check)
    ran = [x for x in rows if not x.get("skipped")]
    failed = [x for x in ran if not x.get("passed")]
    skipped = [x for x in rows if x.get("skipped")]
    bias = [x for x in ran if x.get("bias_flag")]
    label = lambda x: f"{html.escape(str(x.get('id')))}{(' ' + html.escape(str(x.get('sub')))) if x.get('sub') else ''}"
    if failed:
        lst = "; ".join(f"{label(x)} ({html.escape(str(x.get('name', '')))}), error {_vv5_err(x)} against a tolerance of {x.get('tolerance')}" for x in failed)
        out = (f"Of the {cnt(len(rows))} phase-5 checks of Section {methods_section} tagged to this paper, {cnt(len(failed))} failed: {lst}. "
               f"The other {cnt(len(ran) - len(failed))} that ran passed")
    else:
        out = (f"The one phase-5 check of Section {methods_section} tagged to this paper that ran passed" if len(ran) == 1 else
               f"Every one of the {cnt(len(ran))} phase-5 checks of Section {methods_section} tagged to this paper that ran passed")
    if skipped:
        out += ("; " + cnt(len(skipped)) + (" was" if len(skipped) == 1 else " were") + " not run: " +
                "; ".join(f"{label(x)} ({html.escape(str(x.get('skipped')))})" for x in skipped))
    if bias:
        out += ("; " + cnt(len(bias)) + " met " + ("its" if len(bias) == 1 else "their") + " tolerance with a 99&#8239;% interval that misses the reference, "
                "recorded as a bias flag: " + ", ".join(label(x) for x in bias))
    return out + "."


# ---------------------------------------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------------------------------------
class R:
    def __init__(self):
        rd = lambda f: pd.read_csv(os.path.join(RES, f))
        jl = lambda f: json.load(open(f, encoding="utf-8"))
        self.c = rd("table_E43_cells.csv")
        self.p = rd("table_E43_pairs.csv")
        self.f = jl(os.path.join(RES, "E43_fit.json"))
        self.k = jl(os.path.join(RES, "ATC_roads_corridor.json"))
        self.d = jl(RP.E43_DESIGN)
        files = RP.run_files("E43")
        self.runs = pd.concat([pd.read_csv(f, usecols=lambda c: c in ("cell", "label", "seed", "start_year", "run_s",
                                                                       "density", "single_share"))
                               for f in files], ignore_index=True) if files else pd.DataFrame()
        ba = os.path.join(RES, "E43_fixpoint_before_after.json")      # experiments/phase5/compare_rerun.py --exp E43
        self.ba = jl(ba) if os.path.exists(ba) else None
        self.e44 = os.path.join(RES, "E44_bounds.json")
        self.e45 = os.path.join(RES, "E45_modelcheck.json")
        self.e44j = jl(self.e44) if os.path.exists(self.e44) else None       # tools/atc/run_e44.py summarize
        d44 = os.path.join(RES, "E44_defects.json")                           # PREREG change 8
        self.e44d = jl(d44) if os.path.exists(d44) else None
        self.e45j = jl(self.e45) if os.path.exists(self.e45) else None       # tools/atc/run_e45.py
        d45 = os.path.join(RES, "E45_development.json")                       # counterexamples fixed in development
        self.e45d = jl(d45) if os.path.exists(d45) else None
        b44 = os.path.join(RES, "E44_bins.csv")                               # per-type parameter bins
        self.e44b = pd.read_csv(b44) if os.path.exists(b44) else None
        # E47 (Mars, B-82): tools/atc/run_e47.py analyse -> bounds (E44's structure), fit (headline, road cells), bins
        f47 = {k: os.path.join(RES, f"E47_{k}") for k in ("bounds.json", "fit.json", "bins.csv", "runs.csv")}
        self.e47b = jl(f47["bounds.json"]) if os.path.exists(f47["bounds.json"]) else None
        self.e47f = jl(f47["fit.json"]) if os.path.exists(f47["fit.json"]) else None
        self.e47bins = pd.read_csv(f47["bins.csv"]) if os.path.exists(f47["bins.csv"]) else None
        self.e47runs = pd.read_csv(f47["runs.csv"]) if os.path.exists(f47["runs.csv"]) else None
        d47 = os.path.join(ROOT, "data", "scenarios", "E47-design.json")
        self.e47d = jl(d47) if os.path.exists(d47) else None

    def cell(self, key, year=2028, **fmt):
        label = LABELS.get(key, key).format(**fmt)
        g = self.c[(self.c["label"] == label) & (self.c["start_year"] == year)]
        if len(g) == 0:
            raise Pending(f"E43 cell {label!r} ({year}) has no runs yet")
        if len(g) > 1:
            raise KeyError(f"E43 cell {label!r} ({year}): {len(g)} rows")
        return g.iloc[0].to_dict()

    def pair(self, key, metric=PRIMARY, **fmt):
        label = LABELS.get(key, key).format(**fmt)
        g = self.p[(self.p["comparison"] == label) & (self.p["metric"] == metric)]
        if len(g) != 1:
            raise KeyError(f"pairs row {label!r} on {metric}: {len(g)} rows "
                           f"(have {sorted(self.p['comparison'].unique())[:6]} ...)")
        row = g.iloc[0].to_dict()
        if int(row["n"]) == 0 or not np.isfinite(row["mean"]):
            raise Pending(f"{label} has no paired runs yet")
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

    def fill(key, fn, tag):
        try:
            V[key] = fn()
        except Pending as e:
            if not allow_pending:
                raise SystemExit(f"{key}: pending ({e}); rerun with --allow-pending to build a draft")
            pending.append(f"{key}: {e}")
            V[key] = f'<span class="pending">[[PENDING {tag}]]</span>'

    def pend(key, tag, why):
        fill(key, lambda: (_ for _ in ()).throw(Pending(why)), tag)

    # --- design and the roads ------------------------------------------------------------------------------
    k = r.k
    V["P2-N-RUNS-E43"] = cnt(r.f["n_rows"])
    V["P2-N-CELLS-E43"] = cnt(len(RP.e43_cells()))
    V["P2-K30"] = f"{_fin(r.d['load_multiplier_30pct']):.3f}"
    hz = r.f["horizons_days"]
    V["P2-HORIZON-X4-D"] = cnt(RP.E43_DENSITY[4][0] / 24.0)
    V["P2-HORIZON-X8-D"] = cnt(RP.E43_DENSITY[8][0] / 24.0)
    check(all(abs(h - RP.E43_DENSITY[4][0] / 24.0) < 0.01 for h in hz.get("4", [])), "every 4x row runs the design horizon")
    V["P2-N-SAMPLES"] = cnt(k["samples"])
    V["P2-ROUTE-KM"] = f"{num(k['route_km_unique'], 0)}{NB}km"
    V["P2-N-JUNCTIONS"] = cnt(k["junctions_excluded"])
    bsl = k["by_slope_limit_deg"]
    V["P2-MEDIAN-WIDTH-20"] = f"{num(bsl['20']['median_width_m'], 0)}{NB}m"
    V["P2-SLOPE-MAX"] = f"{num(k['slope_at_sample_percentiles_deg']['1.0'], 1)}&deg;"
    check(bsl["20"]["single_lane_share"] == 0, "no sample is single-lane at 20 deg")
    for lim in ("15", "10", "8"):
        V[f"P2-SINGLE-KM-{lim}"] = f"{num(bsl[lim]['single_lane_km_unique'], 1)}{NB}km"
    V["P2-SINGLE-SHARE-10"] = pc(bsl["10"]["single_lane_share"], 1)
    check(abs(bsl["10"]["single_lane_share"] - RP.SINGLE_SHARE) < 0.005, "the default share 0.15 is the 10 deg value")
    shares = sorted(float(s) for s in r.runs["single_share"].unique()) if len(r.runs) else [RP.SINGLE_SHARE]
    V["P2-SHARE-MAX-PCT"] = pc(max(shares), 0)
    V["P2-SINGLE-KM-DEFAULT"] = f"{num(r.cell('atc', m=1)['road_single_km'], 1)}{NB}km"
    fill("P2-SHARE40-SINGLE-KM", lambda: f"{num(r.cell('atc_share', s='0.4')['road_single_km'], 1)}{NB}km", "E43 share 0.4")

    # --- the road layer at 1x (5.1) --------------------------------------------------------------------
    a1 = r.cell("atc", m=1)
    V["P2-ATC-X1-TRAVERSALS"] = cnt(a1["road_traversals"])
    V["P2-ATC-X1-CONFLICTS"] = cnt(a1["road_conflicts"])
    V["P2-ATC-X1-CONFLICTS-PER-WEEK"] = num(a1["road_conflicts"] / 52.0, 1)
    V["P2-ATC-X1-BAY-WAIT-H"] = h_(a1["road_wait_h"], 1)
    V["P2-ATC-X1-APRON-WAIT-H"] = h_(a1["road_apron_wait_h"], 1)
    V["P2-ATC-X1-EVA-SLOW-H"] = h_(a1["road_eva_slow_h"], 1)
    V["P2-ATC-X1-STANDDOWNS"] = cnt(a1["plume_standdowns"])
    ow = r.f["owner_bay_wait_h_atc"]["1"]
    for o in "ABC":
        V[f"P2-OWNER-{o}-BAY-WAIT-X1"] = h_(ow[o], 1)
    check(max(ow.values()) > 1.2 * min(ow.values()), "the bay wait fell on the owners unequally")
    hi, lo = max(ow, key=ow.get), min(ow, key=ow.get)
    V["P2-OWNER-BAY-WAIT-ORDER-CLAUSE"] = f"owner {hi} waited most and owner {lo} least"
    dl = sum(r.f["deadlocks_total_by_density"].values())
    V["P2-DEADLOCKS-TOTAL"] = words(dl) if dl < 10 else cnt(dl)
    V["P2-DEADLOCKS-TOTAL-N"] = cnt(dl)
    check(dl == 0, "no run in any cell recorded a deadlock")
    # base visibility by start year (results/E40_fit.json, the same source as P1), for the E43 year choice in 4.2
    vis = json.load(open(os.path.join(RES, "E40_fit.json"), encoding="utf-8"))["hypotheses"]["H2"]["30"]["visibility"]
    V["P2-VIS-2028"] = pc(vis["2028"], 1)
    V["P2-VIS-2038"] = pc(vis["2038"], 1)
    check(vis["2028"] > vis["2038"], "2028 is the better of the two E43 start years for Earth visibility")

    # --- H8 per density (5.2, 5.3) ---------------------------------------------------------------------------
    pcts: Dict[int, float] = {}
    for m in (1, 2, 4, 8):
        def _m(m=m):
            n, a, h = r.cell("none", m=m), r.cell("atc", m=m), r.pair("H8", m=m)
            V[f"P2-NONE-X{m}-DELAY"] = h_(n[PRIMARY], 1)
            V[f"P2-H8-X{m}-DELAY"] = h_(a[PRIMARY], 1)
            V[f"P2-H8-X{m}-DIFF"] = h_(h["mean"], 2)      # the prose says "added"; positivity is checked below
            V[f"P2-H8-X{m}-DIFF-CI"] = ci(h["lo"], h["hi"], 2)
            check(h["mean"] > 0, f"the rules add delay at x{m} (the prose says 'added', without a sign)")
            V[f"P2-H8-X{m}-PCT"] = pc(h["share_of_b"], 1)
            V[f"P2-H8-X{m}-UPPER"] = pc(h["ratio_hi"], 1)     # upper end of the two-sided 95 % interval (PREREG)
            V[f"P2-ATC-X{m}-CONFLICTS"] = cnt(a["road_conflicts"])
            V[f"P2-ATC-X{m}-BAY-WAIT-H"] = h_(a["road_wait_h"], 0)
            pcts[m] = h["share_of_b"]
            return h
        try:
            _m()
        except Pending as e:
            if m != 8:
                raise
            for key in (f"P2-NONE-X{m}-DELAY", f"P2-H8-X{m}-DELAY", f"P2-H8-X{m}-DIFF", f"P2-H8-X{m}-DIFF-CI",
                        f"P2-H8-X{m}-PCT", f"P2-H8-X{m}-UPPER", f"P2-ATC-X{m}-CONFLICTS", f"P2-ATC-X{m}-BAY-WAIT-H"):
                pend(key, "E43 8x", str(e))
    h1 = r.pair("H8", m=1)
    sup = r.f["H8"]["1"]["supported"]
    check(sup == (h1["ratio_hi"] < MARGIN) == (h1["ratio_hi95"] < MARGIN),
          "the H8 verdict is the same under the two-sided interval's upper end and the one-sided bound")
    check(sup, "the rules added less than 5 % at today's fleet (abstract, intro, conclusion)")
    V["P2-H8-VERDICT-SENTENCE"] = (
        f"H8's confirmatory clause is supported: the upper bound is below the pre-registered 5{PCT} margin."
        if sup else
        f"H8's confirmatory clause is not supported: the upper bound exceeds the pre-registered 5{PCT} margin.")
    for mtr, key in (("delay_p90_h", "P2-H8-X1-P90-DIFF"), ("atc_urgent_wait_mean_cens_h", "P2-H8-X1-URGENT-DIFF")):
        row = r.pair("H8", mtr, m=1)
        V[key] = f"{h_(row['mean'], 2, sign=True)} {ci(row['lo'], row['hi'], 2)}"
    row = r.pair("H8", "delivered_items", m=1)
    V["P2-H8-X1-ITEMS-DIFF"] = f"{num(row['mean'], 1, sign=True)} {ci(row['lo'], row['hi'], 1, unit='')}"
    V["P2-X1-ITEMS"] = cnt(r.cell("none", m=1)["delivered_items"])
    row = r.pair("H8", "operator_hours", m=1)
    V["P2-H8-X1-OPERATOR-DIFF"] = f"{h_(row['mean'], 1, sign=True)} {ci(row['lo'], row['hi'], 1)}"
    check(pcts.get(1, 0) < pcts.get(2, 0) < pcts.get(4, 0), "the cost rose with the fleet (1x < 2x < 4x)")
    nd = [r.cell("none", m=m)[PRIMARY] for m in (1, 2, 4)]
    check(nd[0] > nd[1] > nd[2], "the baseline delay fell as the fleet grew")

    def x8(kind):
        if "8" not in r.f["H8"]:
            raise Pending("E43 8x cells not run (PREREG issue 5)")
        h = r.f["H8"]["8"]["test"]
        check(h["mean"] > 0, "the rules add delay at x8 (the prose says 'added', without a sign)")
        p = pc(h["share_of_b"], 1)
        return {"clause": f"and {p} at eight times",
                "sentence": f"At eight times, over {V['P2-HORIZON-X8-D']} days, the rules added {h_(h['mean'], 2)} "
                            f"{ci(h['lo'], h['hi'], 2)}, {p} (upper bound {pc(h['ratio_hi'], 1)}).",
                "disc": f"{p} of delay per delivery"}[kind]
    fill("P2-H8-X8-CLAUSE", lambda: x8("clause"), "E43 8x")
    fill("P2-H8-X8-SENTENCE", lambda: x8("sentence"), "E43 8x")
    fill("P2-H8-X8-DISCUSSION-CLAUSE", lambda: x8("disc"), "E43 8x")

    # --- uncoordinated (5.4) -------------------------------------------------------------------------------
    for m in (1, 2, 4, 8):
        for y in (2028, 2038):
            def _u(m=m, y=y):
                u, p = r.cell("unc", y, m=m), r.pair("unc_none", m=m, y=y)
                V[f"P2-UNC-X{m}-DELAY-{y}"] = h_(u[PRIMARY], 1)
                V[f"P2-UNC-X{m}-DIFF-{y}"] = h_(p["mean"], 1, sign=True)
                V[f"P2-UNC-X{m}-DIFF-CI-{y}"] = ci(p["lo"], p["hi"], 1)
                V[f"P2-UNC-X{m}-RATIO-{y}"] = num(1 + p["share_of_b"], 1)
                V[f"P2-UNC-X{m}-HAND-CONFLICTS-{y}"] = cnt(u["road_hand_conflicts"])
                V[f"P2-UNC-X{m}-HAND-WAIT-H-{y}"] = h_(u["road_hand_wait_h"], 0)
                V[f"P2-UNC-X{m}-OTHER-STOP-H-{y}"] = h_(u["road_other_stop_h"], 0)
                check(p["lo"] > 0 and u["road_hand_wait_h"] > 0, f"uncoordinated x{m} {y} costs more than the baseline")
            try:
                _u()
            except Pending as e:
                if m != 8:
                    raise
                for key in ("DELAY", "DIFF", "DIFF-CI", "RATIO", "HAND-CONFLICTS", "HAND-WAIT-H", "OTHER-STOP-H"):
                    pend(f"P2-UNC-X{m}-{key}-{y}", "E43 8x", str(e))
    for key in ("RATIO", "HAND-WAIT-H", "DELAY"):
        V[f"P2-UNC-X1-{key}"] = V[f"P2-UNC-X1-{key}-2028"]
    for y in (2028, 2038):
        p = r.pair("unc_atc", m=1, y=y)
        V[f"P2-UNC-VS-ATC-X1-DIFF-{y}"] = f"{h_(p['mean'], 1, sign=True)} {ci(p['lo'], p['hi'], 1)}"
    fill("P2-UNC-X8-SENTENCE", lambda: (_ for _ in ()).throw(Pending("E43 8x cells not run")) if "8" not in r.f["H8"]
         else f"At eight times, {V['P2-UNC-X8-RATIO-2028']} and {V['P2-UNC-X8-RATIO-2038']} times.", "E43 8x")

    # --- sweeps (5.5) ----------------------------------------------------------------------------------------
    for s, tag in (("0", "0"), ("0.05", "5"), ("0.4", "40")):
        pa, pu = r.pair("share_atc", s=s), r.pair("share_unc", s=s)
        V[f"P2-SHARE{tag}-ATC-DIFF"] = h_(pa["mean"], 2, sign=True)
        V[f"P2-SHARE{tag}-UNC-DIFF"] = h_(pu["mean"], 1, sign=True)
        if tag != "0":
            V[f"P2-SHARE{tag}-UNC-RATIO"] = num(1 + pu["share_of_b"], 1)
    pa = r.pair("share_atc", s="0.4")
    V["P2-SHARE40-ATC-DIFF-CI"] = ci(pa["lo"], pa["hi"], 2)
    V["P2-SHARE40-ATC-PCT"] = pc(pa["share_of_b"], 1, sign=True)
    V["P2-SHARE40-ATC-PCT-ABS"] = pc(abs(pa["ratio_hi"]), 1)
    V["P2-SHARE40-ATC-BAY-WAIT-H"] = h_(r.cell("atc_share", s="0.4")["road_wait_h"], 0)
    V["P2-SHARE0-UNC-HAND-CONFLICTS"] = num(r.cell("unc_share", s="0")["road_hand_conflicts"], 1)
    check(abs(r.pair("share_atc", s="0")["mean"]) < 0.5, "with no single-lane road the ATC mode is within 0.5 h of the baseline")
    for b, tag in (("0.5", "05"), ("2", "2")):
        p = r.pair("bay_atc", b=b)
        V[f"P2-BAY{tag}-ATC-VS-ATC-DIFF"] = h_(p["mean"], 2, sign=True)
        if tag == "2":
            check(p["mean"] == 0 and p["lo"] == 0 and p["hi"] == 0, "bays every 2 km change nothing (identical by construction)")
        if tag == "05":
            V["P2-BAY05-ATC-VS-ATC-DIFF-CI"] = ci(p["lo"], p["hi"], 2)
            V["P2-BAY05-ATC-TRAVERSALS"] = cnt(r.cell("atc_bay", b=b)["road_traversals"])
    p7, c7 = r.pair("r7_atc"), r.cell("atc_r7")
    check(p7["mean"] > 0, "the strict R7 reading raises the ATC mode's delay (the prose says 'rose by')")
    V["P2-R7-ATC-DIFF"] = h_(p7["mean"], 1)
    V["P2-R7-ATC-DIFF-CI"] = ci(p7["lo"], p7["hi"], 1)
    V["P2-R7-HAND-CONFLICTS"] = cnt(c7["road_hand_conflicts"])
    V["P2-R7-HAND-WAIT-H"] = h_(c7["road_hand_wait_h"], 0)
    V["P2-R7-UNLINKED-JOBS"] = cnt(c7["road_r7_unlinked_jobs"])
    check(p7["mean"] > 0.5 * r.pair("unc_none", m=1, y=2028)["mean"], "the strict R7 cost almost as much as the uncoordinated mode")
    check(pa["share_of_b"] < MARGIN, "the ATC mode's cost stayed under the margin at a 40 % share")

    # --- compute (4.7) ----------------------------------------------------------------------------------------
    rs = r.f["run_s_mean_by_label"]
    for m in (1, 2, 4):
        labs = [l for l in rs if re.fullmatch(rf"(none|atc|uncoordinated) x{m}", l)]
        V[f"P2-RUN-S-X{m}"] = f"{num(np.mean([rs[l] for l in labs]), 0)}{NB}s"
    fill("P2-RUN-S-X8-CLAUSE", lambda: (_ for _ in ()).throw(Pending("E43 8x cells not run")) if not any(
        re.fullmatch(r"(none|atc|uncoordinated) x8", l) for l in rs) else
        f"the {V['P2-HORIZON-X8-D']}-day runs at eight times took "
        f"{num(np.mean([rs[l] for l in rs if re.fullmatch(r'(none|atc|uncoordinated) x8', l)]), 0)}{NB}s", "E43 8x")
    V["P2-E43-CPU-H"] = f"{num(r.runs['run_s'].sum() / 3600.0, 1)}{NB}h" if len(r.runs) else "0"

    # --- choices after looking (4.6) --------------------------------------------------------------------------
    dc = r.d.get("design_changes", [])
    # three dated entries in E43-design.json: the 60 -> 30 d cut, the abandonment of the cut, the restoration to 60 d
    check(len(dc) == 3, "the design file holds the three dated 8x entries the text describes")
    V["P2-N-CHANGES-WORD"] = "Three"      # the share, the horizon (one choice with three dated entries), the defect
    first_s = re.search(r"took ([\d.]+) s at 60 days", dc[0]["why"]) if dc else None
    cut_s = re.search(r"went past (\d+) s", dc[1]["why"]) if len(dc) > 1 else None
    x8_days = int(round(RP.E43_DENSITY[8][0] / 24.0))
    check(bool(first_s and cut_s and x8_days == 60), "the 8x horizon entries carry the run times the sentence quotes")
    V["P2-X8-HORIZON-SENTENCE"] = (
        f"it was planned at {x8_days} days on ten seeds, cut to 30 days when the first {x8_days}-day run took "
        f"{num(float(first_s.group(1)), 0)}{NB}s, over the per-run limit of Section 4.7, abandoned when a 30-day run "
        f"went past {cut_s.group(1)}{NB}s, and restored to {x8_days} days once the defect below was fixed; no 30-day row "
        f"was ever used, and every eight-times row in this paper is a {x8_days}-day row."
        if first_s and cut_s else "see the design file.")

    def wake_sentence():
        ba = r.ba
        if ba is None:
            raise Pending("compare_rerun.py --exp E43 has not been run against the archived rows")
        if ba["n_new"] < r.f["n_rows"]:
            raise Pending("the before/after table is older than the run files")
        check(ba.get("primary_max_abs_label", "").startswith("uncoordinated"),
              "the largest single-run change of the rerun is in the uncoordinated mode")
        return (f"the dispatcher's consolidation hold re-posted a wake-up for every held lane on every call, so the "
                f"event queue grew geometrically with fleet size (the cause of the {cut_s.group(1)}{NB}s run above) and, "
                f"because one dispatch call does not reach a fixed point, the duplicates also changed assignments. "
                f"The fix, pre-registered as change 5 of [43] before any rerun row, posts one wake-up per lane and lot "
                f"and repeats dispatch at the same instant until nothing changes. Every cell of E43 was then rerun; "
                f"the {cnt(ba['n_old'])} earlier rows are archived and reproducible with the fix off. Against the "
                f"{cnt(ba['n_matched'])} archived rows with the same cell and seed, the primary outcome moved by "
                f"{h_(ba['primary_mean_change_h'], 2, sign=True)} on average and by {h_(ba['primary_mean_abs_change_h'], 1)} "
                f"in absolute value, with a largest single-run change of {h_(ba['primary_max_abs_change_h'], 0)} "
                f"(in the uncoordinated mode, whose hand-resolution waits depend on the order of events); "
                f"{pc(ba['share_rows_moved_over_0.1h'], 0)} of the rows moved by more than 0.1{NB}h. The mean run time "
                f"fell from {num(ba['run_s_old_mean'], 0)} to {num(ba['run_s_new_mean'], 0)}{NB}s and the longest run "
                f"from {num(ba['run_s_old_max'], 0)} to {num(ba['run_s_new_max'], 0)}{NB}s. Table 4 and Table 5 hold "
                f"only rerun rows; the before/after table per cell is results/E43_fixpoint_before_after.csv.")
    fill("P2-WAKE-SENTENCE", wake_sentence, "change 5 before/after")

    # cells with fewer rows than their design block (a rerun stopped before the end)
    expected = {}
    for c in r.d["cells"]:                     # the design file's cells carry label and block
        mb = re.fullmatch(r"y(\d{4}):(\d+)", c["block"])
        expected[(c["label"], int(mb.group(1)))] = int(mb.group(2))
    have = r.runs.groupby(["label", "start_year"]).size().to_dict() if len(r.runs) else {}
    short = [(lab, y, have.get((lab, y), 0), n) for (lab, y), n in expected.items() if have.get((lab, y), 0) < n]
    x8_have = sum(v for (lab, y), v in have.items() if lab.endswith(" x8"))
    V["P2-X8-STATUS-SENTENCE"] = (
        f"The eight-times cells ran at {x8_days} days on ten seeds ({cnt(x8_have)} runs) after the dispatch fix of "
        f"Section 4.6; without it they could not run, and no 30-day row was used." if x8_have else
        "The eight-times cells did not run.")
    V["P2-INCOMPLETE-CELLS-SENTENCE"] = (
        "Every cell ran all its seeds." if not short else
        "; ".join(f"the cell {html.escape(lab)} ({y}) has {cnt(h)} of {cnt(n)} seeds" for lab, y, h, n in short).capitalize()
        + ": the rerun was stopped for memory on 29 October 2026 before the end and not restarted, so its numbers are "
          "provisional and its interval is wider than the design intended.")
    r7_n = int(p7["n"])
    V["P2-R7-N-CLAUSE"] = ("on all 30 seeds" if r7_n >= expected.get(("atc x1 r7", 2028), 30) else
                           f"on the {words(r7_n)} seeds that had run when the rerun was stopped (Section 5.9)")
    fill("P2-CHECKS-SENTENCE", lambda: vv5_checks_sentence("P2", "5.9", check), "B-79")
    fill("P2-FAILED-CHECKS-SENTENCE", lambda: vv5_failed_sentence("P2", "3.8", check), "B-79")
    def shared_check_limitation():
        # empty when the engine's road layer enforces the rules through the same safety_check() the encounter
        # simulator and the checker use; the limitation sentence only if it has its own implementation
        src = open(os.path.join(ROOT, "lunarsim", "atc", "roads.py"), encoding="utf-8").read()
        if "safety_check(" in src and "from .safety import" in src:
            return ""
        return ("The logistics model's road layer enforces the reservation and closure rules in its own code and does "
                "not call the vehicle safety program, so the two implementations were checked separately.")
    fill("P2-SHARED-CHECK-LIMITATION", shared_check_limitation, "B-78")

    def deadlock_scope():
        # the checker (E45) found that R3's one-hop exit rule can deadlock on a ring of single-lane segments; the clause
        # says whether this base's road graph has such a ring at any share (results/ATC_roads_rings.json, BACKEND)
        rings = os.path.join(RES, "ATC_roads_rings.json")
        if not os.path.exists(rings):
            raise Pending("the single-lane ring check (results/ATC_roads_rings.json) has not landed")
        rg = json.load(open(rings, encoding="utf-8"))
        bs = rg["by_share"]
        d15, d05, d40 = bs["0.15"], bs["0.05"], bs["0.4"]
        check(all(len(b["ring_lengths_m"]) == b["rings"] for b in bs.values()), "ring counts match their length lists")
        check(d15["rings"] >= 1 or d15["raw_sample_cycles"] >= 1, "the ring question is undetermined at the default share")
        merged = f"{words(d15['rings'])} candidate ring of {num(d15['ring_lengths_m'][0], 0)}{NB}m" if d15["rings"] == 1 \
            else f"{words(d15['rings'])} candidate rings"
        return (f"That zero is a property of the logistics model rather than of the rule: its bays are unbounded and "
                f"its reservation table is filled one job at a time (Section 3.4), so no circular wait can form there, "
                f"and the count is a check of the code. With finite bays the exit-bay rule is not deadlock-free on a "
                f"ring of single-lane segments, as the encounter simulator's ring type shows (Section 5.6), and whether "
                f"this base has such a ring the 5{NB}m route samples cannot settle: merged to road nodes within "
                f"{num(rg['merge_m'], 0)}{NB}m they show {merged} at the default share, {words(d05['rings'])} at a "
                f"5{PCT} share and {cnt(d40['rings'])} at 40{PCT}, but the merge can itself join neighbouring roads, "
                f"and before merging the {cnt(d15['raw_sample_cycles'])} loops at the default share are one road "
                f"sampled twice by different legs. A surveyed centreline map would settle it; the samples do not.")
    fill("P2-DEADLOCK-SCOPE-CLAUSE", deadlock_scope, "E45 ring check")

    # --- E44, E45, E47 -----------------------------------------------------------------------------------------
    e44 = ("P2-E44-N-ENCOUNTERS", "P2-E44-DESIGN-SENTENCE", "P2-E44-DESIGN-SENTENCE-SHORT", "P2-E44-INTRO-CLAUSE",
           "P2-E44-RESULTS-PARAGRAPH", "P2-E44-DISCUSSION-CLAUSE", "P2-E44-COMPARISON-CLAUSE", "P2-E44-COMPUTE-SENTENCE",
           "P2-H7-ABSTRACT-CLAUSE")
    e45 = ("P2-E45-N-NODES", "P2-E45-DESIGN-SENTENCE", "P2-E45-INTRO-CLAUSE", "P2-E45-RESULTS-PARAGRAPH",
           "P2-E45-DISCUSSION-CLAUSE", "P2-E45-COMPUTE-SENTENCE", "P2-CONCLUSION-SAFETY-CLAUSE")

    # ---- E44: the encounter simulator (results/E44_bounds.json, E44_defects.json; PREREG changes 6 and 8) -----
    def e44():
        j = r.e44j
        if j is None:
            raise Pending("E44 (encounter simulator, B-78) has not run")
        ty = j["types"]
        missing = [k for k in range(1, 13) if str(k) not in ty]
        if missing:
            raise Pending(f"E44 types {missing} have no rows yet")
        short = [k for k in range(1, 13) if ty[str(k)]["n"] < E44_N.get(k, E44_N_DEFAULT)]
        if short:
            raise Pending(f"E44 types {short} are below their designed n")
        if r.e44d is None:
            raise Pending("results/E44_defects.json (change 8) is missing")
        if "change_9" not in r.e44d:
            raise Pending("E44_defects.json has no change_9 record (the type-6 rerun of change 9 has not landed)")
        return j

    def t44(j, k):
        return j["types"][str(k)]

    def c9():
        """The change-9 record of E44_defects.json (type-6 builder defect, metric change, deadlock finding)."""
        return r.e44d["change_9"]

    def deadlocked_clean(j, zero):
        """Types with no violation whose deadlock count is not zero: clean of violations, not live."""
        return [k for k in zero if t44(j, k)["outcomes"]["deadlock"] > 0]

    def cp_upper(k, n, alpha):
        """Clopper-Pearson upper limit for k events in n at level 1 - alpha."""
        from scipy.stats import beta
        return 1.0 if k >= n else float(beta.ppf(1 - alpha, k + 1, n - k))

    def weighted_bound(t, alpha):
        """The violating type's bound on its weighted violation share at the effective n (3.5 promises n_eff)."""
        return cp_upper(t["outcome_shares_weighted"]["violation"] * t["n_eff"], t["n_eff"], alpha)

    def not_driven_clause(j):
        nd = {k: t44(j, k)["outcomes"]["not_driven"] for k in range(1, 13) if t44(j, k)["outcomes"]["not_driven"] > 0}
        return " and ".join(f"{cnt(v)} type-{k} draws" for k, v in nd.items()) + " could not hold the vehicle on the slope"

    def deadlock_clause(j, zero):
        """Abstract and conclusion: every type clean of violations but not live, type 5 included (PREREG change 6)."""
        dc = deadlocked_clean(j, zero)
        parts = []
        for k in dc:
            t = t44(j, k)
            if k == 5:
                parts.append(f"the ring of one-lane segments with finite bays deadlocked in "
                             f"{pc(t['outcomes']['deadlock'] / t['n_driven'], 1)} of its encounters")
            elif k == 6:
                parts.append(f"the landing closure {words(t['outcomes']['deadlock'])} times in {cnt(t['n_driven'])} "
                             f"at a crossing on the zone boundary")
            else:
                parts.append(f"type {k} in {cnt(t['outcomes']['deadlock'])} encounters")
        return ", and ".join(parts) if len(parts) <= 2 else "; ".join(parts)

    def e44_split(j):
        zero = [k for k in range(1, 13) if t44(j, k)["violations"] == 0]
        viol = [k for k in range(1, 13) if t44(j, k)["violations"] > 0]
        return zero, viol

    def e44_violating_clause(j, viol, with_counts=True):
        """One clause per violating type; type 9's dead stop is named, the others are generic."""
        parts = []
        for k in viol:
            t = t44(j, k)
            kinds = {kk: v for kk, v in t["violations_by_kind"].items() if v > 0}
            if k == 9:
                gap, con = t["violations_by_kind"]["viol_gap"], t["violations_by_kind"]["viol_contact"]
                parts.append(f"a vehicle that stops dead inside a one-lane segment (type 9), where the following "
                             f"vehicle closed below the required gap in {cnt(gap)} of {cnt(t['n'])} encounters and "
                             f"touched it in {cnt(con)}, because the gap rule assumes a leader that brakes rather "
                             f"than stops")
            else:
                parts.append(f"type {k} ({T12[k]}), with {cnt(t['violations'])} violations "
                             f"({', '.join(f'{cnt(v)} {KIND[kk]}' for kk, v in kinds.items())})")
        return ("the exception is " if len(parts) == 1 else "the exceptions are ") + "; ".join(parts)

    def e44_n_encounters():
        j = e44()
        return cnt(sum(t44(j, k)["n_driven"] for k in range(1, 13)))
    fill("P2-E44-N-ENCOUNTERS", e44_n_encounters, "E44")

    def e44_design_sentence():
        j = e44()
        nm = j["near_miss_definition"]
        t1 = t44(j, 1)
        d = r.e44d["defects_found_in_main_run"]
        check(len(d["defects"]) == 2, "two simulator defects were found in the first main run")
        return (f"Types 1 and 7 run {cnt(E44_N[1])} encounters each and the other ten {cnt(E44_N_DEFAULT)} (change 6 "
                f"of [43], a cost of compute on the shared machine that weakens those bounds tenfold); type-1 draws "
                f"whose slope and friction cannot hold the vehicle ({pc(1 - t1['n_driven'] / t1['n'], 0)} of them) "
                f"are not driven and are counted apart. Each type's bound is the 95{PCT} upper limit on the "
                f"probability of a hard violation under that type's parameter distribution: with no violation "
                f"1 &minus; 0.05<sup>1/n<sub>eff</sub></sup> and, beside it, the Bonferroni limit "
                f"1 &minus; (0.05/12)<sup>1/n<sub>eff</sub></sup> over the twelve types; with violations the "
                f"Clopper&ndash;Pearson upper limit on the unweighted count at the same levels, with the limit on the "
                f"weighted violation share at the effective n reported beside it. Types 6, 7 and 9 are "
                f"importance-sampled (the inside vehicle's exit distance, the crew's emergence time and the dead-stop "
                f"time) with weights p/q and an effective n of (&Sigma;w)<sup>2</sup>/&Sigma;w<sup>2</sup>; type 12 "
                f"fuzzes draws of types 1, 2, 4 and 7 and so inherits type 1's undriven slopes and type 7's weights. "
                f"A near "
                f"miss is a same-lane gap below twice d<sub>min</sub>, a time to collision below "
                f"{num(nm['ttc_s'], 0)}{NB}s, a crew clearance below twice the stopping radius, or a zone exit "
                f"margin below {num(nm['zone_exit_margin_s'], 0)}{NB}s; the minimum margin is the smallest clearance "
                f"to another vehicle or crew member. Every encounter receives exactly one of six outcomes by "
                f"precedence (not driven, violation, blocked by a fault, deadlock, finished, incomplete); deadlock is "
                f"judged only where no random fuzzer runs, and an emergency-brake event (no candidate satisfies "
                f"every rule and the shield applies full braking) is a rate, not an outcome. The first main run was "
                f"stopped when two simulator defects showed as violations, the vehicle body swinging off the path at "
                f"corners and type-6 crossings built without a junction tile; both were fixed, the stored encounters "
                f"regenerated and all twelve types rerun at the same n (change 8 of [43]); the stopped run's counts "
                f"are reported in Section 5.6 and its files archived. During the rerun the type-6 cell ran three "
                f"times: its first pass showed a third defect, start states inside a vehicle's own stopping distance "
                f"of a crossing tile, and a same-lane test in the gap metric wide enough to count two vehicles "
                f"leaving a shallow crossing on different roads; its second pass exposed a stall classifier that "
                f"counted a vehicle correctly held at a closed zone as waiting for a grant. The builder and the "
                f"classifier were fixed, the metric's same-lane test narrowed "
                f"{'to a heading difference of 10&deg;' if c9()['metric_change']['method'].startswith('heading') else 'to the same road and direction'} "
                f"(the shield's own leader test is unchanged), and types 3, 5 and 6 rerun at the same n so that every "
                f"count is under the one final metric and classifier (change 9 of [43]). Twenty stored encounters "
                f"must reproduce exactly on every build.")
    fill("P2-E44-DESIGN-SENTENCE", e44_design_sentence, "E44")

    def e44_design_short():
        j = e44()
        return (f"{cnt(sum(t44(j, k)['n'] for k in range(1, 13)))} encounters in the twelve types of Table 3 "
                f"({cnt(E44_N[1])} in types 1 and 7, {cnt(E44_N_DEFAULT)} in each other), with the three planners "
                f"of Section 3.5, importance weights on types 6, 7 and 9, and a 95{PCT} per-type bound with a "
                f"Bonferroni correction over the types.")
    fill("P2-E44-DESIGN-SENTENCE-SHORT", e44_design_short, "E44")

    def e44_intro_clause():
        j = e44()
        zero, viol = e44_split(j)
        n = sum(t44(j, k)["n_driven"] for k in range(1, 13))
        bmax = max(t44(j, k)["bonferroni_bound"] for k in zero)
        s = (f"In {cnt(n)} driven encounters of twelve types the safety program allowed no hard violation in "
             f"{words(len(zero))} types, with a bound on the violation probability of {sci(bmax)} or less, jointly "
             f"at 95{PCT} over the twelve types, under each type's parameter distribution")
        if viol:
            s += "; " + e44_violating_clause(j, viol)
        return s + " (Section 5.6)."
    fill("P2-E44-INTRO-CLAUSE", e44_intro_clause, "E44")

    def e44_results_paragraph():
        j = e44()
        d = r.e44d["defects_found_in_main_run"]
        zero, viol = e44_split(j)
        n_all = sum(t44(j, k)["n"] for k in range(1, 13))
        n_drv = sum(t44(j, k)["n_driven"] for k in range(1, 13))
        for k in range(1, 13):
            check(t44(j, k).get("outcomes_sum_equals_n", True), f"type {k}: the outcome classes sum to n")
        bz = {k: t44(j, k)["bonferroni_bound"] for k in zero}
        kmin, kmax = min(bz, key=bz.get), max(bz, key=bz.get)
        nz = sum(t44(j, k)["n_driven"] for k in zero)
        check(sum(t44(j, k)["outcomes"]["not_driven"] for k in range(1, 13)) == n_all - n_drv,
              "the undriven draws account for the whole gap between generated and driven")
        s = (f"Table 6 gives every type. Of the {cnt(n_all)} encounters generated, {cnt(n_drv)} were driven "
             f"({not_driven_clause(j)}). "
             f"{words(len(zero)).capitalize()} of the twelve types produced no hard violation in {cnt(nz)} driven "
             f"encounters; their Bonferroni bounds run from {sci(bz[kmin])} (type {kmin}, {T12[kmin]}, effective "
             f"n {cnt(t44(j, kmin)['n_eff'])}) to {sci(bz[kmax])} (type {kmax}, {T12[kmax]}, effective n "
             f"{cnt(t44(j, kmax)['n_eff'])}). ")
        for k in viol:
            t = t44(j, k)
            kinds = {kk: v for kk, v in t["violations_by_kind"].items() if v > 0}
            s += (f"Type {k} ({T12[k]}) had {cnt(t['violations'])} violating encounters in {cnt(t['n_driven'])} "
                  f"(effective n {cnt(t['n_eff'])}): "
                  f"{', '.join(f'{cnt(v)} {KIND[kk]}' for kk, v in kinds.items())}"
                  + ("; an encounter may count under more than one kind" if len(kinds) > 1 else "")
                  + f". Its Clopper&ndash;Pearson upper limit is {sci(t['bonferroni_bound'])} on the unweighted "
                    f"count"
                  + (f" and {sci(weighted_bound(t, j['alpha_per_type']))} on its weighted violation share "
                     f"({pc(t['outcome_shares_weighted']['violation'], 2)}) at the effective n. "
                     if t["n_eff"] < t["n_driven"] - 1 else ". "))
            check("unweighted" in t.get("bound_rule", ""), f"type {k}'s stored bound is the unweighted limit")
            if k == 9:
                g = d["genuine_finding"]
                check("dead stop" in g["name"], "the type-9 finding in E44_defects.json is the dead stop")
                if r.e44b is not None:
                    b9 = r.e44b[r.e44b["type"] == 9].set_index("bin")["violation"]
                    check(int(b9.get("kind=dead", 0)) == t["violations"] and
                          int(b9.get("kind=slip", 0)) == 0 and int(b9.get("kind=drift", 0)) == 0,
                          "every type-9 violation is in the dead-stop bin (E44_bins.csv)")
                s += (f"Every one of them is in the dead-stop bin, where a fault stops the leader instantly; the slip "
                      f"and drift bins of the same type produced none (Section 6.1). ")
        dc_all = deadlocked_clean(j, zero)
        live = [k for k in zero if k not in dc_all]
        if viol:
            s += (f"H7 as registered, zero violations in every type, is therefore not supported: {words(len(zero))} "
                  f"types produced no violation, of which {words(len(live))} were also free of deadlocks"
                  + (f"; {'type ' if len(dc_all) == 1 else 'types '}{' and '.join(str(k) for k in dc_all)} "
                     f"{'is' if len(dc_all) == 1 else 'are'} clean of violations but not live (below). "
                     if dc_all else ". "))
        else:
            s += ("H7's first clause, zero violations in every type, holds"
                  + (f", though {'type ' if len(dc_all) == 1 else 'types '}{' and '.join(str(k) for k in dc_all)} "
                     f"deadlocked (below). " if dc_all else ". "))
        # importance weights, near misses, margins
        ne = {k: t44(j, k) for k in range(1, 13) if t44(j, k)["n_eff"] < t44(j, k)["n_driven"] - 1}
        s += ("The importance weights reduce the effective n to " +
              ", ".join(f"{cnt(t['n_eff'])} of {cnt(t['n_driven'])} in type {k}" for k, t in ne.items()) + ". ")
        nm_tot = sum(t44(j, k)["near_misses"] for k in range(1, 13))
        nm_gap = sum(t44(j, k)["near_misses_by_kind"]["near_gap"] for k in range(1, 13))
        check(nm_gap > 0.5 * nm_tot, "most near misses are same-lane gaps under twice d_min")
        s += (f"Near misses, mostly a same-lane gap under twice d<sub>min</sub>, occurred in "
              f"{cnt(nm_tot)} encounters ({pc(nm_tot / n_drv, 0)} of those driven); the smallest clearance in any "
              f"type without a violation was {num(min(t44(j, k)['min_margin_m'] for k in zero), 1)}{NB}m. ")
        # outcomes
        t5 = t44(j, 5)
        dl = {k: t44(j, k)["outcomes"]["deadlock"] for k in range(1, 13) if t44(j, k)["outcomes"]["deadlock"] > 0}
        if dl:
            why = {5: "the ring of one-lane segments with finite bays",
                   6: "the landing closure"}
            s += ("Deadlocks occurred in " + ", ".join(
                f"{cnt(v)} of {cnt(t44(j, k)['n_driven'])} type-{k} encounters"
                + (f" ({pc(v / t44(j, k)['n_driven'], 1)}" if v / t44(j, k)["n_driven"] >= 0.001 else " (")
                + f"{why[k] if k in why and v / t44(j, k)['n_driven'] < 0.001 else (', ' + why[k] if k in why else '')})"
                for k, v in dl.items()) + " and in no other type. ")
            if 6 in dl:
                g6 = c9()["classification_defect"]["remaining_type6_deadlocks"]
                check(g6["count"] == dl[6] and g6["all_at_R_m"] == 1000,
                      "the type-6 deadlocks are the traced remainder, all at the 1 km radius")
                s += (f"The {words(dl[6])} type-6 deadlocks are all at the {cnt(1000)}{NB}m zone radius, and a trace "
                      f"of each shows one common cause, a crossing that lies on the zone boundary (Section 6.1). ")
        else:
            s += "No encounter deadlocked. "
        bf = {k: t44(j, k)["outcomes"]["blocked_by_fault"] for k in range(1, 13)
              if t44(j, k)["outcomes"]["blocked_by_fault"] > 0}
        if bf:
            s += ("A fault blocked " + ", ".join(f"{cnt(v)} type-{k} encounters" for k, v in bf.items()) +
                  " before any rule was tested. ")
        eb = max(range(1, 13), key=lambda k: t44(j, k)["emergency_brake_rate"])
        s += (f"The emergency brake fired in up to {pc(t44(j, eb)['emergency_brake_rate'], 1)} of a type's "
              f"encounters (type {eb}, {T12[eb]}). ")
        # the stopped first run
        f = d["first_run_violations_by_type"]
        rr = {k: v for dd in d["defects"] for k, v in dd["re_run_after_fix"].items()}
        g9 = d["genuine_finding"]["re_run_after_both_fixes"]
        s += (f"The first main run, stopped after types 1&ndash;10 and part of type 11, had shown "
              + ", ".join(f"{cnt(v)} violations in type {k}" for k, v in f.items() if k != "others")
              + " and none elsewhere. Of the violating encounters without a random fuzzer, which are deterministic "
                "and can be rerun as they were, "
              + ", ".join(f"{cnt(v['re_run'])} of {cnt(v['of_fuzzer_free_violating'])} in type {k}"
                          for k, v in rr.items())
              + f" were rerun after the fix and every one was clean"
              + (f" ({d['re_run_selection_short']})" if d.get("re_run_selection_short") else "")
              + f"; {cnt(g9['re_run'])} of {cnt(g9['of_fuzzer_free_violating'])} in type 9 were rerun after both "
                f"fixes and every one still violated ({cnt(g9['gap_below_D0'])} below the gap, "
                f"{cnt(g9['contact'])} contacts). The stopped run's files are archived and used for nothing else. ")
        check(all(v["still_violating"] == 0 for v in rr.values()),
              "every deterministic encounter rerun after a defect fix was clean")
        check(g9["still_violating"] == g9["re_run"], "every rerun type-9 encounter still violated")
        # change 9: the type-6 cell of the rerun was itself run twice
        c = c9()
        f6, mc, cd = c["first_pass_type6"], c["metric_change"], c["classification_defect"]
        t5d = t44(j, 5)["outcomes"]["deadlock"]
        vd = c["variant_dropped"]
        s += (f"The type-6 cell was run three times. Its first pass showed {cnt(f6['viol_r3'])} R3 violations, "
              f"vehicles that started inside their own stopping distance of a crossing tile, a start the protocol "
              f"never faces, {cnt(f6['viol_gap'])} gap counts between vehicles leaving a shallow crossing on "
              f"different roads with {num(mc['min_clearance_m'], 1)}{NB}m or more between their bodies and no "
              f"contact, and {cnt(f6['deadlock'])} encounters classed as deadlocks. The first was fixed in the "
              f"builder and the second by narrowing the gap metric's same-lane test "
              f"({'heading within 10&deg;' if mc['method'].startswith('heading') else 'same road and direction'} "
              f"instead of 30&deg;; the shield's leader test is unchanged). No violation count in any other type "
              f"changes under the narrower test, and type 9's reproduced exactly; the near-miss counts of type "
              f"{' and '.join(str(k) for k in mc['near_miss_changed_types'])} and the minimum-gap diagnostic of "
              f"type {' and '.join(str(k) for k in mc['min_gap_diagnostic_changed_types'] if k not in mc['near_miss_changed_types'])} "
              f"did change, so types {' and '.join(str(k) for k in mc['rerun_full_under_final_metric'])} were rerun "
              f"in full under the final metric. The second pass, with both corrections, had no violation and "
              f"{cnt(cd['type6_deadlocks_before'])} encounters classed as deadlocks; a trace showed slow haulers "
              f"correctly held at the closed zone, stopped just short of its line, that the stall check counted as "
              f"waiting for a grant. The classifier was corrected (the deadlock flag and, in type 6, where the "
              f"stall test ends an encounter; no violation changed) and types 5 and 6 rerun. The third pass is the "
              f"one reported: type 6 fell from {cnt(cd['type6_deadlocks_before'])} deadlocks to the "
              f"{words(t44(j, 6)['outcomes']['deadlock'])} above, and type 5's ring deadlocks "
              + (f"stand at {cnt(t5d)}" if t5d == cd["type5_deadlocks_before"] else
                 f"moved from {cnt(cd['type5_deadlocks_before'])} to {cnt(t5d)}")
              + f" (change 9 of [43]). Between the second and third passes an exploratory type-6 cell with an added "
                f"request rule, registered in change 9 against a mechanism that the trace then withdrew, ran once "
                f"({cnt(vd['deadlocks'])} deadlocks against {cnt(vd['against_registered'])}) and tested nothing; it "
                f"is archived with the earlier passes and used for nothing else.")
        check(vd["violations"] == 0 and vd["status"].startswith("no mechanism"), "the dropped variant record is as expected")
        check(mc.get("other_types_violations_unchanged", False) and mc.get("t9_reproduced", {}).get("viol_gap") ==
              t44(j, 9)["violations_by_kind"]["viol_gap"], "the narrower same-lane test left every violation count unchanged")
        check(set(mc["near_miss_changed_types"]) | set(mc["min_gap_diagnostic_changed_types"])
              <= set(mc["rerun_full_under_final_metric"]),
              "every type whose near-miss count or gap diagnostic moved under the narrower test was rerun in full")
        check(sorted(cd["types_rerun"]) == [5, 6] and cd["type6_deadlocks_after"] == t44(j, 6)["outcomes"]["deadlock"]
              and cd["type5_deadlocks_after"] == t5d, "types 5 and 6 were rerun and their deadlock counts match the record")
        return s
    fill("P2-E44-RESULTS-PARAGRAPH", e44_results_paragraph, "E44")

    def e44_discussion_clause():
        j = e44()
        zero, viol = e44_split(j)
        t9 = t44(j, 9)
        s = ""
        if viol == [9]:
            s = (f"The simulator's one failure is where the derivation says it should be. R1's gap is computed for "
                 f"a leader that brakes at b<sub>max</sub>, and a vehicle that stops dead, a fault rather than a "
                 f"manoeuvre, lies outside that model [14], so a same-direction follower already inside a one-lane "
                 f"segment can close below the gap and, in {cnt(t9['violations_by_kind']['viol_contact'])} of "
                 f"{cnt(t9['n_driven'])} encounters, touch. A dead-stop margin, the follower's own stopping distance "
                 f"at its current speed, would close the case at a cost in segment capacity; we did not run it, and "
                 f"the count stands as a limit of braking-based separation. ")
        elif viol:
            s = ("The simulator's failures, " + e44_violating_clause(j, viol).replace("the exceptions are ", "")
                 .replace("the exception is ", "") + ", are reported as found. ")
        t5 = t44(j, 5)
        if t5["outcomes"]["deadlock"] > 0:
            s += (f"The ring deadlocks of type 5 ({pc(t5['outcomes']['deadlock'] / t5['n_driven'], 1)} of its "
                  f"encounters) are the property noted before the main run [43]: the exit-bay rule is not "
                  f"deadlock-free on a ring of one-lane segments with finite bays, and the logistics model's zero "
                  f"count comes from its unbounded bays; the count "
                  + ("stood" if t5["outcomes"]["deadlock"] == c9()["classification_defect"]["type5_deadlocks_before"]
                     else f"moved from {cnt(c9()['classification_defect']['type5_deadlocks_before'])}")
                  + " when the stall classifier was corrected (change 9 of [43]). ")
        t6 = t44(j, 6)
        if t6["outcomes"]["deadlock"] > 0:
            s += (f"The {words(t6['outcomes']['deadlock'])} deadlocks of type 6 are a gap in the rules: a crossing "
                  f"that lies on a landing zone's boundary can be held by a vehicle stopped at the zone line, and the "
                  f"vehicle leaving the closing zone through it is blocked. R3 keeps a vehicle out of a segment it "
                  f"cannot leave into a bay, but no rule keeps it out of a junction whose far side is a hold point. "
                  f"The repair is a one-line extension of R3's exit check to junctions; we did not run it, and the "
                  f"count stands as found. ")
        return s.strip()
    fill("P2-E44-DISCUSSION-CLAUSE", e44_discussion_clause, "E44")

    def e44_comparison_clause():
        j = e44()
        zero, viol = e44_split(j)
        b5, b4 = 1 - 0.05 ** (1 / 100_000), 1 - 0.05 ** (1 / 10_000)
        return (f"Our per-type bounds are the zero-numerator bounds of Hanley and Lippman-Hand [33]: with no "
                f"violation in n encounters the 95{PCT} upper limit is close to 3/n, {sci(b5)} at "
                f"{cnt(100_000)} and {sci(b4)} at {cnt(10_000)}, larger at the smaller effective n of the weighted "
                f"types, and they hold for the generated "
                f"distribution of each type, not for the base's actual traffic. Zhao and colleagues reach rarer "
                f"events by importance sampling on the lane-change parameters [35]; we used the same device on "
                f"three types (the exit distance, the crew's emergence time and the dead-stop time), which cost "
                f"effective sample size (Section 5.6) and found the one violating case, type 9, where the boosted "
                f"region was.")
    fill("P2-E44-COMPARISON-CLAUSE", e44_comparison_clause, "E44")

    def e44_compute_sentence():
        j = e44()
        secs = {k: t44(j, k)["run_time_s"] for k in range(1, 13)}
        kmax = max(secs, key=secs.get)
        return (f"E44's final run took {num(sum(secs.values()) / 3600, 1)}{NB}h of processor time in resumable "
                f"batches of 250 to 4,000 encounters, type {kmax} the longest at {num(secs[kmax] / 3600, 1)}{NB}h, "
                f"with a process peak of {num(max(t44(j, k)['peak_rss_mb'] for k in range(1, 13)), 0)}{NB}MB.")
    fill("P2-E44-COMPUTE-SENTENCE", e44_compute_sentence, "E44")

    # ---- E45: the discrete model and its checker (results/E45_modelcheck.json) ---------------------------------
    def e45():
        j = r.e45j
        if j is None:
            raise Pending("E45 (model checker, B-78) has not run")
        if not j.get("models") or not j.get("mutations"):
            raise Pending("E45_modelcheck.json has no models or mutations")
        return j

    def e45_nodes():
        try:
            from lunarsim.atc import modelcheck as MC
        except Exception as e:                  # BACKEND's file is not yet in the tree
            raise Pending(f"lunarsim/atc/modelcheck.py not importable ({e})")
        return cnt(len(MC.X))
    fill("P2-E45-N-NODES", e45_nodes, "E45")

    E45_NAME = {"A_pad_and_oncoming": "a pad visit with one oncoming vehicle (landing, crew and radio links)",
                "B_three_on_line": "three vehicles on the line, two of them interchangeable (crew, no landing)",
                "C_pad_two_oncoming": "a pad visit with two oncoming vehicles (landing and crew)",
                "D_pad_two_oncoming_links": "a pad visit with two oncoming vehicles and radio links"}
    E45_MUT = {"R3_exit": "R3 without the exit-slot check", "R5_entry": "R5 without the entry check",
               "R7_hold": "R7 without the hold"}

    def e45_design_sentence():
        j = e45()
        check(set(j["models"]) == set(E45_NAME), "E45 ran the four named layouts")
        check(set(j["mutations"]) == set(E45_MUT), "E45 ran the three named mutations")
        return (f"Four layouts of the discrete model of Section 3.6: " + "; ".join(E45_NAME[k] for k in E45_NAME) +
                f". Then the three mutations, " + ", ".join(E45_MUT.values()) +
                ", each required to produce a counterexample on the layout where the rule acts.")
    fill("P2-E45-DESIGN-SENTENCE", e45_design_sentence, "E45")

    def e45_totals(j):
        ms = j["models"]
        return (sum(m["states"] for m in ms.values()), sum(m["transitions"] for m in ms.values()),
                max(m["K_max_steps_to_goal"] for m in ms.values()))

    def e45_intro_clause():
        j = e45()
        st, tr, K = e45_totals(j)
        check(j["all_models_pass"], "every E45 layout passes")
        check(j["all_mutations_caught"], "every E45 mutation is caught")
        return (f"The exhaustive search of the discrete model found no unsafe state, no deadlock and no livelock "
                f"in {cnt(st)} reachable states over four layouts, every state could reach the goal within {cnt(K)} "
                f"steps, and each of three removed rules produced a counterexample (Section 5.7).")
    fill("P2-E45-INTRO-CLAUSE", e45_intro_clause, "E45")

    def e45_results_paragraph():
        j = e45()
        ms, mu = j["models"], j["mutations"]
        st, tr, K = e45_totals(j)
        big = max(ms, key=lambda k: ms[k]["states"])
        s = (f"The four layouts have {cnt(st)} reachable states and {cnt(tr)} transitions in all; the largest, "
             f"{E45_NAME[big]}, has {cnt(ms[big]['states'])} states. In every layout the search found no state "
             f"that breaks a safety invariant, no deadlock state, no state from which the goal is unreachable and no "
             f"livelock component; the longest shortest path to the goal is {cnt(K)} steps of {num(j['step_s'], 1)}"
             f"{NB}s on {num(j['cell_m'], 0)}{NB}m cells. ")
        for k, m in ms.items():
            check(m["violating_states"] == 0 and m["deadlock_states"] == 0 and m["cannot_reach_goal"] == 0
                  and m["livelock_sccs"] == 0 and m["passes"], f"E45 layout {k} passes every check")
        s += "Each mutation produced its counterexample. "
        r3 = mu["R3_exit"]
        if "deadlock_trace_length" in r3:
            s += (f"Without R3's exit-slot check, {cnt(r3['deadlock_states'])} reachable states of the three-vehicle "
                  f"line are deadlocks and {cnt(r3['cannot_reach_goal'])} cannot reach the goal "
                  f"({cnt(r3['livelock_sccs'])} livelock components); the shortest deadlock trace is "
                  f"{cnt(r3['deadlock_trace_length'])} steps. ")
        r5, r7 = mu["R5_entry"], mu["R7_hold"]
        s += (f"Without R5's entry check, {cnt(r5['violating_states'])} reachable states have a vehicle inside the "
              f"landing zone while it is closed, the shortest reached in {cnt(r5['counterexample_length'])} steps. "
              f"Without R7's hold, {cnt(r7['violating_states'])} reachable states break an invariant ("
              + ", ".join(f"{cnt(v)} {kk}" for kk, v in r7["violation_kinds"].items())
              + f"; a state may break both), the shortest in {cnt(r7['counterexample_length'])} steps. The traces "
                f"are stored beside the results. H7's second clause, a counterexample for each removed rule, holds.")
        for k, m in mu.items():
            check(m["counterexample_found"], f"E45 mutation {k} produced a counterexample")
        if r.e45d is not None:                       # results/E45_development.json: found and fixed before the final run
            items = r.e45d["items"]
            kinds = [it["kind"] for it in items]
            n_rule = sum("rule" in k for k in kinds)
            n_check = len(items) - n_rule
            check(set(kinds) == {"property definition", "checker adapter", "checker model", "rule interpretation (R3 exit slot)"},
                  "the E45 development record holds the four known items")
            s += (f" Development of the checker found {words(len(items))} counterexamples before the final run, "
                  f"{words(n_check)} in the checker itself (R6 checked as a state invariant rather than on the "
                  f"vehicle's motion, which flagged crew walking up to a stopped vehicle; no crew distance computed on "
                  f"the landing spur, 80 violating states in the first layout; bay slots counted per lane, which hid "
                  f"the R3 mutation)")
            rule = [it for it in items if "rule" in it["kind"]]
            if rule:
                s += (f" and {words(n_rule)} in the reading of a rule: with the bays fixed, the three-vehicle line "
                      f"deadlocked when a vehicle granted the segment with a free exit slot lost that slot to a vehicle "
                      f"that drove into the bay afterwards. R3's &ldquo;reserved for it&rdquo; therefore binds every "
                      f"other vehicle: a bay counts the slots reserved by segment holders as taken, in the checker and "
                      f"in the encounter simulator alike.")
            else:
                s += "."
        return s
    fill("P2-E45-RESULTS-PARAGRAPH", e45_results_paragraph, "E45")

    def e45_discussion_clause():
        j = e45()
        st, tr, K = e45_totals(j)
        return (f"the exhaustive check says that the rules are consistent on every layout the checker can hold, "
                f"{cnt(st)} states of up to three vehicles on one segment with its bays, a pad and a crew member, "
                f"and that each of the three clauses we removed is load-bearing: without it the search finds an "
                f"unsafe or a stuck state within a few steps. It says nothing about larger layouts, which is where "
                f"the simulator takes over.")
    fill("P2-E45-DISCUSSION-CLAUSE", e45_discussion_clause, "E45")

    def e45_compute_sentence():
        j = e45()
        ms, mu = j["models"], j["mutations"]
        big = max(ms, key=lambda k: ms[k]["states"])
        tot = sum(m["seconds"] for m in ms.values()) + sum(m["seconds"] for m in mu.values())
        return (f"E45's four layouts and three mutations took {num(tot, 0)}{NB}s in all, the largest layout "
                f"{num(ms[big]['seconds'], 0)}{NB}s and {num(ms[big]['peak_mb_traced'], 0)}{NB}MB.")
    fill("P2-E45-COMPUTE-SENTENCE", e45_compute_sentence, "E45")

    def h7_abstract_clause():
        j, j5 = e44(), e45()
        zero, viol = e44_split(j)
        st, tr, K = e45_totals(j5)
        s = (f"The safety program allowed no violation in {words(len(zero))} of twelve encounter types")
        if viol == [9]:
            s += ("; the exception, a vehicle stopping dead in a one-lane segment, defeats a gap rule derived "
                  "for a braking leader")
        elif viol:
            s += "; " + e44_violating_clause(j, viol, with_counts=False)
        if deadlocked_clean(j, zero):
            s += "; " + deadlock_clause(j, zero)
        s += (f". The exhaustive search of {cnt(st)} reachable states found no unsafe or stuck state and "
              f"caught three removed rules.")
        return s
    fill("P2-H7-ABSTRACT-CLAUSE", h7_abstract_clause, "E44/E45")

    def conclusion_safety_clause():
        j, j5 = e44(), e45()
        zero, viol = e44_split(j)
        st, tr, K = e45_totals(j5)
        n = sum(t44(j, k)["n_driven"] for k in range(1, 13))
        s = (f"The exhaustive check found no unsafe or stuck state in {cnt(st)} reachable states; the simulator "
             f"found no violation in {words(len(zero))} of twelve encounter types")
        if viol == [9]:
            s += ", one in the twelfth, a vehicle that stops dead inside a one-lane segment"
        elif viol:
            s += "; " + e44_violating_clause(j, viol, with_counts=False)
        if deadlocked_clean(j, zero):
            s += "; " + deadlock_clause(j, zero)
        return s + "."
    fill("P2-CONCLUSION-SAFETY-CLAUSE", conclusion_safety_clause, "E44/E45")

    # ---- E47: Mars (results/E47_fit.json, E47_bounds.json, E47_bins.csv, E47_runs.csv; data/scenarios/E47-design.json)
    MARS_CELLS = ("mars_rtt6_norelay", "mars_rtt20_norelay", "mars_rtt44_norelay",
                  "mars_rtt6_relay", "mars_rtt20_relay", "mars_rtt44_relay")
    MARS_HEAD = "mars_rtt20_norelay"          # the headline cell: the middle round trip, no relay (the base case)
    FRACTION = {2: "half", 3: "third", 4: "quarter", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth"}

    def e47():
        """Readiness: every type at its designed n, every road cell with its 30 seeds, the design file present."""
        if r.e47f is None or r.e47b is None or r.e47bins is None or r.e47runs is None:
            raise Pending("E47 (Mars, B-82) has not run")
        if r.e47d is None:
            raise Pending("data/scenarios/E47-design.json is missing")
        ty = r.e47b["types"]
        want = r.e47d["encounters"]["n_per_type"]
        missing = [k for k in range(1, 13) if str(k) not in ty]
        if missing:
            raise Pending(f"E47 types {missing} have no rows yet")
        short = [k for k in range(1, 13) if ty[str(k)]["n"] < int(want[str(k)])]
        if short:
            raise Pending(f"E47 types {short} are below their designed n")
        rc = r.e47f["road_coordination"]["delay_mean_h"]
        for c in MARS_CELLS + ("moon_2028", "moon_2038"):
            if c not in rc or int(rc[c]["uncoordinated_minus_atc"]["n"]) < 30:
                raise Pending(f"E47 road cell {c} is incomplete")
        return r.e47f, r.e47b

    def t47(b, k):
        return b["types"][str(k)]

    def times(n):
        return {1: "once", 2: "twice"}.get(int(n), f"{words(n)} times")

    def e47_g():
        return _fin(r.e47d["encounters"]["gravity_m_s2"]["value"])

    def e47_mus():
        return [float(m) for m in r.e47d["encounters"]["friction_mu"]["values"]]

    def e47_brake_limit(mu, g):
        """Steepest downhill (deg) on which the guaranteed braking of lunarsim.atc.safety stays positive, by bisection."""
        import lunarsim.atc.safety as S
        lo, hi = 0.0, 45.0
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if float(S.b_guaranteed(mid, mu, g)) > 0:
                lo = mid
            else:
                hi = mid
        return lo

    def e47_brake_limits():
        """Holdable downhill per friction value on each body; Mars is one number (the service-brake cap binds)."""
        import lunarsim.atc.safety as S
        b = _fin(r.e47d["encounters"]["vehicles"]["service_braking_m_s2"])
        check(abs(b - S.B_MIN_FLAT) < 1e-9, "the design's service brake is the safety program's B_MIN_FLAT")
        mars = [e47_brake_limit(mu, e47_g()) for mu in e47_mus()]
        moon = [e47_brake_limit(mu, S.G_MOON) for mu in e47_mus()]
        check(max(mars) - min(mars) < 0.05, "the Mars limit is the same at every friction value (the cap binds)")
        check(abs(mars[0] - math.degrees(math.asin(b / e47_g()))) < 0.05, "the Mars limit is asin(b_service / g)")
        check(abs(mars[0] - r.e47f["headline"]["steepest_holdable_downhill_deg_mars"]) < 0.1,
              "the Mars brake limit in the headline is the one computed from the design's brake and gravity")
        return mars[0], min(moon), max(moon)

    def e47_flat_brake_diff():
        """Largest difference between the bodies in the flat braking term min(b_service, mu g), over the design's mu."""
        import lunarsim.atc.safety as S
        return max(abs(float(S.b_guaranteed(0.0, mu, e47_g())) - float(S.b_guaranteed(0.0, mu, S.G_MOON)))
                   for mu in e47_mus())

    def e47_thetas(bins, k, driven_only=True):
        """Downhill angles of the bins of type k in a bins table ('theta=10.0; mu=0.3'), driven ones by default."""
        g = bins[(bins["type"] == k) & ((bins["n_driven"] > 0) if driven_only else True)]
        out = set()
        for b in g["bin"]:
            m = re.search(r"theta=([\d.]+)", str(b))
            if m:
                out.add(float(m.group(1)))
        return sorted(out)

    def e47_slope_types():
        """Types that draw a slope at all (a theta bin above 0 in E44), and whether any sloped Mars encounter was driven."""
        sloped = [k for k in range(1, 13) if any(t > 0 for t in e47_thetas(r.e44b, k, driven_only=False))]
        driven_sloped = [k for k in sloped if any(t > 0 for t in e47_thetas(r.e47bins, k))]
        return sloped, driven_sloped

    def e47_split(b):
        zero = [k for k in range(1, 13) if t47(b, k)["violations"] == 0]
        viol = [k for k in range(1, 13) if t47(b, k)["violations"] > 0]
        return zero, viol

    def e47_road():
        """The six Mars cells and the two Moon cells of the same comparison, checked against E43's Table 5."""
        f, b = e47()
        rc = f["road_coordination"]["delay_mean_h"]
        check(f["headline"]["atc_mars_equals_moon"] is True and f["road_coordination"]["atc_mars_equals_moon"] is True,
              "the ATC mode's Mars runs equal E43's ATC runs (it uses neither gravity nor the Earth link)")
        for y in (2028, 2038):
            p = r.pair("unc_atc", m=1, y=y)
            m = rc[f"moon_{y}"]["uncoordinated_minus_atc"]
            check(abs(m["mean"] - p["mean"]) < 0.05 and abs(m["ci"][0] - p["lo"]) < 0.5 and abs(m["ci"][1] - p["hi"]) < 0.5,
                  f"E47's Moon comparison for {y} is E43's uncoordinated - atc pair")
        check(len(r.e47runs) == 30 * (len(MARS_CELLS) + 1), "E47 ran seven road cells of 30 seeds")
        check(abs(rc["moon_2028"]["atc_mean"] - r.cell("atc", m=1)[PRIMARY]) < 0.01, "E47's ATC mean is E43's")
        return rc

    def e47_moon_pair(y):
        """The Moon's uncoordinated - atc difference as Table 5 reports it (one bootstrap, quoted once)."""
        p = r.pair("unc_atc", m=1, y=y)
        return p["mean"], p["lo"], p["hi"], p["share_of_b"]

    def e47_ratio():
        """Mars-over-Moon ratio of the uncoordinated mode's cost at the headline cell, against 2028."""
        rc = e47_road()
        ratio = rc[MARS_HEAD]["uncoordinated_minus_atc"]["mean"] / e47_moon_pair(2028)[0]
        check(abs(ratio - r.e47f["headline"]["uncoordinated_penalty_delay_h"]["mars_over_moon_2028"]) < 0.005,
              "the headline Mars-over-Moon ratio is the one computed from the cells")
        return ratio

    def e47_less():
        """H9's third clause judged on the intervals: every Mars cell below both Moon cells' lower limits (or above)."""
        rc = e47_road()
        moon_lo = min(e47_moon_pair(2028)[1], e47_moon_pair(2038)[1])
        moon_hi = max(e47_moon_pair(2028)[2], e47_moon_pair(2038)[2])
        less = all(rc[c]["uncoordinated_minus_atc"]["ci"][1] < moon_lo for c in MARS_CELLS)
        more = all(rc[c]["uncoordinated_minus_atc"]["ci"][0] > moon_hi for c in MARS_CELLS)
        if not (less or more):
            raise Pending("H9 clause 3 is mixed across the Mars cells; the wording is not written for that case")
        return less

    def e47_fraction():
        """'about one-sixth': the rounded reciprocal of the ratio, only when the ratio is within 0.5 of that integer."""
        inv = 1.0 / e47_ratio()
        n = int(round(inv))
        check(abs(inv - n) < 0.5 and 2 <= n <= 8, "the Mars cost is near a simple fraction of the Moon's")
        return FRACTION[n]

    def e47_shares():
        """The uncoordinated mode's extra delay as a share of the ATC mode's delay: Mars headline cell and the Moon 2028."""
        rc = e47_road()
        atc = r.cell("atc", m=1)[PRIMARY]
        mars = rc[MARS_HEAD]["uncoordinated_minus_atc"]["mean"] / atc
        moon = e47_moon_pair(2028)[3]
        check(abs(moon - e47_moon_pair(2028)[0] / atc) < 0.02, "Table 5's share is the difference over the ATC delay")
        return mars, moon, atc

    def e47_per_conflict():
        """Hours waited for Earth per conflict referred, Mars headline cell against the Moon's 2028 cell."""
        rc = e47_road()
        mars = rc[MARS_HEAD]["hand_wait_h_mean"] / rc[MARS_HEAD]["hand_conflicts_mean"]
        u = r.cell("unc", 2028, m=1)
        moon = u["road_hand_wait_h"] / u["road_hand_conflicts"]
        check(mars < moon, "a referred conflict waits less for Earth on Mars than on the Moon")
        return mars, moon, rc[MARS_HEAD], u

    def e47_more_conflicts():
        """Whether the Mars fleet referred more conflicts and delivered more items than the lunar one (same seeds)."""
        pm, pl, mc, u = e47_per_conflict()
        runs = r.e47runs
        g = runs[runs["label"] == "uncoordinated x1 mars rtt 20 no relay"]
        check(len(g) == 30, "the headline Mars cell has 30 runs")
        items_mars, items_moon = float(g["delivered_items"].mean()), float(u["delivered_items"])
        more = mc["hand_conflicts_mean"] > u["road_hand_conflicts"] and items_mars > items_moon
        return more, mc["hand_conflicts_mean"], u["road_hand_conflicts"], items_mars, items_moon

    def e47_design_sentence():
        f, b = e47()
        d = r.e47d
        n_enc = sum(int(v) for v in d["encounters"]["n_per_type"].values())
        check(n_enc == sum(t47(b, k)["n"] for k in range(1, 13)), "the Mars encounter count is the design's")
        ns = d["encounters"]["n_per_type"]
        big = sorted(int(k) for k, v in ns.items() if int(v) != int(ns["2"]))
        link = d["road_coordination"]["mars_link"]
        rtts = d["road_coordination"]["rtt_min"]["values"]
        storms = link["storms"]
        check(len(set(st[1] for st in storms)) == 1, "the dust storms have one length")
        return (f"E44's twelve types at g = {num(e47_g(), 2)}{NB}m/s<sup>2</sup> with the lunar vehicles unchanged, "
                f"{cnt(ns['2'])} encounters per type and {cnt(ns[str(big[0])])} for types "
                f"{' and '.join(str(k) for k in big)}, generated from E44's seeds so that each Mars encounter is paired "
                f"with the lunar encounter of the same type, batch and index; and E43's ATC and uncoordinated cells at "
                f"today's fleet, seeds 1&ndash;30 (the 2028 label marks the paired lunar runs; the Mars link uses no "
                f"start year), with a Mars Earth link: round trips of {', '.join(cnt(x) for x in rtts[:-1])} and "
                f"{cnt(rtts[-1])} minutes added to the {words(d['road_coordination']['t_hand_h']['value'])} hours of "
                f"staff time per referred conflict, Earth in view for the first {pc(link['dte_fraction'], 0)} of each "
                f"sol (Assumed) or, as a variant, continuously through one areostationary relay, a "
                f"{cnt(link['conjunction_days'])}-day conjunction from day {cnt(link['conjunction_start_d'])} and "
                f"{words(len(storms))} {words(storms[0][1])}-day dust storms, both as loss of the Earth link only. "
                f"{cnt(n_enc)} encounters and {cnt(len(r.e47runs))} runs in {words(len(MARS_CELLS) + 1)} cells.")
    fill("P2-E47-DESIGN-SENTENCE", e47_design_sentence, "E47")

    def e47_geometry_sentence():
        f, b = e47()
        if f["second_geometry"]["done"]:
            raise Pending("the second Mars geometry ran; the sentence for that case is not written")
        return ("a second geometry on a Mars site was planned and not run, because the terrain reader is written for "
                "the lunar polar tiles and a Jezero base would need its own reader, sites and route network (Section 7).")
    fill("P2-E47-GEOMETRY-SENTENCE", e47_geometry_sentence, "E47")

    def e47_safety_facts():
        """Shared by the intro, results, discussion and abstract: the violation and deadlock picture on Mars."""
        f, b = e47()
        j = e44()
        zero, viol = e47_split(b)
        zero44, viol44 = e44_split(j)
        check(viol == viol44, "the Mars types with a violation are the Moon's")
        check(all(t47(b, k)["violations_by_kind"]["viol_contact"] == 0 for k in range(1, 13)), "no contact on Mars")
        h = f["headline"]
        check(h["violations_mars_excluding_type9"] == sum(t47(b, k)["violations"] for k in zero),
              "the headline's count outside type 9 is the table's")
        for k in range(1, 13):
            e = f["encounters"][str(k)]
            check(e["violations_mars_same_encounters"] == e["violations_moon_same_encounters"],
                  f"type {k}: the paired lunar encounters violated exactly where the Mars ones did")
        dl = {k: t47(b, k)["outcomes"]["deadlock"] for k in range(1, 13) if t47(b, k)["outcomes"]["deadlock"] > 0}
        dl44 = {k: t44(j, k)["outcomes"]["deadlock"] for k in range(1, 13) if t44(j, k)["outcomes"]["deadlock"] > 0}
        check(set(dl) == set(dl44) == {5, 6}, "the deadlocking types on Mars are the Moon's two (the ring and the closure)")
        check({int(k): v for k, v in h["deadlocks_mars"].items()} == dl, "the headline deadlock counts are the table's")
        sloped, driven_sloped = e47_slope_types()
        if driven_sloped:
            raise Pending(f"sloped Mars encounters were driven in types {driven_sloped}; the wording assumes none")
        check(bool(sloped), "some encounter types draw a slope")
        return zero, viol, dl, dl44, sloped

    def e47_intro_clause():
        f, b = e47()
        zero, viol, dl, dl44, sloped = e47_safety_facts()
        mars_lim, moon_lo, moon_hi = e47_brake_limits()
        t9 = t47(b, 9)
        less = e47_less()
        s = (f"On Mars, with the lunar vehicles on the same roads, the safety program behaved as on the Moon, "
             f"{'the dead-stop exception included, ' if viol == [9] else ''}but only on the flat: at Mars gravity "
             f"the lunar brakes hold no downhill steeper than {num(mars_lim, 1)}&deg;, so no sloped encounter could "
             f"be driven. Coordination that depends on Earth lost "
              f"{'about one-' + e47_fraction() + ' of' if less else 'more than'} what it loses on the Moon, "
              f"{'the opposite of' if less else 'as in'} what we pre-registered for Mars (H9, Section 4.1): with "
              f"Earth in view for half of every sol, as we assumed, a referred conflict waits hours, not the days of "
              f"the polar base's window gaps (Section 5.8).")
        return s
    fill("P2-E47-INTRO-CLAUSE", e47_intro_clause, "E47")

    def e47_results_paragraph():
        f, b = e47()
        j = e44()
        zero, viol, dl, dl44, sloped = e47_safety_facts()
        mars_lim, moon_lo, moon_hi = e47_brake_limits()
        rc = e47_road()
        h = f["headline"]
        n_enc = sum(t47(b, k)["n"] for k in range(1, 13))
        t9, t9m = t47(b, 9), t44(j, 9)
        n_std = t47(b, 2)["n"]
        bound_std = 1 - 0.05 ** (1 / n_std)
        bonf_std = 1 - (0.05 / 12) ** (1 / n_std)
        weighted = any(t47(b, k)["n_eff"] < t47(b, k)["n_driven"] - 1 for k in zero)
        s = (f"The Mars part ran E44's twelve types at g = {num(e47_g(), 2)}{NB}m/s<sup>2</sup> with the lunar "
             f"vehicles, {cnt(n_enc)} encounters paired with the lunar encounters of the same seeds, and E43's two "
             f"road modes at today's fleet with a Mars Earth link (Tables 7 and 8). The safety program allowed no "
             f"violation in {words(len(zero))} of the twelve types")
        if viol == [9]:
            gap = t9["violations_by_kind"]["viol_gap"]
            check(gap == t9["violations"], "type 9's Mars violations are all gap violations")
            s += (f"; in the dead-stop type the following vehicle closed below the required gap in {cnt(gap)} of "
                  f"{cnt(t9['n'])} encounters, the same {words(gap)} encounters that violated on the Moon, and no "
                  f"vehicle touched another.")
        else:
            s += "; " + e44_violating_clause(b, viol) + "."
        s += (f" With no violation the bound at {cnt(n_std)} encounters is {sci(bonf_std)} with the Bonferroni "
              f"correction ({sci(bound_std)} without), {'larger' if weighted else 'the same'} at the effective n of "
              f"the weighted types; type 9's Clopper&ndash;Pearson limit is {sci(t9['bonferroni_bound'])} with the "
              f"correction ({sci(t9['bound'])} without), against {sci(t9m['bonferroni_bound'])} ({sci(t9m['bound'])}) "
              f"on the Moon at {words(round(t9m['n'] / t9['n']))} times the sample.")
        check(abs(t9m["n"] / t9["n"] - round(t9m["n"] / t9["n"])) < 0.01, "the Moon's type-9 sample is a whole multiple")
        s += (f" The ring deadlocked in {cnt(dl[5])} of {cnt(t47(b, 5)['n_driven'])} encounters "
              f"({pc(dl[5] / t47(b, 5)['n_driven'], 1)}, against {pc(dl44[5] / t44(j, 5)['n_driven'], 1)} on the Moon) "
              f"and the landing closure {times(dl[6])} in {cnt(t47(b, 6)['n_driven'])} "
              f"({words(dl44[6])} in {cnt(t44(j, 6)['n_driven'])} on the Moon); no other type deadlocked.")
        e1 = f["encounters"]["1"]
        nd_m, nd_l, n1 = e1["not_driven_mars"], e1["not_driven_moon_same_encounters"], e1["n"]
        check(abs(nd_m / n1 - h["type1_not_driven_share_mars"]) < 0.001
              and abs(nd_l / n1 - h["type1_not_driven_share_moon"]) < 0.001,
              "the type-1 undriven shares in the headline are the counts over n")
        check(nd_m == t47(b, 1)["outcomes"]["not_driven"], "the fit's undriven count is the bounds table's")
        th_l = e47_thetas(r.e44b, 1)
        # the bins file lists driven bins only; the full slope set of type 1 is in its title ('flat, 10/15/20 deg')
        m_t = re.search(r"\(flat, ([\d/]+)\s*deg", t47(b, 1)["title"])
        if not m_t:
            raise Pending("type 1's title no longer lists its downhill angles")
        all_th = [0.0] + [float(x) for x in m_t.group(1).split("/")]
        excl_moon = [t for t in all_th if t > moon_hi]
        check(bool(excl_moon) and all(t <= moon_lo for t in all_th if t not in excl_moon)
              and sorted(set(all_th) - set(excl_moon)) == th_l,
              "the lunar following bins split cleanly into holdable (driven) and excluded at every friction value")
        check(abs(nd_l / n1 - len(excl_moon) / len(all_th)) < 0.02, "the lunar undriven share is the excluded bins' share")
        check(abs(nd_m / n1 - len([t for t in all_th if t > mars_lim]) / len(all_th)) < 0.02,
              "the Mars undriven share is the share of bins steeper than the Mars limit")
        check(f["encounters"]["12"]["not_driven_mars"] > f["encounters"]["12"]["not_driven_moon_same_encounters"],
              "type 12, which inherits type 1's slopes, also lost draws on Mars")
        check(bool(th_l) and max(th_l) <= moon_hi and all(t <= moon_lo for t in th_l),
              "every driven lunar following encounter is on a slope the service brake holds at every friction value")
        check(nd_m > nd_l, "more following draws are undrivable on Mars than on the Moon")
        diff = e47_flat_brake_diff()
        s += (f" Of the {cnt(n1)} following draws, {cnt(nd_m)} ({pc(nd_m / n1, 1)}) were on downhills steeper than "
              f"{num(mars_lim, 1)}&deg;, the steepest the vehicles' "
              f"{num(r.e47d['encounters']['vehicles']['service_braking_m_s2'], 1)}{NB}m/s<sup>2</sup> service brake "
              f"holds at Mars gravity (Section 3.5), and were not driven; on the Moon the limit is "
              f"{num(moon_lo, 1)}&ndash;{num(moon_hi, 1)}&deg; depending on the friction value, "
              f"{'only the ' + ' and '.join(num(t, 0) + '&deg;' for t in excl_moon) + ' draws are excluded' if excl_moon else 'no draw is excluded'}, "
              f"and {cnt(nd_l)} ({pc(nd_l / n1, 1)}) of the same draws were not driven. No sloped encounter of any "
              f"type was driven on Mars, and on the flat the braking term of R1 and R2 differs between the bodies by "
              f"at most {num(diff, 2)}{NB}m/s<sup>2</sup>, so the driven Mars encounters repeat the lunar ones with "
              f"the same seeds.")
        rd = h["rule_delay_nominal_s"]
        ratio = rd["mars"] / rd["moon"]
        check(abs(ratio - h["rule_delay_nominal_mars_over_moon"]) < 0.01, "the rule-delay ratio is the headline's")
        s += (f" For the {cnt(rd['n'])} paired encounters that nominal planners drove to the end on both bodies, the "
              f"rules delayed the vehicles by {num(rd['mars'], 1)}{NB}s on Mars and {num(rd['moon'], 1)}{NB}s on the "
              f"Moon, a ratio of {num(ratio, 2)}.")
        c = lambda k: rc[k]["uncoordinated_minus_atc"]
        hm = c(MARS_HEAD)
        sm, sl, atc = e47_shares()
        m28, m38 = e47_moon_pair(2028), e47_moon_pair(2038)
        s += (f" The logistics model's ATC mode uses neither gravity nor the Earth link, and its 30 Mars runs equalled "
              f"E43's ATC runs on every seed. The uncoordinated mode cost {h_(c('mars_rtt6_norelay')['mean'], 1)} "
              f"{ci(*c('mars_rtt6_norelay')['ci'], 1)}, {h_(hm['mean'], 1)} {ci(*hm['ci'], 1)} and "
              f"{h_(c('mars_rtt44_norelay')['mean'], 1)} {ci(*c('mars_rtt44_norelay')['ci'], 1)} of delay per "
              f"delivery above the ATC mode at round trips of 6, 20 and 44 minutes without a relay, and "
              f"{h_(c('mars_rtt6_relay')['mean'], 1)}, {h_(c('mars_rtt20_relay')['mean'], 1)} and "
              f"{h_(c('mars_rtt44_relay')['mean'], 1)} with the relay (Table 8); at 20 minutes without a relay that "
              f"is {num(sm, 2)} of the ATC mode's {h_(atc, 1)}. On the Moon the same difference was "
              f"{h_(m28[0], 1)} {ci(m28[1], m28[2], 1)} in 2028, {num(sl, 1)} times the ATC mode's delay, and "
              f"{h_(m38[0], 1)} {ci(m38[1], m38[2], 1)} in 2038 (Table 5); the Mars cost is {num(e47_ratio(), 2)} of "
              f"the Moon's 2028 cost.")
        pm, pl, mc, u = e47_per_conflict()
        s += (f" The Mars fleet referred {cnt(mc['hand_conflicts_mean'])} conflicts a year to Earth and waited "
              f"{h_(mc['hand_wait_h_mean'], 0)} for the decisions, {h_(pm, 1)} per conflict; the lunar fleet referred "
              f"{cnt(u['road_hand_conflicts'])} and waited {h_(u['road_hand_wait_h'], 0)}, {h_(pl, 1)} per conflict.")
        rdv = "holds" if 0.9 <= ratio <= 1.1 else "fails"
        less = e47_less()
        third = ("contradicted: it loses less in every Mars cell, with intervals that do not overlap the Moon's"
                 if less else "supported in every Mars cell")
        s += (f" H9's first clause, zero violations under Mars gravity, is supported on the flat in the same "
              f"{words(len(zero))} types as H7, fails in type 9 for the same encounters, and is untested on slopes; "
              f"its second, a similar rule cost, is tested only by the encounter delays, where it {rdv}; its third, "
              f"that Earth-dependent coordination loses more on Mars, is {third}.")
        return s
    fill("P2-E47-RESULTS-PARAGRAPH", e47_results_paragraph, "E47")

    def e47_discussion_clause():
        import lunarsim.atc.safety as S
        f, b = e47()
        rc = e47_road()
        c = lambda k: rc[k]["uncoordinated_minus_atc"]
        mars_lim, moon_lo, moon_hi = e47_brake_limits()
        nr = [c(f"mars_rtt{x}_norelay") for x in (6, 20, 44)]
        check(all(a["ci"][0] <= bb["ci"][1] and bb["ci"][0] <= a["ci"][1] for a in nr for bb in nr),
              "the three round trips give costs whose intervals overlap")
        check(all(c(f"mars_rtt{x}_relay")["mean"] < c(f"mars_rtt{x}_norelay")["mean"] for x in (6, 20, 44)),
              "the relay lowers the mean cost at each round trip")
        pm, pl, mc, u = e47_per_conflict()
        e1 = f["encounters"]["1"]
        less = e47_less()
        rd = f["headline"]["rule_delay_nominal_s"]
        check(0.9 <= rd["mars"] / rd["moon"] <= 1.1, "the rules cost the same on Mars (nominal rule delay within 10 %)")
        mus = e47_mus()
        bs = _fin(r.e47d["encounters"]["vehicles"]["service_braking_m_s2"])
        fric_moon = [mu for mu in mus if mu * S.G_MOON < bs]          # friction binds on the flat on the Moon
        cap_mars = all(mu * e47_g() >= bs for mu in mus)
        check(cap_mars and fric_moon and len(fric_moon) < len(mus),
              "on Mars the service-brake cap binds at every friction value; on the Moon only above the lowest")
        more, hc_m, hc_l, it_m, it_l = e47_more_conflicts()
        s = (f"the safety program behaved as on the Moon, the dead-stop exception included, but that is weaker evidence "
             f"than it looks: the only ground the lunar brakes hold at Mars gravity is nearly flat, and on the flat the "
             f"braking term is the same on both bodies, so the Mars encounters that were driven repeat the lunar ones; "
             f"the rules are untested on the slopes where Mars gravity acts. The same holds for the rules' cost, "
             f"measured only by the paired encounter delays. The Earth-dependent mode lost "
             f"{'about one-' + e47_fraction() + ' of' if less else 'more than'} what it loses on the Moon, "
             f"{h_(c(MARS_HEAD)['mean'], 1)} against {h_(e47_moon_pair(2028)[0], 1)}, "
             f"{'the opposite of' if less else 'as in'} H9's third clause. The reason is in the Earth windows, not the "
             f"round trip: the three round trips gave the same cost within their intervals, and the relay lowered the "
             f"mean at each, while a Mars base, as we modelled it, sees Earth for half of every sol (Assumed, Section 7) "
             f"and the polar base's computed windows [42] leave it blind for days, so a referred conflict waited "
             f"{h_(pm, 1)} for a decision on Mars and {h_(pl, 1)} on the Moon. The reversal therefore holds for any "
             f"Mars site whose horizon returns Earth every sol, and would not for one that does not.")
        if hc_m > hc_l:
            s += (f" The Mars fleet referred more conflicts ({cnt(hc_m)} against {cnt(hc_l)}) for the same demand and "
                  f"almost the same deliveries ({cnt(it_m)} against {cnt(it_l)} items); we have not traced the cause.")
        s += (f" The one Mars-specific finding is about hardware. The guaranteed braking of Section 3.5 is the smaller "
              f"of the service brake and the friction limit, less the downhill component: on the Moon the friction "
              f"term binds at &mu; = {num(fric_moon[0], 1)} and the {num(bs, 1)}{NB}m/s<sup>2</sup> service brake "
              f"above it, so the holdable downhill is {num(moon_lo, 1)}&ndash;{num(moon_hi, 1)}&deg;; on Mars the "
              f"service brake binds at every friction value, so braking does not grow with gravity while the slope "
              f"term does, and the holdable downhill falls to {num(mars_lim, 1)}&deg;. "
              f"Of the following draws, {pc(e1['not_driven_mars'] / e1['n'], 0)} were on steeper ground, against "
              f"{pc(e1['not_driven_moon_same_encounters'] / e1['n'], 0)} on the Moon. R2 gives a zero admissible "
              f"speed on such a slope, so the safety program refuses the slope; it has no rule that says a vehicle is "
              f"under-braked for the body it is on, and vehicles for Mars need a service brake sized for Mars gravity.")
        return s
    fill("P2-E47-DISCUSSION-CLAUSE", e47_discussion_clause, "E47")

    def e47_limitation_sentence():
        f, b = e47()
        d = r.e47d
        n_std = t47(b, 2)["n"]
        flags = d["road_coordination"]["mars_link_flags"]
        check(all("Assumed" in flags[k] for k in ("dte_fraction", "conjunction_start_d", "storms")),
              "the Earth-visibility fraction, the conjunction date and the storms are assumed")
        bonf = [t47(b, k)["bonferroni_bound"] for k in range(1, 13) if t47(b, k)["violations"] == 0]
        ratio = t44(e44(), 2)["n"] / n_std
        check(abs(ratio - round(ratio)) < 0.01, "the lunar sample is a whole multiple of the Mars sample")
        return (f"The Mars part runs the same base, roads, routes and demand with Mars gravity, a Mars Earth link and "
                f"the lunar vehicles, and its encounters repeat the lunar ones on the flat (Section 6.1); a Mars site "
                f"with its own terrain, roads and vehicles was planned and not run, because the terrain reader is "
                f"written for the lunar polar tiles; the share of each sol with Earth in view, the conjunction date and "
                f"the dust storms are assumed, and the simulated year holds a conjunction, which comes once in about "
                f"26 months, a conservative choice; and at {cnt(n_std)} encounters per type the Mars bounds are "
                f"{words(round(ratio))} times the Moon's for the same type, {sci(1 - (0.05 / 12) ** (1 / n_std))} for "
                f"the unweighted types with the Bonferroni correction and up to {sci(max(bonf))} for the weighted "
                f"types (Table 7).")
    fill("P2-E47-LIMITATION-SENTENCE", e47_limitation_sentence, "E47")

    def h9_abstract_clause():
        f, b = e47()
        zero, viol, dl, dl44, sloped = e47_safety_facts()
        check(viol == [9] and e47_less(), "the abstract's Mars clause describes the observed outcome")
        return (f"On Mars the rules behaved as on the Moon, and referral to Earth cost about one-{e47_fraction()} "
                f"as much.")
    fill("P2-H9-ABSTRACT-CLAUSE", h9_abstract_clause, "E47")

    def conclusion_mars_clause():
        f, b = e47()
        zero, viol, dl, dl44, sloped = e47_safety_facts()
        check(viol == [9] and e47_less(), "the conclusion's Mars clause describes the observed outcome")
        mars_lim, moon_lo, moon_hi = e47_brake_limits()
        return (f"On Mars the rules behaved as on the Moon and referral to Earth cost about one-{e47_fraction()} as "
                f"much; at Mars gravity the lunar vehicles' brakes hold no downhill steeper than {num(mars_lim, 1)}&deg;.")
    fill("P2-CONCLUSION-MARS-CLAUSE", conclusion_mars_clause, "E47")

    V["P2-REFERENCES"] = references()
    T = {"E43_cells": table_cells(r), "E43_pairs": table_pairs(r), "E44": None, "E47": None, "E47_link": None}
    try:
        f47, b47 = e47()
        T["E47"] = table_e47(r, b47)
        T["E47_link"] = table_e47_link(r, f47)
    except Pending as e:
        if not allow_pending:
            raise SystemExit(f"TABLE:E47 pending ({e}); rerun with --allow-pending to build a draft")
        pending.append(f"TABLE:E47: {e}")
        T["E47"] = '<p class="pending">[[PENDING E47: Table 7, Mars encounters per type]]</p>'
        T["E47_link"] = '<p class="pending">[[PENDING E47: Table 8, the Mars Earth link]]</p>'
    try:
        T["E44"] = table_e44(r, e44())
    except Pending as e:
        if not allow_pending:
            raise SystemExit(f"TABLE:E44 pending ({e}); rerun with --allow-pending to build a draft")
        pending.append(f"TABLE:E44: {e}")
        T["E44"] = '<p class="pending">[[PENDING E44: Table 6, encounters per type with bounds]]</p>'
    F = {"E43_density": fig_density(r)}
    if broken:
        raise SystemExit("claims contradicted by the data:\n  " + "\n  ".join(broken))
    return V, T, F, pending


# ---------------------------------------------------------------------------------------------------------
# tables and the figure
# ---------------------------------------------------------------------------------------------------------
def _tab(caption, head, rows, cls="", note=""):
    out = [f'<table class="{cls}">', f"<caption>{caption}</caption>",
           "<thead><tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead>", "<tbody>"]
    out += ["<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows]
    out += ["</tbody></table>"] + ([f'<p class="tabnote">{note}</p>'] if note else [])
    return "\n".join(out)


def table_cells(r: R):
    rows = []
    for _, c in r.c.sort_values(["density", "label", "start_year"]).iterrows():
        road = not c["mode"] == "none"
        rows.append([html.escape(c["label"]), int(c["start_year"]), int(c["n"]), num(c["horizon_days"], 0),
                     num(c[PRIMARY], 1), num(c["delay_p90_h"], 1), num(c["delivered_items"], 0),
                     num(c["road_wait_h"], 1) if road else "&ndash;", num(c["road_conflicts"], 0) if road else "&ndash;",
                     num(c["road_hand_conflicts"], 1) if road else "&ndash;", num(c["road_hand_wait_h"], 0) if road else "&ndash;",
                     num(c["road_deadlocks_total"], 0) if road else "&ndash;"])
    return _tab("Table 4. Cell means of E43. Delay is the mean delay per delivered item (h) and its 90th percentile; "
                "bay wait, conflicts, conflicts referred to Earth and the hours waited for Earth are fleet totals per "
                "run; deadlocks are the total over the cell's runs. Horizon in days.",
                ["Cell", "Start year", "Runs", "Horizon", "Delay (h)", "p90 (h)", "Items", "Bay wait (h)", "Conflicts",
                 "To Earth", "Earth wait (h)", "Deadlocks"], rows, cls="wide")


def table_e44(r: R, j, number=6, body="E44"):
    """Table 6: encounters per type with their bounds (results/E44_bounds.json); Table 7 reuses it for E47."""
    rows = []
    for k in range(1, 13):
        t = j["types"][str(k)]
        kinds = {kk: v for kk, v in t["violations_by_kind"].items() if v > 0}
        short = {"viol_contact": "contact", "viol_gap": "gap", "viol_zone": "zone", "viol_crew": "crew",
                 "viol_r3": "R3", "viol_slots": "slots"}
        viol = (cnt(t["violations"]) if not kinds else
                cnt(t["violations"]) + " (" + ", ".join(f"{cnt(v)} {short[kk]}" for kk, v in kinds.items()) + ")")
        o = t["outcomes"]
        rows.append([k, html.escape(T12[k]), cnt(t["n"]), cnt(t["n_driven"]), cnt(t["n_eff"]), viol,
                     sci(t["bonferroni_bound"]), cnt(t["near_misses"]), num(t["min_margin_m"], 1),
                     cnt(o["deadlock"]), cnt(o["blocked_by_fault"]), pc(t["emergency_brake_rate"], 1)])
    variant_note = ""
    return _tab(f"Table {number}. {body}, encounters per type: generated, driven and effective n, hard violations (by kind), the "
                f"95{PCT} upper bound on the per-encounter violation probability with the Bonferroni correction over "
                "the twelve types, near misses, the smallest clearance, deadlocks, encounters blocked by a fault and the "
                "emergency-brake rate.",
                ["#", "Type", "n", "driven", "effective n", "violations", "bound (Bonferroni)", "near misses",
                 "min margin (m)", "deadlocks", "blocked by fault", "emergency brake"], rows, "wide",
                "Bound: with no violation 1 &minus; (0.05/12)<sup>1/n<sub>eff</sub></sup>; with violations the "
                "Clopper&ndash;Pearson upper limit at &alpha;/12 on the unweighted count (the limit on the weighted "
                "share at the effective n is given in the text). Effective n = (&Sigma;w)<sup>2</sup>/&Sigma;w<sup>2</sup> "
                "under the importance weights of types 6, 7 and 9, which type 12 inherits from its type-7 draws. A "
                "negative minimum margin is a contact. Deadlocks are judged only in encounters without a random "
                "fuzzer." + variant_note)


def table_e47(r: R, b):
    """Table 7: the Mars encounters, E44's table at Mars gravity (results/E47_bounds.json)."""
    return table_e44(r, b, number=7, body="E47 (Mars)")


def table_e47_link(r: R, f):
    """Table 8: the uncoordinated mode on Mars against the ATC mode, by round trip and relay, with the Moon's cells."""
    rc = f["road_coordination"]["delay_mean_h"]
    atc = r.cell("atc", m=1)[PRIMARY]
    rows = []
    for rtt in (6, 20, 44):
        for relay in (False, True):
            c = rc[f"mars_rtt{rtt}_{'relay' if relay else 'norelay'}"]
            d = c["uncoordinated_minus_atc"]
            rows.append(["Mars", cnt(rtt), "areostationary" if relay else "none", cnt(d["n"]),
                         num(d["mean"], 1), ci(*d["ci"], 1, unit=""), num(d["mean"] / atc, 2),
                         num(c["hand_conflicts_mean"], 1), num(c["hand_wait_h_mean"], 0)])
    for y in (2028, 2038):
        p = r.pair("unc_atc", m=1, y=y)                      # Table 5's values, so one quantity has one interval
        u = r.cell("unc", y, m=1)
        rows.append([f"Moon, {y}", f"2.6{NB}s", "&ndash;", cnt(p["n"]), num(p["mean"], 1), ci(p["lo"], p["hi"], 1, unit=""),
                     num(p["share_of_b"], 2), num(u["road_hand_conflicts"], 1), num(u["road_hand_wait_h"], 0)])
    return _tab("Table 8. E47, the uncoordinated mode against the ATC mode at today's fleet: the paired difference in "
                "mean delay per delivery (h, 95&#8239;% bootstrap interval over seeds) and the same as a share of the "
                "ATC mode's delay, conflicts referred to Earth and the hours waited for Earth (fleet totals per run), "
                "on Mars by round trip and relay and on the Moon in the two E43 years (the rows of Table 5). The "
                "relay keeps the base in contact for the whole sol outside the conjunction and the storms. The ATC "
                "mode uses neither gravity nor the Earth link, so its Mars runs equal its lunar runs.",
                ["Body", "Round trip (min)", "Relay", "Seeds", "Uncoordinated &minus; ATC (h)", "95&#8239;% interval",
                 "Share of ATC", "To Earth", "Earth wait (h)"], rows, cls="wide")


def table_pairs(r: R):
    rows = []
    for _, p in r.p[r.p["metric"] == PRIMARY].iterrows():
        rows.append([html.escape(p["comparison"]), int(p["n"]), num(p["mean"], 2, sign=True),
                     ci(p["lo"], p["hi"], 2, unit=""), pc(p["share_of_b"], 1, sign=True),
                     pc(p["ratio_hi"], 1, sign=True)])
    return _tab("Table 5. Paired differences in the mean delay per delivered item (h), 95 % bootstrap intervals over "
                "seeds, the difference as a share of the baseline's mean, and the upper end of the two-sided 95 % "
                "interval of that share. The H8 rule applies to the x1 row only.",
                ["Comparison", "n", "Difference (h)", "95 % CI", "Share of baseline", "Upper bound"], rows, cls="wide")


def fig_density(r: R):
    """Delay per delivery against the fleet multiple for the three modes, as inline SVG."""
    series = {"none": [], "atc": [], "uncoordinated (2028)": []}
    for m in (1, 2, 4, 8):
        for name, key, y in (("none", "none", 2028), ("atc", "atc", 2028), ("uncoordinated (2028)", "unc", 2028)):
            try:
                series[name].append((m, r.cell(key, y, m=m)[PRIMARY]))
            except Pending:
                pass
    W, H, L, B = 520, 300, 60, 40
    ymax = max(v for s in series.values() for _, v in s) * 1.1
    xs = {1: 0, 2: 1, 4: 2, 8: 3}
    X = lambda m: L + xs[m] * (W - L - 20) / 3
    Y = lambda v: H - B - v / ymax * (H - B - 20)
    out = [f'<figure id="p2-fig-density"><svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
           'aria-label="Delay per delivery against fleet multiple">',
           f'<line x1="{L}" y1="{H - B}" x2="{W - 20}" y2="{H - B}" stroke="#333"/>',
           f'<line x1="{L}" y1="20" x2="{L}" y2="{H - B}" stroke="#333"/>']
    for m in (1, 2, 4, 8):
        out.append(f'<text x="{X(m):.0f}" y="{H - B + 16}" font-size="11" text-anchor="middle">&times;{m}</text>')
    for t in np.linspace(0, ymax, 5):
        out.append(f'<text x="{L - 6}" y="{Y(t) + 4:.0f}" font-size="10" text-anchor="end">{t:.0f}</text>')
    out.append(f'<text x="{L - 40}" y="{H / 2:.0f}" font-size="11" transform="rotate(-90 {L - 40} {H / 2:.0f})" '
               'text-anchor="middle">delay per delivery (h)</text>')
    colours = {"none": "#555", "atc": "#1565c0", "uncoordinated (2028)": "#c62828"}
    for name, pts in series.items():
        if not pts:
            continue
        d = " ".join(f"{X(m):.1f},{Y(v):.1f}" for m, v in pts)
        out.append(f'<polyline points="{d}" fill="none" stroke="{colours[name]}" stroke-width="2"/>')
        for m, v in pts:
            out.append(f'<circle cx="{X(m):.1f}" cy="{Y(v):.1f}" r="3" fill="{colours[name]}"/>')
        m, v = pts[-1]
        out.append(f'<text x="{X(m) + 6:.0f}" y="{Y(v) + 4:.0f}" font-size="11" fill="{colours[name]}">{name}</text>')
    out.append("</svg><figcaption>Figure 1. Mean delay per delivered item against the fleet multiple, with the road "
               "layer off (none), with one shared reservation table (atc) and with each owner keeping its own table "
               "and conflicts settled from Earth (uncoordinated, start year 2028). Cell means over seeds; the four- "
               "and eight-times cells run shorter horizons on ten seeds (Table 4).</figcaption></figure>")
    return "\n".join(out)


def references():
    notes = open(os.path.join(HERE, "NOTES.md"), encoding="utf-8").read()
    notes = notes.split("\n## Reference statistics")[0]          # the notes below the list are not entries
    out = ['<ol class="refs">']
    for m in re.finditer(r"^\[(\d+)\]\s+(.+?)(?=\n\n|\n\[\d+\]|\n## |\Z)", notes, re.S | re.M):
        txt = html.escape(" ".join(m.group(2).split()))
        txt = re.sub(r"\s*\((TAS|P1|PWG)[^)]*\)\s*$", "", txt)
        txt = re.sub(r"\*(.+?)\*", r"<i>\1</i>", txt)
        txt = re.sub(r"(https?://[^\s<]+)", lambda u: f'<a href="{u.group(1)}">{u.group(1)}</a>', txt)
        out.append(f'<li value="{m.group(1)}">{txt}</li>')
    if len(out) < 2:
        raise SystemExit("no references found in NOTES.md")
    nums = [int(re.search(r'value="(\d+)"', o).group(1)) for o in out[1:]]
    if nums != list(range(1, len(nums) + 1)):
        raise SystemExit(f"reference list is not 1..n without gaps or repeats: {nums}")
    return "\n".join(out + ["</ol>"])


# ---------------------------------------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------------------------------------
def build(no_pdf: bool, allow_pending: bool):
    r = R()
    V, T, F, pending = values(r, allow_pending)
    bad = {k: v for k, v in V.items() if re.search(r"\b(nan|inf|NaN|None)\b", v)}
    if bad:
        raise SystemExit(f"non-finite values: {bad}")
    doc = "\n".join(open(os.path.join(HERE, p), encoding="utf-8").read() for p in PARTS)
    for kind, items in (("TABLE", T), ("FIG", F)):
        for name, body in items.items():
            marker = f"<!-- {kind}:{name} -->"
            if marker not in doc:
                raise SystemExit(f"{marker} marker missing from the parts")
            doc = doc.replace(marker, body)
    stripped = re.sub(r"<!--.*?-->", "", doc, flags=re.S)
    used = set(re.findall(r"\{\{(P2-[A-Z0-9.-]+)\}\}", stripped))
    doc = re.sub(r"\{\{(P2-[A-Z0-9.-]+)\}\}", lambda x: V[x.group(1)] if x.group(1) in V else x.group(0), doc)
    left = sorted(set(re.findall(r"\{\{P2-[^}]*\}\}", re.sub(r"<!--.*?-->", "", doc, flags=re.S))))
    if left:
        raise SystemExit(f"unfilled placeholders: {left}")
    body = re.sub(r"<[^>]+>", " ", re.sub(r"<!--.*?-->", "", doc, flags=re.S))
    if re.search(r"\b(nan|NaN|inf)\b", body):
        raise SystemExit("nan/inf in the assembled text: " + re.search(r".{40}\b(nan|NaN|inf)\b.{40}", body).group(0))
    listed = open(os.path.join(HERE, "PLACEHOLDERS.md"), encoding="utf-8").read()
    listed_keys = {k.rstrip(".-") for k in
                   re.findall(r"(?<![A-Za-z0-9-])P2-(?:[A-Z0-9.-]|\{[a-z]+\})+(?![A-Za-z0-9{}-])", listed)}

    def family(key):
        """PLACEHOLDERS.md documents families: X{m}, {y}, SHARE{s}, BAY{b}, OWNER-{o}, SINGLE-KM-{lim}."""
        key = re.sub(r"-X[1248](?=-|$)", "-X{m}", key)
        key = re.sub(r"-(2028|2038)(?=-|$)", "-{y}", key)
        key = re.sub(r"SHARE(0|5|40)-", "SHARE{s}-", key)
        key = re.sub(r"BAY(05|2)-", "BAY{b}-", key)
        key = re.sub(r"OWNER-[ABC]-", "OWNER-{o}-", key)
        key = re.sub(r"SINGLE-KM-(15|10|8)(?=-|$)", "SINGLE-KM-{lim}", key)
        return key
    undocumented = sorted(k for k in used if k not in listed_keys and family(k) not in listed_keys)
    if undocumented:
        raise SystemExit(f"placeholders in the parts but not in PLACEHOLDERS.md: {undocumented}")
    unused = sorted(k for k in V if k not in used and k != "P2-REFERENCES")
    if unused:
        print("note: values not used in the text:", ", ".join(unused))
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
    m = re.search(r'<h2 id="p2-sec-conclusion">.*?</h2>(.*?)<h2', doc, re.S)
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
    out = os.path.join(HERE, "paper.html")
    open(out, "w", encoding="utf-8", newline="\n").write(doc)
    json.dump({k: v for k, v in V.items() if k != "P2-REFERENCES"},
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
