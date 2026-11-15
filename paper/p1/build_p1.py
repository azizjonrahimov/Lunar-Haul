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

Referee revision of 12 Nov 2026: the raw run rows and the rows archived before PREREG change 5 are read as well
(R.full, R.arch), for the before/after of the primary outcome and of every tested comparison, the distinct-run
counts, the seed rule, H6 in items and the unregistered direct comparisons. Two inputs await a task and have a
placeholder path in dev_notes.json (B-106: learned_eval.rerun_file; B-100: lrip_v02.schema_file); see
PLACEHOLDERS.md, 'Inputs that await a task'. No pending marker may print (decision A4).

Keys whose experiment has not run (E41, the 60 % cells of E40) are filled with a visible
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
from experiments.phase5 import analyse_e40 as AE  # noqa: E402  (the same pairing and bootstrap as the pairs table)

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
# B-79: the phase-5 verification checks (results/vv_phase5.json, the schema agreed with FRONTEND on 30 Oct)
# ---------------------------------------------------------------------------------------------------------
VV5 = os.path.join(RES, "vv_phase5.json")


def cnt(x):
    return num(x, 0)


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
            f", by technique: {tech_txt}. Deterministic identities are held to 10<sup>&minus;9</sup> relative or exact; stochastic checks "
            f"pass when the error is within a tolerance set in advance, and a 99&#8239;% batch-means interval that misses the reference is recorded "
            f"as a bias flag, not a failure" + (f"; the checks ran at commit <code>{html.escape(commit[:7])}</code>" if commit else "") +
            f". Their outcomes are in Section {results_section}.")


def vv5_failed_sentence(tag, methods_section, check, brief=False):
    d, rows = vv5_load(tag, check)
    ran = [x for x in rows if not x.get("skipped")]
    failed = [x for x in ran if not x.get("passed")]
    skipped = [x for x in rows if x.get("skipped")]
    bias = [x for x in ran if x.get("bias_flag")]
    label = lambda x: f"{html.escape(str(x.get('id')))}{(' ' + html.escape(str(x.get('sub')))) if x.get('sub') else ''}"
    if brief:
        # Referee S16(b): the failures in plain words, grouped by check; the checks that were not run are counted,
        # with their reasons left in the results file (they are internal notes, not results).
        reg = {"A_EARTH plan_ahead": "owners alone from Earth with plan ahead", "A_EARTH strict": "owners alone from Earth, strict",
               "A_MOON": "owners alone on the Moon", "B_EARTH strict": "the strict dispatcher on Earth"}
        pol = {"atc_bid_v1": "the network", "atc_bid_linear_v1": "the linear model"}
        groups = {}
        for x in failed:
            groups.setdefault(str(x.get("id")), []).append(x)
        bits = []
        for cid, xs in groups.items():
            subs = [str(x.get("sub", "")) for x in xs]
            if cid == "D10" and all(s.startswith("pairing ") and s[len("pairing "):] in reg for s in subs):
                bits.append(f"{words(len(xs))} are the pairing check D10 (pairing by seed reduces the variance of the difference "
                            f"from the full-information marketplace) for " + listing(reg[s[len('pairing '):]] for s in subs) +
                            f", whose delay varies mostly between start years (Section 4.5)")
            elif cid == "L5" and all(s in pol for s in subs):
                bits.append(f"{words(len(xs))} are the monotonicity check L5 (the learned bid is monotone in approach time, mass "
                            f"and battery charge) for " + listing(pol[s] for s in subs))
            else:
                bits.append(f"{words(len(xs))} " + ("is" if len(xs) == 1 else "are") + f" check {html.escape(cid)} ("
                            + listing(html.escape(s) for s in subs) + ")")
        out = (f"Of the {cnt(len(rows))} phase-5 checks of Section {methods_section} tagged to this paper, "
               + (f"{cnt(len(failed))} failed: " + "; ".join(bits) + f". The other {cnt(len(ran) - len(failed))} that ran passed"
                  if failed else f"every one of the {cnt(len(ran))} that ran passed"))
        if skipped:
            out += (f"; {cnt(len(skipped))} " + ("was" if len(skipped) == 1 else "were") + " not run, because the check does not "
                    "apply to this model or was left out, each with its reason in <code>results/vv_phase5.json</code>")
        if bias:
            out += (f"; {words(len(bias))} met " + ("its" if len(bias) == 1 else "their") + " tolerance with a 99&#8239;% "
                    "interval that misses the reference, recorded as a bias flag (" + ", ".join(label(x) for x in bias) + ")")
        return out + "."
    if failed:
        how = lambda x: ("the condition did not hold" if float(x.get("tolerance") or 0) == 0 and x.get("mode") == "abs"
                         else f"error {_vv5_err(x)} against a tolerance of {x.get('tolerance')}")
        lst = "; ".join(f"{label(x)} ({html.escape(str(x.get('name', '')))}), {how(x)}" for x in failed)
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


def idfix_sentence(check, exp_labels):
    """The cargo-id defect of PREREG change 10, from results/id_fix_evidence.json: counts only, never typed."""
    path = os.path.join(RES, "id_fix_evidence.json")
    if not os.path.exists(path):
        raise Pending("results/id_fix_evidence.json (the cargo-id fix evidence, B-79) has not landed")
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    rows = d.get("rows", [])
    check(int(d["identical"]) == sum(1 for x in rows if x.get("identical")) and int(d["runs"]) == len(rows), "id-fix evidence: totals equal the rows")
    check(int(d["ids_reused_post"]) == 0, "id-fix evidence: no id reused after the fix")
    mine = [x for x in rows if x.get("exp") in exp_labels]
    per = [x["ids_reused_pre"] for x in rows]
    items = [x["items"] for x in rows]
    exps = sorted({str(x.get("exp")) for x in rows})
    return (f"After every experiment had run, a verification check found that cargo ids were not unique: {cnt(min(per))}&ndash;{cnt(max(per))} of "
            f"about {cnt(round(sum(items) / len(items), -1))} items a year reused an earlier id, in every regime (change 10 of the pre-registration). "
            f"Ids enter the simulator's decisions only through a planning memo within one dispatch call. The fix was tested by rerunning "
            f"{cnt(d['runs'])} full years ({', '.join(exps)}: every regime or mode, seeds 1&ndash;3), of which {cnt(d['identical'])} gave outcomes "
            f"identical item by item, compared by content without ids"
            + (f", {cnt(len(mine))} of them in this paper's experiment" if mine else "") +
            f"; reused ids fell from {cnt(d['ids_reused_pre'])} to {cnt(d['ids_reused_post'])}. No experiment was rerun and no reported number changes; "
            f"trace and scene files written before the fix still carry the duplicate ids.")


def _vv5_d10(tag, check):
    d, rows = vv5_load(tag, check)
    dem = [x for x in d.get("rows", []) if x.get("id") == "D10" and x.get("sub") == "E40 demand identical"]
    if not dem:
        raise Pending("the D10 row 'E40 demand identical' is not in results/vv_phase5.json")
    check(bool(dem[0].get("passed")) and float(dem[0].get("error") or 0) == 0, "D10: the demand stream is identical across every E40 regime pair")
    m = re.search(r"([\d,]+) regime pairs", str(dem[0].get("basis", "")))
    return d, rows, (m.group(1) if m else None)


def vv5_demand_sentence(tag, methods_section, check):
    """P2: the pairing confirmed by D10 on the companion paper's regimes."""
    d, rows, n_pairs = _vv5_d10(tag, check)
    return (f"The engine's phase-5 check D10 (Section {methods_section}) confirms the pairing on the companion paper's regimes: the demand stream, "
            f"landings and manifests, was identical" + (f" across {n_pairs} regime pairs" if n_pairs else "") + " on the same seed and start year, "
            f"while the per-job intervention and fault redraws, shared in draw order, diverge once the allocations differ; E43's modes draw from the "
            f"same streams, so a pair shares its year and diverges in those draws after the first conflict.")


def vv5_pairing_sentence(tag, methods_section, check):
    """P1: how much the pairing buys, per regime, from the D10 pairing rows' detail (variance-reduction factor)."""
    d, rows, n_pairs = _vv5_d10(tag, check)
    pr = [x for x in rows if x.get("id") == "D10" and str(x.get("sub", "")).startswith("pairing ")]
    if not pr:
        raise Pending("the D10 pairing rows are not in results/vv_phase5.json")
    if any(not isinstance(x.get("detail"), dict) or "vrf" not in x["detail"] for x in pr):
        raise Pending("the D10 pairing rows carry no detail.vrf yet (BACKEND adds the variance-reduction factor)")
    good = [x for x in pr if x.get("passed")]
    weak = [x for x in pr if not x.get("passed")]
    reg = lambda x: html.escape(str(x["sub"])[len("pairing "):])
    vr = lambda xs: (min(float(x["detail"]["vrf"]) for x in xs), max(float(x["detail"]["vrf"]) for x in xs))
    dem = [x for x in d.get("rows", []) if x.get("id") == "D10" and x.get("sub") == "E40 demand identical"][0]
    check("10 % load" in str(dem.get("basis", "")) and all("80 paired runs" in str(x.get("basis", "")) and
                                                           "mean delay per delivery" in str(x.get("basis", "")) for x in pr),
          "the D10 pairing rows are at 10 % load, on the mean delay per delivery, over 80 paired runs")
    s = (f"The pairing holds for demand, landings and initial faults: in the engine's phase-5 checks (D10, Section {methods_section}) every regime's "
         f"E40 run had the same demand as the full-information marketplace's on the same seed and start year" + (f" across {n_pairs} regime pairs" if n_pairs else "") +
         "; the per-job intervention and fault redraws are shared in draw order and diverge once the allocations differ, in every regime. "
         "How much the pairing buys was measured at 10&#8239;% load, on the mean delay per delivery and not on the primary outcome, over the 80 rows "
         "of each cell, which include the repeated runs of the regimes that never wait for Earth. ")
    if good:
        lo, hi = vr(good)
        s += (f"Against the marketplace, pairing cut the variance of the paired difference to {num(lo, 2)}&ndash;{num(hi, 2)} "
              f"of the unpaired sum for {', '.join(reg(x) for x in good)}")
    if weak:
        lo, hi = vr(weak)
        s += ((", and" if good else "Against the marketplace, pairing cut it") + f" only to {num(lo, 2)}&ndash;{num(hi, 2)} for {', '.join(reg(x) for x in weak)}, "
              "whose delay varies mostly between start years; their paired intervals are little narrower than unpaired ones would be. A bootstrap "
              "over pairs treats the runs of one start year as independent, so for H2 we also give the interval obtained by resampling whole start "
              "years (Section 5.3).")
    else:
        s += "."
    return s


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
        # PREREG change 5 before/after per experiment (experiments/phase5/compare_rerun.py --exp E40 / E42 / E41)
        self.ba = {e: jl(f"{e}_fixpoint_before_after.json") for e in ("E40", "E42", "E41")
                   if os.path.exists(os.path.join(RES, f"{e}_fixpoint_before_after.json"))}
        # E41 pairs, cells and decisions (experiments/phase5/analyse_e41_pairs.py); absent or short cells are Pending
        ex = lambda f: os.path.exists(os.path.join(RES, f))
        self.p41 = rd("table_E41_pairs.csv") if ex("table_E41_pairs.csv") else None
        self.c41 = rd("table_E41_cells.csv") if ex("table_E41_cells.csv") else None
        self.f41 = jl("E41_fit.json") if ex("E41_fit.json") else None
        self.lin =json.load(open(os.path.join(ROOT, "data/policies/atc_bid_linear_v1.json"), encoding="utf-8"))
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
        # Table 6, the guard runs and the imitation statistics come from the evaluation of 27 October, made on the
        # engine before PREREG changes 4 and 5. Task B-106 reruns the out-of-range cells and the guard runs; when its
        # file exists (dev_notes.json "learned_eval"."rerun_file") `ood` and `guards` are read from it and the label
        # in the caption and the text changes with it.
        le = self.dev["learned_eval"]
        check_path = os.path.join(ROOT, le["file"])
        if os.path.abspath(check_path) != os.path.abspath(os.path.join(RES, "ATC_learned_eval.json")):
            raise ValueError("dev_notes.json learned_eval.file is not results/ATC_learned_eval.json")
        rp = os.path.join(ROOT, le["rerun_file"])
        self.L_rerun = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else None
        # B-122 (15 Nov): the 12 Nov rerun ran without PREREG change 5 (train_bid never set the opt-in fixed point); the
        # evaluation on the engine with change 5 is the source of every learned-bid value P1 prints
        fp = os.path.join(ROOT, le["fixpoint_file"])
        if not os.path.exists(fp):
            raise SystemExit(f"{le['fixpoint_file']} is missing: the learned-bid evaluation on the fixed point (B-122) is read from it")
        self.L_fix = json.load(open(fp, encoding="utf-8"))
        self._full, self._arch = {}, {}

    KEY = ["cell", "seed", "start_year"]

    def full(self, exp):
        """Every column of an experiment's current run rows (the union of its run files), with the block added."""
        if exp not in self._full:
            files = RP.run_files(exp)
            if not files:
                raise Pending(f"{exp} has not run")
            d = pd.concat([pd.read_csv(f, float_precision="round_trip") for f in files], ignore_index=True)
            d = d.drop_duplicates(self.KEY, keep="last")
            if "label" not in d:
                d["label"] = d["cell"].str.extract(r"label=([^;]+)")[0]
            self._full[exp] = AE.add_block(d)
        return self._full[exp]

    def arch(self, exp):
        """The rows archived before PREREG change 5 (results/archive/<exp>_runs*.pre-fixpoint-*.csv)."""
        if exp not in self._arch:
            files = sorted(glob.glob(os.path.join(RES, "archive", f"{exp}_runs*.pre-fixpoint-*.csv")))
            if not files:
                raise Pending(f"no archived rows of {exp} from before change 5")
            d = pd.concat([pd.read_csv(f, float_precision="round_trip") for f in files], ignore_index=True)
            d = d.drop_duplicates(self.KEY, keep="last")
            if "label" not in d:
                d["label"] = d["cell"].str.extract(r"label=([^;]+)")[0]
            self._arch[exp] = AE.add_block(d)
        return self._arch[exp]

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

    def pair41(self, comparison, metric="atc_urgent_wait_mean_cens_h", n_full=30):
        """A row of table_E41_pairs.csv; Pending until the cell has all its seeds."""
        if self.p41 is None:
            raise Pending("E41 pairs (analyse_e41_pairs.py) have not been built")
        d = self.p41[(self.p41["comparison"] == comparison) & (self.p41["metric"] == metric)]
        if len(d) != 1:
            raise KeyError(f"E41 pairs row {comparison!r} / {metric}: {len(d)} rows")
        row = d.iloc[0].to_dict()
        if int(row["n"]) < n_full or not np.isfinite(row["mean"]):
            raise Pending(f"E41 pair {comparison!r} has {int(row['n'])} of {n_full} runs")
        return row

    def cell41(self, label, n_full=30):
        """A row of table_E41_cells.csv (cell means); Pending until the cell has all its seeds."""
        if self.c41 is None:
            raise Pending("E41 cells (analyse_e41_pairs.py) have not been built")
        d = self.c41[self.c41["label"] == label]
        if len(d) == 0 or int(d.iloc[0]["n"]) < n_full:
            raise Pending(f"E41 cell {label!r} has {int(d.iloc[0]['n']) if len(d) else 0} of {n_full} runs")
        return d.iloc[0].to_dict()

    def runs_of(self, exp, label):
        d = self.runs.get(exp)
        if d is None:
            raise Pending(f"{exp} has not run")
        g = d[d["label"] == label]
        if len(g) == 0:
            raise Pending(f"{exp} cell {label!r} has no runs yet")
        return g


# ---------------------------------------------------------------------------------------------------------
# B-117 (a, b, c): three control runs made after the results were known (pass of 14 Nov 2026)
# ---------------------------------------------------------------------------------------------------------
def b117_controls(r, V, check, h3, m3):
    """The three controls the referees named (S3, S11, S12), each from its own results file. They were run after the
    results they bear on had been seen: every sentence calls them controls, never pre-registered tests. Every number
    is read from the files; what a fixed phrase asserts is a build check."""
    M = "atc_urgent_wait_mean_cens_h"

    def jl(name):
        path = os.path.join(RES, name)
        if not os.path.exists(path):
            raise SystemExit(f"{name}: the control's results file is missing")
        return json.load(open(path, encoding="utf-8"))

    def q(d):
        """A paired difference as {mean, lo, hi, lo90, hi90} whichever way the file spells its interval."""
        if "ci" in d:
            return {"mean": d["mean"], "lo": d["ci"][0], "hi": d["ci"][1], "lo90": d["ci90"][0], "hi90": d["ci90"][1], "n": d["n"]}
        return d

    dd = lambda x, nd=2: f"{h_(x['mean'], nd, sign=True)} ({ci_h(x['lo'], x['hi'], nd)})"
    din = lambda x, nd=2: f"{h_(x['mean'], nd, sign=True)}, {ci_h(x['lo'], x['hi'], nd)}"      # inside brackets
    size = lambda x, nd=2: f"{h_(abs(x['mean']), nd)} ({ci_h(*sorted((abs(x['lo']), abs(x['hi']))), nd)})"
    zero_in = lambda x: x["lo"] < 0 < x["hi"]
    CTRL = "a control run made after these results were known, not a pre-registered test"

    # ---- (a) the marketplace with the auction's return move --------------------------------------------------
    A = jl("B117a_oracle_rally.json")
    ca = A["cells"]
    o, c, om = ca["O_ORACLE"], ca["C_AUCTION"], ca["O + rally (unheard)"]
    pa = {k: q(v) for k, v in A["pairs_urgent_wait_h"].items()}
    a_o, m_o, a_m = pa["C_AUCTION - O_ORACLE"], pa["O + rally (unheard) - O_ORACLE"], pa["C_AUCTION - O + rally (unheard)"]
    n_a = len(A["seeds"])
    check(all(A["reproduces_E40_runs"][k]["equal"] and max(A["reproduces_E40_runs"][k]["max_abs_diff"].values()) == 0
              for k in ("O_ORACLE", "C_AUCTION")),
          "the control's marketplace and auction cells equal E40's stored runs value for value")
    check(n_a == 30 == a_m["n"] and A["seeds"] == list(range(1, 31)), "the return-move control uses the 30 seeds of block one")
    check(abs(o[M] - h3["b_mean"]) < 1e-3 and abs(a_o["mean"] - h3["mean"]) < 1e-3
          and abs(a_o["lo"] - h3["lo"]) < 0.01 and abs(a_o["hi"] - h3["hi"]) < 0.01,
          "the control's auction-minus-marketplace difference is the H3a row of E40")
    on = r.cell41("C_AUCTION loss 0.1")
    check(abs(c[M] - on[M]) < 1e-3 and abs(c["atc_rallies"] - on["atc_rallies"]) < 0.01,
          "the control's auction cell is the default auction cell (wait and returns a year)")
    check("Not PREREG cells" in A["note"] and "Pre-declared" in A["note"] and "nearest" in A["note"] and "lost-link rule" in A["note"],
          "the return-move control is declared as not pre-registered and as the auction's own trigger and move")
    check(zero_in(a_m) and abs(a_m["mean"]) < 0.05 and h_(om[M], 2) == h_(c[M], 2),
          "with the return move the marketplace waits as long as the auction, to the second decimal")
    check(zero_in(m_o) and zero_in(a_o) and abs(m_o["mean"] - a_o["mean"]) < 0.05,
          "the move shifts the marketplace's point estimate by what the auction led by, and neither interval excludes zero")
    check(o["atc_rallies"] == 0 and om["atc_rallies"] < c["atc_rallies"], "the marketplace makes the move less often than the auction")
    inside = -m3 < a_m["lo90"] and a_m["hi90"] < m3
    lead = h_(abs(a_o["mean"]), 2)
    V["P1-B117A-SENTENCE"] = (
        f"The marketplace was later run with the same move, in {CTRL}: an idle robot with no radio path to the mast "
        f"drives to the nearest site the mast sees, the trigger and the move of the auction's rule. On the same "
        f"{n_a} seeds, with E40's marketplace and auction cells repeated and equal to the stored runs value for "
        f"value, the marketplace with the move waited {h_(om[M], 2)}, against {h_(o[M], 2)} without it and "
        f"{h_(c[M], 2)} for the auction; the auction minus the marketplace with the move is {dd(a_m)}. The marketplace "
        f"made the move {num(om['atc_rallies'], 0)} times a year and the auction {num(c['atc_rallies'], 0)}. The "
        f"auction's lead of {lead} in the point estimate is therefore the return move and not the place of the "
        f"decision: given the same move, deciding on the robots at this message loss waited as long as deciding with "
        f"full information"
        + (f", and the 90{PCT} interval of that difference ({ci_h(a_m['lo90'], a_m['hi90'], 2)}) lies inside the "
           f"&plusmn;{h_(m3)} that H3a set for the comparison without the move, a margin that was not registered for "
           f"this one" if inside else "")
        + f". The move itself is not shown to help: it changed the marketplace's wait by {dd(m_o)}.")
    V["P1-B117A-INTRO-SENTENCE"] = (
        f"In a control run made after these results were known, the marketplace, given the auction's own move for "
        f"robots that nobody hears, waited as long as the auction ({din(a_m)}), so the auction's lead in that point "
        f"estimate is the move and not the place of the decision.")
    V["P1-B117A-DISC-SENTENCE"] = (
        f"A control run made after these results gave the marketplace the auction's return move, and it then waited as "
        f"long as the auction ({din(a_m)}): the {lead} is the move, not the place of the decision. One thing still "
        f"qualifies the reading: in the model the best bid of a round always wins whatever is lost (Sections 5.4 and 3.7).")
    V["P1-B117A-RELATED-CLAUSE"] = (
        f"With the auction's return move, in a control run afterwards, the reference waited as long as the auction "
        f"({din(a_m)}; Section 5.4).")
    V["P1-B117A-LIMIT-SENTENCE"] = (
        f"A control run after the results were known gave the marketplace the same move: it then waited as long as "
        f"the auction ({din(a_m)}), so the auction's small lead over the marketplace in the main comparison is the "
        f"rule (Section 5.4). The control is one cell at one load, and the move's own effect on the marketplace, "
        f"{dd(m_o)}, is not distinguishable from zero.")
    V["P1-B117A-CLAIM"] = (
        f" In E40 the auction's idle robots return towards the mast and the marketplace's do not. Control run "
        f"afterwards (not pre-registered), {n_a} paired seeds: given the same move the marketplace waits as long as "
        f"the auction ({din(a_m)}).")

    # ---- (b) bundle depths 2 and 5 without loss --------------------------------------------------------------
    B = jl("B117b_depth_loss0.json")
    cb = B["cells"]
    dm = B["depth_minus_depth1"][M]
    pl = B["part_due_to_loss"]
    cellname = lambda dp, L: "C_AUCTION " + ("" if dp == 1 else f"depth {dp} ") + f"loss {L}"
    LOSSES = ("0", "0.25", "0.4")
    check(B["repeated_E41_cells_reproduce"] is True
          and all(v == 0 for cell in B["repeated_E41_cells_max_abs_diff"].values() for v in cell.values())
          and len(B["repeated_E41_cells_max_abs_diff"]) == 2,
          "the two E41 cells repeated by the depth control equal the stored runs value for value")
    check(B["seeds"] == list(range(1, 31)), "the depth control uses seeds 1 to 30")
    for dp in (2, 5):
        for L in ("0.25", "0.4"):
            e41, new = r.pair41(f"C_AUCTION depth {dp} loss {L} - C_AUCTION loss {L}"), dm[f"depth {dp} - depth 1, loss {L}"]
            check(abs(e41["mean"] - new["mean"]) < 5e-3 and abs(e41["lo"] - new["lo"]) < 0.15 and abs(e41["hi"] - new["hi"]) < 0.15,
                  f"the depth control's depth {dp} penalty at loss {L} is E41's (the interval to the bootstrap's own draw)")
            check(abs(r.cell41(f"C_AUCTION depth {dp} loss {L}")["atc_claims_stale"] - cb[cellname(dp, L)]["atc_claims_stale"]) < 0.05,
                  f"the depth control's stale claims at depth {dp} and loss {L} are E41's")
    p0 = {dp: dm[f"depth {dp} - depth 1, loss 0"] for dp in (2, 5)}
    check(all(p0[dp]["lo"] > 0 and p0[dp]["n"] == 30 for dp in p0), "both bundle depths cost urgent wait without any loss")
    stale = {dp: [cb[cellname(dp, L)]["atc_claims_stale"] for L in LOSSES] for dp in (2, 5)}
    check(all(max(v) - min(v) < 0.05 * min(v) for v in stale.values()) and all(cb[cellname(1, L)]["atc_claims_stale"] == 0 for L in LOSSES),
          "the stale claims are the same at every loss, and depth 1 has none")
    check(all(cb[cellname(1, L)][M] < min(cb[cellname(2, L)][M], cb[cellname(5, L)][M]) for L in LOSSES),
          "depth 1 has the shortest urgent wait at every loss, 0 included")
    sig = sorted(k for k, v in pl.items() if not zero_in(v))
    check(sig == ["depth 5, loss 0.4"] and pl["depth 5, loss 0.4"]["lo"] > 0,
          "the part of the depth penalty due to loss is distinguishable from zero only at depth 5 and loss 0.40")
    full54 = r.pair41("C_AUCTION depth 5 loss 0.4 - C_AUCTION loss 0.4")
    check(abs(pl["depth 5, loss 0.4"]["mean"] + pl["depth 5, loss 0.4"]["b_mean"] - full54["mean"]) < 5e-3,
          "the penalty at depth 5 and loss 0.40 is the penalty without loss plus the part due to loss")
    check(pl["depth 5, loss 0.4"]["mean"] > pl["depth 5, loss 0.25"]["mean"], "the part due to loss at depth 5 is larger at loss 0.40")
    s3 = lambda v: listing(num(x, 0) for x in v)
    d1 = lambda x: f"{h_(x['mean'], 1, sign=True)} ({ci_h(x['lo'], x['hi'], 1)})"
    V["P1-B117B-SENTENCE"] = (
        f"E41 had no cell with depth 2 or 5 and no loss, so it could not say how much of this penalty is due to loss. "
        f"The two cells were added in {CTRL}, on the same 30 seeds, with two cells of E41 repeated and equal to the "
        f"stored runs value for value. Without any loss, depth 2 raised the urgent wait by "
        f"{h_(p0[2]['mean'], 1)} ({ci_h(p0[2]['lo'], p0[2]['hi'], 1)}) against depth 1 and depth 5 by "
        f"{h_(p0[5]['mean'], 1)} ({ci_h(p0[5]['lo'], p0[5]['hi'], 1)}), and the stale claims are the same at every "
        f"loss: {s3(stale[2])} a year at depth 2 and {s3(stale[5])} at depth 5, at loss 0, 0.25 and 0.40. Bundling "
        f"therefore costs urgent wait under this demand with no message lost. The part that loss adds, the penalty at "
        f"a loss minus the penalty without loss, paired by seed, is distinguishable from zero only at depth 5 and loss "
        f"0.40: {d1(pl['depth 5, loss 0.4'])} of the {h_(full54['mean'], 1)}. At depth 5 and loss 0.25 it is "
        f"{d1(pl['depth 5, loss 0.25'])}, and at depth 2 {d1(pl['depth 2, loss 0.25'])} and "
        f"{d1(pl['depth 2, loss 0.4'])}. Depth 1 had the shortest wait at every loss, 0 included, so the best depth "
        f"cannot fall under loss here as it does in Lott and Honary's benchmark [10]; what agrees with that "
        f"benchmark is that the cost of depth 5 grows under heavy loss.")
    V["P1-B117B-CLAIM"] = (
        f" Depths 2 and 5 without loss were run afterwards as a control (not pre-registered), 30 paired seeds: "
        f"bundling costs urgent wait with no message lost ({din(p0[2], 1)} at depth 2; {din(p0[5], 1)} at depth 5), and loss "
        f"adds to it measurably only at depth 5 and loss 0.40.")

    # ---- (c) the linear bid's weights removed one at a time, and the hand-built rule tuned --------------------
    # B-122: the file's main content is on the engine with the dispatch fixed point; the first run (without it) is
    # kept under "no_fixpoint_2026-11-15" and only its tuned point is quoted, to say that the selection moved
    C = jl("B117c_bid_ablation.json")
    NOFIX = C["no_fixpoint_2026-11-15"]
    F = r.L_fix["eval"]
    check(str(C["code"]).endswith("+fixpoint") and "change 5 on" in C["engine"] and "not retrained" in C["engine"]
          and "selected again" in C["engine"] and not str(NOFIX["code"]).endswith("+fixpoint"),
          "control (c) ran on the fixed point, with the policy not retrained and the hand rule selected again; the kept first run did not")
    ab = {k: {"wait": v["urgent_wait_h"], "lin": q(v["minus_linear"]), "hand": q(v["minus_hand"])} for k, v in C["ablation_30"].items()}
    names = r.lin["obs"]["names"]
    w_pol = dict(zip(names, np.asarray(r.lin["layers"][0]["w"], float).reshape(-1)))
    check(sorted(ab) == sorted(names) == sorted(C["weights"]) and all(abs(C["weights"][k] - w_pol[k]) < 1e-9 for k in names),
          "the ablation covers every weight of the published linear policy, with the policy file's values")
    hand30, lin30 = C["urgent_wait_h_30"]["hand"], C["urgent_wait_h_30"]["linear"]
    check(C["references_reproduce_cached_eval_runs"] is True and C["seeds"] == list(range(1, 31))
          and all(v["lin"]["n"] == 30 for v in ab.values())
          and abs(hand30 - F[str(LOAD_MAIN)]["hand"]["urgent_mean_h"]) < 1e-3 and abs(lin30 - F[str(LOAD_MAIN)]["linear"]["urgent_mean_h"]) < 1e-3,
          "the ablation's hand-built and linear references equal the fixed-point evaluation, on seeds 1 to 30")
    zin = lambda x: x["lo"] <= 0 <= x["hi"]
    exact0 = sorted(k for k, v in ab.items() if v["lin"]["mean"] == 0 and v["lin"]["lo"] == 0 == v["lin"]["hi"])
    resolved = sorted(k for k, v in ab.items() if not zin(v["lin"]))
    rest = sorted(k for k in ab if k not in resolved and k not in exact0)
    check(resolved == ["landing", "prio", "slack_d"] and ab["slack_d"]["lin"]["lo"] > 0 and ab["prio"]["lin"]["lo"] > 0
          and ab["landing"]["lin"]["hi"] < 0,
          "removing the slack or the priority weight raises the wait, removing the landing weight lowers it, and no other interval excludes zero")
    check(exact0 == ["link_base", "queue"], "two weights leave every seed's wait as it was")
    check(len(rest) == len(names) - 5 and all(zin(ab[k]["lin"]) for k in rest), "for the other weights the interval includes zero")
    sl, pr, ld = ab["slack_d"], ab["prio"], ab["landing"]
    check(zero_in(sl["hand"]) and abs(sl["wait"] - hand30 - sl["hand"]["mean"]) < 1e-3 and abs(sl["wait"] - lin30 - sl["lin"]["mean"]) < 1e-3,
          "without its slack weight the linear policy is not distinguishable from the hand-built bids")
    check(w_pol["slack_d"] < 0 and w_pol["slack_d"] == min(w_pol.values()), "the slack weight is the most negative: it raises the bid of an item with more slack")
    check(w_pol["landing"] > 0, "the landing weight lowers the bid of an item the longer until the next landing")
    T = C["tuned_hand"]
    t30, t60 = T["load_30"], T["load_60"]
    th30, lt30, th60, lt60 = q(t30["tuned_minus_hand"]), q(t30["linear_minus_tuned"]), q(t60["tuned_minus_hand"]), q(t60["linear_minus_tuned"])
    check(abs(t30["hand_h"] - hand30) < 1e-9 and abs(t30["linear_h"] - lin30) < 1e-9, "the tuned rule is paired with the ablation's references at the middle load")
    check(abs(t60["hand_h"] - F[str(LOAD_HEAVY)]["hand"]["urgent_mean_h"]) < 1e-3 and abs(t60["linear_h"] - F[str(LOAD_HEAVY)]["linear"]["urgent_mean_h"]) < 1e-3
          and "repeated here" in T["note_60"] and "fixed-point evaluation" in T["note_60"],
          "the 60 % references were repeated and equal the fixed-point evaluation")
    check(th30["hi"] < 0 and lt30["lo"] > 0, "at the middle load the tuned hand-built rule beats the untuned rule and the linear bids")
    check(th60["hi"] < 0 and lt60["hi"] < 0, "at 60 % load the tuned rule beats the untuned rule and the linear bids stay ahead of it")
    check(abs(th60["mean"] + lt60["mean"] - (t60["linear_h"] - t60["hand_h"])) < 1e-3,
          "at 60 % the tuned rule's gain and the linear bids' remaining lead add up to the linear bids' gain over the rule as written")
    m = re.search(r"w_p1 = ([\d.]+) h, w_p2 = ([\d.]+) h, w_age = ([\d.]+), vot_scale = ([\d.]+)", C["note"])
    b = re.search(r"(\d+) candidates, (\d+) elite, (\d+)\s+generations", C["note"])
    if not m or not b:
        raise KeyError("B117c_bid_ablation.json: the note does not state the hand rule's defaults and the search budget")
    dflt = [float(x) for x in m.groups()]
    hist = T["history"]
    check(len(hist) == int(b.group(3)) and all(len(g["fitness"]) == int(b.group(1)) for g in hist),
          "the tuning ran the generations and candidates its note states")
    check("CEM_FIT_SEEDS" in C["note"] and "CEM_TUNE_SEEDS" in C["note"] and "linear CEM's own budget and seeds" in C["note"]
          and "30 % load" in C["note"] and "Pre-declared" in C["note"],
          "the hand-built rule was tuned with the linear search's budget and seeds, at the middle load, as declared beforehand")
    check(min(range(len(hist)), key=lambda i: hist[i]["tune_mu"]) == T["selected_generation"]
          and abs(hist[T["selected_generation"]]["tune_mu"] - T["selection_seeds_mean_h"]) < 1e-9
          and all(abs(hist[T["selected_generation"]]["params"][k] - T["params"][k]) < 1e-9 for k in T["params"]),
          "the tuned point is the generation with the best mean on the selection seeds")
    check(abs(dflt[0] - 6) < 1e-9 and abs(dflt[1] - 2) < 1e-9 and abs(dflt[2] - 0.08) < 1e-9 and dflt[3] == 1,
          "the hand-built rule's defaults are the credits Section 3.7 states")
    tp, op = T["params"], NOFIX["tuned_hand"]["params"]
    PK = ("w_p1", "w_p2", "w_age", "vot_scale")
    check(abs(tp["w_p1"] - op["w_p1"]) > 1 and T["selected_generation"] != NOFIX["tuned_hand"]["selected_generation"],
          "the search selected a different point on each engine")
    same_dir = [k for k, d in zip(PK, dflt) if (tp[k] > d) == (op[k] > d)]
    check(same_dir == ["w_p1", "w_age", "vot_scale"], "both points raise the urgent credit and the scale and lower the age credit; they differ on the normal credit")
    n_w = len(names)
    gen = T["selected_generation"]
    ORD = ["first", "second", "third", "fourth", "fifth", "sixth"]
    pt = lambda p: f"{num(p['w_p1'], 1)}{NB}h, {num(p['w_p2'], 1)}{NB}h, {num(p['w_age'], 3)}{NB}h and {num(p['vot_scale'], 2)}"
    lead60 = f"{h_(abs(lt60['mean']), 1)} ({ci_h(-lt60['hi'], -lt60['lo'], 1)})"
    V["P1-B117C-ABLATION-SENTENCE"] = (
        f"Two controls were run after these results were known; they are not pre-registered tests, and both ran on "
        f"the engine with the fixed point. The first removes the linear policy's {n_w} weights one at a time, each "
        f"set to zero with the others left as they are, and runs each policy on the 30 evaluation seeds at the middle "
        f"load as the evaluation above runs them, where hand-built bids waited {h_(hand30, 2)} and the full linear "
        f"policy {h_(lin30, 2)}; both references were repeated and equal the evaluation's runs. Removing the weight "
        f"on {FEATURE_WORDS['slack_d']} raised the wait by {size(sl['lin'])} and left no gain over the hand-built "
        f"bids ({din(sl['hand'])}). Removing the weight on priority raised it by {size(pr['lin'])}. Removing the "
        f"weight on {FEATURE_WORDS['landing']} lowered it, by {size(ld['lin'])}: at this load that weight costs "
        f"urgent wait. Two weights changed nothing on any seed: {FEATURE_WORDS['link_base']} and "
        f"{FEATURE_WORDS['queue']}. For the other {words(len(rest))} the interval includes zero (point values from "
        f"{h_(min(ab[k]['lin']['mean'] for k in rest), 2, sign=True)} to "
        f"{h_(max(ab[k]['lin']['mean'] for k in rest), 2, sign=True)}). At this load the gain of the linear bids is "
        f"therefore their slack weight, which raises the bid of an item the more slack it has left; the removal does "
        f"not refit the other weights.")
    V["P1-B117C-TUNED-SENTENCE"] = (
        f"The second tunes the hand-built rule. Its four parameters, the credits of {num(dflt[0])}{NB}h and "
        f"{num(dflt[1])}{NB}h for urgent and normal items, the {num(dflt[2], 2)}{NB}h per hour waited and a scale of "
        f"{num(dflt[3])} on the shippers' value of time (Section 3.7), were fitted by the search that fitted the "
        f"linear model, with its budget ({len(hist)} generations of {len(hist[0]['fitness'])} candidates), its "
        f"training and tuning seeds and the middle load. The point selected, the best of the {ORD[gen]} generation on "
        f"the tuning seeds, is {pt(tp)}. The same search on the engine without the fixed point had selected {pt(op)}, "
        f"so which point is selected depends on the engine; both raise the urgent credit and the scale and lower the "
        f"credit for age. On the 30 evaluation seeds at the middle load the tuned rule waited "
        f"{h_(t30['urgent_wait_h'], 2)}: {size(th30)} less than the hand-built rule as written and {size(lt30)} less "
        f"than the linear bids. At {LOAD_HEAVY}{PCT} load, which neither was tuned on, it waited "
        f"{h_(t60['urgent_wait_h'], 2)}, {size(th60)} less than the {h_(t60['hand_h'], 2)} of the rule as written, "
        f"and the linear bids, at {h_(t60['linear_h'], 2)}, stayed {lead60} ahead of it; the hand-built and linear "
        f"runs at both loads were repeated and equal the evaluation's runs. So at the load both were tuned on, four "
        f"tuned parameters of the hand-built rule do better than the learned linear correction, and at "
        f"{LOAD_HEAVY}{PCT} load the tuning carries over in part while the learned correction keeps the lead. The "
        f"comparison of learned with hand-built bids turns on what carries over to a load that neither was fitted "
        f"to, and not on search against no search.")
    V["P1-B117C-INTRO-SENTENCE"] = (
        f"Two controls run after these results qualify that gain: it disappears when one of the correction's {n_w} "
        f"weights, the slack to an item's target time, is set to zero, and the hand-built rule with its four "
        f"parameters tuned by the same search waited {h_(lt30['mean'], 1)} less than the linear bids at this load; at "
        f"{LOAD_HEAVY}{PCT} load the tuned rule closed part of the gap, and the linear bids stayed "
        f"{h_(abs(lt60['mean']), 1)} ahead of it (Section 5.6).")
    V["P1-B117C-DISC-SENTENCE"] = (
        f"Two controls run afterwards locate that gain and limit it: it disappears when the slack weight alone is "
        f"set to zero, and the hand-built rule with its four parameters tuned by the same search waited "
        f"{size(lt30)} less than the linear bids at the middle load; at {LOAD_HEAVY}{PCT} load the tuned rule waited "
        f"{h_(abs(th60['mean']), 1)} less than the rule as written and the linear bids stayed "
        f"{h_(abs(lt60['mean']), 1)} ahead of it (Section 5.6).")
    V["P1-B117C-RELATED-SENTENCE"] = (
        f"A control run after these results tuned it, with the linear model's search, budget and seeds. At the middle "
        f"load the tuned rule waited {h_(t30['urgent_wait_h'], 2)}, {size(lt30)} less than the linear bids; at "
        f"{LOAD_HEAVY}{PCT} load it waited {h_(abs(th60['mean']), 1)} less than the rule as written, and the linear "
        f"bids stayed {lead60} ahead of it. A stronger hand-built rule does more than shrink the gain at the load it "
        f"is tuned on: it reverses it. That is the comparison that Accorsi and colleagues ask for [26]. At a load "
        f"that neither was fitted to, the learned correction keeps a smaller lead.")
    V["P1-B117C-WEIGHTS-CLAUSE"] = (
        f"At the middle load the linear model's gain rests on one of its {n_w} weights, the slack to the item's "
        f"target time (Section 5.6).")
    V["P1-B117C-IMPL-SENTENCE"] = (
        f"The gain from learning needed no neural network: it came from a linear model of {n_w} weights, and at the "
        f"middle load from one of them. At that load it needed no learning either: four parameters of the hand-built "
        f"rule, tuned by the same search, did better. At {LOAD_HEAVY}{PCT} load, which neither was tuned on, the tuned "
        f"rule kept part of its gain and the linear bids stayed ahead of it (Section 5.6).")
    V["P1-B117C-CLAIM"] = (
        f" Controls run afterwards (not pre-registered), 30 paired seeds, on the fixed point: without its slack weight "
        f"the linear model has no gain ({din(sl['hand'])} against hand-built bids); a hand-built rule tuned by the "
        f"same search is better than the linear model at the middle load (by {h_(lt30['mean'], 2)}, "
        f"{ci_h(lt30['lo'], lt30['hi'], 2)}) and, at {LOAD_HEAVY}{PCT} load, better than the rule as written and "
        f"behind the linear model (by {h_(abs(lt60['mean']), 1)}, {ci_h(-lt60['hi'], -lt60['lo'], 1)}).")
    V["P1-B117-LIMIT-SENTENCE"] = (
        f"The marketplace with the return move (Section 5.4), the bundle depths without loss (Section 5.5) and the "
        f"ablation and the tuned hand-built rule (Section 5.6) are controls, not pre-registered tests: each was run "
        f"after every result it bears on had been seen, and none is in a Holm family. The hand-built rule was tuned "
        f"at the middle load only and selected on the linear search's tuning seeds; its best selection score came in "
        f"the {ORD[gen]} of {len(hist)} generations, and the search chose a different point on each engine. It was "
        f"not tuned at {LOAD_HEAVY}{PCT} load, so its result there says how far this tuning carries over, not how "
        f"close a hand-built rule tuned at that load could come to the linear bids. The ablation removes one weight "
        f"at a time from a fixed policy and does not refit the others. Both controls ran on the engine with the "
        f"fixed point, with the linear policy trained without it. The return move was given to the marketplace in one cell, "
        f"at the middle load.")
    V["P1-B117-DEPARTURE-SENTENCE"] = (
        f"Three control runs were added after the results were known, at the referees' request: the marketplace with "
        f"the auction's return move (Section 5.4), bundle depths 2 and 5 without message loss (Section 5.5), and the "
        f"linear policy's weights removed one at a time together with the hand-built rule tuned by the linear "
        f"model's search (Section 5.6). They are controls and not pre-registered tests; each repeats stored cells "
        f"and reproduces them exactly before its new cells are read, and none changes a number printed before.")
    V["P1-B117-ABSTRACT-SENTENCE"] = (
        f"Controls, not pre-registered: given the auction's return move, the marketplace matched it; the linear gain "
        f"was its slack weight; a likewise-tuned hand rule beat the linear bids at {LOAD_MAIN}{PCT} and cut their lead "
        f"at {LOAD_HEAVY}{PCT}")
    V["P1-B117-CONCLUSION-SENTENCE"] = (
        f"Controls, not pre-registered: given the auction's return move, the marketplace matched it; the linear gain "
        f"was its slack weight; a likewise-tuned hand rule beat the linear bids at {LOAD_MAIN}{PCT} and cut their lead "
        f"at {LOAD_HEAVY}{PCT}")
    return {"lead_is_move": True}


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

    # --- PREREG change 5 (4.6): the dispatch fixed-point rerun, before/after from compare_rerun.py ---------------
    # Referee M2: the row movements are computed here for the paper's primary outcome (the censored mean urgent
    # wait), from the archived and the current rows matched by cell, seed and start year. compare_rerun.py's JSON
    # gives them for delay_mean_h, the mean delay per delivery of all cargo, which an earlier build quoted under
    # the primary outcome's name. The before/after of every tested comparison (PREREG change 5) is Table C1.
    PRIMARY = "atc_urgent_wait_mean_cens_h"
    # Second pass (12 Nov): the availability of the relay case that the text calls "the 80 % relay", read from the
    # coverage recorded in that cell's run rows (run_phase5's cell definition), never typed. The site reads the key.
    cov = r.full("E40")
    cov = cov[cov["label"] == LABELS["relay08"]]["coverage"].dropna().unique()
    if len(cov) != 1:
        raise ValueError(f"the relay cell {LABELS['relay08']} has {len(cov)} coverage values in E40_runs")
    RELAY08 = sh(float(cov[0]), 0)
    V["P1-RELAY08-SHARE"] = RELAY08
    REGIME_WORDS = {"A_EARTH strict": "owners alone from Earth, strict", "A_EARTH plan_ahead": "owners alone from Earth, plan ahead",
                    "A_MOON": "owners alone on the Moon", "B_EARTH strict": "the strict dispatcher on Earth",
                    "B_EARTH plan_ahead": "the plan-ahead dispatcher on Earth", "B_EARTH_RELAY 0.8": f"the {RELAY08} relay",
                    "B_EARTH_RELAY 1.0": "the relay that is always up", "C_LEADER": "the elected leader",
                    "C_AUCTION": "the auction", "C_LEARNED_LIN": "the learned linear bids",
                    "C_LEARNED_MLP": "the learned network bids", "O_ORACLE": "the full-information marketplace"}

    def moved_rows(exp):
        new, old = r.full(exp), r.arch(exp)
        m = new.merge(old, on=R.KEY, suffixes=("_new", "_old"))
        d = (m[f"{PRIMARY}_new"] - m[f"{PRIMARY}_old"]).dropna()
        i = d.abs().idxmax()
        return {"n_old": len(old), "n": len(d), "mean": float(d.mean()), "abs": float(d.abs().mean()),
                "max": float(d.abs().max()), "label": str(m.loc[i, "label_new"]),
                "load": int(m.loc[i, "load_new"]) if "load_new" in m else LOAD_MAIN}

    def raw_pair(df, a, b, load=LOAD_MAIN, metric=PRIMARY, block=None, scale=1.0):
        """A paired difference from raw run rows, with analyse_e40's pairing and bootstrap (the pairs table's own)."""
        d, _ = AE.paired(df, dict(label=a, load=load), dict(label=b, load=load), metric, None, block)
        bb = AE.boot(d * scale)
        if bb["n"] < 2:
            raise Pending(f"{a} - {b} at {load} %: {bb['n']} matched runs")
        base = df[(df["label"] == b) & (df["load"] == load)]
        if block:
            base = base[base["run_block"] == block]
        return {"n": bb["n"], "mean": bb["mean"], "lo": bb["ci"][0], "hi": bb["ci"][1], "lo90": bb["ci90"][0],
                "hi90": bb["ci90"][1], "p": bb["p"], "b_mean": float(base[metric].mean() * scale)}

    # (name, experiment, a, b, block, metric, scale, unit, rule): the tested comparisons and the two secondary ones
    def _tost(q, o_mean):
        return "inside the margin" if -0.1 * o_mean < q["lo90"] and q["hi90"] < 0.1 * o_mean else "not inside the margin"
    BA = [("H1, sharing", "E40", "B_EARTH_RELAY 1.0", "A_EARTH full coverage", "v1", PRIMARY, 1.0, "h",
           lambda q, o: "supported" if q["hi"] < 0 else "not supported"),
          ("H2, availability (pooled years)", "E40", "B_EARTH strict", "O_ORACLE", None, PRIMARY, 1.0, "h",
           lambda q, o: "supported" if q["lo"] > 0.1 * o else "not supported"),
          ("H2, secondary: plan ahead", "E40", "B_EARTH plan_ahead", "O_ORACLE", None, PRIMARY, 1.0, "h",
           lambda q, o: "recovers part" if q["lo"] > 0 else "recovers all"),
          ("H2, secondary: relay 0.8 (equivalence, 90&#8239;% interval)", "E40", "B_EARTH_RELAY 0.8", "O_ORACLE", None, PRIMARY, 1.0, "h",
           lambda q, o: _tost(q, o)),
          ("H3a, auction (equivalence, 90&#8239;% interval)", "E40", "C_AUCTION", "O_ORACLE", "v1", PRIMARY, 1.0, "h",
           lambda q, o: _tost(q, o)),
          ("H4, linear model", "E40", "C_LEARNED_LIN", "C_AUCTION", "v1", PRIMARY, 1.0, "h",
           lambda q, o: "supported" if q["hi"] < 0 else "not supported"),
          ("H4, network", "E40", "C_LEARNED_MLP", "C_AUCTION", "v1", PRIMARY, 1.0, "h",
           lambda q, o: "supported" if q["hi"] < 0 else "not supported"),
          ("H6, cross-owner pairs (share of cargo mass, team share 0.25)", "E42", "C_AUCTION team 25 any loss 0.1",
           "C_AUCTION team 25 same_owner loss 0.1", None, "delivered_share", 100.0, "pp",
           lambda q, o: "supported" if q["lo"] > 0 else "not supported")]

    def before_after():
        rows = []
        for name, exp, a, b, blk, metric, scale, unit, rule in BA:
            out = {}
            for tag, df in (("before", r.arch(exp)), ("after", r.full(exp))):
                q = raw_pair(df, a, b, metric=metric, block=blk, scale=scale)
                o = df[(df["label"] == "O_ORACLE") & (df["load"] == LOAD_MAIN)]
                if blk:
                    o = o[o["run_block"] == blk]
                q["verdict"] = rule(q, float(o[PRIMARY].mean()) if len(o) else float("nan"))
                out[tag] = q
            rows.append((name, unit, out["before"], out["after"]))
        return rows

    def fixpoint_sentence():
        mv = {e: moved_rows(e) for e in ("E40", "E42", "E41")}
        rows = before_after()
        first = {"H1": "H1, sharing", "H2": "H2, availability", "H3a": "H3a, auction", "H4": "H4, linear", "H6": "H6, cross-owner"}
        by = {k: next((b, a) for name, unit, b, a in rows if name.startswith(v)) for k, v in first.items()}
        # the "after" side must be the pairs table's own value (the same rows, pairing and bootstrap)
        for key, lab in (("H1", "H1"), ("H2", "H2_pooled"), ("H3a", "H3a"), ("H4", "H4_LIN")):
            check(abs(by[key][1]["mean"] - r.pair(lab, LOAD_MAIN)["mean"]) < 1e-3 and
                  abs(by[key][1]["lo"] - r.pair(lab, LOAD_MAIN)["lo"]) < 1e-3,
                  f"the after value of {key} recomputed from the raw rows equals table_E40_pairs.csv")
        changed = [name for name, unit, b, a in rows if b["verdict"] != a["verdict"]]
        ba = lambda q, nd=2: f"{num(q['mean'], nd, sign=True)} ({num(q['lo'], nd)} to {num(q['hi'], nd)})"
        e40, e42, e41 = mv["E40"], mv["E42"], mv["E41"]
        tot_old = sum(v["n_old"] for v in mv.values())
        where = lambda v: f", {REGIME_WORDS.get(v['label'], 'one cell')} at {v['load']}{PCT} load" if v["label"] in REGIME_WORDS else ""
        return (f"The dispatcher's consolidation hold re-posted a wake-up for every held lane on every call, so the "
                f"event queue grew with fleet size and, because one dispatch call does not reach a fixed point, the "
                f"duplicates also changed assignments. The fix, pre-registered as change 5 before any rerun row, posts "
                f"one wake-up per lane and lot and repeats dispatch at the same instant until nothing changes. Every "
                f"block of E40, E41 and E42 was rerun with it; the {tot_old:,} earlier rows are archived and "
                f"reproducible with the fix off, and every number from E40, E41 and E42 in this paper is from the "
                f"rerun rows. Against the archived row of the same cell, seed and start year, the primary outcome "
                f"moved by {num(e40['mean'], 2, sign=True)}{NB}h on average and {num(e40['abs'], 1)}{NB}h in absolute "
                f"value in E40 ({e40['n']:,} rows with a value; at most {num(e40['max'], 0)}{NB}h in one run"
                f"{where(e40)}), by {num(e42['mean'], 2, sign=True)}{NB}h and {num(e42['abs'], 1)}{NB}h in E42 "
                f"({e42['n']:,} rows; at most {num(e42['max'], 0)}{NB}h) and by {num(e41['mean'], 2, sign=True)}{NB}h "
                f"and {num(e41['abs'], 1)}{NB}h in the {e41['n']:,} rows of E41 that existed before the fix (at most "
                f"{num(e41['max'], 0)}{NB}h). An earlier version of this section quoted smaller figures; they were "
                f"for the mean delay per delivery of all cargo and not for the primary outcome. Table C1 in "
                f"Appendix C gives every tested comparison before and after the fix, as change 5 promised. "
                + ("No verdict changed. " if not changed else
                   f"The verdict changed for {listing(html.unescape(c) for c in changed)}. ")
                + f"The paired differences moved from {ba(by['H3a'][0])} to {ba(by['H3a'][1])}{NB}h for H3a, from "
                  f"{ba(by['H4'][0])} to {ba(by['H4'][1])}{NB}h for H4's linear model, from {ba(by['H2'][0], 1)} to "
                  f"{ba(by['H2'][1], 1)}{NB}h for H2 and from {ba(by['H6'][0], 1)} to {ba(by['H6'][1], 1)} "
                  f"percentage points for H6.")
    fill("P1-FIXPOINT-SENTENCE", fixpoint_sentence, "change 5 before/after")

    def fixpoint_table():
        rows = []
        for name, unit, b, a in before_after():
            lohi = (lambda q: (q["lo90"], q["hi90"])) if "90" in name else (lambda q: (q["lo"], q["hi"]))
            u = f"{NB}h" if unit == "h" else f"{NB}pp"
            cell = lambda q: f"{num(q['mean'], 2, sign=True)}{u} [{num(lohi(q)[0], 2)}, {num(lohi(q)[1], 2)}]"
            rows.append([name, f"{b['n']}", cell(b), b["verdict"], cell(a), a["verdict"]])
        return _tab("<b>Table C1.</b> Every tested comparison before and after the engine fix of change 5 "
                    "(Section 4.6): the paired mean difference at the middle load with its 95&#8239;% bootstrap "
                    "interval (the 90&#8239;% interval for the two equivalence claims), from the archived rows and "
                    "from the rerun rows, with the same pairing and bootstrap as Table 7. H2 is shown pooled over "
                    "the start years; pp is percentage points.",
                    ["Comparison", "n", "Before the fix", "Outcome", "After the fix", "Outcome"], rows, cls="wide")
    fill("P1-TABLE-FIXPOINT", fixpoint_table, "change 5 before/after")

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

    # Referee M11: rows are not all distinct runs. A row repeats another row of its cell when it has the same seed and
    # the same value, to nine decimals, of every outcome column below (the start year and the columns that only
    # describe that year's Earth windows are left out). The Earth-independent regimes repeat by construction
    # (PREREG change 4); owners alone on the Moon repeats whenever no apron conflict went to Earth.
    OUTCOMES = [PRIMARY, "atc_urgent_wait_mean_h", "delivered_kg", "delivered_items", "delay_mean_h", "jobs",
                "tonne_days_waiting", "backlog_kg", "km_total", "energy_kwh"]

    def distinct(exp):
        out = {}
        for cell, g in r.full(exp).groupby("cell"):
            k = g[["seed"] + OUTCOMES].round(9).fillna(-999.0)
            out[(str(g["label"].iloc[0]), int(g["load"].iloc[0]))] = (len(g), len(k.drop_duplicates()))
        return out
    D40 = distinct("E40")
    rows40, dist40 = sum(n for n, d in D40.values()), sum(d for n, d in D40.values())
    check(rows40 == n_runs["E40"], "the distinct-run count covers every E40 row")
    ei_rep = {k: n - d for k, (n, d) in D40.items() if k[0] in RP.EARTH_INDEPENDENT and n != d}
    other_rep = {k: (n, d) for k, (n, d) in D40.items() if k[0] not in RP.EARTH_INDEPENDENT and n != d}
    check(all(v == 50 for v in ei_rep.values()), "an Earth-independent cell run on both blocks repeats its 50 block-two runs")
    check(all(n == d for e in ("E41", "E42") for n, d in distinct(e).values()), "no row of E41 or E42 repeats another of its cell")
    # E41's default cell and E42's cell at team share 0.10 and loss 0.10 are E40's auction cell again, by design
    a40 = r.full("E40")
    a40 = a40[(a40["label"] == LABELS["auction"]) & (a40["load"] == LOAD_MAIN) & (a40["run_block"] == "v1")].set_index("seed")[OUTCOMES]
    again = 0
    for exp, lab in (("E41", LABELS["E41_rally_on"]), ("E42", "C_AUCTION team 10 any loss 0.1")):
        g = r.full(exp)
        g = g[g["label"] == lab].set_index("seed")[OUTCOMES]
        check(len(g) == len(a40) and float((g - a40).abs().max().max()) < 1e-9, f"{exp} {lab} repeats E40's auction cell run for run")
        again += len(g)
    n_rep = rows40 - dist40
    V["P1-E40-N-DISTINCT"] = f"{dist40:,}"
    V["P1-N-RUNS-REPEATS"] = f"{n_rep:,}"
    V["P1-N-RUNS-DISTINCT-MAX"] = f"{sum(n_runs.values()) - n_rep - again:,}"
    moon = {load: D40[(LABELS["A_moon"], load)] for load in (LOAD_LIGHT, LOAD_MAIN, LOAD_HEAVY)}
    rest = {k: v for k, v in other_rep.items() if k[0] != LABELS["A_moon"]}
    V["P1-RUNS-SENTENCE"] = (
        f"Rows are not all distinct runs. Of E40's {rows40:,} rows, {dist40:,} are distinct: {n_rep:,} repeat another "
        f"row of their cell exactly (the same seed and the same outcomes). {sum(ei_rep.values()):,} of the repeats are "
        f"the second block of the {len(ei_rep)} cells whose regime never waits for Earth (Section 4.6), which no "
        f"comparison counts. The rest are in cells that do depend on Earth: owners alone on the Moon, whose only use "
        f"of Earth is the hand coordination of apron conflicts, has "
        + listing(f"{moon[l][1]} distinct runs of {moon[l][0]} at {l}{PCT} load" for l in moon)
        + ("" if not rest else ", and " + listing(f"{REGIME_WORDS.get(k[0], k[0])} at {k[1]}{PCT} load has {d} of {n}"
                                                  for k, (n, d) in sorted(rest.items())))
        + f". Table 5 gives the distinct count beside the rows. A further {again} rows of E41 and E42 rerun E40's "
          f"auction cell by design, as a check that the experiments agree, so the {sum(n_runs.values()):,} rows hold "
          f"at most {sum(n_runs.values()) - n_rep - again:,} distinct simulated years.")
    r.distinct40 = D40
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
    # the value Table 5 shows: the block-one mean for an Earth-independent regime, the 80-run mean otherwise
    def sv(row, key):
        return row[f"{key}_v1"] if bool(row["earth_independent"]) and f"{key}_v1" in row else row[key]
    a_vals = [sv(reg30[k], M) for k in ("A_strict", "A_plan", "A_moon", "A_full")]
    mid = {k: sv(reg30[k], M) for k in EARTH_LOSING}
    bot = {k: sv(reg30[k], M) for k in BOTTOM}
    check(min(a_vals) > max(mid.values()) > max(bot.values()), "owners alone wait longest, Earth-losing pooled next")
    check(min(mid, key=mid.get) == "relay08" and max(mid, key=mid.get) == "B_strict",
          "the middle group runs from relay 0.8 to strict")
    check(min(bot, key=bot.get) == "lin", "the bottom group starts from learned linear bids")
    kmax = max(bot, key=bot.get)
    BOT_NAME = {"O": "the full-information marketplace", "relay10": "the relay that is always up",
                "leader": "the elected leader", "auction": "the auction", "mlp": "the network",
                "lin": "learned linear bids"}
    V["P1-BOTTOM-MAX-NAME"] = listing(BOT_NAME[k] for k in BOTTOM if bot[kmax] - bot[k] < 0.05)
    V["P1-A-URGENT-RANGE-30"] = rng_txt(a_vals, lambda x: num(x, 0)) + NB + "h"
    V["P1-RELAY08-URGENT-30"], V["P1-B-STRICT-URGENT-30"] = h_(mid["relay08"]), h_(mid["B_strict"])
    V["P1-LIN-URGENT-30"], V["P1-LEADER-URGENT-30"] = h_(bot["lin"]), h_(bot[kmax])   # the group's top, named by P1-BOTTOM-MAX-NAME
    V["P1-O-URGENT-30"] = h_(bot["O"])
    V["P1-B-STRICT-URGENT-10"] = h_(r.reg("B_strict", LOAD_LIGHT)[M])
    pooled_t = [sv(reg30[k], "delivered_kg") / 1000 for k in EARTH_LOSING + BOTTOM]
    a_t = [sv(reg30[k], "delivered_kg") / 1000 for k in ("A_strict", "A_plan", "A_moon", "A_full")]
    check((max(pooled_t) - min(pooled_t)) / np.mean(pooled_t) < 0.02, "tonnes are almost the same among pooled regimes")
    check(max(a_t) < min(pooled_t), "owners alone deliver much less")
    V["P1-POOLED-T-RANGE-30"] = rng_txt(pooled_t, lambda x: num(x, 0)) + NB + "t"
    V["P1-A-T-RANGE-30"] = rng_txt(a_t, lambda x: num(x, 0)) + NB + "t"
    V["P1-CARGO-UTIL-30"] = sh(sv(reg30["O"], "p5_cargo_util"), 0)
    V["P1-UTIL-FLEET-30"] = sh(sv(reg30["O"], "utilisation"), 1)
    pooled10 = [sv(r.reg(k, LOAD_LIGHT), M) for k in EARTH_LOSING + BOTTOM if k != "B_strict"]
    V["P1-POOLED-SPREAD-10"] = h_(max(pooled10) - min(pooled10))
    check(r.reg("B_strict", LOAD_LIGHT)[M] > max(pooled10), "the strict dispatcher is the exception at light load")
    # the marketplace mean over the 80 matched runs of the H2 comparison (5.3 quotes the n = 80 contrast)
    V["P1-O-URGENT-30-ALL"] = h_(r.pair("H2_pooled", LOAD_MAIN)["b_mean"])

    # --- H1 ------------------------------------------------------------------------------------------------
    h1 = r.pair("H1", LOAD_MAIN)
    check(h1["block"] == "v1", "H1 uses the v1 block (both regimes Earth-independent)")
    check(h1["hi"] < 0 and bool(r.fit("hypotheses", "H1", str(LOAD_MAIN), "supported")), "H1 is supported")
    V["P1-H1-DIFF-30"] = h_(-h1["mean"], 0)
    V["P1-H1-DIFF-30-CI"] = ci_abs(h1, 0)
    V["P1-H1-N-30"] = f"{int(h1['n'])}"
    holm = r.fit("holm", "adjusted_p")
    V["P1-H1-PHOLM"] = p_eq(holm[LABELS["holm_H1"]])
    V["P1-A-BACKLOG-T-30"] = t_(reg30["A_full"]["backlog_kg"] / 1000)     # the H1 comparison's owners-alone cell
    ad = r.pair("H2_A_delivered_only", LOAD_MAIN)
    check(ad["lo"] > 0, "owners alone wait longer even on delivered items")
    V["P1-A-DELIV-MINUS-O-30"] = h_(ad["mean"], 0)
    # the share of the censored gap that lies in items owners alone had not delivered by year end: one minus the
    # delivered-only paired difference over the censored one (both "H1 (reported)" rows, v1)
    h1d = r.pair("H1_delivered_only", LOAD_MAIN)
    undel = 1 - abs(h1d["mean"]) / abs(h1["mean"])
    # Referee M3: withdrawn from the paper. The ratio joins a censored and a delivered-only difference, which are
    # means over different item sets and do not add, and it was printed beside the delivered-only figure of another
    # comparison (owners alone with strict fallback against the marketplace). The key stays in values.json only
    # because the site's /paper/ page still reads it; the text states each comparison as what it is.
    V["P1-H1-UNDELIVERED-SHARE"] = sh(undel, 1)
    check(h1d["block"] == "v1" and h1d["hi"] < 0, "on delivered items owners alone with Earth always in view wait longer (H1 pair)")
    V["P1-H1-DELIV-DIFF"], V["P1-H1-DELIV-DIFF-CI"] = h_(-h1d["mean"], 1), ci_abs(h1d, 1)
    V["P1-A-DELIV-MINUS-O-CI"] = ci_h(ad["lo"], ad["hi"], 0)
    V["P1-A-DELIV-N"] = f"{int(ad['n'])}"
    oy = r.pair("H2_old_yardstick", LOAD_MAIN)
    V["P1-A-CENS-MINUS-O-30"] = h_(oy["mean"], 0)
    # what owner C delivers alone, and what the fleet leaves undelivered (the inputs behind H1's size)
    f40 = r.full("E40")
    af = f40[(f40["label"] == LABELS["A_full"]) & (f40["load"] == LOAD_MAIN) & (f40["run_block"] == "v1")]
    po = f40[(f40["label"] == LABELS["relay10"]) & (f40["load"] == LOAD_MAIN) & (f40["run_block"] == "v1")]
    check(af["own_C_delivered_t"].mean() < 0.02 * po["own_C_delivered_t"].mean(), "alone, owner C delivers almost none of its cargo")
    V["P1-OWNER-C-ALONE-T"], V["P1-OWNER-C-POOLED-T"] = t_(af["own_C_delivered_t"].mean(), 1), t_(po["own_C_delivered_t"].mean())
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
    # the 95 % interval like every other in the section; the 90 % interval, on which the equivalence margin of 4.5 is
    # judged, is printed beside it with its level (referee row 78: it had been printed alone, without its level)
    V["P1-RELAY08-MINUS-O"], V["P1-RELAY08-MINUS-O-CI"] = h_(relay["mean"]), ci_h(relay["lo"], relay["hi"])
    V["P1-RELAY08-MINUS-O-CI90"] = ci_h(relay["lo90"], relay["hi90"])
    # Referee S2: the pooled interval resamples the 80 pairs as if independent, although most of the variance is
    # between the nine start years and seeds 1-10 appear in six years each. Resampling whole start years:
    f40 = r.full("E40")
    ja = f40[(f40["label"] == LABELS["B_strict"]) & (f40["load"] == LOAD_MAIN)][["seed", "start_year", PRIMARY]]
    jb = f40[(f40["label"] == LABELS["O"]) & (f40["load"] == LOAD_MAIN)][["seed", "start_year", PRIMARY]]
    jj = ja.merge(jb, on=["seed", "start_year"], suffixes=("_a", "_b"))
    jj["d"] = jj[f"{PRIMARY}_a"] - jj[f"{PRIMARY}_b"]
    check(len(jj) == int(h2["n"]) and abs(jj["d"].mean() - h2["mean"]) < 1e-3, "the H2 pairs rebuilt from the raw rows are the table's")
    groups = [g["d"].to_numpy(float) for _, g in jj.groupby("start_year")]
    rngc = np.random.default_rng(40)
    cm = np.array([np.concatenate([groups[i] for i in rngc.integers(0, len(groups), len(groups))]).mean()
                   for _ in range(AE.B)])
    yc_lo, yc_hi = float(np.quantile(cm, 0.025)), float(np.quantile(cm, 0.975))
    check(yc_lo > margin, "H2 clears its margin when whole start years are resampled")
    check(yc_hi - yc_lo > h2["hi"] - h2["lo"], "the year-clustered interval is the wider one")
    V["P1-H2-YEARCLUSTER-CI"] = ci_h(yc_lo, yc_hi)
    V["P1-H2-N-YEARS"] = words(len(groups))
    V["P1-H2-N-PER-YEAR"] = f"{min(len(g) for g in groups)} to {max(len(g) for g in groups)}"
    V["P1-H2-OLD-YARDSTICK-MET"] = ("would not have been met" if h2["mean"] < r.fit("hypotheses", "H2", str(LOAD_MAIN), "original_yardstick_half_A_minus_O")
                                    else "would have been met")
    # Referee M13 and O1: the direct comparisons a reader looks for, paired on the 30 seeds of block one (the auction
    # is Earth-independent, so the second block would repeat its runs). Not registered.
    ar = raw_pair(f40, LABELS["auction"], LABELS["relay08"], block="v1")
    ap = raw_pair(f40, LABELS["auction"], LABELS["B_plan"], block="v1")
    a1 = raw_pair(f40, LABELS["auction"], LABELS["relay10"], block="v1")
    check(ar["hi"] < 0 and ap["hi"] < 0, "the auction waits less than the 80 % relay and than plan-ahead (block one)")
    check(a1["lo"] < 0 < a1["hi"], "the auction is not distinguishable from the relay that is always up")
    ro = f40[(f40["label"] == LABELS["relay10"]) & (f40["load"] == LOAD_MAIN)].merge(
        f40[(f40["label"] == LABELS["O"]) & (f40["load"] == LOAD_MAIN)], on=["seed", "start_year"])
    check(len(ro) == 80 and float((ro[f"{PRIMARY}_x"] - ro[f"{PRIMARY}_y"]).abs().max()) == 0.0,
          "the relay that is always up equals the marketplace run for run")
    V["P1-AUCTION-MINUS-RELAY08"], V["P1-AUCTION-MINUS-RELAY08-CI"] = h_(-ar["mean"], 1), ci_abs(ar, 1)
    V["P1-AUCTION-MINUS-PLAN"], V["P1-AUCTION-MINUS-PLAN-CI"] = h_(-ap["mean"], 1), ci_abs(ap, 1)
    V["P1-AUCTION-DIRECT-N"] = f"{ar['n']}"
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
    # magnitude with a direction word, so that the sentence never reads "waiting -0.84 h relative to"
    V["P1-H3A-DIFF"] = f"{h_(abs(h3['mean']), 2)} {'less' if h3['mean'] < 0 else 'longer'}"
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
    # "matched" only when equivalence is shown; a zero-covering interval that is too wide is reported as such
    V["P1-H3A-ABSTRACT-CLAUSE"] = (f"came within {pc(abs(100 * h3['share_of_b']), 1)} of the full-information "
                                   f"marketplace, equivalent within the pre-registered margin" if equiv else
                                   f"came within {h_(abs(h3['mean']), 1)} of the full-information marketplace, not "
                                   f"distinguishable from zero but too wide to show equivalence"
                                   if h3["lo"] < 0 < h3["hi"] else
                                   f"was {'better' if h3['hi'] < 0 else 'worse'} than the full-information marketplace "
                                   f"by {pc(abs(100 * h3['share_of_b']), 1)}")
    check(h3["mean"] <= 0 and h3["hi"] <= m3, "deciding on the Moon recovers all of the strict dispatcher's loss")
    check(h3["lo"] < 0 < h3["hi"], "the auction-marketplace difference is not distinguishable from zero")
    check(abs(h3["mean"]) < 0.1 * h2["mean"] and abs(h3["hi"]) < 0.1 * h2["mean"],
          "the auction's difference from the marketplace is a small fraction of the strict dispatcher's loss (6.1)")
    check(relay["mean"] < h2["mean"] and relay["lo"] > margin,
          "the relay's loss is small next to the strict dispatcher's and still above a tenth of O's mean (6.1)")
    ld = r.pair("leader_minus_O", LOAD_MAIN)
    # "came within X of it": a magnitude, not a signed difference
    V["P1-LEADER-MINUS-O"], V["P1-LEADER-MINUS-O-CI"] = h_(abs(ld["mean"]), 2), ci_h(ld["lo"], ld["hi"])
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

    # --- the registered 60 % halves of H1 and H4, and the regime groups at 60 % (raw p; outside the Holm family)
    h1_60 = r.pair("H1", LOAD_HEAVY)
    lin60, mlp60 = r.pair("H4_LIN", LOAD_HEAVY), r.pair("H4_MLP", LOAD_HEAVY)
    V["P1-H1-60-SENTENCE"] = (
        f"At {LOAD_HEAVY}{PCT} load the same comparison cut the wait by {h_(-h1_60['mean'], 0)} (95{PCT} CI "
        f"{ci_abs(h1_60, 0)}, n = {int(h1_60['n'])}, p {p_eq(h1_60['p'])}), so H1's second half, that pooling "
        f"helps at {LOAD_HEAVY}{PCT} load too, is " + ("supported" if h1_60["hi"] < 0 else "not supported") +
        " (Table 7; the 60&#8239;% rows lie outside the Holm family of Section 4.5).")
    def h4_60(p, name):
        if p["hi"] < 0:
            return f"the {name} cut the wait by {h_(-p['mean'])} (95{PCT} CI {ci_abs(p)})"
        if p["lo"] > 0:
            return f"the {name} lengthened the wait by {h_(p['mean'])} (95{PCT} CI {ci_h(p['lo'], p['hi'])})"
        return (f"the {name}'s difference, {h_(p['mean'], 1, sign=True)} (95{PCT} CI {ci_h(p['lo'], p['hi'])}), "
                f"includes zero")
    V["P1-H4-60-SENTENCE"] = (f"At {LOAD_HEAVY}{PCT} load " + h4_60(lin60, "linear model") + " and " +
                              h4_60(mlp60, "network") + f" (n = {int(lin60['n'])}; Table 7).")
    GROUP_NAME = {"B_strict": "the strict dispatcher on Earth", "B_plan": "the plan-ahead dispatcher on Earth",
                  "relay08": f"the {RELAY08} relay"}
    def shown(k, load):
        row = r.reg(k, load)
        return row[f"{M}_v1"] if bool(row["earth_independent"]) and f"{M}_v1" in row else row[M]
    a60 = [shown(k, LOAD_HEAVY) for k in ("A_strict", "A_plan", "A_moon", "A_full")]
    mid60 = {k: shown(k, LOAD_HEAVY) for k in EARTH_LOSING}
    bot60 = {k: shown(k, LOAD_HEAVY) for k in BOTTOM}
    check(min(a60) > max(mid60.values()) and min(a60) > max(bot60.values()), "owners alone wait longest at 60 % too")
    rng = lambda vals: rng_txt(list(vals), lambda x: num(x, 0)) + NB + "h"
    if min(mid60.values()) > max(bot60.values()):
        V["P1-GROUPS-60-SENTENCE"] = (f"At {LOAD_HEAVY}{PCT} load the three groups stand in the same order: owners "
                                      f"alone {rng(a60)}, the Earth-losing pooled regimes {rng(mid60.values())} and "
                                      f"the on-Moon regimes with the marketplace {rng(bot60.values())}.")
    else:
        inside = [k for k in EARTH_LOSING if mid60[k] <= max(bot60.values())]
        V["P1-GROUPS-60-SENTENCE"] = (f"At {LOAD_HEAVY}{PCT} load owners alone still wait longest ({rng(a60)}), but "
                                      f"the middle and bottom groups overlap: " +
                                      listing(f"{GROUP_NAME[k]} waits {h_(mid60[k])}" for k in inside) +
                                      f", inside the range of the on-Moon regimes and the marketplace "
                                      f"({rng(bot60.values())}).")
    if lin10["hi"] < 0:
        V["P1-H4-LIGHT-CLAUSE"] = "and the linear model helped there too"
    elif lin10["lo"] < 0 < lin10["hi"]:
        V["P1-H4-LIGHT-CLAUSE"] = ("and there the data could show neither a gain nor its absence: the gain's "
                                   f"interval ({ci_h(-lin10['hi'], -lin10['lo'])}) includes zero and reaches past the "
                                   "&plusmn;2&#8239;% margin")
    else:
        V["P1-H4-LIGHT-CLAUSE"] = "and there the linear model was worse than the hand-built bids"
    # Referee M8, task B-106, and B-122: the evaluation of the learned bids (30 seeds at 30 and 60 % load), the guard
    # runs (10 seeds) and the out-of-range cells are read from the run on the engine with PREREG change 5 (the dispatch
    # fixed point). The 12 Nov rerun (B-106) ran without it; its headline values are quoted once, as the old values,
    # in 4.6. The imitation statistics are a training record and are not rerun. H4's confirmatory test stays E40's.
    le = r.dev["learned_eval"]
    OLD, RR = r.L_rerun, r.L_fix
    if OLD is None:
        raise SystemExit(f"{le['rerun_file']} is missing: the old values of the learned-bid evaluation are read from it")
    check("WITHOUT PREREG change 5" in OLD.get("engine_note_b122", "") and "ATC_learned_eval_fixpoint.json" in OLD["engine_note_b122"],
          "the 12 November rerun file says it ran without change 5 and names the fixed-point file")
    check("change 5 on" in RR["engine"] and str(RR["code"]).endswith("+fixpoint")
          and "same evaluation seeds" in RR["fixpoint_note"] and "were not retrained" in RR["fixpoint_note"]
          and "trained" in RR["fixpoint_note"] and "without the fixed point" in RR["fixpoint_note"],
          "the fixed-point evaluation ran with change 5, on the same seeds and policies, which were trained without it and not retrained")
    gate = RR["gate_hand_30_equals_E40_C_AUCTION"]
    check(gate["max_abs_diff_h"] == 0 and abs(gate["E40_mean_h"] - lin30["b_mean"]) < 1e-3,
          "the fixed-point evaluation's hand bids at 30 % equal E40's auction runs run for run")
    ood_rerun = isinstance(RR.get("ood"), dict) and len(RR["ood"]) > 0
    if not ood_rerun:
        raise SystemExit("the fixed-point evaluation has no out-of-range cells")
    r.ood_src, r.ood_rerun = RR["ood"], ood_rerun
    rd = OLD["dates"]["rerun"]
    y, mth, dd = (int(x) for x in rd.split("-"))
    RERUN_DATE = f"{dd} {['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'][mth - 1]} {y}"
    check("same evaluation seeds" in OLD["rerun_note"] and "not retrained" in OLD["rerun_note"], "the rerun used the same seeds and policies")
    ev, evo = RR["eval"], OLD["eval"]
    ci2 = lambda q, nd=2: f"{num(q['ci95'][0], nd)} to {num(q['ci95'][1], nd)}{NB}h"
    l30, l60 = ev[str(LOAD_MAIN)]["linear"], ev[str(LOAD_HEAVY)]["linear"]
    m30, m60 = ev[str(LOAD_MAIN)]["mlp"], ev[str(LOAD_HEAVY)]["mlp"]
    o30, o60 = evo[str(LOAD_MAIN)]["linear"]["vs_hand_h"], evo[str(LOAD_HEAVY)]["linear"]["vs_hand_h"]
    check(l30["vs_hand_h"]["ci95"][1] < 0 and l60["vs_hand_h"]["ci95"][1] < 0, "on the fixed point the linear bids cut the urgent wait at 30 and 60 % load")
    check(all(q["vs_hand_h"]["ci95"][0] < 0 < q["vs_hand_h"]["ci95"][1] for q in (m30, m60)), "on the fixed point the network is not distinguishable from hand bids at either load")
    check(o30["ci95"][1] < 0 and o60["ci95"][1] < 0 and all(evo[L]["mlp"]["vs_hand_h"]["ci95"][0] < 0 < evo[L]["mlp"]["vs_hand_h"]["ci95"][1] for L in ("30", "60")),
          "without the fixed point the same verdicts held: the linear bids cut the wait at both loads, the network at neither")
    # the fixed-point evaluation is E40's runs: its means equal E40's cells of the same bid rules at both loads
    E40LAB = {"hand": "C_AUCTION", "mlp": "C_LEARNED_MLP", "linear": "C_LEARNED_LIN"}
    for L in (LOAD_MAIN, LOAD_HEAVY):
        rr = r.r[r.r["load"] == L].set_index("label")
        for k, lab in E40LAB.items():
            check(abs(ev[str(L)][k]["urgent_mean_h"] - float(rr.loc[lab, "atc_urgent_wait_mean_cens_h_v1"])) < 1e-3,
                  f"the fixed-point evaluation's {k} cell at {L} % equals E40's {lab} cell (block one)")
    for kind, key in (("linear", "H4_LIN"), ("mlp", "H4_MLP")):
        for L in (LOAD_MAIN, LOAD_HEAVY):
            e = r.pair(key, L)
            check(abs(ev[str(L)][kind]["vs_hand_h"]["mean"] - e["mean"]) < 1e-3, f"the fixed-point evaluation's {kind} difference at {L} % is E40's H4 difference")
    check(abs(l30["vs_hand_h"]["mean"] - lin30["mean"]) < 1e-3, "the evaluation's linear gain at 30 % is E40's")
    V["P1-LEARNED-EVAL-LABEL"] = "evaluation on the engine with the dispatch fixed point"
    V["P1-LEARNED-EVAL-SENTENCE"] = (
        f"The evaluation of the learned bids first made on {le['file_date']}, before the engine fixes of changes 4 and "
        f"5, was rerun on {RERUN_DATE} with the same seeds and policies, but without change 5, the dispatch fixed "
        f"point; the values here are from a third run on the engine with it (Section 4.6). Its hand-built bids at "
        f"{LOAD_MAIN}{PCT} load equal E40's auction runs run for run, and its means for all three bid rules equal "
        f"E40's cells at both loads. On its {l30['vs_hand_h']['n']} seeds the linear correction changed the urgent "
        f"wait against hand-built bids by {h_(l30['vs_hand_h']['mean'], 2, sign=True)} ({ci2(l30['vs_hand_h'])}; "
        f"{pc(100 * l30['vs_hand_share'], 1, sign=True)}) at {LOAD_MAIN}{PCT} load and by "
        f"{h_(l60['vs_hand_h']['mean'], 1, sign=True)} ({ci2(l60['vs_hand_h'], 1)}; "
        f"{pc(100 * l60['vs_hand_share'], 1, sign=True)}) at {LOAD_HEAVY}{PCT}, E40's differences with a paired t "
        f"interval; the network's difference was {h_(m30['vs_hand_h']['mean'], 2, sign=True)} "
        f"({ci2(m30['vs_hand_h'])}) and {h_(m60['vs_hand_h']['mean'], 1, sign=True)} ({ci2(m60['vs_hand_h'], 1)}), "
        f"not distinguishable from zero at either load.")
    V["P1-LEARNED-EVAL-DEPARTURE-SENTENCE"] = (
        f"The evaluation of the learned bids made before the main runs, which predated both engine fixes, was rerun in "
        f"full on {RERUN_DATE}, but that rerun ran without change 5, the dispatch fixed point: the training script "
        f"that runs the evaluation never switched it on, and it is off unless switched on. The evaluation was run "
        f"again with it, and every learned-bid value in Section 5.6 (the evaluation, the guard runs, Table 6, the "
        f"agreement with the marketplace and the two controls) is from that run, whose hand-built bids at "
        f"{LOAD_MAIN}{PCT} load equal E40's auction runs run for run. The linear correction against hand-built bids "
        f"went from {h_(o30['mean'], 2, sign=True)} ({ci2(o30)}) to {h_(l30['vs_hand_h']['mean'], 2, sign=True)} "
        f"({ci2(l30['vs_hand_h'])}) at {LOAD_MAIN}{PCT} load and from {h_(o60['mean'], 1, sign=True)} "
        f"({ci2(o60, 1)}) to {h_(l60['vs_hand_h']['mean'], 1, sign=True)} ({ci2(l60['vs_hand_h'], 1)}) at "
        f"{LOAD_HEAVY}{PCT}; no registered decision changed, since H4 is tested on E40. The check on other cargo at "
        f"{LOAD_MAIN}{PCT} load now comes out clean, and in Table 6 the light-load interval now reaches zero (Section "
        f"5.6). The policies were trained without the fixed point and were not retrained (Section 7).")
    # the guard runs: does other cargo pay for the gain? (10 seeds; linear minus hand)
    GD, GO = RR["guards"], OLD["guards"]
    g = GD[str(LOAD_HEAVY)]
    gm, gmo = GD[str(LOAD_MAIN)], GO[str(LOAD_MAIN)]
    d_ = lambda q: q["linear_minus_hand"]
    for k in ("atc_urgent_wait_mean_cens_h", "delay_prio2_mean_h", "delay_mean_bulk", "delay_mean_h", "tonne_days_waiting"):
        check(d_(g[k])["ci95"][1] < 0, f"guard {k} fell with the learned bids at 60 % (interval below zero)")
    check(abs(g["delivered_kg"]["linear"] / g["delivered_kg"]["hand"] - 1) < 0.005, "tonnes delivered did not change")
    # "no guard metric worsens" at either load: for every metric where more is worse, no interval lies above zero,
    # and delivered mass has no interval below zero
    WORSE_UP = ("atc_urgent_wait_mean_cens_h", "delay_prio2_mean_h", "delay_mean_bulk", "delay_mean_h", "tonne_days_waiting", "atc_starved_items")
    for L in (LOAD_MAIN, LOAD_HEAVY):
        gg = GD[str(L)]
        check(sorted(gg) == sorted(WORSE_UP + ("delivered_kg",)), f"the guard metrics at {L} % are the seven the text covers")
        check(all(d_(gg[k])["ci95"][0] <= 0 for k in WORSE_UP) and d_(gg["delivered_kg"])["ci95"][1] >= 0,
              f"on the fixed point no guard metric worsens with the learned bids at {L} %")
    V["P1-GUARD-TONNEDAYS-PCT"] = pc(100 * (g["tonne_days_waiting"]["linear"] / g["tonne_days_waiting"]["hand"] - 1), 0,
                                     sign=True)
    gu, gb, ga = d_(gm["atc_urgent_wait_mean_cens_h"]), d_(gm["delay_mean_bulk"]), d_(gm["delay_mean_h"])
    gbo, guo = d_(gmo["delay_mean_bulk"]), d_(gmo["atc_urgent_wait_mean_cens_h"])
    word = lambda q: ("fell" if q["ci95"][1] < 0 else "rose" if q["ci95"][0] > 0 else "did not move measurably")
    urgent_ok30 = gu["ci95"][1] < 0
    check(urgent_ok30 and gb["ci95"][0] < 0 < gb["ci95"][1], "on the fixed point the urgent gain shows on the guard seeds and bulk delay does not move")
    check(gbo["ci95"][0] > 0 and guo["ci95"][0] < 0 < guo["ci95"][1],
          "without the fixed point bulk cargo waited longer and the urgent gain was not distinguishable from zero on the guard seeds")
    V["P1-GUARD-30-SENTENCE"] = (
        f"At {LOAD_MAIN}{PCT} load the check comes out clean on the engine with the fixed point, and it did not on the "
        f"engine without it. On its {gu['n']} seeds the urgent wait {word(gu)} ({h_(gu['mean'], 2, sign=True)}, "
        f"{ci2(gu)}), the delay of bulk cargo {word(gb)} ({h_(gb['mean'], 2, sign=True)}, {ci2(gb)}), the delay of "
        f"all cargo {word(ga)} ({h_(ga['mean'], 2, sign=True)}, {ci2(ga)}), and no measure of other cargo rose with "
        f"an interval clear of zero, at this load or at {LOAD_HEAVY}{PCT}. Without the fixed point the delay of bulk "
        f"cargo rose ({h_(gbo['mean'], 2, sign=True)}, {ci2(gbo)}) and the urgent gain was not distinguishable from "
        f"zero on those ten seeds ({h_(guo['mean'], 2, sign=True)}, {ci2(guo)}).")
    V["P1-GUARD-30-CLAUSE"] = ("a ten-seed check found no cost to other cargo at the middle load either; without the "
                               "fixed point it had found bulk cargo waiting slightly longer")
    ha = {k: ev[str(LOAD_MAIN)][k]["heldout_agreement"] for k in ("hand", "mlp", "linear")}
    check("NOT rerun" in str(RR["imitation"].get("status", "")), "the fixed-point file marks the imitation statistics as not rerun")
    V["P1-IMIT-RERUN-SENTENCE"] = (
        f"These figures are a record of training: the first imitation round on the tuning seeds, with the engine of "
        f"{le['file_date']}; they were not rerun. On the engine with the dispatch fixed point, on the evaluation seeds "
        f"at {LOAD_MAIN}{PCT} load, the hand-built bids chose the marketplace's item in {sh(ha['hand'], 2)} of rounds, "
        f"the network's bids in {sh(ha['mlp'], 2)} and the linear bids in {sh(ha['linear'], 2)}. These come from runs "
        f"that record every round, which on this engine lose a wake-up of the dispatcher and so are not the runs "
        f"that give the outcomes (Section 7).")
    V["P1-OOD-LABEL-SENTENCE"] = "The cells of Table 6 are from the same run on the engine with the fixed point."
    V["P1-LEARNED-ENGINE-LIMIT-SENTENCE"] = (
        f"The two policies were trained, by imitation and by the search on the objective, on the engine without the "
        f"dispatch fixed point of change 5, and were not retrained when it came in. Their evaluation, the guard runs, "
        f"Table 6 and the two controls of Section 5.6 are on the engine with it, and the evaluation of {RERUN_DATE} "
        f"that a first draft quoted ran without it (Section 4.6). Policies searched on the current engine might "
        f"differ. With the fixed point on, a run that also records, at every auction round, the marketplace's choice "
        f"for the agreement figures loses a wake-up of the dispatcher, and so gives a different outcome from the same "
        f"run without recording: the marketplace call that makes the record suppresses the wake-up it schedules but "
        f"still marks it as pending, and the real dispatch then skips its own. The cause is found and not yet fixed. "
        f"Every outcome reported comes from runs without recording; the agreement figures of Section 5.11 on this "
        f"engine come from recording runs and carry the lost wake-up. The other-cargo check is on ten seeds per load: on this engine it found no cost at "
        f"either load, and on the engine without the fixed point it found bulk cargo waiting slightly longer at the "
        f"middle load. The imitation statistics of Section 5.11 are a training record from the earlier engine. The "
        f"frozen policies were run on the evaluation seeds more than once, in the first evaluation, in E40 before and "
        f"after change 5 and in the two reruns of that evaluation; no training or selection used those seeds.")
    ood = r.ood_src

    # Part 4 (12 Nov): the cell "year 2038" is not an out-of-range test. The start-year setting has no effect on
    # these Earth-independent runs, so the cell repeats the guard runs at the middle load (start year 2028, the same
    # seeds). It is kept out of the count, and the build stops if it ever differs from the guard values.
    YEAR_CELL = "year 2038"
    if YEAR_CELL not in ood:
        raise KeyError(f"the out-of-range table has no cell {YEAR_CELL!r}")
    if ood_rerun:
        yc, gq = ood[YEAR_CELL], gm["atc_urgent_wait_mean_cens_h"]
        same = (abs(yc["hand"]["urgent_mean_h"] - gq["hand"]) < 1e-3 and abs(yc["linear"]["urgent_mean_h"] - gq["linear"]) < 1e-3
                and abs(yc["linear"]["vs_hand_h"]["mean"] - gq["linear_minus_hand"]["mean"]) < 1e-3
                and all(abs(a - b) < 1e-3 for a, b in zip(yc["linear"]["vs_hand_h"]["ci95"], gq["linear_minus_hand"]["ci95"]))
                and yc["linear"]["vs_hand_h"]["n"] == gq["linear_minus_hand"]["n"])
        if not same:
            raise SystemExit(f"the out-of-range cell {YEAR_CELL!r} no longer equals the guard runs at {LOAD_MAIN} % load: "
                             f"the paper says it repeats them and keeps it out of the count; revise P1-OOD-SENTENCE")
    diffs = {k: v["linear"]["vs_hand_h"] for k, v in ood.items() if k != YEAR_CELL}
    check(all(d["mean"] < 0 for d in diffs.values()), "the linear model kept the same sign in every out-of-range cell")
    V["P1-OOD-N-CELLS"] = words(len(diffs))
    n_sig = sum(d["ci95"][1] < 0 for d in diffs.values())
    V["P1-OOD-N-SIG"] = words(n_sig)
    OOD_WORDS = {"2eq": "two owners", "5eq": "five owners", "loss 0.25": "message loss 0.25", "loss 0.40": "message loss 0.40",
                 "load 10 %": "light load"}
    if set(diffs) != set(OOD_WORDS):
        raise KeyError(f"unexpected out-of-range cells: {sorted(diffs)}")
    oq = lambda k: f"{OOD_WORDS[k]} ({h_(diffs[k]['mean'], 2, sign=True)}, {num(diffs[k]['ci95'][0], 2)} to {num(diffs[k]['ci95'][1], 2)}{NB}h)"
    sig = [k for k in diffs if diffs[k]["ci95"][1] < 0]
    ns = [k for k in diffs if diffs[k]["ci95"][1] >= 0]
    V["P1-OOD-SENTENCE"] = (
        f"Outside its training range the linear model was run in {words(len(diffs))} cells of ten seeds each: two "
        f"and five owners, message loss 0.25 and 0.40, and light load. It kept the same sign in all "
        f"{words(len(diffs))}, with an interval clear of zero in {words(n_sig)}"
        + (": " + listing(oq(k) for k in sig) if sig else "")
        + (". The interval includes zero at " + listing(oq(k) for k in ns) if ns else "")
        + " (Table 6). "
        + ("A sixth cell, a later start year, is not an out-of-range test and is not counted: the start year "
           "changes nothing in these runs, which never wait for Earth, so the cell repeats the guard runs at the "
           "middle load value for value. " if ood_rerun else
           "A sixth cell, a later start year, is not counted: the start year changes nothing in these runs, which "
           "never wait for Earth. ")
        + (f"The file of {le['file_date']} mixed engine states: its out-of-range runs were made after a fix that "
           f"its evaluation and guard runs predate. The run on the fixed point has all three on one engine." if ood_rerun else ""))
    # the linear weights in plain words: the output is a bid correction in hours (positive = bids lower = favoured)
    w = np.asarray(r.lin["layers"][0]["w"], float).reshape(-1)
    names, scale = r.lin["obs"]["names"], r.lin["obs"]["scale"]
    if len(w) != len(names):
        raise ValueError("linear policy: weights and feature names differ in length")
    order = np.argsort(-np.abs(w))
    fav = [i for i in order if w[i] > 0][:3]
    dis = [i for i in order if w[i] < 0][:3]
    unit = lambda i: f"{num(w[i], 2, sign=True)}{NB}h per unit" + (f", the feature scaled by 1/{scale[i]:g}"
                                                                     if scale[i] != 1 else "")
    V["P1-LIN-WEIGHTS-SENTENCE"] = (
        "The largest weights lower the bid, and so favour the item, for " +
        listing(f"{FEATURE_WORDS[names[i]]} ({unit(i)})" for i in fav) +
        ", and raise it for " + listing(f"{FEATURE_WORDS[names[i]]} ({unit(i)})" for i in dis) +
        "; the other weights in each direction are smaller than these.")
    check(all(abs(w[i]) <= min(abs(w[j]) for j in fav) for i in range(len(w)) if w[i] > 0 and i not in fav) and
          all(abs(w[i]) <= min(abs(w[j]) for j in dis) for i in range(len(w)) if w[i] < 0 and i not in dis),
          "the three named weights in each direction are that direction's largest")

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
    # referee row 42: the count that passed when those rows were rerun (B-74), and the suite's size at this revision
    V["P1-CHECK-N-TESTS-NOW"] = f"{dev['regression_check']['pytest_collected']}"
    V["P1-CHECK-TESTS-DATE"] = html.escape(dev["regression_check"]["pytest_collected_date"])
    check(dev["regression_check"]["pytest_collected"] >= dev["regression_check"]["pytest_tests"], "the test suite has not shrunk")
    # Referee S8: how many urgent items a run holds (the primary outcome is a mean over them)
    ui = {}
    for load in (LOAD_LIGHT, LOAD_MAIN, LOAD_HEAVY):
        gl = r.full("E40")
        gl = gl[gl["load"] == load]
        go = gl[(gl["label"] == LABELS["O"]) & (gl["run_block"] == "v1")]["atc_urgent_items"]
        ui[load] = (float(go.mean()), int(gl["atc_urgent_items"].min()), int(gl["atc_urgent_items"].max()))
    n_empty = int((r.full("E40")["atc_urgent_items"] == 0).sum())
    V["P1-URGENT-ITEMS-SENTENCE"] = (
        "A run holds few urgent items: on average "
        + listing(f"{num(ui[l][0], 0)} at {l}{PCT} load (from {ui[l][1]} to {ui[l][2]} over all E40 runs)" for l in ui)
        + ", counted in the full-information marketplace's block-one runs"
        + (f"; {words(n_empty)} run at light load had none and has no value of the outcome" if n_empty == 1 else
           f"; {words(n_empty)} runs had none" if n_empty else "")
        + ". The light-load results therefore rest on means of about "
        + f"{num(ui[LOAD_LIGHT][0], 0)} items a run.")
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
    # the registered rule (half-width over 10 % of the mean: add seeds in tens) against H3a's comparison, disclosed
    half90 = (h3["hi90"] - h3["lo90"]) / 2
    tenpct = 0.1 * abs(h3["b_mean"])
    # Referee M6: the rule read on each E40 cell's mean of the primary outcome (the valid runs: block one for an
    # Earth-independent regime, all 80 otherwise), with the percentile bootstrap used everywhere else.
    f40 = r.full("E40")
    over, near, per_load = [], [], {}
    for (load, label), gcell in f40.groupby(["load", "label"]):
        gv = gcell[gcell["run_block"] == "v1"] if label in RP.EARTH_INDEPENDENT else gcell
        bb = AE.boot(gv[PRIMARY].dropna().to_numpy(float))
        ratio = (bb["ci"][1] - bb["ci"][0]) / 2 / bb["mean"]
        per_load.setdefault(int(load), [0, 0])[1] += 1
        if ratio > 0.10:
            over.append((int(load), label))
            per_load[int(load)][0] += 1
        if abs(ratio - 0.10) < 0.005:
            near.append((int(load), label))
    n_cells40 = sum(v[1] for v in per_load.values())
    check(n_cells40 == n_cells["E40"], "the seed rule is read on every E40 cell")
    check(len(over) > n_cells40 / 2, "the half-width exceeds 10 % of the mean in most E40 cells")
    # the same rule read on the paired differences of the confirmatory comparisons, against 10 % of the reference mean
    conf = [("H1", h1, "lo", "hi"), ("H2", h2, "lo", "hi"), ("H3a", h3, "lo90", "hi90"), ("H4 (linear)", lin30, "lo", "hi"),
            ("H4 (network)", mlp30, "lo", "hi")]
    wide = [nm for nm, q, a, b in conf if (q[b] - q[a]) / 2 > 0.1 * abs(q["b_mean"])]
    V["P1-SEEDS-N-OVER"], V["P1-SEEDS-N-CELLS"] = f"{len(over)}", f"{n_cells40}"
    V["P1-SEEDS-ADDED"] = (
        f"The rule was not applied: no seeds were added in any cell, and every cell holds the 30 seeds of the design"
        + (" (and the 50 runs of the second block where it applies)" if any(k.endswith("|v3") for k in npc) else "")
        + f". Read on each cell's mean of the primary outcome, the 95{PCT} half-width exceeded 10{PCT} of the mean in "
          f"{len(over)} of the {n_cells40} E40 cells: "
        + listing(f"{per_load[l][0]} of {per_load[l][1]} at {l}{PCT} load" for l in sorted(per_load))
        + (f" ({words(len(near))} cells lie within half a percentage point of the threshold, so the count depends that "
           f"much on the resampling)" if near else "")
        + ". Read on the paired differences, against 10" + PCT + " of the reference regime's mean, it was exceeded for "
        + (listing(wide) if wide else "none of the confirmatory comparisons")
        + f" (for H3a a 90{PCT} half-width of {h_(half90, 2)} against {h_(tenpct, 2)}). By the rule ten more seeds at a "
          f"time should have been run in those cells. We did not extend any sample after seeing results, so every "
          f"interval in this paper is from the fixed design of 30 seeds, or of 80 runs where a regime depends on "
          f"Earth (Section 7).")
    check(half90 > tenpct, "H3a's 90 % half-width exceeds 10 % of the marketplace mean")
    check(not r.rerun["flagged"], "the rerun after the ordering fix changed no cell")

    # --- E41 (pending until it runs) -------------------------------------------------------------------------
    def rally(label, col, fmt):
        g = r.runs_of("E41", LABELS[label])
        return fmt(g[col].mean())
    fill("P1-E41-RALLY-ON-URGENT", lambda: rally("E41_rally_on", M, h_), "E41")
    fill("P1-E41-RALLY-OFF-URGENT", lambda: rally("E41_rally_off", M, h_), "E41")
    fill("P1-E41-RALLY-ON-T", lambda: rally("E41_rally_on", "delivered_kg", lambda x: t_(x / 1000)), "E41")
    fill("P1-E41-RALLY-OFF-T", lambda: rally("E41_rally_off", "delivered_kg", lambda x: t_(x / 1000)), "E41")
    # Section 5.5: three composed paragraphs from table_E41_pairs.csv, table_E41_cells.csv and E41_fit.json. Every
    # direction word is chosen from the interval, so the prose cannot contradict the numbers it quotes.
    REG4 = ("C_LEADER", "C_AUCTION", "C_LEARNED_MLP", "C_LEARNED_LIN")
    NAME4 = {"C_LEADER": "the elected leader", "C_AUCTION": "the auction", "C_LEARNED_MLP": "the learned network bids",
             "C_LEARNED_LIN": "the learned linear bids"}

    def delta(p, nd=1):
        """'+1.4 h (95 % CI 0.2 to 2.6 h)'."""
        return f"{h_(p['mean'], nd, sign=True)} (95{PCT} CI {ci_h(p['lo'], p['hi'], nd)})"

    def excl0(p):
        return p["lo"] > 0 or p["hi"] < 0

    def moved(p, what, nd=1):
        """'raised X by ...', 'cut X by ...' or 'moved X by ... (not distinguishable from zero)'."""
        if p["lo"] > 0:
            return f"raised {what} by {h_(p['mean'], nd)} (95{PCT} CI {ci_h(p['lo'], p['hi'], nd)})"
        if p["hi"] < 0:
            return f"cut {what} by {h_(-p['mean'], nd)} (95{PCT} CI {ci_abs(p, nd)})"
        if p["mean"] == 0 and p["lo"] == 0 and p["hi"] == 0:
            return f"left {what} unchanged on every seed"
        return (f"{'lowered' if p['mean'] < 0 else 'raised'} {what} by {h_(abs(p['mean']), nd)} (95{PCT} CI "
                f"{ci_h(p['lo'], p['hi'], nd)}), not distinguishable from zero")

    def need_f41():
        if r.f41 is None:
            raise Pending("E41_fit.json (analyse_e41_pairs.py) has not been built")
        return r.f41

    def e41_loss_sentence():
        f = need_f41()
        base = {reg: r.pair41(f"{reg} loss 0 - O_ORACLE") for reg in REG4}
        at40 = {reg: r.pair41(f"{reg} loss 0.4 - {reg} loss 0") for reg in REG4}
        burst = {reg: r.pair41(f"{reg} burst 0.25 - {reg} loss 0.25") for reg in REG4}
        slope, cross = f["slope_per_point_of_loss"], f["crossing_loss_vs_oracle"]
        if any(reg not in slope for reg in REG4):
            raise Pending("E41 loss cells incomplete for the slope")
        o = base["C_AUCTION"]["b_mean"]
        check(all(abs(base[reg]["b_mean"] - o) < 1e-9 for reg in REG4), "every regime pairs with the same oracle runs")
        diff = [reg for reg in REG4 if excl0(base[reg])]
        s1 = ("With no message loss the four on-Moon regimes kept urgent cargo waiting " +
              listing(f"{h_(base[reg]['b_mean'] + base[reg]['mean'])} ({NAME4[reg]})" for reg in REG4) +
              f", against {h_(o)} for the full-information marketplace on the same seeds; " +
              ("none of the four differed from it by a 95&#8239;% CI that excludes zero." if not diff else
               listing(f"{NAME4[reg]} lay {'below' if base[reg]['hi'] < 0 else 'above'} it by "
                       f"{h_(abs(base[reg]['mean']))} ({ci_h(*sorted((abs(base[reg]['lo']), abs(base[reg]['hi']))))})"
                       for reg in diff) + (" and the others did not differ from it." if len(diff) < 4 else ".")))
        check(all(at40[reg]["mean"] > 0 for reg in REG4), "loss 0.40 lengthened every regime's wait on average")
        s2 = ("Raising the loss to 0.40 added " +
              listing(f"{h_(at40[reg]['mean'])} ({ci_h(at40[reg]['lo'], at40[reg]['hi'])}) for {NAME4[reg]}"
                      for reg in REG4) +
              ", that is " + listing(f"{num(slope[reg]['pct_of_loss0_per_point'], 2)}" for reg in REG4) +
              f"{PCT} of the loss-free wait per point of loss. The best allocators in Lott and Honary's benchmark "
              f"lose about 0.3{PCT} of makespan per point [11]; makespan and cargo wait are different quantities, so "
              "the two slopes are set side by side and not compared.")
        above = [reg for reg in REG4 if cross.get(reg)]
        below = [reg for reg in REG4 if not cross.get(reg)]
        by_loss = sorted({cross[reg] for reg in above}, key=float)
        s3 = ((listing(listing(NAME4[reg] for reg in above if cross[reg] == L) +
                       f" rose above the marketplace at loss {num(float(L), 2)}" for L in by_loss)
               + " (one-sided 95&#8239;% lower bound of the paired difference above zero)" if above else "") +
              ("; " if above and below else "") +
              (listing(NAME4[reg] for reg in below) + (" stayed level with or below it through loss 0.40"
                                                       if below else "")) + ".")
        s3 = s3[0].upper() + s3[1:]
        bd = [reg for reg in REG4 if excl0(burst[reg])]
        s4 = ("Bursty loss at a mean rate of 0.25, against steady loss at the same rate, " +
              ("was not distinguishable from steady loss at 0.25 for any regime (differences " +
               listing(delta(burst[reg]) for reg in REG4) + ")." if not bd else
               listing(f"{moved(burst[reg], 'the wait of ' + NAME4[reg])}" for reg in bd) +
               (" and left the others within their intervals of zero." if len(bd) < 4 else ".")))
        return " ".join((s1, s2, s3, s4))

    def e41_depth_sentence():
        f = need_f41()
        h3b = f["H3b"]
        if h3b.get("supported") is None:
            raise Pending("E41 depth cells of the auction incomplete")
        d5 = {L: r.pair41(f"C_AUCTION depth 5 loss {L} - C_AUCTION loss {L}") for L in ("0.25", "0.4")}
        d2 = {L: r.pair41(f"C_AUCTION depth 2 loss {L} - C_AUCTION loss {L}") for L in ("0.25", "0.4")}
        st1, st5 = r.cell41("C_AUCTION loss 0.4"), r.cell41("C_AUCTION depth 5 loss 0.4")
        learned = {reg: r.pair41(f"{reg} depth 5 loss 0.4 - {reg} loss 0.4") for reg in ("C_LEARNED_MLP", "C_LEARNED_LIN")}
        check(bool(h3b["supported"]) == all(d5[L]["lo"] > 0 for L in d5), "H3b verdict follows the two intervals")
        verdict = "supported" if h3b["supported"] else "not supported"
        stale = st5["atc_claims_stale"] - st1["atc_claims_stale"]
        # Referee S11: no cell has depth 2 or 5 without loss, and the stale claims barely move between the two losses
        sc = {(dp, L): r.cell41(f"C_AUCTION depth {dp} loss {L}")["atc_claims_stale"] for dp in (2, 5) for L in ("0.25", "0.4")}
        flat = all(abs(sc[(dp, "0.4")] - sc[(dp, "0.25")]) < 0.05 * sc[(dp, "0.25")] for dp in (2, 5))
        no_loss0 = not any(str(x).startswith("C_AUCTION depth") and str(x).endswith("loss 0") for x in r.c41["label"])
        check(no_loss0, "E41 has no bundle-depth cell without message loss")
        check(flat, "the stale claims are almost the same at loss 0.25 and 0.40")
        s11 = ""      # the two loss-free cells were run as a control (B-117 b): P1-B117B-SENTENCE follows this one
        return (f"Bundles of up to five jobs {'hurt' if h3b['supported'] else 'did not hurt'} the auction: against "
                f"depth 1, depth 5 {moved(d5['0.25'], 'the urgent wait')} at loss 0.25 and "
                f"{moved(d5['0.4'], 'it')} at loss 0.40, and depth 2 {moved(d2['0.25'], 'it')} at loss 0.25 and "
                f"{moved(d2['0.4'], 'it')} at loss 0.40. Stale claims, bids on items that another robot had already taken by the "
                f"time the bundle was accepted, {'rose' if stale > 0 else 'fell' if stale < 0 else 'did not change'} "
                f"from {num(st1['atc_claims_stale'], 0)} to {num(st5['atc_claims_stale'], 0)} per year at depth 5 "
                f"and loss 0.40. H3b, that depth 5 is worse than depth 1 at loss 0.25 to 0.40, is {verdict}. "
                f"For the learned bids at loss 0.40, depth 5 "
                + listing(f"{moved(learned[reg], 'the wait of ' + NAME4[reg])}" for reg in learned) + "." + s11)

    def e41_range_sentence():
        f = need_f41()
        rg = {k: r.pair41(f"C_AUCTION range {k} - C_AUCTION loss 0.1") for k in ("2 km", "10 km", "perfect")}
        rally = r.pair41("C_AUCTION rally off - C_AUCTION loss 0.1")
        mast = r.pair41("C_AUCTION mast2 PAD_B - C_AUCTION loss 0.1")
        c = {k: r.cell41(f"C_AUCTION {k}") for k in ("loss 0.1", "range 2 km", "rally off", "mast2 PAD_B")}
        out = {k: c[k]["atc_robots_out_share"] for k in c}
        h3c = f["H3c"]["cells"]
        conds = ["loss 0", "loss 0.1", "loss 0.25", "loss 0.4", "burst 0.25", "range 2 km", "range 10 km",
                 "range perfect", "rally off", "mast2 PAD_B"]
        if any(k not in h3c or h3c[k]["n"] < 30 for k in conds):
            raise Pending("E41 leader or auction cells incomplete for H3c")
        COND = {"loss 0": "loss 0", "loss 0.1": "loss 0.10", "loss 0.25": "loss 0.25", "loss 0.4": "loss 0.40",
                "burst 0.25": "bursty loss", "range 2 km": "a 2&nbsp;km range", "range 10 km": "a 10&nbsp;km range",
                "range perfect": "a perfect radio", "rally off": "the lost-link rule off",
                "mast2 PAD_B": "the second mast"}
        matched = [k for k in conds if h3c[k]["matches"]]
        differed = [k for k in conds if h3c[k]["lo"] > 0 or h3c[k]["hi"] < 0]
        undecided = [k for k in conds if k not in matched and k not in differed]
        s1 = (f"Radio range mattered less than loss: against the default 5&nbsp;km range, a 2&nbsp;km range "
              f"{moved(rg['2 km'], chr(39).join(('the auction', 's urgent wait')))}, a 10&nbsp;km range "
              f"{moved(rg['10 km'], 'it')} and a radio that reaches every robot {moved(rg['perfect'], 'it')}.")
        def rally_verb(p):
            if p["lo"] > 0:
                return f"rose by {h_(p['mean'])} (95{PCT} CI {ci_h(p['lo'], p['hi'])})"
            if p["hi"] < 0:
                return f"fell by {h_(-p['mean'])} (95{PCT} CI {ci_abs(p)})"
            return f"moved by {delta(p)}, not distinguishable from zero"
        cut = out["mast2 PAD_B"] < out["loss 0.1"]
        s2 = (f"With the lost-link rule off the wait {rally_verb(rally)}, and the share of robot-time out of reach of "
              f"every mast went from {sh(out['loss 0.1'], 1)} to {sh(out['rally off'], 1)} "
              f"({num(c['loss 0.1']['atc_rallies'], 0)} returns to a mast per year with the rule on). "
              f"A second mast at pad B "
              f"{moved(mast, 'the wait')} and {'cut' if cut else 'left'} that share "
              f"{'from ' + sh(out['loss 0.1'], 1) + ' to ' if cut else 'at '}{sh(out['mast2 PAD_B'], 1)}.")
        s3 = ("H3c, that the elected leader matches the auction unless the mesh partitions, was tested in ten cells by "
              f"equivalence within &plusmn;10&#8239;% (90&#8239;% CI of the ratio): the leader matched the auction "
              + ("under " + listing(COND[k] for k in matched) if matched else "in no cell") +
              ("; it differed under " + listing(f"{COND[k]} ({'slower' if h3c[k]['mean'] > 0 else 'faster'} by "
                                                f"{h_(abs(h3c[k]['mean']))}, 95{PCT} CI "
                                                f"{ci_h(*sorted((abs(h3c[k]['lo']), abs(h3c[k]['hi']))))})"
                                                for k in differed) if differed else "") +
              ("; under " + listing(COND[k] for k in undecided) + " the interval was too wide to decide either way"
               if undecided else "") + ".")
        return " ".join((s1, s2, s3))

    def h3a_rally_sentence():
        """Referee S3: the auction's robots are sent back towards the mast and the marketplace's are not."""
        on, perf = r.cell41("C_AUCTION loss 0.1"), r.cell41("C_AUCTION range perfect")
        pp = r.pair41("C_AUCTION range perfect - C_AUCTION loss 0.1")
        above = perf[M] - h3["b_mean"]
        check(perf["atc_rallies"] < 0.05 * on["atc_rallies"], "with a radio that reaches every robot almost no robot returns to the mast")
        check(above > 0 and h3["mean"] < 0, "with a perfect radio the auction waits longer than the marketplace; by default, less")
        return (f"The comparison is confounded by the lost-link rule. The on-Moon regimes send an idle robot that nobody "
                f"hears back to a site the mast sees, {num(on['atc_rallies'], 0)} times a year in the auction's runs, and "
                f"the marketplace has no such move. Where the radio reaches every robot the returns fall to "
                f"{num(perf['atc_rallies'], 0)} a year and the auction's wait is {h_(perf[M])}, {h_(above)} above the "
                f"marketplace's and {h_(pp['mean'])} ({ci_h(pp['lo'], pp['hi'])}) above its own default cell "
                f"(Section 5.5). That pointed to the repositioning, and not to the place of the decision, as the "
                f"source of the auction's small advantage in the point estimate, but E40 could not separate the two.")
    fill("P1-H3A-RALLY-SENTENCE", h3a_rally_sentence, "E41")
    fill("P1-E41-LOSS-SENTENCE", e41_loss_sentence, "E41")
    fill("P1-E41-DEPTH-SENTENCE", e41_depth_sentence, "E41")
    fill("P1-E41-RANGE-SENTENCE", e41_range_sentence, "E41")
    # B-117 a, b, c (14 Nov): the three controls run after the results were known, each from its own results file
    b117_controls(r, V, check, h3, m3)

    def e41_depth_clause():
        h3b = need_f41()["H3b"]
        if h3b.get("supported") is None:
            raise Pending("E41 depth cells of the auction incomplete")
        return ("Bundle depth 5 made the auction " + ("worse" if h3b["supported"] else "no worse") +
                " at message loss 0.25 and 0.40 (Section 5.5)")

    fill("P1-E41-DEPTH-CLAUSE", e41_depth_clause, "E41")
    fill("P1-CHECKS-SENTENCE", lambda: vv5_checks_sentence("P1", "5.11", check), "B-79")
    fill("P1-FAILED-CHECKS-SENTENCE", lambda: vv5_failed_sentence("P1", "3.11", check, brief=True), "B-79")
    fill("P1-ID-FIX-SENTENCE", lambda: idfix_sentence(check, ("E40", "E41", "E42")), "B-79 id fix")

    def l5_sentence():
        d, rows = vv5_load("P1", check)
        l5 = [x for x in rows if x.get("id") == "L5"]
        if not l5:
            raise Pending("the L5 rows are not in results/vv_phase5.json")
        failed = [x for x in l5 if not x.get("passed")]
        if not failed:
            return "The learned bids were monotone in approach time, mass and battery on every probe (L5)."
        bits = []
        pol = {"atc_bid_v1": "the network", "atc_bid_linear_v1": "the linear model"}
        for x in failed:
            bits.append(f"{pol.get(str(x.get('sub')), html.escape(str(x.get('sub'))))} in {num(100 * x['simulated'], 0)}{PCT} of the probes")
        return (f"The L5 failures are properties of the trained policies, not of the code: the learned bid was not monotone in approach time, "
                f"mass and battery for " + " and ".join(bits) + ", as the policies were tuned on urgent wait and not constrained to monotone bids (Section 3.10).")
    fill("P1-CHECK-FINDINGS-SENTENCE", l5_sentence, "B-79 tranche 3")
    fill("P1-PAIRING-SENTENCE", lambda: vv5_pairing_sentence("P1", "3.11", check), "B-79")
    fill("P1-E41-REPLICATION-SENTENCE", lambda: (
        lambda rep: (f"E41's default auction cell reran E40's auction at 30&#8239;% on the same {int(rep['n'])} seeds "
                     + ("and reproduced every run exactly" if rep["mean"] == 0 and rep["lo"] == 0 and rep["hi"] == 0
                        else f"with a mean difference of {delta(rep, 2)}") + ".")
    )(need_f41()["replication_e40"] or (_ for _ in ()).throw(Pending("E41 replication pair not built"))), "E41")

    # --- H6 (E42) ------------------------------------------------------------------------------------------
    f6 = r.fit("hypotheses", "H6")
    check(bool(f6["supported"]), "H6 is supported")

    def h6_sentence():
        # every pair here reads E42 cells; a partial E42 raises Pending inside the fill, not at module level
        parts = []
        for team in ("10", "25"):
            ti = r.pair("H6_team_items", LOAD_MAIN, team=team, loss="0.1")
            parts.append(f"from {sh(ti['b_mean'])} to {sh(ti['b_mean'] + ti['mean'])} at team share 0.{team} "
                         f"(paired difference {num(100 * ti['mean'], 0)} percentage points, 95&#8239;% CI "
                         f"{num(100 * ti['lo'], 0)} to {num(100 * ti['hi'], 0)}, n = {int(ti['n'])})")
            check(ti["lo"] > 0, f"cross-owner pairs raise the share of team items delivered at team share 0.{team}")
        # Referee M5: the tested metric is delivered_share, kilograms delivered over kilograms ready (engine.py), a
        # share of mass. The item counts are computed here from the E42 rows. Referee M12(a): the share of team
        # items a single owner can lift is an input (the mass range against the one same-owner pair of 2,080 kg).
        mass = [r.pair("H6", LOAD_MAIN, team=t, loss="0.1") for t in ("10", "25")]
        check(all(a["metric"] == "delivered_share" for a in mass), "the H6 rows are on delivered_share (mass)")
        check(all(a["lo"] > 0 for a in mass), "cross-owner pairs raise the share of cargo mass delivered")
        check(f6["test"]["comparison"] == LABELS["H6"].format(team="25", loss="0.1"), "the Holm family's H6 row is team share 0.25, loss 0.10")
        e42 = r.full("E42")
        cellname = lambda t, scope: f"C_AUCTION team {t} {scope} loss 0.1"
        items = [raw_pair(e42, cellname(t, "any"), cellname(t, "same_owner"), metric="delivered_items") for t in ("10", "25")]
        check(all(a["lo"] > 0 for a in items), "cross-owner pairs raise the number of items delivered")
        so = {t: e42[e42["label"] == cellname(t, "same_owner")] for t in ("10", "25")}
        lift = {t: (so[t]["p5_team_items_same_owner_liftable"].mean(), so[t]["p5_team_items"].mean(),
                    so[t]["p5_team_items_delivered"].mean()) for t in so}
        check(all(abs(lift[t][2] - lift[t][0]) < 0.25 for t in lift),
              "same-owner pairs deliver about as many team items as lie within the one same-owner pair's capacity")
        held = all(r.pair("H6", LOAD_MAIN, team=t, loss=l)["lo"] > 0 for t in ("10", "25") for l in ("0.25", "0.4"))
        return (
            "Allowing pairs of different owners raised the share of team items delivered " + " and ".join(parts) +
            " at message loss 0.10. The starting share is an input and not a finding: of the "
            + listing(f"{num(lift[t][1], 1)} team items a year at team share 0.{t}, {num(lift[t][0], 1)} "
                      f"({sh(lift[t][0] / lift[t][1])})" for t in ("10", "25"))
            + " weigh no more than the one same-owner pair can lift (FLEX with CLV-1, 2,080&nbsp;kg), by the mass range "
              "we assumed, and the same-owner auction delivered "
            + listing(num(lift[t][2], 1) for t in ("10", "25")) +
            ". H6 is registered on &ldquo;the share of items delivered&rdquo; and names no team share [43]. The "
            "engine's measure is a share of mass, the kilograms delivered over the kilograms ready: it rose by "
            + listing(f"{num(100 * a['mean'], 1)} percentage points ({num(100 * a['lo'], 1)} to "
                      f"{num(100 * a['hi'], 1)}) at team share 0.{t}" for a, t in zip(mass, ("10", "25"))) +
            ". Counted in items, cross-owner pairs delivered "
            + listing(f"{num(a['mean'], 1)} more items a year ({num(a['lo'], 1)} to {num(a['hi'], 1)}) on "
                      f"{num(a['b_mean'], 0)} at team share 0.{t}" for a, t in zip(items, ("10", "25"))) +
            f". Every interval excludes zero, so H6's first part is supported in kilograms and in items. The Holm "
            f"family tests it on the mass share at team share 0.25, a cell the registration does not name "
            f"(adjusted p {p_eq(holm[LABELS['holm_H6']])}, Table 7); 0.10 is the design's default. The gain "
            + ("held" if held else "did not hold in every cell") + " at loss 0.25 and 0.40 (Table 8).")

    fill("P1-H6-SHARE-SENTENCE", h6_sentence, "E42")
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
    tof = {t: meet("E42_meet_timeout", loss="0.25", to=t)[fm] for t in ("0.5", "2")}
    tof["1"] = base["0.25"]
    trades = tof["2"] < tof["1"] < tof["0.5"]           # fewer failures the longer the timeout
    # the commit step, paired by seed and year (with the step minus without it): failed meetings and the primary outcome
    def pair_metric(label, metric):
        d = r.p[(r.p["comparison"] == label) & (r.p["load"] == LOAD_MAIN) & (r.p["metric"] == metric)]
        d = d[d["valid"].astype(bool)]
        if len(d) != 1:
            raise KeyError(f"pairs row {label!r} on {metric}: {len(d)} rows; rerun analyse_e40.py")
        return d.iloc[0].to_dict()
    cm = {l: pair_metric(f"H6 commit step: with - without, team 25, loss {l}", "atc_failed_meetings") for l in noc}
    cw = {l: pair_metric(f"H6 commit step: with - without, team 25, loss {l}", M) for l in noc}
    fewer_with = all(cm[l]["hi"] < 0 for l in noc)
    cost = all(cw[l]["lo"] > 0 for l in noc)
    def noc_clause():
        if all(noc[l] == 0 for l in noc):
            return "it had none at either loss"
        return (f"it had {compare(noc['0.25'], base['0.25'])} at loss 0.25 ({num(noc['0.25'], 1)}) and "
                f"{compare(noc['0.4'], base['0.4'])} at 0.40 ({num(noc['0.4'], 1)})")
    # Referee M12(b)-(d): what in the meeting results follows from the handshake model of lunarsim/atc/auction.py
    # (_team_hook: no message is sent twice; _failed_meeting: each failure waits exactly the timeout; the arbitrated
    # variant retries timeout / RETRY_H times per vehicle).
    from lunarsim.atc import auction as AUC
    arb_tries = max(1, int(AUC.TIMEOUT_H / AUC.RETRY_H))
    prod = {"0.5": tof["0.5"] * 0.5, "1": tof["1"] * 1.0, "2": tof["2"] * 2.0}
    wait_is_product = all(abs(prod[t] - w) <= 0.02 * max(w, 1e-9) for t, w in (("0.5", to["0.5"]), ("1", to1), ("2", to["2"])))
    check(wait_is_product, "meeting wait equals failed meetings times the timeout in the three timeout cells")
    V["P1-H6-MEETINGS-SENTENCE"] = (
        f"Failed meetings {'rose' if rises else 'did not rise steadily'} with message loss: at team share 0.25 the "
        f"auction with the commit step and a 1&nbsp;h timeout had on average {num(base['0.1'], 1)} failed meetings "
        f"per year at loss 0.10, {num(base['0.25'], 1)} at 0.25 and {num(base['0.4'], 1)} at 0.40. Without the "
        f"commit step {noc_clause()}: paired by seed, the step "
        + ("cut" if fewer_with else "did not cut") + " failed meetings by "
        + listing(f"{num(-cm[l]['mean'], 1)} ({num(-cm[l]['hi'], 1)} to {num(-cm[l]['lo'], 1)}) at loss "
                  f"{'0.40' if l == '0.4' else l}" for l in noc) +
        ". That is the direction the second part of H6 names, but it is a property of the model and not an "
        "independent measurement. No message is repeated inside a handshake. With the commit step a meeting fails "
        "only when the proposal and the answer arrive and the commit is lost; without it a meeting fails whenever "
        "the single proposal is lost. If a message gets through with probability <i>s</i>, the two cases have "
        "probability <i>s</i><sup>2</sup>(1&nbsp;&minus;&nbsp;<i>s</i>) and 1&nbsp;&minus;&nbsp;<i>s</i>, and the "
        "second is the larger for every <i>s</i> below one. We therefore report the second part of H6 as following "
        "from the message count and not as supported by a test. What the runs do measure is the step's price: the "
        "urgent wait with it was "
        + listing(f"{h_(cw[l]['mean'], 1)} ({ci_h(cw[l]['lo'], cw[l]['hi'])}) "
                  f"{'longer' if cw[l]['mean'] > 0 else 'shorter'} at loss {'0.40' if l == '0.4' else l}" for l in noc)
        + (", a cost that excludes zero at both losses" if cost else "") +
        f", because a meeting that the step refuses is a lift that waits. The timeout sets the waiting and cannot "
        f"buy fewer failures in this model, where a partner that missed the commit never comes: the hours robots "
        f"spent waiting at meeting points are the failed meetings times the timeout, {num(to['0.5'], 1)} with a "
        f"0.5&nbsp;h timeout, {num(to1, 1)} with 1&nbsp;h and {num(to['2'], 1)} with 2&nbsp;h at loss 0.25. The "
        f"exploratory variant in which the base computer arbitrates each "
        + ("meeting had no failed meetings at either loss" if all(v == 0 for v in arb.values()) else
           f"meeting had {num(arb['0.25'], 1)} and {num(arb['0.4'], 1)} failed meetings at loss 0.25 and 0.40")
        + f". It repeats its message to each vehicle up to {arb_tries} times within the timeout, where the commit "
          f"variant repeats nothing, so that comparison is one of retry budgets and not of protocols.")
    check(to["0.5"] < to1 < to["2"], "meeting wait grows with the timeout")
    # one clause for the abstract, 6.1 and the conclusion: the team-share-0.10 lift in team items and the commit step's
    # effect, with the same rule as the meetings sentence (supported if failures without the step exceed 1.1x)
    t10 = r.pair("H6_team_items", LOAD_MAIN, team="10", loss="0.1")
    check(not trades, "a longer timeout does not buy fewer failed meetings")
    # Referee M12(a): the same-owner share is an input (the mass range against the one same-owner pair), so the
    # clauses name it as such and report what cross-owner pairs delivered.
    V["P1-H6-ABSTRACT-CLAUSE"] = (
        f"of the crates that need two rovers, {sh(t10['b_mean'])} are within the one same-owner pair's capacity by "
        f"construction, and pairs of different owners' robots delivered {sh(t10['b_mean'] + t10['mean'])}; a commit "
        f"step before each meeting "
        + ("cost urgent wait" if cost else "had no measurable cost in urgent wait")
        + ", and its lower count of failed meetings follows from the handshake's message count")

    check(t10["lo"] > 0, "cross-owner pairs raise the share of team items delivered (abstract clause)")
    V["P1-H6-SHORT-CLAUSE"] = (f"Of crates that need two rovers, {sh(t10['b_mean'])} fit the one same-owner pair "
                               f"by construction; cross-owner pairs delivered {sh(t10['b_mean'] + t10['mean'])}")

    # --- tables and the figure ---------------------------------------------------------------------------
    V["P1-TABLE-REGIMES"] = table_regimes(r)
    V["P1-TABLE-OOD"] = table_ood(r)
    V["P1-FIG-H2-YEARS"] = fig_h2_years(r, yrs, vis, margin)
    V["P1-REFERENCES"] = references()
    T = {"pairs": table_pairs(r, holm), "e42": table_e42(r)}
    # --- Phase 6: the protocol, E53, E54, the propositions and the proved / tested / assumed table -----------
    p6, st6 = phase6_values(r, V, fill, check)
    e53 = phase6_e53(p6, st6, V, check)
    phase6_e54(p6, V, fill, check)
    phase6_props(p6, st6, r, V, fill, check)
    phase6_proved(p6, r, V, fill, check, {"equiv": equiv, "fewer_with": fewer_with}, e53)
    # Referee M10 and decision B3: a design calculation, the packet before link framing and coding, and the limit
    # P3's abstract states (a scheduled channel, one hop)
    V["P1-LRIP-ABSTRACT-SENTENCE"] = (
        f"The robots' {V['P1-LRIP-N-MSG']} message types are written down and their encoding implemented: an "
        f"authenticated position report is a {V['P1-PROP6-SECURED-B']} packet before link framing and coding; by "
        f"calculation 20 rovers reporting once a second offer {kbps(e53['v1'], 1)}, which "
        + (f"fits a {kbps(e53['nb'], 0)} channel only if the base schedules it and reports travel one hop"
           if e53["sched_only"] else
           f"{'fits' if e53['v1'] <= e53['nb'] else 'does not fit'} a {kbps(e53['nb'], 0)} channel"))
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
    rows, notes = [], {}
    M = "atc_urgent_wait_mean_cens_h"
    if f"{M}_v1" not in r.r.columns:
        raise KeyError("table_E40_regimes.csv has no *_v1 columns; rerun experiments/phase5/analyse_e40.py")
    for load in (LOAD_LIGHT, LOAD_MAIN, LOAD_HEAVY):
        d = r.r[r.r["load"] == load].copy()
        if len(d) == 0:
            continue
        # an Earth-independent cell shows its block-one mean (seeds 1-30), the same runs its "Runs" counts;
        # the 80-run mean would count seeds 1-10 six times. Sorted on the value shown.
        d["_shown"] = np.where(d["earth_independent"].astype(bool), d[f"{M}_v1"], d[M])
        d = d.sort_values("_shown", ascending=False)
        first = True
        full = r.full("E40")
        for _, c in d.iterrows():
            indep = bool(c["earth_independent"])
            lab = html.escape(c["label"]) + ("&dagger;" if indep else "")
            n = f"{int(c['n_v1'])}" if indep else f"{int(c['n'])}"
            if not indep:                     # referee M11 and row 65: distinct runs, and runs with an urgent item
                nd = r.distinct40[(c["label"], int(load))][1]
                g = full[(full["label"] == c["label"]) & (full["load"] == load)]
                nv = int(g[M].notna().sum())
                if nd != int(c["n"]):
                    n += f" ({nd} distinct)&Dagger;"
                    notes["distinct"] = True
                if nv != int(c["n"]):
                    n += f" ({nv} with an urgent item)&sect;"
                    notes["empty"] = True
            v = (lambda k: c[f"{k}_v1"]) if indep else (lambda k: c[k])
            rows.append([f"{load}" if first else "", lab, n, num(v(M), 1),
                         num(v("atc_urgent_wait_p95_cens_h"), 0), sh(v("atc_urgent_within24_share")),
                         num(v("delivered_kg") / 1000, 0), num(v("backlog_kg") / 1000, 0),
                         sh(v("utilisation"), 1)])
            first = False
    return _tab("<b>Table 5.</b> Each decision regime at each load: mean urgent wait (h, censored at the horizon), "
                "its 95th percentile, the share of urgent items delivered within a day, tonnes delivered and left in "
                "the backlog at the end of the year, and whole-fleet utilisation. Cell means over the runs listed.",
                ["Load (%)", "Regime", "Runs", "Urgent wait (h)", "p95 (h)", "Within 24 h", "Delivered (t)",
                 "Backlog (t)", "Fleet busy"], rows, cls="wide",
                note="&dagger; Earth-independent regime: a seed gives the same run in every start year, so only the "
                     "30 runs of block one are counted and shown (change 4 of the pre-registration [43])."
                     + (" &Dagger; Some rows of this cell repeat another row exactly (the same seed and outcomes in "
                        "another start year); the means are over all rows, and the cell is in no tested comparison."
                        if notes.get("distinct") else "")
                     + (" &sect; One run had no urgent item, so the urgent-wait columns are means over the other runs."
                        if notes.get("empty") else ""))


def table_ood(r: R):
    rows = []
    le = r.dev["learned_eval"]
    origin = ("from the evaluation of the learned bids on the engine with the dispatch fixed point (change 5; Section 4.6)" if r.ood_rerun else
              f"from the evaluation of the learned bids of {le['file_date']}, made before the main runs and on the "
              f"engine before the two fixes of changes 4 and 5 (Section 4.6); unlike the rest of that evaluation, "
              f"these six cells were not rerun on the corrected engine")
    for cell, v in r.ood_src.items():
        d = v["linear"]["vs_hand_h"]
        rows.append([html.escape(cell), num(v["hand"]["urgent_mean_h"], 1), num(v["linear"]["urgent_mean_h"], 1),
                     f"{num(d['mean'], 2, sign=True)} [{num(d['ci95'][0], 2)}, {num(d['ci95'][1], 2)}]", f"{d['n']}"])
    return _tab(f"<b>Table 6.</b> The linear bids outside their training range, {origin}: mean urgent wait (h) with "
                "hand-built and learned bids, and the paired "
                "difference with its 95&#8239;% interval, on ten evaluation seeds the model never saw. 2eq and 5eq "
                "split the same eight vehicles and the demand equally among two and five owners. The last row, a "
                "later start year, repeats the guard runs at the middle load and is not an out-of-range test "
                "(Section 5.6). Where E41 reran a cell on 30 seeds (loss 0.25 and 0.40, "
                "Section 5.5) and E40 on 30 seeds (load 10&#8239;%, Section 5.6), those values supersede these.",
                ["Cell", "Hand-built (h)", "Learned (h)", "Difference (h)", "n"], rows)


def table_pairs(r: R, holm):
    """Table 7: the confirmatory family at the middle load with raw and Holm-adjusted p."""
    fam = [("H1", r.pair("H1", LOAD_MAIN), LABELS["holm_H1"], -1),
           ("H2", r.pair("H2_pooled", LOAD_MAIN), LABELS["holm_H2"], +1),
           ("H4, linear", r.pair("H4_LIN", LOAD_MAIN), LABELS["holm_H4_LIN"], -1),
           ("H4, network", r.pair("H4_MLP", LOAD_MAIN), LABELS["holm_H4_MLP"], -1),
           ("H6", r.fit("hypotheses", "H6", "test"), LABELS["holm_H6"], +1)]
    rows = []
    # referee S16(c, d): the block in words, and the comparison without the hypothesis label the first column gives
    BLOCK_WORDS = {"v1": "one (30 seeds)", "all": "one and two (80 runs)"}
    comp_words = lambda c: html.escape(re.sub(r"^H\d+[a-z]?( \([a-z ]+\))?: ", "", str(c)))
    for name, row, hk, sign in fam:
        adj = holm[hk]
        ok = adj < 0.05 and np.sign(row["mean"]) == sign
        unit = "" if row["metric"] == "delivered_share" else NB + "h"
        val = (f"{num(100 * row['mean'], 1, sign=True)} pp [{num(100 * row['lo'], 1)}, {num(100 * row['hi'], 1)}]"
               if not unit else f"{num(row['mean'], 1, sign=True)}{unit} [{num(row['lo'], 1)}, {num(row['hi'], 1)}]")
        blk = "v1" if name == "H6" else row["block"]      # E42 has block one only
        outcome = "supported" if ok else ("wrong direction" if adj < 0.05 else "not supported")
        if name == "H4, linear":      # referee M4: PREREG change 3; the row entered the family after B-74's evaluation
            outcome += "; the secondary model, added to the family after its result on these seeds was seen"
        if name == "H4, network":
            outcome += "; the registered model"
        if name == "H6":              # referee M5: the metric is a share of mass, at a team share the registration does not name
            outcome += "; on the share of cargo mass, at team share 0.25"
        rows.append([name, comp_words(row["comparison"]), BLOCK_WORDS[blk], f"{int(row['n'])}", val,
                     pfmt(row["p"]), pfmt(adj), outcome])
    # the registered 60 % halves of H1 and H4: raw p only, outside the Holm family
    for name, row in (("H1, 60&#8239;%", r.pair("H1", LOAD_HEAVY)), ("H4, linear, 60&#8239;%", r.pair("H4_LIN", LOAD_HEAVY)),
                      ("H4, network, 60&#8239;%", r.pair("H4_MLP", LOAD_HEAVY))):
        val = f"{num(row['mean'], 1, sign=True)}{NB}h [{num(row['lo'], 1)}, {num(row['hi'], 1)}]"
        rows.append([name, comp_words(row["comparison"]), BLOCK_WORDS[row["block"]], f"{int(row['n'])}", val, pfmt(row["p"]),
                     "&ndash;", "supported" if row["hi"] < 0 else "not supported"])
    return _tab("<b>Table 7.</b> The confirmatory family at the middle load: paired mean difference with its "
                "95&#8239;% bootstrap interval (hours of mean urgent wait; percentage points, pp, of cargo mass "
                "delivered for H6), the two-sided bootstrap p and Holm's adjusted p. The family differs from the "
                "registered one in two ways (Section 4.6): H3a, an equivalence claim, is tested outside it in "
                "Section 5.4, and H4 has two rows. Regime codes are those of Table 3; a comparison is the first "
                "regime minus the second. The last three rows are the registered 60&#8239;% "
                "halves of H1 and H4, outside the Holm family, with the raw p only.",
                ["Hypothesis", "Comparison", "Block", "n", "Difference [95&#8239;% CI]", "p", "Holm p", "Outcome"],
                rows, cls="wide")


def table_e42(r: R):
    cells = r.fit("E42", "cells")
    rows = []

    def cell_words(label):
        """Referee S16(d): an E42 cell in words instead of its internal label."""
        m = re.match(r"^(C_AUCTION|A_EARTH strict own teams) team (\d+)(?: (any|same_owner) loss ([\d.]+))?(.*)$", label)
        if not m:
            raise KeyError(f"E42 cell label {label!r} has an unexpected form")
        who = "Auction" if m.group(1) == "C_AUCTION" else "Owners alone from Earth, strict"
        out = [who, f"team share {int(m.group(2)) / 100:.2f}"]
        if m.group(3):
            out += ["pairs of any owners" if m.group(3) == "any" else "same-owner pairs only", f"loss {float(m.group(4)):.2f}"]
        extra = m.group(5).strip()
        ex = {"": None, "no commit": "no commit step", "timeout 0.5": "timeout 0.5&nbsp;h", "timeout 2": "timeout 2&nbsp;h",
              "arbitrated (exploratory)": "meetings arbitrated by the base (exploratory)"}
        if extra not in ex:
            raise KeyError(f"E42 cell label {label!r}: unknown variant {extra!r}")
        if ex[extra]:
            out.append(ex[extra])
        return ", ".join(out)
    for label, c in cells.items():
        rows.append([cell_words(label), f"{c['n']}", num(c["atc_urgent_wait_mean_cens_h"], 1),
                     num(c["delivered_kg"] / 1000, 0),
                     f"{num(c['p5_team_items_delivered'], 1)} of {num(c['p5_team_items'], 1)}",
                     num(c["atc_failed_meetings"], 1), num(c["atc_team_no_agreement"], 1),
                     num(c["atc_meeting_wait_h"], 1)])
    return _tab("<b>Table 8.</b> Every E42 cell at the middle load: mean urgent wait (h), tonnes delivered, team "
                "items delivered out of those offered, failed meetings, meetings with no agreement and the hours "
                "robots waited at meeting points, all per simulated year. Unless a row says otherwise the meeting "
                "uses the commit step and a 1&nbsp;h timeout. The hours waited are the failed meetings times the "
                "timeout, by the model.",
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
        txt = re.sub(r"\s*\((MOA|VCI|PWG|R1|added by LEAD|N03|N04)[^)]*\)\s*$", "", txt)       # the note's grade, not for print
        txt = re.sub(r"\*(.+?)\*", r"<i>\1</i>", txt)
        txt = re.sub(r"(https?://[^\s<]+)", lambda u: f'<a href="{u.group(1)}">{u.group(1)}</a>', txt)
        out.append(f'<li value="{m.group(1)}">{txt}</li>')
    if len(out) < 2:
        raise SystemExit("no references found in NOTES.md")
    return "\n".join(out + ["</ol>"])


# ---------------------------------------------------------------------------------------------------------
# Phase 6: the interaction protocol (LRIP v0.1; E53, H13), the lost link (E54, H14), the propositions of
# Appendix B and the "Proved, tested, assumed" table. Sources (read-only): lunarsim/schemas/lrip-v0.1.json,
# lunarsim/atc/lrip (codec, manifest), data/atc/lrip (two manifests, the conformance vectors),
# results/E53_bitrate.json + E53_table.csv, results/E54_dtn.json, results/ATC_auction_bounds.json and
# paper/p1/dev_notes.json (the inputs of Propositions 4 and 5 and the capability-filter check, each with its source).
# ---------------------------------------------------------------------------------------------------------
def kbps(x, nd=2):
    return f"{num(x, nd)}{NB}kbit/s"


def nbytes(n):
    return f"{int(n):,}{NB}B"


def secs(x, nd=0):
    return f"{num(x, nd)}{NB}s"


class P6:
    def __init__(self):
        jl = lambda *p: json.load(open(os.path.join(ROOT, *p), encoding="utf-8"))
        # Second pass, part 2 (12 Nov; task B-100): the paper describes LRIP v0.2. E53's v0.2 rerun is the key
        # "lrip_v02" of E53_bitrate.json and E53_table_v02.csv; the v0.1 values stay under e53_v01 / t53_v01 for the
        # things computed with them (the design note's figures, the family file, the driving split of B-103).
        self.e53_v01 = jl("results", "E53_bitrate.json")
        self.t53_v01 = pd.read_csv(os.path.join(RES, "E53_table.csv"))
        v2 = self.e53_v01.get("lrip_v02")
        if v2 is None:
            raise SystemExit("results/E53_bitrate.json has no lrip_v02 (task B-100)")
        t2 = pd.read_csv(os.path.join(RES, "E53_table_v02.csv"))
        self.t53 = t2[t2["framing"] == "lrip"].drop(columns=["framing"]).reset_index(drop=True)
        self.v02 = v2
        h2, eta = v2["h13_check_v02"], self.e53_v01["eta"]
        self.e53 = dict(self.e53_v01)
        self.e53["sizes"] = v2["sizes_v0.2"]
        self.e53["per_rover_at_1hz"] = v2["per_rover_at_1hz"]
        self.e53["h13"] = {"at_1hz_kbps_p95": h2["at_1hz_kbps_p95"], "at_10hz_kbps_p95": h2["at_10hz_kbps_p95"],
                           "supported": bool(self.e53_v01["h13"]["supported"]) and bool(h2["same_verdict_as_v0.1"]),
                           "airtime_1hz_scheduled_kbps": h2["airtime_1hz_scheduled_kbps"],
                           "airtime_1hz_slotted_aloha_kbps": h2["at_1hz_kbps_p95"] / eta["slotted_aloha"]}
        self.e53["manifest_bytes"] = {k: {"json": v["json"], "compact_cbor": v["compact_cbor"], "compact_cbor_v01": v["compact_cbor_v0.1"],
                                          "note03_compact": self.e53_v01["manifest_bytes"][k]["note03_compact"]}
                                      for k, v in v2["manifest_bytes_v0.2"].items()}
        p54 = os.path.join(RES, "E54_dtn.json")
        self.e54 = json.load(open(p54, encoding="utf-8")) if os.path.exists(p54) else None
        # the Earth-bound ledger over 61 days (the main E54 table's ledger columns are cut off by its 31-day window
        # and are never quoted)
        p54l = os.path.join(RES, "E54_ledger.json")
        self.e54l = json.load(open(p54l, encoding="utf-8")) if os.path.exists(p54l) else None
        # the Phase 6 confirmatory family with Holm's correction (tools/atc/phase6_family.py)
        pfam = os.path.join(RES, "phase6_family.json")
        self.fam = json.load(open(pfam, encoding="utf-8")) if os.path.exists(pfam) else None
        p48 = os.path.join(RES, "E48_sizing.json")
        self.e48 = json.load(open(p48, encoding="utf-8")) if os.path.exists(p48) else None
        self.schema = jl("lunarsim", "schemas", "lrip-v0.2.json")
        self.dev = jl("paper", "p1", "dev_notes.json")
        self.conf = jl("data", "atc", "lrip", "conformance-v0.2.json")
        self.e53["conformance_vectors"] = len(self.conf["vectors"])
        self.man = {k: jl("data", "atc", "lrip", "v0.2", f"manifest-{k}.json") for k in ("small_rover", "hopper")}
        from lunarsim.atc import lrip, messages, regimes
        from lunarsim.atc.lrip import codec, manifest
        self.lrip, self.codec, self.manifest, self.messages, self.regimes = lrip, codec, manifest, messages, regimes

    def row53(self, geometry, auth, hz, n):
        t = self.t53
        d = t[(t["geometry"] == geometry) & (t["auth"] == auth) & np.isclose(t["position_hz"], hz) & (t["rovers"] == n)]
        if len(d) != 1:
            raise KeyError(f"E53_table.csv row {geometry}/{auth}/{hz} Hz/{n} rovers: {len(d)} rows")
        return d.iloc[0].to_dict()

    def row54(self, loss, proto):
        if self.e54 is None:
            raise Pending("E54 (results/E54_dtn.json) has not run")
        d = [x for x in self.e54["rows"] if abs(x["loss"] - loss) < 1e-9 and x["protocol"] == proto]
        if len(d) != 1:
            raise KeyError(f"E54_dtn.json row loss {loss} / {proto}: {len(d)} rows")
        return d[0]

    def h14(self):
        if self.e54 is None:
            raise Pending("E54 (results/E54_dtn.json) has not run")
        return self.e54["h14"]

    def family(self):
        if self.fam is None:
            raise Pending("the Phase 6 family (results/phase6_family.json) has not been built")
        return self.fam

    def vectors_decoded(self):
        """How many golden packets our codec decodes to their recorded fields (the test of tests/test_lrip.py)."""
        c, keys = self.conf, self.conf["keys"]
        K = self.codec.Keys(mac_key=bytes.fromhex(keys["aes_cmac_key_hex"]),
                            verify_key=self.codec.ed25519_keys(bytes.fromhex(keys["ed25519_seed_hex"]))[1])
        ok = 0
        for x in c["vectors"]:
            pkt = bytes.fromhex(x["hex"])
            try:
                d = self.lrip.decode(pkt, auth="auto" if x["auth"] else None, keys=K, profile=x["profile"])
            except ValueError:
                continue
            good = d is not None and d.name == x["message"] and len(pkt) == x["bytes"]
            if good and "manifest_cbor_hex" not in x["fields"]:
                good = all(abs(float(x["fields"][k]) - float(d.fields[k])) < 1e-9 for k in x["fields"])
            ok += bool(good)
        return ok


def _field_range(f):
    """Plain-language step and range of a schema field [name, type, bits, scale, unit], and the number of distinct
    values the report needs it to tell apart (Proposition 6)."""
    name, typ, bits, scale, unit = f
    if typ == "int":
        half = (1 << (bits - 1)) * scale
        return f"&plusmn;{num(half / 1000, 1)}{NB}km in steps of {scale:g}{NB}m", 1 << bits
    if typ == "flag":
        return "yes or no", 2
    if typ.startswith("enum"):
        return None, None                                   # filled by the caller from the enumeration
    top = ((1 << bits) - 1) * scale
    return f"0 to {top:g} in steps of {scale:g}", 1 << bits


def _sig(x):
    """A load in kbit/s with three significant figures, for table cells."""
    return num(x, 2 if abs(x) < 10 else (1 if abs(x) < 100 else 0))


def phase6_values(r, V, fill, check):
    p = P6()
    S, fr, C, M = p.schema, p.schema["framing"], p.codec, p.manifest
    msgs = S["messages"]
    code = lambda names: listing(f"<code>{n}</code>" for n in names)

    # --- framing and sizes (3.12, Appendix A, Proposition 6) ----------------------------------------------
    spp, hdr, sec = (fr[k]["bytes"] for k in ("space_packet", "lrip_header", "security_header"))
    mac8, mac16, sig = fr["trailer"]["mac8"], fr["trailer"]["mac16"], fr["trailer"]["signature"]
    for k in ("space_packet", "lrip_header", "security_header"):
        check(sum(f[1] for f in fr[k]["fields"]) == 8 * fr[k]["bytes"], f"the {k} fields of the schema fill its bytes")
    man_b = {k: len(M.encode(m)) for k, m in p.man.items()}
    st = C.size_table(man_b["small_rover"])
    check(all(st[m["name"]] == p.e53["sizes"][m["name"]] for m in msgs), "E53 used the codec's packet sizes")
    check(all(st[m["name"]]["payload"] * 8 == sum(f[2] for f in m["fields"]) for m in msgs if m["fields"]),
          "every message's fields fill whole bytes exactly")
    check(all(st[m["name"]]["mac8"] == st[m["name"]]["payload"] + spp + hdr + sec + mac8 for m in msgs),
          "a secured packet is the content plus the three headers and the code")
    V["P1-LRIP-N-MSG"] = f"{len(msgs)}"
    V["P1-LRIP-SPP-B"], V["P1-LRIP-HDR-B"], V["P1-LRIP-SEC-B"] = nbytes(spp), nbytes(hdr), nbytes(sec)
    V["P1-LRIP-MAC-B"], V["P1-LRIP-MAC16-B"], V["P1-LRIP-SIG-B"] = nbytes(mac8), nbytes(mac16), nbytes(sig)
    V["P1-LRIP-OVERHEAD-B"] = nbytes(spp + hdr + sec + mac8)
    V["P1-LRIP-OVERHEAD-SIG-B"] = nbytes(spp + hdr + sec + sig)
    V["P1-LRIP-HOP-LIMIT"] = "5"                                # design note 03, C1; not a schema constant (typed input)
    V["P1-LRIP-BUNDLE-B"] = nbytes(fr["bundle_overhead_bytes"])
    en = S["enums"]
    check(len(S["versioning"]) == 5 and "since" in S["versioning"][4], "the schema states five versioning rules, the fifth on fields added since a minor version")
    check(en["alert_type"][str(en["alert_type"]["unknown_as"])] == "hazard" and en["mode"][str(en["mode"]["unknown_as"])] == "fault",
          "an unknown alert type reads as a hazard and an unknown mode as a fault")

    pub = [m["name"] for m in msgs if m["pattern"].startswith("publish")]
    req = [m["name"] for m in msgs if m["pattern"].startswith("request")]
    rsp = [m["name"] for m in msgs if m["pattern"].startswith("response")]
    signed = [m["name"] for m in msgs if m.get("signed")]
    check(len(pub) + len(req) + len(rsp) == len(msgs), "every message is published, a request or a response")
    check(sorted(signed) == sorted(rsp), "the signed messages are exactly the responses")
    check(set(signed) == {"TASK_AWARD", "RESERVE_GRANT", "CAP_MANIFEST"},
          "the signed messages are the award, the grant and the manifest")
    alert = next(m for m in msgs if m["name"] == "ALERT")
    check("all_stop" in alert.get("signed_when", "") and "landing_closure" in alert.get("signed_when", ""),
          "an all-stop or landing-closure ALERT from the base is signed")
    V["P1-LRIP-PATTERN-SENTENCE"] = (
        f"Of the {len(msgs)} messages, {words(len(pub))} are published ({code(pub)}), {words(len(req))} are "
        f"requests ({code(req)}) and {words(len(rsp))} are the responses to them ({code(rsp)}).")
    V["P1-LRIP-ALERT-SIGNED-B"] = nbytes(st["ALERT"]["signed"])
    V["P1-LRIP-AWARD-B"], V["P1-LRIP-GRANT-B"] = nbytes(st["TASK_AWARD"]["default"]), nbytes(st["RESERVE_GRANT"]["default"])

    # Decision B3 (referee M10, P3 M4) and task B-100: what the position report of v0.2 carries, where the frame,
    # datum and time scale are declared, and what is still not carried. Everything is read from the schema, the
    # codec and the v0.2 block of E53_bitrate.json.
    posm = next(m for m in msgs if m["name"] == "POSITION")
    helm = next(m for m in msgs if m["name"] == "HELLO")
    pnames = [f[0] for f in posm["fields"]]
    hnames = [f[0] for f in helm["fields"]]
    check(pnames == ["e", "n", "h", "heading", "speed", "sigma_h", "nav_src", "moving", "u95_code"],
          "v0.2's POSITION holds east, north, height, heading, speed, a one-sigma value, the source, a moving flag and the 95 % code")
    u95 = posm["fields"][-1]
    check(u95[2] == 6 and u95[5].get("was") == "spare" and u95[5].get("since") == 2, "the 95 % code takes the six bits that were spare in v0.1")
    check(not any(k in n.lower() for n in pnames for k in ("frame", "datum", "scale", "cov")),
          "the position report itself carries no frame, datum, time-scale or covariance field")
    check(hnames[-3:] == ["frame_id", "datum_id", "time_scale"] and all(f[5].get("since") == 2 for f in helm["fields"][-3:]),
          "HELLO declares frame, datum and time scale since minor version 2")
    st1 = C.size_table(man_b["small_rover"], minor=1)
    moved = {k: (st1[k]["default"], st[k]["default"]) for k in st if k != "CAP_MANIFEST" and st1[k]["default"] != st[k]["default"]}
    check(list(moved) == ["HELLO"] and st["POSITION"] == st1["POSITION"], "from v0.1 to v0.2 only HELLO changes size; POSITION does not")
    check(all(st1[k]["default"] == p.e53_v01["sizes"][k]["default"] for k in st1 if k != "CAP_MANIFEST"),
          "the codec at minor version 1 gives the v0.1 sizes E53 first used (v0.1 stays bit-exact)")
    decl_s = helm["declaration_interval_s"]
    check(abs(p.v02["hello_min_hz"] * decl_s - 1.0) < 1e-9, "E53's v0.2 traffic sends HELLO at least once per declaration interval")
    check("refused" in S["declaration_rule"] and "key epoch" in S["declaration_rule"], "the schema states the declaration rule")
    dman = {k: (v["compact_cbor_v01"], v["compact_cbor"]) for k, v in p.e53["manifest_bytes"].items()}
    dm = {b - a for a, b in dman.values()}
    check(len(dm) == 1, "the declaration adds the same number of bytes to both example manifests")
    V["P1-LRIP-V02-SENTENCE"] = (
        f"This paper describes version 0.2. Its position report carries east, north and height in the site grid, "
        f"heading, speed, a one-sigma horizontal value, the navigation source, a moving flag and, in the six bits "
        f"that version 0.1 left spare, a code for the 95{PCT} horizontal uncertainty on a logarithmic scale; it is "
        f"still {nbytes(st['POSITION']['payload'])} of content and a packet of {nbytes(st['POSITION']['mac8'])}. "
        f"The frame, the datum and the time scale of a vehicle's positions are not repeated in every report. The "
        f"vehicle declares them in its heartbeat, <code>HELLO</code>, which grows from {nbytes(moved['HELLO'][0])} to "
        f"{nbytes(moved['HELLO'][1])} and is sent at least every {secs(decl_s)}, and in its manifest, which grows "
        f"by {nbytes(dm.pop())}. A receiver refuses a position report from a sender that has no authenticated "
        f"declaration under its current key epoch. Packets of version 0.1 still encode and decode bit for bit. A "
        f"covariance is not carried: the report states its uncertainty as the one-sigma value and the "
        f"95{PCT} code only.")

    # Part 7 (13 Nov, review C1 to C9, commit 8d53587): what the receiver in the codec checks. Each clause of the
    # sentence is exercised here on packets the codec builds, so the sentence stays true of the code.
    def receiver_sentence():
        sk, pk = C.ed25519_keys(bytes(range(32)))
        K = C.Keys(mac_key=bytes(range(16)), sign_key=sk, verify_key=pk, epoch=3)
        K9 = C.Keys(mac_key=bytes(range(16)), sign_key=sk, verify_key=pk, epoch=9)
        enc = p.lrip.encode

        def refused(fn, exc):
            try:
                fn()
            except exc:
                return True
            return False
        rx = C.Receiver(K)
        signed = [m["name"] for m in msgs if m.get("signed")]
        check(refused(lambda: rx.accept(enc("STATUS", {}, 5, 1.0, auth=None, seq=1)), C.LripAuthError)
              and rx.refused_unauthenticated == 1, "the receiver refuses a packet without an authentication code")
        check(len(signed) > 0 and all(refused(lambda nm=nm, i=i: rx.accept(enc(nm, {}, 5, 1.0, keys=K, auth="mac8", seq=10 + i)), C.LripAuthError)
                                      for i, nm in enumerate(signed)) and rx.refused_unsigned == len(signed),
              "the receiver refuses, without a signature, every message the schema marks as signed")
        fresh = float(C.FRESHNESS_S)
        stt = lambda seq, t: enc("STATUS", {}, 4, t, keys=K, seq=seq)
        ok1 = rx.accept(stt(5, 100.0), now=100.0) is not None
        check(ok1 and refused(lambda: rx.accept(stt(5, 100.0), now=100.5), C.LripReplayError)
              and refused(lambda: rx.accept(stt(4, 100.0), now=100.5), C.LripReplayError) and rx.refused_replay == 2,
              "the receiver refuses a counter that is not above the highest it has accepted from that sender")
        check(refused(lambda: rx.accept(stt(6, 100.0), now=100.0 + fresh + 1.0), C.LripReplayError) and rx.refused_stale == 1
              and rx.accept(stt(6, 100.0), now=100.0 + fresh - 1.0) is not None and rx.accept(stt(7, 100.0)) is not None,
              "the receiver refuses a validity time outside the freshness window when it is given a clock, and only then")
        check(refused(lambda: rx.accept(enc("STATUS", {}, 4, 1.0, keys=K9, seq=1)), C.LripAuthError) and rx.refused_epoch == 1,
              "the receiver refuses a packet under another key epoch")
        decl = {"link_margin": 10, "neighbours": 3, "bundles_queued": 0, "frame_id": 1, "datum_id": 1, "time_scale": 6}
        pos = {"e": 12.34, "n": -5.67, "h": 1.0, "heading": 90.0, "speed": 1.2, "sigma_h": 1.0, "nav_src": 3, "moving": True}
        rh = C.Receiver(K)
        rh.accept(enc("HELLO", dict(decl, frame_id=2), 7, 5.0, keys=K, seq=1))
        rh.accept(enc("HELLO", dict(decl, frame_id=1), 7, 4.0, keys=K, seq=2))
        kept = rh.decl[7].frame_id == 2
        rh.accept(enc("HELLO", dict(decl, frame_id=0), 7, 7.0, keys=K, seq=3))
        check(kept and 7 not in rh.decl and rh.revoked_declarations == 1
              and refused(lambda: rh.accept(enc("POSITION", pos, 7, 7.5, keys=K, seq=4)), C.LripRefError),
              "an older heartbeat does not replace a newer declaration, and one with invalid codes revokes it")
        good = enc("POSITION", pos, 7, 1.0, keys=K)
        bad = [b"", b"\x00", good[:5], good[:13], good[:-1], good + b"\x00", "not bytes"]

        def value_error_only(c):
            try:
                p.lrip.decode(c, keys=K)
            except ValueError:
                return True
            except Exception:
                return False
            return False
        check(all(value_error_only(c) for c in bad), "short or malformed input is refused with one error type")
        return (
            f"In our implementation the decoder applies these checks on receipt. It refuses a packet that carries no "
            f"authentication code, a message that the schema marks as signed and that carries no signature "
            f"({code(signed)}), a counter that is not above the highest it has accepted from that sender, "
            f"a validity time more than {secs(fresh)} from its own clock when it is given one, and a key epoch other "
            f"than its own; an older heartbeat does not replace a newer declaration, one with invalid codes revokes "
            f"it, and short or malformed input is refused with one kind of error. These checks were added after a "
            f"code review on 13 November 2026, and no packet size or test packet changed with them; before, the "
            f"decoder verified a code or signature where one was present and applied the declaration rule to "
            f"position reports, and the counter and freshness rule "
            f"had been applied only in the simulation model of the companion paper [45]. They are exercised on "
            f"packets that the codec itself builds, each time this paper is built; the codec has not been run over "
            f"a radio link.")
    V["P1-LRIP-RECEIVER-SENTENCE"] = receiver_sentence()

    rows = []
    for m in msgs:
        nm, d = m["name"], st[m["name"]]
        bits = sum(f[2] for f in m["fields"]) if m["fields"] else None
        rate_words = m["default_rate"].replace(" (it carries the declaration)", "")
        rows.append([f"{m['id']}", f"<code>{nm}</code>", html.escape(m["pattern"]), html.escape(rate_words),
                     f"{bits}" if bits else "variable", f"{d['payload']}",
                     f"{d['default']}" + (" (signed)" if m.get("signed") else ""), html.escape(m["carried_by"])])
    V["P1-TABLE-LRIP-MSG"] = _tab(
        f"<b>Table A2.</b> The {len(msgs)} messages of LRIP v0.2, read from the schema file: how each is sent, its "
        f"default rate, its content in bits and bytes, and its size as a packet in the narrow-band profile, before "
        f"link framing and channel coding: the content plus {nbytes(spp + hdr + sec + mac8)} of headers and "
        f"authentication code, or plus {nbytes(spp + hdr + sec + sig)} where a signature replaces the code. Inside a "
        f"Proximity-1 frame each packet gains {nbytes(fr['proximity1_frame_bytes'])}. <code>CAP_MANIFEST</code> is "
        f"the small-rover example of Section 3.12. In the last column a bundle is a Bundle Protocol bundle [60] and "
        f"CFDP is the file delivery protocol of the same family of space standards; in the design a bid is encrypted "
        f"inside its bundle until the auction closes, which the codec does not implement.",
        ["ID", "Message", "Pattern", "Default rate", "Content (bits)", "Content (B)",
         "Packet (B), before link framing and coding", "Carried by"],
        rows, cls="wide",
        note=f"An <code>ALERT</code> that is an all-stop or a landing closure from the base is signed and is then "
             f"{nbytes(st['ALERT']['signed'])}.")

    # --- the capability manifest ---------------------------------------------------------------------------
    sm, hp = p.man["small_rover"], p.man["hopper"]
    js = lambda o: html.escape(json.dumps(o), quote=False)
    caps = [f"  {js(c)}" for c in sm["capabilities"]]
    V["P1-LRIP-MANIFEST-EXAMPLE"] = (
        '<pre class="listing">{' + f'"lrip": {js(sm["lrip"])}, "rev": {js(sm["rev"])},\n'
        f' "vehicle": {js(sm["vehicle"])},\n'
        f' "physical": {{<i>{len(sm["physical"])} size and motion limits</i>}}, "energy": {{<i>{len(sm["energy"])} '
        f'values</i>}}, "comms": [<i>{len(sm["comms"])} radios</i>], "nav": {{<i>sources and accuracy</i>}},\n'
        f' "messages": {js(sm["messages"])},\n "capabilities": [\n' + ",\n".join(caps) + "],\n"
        f' "lost_link": {js(sm["lost_link"])}' + "}</pre>")
    json_b = {k: len(M.minified_json(m)) for k, m in p.man.items()}
    mb = p.e53["manifest_bytes"]
    check(all(json_b[k] == mb[k]["json"] and man_b[k] == mb[k]["compact_cbor"] for k in man_b),
          "the manifest sizes recomputed here equal those in E53_bitrate.json")
    alt = {}
    for k, m in p.man.items():                               # the same encoder with owner and model as registry numbers
        m2 = json.loads(json.dumps(m))
        m2["vehicle"]["owner"], m2["vehicle"]["model"] = 1, 2
        alt[k] = len(M.encode(m2))
    check(all(mb[k]["note03_compact"] < alt[k] < man_b[k] for k in man_b),
          "text names for owner and model explain part of the difference from the design note's estimate")
    V["P1-LRIP-MANIFEST-CBOR-SMALL"], V["P1-LRIP-MANIFEST-CBOR-HOPPER"] = nbytes(man_b["small_rover"]), nbytes(man_b["hopper"])
    V["P1-LRIP-MANIFEST-SIZE-SENTENCE"] = (
        f"As minified JSON the two example manifests are {json_b['small_rover']:,} and {nbytes(json_b['hopper'])}; "
        f"in the compact form they are {nbytes(man_b['small_rover'])} (small rover) and {nbytes(man_b['hopper'])} "
        f"(hopper), and the small rover's is a signed packet of {nbytes(st['CAP_MANIFEST']['default'])}. The design "
        f"note had estimated {mb['small_rover']['note03_compact']} and {nbytes(mb['hopper']['note03_compact'])}. The "
        f"measured sizes are larger mainly because the implementation keeps the owner and model names as text, so "
        f"that a manifest from an owner the reader has never met still decodes: with the two names replaced by "
        f"registry numbers the same encoder gives {alt['small_rover']} and {nbytes(alt['hopper'])}.")
    cap = next(c for c in sm["capabilities"] if c["name"] == "transport.carry")
    cmax, iface = cap["params"]["mass_kg"]["max"], cap["params"]["interface"][0]
    task = lambda name, ver, **prm: {"capability": name, "ver": ver, "params": prm}
    lo, hi = 0.75 * cmax, 1.25 * cmax
    yes = M.can_do(task("transport.carry", cap["ver"], mass_kg=lo), sm)
    no = [M.can_do(task("transport.carry", cap["ver"], mass_kg=hi), sm),
          M.can_do(task("transport.carry", "1.1", mass_kg=lo), sm),
          M.can_do(task("transport.carry", "2.0", mass_kg=lo), sm),
          M.can_do(task("transport.carry", cap["ver"], mass_kg=lo, interface=["tray-B"]), sm),
          M.can_do(task("transport.carry", cap["ver"], mass_kg=lo), hp),
          M.can_do(task("transport.carry", cap["ver"], mass_kg=lo), None)]
    hop = next(c for c in hp["capabilities"] if c["name"] == "transport.hop")
    hop_ok = M.can_do(task("transport.hop", hop["ver"], mass_kg=0.5 * hop["params"]["mass_kg"]["max"]), hp)
    check(cap["ver"] == "1.0" and iface != "tray-B", "the example's carrying capability is version 1.0 with one interface")
    check(yes and hop_ok and not any(no), "the matching rule accepts and refuses the example tasks as the text says")
    V["P1-LRIP-CANDO-SENTENCE"] = (
        f"For the small rover above (<code>transport.carry</code> version {cap['ver']}, at most {num(cmax)}{NB}kg, "
        f"interface {html.escape(iface)}), the rule accepts a carrying task of {num(lo)}{NB}kg and refuses one of "
        f"{num(hi)}{NB}kg, one that asks for version 1.1 or 2.0, and one that needs an interface the manifest does "
        f"not list. The hopper's manifest lists <code>transport.hop</code> and no <code>transport.carry</code>: it "
        f"is refused for every carrying task and accepted for a hop with {num(0.5 * hop['params']['mass_kg']['max'])}"
        f"{NB}kg. A vehicle with no manifest is refused.")

    # --- conformance vectors and the auction's filter ------------------------------------------------------
    vec = p.conf["vectors"]
    cnt_v = lambda prof, auth: sum(1 for x in vec if x["profile"] == prof and (x["auth"] in auth))
    nN_mac, nN_sig, nN_un = cnt_v("N", ("mac8",)), cnt_v("N", ("sig",)), cnt_v("N", (None,))
    nB = cnt_v("B", ("mac8", "sig", None))
    check(nN_mac + nN_sig == len(msgs) and nN_un == len(msgs) and nB == len(msgs) and len(vec) == 3 * len(msgs),
          "the conformance file holds every message three times")
    check(len(vec) == p.e53["conformance_vectors"], "E53_bitrate.json counts the same conformance vectors")
    n_ok = p.vectors_decoded()
    check(n_ok == len(vec), f"our codec decodes every conformance vector ({n_ok} of {len(vec)})")
    V["P1-LRIP-N-VECTORS"] = f"{len(vec)}"
    V["P1-LRIP-VECTORS-SENTENCE"] = (
        f"The release holds {len(vec)} golden packets: every message in the narrow-band profile with authentication "
        f"({nN_mac} with the {nbytes(mac8)} code, {nN_sig} signed), the same {nN_un} without security, and "
        f"{nB} in the broadband profile, each as hexadecimal bytes with the field values it must decode to, and the "
        f"two example manifests in compact form. The keys in the file are test keys."
        + ("" if any(x["profile"] == "B" and x["auth"] == "mac16" for x in vec) else
           f" The broadband vectors carry the {nbytes(mac8)} code; the {nbytes(mac16)} code that Table A1 gives for "
           f"broadband has no vector yet."))
    cf = r.dev["capability_filter_check"]
    check(cf["identical"] == cf["summary_values"] and cf["runs"] == 1, "the capability filter changed no summary value")
    # Referee S13(f): the companion papers quote another check (every Phase 6 option off equals the Phase 5 run)
    # Part 7 (13 Nov, review N2): the row is now a comparison with a stored run of the code before Phase 6, and a
    # second row shows that the comparison can fail. Both are read with `passed`; a missing row stops the build.
    pv6 = os.path.join(RES, "vv_phase6.json")
    if not os.path.exists(pv6):
        raise Pending("results/vv_phase6.json has not been built")
    vv6 = json.load(open(pv6, encoding="utf-8"))
    g1r = {x.get("sub"): x for x in vv6.get("rows", []) if x.get("id") == "G1"}
    if "options off" not in g1r or "option on changes the run" not in g1r:
        raise KeyError("vv_phase6.json has no G1 rows 'options off' and 'option on changes the run'")
    mg = re.search(r"(\d+) days, seed (\d+): (\d+) summary values against results/(\S+) \(commit (\w+)\)", str(g1r["options off"].get("basis", "")))
    mo = re.search(r"(\d+) of (\d+) summary values differ", str(g1r["option on changes the run"].get("basis", "")))
    if not mg or not mo:
        raise KeyError("vv_phase6.json: the G1 rows do not state their scope in the expected words")
    check(bool(g1r["options off"]["passed"]) and bool(g1r["option on changes the run"]["passed"]) and int(mo.group(2)) == int(mg.group(3))
          and int(mo.group(1)) > 0, "both G1 rows of vv_phase6.json pass, on the same summary values")
    check(os.path.exists(os.path.join(RES, mg.group(4))), "the stored reference run of the options-off check is in the results directory")
    g1_note = (f" This is not the check that the companion papers quote [44, 45], in which every engine option added for "
               f"the protocol is switched off and the run is compared with a stored run of the code as it was before "
               f"those options (commit <code>{mg.group(5)}</code>): none of {mg.group(3)} summary values differs, in "
               f"one scenario over {mg.group(1)} days on seed {mg.group(2)}, and with one option switched on "
               f"{mo.group(1)} of them differ, so the comparison can fail. That check was rebuilt after a code review "
               f"on 13 November 2026; before, it compared a run with itself.")
    V["P1-LRIP-CAPFILTER-SENTENCE"] = (
        f"With manifests generated from the vehicle classes, switching the filter on changed none of the "
        f"{cf['summary_values']} summary values of a {cf['days']}-day run of the auction (one run, seed {cf['seed']}, "
        f"message loss {cf['loss']:.2f}), because those manifests state exactly the capacity the engine already "
        f"checks; with no manifests at all, deliveries fell below {sh(cf['delivered_share_without_manifests_below'])} "
        f"of that run's." + g1_note)
    return p, st


def phase6_e53(p, st, V, check):
    """E53 (Sections 4.8 and 5.8, Tables 9 and 10) and the worked numbers of Proposition 2."""
    e = p.e53
    nb, bb = e["channels_kbps"]["narrow-band (Phase 5 target)"], e["channels_kbps"]["broadband"]
    eta_s, eta_a = e["eta"]["scheduled"], e["eta"]["slotted_aloha"]
    check(abs(eta_a - 1 / math.e) < 1e-9, "E53's random-access efficiency is 1/e")
    NS = sorted(int(x) for x in p.t53["rovers"].unique())
    HZ = sorted(float(x) for x in p.t53["position_hz"].unique())
    check(NS == [5, 10, 20, 40, 80] and HZ == [0.1, 1.0, 10.0], "E53 covers 5 to 80 rovers at 0.1, 1 and 10 Hz")
    V["P1-E53-DRAWS"] = f"{e['draws']}"
    V["P1-E53-NB-KBPS"], V["P1-E53-BB-KBPS"] = kbps(nb, 0), kbps(bb, 0)
    V["P1-E53-ETA-SCHED"], V["P1-E53-ETA-ALOHA"] = f"{eta_s:g}", f"{eta_a:.2f}"
    row = p.row53
    per = {(a, hz): row("fleet", a, hz, 20)["per_rover_kbps"] for a in ("on", "off") for hz in HZ}
    check(all(abs(row(g, a, hz, n)["per_rover_kbps"] - per[(a, hz)]) < 1e-9
              for g in ("fleet", "spread") for a in ("on", "off") for hz in HZ for n in NS),
          "the per-rover load does not depend on fleet size or geometry")
    pr = e["per_rover_at_1hz"]["on"]
    check(abs(sum(v["bps"] for v in pr.values()) / 1000 - per[("on", 1.0)]) < 1e-3,
          "the per-rover load at 1 Hz is the sum over message types")
    beacons = sum(pr[k]["rate_hz"] * st[k]["default"] for k in ("POSITION", "STATUS", "INTENT", "HELLO"))     # B/s
    check(abs(beacons * 8 / 1000 - per[("on", 1.0)]) < 1e-3, "position, status, intent and heartbeat make up the 1 Hz load")
    check(abs(pr["HELLO"]["rate_hz"] - p.v02["hello_min_hz"]) < 1e-9, "at 1 Hz the heartbeat is sent at its minimum rate, for the declaration")
    check(sum(v["bps"] for k, v in pr.items() if k not in ("POSITION", "STATUS", "INTENT", "HELLO")) < 1e-3 * 1000 * per[("on", 1.0)],
          "event messages add less than a thousandth to the per-rover load")
    check(pr["POSITION"]["rate_hz"] == 1.0 and pr["STATUS"]["rate_hz"] == 0.1 and pr["INTENT"]["rate_hz"] == 0.1,
          "status and intent are sent at 0.1 Hz")
    slow = (0.1 * (st["POSITION"]["default"] + st["STATUS"]["default"] + st["INTENT"]["default"])
            + 0.7 * st["HELLO"]["default"]) * 8 / 1000
    check(abs(slow - per[("on", 0.1)]) < 1e-3, "at 0.1 Hz the heartbeat fills up to one message a second")
    V["P1-E53-PER-ROVER-1HZ"] = kbps(per[("on", 1.0)], 3)
    V["P1-E53-PER-ROVER-1HZ-BPS"] = f"{num(per[('on', 1.0)] * 1000 / 8, 1)}{NB}B/s"
    V["P1-E53-PER-ROVER-01HZ"], V["P1-E53-PER-ROVER-10HZ"] = kbps(per[("on", 0.1)], 3), kbps(per[("on", 10.0)], 2)

    # H13 as pre-registered: 20 rovers, authentication on, the busiest link's p95 over the draws, fleet geometry
    h = e["h13"]
    r1, r10 = row("fleet", "on", 1.0, 20), row("fleet", "on", 10.0, 20)
    v1, v10 = r1["busiest_link_kbps_p95"], r10["busiest_link_kbps_p95"]
    check(abs(h["at_1hz_kbps_p95"] - v1) < 1e-6 and abs(h["at_10hz_kbps_p95"] - v10) < 1e-6,
          "H13 is judged on the fleet-geometry rows of E53_table.csv")
    sup = v1 <= nb and v10 > nb
    check(sup == bool(h["supported"]), "H13's verdict in E53_bitrate.json follows its pre-registered rule")
    V["P1-E53-H13-1HZ"], V["P1-E53-H13-10HZ"] = kbps(v1), kbps(v10, 1)
    V["P1-E53-H13-VERDICT"] = "supported" if sup else "not supported"
    # Referee M10 and decisions A1, B3, B8: H13 is a design calculation. Reports are not relayed, so no node can hear
    # more than the fleet's summed load, 20 x the per-rover load, in any geometry; and the design note that the
    # second pre-registration names as its parameter source had the same arithmetic before E53 ran.
    fleet_sum = 20 * per[("on", 1.0)]
    check(abs(v1 - r1["one_hop_sum_kbps"]) < 1e-3 and abs(v1 - fleet_sum) < 0.002 * v1,
          "H13's 95th percentile at 1 Hz is the fleet's summed load (20 x the per-rover load, to the table's rounding)")
    check(fleet_sum <= nb, "the fleet's summed load at 1 Hz is below the budget, so H13's first clause holds in any geometry")
    dn = p.dev["h13_design_note"]
    v1_01 = p.e53_v01["h13"]["at_1hz_kbps_p95"]
    check(abs(dn["kbps_20_at_1hz"] - v1_01) < 0.1, "the design note's figure at 1 Hz is E53's with the v0.1 sizes, to the note's precision")
    check(v1 > v1_01, "the declaration in the heartbeat raises the load from v0.1 to v0.2")
    side = ("on the predicted side of the threshold in both clauses" if sup else
            "above the threshold in its first clause: the earlier budget was too small" if v1 > nb else
            "on the predicted side in its first clause and not in its second")
    V["P1-E53-H13-SENTENCE"] = (
        f"With authentication on and 20 rovers, the busiest link carried {kbps(v1)} at one position report a second "
        f"(95th percentile over the {e['draws']} draws; mean {kbps(r1['busiest_link_kbps_mean'])}), "
        f"{'inside' if v1 <= nb else 'above'} the {kbps(nb, 0)} of the earlier budget, and {kbps(v10, 1)} at ten "
        f"a second, {'above' if v10 > nb else 'inside'} it. H13 is {side}, and we report it as a design calculation "
        f"and not as a test [54]. Its first clause is arithmetic on the sizes and rates we assumed and holds in any "
        f"geometry: reports are not relayed, so no node can hear more than the fleet's sum, 20 &times; "
        f"{kbps(per[('on', 1.0)], 3)} = {kbps(fleet_sum)}, which is the 95th percentile above. The design note from "
        f"which the second pre-registration took its parameters had already computed "
        f"{num(dn['per_robot_Bps'])}{NB}B/s per robot, {kbps(dn['kbps_20_at_1hz'], 1)} for 20 robots and "
        f"{kbps(dn['kbps_20_at_10hz'], 1)} for their position reports alone at ten a second, for the first version "
        f"of the protocol; E53 gave {kbps(v1_01)} with that version's sizes, and the heartbeat that carries the "
        f"declaration in version 0.2 raises it to the {kbps(v1)} above.")
    V["P1-LRIP-INTRO-SENTENCE"] = (
        f"By the sizes and rates we assumed, twenty rovers reporting once a second offer {kbps(v1)}, "
        f"{'inside' if v1 <= nb else 'above'} the {kbps(nb, 0)} we had budgeted, and {kbps(v10, 1)} at ten reports a "
        f"second, which {'does not fit' if v10 > nb else 'still fits'}. This is a design calculation and not a test, "
        f"and it holds only on a channel that the base schedules, with reports travelling one hop (Section 5.8).")
    V["P1-LRIP-CONCLUSION-SENTENCE"] = (
        f"the periodic reports and the task and road messages of 20 rovers offer {kbps(v1, 1)} at one authenticated "
        f"position report a second")
    o1, o10 = row("fleet", "off", 1.0, 20)["busiest_link_kbps_p95"], row("fleet", "off", 10.0, 20)["busiest_link_kbps_p95"]
    same = (o1 <= nb) == (v1 <= nb) and (o10 > nb) == (v10 > nb)
    V["P1-E53-AUTH-SENTENCE"] = (
        f"Without authentication the same link carries {kbps(o1)} and {kbps(o10, 1)}: the security header and code "
        f"add {pc(100 * (per[('on', 1.0)] / per[('off', 1.0)] - 1), 0)} to the load at 1&nbsp;Hz and "
        + ("change neither side of the comparison." if same else "change the comparison with the budget."))

    air_s, air_a, air_2 = v1 / eta_s, v1 / eta_a, 2 * v1 / eta_s
    check(abs(air_s - h["airtime_1hz_scheduled_kbps"]) < 0.01 and abs(air_a - h["airtime_1hz_slotted_aloha_kbps"]) < 0.01,
          "the airtime values recomputed here equal those in E53_bitrate.json")
    check(air_s <= nb < min(air_a, air_2) and v10 > nb,
          "the budget holds at 1 Hz on a scheduled channel and fails at 10 Hz, on random access and when reports are relayed")
    fit = lambda x: "fits" if x <= nb else "does not fit"
    sched_only = air_s <= nb < min(air_a, air_2)
    V["P1-LRIP-CONCLUSION-SENTENCE"] += (
        f", which fits a {kbps(nb, 0)} channel only if the base schedules it and reports travel one hop" if sched_only
        else f", which {fit(v1)} a {kbps(nb, 0)} channel")
    # Referee M10(c): the sizes are Space Packets with their security fields. A link frame and channel coding come
    # on top. Inside a Proximity-1 frame every message gains the schema's proximity1_frame_bytes.
    fb = int(p.schema["framing"]["proximity1_frame_bytes"])
    per_fr = sum(v["rate_hz"] * (v["bytes"] + fb) for v in pr.values())                  # B/s per rover, framed
    check(abs(sum(v["rate_hz"] * v["bytes"] for v in pr.values()) * 8 / 1000 - per[("on", 1.0)]) < 1e-3,
          "rates times packet sizes give the per-rover load")
    fr20 = 20 * per_fr * 8 / 1000
    nmax0, nmax_fr = math.floor(eta_s * nb / per[("on", 1.0)]), math.floor(eta_s * nb / (per_fr * 8 / 1000))
    check(fr20 / eta_s <= nb, "with Proximity-1 framing 20 rovers still fit the scheduled channel")
    frow = p.v02["framing_row"]
    check(abs(frow["fleet_auth_1hz_20"]["one_hop_sum_kbps"] - fr20) < 0.01 and abs(frow["airtime_1hz_scheduled_kbps"] - fr20 / eta_s) < 0.01,
          "the framed loads recomputed here equal the framing row of E53's v0.2 block")
    check(sorted(p.v02["traffic_model_coverage"]["sent_by_E53"]) == sorted(pr), "the traffic model's message types are those the v0.2 block lists")
    V["P1-LRIP-FRAME-B"] = nbytes(fb)
    V["P1-E53-FRAMING-SENTENCE"] = (
        f"These are packet sizes before link framing and channel coding. Inside a Proximity-1 frame every message "
        f"gains {nbytes(fb)} (a synchronisation marker, the frame header and a checksum, as our design note counts "
        f"them from the Proximity-1 standards [58]): a rover then offers "
        f"{num(per_fr, 1)}{NB}B/s and 20 rovers {kbps(fr20, 1)}, a scheduled channel must run at "
        f"{kbps(fr20 / eta_s, 1)}, and the {kbps(nb, 0)} channel is full at {nmax_fr} rovers and not at {nmax0}. "
        f"Channel coding is counted in neither figure.")
    # Referee M10(d): the traffic model holds only some of the message types
    all_types = [m["name"] for m in p.schema["messages"]]
    absent = [n for n in all_types if n not in pr]
    check(len(pr) + len(absent) == len(all_types), "every message type is in the traffic model or named as absent")
    V["P1-E53-N-TYPES"] = f"{len(pr)}"
    V["P1-E53-TYPES-SENTENCE"] = (
        f"The traffic model holds {len(pr)} of the {len(all_types)} message types"
        + (": " + listing(f"<code>{n}</code>" for n in absent) + " are not in it, so the count is of the periodic "
           "reports and the task and road messages and not of the full message set." if absent else "."))
    # Second pass (12 Nov), tasks B-103 and B-104 (decisions B9, B10): the same calculation on driving steps only and
    # with STATUS and INTENT at 1 Hz (E53_bitrate.json "driving_split"), and the link rate under a curved-Moon loss
    # (E48_sizing.json "revision_b104"). Both are calculations on assumed inputs and are labelled so.
    ds = p.v02.get("driving_split")
    if ds is None:
        raise Pending("E53_bitrate.json lrip_v02 has no driving_split (task B-110)")
    d01 = p.e53_v01.get("driving_split") or {}
    ls = (d01.get("e54_link_shares_30_seeds") or {}).get("linked_share_driving_time")
    if ls is None:
        raise Pending("E53_bitrate.json driving_split has no E54 link shares (task B-103)")
    G2 = ds["e53_auth_20_rovers"]
    dv, pk = G2["lrip"]["fleet_driving"]["1 Hz"], G2["lrip"]["fleet_parked"]["1 Hz"]
    dvf = G2["proximity1"]["fleet_driving"]["1 Hz"]
    s1, s1f = ds["status_intent_at_1hz"]["lrip"], ds["status_intent_at_1hz"]["proximity1"]
    check(abs(pk["busiest_link_kbps_p95"] - v1) < 1e-3, "the parked draws reproduce the fleet geometry's busiest link (v0.2 sizes)")
    check(dv["mean_hops_to_base"] > pk["mean_hops_to_base"] and dv["reachable_share"] < pk["reachable_share"],
          "driving vehicles are more hops from the base and fewer of them have a path to it")
    check(dv["scheduled_airtime_p95_kbps"] <= nb and dvf["scheduled_airtime_p95_kbps"] <= nb,
          "on driving steps the scheduled channel still carries 20 rovers at 1 Hz, framed or not")
    check(dv["slotted_aloha_airtime_p95_kbps"] > nb and dvf["slotted_aloha_airtime_p95_kbps"] > nb,
          "on driving steps slotted random access does not fit the narrow-band channel")
    s1_all = [s1["sources_20_rovers_kbps"], s1f["sources_20_rovers_kbps"],
              s1["busiest_link_20_rovers"]["fleet"]["scheduled_airtime_p95_kbps"],
              s1["busiest_link_20_rovers"]["fleet_driving"]["scheduled_airtime_p95_kbps"],
              s1f["busiest_link_20_rovers"]["fleet"]["scheduled_airtime_p95_kbps"],
              s1f["busiest_link_20_rovers"]["fleet_driving"]["scheduled_airtime_p95_kbps"]]
    s1_over = all(x > nb for x in s1_all)
    V["P1-E53-DRIVING-SENTENCE"] = (
        f"Two further calculations, with the same sizes, show how far the result depends on its inputs. Only "
        f"{sh(ds['pool_driving_share'], 1)} of the vehicle-steps in the pool that the fleet geometry samples are "
        f"driving steps. Drawn from those alone, 20 rovers are {num(dv['mean_hops_to_base'], 2)} hops from the base "
        f"on average where a path exists, {sh(dv['reachable_share'])} of them have one, and the busiest link "
        f"carries {kbps(dv['busiest_link_kbps_p95'], 1)} at one position report a second (95th percentile), against "
        f"{num(pk['mean_hops_to_base'], 2)} hops, {sh(pk['reachable_share'])} and "
        f"{kbps(pk['busiest_link_kbps_p95'], 1)} for parked vehicles. As scheduled airtime the driving draws need "
        f"{kbps(dv['scheduled_airtime_p95_kbps'])}, or {kbps(dvf['scheduled_airtime_p95_kbps'])} in Proximity-1 "
        f"frames, and on slotted random access {kbps(dv['slotted_aloha_airtime_p95_kbps'], 1)} or "
        f"{kbps(dvf['slotted_aloha_airtime_p95_kbps'], 1)}, which does not fit. Over the recorded month of "
        f"Section 5.9 a vehicle had a path to the base for {sh(ls)} of its driving time. If the status and intent "
        f"reports are also sent once a second, the 20 rovers offer {kbps(s1['sources_20_rovers_kbps'], 2)} at the "
        f"sources, {kbps(s1f['sources_20_rovers_kbps'], 2)} framed, which is "
        + (f"above the {kbps(nb, 0)} channel in every case, before any airtime is counted: H13's first clause holds "
           f"only at the report rates we assumed." if s1_over else
           f"not inside the {kbps(nb, 0)} channel in every case."))
    b104 = p.e48.get("revision_b104") if p.e48 is not None else None
    if b104 is None:
        raise Pending("E48_sizing.json has no revision_b104 (task B-104)")
    wh = b104["per_class"]["LTV1"]["worst_hop"]
    check(wh["kbps"]["spherical_ground"] < wh["kbps"]["flat_ground"] < wh["kbps"]["free_space"],
          "the curved-Moon loss gives a lower rate than flat ground, and flat ground a lower one than free space")
    V["P1-LINKLAW-SENTENCE"] = (
        f"Nor does the link law enter this paper's runs: a link exists or it does not. As a calculation outside "
        f"them, the companion paper's link budget [44] gives two rover antennas {num(wh['d_m'] / 1000)}{NB}km apart "
        f"{kbps(wh['kbps']['flat_ground'], 0)} over flat ground and {kbps(wh['kbps']['spherical_ground'], 0)} when "
        f"the Moon's curvature is counted ({num(wh['spherical_minus_flat_db'], 1)}{NB}dB more loss), so the "
        f"{num(wh['d_m'] / 1000)}{NB}km range we assume is a range at which a narrow-band channel closes and a "
        f"megabit channel may not.")
    V["P1-E53-AIR-SCHED"], V["P1-E53-AIR-ALOHA"] = kbps(air_s), kbps(air_a, 1)
    V["P1-E53-AIRTIME-SENTENCE"] = (
        f"Load at the sources is not airtime (Proposition 2). On a channel that the base schedules, with a fifth of "
        f"the time left as guard intervals (efficiency {eta_s:g}, Assumed), the {kbps(v1)} of 20 rovers needs a "
        f"channel of {kbps(air_s)}, which {fit(air_s)} {kbps(nb, 0)}. On slotted random access, whose efficiency "
        f"tends to 1/e, it needs {kbps(air_a, 1)}, which {fit(air_a)}; and if every report were relayed once, the "
        f"scheduled channel would need {kbps(air_2, 1)}, which {fit(air_2)}.")
    V["P1-PROP2-EXAMPLE-SENTENCE"] = (
        f"With E53's sizes and rates a rover offers {num(per[('on', 1.0)] * 1000 / 8, 1)}{NB}B/s, so "
        f"<i>N</i>&nbsp;=&nbsp;20 gives <i>L</i>&nbsp;=&nbsp;{kbps(20 * per[('on', 1.0)])}. With "
        f"<i>h</i>&nbsp;=&nbsp;1: <i>R</i>&nbsp;&ge;&nbsp;{kbps(20 * per[('on', 1.0)] / eta_s)} on a scheduled channel "
        f"(&eta;&nbsp;=&nbsp;{eta_s:g}) and {kbps(20 * per[('on', 1.0)] / eta_a, 1)} at &eta;&nbsp;=&nbsp;1/e; with "
        f"<i>h</i>&nbsp;=&nbsp;2 on the scheduled channel, {kbps(2 * 20 * per[('on', 1.0)] / eta_s, 1)}.")
    V["P1-PROP2-ALOHA-N20"] = f"{(1 - 1 / 20) ** 19:.3f}"
    V["P1-PROP2-ALOHA-LIMIT"] = f"{1 / math.e:.3f}"

    # the fleet at which the scheduled narrow-band channel is full (fleet geometry: the busiest link hears everyone)
    check(all(row("fleet", "on", 1.0, n)["busiest_link_kbps_p95"] >= 0.99 * row("fleet", "on", 1.0, n)["one_hop_sum_kbps"]
              for n in NS), "in the fleet geometry the busiest link carries the whole fleet's reports")
    nmax = math.floor(eta_s * nb / per[("on", 1.0)])
    r40 = row("fleet", "on", 1.0, 40)["busiest_link_kbps_p95"]
    V["P1-E53-NMAX-SCHED"] = f"{nmax}"
    V["P1-E53-NMAX-SENTENCE"] = (
        f"This geometry draws positions from the trajectories of the eight simulated vehicles with every "
        f"vehicle-step equally likely, so the draws follow where the fleet spends its time, which is near the base, "
        f"and that sampling is why the busiest link hears the whole fleet (mean hops to the base "
        f"{rng_txt([row('fleet', 'on', 1.0, n)['mean_hops_to_base'] for n in NS], lambda x: num(x, 2))}; "
        f"{rng_txt([row('fleet', 'on', 1.0, n)['reachable_share'] for n in NS], lambda x: sh(x))} of rovers with a "
        f"path to it), so the scheduled {kbps(nb, 0)} channel is full at {nmax} rovers reporting once a second"
        + (f": 40 rovers fit as load ({kbps(r40, 1)}) and not as airtime ({kbps(r40 / eta_s, 1)})." if r40 <= nb < r40 / eta_s
           else ".")
        + " Vehicles on the road are placed differently, as the next paragraph shows.")
    r5 = row("fleet", "on", 10.0, 5)["busiest_link_kbps_p95"]
    r80 = row("fleet", "on", 10.0, 80)["busiest_link_kbps_p95"]
    V["P1-E53-10HZ-SENTENCE"] = (
        (f"At ten reports a second even five rovers load it with {kbps(r5, 1)}. " if r5 > nb else
         f"At ten reports a second five rovers still fit ({kbps(r5, 1)}). ")
        + f"The {kbps(bb, 0)} broadband channel "
        + (f"carries 80 rovers at ten reports a second ({kbps(r80, 0)} as load, {kbps(r80 / eta_s, 0)} as scheduled "
           f"airtime)." if r80 / eta_s <= bb else f"does not carry 80 rovers at ten reports a second ({kbps(r80, 0)})."))

    # the spread geometry (LEAD, 11 Nov; not the pre-registered one)
    sp = {n: row("spread", "on", 1.0, n) for n in NS}
    sh_mean = [sp[n]["busiest_link_kbps_mean"] / sp[n]["one_hop_sum_kbps"] for n in NS]
    sh_p95 = [sp[n]["busiest_link_kbps_p95"] / sp[n]["one_hop_sum_kbps"] for n in NS]
    reach = [sp[n]["reachable_share"] for n in NS]
    check(0.35 <= min(sh_mean) and max(sh_mean) <= 0.65, "spread out, the busiest link carries about half the fleet sum")
    check(reach == sorted(reach) and reach[0] < 0.5 and reach[-1] < 0.95, "few spread rovers reach the base, more as they multiply")
    nfit = [n for n in NS if sp[n]["busiest_link_kbps_p95"] / eta_s <= nb]
    check(sp[20]["reachable_share"] < 2 / 3 and sp[20]["busiest_link_kbps_p95"] / eta_s < nb,
          "at 20 spread rovers fewer than two in three reach the base, and the channel is not full")
    V["P1-E53-SPREAD-SENTENCE"] = (
        f"With the same number of rovers spread uniformly over the route samples, radio neighbourhoods are smaller. "
        f"The busiest link carried about half the fleet's summed load, {sh(min(sh_mean))} to {sh(max(sh_mean))} on "
        f"average over draws and {sh(min(sh_p95))} to {sh(max(sh_p95))} at the 95th percentile: "
        f"{kbps(sp[20]['busiest_link_kbps_p95'])} for 20 rovers at 1&nbsp;Hz against {kbps(v1)} near the base. A "
        f"scheduled {kbps(nb, 0)} channel then carries {max(nfit)} spread rovers at 1&nbsp;Hz"
        + ("" if max(nfit) == NS[-1] else f" and not {NS[NS.index(max(nfit)) + 1]}") +
        f". The price is reach. Events took {num(min(sp[n]['mean_hops_to_base'] for n in NS), 1)} to "
        f"{num(max(sp[n]['mean_hops_to_base'] for n in NS), 1)} hops to the base where a path existed, and only "
        + listing(sh(x) for x in reach) + f" of {listing(NS)} rovers had one. A sparse fleet spread over the routes "
        f"is cut off from the base before its radio channel fills (Table 10).")

    rows = []
    for a in ("on", "off"):
        for hz in HZ:
            rows.append([f"{nbytes(p.schema['framing']['trailer']['mac8'])} code, awards and grants signed"
                         if a == "on" else "none", f"{hz:g}&nbsp;Hz", num(per[(a, hz)], 3 if per[(a, hz)] < 1 else 2)]
                        + [_sig(row("fleet", a, hz, n)["busiest_link_kbps_p95"]) for n in NS])
    V["P1-TABLE-E53-FLEET"] = _tab(
        f"<b>Table 9.</b> E53, fleet geometry (pre-registered): load per rover and load of the busiest link "
        f"(kbit/s, 95th percentile over {e['draws']} draws of rover positions) by position-report rate and fleet "
        f"size, with and without authentication. The busiest link is the largest sum of transmissions that any "
        f"node hears. Sizes are counted by the codec; no radio is simulated.",
        ["Authentication", "Position reports", "Per rover"] + [f"{n} rovers" for n in NS], rows)
    rows = [[f"Busiest link at {hz:g}&nbsp;Hz (kbit/s, 95th percentile)"]
            + [_sig(row("spread", "on", hz, n)["busiest_link_kbps_p95"]) for n in NS] for hz in HZ]
    rows.append(["Busiest link as a share of the fleet sum (mean over draws)"] + [sh(x) for x in sh_mean])
    rows.append(["Mean hops to the base, where a path exists"] + [num(sp[n]["mean_hops_to_base"], 2) for n in NS])
    rows.append(["Rovers with a path to the base"] + [sh(x) for x in reach])
    V["P1-TABLE-E53-SPREAD"] = _tab(
        "<b>Table 10.</b> E53, spread geometry (added after the pre-registration, not used for H13): rovers placed "
        "uniformly over the route samples, authentication on.", ["Quantity"] + [f"{n} rovers" for n in NS], rows)
    return {"v1": v1, "v10": v10, "nb": nb, "sup": sup, "nmax": nmax, "per1": per[("on", 1.0)], "draws": e["draws"],
            "sched_only": sched_only, "n_types": len(pr), "n_all": len(all_types), "fr20": fr20,
            "hops": [row("fleet", "on", 1.0, n)["mean_hops_to_base"] for n in NS]}


E54_SUP_REVIEW = "superseded_2026-11-13_b118"      # the values before the code review of 13 Nov 2026
E54_SUP_WINDOW = "superseded_2026-11-14_b120_b"    # the ledger split before the end-of-window fix of 14 Nov 2026
E54_NAMES = {"drop_retry": "drop and retry", "sf": "store and forward", "sf_ll": "store and forward + return to the last link point"}


def phase6_e54(p, V, fill, check):
    """E54 (Sections 4.8 and 5.9, Table 11). Every value goes through fill(): a missing results file is Pending."""
    LOSS = 0.25                                                 # H14's pre-registered loss

    def design():
        p.h14()                                                 # Pending when the results file is missing
        e = p.e54
        prm = e["parameters"]
        b0, b1 = e["blackout_days"]
        n = len(e["seeds"])
        check(abs((b1 - b0) - 14.0) < 1e-9, "E54's imposed Earth blackout lasts 14 days")
        check(prm["retry_s"] > 60.0, "drop-and-retry's retry interval is longer than a grant's 60 s lifetime")
        span_min = (prm["max_tries"] - 1) * prm["retry_s"] / 60.0
        check(span_min * 60 < prm["lease_s"], "drop-and-retry gives up before the lease ends")
        g = p.row54(0.25, "sf")
        n_res = round(e["reservations_per_seed"] * n)
        check(g["grant_n"] == g["award_n"] and g["grant_n"] > 2 * n_res,
              "the replay generates a grant for every award, more than twice the recorded single-lane reservations")
        # Part 7 (13 Nov, review N6 and task B-117): the return rule in the code is the one Section 3.13 states, and
        # the awards are the jobs plus the second vehicle of each team job
        check(prm.get("return_rule") == "papers" and abs(prm["return_speed_factor"] - 0.5) < 1e-12
              and "upper reading" in str(e.get("lost_link_rule", "")),
              "E54's lost-link return is the rule of Section 3.13 (hold, then retrace at half speed), read at its upper end")
        aj = e["awards_and_jobs"]
        check(abs(aj["awards_per_seed"] - aj["jobs_per_seed"] - (aj["vehicles_per_job_max"] - 1) * aj["team_jobs_per_seed"]) < 1e-6
              and round(aj["awards_per_seed"] * n) == g["award_n"] and abs(aj["jobs_per_seed"] - e["jobs_per_seed"]) < 1e-9
              and aj["vehicles_per_job_max"] == 2,
              "the awards of the replay are its jobs plus one more for each two-vehicle team job")
        return (
            f"The month is July 2028 as the engine recorded it for the auction at the middle load, with the fleet of "
            f"eight vehicles and the road rules of [45], on {n} seeds ({num(e['jobs_per_seed'])} jobs and "
            f"{num(e['reservations_per_seed'])} single-lane road reservations a seed). Three ways of carrying the messages are compared at per-hop loss 0.10, 0.25 and 0.40. "
            f"<i>Drop and retry</i> sends end to end along the current shortest path, again every "
            f"{secs(prm['retry_s'])}, at most {prm['max_tries']} times and never past the message's lifetime. "
            f"<i>Store and forward</i> moves a message hop by hop with custody [60]: a lost transmission is repeated "
            f"after {secs(prm['custody_timer_s'])} while the link lasts, a message with no path waits in a "
            f"{num(prm['queue_bytes'] / 1e6)}{NB}MB store, and it expires at its lifetime. Both sets of retry "
            f"settings are Assumed and were not swept: the baseline's {words(prm['max_tries'])} tries end "
            f"{num(span_min)} minutes into a lifetime of {num(prm['lease_s'] / 60)} minutes, while store and forward "
            f"repeats for all of it. The third adds the <i>lost-link return</i> of Section 3.13: a vehicle that has "
            f"had no path to the base for {secs(prm['t_hold_s'])} retraces its path at half speed to the last point "
            f"where it had one. The replay follows the recorded drive, in which the vehicle did not stop at the next "
            f"safe point, so the stretch it retraces is the one driven in those {secs(prm['t_hold_s'])}, an upper "
            f"reading of the rule. The messages are generated from the recorded run: an award to each vehicle of a job "
            f"({num(aj['awards_per_seed'], 1)} awards a seed, the {num(aj['jobs_per_seed'], 1)} jobs and one more for each "
            f"of the {num(aj['team_jobs_per_seed'], 2)} team jobs of two vehicles; its lifetime is the lease of {num(prm['lease_s'] / 3600)}{NB}h, the time after which an awarded job "
            f"returns to the pool; an award that expires undelivered is a lost job, auctioned again), a reservation "
            f"grant with every award (lifetime 60{NB}s; {g['grant_n']:,} grants against the {n_res:,} single-lane "
            f"reservations of the recorded runs, so more than half of them belong to jobs with no such reservation), "
            f"a report at the end of each job, and a status report every {secs(prm['status_period_s'])} for the "
            f"base's age of information. A {num(b1 - b0)}-day Earth blackout is imposed on days {num(b0)} to "
            f"{num(b1)}, as H14 names it. It can affect only messages addressed to Earth, which here are the daily "
            f"records of who did what (the ledger); awards, grants, reports and status travel between the base and "
            f"the vehicles and do not depend on it.")
    fill("P1-E54-DESIGN-SENTENCE", design, "E54")
    fill("P1-E54-HOLD-S", lambda: (p.h14(), secs(p.e54["parameters"]["t_hold_s"]))[1], "E54")
    fill("P1-E54-RDV-H", lambda: (p.h14(), f"{num(p.e54['parameters']['t_rdv_s'] / 3600)}{NB}h")[1], "E54")

    def ladder_sentence():
        p.h14()
        ll, prm = p.man["small_rover"]["lost_link"], p.e54["parameters"]
        check(ll["t_return_s"] == prm["t_hold_s"] and ll["t_rendezvous_s"] == prm["t_rdv_s"],
              "the example manifest's lost-link times are those E54 uses")
        return (f"The example manifest of Section 3.12 carries these times for its vehicle: {secs(ll['t_hold_s'])} "
                f"without the base before it treats itself as cut off, {secs(ll['t_return_s'])} held before it "
                f"returns, {secs(ll['t_rendezvous_s'])} at the last link point before it leaves for the meeting point.")
    fill("P1-LRIP-LADDER-SENTENCE", ladder_sentence, "E54")

    def h14_sentence():
        h = p.h14()
        prm = p.e54["parameters"]
        dr, ll, d = h["lost_jobs_drop_retry_per_seed"], h["lost_jobs_sf_ll_per_seed"], h["difference_sf_ll_minus_drop_retry"]
        rdr, rsf, rll = (p.row54(LOSS, k) for k in ("drop_retry", "sf", "sf_ll"))
        fewer = d["ci"][1] < 0
        check(bool(h["supported"]) == (fewer and h["stuck_reservations_sf_ll"] == 0), "H14's verdict in the file follows its rule")
        check(round(dr["mean"] * dr["n"]) == rdr["award_lost"] and round(ll["mean"] * ll["n"]) == rll["award_lost"],
              "the lost jobs per seed add up to the table's counts")
        none = rll["award_lost"] == 0
        # Referee M9(a): how much of the baseline's loss is five independent losses in a row on a one-hop path
        k = int(prm["max_tries"])
        p5 = {l: p.row54(l, "drop_retry")["award_n"] * l ** k for l in (0.10, 0.25, 0.40)}
        lost = {l: p.row54(l, "drop_retry")["award_lost"] for l in p5}
        check(all(p5[l] <= lost[l] for l in p5), "five losses in a row account for no more than the baseline's lost awards")
        check(p5[LOSS] > 0.5 * lost[LOSS] and p5[0.40] > 0.5 * lost[0.40],
              "five losses in a row account for more than half of the baseline's lost awards at loss 0.25 and 0.40")
        hops = [float(x) for x in p.t53[(p.t53["geometry"] == "fleet") & (p.t53["auth"] == "on")
                                        & np.isclose(p.t53["position_hz"], 1.0)]["mean_hops_to_base"]]
        tries_sf = prm["lease_s"] / prm["custody_timer_s"]
        span_min = (k - 1) * prm["retry_s"] / 60.0
        return (
            f"At per-hop loss {LOSS:.2f}, drop and retry lost {rdr['award_lost']} of "
            f"{rdr['award_n']:,} awards, {num(dr['mean'], 2)} jobs a seed (95&#8239;% CI {num(dr['ci'][0], 2)} to "
            f"{num(dr['ci'][1], 2)}). Store and forward lost {rsf['award_lost']}, and "
            f"{'none' if none else rll['award_lost']} when unheard vehicles were assumed to return to their last link "
            f"point. The paired difference between the third and the first is "
            f"{num(d['mean'], 2)} jobs a seed (95&#8239;% CI {num(d['ci'][0], 2)} to {num(d['ci'][1], 2)}, "
            f"n&nbsp;=&nbsp;{d['n']}), which {'excludes' if fewer else 'includes'} zero: the first clause of H14 "
            f"{'holds' if fewer else 'does not hold'} against this baseline. The baseline decides much of that. Drop "
            f"and retry gives up after {words(k)} tries, {num(span_min)} minutes into a lease of "
            f"{num(prm['lease_s'] / 60)} minutes, while store and forward can repeat {num(tries_sf)} times in the "
            f"same hour; neither setting was swept. Paths are almost always one hop (a mean of "
            f"{num(min(hops), 2)} to {num(max(hops), 2)} hops to the base in E53), so custody at relays plays little "
            f"part, and {words(k)} independent losses in a row have probability <i>p</i><sup>{k}</sup>: "
            f"{rdr['award_n']:,}&nbsp;&times;&nbsp;{LOSS:.2f}<sup>{k}</sup> = {num(p5[LOSS], 1)} of the "
            f"{lost[LOSS]} lost awards, {num(p5[0.40], 0)} of the {lost[0.40]} lost at loss 0.40 and "
            f"{num(p5[0.10], 2)} of the {lost[0.10]} at 0.10. The others are vehicles that had no path for the whole "
            f"lease, of which store and forward itself lost {rsf['award_lost']}. The comparison is therefore mostly "
            f"one of {words(k)} tries in {num(span_min)} minutes against {num(tries_sf)} tries in an hour, and a "
            f"baseline that retried every {secs(prm['custody_timer_s'])} without a cap was not run. The 14-day Earth "
            f"blackout that H14 names cannot affect this clause (Section 4.8).")
    fill("P1-E54-H14-SENTENCE", h14_sentence, "E54")
    fill("P1-E54-H14-VERDICT", lambda: ("first clause holds against the stated baseline; second clause not testable as written"
                                        if p.h14()["difference_sf_ll_minus_drop_retry"]["ci"][1] < 0 else
                                        "first clause does not hold; second clause not testable as written"), "E54")

    def stuck_sentence():
        h, e = p.h14(), p.e54
        rdr, rll = p.row54(LOSS, "drop_retry"), p.row54(LOSS, "sf_ll")
        check(rll["stuck_reservations"] == 0 and rll["stuck_hours"] == 0, "the results file sets stuck reservations to zero under the rule")
        check(rdr["stuck_reservations"] == h["stuck_reservations_drop_retry"] > 0, "without the return some reservations end with their holder out of reach")
        check("UNCONFIRMED segment" in str(e.get("stuck_definition", "")) and "leaves on schedule" in str(e.get("stuck_definition", "")),
              "the results file defines a stuck reservation as an unconfirmed segment, with every vehicle leaving on schedule")
        # Part 7 (13 Nov, review N7): the file says which half of H14 is measured
        check(bool(h.get("clause_1_measured")) and "BY RULE, not by measurement" in str(h.get("clause_2_basis", ""))
              and "by construction" in str(h.get("clause_2_basis", "")),
              "the results file says H14's second clause holds by rule, not by measurement, and only the first is measured")
        n = len(e["seeds"])
        return (
            f"H14's second clause, that the rule leaves no reservation stuck past its timeout, is not testable as "
            f"written, and we report no verdict on it [54]. The zero that the results file holds for it is set by "
            f"the rule's definition: in the file's words the clause holds by rule, not by measurement, and only the "
            f"first clause is measured. The rule as first written released a silent vehicle's reservation at its "
            f"timeout and is withdrawn: releasing the segment is unsafe if the vehicle is disabled inside it. "
            f"Under the rule of Section 3.13 the segment is marked unconfirmed and may be entered only at caution "
            f"speed. What the replay gives is a count. Without the return to the last link point, "
            f"{rdr['stuck_reservations']:,} of the {round(e['reservations_per_seed'] * n):,} reservations in the {n} "
            f"seeds ended while their holder had no path to the base "
            f"{secs(e['parameters']['grace_s'])} after the timeout. In the replay every vehicle had left its segment "
            f"on schedule, but the base cannot know that, so these segments stay unconfirmed until the holder is "
            f"heard again: {num(rdr['stuck_hours'])}{NB}h in all, {num(rdr['stuck_hours'] / n)}{NB}h a seed. How "
            f"many stay unconfirmed when vehicles return to their last link point was not counted, and what crossing "
            f"an unconfirmed segment at caution speed costs in delay is not priced.")
    fill("P1-E54-STUCK-SENTENCE", stuck_sentence, "E54")

    def grants_sentence():
        e = p.e54
        g = {l: {k: p.row54(l, k) for k in E54_NAMES} for l in (0.10, 0.25, 0.40)}
        dr = {l: g[l]["drop_retry"]["grant_lost_share"] for l in g}
        check(all(abs(dr[l] - l) < 0.02 for l in dr), "drop-and-retry loses grants at about the per-hop loss rate")
        check(all(g[l]["sf"]["grant_lost_share"] < 0.01 and g[l]["sf_ll"]["grant_lost_share"] < 0.01 for l in g),
              "custody loses under 1 % of grants at every loss")
        sf, ll = g[LOSS]["sf"], g[LOSS]["sf_ll"]
        return (
            f"One further difference is a consequence of two settings and not a finding. A reservation grant lives "
            f"60{NB}s and drop and retry repeats after {secs(e['parameters']['retry_s'])}, so it has one try on one "
            f"hop and loses grants at the per-hop loss rate itself: {pc(100 * dr[0.10], 1)}, "
            f"{pc(100 * dr[0.25], 1)} and {pc(100 * dr[0.40], 1)} at loss 0.10, 0.25 and 0.40. With custody, "
            f"{sf['grant_lost']} of {sf['grant_n']:,} grants were lost at loss {LOSS:.2f} "
            f"({pc(100 * sf['grant_lost_share'], 2)}), and "
            f"{'none' if ll['grant_lost'] == 0 else ll['grant_lost']} with the return to the last link point. These "
            f"are counts of messages: a grant was generated for every award, and more than half of the jobs have no "
            f"single-lane reservation (Section 4.8), so a lost grant here is not a vehicle stopped before a segment.")
    fill("P1-E54-GRANTS-SENTENCE", grants_sentence, "E54")

    def cost_sentence():
        """Referee M9(b): what the replay leaves out of the lost-link return."""
        e = p.e54
        ls = e["link_shares"]["linked_share_driving_time"]
        check(0 < ls < 1, "vehicles have a path to the base for part of their driving time only")
        return (
            f"The return is applied by editing the contact plan while the recorded job timeline stays: for the "
            f"radio a returning vehicle stands at its last link point, and for the logistics it is driving its job "
            f"at the same time. The replay therefore counts what the return gains in contact and not what it costs "
            f"in interrupted jobs. That cost is not small: the rule produced "
            f"{num(e['lost_link_returns_per_seed'], 1)} returns a seed against {num(e['jobs_per_seed'], 1)} jobs, and in "
            f"the recorded month a vehicle had a path to the base for only {sh(ls)} of its driving time, so the "
            f"ladder of Section 3.13 read literally would interrupt a large share of drives.")
    fill("P1-E54-COST-SENTENCE", cost_sentence, "E54")

    def v02_sentence():
        """Part 6 (13 Nov, task B-111, results/E54_dtn.json block `lrip_v02`): the replay repeated at the packet sizes of
        protocol version 0.2 and in Proximity-1 frames. No value and no verdict changes; the checks below fail the build
        if that stops being true. It is a property of the replay's message set, not a test of version 0.2."""
        p.h14()
        e = p.e54
        if "lrip_v02" not in e:
            raise Pending("E54_dtn.json has no block lrip_v02 (task B-111)")
        b = e["lrip_v02"]
        rows, sz = b["rows"], b["sizes_bytes"]
        same = lambda a, c: all(a[k] == c[k] for k in a if not k.endswith("_bytes"))
        check(list(b["values_moved_vs_v01"]) == [] and
              all(len(rows[v]) == len(rows["v0.1"]) and all(same(x, y) for x, y in zip(rows["v0.1"], rows[v]))
                  for v in ("v0.2", "v0.2_proximity1")),
              "the E54 replay at version 0.2 sizes and in Proximity-1 frames gives the version 0.1 value in every row")
        pub = [x for x in e["rows"] if x["protocol"] in E54_NAMES]     # without the rows of the pre-review return rule
        check(all(b["reproduction_of_main_table_v01"].values()) and len(pub) == len(rows["v0.1"]) and
              all(all(x[k] == y[k] for k in y if k in x) for x, y in zip(rows["v0.1"], pub)),
              "the version 0.1 rows of the E54 size rerun equal the rows of the main table (Table 11)")
        check(all(b["h14"][v] == b["h14"]["v0.1"] for v in b["h14"]) and
              all(b["h14"][v]["difference_sf_ll_minus_drop_retry"] == e["h14"]["difference_sf_ll_minus_drop_retry"] for v in b["h14"]),
              "H14's first clause comes out the same at version 0.2 sizes and in Proximity-1 frames")
        check(all(bool(v["h14_supported"]) and bool(v["same_as_v0.1"]) for v in b["verdicts"].values()),
              "no verdict of E54 changes at version 0.2 sizes")
        fb = int(p.schema["framing"]["proximity1_frame_bytes"])
        check(sz["v0.2"] == sz["v0.1"] and sorted(sz["v0.1"]) == ["RESERVE_GRANT", "TASK_AWARD", "TASK_STATE"] and
              all(int(sz["v0.2_proximity1"][k]) - int(sz["v0.2"][k]) == fb for k in sz["v0.2"]),
              "the replay sends awards, grants and task states, whose sizes version 0.2 does not change; a Proximity-1 frame adds its bytes to each")
        q = float(e["parameters"]["queue_bytes"])
        worst = max(float(v) for v in b["max_queue_bytes_bound"].values())
        check(worst < 0.01 * q, "every message of a seed held at once is under 1 % of a node's store")
        return (f"The replay E54 was repeated at the packet sizes of version 0.2 and in Proximity-1 frames, and no value "
                f"and no verdict changed. That is a property of the replay's message set and not a test of version 0.2: "
                f"it sends task awards, reservation grants and task states, whose sizes version 0.2 does not change, and "
                f"a size counts only against a node's store of {num(q / 1e6)}{NB}MB.")
    fill("P1-E54-V02-SENTENCE", v02_sentence, "E54 lrip_v02 (B-111)")

    def aoi_sentence():
        e = p.e54
        dr, sf, ll = (p.row54(LOSS, k) for k in ("drop_retry", "sf", "sf_ll"))
        check(abs(dr["aoi_mean_s"] - sf["aoi_mean_s"]) < 0.01 * sf["aoi_mean_s"], "the transport does not change the base's age of information")
        check(ll["aoi_mean_s"] < 0.05 * sf["aoi_mean_s"], "the lost-link rule cuts the base's age of information")
        check(sf["task_state_lost"] < dr["task_state_lost"] and sf["task_state_delay_mean_s"] > dr["task_state_delay_mean_s"]
              and ll["task_state_delay_mean_s"] < sf["task_state_delay_mean_s"], "holding delivers more end-of-job reports, later")
        return (
            f"The return to the last link point changes what the base knows, not what the radio loses. Without it the base's "
            f"picture of a vehicle was on average {num(sf['aoi_mean_s'] / 60)}{NB}min old "
            f"({secs(sf['aoi_mean_s'])}) under either transport, and the worst-placed vehicle went unheard for "
            f"{num(sf['aoi_worst_vehicle_s'] / 3600)}{NB}h. With it the mean age was {secs(ll['aoi_mean_s'], 1)} and the "
            f"worst vehicle's {secs(ll['aoi_worst_vehicle_s'], 1)}: the return was made "
            f"{num(e['lost_link_returns_per_seed'], 1)} times a seed and removed "
            f"{num(e['lost_link_isolation_h_saved_per_seed'])} vehicle-hours of isolation a seed. The end-of-job "
            f"reports show the cost of holding a message: drop and retry lost {sh(dr['task_state_lost_share'])} of "
            f"them, store and forward lost {sh(sf['task_state_lost_share'], 1)} and delivered the rest "
            f"{secs(sf['task_state_delay_mean_s'])} late on average, because a vehicle that ends a job out of reach "
            f"waits for a contact, and with the return to the last link point the delay fell to "
            f"{secs(ll['task_state_delay_mean_s'], 1)}"
            + (" and no report was lost." if ll["task_state_lost"] == 0 else f" and {ll['task_state_lost']} were lost."))
    fill("P1-E54-AOI-SENTENCE", aoi_sentence, "E54")

    def superseded():
        """The values published before the code review of 13 Nov 2026, kept in the results file under a dated key."""
        p.h14()
        # The file holds one superseded block per correction; each is selected by its key (pass of 14 Nov, B-120).
        ks = [E54_SUP_REVIEW]
        have = sorted(k for k in p.e54 if k.startswith("superseded_"))
        if have != sorted([E54_SUP_REVIEW, E54_SUP_WINDOW]):
            raise KeyError(f"E54_dtn.json: expected the superseded blocks {E54_SUP_REVIEW} and {E54_SUP_WINDOW}, found {have}")
        o = p.e54[ks[0]]
        if o.get("superseded_on") != "2026-11-13":
            raise KeyError(f"E54_dtn.json {ks[0]}: superseded_on is {o.get('superseded_on')}, expected 2026-11-13")

        def row(loss, proto):
            d = [x for x in o["rows"] if abs(x["loss"] - loss) < 1e-9 and x["protocol"] == proto]
            if len(d) != 1:
                raise KeyError(f"E54_dtn.json {ks[0]} row loss {loss} / {proto}: {len(d)} rows")
            return d[0]
        return o, row

    def correction_sentence():
        """Part 7 (13 Nov, review N3 to N7): what the code review changed in this section, said once, with the earlier
        values read from the results file's superseded block."""
        e, h = p.e54, p.h14()
        o, orow = superseded()
        ll, oll = p.row54(LOSS, "sf_ll"), orow(LOSS, "sf_ll")
        pre = p.row54(LOSS, "sf_ll_pre_review")
        check(all(s in str(o["reason"]) for s in ("counted delivered", "floored", "hour before the loss", "censored")),
              "the superseded block of E54 names the four corrections the text lists")
        check(ll["aoi_mean_s"] < 0.5 * oll["aoi_mean_s"] and ll["task_state_delay_mean_s"] < 0.5 * oll["task_state_delay_mean_s"]
              and e["lost_link_returns_per_seed"] > o["lost_link_returns_per_seed"],
              "the correction lowered the age of information and the report delay with the return, and raised the number of returns")
        check(all(p.row54(l, k)["award_lost"] == orow(l, k)["award_lost"] for l in (0.10, 0.25, 0.40) for k in E54_NAMES),
              "no count of lost awards changed with the correction")
        check(o["h14"]["difference_sf_ll_minus_drop_retry"] == h["difference_sf_ll_minus_drop_retry"]
              and all(e["h14_variants"][v]["difference_sf_ll_minus_drop_retry"] == h["difference_sf_ll_minus_drop_retry"]
                      and bool(e["h14_variants"][v]["supported"]) == bool(h["supported"])
                      for v in ("lost_incl_censored", "pre_review_return_rule")),
              "H14's first clause is the same before the correction, with censored messages counted as lost and under the earlier return rule")
        kinds = ("award", "grant", "task_state")
        check(all(p.row54(l, k)[f"{m}_censored"] == 0 for l in (0.10, 0.25, 0.40) for k in E54_NAMES for m in kinds),
              "no award, grant or end-of-job report was still undelivered at the end of the month")
        check("censored = still alive and undelivered at the window's end" in str(e.get("outcome_definitions", "")),
              "the results file tells censored messages apart from lost ones")
        g40, o40 = {k: p.row54(0.40, k)["grant_lost"] for k in ("sf", "sf_ll")}, {k: orow(0.40, k)["grant_lost"] for k in ("sf", "sf_ll")}
        check(g40 != o40 or ll["grant_lost"] != oll["grant_lost"], "the correction changed the grants lost under custody")
        check(abs(pre["aoi_mean_s"] - ll["aoi_mean_s"]) > 1.0 and abs(e["lost_link_pre_review"]["returns_per_seed"] - o["lost_link_returns_per_seed"]) < 1e-9,
              "the earlier return rule, kept as a variant, gives another age of information and the earlier number of returns")
        # the floor of the age of information, read from the results file (it was typed here before 14 Nov)
        fl = re.findall(r"floored at (\d+(?:\.\d+)?) s", str(e.get("outcome_definitions", "")))
        fl_old = re.findall(r"floored at dt/2 = (\d+(?:\.\d+)?) s", str(o["reason"]))
        if len(fl) != 1 or fl != fl_old:
            raise KeyError(f"E54_dtn.json: the floor of the age of information is not stated once and alike "
                           f"(outcome_definitions {fl}, {E54_SUP_REVIEW} reason {fl_old})")
        floor_s = float(fl[0])
        # Pass of 14 Nov (B-120 B): the rerun moved one count, the split of the month's undelivered Earth ledgers
        # between lost and censored. This paper prints no other value that moved; the move is named once, from the file.
        w = e[E54_SUP_WINDOW]
        check(w.get("superseded_on") == "2026-11-14" and all(s in str(w["reason"]) for s in ("censored", "lifetime", "window's end")),
              "the second superseded block of E54 is the one of the end-of-window fix of 14 November")
        LED = ("ledger_earth_lost", "ledger_earth_lost_share", "ledger_earth_censored")

        def moved(new_rows, old_rows):
            """The fields that differ between two row lists, as {field: {(protocol, old, new)}}."""
            key = lambda x: (round(x["loss"], 9), x["protocol"])
            a, b = {key(x): x for x in new_rows}, {key(x): x for x in old_rows}
            if sorted(a) != sorted(b) or len(a) != len(new_rows):
                raise KeyError("E54_dtn.json: the rerun and its superseded block do not hold the same rows")
            out = {}
            for k in a:
                if set(a[k]) != set(b[k]):
                    raise KeyError(f"E54_dtn.json row {k}: the rerun and its superseded block do not hold the same fields")
                for f in a[k]:
                    if a[k][f] != b[k][f]:
                        out.setdefault(f, set()).add((k[1], b[k][f], a[k][f]))
            return out
        mv = moved(e["rows"], w["rows"])
        check(sorted(mv) == sorted(LED), "the rerun of 14 November moved only the split of the Earth ledgers between lost and censored")
        check(all(len(mv.get(f, ())) == 3 and {q[0] for q in mv[f]} == {"sf", "sf_ll", "sf_ll_pre_review"} and len({q[1:] for q in mv[f]}) == 1 for f in LED),
              "the split moved alike in every store-and-forward row and in no drop-and-retry row")
        check(e["h14"] == w["h14"] and e["h14_variants"] == w["h14_variants"], "H14 and its variants are identical before and after the rerun of 14 November")
        sizes, sizes_w = e["lrip_v02"]["rows"], w["lrip_v02"]["rows"]
        check(sorted(sizes) == sorted(sizes_w)
              and all(sorted(moved(sizes[s], sizes_w[s])) == sorted(LED) for s in sizes)
              and e["lrip_v02"]["h14"] == w["lrip_v02"]["h14"] and e["lrip_v02"]["verdicts"] == w["lrip_v02"]["verdicts"],
              "in the size rerun too, only the ledger split moved on 14 November")
        lg, lw = p.row54(LOSS, "sf"), [x for x in w["rows"] if abs(x["loss"] - LOSS) < 1e-9 and x["protocol"] == "sf"][0]
        n_s = len(e["seeds"])
        check(lg["ledger_earth_lost_incl_censored"] == lw["ledger_earth_lost_incl_censored"]
              == lg["ledger_earth_lost"] + lg["ledger_earth_censored"] == lw["ledger_earth_lost"] + lw["ledger_earth_censored"],
              "the undelivered Earth ledgers are as many before and after; only their split moved")
        check(lg["ledger_earth_lost"] - lw["ledger_earth_lost"] == n_s == lw["ledger_earth_censored"] - lg["ledger_earth_censored"],
              "one Earth ledger a seed went from censored to lost")
        check(abs(lg["ledger_earth_lost_share"] - lg["ledger_earth_lost"] / lg["ledger_earth_n"]) < 1e-4
              and abs(lw["ledger_earth_lost_share"] - lw["ledger_earth_lost"] / lw["ledger_earth_n"]) < 1e-4,
              "the lost share of the Earth ledgers is the lost count over the number sent")
        window_note = (
            f" A second review, on 14 November 2026, moved one count that this section does not otherwise print: of "
            f"the {lg['ledger_earth_n']:,} daily ledgers sent to Earth in the month (all seeds), store and forward "
            f"left {lg['ledger_earth_lost_incl_censored']} undelivered, of which {lg['ledger_earth_lost']} are now "
            f"counted lost ({sh(lg['ledger_earth_lost_share'])}) and {lg['ledger_earth_censored']} censored; before, "
            f"{lw['ledger_earth_lost']} ({sh(lw['ledger_earth_lost_share'])}) and {lw['ledger_earth_censored']}. One "
            f"ledger a seed had a lifetime that ended exactly at the month's end and had been counted censored; its "
            f"whole lifetime was observed, so it is lost. No value of Table 11 and no part of H14 changed.")
        return (
            f"The values of this section and of Table 11 were corrected after a code review on 13 November 2026, "
            f"which found that a message could be counted as delivered after its lifetime had ended, that the age "
            f"of information had a floor of half a step ({secs(floor_s)}), and that the return rule in the code was not "
            f"the one of Section 3.13. Before, the mean age with the return was {secs(oll['aoi_mean_s'], 1)} "
            f"({secs(oll['aoi_worst_vehicle_s'], 1)} for the worst vehicle), the end-of-job reports with the return came {secs(oll['task_state_delay_mean_s'], 1)} late "
            f"with {oll['task_state_lost']} lost, "
            f"{'no grant was' if oll['grant_lost'] == 0 else str(oll['grant_lost']) + ' grants were'} lost with the "
            f"return at loss {LOSS:.2f} (at loss 0.40 store and forward lost {o40['sf']} and {o40['sf_ll']} with the "
            f"return, now {g40['sf']} and {g40['sf_ll']}), and the return was made "
            f"{num(o['lost_link_returns_per_seed'], 1)} times a seed, removing "
            f"{num(o['lost_link_isolation_h_saved_per_seed'])} vehicle-hours of isolation. No count of lost awards "
            f"changed, and the first clause of H14 gives the same difference before the correction, with messages "
            f"still undelivered at the end of the month counted as lost, and under the return rule the code had "
            f"before the review, which is kept as a variant (mean age {secs(pre['aoi_mean_s'], 1)})." + window_note)
    fill("P1-E54-CORRECTION-SENTENCE", correction_sentence, "E54 (code review, 13 Nov)")

    def ledger_sentence():
        L = p.e54l
        if L is None:
            raise Pending("the 61-day ledger replay (results/E54_ledger.json) has not run")
        down = L["longest_earth_down_d"]
        rows = L["rows"]
        n_seeds = len(p.e54["seeds"]) if p.e54 is not None else 30
        check(all(x["bundles"] % n_seeds == 0 for x in rows) and len({x["bundles"] for x in rows}) == 1,
              "the ledger file holds the same number of bundles in every row, a multiple of the seeds")
        n_b = rows[0]["bundles"] // n_seeds
        dr = [x["lost_share"] for x in rows if x["protocol"] == "drop_retry"]
        sf = {}
        for x in rows:
            if x["protocol"] == "sf":
                sf.setdefault(x["lifetime_d"], set()).add(x["lost_share"])
        check(max(dr) - min(dr) < 0.01, "drop-and-retry loses the same share of ledger bundles whatever the lifetime")
        check(all(len(v) == 1 for v in sf.values()), "the ledger's loss under store-and-forward does not depend on the per-hop loss")
        short = sorted(d for d in sf if d < down)
        long_ = sorted(d for d in sf if d > down)
        check(short == [14.0] and len(long_) == 2, "one ledger lifetime is shorter than the longest Earth-down stretch and two are longer")
        check(all(max(sf[d]) == 0 for d in long_) and max(sf[14.0]) > 0, "a lifetime longer than the longest Earth-down stretch loses no ledger bundle")
        return (
            f"The daily ledger bundle to Earth was replayed over 61 days ({n_b} bundles; the replay does not "
            f"depend on the seed, and the file repeats it for each), in which the longest stretch without Earth "
            f"was {num(down, 1)} days (the imposed blackout together with the natural gaps next to it). Drop and "
            f"retry lost {sh(np.mean(dr))} of the bundles whatever their lifetime. Store and forward lost "
            f"{sh(max(sf[14.0]))} with the 14-day lifetime first chosen and none with a lifetime of "
            f"{num(long_[0], 1)} or {num(long_[1])} days: the lifetime of an Earth-bound bundle must exceed the "
            f"longest stretch without Earth, a sizing rule for the network's design [44].")
    fill("P1-E54-LEDGER-SENTENCE", ledger_sentence, "E54 ledger")

    def ledger_design():
        L = p.e54l
        if L is None or p.e54 is None:
            raise Pending("the 61-day ledger replay (results/E54_ledger.json) has not run")
        check("earth_up_share_61d" in L, "the ledger replay covers 61 days")
        lives = sorted({x["lifetime_d"] for x in L["rows"]})
        return (f"The Earth-bound ledger, one bundle of {num(p.e54['ledger_bytes'] / 1000)}{NB}kB a day (Assumed), is "
                f"replayed separately over 61 days with lifetimes of "
                + listing(num(d, 0 if abs(d - round(d)) < 1e-9 else 1) for d in lives) + " days.")
    fill("P1-E54-LEDGER-DESIGN", ledger_design, "E54 ledger")

    def table():
        rows = []
        for l in (0.10, 0.25, 0.40):
            for k, name in E54_NAMES.items():
                x = p.row54(l, k)
                rows.append([f"{l:.2f}", name, f"{x['award_lost']}", num(x["award_delay_mean_s"], 1),
                             f"{x['grant_lost']:,}", f"{x['task_state_lost']:,}", num(x["task_state_delay_mean_s"]),
                             num(x["aoi_mean_s"]), num(x["aoi_worst_vehicle_s"] / 3600, 2),
                             "not counted" if k == "sf_ll" else f"{x['stuck_reservations']:,} ({num(x['stuck_hours'])}{NB}h)"])
        x = p.row54(0.25, "sf")
        prm = p.e54["parameters"]
        return _tab(
            f"<b>Table 11.</b> E54: a message-level replay of one recorded month, {len(p.e54['seeds'])} seeds. Counts "
            f"are sums over the seeds, out of {x['award_n']:,} awards, {x['grant_n']:,} grants (one generated for "
            f"every award) and {x['task_state_n']:,} end-of-job reports. Drop and retry makes at most "
            f"{prm['max_tries']} tries {secs(prm['retry_s'])} apart; store and forward repeats every "
            f"{secs(prm['custody_timer_s'])} until the message's lifetime ends (both Assumed, not swept). The age of "
            f"information is the age of the newest status report the base holds for a vehicle. A message is lost "
            f"when its lifetime ends undelivered by the month's end; one still alive and undelivered at the month's "
            f"end is censored and not counted as lost, and no award, grant or report was. The values are those "
            f"after the correction of 13 November 2026 (Section 5.9); the earlier table is kept in the results "
            f"file. The last column "
            f"counts reservations that ended while their holder was out of the base's reach, so that the segment "
            f"stays unconfirmed, with the hours until the holder was heard again; no vehicle was still inside a "
            f"segment. It does not depend on the transport or the loss rate, and it was not counted for the rows "
            f"with the return to the last link point, in which the return is applied to the contact plan and not "
            f"to the vehicles' jobs.",
            ["Per-hop loss", "Transport", "Awards lost (lost jobs)", "Award delay, mean (s)", "Grants lost",
             "End-of-job reports lost", "their delay, mean (s)", "Age at the base, mean (s)", "worst vehicle (h)",
             "Segments left unconfirmed (hours unconfirmed)"], rows, cls="wide")
    fill("P1-TABLE-E54", table, "E54")

    def family_sentence():
        F = p.family()
        H = F["hypotheses"]
        tested = sorted(k for k, v in H.items() if "holm" in v)
        untested = sorted(k for k, v in H.items() if "holm" not in v)
        check(sorted(H) == ["H10", "H13", "H14", "H15a", "H9"], "the Phase 6 family holds H9, H10, H13, H14 and H15a")
        check(tested == ["H10", "H14", "H15a"] and untested == ["H13", "H9"],
              "Holm's correction covers H10, H14 and H15a; H9 and H13 are listed without a test")
        check(abs(F["alpha"] - 0.05) < 1e-12, "the family is corrected at alpha 0.05")
        return (
            f"Both sit in that file's confirmatory family with H9&prime;, H10&prime; and H15a, which are reported in "
            f"the companion paper [45]. The registration asks for Holm's procedure [52] across all five. It is "
            f"applied at &alpha;&nbsp;=&nbsp;{F['alpha']:g} to the three that have a sampling test, H10&prime;, H14 "
            f"and H15a; H9&prime; and H13 are comparisons with a threshold and are listed without a test, which is "
            f"a change from the registered family. For the correction H14 is tested by an exact sign test on the "
            f"lost jobs per seed. That test was added after the results were seen; the registered rule, a paired "
            f"interval that excludes zero, gives the same verdict [54].")
    fill("P1-P6-FAMILY-SENTENCE", family_sentence, "Phase 6 family")

    def holm_sentence():
        F, h = p.family(), p.h14()
        H = F["hypotheses"]
        f14, f10, f15 = H["H14"], H["H10"], H["H15a"]
        n = f14["seeds_fewer"] + f14["seeds_more"] + f14["seeds_tied"]
        check(n == h["difference_sf_ll_minus_drop_retry"]["n"]
              and abs(f14["mean_diff_jobs"] - h["difference_sf_ll_minus_drop_retry"]["mean"]) < 1e-9,
              "the family file tests the same per-seed lost jobs as E54")
        check(f14["holm"]["p_adjusted"] >= f14["p"], "Holm's adjusted p is not below the raw p")
        # Referee S1: the file's p is one-sided (0.5^9 with no seed the other way); every other p here is two-sided
        nz = f14["seeds_fewer"] + f14["seeds_more"]
        one_sided = sum(math.comb(nz, i) for i in range(f14["seeds_fewer"], nz + 1)) / 2 ** nz
        check(abs(one_sided - f14["p"]) < 1e-9, "the family file's sign-test p for H14 is the one-sided exact p")
        two_sided = min(1.0, 2 * one_sided)
        ps = sorted([("H14", two_sided), ("H15a", float(f15["p"])), ("H10", float(f10["p_intersection_union"]))], key=lambda q: q[1])
        adj, run = {}, 0.0
        for i, (nm, pv) in enumerate(ps):
            run = max(run, min(1.0, (len(ps) - i) * pv))
            adj[nm] = run
        check(abs(adj["H15a"] - f15["holm"]["p_adjusted"]) < 1e-9 and abs(adj["H10"] - f10["holm"]["p_adjusted"]) < 1e-9,
              "Holm's procedure recomputed here gives the family file's adjusted p for H15a and H10'")
        ok14 = bool(f14["holm"]["rejected_at_0.05"]) and adj["H14"] < 0.05 and f14["mean_diff_jobs"] < 0
        check(bool(f15["holm"]["rejected_at_0.05"]) and not bool(f10["holm"]["rejected_at_0.05"])
              and "not supported" in F["summary"]["H10"], "in the family H15a is supported and H10' is not supported as a whole")
        upper = "upper bound" in str(f15.get("p_note", ""))
        # Second pass after the code review (14 Nov): E50 was regenerated with the positioning fix and the family file
        # rebuilt from it; the earlier H10' value is read from the file's superseded block and named once.
        sk = [k for k, v in F.items() if k.startswith("superseded_") and isinstance(v, dict) and "n15" in k]
        if len(sk) != 1:
            raise KeyError(f"phase6_family.json: expected one superseded block for the positioning fix, found {sk}")
        o10 = F[sk[0]]["hypotheses"]["H10"]
        check("positioning fix" in str(F[sk[0]].get("reason", "")), "the family file's superseded block is the one of the positioning fix")
        check(bool(o10["holm"]["rejected_at_0.05"]) == bool(f10["holm"]["rejected_at_0.05"])
              and pfmt(o10["holm"]["p_adjusted"]) != pfmt(f10["holm"]["p_adjusted"]),
              "H10' has the same verdict before and after the positioning fix, at another adjusted p")
        check(all(F[sk[0]]["hypotheses"][k]["holm"] == H[k]["holm"] for k in ("H14", "H15a")),
              "the positioning fix did not move H14 or H15a in the family")
        prim = f10["clauses"]["layered within 1.5x of perfect at 1x (TOST)"]["p"]
        grow = f10["clauses"]["the gap grows with the fleet (4x and 8x)"]
        check(prim < 0.05 and grow["p_one_sided_4x"] > 0.05 and grow["p_one_sided_8x"] > 0.05
              and abs(f10["p_intersection_union"] - max(grow["p_one_sided_4x"], grow["p_one_sided_8x"],
                                                        f10["clauses"]["dead reckoning with the margin larger at 1x"]["p_one_sided"])) < 1e-12,
              "H10's equivalence clause holds and its growth clause does not, at four and at eight times the fleet")
        check("e50_code" in F and not any("not_rerun" in str(k) for k in F), "the family file is built from one regenerated E50")
        open10 = any("pending" in str(k) or "not yet run" in json.dumps(v) for k, v in f10["clauses"].items())
        more = "none" if f14["seeds_more"] == 0 else f"{f14['seeds_more']}"
        return (
            f"In the family of the second pre-registration, the difference in lost jobs is tested by an exact sign "
            f"test over the {n} seeds: fewer with store and forward and the return in {f14['seeds_fewer']} seeds, "
            f"more in {more}, the same in {f14['seeds_tied']} (one-sided p&nbsp;{p_eq(f14['p'])}; two-sided "
            f"p&nbsp;{p_eq(two_sided)}). Holm's correction over the three hypotheses of that family with a sampling "
            f"test gives an adjusted p of {pfmt(f14['holm']['p_adjusted'])} on the one-sided p and "
            f"{pfmt(adj['H14'])} on the two-sided one, so the first clause of H14 "
            f"{'stands' if ok14 else 'does not stand'} after the correction, against the baseline described above. "
            f"Of the other two, H15a is supported (adjusted p&nbsp;{'at most ' + pfmt(f15['holm']['p_adjusted']) if upper else p_eq(f15['holm']['p_adjusted'])}) "
            f"and H10&prime; is not supported as a whole (adjusted p&nbsp;{p_eq(f10['holm']['p_adjusted'])}"
            + (", on the fleet sizes run when the family file was built, which do not include the largest" if open10 else "")
            + f"; {p_eq(o10['holm']['p_adjusted']).replace('=&nbsp;', '')} before the position experiment behind it was "
              f"regenerated after a correction to its positioning code, found in a code review on 13 November 2026"
            + "); both are reported in the companion paper [45].")
    fill("P1-E54-HOLM-SENTENCE", holm_sentence, "Phase 6 family")

    def h13_draws_sentence():
        F = p.family()
        c = F["hypotheses"]["H13"]["clauses"]
        h01 = p.e53_v01["h13"]
        check(abs(c["1 Hz"]["busiest_kbps_p95"] - h01["at_1hz_kbps_p95"]) < 1e-3
              and abs(c["10 Hz"]["busiest_kbps_p95"] - h01["at_10hz_kbps_p95"]) < 1e-3,
              "the family file's H13 values are those of E53 with the v0.1 sizes")
        check(bool(p.v02["h13_check_v02"]["same_verdict_as_v0.1"]), "H13 falls on the same side of the threshold with the v0.2 sizes")
        a, b = c["1 Hz"]["draws_on_predicted_side"], c["10 Hz"]["draws_on_predicted_side"]
        every = a == 1.0 and b == 1.0
        check(every == ("every draw" in F["summary"]["H13"]), "the family file's H13 summary matches its draws")
        return ((f"That each clause held in every one of the {p.e53['draws']} draws carries no information for the "
                 f"first clause, which no draw could have failed" if every else
                 f"The first clause held in {sh(a)} of the {p.e53['draws']} draws and the second in {sh(b)}")
                + ". H13 has no sampling test, and Holm's correction of the second pre-registration's family does "
                  "not include it.")
    fill("P1-E53-DRAWS-SENTENCE", h13_draws_sentence, "Phase 6 family")

    def abstract_clause():
        h, prm = p.h14(), p.e54["parameters"]
        d = h["difference_sf_ll_minus_drop_retry"]
        rdr, rsf, rll = (p.row54(LOSS, k) for k in ("drop_retry", "sf", "sf_ll"))
        if d["ci"][1] < 0:
            return (f"drop-and-retry capped at {words(prm['max_tries'])} tries lost {rdr['award_lost']} of "
                    f"{rdr['award_n']:,} awards at {num(100 * LOSS)}{PCT} message loss; store-and-forward that "
                    f"retries for the whole lease lost {rsf['award_lost']}, and "
                    f"{'none' if rll['award_lost'] == 0 else rll['award_lost']} when unheard vehicles were assumed "
                    f"to return to their last link point")
        return "store-and-forward did not lose measurably fewer awarded jobs than drop-and-retry"
    fill("P1-E54-ABSTRACT-CLAUSE", abstract_clause, "E54")

    def short_clause():
        """The same counts in fewer words, for the abstract and the conclusion (their word limits)."""
        h, prm = p.h14(), p.e54["parameters"]
        rdr, rsf, rll = (p.row54(LOSS, k) for k in ("drop_retry", "sf", "sf_ll"))
        if h["difference_sf_ll_minus_drop_retry"]["ci"][1] < 0:
            return (f"drop-and-retry capped at {words(prm['max_tries'])} tries lost {rdr['award_lost']} of "
                    f"{rdr['award_n']:,} awards at {num(100 * LOSS)}{PCT} loss, store-and-forward {rsf['award_lost']}, "
                    f"and {'none' if rll['award_lost'] == 0 else rll['award_lost']} when unheard vehicles were assumed "
                    f"to return to their last link point")
        return "store-and-forward did not lose measurably fewer awarded jobs than drop-and-retry"
    fill("P1-E54-SHORT-CLAUSE", short_clause, "E54")

    def aoi_clause():
        sf, ll = p.row54(LOSS, "sf"), p.row54(LOSS, "sf_ll")
        return (f"the base's picture of a vehicle was {num(sf['aoi_mean_s'] / 60)}{NB}min old on average without the "
                f"return to the last link point and {secs(ll['aoi_mean_s'], 1)} with it, a gain counted without the "
                f"jobs the return would interrupt")
    fill("P1-E54-AOI-CLAUSE", aoi_clause, "E54")


def phase6_props(p, st, r, V, fill, check):
    """The worked numbers and data checks of Propositions 1 and 3 to 6 (Appendix B); Proposition 2's are in phase6_e53."""
    # --- Proposition 1: the small-instance check per depth, and the tight example ------------------------------
    b = r.bounds["cbba_lite_vs_optimum"]
    deep_keys = sorted(k for k in b if k != "1")
    d1, deep = b["1"]["score_share_min"], min(b[k]["score_share_min"] for k in deep_keys)
    check(d1 >= 0.5 and not b["1"]["below_half"], "at depth 1 no small instance fell below half the optimum (Proposition 1a)")
    check(deep >= 1 / 3, "at greater depth no small instance fell below a third of the optimum (Proposition 1c)")
    check(r.bounds["items_assigned_twice"] == 0, "no item was assigned twice in the small instances")
    V["P1-BOUNDS-CBBA-MIN-D1"], V["P1-BOUNDS-CBBA-MIN-DEEP"] = sh(d1, 1), sh(deep, 1)
    V["P1-BOUNDS-CBBA-DEPTHS"] = listing(deep_keys)
    eps = 0.01                                                  # the 2 x 2 instance that shows 1/2 cannot be raised
    W = [[1 + eps, 1.0], [1.0, 0.0]]
    i, j = max(((a, c) for a in range(2) for c in range(2)), key=lambda q: W[q[0]][q[1]])
    greedy = W[i][j] + W[1 - i][1 - j]
    best = max(W[0][0] + W[1][1], W[0][1] + W[1][0])
    check(abs(greedy - (1 + eps)) < 1e-12 and abs(best - 2) < 1e-12, "the 2 x 2 example gives 1 + epsilon against 2")

    # --- Proposition 3: age of information over k hops (lunarsim/atc/messages.py: independent loss, no retry) ----
    T, D = 1.0, float(p.messages.HOP_LATENCY_S)
    losses, hops, eps3 = [float(x) for x in p.messages.LOSS_LEVELS], (1, 3, 5), 1e-3

    def age(pl, k):
        q = (1 - pl) ** k
        m = 1 if q >= 1 else max(1, math.ceil(math.log(eps3) / math.log(1 - q) - 1e-12))
        return k * D + T * (2 - q) / (2 * q), k * D + T * m
    rng = np.random.default_rng(3)                              # the formula against a direct simulation of the model
    ok = (rng.random((400_000, 3)) >= 0.25).all(axis=1)
    X = np.diff(np.nonzero(ok)[0]) * T
    sim = 3 * D + float((X ** 2).sum() / (2 * X.sum()))
    check(abs(sim - age(0.25, 3)[0]) < 0.02 * sim, "Proposition 3's mean age equals a direct simulation of its model within 2 %")
    check(float((X > age(0.25, 3)[1] - 3 * D + 1e-9).mean()) < 2e-3, "the 99.9 % age bound holds in the simulation")
    rows = [[f"{pl:.2f}"] + [f"{num(age(pl, k)[0], 2)}{NB}s; {num(age(pl, k)[1], 1)}{NB}s" for k in hops] for pl in losses]
    V["P1-TABLE-PROP3"] = _tab(
        f"<b>Table B1.</b> Proposition 3(a) for a report sent every {num(T)}{NB}s with {num(1000 * D)}{NB}ms per hop "
        f"(the engine's value, Assumed): mean age at the receiver, and the age exceeded {num(100 * eps3, 1)}{PCT} "
        f"of the time, by per-hop loss and number of hops.",
        ["Per-hop loss"] + [f"{k} hop" + ("s" if k > 1 else "") for k in hops], rows)
    a403, a251 = age(0.40, 3), age(0.25, 1)
    V["P1-PROP3-EXAMPLE-SENTENCE"] = (
        f"At per-hop loss 0.40 over three hops the mean age of a 1{NB}Hz report is {num(a403[0], 1)}{NB}s and it "
        f"exceeds {num(a403[1])}{NB}s one time in a thousand; for a direct neighbour at loss 0.25 the two figures are "
        f"{num(a251[0], 2)}{NB}s and {num(a251[1], 1)}{NB}s.")

    def prop3_e54():
        sf, ll = p.row54(0.25, "sf"), p.row54(0.25, "sf_ll")
        return (f"E54's ages are of kind (b): the worst vehicle's {num(sf['aoi_worst_vehicle_s'] / 3600)}{NB}h "
                f"without the lost-link rule is its longest stretch with no path to the base, and the rule shortens "
                f"that stretch to {secs(ll['aoi_worst_vehicle_s'])} (Section 5.9).")
    fill("P1-PROP3-E54-SENTENCE", prop3_e54, "E54")

    # --- Proposition 4: hand-over after a failure (inputs: dev_notes.json, each with its source) -----------------
    # Referee S5: the example uses the protocol's own heartbeat (HELLO at 1 Hz whenever nothing else was sent), and
    # it includes what Section 3.13 puts between "silent" and the re-auction: a second, longer timeout to which the
    # design gives no value, bounded by the lease after which a silent vehicle's job returns to the pool (E54's).
    q4 = r.dev["prop4_inputs"]
    Thb, k = q4["heartbeat_s"], int(q4["misses_k"])
    hello = next(m for m in p.schema["messages"] if m["name"] == "HELLO")
    check(hello["default_rate"].startswith("1 Hz") and abs(Thb - 1.0) < 1e-9,
          "Proposition 4's heartbeat period is the protocol's HELLO rate, 1 Hz")
    det_mean, det_max = (k - 0.5) * Thb, k * Thb
    fa = lambda pl, kk: 86400.0 / Thb * (1 - pl) * pl ** kk                    # false "silent" marks per watcher and day
    kmin = lambda pl: next(kk for kk in range(1, 200) if fa(pl, kk) < 1.0)
    auct = q4["auction_rounds"] * q4["round_s"]
    appr_min = q4["approach_km"] / q4["approach_kmh"] * 60.0
    xfer_min = q4["cargo_aboard_prob"] * q4["transfer_h"] * 60.0
    sight_min = (det_mean + auct) / 60.0 + appr_min + xfer_min                  # if a sighting confirms the failure at once
    from lunarsim.engine import TEAM_SETUP_H
    check(abs(TEAM_SETUP_H - q4["transfer_h"]) < 1e-9, "Proposition 4's transfer time is the engine's coupling time")
    G, W = q4["earth_gap_d"] * 24.0, q4["earth_window_d"] * 24.0
    earth_h = G * G / (2 * (G + W))

    def prop4_example():
        if p.e54 is None:
            raise Pending("E54 (results/E54_dtn.json) has not run: Proposition 4's lease is read from it")
        lease_min = p.e54["parameters"]["lease_s"] / 60.0
        total_min = lease_min + auct / 60.0 + appr_min + xfer_min
        check(earth_h * 60 > 10 * total_min, "waiting for Earth costs more than ten times the hand-over on the Moon")
        check(det_mean + auct < 60, "detection and auction are seconds, so the lease sets the hand-over")
        return total_min, lease_min, (
            f"The protocol's heartbeat is {secs(Thb)}: a vehicle sends <code>HELLO</code> whenever it would otherwise "
            f"send nothing in a second (Table A2). With <i>k</i>&nbsp;=&nbsp;{k} (Assumed), a failed vehicle is "
            f"marked silent after {secs(det_mean, 1)} on average and at most {secs(det_max)}. One rover watching one "
            f"live rover raises {num(fa(0.10, k), 2)} false marks a day at loss 0.10 and {num(fa(0.40, k))} at 0.40; "
            f"keeping them below one a day needs <i>k</i>&nbsp;=&nbsp;{kmin(0.10)}, {kmin(0.25)} and {kmin(0.40)} at "
            f"loss 0.10, 0.25 and 0.40. Being marked silent does not hand the job over. By Section 3.13 the base "
            f"marks the vehicle failed only after a second, longer timeout or a sighting, and the design gives that "
            f"timeout no value; a silent vehicle's job returns to the pool when its lease ends, at most "
            f"{num(lease_min)}{NB}min after it was last heard with the lease of E54. With that lease, "
            f"{words(q4['auction_rounds'])} auction rounds of {secs(q4['round_s'])}, a new winner "
            f"{q4['approach_km']:g}{NB}km away at {q4['approach_kmh']:g}{NB}km/h, and cargo aboard the failed rover "
            f"with probability {q4['cargo_aboard_prob']:g} and a {q4['transfer_h']:g}{NB}h transfer (all Assumed), "
            f"the expected extra wait is up to {num(lease_min)}{NB}min + {secs(auct)} + {num(appr_min, 1)}{NB}min + "
            f"{num(xfer_min)}{NB}min = {num(total_min, 1)}{NB}min, about {h_(total_min / 60)}. If a sighting "
            f"confirmed the failure at once it would be {secs(det_mean, 1)} + {secs(auct)} + "
            f"{num(appr_min, 1)}{NB}min + {num(xfer_min)}{NB}min = {num(sight_min, 1)}{NB}min. Detection and auction "
            f"are seconds in both cases, so a shorter heartbeat would buy nothing; the lease sets the wait.")
    fill("P1-PROP4-EXAMPLE-SENTENCE", lambda: prop4_example()[2], "E54")
    fill("P1-PROP4-EARTH-SENTENCE", lambda: (
        f"With gaps of {q4['earth_gap_d']:g} days and windows of {q4['earth_window_d']:g} days at this base [42], "
        f"the wait for Earth alone is {num(earth_h, 1)}{NB}h, {num(earth_h * 60 / prop4_example()[0])} times the "
        f"hand-over on the Moon with the lease and {num(earth_h * 60 / sight_min)} times the one after a sighting."),
        "E54")
    fill("P1-PROP4-TOTAL-H", lambda: h_(prop4_example()[0] / 60), "E54")
    V["P1-PROP4-EARTH-H"] = f"{num(earth_h)}{NB}h"

    # --- Proposition 5: operators against fleet size and autonomy level (a model; inputs in dev_notes.json) -----
    q5 = r.dev["prop5_inputs"]
    rho, fleets = q5["rho_max"], q5["fleets"]
    rows = [["Waypoint driving from Earth (VIPER's plan [76])", "continuous", "continuous",
             f"{num(1 / q5['viper_people_per_rover'], 2)}"] + [f"{q5['viper_people_per_rover'] * n}" for n in fleets]]
    fan = []
    for lv in q5["levels"]:
        lam, hh = lv["requests_per_vehicle_h"], lv["handling_min"] / 60.0
        fan.append(rho / (lam * hh))
        rows.append([html.escape(lv["name"]), f"{lam:g}", f"{lv['handling_min']:g}", num(fan[-1], 1)]
                    + [f"{math.ceil(n * lam * hh / rho - 1e-12)}" for n in fleets])
    check(fan == sorted(fan), "the fan-out grows with the autonomy level")
    V["P1-PROP5-RHO"] = f"{rho:g}"
    V["P1-TABLE-PROP5"] = _tab(
        f"<b>Table B2.</b> Proposition 5 evaluated: vehicles per operator and operators on console for "
        f"{listing(fleets)} vehicles, by autonomy level, with operators loaded to at most {rho:g} of their time. "
        f"The request rates and handling times are Assumed and were chosen so that the result lands near the "
        f"published ratios named in the text: the table checks that the formula can be made consistent with those "
        f"ratios, and it predicts nothing. The first row is VIPER's planned staffing, not the formula.",
        ["Autonomy level", "Requests per vehicle-hour", "Minutes per request", "Vehicles per operator"]
        + [f"Operators for {n}" for n in fleets], rows)

    # --- Proposition 6: the position report, field by field (schema), against the codec ------------------------
    pos = next(m for m in p.schema["messages"] if m["name"] == "POSITION")
    rows, counts, total = [], [], 0
    for f in pos["fields"]:
        name, typ, bits, scale, unit = f[:5]
        total += bits
        if typ == "spare":
            rows.append(["spare", "zero; left by byte alignment", f"{bits}", "&ndash;", "&ndash;"])
            continue
        if typ.startswith("enum"):
            n = sum(1 for kk in p.schema["enums"][typ.split(":")[1]] if kk.isdigit())
            what = f"one of {n} sources"
        elif name == "heading":
            n = round(360 / scale)
            what = f"0 to {360 - scale:g}&deg; in steps of {scale:g}&deg;"
        elif name == "u95_code":
            n = 1 << bits
            what = "a code for the 95&#8239;% horizontal uncertainty, 0.05&nbsp;m to 1.95&nbsp;km on a logarithmic scale, with codes for larger and for unknown"
        elif name == "sigma_h":
            n = 1 << bits
            what = f"0 to {((1 << bits) - 2) * scale:g}{NB}m in steps of {scale:g}{NB}m, and one code for unknown"
        else:
            what, n = _field_range(f[:5])
            if typ == "uint":
                what = what.replace(" in steps", f"{NB}{html.escape(unit)} in steps") + f"{NB}{html.escape(unit)}"
        counts.append(n)
        rows.append([f"<code>{name}</code>", what, f"{bits}", f"{n:,}", f"{math.ceil(math.log2(n))}"])
    need = sum(math.ceil(math.log2(n)) for n in counts)
    joint = sum(math.log2(n) for n in counts)
    sizes = p.codec.size_table()["POSITION"]
    gold = {(x["profile"], x["auth"]): x["bytes"] for x in p.conf["vectors"] if x["message"] == "POSITION"}
    fr = p.schema["framing"]
    over = fr["space_packet"]["bytes"] + fr["lrip_header"]["bytes"] + fr["security_header"]["bytes"] + fr["trailer"]["mac8"]
    check(total == 104 and sizes["payload"] * 8 == total, "the position report's fields add up to 104 bits, 13 bytes")
    check(sizes["payload"] == 13 and sizes["mac8"] == 41 == sizes["payload"] + over, "the codec counts 13 B of content and 41 B secured")
    check(gold[("N", "mac8")] == sizes["mac8"] and gold[("N", None)] == sizes["unsecured"], "the golden position packets have the codec's sizes")
    check(math.ceil(joint) == need == total and need / 8 == sizes["payload"],
          "the fields need every bit of the layout, jointly and field by field, which is 13 whole bytes")
    check(8 * (sizes["payload"] - 1) < joint, "twelve bytes are fewer bits than the fields need jointly")
    rows.append(["<b>Total</b>", "", f"<b>{total}</b>", "", f"<b>{need}</b>"])
    V["P1-TABLE-PROP6"] = _tab(
        "<b>Table B3.</b> The position report field by field, from the schema file: range and step, bits used, the "
        "number of values the field must tell apart, and the bits that number needs.",
        ["Field", "Range and step", "Bits", "Values", "Bits needed"], rows)
    V["P1-PROP6-BITS"], V["P1-PROP6-NEED-BITS"], V["P1-PROP6-JOINT-BITS"] = f"{total}", f"{need}", f"{joint:.1f}"
    # Referee S6: for most fields the number of values is 2^bits because the range was set by the bit width
    real = [f for f in pos["fields"] if f[1] != "spare"]
    defin = [f[0] for f, n in zip(real, counts) if n == 1 << f[2]]
    other = [f[0] for f, n in zip(real, counts) if n != 1 << f[2]]
    check(len(real) == len(counts) and len(defin) + len(other) == len(real), "every field of the position report is classed")
    step_pos = next(f[3] for f in real if f[0] == "e")
    step_sig = next(f[3] for f in real if f[0] == "sigma_h")
    V["P1-PROP6-DEFINITIONAL-SENTENCE"] = (
        f"What the count proves is limited. For {words(len(defin))} of the {words(len(real))} fields ("
        + listing(f"<code>{n}</code>" for n in defin) + f") the number of values is two to the power of the field's "
        f"bits, because we set the range by the bit width; for those the lower bound is definitional. Only "
        + listing(f"<code>{n}</code>" for n in other) + f" have a count that is not a power of two, which is why the "
        f"joint count is {joint:.1f} bits, which rounds up to the {need} the layout uses. The steps are also not matched to one another: the "
        f"position step is {num(100 * step_pos)}{NB}cm and the step of its own uncertainty {num(100 * step_sig)}{NB}cm. "
        f"A coarser position step or a smaller site grid would save bits, so {nbytes(sizes['payload'])} is the size "
        f"of this layout and not a lower bound for a position report in general.")
    V["P1-PROP6-SPARE-BITS"] = f"{total - need}"
    V["P1-PROP6-CONTENT-B"], V["P1-PROP6-SECURED-B"] = nbytes(sizes["payload"]), nbytes(sizes["mac8"])
    V["P1-PROP6-MAC16-B"], V["P1-PROP6-UNSEC-B"] = nbytes(sizes["mac16"]), nbytes(sizes["unsecured"])
    V["P1-PROP6-CBOR-B"] = nbytes(gold[("B", "mac8")])
    check(gold[("N", "mac8")] == p.e53_v01["sizes"]["POSITION"]["mac8"], "the position packet has the size it had in v0.1")

    # --- the leader's election time (3.6, 3.13): what the engine assumes -----------------------------------------
    reg = p.regimes.DEFAULTS
    n_fail = 8760.0 / (reg["base_mtbf_h"] + reg["base_repair_h"])
    check(reg["reelect_h"] == 0.5 and reg["base_mtbf_h"] == 2000.0 and reg["base_repair_h"] == 24.0,
          "the engine's base-computer constants are those the text types")
    V["P1-LEADER-N-FAIL-YEAR"] = num(n_fail, 1)
    V["P1-LEADER-ELECTION-H-YEAR"] = h_(n_fail * reg["reelect_h"])


def phase6_proved(p, r, V, fill, check, ctx, e53):
    """The "Proved, tested, assumed" table (Section 6.6): one row per claim; verdict words come from the data.
    Decision A1 of the referee round: a result that could not have come out otherwise (arithmetic on assumed inputs,
    a property of a rule or of the model, a count fixed by the design) is "calculated from assumed inputs" or "a
    property of the model", never "tested" or "supported"."""
    def table():
        n1, n2 = int(r.pair("H1", LOAD_MAIN)["n"]), int(r.pair("H2_pooled", LOAD_MAIN)["n"])
        n3, n4 = int(r.pair("H3a", LOAD_MAIN)["n"]), int(r.pair("H4_LIN", LOAD_MAIN)["n"])
        n6 = int(r.pair("H6_team_items", LOAD_MAIN, team="10", loss="0.1")["n"])
        n_years = len(r.fit("hypotheses", "H2", str(LOAD_MAIN), "visibility"))
        h14 = p.h14()
        d14 = h14["difference_sf_ll_minus_drop_retry"]
        f14 = p.family()["hypotheses"]["H14"]
        prm = p.e54["parameters"]
        rdr = p.row54(0.25, "drop_retry")
        n_res = round(p.e54["reservations_per_seed"] * len(p.e54["seeds"]))
        bn = r.bounds
        check("10 x 10 square" in str(bn.get("model", "")), "the small instances use a toy score on a 10 x 10 square")
        cf = r.dev["capability_filter_check"]
        reg = p.regimes.DEFAULTS
        mlp30, lin30 = r.pair("H4_MLP", LOAD_MAIN), r.pair("H4_LIN", LOAD_MAIN)
        check(mlp30["hi"] >= 0 and lin30["hi"] < 0, "H4: the network's interval includes zero, the linear model's does not")
        R = [
            ("Pooling vehicles across owners cuts the mean urgent wait (H1)",
             f"Tested: E40, {n1} paired seeds, {LOAD_MAIN}{PCT} load, both sides with Earth always in view. Supported. "
             f"The size of the difference follows from two inputs: one owner has no cargo rover, and cargo not "
             f"delivered counts with its wait to the end of the one-year run.", "5.2, 7"),
            ("A pooled dispatcher on Earth that stops at every blackout keeps urgent cargo waiting longer than one "
             "that never stops, by more than 10&#8239;% (H2)",
             f"Tested: E40, {n2} paired runs over {words(n_years)} start years, on the yardstick as revised in "
             f"change 2 after a five-seed development run. Supported; the yardstick first registered "
             f"{V['P1-H2-OLD-YARDSTICK-MET']}.", "5.3, 4.6"),
            ("The robots' auction is within &plusmn;10&#8239;% of the full-information marketplace at message loss "
             "0.10 (H3a)",
             f"Tested: E40, {n3} paired seeds. Equivalence {'shown' if ctx['equiv'] else 'not shown'}"
             + ("." if ctx["equiv"] else "; the difference is also not distinguishable from zero."
                if r.pair("H3a", LOAD_MAIN)["lo"] < 0 < r.pair("H3a", LOAD_MAIN)["hi"] else ".")
             + V["P1-B117A-CLAIM"], "5.4"),
            ("Learned bids beat hand-built bids on seeds not used for training or selection (H4)",
             f"Tested: E40, {n4} seeds. Not supported for the network, the registered model, which was trained with "
             f"less freedom. Supported for the linear model, which the registration names as the secondary model "
             f"and which entered the Holm family after its result on these seeds had been seen."
             + V["P1-B117C-CLAIM"], "5.6, 4.6, 7"),
            ("Pairs of different owners raise the share of items delivered (H6, first part)",
             f"Tested: E42, {n6} seeds per cell. Supported, on the share of cargo mass and on items. The share of "
             f"team items that same-owner pairs can lift is an input.", "5.7"),
            ("Without a commit step failed meetings rise under loss (H6, second part)",
             "A property of the model: no message is repeated inside a handshake, so the two failure probabilities "
             "follow from the message count. Measured in E42: what the commit step costs in urgent wait.", "5.7"),
            ("In the auction the lowest bid of each connected part of the network always wins its load; message loss "
             "adds parallel winners and wasted trips",
             "A property of the model: the auction is simulated round by round, not message by message. A "
             "message-level implementation, in which the best bid can go unheard, could do worse.", "3.7, 7"),
            ("Message loss, bundle depth, radio range, the lost-link rule and a second mast move the on-Moon regimes "
             "as reported (H3b, H3c, exploratory)",
             "Tested: E41, 30 seeds per cell, one factor at a time around the auction at the middle load. E41 has "
             "no cell with deeper bundles and no loss." + V["P1-B117B-CLAIM"], "5.5"),
            ("The linear bids keep their sign outside the training range; whether other cargo pays for the gain",
             f"Tested on ten seeds per cell. Sign outside the range: "
             + ("on the engine with the dispatch fixed point" if r.ood_rerun else "values that predate the two engine fixes, not rerun")
             + f". Other cargo ({V['P1-LEARNED-EVAL-LABEL']}): no cost at {LOAD_HEAVY}{PCT} load; {V['P1-GUARD-30-CLAUSE']}. "
             f"The policies were trained without the fixed point and not retrained.", "5.6, 4.6, 7"),
            ("With perfect links and depth 1 the auction reproduces the marketplace's event trace; with every new "
             "feature off the engine reproduces the earlier papers",
             f"Tested: exact comparison of event traces, and {r.dev['regression_check']['rows_rerun_identical']} "
             f"earlier result rows rerun with no difference.", "3.11"),
            ("One auction round with one job per robot reaches at least half the best total score (Proposition 1a)",
             f"Proved. Assumes non-negative pair scores, the best remaining pair fixed first, and bids that reach "
             f"every bidder; loads of several items are outside it. The score is measured down from a ceiling bid: "
             f"the proposition gives no bound on cost or waiting, where a greedy round can be arbitrarily worse "
             f"than the best. Checked on {bn['instances']} small instances with a toy score on a square, not the "
             f"engine's bids (lowest share {sh(bn['cbba_lite_vs_optimum']['1']['score_share_min'], 1)}).",
             "Appendix B, 3.11"),
            ("Bundles of several jobs: at least 1/2 of the best score when the bundle limit does not bind, 1/3 when "
             "it does (Proposition 1b, 1c)",
             "Proved under diminishing marginal gain, which was not verified for the engine's bid. The 50&#8239;% "
             "published for the general case is quoted as reported in [5, 74]; the original proof [4] was not read. "
             "Deeper bundles are not this paper's default.", "Appendix B, 2.1"),
            (f"A position report is {V['P1-PROP6-CONTENT-B']} of content and a packet of {V['P1-PROP6-SECURED-B']} "
             f"with authentication, before link framing and coding (Proposition 6)",
             f"Counted over the schema's fields. The lower bound of {V['P1-PROP6-NEED-BITS']} bits is definitional "
             f"for most fields, whose ranges were set by their bit widths. Tested: the codec's sizes, and "
             f"{len(p.conf['vectors'])} golden packets decoded each time the paper is built.", "Appendix B, 3.12"),
            (f"The periodic reports and the task and road messages of 20 rovers fit the {kbps(e53['nb'], 0)} budget "
             f"at one position report a second with authentication, and not at ten (H13)",
             f"Calculated from assumed inputs (message sizes times rates), not a test: the first clause holds in any "
             f"geometry, and the design note had the result before E53 ran. On the predicted side of the threshold "
             f"in {'both clauses' if e53['sup'] else 'one clause'}. It covers {e53['n_types']} of the "
             f"{e53['n_all']} message types, as packets before link framing and coding, and holds only on a "
             f"scheduled channel with reports travelling one hop.", "5.8"),
            ("A shared channel must run at <i>R</i>&nbsp;&ge;&nbsp;<i>L</i><i>h</i>/&eta; (Proposition 2)",
             f"Proved. Assumed: &eta;&nbsp;=&nbsp;{p.e53['eta']['scheduled']:g} for a scheduled channel, not swept; "
             f"the random-access value is derived.", "Appendix B, 5.8"),
            ("Age of a relayed report under per-hop loss, and under store and forward (Proposition 3)",
             "Proved. Part (a) assumes independent loss per hop and no retry, and is checked against a seeded "
             "simulation of that model each time the paper is built; bursty loss is not covered, and no experiment "
             "here relays reports over more than one hop.", "Appendix B"),
            ("Store and forward loses fewer awarded jobs than drop and retry (H14, first clause)",
             f"Tested: E54, {d14['n']} seeds, a message-level replay of one recorded month with the fleet of eight "
             f"vehicles, per-hop loss 0.25. Holds against a baseline that gives up after {prm['max_tries']} tries in "
             f"{num((prm['max_tries'] - 1) * prm['retry_s'] / 60)} minutes of a {num(prm['lease_s'] / 60)}-minute "
             f"lease (Assumed, not swept), with a Holm-adjusted p of {pfmt(f14['holm']['p_adjusted'])} on a "
             f"one-sided sign test added after the results. Not an engine run.", "5.9, 7"),
            ("The lost-link rule leaves no reservation stuck past its timeout (H14, second clause)",
             f"Not testable as written; no verdict: in the results file the clause holds by rule, not by "
             f"measurement. The rule first written, which released a silent vehicle's "
             f"reservation, is withdrawn. Counted in E54 without the return to the last link point: "
             f"{rdr['stuck_reservations']:,} of {n_res:,} reservations ended with their holder out of reach.", "5.9"),
            ("A silent vehicle's reserved segment is not released: it is marked unconfirmed and may be entered only "
             "at caution speed",
             "Assumed (a rule of the protocol). The delay that caution-speed traversal costs is not priced.",
             "3.13, 5.9"),
            ("Expected extra wait of a job after a rover fails, decided on the Moon and decided on Earth "
             "(Proposition 4)",
             "Proved as formulas, assuming independent heartbeat loss and fixed gaps and windows. Calculated from "
             "assumed inputs. Not tested: no rover failure is simulated.", "Appendix B, 3.13"),
            ("Operators needed against fleet size and autonomy level (Proposition 5)",
             "Calculated from assumed inputs that were chosen to land near published supervision ratios "
             "[76&ndash;79]: a consistency check, not a prediction. Not tested.", "Appendix B"),
            ("The capability filter with manifests made from the vehicle classes changes no outcome",
             f"Tested once: one {cf['days']}-day run, seed {cf['seed']}, {cf['identical']} of {cf['summary_values']} "
             f"summary values identical. The case it is meant for, a vehicle of a class the dispatcher has never "
             f"seen, was not run.", "3.12"),
            ("Robots that nobody hears drive to a rally point the mast can see",
             "Assumed (our rule). Swept: switched off in E41.", "3.9, 5.5"),
            ("Radio links exist on line of sight within 5&nbsp;km; a hop loses a message with probability 0.10",
             "Assumed. Swept in E41: range 2, 5, 10&nbsp;km and unlimited; loss 0 to 0.40 and bursty.", "3.4, 3.5, 5.5"),
            ("Three owners with a third of the cargo each, one of them without a cargo rover",
             "Assumed, not varied in E40 to E42.", "3.2, 7"),
            (f"The base computer fails every {num(reg['base_mtbf_h'])}{NB}h, is repaired in {num(reg['base_repair_h'])}"
             f"{NB}h, and a new leader takes {reg['reelect_h']:g}{NB}h to elect",
             "Assumed, not swept. CADRE's design re-chooses a leader within 10&nbsp;s [71].", "3.6, 3.13"),
            ("Owners report their costs honestly; vehicles do not interfere on the road",
             "Assumed, not varied here; removed in the companion papers [44, 45].", "7"),
            ("Two independent implementations of the protocol understand each other",
             "Not tested. One implementation exists; the conformance vectors are the test a second must pass.",
             "3.12, 7"),
            ("The messages get through on a real radio at these rates",
             "Not tested: no radio hardware, no link budget and no channel-access protocol was run.", "7"),
            ("The leader regime reproduces CADRE's published behaviour",
             "Not tested; the steps are listed as future work.", "6.5"),
        ]
        body = "\n".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in R)
        return ('<table class="wide" id="p1-tab-proved"><caption><b>Table 12.</b> Every claim of this paper with its '
                'status: proved (with the assumption), tested (with the experiment, its runs and its scenario), '
                'calculated from assumed inputs or a property of the model (it could not have come out otherwise), '
                'assumed (with the sweep, if any) or not tested.</caption>\n<tr><th>Claim</th><th>Status</th>'
                '<th>Section</th></tr>\n' + body + "\n</table>")
    fill("P1-TABLE-PROVED", table, "E54")


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
    json.dump({k: v for k, v in V.items() if not k.startswith("P1-TABLE") and k not in ("P1-REFERENCES", "P1-FIG-H2-YEARS", "P1-LRIP-MANIFEST-EXAMPLE")},
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
