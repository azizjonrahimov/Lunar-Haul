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
D46 = os.path.join(ROOT, "data", "scenarios", "E46-design.json")
D48 = os.path.join(ROOT, "data", "scenarios", "E48-design.json")
OWN_CHECK_IDS: tuple = ("A8", "X7")   # the ids of P3's seven own checks in results/vv_phase5.json, assigned by B-79 batch 3
E48 = os.path.join(RES, "E48_sizing.json")
RULES = ("none", "first", "second", "posted")  # payment rules of E46 as run (change 7 of the PREREG restored first price)
RULE_NAME = {"none": "no payments", "first": "first price", "second": "the per-item second price",
             "posted": "the posted price with Shapley sharing"}
BID_RULES = ("first", "second")                 # the rules with a bid to scale (the manipulation test)
RULE_SHORT = {"none": "None", "first": "First price", "second": "Second price (per item)", "posted": "Posted price, Shapley sharing"}


def cap1(x: str) -> str:
    """Upper-case the first character only (str.capitalize lower-cases the rest: 'M USD', 'owner B')."""
    return x[:1].upper() + x[1:]
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


def vv5_checks_sentence(tag, results_section, check, exclude=()):
    d, rows = vv5_load(tag, check)
    rows = [x for x in rows if x.get("id") not in exclude]      # the paper's own checks are listed by name before this sentence
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
    return (f"In addition, {cnt(len(rows))} {'further ' if exclude else ''}checks of the engine's phase-5 verification suite (<code>lunarsim/vv5.py</code>, results in "
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
        self.d46 = jl(D46) if os.path.exists(D46) else None
        self.d48 = jl(D48) if os.path.exists(D48) else None
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
    def design(self, which, *keys):
        d = self.d46 if which == 46 else self.d48
        if d is None:
            raise Pending(f"data/scenarios/E{which}-design.json is missing")
        return _get(d, *keys)

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
    V["P3-CHANGES-SENTENCE"] = ("" if not later else
                                "Dated changes of [59] that touch this paper: " +
                                "; ".join(html.escape(c) for c in later) + ".")

    # --- checks (3.6, 5.8) -------------------------------------------------------------------------------------------
    fill("P3-CHECKS-SENTENCE", lambda: vv5_checks_sentence("P3", "5.8", check, exclude=OWN_CHECK_IDS), "B-79")
    fill("P3-FAILED-CHECKS-SENTENCE", lambda: vv5_failed_sentence("P3", "3.6", check), "B-79")
    fill("P3-ID-FIX-SENTENCE", lambda: idfix_sentence(check, ("E46", "E48")), "B-79 id fix")

    # --- E48 -----------------------------------------------------------------------------------------------------------
    def dr_seeds(xs):
        xs = [int(x) for x in xs]
        return f"{xs[0]}&ndash;{xs[-1]}" if xs == list(range(xs[0], xs[-1] + 1)) else ", ".join(str(x) for x in xs)

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
        out["fits"] = {"cpu": worst_cpu < 1.0, "memory": out["mem_worst_mb"] <= out["mem_capacity_mb"],     # memory is not scaled by the speed factor
                       "link": out["kbps_20"] <= out["kbps_target"]}
        return out

    def h10_sentence():
        s = e48_scaled()
        fits = s["fits"]
        parts = [f"the safety check at {num(s['cpu_share_worst'] * 100, 1)}{PCT} of one core of the reference processor at the worst class "
                 f"(the {CLASS_NAME[s['cpu_class_worst']]})",
                 f"the on-robot part at {unit(s['mem_worst_mb'], 'MB', 1)} of {unit(s['mem_capacity_mb'], 'MB')}",
                 f"and the radio traffic at {num(s['kbps_20'], 2)}{NB}kbit/s for 20 robots against the {num(s['kbps_target'], 0)}{NB}kbit/s target"]
        mk = r.s48("h10", "market_mb_per_day")
        parts.append(f"and the market's messages at {unit(mk, 'MB', 3)} a day against the {unit(r.s48('targets', 'market_mb_per_day'), 'MB')} target")
        fits["market"] = _fin(mk) <= _fin(r.s48("targets", "market_mb_per_day"))
        verdict = ("H10, exploratory, holds on every count: " if all(fits.values()) else
                   "H10, exploratory, does not hold on every count (" + ", ".join(k for k, v in fits.items() if not v) + " over the limit): ")
        return (verdict + ", ".join(parts) + f", with the scaling factor at {num(s['factor'], 1)} (range {num(s['range'][0], 1)}&ndash;{num(s['range'][1], 1)}); "
                "the bidding, which H10 also names, has no registered capacity (Section 5.1 reports the scaled round against the one-second decision).")
    fill("P3-H10-VERDICT-SENTENCE", h10_sentence, "E48")

    def e48_round():
        s = e48_scaled()
        worst = max((c for c in CLASSES if c != "BASE"), key=lambda c: r.s48("classes", c, "cpu_auction_round_ms")["p99"])
        a = r.s48("classes", worst, "cpu_auction_round_ms")
        med, p99 = a["median"] * s["factor"] / 1000.0, a["p99"] * s["factor"] / 1000.0
        over = p99 > 1.0
        return (f"Scaled by the same factor, an auction round on the {CLASS_NAME[worst]} takes {unit(med, 's', 2)} at the median and {unit(p99, 's', 2)} "
                f"at the 99th percentile, {'above' if over else 'within'} the one-second decision that the link model of Section 5.3 assumes.")
    fill("P3-E48-ROUND-SENTENCE", e48_round, "E48")

    def e48_reference():
        fl, lp = r.design(48, "flight"), r.design(48, "laptop")
        return (f"The reference flight processor is the {html.escape(fl['processor'])}, at {num(fl['benchmark'], 1)} {html.escape(fl['benchmark_name'])} "
                f"(source: {html.escape(fl['source'].split(';')[0])}) with {unit(fl['memory_mb'], 'MB')} of memory ({html.escape(fl['memory_flag'])}); the laptop "
                f"is an {html.escape(lp['processor'])} at {num(lp['benchmark'], 0)} {html.escape(lp['benchmark_name'])}, itself assumed "
                f"({html.escape(lp['benchmark_note'])}); the factor is their ratio, {num(fl['factor'], 1)}, with the range "
                f"{num(fl['factor_range'][0], 1)}&ndash;{num(fl['factor_range'][1], 1)} from the laptop's CoreMark range, and the CPU share uses "
                f"the 99th-percentile call time at every call, so it is an upper bound (Assumed).")
    fill("P3-E48-REFERENCE-SENTENCE", e48_reference, "E48 design")

    def e48_mtbf():
        fo = r.design(48, "failover")
        lv = ", ".join(unit(x, "h", 0) for x in fo["mtbf_levels_h"])
        return (f"The failover sweep runs the base computer at an MTBF of {lv}, a repair time of {unit(fo['repair_h'], 'h', 0)} and a re-election delay "
                f"of {unit(fo['reelect_h'], 'h', 1)}, on {words(len(fo['seeds']))} seeds of {html.escape(fo['regime'])}, flagged {html.escape(fo['flag'])}; "
                f"the re-election delay is an input, not a measurement.")
    fill("P3-E48-MTBF-SENTENCE", e48_mtbf, "E48 design")

    def e48_horizons():
        hz = r.design(48, "runs", "horizon_days")
        return ("The instrumented runs last " + ", ".join(f"{unit(float(v), 'days', 0)} at {k} times today's fleet" for k, v in hz.items()) +
                "; the ledger's yearly growth at four and eight times is extrapolated from jobs per hour.")
    fill("P3-E48-HORIZONS-SENTENCE", e48_horizons, "E48 design")

    def e48_traffic_note():
        by = r.s48("messages", "per_robot_hour_by_type")
        bt = r.s48("messages", "bytes_per_type")
        bits = []
        for m in ("1", "4", "8"):
            tot = sum(by[m].values())
            st = by[m]["status"]
            bytes_st = st * bt["status"]
            bytes_all = sum(v * (bt.get(k, (bt["bid"] + bt["award"] + bt["claim"]) / 3.0)) for k, v in by[m].items())
            bits.append(f"{pc(st / tot, 2)} of the messages and {pc(bytes_st / bytes_all, 2)} of the bytes at {m} times")
        omitted = "rebroadcasts, team-lift proposals, answers and commits, and ledger entries"
        return (f"The status message at the assumed 1{NB}Hz is " + ", ".join(bits) + f"; the traffic counts reservation requests, grants and releases "
                f"from road traversals, bids, awards and claims from auction rounds, and landing announcements, and omits {omitted}.")
    fill("P3-E48-TRAFFIC-NOTE", e48_traffic_note, "E48")

    def e48_cpu():
        s = e48_scaled()
        robots = [c for c in CLASSES if c != "BASE"]
        sc = {c: r.s48("classes", c, "cpu_safety_check_us") for c in robots}
        med = [sc[c]["median"] for c in robots]
        p99 = [sc[c]["p99"] for c in robots]
        worst = max(robots, key=lambda c: sc[c]["p99"])
        mem = {c: r.s48("classes", c, "peak_memory_mb") for c in robots}
        a = r.s48("classes", worst, "cpu_auction_round_ms")
        b = r.s48("classes", "BASE", "cpu_auction_round_ms")
        n_calls = {sc[c]["n"] for c in robots}
        return (f"Measured on {html.escape(s['laptop'])} and scaled to the {html.escape(s['processor'])} by a factor of {num(s['factor'], 1)} "
                f"(range {num(s['range'][0], 1)}&ndash;{num(s['range'][1], 1)}, Assumed): across the four robot classes a safety check took "
                f"{unit(min(med), '&micro;s', 0)}&ndash;{unit(max(med), '&micro;s', 0)} at the median and {unit(min(p99), '&micro;s', 0)}&ndash;"
                f"{unit(max(p99), '&micro;s', 0)} at the 99th percentile over {' and '.join(cnt(n) for n in sorted(n_calls))} calls per class, "
                f"worst on the {CLASS_NAME[worst]}; an auction round took {unit(a['median'], 'ms', 2)} at the median and {unit(a['p99'], 'ms', 1)} "
                f"at the 99th percentile over {cnt(a['n'])} rounds; the on-robot part peaked at "
                + (unit(max(mem.values()), 'MB', 2) if abs(max(mem.values()) - min(mem.values())) < 0.005 else
                   f"{unit(min(mem.values()), 'MB', 2)}&ndash;{unit(max(mem.values()), 'MB', 2)}")
                + f". The base computer's reservation check over the shared table, a different function from the "
                f"vehicles' safety check, took {unit(r.s48('classes', 'BASE', 'cpu_safety_check_us')['median'], '&micro;s', 0)} at the median and "
                f"{unit(r.s48('classes', 'BASE', 'cpu_safety_check_us')['p99'], '&micro;s', 0)} at the 99th percentile, and its auction round "
                f"{unit(b['median'], 'ms', 2)} and {unit(b['p99'], 'ms', 1)} (Table 5).")
    fill("P3-E48-RESULTS-CPU", e48_cpu, "E48")

    def e48_messages():
        s = e48_scaled()
        bt = r.s48("messages", "bytes_per_type")
        mph, bph = r.s48("messages", "per_robot_hour"), r.s48("messages", "bytes_per_robot_hour")
        led = r.s48("ledger_mb_per_year")
        types = "; ".join(f"{html.escape(k)} {unit(v, 'B')}" for k, v in bt.items())
        return (f"With the assumed byte layouts of Section 3.4 the message types weigh: {types}. Computed from each run's event counts and the "
                f"status rate, the fleet generated {num(mph['1'], 1)} messages and "
                f"{unit(bph['1'], 'B', 0)} per robot-hour at today's fleet, {num(mph['4'], 1)} and {unit(bph['4'], 'B', 0)} at four times, "
                f"and {num(mph['8'], 1)} and {unit(bph['8'], 'B', 0)} at eight times; at today's fleet that is {num(s['bps_robot'], 1)}{NB}B/s per robot "
                f"against the {num(s['bps_target'], 0)}{NB}B/s target and {num(s['kbps_20'], 2)}{NB}kbit/s for 20 robots against {num(s['kbps_target'], 0)}{NB}kbit/s. "
                f"The ledger grows by {unit(led['1'], 'MB', 1)} a year at today's fleet, {unit(led['4'], 'MB', 1)} at four times and {unit(led['8'], 'MB', 1)} at eight, "
                f"extrapolated from each run's jobs per hour. The market's messages come to {unit(r.s48('h10', 'market_mb_per_day'), 'MB', 3)} a day "
                f"at today's fleet.")
    fill("P3-E48-RESULTS-MESSAGES", e48_messages, "E48")

    def e48_link():
        bits = []
        for c in CLASSES:
            lk = r.s48("classes", c, "link")
            bits.append(f"the {CLASS_NAME[c]} (antenna {unit(lk['antenna_m'], 'm', 1)}, {unit(lk['tx_power_w'], 'W', 2)}): "
                        f"{num(lk['worst_hop_kbps'], 0)}{NB}kbit/s at the worst hop, {unit(lk['latency_budget_ms'], 'ms')} over "
                        f"{words(lk['latency_hops'])} hop{'s' if int(lk['latency_hops']) != 1 else ''}, direct view of the mast from "
                        f"{pc(lk['reachable_share'], 1)} of the route samples")
        f0 = r.s48("classes", "LTV1", "link")
        return (f"Per class, under the models of Section 3.3, at {num(f0['freq_ghz'], 1)}{NB}GHz with the data rate at the worst hop, the modelled "
                f"latency of a 100-byte message (10{NB}ms per hop plus transmit time plus the scaled safety check, against the one-second decision "
                f"the model assumes) and the share of route samples in direct view of the mast: " + "; ".join(bits) + ".")
    fill("P3-E48-RESULTS-LINK", e48_link, "E48")

    def e48_failover():
        fo = r.s48("failover")
        levels = [str(int(x)) if float(x) == int(x) else str(x) for x in fo["mtbf_levels_h"]]   # keys "500", "2000", "8000"
        bits, twice = [], 0
        for lv in levels:
            b = fo["by_mtbf"][lv]
            twice += int(b["jobs_assigned_twice"])
            bits.append(f"at an MTBF of {unit(float(lv), 'h')} the base computer was down {pc(b['down_share'], 2)} of the time, the fleet had no leader "
                        f"{pc(b['no_leader_share'], 2)} of the time with the assumed re-election delay of {unit(b['reelect_s'] / 3600.0, 'h', 1)}, and the base "
                        f"computer's assignment table was rebuilt after repair {num(b['merges'], 1)} times a year on average over {words(b['seeds'])} seeds")
        check(twice == 0, "no job was assigned twice after a rebuild (3.4, 3.6)")
        return "At" + "; ".join(bits)[2:] + f". After every rebuild the table held {words(twice)} job assigned twice."
    fill("P3-E48-RESULTS-FAILOVER", e48_failover, "E48")

    def e48_design():
        ru = r.s48("runs")
        dr, fo = r.design(48, "runs"), r.design(48, "failover")
        n_t, n_f = len(dr["seeds"]) * len(dr["multiples"]), len(fo["seeds"]) * len(fo["mtbf_levels_h"])
        check(n_t + n_f == int(ru["n"]), "E48 runs = timing runs + failover runs")
        return (f"{cnt(ru['n'])} runs were instrumented: {words(n_t)} timing runs, seeds {', '.join(str(x) for x in dr['seeds'])} at "
                f"{', '.join(str(x) for x in dr['multiples'])} times today's fleet ({html.escape(dr['regime'])}), and {words(n_f)} failover runs, seeds "
                f"{dr_seeds(fo['seeds'])} at the three MTBF levels ({html.escape(fo['regime'])}); the auction round and the peak memory are measured "
                f"once per run, not per class.")
    fill("P3-E48-DESIGN-SENTENCE", e48_design, "E48")
    fill("P3-E48-COMPUTE-SENTENCE", lambda: f"The instrumented runs of E48 took {unit(r.s48('runs', 'run_s_mean'), 's', 0)} each on average and "
         f"{unit(r.s48('runs', 'cpu_h'), 'h', 1)} of processor time in all.", "E48")

    def e48_round_p99_s():
        s = e48_scaled()
        worst = max((c for c in CLASSES if c != "BASE"), key=lambda c: r.s48("classes", c, "cpu_auction_round_ms")["p99"])
        return r.s48("classes", worst, "cpu_auction_round_ms")["p99"] * s["factor"] / 1000.0

    def e48_clause(kind):
        s = e48_scaled()
        fits_all = all(s["fits"].values())
        ok = "fits" if fits_all else "does not fit"
        p99s = e48_round_p99_s()
        round_txt = (f"one auction round in a hundred takes {unit(p99s, 's', 2)}, above the one-second decision" if p99s > 1.0 else
                     f"an auction round stays within the one-second decision at the 99th percentile")
        if kind == "abstract":
            return (f"Scaled by {num(s['factor'], 1)} to the reference flight processor, the safety check takes {num(s['cpu_share_worst'] * 100, 1)}{PCT} "
                    f"of one core at the worst class and the radio traffic is {num(s['kbps_20'], 2)}{NB}kbit/s for 20 robots, within target; {round_txt}.")
        if kind == "intro":
            return (f"Lunar ATC {ok} the vehicles of Section 3.2 as implemented: at the worst class the safety check takes "
                    f"{num(s['cpu_share_worst'] * 100, 1)}{PCT} of one core of the reference processor, the on-robot part {unit(s['mem_worst_mb'], 'MB', 1)}, "
                    f"and 20 robots generate {num(s['kbps_20'], 2)}{NB}kbit/s against a 16{NB}kbit/s-class link (Sections 5.1 to 5.3).")
        if kind == "discussion":
            return (f"the safety check, the on-robot memory and the radio traffic {'fit' if fits_all else 'do not all fit'} the reference processor and the link class "
                    f"with the stated factor, the class nearest a limit being the {CLASS_NAME[s['cpu_class_worst']]}, while {round_txt}.")
        if kind == "comparison":
            bph = r.s48("messages", "bytes_per_robot_hour")
            ratio = 13800.0 / max(_fin(bph["1"]) / 3600.0, 1e-9)
            by = r.s48("messages", "per_robot_hour_by_type", "1")
            market = sum(v for k, v in by.items() if k != "status")
            return (f"The radio traffic of Lunar ATC, {num(s['bps_robot'], 1)}{NB}B/s per robot, is {num(ratio, 0)} times smaller than the "
                    f"13.8{NB}kB/s the two-rover convoy controller of [25] used; the market's own messages come to {num(market, 2)} per robot-hour "
                    f"at today's fleet.")
        if kind == "conclusion":
            return (f"On flight hardware the safety check and radio traffic {'fit' if fits_all else 'do not fit'} the reference processor and "
                    f"link for 20 robots; {round_txt}.")
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
    M = 1e6
    MUSD = "M" + NB + "USD"

    def musd(x_usd, nd=2, sign=False):
        return unit(x_usd / M, MUSD, nd, sign)

    def musd_m(x_m, nd=2, sign=False):
        return unit(x_m, MUSD, nd, sign)

    def ci_m(lo, hi, nd=2):
        return ci(lo / M, hi / M, nd)

    def alone_mean(split, owner):
        return r.pair46(f"coalition ABC - alone, owner {owner} ({split})", "profit_usd")["b_mean"]

    fill("P3-E46-N-RUNS", lambda: cnt(r.f46("n_rows")), "E46")

    def e46_design():
        d = r.f46("design")
        n, ns, nsp = int(r.f46("n_rows")), len(d["seeds"]), len(d["splits"])
        kinds = n / (ns * nsp)
        check(kinds == int(kinds), "E46 run count = seeds x splits x run kinds")
        check(all(x in d["rules"] for x in RULES) and len(d["rules"]) == len(RULES), "E46 ran the four rules of 3.5")
        return (f"{cnt(n)} physical runs, {cnt(ns)} seeds by {cnt(nsp)} splits by {cnt(kinds)} run kinds (the pooled market, the oracle, "
                f"the owners alone, the three pair coalitions and one owner at a time scaling its asks by each of the {cnt(len(d['k_levels']))} "
                f"factors); payments are computed afterwards from each run's job log, so the four rules and the {cnt(len(d['q_levels']))} audit "
                f"shares share one allocation per seed and cost no further runs, giving {cnt(r.f46('n_cells'))} cells of {cnt(ns)} seeds. "
                f"The first-price cell is the one restored by change 7 of [59].")
    fill("P3-E46-DESIGN-SENTENCE", e46_design, "E46")
    fill("P3-E46-COMPUTE-SENTENCE", lambda: f"A simulated year of E46 took {unit(r.f46('run_s_mean'), 's', 0)} on average and the experiment "
         f"{unit(r.f46('cpu_h'), 'h', 1)} of processor time.", "E46")

    def e46_tariff():
        t = r.f46("tariff_usd_per_tkm")
        return (f"In E46 the posted price is {unit(t['3eq'], 'USD per tonne-kilometre', 2)} with equal shares and "
                f"{unit(t['3uneq'], 'USD per tonne-kilometre', 2)} with 50/35/15 shares, set before the main runs as the price at which "
                f"the carriers' true costs are recovered over ten calibration seeds (101&ndash;110) that the main runs do not use; "
                f"the audit penalty multiple is m = {num(r.f46('audit_penalty_multiple'), 0)} (Assumed; the design file declares 2&ndash;5 and E46 runs one value).")
    fill("P3-E46-TARIFF-SENTENCE", e46_tariff, "E46")

    def e46_loss():
        ml = r.design(46, "message_loss")
        check(float(ml["value"]) == 0.0, "E46 runs with a perfect radio by design (3.3, 4.2)")
        return (f"E46 sets the message loss to {num(ml['value'], 2)} in every cell, the owners-alone and coalition runs included: a perfect radio by "
                f"design, so that paired differences show incentives and not message-loss noise, which the companion paper [60] covers.")
    fill("P3-E46-LOSS-SENTENCE", e46_loss, "E46 design")

    def e46_reserve():
        sp = r.f46("second_price")
        bits = []
        for split in SPLITS:
            x = _get(sp, split)
            bits.append(f"with {SPLIT_NAME[split]} {pc(x['with_alternative_share'], 0)} of jobs had a competing free vehicle, {pc(x['reserve_share'], 0)} were "
                        f"priced by the tariff reserve and {pc(x['floor_at_ask_share'], 0)} paid the carrier its own ask")
        return "Under the per-item second price, " + "; ".join(bits) + "."
    fill("P3-E46-RESERVE-SENTENCE", e46_reserve, "E46 fit second_price (BACKEND)")

    def e46_budget():
        bg = r.f46("budget")
        bits = []
        for rule in ("first", "second"):
            for split in SPLITS:
                b = _get(bg, rule, split)
                bits.append(f"{musd(b['mean'], 2, sign=True)} {ci_m(b['lo'], b['hi'])} under {RULE_NAME[rule]} with {SPLIT_NAME[split]}")
        for split in SPLITS:
            check(abs(_get(bg, "posted", split)["mean"]) < 1e-6 and abs(_get(bg, "none", split)["mean"]) < 1e-6 if "none" in bg else abs(_get(bg, "posted", split)["mean"]) < 1e-6,
                  f"budget zero under the posted price ({split})")
        f3 = _get(bg, "first", "3eq")
        return (f"The operator's budget with honest asks, receipts less payouts with its 95{PCT} interval over seeds, was " + "; ".join(bits) +
                f"; zero under the posted price and under no payments by construction" +
                f". Under first price with honest asks the carriers are paid their true costs, so that budget is the tariff receipts "
                f"({musd(f3['receipts_mean'], 1)} a year with equal shares) less the true carrier cost ({musd(f3['payouts_mean'], 1)}); the tariff was set "
                f"to recover that cost on the calibration seeds (Section 3.5).")
    fill("P3-E46-BUDGET-SENTENCE", e46_budget, "E46 fit budget (BACKEND)")

    def e46_transfers(kind="sentence"):
        tr = r.f46("transfers")
        sw = r.f46("settled_with_transfers")
        bits = []
        for split in SPLITS:
            owners = ", ".join(f"owner {o} {musd(_get(tr, split, o)['mean'], 0, sign=True)} {ci_m(_get(tr, split, o)['lo'], _get(tr, split, o)['hi'], 0)}" for o in "ABC")
            bits.append(f"with {SPLIT_NAME[split]} {owners}")
        payer = {split: min("ABC", key=lambda o: _get(tr, split, o)["mean"]) for split in SPLITS}
        if kind == "clause":
            return ("the Shapley transfers move " + " and ".join(f"{musd(-_get(tr, split, payer[split])['mean'], 0)} a year from owner {payer[split]} with {SPLIT_NAME[split]}" for split in SPLITS)
                    + " to the other two owners")
        return (f"The Shapley sharing is settled by transfers between owners, Shapley payoff less the owner's cash profit under the posted price on the same seed: "
                + "; ".join(bits) + f". With the transfers included, the cash settled on Earth under the posted price is "
                + " and ".join(f"{musd(_get(sw, split)['mean'], 1)} {ci_m(_get(sw, split)['lo'], _get(sw, split)['hi'], 1)} a year with {SPLIT_NAME[split]}" for split in SPLITS)
                + ", against the tariff cash alone in Table 7.")
    fill("P3-E46-TRANSFERS-SENTENCE", e46_transfers, "E46 fit transfers (BACKEND)")
    fill("P3-E46-TRANSFERS-CLAUSE", lambda: e46_transfers("clause"), "E46 fit transfers (BACKEND)")

    def e46_vs_none(kind="sentence"):
        vn = r.f46("vs_none")
        worse = []
        bits = []
        for rule in ("first", "second", "posted"):
            for split in SPLITS:
                owners = []
                for o in "ABC":
                    x = _get(vn, rule, split, o)
                    owners.append(f"{o} {musd(x['mean'], 1, sign=True)} {ci_m(x['lo'], x['hi'], 1)}")
                    if x["hi"] < 0:
                        worse.append(f"owner {o} under {RULE_NAME[rule]} with {SPLIT_NAME[split]}")
                bits.append(f"under {RULE_NAME[rule]} with {SPLIT_NAME[split]} " + ", ".join(owners))
        owners_worse = sorted({w.split()[1] for w in worse})
        cases = len([x for x in ("first", "second", "posted") for sp in SPLITS])
        one_owner_everywhere = len(owners_worse) == 1 and len(worse) == cases
        if kind == "summary":
            return owners_worse, one_owner_everywhere, worse
        if kind == "clause":
            if not worse:
                return "no owner is worse off under any paid rule than under none"
            if one_owner_everywhere:
                incl = [f"{o}'s under {RULE_NAME[rule]} with {SPLIT_NAME[sp]}" for rule in ("first", "second", "posted") for sp in SPLITS for o in "ABC"
                        if o != owners_worse[0] and _get(vn, rule, sp, o)["lo"] <= 0 <= _get(vn, rule, sp, o)["hi"]]
                return (f"against no payments owner {owners_worse[0]} is worse off under every paid rule and both splits, with the interval below zero; "
                        f"no other owner's interval lies below zero" + (f" ({', '.join(incl)} include{'s' if len(incl) == 1 else ''} it)" if incl else ""))
            return "against no payments " + "; ".join(worse) + (" is" if len(worse) == 1 else " are") + " worse off, with the interval below zero"
        return ("Against the no-payment pooled market on the same seeds, each owner's profit changed by: " + "; ".join(bits) + " (M USD a year).")
    fill("P3-E46-VS-NONE-SENTENCE", e46_vs_none, "E46 fit vs_none (BACKEND)")
    fill("P3-E46-VS-NONE-CLAUSE", lambda: e46_vs_none("clause"), "E46 fit vs_none (BACKEND)")

    def e46_surplus():
        bits = []
        for sp in SPLITS:
            al = {o: alone_mean(sp, o) for o in "ABC"}
            none_c = r.cell46("none", sp)
            gain_none = {o: none_c[f"profit_{o}_musd"] * M - al[o] for o in "ABC"}
            rows = {x["owner"]: x for x in r.f46("H5", sp, "clause3", "rows") if x["coalition"] == "ABC"}
            gain_sh = {o: rows[o]["mean"] for o in "ABC"}
            tot_n, tot_s = sum(gain_none.values()), sum(gain_sh.values())
            check(abs(tot_n - tot_s) < 0.02 * abs(tot_s), f"the pooling gain over alone is the same total under no payments and under Shapley ({sp})")
            tr = {o: _get(r.f46("transfers"), sp, o)["mean"] for o in "ABC"}
            top_n = max("ABC", key=lambda o: gain_none[o])
            top_s = max("ABC", key=lambda o: gain_sh[o])
            bits.append(f"with {SPLIT_NAME[sp]} the pooling gain over alone is {musd(tot_s, 0)} a year; under no payments owner {top_n} keeps "
                        f"{pc(gain_none[top_n] / tot_n, 0)} of it ({', '.join(f'{o} {pc(gain_none[o] / tot_n, 0)}' for o in 'ABC')}), under the Shapley sharing "
                        f"owner {top_s} receives the largest share, {pc(gain_sh[top_s] / tot_s, 0)} ({', '.join(f'{o} {pc(gain_sh[o] / tot_s, 0)}' for o in 'ABC')}), "
                        f"and the transfer of each owner is the difference between the two ({', '.join(f'{o} {musd(tr[o], 0, sign=True)}' for o in 'ABC')})")
        return cap1("; ".join(bits)) + "."
    fill("P3-E46-SURPLUS-SENTENCE", e46_surplus, "E46")

    def h5_power(kind):
        ex = r.f46("exploratory")
        afg = {sp: _get(ex, "allocation_fixed_gain", "first", sp) for sp in SPLITS}
        rt = {sp: _get(ex, "reallocation_term", sp) for sp in SPLITS}
        pos = all(afg[sp]["lo"] > 0 for sp in SPLITS)
        ratio = min(rt[sp]["sd"] / afg[sp]["gain"] for sp in SPLITS if afg[sp]["gain"] > 0)
        if kind == "abstract":
            return (f"A post hoc split shows the first-price gain's cash part {'positive' if pos else 'not clearly positive'}, "
                    f"{num(min(a['gain'] for a in afg.values()) / M, 1, sign=True)} to {musd(max(a['gain'] for a in afg.values()), 1, sign=True)}, "
                    f"and its delay part noisy.")
        if kind == "conclusion":
            return (f"A post hoc split shows that gain's cash part {'positive' if pos else 'not clearly positive'} and its delay part noisy.")
        return (f"The cash part of that gain, with the allocation held fixed, was {musd(afg['3eq']['gain'], 2, sign=True)} a year "
                f"{ci_m(afg['3eq']['lo'], afg['3eq']['hi'])} with equal shares and {musd(afg['3uneq']['gain'], 2, sign=True)} "
                f"{ci_m(afg['3uneq']['lo'], afg['3uneq']['hi'])} with 50/35/15 shares, a decomposition made after the runs (Section 4.6); the registered "
                f"measure adds the deviator's own cargo delay, whose standard deviation over seeds is at least {num(ratio, 1)} times that cash.")
    fill("P3-H5-POWER-CLAUSE", lambda: h5_power("full"), "E46 post hoc")
    fill("P3-H5-POWER-ABSTRACT-CLAUSE", lambda: h5_power("abstract"), "E46 post hoc")
    fill("P3-H5-POWER-CONCLUSION-CLAUSE", lambda: h5_power("conclusion"), "E46 post hoc")

    def own_checks():
        if not OWN_CHECK_IDS:
            raise Pending("the ids of P3's seven own checks are assigned by B-79 batch 3")
        d, rows = vv5_load("P3", check)
        got = {(x.get("id"), x.get("sub")): x for x in rows}
        have = [x for x in rows if x.get("id") in OWN_CHECK_IDS]
        missing = [i for i in OWN_CHECK_IDS if not any(x.get("id") == i for x in rows)]
        if missing:
            raise Pending("own checks not yet in results/vv_phase5.json: " + ", ".join(missing))
        names = []                                  # one entry per check; a check with several rows shares the name before the colon
        for x in have:
            base = str(x.get("name", "")).split(": ")[0]
            if base not in [n for n, _ in names]:
                names.append((base, str(x.get("id"))))
        low1 = lambda t: t[:1].lower() + t[1:]
        return ("; ".join(f"{low1(html.escape(n))} ({html.escape(i)})" for n, i in names) +
                f" ({words(len(names))} checks in {cnt(len(have))} rows; outcomes in Section 5.8).")
    fill("P3-OWN-CHECKS-SENTENCE", own_checks, "B-79 batch 3")

    def sign_word(x, pos="a surplus", neg="a deficit", zero="a balanced budget"):
        return pos if x > 1e-9 else (neg if x < -1e-9 else zero)

    def e46_rules():
        eff = {sp: r.cell46("none", sp)["efficiency_loss_pct"] for sp in SPLITS}
        for sp in SPLITS:
            for rule in RULES:
                check(abs(r.cell46(rule, sp)["efficiency_loss_pct"] - eff[sp]) < 1e-6, f"one allocation: the efficiency loss is the same under every rule ({sp})")
            for r1, r2 in (("second", "first"), ("posted", "first"), ("posted", "second")):
                for met in ("delay_h", "delivered"):
                    pr = r.pair46(f"{r1} - {r2} ({sp}, truthful)", met)
                    check(pr["mean"] == 0 and pr["lo"] == 0 and pr["hi"] == 0, f"one allocation: {r1} - {r2} on {met} is zero on every seed ({sp})")
            check(abs(r.cell46("none", sp)["operator_budget_musd"]) < 1e-9, f"no payments: the operator's budget is zero ({sp})")
            check(abs(r.cell46("posted", sp)["operator_budget_musd"]) < 1e-6, f"posted price: the same tariff in and out, budget zero ({sp})")
        bud = {rule: {sp: r.cell46(rule, sp)["operator_budget_musd"] for sp in SPLITS} for rule in RULES}
        paid = [rule for rule in RULES if rule != "none"]
        settled = [r.cell46(rule, sp)["settled_earth_musd"] for rule in paid for sp in SPLITS]
        open_end = [r.cell46(rule, sp)["open_end_musd"] for rule in paid for sp in SPLITS]
        return (f"With honest bids the four rules share one allocation, so the items delivered and the cargo delay are the same under every rule on every "
                f"seed (the paired differences between rules in delay and in deliveries are exactly zero), and the market's system cost, true carrier cost "
                f"plus delay cost, was above the oracle's by {pc(eff['3eq'] / 100, 1)} with equal shares and {pc(eff['3uneq'] / 100, 1)} with 50/35/15 shares "
                f"under every rule. Under no payments no money moved; under the posted price the budget "
                f"{sign_word(bud['posted']['3eq'], 'ran a surplus', 'ran a deficit', 'was balanced')} by construction, the same tariff paid in by shippers and out to carriers. Across the three paid rules and "
                f"both splits the cash settled on Earth was {musd_m(min(settled), 1)} to {musd_m(max(settled), 1)} a year and the balance still open at "
                f"the year's end at most {musd_m(max(open_end), 2)} (Table 7).")
    fill("P3-E46-RESULTS-RULES", e46_rules, "E46")

    def e46_ir():
        c = r.e46c
        viol_all = int(c["ir_violations"].sum())
        viol_truth = sum(int(r.cell46(rule, sp)["ir_violations"]) for rule in RULES for sp in SPLITS)
        al = {sp: {o: alone_mean(sp, o) for o in "ABC"} for sp in SPLITS}
        rows = sorted(({**x, "split": sp} for sp in SPLITS for x in r.f46("H5", sp, "clause3", "rows")), key=lambda x: x["mean"])
        lo_row, hi_row = rows[0], rows[-1]
        ties = [x for x in rows if abs(x["mean"] - lo_row["mean"]) < 1e-6 and x["coalition"] == lo_row["coalition"] and x["split"] == lo_row["split"]]
        lo_who = (f"owner {html.escape(lo_row['owner'])}'s" if len(ties) == 1 else
                  "each of " + " and ".join(html.escape(x["owner"]) for x in ties) + "'s")
        return (f"Working alone on their own cargo on the same seeds, the owners' mean profits were {musd(al['3eq']['A'], 1)}, "
                f"{musd(al['3eq']['B'], 1)} and {musd(al['3eq']['C'], 1)} a year for A, B and C with equal shares and {musd(al['3uneq']['A'], 1)}, "
                f"{musd(al['3uneq']['B'], 1)} and {musd(al['3uneq']['C'], 1)} with 50/35/15 shares (alone profit is the negative of the owner's vehicle "
                f"costs and its cargo's delay cost, with no receipts). Under every rule and split each owner's mean market profit (Table 7) was above its alone "
                f"profit: the market left an owner below alone in {cnt(viol_truth)} of the {cnt(len(RULES) * len(SPLITS) * 3)} owner-rule-split cases "
                f"with honest bids and in {cnt(viol_all)} of the {cnt(len(c) * 3)} owner-cell cases over every cell. Under the posted price the "
                f"profit of Table 7 is the owner's Shapley value of the coalition's value, true carrier costs plus delay costs with the sign reversed, "
                f"not its cash, and that value is what the Shapley clause of H5 compares with alone. In every tested coalition every owner's Shapley "
                f"value was above its alone profit: the smallest difference was {lo_who} in coalition "
                f"{html.escape(lo_row['coalition'])} with {SPLIT_NAME[lo_row['split']]}, {musd(lo_row['mean'], 1, sign=True)} "
                f"{ci_m(lo_row['lo'], lo_row['hi'], 1)}, and the largest owner {html.escape(hi_row['owner'])}'s in coalition "
                f"{html.escape(hi_row['coalition'])} with {SPLIT_NAME[hi_row['split']]}, {musd(hi_row['mean'], 0, sign=True)} "
                f"{ci_m(hi_row['lo'], hi_row['hi'], 0)} (Table 8).")
    fill("P3-E46-RESULTS-IR", e46_ir, "E46")

    def e46_manip():
        bits = []
        for sp in SPLITS:
            g = {rule: r.f46("max_gain", rule, sp) for rule in BID_RULES}
            same = all(g[x]["owner"] == g["first"]["owner"] and abs(g[x]["k"] - g["first"]["k"]) < 1e-9 for x in BID_RULES)
            effect = (f"that deviation changed the fleet's cargo delay by {unit(g['first']['system_cost_h'], 'h', 0, sign=True)} "
                      f"{ci(g['first']['lo_cost'], g['first']['hi_cost'], 0)} and the system cost by {musd(g['first']['system_cost_usd'], 2, sign=True)}")
            if same:
                for x in BID_RULES:
                    check(abs(g[x]["system_cost_h"] - g["first"]["system_cost_h"]) < 1e-9, f"one deviation run under both bid rules ({sp})")
                bits.append(f"with {SPLIT_NAME[sp]} the largest gain from scaling came from owner {html.escape(str(g['first']['owner']))} at "
                            f"k = {num(g['first']['k'], 2)} under both bid rules: {musd(g['first']['gain'], 2, sign=True)} a year "
                            f"{ci_m(g['first']['lo'], g['first']['hi'], 2)} under first price and {musd(g['second']['gain'], 2, sign=True)} "
                            f"{ci_m(g['second']['lo'], g['second']['hi'], 2)} under the per-item second price; {effect}")
            else:
                for rule in BID_RULES:
                    x = g[rule]
                    bits.append(f"with {SPLIT_NAME[sp]} under {RULE_NAME[rule]} the largest gain from scaling was {musd(x['gain'], 2, sign=True)} a year "
                                f"{ci_m(x['lo'], x['hi'], 2)} for owner {html.escape(str(x['owner']))} at k = {num(x['k'], 2)}; that deviation changed "
                                f"the fleet's cargo delay by {unit(x['system_cost_h'], 'h', 0, sign=True)} {ci(x['lo_cost'], x['hi_cost'], 0)} and the "
                                f"system cost by {musd(x['system_cost_usd'], 2, sign=True)}")
        return ". ".join(cap1(b) for b in bits) + ". Under the posted price there is no bid to scale."
    fill("P3-E46-RESULTS-MANIP", e46_manip, "E46")

    def e46_audits():
        bits = []
        for rule in BID_RULES:
            for sp in SPLITS:
                au = r.f46("audits", rule, sp)
                qs = []
                for q in ("5", "20"):
                    rec = au[q]["recovered_share"]
                    qs.append(f"an audit share of {q}{PCT} recovered {pc(rec, 0) if rec is not None else 'none'} of the gain, leaving "
                              f"{musd(au[q]['net_gain'], 2, sign=True)}")
                bits.append(f"under {RULE_NAME[rule]} with {SPLIT_NAME[sp]} " + " and ".join(qs))
        return cap1("; ".join(bits)) + " a year net of expected penalties, at a penalty multiple of " + \
            f"{num(r.f46('audit_penalty_multiple'), 0)} times the misreport."
    fill("P3-E46-RESULTS-AUDITS", e46_audits, "E46")

    def h5_flags():
        """Per clause, the per-split verdicts, recomputed here from the intervals by the rules of PREREG change 7 (Section 4.1)."""
        out = {}
        for sp in SPLITS:
            h = r.f46("H5", sp)
            c1, c2, c3 = h["clause1"], h["clause2"], h["clause3"]
            if c1.get("tested", True):
                check(bool(c1["supported"]) == (float(c1["lo"]) > 0), f"clause 1 ({sp}): supported iff the largest first-price gain's interval is above zero")
            if c2.get("tested", True):
                check(bool(c2["supported"]) == (float(c2["diff_hi"]) < 0 and float(c2["diff_mean"]) < 0),
                      f"clause 2 ({sp}): supported iff the second-price gain is smaller with the paired difference's interval excluding zero")
            if c3.get("tested", True):
                check(bool(c3["supported"]) == (float(c3["min_upper"]) >= 0),
                      f"clause 3 ({sp}): supported iff no owner's coalition-less-alone interval lies entirely below zero")
                check(float(c3["min_lower"]) <= float(c3["min_upper"]), f"clause 3 ({sp}): bounds ordered")
            out[sp] = (c1, c2, c3)
        return out

    def verdict(cs):
        """One word per clause over both splits: supported / not supported / supported with <split> only / not tested."""
        tested = [sp for sp, c in cs.items() if c.get("tested", True)]
        if not tested:
            return "not tested"
        sup = [sp for sp in tested if cs[sp]["supported"]]
        if len(sup) == len(tested):
            return "supported"
        if not sup:
            return "not supported"
        return "supported with " + " and ".join(SPLIT_NAME[sp] for sp in sup) + " only"

    def h5_sentence(kind="full"):
        f = h5_flags()
        v1 = verdict({sp: f[sp][0] for sp in SPLITS})
        v2 = verdict({sp: f[sp][1] for sp in SPLITS})
        v3 = verdict({sp: f[sp][2] for sp in SPLITS})
        c1e, c1u = f["3eq"][0], f["3uneq"][0]
        c2e, c2u = f["3eq"][1], f["3uneq"][1]
        c3e, c3u = f["3eq"][2], f["3uneq"][2]
        if kind == "full":
            return (f"H5 clause by clause, in both splits: that first-price bids reward shading is {v1} (the largest first-price gain's 95{PCT} "
                    f"interval is {ci_m(c1e['lo'], c1e['hi'])} with equal shares and {ci_m(c1u['lo'], c1u['hi'])} with 50/35/15 shares, in {MUSD} a year); "
                    f"that the per-item second price reduces the largest gain is {v2} (paired difference {musd(c2e['diff_mean'], 2, sign=True)} "
                    f"{ci_m(c2e['diff_lo'], c2e['diff_hi'])} and {musd(c2u['diff_mean'], 2, sign=True)} {ci_m(c2u['diff_lo'], c2u['diff_hi'])}); "
                    f"that the posted price with Shapley sharing leaves no owner worse off than alone in any tested coalition is {v3}, against the "
                    f"owners-alone baseline of Section 3.5 (the comparison against no payments is in Section 5.6; over every "
                    f"owner and coalition the smallest upper bound of Shapley value less alone profit is {musd(c3e['min_upper'], 1, sign=True)} and "
                    f"{musd(c3u['min_upper'], 1, sign=True)}, and the smallest lower bound {musd(c3e['min_lower'], 1, sign=True)} and "
                    f"{musd(c3u['min_lower'], 1, sign=True)}).")
        gmax = max(c1e["gain"], c1u["gain"])
        incl = "includes" if (c1e["lo"] <= 0 <= c1e["hi"] or c1u["lo"] <= 0 <= c1u["hi"]) else "excludes"
        if kind == "abstract":
            return (f"First-price bid shading gained at most {musd(gmax, 1)} a year with an interval {'including' if incl == 'includes' else 'excluding'} zero, so that clause of H5 is {v1}; "
                    f"the second price {'reduced' if v2 == 'supported' else 'did not reduce'} it ({v2}); the Shapley clause is {v3}.")
        if kind == "intro":
            return (f"H5's first clause, that first-price bids reward shading, is {v1}; its second, that the second price reduces the gain, is {v2}; "
                    f"its third, that the posted price with Shapley sharing leaves no owner worse off than alone, is {v3} (Section 5.7).")
        raise KeyError(kind)
    fill("P3-H5-VERDICT-SENTENCE", h5_sentence, "E46")
    fill("P3-H5-ABSTRACT-CLAUSE", lambda: h5_sentence("abstract"), "E46")
    fill("P3-H5-INTRO-CLAUSE", lambda: h5_sentence("intro"), "E46")

    def e46_clause(kind):
        ir_ok = [rule for rule in RULES if all(int(r.cell46(rule, sp)["ir_violations"]) == 0 for sp in SPLITS)]
        every = len(ir_ok) == len(RULES)
        rules_txt = ("every rule" if every else (", ".join(RULE_NAME[x] for x in ir_ok) if ir_ok else "no rule"))
        bud = {rule: {sp: r.cell46(rule, sp)["operator_budget_musd"] for sp in SPLITS} for rule in RULES}
        mg = {rule: {sp: r.f46("max_gain", rule, sp) for sp in SPLITS} for rule in BID_RULES}
        gmax = max(g["gain"] for rule in BID_RULES for g in mg[rule].values())
        au20 = {rule: {sp: r.f46("audits", rule, sp, "20")["net_gain"] for sp in SPLITS} for rule in BID_RULES}
        removed = [rule for rule in BID_RULES if all(au20[rule][sp] <= 0 for sp in SPLITS)]
        sec_ratio = bud["second"]["3eq"] / bud["first"]["3eq"] if bud["first"]["3eq"] else None
        if kind == "abstract":
            bid_sign = {sign_word(bud[x]['3eq']) for x in BID_RULES}
            ow, one, worse = e46_vs_none("summary")
            vs = ("" if not worse else (f", but owner {ow[0]} fell below the no-payment market under every paid rule" if one else
                                        f", but {cnt(len(worse))} owner-rule-split cases fell below the no-payment market"))
            return (f"Every owner beat its alone profit under {rules_txt}{vs}; "
                    f"{('the bid rules ran ' + bid_sign.pop()) if len(bid_sign) == 1 else ('first price ran ' + sign_word(bud['first']['3eq']) + ' and the second price ' + sign_word(bud['second']['3eq']))}, "
                    f"the posted price {sign_word(bud['posted']['3eq'], 'ran a surplus', 'ran a deficit', 'broke even')}.")
        if kind == "intro":
            ow, one, worse = e46_vs_none("summary")
            vs = ("" if not worse else (f", though owner {ow[0]} was worse off than under no payments under every paid rule" if one else
                                        f", though {cnt(len(worse))} owner-rule-split cases were worse off than under no payments"))
            return (f"In the market, {rules_txt} made every owner at least as well off as alone in both splits{vs}; the operator ran "
                    f"{sign_word(bud['first']['3eq'])} under first price, {sign_word(bud['second']['3eq'])} under the second price and "
                    f"{sign_word(bud['posted']['3eq'])} under the posted price (Sections 5.5 to 5.7).")
        if kind == "discussion":
            return (f"{rules_txt} left every owner's mean profit above its alone profit; the operator ran {sign_word(bud['first']['3eq'])} "
                    f"under first price ({musd_m(abs(bud['first']['3eq']))} a year with equal shares), {sign_word(bud['second']['3eq'])} under the "
                    f"second price ({musd_m(abs(bud['second']['3eq']))}, {num(abs(sec_ratio), 1) if sec_ratio else 'n/a'} times first price's) and "
                    f"{sign_word(bud['posted']['3eq'])} under the posted price; the largest gain from scaling bids was {musd(gmax, 2, sign=True)} a year, "
                    f"and audits at 20{PCT} {('removed it under ' + ' and '.join(RULE_NAME[x] for x in removed)) if removed else 'did not remove it under either bid rule'}.")
        if kind == "comparison":
            small = r.pair46("coalition ABC - alone, owner C (3uneq)", "profit_usd")
            return (f"The smallest owner of the 50/35/15 split {'gained' if small['lo'] > 0 else ('lost' if small['hi'] < 0 else 'neither gained nor lost')} "
                    f"under the posted price with Shapley sharing ({musd(small['mean'], 0, sign=True)} a year {ci_m(small['lo'], small['hi'], 0)} in the "
                    f"grand coalition against working alone) and {'lost' if r.f46('vs_none', 'posted', '3uneq', 'C')['hi'] < 0 else 'did not lose'} "
                    f"{musd(abs(r.f46('vs_none', 'posted', '3uneq', 'C')['mean']), 0)} against the no-payment market, where Kondor's smallest operator paid the largest "
                    f"fleet penalty [39]; the operator's budget "
                    f"under the second price was {sign_word(bud['second']['3eq'])}.")
        if kind == "implication":
            return (f"{rules_txt} kept every owner in; the budget was {sign_word(bud['posted']['3eq'])} under the posted price and "
                    f"{sign_word(bud['second']['3eq'])} under the second price.")
        if kind == "conclusion":
            ow, one, worse = e46_vs_none("summary")
            vs = ("" if not worse else (f" but owner {ow[0]} lost against no payments under every paid rule," if one else
                                        f" but {cnt(len(worse))} owner-rule-split cases lost against no payments,"))
            return (f"Every owner beat alone under {rules_txt},{vs} and the largest "
                    f"gain from scaling bids was {musd(gmax, 1, sign=True)} a year, interval including zero." if any(mg[rule][sp]["lo"] <= 0 for rule in BID_RULES for sp in SPLITS)
                    else f"Every owner beat alone under {rules_txt},{vs} and the largest gain from scaling bids was {musd(gmax, 1, sign=True)} a year.")
        raise KeyError(kind)
    for kind, key in (("abstract", "P3-E46-ABSTRACT-CLAUSE"), ("intro", "P3-E46-INTRO-CLAUSE"), ("discussion", "P3-E46-DISCUSSION-CLAUSE"),
                      ("comparison", "P3-E46-COMPARISON-CLAUSE"), ("implication", "P3-E46-IMPLICATION-CLAUSE"),
                      ("conclusion", "P3-E46-CONCLUSION-CLAUSE")):
        fill(key, lambda kind=kind: e46_clause(kind), "E46")

    def e46_posthoc():
        ex = r.f46("exploratory")
        afg = {rule: {sp: _get(ex, "allocation_fixed_gain", rule, sp) for sp in SPLITS} for rule in BID_RULES}
        rt = {sp: _get(ex, "reallocation_term", sp) for sp in SPLITS}
        ratio = min(rt[sp]["sd"] / afg["first"][sp]["gain"] for sp in SPLITS if afg["first"][sp]["gain"] > 0)
        return (f"A decomposition made after the runs, not pre-registered, separates the two parts of that gain: with the allocation held fixed, "
                f"the scaled asks alone paid the deviator {musd(afg['first']['3eq']['gain'], 2, sign=True)} a year "
                f"{ci_m(afg['first']['3eq']['lo'], afg['first']['3eq']['hi'])} under first price with equal shares and "
                f"{musd(afg['first']['3uneq']['gain'], 2, sign=True)} {ci_m(afg['first']['3uneq']['lo'], afg['first']['3uneq']['hi'])} with 50/35/15 "
                f"shares ({musd(afg['second']['3eq']['gain'], 2, sign=True)} and {musd(afg['second']['3uneq']['gain'], 2, sign=True)} under the second "
                f"price); the rest of the paired gain is the change in the deviator's own cargo delay once its asks move jobs, a term with a mean of "
                f"{musd(rt['3eq']['mean'], 2, sign=True)} and {musd(rt['3uneq']['mean'], 2, sign=True)} and a standard deviation over seeds of "
                f"{musd(rt['3eq']['sd'], 0)} and {musd(rt['3uneq']['sd'], 0)}, at least {num(ratio, 1)} times the cash, which is why the "
                f"registered interval covers zero although shading pays in cash.")
    fill("P3-E46-POSTHOC-SENTENCE", e46_posthoc, "E46 post hoc (BACKEND's exploratory block)")

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
    return _tab("Table 2. The vehicle classes of the catalogue (lunarsim/atc/vehicles-p5.json). Each cell gives "
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
                f"99th percentile; peak memory of the on-robot part in MB; power with its flag. The auction round and the peak memory are measured "
                f"once per run and repeated in every row; the base computer's timed check is its reservation check over the shared table.",
                ["Class", "Safety check, base: reservation check (&micro;s)", "Auction round (ms)", "Peak memory (MB)", "Power (W)"], rows, cls="wide")


def table_e48_link(r: R):
    rows = []
    for c in CLASSES:
        lk = r.s48("classes", c, "link")
        rows.append([CLASS_NAME[c].capitalize(), num(lk["antenna_m"], 1), num(lk["freq_ghz"], 1), num(lk["tx_power_w"], 2),
                     num(lk["worst_hop_kbps"], 1), num(lk["latency_budget_ms"], 0), pc(lk["reachable_share"], 1)])
    return _tab("Table 6. Link budget per vehicle class under the models of Section 3.3: antenna height (m), frequency (GHz), transmit power (W), "
                "data rate at the worst hop (kbit/s), modelled latency of a 100-byte message over three hops (one for the base) plus the scaled safety check (ms), and the share of the route samples "
                "in direct view of the base mast within 5 km (multi-hop reach is higher and not measured).",
                ["Class", "Antenna (m)", "Frequency (GHz)", "Power (W)", "Worst hop (kbit/s)", "Modelled latency (ms)", "Direct view of mast (share of route samples)"], rows, cls="wide")


def table_e46_rules(r: R):
    rows = []
    for rule in RULES:
        for split in SPLITS:
            c = r.cell46(rule, split)
            rows.append([RULE_SHORT[rule], SPLIT_NAME[split], int(c["n"]), num(c["profit_A_musd"], 1, sign=True),
                         num(c["profit_B_musd"], 1, sign=True), num(c["profit_C_musd"], 1, sign=True), num(c["operator_budget_musd"], 2, sign=True),
                         pc(c["efficiency_loss_pct"] / 100, 1), num(c["settled_earth_musd"], 1), num(c["open_end_musd"], 3), int(c["ir_violations"])])
    return _tab("Table 7. Cell means over the seeds of E46 per payment rule and share split, honest bids, no audits, in M USD a year. "
                "Profit is each owner's earnings less its private costs, the tariff it paid for its own cargo and its cargo's delay cost; under the "
                "posted price it is instead the owner's Shapley value of the coalition's value (carrier costs plus delay costs, sign reversed), the "
                "quantity H5's third clause compares with alone. Budget is the operator's surplus (+) or deficit (&minus;). Efficiency loss is the "
                "market's system cost (true carrier cost plus delay cost) above the oracle of [60], the same under every rule because the rules share "
                "one allocation. Settled is half the sum of the owners' absolute net cash flows; open is the pay due on jobs unfinished at the year's end. "
                "IR violations count the owners whose mean market profit was below their mean alone profit.",
                ["Rule", "Split", "Runs", "Profit A", "Profit B", "Profit C", "Budget", "Efficiency loss", "Settled on Earth",
                 "Open at year end", "IR violations"], rows, cls="wide")


def table_e46_owners(r: R):
    rows = []
    for split in SPLITS:
        for x in r.f46("H5", split, "clause3", "rows"):
            p = r.pair46(f"coalition {x['coalition']} - alone, owner {x['owner']} ({split})", "profit_usd")
            rows.append([SPLIT_NAME[split], html.escape(x["coalition"]), html.escape(x["owner"]), int(p["n"]), num(p["b_mean"] / 1e6, 1),
                         num(p["mean"] / 1e6, 1, sign=True), ci(p["lo"] / 1e6, p["hi"] / 1e6, 1)])
    return _tab("Table 8. Each owner's Shapley value in every tested coalition under the posted price against working alone on the same seeds, in "
                "M USD a year: the alone profit, the paired difference (Shapley value in the coalition minus alone) and its 95&#8239;% bootstrap "
                "interval over seeds. In a two-owner coalition both owners receive the same difference by construction, half the coalition's gain.",
                ["Split", "Coalition", "Owner", "n", "Alone profit", "Difference", "95&#8239;% CI"], rows, cls="wide")


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
