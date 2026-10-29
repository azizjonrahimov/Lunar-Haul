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
WORDS = {0: "no", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine"}
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
        self.e44 = os.path.join(RES, "E44_bounds.json")
        self.e45 = os.path.join(RES, "E45_modelcheck.json")

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
    check(dl == 0, "no run in any cell recorded a deadlock")

    # --- H8 per density (5.2, 5.3) ---------------------------------------------------------------------------
    pcts: Dict[int, float] = {}
    for m in (1, 2, 4, 8):
        def _m(m=m):
            n, a, h = r.cell("none", m=m), r.cell("atc", m=m), r.pair("H8", m=m)
            V[f"P2-NONE-X{m}-DELAY"] = h_(n[PRIMARY], 1)
            V[f"P2-H8-X{m}-DELAY"] = h_(a[PRIMARY], 1)
            V[f"P2-H8-X{m}-DIFF"] = h_(h["mean"], 2, sign=True)
            V[f"P2-H8-X{m}-DIFF-CI"] = ci(h["lo"], h["hi"], 2)
            V[f"P2-H8-X{m}-PCT"] = pc(h["share_of_b"], 1, sign=True)
            V[f"P2-H8-X{m}-UPPER"] = pc(h["ratio_hi95"], 1, sign=True)
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
    check(sup == (h1["ratio_hi95"] < MARGIN), "the fit's H8 verdict matches the rule")
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
        p = pc(h["share_of_b"], 1, sign=True)
        return {"clause": f"and {p} at eight times",
                "sentence": f"At eight times, over {V['P2-HORIZON-X8-D']} days, the rules added {h_(h['mean'], 2, sign=True)} "
                            f"{ci(h['lo'], h['hi'], 2)}, {p} (upper bound {pc(h['ratio_hi95'], 1, sign=True)}).",
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
    V["P2-SHARE40-ATC-PCT-ABS"] = pc(abs(pa["ratio_hi95"]), 1)
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
    V["P2-R7-ATC-DIFF"] = h_(p7["mean"], 1, sign=True)
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
    V["P2-N-CHANGES-WORD"] = words(1 + len(dc) + 1).capitalize()
    V["P2-X8-HORIZON-SENTENCE"] = " ".join(f"{html.escape(c['what'])}, because {html.escape(c['why'])}." for c in dc) \
        if dc else "no change was needed."
    pend("P2-WAKE-SENTENCE", "PREREG issue 5", "the duplicate wake-up decision is pending (paper/atc/PREREG.md, issue 5)")
    pend("P2-X8-STATUS-SENTENCE", "E43 8x", "whether the 8x cells run depends on the PREREG issue 5 decision")
    pend("P2-CHECKS-SENTENCE", "B-79", "the phase-5 checks are counted once B-79's batches land")
    pend("P2-FAILED-CHECKS-SENTENCE", "B-79", "the check outcomes are read from the verification data once B-79 lands")
    pend("P2-SHARED-CHECK-LIMITATION", "B-78", "whether roads.py calls the shared safety_check() is known once B-78 lands")

    # --- E44, E45, E47 -----------------------------------------------------------------------------------------
    e44 = ("P2-E44-N-ENCOUNTERS", "P2-E44-DESIGN-SENTENCE", "P2-E44-DESIGN-SENTENCE-SHORT", "P2-E44-INTRO-CLAUSE",
           "P2-E44-RESULTS-PARAGRAPH", "P2-E44-DISCUSSION-CLAUSE", "P2-E44-COMPARISON-CLAUSE", "P2-E44-COMPUTE-SENTENCE",
           "P2-H7-ABSTRACT-CLAUSE")
    e45 = ("P2-E45-N-NODES", "P2-E45-DESIGN-SENTENCE", "P2-E45-INTRO-CLAUSE", "P2-E45-RESULTS-PARAGRAPH",
           "P2-E45-DISCUSSION-CLAUSE", "P2-E45-COMPUTE-SENTENCE", "P2-CONCLUSION-SAFETY-CLAUSE")
    e47 = ("P2-E47-DESIGN-SENTENCE", "P2-E47-GEOMETRY-SENTENCE", "P2-E47-INTRO-CLAUSE", "P2-E47-RESULTS-PARAGRAPH",
           "P2-E47-DISCUSSION-CLAUSE", "P2-E47-LIMITATION-SENTENCE", "P2-H9-ABSTRACT-CLAUSE", "P2-CONCLUSION-MARS-CLAUSE")
    for key in e44:
        pend(key, "E44", "E44 (encounter simulator, B-78) has not run")
    for key in e45:
        pend(key, "E45", "E45 (model checker, B-78) has not run")
    for key in e47:
        pend(key, "E47", "E47 (Mars, B-82) has not run")

    V["P2-REFERENCES"] = references()
    T = {"E43_cells": table_cells(r), "E43_pairs": table_pairs(r),
         "E44": '<p class="pending">[[PENDING E44: Table 6, encounters per type with bounds]]</p>' if allow_pending else None,
         }
    if T["E44"] is None:
        raise SystemExit("TABLE:E44 pending (E44 has not run); rerun with --allow-pending to build a draft")
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


def table_pairs(r: R):
    rows = []
    for _, p in r.p[r.p["metric"] == PRIMARY].iterrows():
        rows.append([html.escape(p["comparison"]), int(p["n"]), num(p["mean"], 2, sign=True),
                     ci(p["lo"], p["hi"], 2, unit=""), pc(p["share_of_b"], 1, sign=True),
                     pc(p["ratio_hi95"], 1, sign=True)])
    return _tab("Table 5. Paired differences in the mean delay per delivered item (h), 95 % bootstrap intervals over "
                "seeds, the difference as a share of the baseline's mean, and the one-sided 95 % upper bound of that "
                "share. The H8 rule applies to the x1 row only.",
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
    out = ['<ol class="refs">']
    for m in re.finditer(r"^\[(\d+)\]\s+(.+?)(?=\n\n|\n\[\d+\]|\n## |\Z)", notes, re.S | re.M):
        txt = html.escape(" ".join(m.group(2).split()))
        txt = re.sub(r"\s*\((TAS|P1|PWG)[^)]*\)\s*$", "", txt)
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
