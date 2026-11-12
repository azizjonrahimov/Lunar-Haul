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
    s = (f"The pairing holds for demand, landings and initial faults: in the engine's phase-5 checks (D10, Section {methods_section}) every regime's "
         f"E40 run had the same demand as the oracle's on the same seed and start year" + (f" across {n_pairs} regime pairs" if n_pairs else "") +
         "; the per-job intervention and fault redraws are shared in draw order and diverge once the allocations differ, in every regime. ")
    if good:
        lo, hi = vr(good)
        s += (f"Against the oracle, pairing cut the variance of the paired difference in mean delay per delivery to {num(lo, 2)}&ndash;{num(hi, 2)} "
              f"of the unpaired sum for {', '.join(reg(x) for x in good)}")
    if weak:
        lo, hi = vr(weak)
        s += ((", and" if good else "Against the oracle, pairing cut it") + f" only to {num(lo, 2)}&ndash;{num(hi, 2)} for {', '.join(reg(x) for x in weak)}, "
              "whose delay varies mostly between start years; their paired intervals are little narrower than unpaired ones would be, and the bootstrap "
              "over pairs includes that variation.")
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
    def fixpoint_sentence():
        missing = [e for e in ("E40", "E42", "E41") if e not in r.ba]
        if missing:
            raise Pending(f"the before/after of {', '.join(missing)} (compare_rerun.py) has not landed")
        parts = []
        for e in ("E40", "E42", "E41"):
            b = r.ba[e]
            parts.append(f"{e}: {b['n_matched']:,} rows matched, the primary outcome moved by "
                         f"{num(b['primary_mean_change_h'], 2, sign=True)}{NB}h on average and "
                         f"{num(b['primary_mean_abs_change_h'], 1)}{NB}h in absolute value, at most "
                         f"{num(b['primary_max_abs_change_h'], 0)}{NB}h in one run")
        tot_old = sum(r.ba[e]["n_old"] for e in r.ba)
        return (f"The dispatcher's consolidation hold re-posted a wake-up for every held lane on every call, so the "
                f"event queue grew with fleet size and, because one dispatch call does not reach a fixed point, the "
                f"duplicates also changed assignments. The fix, pre-registered as change 5 before any rerun row, posts "
                f"one wake-up per lane and lot and repeats dispatch at the same instant until nothing changes. Every "
                f"block of E40, E41 and E42 was rerun with it; the {tot_old:,} earlier rows are archived and "
                f"reproducible with the fix off, and every number in this paper is from the rerun rows. Against the "
                f"archived rows with the same cell and seed ({'; '.join(parts)}). The per-cell before/after tables "
                f"are results/E40_fixpoint_before_after.csv and the E41 and E42 files beside it.")
    fill("P1-FIXPOINT-SENTENCE", fixpoint_sentence, "change 5 before/after")

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
    check(undel > 0.9, "almost the whole H1 gap is cargo owners alone never delivered")
    V["P1-H1-UNDELIVERED-SHARE"] = sh(undel, 1)        # one decimal: "almost the whole gap" must not read "100 %"
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
    # the 90 % interval: the equivalence margin of 4.5 is judged on it (the referee round asked for the same interval)
    V["P1-RELAY08-MINUS-O"], V["P1-RELAY08-MINUS-O-CI"] = h_(relay["mean"]), ci_h(relay["lo90"], relay["hi90"])
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
                                   f"came within {h_(abs(h3['mean']), 1)} of the full-information marketplace, a "
                                   f"difference not distinguishable from zero but too wide to show equivalence"
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
                  "relay08": "the 80&#8239;% relay"}
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
    V["P1-SEEDS-ADDED"] = ("No seeds were added: every cell holds the 30 seeds of the design"
                           + (" (and the 50 runs of the second block where it applies)" if any(
                               k.endswith("|v3") for k in npc) else "") + "."
                           + (f" The rule was not applied to H3a's comparison, whose 90{PCT} half-width of "
                              f"{h_(half90, 2)} exceeds 10{PCT} of the marketplace mean ({h_(tenpct, 2)}); by the rule "
                              f"ten more seeds should have been run for it. We report the equivalence test as it "
                              f"stands rather than extend the sample after seeing the result (Section 7)."
                              if half90 > tenpct else ""))
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
              f"{PCT} of the loss-free wait per point of loss, against about 0.3{PCT} of makespan per point for the "
              "best allocators in Lott and Honary's benchmark [11].")
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
        return (f"Bundles of up to five jobs {'hurt' if h3b['supported'] else 'did not hurt'} the auction: against "
                f"depth 1, depth 5 {moved(d5['0.25'], 'the urgent wait')} at loss 0.25 and "
                f"{moved(d5['0.4'], 'it')} at loss 0.40, and depth 2 {moved(d2['0.25'], 'it')} at loss 0.25 and "
                f"{moved(d2['0.4'], 'it')} at loss 0.40. Stale claims, bids on items that another robot had already taken by the "
                f"time the bundle was accepted, {'rose' if stale > 0 else 'fell' if stale < 0 else 'did not change'} "
                f"from {num(st1['atc_claims_stale'], 0)} to {num(st5['atc_claims_stale'], 0)} per year at depth 5 "
                f"and loss 0.40. H3b, that depth 5 is worse than depth 1 at loss 0.25 to 0.40, is {verdict}. "
                f"For the learned bids at loss 0.40, depth 5 "
                + listing(f"{moved(learned[reg], 'the wait of ' + NAME4[reg])}" for reg in learned) + ".")

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

    fill("P1-E41-LOSS-SENTENCE", e41_loss_sentence, "E41")
    fill("P1-E41-DEPTH-SENTENCE", e41_depth_sentence, "E41")
    fill("P1-E41-RANGE-SENTENCE", e41_range_sentence, "E41")

    def e41_depth_clause():
        h3b = need_f41()["H3b"]
        if h3b.get("supported") is None:
            raise Pending("E41 depth cells of the auction incomplete")
        return ("Bundle depth 5 made the auction " + ("worse" if h3b["supported"] else "no worse") +
                " at message loss 0.25 and 0.40 (Section 5.5)")

    fill("P1-E41-DEPTH-CLAUSE", e41_depth_clause, "E41")
    fill("P1-CHECKS-SENTENCE", lambda: vv5_checks_sentence("P1", "5.11", check), "B-79")
    fill("P1-FAILED-CHECKS-SENTENCE", lambda: vv5_failed_sentence("P1", "3.11", check), "B-79")
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
        for x in failed:
            bits.append(f"{html.escape(str(x.get('sub')))} in {num(100 * x['simulated'], 0)}{PCT} of the probes")
        return (f"The L5 failures are properties of the trained policies, not of the code: the learned bid was not monotone in approach time, "
                f"mass and battery for " + " and ".join(bits) + ", as the policies were tuned on urgent wait and not constrained to monotone bids (Section 3.5).")
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
        all_items = [r.pair("H6", LOAD_MAIN, team=t, loss="0.1") for t in ("10", "25")]
        check(all(a["lo"] > 0 for a in all_items), "cross-owner pairs raise the share of all items delivered")
        held = all(r.pair("H6", LOAD_MAIN, team=t, loss=l)["lo"] > 0 for t in ("10", "25") for l in ("0.25", "0.4"))
        return (
            "Allowing pairs of different owners raised the share of team items delivered " + " and ".join(parts) +
            " at message loss 0.10, and the share of all items delivered by " +
            listing(f"{num(100 * a['mean'], 1)} percentage points ({num(100 * a['lo'], 1)} to "
                    f"{num(100 * a['hi'], 1)}) at team share 0.{t}" for a, t in zip(all_items, ("10", "25"))) +
            f". H6's first part, registered on the share of all items at team share 0.25, is supported "
            f"(Holm-adjusted p {p_eq(holm[LABELS['holm_H6']])}, Table 7). The gain "
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
    timeout_lead = ("The timeout trades waiting for failures:" if trades else
                    "The timeout sets the waiting without buying fewer failures:")
    timeout_tail = ("" if trades else f", while failed meetings stayed between {num(min(tof.values()), 1)} and "
                                     f"{num(max(tof.values()), 1)}")
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
    V["P1-H6-MEETINGS-SENTENCE"] = (
        f"Failed meetings {'rose' if rises else 'did not rise steadily'} with message loss: at team share 0.25 the "
        f"auction with the commit step and a 1&nbsp;h timeout had on average {num(base['0.1'], 1)} failed meetings "
        f"per year at loss 0.10, {num(base['0.25'], 1)} at 0.25 and {num(base['0.4'], 1)} at 0.40. Without the "
        f"commit step {noc_clause()}: paired by seed, the step "
        + ("cut" if fewer_with else "did not cut") + " failed meetings by "
        + listing(f"{num(-cm[l]['mean'], 1)} ({num(-cm[l]['hi'], 1)} to {num(-cm[l]['lo'], 1)}) at loss "
                  f"{'0.40' if l == '0.4' else l}" for l in noc) +
        f", so the second part of H6, that failed meetings rise without a commit step, is "
        + ("supported" if fewer_with else "not supported") +
        f". The step is not free: the urgent wait with it was "
        + listing(f"{h_(cw[l]['mean'], 1)} ({ci_h(cw[l]['lo'], cw[l]['hi'])}) "
                  f"{'longer' if cw[l]['mean'] > 0 else 'shorter'} at loss {'0.40' if l == '0.4' else l}" for l in noc)
        + (", a cost that excludes zero at both losses" if cost else "") +
        f", because a meeting that the step refuses is a lift that waits. {timeout_lead} at "
        f"loss 0.25 the hours robots spent "
        f"waiting at meeting points were {num(to['0.5'], 1)} with a 0.5&nbsp;h timeout, {num(to1, 1)} with 1&nbsp;h "
        f"and {num(to['2'], 1)} with 2&nbsp;h{timeout_tail}. The exploratory variant in which the base computer arbitrates each "
        + ("meeting had no failed meetings at either loss." if all(v == 0 for v in arb.values()) else
           f"meeting had {num(arb['0.25'], 1)} and {num(arb['0.4'], 1)} failed meetings at loss 0.25 and 0.40."))
    check(to["0.5"] < to1 < to["2"], "meeting wait grows with the timeout")
    # one clause for the abstract, 6.1 and the conclusion: the team-share-0.10 lift in team items and the commit step's
    # effect, with the same rule as the meetings sentence (supported if failures without the step exceed 1.1x)
    t10 = r.pair("H6_team_items", LOAD_MAIN, team="10", loss="0.1")
    V["P1-H6-ABSTRACT-CLAUSE"] = (
        f"Pairs of different owners' robots lifting heavy crates raised the share of team items delivered "
        f"from {sh(t10['b_mean'])} to {sh(t10['b_mean'] + t10['mean'])}; a commit step before each meeting "
        + ("cut failed meetings under loss" if fewer_with else "did not cut failed meetings")
        + (", at a cost in urgent wait" if cost else ""))

    check(t10["lo"] > 0, "cross-owner pairs raise the share of team items delivered (abstract clause)")
    V["P1-H6-SHORT-CLAUSE"] = (f"Pairs of different owners' robots raised the share of team items delivered "
                               f"from {sh(t10['b_mean'])} to {sh(t10['b_mean'] + t10['mean'])}")

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
    V["P1-LRIP-ABSTRACT-SENTENCE"] = (
        f"The robots' messages are specified and implemented as {V['P1-LRIP-N-MSG']} types with a capability "
        f"manifest: an authenticated position report is {V['P1-PROP6-SECURED-B']}, and 20 "
        f"rovers reporting once a second load the busiest link with {kbps(e53['v1'], 1)}, "
        f"{'inside' if e53['v1'] <= e53['nb'] else 'above'} a {kbps(e53['nb'], 0)} budget, against "
        f"{kbps(e53['v10'], 1)} at ten a second")
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
        for _, c in d.iterrows():
            indep = bool(c["earth_independent"])
            lab = html.escape(c["label"]) + ("&dagger;" if indep else "")
            n = f"{int(c['n_v1'])}" if indep else f"{int(c['n'])}"
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
                     "30 runs of block one are counted and shown (change 4 of the pre-registration [43]).")


def table_ood(r: R):
    rows = []
    for cell, v in r.L["ood"].items():
        d = v["linear"]["vs_hand_h"]
        rows.append([html.escape(cell), num(v["hand"]["urgent_mean_h"], 1), num(v["linear"]["urgent_mean_h"], 1),
                     f"{num(d['mean'], 2, sign=True)} [{num(d['ci95'][0], 2)}, {num(d['ci95'][1], 2)}]", f"{d['n']}"])
    return _tab("<b>Table 6.</b> The linear bids outside their training range, from the evaluation of the learned "
                "bids before the main runs: mean urgent wait (h) with hand-built and learned bids, and the paired "
                "difference with its 95&#8239;% interval, on ten evaluation seeds the model never saw. 2eq and 5eq "
                "split the same eight vehicles and the demand equally among two and five owners. Where E41 reran a cell on 30 seeds (loss 0.25 and 0.40, "
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
    for name, row, hk, sign in fam:
        adj = holm[hk]
        ok = adj < 0.05 and np.sign(row["mean"]) == sign
        unit = "" if row["metric"] == "delivered_share" else NB + "h"
        val = (f"{num(100 * row['mean'], 1, sign=True)} pp [{num(100 * row['lo'], 1)}, {num(100 * row['hi'], 1)}]"
               if not unit else f"{num(row['mean'], 1, sign=True)}{unit} [{num(row['lo'], 1)}, {num(row['hi'], 1)}]")
        blk = "v1" if name == "H6" else row["block"]      # E42 has block one only
        rows.append([name, html.escape(row["comparison"]), blk, f"{int(row['n'])}", val,
                     pfmt(row["p"]), pfmt(adj),
                     "supported" if ok else ("wrong direction" if adj < 0.05 else "not supported")])
    # the registered 60 % halves of H1 and H4: raw p only, outside the Holm family
    for name, row in (("H1, 60&#8239;%", r.pair("H1", LOAD_HEAVY)), ("H4, linear, 60&#8239;%", r.pair("H4_LIN", LOAD_HEAVY)),
                      ("H4, network, 60&#8239;%", r.pair("H4_MLP", LOAD_HEAVY))):
        val = f"{num(row['mean'], 1, sign=True)}{NB}h [{num(row['lo'], 1)}, {num(row['hi'], 1)}]"
        rows.append([name, html.escape(row["comparison"]), row["block"], f"{int(row['n'])}", val, pfmt(row["p"]),
                     "&ndash;", "supported" if row["hi"] < 0 else "not supported"])
    return _tab("<b>Table 7.</b> The confirmatory family at the middle load: paired mean difference with its "
                "95&#8239;% bootstrap interval, the two-sided bootstrap p and Holm's adjusted p. H3a is an "
                "equivalence claim and is tested in Section 5.4. The last three rows are the registered 60&#8239;% "
                "halves of H1 and H4, outside the Holm family, with the raw p only.",
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
        self.e53 = jl("results", "E53_bitrate.json")
        self.t53 = pd.read_csv(os.path.join(RES, "E53_table.csv"))
        p54 = os.path.join(RES, "E54_dtn.json")
        self.e54 = json.load(open(p54, encoding="utf-8")) if os.path.exists(p54) else None
        # the Earth-bound ledger over 61 days (the main E54 table's ledger columns are cut off by its 31-day window
        # and are never quoted)
        p54l = os.path.join(RES, "E54_ledger.json")
        self.e54l = json.load(open(p54l, encoding="utf-8")) if os.path.exists(p54l) else None
        self.schema = jl("lunarsim", "schemas", "lrip-v0.1.json")
        self.conf = jl("data", "atc", "lrip", "conformance-v0.1.json")
        self.man = {k: jl("data", "atc", "lrip", f"manifest-{k}.json") for k in ("small_rover", "hopper")}
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
    check(len(S["versioning"]) == 4, "the schema states four versioning rules")
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

    rows = []
    for m in msgs:
        nm, d = m["name"], st[m["name"]]
        bits = sum(f[2] for f in m["fields"]) if m["fields"] else None
        rows.append([f"{m['id']}", f"<code>{nm}</code>", html.escape(m["pattern"]), html.escape(m["default_rate"]),
                     f"{bits}" if bits else "variable", f"{d['payload']}",
                     f"{d['default']}" + (" (signed)" if m.get("signed") else ""), html.escape(m["carried_by"])])
    V["P1-TABLE-LRIP-MSG"] = _tab(
        f"<b>Table A2.</b> The {len(msgs)} messages of LRIP v0.1, read from the schema file: how each is sent, its "
        f"default rate, its content in bits and bytes, and its size on the air in the narrow-band profile, that is "
        f"the content plus {nbytes(spp + hdr + sec + mac8)} of headers and authentication code, or plus "
        f"{nbytes(spp + hdr + sec + sig)} where a signature replaces the code. <code>CAP_MANIFEST</code> is the "
        f"small-rover example of Section 3.12.",
        ["ID", "Message", "Pattern", "Default rate", "Content (bits)", "Content (B)", "On the air (B)", "Carried by"],
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
        f"(hopper), and the small rover's is {nbytes(st['CAP_MANIFEST']['default'])} on the air, signed. The design "
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
        f"two example manifests in compact form. The keys in the file are test keys.")
    cf = r.dev["capability_filter_check"]
    check(cf["identical"] == cf["summary_values"] and cf["runs"] == 1, "the capability filter changed no summary value")
    V["P1-LRIP-CAPFILTER-SENTENCE"] = (
        f"With manifests generated from the vehicle classes, switching the filter on changed none of the "
        f"{cf['summary_values']} summary values of a {cf['days']}-day run of the auction (one run, seed {cf['seed']}, "
        f"message loss {cf['loss']:.2f}), because those manifests state exactly the capacity the engine already "
        f"checks; with no manifests at all, deliveries fell below {sh(cf['delivered_share_without_manifests_below'])} "
        f"of that run's.")
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
    beacons = sum(pr[k]["rate_hz"] * st[k]["default"] for k in ("POSITION", "STATUS", "INTENT"))     # B/s
    check(abs(beacons * 8 / 1000 - per[("on", 1.0)]) < 1e-3, "position, status and intent reports make up the 1 Hz load")
    check(sum(v["bps"] for k, v in pr.items() if k not in ("POSITION", "STATUS", "INTENT")) < 1e-3 * 1000 * per[("on", 1.0)],
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
    verdict = ("Both clauses of H13 hold, and it is supported as pre-registered [54]." if sup else
               "H13's first clause fails, so it is not supported: the earlier budget was too small." if v1 > nb else
               "H13's second clause fails, so it is not supported as pre-registered [54].")
    V["P1-E53-H13-SENTENCE"] = (
        f"With authentication on and 20 rovers, the busiest link carried {kbps(v1)} at one position report a second "
        f"(95th percentile over the {e['draws']} draws; mean {kbps(r1['busiest_link_kbps_mean'])}), "
        f"{'inside' if v1 <= nb else 'above'} the {kbps(nb, 0)} of the earlier budget, and {kbps(v10, 1)} at ten "
        f"a second, {'above' if v10 > nb else 'inside'} it. {verdict}")
    V["P1-LRIP-INTRO-SENTENCE"] = (
        f"Twenty rovers reporting once a second load the busiest radio link with {kbps(v1)}, "
        f"{'inside' if v1 <= nb else 'above'} the {kbps(nb, 0)} we had budgeted, and at ten reports a second with "
        f"{kbps(v10, 1)}, which {'does not fit' if v10 > nb else 'still fits'}; the pre-registered hypothesis on this "
        f"point (H13) is {'supported' if sup else 'not supported'} (Section 5.8).")
    V["P1-LRIP-CONCLUSION-SENTENCE"] = (
        f"{len(p.schema['messages'])} message types "
        + (f"fit a {kbps(nb, 0)} channel for 20 rovers at one authenticated position report a second and not at ten"
           if sup else
           f"load a {kbps(nb, 0)} channel with {kbps(v1)} for 20 rovers at one authenticated position report a second "
           f"and {kbps(v10, 1)} at ten"))
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
        f"In this geometry the busiest link hears the whole fleet (mean hops to the base "
        f"{rng_txt([row('fleet', 'on', 1.0, n)['mean_hops_to_base'] for n in NS], lambda x: num(x, 2))}; "
        f"{rng_txt([row('fleet', 'on', 1.0, n)['reachable_share'] for n in NS], lambda x: sh(x))} of rovers with a "
        f"path to it), so the scheduled {kbps(nb, 0)} channel is full at {nmax} rovers reporting once a second"
        + (f": 40 rovers fit as load ({kbps(r40, 1)}) and not as airtime ({kbps(r40 / eta_s, 1)})." if r40 <= nb < r40 / eta_s
           else "."))
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
    return {"v1": v1, "v10": v10, "nb": nb, "sup": sup, "nmax": nmax, "per1": per[("on", 1.0)], "draws": e["draws"]}


E54_NAMES = {"drop_retry": "drop and retry", "sf": "store and forward", "sf_ll": "store and forward + lost-link rule"}


def phase6_e54(p, V, fill, check):
    """E54 (Sections 4.8 and 5.9, Table 11). Every value goes through fill(): a missing results file is Pending."""
    LOSS = 0.25                                                 # H14's pre-registered loss

    def design():
        p.h14()                                                 # Pending when the results file is missing
        e = p.e54
        prm = e["parameters"]
        b0, b1 = e["blackout_days"]
        check(abs((b1 - b0) - 14.0) < 1e-9, "E54's imposed Earth blackout lasts 14 days")
        check(prm["retry_s"] > 60.0, "drop-and-retry's retry interval is longer than a grant's 60 s lifetime")
        return (
            f"The month is July 2028 as the engine recorded it for the auction at the middle load, with today's "
            f"fleet and the road rules of [45], on {len(e['seeds'])} seeds ({num(e['jobs_per_seed'])} jobs and "
            f"{num(e['reservations_per_seed'])} single-lane road reservations a seed). Three ways of carrying the messages are compared at per-hop loss 0.10, 0.25 and 0.40. "
            f"<i>Drop and retry</i> sends end to end along the current shortest path, again every "
            f"{secs(prm['retry_s'])}, at most {prm['max_tries']} times and never past the message's lifetime. "
            f"<i>Store and forward</i> moves a message hop by hop with custody [60]: a lost transmission is repeated "
            f"after {secs(prm['custody_timer_s'])} while the link lasts, a message with no path waits in a "
            f"{num(prm['queue_bytes'] / 1e6)}{NB}MB store, and it expires at its lifetime. The third adds the "
            f"<i>lost-link rule</i> of Section 3.13: a vehicle that has had no path to the base for "
            f"{secs(prm['t_hold_s'])} retraces its path at half speed to the last point where it had one, and the "
            f"base releases its reservations at their timeout. The messages are those of the recorded run: an award "
            f"to each vehicle of a job (lifetime the {num(prm['lease_s'] / 3600)}{NB}h lease; an award that expires "
            f"undelivered is a lost job, auctioned again), a reservation grant (lifetime 60{NB}s), a report at the "
            f"end of each job, and a status report every {secs(prm['status_period_s'])} for the base's age of "
            f"information. A {num(b1 - b0)}-day Earth blackout is imposed on days {num(b0)} to {num(b1)}.")
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
        dr, ll, d = h["lost_jobs_drop_retry_per_seed"], h["lost_jobs_sf_ll_per_seed"], h["difference_sf_ll_minus_drop_retry"]
        rdr, rsf, rll = (p.row54(LOSS, k) for k in ("drop_retry", "sf", "sf_ll"))
        fewer = d["ci"][1] < 0
        check(bool(h["supported"]) == (fewer and h["stuck_reservations_sf_ll"] == 0), "H14's verdict follows its rule")
        check(round(dr["mean"] * dr["n"]) == rdr["award_lost"] and round(ll["mean"] * ll["n"]) == rll["award_lost"],
              "the lost jobs per seed add up to the table's counts")
        none = rll["award_lost"] == 0
        return (
            f"At per-hop loss {LOSS:.2f} with the 14-day blackout, drop and retry lost {rdr['award_lost']} of "
            f"{rdr['award_n']:,} awards, {num(dr['mean'], 2)} jobs a seed (95&#8239;% CI {num(dr['ci'][0], 2)} to "
            f"{num(dr['ci'][1], 2)}). Store and forward lost {rsf['award_lost']}, and with the lost-link rule "
            f"{'none' if none else rll['award_lost']}. The paired difference between the third and the first is "
            f"{num(d['mean'], 2)} jobs a seed (95&#8239;% CI {num(d['ci'][0], 2)} to {num(d['ci'][1], 2)}, "
            f"n&nbsp;=&nbsp;{d['n']}), which {'excludes' if fewer else 'includes'} zero: the first clause of H14 is "
            f"{'supported' if fewer else 'not supported'}. Lost jobs are rare under either transport, because the "
            f"base keeps trying for the whole lease while the vehicle is in reach.")
    fill("P1-E54-H14-SENTENCE", h14_sentence, "E54")
    fill("P1-E54-H14-VERDICT", lambda: "supported" if p.h14()["supported"] else "not supported", "E54")

    def stuck_sentence():
        h, e = p.h14(), p.e54
        rdr, rll = p.row54(LOSS, "drop_retry"), p.row54(LOSS, "sf_ll")
        check(rll["stuck_reservations"] == 0 and rll["stuck_hours"] == 0, "the results file sets stuck reservations to zero under the rule")
        check(rdr["stuck_reservations"] == h["stuck_reservations_drop_retry"] > 0, "without the rule some reservations stay blocked")
        check("UNCONFIRMED release" in str(e.get("stuck_definition", "")) and "leaves on schedule" in str(e.get("stuck_definition", "")),
              "the results file defines a stuck reservation as an unconfirmed release, with every vehicle leaving on schedule")
        n = len(e["seeds"])
        return (
            f"H14's second clause, that the rule leaves no reservation blocked past its timeout, holds by "
            f"construction and is not a measurement: a vehicle that follows the rule never stops inside a single-lane "
            f"segment, so the base may release its reservation at the timeout whether or not it hears the vehicle. "
            f"What the replay measures is what the rule avoids. Without it, "
            f"{rdr['stuck_reservations']:,} of the {round(e['reservations_per_seed'] * n):,} reservations in the {n} "
            f"seeds ended while their holder had no path to the base "
            f"{secs(e['parameters']['grace_s'])} after the timeout. These are releases the base could not confirm, "
            f"not vehicles still inside a segment: in the replay every vehicle leaves on schedule, but the base "
            f"cannot know that, so it keeps the segment blocked until the holder is heard again, "
            f"{num(rdr['stuck_hours'])}{NB}h in all, {num(rdr['stuck_hours'] / n)}{NB}h a "
            f"seed. With the first clause measured and the second a property of the rule, H14 is "
            f"{'supported' if h['supported'] else 'not supported'} [54].")
    fill("P1-E54-STUCK-SENTENCE", stuck_sentence, "E54")

    def grants_sentence():
        g = {l: {k: p.row54(l, k) for k in E54_NAMES} for l in (0.10, 0.25, 0.40)}
        dr = {l: g[l]["drop_retry"]["grant_lost_share"] for l in g}
        check(all(abs(dr[l] - l) < 0.02 for l in dr), "drop-and-retry loses grants at about the per-hop loss rate")
        check(all(g[l]["sf"]["grant_lost_share"] < 0.01 and g[l]["sf_ll"]["grant_lost_share"] < 0.01 for l in g),
              "custody loses under 1 % of grants at every loss")
        sf, ll = g[LOSS]["sf"], g[LOSS]["sf_ll"]
        return (
            f"The larger effects are elsewhere. A reservation grant lives 60{NB}s, so drop and retry has one try, "
            f"and it lost grants at about the per-hop loss rate itself: {pc(100 * dr[0.10], 1)}, "
            f"{pc(100 * dr[0.25], 1)} and {pc(100 * dr[0.40], 1)} at loss 0.10, 0.25 and 0.40. Each lost grant is a "
            f"vehicle that stops before a single-lane segment. With custody, {sf['grant_lost']} of "
            f"{sf['grant_n']:,} grants were lost at loss {LOSS:.2f} ({pc(100 * sf['grant_lost_share'], 2)}), and "
            f"{'none' if ll['grant_lost'] == 0 else ll['grant_lost']} with the lost-link rule.")
    fill("P1-E54-GRANTS-SENTENCE", grants_sentence, "E54")

    def aoi_sentence():
        e = p.e54
        dr, sf, ll = (p.row54(LOSS, k) for k in ("drop_retry", "sf", "sf_ll"))
        check(abs(dr["aoi_mean_s"] - sf["aoi_mean_s"]) < 0.01 * sf["aoi_mean_s"], "the transport does not change the base's age of information")
        check(ll["aoi_mean_s"] < 0.05 * sf["aoi_mean_s"], "the lost-link rule cuts the base's age of information")
        check(sf["task_state_lost"] < dr["task_state_lost"] and sf["task_state_delay_mean_s"] > dr["task_state_delay_mean_s"]
              and ll["task_state_delay_mean_s"] < sf["task_state_delay_mean_s"], "holding delivers more end-of-job reports, later")
        return (
            f"The lost-link rule changes what the base knows, not what the radio loses. Without it the base's "
            f"picture of a vehicle was on average {num(sf['aoi_mean_s'] / 60)}{NB}min old "
            f"({secs(sf['aoi_mean_s'])}) under either transport, and the worst-placed vehicle went unheard for "
            f"{num(sf['aoi_worst_vehicle_s'] / 3600)}{NB}h. With it the mean age was {secs(ll['aoi_mean_s'])} and the "
            f"worst vehicle's {secs(ll['aoi_worst_vehicle_s'])}: the rule produced "
            f"{num(e['lost_link_returns_per_seed'])} returns a seed and removed "
            f"{num(e['lost_link_isolation_h_saved_per_seed'])} vehicle-hours of isolation a seed. The end-of-job "
            f"reports show the cost of holding a message: drop and retry lost {sh(dr['task_state_lost_share'])} of "
            f"them, store and forward lost {sh(sf['task_state_lost_share'], 1)} and delivered the rest "
            f"{secs(sf['task_state_delay_mean_s'])} late on average, because a vehicle that ends a job out of reach "
            f"waits for a contact, and with the return to the last link point the delay fell to "
            f"{secs(ll['task_state_delay_mean_s'])}.")
    fill("P1-E54-AOI-SENTENCE", aoi_sentence, "E54")

    def ledger_sentence():
        L = p.e54l
        if L is None:
            raise Pending("the 61-day ledger replay (results/E54_ledger.json) has not run")
        down = L["longest_earth_down_d"]
        rows = L["rows"]
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
            f"The daily ledger bundle to Earth was replayed over 61 days, in which the longest stretch without Earth "
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
                             "0 (by construction)" if k == "sf_ll" else f"{x['stuck_reservations']:,} ({num(x['stuck_hours'])}{NB}h)"])
        x = p.row54(0.25, "sf")
        return _tab(
            f"<b>Table 11.</b> E54: a message-level replay of one recorded month, {len(p.e54['seeds'])} seeds, with a "
            f"14-day Earth blackout. Counts are sums over the seeds, out of {x['award_n']:,} awards, "
            f"{x['grant_n']:,} grants and {x['task_state_n']:,} end-of-job reports. The age of information is the "
            f"age of the newest status report the base holds for a vehicle. The last column is not a measurement in "
            f"its third row of each block: under the rule the base releases a reservation at its timeout.",
            ["Per-hop loss", "Transport", "Awards lost (lost jobs)", "Award delay, mean (s)", "Grants lost",
             "End-of-job reports lost", "their delay, mean (s)", "Age at the base, mean (s)", "worst vehicle (h)",
             "Reservations blocked past timeout"], rows, cls="wide")
    fill("P1-TABLE-E54", table, "E54")

    def abstract_clause():
        h = p.h14()
        dr, ll, d = h["lost_jobs_drop_retry_per_seed"], h["lost_jobs_sf_ll_per_seed"], h["difference_sf_ll_minus_drop_retry"]
        if d["ci"][1] < 0:
            return (f"store-and-forward with a lost-link rule lost {'no' if ll['mean'] == 0 else num(ll['mean'], 2)} "
                    f"awarded jobs where drop-and-retry lost {num(dr['mean'], 2)} a seed")
        return "store-and-forward with a lost-link rule did not lose measurably fewer awarded jobs than drop-and-retry"
    fill("P1-E54-ABSTRACT-CLAUSE", abstract_clause, "E54")

    def aoi_clause():
        sf, ll = p.row54(LOSS, "sf"), p.row54(LOSS, "sf_ll")
        return (f"the base's picture of a vehicle was {num(sf['aoi_mean_s'] / 60)}{NB}min old on average without the "
                f"lost-link rule and {secs(ll['aoi_mean_s'])} with it")
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
    q4 = r.dev["prop4_inputs"]
    Thb, k = q4["heartbeat_s"], int(q4["misses_k"])
    det_mean, det_max = (k - 0.5) * Thb, k * Thb
    fa = lambda pl, kk: 86400.0 / Thb * (1 - pl) * pl ** kk                    # false "silent" marks per pair and day
    kmin = lambda pl: next(kk for kk in range(1, 200) if fa(pl, kk) < 1.0)
    auct = q4["auction_rounds"] * q4["round_s"]
    appr_min = q4["approach_km"] / q4["approach_kmh"] * 60.0
    xfer_min = q4["cargo_aboard_prob"] * q4["transfer_h"] * 60.0
    total_min = (det_mean + auct) / 60.0 + appr_min + xfer_min
    from lunarsim.engine import TEAM_SETUP_H
    check(abs(TEAM_SETUP_H - q4["transfer_h"]) < 1e-9, "Proposition 4's transfer time is the engine's coupling time")
    G, W = q4["earth_gap_d"] * 24.0, q4["earth_window_d"] * 24.0
    earth_h = G * G / (2 * (G + W))
    check(earth_h * 60 > 10 * total_min, "waiting for Earth costs more than ten times the hand-over on the Moon")
    V["P1-PROP4-EXAMPLE-SENTENCE"] = (
        f"With a heartbeat every {secs(Thb)} (Assumed; the period at which CADRE's rovers send their state to the "
        f"leader [71]) and <i>k</i>&nbsp;=&nbsp;{k}, detection takes {secs(det_mean)} on average and at most "
        f"{secs(det_max)}. A pair of live rovers raises {num(fa(0.10, k), 2)} false marks a day at loss 0.10 and "
        f"{num(fa(0.40, k))} at 0.40; keeping them below one a day needs <i>k</i>&nbsp;=&nbsp;{kmin(0.10)}, "
        f"{kmin(0.25)} and {kmin(0.40)} at loss 0.10, 0.25 and 0.40. With {words(q4['auction_rounds'])} auction rounds "
        f"of {secs(q4['round_s'])}, a new winner {q4['approach_km']:g}{NB}km away at {q4['approach_kmh']:g}{NB}km/h, "
        f"and cargo aboard the failed rover with probability {q4['cargo_aboard_prob']:g} and a "
        f"{q4['transfer_h']:g}{NB}h transfer (all Assumed), the expected extra wait is {secs(det_mean)} + "
        f"{secs(auct)} + {num(appr_min, 1)}{NB}min + {num(xfer_min)}{NB}min = {num(total_min, 1)}{NB}min, of which "
        f"detection and auction are {secs(det_mean + auct)}: a shorter heartbeat would buy nothing.")
    V["P1-PROP4-EARTH-SENTENCE"] = (
        f"With gaps of {q4['earth_gap_d']:g} days and windows of {q4['earth_window_d']:g} days at this base [42], "
        f"the wait for Earth alone is {num(earth_h, 1)}{NB}h, {num(earth_h * 60 / total_min)} times the whole "
        f"hand-over on the Moon.")
    V["P1-PROP4-TOTAL-MIN"], V["P1-PROP4-EARTH-H"] = f"{num(total_min)}{NB}min", f"{num(earth_h)}{NB}h"

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
        f"The request rates and handling times are Assumed, chosen near the published ratios named in the text; "
        f"the first row is VIPER's planned staffing, not the formula.",
        ["Autonomy level", "Requests per vehicle-hour", "Minutes per request", "Vehicles per operator"]
        + [f"Operators for {n}" for n in fleets], rows)

    # --- Proposition 6: the position report, field by field (schema), against the codec ------------------------
    pos = next(m for m in p.schema["messages"] if m["name"] == "POSITION")
    rows, counts, total = [], [], 0
    for f in pos["fields"]:
        name, typ, bits, scale, unit = f
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
        elif name == "sigma_h":
            n = 1 << bits
            what = f"0 to {((1 << bits) - 2) * scale:g}{NB}m in steps of {scale:g}{NB}m, and one code for unknown"
        else:
            what, n = _field_range(f)
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
    check(math.ceil(joint) == need and math.ceil(need / 8) == sizes["payload"],
          "the fields need 98 bits jointly and field by field, which is 13 whole bytes")
    check(8 * (sizes["payload"] - 1) < joint, "twelve bytes are fewer bits than the fields need jointly")
    rows.append(["<b>Total</b>", "", f"<b>{total}</b>", "", f"<b>{need}</b>"])
    V["P1-TABLE-PROP6"] = _tab(
        "<b>Table B3.</b> The position report field by field, from the schema file: range and step, bits used, the "
        "number of values the field must tell apart, and the bits that number needs.",
        ["Field", "Range and step", "Bits", "Values", "Bits needed"], rows)
    V["P1-PROP6-BITS"], V["P1-PROP6-NEED-BITS"], V["P1-PROP6-JOINT-BITS"] = f"{total}", f"{need}", f"{joint:.1f}"
    V["P1-PROP6-SPARE-BITS"] = f"{total - need}"
    V["P1-PROP6-CONTENT-B"], V["P1-PROP6-SECURED-B"] = nbytes(sizes["payload"]), nbytes(sizes["mac8"])
    V["P1-PROP6-MAC16-B"], V["P1-PROP6-UNSEC-B"] = nbytes(sizes["mac16"]), nbytes(sizes["unsecured"])
    V["P1-PROP6-CBOR-B"] = nbytes(gold[("B", "mac8")])

    # --- the leader's election time (3.6, 3.13): what the engine assumes -----------------------------------------
    reg = p.regimes.DEFAULTS
    n_fail = 8760.0 / (reg["base_mtbf_h"] + reg["base_repair_h"])
    check(reg["reelect_h"] == 0.5 and reg["base_mtbf_h"] == 2000.0 and reg["base_repair_h"] == 24.0,
          "the engine's base-computer constants are those the text types")
    V["P1-LEADER-N-FAIL-YEAR"] = num(n_fail, 1)
    V["P1-LEADER-ELECTION-H-YEAR"] = h_(n_fail * reg["reelect_h"])


def phase6_proved(p, r, V, fill, check, ctx, e53):
    """The "Proved, tested, assumed" table (Section 6.6): one row per claim; verdict words come from the data."""
    def table():
        n1, n2 = int(r.pair("H1", LOAD_MAIN)["n"]), int(r.pair("H2_pooled", LOAD_MAIN)["n"])
        n3, n4 = int(r.pair("H3a", LOAD_MAIN)["n"]), int(r.pair("H4_LIN", LOAD_MAIN)["n"])
        n6 = int(r.pair("H6_team_items", LOAD_MAIN, team="10", loss="0.1")["n"])
        n_years = len(r.fit("hypotheses", "H2", str(LOAD_MAIN), "visibility"))
        h14 = p.h14()
        d14 = h14["difference_sf_ll_minus_drop_retry"]
        bn = r.bounds
        cf = r.dev["capability_filter_check"]
        reg = p.regimes.DEFAULTS
        R = [
            ("Pooling vehicles across owners cuts the mean urgent wait (H1)",
             f"Tested: E40, {n1} paired seeds, {LOAD_MAIN}{PCT} load, both sides with Earth always in view. Supported.",
             "5.2"),
            ("A pooled dispatcher on Earth that stops at every blackout keeps urgent cargo waiting longer than one "
             "that never stops, by more than 10&#8239;% (H2)",
             f"Tested: E40, {n2} paired runs over {words(n_years)} start years. Supported.", "5.3"),
            ("The robots' auction is within &plusmn;10&#8239;% of the full-information marketplace at message loss "
             "0.10 (H3a)",
             f"Tested: E40, {n3} paired seeds. Equivalence {'shown' if ctx['equiv'] else 'not shown'}"
             + ("." if ctx["equiv"] else "; the difference is also not distinguishable from zero."
                if r.pair("H3a", LOAD_MAIN)["lo"] < 0 < r.pair("H3a", LOAD_MAIN)["hi"] else "."), "5.4"),
            ("Learned bids beat hand-built bids on held-out seeds (H4)",
             f"Tested: E40, {n4} held-out seeds. Supported for the linear model; not supported for the network, which "
             f"was trained with less freedom.", "5.6, 7"),
            ("Pairs of different owners raise the share of items delivered; without a commit step failed meetings "
             "rise under loss (H6)",
             f"Tested: E42, {n6} seeds per cell. First part supported; second part "
             f"{'supported' if ctx['fewer_with'] else 'not supported'}.", "5.7"),
            ("Message loss, bundle depth, radio range, the lost-link rule and a second mast move the on-Moon regimes "
             "as reported (H3b, H3c, exploratory)",
             "Tested: E41, 30 seeds per cell, one factor at a time around the auction at the middle load.", "5.5"),
            ("With perfect links and depth 1 the auction reproduces the marketplace's event trace; with every new "
             "feature off the engine reproduces the earlier papers",
             f"Tested: exact comparison of event traces, and {r.dev['regression_check']['rows_rerun_identical']} "
             f"earlier result rows rerun with no difference.", "3.11"),
            ("One auction round with one job per robot reaches at least half the best total score (Proposition 1a)",
             f"Proved. Assumes non-negative pair scores, the best remaining pair fixed first, and bids that reach "
             f"every bidder; the score is measured down from a ceiling bid, not in cost, and loads of several items "
             f"are outside it. Checked on {bn['instances']} small instances (lowest share "
             f"{sh(bn['cbba_lite_vs_optimum']['1']['score_share_min'], 1)}).", "Appendix B, 3.11"),
            ("Bundles of several jobs: at least 1/2 of the best score when the bundle limit does not bind, 1/3 when "
             "it does (Proposition 1b, 1c)",
             "Proved under diminishing marginal gain. The 50&#8239;% published for the general case is quoted as "
             "reported in [5, 74]; the original proof [4] was not read. Deeper bundles are not this paper's default.",
             "Appendix B, 2.1"),
            (f"A position report is {V['P1-PROP6-CONTENT-B']} of content and {V['P1-PROP6-SECURED-B']} secured, and "
             f"no fixed-length code of its fields is shorter than {V['P1-PROP6-NEED-BITS']} bits (Proposition 6)",
             f"Proved: a count over the schema's fields. Tested: the codec's sizes, and {len(p.conf['vectors'])} "
             f"golden packets decoded each time the paper is built.", "Appendix B, 3.12"),
            (f"The full message set fits the {kbps(e53['nb'], 0)} budget for 20 rovers at one position report a "
             f"second with authentication, and not at ten (H13)",
             f"Tested: E53, {e53['draws']} draws of rover positions, fleet geometry, sizes counted by the codec. "
             f"{'Supported' if e53['sup'] else 'Not supported'}. A count of bytes: no radio and no channel access "
             f"was simulated.", "5.8"),
            ("A shared channel must run at <i>R</i>&nbsp;&ge;&nbsp;<i>L</i><i>h</i>/&eta; (Proposition 2)",
             f"Proved. Assumed: &eta;&nbsp;=&nbsp;{p.e53['eta']['scheduled']:g} for a scheduled channel, not swept; "
             f"the random-access value is derived.", "Appendix B, 5.8"),
            ("Age of a relayed report under per-hop loss, and under store and forward (Proposition 3)",
             "Proved. Part (a) assumes independent loss per hop and no retry, and is checked against a seeded "
             "simulation of that model each time the paper is built; bursty loss is not covered.", "Appendix B"),
            ("Store and forward with the lost-link rule loses fewer awarded jobs than drop and retry (H14)",
             f"Tested: E54, {d14['n']} seeds, a message-level replay of one recorded month at today's fleet, per-hop "
             f"loss 0.25, 14-day Earth blackout. {'Supported' if h14['supported'] else 'Not supported'}; the interval "
             f"is not adjusted for multiplicity. Not an engine run: the return is applied to the contact plan.",
             "5.9, 7"),
            ("Under the lost-link rule no reservation stays blocked past its timeout",
             "By construction of the rule, not measured. Measured in E54: the blocked hours the rule avoids.", "5.9"),
            ("Expected extra wait of a job after a rover fails, decided on the Moon and decided on Earth "
             "(Proposition 4)",
             "Proved as formulas, assuming independent heartbeat loss and fixed gaps and windows. Inputs assumed. Not "
             "tested: no rover failure is simulated.", "Appendix B, 3.13"),
            ("Operators needed against fleet size and autonomy level (Proposition 5)",
             "A model, not a result: request rates and handling times are assumed near published supervision ratios "
             "[76&ndash;79]. Not tested.", "Appendix B"),
            ("The capability filter with manifests made from the vehicle classes changes no outcome",
             f"Tested once: one {cf['days']}-day run, seed {cf['seed']}, {cf['identical']} of {cf['summary_values']} "
             f"summary values identical.", "3.12"),
            ("Robots that nobody hears drive to a rally point the mast can see",
             "Assumed (our rule). Swept: switched off in E41.", "3.9, 5.5"),
            ("Radio links exist on line of sight within 5&nbsp;km; a hop loses a message with probability 0.10",
             "Assumed. Swept in E41: range 2, 5, 10&nbsp;km and unlimited; loss 0 to 0.40 and bursty.", "3.4, 3.5, 5.5"),
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
