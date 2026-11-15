"""Assemble paper P3 ("The vehicles, the network and the market"): fill every {{P3-...}} placeholder, insert the
tables, write paper/p3/paper.html and render the PDF with headless Chrome.

    python paper/p3/build_p3.py [--no-pdf] [--allow-pending]

Sources (read-only): lunarsim/atc/vehicles-p5.json (the vehicle catalogue with flags and sources), one p5 scenario
(the fleet and the load factor), results/ATC_mesh.json (B-70's mesh summary), lunarsim/atc/regimes.py, messages.py,
radio.py and auction.py (the Assumed defaults), the two policy files (the learned bids' sizes), paper/atc/PREREG.md
(dated changes), paper/p3/NOTES.md (references), and the experiment files once they exist: results/E46_cells.csv,
results/E46_pairs.csv, results/E46_fit.json (B-76 REVISED; file names proposed in PLACEHOLDERS.md, not yet promised)
and results/E48_sizing.json (B-81; rebuilt by B-89 on 11 Nov 2026 with the flat-ground link, the secured sizes, the airtime
and a revision block, PREREG change 11). Until an experiment file exists every key that depends on it is pending and, with
--allow-pending, prints as a visible [[PENDING ...]] marker.

Since the correction of 11 Nov 2026 the link is not one yes or no: e48_air() reads the authenticated load and three airtime
cases (a base-scheduled channel and slotted random access at the measured mean hop count, a scheduled channel with two-hop
relaying) and link_text() words the claim from them; e48_links() carries the checks behind "beyond the horizon", "upper bound"
and the two-ray law, and a class beyond its horizon at the worst hop never prints a zero rate.

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
# Phase 6 (the interaction protocol; paper/atc/PREREG6.md). A file that is absent makes every key that needs it pending.
# E50b, E52, E55 and B-97 have no file yet: the names below are proposed in PLACEHOLDERS.md, not promised by BACKEND.
PREREG6 = os.path.join(ROOT, "paper", "atc", "PREREG6.md")
P6_FILES = {"E50": "E50_summary.json", "E51": "E51_clocks.json", "E51b": "E51b_clocks.json", "E53": "E53_bitrate.json",
            "E54": "E54_dtn.json", "E54L": "E54_ledger.json", "E50b": "E50b_summary.json", "E52": "E52_map.json",
            "E55": "E55_integrity.json", "B97": "B97_realdata.json", "FAM": "phase6_family.json", "VV6": "vv_phase6.json"}
P6_TASK = {"E50": "B-90", "E51": "B-91", "E51b": "B-91b", "E53": "B-93", "E54": "B-94", "E54L": "B-94, ledger lifetimes",
           "E50b": "B-90b", "E52": "B-92", "E55": "B-95", "B97": "B-97", "FAM": "tools/atc/phase6_family.py", "VV6": "B-98"}

C_LIGHT = 299792458.0            # m/s
R_MOON = 1737.4e3                # m, the reference sphere of the LOLA products and of radio.py
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


class Landed(Exception):
    """An awaited result is now in its file, and its composing function has not been written against the file's schema."""


AWAITED: List[str] = []          # the awaited keys of this build, printed by build(); none of them prints a marker (decision A4)


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

    # --- Phase 6 ---------------------------------------------------------------------------------------------
    def p6(self, exp, *keys):
        """A field of a Phase 6 results file, loaded on first use; pending while the file (or the field) is absent."""
        cache = self.__dict__.setdefault("_p6", {})
        if exp not in cache:
            path = os.path.join(RES, P6_FILES[exp])
            if not os.path.exists(path):
                raise Pending(f"{exp} ({P6_TASK[exp]}, results/{P6_FILES[exp]}) has not run")
            cache[exp] = json.load(open(path, encoding="utf-8"))
        return _get(cache[exp], *keys)

    def row6(self, exp, **where):
        """The one row of a Phase 6 file's `rows` that matches every key of `where` (numbers compared with a tolerance)."""
        def same(a, b):
            if isinstance(b, (int, float)) and not isinstance(b, bool) and isinstance(a, (int, float)) and not isinstance(a, bool):
                return abs(float(a) - float(b)) < 1e-9
            return a == b
        g = [x for x in self.p6(exp, "rows") if all(same(x.get(k), v) for k, v in where.items())]
        if len(g) != 1:
            raise KeyError(f"{exp} row {where}: {len(g)} rows")
        return g[0]

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
# the referee's spherical-ground figures (reports/referee_phase6_p3.md, finding M14; decision B10)
# ---------------------------------------------------------------------------------------------------------
REFEREE_P3 = os.path.join(ROOT, "reports", "referee_phase6_p3.md")


def referee_m14(r: "R", check):
    """The loss and the rates over a spherical ground at the hops of Table 7 (second pass, 12 Nov 2026: task B-104 has landed). They are the
    project's own calculation with ITU-R P.526 section 3.2 [20], results/E48_sizing.json block `revision_b104`, and replace the referee's
    figures that the first pass quoted from the report (finding M14, decision B10). The name is kept for its callers."""
    b = r.s48("revision_b104")
    pc_ = b["per_class"]
    cls = ("LTV1", "SMALL", "HOPPER", "BASE")
    lk = {c: r.s48("classes", c, "link") for c in cls}
    for c in cls:
        lh = pc_[c]["longest_hop"]
        check(abs(_fin(lh["d_m"]) - _fin(lk[c]["longest_hop_m"])) < 0.5 and abs(_fin(lh["kbps"]["flat_ground"]) - _fin(lk[c]["longest_hop_kbps"])) < 0.06,
              f"{CLASS_NAME[c]}: the flat-ground side of the spherical-ground block is Table 7's longest hop and rate")
        check(_fin(lh["loss_db"]["spherical_ground"]) > _fin(lh["loss_db"]["flat_ground"]) > _fin(lh["loss_db"]["free_space"]) and
              _fin(lh["kbps"]["spherical_ground"]) < _fin(lh["kbps"]["flat_ground"]),
              f"{CLASS_NAME[c]}: over a spherical ground the loss at the longest hop is higher and the rate lower than over flat ground")
    check("P.526-16" in str(b["source_note"]) and "checked against the text" in str(b["source_note"]) and "section 3.2" in str(b["method"]),
          "the spherical-ground method is ITU-R P.526 section 3.2, checked against the text of P.526-16")
    loss = {c: (_fin(pc_[c]["longest_hop"]["loss_db"]["spherical_ground"]), _fin(pc_[c]["longest_hop"]["loss_db"]["flat_ground"])) for c in cls}
    rates = {c: (_fin(pc_[c]["longest_hop"]["kbps"]["spherical_ground"]), _fin(pc_[c]["longest_hop"]["kbps"]["flat_ground"])) for c in cls}
    ratio = {c: rates[c][1] / rates[c][0] for c in cls}
    dl = {c: loss[c][0] - loss[c][1] for c in cls}
    moved = list(b["verdicts_moved"])
    v = {c: pc_[c]["verdicts_flat_vs_spherical"] for c in cls}
    mv = sorted(c for c in cls if any(k != "reachable_share" and x[0] != x[1] for k, x in v[c].items()))
    check(sorted(m_.split(":")[0] for m_ in moved) == sorted(c for c in pc_ if any(k != "reachable_share" and x[0] != x[1] for k, x in pc_[c]["verdicts_flat_vs_spherical"].items()))
          and all("1_Mbps_at_longest_hop True -> False" in m_ for m_ in moved) and mv == ["LTV1"],
          "over a spherical ground one verdict moves: the crew and cargo rovers' longest hop no longer carries 1 Mbit/s")
    check(all(x["carries_20_robot_airtime_at_longest_hop"] == [True, True] and x["16_kbps_at_longest_hop"] == [True, True] for x in v.values()) and
          all(abs(_fin(pc_[c]["reachable_share_spherical"]) - _fin(lk[c]["reachable_share"])) < 0.0005 for c in cls if c != "BASE"),
          "over a spherical ground every class still carries the fleet's airtime and 16 kbit/s at its longest hop, and the mast-reach shares do not change")
    bulge = {c: _fin(lk[c]["longest_hop_m"]) ** 2 / (8.0 * R_MOON) for c in ("LTV1", "SMALL")}
    rt = lambda x: num(x, 0 if x >= 100 else 1)
    words_ = (f"{', '.join(rt(rates[c][0]) for c in cls[:3])} and {rt(rates['BASE'][0])}{NB}kbit/s in place of "
              f"{', '.join(rt(rates[c][1]) for c in cls[:3])} and {rt(rates['BASE'][1])} for the crew and cargo rovers, the small rover, the hopper and the mast")
    veh = [c for c in cls if c != "BASE"]
    return {"loss": loss, "rates": rates, "ratio": ratio, "dl": dl, "bulge": bulge, "lk": lk, "rates_txt": words_, "block": b,
            "veh_ratio": (min(ratio[c] for c in veh), max(ratio[c] for c in veh)), "veh_dl": (min(dl[c] for c in veh), max(dl[c] for c in veh)),
            "range_1m": (_fin(pc_["LTV1"]["range_m_for_kbps_spherical"]["1000"]), _fin(pc_["LTV1"]["range_m_for_kbps_flat"]["1000"])),
            "airtime": _fin(b["airtime_needed_kbps"])}


# ---------------------------------------------------------------------------------------------------------
# Phase 6: position, time, the shared map# ---------------------------------------------------------------------------------------------------------
# Phase 6: position, time, the shared map, the stack and its security (PREREG6; research notes 01 to 04)
# ---------------------------------------------------------------------------------------------------------
E50_SETS = ("dr", "dr+ranging", "dr+ranging+fixes", "lans@2030")
E50_SET_NAME = {"dr": "dead reckoning alone", "dr+ranging": "with ranging", "dr+ranging+fixes": "with ranging and terrain fixes",
                "lans@2030": "with the navigation service as assumed for 2030"}
MULT_NAME = {"1": "today's fleet", "4": "four times the fleet", "8": "eight times the fleet"}


def mci(x, nd=1, u="m"):
    """A mean over seeds with its 95 % interval: '12.6 m [12.1, 13.2]'."""
    return f"{unit(x['mean'], u, nd)} {ci(x['ci'][0], x['ci'][1], nd)}"


def sig(x, n=3):
    """n significant figures with a thousands separator (for values that span orders of magnitude)."""
    x = _fin(x)
    if x == 0:
        return "0"
    nd = n - 1 - int(math.floor(math.log10(abs(x))))
    return num(round(x, nd), max(0, nd))


def dist(m, n=3):
    """A distance given in metres: metres below 1 km, kilometres from there, n significant figures."""
    return f"{sig(m, n)}{NB}m" if _fin(m) < 1000 else f"{sig(m / 1000.0, n)}{NB}km"


def dur(s):
    """A duration given in seconds, in the unit a reader would use."""
    s = _fin(s)
    for lim, div, u in ((1.0, 1e-3, "ms"), (120.0, 1.0, "s"), (7200.0, 60.0, "min"), (172800.0, 3600.0, "h")):
        if s < lim:
            return f"{sig(s / div, 2 if s / div < 10 else 3)}{NB}{u}"
    return f"{sig(s / 86400.0, 2 if s / 86400.0 < 10 else 3)}{NB}days"


def values_p6(r: R, V, fill, check, fill_await, landed):
    """Every Phase 6 key. Returns the Phase 6 tables as name -> (builder, tag, caption)."""
    from lunarsim.atc import pnt as PNT
    from lunarsim.atc import safety as SAFETY
    PD = PNT.DEFAULTS
    T6: Dict[str, Any] = {}

    # --- A. positioning (3.5, 4.2, 5.8): the model's inputs from lunarsim/atc/pnt.py, the results from E50 -------------
    def nav_layers():
        av = PD["lans_availability"]
        check(av[2026] == av[2027] == av[2028] == 0.0 and av[2029] < av[2030] < av[2031] == av[2032],
              "the assumed availability of the navigation service is zero to 2028 and rises to 2031 (3.5)")
        check(PD["beacons"] == ["BASE", "DEPOT", "POWER", "PAD_A"] and PD["year"] == 2028, "E50's four beacons and its year (3.5)")
        check(abs(PD["budget_m"] - SAFETY.D0_M) < 1e-12, "the separation budget is rule R1's static margin D0 (3.5, 4.2)")
        return (f"The model of E50 gives each layer one number (Table 4). Dead reckoning drifts by {pc(PD['dr_firm'], 0)} of the distance driven "
                f"on firm level ground, {pc(PD['dr_loose'], 0)} on loose soil or slopes above {num(PD['slope_loose_deg'], 0)}&deg; and "
                f"{pc(PD['dr_shadow'], 0)} in shadow, with a star tracker holding the heading to {num(PD['heading_sigma_deg'], 1)}&deg;. A two-way "
                f"range is good to {unit(PD['uwb_sigma_m'], 'm', 1)} within {unit(PD['uwb_range_m'], 'm', 0)} and to {unit(PD['radio_sigma_m'], 'm', 0)} "
                f"over the base radio out to {unit(PD['radio_range_m'] / 1000.0, 'km', 0)}, to {words(len(PD['beacons']))} beacons surveyed to "
                f"{unit(PD['beacon_sigma_m'], 'm', 2)} and to at most {words(PD['max_peers'])} other vehicles in line of sight. A terrain fix is good to "
                f"{unit(PD['fix_sigma_lit_m'], 'm', 1)} in sunlight and {unit(PD['fix_sigma_dark_m'], 'm', 0)} in the dark, where {pc(PD['fix_fail_dark'], 0)} "
                f"of attempts are taken to fail (Assumed); an opportunity comes every {unit(PD['fix_spacing_lit_m'], 'm', 0)} in sunlight and every "
                f"{unit(PD['fix_spacing_dark_m'], 'm', 0)} in shadow, costs a stop of {unit(PD['fix_stop_s'], 's', 0)}, and is taken when the vehicle's own "
                f"95{PCT} bound exceeds {unit(PD['fix_trigger_m'], 'm', 1)}; a vehicle that arrives at a site takes one there. The navigation service "
                f"is given the providers' target of {unit(PD['lans_95_m'], 'm', 0)} (95{PCT}) with the height taken from the map [79], where their own "
                f"simulation gives 17.2{NB}m [77], for a share of each day of {num(av[2028], 0)} in 2028, {num(av[2029], 1)} in 2029, {num(av[2030], 1)} "
                f"in 2030 and {num(av[2031], 1)} from 2031 (both Assumed). "
                f"The budget all of this is held against is {unit(PD['budget_m'], 'm', 0)}, the distance rule R1 of [61] keeps free for position "
                f"uncertainty.")
    fill("P3-NAV-LAYERS-SENTENCE", nav_layers, "pnt.py defaults")
    V["P3-NAV-BUDGET-M"] = unit(PD["budget_m"], "m", 0)

    def e50(mult, lset, region, metric):
        return r.p6("E50", "errors", mult, lset, region, metric)

    _steps: Dict[str, Any] = {}

    def e50_steps():
        """results/E50_errors.csv at today's fleet, the ranging layer set: per seed the driving steps overall, where two or more beacons
        are in line of sight ('near') and elsewhere ('away'), and the parked steps. Gives the shares the referee asked for (M2, M5)."""
        if _steps:
            return _steps
        path = os.path.join(RES, "E50_errors.csv")
        _need(path, "E50's per-seed error table")
        c = pd.read_csv(path)
        c = c[(c["mult"] == 1) & (c["layer_set"] == "dr+ranging")]
        g = {reg: c[c["region"] == reg].set_index("seed").sort_index() for reg in ("all", "near", "away", "parked")}
        seeds = list(r.p6("E50", "seeds", "1"))
        check(list(g["all"].index) == seeds and bool(((g["near"]["n_steps"] + g["away"]["n_steps"]) == g["all"]["n_steps"]).all()),
              "E50's per-seed table has every seed of today's fleet, and near plus away is every driving step")
        check(abs(float(g["near"]["p95_m"].mean()) - _fin(e50("1", "dr+ranging", "near", "p95_m")["mean"])) < 1e-3,
              "E50's per-seed table gives the summary's 95th percentile where two or more beacons are in view")
        s1 = seeds[0]
        _steps.update({"g": g, "seeds": seeds,
                       "near_share": float(g["near"]["n_steps"].sum()) / float(g["all"]["n_steps"].sum()),
                       "near_over": float(g["near"]["share_err_over_budget"].mean()),
                       "near_max_mean": float(g["near"]["max_m"].mean()), "near_max": float(g["near"]["max_m"].max()),
                       "near_p95_max": float(g["near"]["p95_m"].max()),
                       "parked_share_s1": float(g["parked"]["n_steps"][s1]) / float(g["parked"]["n_steps"][s1] + g["all"]["n_steps"][s1]),
                       "parked_s1": int(g["parked"]["n_steps"][s1]), "driving_s1": int(g["all"]["n_steps"][s1])})
        return _steps

    P6_FILES["E50N"], P6_TASK["E50N"] = "E50_near_base.json", "B-101"
    READING = {"a": "where two or more beacons are in line of sight", "b": "where one or more beacons are in line of sight",
               "c": "within 1&nbsp;km of the base mast", "e": "within the 5&nbsp;km radio range of a base beacon, the registered words taken literally"}

    def referee_m5():
        """H9' clause 2 under the readings of 'near the base' (second pass, 12 Nov 2026: task B-101 has landed, results/E50_near_base.json).
        A simulation on assumed ranging errors, on all seeds at today's fleet and at four times it; it replaces the referee's six-seed
        rerun that the first pass quoted (finding M5, decision B4). Returns the readings per fleet multiple and the sweep; the name is
        kept for its callers. Readings d and e cover every driving step and are one row here (e, the registered wording)."""
        rd = r.p6("E50N", "readings")
        check(all(k in rd for k in "abcde") and "PREREG6's words" in str(rd["e"]) and "2+ beacons" in str(rd["a"]) and "1 km" in str(rd["c"]),
              "the readings of 'near the base' are: two or more beacons in view, one or more, within 1 km, within radio range of the mast, and the registered words")
        b = _fin(r.p6("E50N", "budget_m"))
        out = {}
        for m in r.p6("E50N", "multiples"):
            mm_ = r.p6("E50N", "multiples", m)
            check(bool(mm_["e50_reproduced_all"]) and list(mm_["seeds"]) == list(r.p6("E50", "seeds", m)), f"B-101 reproduces E50's cells on E50's seeds at {m} times the fleet")
            rs = mm_["sets"]["dr+ranging"]
            check(abs(_fin(rs["d"]["in_p95_m_mean"]) - _fin(rs["e"]["in_p95_m_mean"])) < 1e-9 and _fin(mm_["share_of_driving"]["e"]["mean"]) == 1.0 and
                  abs(_fin(rs["e"]["in_p95_m_mean"]) - _fin(e50(m, "dr+ranging", "all", "p95_m")["mean"])) < 1e-3,
                  f"at {m} times the fleet the registered wording covers every driving step, so its value is E50's overall percentile")
            check(abs(_fin(rs["a"]["in_p95_m_mean"]) - _fin(e50(m, "dr+ranging", "near", "p95_m")["mean"])) < 1e-3, f"reading (a) at {m} times the fleet is E50's near-base percentile")
            rows = []
            for k in ("a", "b", "c", "e"):
                x = rs[k]
                rows.append({"k": k, "share": _fin(mm_["share_of_driving"][k]["mean"]), "p95": _fin(x["in_p95_m_mean"]), "ci": [_fin(v) for v in x["in_p95_m_ci95_seeds"]],
                             "inside": int(x["seeds_inside_budget"]), "n": int(x["seeds_with_steps"])})
            check(rows[0]["inside"] == rows[0]["n"] and all(x["inside"] == 0 and x["p95"] > b for x in rows[1:]),
                  f"at {m} times the fleet H9' clause 2 holds in every seed under reading (a) and in no seed under the others, the registered words included")
            out[m] = {"rows": rows, "sets": mm_["sets"]}
        sw = r.p6("E50N", "sweep")
        check(str(sw["layer_set"]) == "dr+ranging", "the sweep of B-101 is on the ranging layer set")
        srow = lambda p, v: next(x for x in sw["rows"] if x["param"] == p and abs(_fin(x["value"]) - v) < 1e-9)
        rad = {v: srow("radio_sigma_m", v) for v in (1.0, 3.0, 10.0)}
        uwb = {v: srow("uwb_sigma_m", v) for v in (0.1, 0.3, 0.7)}
        check(abs(PD["radio_sigma_m"] - 3.0) < 1e-9 and abs(PD["uwb_sigma_m"] - 0.3) < 1e-9, "the sweep's middle values are the model's defaults")
        check(int(rad[10.0]["a"]["seeds_inside_budget"]) == 0 and int(rad[1.0]["a"]["seeds_inside_budget"]) == int(rad[1.0]["a"]["seeds"]) and
              all(int(rad[v][k]["seeds_inside_budget"]) == 0 for v in rad for k in "bce"),
              "the long-range ranging error decides clause 2 under reading (a): inside at 1 m and 3 m, outside at 10 m; under the other readings it fails at every value")
        ua = [_fin(uwb[v]["a"]["in_p95_m_mean"]) for v in uwb]
        check(max(ua) - min(ua) < 0.05 * min(ua) and all(int(uwb[v]["a"]["seeds_inside_budget"]) == int(uwb[v]["a"]["seeds"]) for v in uwb),
              "the ultra-wideband ranging error barely moves the percentile (under 5 % over its sweep)")
        return out, {"rad": rad, "uwb": uwb, "n": len(sw["seeds"]), "budget": b}

    def e50_design():
        d = r.p6("E50", "design")
        seeds = r.p6("E50", "seeds")
        check(d["regime"] == "C_AUCTION" and abs(_fin(d["regime_kw"]["loss"]) - 0.10) < 1e-9 and d["roads"] == "atc" and
              int(d["regime_kw"]["start_year"]) == PD["year"], "E50 replays the auction regime with roads, loss 0.10, in 2028 (4.2)")
        check(abs(_fin(d["budget_m"]) - PD["budget_m"]) < 1e-12 and abs(_fin(d["dt_s"]) - 60.0) < 1e-9 and abs(_fin(d["shift_h"]) - 8.0) < 1e-9,
              "E50's budget, step and shift are 5 m, 60 s and 8 h (4.2)")
        check("at least 2 of the 4 beacons" in str(d["region_rule"]), "near the base = in line of sight of at least two of the four beacons (4.2)")
        check(int(d["lans_variant_year"]) == 2030, "the navigation-service variant of E50 is the year 2030 (4.2)")
        check(all(abs(_fin(e50(m, "dr+ranging+fixes+lans", "all", "p95_m")["mean"]) - _fin(e50(m, "dr+ranging+fixes", "all", "p95_m")["mean"])) < 1e-9
                  for m in seeds), "with the service's 2028 availability of zero the fourth layer set equals the third (4.2)")
        ns = {m: len(v) for m, v in seeds.items()}
        st = e50_steps()
        check(all(int(e50(m, "dr", "all", "p95_m")["n"]) == n for m, n in ns.items()), "E50's seed counts are those of its cells")
        ran = " and ".join(f"{cnt(n)} at {MULT_NAME[m]}" for m, n in ns.items())
        return (f"The run is the auction regime of [60] with the road layer of [61] on, three owners with equal shares, the middle load and a message "
                f"loss of {num(d['regime_kw']['loss'], 2)}, in July 2028. Each seed is first run with perfect position; its recorded trajectories are then "
                f"replayed through the navigation model of Section 3.5 in steps of {unit(d['dt_s'], 's', 0)}, once per layer set: dead reckoning alone, "
                f"with ranging, with ranging and terrain fixes, and with the navigation service added, which in 2028 is never available, so that set "
                f"equals the third and a variant with the service as assumed for {int(d['lans_variant_year'])} is run beside it. Errors start at zero "
                f"at the window's start (every vehicle surveyed then, Assumed). Seeds: {ran}, fewer at the larger fleets because of run time, as the "
                f"dated changes of [67] record. The results are split by region: a vehicle-step is called near the base when its route sample is in "
                f"radio line of sight of at least two of the four beacons, and away from it otherwise. That rule was chosen with the experiment; it is "
                f"not in the registration, whose words are &ldquo;within radio range of the base beacons&rdquo;, and it covers {pc(st['near_share'], 1)} "
                f"of the driving steps (Section 5.8 reports the clause under other readings; a dated entry of [67] records the choice). The replay is "
                f"a covariance analysis with a matched filter: the errors are drawn from the same linear-Gaussian model that the filter assumes, with the "
                f"bias of a leg as a filter state, no outlier, no range bias from a blocked path, no wrong fix accepted as good, and the beacons' survey "
                f"errors treated as white. The error it reports is therefore the best any estimator could do if the model were the world.")
    fill("P3-E50-DESIGN-SENTENCE", e50_design, "E50")

    def e50_errors():
        seeds = r.p6("E50", "seeds")
        out = []
        for m in seeds:
            hours = r.p6("E50", "errors", m, "dr", "shift_p95_m_mean_over_seeds")
            first = int(r.p6("E50", "h9", m, "dr_first_driving_hour_p95_over_budget"))
            check(_fin(hours[first - 1]) > PD["budget_m"] and all(_fin(h) <= PD["budget_m"] for h in hours[:first - 1]),
                  f"E50 {m}x: the first driving hour whose 95th percentile passes the budget is the one the file names")
            bits = []
            for s in E50_SETS:
                a, n_, w = (e50(m, s, reg, "p95_m") for reg in ("all", "near", "away"))
                if s == "dr":
                    check(abs(n_["mean"] - w["mean"]) < 0.05 * a["mean"], f"E50 {m}x: dead reckoning alone is the same near the base and away from it (5.8)")
                    bits.append(f"{E50_SET_NAME[s]} {mci(a, 0)}, the same in both regions")
                    continue
                bits.append(f"{E50_SET_NAME[s]} {mci(a, 1 if a['mean'] >= 10 else 2)} overall, {mci(n_, 2 if n_['mean'] < 10 else 1)} in the first region and "
                            f"{mci(w, 1 if w['mean'] >= 10 else 2)} in the second")
            sh = [pc(e50(m, s, "all", "share_b95_over_budget")["mean"], 0) for s in E50_SETS]
            share = ", ".join(sh[:-1]) + " and " + sh[-1]
            out.append(f"At {MULT_NAME[m]} ({cnt(len(seeds[m]))} seeds) the 95th percentile of the position error over driving vehicle-steps, overall, "
                       f"where two or more of the four beacons are in line of sight (the first region) and elsewhere (the second), was: "
                       + "; ".join(bits) + f". Under dead reckoning alone that percentile was {unit(hours[0], 'm', 0)} in the first driving hour and "
                       f"{unit(hours[7], 'm', 0)} in the eighth. The vehicle's own 95{PCT} bound was above the {unit(PD['budget_m'], 'm', 0)} budget for "
                       f"{share} of the driving steps, in the same order of layer sets.")
        st = e50_steps()
        nr = r.p6("E50", "errors", "1", "dr+ranging", "near")
        o1 = r.p6("E50", "superseded_2026-11-13_b118_n15", "errors", "1")
        check("positioning fix" in str(r.p6("E50", "superseded_2026-11-13_b118_n15", "reason")), "E50's earlier values are kept as superseded by the positioning fix (5.8)")
        return (" ".join(out) + f" The first region holds {pc(st['near_share'], 1)} of the driving steps at today's fleet. Inside it, with ranging, "
                f"{pc(st['near_over'], 1)} of the steps still had an error above the budget, the largest error of a seed was {unit(st['near_max_mean'], 'm', 0)} "
                f"on average and {unit(st['near_max'], 'm', 0)} at most, and the vehicle's own 95{PCT} bound, which is what a rule can act on, was above the "
                f"budget in {pc(nr['share_b95_over_budget']['mean'], 0)} of the steps. Table 10 gives the medians and the fix stops. Every value of this "
                f"section was regenerated on the same seeds after a code review on 13 November 2026 corrected the positioning code (how the last "
                f"step of a leg and the update at a vehicle's arrival step are handled): before, at today's fleet, the "
                f"95th percentiles were {unit(o1['dr']['all']['p95_m']['mean'], 'm', 0)} with dead reckoning alone, "
                f"{unit(o1['dr+ranging']['near']['p95_m']['mean'], 'm', 2)} with ranging in the first region and "
                f"{unit(o1['dr+ranging+fixes']['away']['p95_m']['mean'], 'm', 1)} with terrain fixes in the second.")
    fill("P3-E50-RESULTS-ERRORS", e50_errors, "E50")

    def h9_parts():
        """Per multiple: the three clauses of H9 (PREREG6), each recomputed from the numbers and compared with the file's flag."""
        res = {}
        for m in r.p6("E50", "seeds"):
            h = r.p6("E50", "h9", m)
            b = _fin(h["budget_m"])
            dr_ok = int(h["dr_first_driving_hour_p95_over_budget"]) <= _fin(r.p6("E50", "design", "shift_h"))
            near_ok = _fin(h["ranging_near_p95_m"]["ci"][1]) < b
            away_ok = _fin(h["fixes_away_p95_m"]["ci"][1]) < b
            check(dr_ok == bool(h["dr_supported"]) and near_ok == bool(h["ranging_near_supported"]) and away_ok == bool(h["fixes_away_supported"]),
                  f"E50 {m}x: H9's three flags follow from the numbers by the file's rule")
            check(abs(_fin(h["ranging_near_p95_m"]["mean"]) - _fin(e50(m, "dr+ranging", "near", "p95_m")["mean"])) < 1e-9 and
                  abs(_fin(h["fixes_away_p95_m"]["mean"]) - _fin(e50(m, "dr+ranging+fixes", "away", "p95_m")["mean"])) < 1e-9,
                  f"E50 {m}x: H9 is tested on the ranging set near the base and the fixes set away from it")
            res[m] = {"dr": dr_ok, "near": near_ok, "away": away_ok, "h": h, "lans_away": e50(m, "lans@2030", "away", "p95_m"), "b": b}
        return res

    def sup(flags):
        return "supported" if all(flags) else ("not supported" if not any(flags) else "supported at some fleet sizes and not at others")

    def h9_verdict():
        """5.8: H9' clause by clause. Clause 2 is reported under every reading and its verdict is 'depends on the reading' (decisions A2
        and B4; PREREG6 section 6). Since the second pass the readings are B-101's, on all seeds (results/E50_near_base.json)."""
        p = h9_parts()
        ms = list(p)
        at = lambda key, nd=2: ", ".join(f"{mci(p[m]['h'][key], nd)} at {MULT_NAME[m]}" for m in ms)
        lans = [p[m]["lans_away"] for m in ms]
        lans_in = [_fin(x["ci"][1]) < p[m]["b"] for x, m in zip(lans, ms)]
        rd, sw = referee_m5()
        share = lambda x: "every driving step" if x > 0.9995 else f"{pc(x, 0)} of driving steps"
        seeds_in = lambda x: "every seed inside" if x["inside"] == x["n"] else ("no seed inside" if x["inside"] == 0 else f"{cnt(x['inside'])} of {cnt(x['n'])} seeds inside")
        m_ = lambda x: unit(x["p95"], "m", 2 if x["p95"] < 10 else 1)

        def one(m):
            rows = rd[m]["rows"]
            return (f"At {MULT_NAME[m]} ({cnt(rows[0]['n'])} seeds) the percentile is " +
                    "; ".join(f"{m_(x)} {ci(x['ci'][0], x['ci'][1], 2 if x['p95'] < 10 else 1)} {READING[x['k']]} ({share(x['share'])}, {seeds_in(x)})" for x in rows) + ".")
        not_run = [m for m in ms if m not in rd]
        e1 = rd["1"]["rows"][-1]
        rad, uwb = sw["rad"], sw["uwb"]
        rv, uv = sorted(rad), sorted(uwb)
        ra = lambda v, k="a": unit(rad[v][k]["in_p95_m_mean"], "m", 2 if _fin(rad[v][k]["in_p95_m_mean"]) < 10 else 1)
        fx = {k: rd["1"]["sets"]["dr+ranging+fixes"][k] for k in ("b", "c", "e")}
        check(all(p[m]["near"] for m in ms), "under reading (a) H9' clause 2 is inside the budget at every fleet size run (5.8)")
        return (f"H9&prime; of [67] has three clauses, each against the {unit(p[ms[0]]['b'], 'm', 0)} budget. First, dead reckoning alone passes the budget "
                f"within one eight-hour shift of driving: {sup([p[m]['dr'] for m in ms])} (in driving hour "
                + ", ".join(f"{int(p[m]['h']['dr_first_driving_hour_p95_over_budget'])} at {MULT_NAME[m]}" for m in ms) +
                f"). Second, with ranging the 95th percentile stays inside the budget &ldquo;within radio range of the base beacons&rdquo;: the verdict "
                f"depends on the reading of those words. The analysis first used one reading, two or more of the four beacons in line of sight, chosen "
                f"after the results; a further simulation on the same assumed ranging errors then evaluated the clause under four readings on every seed. "
                + " ".join(one(m) for m in rd) +
                f" Under the registered wording taken literally, which covers every driving step because every route point lies within radio range of "
                f"the base, the clause fails in every seed: {m_(e1)} against a budget of {unit(sw['budget'], 'm', 0)}. It holds only under the narrowest "
                f"reading, so it is reported under each reading and is neither supported nor refuted as a whole; a dated entry of [67] records this."
                + (f" The readings were not computed at {' or '.join(MULT_NAME[m] for m in not_run)}." if not_run else "") +
                f" A sweep on {words(sw['n'])} seeds at today's fleet shows which assumed input decides the clause under the narrowest reading: with a "
                f"long-range ranging error of {num(rv[0], 0)}, {num(rv[1], 0)} and {unit(rv[2], 'm', 0)} the percentile is {ra(1.0)}, {ra(3.0)} and {ra(10.0)}, inside the budget in "
                f"{'every' if int(rad[1.0]['a']['seeds_inside_budget']) == sw['n'] else 'some'} seed at the first two and in "
                f"{'none' if int(rad[10.0]['a']['seeds_inside_budget']) == 0 else 'some'} at the third, while an ultra-wideband error of {num(uv[0], 1)}, "
                f"{num(uv[1], 1)} and {unit(uv[2], 'm', 1)} gives {', '.join(num(uwb[v]['a']['in_p95_m_mean'], 2) for v in (0.1, 0.3))} and {unit(uwb[0.7]['a']['in_p95_m_mean'], 'm', 2)}, "
                f"barely a difference; under the registered wording the percentile is {ra(1.0, 'e')}, {ra(3.0, 'e')} and {ra(10.0, 'e')} over the same "
                f"three ranging errors, outside the budget at each. Third, with terrain fixes the percentile stays inside the budget away from the "
                f"base, that is, where fewer than two beacons are in line of sight: {sup([p[m]['away'] for m in ms])} ({at('fixes_away_p95_m', 1)}); with "
                f"fixes the percentile at today's fleet is {unit(fx['b']['in_p95_m_mean'], 'm', 2)} where one or more beacons are in view "
                f"({cnt(fx['b']['seeds_inside_budget'])} of {cnt(fx['b']['seeds_with_steps'])} seeds inside), {unit(fx['c']['in_p95_m_mean'], 'm', 2)} within "
                f"1&nbsp;km and {unit(fx['e']['in_p95_m_mean'], 'm', 1)} over all driving. With the navigation service as assumed for 2030 the value away "
                f"from the base is " + ", ".join(f"{mci(x, 2)} at {MULT_NAME[m]}" for x, m in zip(lans, ms)) +
                f", {'inside' if all(lans_in) else ('still outside' if not any(lans_in) else 'inside at some fleet sizes only')} the budget.")
    fill("P3-H9-VERDICT-SENTENCE", h9_verdict, "E50")

    def e50_fixstops():
        ms = list(r.p6("E50", "seeds"))
        f = {m: r.p6("E50", "errors", m, "dr+ranging+fixes", "fix_stop_h_per_month") for m in ms}
        nveh = len(r.fleet())
        check(all(_fin(r.p6("E50", "errors", m, s, "fix_stop_h_per_month")["mean"]) == 0 for m in ms for s in ("dr", "dr+ranging")),
              "only the layer sets with terrain fixes stop for them (5.8)")
        check("not in the engine's delay" in str(r.p6("E50", "h10", "note")), "E50's delay does not include the fix stops (5.8, 7)")
        return (f"Terrain fixes cost standing time, {unit(PD['fix_stop_s'], 's', 0)} each: "
                + " and ".join(f"{mci(f[m], 1, 'h')} a month for the {words(nveh * int(m))} vehicles of {MULT_NAME[m]}" for m in ms) +
                f". E50 replays recorded trajectories and does not move the vehicles, so the delay it reports for the widened margins, which the companion "
                f"paper quotes [61], does not include those stops; a dated change of [67] labels it &ldquo;without stop time&rdquo;.")
    fill("P3-E50-FIXSTOP-SENTENCE", e50_fixstops, "E50")
    fill_await("P3-E50-8X-SENTENCE", lambda: f"At eight times the fleet the same percentiles were " +
               "; ".join(f"{E50_SET_NAME[s]} {mci(e50('8', s, 'all', 'p95_m'))}" for s in E50_SETS) + ".",
               "The cells at eight times the fleet, five seeds, are not in this version; their percentiles will be reported here.",
               "E50 at eight times the fleet (results/E50_summary.json, errors.8)")

    def e50b():
        """5.8: E50b (B-90b, results/E50b_summary.json), the delay with the terrain-fix stops inside the engine. Exploratory: registered
        after E50's first results (PREREG6 section 6) and run after them. Every direction word is chosen from the file."""
        d, mt, st = r.p6("E50b", "design"), r.p6("E50b", "metrics"), r.p6("E50b", "stops")
        seeds = list(r.p6("E50b", "seeds"))
        check(abs(_fin(d["stop_s"]) - PD["fix_stop_s"]) < 1e-9 and "fleet x1" in str(d["base"]) and seeds == list(r.p6("E50", "seeds", "1")),
              "E50b runs E50's scenario and seeds at today's fleet with the stop time of the navigation model (5.8)")
        check(bool(r.p6("E50b", "e50_reproduced_all_seeds")), "E50b's arm without stop time reproduces E50's cells in every seed (5.8)")
        dl, rw, vi = mt["delay_mean_h"], mt["road_wait_h"], mt["violations"]
        n = int(dl["n_seeds"])
        check(n == len(seeds) and int(dl["seeds_higher"]) + int(dl["seeds_lower"]) <= n, "E50b's delay is paired over all its seeds (5.8)")
        check(abs(_fin(dl["with_stop_time"]) - _fin(dl["without_stop_time"]) - _fin(dl["diff_mean"])) < 1e-9, "E50b: the delay difference is with minus without (5.8)")
        lo, hi = (_fin(x) for x in dl["diff_ci95_bootstrap"])
        up = _fin(dl["diff_mean"]) > 0
        rel = _fin(dl["diff_mean"]) / _fin(dl["without_stop_time"])
        rlo, rhi = (_fin(x) for x in rw["diff_ci95_bootstrap"])
        road_same = rlo <= 0 <= rhi
        ins, nav = _fin(st["engine_fix_stop_h_mean"]), _fin(st["perfect_run_fix_stop_h_mean"])
        check(abs(nav - _fin(r.p6("E50", "errors", "1", "dr+ranging+fixes", "fix_stop_h_per_month")["mean"])) < 0.01,
              "E50b: the fix time of the navigation replay is E50's fix-stop time at today's fleet (5.8)")
        check(0 < ins < nav, "E50b inserts part of the navigation replay's fix time, so its delay difference is a lower bound (5.8, 7)")
        n_with, n_without = int(round(_fin(vi["with_stop_time"]) * n)), int(round(_fin(vi["without_stop_time"]) * n))
        check(abs(_fin(vi["with_stop_time"]) * n - n_with) < 1e-6 and abs(_fin(vi["without_stop_time"]) * n - n_without) < 1e-6 and
              int(vi["seeds_higher"]) + int(vi["seeds_lower"]) <= max(n_with, n_without, 1),
              "E50b's violation means are whole counts of runs over its seeds (5.8)")
        sp = r.p6("E50b", "superseded_2026-11-13_b118_n15")
        od, ov = sp["metrics"]["delay_mean_h"], sp["metrics"]["violations"]
        o_with, o_without = int(round(_fin(ov["with_stop_time"]) * n)), int(round(_fin(ov["without_stop_time"]) * n))
        vtxt = lambda a: "no run" if a == 0 else (f"{words(a)} run" + ("s" if a != 1 else "") + f" of {cnt(n)}")
        vio = (f"with stop time {vtxt(n_with)} had a violation and without it {vtxt(n_without)}" if n_with != n_without else
               f"{vtxt(n_with)} had a violation with stop time or without it")
        vlo, vhi = (_fin(x) for x in vi["diff_ci95_bootstrap"])
        vio += (", a difference whose interval includes zero, so the stop time is not shown to add or to remove violations" if vlo <= 0 <= vhi else
                ", a difference whose interval excludes zero")
        zero = "excludes" if (lo > 0 or hi < 0) else "includes"
        return (f"A follow-up run, E50b, put the stops into the engine; it was registered after E50's first results and run after them, so it is "
                f"exploratory [67]. At today's fleet, on the same {cnt(n)} seeds, whose arm without stop time reproduces E50's cells exactly, the delay per "
                f"delivery {'rose' if up else 'fell'} from {unit(dl['without_stop_time'], 'h', 2)} without stop time to {unit(dl['with_stop_time'], 'h', 2)} "
                f"with it, by {unit(abs(_fin(dl['diff_mean'])), 'h', 2)} {ci(lo, hi, 2)} or {pc(abs(rel), 1)}; the bootstrap interval {zero} zero, a paired "
                f"t-test gives p = {num(dl['paired_t_p'], 3)}, and the delay was higher in {cnt(dl['seeds_higher'])} seeds and lower in {cnt(dl['seeds_lower'])}. "
                f"The time spent waiting at roads {'did not change' if road_same else 'changed'} ({unit(rw['diff_mean'], 'h', 2, sign=True)} {ci(rlo, rhi, 2)}); "
                f"{vio}. This is the price of the terrain-fix layer in delay, and it is a lower bound: the engine "
                f"inserted {unit(ins, 'h', 1)} of stops a month, {pc(ins / nav, 0)} of the {unit(nav, 'h', 1)} of fix time in the navigation replay, because "
                f"the other stops fall on repositioning drives, which do not pass through the road layer; a stop that falls inside a single-lane "
                f"segment ({pc(st['fixes_inside_single_lane_share'], 0)} of the fixes) is taken just after the segment's exit. E50b was rerun after the "
                f"positioning code was corrected on 13 November 2026: before, the difference in delay was {unit(od['diff_mean'], 'h', 2)} and "
                f"{vtxt(o_with)} had a violation with stop time, {vtxt(o_without)} without it.")
    fill("P3-E50B-SENTENCE", e50b, "E50b (B-90b): the delay with the fix stops in the engine")

    def table_nav():
        rows = [
            ["Wheel odometry, inertial unit and stereo cameras with lamps (visual odometry)", "Every driving class; the hopper on the ground",
             f"Drift {pc(PD['dr_firm'], 0)} of distance on firm level ground; {pc(PD['dr_loose'], 0)} on loose soil or slopes above "
             f"{num(PD['slope_loose_deg'], 0)}&deg;; {pc(PD['dr_shadow'], 0)} in shadow",
             "Measured on Earth (firm ground, 1 to 2.5&#8239;%; the lunar crater-matching work takes &ldquo;typically under 2&#8239;%&rdquo; as a design assumption); Measured on Earth (loose soil); Assumed (shadow)", "[69, 70, 71, 72]"],
            ["Star tracker, Sun sensor as backup", "As above", f"Heading held to {num(PD['heading_sigma_deg'], 1)}&deg;; a gyroscope alone drifts "
             f"{num(PD['gyro_drift_deg_h'], 0)}&deg; an hour", "Assumed (the source says a small fraction of a degree); Measured on Mars (gyroscope)", "[70, 69]"],
            ["Ranging radio, two-way (ultra-wideband)", "Every class and every beacon", f"{unit(PD['uwb_sigma_m'], 'm', 1)} per range within "
             f"{unit(PD['uwb_range_m'], 'm', 0)}", "Measured on Earth (accuracy); Assumed (range: no lunar value is public)", "[75]"],
            ["Two-way ranging over the base radio", "As above", f"{unit(PD['radio_sigma_m'], 'm', 0)} per range out to "
             f"{unit(PD['radio_range_m'] / 1000.0, 'km', 0)}, in terrain line of sight", "Assumed", "&ndash;"],
            ["Surveyed beacons", "The base mast, the depot, the power plant and one landing pad", f"{cap1(words(len(PD['beacons'])))} beacons, each surveyed to "
             f"{unit(PD['beacon_sigma_m'], 'm', 2)}", "Assumed (number, places, and that the beacons are surveyed on the 5&nbsp;m site model, whose laser tracks are placed to "
             "0.1 to 0.2&nbsp;m horizontally after adjustment; the wider polar product states 1&nbsp;m, Section 3.7)", "[76, 90]"],
            ["Cameras or lidar with the orbital map on board (terrain fix)", "Every driving class",
             f"{unit(PD['fix_sigma_lit_m'], 'm', 1)} in sunlight; {unit(PD['fix_sigma_dark_m'], 'm', 0)} in the dark with {pc(PD['fix_fail_dark'], 0)} of attempts "
             f"failing; every {unit(PD['fix_spacing_lit_m'], 'm', 0)} sunlit, {unit(PD['fix_spacing_dark_m'], 'm', 0)} in shadow; a stop of "
             f"{unit(PD['fix_stop_s'], 's', 0)}", "Spec (sunlit: a requirement of 5&nbsp;m at three sigma); simulation and field tests on Earth (accuracy in the dark); "
             "Assumed (the share of failed attempts, the spacing, the stop)",
             "[70, 71, 73]"],
            ["Receiver for the lunar navigation service", "Every class, once the service exists",
             f"{unit(PD['lans_95_m'], 'm', 0)} (95&#8239;%) with the map's height; share of the day with a fix "
             + ", ".join(f"{num(PD['lans_availability'][y], 1 if PD['lans_availability'][y] else 0)} in {y}" for y in (2028, 2029, 2030, 2031)),
             "Assumed (accuracy: the providers' target; their own simulation gives 17.2&nbsp;m); Assumed (availability by year)", "[77, 78, 79, 80]"],
            ["Oscillator and two-way time transfer to the base", "Every class", "See Section 3.6", "Assumed distribution over vehicles, taken from the excursion of one "
             "crystal measured on the lunar surface; Spec (atomic)", "[82, 86]"],
        ]
        return _tab("Table 4. What a vehicle carries to know where it is, as E50 models it (<code>lunarsim/atc/pnt.py</code>). The number is the value "
                    "the model uses; the flag says what stands behind it, in the words of Table 3 and Section 3. E50 gives every vehicle the same set and "
                    "does not model a hopper's flight separately (Assumed). No part in this table has been measured on the lunar surface; the crystal "
                    "of the last row is one receiver's, measured there once.", ["Part", "Carried by", "The number that characterises it", "Flag", "Source"], rows, cls="wide")
    T6["nav"] = (table_nav, "pnt.py", "Table 4, navigation parts")

    def table_e50():
        rows = []
        for m in r.p6("E50", "seeds"):
            for s in E50_SETS:
                e = lambda reg, met: e50(m, s, reg, met)
                p = e("all", "p95_m")
                rows.append([cap1(MULT_NAME[m]), cap1(E50_SET_NAME[s]), cnt(p["n"]), sig(e("all", "median_m")["mean"], 3),
                             f"{sig(p['mean'], 3)} [{sig(p['ci'][0], 3)}, {sig(p['ci'][1], 3)}]", sig(e("near", "p95_m")["mean"], 3), sig(e("away", "p95_m")["mean"], 3),
                             pc(e("all", "share_b95_over_budget")["mean"], 0), num(r.p6("E50", "errors", m, s, "fix_stop_h_per_month")["mean"], 1)])
        return _tab(f"Table 10. Position error by layer set in E50, means over seeds: the median and the 95th percentile of the error over driving "
                    f"vehicle-steps with its 95&#8239;% bootstrap interval, the 95th percentile near the base and away from it, the share of driving steps in which "
                    f"the vehicle's own 95&#8239;% bound exceeds the {unit(PD['budget_m'], 'm', 0)} budget, and the hours a month the fleet stands still for terrain "
                    f"fixes. The navigation service's 2028 availability is zero, so the row with terrain fixes is also the full layered scheme of 2028.",
                    ["Fleet", "Layer set", "Seeds", "Median (m)", "95th percentile (m)", "Near the base (m)", "Away from the base (m)",
                     "Own bound over budget", "Fix stops (h a month)"], rows, cls="wide")
    T6["E50_errors"] = (table_e50, "E50", "Table 10, position error by layer set")

    # --- B. time (3.6, 4.2, 5.9): the clock model's constants and the results of E51 and E51b -----------------------------
    IVL = {10: "10&nbsp;s", 60: "1&nbsp;min", 600: "10&nbsp;min", 3600: "1&nbsp;h", 21600: "6&nbsp;h", 86400: "1&nbsp;day", "never": "never"}
    DAY_US = 86400.0e6
    CLS_NAME = {"crystal": "crystal", "csac": "atomic clock"}

    def clock_rate():
        """Proposition 3, term by term (constants of Ashby and Patla [23], Table I; IAU L_G): the rate of a clock on the lunar surface
        against one on Earth's geoid, first order in 1/c^2, point masses on a circular orbit, the Sun left out."""
        GME, GMM, a = 3.986004418e14, 4.90280031e12, 3.84399e8
        LG = 6.969290134e-10
        LL = GMM / (R_MOON * C_LIGHT ** 2)
        mu, v2 = GMM / (GME + GMM), (GME + GMM) / a
        Lorb = (GME / a + (1 - mu) ** 2 * v2 / 2 - GMM / a - mu ** 2 * v2 / 2) / C_LIGHT ** 2
        return {"LG": LG, "LL": LL, "Lorb": Lorb, "rate": LG - LL - Lorb, "mu": mu, "v2": v2, "UE": GME / a, "KM": (1 - mu) ** 2 * v2 / 2,
                "UM": GMM / a, "KE": mu ** 2 * v2 / 2}

    def time_scale():
        c = clock_rate()
        k = _fin(r.p6("E51", "constants", "rate_moon_minus_earth"))
        check(abs(c["rate"] - k) < 5e-14, "the clock model's Earth-to-Moon rate is the one Proposition 3 derives (3.6, Appendix A)")
        check(abs(c["rate"] * DAY_US - 56.02) < 0.01 and abs((c["LG"] - c["Lorb"]) * DAY_US - 58.7) < 0.05,
              "the derived rate is 56.02 microseconds a day, and 58.7 without the Moon's own potential (3.6)")
        check(all(abs(c["rate"] * DAY_US - x) < 0.01 for x in (56.0199, 56.025, 56.0256)), "the three published rates agree with the derivation to 0.01 microseconds a day (3.6)")
        return (f"Proposition 3 derives the offset term by term and gives {num(c['rate'] * DAY_US, 2)}&nbsp;&micro;s a day, a rate of "
                f"{num(c['rate'] * 1e10, 4)}&nbsp;&times;&nbsp;10<sup>&minus;10</sup>, which is the constant the clock model of E51 uses; left uncorrected it is "
                f"{num(c['rate'] * 86400.0 * C_LIGHT / 1000.0, 1)}&nbsp;km of light time a day, and without the Moon's own potential it would be "
                f"{num((c['LG'] - c['Lorb']) * DAY_US, 1)}&nbsp;&micro;s a day.")
    fill("P3-TIME-SCALE-SENTENCE", time_scale, "E51 constants")

    def e10(x, nd=0):
        """x as m x 10^e."""
        e = int(math.floor(math.log10(abs(_fin(x)))))
        return f"{num(x / 10 ** e, nd)}&nbsp;&times;&nbsp;10<sup>{MINUS if e < 0 else ''}{abs(e)}</sup>"

    def time_model():
        k = r.p6("E51", "constants")
        cr, cs = k["classes"]["crystal"], k["classes"]["csac"]
        check(_fin(cr["y_lo"]) == 0 and _fin(cr["ageing_per_month"]) == 0, "the crystal's frequency error starts at zero and it has no ageing term (3.6)")
        return (f"The model has two classes. A temperature-compensated crystal has a constant frequency error drawn per vehicle, uniformly between 0 and "
                f"{e10(cr['y_hi'])} and so of one sign. That range is the excursion the crystal of one receiver, LuGRE's, showed on the lunar surface as it "
                f"warmed from 25 to 45&nbsp;&deg;C [82] (read from a figure's axis); using one crystal's excursion as the spread of constant offsets across "
                f"vehicles is our modelling choice (Assumed). A chip-scale atomic clock has a frequency error with a standard deviation of "
                f"{e10(cs['y_sigma'])}, its temperature term, and ages by {e10(cs['ageing_per_month'])} a month [86] (Spec; the data sheet says the model is "
                f"not rated for space). A vehicle is synchronised by a two-way time transfer whenever it has a radio path to the base mast, which leaves "
                f"a residual of {unit(_fin(k['tt_sigma_s']) * 1e9, 'ns', 0)} (Assumed) and corrects the offset, not the frequency (Assumed; Section 5.9 "
                f"reports a variant that steers frequency). A reservation is stamped in the vehicle's own clock and keeps a guard of "
                f"{unit(k['guard_s'], 's', 1)} (Assumed).")
    fill("P3-TIME-MODEL-SENTENCE", time_model, "E51 constants")
    fill("P3-TIME-GUARD-S", lambda: unit(r.p6("E51", "constants", "guard_s"), "s", 1), "E51 constants")

    def e51_design():
        d = r.p6("E51", "design")
        scn = str(d["scenario"])
        check(all(x in scn for x in ("C_AUCTION", "30 % load", "loss 0.10", "roads atc", "fleet x 1", "July 2028")), "E51 replays E50's month at today's fleet (4.2)")
        check(list(d["intervals_s"]) == [10, 60, 600, 3600, 21600, 86400, None] and list(d["guards_s"]) == [0.01, 0.1, 1.0, 0.0],
              "E51's resync intervals run from 10 s to never and its guards are 0.01, 0.1 and 1 s and none (4.2)")
        check(list(d["classes"]) == ["crystal", "csac"] and list(d["scales"]) == ["lunar", "earth_scale"], "E51 runs two classes on two scales (4.2)")
        fail = 1.0 - _fin(r.p6("E51", "contact_share_mean"))
        pairs = int(r.row6("E51", **{"class": "crystal", "scale": "lunar", "interval_s": 10})["conflict_pairs_checked"])
        b = r.p6("E51b", "design")
        k = r.p6("E51", "constants")
        check(abs(_fin(b["thermal_amp"]["crystal"]) - _fin(k["classes"]["crystal"]["y_hi"]) / 2) < 1e-15 and
              abs(_fin(b["thermal_amp"]["csac"]) - _fin(k["classes"]["csac"]["y_sigma"])) < 1e-18 and abs(_fin(b["thermal_period_s"]) - 86400.0) < 1e-9,
              "E51b's thermal cycle is half the crystal's measured swing and the atomic clock's temperature term, over 24 h (4.2)")
        return (f"E51 replays the month of E50 at today's fleet, the perfect-position run of each of {cnt(len(d['seeds']))} seeds, and gives every vehicle a clock "
                f"of one class. Resynchronisation is attempted every 10&nbsp;s, 1&nbsp;min, 10&nbsp;min, 1&nbsp;h, 6&nbsp;h or 1&nbsp;day, or never, and succeeds "
                f"only when the vehicle has a radio path to the base mast over the mesh; {pc(fail, 1)} of the attempts find none. The measures are the error "
                f"a clock adds to one-way ranging against a beacon on the base's clock (the speed of light times the clock error), to single-sided two-way "
                f"ranging between two vehicles with a reply delay of {unit(_fin(k['t_reply_s']) * 1000, 'ms', 0)}, and to a time-stamped position at "
                f"{unit(d['v_stamp_ms'], 'm/s', 0)}; the largest clock error; and the reservation conflicts caused by clock error alone. Such a conflict is a pair "
                f"of conflicting single-lane reservations, of {cnt(pairs)} such pairs in the {cnt(len(d['seeds']))} seeds, whose two clock errors close the nominal "
                f"gap between them by more than twice the guard; the guard is {unit(k['guard_s'], 's', 1)}, with a row for no guard. This is a check on the logged "
                f"reservations, not a new run of the engine, and it is made at today's fleet only: the fleets of four and eight times, where reservations "
                f"are more frequent, were not checked. Four things were added after the first results and are labelled post hoc (Section 4.6): guards of "
                f"0.01 and 1&nbsp;s; every vehicle on Earth seconds; a transfer that also steers frequency, with a daily thermal cycle of {e10(b['thermal_amp']['crystal'])} on the crystal and "
                f"{e10(b['thermal_amp']['csac'])} on the atomic clock (Assumed period of 24&nbsp;h); and a mixed fleet in which half the vehicles count Earth "
                f"seconds, with and without the conversion of Proposition 3.")
    fill("P3-E51-DESIGN-SENTENCE", e51_design, "E51")

    def mm(x_m):
        return f"{sig(_fin(x_m) * 1000.0, 2)}{NB}mm"

    def e51row(cls, ivl, scale="lunar"):
        return r.row6("E51", **{"class": cls, "scale": scale, "interval_s": ivl})

    def e51_results():
        ivs = [10, 3600, 86400, "never"]
        out = []
        for cls in ("crystal", "csac"):
            rows = [e51row(cls, i) for i in ivs]
            check(all(_fin(a["one_way_m_p95"]) <= _fin(b["one_way_m_p95"]) for a, b in zip(rows, rows[1:])),
                  f"E51 {cls}: the one-way ranging error grows with the resync interval (5.9)")
            check(len({round(_fin(x["two_way_single_sided_m_p95"]), 9) for x in rows}) == 1, f"E51 {cls}: two-way ranging does not depend on the resync interval (5.9)")
            out.append(f"With the {CLS_NAME[cls]}, the error added to one-way ranging at the 95th percentile was "
                       + ", ".join(f"{dist(x['one_way_m_p95'])} at a resync interval of {IVL[i]}" if i != "never" else f"and {dist(x['one_way_m_p95'])} never resynchronised"
                                   for i, x in zip(ivs, rows))
                       + f"; the largest clock error ran from {dur(rows[0]['max_abs_clock_s'])} to {dur(rows[-1]['max_abs_clock_s'])}, the error of a position "
                       f"stamp at 1&nbsp;m/s from {mm(rows[0]['stamp_m_at_1ms_p95'])} to {mm(rows[-1]['stamp_m_at_1ms_p95'])}, and single-sided two-way "
                       f"ranging between vehicles {mm(rows[0]['two_way_single_sided_m_p95'])} at every interval.")
        p = r.row6("E51", **{"class": "perfect"})
        check(all(_fin(p[k]) == 0 for k in ("one_way_m_p95", "max_abs_clock_s", "conflicts_guard_0", "conflicts_guard_0.1")), "perfect clocks add nothing and cause no conflict (5.9)")
        c0 = e51row("crystal", 10)
        check(c0["one_way_m_p95"] > 1000 * _fin(c0["one_way_m_median"]), "the crystal's 95th percentile at a 10 s resync is set by vehicles out of contact (5.9)")
        return (" ".join(out) + f" With perfect clocks every measure is zero, the baseline. The crystal's 95th percentile is set by vehicles that are out "
                f"of contact and free-run however often a transfer is attempted, vehicles that could not range to the base either: at a 10&nbsp;s resync its "
                f"median is {dist(c0['one_way_m_median'], 2)} and its largest clock error {dur(c0['max_abs_clock_s'])} (Table 11). Two-way ranging, which Section 3.5 uses, is unaffected by the "
                f"interval because the clock offset cancels in it.")
    fill("P3-E51-RESULTS-SENTENCE", e51_results, "E51")

    def e51_guards():
        ivs = [10, 60, 600, 3600, 21600, 86400, "never"]
        G = ("0.01", "0.1", "1", "0")
        tab = {g: [int(e51row("crystal", i)[f"conflicts_guard_{g}"]) for i in ivs] for g in G}
        cs = {g: [int(e51row("csac", i)[f"conflicts_guard_{g}"]) for i in ivs] for g in G}
        check(all(x == 0 for g in ("0.01", "0.1", "1") for x in cs[g]) and min(cs["0"]) > 0, "the atomic clock has no conflict with any guard and some without one (5.9)")
        check(min(tab["0"]) > 0, "without a guard the crystal has conflicts at every interval (5.9)")

        def safe_to(g):
            ok = [i for i, x in zip(ivs, tab[g]) if x == 0]
            check(ok == ivs[:len(ok)], f"guard {g} s: the conflict-free intervals are the shortest ones (5.9)")
            return ok[-1] if ok else None
        s1, s01, s001 = safe_to("1"), safe_to("0.1"), safe_to("0.01")
        if None in (s1, s01, s001):
            raise Pending("a guard has no conflict-free interval; the guard sentence of 5.9 needs rewording")
        worst = _fin(e51row("crystal", "never")["max_abs_clock_s"])
        txt = lambda s: "even when it is never resynchronised" if s == "never" else f"with a resync at least every {IVL[s]}"
        nxt = lambda g, s: "" if s == "never" else f" ({cnt(tab[g][ivs.index(s) + 1])} at the next longer interval, {cnt(tab[g][-1])} never resynchronised)"
        return (f"Counted over the {cnt(len(r.p6('E51', 'seeds')))} seeds, and with the 0.01 and 1&nbsp;s guards added post hoc, the crystal caused no clock-only "
                f"reservation conflict with a guard of 1&nbsp;s "

                f"{txt(s1)}{nxt('1', s1)}, with a guard of 0.1&nbsp;s {txt(s01)}{nxt('0.1', s01)}, and with a guard of 0.01&nbsp;s {txt(s001)}{nxt('0.01', s001)}; "
                f"with no guard it caused {cnt(min(tab['0']))} to {cnt(max(tab['0']))} at every interval. Its largest clock error when never resynchronised was "
                f"{dur(worst)}. The atomic clock caused none with any guard at any interval, and {cnt(min(cs['0']))} to {cnt(max(cs['0']))} with none. The column "
                f"without a guard needs care: it counts a pair as soon as the two clock errors close the nominal gap at all, and for reservations booked back "
                f"to back, with no nominal gap, that is the sign of the difference of two clock errors, however small. It is a count of back-to-back pairs "
                f"and not of conflicts a vehicle would meet, which is why the better clock shows more of them than the crystal at a 10&nbsp;s resync.")
    fill("P3-E51-GUARD-SENTENCE", e51_guards, "E51")

    def h11_verdict():
        """5.9: H11' in its two halves. The first is an observation on the logged reservations; the second is a property of the assumed
        transfer residual and could not have failed (finding M6; decision A1): it is called a design calculation."""
        h = r.p6("E51", "h11")
        uwb = _fin(r.p6("E51", "design", "uwb_sigma_m"))
        ivs = [10, 60, 600, 3600, 21600, 86400]
        both = [i for i in ivs if int(e51row("crystal", i)["conflicts_guard_0.1"]) == 0 and int(e51row("crystal", i)["seeds_with_conflict_guard_0.1"]) == 0
                and _fin(e51row("crystal", i)["one_way_m_p95"]) > uwb]
        check(both == list(h["intervals_meeting_both"]) and bool(h["supported"]) == bool(both), "H11's flag and intervals follow from the rows by the file's rule (5.9)")
        res_m = _fin(r.p6("E51", "constants", "tt_sigma_s")) * C_LIGHT
        check(res_m > 10 * uwb, "the assumed transfer residual alone is far above the ranging radio's noise, so H11's ranging half holds for any oscillator (5.9)")
        pairs = int(e51row("crystal", 10)["conflict_pairs_checked"])
        head = (f"H11 of [67] asks for a resync interval at which the cheaper oscillator causes no reservation conflict while its clock error still adds "
                f"more to one-way ranging than the ranging radio's own noise of {unit(uwb, 'm', 1)}. ")
        calc = (f"The second half is not a test. The time transfer is assumed to leave {unit(res_m / C_LIGHT * 1e9, 'ns', 0)}, which is {unit(res_m, 'm', 0)} of "
                f"range, so the clock error exceeds the radio's noise for any oscillator, a perfect one included: it is a design calculation on that "
                f"assumed residual and could not have come out otherwise (a dated entry of [67]).")
        if not both:
            return head + "The first half was not observed: no interval of the sweep has zero clock-caused conflicts with the 0.1&nbsp;s guard. " + calc
        return (head + f"The first half was observed: with the 0.1&nbsp;s guard every interval from {IVL[both[0]]} to {IVL[both[-1]]} gave no clock-caused "
                f"conflict in any seed, over the {cnt(pairs)} pairs of conflicting single-lane reservations in the recorded months. " + calc +
                f" By the registered rule the hypothesis counts as supported; it is exploratory and outside the confirmatory family.")
    fill("P3-H11-VERDICT-SENTENCE", h11_verdict, "E51")

    def e51b_row(part, cls, ivl, variant):
        g = [x for x in r.p6("E51b", "rows") if x["part"] == part and x["class"] == cls and x["interval_s"] == ivl and str(x["variant"]).startswith(variant)]
        if len(g) != 1:
            raise KeyError(f"E51b row {part} {cls} {ivl} {variant}: {len(g)} rows")
        return g[0]

    def e51b_steering():
        ivs = list(r.p6("E51b", "design", "intervals_s"))
        tt = _fin(r.p6("E51", "constants", "tt_sigma_s"))
        check("sqrt(2) x 100 ns / interval" in str(r.p6("E51b", "estimator")) and abs(tt - 1e-7) < 1e-15, "the steering estimator's noise is sqrt(2) x 100 ns / interval (5.9)")
        out = []
        for cls in ("crystal", "csac"):
            ratio = {i: _fin(e51b_row("steering", cls, i, "offset")["one_way_m_p95"]) / _fin(e51b_row("steering", cls, i, "steer")["one_way_m_p95"]) for i in ivs}
            better = [i for i in ivs if ratio[i] > 1]
            worse = [i for i in ivs if ratio[i] <= 1]
            s = (f"steering cut the {CLS_NAME[cls]}'s one-way ranging error at the 95th percentile by a factor of {num(min(ratio[i] for i in better), 1)} to "
                 f"{num(max(ratio[i] for i in better), 1)}" + ("" if not worse else f" at resync intervals of {IVL[better[0]]} and longer"))
            for i in worse:
                o, st = e51b_row("steering", cls, i, "offset"), e51b_row("steering", cls, i, "steer")
                noise = math.sqrt(2) * tt / i
                ysig = _fin(r.p6("E51", "constants", "classes", cls, "y_sigma")) if cls == "csac" else _fin(r.p6("E51", "constants", "classes", cls, "y_hi"))
                check(noise > ysig, f"E51b {cls} at {i} s: the estimator's noise exceeds the oscillator's own frequency error where steering hurts (5.9)")
                s += (f" and made it worse at {IVL[i]}, {dist(st['one_way_m_p95'])} against {dist(o['one_way_m_p95'])}, because the estimate's own noise there, "
                      f"{e10(noise, 1)}, is larger than the clock's frequency error")
            out.append(s)
        check(all(int(x["conflicts_guard_0.1"]) == 0 for x in r.p6("E51b", "rows") if x["part"] == "steering"), "no steering cell has a conflict with the 0.1 s guard (5.9)")
        return (f"With a daily thermal cycle on the frequency and a transfer that also estimates it (post hoc), " + "; ".join(out) +
                f". No steering cell had a clock-caused conflict with the 0.1&nbsp;s guard.")
    fill("P3-E51B-STEERING-SENTENCE", e51b_steering, "E51b")

    def e51b_mixed():
        ivs = list(r.p6("E51b", "design", "mixed_intervals_s"))
        ivs = ["never" if i is None else i for i in ivs]
        add = {}
        for cls in ("crystal", "csac"):
            for i in ivs:
                a, b = e51b_row("mixed", cls, i, "half Earth seconds"), e51b_row("mixed", cls, i, "lunar for all")
                add[(cls, i)] = _fin(a["cross_scale_one_way_m_p95"]) / _fin(b["cross_scale_one_way_m_p95"]) - 1.0
                check(int(a["cross_scale_conflicts_guard_0.1"]) == int(b["cross_scale_conflicts_guard_0.1"]) and
                      int(a["cross_scale_conflicts_guard_0.01"]) == int(b["cross_scale_conflicts_guard_0.01"]),
                      f"E51b mixed {cls} {i}: the conversion changes no conflict count (5.9)")
        check(all(int(e51b_row("mixed", "csac", i, "half Earth seconds")["cross_scale_conflicts_guard_0.01"]) == 0 for i in ivs), "the atomic clock has no cross-scale conflict (5.9)")
        ca = [add[("csac", i)] for i in ivs]
        cr = [add[("crystal", i)] for i in ivs]
        check(min(ca) > 0.10 and max(cr) < 0.01, "mixed scales matter for the atomic clock and vanish under the crystal's drift (5.9)")
        x10 = e51b_row("mixed", "csac", ivs[0], "half Earth seconds")
        y10 = e51b_row("mixed", "csac", ivs[0], "lunar for all")
        return (f"In a fleet where half the vehicles count Earth seconds (post hoc), one-way ranging between two vehicles on different scales was "
                f"{pc(min(ca), 0)} to {pc(max(ca), 0)} worse for the atomic clock without the conversion of Proposition 3 than with it "
                f"({dist(x10['cross_scale_one_way_m_p95'])} against {dist(y10['cross_scale_one_way_m_p95'])} at a resync interval of {IVL[ivs[0]]}), and less than "

                f"{pc(max(max(cr), 0.0005), 1)} worse for the crystal, whose own drift hides the offset. The count of clock-caused reservation conflicts between "
                f"vehicles on different scales was the same with and without the conversion at every interval and guard, and zero for the atomic clock.")
    fill("P3-E51B-MIXED-SENTENCE", e51b_mixed, "E51b")

    def holdover_check():
        """Proposition 4's holdover formula against the file's analytic column (the 95th-percentile frequency error of each class)."""
        k = r.p6("E51", "constants", "classes")
        A = _fin(k["csac"]["ageing_per_month"]) / (30.0 * 86400.0)
        y = {"crystal": 0.95 * _fin(k["crystal"]["y_hi"]), "csac": 1.959964 * _fin(k["csac"]["y_sigma"])}
        for cls in ("crystal", "csac"):
            for use, h in r.p6("E51", "holdover", cls).items():
                b = _fin(h["budget_s"])
                t = b / y[cls] if cls == "crystal" else (-y[cls] + math.sqrt(y[cls] ** 2 + 2 * A * b)) / A
                check(abs(t - _fin(h["analytic_y95_s"])) < 1e-3 * t, f"Proposition 4: the holdover of the {cls} for '{use}' is the formula's value")
                check(abs(_fin(h["p5_over_vehicles_s"]) - t) < 0.06 * t, f"E51: the simulated holdover of the {cls} for '{use}' is within 6 % of the formula")
        return y, A

    def table_e51():
        ivs = [10, 60, 600, 3600, 21600, 86400, "never"]
        rows = []
        for cls in ("crystal", "csac"):
            for i in ivs:
                x = e51row(cls, i)
                rows.append([cap1(CLS_NAME[cls]), IVL[i], dist(x["one_way_m_p95"]), dur(x["max_abs_clock_s"]),
                             sig(_fin(x["stamp_m_at_1ms_p95"]) * 1000, 2), cnt(x["conflicts_guard_0.01"]), cnt(x["conflicts_guard_0.1"]),
                             cnt(x["conflicts_guard_1"]), cnt(x["conflicts_guard_0"])])
        return _tab(f"Table 11. Clock error and what it does, E51, lunar time scale, {cnt(len(r.p6('E51', 'seeds')))} seeds at today's fleet: the error added to "
                    f"one-way ranging (95th percentile), the largest clock error, the error of a position stamp at 1&nbsp;m/s (95th percentile, mm), and the "
                    f"reservation conflicts caused by clock error alone, summed over the seeds, for guards of 0.01, 0.1 and 1&nbsp;s and for none. A resync is "
                    f"attempted at the stated interval and succeeds only with a radio path to the base mast.",
                    ["Oscillator", "Resync interval", "One-way ranging error", "Largest clock error", "Position stamp (mm)", "Conflicts, guard 0.01 s",
                     "Guard 0.1 s", "Guard 1 s", "No guard"], rows, cls="wide")
    T6["E51_clocks"] = (table_e51, "E51", "Table 11, clock error by oscillator and resync interval")

    def table_holdover():
        holdover_check()
        hc, ha = r.p6("E51", "holdover", "crystal"), r.p6("E51", "holdover", "csac")
        check(list(hc) == list(ha), "the holdover table has the same uses for both classes")
        bs = [_fin(v["budget_s"]) for v in hc.values()]
        check(7.0 <= math.log10(max(bs) / min(bs)) < 8.0, "the budgets of the uses of time span seven orders of magnitude (3.6)")
        rows = []
        tt, n_below = _fin(r.p6("E51", "constants", "tt_sigma_s")), 0
        for use in hc:
            b = _fin(hc[use]["budget_s"])
            bud = f"{sig(b * 1e9, 3)}&nbsp;ns" if b < 1e-6 else (f"{sig(b * 1e6, 2)}&nbsp;&micro;s" if b < 1e-3 else (f"{sig(b * 1e3, 2)}&nbsp;ms" if b < 0.1 else f"{sig(b, 2)}&nbsp;s"))
            below = b < tt
            n_below += int(below)
            rows.append([html.escape(cap1(use.split(" (")[0])), bud + (f" (below the assumed transfer residual of {unit(tt * 1e9, 'ns', 0)}: not reachable)" if below else ""),
                         dur(hc[use]["p5_over_vehicles_s"]), dur(ha[use]["p5_over_vehicles_s"])])
        check(n_below == 2, "two budgets of Table 12 lie below the assumed transfer residual and are marked not reachable (5.9)")
        nveh = {int(v["n_vehicles"]) for v in hc.values()}
        return _tab(f"Table 12. Holdover: the longest time without a resync for which 95&#8239;% of the drawn clocks keep each use inside its budget. The "
                    f"times are the closed form of Proposition 4, part (c), applied to {' and '.join(cnt(n) for n in sorted(nveh))} drawn clocks of each class; they "
                    f"are a calculation, not a simulation of the fleet, and the analytic value the build compares them with is the same formula at the "
                    f"95th-percentile frequency error. The formula sets the residual of the synchronisation to zero, while the model's transfer leaves "
                    f"{unit(tt * 1e9, 'ns', 0)}: the uses whose budget is below that residual are outside it at the instant of synchronisation and are "
                    f"marked. The budgets are derived in Proposition 4 and its remarks, except the two slot budgets, which are the cellular requirement "
                    f"[87] and a 10&nbsp;ms slot with a 1&#8239;% guard.", ["Use", "Clock error allowed", "Crystal holds it for", "Atomic clock holds it for"], rows)
    T6["E51_holdover"] = (table_holdover, "E51", "Table 12, holdover per use")

    # --- C. the shared map and its frame (3.7, 4.2, 5.10): Proposition 5's numbers, the tile sizes and E52 --------------
    FK_ANGLES_ARCSEC = (67.8526, 78.6944, 0.2785)      # NAIF moon_de440_250416.tf, TKFRAME_31009_ANGLES about axes (3, 2, 1) [88]
    TILE_CENTRE = (-89.4632, 222.5104)                 # the centre of the Connecting Ridge terrain tile, degrees (research note 02, E1)

    def frame_shift(lat, lon):
        """Proposition 5: the displacement |(M - I) r| on the 1,737.4 km sphere when coordinates of one frame are read in the other."""
        a3, a2, a1 = (math.radians(x / 3600.0) for x in FK_ANGLES_ARCSEC)
        rz = np.array([[math.cos(a3), math.sin(a3), 0], [-math.sin(a3), math.cos(a3), 0], [0, 0, 1]])
        ry = np.array([[math.cos(a2), 0, -math.sin(a2)], [0, 1, 0], [math.sin(a2), 0, math.cos(a2)]])
        rx = np.array([[1, 0, 0], [0, math.cos(a1), math.sin(a1)], [0, -math.sin(a1), math.cos(a1)]])
        M = rz @ ry @ rx
        la, lo = math.radians(lat), math.radians(lon)
        rr = R_MOON * np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
        return float(np.linalg.norm(M @ rr - rr)), float(math.acos((np.trace(M) - 1.0) / 2.0))

    def frame_numbers():
        from lunarsim.atc import geo as GEO
        pole, ang = frame_shift(-90.0, 0.0)
        site, _ = frame_shift(*TILE_CENTRE)
        eq, _ = frame_shift(0.0, 0.0)
        for name, val, at in (("pole", pole, (-90.0, 0.0)), ("tile centre", site, TILE_CENTRE), ("latitude 0, longitude 0", eq, (0.0, 0.0))):
            check(abs(float(np.linalg.norm(GEO.frame_mixup_shift(*at))) - val) < 0.05,
                  f"Proposition 5: the frame shift at the {name} equals lunarsim/atc/geo.py's to 0.05 m")
        a2, a1 = (math.radians(x / 3600.0) for x in FK_ANGLES_ARCSEC[1:])
        check(abs(pole - R_MOON * math.hypot(a2, a1)) < 0.01, "Proposition 5: at the pole the shift is R x sqrt(theta_x^2 + theta_y^2) to first order")
        check(abs(eq - R_MOON * ang) < 0.01 and abs(math.degrees(ang) - 0.02886) < 1e-5, "Proposition 5: the largest shift is R x the rotation angle of 0.02886 degrees")
        check(abs(R_MOON - GEO.R_MOON) < 1e-9, "one reference sphere in the build and in geo.py")
        fk = os.path.join(ROOT, ".cache", "comms", "kernels", "moon_de440_250416.tf")
        if os.path.exists(fk):          # the kernel is a download, not a repository file: checked when it is there
            m = re.search(r"TKFRAME_31009_ANGLES\s*=\s*\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\)", open(fk, encoding="latin-1").read())
            check(bool(m) and tuple(float(x) for x in m.groups()) == FK_ANGLES_ARCSEC, "the three angles are those of the NAIF lunar frame kernel")
        return {"pole": pole, "site": site, "eq": eq, "ang": ang}

    def map_frame():
        f = frame_numbers()
        return (f"Proposition 5 gives the size of the mistake the identifier prevents: the same numbers read in the other frame move a point by "
                f"{unit(f['pole'], 'm', 1)} at the south pole, {unit(f['site'], 'm', 1)} at the centre of our terrain tile and {unit(f['eq'], 'm', 1)} at "
                f"most, computed from the three angles of the NAIF frame kernel [88] and equal to a direct evaluation with the SPICE toolkit to within "
                f"0.05&nbsp;m [68].")
    fill("P3-MAP-FRAME-SENTENCE", map_frame, "geo.py frame shift")

    def e52row(out_h, order, rate):
        return r.row6("E52", out_h=out_h, order=order, rate_kbps=rate)

    def map_sizes():
        """Proposition 6's numbers for one 256 m layer of the 16 km site, with the checks against E52's rows."""
        from lunarsim.atc import smap as SMAP
        ns = SMAP.tiles_per_side("hazard")
        N, D, h, v = ns * ns, SMAP.quadtree_depth(ns), 8, 2
        check(D == math.ceil(math.log(N, 4)), "Proposition 6: the quadtree depth is ceil(log4 N)")
        n = int(r.p6("E52", "parameters", "tiles_per_day"))
        tree, flat = h * (1 + 4 * n * D), N * (v + h)
        lay = r.p6("E52", "layers")
        nl = len(lay)
        n_all = sum(SMAP.tiles_per_side(k) ** 2 for k in lay)
        for x in r.p6("E52", "rows"):
            check(_fin(x["tree_overhead_bytes"]) <= h * (nl + 4 * _fin(x["tiles_changed_mean"]) * D) + 1e-9,
                  f"Proposition 6: E52's hash-tree walk after {x['out_h']} h is within the bound h (1 + 4 n D) per layer")
            check(abs(_fin(x["flat_manifest_bytes"]) - n_all * (v + h)) < 1e-9, "E52's flat manifest is 10 bytes for every tile of the four raster layers")
        check(SMAP.POS_SIGMA_LIMIT_M == 2.0 and SMAP.HEIGHT_DIFF_LIMIT_M == 1.0 and SMAP.HAZARD_GROWTH_SIGMA == 3.0 and SMAP.SITE_M == 16000.0,
              "the acceptance limits and the site size typed in 3.7 are those of lunarsim/atc/smap.py")
        cells = (256.0 / 1.0) ** 2
        bits = {k: _fin(lay[k]["bytes"]) * 8 / cells for k in ("hazard", "traversability", "elevation1")}
        check(abs(bits["hazard"] - 0.25) < 1e-3 and abs(bits["traversability"] - 1.44) < 1e-3 and abs(bits["elevation1"] - 4.0) < 1e-9,
              "the three tile sizes are 256 x 256 cells at 0.25, 1.44 and 4 bits a cell (3.7)")
        return {"N": N, "ns": ns, "D": D, "h": h, "v": v, "n": n, "tree": tree, "flat": flat, "cross": N * (v + h) / (4.0 * D * h), "lay": lay,
                "day": n * sum(_fin(lay[k]["bytes"]) for k in ("hazard", "traversability", "elevation1"))}

    def map_sync():
        s = map_sizes()
        lay, p = s["lay"], r.p6("E52", "parameters")
        kb = lambda b: f"{num(_fin(b) / 1000.0, 1)}{NB}kB"
        return (f"On the wire a 256&nbsp;m tile of 1&nbsp;m cells weighs {cnt(lay['hazard']['bytes'])}&nbsp;B as a hazard layer, at 0.25 bit a cell (Assumed; "
                f"a slope mask of our own terrain compressed to a median of 0.12 bit a cell), {cnt(lay['traversability']['bytes'])}&nbsp;B as a "
                f"traversability layer, at the 1.44 bits a cell that five slope classes of our terrain compressed to, and {cnt(lay['elevation1']['bytes'])}&nbsp;B "
                f"as rover-made elevation, at 4 bits a cell (Assumed). These are computed from tile sizes, not from a flown map [68]. The 16&nbsp;km site has "
                f"{cnt(s['N'])} such tiles a layer. With {cnt(s['n'])} of them changed in a day (Assumed: half the tiles the haul routes cross), the hash-tree "
                f"walk costs at most {cnt(s['tree'])}&nbsp;B a layer by Proposition 6, against {cnt(s['flat'])}&nbsp;B for a flat list of every tile's version "
                f"and hash; the tree is the smaller for up to {cnt(math.floor(s['cross']))} changed tiles (the bound is n below {num(s['cross'], 1)}). Both counts "
                f"are hash bytes in one direction, without the replies that say which children differ and without message headers. The tiles themselves then come to "
                f"{kb(s['n'] * _fin(lay['hazard']['bytes']))} of hazards, which go first, and {num(s['day'] / 1e6, 2)}&nbsp;MB for the three layers together.")
    fill("P3-MAP-SYNC-SENTENCE", map_sync, "E52 layers")

    def e52_design():
        p = r.p6("E52", "parameters")
        lay = r.p6("E52", "layers")
        s = map_sizes()
        check(abs(_fin(p["loss"]) - 0.2) < 1e-9 and abs(_fin(p["speed_ms"]) - 1.0) < 1e-9 and abs(_fin(p["hidden_share"]) - 0.5) < 1e-9,
              "E52: packet loss 0.2, a rover at 1 m/s, half the hazards invisible to it (4.2)")
        outs = sorted({int(x["out_h"]) for x in r.p6("E52", "rows")})
        rates = sorted({int(x["rate_kbps"]) for x in r.p6("E52", "rows")})
        check(outs == [1, 6, 24, 72, 168, 336] and rates == [10, 16, 100, 1000], "E52's outages run from 1 h to 14 days and its link rates from 10 kbit/s to 1 Mbit/s (4.2)")
        return (f"E52 keeps the base's map and one rover's copy of it for the 16&nbsp;km site: {cnt(s['N'])} tiles of 256&nbsp;m in each of the hazard, "
                f"traversability and rover-made elevation layers and a radio-coverage layer in {cnt(lay['radio']['tile_m'])}&nbsp;m tiles of {cnt(lay['radio']['bytes'])}&nbsp;B, at the "
                f"wire sizes of Section 3.7. The rover loops the haul routes at {unit(p['speed_ms'], 'm/s', 0)}; the routes cross {cnt(r.p6('E52', 'route_tiles'))} "
                f"tiles. While it is out of contact, {cnt(p['tiles_per_day'])} route tiles a day get a new version in each of the three layers, and new hazards "
                f"appear on the routes at {num(p['hazards_per_day'], 0)} a day, keep-out zones at {num(p['keepouts_per_day'], 1)} a day and road-edge changes at "
                f"{num(p['road_edges_per_day'], 0)} a day; {pc(p['hidden_share'], 0)} of the hazards are invisible to the rover's own sensors (all Assumed). "
                f"After 1&nbsp;h, 6&nbsp;h, 1, 3, 7 or 14 days the rover regains a link of 10, 16, 100 or 1,000&nbsp;kbit/s with a packet loss of "
                f"{num(p['loss'], 1)} and synchronises, either hazards first (keep-out zones, hazard tiles on its route, other hazards, roads, "
                f"traversability, radio coverage, elevation) or oldest change first, over {cnt(r.p6('E52', 'seeds'))} seeds. The outcomes are the bytes sent "
                f"against a full resend of every raster layer ({num(_fin(r.p6('E52', 'full_resend_bytes')) / 1e6, 1)}&nbsp;MB), the time until the hazard "
                f"layer is current, and the hazards the rover drives into because its copy is stale, during the outage and after contact. The registered run has one setting "
                f"of the change rates; Section 5.10 reports a sweep of them, run after the fact.")
    fill("P3-E52-DESIGN-SENTENCE", e52_design, "E52")

    def e52_results():
        hf, of = e52row(24, "hazards_first", 16), e52row(24, "oldest_first", 16)
        mb = lambda b: f"{num(_fin(b) / 1e6, 2)}{NB}MB" if _fin(b) >= 1e6 else f"{num(_fin(b) / 1e3, 0)}{NB}kB"
        check(hf["bytes_mean"] == of["bytes_mean"] and abs(_fin(hf["t_all_s"]) - _fin(of["t_all_s"])) < 1e-6, "the order changes neither the bytes nor the time to finish (5.10)")
        ratio = _fin(of["t_hazards_current_s"]) / _fin(hf["t_hazards_current_s"])
        b = {o: _fin(e52row(o, "hazards_first", 16)["bytes_mean"]) for o in (1, 6, 24, 72, 168, 336)}
        check(all(b[x] <= b[y] for x, y in zip((1, 6, 24, 72, 168), (6, 24, 72, 168, 336))) and b[336] < 1.05 * b[72], "the bytes to sync grow with the outage and level off after three days (5.10)")
        hits = {o: _fin(e52row(o, "hazards_first", 16)["hits_during_outage_mean"]) for o in b}
        after_hf = max(_fin(e52row(o, "hazards_first", rt)["hits_after_contact_mean"]) for o in b for rt in (10, 16, 100, 1000))
        after_of = max(_fin(e52row(o, "oldest_first", rt)["hits_after_contact_mean"]) for o in b for rt in (10, 16, 100, 1000))
        check(hits[336] > 5 * max(after_hf, after_of) and after_hf <= after_of, "most stale-map hits of a long outage happen during the outage, and hazards-first has no more hits after contact than oldest-first (5.10, 6.1)")
        sp = r.p6("E52", "superseded_2026-11-13_b118_n1")
        old = sp["rows"]
        old_hf = max(_fin(x["hits_after_contact_mean"]) for x in old if x["order"] == "hazards_first")
        old_of = max(_fin(x["hits_after_contact_mean"]) for x in old if x["order"] == "oldest_first")
        old_day = next(_fin(x["hits_during_outage_mean"]) for x in old if x["out_h"] == 24 and x["order"] == "hazards_first" and x["rate_kbps"] == 16)
        new_by = {(x["out_h"], x["order"], x["rate_kbps"]): x for x in r.p6("E52", "rows")}
        check(len(old) == len(new_by) and all(all(x[k] == new_by[(x["out_h"], x["order"], x["rate_kbps"])][k] for k in x if not k.startswith("hits_")) for x in old) and
              sp["h12"] == r.p6("E52", "h12"), "the code-review correction of E52 moved only the stale-map hit counts: bytes, times and H12 are unchanged (5.10)")
        return (f"After a day out of contact the rover's copy was behind by {num(hf['tiles_changed_mean'], 0)} tile versions on average. Bringing it up to date "
                f"took {mb(hf['bytes_mean'])}, {pc(hf['share_of_full_resend'], 2)} of a full resend, of which the hash-tree walk was "
                f"{cnt(hf['tree_overhead_bytes'])}&nbsp;B, against {cnt(hf['flat_manifest_bytes'])}&nbsp;B for a flat list of every tile. At 16&nbsp;kbit/s the "
                f"hazard layer was current after {dur(hf['t_hazards_current_s'])} with hazards first and after {dur(of['t_hazards_current_s'])} with the oldest "
                f"change first, {num(ratio, 0)} times later; everything was current after {dur(hf['t_all_s'])} in either order. The bytes level off: "
                f"{mb(b[1])} after an hour, {mb(b[6])} after six hours, {mb(b[72])} after three days and {mb(b[336])} after fourteen, when every route tile has "
                f"changed in each of the three layers. The hazards the rover drove into because its copy was stale were, during the outage itself, "
                f"{num(hits[1], 2)} for an hour out of contact, {num(hits[24], 2)} for a day and {num(hits[336], 1)} for fourteen days, and after contact at most "
                f"{num(after_hf, 2)} with hazards first and {num(after_of, 2)} with the oldest change first, at any outage and link rate (means over "
                f"{cnt(r.p6('E52', 'seeds'))} seeds; Table 13). The hit counts were corrected after a code review on 13 November 2026, which found that "
                f"every tile of a road leg had been given the tour distance of the leg's end: before, the largest counts after contact were "
                f"{num(old_hf, 2)} and {num(old_of, 2)} and the count for a day out of contact {num(old_day, 2)}; bytes and times did not change.")
    fill("P3-E52-RESULTS-SENTENCE", e52_results, "E52")

    def h12_verdict():
        """5.10: H12 is a design calculation, not a test (finding M6; decisions A1 and B8; PREREG6 section 6): the share is the assumed
        change rate over the tile count, and a subset sent first is always finished first."""
        h = r.p6("E52", "h12")
        share = _fin(h["share_of_full_resend_24h"])
        pr = h["paired_24h"]
        c1 = share < 0.10
        c2 = all(int(v["seeds_hazards_first_sooner"]) == int(v["n"]) and _fin(v["mean_s"]) < 0 for v in pr.values())
        check(bool(h["supported"]) == (c1 and c2) and all(bool(x) for x in h["sooner_at_every_rate"].values()) == c2 and
              abs(share - _fin(e52row(24, "hazards_first", 16)["share_of_full_resend"])) < 1e-5, "H12's flag follows from its two clauses (5.10)")
        s = map_sizes()
        n_day, n_all = 3 * s["n"], 3 * s["N"]
        check(abs(n_day / n_all - share) < 2e-4, "H12's share of a full resend is the assumed changed tiles over the tiles of the three layers (5.10)")
        rates = sorted(pr, key=float)
        prod = [abs(_fin(pr[k]["mean_s"])) * float(k) for k in rates]
        check(max(prod) / min(prod) < 1.01, "H12: the paired differences between the two orders are in inverse ratio to the link rate (5.10)")
        return (f"H12 of [67] was registered as a hypothesis with two clauses for a rover that was out of contact for 24&nbsp;h. Neither is a test: both "
                f"are design calculations on the assumed inputs and could not have failed, and a dated entry of [67] records it. First, that a "
                f"hazards-first sync of changed tiles needs under 10&#8239;% of the bytes of a full resend: with {cnt(s['n'])} route tiles assumed to change a "
                f"day in each of three layers of {cnt(s['N'])} tiles, the changed tiles are {cnt(n_day)} of {cnt(n_all)}, {pc(n_day / n_all, 2)} of the map, so a "
                f"sync of changed tiles is {pc(share, 2)} of a full resend; the result follows from the assumed change rate, and the sweep reported below gives its range. Second, that it brings the hazard layer current "
                f"sooner than oldest-first at every link rate: a subset sent first is always finished first, {'in every seed' if c2 else 'though not in every seed here'}, "
                f"and the paired means, "
                + ", ".join(f"{dur(abs(_fin(pr[k]['mean_s'])))} at {cnt(float(k))}{KBPS6}" for k in rates) +
                f", are in exact inverse ratio to the link rate. What E52 adds to the arithmetic is the sizes of Table 13 and the count of stale-map hits.")
    KBPS6 = NB + "kbit/s"
    fill("P3-H12-VERDICT-SENTENCE", h12_verdict, "E52")

    def e52_limit():
        """6.1: where the stale-map hits happen (direction checked in e52_results)."""
        e52_results()
        d1, d14 = (_fin(e52row(o, "hazards_first", 16)["hits_during_outage_mean"]) for o in (24, 336))
        after = max(_fin(x["hits_after_contact_mean"]) for x in r.p6("E52", "rows"))
        return (f"a rover out of contact for a day drove into {num(d1, 1)} hazards its copy did not show, and one out for fourteen days into {num(d14, 1)}, "
                f"all during the outage; after contact the count was at most {num(after, 1)} in any cell")
    fill("P3-E52-LIMIT-CLAUSE", e52_limit, "E52")

    def table_e52():
        rows = []
        mb = lambda b: f"{num(_fin(b) / 1e6, 2)}{NB}MB" if _fin(b) >= 1e6 else f"{num(_fin(b) / 1e3, 0)}{NB}kB"
        name = {1: "1&nbsp;h", 6: "6&nbsp;h", 24: "1&nbsp;day", 72: "3&nbsp;days", 168: "7&nbsp;days", 336: "14&nbsp;days"}
        for o in (1, 6, 24, 72, 168, 336):
            h16, o16, h100, o100 = (e52row(o, a, b) for a, b in (("hazards_first", 16), ("oldest_first", 16), ("hazards_first", 100), ("oldest_first", 100)))
            rows.append([name[o], num(h16["tiles_changed_mean"], 1), mb(h16["bytes_mean"]), pc(h16["share_of_full_resend"], 2), cnt(h16["tree_overhead_bytes"]),
                         f"{sig(h16['t_hazards_current_s'], 2)} / {sig(o16['t_hazards_current_s'], 3)}", f"{sig(h100['t_hazards_current_s'], 2)} / {sig(o100['t_hazards_current_s'], 3)}",
                         dur(h16["t_all_s"]), num(h16["hits_during_outage_mean"], 2), f"{num(h16['hits_after_contact_mean'], 2)} / {num(o16['hits_after_contact_mean'], 2)}"])
        return _tab(f"Table 13. Bringing a rover's map up to date after time out of contact, E52, means over {cnt(r.p6('E52', 'seeds'))} seeds: tile versions "
                    f"changed, bytes to synchronise and their share of a full resend, the hash-tree walk inside those bytes, the time until the hazard layer "
                    f"is current with hazards first and with the oldest change first at 16 and at 100&nbsp;kbit/s, the time until everything is current at "
                    f"16&nbsp;kbit/s, and the hazards the rover drove into because its copy was stale. The change rates are Assumed (Section 4.2).",
                    ["Out of contact", "Tile versions changed", "Bytes to sync", "Share of a full resend", "Hash-tree walk (B)",
                     "Hazards current at 16 kbit/s, hazards first / oldest first (s)", "At 100 kbit/s (s)", "Everything current at 16 kbit/s",
                     "Hazards hit during the outage", "Hit after contact at 16 kbit/s, hazards first / oldest first"], rows, cls="wide")
    T6["E52_map"] = (table_e52, "E52", "Table 13, map synchronisation after an outage")

    # --- D. the stack and its security (3.8, 4.2, 5.11, 5.12): E53 (sizes, bit rate), E54 (store and forward, lost link) ----
    def e53row(geometry, auth, hz, rovers):
        return r.row6("E53", geometry=geometry, auth=auth, position_hz=hz, rovers=rovers)

    def lrip_sizes():
        """The byte layout of an authenticated message, from the codec's size table in the E53 file."""
        sz = r.p6("E53", "sizes")
        P = sz["POSITION"]
        hdr = int(P["unsecured"]) - int(P["payload"])
        check(all(int(v["unsecured"]) - int(v["payload"]) == hdr for v in sz.values()), "every message carries the same packet and protocol headers (3.8)")
        mac8 = {int(v["mac8"]) - int(v["unsecured"]) for v in sz.values()}
        mac16 = {int(v["mac16"]) - int(v["unsecured"]) for v in sz.values()}
        sg = {int(v["signed"]) - int(v["unsecured"]) for v in sz.values()}
        check(mac8 == {14} and mac16 == {22} and sg == {70} and hdr == 14,
              "authentication adds a 6-byte security header and an 8- or 16-byte code, or a 64-byte signature, to every message (3.8, Proposition 7)")
        signed = sorted(k for k, v in sz.items() if int(v["default"]) == int(v["signed"]))
        check(signed == ["CAP_MANIFEST", "RESERVE_GRANT", "TASK_AWARD"], "awards, grants and manifests are the messages signed by default (3.8)")
        return {"sz": sz, "hdr": hdr, "n": len(sz), "signed": signed}

    SCHEMA = os.path.join(ROOT, "lunarsim", "schemas", "lrip-v0.1.json")

    def lrip_position():
        """What version 0.1 of the protocol serialises in a POSITION message and in its header (lunarsim/schemas/lrip-v0.1.json, the file
        the codec lunarsim/atc/lrip/codec.py packs from). Finding M4 and decision B3: no frame, datum or time-scale identifier and no
        covariance is in the packet; the design requires them and version 0.2 adds them (task B-100)."""
        _need(SCHEMA, "the LRIP v0.1 schema")
        sc = json.load(open(SCHEMA, encoding="utf-8"))
        pos = [m_ for m_ in sc["messages"] if m_["name"] == "POSITION"]
        check(str(sc["version"]) == "0.1" and len(pos) == 1 and len(sc["messages"]) == 15, "the schema is LRIP version 0.1 with 15 message types, one of them POSITION (3.8)")
        f = {x[0]: x for x in pos[0]["fields"]}
        bits = sum(int(x[2]) for x in pos[0]["fields"])
        check(list(f) == ["e", "n", "h", "heading", "speed", "sigma_h", "nav_src", "moving", "spare"] and bits == 104,
              "POSITION v0.1 is east, north, height, heading, speed, one scalar uncertainty, a source code, a moving flag and spare bits: 104 bits (3.8)")
        hdr = sc["framing"]["lrip_header"]
        names = " ".join(str(x[0]) for x in pos[0]["fields"]) + " " + " ".join(str(x[0]) for x in hdr["fields"])      # field names: the height's note says "site datum"
        check(not re.search(r"frame|datum|cov|scale", names, re.I) and [x[0] for x in hdr["fields"]] == ["ver_major", "ver_minor", "msg_type", "sender_id", "t_valid"],
              "neither POSITION v0.1 nor the protocol header has a frame, datum or time-scale identifier or a covariance (3.5 to 3.8)")
        check("site time base" in str(hdr["t_valid_note"]) and abs(_fin(hdr["t_valid_unit_s"]) - 0.1) < 1e-12 and int(hdr["bytes"]) == 8,
              "the 8-byte protocol header carries one time stamp in tenths of a second on the site time base (3.6, 3.8)")
        check(bits // 8 == int(r.p6("E53", "sizes", "POSITION", "payload")), "the schema's POSITION is the 13 B the codec's size table counts (3.8)")
        return {"f": f, "bits": bits, "hdr": hdr, "p1": int(sc["framing"]["proximity1_frame_bytes"]), "rate": str(pos[0]["default_rate"]), "n": len(sc["messages"])}

    def traffic_types():
        """Which of the protocol's message types the traffic model of E53 sends (per_rover_at_1hz), and which it leaves out."""
        sz = r.p6("E53", "sizes")
        sent = list(r.p6("E53", "per_rover_at_1hz", "on"))
        out = [k for k in sz if k not in sent]
        check(set(sent) <= set(sz) and len(sent) == 11 and len(sz) == 15 and
              sorted(out) == ["CAP_MANIFEST", "CAP_QUERY", "MAP_NOTICE", "TASK_ANNOUNCE"],
              "the traffic model sends 11 of the 15 message types; the task announcement, the capability query and manifest and the map notice are not in it (3.8, 5.11)")
        return sent, out

    SCHEMA2 = os.path.join(ROOT, "lunarsim", "schemas", "lrip-v0.2.json")
    _v2: Dict[str, Any] = {}

    def lrip_v02():
        """Version 0.2 of the protocol (task B-100): lunarsim/schemas/lrip-v0.2.json and results/E53_bitrate.json block `lrip_v02`. What a
        position carries in v0.2: a 95 % bound in the report itself; frame, datum and time scale declared per sender in HELLO or in the
        signed manifest and bound to the security context; no covariance. The rates are a calculation on the traffic model of E53."""
        if _v2:
            return _v2
        _need(SCHEMA2, "the LRIP v0.2 schema")
        sc = json.load(open(SCHEMA2, encoding="utf-8"))
        pos = next(m_ for m_ in sc["messages"] if m_["name"] == "POSITION")
        hel = next(m_ for m_ in sc["messages"] if m_["name"] == "HELLO")
        pf = {x[0]: x for x in pos["fields"]}
        hf = {x[0]: x for x in hel["fields"]}
        check(str(sc["version"]) == "0.2" and "u95_code" in pf and int(pf["u95_code"][2]) == 6 and pf["u95_code"][-1].get("was") == "spare" and
              sum(int(x[2]) for x in pos["fields"]) == 104 and not any(re.search(r"cov|frame|datum|scale", k) for k in pf),
              "POSITION v0.2 carries a 95 % bound in the six bits that were spare, keeps its 104 bits, and carries no covariance and no identifier (3.8)")
        note = str(pf["u95_code"][4])
        check(all(x in note for x in ("0.05 m x 2^(code/4)", "coded upward", "62: above 1.95 km", "63 unknown")), "the 95 % bound of v0.2 is 0.05 m x 2^(code/4), coded upward, with codes for 'above 1.95 km' and 'unknown' (3.8)")
        check([int(hf[k][2]) for k in ("frame_id", "datum_id", "time_scale")] == [6, 6, 4] and "refused" in str(sc["declaration_rule"]) and
              "key epoch" in str(sc["declaration_rule"]) and "signed capability manifest" in str(sc["declaration_rule"]),
              "HELLO v0.2 declares frame, datum and time scale, and a POSITION without a declaration under the sender's current key epoch is refused (3.8)")
        b = r.p6("E53", "lrip_v02")
        s1, s2 = r.p6("E53", "sizes"), b["sizes_v0.2"]
        moved = sorted(k for k in s1 if s1[k] != s2[k])
        check(moved == ["CAP_MANIFEST", "HELLO"] and set(b["sizes_moved"]) == {"HELLO"} and int(s2["POSITION"]["mac8"]) == int(s1["POSITION"]["mac8"]),
              "from v0.1 to v0.2 only the HELLO and the manifest change size; the position report does not (3.8)")
        on2, off2 = (sum(_fin(v["bps"]) for v in b["per_rover_at_1hz"][k].values()) for k in ("on", "off"))
        h2 = b["h13_check_v02"]
        check(abs(on2 * 20 / 1000.0 - _fin(h2["at_1hz_kbps_p95"])) < 0.01 and bool(h2["same_verdict_as_v0.1"]) and _fin(h2["at_1hz_kbps_p95"]) <= 16.0 < _fin(h2["at_10hz_kbps_p95"]),
              "with v0.2 the busiest link carries 20 times the per-rover rate and H13's two comparisons come out as with v0.1 (5.11)")
        fr = b["framing_row"]
        check("+12 B" in str(fr["note"]) and bool(fr["fleet_auth_1hz_20"]["fits_nb_scheduled_p95"]) and not bool(fr["fleet_auth_1hz_20"]["fits_nb_slotted_aloha_p95"]) and
              _fin(fr["airtime_1hz_scheduled_kbps"]) <= 16.0,
              "in Proximity-1 frames the v0.2 traffic of 20 rovers at 1 Hz fits the narrow channel when scheduled and not on slotted random access (5.11)")
        cov = b["traffic_model_coverage"]
        check(len(cov["sent_by_E53"]) == 11 and sorted(cov["not_sent_by_E53"]) == ["CAP_MANIFEST", "CAP_QUERY", "MAP_NOTICE", "TASK_ANNOUNCE"], "the traffic model sends 11 of the 15 types under v0.2 too")
        _v2.update({"b": b, "pf": pf, "hf": hf, "hel": hel, "s2": s2, "on": on2, "off": off2, "h": h2, "fr": fr, "p1": int(sc["framing"]["proximity1_frame_bytes"]),
                    "interval": _fin(hel["declaration_interval_s"]), "mb": b["manifest_bytes_v0.2"]["small_rover"], "vec": int(b["conformance_vectors_v0.2"])})
        return _v2

    def sec_layout():
        s = lrip_sizes()
        sz = s["sz"]
        mb = r.p6("E53", "manifest_bytes")
        ps = lrip_position()
        f = ps["f"]
        sent, out = traffic_types()
        v2 = lrip_v02()
        P = sz["POSITION"]
        res = lambda k, u: f"{int(f[k][2])} bits at {num(f[k][3], 2 if _fin(f[k][3]) < 0.1 else 1)}{NB}{u}"
        hf, s2 = v2["hf"], v2["s2"]
        return (f"The messages are implemented and serialised, unlike the assumed layouts of Section 3.4: {words(s['n']) if s['n'] < 10 else cnt(s['n'])} message "
                f"types in one schema with two encodings, bit-packed for the narrow channel and CBOR for the broadband one, with real AES-CMAC and Ed25519 "
                f"and {cnt(r.p6('E53', 'conformance_vectors'))} conformance vectors per version in the repository; the vectors test the codec, not a radio. "
                f"There are two versions, and what each puts on the wire has to be said exactly. In both, a position report holds east and north in the "
                f"site grid ({res('e', 'm')} each), the height above the site datum ({res('h', 'm')}), heading ({int(f['heading'][2])} bits), speed "
                f"({int(f['speed'][2])} bits), one scalar one-sigma horizontal uncertainty ({res('sigma_h', 'm')}), a {int(f['nav_src'][2])}-bit code for "
                f"the navigation source and a moving flag, and the {cnt(ps['hdr']['bytes'])}-byte protocol header adds the version, the message type, the "
                f"sender and one time stamp in tenths of a second. Version 0.1, with which the experiments of this paper were first run, stops there: "
                f"{int(f['spare'][2])} bits of the report are spare, and nothing in any message names the frame, the datum or the time scale. Version 0.2 "
                f"closes that gap in two ways. The uncertainty travels in the report itself: the {int(v2['pf']['u95_code'][2])} bits that were spare carry a "
                f"95{PCT} horizontal bound on a logarithmic scale, 0.05{NB}m times 2 to the power of a quarter of the code, rounded upward so that the "
                f"decoded bound never understates, with one code for a bound above 1.95{NB}km and one for unknown. The frame, the datum and the time "
                f"scale do not travel in every report: each sender declares them, in {int(hf['frame_id'][2])}, {int(hf['datum_id'][2])} and "
                f"{int(hf['time_scale'][2])} bits, in a heartbeat sent at least every {unit(v2['interval'], 's', 0)} and in its signed manifest, and the "
                f"declaration is bound to the security context: it holds for the key epoch under which it was authenticated, and a receiver refuses a "
                f"position report whose sender has no declaration under its current key epoch, as it refuses an unauthenticated one. A covariance is "
                f"not carried in either version: the report has a one-sigma value and, in version 0.2, a 95{PCT} bound, both scalars. The report is "
                f"{cnt(ps['bits'])} bits, {cnt(P['payload'])}&nbsp;B, in both versions: {cnt(P['unsecured'])}&nbsp;B with its packet and protocol headers, "
                f"{cnt(P['mac8'])}&nbsp;B with the security header and the 8-byte code, and {cnt(P['mac16'])}&nbsp;B with the 16-byte code; these are packet "
                f"sizes before link framing and coding, and a Proximity-1 frame adds {cnt(ps['p1'])}&nbsp;B [94]. A status report is "
                f"{cnt(sz['STATUS']['mac8'])}&nbsp;B, a bid {cnt(sz['TASK_BID']['mac8'])}&nbsp;B, a reservation request {cnt(sz['RESERVE_REQ']['mac8'])}&nbsp;B, and the "
                f"signed award and grant {cnt(sz['TASK_AWARD']['signed'])} and {cnt(sz['RESERVE_GRANT']['signed'])}&nbsp;B. Two sizes differ between the versions: "
                f"the heartbeat, {cnt(sz['HELLO']['mac8'])}&nbsp;B in version 0.1 and {cnt(s2['HELLO']['mac8'])}&nbsp;B with the declaration, and the capability "
                f"manifest of the small rover, {cnt(mb['small_rover']['compact_cbor'])} and {cnt(v2['mb']['compact_cbor'])}&nbsp;B in compact binary "
                f"({cnt(mb['small_rover']['json'])} and {cnt(v2['mb']['json'])}&nbsp;B as JSON). The identifiers are the site's own registry (Assumed; not "
                f"registered with any agency). The traffic model of Section 4.2 sends {cnt(len(sent))} of the {cnt(s['n'])} types: the three reports, the "
                f"alert, the bid, the award and the task state, the three reservation messages and the heartbeat; the task announcement, the capability "
                f"query and manifest and the map notice are not in it.")
    fill("P3-SEC-LAYOUT-SENTENCE", sec_layout, "E53 sizes")
    def limit_lrip():
        """Section 7: what the protocol carries and what it does not, after version 0.2 (finding M4, decision B3; task B-100)."""
        v2 = lrip_v02()
        sent, out = traffic_types()
        sz = r.p6("E53", "sizes")
        return (f"The design of Sections 3.5 to 3.7 asked for a frame, a datum, a time scale and a covariance with every position. Version 0.2 gives "
                f"the first three by a declaration per sender, bound to its key epoch, not by fields in each report, and it gives a scalar 95{PCT} bound "
                f"where the design asked for a covariance; a receiver that needs the shape of the error does not get it. The identifiers are the site's "
                f"own registry and are registered nowhere. The experiments were run with version 0.1; the figures of version 0.2 are a calculation on the "
                f"same traffic model, which sends {cnt(len(sent))} of the {cnt(len(sz))} message types, and they are packet sizes: a Proximity-1 frame adds "
                f"{cnt(v2['p1'])}&nbsp;B a packet and coding more. The {cnt(v2['vec'])} conformance vectors of each version test the codec against itself; no "
                f"second implementation and no radio has read them.")
    fill("P3-LIMIT-LRIP-SENTENCE", limit_lrip, "E53, the schema")

    def limit_near():
        """Section 7: how much of the driving 'near the base' is, and what decides the clause (finding M5; B-101)."""
        st = e50_steps()
        rd, sw = referee_m5()
        rows = {x["k"]: x for x in rd["1"]["rows"]}
        return (f"The region in which ranging holds the position budget, two or more beacons in line of sight, covers {pc(st['near_share'], 0)} of driving "
                f"steps and was chosen after the results. In the simulation, on assumed ranging errors, the 95th percentile at today's fleet is "
                f"{unit(rows['c']['p95'], 'm', 1)} within a kilometre of the base and {unit(rows['e']['p95'], 'm', 1)} under the registered wording, "
                f"outside the budget in every seed. Inside the narrow region the result rests on the long-range ranging error, an assumption without "
                f"a lunar measurement: at {unit(max(sw['rad']), 'm', 0)} in place of {unit(PD['radio_sigma_m'], 'm', 0)} the percentile is "
                f"{unit(sw['rad'][10.0]['a']['in_p95_m_mean'], 'm', 1)}. The beacon survey error and the ultra-wideband reach were not swept"
                + ("" if "8" in rd else ", and the readings were not computed at eight times the fleet") + f". Inside the region {pc(st['near_over'], 1)} of the steps still exceed the budget.")
    fill("P3-LIMIT-NEAR-SENTENCE", limit_near, "E50, B-101")

    def lrip_v02_sentence():
        """5.11: the sizes and rates of version 0.2 beside those of version 0.1, with link framing as a separate figure (task B-100)."""
        v2 = lrip_v02()
        on1, off1 = e53row("fleet", "on", 1.0, 20), e53row("fleet", "off", 1.0, 20)
        h1, h2, fr = r.p6("E53", "h13"), v2["h"], v2["fr"]
        add1 = _fin(on1["per_rover_kbps"]) / _fin(off1["per_rover_kbps"]) - 1.0
        add2 = v2["on"] / v2["off"] - 1.0
        w = lambda x: "within" if _fin(x) <= 16.0 else "above"
        f20 = fr["fleet_auth_1hz_20"]
        return (f"The figures above are for version 0.1. With version 0.2 the report keeps its size and the only change in the traffic is the "
                f"heartbeat with its declaration, now sent at least every {unit(v2['interval'], 's', 0)}: a rover generates {num(v2['on'] / 8.0, 1)}&nbsp;B/s "
                f"in place of {num(_fin(on1['per_rover_kbps']) * 1000 / 8, 1)}, authentication adds {pc(add2, 0)} in place of {pc(add1, 0)}, and for 20 "
                f"rovers at 1&nbsp;Hz the busiest link carries {num(h2['at_1hz_kbps_p95'], 2)}{KBPS6} in place of {num(h1['at_1hz_kbps_p95'], 2)} and needs "
                f"{num(h2['airtime_1hz_scheduled_kbps'], 2)}{KBPS6} of a scheduled channel in place of {num(h1['airtime_1hz_scheduled_kbps'], 2)}, "
                f"{w(h2['airtime_1hz_scheduled_kbps'])} the target; at 10&nbsp;Hz it carries {num(h2['at_10hz_kbps_p95'], 1)}{KBPS6}. All of these are "
                f"packet sizes. With every packet in a Proximity-1 frame, {cnt(v2['p1'])}&nbsp;B more, the same 20 rovers offer "
                f"{num(f20['busiest_link_kbps_p95'], 2)}{KBPS6} and need {num(fr['airtime_1hz_scheduled_kbps'], 2)}{KBPS6} of a scheduled channel, "
                f"{w(fr['airtime_1hz_scheduled_kbps'])} the target, and {'do not fit' if not bool(f20['fits_nb_slotted_aloha_p95']) else 'fit'} it on slotted "
                f"random access; channel coding is not counted. The two comparisons of H13 come out the same under version 0.2. These are calculations "
                f"on a traffic model; the split by driving positions and the case with status and intent at 1&nbsp;Hz (Section 5.2) are given at the "
                f"sizes of version 0.2, and {e54_v02('clause')} (Section 5.12).")

    def e53_design():
        eta = r.p6("E53", "eta")
        ch = r.p6("E53", "channels_kbps")
        check(abs(_fin(eta["scheduled"]) - 0.8) < 1e-9 and abs(_fin(eta["slotted_aloha"]) - math.exp(-1)) < 1e-9, "E53's access efficiencies are 0.8 and 1/e (4.2)")
        check(sorted(_fin(v) for v in ch.values()) == [16.0, 1000.0], "E53's two channels are 16 kbit/s and 1 Mbit/s (4.2)")
        rows = r.p6("E53", "rows")
        ns = sorted({int(x["rovers"]) for x in rows})
        hz = sorted({_fin(x["position_hz"]) for x in rows})
        check(ns == [5, 10, 20, 40, 80] and hz == [0.1, 1.0, 10.0] and {x["geometry"] for x in rows} == {"fleet", "spread"}, "E53's fleet sizes, rates and geometries (4.2)")
        st = e50_steps()
        ps = lrip_position()
        check("1 Hz moving, 0.1 Hz parked" in ps["rate"], "the protocol's default position rate is 1 Hz moving and 0.1 Hz parked (4.2)")
        return (f"E53 computes the traffic of the protocol from the serialised sizes of version 0.1. Each rover sends a position report at 0.1, 1 or "
                f"10&nbsp;Hz whether it moves or not (the protocol's own default is 1&nbsp;Hz moving and 0.1&nbsp;Hz parked), status and intent reports at "
                f"0.1&nbsp;Hz, and the market and reservation events at the rates E48 counted at today's fleet. Reports travel one hop; events are relayed "
                f"to the base. For 5, 10, 20, 40 and 80 rovers, {cnt(r.p6('E53', 'draws'))} draws place the rovers on the terrain mesh, every one with a "
                f"2.5&nbsp;m antenna although half of today's fleet carries 1.0&nbsp;m, in two geometries: at positions taken from the recorded trajectories "
                f"of E50's first seed with every vehicle-step equally likely, which is the registered geometry of H13, and uniformly over all route samples "
                f"(added after the first results, Section 4.6). In that trace {pc(st['parked_share_s1'], 1)} of the vehicle-steps are parked "
                f"({cnt(st['parked_s1'])} against {cnt(st['driving_s1'])} driving), so the registered geometry is a fleet standing at its sites. The outcome is the load on the busiest "
                f"link, the largest sum of what any one node hears, at the 95th percentile over the draws, with authentication on and off, against the "
                f"{num(min(_fin(v) for v in ch.values()), 0)}&nbsp;kbit/s target of Section 3.4 as load and as airtime at the access efficiencies of E48.")
    fill("P3-E53-DESIGN-SENTENCE", e53_design, "E53")

    def e53_results():
        pr = r.p6("E53", "per_rover_at_1hz")
        on, off = e53row("fleet", "on", 1.0, 20), e53row("fleet", "off", 1.0, 20)
        on10, off10 = e53row("fleet", "on", 10.0, 20), e53row("fleet", "off", 10.0, 20)
        bps = lambda d: sum(_fin(v["bps"]) for v in d.values())
        check(abs(bps(pr["on"]) / 1000.0 - _fin(on["per_rover_kbps"])) < 2e-3 and abs(bps(pr["off"]) / 1000.0 - _fin(off["per_rover_kbps"])) < 2e-3,
              "E53: the per-rover rate is the sum over message types of rate x size x 8 (5.11)")
        add = _fin(on["per_rover_kbps"]) / _fin(off["per_rover_kbps"]) - 1.0
        check(abs(_fin(on["busiest_link_kbps_p95"]) - _fin(on["one_hop_sum_kbps"])) < 0.01, "in the fleet geometry the busiest link carries the whole fleet's sum (5.11)")
        fits = [n for n in (5, 10, 20, 40, 80) if bool(e53row("fleet", "on", 1.0, n)["fits_nb_scheduled_p95"])]
        nofit = [n for n in (5, 10, 20, 40, 80) if n not in fits]
        check(fits == [5, 10, 20, 40, 80][:len(fits)], "E53: the fleet sizes that fit the scheduled channel are the smallest ones (5.11)")
        h = r.p6("E53", "h13")
        T = 16.0
        sched, alo = _fin(h["airtime_1hz_scheduled_kbps"]), _fin(h["airtime_1hz_slotted_aloha_kbps"])
        five10 = e53row("fleet", "on", 10.0, 5)
        sz = lrip_sizes()["sz"]
        pay = [int(sz[k]["payload"]) for k in ("POSITION", "STATUS", "INTENT")]
        sec_b = int(sz["POSITION"]["mac8"]) - int(sz["POSITION"]["unsecured"])
        return (f"At the sizes of version 0.1 and with authentication, a rover that reports its position once a second generates {num(_fin(on['per_rover_kbps']) * 1000 / 8, 1)}&nbsp;B/s, "
                f"{num(on['per_rover_kbps'], 3)}{KBPS6}, against {num(_fin(off['per_rover_kbps']) * 1000 / 8, 1)}&nbsp;B/s without it: the security header and "
                f"the code add {pc(add, 0)} to the bit rate, because they are {cnt(sec_b)}&nbsp;B on reports of {cnt(min(pay))} to {cnt(max(pay))}&nbsp;B of content. For 20 rovers in the fleet "
                f"geometry the busiest link carries {num(on['busiest_link_kbps_p95'], 2)}{KBPS6} at 1&nbsp;Hz with authentication and "
                f"{num(off['busiest_link_kbps_p95'], 2)} without, and {num(on10['busiest_link_kbps_p95'], 1)} and {num(off10['busiest_link_kbps_p95'], 1)}{KBPS6} "
                f"at 10&nbsp;Hz; that link carries the sum over the whole fleet, because the fleet works within one radio neighbourhood of the base. As airtime "
                f"the 1&nbsp;Hz traffic of 20 rovers needs {num(sched, 2)}{KBPS6} of a scheduled channel, {'within' if sched <= T else 'above'} the target, and "
                f"{num(alo, 2)} on slotted random access, {'within' if alo <= T else 'above'} it, the same verdicts as E48's event counts gave in Section 5.2. "
                + (f"On a scheduled channel the authenticated 1&nbsp;Hz traffic fits the target for up to {cnt(fits[-1])} rovers of the sizes run and not for "
                   f"{cnt(nofit[0])}; " if fits and nofit else "") +
                f"at 10&nbsp;Hz {cnt(five10['rovers'])} rovers already load the busiest link with {num(five10['busiest_link_kbps_p95'], 1)}{KBPS6} (Table 14).")
    fill("P3-E53-RESULTS-SENTENCE", e53_results, "E53")

    def h13_verdict():
        """5.11: H13 is a design calculation, not a test (finding M6; decisions A1 and B8; PREREG6 section 6): the busiest link carries
        the fleet's sum, sizes times rates, in every draw."""
        h = r.p6("E53", "h13")
        a1, a10 = _fin(h["at_1hz_kbps_p95"]), _fin(h["at_10hz_kbps_p95"])
        on = e53row("fleet", "on", 1.0, 20)
        check(abs(a1 - _fin(on["busiest_link_kbps_p95"])) < 1e-6 and abs(a10 - _fin(e53row("fleet", "on", 10.0, 20)["busiest_link_kbps_p95"])) < 1e-6,
              "H13 is computed on the fleet geometry, 20 rovers, authentication on (5.11)")
        c1, c2 = a1 <= 16.0, a10 > 16.0
        check(bool(h["supported"]) == (c1 and c2), "H13's flag follows from its two clauses (5.11)")
        per = _fin(on["per_rover_kbps"]) * 1000.0 / 8.0
        check(abs(20 * per * 8 / 1000.0 - a1) < 0.005 and abs(a1 - _fin(on["one_hop_sum_kbps"])) < 1e-6,
              "H13's load at 1 Hz is 20 rovers times the per-rover rate: the fleet's sum (5.11)")
        alo, sched = _fin(h["airtime_1hz_slotted_aloha_kbps"]), _fin(h["airtime_1hz_scheduled_kbps"])
        return (f"H13 of [67] says that with authentication on and 20 rovers the busiest link carries no more than 16{KBPS6} at 1&nbsp;Hz position reports "
                f"and more at 10&nbsp;Hz. It is not a test but a design calculation, as a dated entry of [67] records: in the registered geometry every "
                f"rover is in one radio neighbourhood, so the busiest link carries the fleet's sum in every draw, 20 &times; {num(per, 1)}&nbsp;B/s &times; 8 = "
                f"{num(a1, 2)}{KBPS6} at 1&nbsp;Hz and {num(a10, 1)}{KBPS6} at 10&nbsp;Hz, the product of the serialised sizes and the assumed rates that "
                f"Section 5.2 already gives. It could not have come out otherwise. Its comparison is of load with the target; as airtime, the comparison "
                f"that change 11 of [59] adopted, the 1&nbsp;Hz case is {'within' if alo <= 16.0 else 'above'} the target on slotted random access "
                f"({num(alo, 2)}{KBPS6}) and {'within' if sched <= 16.0 else 'above'} it on a channel the base schedules ({num(sched, 2)}{KBPS6}).")
    fill("P3-H13-VERDICT-SENTENCE", h13_verdict, "E53")

    def e53_spread(kind):
        ns = (5, 10, 20, 40, 80)
        sp = {n: e53row("spread", "on", 1.0, n) for n in ns}
        fl = {n: e53row("fleet", "on", 1.0, n) for n in ns}
        ratio = _fin(sp[20]["busiest_link_kbps_p95"]) / _fin(fl[20]["busiest_link_kbps_p95"])
        check(all(_fin(sp[n]["busiest_link_kbps_p95"]) < _fin(fl[n]["busiest_link_kbps_p95"]) and _fin(sp[n]["reachable_share"]) < _fin(fl[n]["reachable_share"])
                  and _fin(sp[n]["mean_hops_to_base"]) > _fin(fl[n]["mean_hops_to_base"]) for n in ns),
              "E53: spread over the routes, the busiest link carries less, more hops are needed and fewer rovers reach the base (3.3, 5.11)")
        check(all(_fin(sp[a]["reachable_share"]) < _fin(sp[b]["reachable_share"]) for a, b in zip(ns, ns[1:])), "E53 spread: the share reaching the base grows with the fleet (5.11)")
        fl_reach = (min(_fin(fl[n]["reachable_share"]) for n in ns), max(_fin(fl[n]["reachable_share"]) for n in ns))
        fl_hops = (min(_fin(fl[n]["mean_hops_to_base"]) for n in ns), max(_fin(fl[n]["mean_hops_to_base"]) for n in ns))
        sp_hops = (min(_fin(sp[n]["mean_hops_to_base"]) for n in ns), max(_fin(sp[n]["mean_hops_to_base"]) for n in ns))
        shares = ", ".join(pc(sp[n]["reachable_share"], 0) for n in ns[:-1]) + " and " + pc(sp[ns[-1]]["reachable_share"], 0)
        if kind == "results":
            return (f"With the rovers spread uniformly over the route samples (post hoc) the busiest link at 1&nbsp;Hz carries {num(sp[20]['busiest_link_kbps_p95'], 2)}{KBPS6} "
                    f"for 20 rovers, {pc(ratio, 0)} of the fleet geometry's, because each node hears fewer neighbours; the rovers that reach the base need "
                    f"{num(sp_hops[0], 1)} to {num(sp_hops[1], 1)} hops on average against {num(fl_hops[0], 2)} to {num(fl_hops[1], 2)}; and only {shares} of "
                    f"5, 10, 20, 40 and 80 rovers reach the base at all, against {pc(fl_reach[0], 0)} to {pc(fl_reach[1], 0)} in the fleet geometry.")
        return (f"E53 measures the other case directly (Section 5.11): with 20 rovers spread uniformly over the route samples the rovers that reach the base "
                f"need {num(sp[20]['mean_hops_to_base'], 1)} hops on average, the busiest link carries {pc(ratio, 0)} of the load it carries when the fleet "
                f"works near the base, and only {pc(sp[20]['reachable_share'], 0)} of the rovers reach the base at all")
    fill("P3-E53-SPREAD-SENTENCE", lambda: e53_spread("results"), "E53 spread geometry")
    fill("P3-E53-SPREAD-CLAUSE", lambda: e53_spread("clause"), "E53 spread geometry")

    def table_e53():
        rows = []
        for geo in ("fleet", "spread"):
            for auth in ("on", "off"):
                for hz in (0.1, 1.0, 10.0):
                    x = {n: e53row(geo, auth, hz, n) for n in (5, 10, 20, 40, 80)}
                    rows.append([{"fleet": "Fleet (registered)", "spread": "Spread (post hoc)"}[geo], cap1(auth), f"{hz:g}", num(_fin(x[5]["per_rover_kbps"]) * 1000 / 8, 1)]
                                + [num(x[n]["busiest_link_kbps_p95"], 2 if _fin(x[n]["busiest_link_kbps_p95"]) < 100 else 0) for n in (5, 10, 20, 40, 80)]
                                + [pc(x[20]["reachable_share"], 0), num(x[20]["mean_hops_to_base"], 2)])
        lrip_v02()
        path = os.path.join(RES, "E53_table_v02.csv")
        _need(path, "the v0.2 table of E53")
        c2 = pd.read_csv(path)
        for framing, label in (("lrip", "Fleet, version 0.2"), ("proximity1", "Fleet, version 0.2 in Proximity-1 frames")):
            g = c2[(c2["framing"] == framing) & (c2["geometry"] == "fleet") & (c2["auth"] == "on") & (np.isclose(c2["position_hz"], 1.0))].set_index("rovers")
            check(list(g.index) == [5, 10, 20, 40, 80], f"E53's v0.2 table has the five fleet sizes for {framing}")
            rows.append([label, "On", "1", num(_fin(g["per_rover_kbps"][5]) * 1000 / 8, 1)]
                        + [num(g["busiest_link_kbps_p95"][n], 2) for n in (5, 10, 20, 40, 80)]
                        + [pc(g["reachable_share"][20], 0), num(g["mean_hops_to_base"][20], 2)])
        check(abs(_fin(c2[(c2["framing"] == "lrip") & (c2["geometry"] == "fleet") & (c2["auth"] == "on") & (np.isclose(c2["position_hz"], 1.0)) & (c2["rovers"] == 20)]["busiest_link_kbps_p95"].iloc[0])
                  - _fin(r.p6("E53", "lrip_v02", "h13_check_v02", "at_1hz_kbps_p95"))) < 1e-6, "E53's v0.2 table and its v0.2 block agree at 20 rovers and 1 Hz")
        return _tab(f"Table 14. Traffic of the interaction protocol, E53: bytes a second per rover and the load on the busiest link (kbit/s, 95th percentile over "
                    f"{cnt(r.p6('E53', 'draws'))} draws of rover positions) for 5 to 80 rovers, by geometry, authentication and position-report rate, with the "
                    f"share of rovers that reach the base and their mean hop count at 20 rovers. Authentication is the 8-byte code on every message and a "
                    f"signature on awards and grants. The first rows are version 0.1 of the protocol, packet sizes before link framing; the last two rows "
                    f"give version 0.2 and version 0.2 with every packet in a Proximity-1 frame. A calculation on a traffic model, not a radio measurement.",
                    ["Geometry", "Authentication", "Position rate (Hz)", "Per rover (B/s)", "5 rovers", "10", "20", "40", "80", "Reach the base (20 rovers)",
                     "Mean hops (20 rovers)"], rows, cls="wide")
    T6["E53_bitrate"] = (table_e53, "E53", "Table 14, traffic of the interaction protocol")

    PROTO = {"drop_retry": "drop-and-retry", "sf": "store-and-forward with custody", "sf_ll": "store-and-forward with the lost-link rule"}

    def e54row(loss, proto):
        return r.row6("E54", loss=loss, protocol=proto)

    def dtn_model():
        p = r.p6("E54", "parameters")
        check(abs(_fin(p["t_hold_s"]) - 600) < 1e-9 and abs(_fin(p["t_rdv_s"]) - 3600) < 1e-9 and abs(_fin(p["lease_s"]) - 3600) < 1e-9 and
              abs(_fin(p["return_speed_factor"]) - 0.5) < 1e-9, "the lost-link ladder's times are 10 min and 1 h, the return is at half speed, the lease is 1 h (3.8)")
        return (f"In the model of E54 a custodian retransmits after {unit(p['custody_timer_s'], 's', 0)} while the link lasts and holds the bundle, in a store of "
                f"{unit(_fin(p['queue_bytes']) / 1e6, 'MB', 0)}, while there is no path; a vehicle unheard for {unit(_fin(p['t_hold_s']) / 60, 'min', 0)} retraces "
                f"its path at half speed to the last point where it had a link; a segment whose holder is still unheard {unit(p['grace_s'], 's', 0)} after "
                f"the reservation's timeout is marked unconfirmed; and the silent vehicle's task returns to the auction when its "
                f"{unit(_fin(p['lease_s']) / 3600, 'h', 0)} lease expires (Assumed values, [68]). E54 was run with the rule as first written, in which the base "
                f"released the reservation at that moment; the release is withdrawn, as above, and Section 5.12 reports what E54's counts mean under the rule "
                f"as it now stands.")
    fill("P3-DTN-MODEL-SENTENCE", dtn_model, "E54 parameters")

    def e54_design():
        p = r.p6("E54", "parameters")
        losses = sorted({_fin(x["loss"]) for x in r.p6("E54", "rows")})
        bo = r.p6("E54", "blackout_days")
        check(losses == [0.1, 0.25, 0.4] and {x["protocol"] for x in r.p6("E54", "rows")} - {"sf_ll_pre_review"} == set(PROTO),
              "E54 runs three protocols at three loss levels, with the return rule of before the code review kept as a variant (4.2)")
        check("its lifetime runs past the end" in str(r.p6("E54", "superseded_2026-11-14_b120_b", "reason")) or "lifetime runs past" in str(r.p6("E54", "outcome_definitions")),
              "E54 calls a message censored only when its lifetime runs past the window's end (4.2)")
        aj = r.p6("E54", "awards_and_jobs")
        check(abs(_fin(aj["awards_per_seed"]) - _fin(aj["jobs_per_seed"]) - _fin(aj["team_jobs_per_seed"])) < 1e-6 and int(aj["vehicles_per_job_max"]) == 2 and
              abs(_fin(aj["awards_per_seed"]) * len(r.p6("E54", "seeds")) - int(e54row(0.25, "drop_retry")["award_n"])) < 1e-6,
              "E54's awards a seed are its jobs plus its two-vehicle team jobs, one award per vehicle (4.2)")
        check(str(p["return_rule"]) == "papers" and "retraces at half speed the path it drove since the loss" in str(r.p6("E54", "lost_link_rule")),
              "E54's lost-link return is the rule the papers state (3.8, 4.2)")
        check(abs((_fin(bo[1]) - _fin(bo[0])) - 14.0) < 1e-9, "E54 imposes a 14-day Earth blackout (4.2)")
        return (f"E54 is a simulation at the level of messages over the recorded month of E50, not a new run of the logistics engine: inside the engine a lost "
                f"message is retried and the regimes know at once that it failed, so a lost job cannot occur there. The contact plan is the terrain mesh along "
                f"the recorded trajectories, per 60&nbsp;s step. The traffic is the month's real events: a task award from the base to each job's vehicle, which "
                f"lives for the {unit(_fin(p['lease_s']) / 3600, 'h', 0)} lease, and whose expiry is counted as a lost job (hypothetically: in the recorded run every "
                f"job was done); a reservation grant, which lives 60&nbsp;s; a "
                f"task-state report at the job's end; a daily ledger bundle of {unit(_fin(r.p6('E54', 'ledger_bytes')) / 1000, 'kB', 0)} to Earth with a lifetime of "
                f"14 days; and a status report every {unit(p['status_period_s'], 's', 0)}, from which the age of the base's information is taken. Earth is "
                f"blacked out from day {num(bo[0], 0)} to day {num(bo[1], 0)} on top of the month's own direct-to-Earth gaps. Three protocols carry the traffic: "
                f"drop-and-retry end to end, a try every {unit(p['retry_s'], 's', 0)} and at most {words(p['max_tries'])} tries, so that it gives up after "
                f"{unit((int(p['max_tries']) - 1) * _fin(p['retry_s']) / 60.0, 'min', 0)} on an award that lives an hour (the retry budget is our choice; the "
                f"registration does not fix it; Section 5.12 gives a sweep of it, run after the results were known); store-and-forward hop by hop with "
                f"custody; and store-and-forward with the lost-link ladder of Section 3.8. The per-hop loss is {', '.join(num(x, 2) for x in losses[:-1])} or "
                f"{num(losses[-1], 2)}, on {cnt(len(r.p6('E54', 'seeds')))} seeds with {num(aj['jobs_per_seed'], 1)} jobs, {num(aj['awards_per_seed'], 1)} awards (one "
                f"for each vehicle of a job; {num(aj['team_jobs_per_seed'], 2)} jobs a seed are team jobs of two vehicles) and "
                f"{num(r.p6('E54', 'reservations_per_seed'), 0)} single-lane reservations a seed. A message is lost when its lifetime ends undelivered inside "
                f"the window, and censored, not lost, when it is undelivered at the window's end and its lifetime runs past that end. Two things are approximations: the return of a silent vehicle is "
                f"applied to the contact plan and is not driven in the engine, and a returning vehicle is given a direct link to the base, which is optimistic "
                f"when its last link went through another vehicle. E54 also counts the reservations whose holder has no path to the base "
                f"{unit(p['grace_s'], 's', 0)} after the reservation's timeout: the base cannot confirm that the segment is clear, although in the replay every "
                f"vehicle left on schedule. Under the rule as it now stands these are the segments marked unconfirmed. The run itself used the rule as first "
                f"written, which released them and so recorded none by construction; that zero is not a result. The registration also lists the wait of "
                f"urgent cargo among E54's outcomes; a replay of messages does not move cargo, so that outcome is not reported. The ledger is simulated separately over 61 days, so that every bundle created in the month resolves, with "
                f"lifetimes of 14 days, 30 days, and the longest Earth outage plus one day.")
    fill("P3-E54-DESIGN-SENTENCE", e54_design, "E54")

    def e54_results():
        L = 0.25
        d, s, l = (e54row(L, k) for k in ("drop_retry", "sf", "sf_ll"))
        check(int(d["award_n"]) == int(s["award_n"]) == int(l["award_n"]), "E54: the three protocols carry the same awards (5.12)")
        check(int(d["grant_lost"]) > 100 * max(1, int(s["grant_lost"])) and int(l["award_lost"]) <= int(s["award_lost"]) <= int(d["award_lost"]),
              "E54: custody removes nearly all lost grants, and lost awards fall from drop-and-retry to custody to the lost-link rule (5.12)")
        check(abs(_fin(s["aoi_mean_s"]) - _fin(d["aoi_mean_s"])) < 0.01 * _fin(d["aoi_mean_s"]) and _fin(l["aoi_mean_s"]) < 0.05 * _fin(s["aoi_mean_s"]),
              "E54: custody alone does not change the age of the base's information; the lost-link rule cuts it (5.12)")
        check(int(l["stuck_reservations"]) == 0 and int(d["stuck_reservations"]) == int(s["stuck_reservations"]) > 0, "E54: reservations stay stuck without the lost-link rule only (5.12)")
        lo, hi = e54row(0.1, "drop_retry"), e54row(0.4, "drop_retry")
        ret, days = _fin(r.p6("E54", "lost_link_returns_per_seed")), 31.0
        sp = r.p6("E54", "superseded_2026-11-13_b118")          # the code-review block, by its explicit key: the file holds a second superseded block since 14 Nov
        sp2 = r.p6("E54", "superseded_2026-11-14_b120_b")
        MOVED = {"ledger_earth_lost", "ledger_earth_lost_share", "ledger_earth_censored"}
        SF = {"sf", "sf_ll", "sf_ll_pre_review"}

        def same_rows(new_rows, old_rows):
            """Every field of every row equal, a field missing on either side fails, except the three ledger fields of the store-and-forward rows."""
            if len(new_rows) != len(old_rows):
                return False
            ko = {(x["loss"], x["protocol"]): x for x in old_rows}
            if len(ko) != len(old_rows):
                return False
            for x in new_rows:
                y = ko.get((x["loss"], x["protocol"]))
                if y is None or set(x) != set(y):
                    return False
                for f in x:
                    if f in MOVED and x["protocol"] in SF:
                        continue
                    if x[f] != y[f]:
                        return False
                if x["protocol"] in SF and not (x["ledger_earth_lost"] != y["ledger_earth_lost"] and
                                                int(x["ledger_earth_lost"]) + int(x["ledger_earth_censored"]) == int(x["ledger_earth_lost_incl_censored"])):
                    return False
            return True
        cur = r.p6("E54", "lrip_v02")
        check(same_rows(r.p6("E54", "rows"), sp2["rows"]) and r.p6("E54", "h14") == sp2["h14"] and r.p6("E54", "h14_variants") == sp2["h14_variants"],
              "E54 rerun of 14 Nov, main rows: every field of every row equals the superseded block except the Earth ledger's expired count, share and "
              "censored count in the store-and-forward rows, with no field missing on either side; H14 and its variants are equal (5.12)")
        check(set(cur["rows"]) == set(sp2["lrip_v02"]["rows"]) and all(same_rows(cur["rows"][v], sp2["lrip_v02"]["rows"][v]) for v in cur["rows"]) and
              cur["h14"] == sp2["lrip_v02"]["h14"] and cur["verdicts"] == sp2["lrip_v02"]["verdicts"],
              "E54 rerun of 14 Nov, the three size sets of protocol version 0.2: the same comparison holds, and H14 and the verdicts are equal (5.12)")
        ol = next(x for x in sp["rows"] if abs(_fin(x["loss"]) - L) < 1e-9 and x["protocol"] == "sf_ll")
        check(all(int(next(x for x in sp["rows"] if abs(_fin(x["loss"]) - L) < 1e-9 and x["protocol"] == k)["award_lost"]) == int(e54row(L, k)["award_lost"])
                  for k in ("drop_retry", "sf", "sf_ll")) and sp["h14"]["difference_sf_ll_minus_drop_retry"] == r.p6("E54", "h14")["difference_sf_ll_minus_drop_retry"],
              "the code-review corrections of E54 changed no award loss and not H14's first clause (5.12)")
        pre = e54row(L, "sf_ll_pre_review")
        hv = r.p6("E54", "h14_variants")
        check(all(v["difference_sf_ll_minus_drop_retry"] == r.p6("E54", "h14")["difference_sf_ll_minus_drop_retry"] for v in hv.values() if isinstance(v, dict)) and sum(1 for v in hv.values() if isinstance(v, dict)) >= 2,
              "H14's first clause is the same with censored messages counted as lost and under the return rule of before the review (5.12)")
        check("until it is heard" in str(r.p6("E54", "stuck_definition")) and "UNCONFIRMED" in str(r.p6("E54", "stuck_definition")),
              "E54's count is of reservations whose release the base cannot confirm, not of vehicles still in a segment (5.12)")
        return (f"At a per-hop loss of {num(L, 2)}, drop-and-retry lost {cnt(d['award_lost'])} of {cnt(d['award_n'])} task awards "
                f"({cnt(lo['award_lost'])} at a loss of 0.10 and {cnt(hi['award_lost'])} at 0.40), store-and-forward with custody {cnt(s['award_lost'])} and, with the "
                f"lost-link rule, {cnt(l['award_lost'])}; the mean delay of an award was {dur(d['award_delay_mean_s'])}, {dur(s['award_delay_mean_s'])} and "
                f"{dur(l['award_delay_mean_s'])}. Of the reservation grants, which live 60&nbsp;s and so get one try under drop-and-retry, "
                f"{cnt(d['grant_lost'])} were lost ({pc(d['grant_lost_share'], 1)}), against {cnt(s['grant_lost'])} and {cnt(l['grant_lost'])}; a lost grant is a "
                f"vehicle that stops before a single-lane segment. Of {cnt(d['task_state_n'])} task-state reports, {cnt(d['task_state_lost'])}, "
                f"{cnt(s['task_state_lost'])} and {cnt(l['task_state_lost'])} were lost, and custody alone delivered them after {dur(s['task_state_delay_mean_s'])} on "
                f"average, the time a report waits in a vehicle that ended its job out of reach, against {dur(l['task_state_delay_mean_s'])} with the lost-link "
                f"rule. The base's information about a vehicle was {dur(s['aoi_mean_s'])} old on average without the rule, and up to "
                f"{dur(s['aoi_worst_vehicle_s'])} for the worst vehicle, with either transport; with the rule it was {dur(l['aoi_mean_s'])} and "
                f"{dur(l['aoi_worst_vehicle_s'])}. E54 counted {cnt(d['stuck_reservations'])} reservations whose holder had no path to the base "
                f"{unit(r.p6('E54', 'parameters', 'grace_s'), 's', 0)} after the reservation's timeout, {cnt(d['stuck_hours'])} hours in all until the holder was "
                f"heard, about {pc(int(d['stuck_reservations']) / (_fin(r.p6('E54', 'reservations_per_seed')) * len(r.p6('E54', 'seeds'))), 0)} of the "
                f"single-lane reservations, because those segments lie on routes the mast does not see. Under the rule as it now stands these are the "
                f"segments marked unconfirmed, which another vehicle may enter only at caution speed. The run with the ladder recorded none, because the "
                f"rule as first written released them at that moment; that zero followed from the rule's definition and is withdrawn as a result, the "
                f"count with the ladder in force was not recomputed, and the cost of crossing an unconfirmed segment at caution speed is not priced. The "
                f"ladder sent a silent vehicle back along its path {num(ret, 1)} times a seed, about {num(ret / days, 1)} a day for the "
                f"{words(len(r.fleet()))} vehicles; the replay does not drive those returns, each at half speed, and no delay figure contains them (Table 15). "
                f"The values of this paragraph were corrected after a code review on 13 November 2026 (a bundle could be counted as delivered after its "
                f"lifetime; the age of information had a floor of half a step; the return rule in the code was not the one stated in Section 3.8): "
                f"before, the age of information with the rule was {dur(ol['aoi_mean_s'])} ({dur(ol['aoi_worst_vehicle_s'])} for the worst vehicle), the "
                f"task-state reports took {dur(ol['task_state_delay_mean_s'])} with {cnt(ol['task_state_lost'])} lost, {cnt(ol['grant_lost'])} grants were lost "
                f"with the rule, and the ladder made {num(sp['lost_link_returns_per_seed'], 1)} returns a seed. The award losses did not change, and under "
                f"the earlier return rule, kept as a variant, the age of information is {dur(pre['aoi_mean_s'])}.")
    fill("P3-E54-RESULTS-SENTENCE", e54_results, "E54")

    def e54_v02(kind="sentence"):
        """5.12 (task B-111, results/E54_dtn.json block `lrip_v02`): the E54 replay repeated at the packet sizes of protocol version 0.2 and
        in Proximity-1 frames. No value and no verdict changes, and the build stops if that ever stops being true. It is a property of the
        replay's message set (its three message types have the same size in both versions), not a test of version 0.2."""
        b = r.p6("E54", "lrip_v02")
        rows, sz = b["rows"], b["sizes_bytes"]
        same = lambda a, c: all(a[k] == c[k] for k in a if not k.endswith("_bytes"))
        check(list(b["values_moved_vs_v01"]) == [] and all(len(rows[v]) == len(rows["v0.1"]) and all(same(x, y) for x, y in zip(rows["v0.1"], rows[v]))
                                                         for v in ("v0.2", "v0.2_proximity1")),
              "the E54 replay at version 0.2 sizes and in Proximity-1 frames gives the version 0.1 value in every row (5.12)")
        pub = [x for x in r.p6("E54", "rows") if x["protocol"] != "sf_ll_pre_review"]
        check(all(b["reproduction_of_main_table_v01"].values()) and len(pub) == len(rows["v0.1"]) and
              all(all(x[k] == y[k] for k in y if k in x) for x, y in zip(rows["v0.1"], pub)),
              "the version 0.1 rows of the rerun reproduce the published rows of E54 (5.12)")
        check(all(b["h14"][v] == b["h14"]["v0.1"] for v in b["h14"]) and
              all(b["h14"][v]["difference_sf_ll_minus_drop_retry"] == r.p6("E54", "h14")["difference_sf_ll_minus_drop_retry"] for v in b["h14"]),
              "H14's first clause comes out the same at version 0.2 sizes and in Proximity-1 frames (5.12)")
        check(all(bool(v["h14_supported"]) and bool(v["same_as_v0.1"]) for v in b["verdicts"].values()), "no verdict of E54 changes at version 0.2 sizes (5.12)")
        check(sz["v0.2"] == sz["v0.1"] and sorted(sz["v0.1"]) == ["RESERVE_GRANT", "TASK_AWARD", "TASK_STATE"] and
              all(int(sz["v0.2_proximity1"][k]) - int(sz["v0.2"][k]) == lrip_position()["p1"] for k in sz["v0.2"]),
              "the replay sends awards, grants and task states, whose sizes version 0.2 does not change; a Proximity-1 frame adds its bytes to each (5.12)")
        q = _fin(r.p6("E54", "parameters", "queue_bytes"))
        worst = max(_fin(v) for v in b["max_queue_bytes_bound"].values())
        check(worst < 0.01 * q, "every message of a seed held at once is under 1 % of a node's store, so no size reaches the store limit (5.12)")
        if kind == "clause":
            return (f"the replay was repeated at the packet sizes of version 0.2 and in Proximity-1 frames, and no value and no verdict changed, which "
                    f"is a property of its message set and not a test of version 0.2")
        return (f"The replay was repeated at the packet sizes of protocol version 0.2 and with every packet in a Proximity-1 frame, on the same "
                f"{cnt(len(b['seeds']))} seeds: no value of Table 15 and no verdict changes. That is a property of the replay's message set, not a test of "
                f"version 0.2. The replay sends task awards, reservation grants and task states, whose sizes version 0.2 does not change "
                f"({cnt(sz['v0.2']['TASK_AWARD'])}, {cnt(sz['v0.2']['RESERVE_GRANT'])} and {cnt(sz['v0.2']['TASK_STATE'])}&nbsp;B; "
                f"{cnt(sz['v0.2_proximity1']['TASK_AWARD'])}, {cnt(sz['v0.2_proximity1']['RESERVE_GRANT'])} and {cnt(sz['v0.2_proximity1']['TASK_STATE'])}&nbsp;B "
                f"framed), and in the replay a size counts only against a node's store of {unit(q / 1e6, 'MB', 0)}: with every message of a seed held at "
                f"once the store would hold {unit(worst / 1e6, 'MB', 2)} at most. Losses and delays come from the contact plan and the per-hop loss, "
                f"which do not depend on a message's size.")
    fill("P3-E54-V02-SENTENCE", e54_v02, "E54 lrip_v02 (B-111)")
    fill("P3-E54-V02-LIMIT", lambda: cap1(e54_v02("clause")) + "; it says nothing about how version 0.2's reports and heartbeats fare on a lossy link.", "E54 lrip_v02 (B-111)")
    fill("P3-LRIP-V02-SENTENCE", lrip_v02_sentence, "E53 lrip_v02 (B-100)")

    P6_FILES["E54R"], P6_TASK["E54R"] = "E54_retry_budget.json", "B-117 (d), (e1)"
    P6_FILES["E52S"], P6_TASK["E52S"] = "E52_sweep.json", "B-117 (j2)"

    def e54_retry(kind="sentence"):
        """5.12, 7 (control B-117 e1, results/E54_retry_budget.json): H14's first clause at twelve retry budgets of the comparator. Run after
        the results were known and not pre-registered; a simulation on the same recorded months."""
        b = r.p6("E54R", "h14_by_budget_loss_0.25")
        pb = r.p6("E54R", "published_budget")
        rows = r.p6("E54R", "rows")
        check(list(r.p6("E54R", "seeds")) == list(r.p6("E54", "seeds")) and bool(pb["reproduces_E54_drop_retry_cells"]) and
              int(pb["max_tries"]) == int(r.p6("E54", "parameters", "max_tries")) and abs(_fin(pb["retry_s"]) - _fin(r.p6("E54", "parameters", "retry_s"))) < 1e-9,
              "the retry sweep runs E54's seeds and its published budget is E54's (5.12)")
        for x in rows:
            if x["published_budget"]:
                y = e54row(_fin(x["loss"]), "drop_retry")
                check(all(x[f] == y[f] for f in ("award_n", "award_lost", "grant_lost", "task_state_lost", "ledger_earth_lost")),
                      f"the retry sweep's published budget reproduces E54's drop-and-retry cells at loss {x['loss']} (5.12)")
        check(sum(1 for x in rows if x["published_budget"]) == 3, "the published budget is in the sweep at the three loss levels (5.12)")
        ok = [k for k, v in b.items() if _fin(v["difference_sf_ll_minus_drop_retry"]["ci"][1]) < 0]
        bad = [k for k in b if k not in ok]
        check(all(bool(b[k]["clause_1_ci_below_0"]) == (k in ok) for k in b), "the sweep's flags follow from the paired intervals (5.12)")
        check(all(_fin(v["lost_jobs_sf_ll_per_seed"]) == 0 for v in b.values()), "with the lost-link rule no award expires at any budget of the sweep (5.12)")
        ns = len(r.p6("E54R", "seeds"))

        def parse(k):
            m_ = re.match(r"(\d+) tries, (\d+) s", k)
            return int(m_.group(1)), int(m_.group(2))
        tries = sorted({parse(k)[0] for k in b})
        gaps = sorted({parse(k)[1] for k in b})
        lost = lambda k: int(round(_fin(b[k]["lost_jobs_drop_retry_per_seed"]) * ns))
        if not bad:
            fail_txt = "The clause holds at every budget"
        else:
            bt = sorted({parse(k)[0] for k in bad})
            bg = sorted(parse(k)[1] for k in bad)
            check(len(bt) == 1 and len({lost(k) for k in bad}) == 1 and all(_fin(b[k]["difference_sf_ll_minus_drop_retry"]["ci"][1]) == 0 for k in bad),
                  "the budgets at which H14's first clause fails share one number of tries and one count of lost awards, and their interval ends at zero (5.12)")
            c0 = b[bad[0]]["difference_sf_ll_minus_drop_retry"]["ci"]
            fail_txt = (f"The clause holds at {cnt(len(ok))} of the {cnt(len(b))} budgets and fails at {words(len(bad))}, {cnt(bt[0])} tries every "
                        f"{' or '.join(cnt(g) for g in bg)}&nbsp;s, where drop-and-retry loses {words(lost(bad[0]))} awards in {cnt(ns)} seeds and the rule none, "
                        f"so the paired interval, {ci(c0[0], c0[1], 2)}, reaches zero")
        if kind == "short":
            return (f"a later sweep finds the clause at {cnt(len(ok))} of {cnt(len(b))} budgets" if bad else f"a later sweep finds the clause at all {cnt(len(b))} budgets")
        if kind == "clause":
            return (f"a sweep of {cnt(len(b))} retry budgets, run after the results were known and not pre-registered, " +
                    (f"finds H14's first clause at {cnt(len(ok))} of them and not at {cnt(bt[0])} tries every {' or '.join(cnt(g) for g in bg)}&nbsp;s" if bad else
                     "finds H14's first clause at every one"))
        worst = max(b, key=lambda k: _fin(b[k]["lost_jobs_drop_retry_per_seed"]))
        return (f"How much of this is the comparator's budget was then checked in a sweep, run after the results were known and not pre-registered: "
                f"drop-and-retry with {', '.join(cnt(t) for t in tries[:-1])} or {cnt(tries[-1])} tries, {', '.join(cnt(g) for g in gaps[:-1])} or "
                f"{cnt(gaps[-1])}&nbsp;s apart, on the same {cnt(ns)} seeds at a loss of 0.25, each against the unchanged store-and-forward with the "
                f"lost-link rule. The published budget reproduces E54's drop-and-retry cells exactly. {fail_txt}. Drop-and-retry loses "
                f"{num(b[worst]['lost_jobs_drop_retry_per_seed'], 1)} jobs a seed with a single try and "
                f"{num(min(_fin(v['lost_jobs_drop_retry_per_seed']) for v in b.values()), 2)} at its best budget: the clause is a statement about a "
                f"comparator that gives up early, and a comparator that keeps trying loses almost nothing in this replay.")
    fill("P3-E54-RETRY-SWEEP-SENTENCE", e54_retry, "E54 retry budgets (B-117 e1)")
    fill("P3-E54-RETRY-LIMIT", lambda: cap1(e54_retry("clause")) + ".", "E54 retry budgets (B-117 e1)")

    def e52_sweep(kind="sentence"):
        """5.10, 7 (control B-117 j2, results/E52_sweep.json): E52's assumed change rates swept one at a time. Run after the fact; a
        calculation on the map's bookkeeping, as E52 is."""
        sw, df = r.p6("E52S", "sweeps"), r.p6("E52S", "defaults")
        n = sum(len(v) for v in sw.values())
        allx = [x for v in sw.values() for x in v.values()]
        h = r.p6("E52", "h12")
        dflt = {p: next(x for k, x in sw[p].items() if abs(float(k) - _fin(df[p])) < 1e-9) for p in sw}
        check(bool(r.p6("E52S", "default_reproduces_E52_map_h12")) and all(abs(_fin(x["share_of_full_resend_24h"]) - _fin(h["share_of_full_resend_24h"])) < 1e-5 for x in dflt.values()) and
              int(r.p6("E52S", "seeds")) == int(r.p6("E52", "seeds")), "the default setting of the sweep reproduces E52's share after 24 h, on E52's seeds (5.10)")
        check(bool(r.p6("E52S", "h12_supported_in_every_setting")) and all(bool(x["h12_supported"]) for x in allx), "H12's two statements hold in every setting of the sweep (5.10)")
        tl = sw["TILES_PER_DAY"]
        tk = sorted(tl, key=float)
        sh = [_fin(tl[k]["share_of_full_resend_24h"]) for k in tk]
        check(all(a < b_ for a, b_ in zip(sh, sh[1:])), "the byte share after 24 h rises with the tile change rate (5.10)")
        d0 = _fin(h["share_of_full_resend_24h"])
        others = [_fin(x["share_of_full_resend_24h"]) for p in sw if p != "TILES_PER_DAY" for x in sw[p].values()]
        check(max(abs(v - d0) for v in others) < 0.01 * d0, "hazard, keep-out and road-edge rates move the byte share by under 1 % of its value (5.10)")
        hz = sw["HAZARD_PER_DAY"]
        hk = sorted(hz, key=float)
        hits = [_fin(hz[k]["hits_during_outage"]["24 h"]) for k in hk]
        check(all(a < b_ for a, b_ in zip(hits, hits[1:])), "stale-map hits during a one-day outage rise with the hazard rate (5.10)")
        full = 3 * int(r.p6("E52", "route_tiles"))
        top = _fin(tl[tk[-1]]["tiles_changed_24h"])
        check(top <= full + 1e-9, "no more tiles change in a day than the routes have in three layers (5.10)")
        levels = ("levels off at the highest rate, where every route tile of the three layers has changed" if abs(top - full) < 0.5 else
                  "has not levelled off inside the swept range")
        if kind == "clause":
            return (f"a sweep of {cnt(n)} settings, run after the fact, puts the share after a day at {pc(sh[0], 2)} to {pc(sh[-1], 1)} of a full resend over "
                    f"{cnt(float(tk[0]))} to {cnt(float(tk[-1]))} changed tiles a day")
        return (f"The change rates were then swept one at a time, after the fact and outside the registration: {cnt(n)} settings on the same "
                f"{cnt(r.p6('E52S', 'seeds'))} seeds, of which the default reproduces the result above. The share of a full resend after a day is "
                f"{', '.join(pc(v, 2) for v in sh[:-1])} and {pc(sh[-1], 2)} at {', '.join(cnt(float(k)) for k in tk[:-1])} and {cnt(float(tk[-1]))} route "
                f"tiles changed a day; it follows the tile change rate and {levels}. The rates of hazards, "
                f"keep-out zones and road-edge changes move it by under a hundredth of its value. The stale-map hits during a day out of contact "
                f"follow the hazard rate: {', '.join(num(v, 2) for v in hits[:-1])} and {num(hits[-1], 2)} at "
                f"{', '.join(num(float(k), 1 if float(k) % 1 else 0) for k in hk[:-1])} and {num(float(hk[-1]), 0)} new hazards a day. Hazards first is current sooner than "
                f"oldest first in every setting, as it must be. The sweep gives the range of the calculation; it does not make the rates less assumed.")
    fill("P3-E52-SWEEP-SENTENCE", e52_sweep, "E52 sweep (B-117 j2)")
    fill("P3-E52-SWEEP-LIMIT", lambda: cap1(e52_sweep("clause")) + ".", "E52 sweep (B-117 j2)")

    def h14_verdict():
        """5.12: H14 clause by clause. The first is tested; the second is not testable as written (decision B1 of the referee round;
        PREREG6 section 6): the zero followed from the rule's definition, and the rule that produced it is withdrawn."""
        h = r.p6("E54", "h14")
        dd = h["difference_sf_ll_minus_drop_retry"]
        c1 = _fin(dd["ci"][1]) < 0
        c2 = int(h["stuck_reservations_sf_ll"]) == 0
        check(bool(h["supported"]) == (c1 and c2) and "loss 0.25" in str(h["rule"]), "H14's flag follows from its two clauses at loss 0.25 (5.12)")
        check("holds BY RULE, not by measurement" in str(h["clause_2_basis"]) and bool(h["clause_1_measured"]), "the results file says H14's second clause holds by rule, not by measurement (5.12)")
        d, s_, l = (e54row(0.25, k) for k in ("drop_retry", "sf", "sf_ll"))
        check(abs(_fin(h["lost_jobs_drop_retry_per_seed"]["mean"]) * len(r.p6("E54", "seeds")) - int(d["award_lost"])) < 1e-6,
              "H14's lost jobs per seed are the expired awards of the table (5.12)")
        check(_fin(d["award_lost_share"]) < 0.01, "lost jobs are rare under drop-and-retry at loss 0.25 (5.12)")
        own = int(s_["award_lost"]) - int(l["award_lost"])
        return (f"H14 of [67], at a message loss of 0.25 with a 14-day Earth blackout, has two clauses. That store-and-forward with the lost-link rule "
                f"loses fewer jobs than drop-and-retry is {'supported' if c1 else 'not supported'}: {num(h['lost_jobs_sf_ll_per_seed']['mean'], 2)} against "
                f"{num(h['lost_jobs_drop_retry_per_seed']['mean'], 2)} {ci(*h['lost_jobs_drop_retry_per_seed']['ci'], 2)} lost jobs a seed, a paired difference "
                f"of {num(dd['mean'], 2)} {ci(dd['ci'][0], dd['ci'][1], 2)}. The size of that difference is the comparator's: {cnt(d['award_lost'])} awards of "
                f"{cnt(d['award_n'])} expired under a retry budget we chose (swept below), custody alone lost {cnt(s_['award_lost'])} and the ladder "
                f"{'none' if int(l['award_lost']) == 0 else cnt(l['award_lost'])}, so the ladder's own contribution is {words(own)} award{'s' if own != 1 else ''} in "
                f"{cnt(len(r.p6('E54', 'seeds')))} months, with a returning vehicle given a direct link. That the rule leaves no reservation stuck past its "
                f"timeout is not testable as written, as a dated entry of [67] records: the zero in the run followed from the definition of the rule as "
                f"first written, which released a silent vehicle's reservation, and that release is unsafe if the vehicle is disabled inside the "
                f"segment. In the words of the results file, the clause holds by rule, not by measurement, and only the first clause is measured. The "
                f"rule now marks the segment unconfirmed, and what E54 gives for it is the count above. The first clause gives the same difference with "
                f"censored messages counted as lost and under the return rule the code had before the review.")
    fill("P3-H14-VERDICT-SENTENCE", h14_verdict, "E54")

    def e54_ledger(kind):
        rows = r.p6("E54L", "rows")
        down = _fin(r.p6("E54L", "longest_earth_down_d"))

        def one(life, proto, loss=0.25):
            g = [x for x in rows if abs(_fin(x["lifetime_d"]) - life) < 0.006 and x["protocol"] == proto and abs(_fin(x["loss"]) - loss) < 1e-9]
            if len(g) != 1:
                raise KeyError(f"E54 ledger row {life} d {proto}: {len(g)} rows")
            return g[0]
        lifes = sorted({round(_fin(x["lifetime_d"]), 2) for x in rows})
        check(len(lifes) == 3 and abs(lifes[0] - 14.0) < 1e-9 and abs(lifes[1] - (round(down, 2) + 1.0)) < 0.011 and abs(lifes[2] - 30.0) < 1e-9,
              "the ledger lifetimes are 14 days, the longest Earth outage plus one day, and 30 days (5.12)")
        s14, s25, s30 = (one(x, "sf") for x in lifes)
        check(int(s14["lost"]) > 0 and int(s25["lost"]) == 0 and int(s30["lost"]) == 0 and lifes[0] < down < lifes[1],
              "the design rule: custody loses ledger bundles when their lifetime is shorter than the longest Earth outage and none when it is longer (5.12, 6.3)")
        dr = [one(x, "drop_retry") for x in lifes]
        check(len({int(x["lost"]) for x in dr}) == 1 and all(len({int(x["lost"]) for x in rows if x["protocol"] == "sf" and abs(_fin(x["lifetime_d"]) - lf) < 0.006}) == 1
                                                              for lf in lifes), "the ledger's losses do not depend on the lifetime under drop-and-retry, nor on the loss level under custody (5.12)")
        ns = len(r.p6("E54", "seeds"))
        per_seed, lost_seed = int(s14["bundles"]) // ns, int(s14["lost"]) // ns
        check(int(s14["bundles"]) == per_seed * ns and int(s14["lost"]) == lost_seed * ns and per_seed == 31,
              "the ledger's lost bundles are the same days in every seed: one bundle a day of a 31-day month (5.12)")
        up_plain = _fin(r.s48("revision", "two_ray_in_the_mesh", "e40_month", "base_dte_share"))
        up_black = _fin(r.p6("E54", "earth_up_share"))
        bo = r.p6("E54", "blackout_days")
        check(up_black < up_plain, "the imposed blackout lowers the share of the month with Earth in view (5.12)")
        if kind == "numbers":
            return {"lost": lost_seed, "per_seed": per_seed, "life": lifes[0], "down": down}
        if kind == "results":
            return (f"The ledger to Earth is a calendar calculation, not a sample of {cnt(ns)} seeds. One bundle is made a day, {cnt(per_seed)} in the month. "
                    f"The longest stretch without Earth in the simulated period is {num(down, 1)} days, the imposed blackout laid over the month's own "
                    f"direct-to-Earth gaps: Earth is in view of the base for {pc(up_plain, 1)} of that month without the blackout and {pc(up_black, 1)} with it. "
                    f"A bundle that lives {num(lifes[0], 0)} days cannot outlast that gap, so with store-and-forward {cnt(lost_seed)} of the {cnt(per_seed)} "
                    f"bundles ({pc(s14['lost_share'], 0)}) expire, the same {cnt(lost_seed)} in every seed and at every loss level; with a lifetime of "
                    f"{num(lifes[1], 1)} days or of {num(lifes[2], 0)} days {'none' if int(s25['lost']) == 0 else cnt(s25['lost'])} does, with a mean delay of "
                    f"{num(s30['delay_mean_d'], 1)} days and a longest of {num(s30['delay_max_d'], 1)}. Drop-and-retry loses {pc(dr[0]['lost_share'], 0)} whatever "
                    f"the lifetime, because its {words(r.p6('E54', 'parameters', 'max_tries'))} tries are over within minutes. The blackout was placed on days "
                    f"{num(bo[0], 0)} to {num(bo[1], 0)} of the window by the experiment's design and was not moved; where it falls against the month's own gaps "
                    f"decides the {num(down, 1)} days, and with them the count.")
        return (f"a ledger bundle that lives {num(lifes[0], 0)} days does not outlast an Earth outage of {num(down, 1)} days, so {cnt(lost_seed)} of the month's "
                f"{cnt(per_seed)} daily bundles expire with store-and-forward and none with a lifetime of {num(lifes[1], 1)} days, a calculation from the calendar")
    fill("P3-E54-LEDGER-SENTENCE", lambda: e54_ledger("results"), "E54 ledger lifetimes")
    fill("P3-E54-LEDGER-CLAUSE", lambda: e54_ledger("clause"), "E54 ledger lifetimes")

    def table_e54():
        rows = []
        for loss in (0.1, 0.25, 0.4):
            for k in ("drop_retry", "sf", "sf_ll"):
                x = e54row(loss, k)
                rows.append([num(loss, 2), cap1(PROTO[k]), f"{cnt(x['award_lost'])} of {cnt(x['award_n'])}", dur(x["award_delay_mean_s"]),
                             f"{cnt(x['grant_lost'])} ({pc(x['grant_lost_share'], 1 if _fin(x['grant_lost_share']) >= 0.001 else 2)})",
                             f"{cnt(x['task_state_lost'])}; {dur(x['task_state_delay_mean_s'])}", f"{dur(x['aoi_mean_s'])}; {dur(x['aoi_worst_vehicle_s'])}",
                             ("not computed (the run released them)" if k == "sf_ll" else f"{cnt(x['stuck_reservations'])}; {cnt(x['stuck_hours'])}")])
        return _tab(f"Table 15. Store-and-forward and the lost-link rule, E54, summed over {cnt(len(r.p6('E54', 'seeds')))} seeds of the recorded month: task awards "
                    f"lost (an expired award is counted as a lost job; in the recorded run every job was done) and their mean delay, reservation grants lost, "
                    f"task-state reports lost and their mean delay, the age of the base's information about a vehicle (mean; worst vehicle), and the "
                    f"reservations whose holder had no path to the base 60&nbsp;s after the timeout, with the hours until it was heard: the segments that the "
                    f"lost-link rule marks unconfirmed. A message-level simulation. The run with the ladder used the rule as first written, which released "
                    f"those reservations, so it holds no count for that row.",
                    ["Per-hop loss", "Protocol", "Awards lost", "Award delay", "Grants lost", "Task states lost; mean delay", "Age of information: mean; worst vehicle",
                     "Segments unconfirmed; hours"], rows, cls="wide")
    T6["E54_dtn"] = (table_e54, "E54", "Table 15, store-and-forward and the lost-link rule")
    def e55_auth():
        """5.11 and Proposition 7: forged codes accepted against 2^-t, replays accepted under the counter and the freshness window."""
        fz, rp = r.p6("E55", "auth", "forgery"), r.p6("E55", "auth", "replay")
        bits = []
        for t in ("8", "16"):
            x = fz[t]
            exp = int(x["attempts"]) * 2.0 ** -int(t)
            check(abs(exp - _fin(x["expected"])) < 1e-6 and abs(int(x["accepted"]) - exp) <= 2.0 * math.sqrt(exp),
                  f"Proposition 7: forgeries accepted at {t} bits are within two standard deviations of attempts x 2^-t")
            bits.append(f"{cnt(x['accepted'])} of {cnt(x['attempts'])} forged messages passed a code truncated to {t} bits, where 2<sup>&minus;{t}</sup> predicts "
                        f"{num(exp, 0 if exp >= 100 else 1)}")
        x64 = fz["64"]
        year = 10.0 * 365.25 * 86400.0
        check(abs(_fin(x64["per_attempt"]) - 2.0 ** -64) < 1e-30 and abs(_fin(x64["year_at_10_per_s_union_bound"]) - year * 2.0 ** -64) < 1e-13,
              "Proposition 7: the 64-bit code's forgery probability is 2^-64 per attempt and q x 2^-64 over a year of ten attempts a second")
        tot = sum(int(v["replays"]) for v in rp.values())
        acc = sum(int(v["replays_accepted"]) for v in rp.values())
        check(acc == 0 and all(int(v["accepted_missed_original"]) == 0 for v in rp.values()), "no replayed message was accepted in E55 (5.11, Proposition 7)")
        per = " and ".join(f"{cnt(v['replays'])} at a loss of {num(float(k), 2)}" for k, v in sorted(rp.items(), key=lambda kv: float(kv[0])))
        desc, rec = str(r.p6("E55", "replay_trial_description")), r.p6("E55", "replay_recent")
        rr = sorted(rec["loss"].items(), key=lambda kv: float(kv[0]))
        acc_r = sum(int(v["replays_accepted"]) for _, v in rr)
        in_win = sum(int(v["accepted_missed_original_inside_window"]) for _, v in rr)
        check("drawn from the whole recorded log" in desc and "about 1 %" in desc and "after the code review of 13 Nov 2026" in str(rec["added"]) and
              "last 60 s" in str(rec["setup"]), "the first replay trial draws from the whole log (about 1 % inside the window); the second, added after the code review, replays recent messages (5.11)")
        check(acc_r == in_win and all(int(v["accepted_other"]) == 0 for _, v in rr),
              "every replay accepted in the recent-replay trial went to a receiver that had missed the original and was inside the window (5.11, Proposition 7)")
        return (f"The acceptance of forged messages was measured with the real AES-CMAC truncated to a short code, because the 8-byte code cannot be tried "
                f"often enough: " + "; ".join(bits) + f". For the 64-bit code of the narrow channel the same law gives {e10(2.0 ** -64, 1)} per attempt and "
                f"{e10(year * 2.0 ** -64, 1)} for ten attempts a second over a year (formula, not a trial). Two replay trials were run against receivers "
                f"that keep the per-sender counter and the 10&nbsp;s freshness window. In the first, {cnt(tot)} replays, {per}, "
                f"{'none was' if acc == 0 else cnt(acc) + ' were'} accepted; but each replayed message was drawn at random from the whole ten-minute log "
                f"and stamped 0 to 60&nbsp;s later, so it was usually minutes old, only about one in a hundred fell inside the window, and the zero says "
                f"little about the window. A second trial, added after a code review on 13 November 2026, replays messages sent in the last 60&nbsp;s: "
                + " and ".join(f"{'none' if int(v['replays_accepted']) == 0 else cnt(v['replays_accepted'])} of {cnt(v['replays'])} "
                               f"{'was' if int(v['replays_accepted']) <= 1 else 'were'} accepted at a loss of {num(float(k), 2)}" for k, v in rr) +
                f"; every accepted copy went to a receiver that had missed the original and was still inside the window ({cnt(in_win)} of {cnt(acc_r)}). "
                f"That is the one replay the rule admits: the receiver then learns a true state that is at most one window old.")
    fill("P3-E55-AUTH-SENTENCE", e55_auth, "E55 authentication")

    def e55_consensus():
        cells = [c for c in r.p6("E55", "consensus", "cells") if int(c["F"]) == 1 and int(c["f"]) <= 1]
        rng = {}
        for geo in ("fleet", "spread"):
            v = [_fin(c["degree_condition_share"]) for c in cells if c["geometry"] == geo]
            if not v:
                raise Pending(f"E55 has no consensus cell for the {geo} geometry")
            rng[geo] = (min(v), max(v))
        check(rng["fleet"][1] < 0.5 and rng["spread"][1] < 0.5, "on the terrain mesh the condition that every honest rover hears three others holds in under half the draws (5.11)")
        both = lambda a: pc(a[0], 0) if abs(a[0] - a[1]) < 5e-4 else f"{pc(a[0], 0)} to {pc(a[1], 0)}"
        rb = r.p6("E55", "h16", "robust_evidence_by_basis")
        check(bool(rb["exact_2F1_robust_N_le_8"]["runs_robust_all_safe"]) and int(rb["exact_2F1_robust_N_le_8"]["runs_robust"]) < int(rb["degree_condition_only_N_gt_8"]["runs_robust"]),
              "H16's exactly robust evidence is a few runs, fewer than those on the degree condition only (5.11)")
        return (f"For agreement by averaging, the trimmed-mean rule of Section 3.8 needs every honest rover to hear at least three others when one value may be "
                f"false. On the terrain mesh that held in {both(rng['fleet'])} of the draws at fleet positions and in {both(rng['spread'])} of the draws spread "
                f"over the routes, so the rule needs more links, relays or masts, or the base as the averaging node. The pre-registered test of the rule, H16 of "
                f"[67], is {'supported' if bool(r.p6('E55', 'h16', 'supported')) else 'not supported as stated'}, and the companion paper reports it [61]; "
                f"its evidence on meshes shown to be robust is {words(rb['exact_2F1_robust_N_le_8']['runs_robust'])} runs, and "
                f"{cnt(rb['degree_condition_only_N_gt_8']['runs_robust'])} more meet only a necessary condition.")
    fill("P3-E55-CONSENSUS-SENTENCE", e55_consensus, "E55 consensus")
    def e55_base_node(kind="sentence"):
        """The variant of E55 in which the base mast joins as an honest node: `consensus_with_base_mast.cells` against `consensus.cells`."""
        key = lambda c: (c["geometry"], int(c["N"]), int(c["f"]), int(c["F"]))
        # the cells in which the faulty rovers do not outnumber what the rule is set for (f <= F), the regime the rule is meant for
        with_ = {key(c): c for c in r.p6("E55", "consensus_with_base_mast", "cells") if c["geometry"] == "fleet" and int(c["f"]) <= int(c["F"])}
        without = {key(c): c for c in r.p6("E55", "consensus", "cells") if c["geometry"] == "fleet" and int(c["f"]) <= int(c["F"])}
        check(set(with_) == set(without) and all(bool(c.get("mast")) for c in with_.values()), "the base-node variant has the same fleet cells as E55's consensus part (5.11)")
        cw = [_fin(c["connected_share"]) for c in with_.values()]
        co = [_fin(c["connected_share"]) for c in without.values()]
        ag = [_fin(c["agreement_share"]) for c in with_.values()]
        check(all(_fin(with_[k]["connected_share"]) > _fin(without[k]["connected_share"]) for k in with_) and max(ag) < 0.5,
              "with the base mast as a node the fleet's graph is connected more often in every cell, and the honest rovers still agree in under half the runs (5.11)")
        over = lambda cells: [_fin(c["safe_share"]) for c in cells if c["geometry"] == "fleet" and int(c["f"]) == 2 and int(c["F"]) == 1]
        so, sw = over(r.p6("E55", "consensus", "cells")), over(r.p6("E55", "consensus_with_base_mast", "cells"))
        check(len(so) == len(sw) > 0 and max(sw) < min(so), "with two faulty rovers against a rule set for one, the mast lowers the share of runs that stay inside the honest range (5.11)")
        if kind == "basis":
            return (f"A variant of E55 with the base mast as an honest node: the graph connected in {pc(min(cw), 0)} to {pc(max(cw), 0)} of the runs, agreement in "
                    f"{pc(min(ag), 0)} to {pc(max(ag), 0)}")
        return (f"With the base mast added as an honest node (a variant run after the first results), and no more faulty rovers than the rule is set for, the "
                f"graph of the fleet geometry was connected in {pc(min(cw), 0)} to {pc(max(cw), 0)} of the runs, up from {pc(min(co), 0)} to {pc(max(co), 0)}, but the "
                f"honest rovers still reached agreement in only "
                f"{pc(min(ag), 0)} to {pc(max(ag), 0)}: agreement by averaging needs more than one relay. A well-connected node also spreads a false value: with "
                f"two faulty rovers against a rule set for one, the share of runs in which the honest rovers stayed inside the honest range fell from "
                f"{pc(min(so), 0)} to {pc(max(so), 0)} without the mast to {pc(min(sw), 0)} to {pc(max(sw), 0)} with it. In this design a shared estimate is "
                f"therefore computed at the base, which is then the node that must not be wrong, and the companion paper gives the details [61].")
    fill("P3-E55-BASE-NODE-SENTENCE", e55_base_node, "E55 variant: the base as the averaging node")
    def b97_parts():
        im = r.p6("B97", "artemis2", "images")
        bad = [x for x in im if str(x.get("fit", "")).startswith("unusable")]
        ok = [x for x in im if "range_err_rel" in x]
        att = [x for x in ok if "off_boresight_err_deg" in x]
        check(len(bad) + len(ok) == len(im) and len(ok) > 0, "every Artemis II frame is either fitted or named unusable (5.13)")
        check("not surface navigation" in str(r.p6("B97", "artemis2", "scope")), "the Artemis II check is limb navigation, not surface navigation (4.2, 5.13)")
        check(all(_fin(x["range_err_rel"]) > 0 for x in ok) and all(_fin(x["limb_px"]["r"]) < _fin(x["r_px_predicted"]) for x in ok),
              "every fitted disc is smaller than predicted and every range is biased high (5.13)")
        check(all(_fin(x["off_boresight_err_deg"]) < 0 for x in att) and bool(r.p6("B97", "artemis2", "pixel_axis_signs_consistent")),
              "the off-boresight angle is low in every frame with attitude, with one choice of pixel-axis signs for the set (5.13)")
        return im, bad, ok, att

    def b97_design():
        im, bad, ok, att = b97_parts()
        cam = r.p6("B97", "artemis2", "camera")
        g = r.p6("B97", "geometry")
        vis, el = _fin(g["orion_visible_share"]), [_fin(x) for x in g["orion_elevation_range_deg"]]
        check(el[0] <= el[1] and (vis == 0) == (el[1] < 0), "the spacecraft of the Earth-link check is below the base's horizon when its visible share is zero (4.2)")
        mon = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
        day = lambda x: f"{int(x['utc'][8:10])} {mon[int(x['utc'][5:7]) - 1]} {x['utc'][:4]}"
        return (f"Two checks use real data, and each is named for what it is. The first takes {words(len(im))} raw frames of the optical-navigation camera of "
                f"the Artemis&nbsp;II flyby, taken between {day(im[0])} and {day(im[-1])} [115], fits a circle to the bright limb of the disc in each (a threshold, a "
                f"robust circle fit, a least-squares refinement), and turns the disc's radius and centre into a range and a direction with the focal length of "
                f"the mission's instrument kernel, {cnt(cam['focal_px'])} pixels; the truth is the mission's own trajectory and attitude kernels [116]. Nothing is "
                f"calibrated, and the body in view is taken from the geometry, not from the archive label. This is limb navigation of a crewed spacecraft in "
                f"cislunar space, {cnt(round(min(_fin(x['range_km_spice']) for x in ok), -3))} to {cnt(round(max(_fin(x['range_km_spice']) for x in ok), -3))}&nbsp;km from "
                f"the body in view; it is not surface navigation and not rover data. It tests a camera model, the frames and the kernels of the kind "
                f"that position-from-image code would rest on; no result of this paper uses such code, because the terrain fix of E50 is a Gaussian "
                f"draw. The second check compares the Earth-link geometry code of [58], which the Earth "
                f"windows of this paper come from, with the SPICE toolkit's own routine for azimuth and elevation, for the spacecraft seen from the base at "
                f"{cnt(g['epochs'])} hourly epochs of its trajectory, and measures how far the base moves when the lunar frame kernel is left out (Section 3.7). "
                f"The spacecraft is below the base's horizon at {'every one' if vis == 0 else pc(1 - vis, 0)} of those epochs (elevation "
                f"{num(el[0], 2)}&deg; to {num(el[1], 2)}&deg;), so the check exercises the transformation to azimuth and elevation and not the terrain mask "
                f"that makes the Earth windows.")
    fill("P3-B97-DESIGN-SENTENCE", b97_design, "B-97")

    def b97_results():
        im, bad, ok, att = b97_parts()
        g = r.p6("B97", "geometry")
        rel = [_fin(x["range_err_rel"]) for x in ok]
        dr = [_fin(x["r_px_predicted"]) - _fin(x["limb_px"]["r"]) for x in ok]
        de = [_fin(x["direction_err_deg_best_signs"]) for x in att]
        ob = [-_fin(x["off_boresight_err_deg"]) for x in att]
        earth = [x for x in ok if x["target"] == "EARTH"]
        moon = [x for x in ok if x["target"] == "MOON"]
        near = [x for x in moon if _fin(x["range_km_spice"]) < 100000.0]
        if not near or not att:
            raise Pending("no Moon frame under 100,000 km, or no frame with attitude, in the B-97 file")
        rk = [_fin(x["range_err_km"]) for x in near]
        rng = [_fin(x["range_km_spice"]) for x in near]
        check(max(rel) < 0.02 and max(de) < 0.25, "the Artemis II range errors are about a percent and the direction errors a tenth or two of a degree (5.13)")
        allr = [_fin(x["range_km_spice"]) for x in ok]
        ct = [math.radians(min(de)) * min(rng), math.radians(max(de)) * max(rng)]
        check(_fin(g["max_abs_az_diff_deg"]) < 1e-12 and _fin(g["max_abs_el_diff_deg"]) < 1e-12, "the Earth-link geometry equals SPICE's routine to 1e-12 degree (5.13)")
        shift = _fin(g["moon_me_vs_iau_moon_shift_at_base_m"])
        check(0 < shift < 155.0, "leaving out the lunar frame kernel moves the base by less than the kernel's stated maximum of about 155 m (3.7, 5.13)")
        return (f"Artemis&nbsp;II optical navigation: of the {words(len(im))} frames, {words(len(bad))} {'is' if len(bad) == 1 else 'are'} saturated and "
                f"{words(len(ok))} usable; {words(len(att))} of those have attitude data and {words(len(ok) - len(att))} "
                f"{'gives' if len(ok) - len(att) == 1 else 'give'} a range only. The range from the fitted disc was {pc(min(rel), 2)} to {pc(max(rel), 2)} above the "
                f"kernels' range, and the direction within {num(min(de), 2)}&deg; to {num(max(de), 2)}&deg;. The errors are not random: the fitted radius was "
                f"{num(min(dr), 1)} to {num(max(dr), 1)} pixels small in every frame, which puts every range high, and the angle off the camera's axis was "
                f"{num(min(ob), 2)}&deg; to {num(max(ob), 2)}&deg; low in every frame, which may be the alignment of the camera frame (the mission's frame kernel "
                f"carries a warning about those angles). We report the bias as it is and do not fit it away; a correction fitted on other frames is the next "
                f"check. {cap1(words(len(earth)))} of the {words(len(ok))} discs are Earth, although every archive label names the Moon. For the "
                f"{words(len(near))} frames of the Moon at about {cnt(round(sum(rng) / len(rng), -3))}&nbsp;km the error is {cnt(min(rk))} to {cnt(max(rk))}&nbsp;km in "
                f"range and, at the direction errors above, about {sig(ct[0], 2)} to {sig(ct[1], 2)}&nbsp;km across the line of sight. That says the geometry chain "
                f"recovers a real body's range to about a percent and its direction to a tenth or two of a degree from one uncalibrated frame. It says "
                f"nothing about the {unit(PD['fix_sigma_lit_m'], 'm', 1)} of a rover's terrain fix (Table 4): that matches craters metres away against a map, a "
                f"different measurement at a different scale. Earth-link geometry: over {cnt(g['epochs'])} epochs the code's azimuth and elevation agreed with the "
                f"routine of the toolkit it is built on to "
                f"{e10(max(_fin(g['max_abs_az_diff_deg']), _fin(g['max_abs_el_diff_deg'])), 0)}&deg;; without the lunar frame kernel the base moved by "
                f"{unit(shift, 'm', 1)}, the silent error of Section 3.7 measured at our site.")
    fill("P3-B97-RESULTS-SENTENCE", b97_results, "B-97")

    # --- G. Appendix A: the worked example of each proposition, computed here and checked against the results files ----------
    def prop1():
        f = _fin(r.s48("classes", "LTV1", "link", "freq_ghz")) * 1e9
        lam = C_LIGHT / f
        d = _fin(r.s48("classes", "LTV1", "link", "worst_hop_m"))
        fs = 20 * math.log10(4 * math.pi * d / lam)
        out = []
        for c, who in (("LTV1", "two rover antennas"), ("SMALL", "two small-robot antennas")):
            lk = r.s48("classes", c, "link")
            h1, h2 = _fin(lk["antenna_m"]), _fin(lk["peer_antenna_m"])
            db, dc = 4 * h1 * h2 / lam, 4 * math.pi * h1 * h2 / lam
            l2 = 40 * math.log10(d) - 20 * math.log10(h1 * h2)
            hz = math.sqrt(2 * R_MOON * h1) + math.sqrt(2 * R_MOON * h2)
            check(abs(db - _fin(lk["breakpoint_m"])) < 0.06 and abs(l2 - _fin(lk["loss_db_worst_hop"])) < 0.06 and abs(hz - _fin(lk["mutual_horizon_m"])) < 0.06,
                  f"Proposition 1: breakpoint, loss at the worst hop and horizon of {who} equal the E48 file's")
            check(abs(20 * math.log10(4 * math.pi * dc / lam) - (40 * math.log10(dc) - 20 * math.log10(h1 * h2))) < 1e-9 and d > dc and l2 > fs,
                  f"Proposition 1: free-space loss equals the two-ray asymptote at 4 pi h1 h2 / lambda, and the worst hop lies beyond it ({who})")
            out.append(f"for {who} at {unit(h1, 'm', 1)} the breakpoint is at {unit(db, 'm', 1)}, the two laws meet at {unit(dc, 'm', 1)}, the loss at "
                       f"{unit(d / 1000.0, 'km', 0)} is {unit(l2, 'dB', 1)} and the mutual horizon is {unit(hz / 1000.0, 'km', 2)}, so that hop is "
                       f"{'beyond' if d > hz else 'within'} the horizon")
        m14 = referee_m14(r, check)
        worst = 10 * math.log10(math.sin(0.5) ** 2 / 0.25)
        check(abs(worst + 0.365) < 0.001, "Proposition 1: the asymptote differs from the exact two-ray factor by 0.36 dB at the meeting point")
        return (f"Worked example, the constants of E48: at {num(f / 1e9, 1)}&nbsp;GHz the wavelength is {unit(lam, 'm', 4)} and free-space loss at "
                f"{unit(d / 1000.0, 'km', 0)} is {unit(fs, 'dB', 1)}; " + "; ".join(out) + f". The build checks each of these against the link budget's file. "
                f"These hops do not meet the assumption that the ground is flat. The sphere's bulge at mid-path, d<sup>2</sup>/8R, is "
                f"{unit(m14['bulge']['LTV1'], 'm', 2)} of the rover antennas' {unit(m14['lk']['LTV1']['antenna_m'], 'm', 1)} at "
                f"{unit(_fin(m14['lk']['LTV1']['longest_hop_m']) / 1000.0, 'km', 0)}, and {unit(m14['bulge']['SMALL'], 'm', 2)}, the antenna height itself, at the "
                f"{unit(_fin(m14['lk']['SMALL']['longest_hop_m']) / 1000.0, 'km', 2)} horizon of two {unit(m14['lk']['SMALL']['antenna_m'], 'm', 1)} antennas, where "
                f"Table 7 evaluates the law for the small classes. A calculation of the loss there with the smooth-sphere method of "
                f"our own reference [20] (ITU-R P.526, section 3.2, checked against its text) gives {unit(m14['loss']['LTV1'][0], 'dB', 1)} against the {unit(m14['loss']['LTV1'][1], 'dB', 1)} above for the rover "
                f"antennas, and {unit(m14['loss']['SMALL'][0], 'dB', 1)} against {unit(m14['loss']['SMALL'][1], 'dB', 1)} for the small ones, 4 to 5&nbsp;dB "
                f"higher, which puts the flat-ground rates of Table 7 {num(m14['veh_ratio'][0], 1)} to {num(m14['veh_ratio'][1], 1)} times too high for the "
                f"vehicle hops and {num(m14['ratio']['BASE'], 1)} times for the mast ({m14['rates_txt']}; Table 7 has both columns). The internal referee of "
                f"this paper raised the point and the calculation confirms it; it is a calculation, not a measurement. Near the horizon the law is "
                f"therefore not conservative, and the 0.36&nbsp;dB of the derivation bounds its error against the flat two-ray model only.")
    fill("P3-PROP1-EXAMPLE", prop1, "E48 link")

    def prop2():
        rd = r.design(48, "radio")
        B, G, F, M = _fin(rd["bandwidth_mhz"]) * 1e6, _fin(rd["antenna_gain_dbi"]), _fin(rd["noise_figure_db"]), _fin(rd["implementation_margin_db"])
        N = -174.0 + 10 * math.log10(B) + F
        out, lt, sm = [], None, None
        for c, who in (("LTV1", "crew rover"), ("SMALL", "small rover")):
            lk = r.s48("classes", c, "link")
            pt = 10 * math.log10(_fin(lk["tx_power_w"]) * 1000.0)
            snr = pt + 2 * G - _fin(40 * math.log10(_fin(lk["worst_hop_m"])) - 20 * math.log10(_fin(lk["antenna_m"]) * _fin(lk["peer_antenna_m"]))) - N - M
            cap = B * math.log2(1 + 10 ** (snr / 10)) / 1000.0
            check(abs(cap - _fin(lk["worst_hop_kbps_if_visible"])) < 0.005 * cap + 0.06 and abs(snr - _fin(lk["snr_db_worst_hop"])) < 0.06,
                  f"Proposition 2: the {who}'s rate and signal-to-noise ratio at the worst hop equal the E48 file's")
            if c == "LTV1":
                lt = lk
            else:
                sm = lk
            out.append(f"the {who} at {unit(lk['tx_power_w'], 'W', 2)} ({num(pt, 1)}&nbsp;dBm) has a signal-to-noise ratio of {unit(snr, 'dB', 1, sign=True)} after "
                       f"the margin and a rate of {num(cap, 0 if cap >= 100 else 1)}{KBPS6}" + ("" if not bool(lk["beyond_horizon_at_worst_hop"]) else
                                                                                           " if its two antennas could see each other, which by Proposition 1 they cannot"))
        return (f"Worked example, the constants of E48: a bandwidth of {unit(B / 1e6, 'MHz', 0)}, antenna gains of {unit(G, 'dBi', 0)}, a noise figure of "
                f"{unit(F, 'dB', 0)} and a margin of {unit(M, 'dB', 0)} give a noise power of {unit(N, 'dBm', 0)}; at the worst hop " + " and ".join(out) +
                f". The last sentence of the statement needs its assumption: on a route with a {unit(_fin(lt['longest_hop_m']) / 1000.0, 'km', 0)} hop between "
                f"two rovers ({num(lt['longest_hop_kbps'], 0)}{KBPS6}) and a {unit(_fin(sm['longest_hop_m']) / 1000.0, 'km', 2)} hop between two small rovers "
                f"({num(sm['longest_hop_kbps'], 1)}{KBPS6}) the lowest rate is on the shorter hop. Every rate here and in Table 7 is the Shannon bound of the "
                f"channel after the margin, not what a modem delivers.")
    fill("P3-PROP2-EXAMPLE", prop2, "E48 link")

    def prop3():
        c = clock_rate()
        time_scale()
        us = lambda x: num(x * DAY_US, 4)
        return (f"Worked example, with GM<sub>E</sub> = 3.986004418&nbsp;&times;&nbsp;10<sup>14</sup> and GM<sub>M</sub> = 4.90280031&nbsp;&times;&nbsp;10<sup>12</sup>&nbsp;m<sup>3</sup>/s<sup>2</sup>, "
                f"a = 3.84399&nbsp;&times;&nbsp;10<sup>8</sup>&nbsp;m, R<sub>M</sub> = 1,737.4&nbsp;km and L<sub>G</sub> = 6.969290134&nbsp;&times;&nbsp;10<sup>&minus;10</sup> [23]: "
                f"&mu; = {num(c['mu'], 6)} and v<sup>2</sup> = {num(c['v2'] / 1e6, 4)}&nbsp;&times;&nbsp;10<sup>6</sup>&nbsp;m<sup>2</sup>/s<sup>2</sup>; the three terms "
                f"are L<sub>G</sub> = {us(c['LG'])}, L<sub>L</sub> = {us(c['LL'])} and L<sub>orb</sub> = {us(c['Lorb'])}&nbsp;&micro;s a day, and the rate is "
                f"{us(c['LG'])} &minus; {us(c['LL'])} &minus; {us(c['Lorb'])} = {num(c['rate'] * DAY_US, 2)}&nbsp;&micro;s a day, {num(c['rate'] * 1e10, 4)}&nbsp;&times;&nbsp;10<sup>&minus;10</sup>; "
                f"more decimals would not mean anything, because a kilometre of site height moves the rate by about 0.002 and the eccentricity term "
                f"left out is 0.11 periodic. "
                f"The clock model of E51 uses this constant, and the build checks the two against each other.")
    fill("P3-PROP3-EXAMPLE", prop3, "E51 constants")

    def prop4():
        y, A = holdover_check()
        hc, ha = r.p6("E51", "holdover", "crystal"), r.p6("E51", "holdover", "csac")
        res = next(k for k in hc if k.startswith("road-segment reservation"))
        rng = next(k for k in hc if k.startswith("one-way ranging, 1 m"))
        k = r.p6("E51", "constants")
        tr = _fin(k["t_reply_s"])
        bound = C_LIGHT * tr * _fin(k["classes"]["crystal"]["y_hi"]) / 2.0
        two = _fin(e51row("crystal", 10)["two_way_single_sided_m_p95"])
        check(two <= bound, "Proposition 4: the simulated two-way ranging error of the crystal is within c x T_reply x (largest rate difference) / 2")
        check(abs(C_LIGHT * 1e-9 - 0.2998) < 1e-4 and abs(_fin(hc[rng]["budget_s"]) - 1.0 / C_LIGHT) < 1e-15, "Proposition 4: 1 ns is 0.2998 m, and a 1 m budget is 1 / c seconds")
        return (f"Worked example, the two classes of E51 at their 95th-percentile frequency error: the crystal at y = {e10(y['crystal'], 1)} holds the "
                f"0.1&nbsp;s of a reservation for {dur(hc[res]['analytic_y95_s'])} and the {sig(_fin(hc[rng]['budget_s']) * 1e9, 3)}&nbsp;ns of a 1&nbsp;m one-way "
                f"range for {dur(hc[rng]['analytic_y95_s'])}; the atomic clock at y = {e10(y['csac'], 1)} with A = {e10(A, 1)} per second holds them for "
                f"{dur(ha[res]['analytic_y95_s'])} and {dur(ha[rng]['analytic_y95_s'])}. With a reply delay of {unit(tr * 1000, 'ms', 0)} and the crystal's largest "
                f"rate difference, single-sided two-way ranging is wrong by at most {unit(bound, 'm', 2)}; E51 gave {unit(two, 'm', 3)} at the 95th percentile. "
                f"Table 12 lists {dur(ha[res]['p5_over_vehicles_s'])} and {dur(ha[rng]['p5_over_vehicles_s'])} for the atomic clock where this example has "
                f"{dur(ha[res]['analytic_y95_s'])} and {dur(ha[rng]['analytic_y95_s'])}: the table takes the fifth percentile of the holdover over the drawn "
                f"clocks, the example the formula at the 95th-percentile frequency error, and the build checks that the two agree within 6&#8239;%. Both are "
                f"the same closed form, so that agreement is of a formula with itself. Part (c) sets the residual x<sub>0</sub> to zero. The model's own "
                f"time transfer leaves {unit(_fin(k['tt_sigma_s']) * 1e9, 'ns', 0)}, which is {unit(_fin(k['tt_sigma_s']) * C_LIGHT, 'm', 0)} of one-way range, so "
                f"the budgets of 1&nbsp;m and 10&nbsp;m of one-way range are exceeded at the instant of synchronisation and their holdover times are not "
                f"reachable with that transfer (Table 12 marks them).")
    fill("P3-PROP4-EXAMPLE", prop4, "E51 holdover")

    def prop5():
        f = frame_numbers()
        a3, a2, a1 = FK_ANGLES_ARCSEC
        return (f"Worked example: the NAIF kernel builds M from rotations of {num(a3, 4)}&Prime;, {num(a2, 4)}&Prime; and {num(a1, 4)}&Prime; about axes 3, 2 and 1 "
                f"[88]. Its rotation angle is {num(math.degrees(f['ang']), 5)}&deg;, so the largest displacement is {unit(f['eq'], 'm', 1)}; at the south pole it is "
                f"{unit(f['pole'], 'm', 1)} and at the centre of our terrain tile, {num(-TILE_CENTRE[0], 4)}&deg;&nbsp;S, {num(TILE_CENTRE[1], 4)}&deg;&nbsp;E, "
                f"{unit(f['site'], 'm', 1)}. The build compares all three with the coordinate code of the repository, which agrees to 0.05&nbsp;m.")
    fill("P3-PROP5-EXAMPLE", prop5, "geo.py frame shift")

    def prop6():
        s = map_sizes()
        hdr_auth = lrip_sizes()["hdr"] + 14          # packet and protocol headers plus the security header and the 8-byte code (3.8)
        check(0.75 < hdr_auth / (4.0 * s["h"]) < 1.0, "Proposition 6: headers and code of one message per opened node come close to doubling the walk")
        worst = max(r.p6("E52", "rows"), key=lambda x: _fin(x["tree_overhead_bytes"]))
        return (f"Worked example, one 256&nbsp;m layer of the 16&nbsp;km site: N = {cnt(s['N'])}, D = {cnt(s['D'])}, h = {cnt(s['h'])}&nbsp;B, v = {cnt(s['v'])}&nbsp;B. "
                f"With n = {cnt(s['n'])} changed tiles the tree costs at most {cnt(s['h'])}&nbsp;&times;&nbsp;(1 + 4&nbsp;&times;&nbsp;{cnt(s['n'])}&nbsp;&times;&nbsp;{cnt(s['D'])}) = "
                f"{cnt(s['tree'])}&nbsp;B and the flat list {cnt(s['flat'])}&nbsp;B; the tree is the smaller for n below {num(s['cross'], 1)}, that is, for up to "
                f"{cnt(math.floor(s['cross']))} changed tiles (at n = {cnt(math.floor(s['cross']))} it costs {cnt(s['h'] * (1 + 4 * math.floor(s['cross']) * s['D']))}&nbsp;B). "
                f"The count leaves out the replies and the framing: if every opened node travels as one authenticated message of {cnt(hdr_auth)}&nbsp;B of headers "
                f"and code around its {cnt(4 * s['h'])}&nbsp;B of hashes, the walk nearly doubles. In E52 the "
                f"largest walk was {cnt(worst['tree_overhead_bytes'])}&nbsp;B for {num(worst['tiles_changed_mean'], 0)} changed tile versions over the layers, far "
                f"inside the bound because changed tiles lie together along the routes; the build checks every row of E52 against the bound.")
    fill("P3-PROP6-EXAMPLE", prop6, "E52")

    def prop7():
        e55_auth()
        fz = r.p6("E55", "auth", "forgery")
        year_s = 365.25 * 86400.0
        q = 10.0 * year_s
        p32 = q * 2.0 ** -32
        check(0.05 < p32 < 0.1, "Proposition 7: a 32-bit code would be forged with a probability of several per cent in a year of ten attempts a second")
        return (f"Worked example: for t = 64 the bound is {e10(2.0 ** -64, 1)} per attempt and, at ten attempts a second for a year (q = {e10(q, 1)}), "
                f"{e10(q * 2.0 ** -64, 1)}; for t = 32 the same year gives {num(p32, 2)}, which is why a 4-byte code is excluded. E55 counted "
                f"{cnt(fz['8']['accepted'])} acceptances in {cnt(fz['8']['attempts'])} attempts at t = 8 and {cnt(fz['16']['accepted'])} in "
                f"{cnt(fz['16']['attempts'])} at t = 16, where the proposition predicts {num(_fin(fz['8']['expected']), 0)} and {num(_fin(fz['16']['expected']), 1)}. "
                f"A 32-bit counter at one message a second lasts {num(2.0 ** 32 / year_s, 0)} years, so the key is changed by policy long before the counter runs out.")
    fill("P3-PROP7-EXAMPLE", prop7, "E55 authentication")

    def prop8():
        from lunarsim.atc import regimes as REGS
        sd = REGS._samples()
        ids = sd["ids"]
        xy = np.array([s["xy_m"] for s in sd["doc"]["samples"]], float)
        pad = f"PAD_A@{r.scn['pad_standoff_km']}"
        names = [b if b != "PAD_A" else pad for b in PD["beacons"]]
        if any(n not in ids for n in names):
            raise Pending("a beacon of E50 is not among the route samples' named sites")
        bxy = xy[[ids[n] for n in names]]
        N = len(bxy)

        def hdop(p):
            th = [math.atan2(b[1] - p[1], b[0] - p[0]) for b in bxy]
            S = sum(complex(math.cos(2 * t), math.sin(2 * t)) for t in th)
            H = np.array([[math.cos(t), math.sin(t)] for t in th])
            direct = math.sqrt(float(np.trace(np.linalg.inv(H.T @ H))))
            closed = 2 * math.sqrt(N) / math.sqrt(N * N - abs(S) ** 2)
            check(abs(direct - closed) < 1e-6 * direct, "Proposition 8: the closed form 2 sqrt(N) / sqrt(N^2 - |S|^2) equals the trace of the inverse normal matrix")
            return closed
        ev = 2 / math.sqrt(N)
        sites = [("CONSTR", "the construction site"), ("ISRU", "the oxygen plant"), ("SCI_1", "the science site"), ("PSR", "the shadowed crater")]
        hd = {k: hdop(xy[ids[k]]) for k, _ in sites}
        check(all(v > ev for v in hd.values()) and hd["PSR"] > 3 * ev, "Proposition 8: seen from the far sites the four beacons give a dilution well above the even-spread value")
        check(hd["CONSTR"] == max(hd.values()), "Proposition 8: the construction site, nearest the base and almost on the beacons' line, has the largest dilution of the four sites")
        base = bxy[names.index("BASE")]
        span = max(float(np.linalg.norm(a - b)) for a in bxy for b in bxy)
        # how far the beacons are from one line: the smaller singular value of the centred coordinates
        sv = np.linalg.svd(bxy - bxy.mean(0), compute_uv=False)
        check(sv[1] < 0.2 * sv[0], "Proposition 8: E50's four beacons lie nearly on one line")
        sr = PD["radio_sigma_m"]
        away = e50("1", "dr+ranging", "away", "p95_m")
        near_med = _fin(e50("1", "dr+ranging", "near", "median_m")["mean"])
        check(near_med < sr * min(hd.values()), "E50's median error where two or more beacons are seen is below the single-epoch bound at every example site: a sequential filter is not bound by it")
        km = lambda k: unit(float(np.linalg.norm(xy[ids[k]] - base)) / 1000.0, 'km', 2 if float(np.linalg.norm(xy[ids[k]] - base)) < 1000 else 1)
        bnd = lambda k: unit(sr * hd[k], 'm', 0 if sr * hd[k] >= 10 else 1)
        return (f"Worked example, the four beacons of E50 (the base mast, the depot, the power plant and one landing pad): they span {unit(span / 1000.0, 'km', 2)} "
                f"and lie nearly on one line. Evenly spread around a vehicle they would give a dilution of {num(ev, 1)}. With all four in view the dilution is "
                + "; ".join(f"{num(hd[k], 1)} seen from {nm}, {km(k)} from the base" for k, nm in sites) +
                f". It does not simply rise with distance: the site nearest the base is the worst of the four, because it lies almost on the beacons' "
                f"line (case iii). With the {unit(sr, 'm', 0)} range error of the base radio the bound on the horizontal error of one epoch (one sigma) is "
                + ", ".join(bnd(k) for k, _ in sites[:-1]) + f" and {bnd(sites[-1][0])} at those four sites. Three things limit what this says about E50. "
                f"The bound assumes all four beacons in view, while E50's region away from the base is where fewer than two are: it says nothing about "
                f"the {unit(away['mean'], 'm', 0)} that E50's ranging layer left there at the 95th percentile. It is a bound for a single epoch of ranges with "
                f"no prior, while E50 runs a sequential filter with a dead-reckoning prior, which is not bound by it: where two or more beacons are seen "
                f"E50's median error is {unit(near_med, 'm', 1)}, below the single-epoch bound at every one of these sites. And it takes the base radio's "
                f"range error for every range, while E50 also has ultra-wideband ranges of {unit(PD['uwb_sigma_m'], 'm', 1)} within "
                f"{unit(PD['uwb_range_m'], 'm', 0)}.")
    fill("P3-PROP8-EXAMPLE", prop8, "E50 beacons")

    # --- H. the "Proved, tested, assumed" table (Section 8): one row per claim, the status from the data where it depends on results ----
    def have(exp, *keys):
        try:
            r.p6(exp, *keys)
            return True
        except Pending:
            return False

    def b97_basis():
        im, bad, ok, att = b97_parts()
        return (f"{cap1(words(len(ok)))} usable frames of one camera, uncalibrated: range within {pc(max(_fin(x['range_err_rel']) for x in ok), 1)}, with a bias "
                f"that is reported and not removed")

    def table_pta():
        """Table 18. Since the referee round of 11 Nov 2026 it has a fourth status, 'calculated from assumed inputs' (decision A1): a result
        that could not have come out otherwise is not called tested. The awaited tasks are rows of the last group."""
        P, T, C, A, N = "Proved", "Tested", "Calculated from assumed inputs", "Assumed", "Not yet tested"

        sv = lambda ok: "supported" if ok else "not supported"
        h9 = h9_parts()
        ms = list(h9)
        seeds50 = ", ".join(f"{cnt(len(r.p6('E50', 'seeds')[m]))} seeds at {MULT_NAME[m]}" for m in ms)
        n51, n52, n54 = cnt(len(r.p6("E51", "seeds"))), cnt(r.p6("E52", "seeds")), cnt(len(r.p6("E54", "seeds")))
        f = frame_numbers()
        c = clock_rate()
        s = map_sizes()
        fz = r.p6("E55", "auth", "forgery")
        fo = r.s48("failover")
        twice = sum(int(v["jobs_assigned_twice"]) for v in fo["by_mtbf"].values())
        n_fo = sum(int(v["seeds"]) for v in fo["by_mtbf"].values())
        h14 = r.p6("E54", "h14")
        c14 = _fin(h14["difference_sf_ll_minus_drop_retry"]["ci"][1]) < 0
        x8 = have("E50", "errors", "8", "dr", "all", "p95_m")
        st = e50_steps()
        rd5, _sens = referee_m5()
        rows5 = rd5["1"]["rows"]
        near = h9["1"]["h"]["ranging_near_p95_m"]
        m14 = referee_m14(r, check)
        k51 = r.p6("E51", "constants")
        res_m = _fin(k51["tt_sigma_s"]) * C_LIGHT
        pairs51 = int(e51row("crystal", 10)["conflict_pairs_checked"])
        h12s = _fin(r.p6("E52", "h12", "share_of_full_resend_24h"))
        h13 = r.p6("E53", "h13")
        d54 = e54row(0.25, "drop_retry")
        led = e54_ledger("numbers")
        e48h, fl = r.s48("h10"), r.s48("flight")
        p99s = _fin(r.s48("classes", "LTV1", "cpu_auction_round_ms", "p99")) * _fin(fl["factor"]) / 1000.0
        ls = r.p6("E54", "link_shares")
        eb = r.p6("E50b", "metrics", "delay_mean_h")
        ebs = r.p6("E50b", "stops")
        dsp = r.p6("E53", "driving_split", "e53_auth_20_rovers", "fleet_driving", "1 Hz")
        rr_ = r.p6("E55", "replay_recent", "loss")
        rr_acc, rr_n = sum(int(v["replays_accepted"]) for v in rr_.values()), sum(int(v["replays"]) for v in rr_.values())
        check(rr_acc == sum(int(v["accepted_missed_original_inside_window"]) for v in rr_.values()), "Table 18: every accepted recent replay is the case Proposition 7(b) allows")
        tp5, mm5 = r.s48("per_robot_round", "timing_passes", "by_multiple"), r.s48("measured_memory", "mb_by_multiple")
        rows = [
            # proved
            ["Beyond the breakpoint the loss over flat ground is 40&nbsp;log&nbsp;d &minus; 20&nbsp;log(h<sub>1</sub>h<sub>2</sub>), whatever the frequency; two antennas "
             "see each other no farther than &radic;(2Rh<sub>1</sub>) + &radic;(2Rh<sub>2</sub>)", P + " (for a plane)",
             "Two rays, reflection coefficient &minus;1, flat ground; a smooth sphere for the horizon. Table 7 applies the law at hops where the horizon is close; "
             f"there a calculation with the smooth-sphere method of [20] gives {num(m14['veh_dl'][0], 1)} to {num(m14['veh_dl'][1], 1)}&nbsp;dB more loss for "
             f"the vehicle hops (Table 7). Not a "
             "measurement: no path loss has been measured on the Moon", "Proposition 1; Sections 4.2, 5.3"],
            ["On a route whose hops have the same antenna heights, power and gains, the rate at the longest hop bounds the rate of every shorter hop from below", P,
             "White Gaussian noise, ideal coding: a Shannon bound, not the rate of a modem", "Proposition 2"],
            [f"A clock on the lunar surface gains {num(c['rate'] * DAY_US, 2)}&nbsp;&micro;s a day on one on Earth's geoid", P,
             "Point masses, circular orbit, first order, Sun left out; agrees with three published values to 0.01&nbsp;&micro;s a day", "Proposition 3; Section 3.6"],
            ["One-way ranging turns 1&nbsp;ns into 0.30&nbsp;m; two-way ranging needs no shared clock; the holdover formula", P,
             "Constant frequency error and linear ageing, no random noise; the holdover formula takes the residual of the synchronisation as zero", "Proposition 4; Table 12"],
            [f"Coordinates read in the wrong lunar frame are off by {unit(f['pole'], 'm', 0)} at the south pole", P,
             "A constant rotation between the two frames, from the NAIF kernel; agrees with the repository's coordinate code to 0.05&nbsp;m", "Proposition 5; Section 3.7"],
            [f"A hash-tree walk finds n changed tiles in at most h(1 + 4nD) hash bytes ({cnt(s['tree'])}&nbsp;B for {cnt(s['n'])} tiles)", f"{P}; {T.lower()}",
             f"No hash collisions; hash bytes in one direction, without replies and framing. Every row of E52 is within the bound ({n52} seeds)", "Proposition 6; Section 5.10"],
            ["A forged message passes a t-bit code with probability 2<sup>&minus;t</sup>; a replay is rejected by any receiver that accepted the original or a later message", f"{P}; {T.lower()}",
             f"An ideal code, a counter never reused under one key. Counted at 8 and 16 bits with the real AES-CMAC: {cnt(fz['8']['accepted'])} of {cnt(fz['8']['attempts'])} and "
             f"{cnt(fz['16']['accepted'])} of {cnt(fz['16']['attempts'])}. Replays of messages up to 60&nbsp;s old: {cnt(rr_acc)} of {cnt(rr_n)} accepted, each by a "
             f"receiver that had missed the original and inside the window, the case the statement allows (E55). The 64-bit value is the formula's", "Proposition 7; Section 5.11"],
            ["Beacons seen within a narrow angle dilute a ranging fix by at least 2/(&radic;N&nbsp;sin&nbsp;2&alpha;); beacons on one line give nothing across it", P,
             "Two-way ranges with equal independent Gaussian errors, all beacons in view, one epoch with no prior: not a bound on E50's sequential filter, and "
             "silent on the region where fewer than two beacons are in view", "Proposition 8"],
            ["The operator's budget is zero under the posted price and under no payments", P, "By construction of the rule: the tariff is paid through", "Section 5.5"],
            # tested
            [f"Positioning (H9&prime;, first clause): dead reckoning alone passes the {unit(PD['budget_m'], 'm', 0)} budget within a shift, {sv(all(h9[m]['dr'] for m in ms))}", T,
             f"E50, a replay of recorded trajectories through a filter matched to its own error model: {seeds50}. A comparison with a threshold, no sampling test. "
             f"Every sensor value is from Earth or Mars tests, a requirement or an assumption (Table 4)", "Section 5.8"],
            [f"Positioning (H9&prime;, second clause): with ranging the 95th percentile of the position error is {unit(near['mean'], 'm', 1)} where two or more of the "
             f"four beacons are in line of sight, {pc(st['near_share'], 0)} of driving steps", T + "; the registered clause depends on the reading",
             f"E50 under the analysis's reading of &ldquo;within radio range of the base beacons&rdquo;, chosen after the results. Under the other readings, "
             f"on every seed at today's fleet (a simulation on assumed ranging errors): {unit(rows5[1]['p95'], 'm', 1)} with one or more beacons in line of "
             f"sight, {unit(rows5[2]['p95'], 'm', 1)} within 1&nbsp;km of the base, and {unit(rows5[3]['p95'], 'm', 1)} under the registered wording, where "
             f"the clause fails in every seed", "Section 5.8"],
            [f"Positioning (H9&prime;, third clause): terrain fixes hold the budget where fewer than two beacons are in line of sight, {sv(all(h9[m]['away'] for m in ms))}", T,
             f"E50, as above ({unit(h9['1']['h']['fixes_away_p95_m']['mean'], 'm', 1)} at today's fleet)", "Section 5.8"],
            [f"With the terrain-fix stops inside the engine the delay per delivery {'rises' if _fin(eb['diff_mean']) > 0 else 'falls'} by "
             f"{unit(abs(_fin(eb['diff_mean'])), 'h', 2)} ({pc(abs(_fin(eb['diff_mean'])) / _fin(eb['without_stop_time']), 1)})", T + ", exploratory",
             f"E50b: {cnt(eb['n_seeds'])} seeds at today's fleet, run after the first results. A lower bound: "
             f"{pc(_fin(ebs['engine_fix_stop_h_mean']) / _fin(ebs['perfect_run_fix_stop_h_mean']), 0)} of the fix time is inserted", "Section 5.8"],
            [f"Time (H11, first half): a crystal resynchronised at every contact causes no reservation conflict with a guard of {unit(k51['guard_s'], 's', 1)}", T + " (observed)",
             f"E51, a check on logged reservations: {cnt(pairs51)} pairs in {n51} seeds at today's fleet only; guard swept from 0.01 to 1&nbsp;s", "Section 5.9"],
            ["Time (H11, second half): the clock error adds more to one-way ranging than the ranging radio's own noise", C,
             f"The assumed residual of the time transfer, {unit(_fin(k51['tt_sigma_s']) * 1e9, 'ns', 0)}, is {unit(res_m, 'm', 0)} of range: true of any oscillator, "
             f"a perfect one included", "Section 5.9"],
            ["Frequency steering and mixed time scales (the variants of E51)", f"{T}, post hoc", f"E51b: {cnt(len(r.p6('E51b', 'seeds')))} seeds; added after the first results", "Section 5.9"],
            [f"The shared map (H12): after a day out of contact a sync of changed tiles is {pc(h12s, 2)} of a full resend, and hazards first is current sooner than oldest first", C,
             f"{cnt(s['n'])} route tiles assumed to change a day in each of three layers of {cnt(s['N'])}; a subset sent first is always finished first. E52 adds the "
             f"sizes and the stale-map hits ({n52} seeds); {e52_sweep('clause')}", "Section 5.10"],
            [f"The protocol's traffic (H13): 20 authenticated rovers load the busiest link with {num(h13['at_1hz_kbps_p95'], 2)}&nbsp;kbit/s at 1&nbsp;Hz and "
             f"{num(h13['at_10hz_kbps_p95'], 1)} at 10&nbsp;Hz", C,
             "The serialised sizes of protocol version 0.1 times the assumed report rates, summed over a fleet in one radio neighbourhood; the same in every draw; the "
             "same comparisons come out alike with version 0.2", "Section 5.11"],
            [f"Store-and-forward with the lost-link rule loses fewer jobs than drop-and-retry (H14, first clause), {sv(c14)}", T,
             f"E54, a message-level simulation on the recorded month, not an engine run: {n54} seeds at today's fleet; {family_sentence('pta14')}. "
             f"{cnt(d54['award_lost'])} awards of {cnt(d54['award_n'])} under drop-and-retry, at a retry budget we chose; {e54_retry('clause')}. Repeated at the packet sizes of protocol "
             f"version 0.2 and in Proximity-1 frames with no value changed: a property of the replay's message set, not a test of version 0.2", "Section 5.12"],
            ["The lost-link rule leaves no reservation stuck past its timeout (H14, second clause)", "Not testable as written",
             f"The zero followed from the rule as first written, which released a silent holder's reservation; that release is withdrawn. E54 gives "
             f"{cnt(d54['stuck_reservations'])} segments and {cnt(d54['stuck_hours'])} hours that the rule now marks unconfirmed; caution-speed traversal is not priced", "Sections 3.8, 5.12"],
            [f"{cap1(words(led['lost']))} of the month's {cnt(led['per_seed'])} daily ledger bundles expire with a {num(led['life'], 0)}-day lifetime", C,
             f"A {num(led['life'], 0)}-day lifetime against {num(led['down'], 1)} days without Earth, set by where the imposed blackout falls in the month; the same in every seed", "Section 5.12"],
            [f"Sizing (H10 of [59], exploratory): the safety check takes {pc(e48h['safety_core_share_flight_per_robot_10hz'], 1)} of one core of the reference processor", T,
             f"E48: one Python function timed on a laptop over the same moves for every class, with no reservation entries in the call, and scaled by an assumed factor", "Section 5.1"],
            [f"One robot's bid computation in an auction round, scaled, takes at most "
             f"{unit(max(_fin(v) for v in tp5['1']['flight_p99_ms_by_pass']) / 1000.0, 's', 2)} at the 99th percentile at today's fleet and at most "
             f"{unit(max(_fin(v) for m_ in ('4', '8') for v in tp5[m_]['flight_p99_ms_by_pass']) / 1000.0, 's', 2)} at four and eight times it: under the "
             f"one-second decision at the central factor, over it only at the top of the factor's range at the larger fleets", T,
             f"E48: three laptop passes of Python in one 30-day month of one seed per fleet size, without the memory tracer (corrected after a code review), "
             f"scaled by an assumed factor; the simulator's whole-fleet call ({unit(p99s, 's', 2)}, pooled) is of the same size", "Section 5.1"],
            [f"The on-robot parts allocate {num(max(_fin(v['all_at_once_peak']) for v in mm5.values()), 2)}&nbsp;MB at most", T + " (measured on a laptop)",
             "E48: peaks of Python allocations in one month of one seed per fleet size; the interpreter, the code and the numerical library's buffers are "
             "not counted; most of it is the learned bid policy", "Section 5.1"],
            [f"The on-robot data come to {unit(e48h['peak_memory_mb_max_robot'], 'MB', 2)}", C,
             "A sum of estimates at assumed layouts: a day of the reservation table, a year of the ledger, the policy files and an allowance; the measured "
             "peak is the row above", "Section 5.1"],
            [f"The authenticated traffic of 20 robots, {num(e48h['link_kbps_needed_20_robots_secured_mac8'], 2)}&nbsp;kbit/s at the sources, would need "
             f"{num(e48h['airtime_kbps_20_robots_secured_mac8_scheduled'], 2)}&nbsp;kbit/s of a base-scheduled channel if every robot were within one hop of the base", C,
             f"Event counts of the instrumented runs times serialised sizes and assumed rates. The hop count is from positions that are "
             f"{pc(st['parked_share_s1'], 0)} parked; a driving vehicle has a path to the base {pc(ls['linked_share_driving_time'], 1)} of the time (E54). "
             f"Drawn from driving steps only, 20 rovers are {num(dsp['mean_hops_to_base'], 2)} hops from the base on average (a calculation on drawn positions)", "Sections 5.2, 5.11"],
            [f"After a rebuild of the base computer's table no job is assigned twice ({'none' if twice == 0 else cnt(twice)} found)", T,
             f"E48 failover sweep: {cnt(n_fo)} seed-runs over three failure rates", "Section 5.4"],
            ["Incentives (H5): " + V.get("P3-H5-ABSTRACT-CLAUSE", "pending"), T, f"E46: {V.get('P3-E46-N-RUNS', 'pending')} simulated years, three owners, two splits, 30 seeds; payments priced "
             "after one allocation. The third clause asks whether pooling is superadditive in the simulator", "Sections 5.5 to 5.7"],
            ["The mast sees " + V["P3-MESH-MAST-DIRECT-SHARE"] + " of the route points directly, and rovers form one network from 2&nbsp;km range", "Computed",
             "Line of sight on the 5&nbsp;m terrain model, whose effective resolution is about 20&nbsp;m, with a grazing ray counted as a link; not a radio measurement", "Section 3.3"],
            ["Agreement by averaging among the rovers, with and without the base mast as a node", T,
             e55_base_node("basis") + "; averaging on the sparse mesh rarely converges, so shared estimates are computed at the base", "Section 5.11"],
            ["Range and direction of the Moon or Earth from one image of its limb, against the kernels of the Artemis&nbsp;II flyby; the Earth-link azimuth and elevation "
             "against the SPICE toolkit", T + " on real data",
             b97_basis() + "; a crewed flyby's navigation camera, not rover data, and not a test of a rover's terrain fix or of the terrain mask", "Section 5.13"],
            # assumed
            ["The factor from the laptop to the flight processor", A, "Reported with its range; a flight implementation could differ by more", "Sections 5.1, 7"],
            ["The radio: 2.4&nbsp;GHz, transmit powers, antenna heights and gains, noise figure, margin, 5&nbsp;km range, hop latency, message loss", A,
             "Loss swept in [60]; margins of 3, 10 and 15&nbsp;dB on the mesh's links; the free-space rate kept as an upper bound", "Sections 3.3, 4.2"],
            ["The two-ray law on paths the terrain shows as visible", A, "One NASA model supports it for lunar ground; no measurement", "Sections 3.3, 7"],
            ["The navigation model's parameters and the navigation service's accuracy and availability by year", A,
             "One value each, with one variant (the service as of 2030); the ranges of the research note were not run. The referee's rerun varied three of them (Section 5.8)", "Table 4"],
            ["The oscillators: the crystal's spread over vehicles is taken from one crystal's excursion on the lunar surface, the atomic clock's is a data-sheet value; the "
             "transfer residual and the guard", A + "; Spec", "Guard swept; frequency steering as a variant", "Sections 3.6, 5.9"],
            ["The map's change rates and the share of hazards a rover cannot see", A, "The four change rates swept one at a time after the fact (Section 5.10); the hidden share not swept", "Section 4.2"],
            ["The base as trust anchor; a site key changed daily; the lost-link ladder's times; the retry budget of drop-and-retry", A,
             "The retry budget swept after the results were known (Section 5.12); the others not swept; no standard names a trust anchor for a site with several owners", "Sections 3.8, 4.2"],
            ["The value of delivery time by priority, the censoring of undelivered cargo at the year's end, the operator's cost per hour, private costs, the audit multiple", A,
             "One value each; the private-cost spread declared and not swept", "Section 3.9"],
            ["The base computer's failure rate and the re-election delay", A, "The failure rate at three levels", "Section 4.2"],
            # not yet tested
            ["Any of this on radio hardware", N, "Stage 2 of Table 16", "Section 6.5"],
            ["Path loss between rover-height antennas on the Moon", N, "No measurement exists; the one flown cellular network connected no device", "Section 3.8"],
            [f"Over a spherical ground the crew and cargo rovers' {unit(_fin(m14['lk']['LTV1']['longest_hop_m']) / 1000.0, 'km', 0)} hop carries "
             f"{num(m14['rates']['LTV1'][0], 0)}&nbsp;kbit/s, not {num(m14['rates']['LTV1'][1], 0)}, and no longer 1&nbsp;Mbit/s", C,
             "ITU-R P.526 section 3.2 for a smooth sphere, checked against the Recommendation's text; assumed radio constants; no lunar measurement", "Section 5.3; Table 7"],
            ["The software on a flight-class processor, in a flight language", N, "The scaling factor stands in for it", "Sections 5.1, 7"],
            [f"Protocol version 0.2 (frame, datum and time scale declared per sender, a 95&#8239;% bound in every position report, no covariance): 20 "
             f"authenticated rovers load the busiest link with {num(lrip_v02()['h']['at_1hz_kbps_p95'], 2)}&nbsp;kbit/s at 1&nbsp;Hz, and with "
             f"{num(lrip_v02()['fr']['fleet_auth_1hz_20']['busiest_link_kbps_p95'], 2)} in Proximity-1 frames", C,
             "Serialised sizes times assumed report rates on the traffic model of E53; the conformance vectors test the codec, not a radio", "Sections 3.8, 5.11"],
            ["Hops and reach to the base with 1.0&nbsp;m antennas for the small classes; the report rate tied to motion", N, "Not run; the traffic model gives every rover a 2.5&nbsp;m antenna", "Sections 5.2, 7"],
            ["Position error at eight times the fleet", T if x8 else N, "E50 at eight times the fleet: " + ("in the file" if x8 else "five seeds, not in this version"), "Section 5.8"],
            ["The lost-link return and the caution-speed crossing of an unconfirmed segment driven inside the engine; ranging and terrain fixes on the lunar surface; a "
             "hopper's navigation in flight", N, "Named as limitations", "Section 7"],
            ["More than three owners; misreports other than bid scaling; a vehicle with a valid key that lies about its position", N,
             "The last is tested in the companion paper [61]", "Section 7"],
        ]
        n_calc = sum(1 for x in rows if x[1] == C)
        check(n_calc == 8, "Table 18 has eight rows calculated from assumed inputs: H11's ranging half, H12, H13, the ledger count, the on-robot data, the link's airtime, the spherical-ground rate and the traffic of protocol version 0.2")
        return _tab("Table 18. Proved, tested, calculated, assumed: every claim of this paper with what stands behind it. &ldquo;Proved&rdquo; means derived in Appendix A "
                    "under the stated assumption; &ldquo;tested&rdquo; means that a simulation experiment could have come out otherwise, with its seeds and fleet; "
                    "&ldquo;calculated from assumed inputs&rdquo; means arithmetic on stated inputs, a property of a rule or a count fixed by the design, which could "
                    "not have come out otherwise and is therefore not called a test; &ldquo;assumed&rdquo; means a value we chose, with what was swept; &ldquo;not yet "
                    "tested&rdquo; is listed, not left out. Nothing in this table is a measurement on the Moon. "
                    "The status of each hypothesis is written by the build script from the results files.", ["Claim", "Status", "What stands behind it", "Where"], rows, cls="wide")
    T6["pta"] = (table_pta, "Phase 6 results", "Table 18, proved, tested, assumed")

    # --- I. the Phase 6 clauses of the abstract, the introduction, the discussion and the conclusion: every word of direction from the data --
    def p6_clause(kind):
        h9 = h9_parts()
        one = h9["1"]
        b = one["b"]
        near, away, lans = one["h"]["ranging_near_p95_m"], one["h"]["fixes_away_p95_m"], one["lans_away"]
        c10 = e51row("crystal", 10)
        h11 = bool(r.p6("E51", "h11", "supported"))
        guard = _fin(r.p6("E51", "constants", "guard_s"))
        e52 = e52row(24, "hazards_first", 16)
        on, off = e53row("fleet", "on", 1.0, 20), e53row("fleet", "off", 1.0, 20)
        add = _fin(on["per_rover_kbps"]) / _fin(off["per_rover_kbps"]) - 1.0
        h13 = bool(r.p6("E53", "h13", "supported"))
        sched = _fin(r.p6("E53", "h13", "airtime_1hz_scheduled_kbps"))
        h14 = r.p6("E54", "h14")
        sp20 = e53row("spread", "on", 1.0, 20)
        ok = lambda x: "supported" if x else "not supported"
        near_in, away_in, lans_in = _fin(near["ci"][1]) < b, _fin(away["ci"][1]) < b, _fin(lans["ci"][1]) < b
        check(near_in == one["near"] and away_in == one["away"], "the Phase 6 clauses use H9's verdicts at today's fleet")
        lost_dr, lost_ll = _fin(h14["lost_jobs_drop_retry_per_seed"]["mean"]), _fin(h14["lost_jobs_sf_ll_per_seed"]["mean"])
        m_ = lambda x, nd=1: unit(x["mean"], "m", nd)
        st = e50_steps()
        rd5, _sens = referee_m5()
        km1, reg = rd5["1"]["rows"][2], rd5["1"]["rows"][3]          # within 1 km of the base; the registered wording (B-101, all seeds)
        check(km1["k"] == "c" and reg["k"] == "e" and km1["p95"] > b and reg["p95"] > b and reg["inside"] == 0,
              "with ranging the budget is not held within a kilometre of the base nor under the registered wording, in any seed")
        ls = r.p6("E54", "link_shares")
        drive = _fin(ls["linked_share_driving_time"])
        eb = r.p6("E50b", "metrics", "delay_mean_h")
        eb_rel = _fin(eb["diff_mean"]) / _fin(eb["without_stop_time"])
        eb_up = _fin(eb["diff_mean"]) > 0
        pairs51 = int(c10["conflict_pairs_checked"])
        d54 = e54row(0.25, "drop_retry")
        if kind == "abstract":
            return (f"Ranging {'holds' if near_in else 'does not hold'} the 95th percentile of position error at {m_(near)} where two or more base "
                    f"beacons are in line of sight, {pc(st['near_share'], 0)} of driving steps, and fails under the registered wording, all driving "
                    f"({unit(reg['p95'], 'm', 1)}); terrain fixes leave {m_(away)} elsewhere. Authentication adds {pc(add, 0)} "
                    f"to the bit rate; senders declare frame, datum and time scale, and reports carry a 95{PCT} bound, not a covariance.")
        if kind == "conclusion":
            return (f"Ranging {'holds' if near_in else 'does not hold'} the {unit(b, 'm', 0)} position budget where two or more beacons are in line of "
                    f"sight ({pc(st['near_share'], 0)} of driving steps), not under wider readings of near the base, and terrain fixes "
                    f"{'hold' if away_in else 'do not hold'} it elsewhere. Authentication adds {pc(add, 0)} to the bit rate, and senders now declare frame, "
                    f"datum and time scale.")
        if kind == "intro":
            return (f"Of the layers under the market, with the hypotheses of [67]: dead reckoning alone passes the {unit(b, 'm', 0)} separation budget within "
                    f"{'the first driving hour' if int(one['h']['dr_first_driving_hour_p95_over_budget']) == 1 else 'a shift'} (H9&prime;, first clause, "
                    f"{ok(one['dr'])}). Whether ranging holds the budget near the base (second clause) depends on the reading of the registered words: the "
                    f"95th percentile is {m_(near, 2)} where two or more of the four beacons are in line of sight, {pc(st['near_share'], 1)} of driving steps, "
                    f"{unit(km1['p95'], 'm', 1)} within a kilometre of the base, and {unit(reg['p95'], 'm', 1)} under the registered wording taken literally, "
                    f"where it fails in every seed. Terrain fixes leave {m_(away)} "
                    f"elsewhere, and {m_(lans, 2)} even with a navigation service as assumed for 2030 (third clause, {ok(one['away'])}); with the fix stops "
                    f"inside the engine the delay per delivery {'rises' if eb_up else 'falls'} by {unit(abs(_fin(eb['diff_mean'])), 'h', 2)}, {pc(abs(eb_rel), 1)}, "
                    f"a lower bound from an exploratory run. A crystal oscillator resynchronised whenever the base is heard caused no reservation conflict "
                    f"with a guard of {unit(guard, 's', 1)} in {cnt(pairs51)} reservation pairs (H11's first half, observed); that its error exceeds the "
                    f"ranging radio's noise follows from the assumed transfer residual and is a design calculation. Two registered hypotheses are design "
                    f"calculations and are reported as such: by the assumed change rate the changed tiles of a day are {pc(e52['share_of_full_resend'], 2)} "
                    f"of a full resend (H12), and 20 rovers load the busiest link with {num(on['busiest_link_kbps_p95'], 2)}{KBPS6} at 1&nbsp;Hz, their sizes "
                    f"times their rates (H13). Authentication adds {pc(add, 0)} to the bit rate of protocol version 0.1. Its position report named neither frame, datum nor "
                    f"time scale; version 0.2 has each sender declare them under its key and puts a 95{PCT} bound in every report, at "
                    f"{num(lrip_v02()['h']['at_1hz_kbps_p95'], 2)}{KBPS6} for the same 20 rovers, and carries no covariance. Store-and-forward with a lost-link rule "
                    f"lost {'no job' if lost_ll == 0 else num(lost_ll, 2) + ' jobs a seed'} where drop-and-retry lost {num(lost_dr, 2)} a seed (H14's first "
                    f"clause, {ok(_fin(h14['difference_sf_ll_minus_drop_retry']['ci'][1]) < 0)}; {cnt(d54['award_lost'])} awards of {cnt(d54['award_n'])}, at a "
                    f"retry budget we chose; {e54_retry('short')}); its second clause is not testable as written, and the rule now marks a silent holder's segment unconfirmed "
                    f"instead of releasing its reservation. {cap1(e54_ledger('clause'))}.")
        if kind == "discussion":
            return (f"Where two or more of the four beacons are in line of sight, ranging holds the 95th percentile of the position error at {m_(near, 2)}, "
                    f"{'inside' if near_in else 'outside'} the {unit(b, 'm', 0)} budget; that region is {pc(st['near_share'], 1)} of the driving steps, and "
                    f"under wider readings of &ldquo;near the base&rdquo; the budget is not held (Section 5.8). In the recorded months a crystal "
                    f"resynchronised at every contact {'caused no reservation conflict' if h11 else 'still caused reservation conflicts'} with a guard of "
                    f"{unit(guard, 's', 1)}; a day of map changes is {num(_fin(e52['bytes_mean']) / 1e6, 2)}&nbsp;MB at the assumed change rate; and the "
                    f"authenticated reports of 20 rovers would need {num(sched, 2)}{KBPS6} of a scheduled channel if every rover were within one hop of "
                    f"the base. Elsewhere, terrain fixes leave the 95th percentile at {m_(away)} ({m_(lans, 2)} with a navigation service as assumed for "
                    f"2030, {'inside' if lans_in else 'still outside'} the budget), a driving vehicle has a radio path to the base in {pc(drive, 1)} of its "
                    f"steps, and of 20 rovers spread over the routes only {pc(sp20['reachable_share'], 0)} reach the base at all.")
        raise KeyError(kind)
    for kind, key in (("abstract", "P3-P6-ABSTRACT-CLAUSE"), ("intro", "P3-P6-INTRO-CLAUSE"), ("discussion", "P3-P6-DISCUSSION-CLAUSE"),
                      ("conclusion", "P3-P6-CONCLUSION-CLAUSE")):
        fill(key, lambda kind=kind: p6_clause(kind), "Phase 6 results")
    fill("P3-P6-COMPUTE-SENTENCE", lambda: f"Of the experiments of the revision, E52 takes {unit(r.p6('E52', 'run_s'), 's', 0)} and E53 "
         f"{unit(r.p6('E53', 'run_s'), 's', 0)}; E50's run time per seed and fleet size, which set its seed counts, is in the dated changes of [67].", "E52, E53")

    # --- J. the confirmatory family of PREREG6 with Holm (results/phase6_family.json) and the Phase 6 verification rows -----------
    def family():
        """The family file, with Holm's adjusted p-values recomputed and each hypothesis's inputs compared with its own results file."""
        hy = r.p6("FAM", "hypotheses")
        alpha = _fin(r.p6("FAM", "alpha"))
        check(set(hy) == {"H9", "H10", "H13", "H14", "H15a"}, "the confirmatory family is H9, H10, H13, H14 and H15a (4.1)")
        tested = sorted(k for k, v in hy.items() if "holm" in v)
        check(tested == ["H10", "H14", "H15a"], "Holm is applied over H10, H14 and H15a, the hypotheses with a sampling test (4.1)")
        p = {"H10": _fin(hy["H10"]["p_intersection_union"]), "H14": _fin(hy["H14"]["p"]), "H15a": _fin(hy["H15a"]["p"])}
        order = sorted(tested, key=lambda k: p[k])
        adj, run = {}, 0.0
        for i, k in enumerate(order):
            run = max(run, min(1.0, (len(order) - i) * p[k]))
            adj[k] = run
        for k in tested:
            check(abs(adj[k] - _fin(hy[k]["holm"]["p_adjusted"])) < 1e-12 and bool(hy[k]["holm"]["rejected_at_0.05"]) == (adj[k] <= alpha),
                  f"Holm's adjusted p-value and decision for {k} follow from the family's three p-values")
        h14 = hy["H14"]
        fewer, more, tied = int(h14["seeds_fewer"]), int(h14["seeds_more"]), int(h14["seeds_tied"])
        n = fewer + more
        sign_p = sum(math.comb(n, i) for i in range(fewer, n + 1)) * 0.5 ** n
        e54h = r.p6("E54", "h14")
        check(abs(sign_p - p["H14"]) < 1e-12 and fewer + more + tied == len(r.p6("E54", "seeds")) and
              abs(_fin(h14["mean_diff_jobs"]) - _fin(e54h["difference_sf_ll_minus_drop_retry"]["mean"])) < 1e-9,
              "H14's p-value is the exact one-sided sign test over E54's seeds, on the paired difference E54 reports")
        check((adj["H14"] <= alpha) == (_fin(e54h["difference_sf_ll_minus_drop_retry"]["ci"][1]) < 0),
              "the sign test with Holm and the registered paired interval give the same verdict on H14 (4.6)")
        c9 = hy["H9"]["clauses"]
        k9 = list(c9)
        e9 = h9_parts()["1"]
        check(len(k9) == 3 and [bool(c9[k]["supported"]) for k in k9] == [e9["dr"], e9["near"], e9["away"]] and
              abs(_fin(c9[k9[1]]["value_m"]) - _fin(e9["h"]["ranging_near_p95_m"]["mean"])) < 1e-9 and
              abs(_fin(c9[k9[2]]["value_m"]) - _fin(e9["h"]["fixes_away_p95_m"]["mean"])) < 1e-9, "the family file's H9 clauses are E50's at today's fleet")
        c13 = hy["H13"]["clauses"]
        check(abs(_fin(c13["1 Hz"]["busiest_kbps_p95"]) - _fin(r.p6("E53", "h13", "at_1hz_kbps_p95"))) < 1e-3 and
              abs(_fin(c13["10 Hz"]["busiest_kbps_p95"]) - _fin(r.p6("E53", "h13", "at_10hz_kbps_p95"))) < 1e-3,
              "the family file's H13 values are E53's (to the three decimals the E53 file keeps)")
        return {"hy": hy, "alpha": alpha, "adj": adj, "p": p, "tested": tested, "k9": k9, "rej": {k: adj[k] <= alpha for k in tested}}

    def share_words(x, unit_word):
        x = _fin(x)
        return f"every {unit_word}" if x == 1.0 else (f"no {unit_word}" if x == 0.0 else f"{pc(x, 0)} of the {unit_word}s")

    def pval(x):
        x = _fin(x)
        return num(x, 2) if x >= 0.095 else (num(x, 3) if x >= 0.0005 else e10(x, 0))

    def family_sentence(kind):
        f = family()
        hy, adj, rej = f["hy"], f["adj"], f["rej"]
        sv = lambda ok: "supported" if ok else "not supported"
        bound = "at most " if "upper bound" in str(hy["H15a"].get("p_note", "")) else ""
        # S2: what the adjusted values would be with all five hypotheses counted (the two without a test taken last), and two-sided for H14
        p = f["p"]
        five = {}
        run = 0.0
        for i, k in enumerate(sorted(("H14", "H15a"), key=lambda k: p[k])):
            run = max(run, min(1.0, (5 - i) * p[k]))
            five[k] = run
        two14 = min(1.0, 2.0 * p["H14"])
        two = {}
        run = 0.0
        p2 = {"H14": two14, "H15a": p["H15a"], "H10": p["H10"]}
        for i, k in enumerate(sorted(p2, key=lambda k: p2[k])):
            run = max(run, min(1.0, (3 - i) * p2[k]))
            two[k] = run
        check(all(v <= f["alpha"] for v in five.values()) and two["H14"] <= f["alpha"],
              "counting all five hypotheses in Holm's step, or taking H14's sign test two-sided, changes no verdict (4.1)")
        if kind == "design":
            return (f"The confirmatory family of [67] is its H9, H10, H13, H14 and H15a, of which the first two are written H9&prime; and H10&prime; here. "
                    f"Holm's step-down procedure at a level of {num(f['alpha'], 2)} is applied over the {words(len(f['tested']))} of them that have a sampling "
                    f"test, H10&prime;, H14 and H15a. That reduction is ours, made after the results: the registration says only that the five are "
                    f"confirmatory, with Holm. H9&prime; compares a value with a threshold and H13 is a calculation, so neither has a p-value. In the family H14 "
                    f"is {sv(rej['H14'])} (adjusted p = {pval(adj['H14'])}), H15a is {sv(rej['H15a'])} (adjusted p {bound}{pval(adj['H15a'])}) and H10&prime; is "
                    f"{sv(rej['H10'])}{' as a whole' if not rej['H10'] else ''} (adjusted p = {pval(adj['H10'])}); H10&prime; and H15a are the companion paper's "
                    f"[61]. With all five counted and the two without a test taken last, the adjusted values would be {bound}{pval(five['H15a'])} for H15a "
                    f"and {pval(five['H14'])} for H14, and no verdict changes. H11 and H12 are exploratory and outside the family.")
        if kind == "h9":
            c9, k9 = hy["H9"]["clauses"], f["k9"]
            return (f"H9&prime; is a comparison with a threshold and has no sampling test; at today's fleet its first clause holds in "
                    f"{share_words(c9[k9[0]]['seeds_on_predicted_side'], 'seed')}, its second in {share_words(c9[k9[1]]['seeds_on_predicted_side'], 'seed')} "
                    f"under the analysis's reading, and its third in {share_words(c9[k9[2]]['seeds_on_predicted_side'], 'seed')}.")
        if kind == "h13":
            c13 = hy["H13"]["clauses"]
            both = min(_fin(c13["1 Hz"]["draws_on_predicted_side"]), _fin(c13["10 Hz"]["draws_on_predicted_side"]))
            return (f"It has no sampling test, and the family's file shows why: the value is on the same side of the threshold in "
                    f"{share_words(both, 'draw')} at both rates, because it is the same sum in every draw.")
        if kind == "h14":
            h = hy["H14"]
            return (f"For the confirmatory family the difference is tested by an exact one-sided sign test on lost jobs per seed, added after the results: "
                    f"fewer with the rule in {cnt(h['seeds_fewer'])} seeds, more in {'none' if int(h['seeds_more']) == 0 else cnt(h['seeds_more'])} and tied in "
                    f"{cnt(h['seeds_tied'])}, p = {pval(f['p']['H14'])}, and {pval(adj['H14'])} after Holm's adjustment, {'below' if rej['H14'] else 'above'} the "
                    f"level of {num(f['alpha'], 2)}; two-sided the same test gives {pval(two14)}, and {pval(two['H14'])} after the adjustment.")
        if kind == "limit":
            return (f"Holm's step covers only the {words(len(f['tested']))} hypotheses of the second registration's confirmatory family that have a sampling "
                    f"test, a reduction made after the results. H9&prime; is a comparison with a threshold, reported by seeds, and H13 is a calculation; "
                    f"neither carries an error rate. H10&prime;, which is {sv(rej['H10'])}{' as a whole' if not rej['H10'] else ''}, and H15a are reported in the "
                    f"companion paper [61]. The p-value of H14 comes from a one-sided sign test that was added for the family after the results were in "
                    f"(Section 4.6).")
        if kind == "pta14":
            return f"Holm-adjusted p = {pval(adj['H14'])} over the family's {words(len(f['tested']))} tested hypotheses, by an exact one-sided sign test over seeds"
        raise KeyError(kind)
    for kind, key in (("design", "P3-FAMILY-SENTENCE"), ("h9", "P3-FAMILY-H9-SENTENCE"), ("h13", "P3-FAMILY-H13-SENTENCE"), ("h14", "P3-FAMILY-H14-SENTENCE"),
                      ("limit", "P3-FAMILY-LIMIT-SENTENCE")):
        fill(key, lambda kind=kind: family_sentence(kind), "phase6_family.json")

    def vv6_rows():
        """The Phase 6 verification rows tagged to this paper, after the summary is recounted and every passed flag recomputed (as vv5_load does)."""
        d = {k: r.p6("VV6", k) for k in ("rows", "summary", "commit")}
        allr, s = d["rows"], d["summary"]
        ran = [x for x in allr if not x.get("skipped")]
        check(int(s["rows"]) == len(allr) and int(s["passed"]) == sum(1 for x in ran if x.get("passed")) and
              int(s["failed"]) == sum(1 for x in ran if not x.get("passed")) and int(s["skipped"]) == len(allr) - len(ran),
              "vv_phase6.json: the summary's counts equal the rows")
        for x in ran:
            tol, err = x.get("tolerance"), (x.get("rel_error") if x.get("mode") == "rel" else x.get("error"))
            if tol is not None and err is not None:
                check(bool(x.get("passed")) == (abs(float(err)) <= float(tol)), f"Phase 6 check {x.get('id')} {x.get('sub')}: the passed flag agrees with its error and tolerance")
        rows = [x for x in allr if "P3" in (x.get("papers") or [])]
        if not rows:
            raise Pending("no check in results/vv_phase6.json is tagged P3")
        return d, rows

    def vv6_sentence(kind):
        d, rows = vv6_rows()
        ids = {str(x["id"]) for x in rows}
        check(ids <= {"P1", "P2", "P3", "P4", "P5", "P6", "P7", "M1", "M2", "M3", "M4", "M5", "C1", "C2", "C3", "C7", "G1", "G2", "G3"} and
              {"P4", "M2", "M4", "C2", "C3", "C7", "G1"} <= ids, "the Phase 6 checks tagged P3 are the positioning, time, map, link and degenerate-case rows (3.10)")
        check(all(x.get("kind") == "V" for x in rows), "the Phase 6 checks tagged P3 are all verifications (3.10)")
        tech = {}
        for x in rows:
            tech[x.get("technique", "unstated")] = tech.get(x.get("technique", "unstated"), 0) + 1
        tech_txt = ", ".join(f"{html.escape(str(k))} ({cnt(v)})" for k, v in sorted(tech.items(), key=lambda kv: (-kv[1], str(kv[0]))))
        g1 = [x for x in rows if x["id"] == "G1" and str(x.get("sub")) == "options off"]
        g1on = [x for x in rows if x["id"] == "G1" and str(x.get("sub")).startswith("option on")]
        if len(g1) != 1 or len(g1on) != 1:
            raise KeyError(f"vv_phase6.json: {len(g1)} rows G1 'options off' and {len(g1on)} rows G1 'option on' tagged P3")
        m = re.search(r"(\d+) days?, seed (\d+): (\d+) summary values against .*\(commit ([0-9a-f]{7})\)", str(g1[0].get("basis", "")))
        mo = re.search(r"(\d+) of (\d+) summary values differ", str(g1on[0].get("basis", "")))
        check(bool(m) and bool(mo) and str(g1[0].get("unit")) == "summary values differing" and bool(g1on[0].get("passed")) and
              os.path.exists(os.path.join(RES, f"vv6_g1_reference_{m.group(4) if m else ''}.json")),
              "the options-off row compares one run's summary values with a stored run of the code before the revision, and a second row shows that an option switched on changes them")
        n_days, n_cmp, g1_commit, n_diff = int(m.group(1)), int(m.group(3)), m.group(4), int(round(_fin(g1[0]["simulated"])))
        n_on = int(mo.group(1))
        check(int(mo.group(2)) == n_cmp and n_on > 0, "the option-on row is over the same summary values and changes some of them")
        g1_scope = (f"one scenario, one seed and {cnt(n_days)} days, {cnt(n_cmp)} summary values, against a stored run of the code before the revision "
                    f"(commit <code>{g1_commit}</code>)")
        if kind == "design":
            commit = str(d.get("commit") or "")
            return (f"The revision has its own suite (<code>lunarsim/vv6.py</code>, results in <code>results/vv_phase6.json</code>): {cnt(len(rows))} of its rows bear "
                    f"on this paper, all verifications that the code does what the derivations say, by Sargent's technique {tech_txt}. They are one row per formula "
                    f"behind Appendix A and Sections 3.5 to 3.8, the growth of dead-reckoning error, the dilution of precision, the lunar clock rate and the clock "
                    f"model's constant, range from clock error, holdover, the coordinate round trip, the frame shift, the map projection, the hash-tree bound, the "
                    f"link budget's worked example, the radio horizon, the rate at the worst hop and the forgery rate of a short code, and three degenerate "
                    f"cases: every engine option of the revision off ({g1_scope}), with a row that shows the comparison can fail, perfect clocks, and the "
                    f"perfect layer set" + (f"; they ran at commit <code>{html.escape(commit[:7])}</code>" if commit else "") + ". That comparison was "
                    f"rebuilt after a code review on 13 November 2026: before, it compared the default run with itself.")
        bad = [x for x in rows if not x.get("skipped") and not x.get("passed")]
        skipped = [x for x in rows if x.get("skipped")]
        head = (f"Every one of the {cnt(len(rows))} checks of the revision's suite tagged to this paper passed" if not bad and not skipped else
                f"Of the {cnt(len(rows))} checks of the revision's suite tagged to this paper, {cnt(len(bad))} failed "
                f"({'; '.join(html.escape(str(x['id']) + ' ' + str(x.get('name', ''))) for x in bad)}) and {cnt(len(skipped))} were not run")
        return (head + f". With every engine option of the revision off, {'none' if n_diff == 0 else cnt(n_diff)} of the summary values compared "
                f"{'differs' if n_diff <= 1 else 'differ'} from the earlier code's run, within this scope: {g1_scope}; with one option switched on, "
                f"{cnt(n_on)} of the {cnt(n_cmp)} differ, so the comparison can fail. It is not a statement that the revision leaves the engine unchanged in general.")
    fill("P3-CHECKS6-SENTENCE", lambda: vv6_sentence("design"), "vv_phase6.json (B-98)")
    fill("P3-CHECKS6-OUTCOME-SENTENCE", lambda: vv6_sentence("outcome"), "vv_phase6.json (B-98)")

    # <<P6-NEXT>>
    return T6




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

    def fill_await(key, fn: Callable[[], str], plain: str, task: str):
        """A key whose result a named BACKEND task will deliver (referee round of 11 Nov 2026, decision A4: no pending marker may
        print). While the file or the field is absent (fn raises Pending) the key is `plain`, one sentence that says what is not in and
        where it will go; the build lists it under "awaited". When the data are there and the composing function is not (fn raises
        Landed), the build stops, so that a result that has landed is never reported as missing; --allow-pending builds a draft."""
        try:
            V[key] = fn()
        except Pending as e:
            AWAITED.append(f"{key}: awaits {task} ({e})")
            V[key] = plain
        except Landed as e:
            if not allow_pending:
                raise SystemExit(f"{key}: {e}; write its composing function in build_p3.py (PLACEHOLDERS.md, 'Awaited keys')")
            AWAITED.append(f"{key}: LANDED, composer not written ({e})")
            V[key] = plain

    def landed(what, getter):
        """For an awaited block whose schema is not known yet: Pending while it is absent, Landed once it is there."""
        getter()
        raise Landed(f"{what} is now in its results file")

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
    fz = los["2.5-2.5"]["2-5 km"]
    check(fz["fresnel_0.6_400MHz"] < fz["fresnel_0.6_2.4GHz"] < fz["los_0m"] and "Fresnel = first-zone ratio >= 0.6" in str(m["note"]),
          "fewer pairs keep 0.6 of the first Fresnel zone clear than have bare line of sight, and fewer still at 400 MHz (3.3, 6.3)")
    V["P3-MESH-FRESNEL-SENTENCE"] = (f"A stricter test is in the same file and is not used by the mesh: with 0.6 of the first Fresnel zone clear at the worst "
                                     f"point, the share for two rover antennas at 2&ndash;5{NB}km falls to {pc(fz['fresnel_0.6_2.4GHz'], 1)} at 2.4{NB}GHz and to "
                                     f"{pc(fz['fresnel_0.6_400MHz'], 1)} at 400{NB}MHz, where the zone is wider (Assumed threshold).")
    V["P3-MESH-FRESNEL-CLAUSE"] = (f"only {pc(fz['fresnel_0.6_400MHz'], 1)} of rover pairs at 2&ndash;5{NB}km keep 0.6 of the first Fresnel zone clear at "
                                   f"400{NB}MHz, against {pc(fz['fresnel_0.6_2.4GHz'], 1)} at 2.4{NB}GHz")
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

    # --- the Assumed defaults of the code (3.3, 3.4, 3.9) ----------------------------------------------------------
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

    # --- checks (3.10, 5.14) -------------------------------------------------------------------------------------------
    fill("P3-CHECKS-SENTENCE", lambda: vv5_checks_sentence("P3", "5.14", check, exclude=OWN_CHECK_IDS), "B-79")
    fill("P3-FAILED-CHECKS-SENTENCE", lambda: vv5_failed_sentence("P3", "3.10", check), "B-79")
    fill("P3-ID-FIX-SENTENCE", lambda: idfix_sentence(check, ("E46", "E48")), "B-79 id fix")

    # --- E48 -----------------------------------------------------------------------------------------------------------
    def dr_seeds(xs):
        xs = [int(x) for x in xs]
        return f"{xs[0]}&ndash;{xs[-1]}" if xs == list(range(xs[0], xs[-1] + 1)) else ", ".join(str(x) for x in xs)

    KBPS = NB + "kbit/s"
    _air: Dict[str, Any] = {}

    def e48_air():
        """B-89 (PREREG change 11): the authenticated load of the target fleet and the channel rate it needs on one shared
        channel (E48 `messages.secured`, `airtime`, `h10`). Every direction word about the 16 kbit/s link comes from here:
        `sched` is the base-scheduled channel at the measured mean hop count, `rand` slotted random access at the same hop
        count, `two` the scheduled channel with every report relayed two hops, `one` the scheduled channel at exactly one hop."""
        if _air:
            return _air
        tg = r.s48("targets")
        robots, target = int(tg["robots"]), _fin(tg["link_kbps_20_robots"])
        sec, air, h10 = r.s48("messages", "secured"), r.s48("airtime"), r.s48("h10")
        bph = {m: _fin(_get(sec, "bytes_per_robot_hour", "1", m)) for m in ("mac8", "mac16")}
        load = {m: bph[m] * robots * 8 / 3600.0 / 1000.0 for m in bph}
        for m in bph:
            check(abs(load[m] - _fin(_get(h10, f"link_kbps_needed_20_robots_secured_{m}"))) < 0.006,
                  f"the secured load of the target fleet ({m}) is bytes per robot-hour x robots x 8 / 3600")
        check(int(_get(air, "robots")) == robots and abs(_fin(_get(air, "channel_kbps")) - target) < 1e-9,
              "the airtime block uses H10's robots and link target")
        carries = _get(h10, "carries_20_robots_1hz_on_16_kbps")
        hops = _fin(_get(carries, "hops"))
        month = r.s48("revision", "two_ray_in_the_mesh", "e40_month")
        hist = {int(k): int(v) for k, v in _get(month, "variants", "default", "hop_histogram").items()}
        check(abs(sum(k * v for k, v in hist.items()) / sum(hist.values()) - hops) < 0.001,
              "the mean hop count to the base computer is the mean of the month's hop histogram")
        check(abs(_fin(_get(air, "mean_hops_to_base", "default radio")) - hops) < 1e-9, "one mean hop count in the airtime and h10 blocks")
        dflt = _get(month, "variants", "default")
        cut = _fin(_get(dflt, "robot_epochs_cut_off_share"))
        check(abs(cut - (1 - sum(hist.values()) / _fin(_get(dflt, "robot_epochs_with_base_up")))) < 0.0005,
              "the cut-off share is the robot-epochs with the base computer up that are not in the hop histogram")
        check(hops < float(conn[key]["median_hops"]), "the month's mean hop count is below the median over all route points (5.2 against 3.3)")

        def row(hop, access):
            g = [x for x in _get(air, "rows") if str(x["sizes"]).startswith("LRIP secured, MAC 8") and str(x["access"]).startswith(access)
                 and (str(x["hops"]).startswith("measured") if hop == "measured" else str(x["hops"]) == hop)]
            if len(g) != 1:
                raise Pending(f"airtime row (secured, MAC 8 B, hops {hop}, {access}) missing from the file")
            x = g[0]
            need, eta = _fin(x["channel_kbps_needed"]), _fin(x["eta"])
            check(abs(need - load["mac8"] * (hops if hop == "measured" else float(hop)) / eta) < 0.02,
                  f"airtime ({hop} hops, {access}): the channel rate needed is the load x hops / access efficiency")
            check(bool(x["fits_16_kbps"]) == (need <= target), f"airtime ({hop} hops, {access}): the fits flag agrees with the target")
            return {"need": need, "fits": need <= target, "eta": eta, "access": str(x["access"])}
        _air.update({"robots": robots, "target": target, "load": load["mac8"], "load16": load["mac16"], "bph": bph, "hops": hops,
                     "hist": hist, "month": month, "cut": cut, "sched": row("measured", "scheduled"), "rand": row("measured", "slotted"),
                     "two": row("2", "scheduled"), "one": row("1", "scheduled")})
        check(bool(carries["scheduled"]) == _air["sched"]["fits"] and bool(carries["slotted_aloha"]) == _air["rand"]["fits"],
              "the h10 block's scheduled and random-access flags agree with the airtime rows")
        check(hops < 1.1 and _air["one"]["fits"] == _air["sched"]["fits"],
              "the 'one hop' wording: the measured mean hop count is below 1.1 and the verdict is the same at exactly one hop")
        check(_air["rand"]["eta"] < _air["sched"]["eta"] and "20 % guard" in _air["sched"]["access"] and "1/e" in _air["rand"]["access"],
              "access efficiencies: a scheduled channel with a 20 % guard time and slotted random access at 1/e (4.2)")
        return _air

    def one_hop_basis():
        """What the one-hop condition of the link claim rests on (finding M2, decision B9): the hop count is taken over positions that are
        mostly parked (E50's trace of seed 1, results/E50_errors.csv), while a driving vehicle has a radio path to the base for a smaller
        share of the time (results/E54_dtn.json, link_shares)."""
        path = os.path.join(RES, "E50_errors.csv")
        _need(path, "E50's per-seed error table")
        c = pd.read_csv(path)
        c = c[(c["mult"] == 1) & (c["seed"] == 1) & (c["layer_set"] == "dr")]
        parked, driving = int(c[c["region"] == "parked"]["n_steps"].iloc[0]), int(c[c["region"] == "all"]["n_steps"].iloc[0])
        ls = r.p6("E54", "link_shares")
        drive, allt = _fin(ls["linked_share_driving_time"]), _fin(ls["linked_share_all_time"])
        lo, hi = (_fin(x) for x in ls["linked_share_driving_time_min_max"])
        check(parked / (parked + driving) > 0.95 and drive < allt and lo <= drive <= hi,
              "the positions behind the hop count are mostly parked, and a driving vehicle has a path to the base less often than a vehicle at any time (3.3, 5.2)")
        check("radio path to the BASE mast" in str(ls["note"]) and int(ls["seeds"]) == len(r.p6("E54", "seeds")), "E54's link shares are of vehicle-steps with a radio path to the base mast, over its seeds")
        return {"parked": parked, "driving": driving, "parked_share": parked / (parked + driving), "drive": drive, "all": allt, "lo": lo, "hi": hi}

    def side(x, target_word="it"):
        """'within' / 'above' the link target, from the row."""
        return ("within " if x["fits"] else "above ") + target_word

    def link_text(a, form):
        """The link claim, one wording per place. Since the referee round it is conditional: the traffic would need this much of a
        base-scheduled channel if every robot were within one hop of the base, and the basis of that condition is stated beside it."""
        T = f"{num(a['target'], 0)}{KBPS}"
        s_, r_, t_ = a["sched"], a["rand"], a["two"]
        k = lambda x: num(x["need"], 2)
        ob = one_hop_basis()
        both_over = (not r_["fits"]) and (not t_["fits"])
        if form == "short":       # the abstract
            return (f"would need {k(s_)}{KBPS} of a base-scheduled channel if every robot were within one hop of the base; a driving robot has "
                    f"a path to it {pc(ob['drive'], 0)} of the time")
        if form == "concl":       # the conclusion
            return (f"{'fits' if s_['fits'] else 'does not fit'} the {T} link {'only ' if both_over and s_['fits'] else ''}on a base-scheduled channel with "
                    f"every robot one hop from the base, which holds at sites and not on the road")
        if form == "long":        # introduction, discussion
            other = (f"{k(r_)}{KBPS} on slotted random access and {k(t_)}{KBPS} if every report were relayed two hops, "
                     + ("both above it" if both_over else f"{side(r_)} and {side(t_)} respectively"))
            return (f"would need {k(s_)}{KBPS} of a channel that the base schedules if every robot were within one hop of the base, "
                    f"{side(s_, 'the ' + T + ' target')}, and {other}. The one-hop condition is taken from positions that are parked in "
                    f"{pc(ob['parked_share'], 0)} of vehicle-steps; a driving vehicle has a radio path to the base {pc(ob['drive'], 1)} of the time, so the "
                    f"condition holds for robots standing at sites and not for a fleet on the move")
        raise KeyError(form)

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
        check(abs(out["kbps_20"] - _fin(r.s48("h10", "link_kbps_needed_20_robots"))) < 0.006, "the unsecured load of the target fleet agrees with the h10 block")
        # the processor and the memory only: the link is no longer one yes or no (PREREG change 11), its three cases are in `air`
        out["fits"] = {"cpu": worst_cpu < 1.0, "memory": out["mem_worst_mb"] <= out["mem_capacity_mb"]}     # memory is not scaled by the speed factor
        out["air"] = e48_air()
        return out

    _b105: Dict[str, Any] = {}

    def b105():
        """Task B-105 (results/E48_sizing.json, blocks `per_robot_round` and `measured_memory`): one robot's bid computation in one auction
        round and the memory the on-robot parts allocate, each from one 30-day month of one seed per fleet multiple, on the laptop; the
        times are scaled by the same assumed factor as the safety check. A measurement on a laptop, not on flight hardware."""
        if _b105:
            return _b105
        pr, mm_ = r.s48("per_robot_round"), r.s48("measured_memory")
        f = _fin(r.s48("flight", "factor"))
        flo, fhi = (_fin(x) for x in r.s48("flight", "factor_range"))
        t = {}
        for m, x in pr["laptop_ms_by_multiple"].items():
            check(abs(_fin(x["p99_ms"]) * f - _fin(x["flight_p99_ms"])) < 0.6 and abs(_fin(x["median_ms"]) * f - _fin(x["flight_median_ms"])) < 0.06 and
                  abs(_fin(x["p99_ms"]) * flo - _fin(x["flight_p99_ms_range"][0])) < 0.6 and abs(_fin(x["p99_ms"]) * fhi - _fin(x["flight_p99_ms_range"][1])) < 0.6 and
                  int(x["days"]) == 30, f"one robot's bid time at {m} times the fleet is the laptop time times the flight factor, from a 30-day month (5.1)")
            tp = pr["timing_passes"]["by_multiple"][m]
            ps = [_fin(v) / 1000.0 for v in tp["flight_p99_ms_by_pass"]]
            plo, phi = (_fin(v) / 1000.0 for v in tp["flight_p99_ms_over_passes_and_factor_range"])
            central = "inside" if max(ps) <= 1.0 else ("above" if min(ps) > 1.0 else "straddling")
            over = "inside" if phi <= 1.0 else ("above" if plo > 1.0 else "straddling")
            check(bool(x.get("timed_without_tracemalloc")) and len(ps) == 3 and abs(ps[0] - _fin(x["flight_p99_ms"]) / 1000.0) < 1e-3 and
                  abs(plo - min(_fin(v) for v in tp["laptop_p99_ms_by_pass"]) * flo / 1000.0) < 1e-3 and abs(phi - max(_fin(v) for v in tp["laptop_p99_ms_by_pass"]) * fhi / 1000.0) < 1e-3 and
                  central == str(tp["against_1s_at_central_factor"]) and over == str(tp["against_1s_over_passes_and_factor_range"]),
                  f"one robot's bid time at {m} times the fleet: three passes timed without the memory tracer, and the file's verdicts against one second follow from them (5.1)")
            t[m] = {"p99": _fin(x["flight_p99_ms"]) / 1000.0, "med": _fin(x["flight_median_ms"]), "lo": plo, "hi": phi, "passes": ps, "central": central, "over": over,
                    "n": int(x["n"]), "free": _fin(x["robots_per_round_mean"]), "robots": int(x["robots"]), "fits": central == "inside"}
        old = r.s48("superseded_2026-11-13_b118_n12", "per_robot_round", "laptop_ms_by_multiple")
        check("tracemalloc" in str(r.s48("superseded_2026-11-13_b118_n12", "reason")), "the earlier per-robot times were superseded because the memory tracer ran during one round in twenty (5.1)")
        check(list(t) == ["1", "4", "8"] and "seed 1" in str(pr["revision"]) and "ONE robot's bid computation" in str(pr["revision"]),
              "the per-robot timing is of one robot's bid computation, seed 1, at one, four and eight times the fleet (5.1)")
        whole = _fin(pr["whole_fleet_dispatch_call_ms_pooled"]["p99"]) * f / 1000.0
        mem = {}
        for m, x in mm_["mb_by_multiple"].items():
            mem[m] = {"all": _fin(x["all_at_once_peak"]), "policy": _fin(x["bid_policy"]["peak"]), "plus": _fin(x["all_at_once_plus_planner_p99"]),
                      "rest": _fin(x["safety_check_peak"]) + _fin(x["reservation_window_24h"]["peak"]) + _fin(x["ledger_month"]["peak"]) + _fin(x["planner_working_peak_p99"]),
                      "ws": _fin(x["process_peak_working_set_mb"])}
        est = _fin(mm_["estimate_mb_for_comparison"])
        check(all(x in str(mm_["revision"]) for x in ("tracemalloc", "interpreter, the code and numpy buffers", "do not use it")) and
              abs(est - _fin(r.s48("classes", "LTV1", "peak_memory_mb"))) < 1e-9 and max(v["plus"] for v in mem.values()) < est,
              "the measured memory is tracemalloc peaks of the on-robot parts, without the interpreter, the code and numpy buffers, and below the estimate (5.1)")
        check(all(v["policy"] > 0.8 * v["all"] for v in mem.values()), "most of the measured peak is the learned bid policy (5.1)")
        _b105.update({"t": t, "whole": whole, "mem": mem, "est": est, "f": f, "old": {m: _fin(v["flight_p99_ms"]) / 1000.0 for m, v in old.items()}})
        return _b105

    def b105_round():
        """5.1: one robot's bid computation per fleet size, three passes timed without the memory tracer (corrected after the code review of
        13 Nov 2026, finding N12). The verdict against the one-second decision is the file's: inside, above or straddling."""
        b = b105()
        t = b["t"]
        MN = {"1": "today's fleet", "4": "four times the fleet", "8": "eight times the fleet"}
        check(abs(b["whole"] - max(max(t[m]["passes"]) for m in t)) < 0.25, "the pooled whole-fleet call is of the size of one robot's 99th percentile at the larger fleets (5.1)")
        over_old = [m for m in ("1", "4", "8") if b["old"][m] > 1.0]
        check(over_old == ["4", "8"], "the superseded per-robot times were above one second at four and eight times the fleet and under it at today's fleet, as the correction sentence says (5.1)")
        old_words = ("and the last two were above one second" if over_old == ["4", "8"] else
                     ("none of them above one second" if not over_old else "of which those at " + " and ".join(MN[m] for m in over_old) + " were above one second"))
        VW = {"inside": "under one second in every pass and over the whole range of the scaling factor",
              "straddling": "under one second in every pass at the central factor and over it only towards the top of the factor's range",
              "above": "over one second in every pass"}
        key = lambda m: t[m]["central"] if t[m]["central"] != "inside" else t[m]["over"]
        groups = {}
        for m in t:
            groups.setdefault(key(m), []).append(MN[m])
        verdict = "; ".join(f"at {' and '.join(v)} it is {VW[k]}" for k, v in groups.items())
        return (f"One robot's own bid computation in an auction round, its loop over the waiting items, was then timed apart from the simulator's round, "
                f"in one 30-day month of one seed per fleet size, three passes each with no memory tracer running, and scaled by the same assumed "
                f"factor. At the 99th percentile the three passes give "
                + "; ".join(f"{', '.join(num(v, 2) for v in t[m]['passes'][:-1])} and {unit(t[m]['passes'][-1], 's', 2)} at {MN[m]} ({num(t[m]['lo'], 2)} to "
                            f"{num(t[m]['hi'], 2)} over the passes and the factor's range; {cnt(t[m]['n'])} robot-rounds, {num(t[m]['free'], 1)} free robots a "
                            f"round)" for m in t) +
                f", and {num(min(t[m]['med'] for m in t), 0)} to {unit(max(t[m]['med'] for m in t), 'ms', 0)} at the median. Against the one-second "
                f"decision: {verdict}. These times were corrected after a code review on 13 November 2026, which found that one round in twenty had been "
                f"timed with the memory tracer running: before, the figures were {num(b['old']['1'], 2)}, {num(b['old']['4'], 2)} and "
                f"{unit(b['old']['8'], 's', 2)}, {old_words}. The slow rounds are those with many waiting items, "
                f"each of which the robot tries to insert into its plan; a cap on the items a robot evaluates in a round would bound the time and is "
                f"not in the design. The whole-fleet figure above is of the same size as one robot's 99th percentile at the larger fleets. This is a "
                f"laptop timing of Python scaled by an assumed factor, on one seed, with a spread between passes of the size shown, not a measurement "
                f"on flight hardware.")

    def b105_memory():
        b = b105()
        mem = b["mem"]
        lo, hi = min(v["all"] for v in mem.values()), max(v["all"] for v in mem.values())
        return (f"The memory was also measured, as the bytes the interpreter allocates for the on-robot parts on one robot's view of a 30-day month of "
                f"one seed: the planner's working memory during a bid, one safety check, the reservation entries of the next 24 hours, the month's "
                f"ledger records and the loaded bid policy, all held at once. The peak is {num(lo, 2)} to {unit(hi, 'MB', 2)} over the three fleet sizes "
                f"({num(max(v['plus'] for v in mem.values()), 2)}{NB}MB with the planner's working memory at its 99th percentile added), against the estimate of "
                f"{unit(b['est'], 'MB', 2)}; {num(min(v['policy'] for v in mem.values()), 2)}{NB}MB of it is the learned bid "
                f"policy, which the default auction does not use, and the other parts together peak at {num(min(v['rest'] for v in mem.values()), 2)} to "
                f"{unit(max(v['rest'] for v in mem.values()), 'MB', 2)}. Not counted are the interpreter, the code and the buffers of the numerical library; "
                f"the whole process holds {num(max(v['ws'] for v in mem.values()), 0)}{NB}MB, nearly all of it interpreter and simulator. It is a laptop "
                f"measurement of a Python implementation, not of flight software.")

    def h10_sentence():
        s = e48_scaled()
        a = s["air"]
        fits = dict(s["fits"])
        mk = r.s48("h10", "market_mb_per_day")
        fits["market"] = _fin(mk) <= _fin(r.s48("targets", "market_mb_per_day"))
        T = f"{num(a['target'], 0)}{KBPS}"
        ob = one_hop_basis()
        b5 = b105()
        w = lambda ok: "within" if ok else "above"
        return (f"H10 of [59], exploratory, is reported count by count. The processor: the safety check takes {num(s['cpu_share_worst'] * 100, 1)}{PCT} of "
                f"one core of the reference processor at 10{NB}Hz, {w(fits['cpu'])} it. The memory: the on-robot data are estimated at "
                f"{unit(s['mem_worst_mb'], 'MB', 1)} and measured on the laptop at {num(max(v['all'] for v in b5['mem'].values()), 2)}{NB}MB at most, of "
                f"{unit(s['mem_capacity_mb'], 'MB')}. The market's messages: {unit(mk, 'MB', 3)} a day, {w(fits['market'])} "
                f"the {unit(r.s48('targets', 'market_mb_per_day'), 'MB')} target. The link: the authenticated radio traffic of {cnt(a['robots'])} robots, "
                f"{num(a['load'], 2)}{KBPS} at the sources, would need {num(a['sched']['need'], 2)}{KBPS} of a channel the base schedules if every robot were "
                f"within one hop of the base ({side(a['sched'], 'the ' + T + ' target')}), {num(a['rand']['need'], 2)}{KBPS} on slotted random access "
                f"({side(a['rand'])}) and {num(a['two']['need'], 2)}{KBPS} if every report were relayed two hops ({side(a['two'])}); the one-hop condition "
                f"holds for robots standing at sites, and a driving robot has a path to the base {pc(ob['drive'], 1)} of the time (Section 5.2). The scaling "
                f"factor is {num(s['factor'], 1)} (range {num(s['range'][0], 1)}&ndash;{num(s['range'][1], 1)}). The bidding, which H10 also names, has no "
                f"registered capacity; against the one-second decision of this design one robot's bid computation, scaled, "
                f"{'stays under it at the central factor at every fleet size' if all(v['fits'] for v in b5['t'].values()) else 'does not stay under it at every fleet size'} "
                f"at the 99th percentile, and {'passes it only at the top of the factor range at four and eight times the fleet' if b5['t']['1']['over'] == 'inside' and b5['t']['4']['over'] == b5['t']['8']['over'] == 'straddling' else 'the factor range changes that at some fleet sizes'} "
                f"(Section 5.1).")
    fill("P3-H10-VERDICT-SENTENCE", h10_sentence, "E48")

    def e48_round():
        """5.1: what was timed for the auction is the simulator's dispatch call for the whole fleet, pooled over the fleet sizes
        (tools/atc/run_e48.py: `mech(sim, cand, free)` in every timing run); it is not one vehicle's computation (finding M1, decision B11)."""
        s = e48_scaled()
        a = r.s48("classes", "LTV1", "cpu_auction_round_ms")
        check(all(r.s48("classes", c, "cpu_auction_round_ms") == a for c in CLASSES), "the dispatch-call timing is one pooled figure, repeated in every class row of the file (5.1)")
        ru = r.s48("runs")
        check(list(ru["multiples"]) == [1, 4, 8], "the dispatch call is timed in the runs at one, four and eight times the fleet (5.1)")
        med, p99 = _fin(a["median"]) * s["factor"] / 1000.0, _fin(a["p99"]) * s["factor"] / 1000.0
        over = p99 > 1.0
        return (f"What was timed for the auction is the simulator's dispatch call for the whole fleet: every free vehicle and every waiting item, with "
                f"the simulator's own model of the message exchange, {cnt(a['n'])} calls pooled over the timing runs at one, four and eight times the fleet. "
                f"Scaled by the same factor it takes {unit(med, 's', 2)} at the median and {unit(p99, 's', 2)} at the 99th percentile, "
                f"{'above' if over else 'within'} the one-second decision that the link model of Section 5.3 assumes; the results file does not split it by "
                f"fleet size. No single vehicle executes that call.")
    fill("P3-E48-ROUND-SENTENCE", e48_round, "E48")
    fill("P3-E48-MEMORY-SENTENCE", lambda: b105_memory(), "E48 measured_memory (B-105)")
    fill("P3-E48-ROBOT-ROUND-SENTENCE", lambda: b105_round(), "E48 per_robot_round (B-105)")
    def e48_spherical():
        """5.3: the spherical-ground column (task B-104, results/E48_sizing.json block `revision_b104`): a calculation with ITU-R P.526
        section 3.2, and which verdicts it moves."""
        m14 = referee_m14(r, check)
        r1 = m14["range_1m"]
        lt = m14["lk"]["LTV1"]
        check(r1[0] < _fin(lt["longest_hop_m"]) <= r1[1] + 1.0, "over a spherical ground the rovers' 1 Mbit/s range is shorter than their longest hop; over flat ground it reaches the horizon")
        return (f"The flat-ground law is used here at hops close to the horizon, where the ground is not flat on the scale of the antennas. A "
                f"calculation over a spherical ground, the smooth-sphere method of ITU-R P.526 section 3.2 [20] with the Moon's radius and no atmosphere, "
                f"checked against the Recommendation's text, gives at the longest hop of each class {unit(m14['loss']['LTV1'][0], 'dB', 1)} against "
                f"{unit(m14['loss']['LTV1'][1], 'dB', 1)} for the crew and cargo rovers, {unit(m14['loss']['SMALL'][0], 'dB', 1)} against "
                f"{unit(m14['loss']['SMALL'][1], 'dB', 1)} for the small rover and the hopper, and {unit(m14['loss']['BASE'][0], 'dB', 1)} against "
                f"{unit(m14['loss']['BASE'][1], 'dB', 1)} for the mast's downlink; the rates become {m14['rates_txt']}. One verdict moves: over a spherical "
                f"ground the rovers' {unit(_fin(lt['longest_hop_m']) / 1000.0, 'km', 0)} hop no longer carries 1{NB}Mbit/s, and their range at that rate "
                f"falls from {unit(r1[1] / 1000.0, 'km', 2)}, the horizon, to {unit(r1[0] / 1000.0, 'km', 2)}. The others do not: every class still carries the "
                f"{num(m14['airtime'], 2)}{KBPS} of the fleet's scheduled airtime and 16{KBPS} at its longest hop, the mast-reach shares are unchanged, and "
                f"the small rover and the hopper did not reach 1{NB}Mbit/s under either law. This is a calculation on assumed radio constants; no path "
                f"loss has been measured on the Moon.")
    fill("P3-E48-SPHERICAL-SENTENCE", e48_spherical, "E48 revision_b104 (B-104)")

    def e53_driving():
        """5.2: hops and reach for driving vehicles (task B-103, results/E53_bitrate.json block `driving_split`): a calculation on drawn
        positions, and the load with all three reports at 1 Hz."""
        ds = r.p6("E53", "driving_split")
        mo, e = ds["e40_month"], ds["e53_auth_20_rovers"]
        a = e48_air()
        check(abs(_fin(mo["check_against_E48"]["all_mean_hops"]) - a["hops"]) < 1e-9 and int(mo["all"]["robot_epochs"]) == int(mo["check_against_E48"]["E48_robot_epochs"]),
              "the driving split reproduces E48's month: the same robot-epochs and the same mean hop count (5.2)")
        d2 = r.p6("E53", "lrip_v02", "driving_split")          # the same split at the packet sizes of protocol version 0.2 (task B-110)
        e2, f2 = d2["e53_auth_20_rovers"]["lrip"], d2["e53_auth_20_rovers"]["proximity1"]
        for k_ in ("fleet_driving", "fleet_parked"):
            check(abs(_fin(e2[k_]["1 Hz"]["mean_hops_to_base"]) - _fin(e[k_]["1 Hz"]["mean_hops_to_base"])) < 1e-9 and
                  abs(_fin(e2[k_]["1 Hz"]["reachable_share"]) - _fin(e[k_]["1 Hz"]["reachable_share"])) < 1e-9 and
                  _fin(e2[k_]["1 Hz"]["busiest_link_kbps_p95"]) > _fin(e[k_]["1 Hz"]["busiest_link_kbps_p95"]),
                  f"{k_}: hops and reach do not depend on the protocol version, and the busiest link carries more with version 0.2's heartbeat (5.2)")
        check("v0.2 packet sizes" in str(d2["note"]) and "12 B per packet" in str(d2["note"]) and abs(_fin(d2["pool_driving_share"]) - _fin(ds["pool_driving_share"])) < 1e-9,
              "the version 0.2 split uses the same pool of driving steps, v0.2 packet sizes and 12 B of Proximity-1 framing (5.2)")
        dr, pk = e2["fleet_driving"]["1 Hz"], e2["fleet_parked"]["1 Hz"]
        drf = f2["fleet_driving"]["1 Hz"]
        T = a["target"]
        w = lambda x: "within" if _fin(x) <= T else "above"
        check(_fin(dr["mean_hops_to_base"]) > _fin(pk["mean_hops_to_base"]) and _fin(dr["busiest_link_kbps_p95"]) < _fin(pk["busiest_link_kbps_p95"]) and
              _fin(dr["reachable_share"]) < _fin(pk["reachable_share"]),
              "drawn from driving steps the rovers need more hops, reach the base less often and load the busiest link less than drawn from parked steps (5.2)")
        si2, sif = d2["status_intent_at_1hz"]["lrip"], d2["status_intent_at_1hz"]["proximity1"]
        si = ds["status_intent_at_1hz"]
        check(abs(_fin(si2["three_beacons_20_rovers_kbps"]) - _fin(si["three_beacons_20_rovers_kbps"])) < 1e-9 and _fin(si2["sources_20_rovers_kbps"]) > _fin(si2["three_beacons_20_rovers_kbps"]),
              "with all three reports at 1 Hz the three reports weigh the same in both versions and version 0.2 adds the heartbeat (5.2)")
        allair = [_fin(x["busiest_link_20_rovers"][g]["scheduled_airtime_p95_kbps"]) for x in (si2, sif) for g in ("fleet", "fleet_driving")]
        ob = one_hop_basis()
        check(abs(_fin(ds["e54_link_shares_30_seeds"]["linked_share_driving_time"]) - ob["drive"]) < 1e-9, "the driving split quotes E54's share of driving time with a path (5.2)")
        check(abs(_fin(si["three_beacons_20_rovers_kbps"]) - sum(int(v) for v in si["bytes_position_status_intent_auth"].values()) * a["robots"] * 8 / 1000.0) < 0.006,
              "the load with all three reports at 1 Hz is the sum of the three serialised sizes times the fleet (5.2)")
        n_dr, n_all = int(mo["driving"]["robot_epochs"]), int(mo["all"]["robot_epochs"])
        return (f"A further calculation splits these figures by driving and parked positions. Of the {cnt(n_all)} robot-epochs behind the mean hop count, "
                f"{cnt(n_dr)} are of a driving robot ({pc(n_dr / n_all, 1)}), too few for a driving hop count: the {num(a['hops'], 3)} hops are a figure for "
                f"parked robots. Drawing 20 rovers from the driving steps of the recorded month only ({pc(ds['pool_driving_share'], 1)} of its "
                f"vehicle-steps), with the traffic model's 2.5{NB}m antennas, the rovers that reach the base are {num(dr['mean_hops_to_base'], 2)} hops from "
                f"it on average, against {num(pk['mean_hops_to_base'], 2)} from parked steps; {pc(dr['reachable_share'], 0)} have a path, against "
                f"{pc(pk['reachable_share'], 0)}; and the busiest link carries {num(dr['busiest_link_kbps_p95'], 2)}{KBPS} at the 95th percentile, against "
                f"{num(pk['busiest_link_kbps_p95'], 2)}, because driving rovers are spread along the routes and share fewer neighbourhoods; the loads are at the "
                f"packet sizes of protocol version 0.2 (Section 3.8), and the hops and the share with a path do not depend on the version. As airtime "
                f"that is {num(dr['scheduled_airtime_p95_kbps'], 2)}{KBPS} on a scheduled channel ({num(drf['scheduled_airtime_p95_kbps'], 2)} with every "
                f"packet in a Proximity-1 frame), {w(max(_fin(dr['scheduled_airtime_p95_kbps']), _fin(drf['scheduled_airtime_p95_kbps'])))} the target, and "
                f"{num(dr['slotted_aloha_airtime_p95_kbps'], 1)}{KBPS} on slotted random access ({num(drf['slotted_aloha_airtime_p95_kbps'], 1)} framed), "
                f"{w(min(_fin(dr['slotted_aloha_airtime_p95_kbps']), _fin(drf['slotted_aloha_airtime_p95_kbps'])))} it. The "
                f"{pc(dr['reachable_share'], 0)} is not the {pc(ob['drive'], 1)} above: here 20 rovers with 2.5{NB}m antennas relay for one another, "
                f"there the real fleet of {words(len(r.fleet()))} vehicles, half of them with 1.0{NB}m antennas, drives its recorded routes over 30 seeds. "
                f"With status and intent at 1{NB}Hz as well, the same calculation at version 0.2 sizes gives {num(si2['sources_20_rovers_kbps'], 2)}{KBPS} at the "
                f"sources ({num(sif['sources_20_rovers_kbps'], 2)} framed) and a scheduled airtime of "
                f"{num(si2['busiest_link_20_rovers']['fleet']['scheduled_airtime_p95_kbps'], 1)}{KBPS} at the fleet's positions and "
                f"{num(si2['busiest_link_20_rovers']['fleet_driving']['scheduled_airtime_p95_kbps'], 1)} at driving positions "
                f"({num(sif['busiest_link_20_rovers']['fleet']['scheduled_airtime_p95_kbps'], 1)} and "
                f"{num(sif['busiest_link_20_rovers']['fleet_driving']['scheduled_airtime_p95_kbps'], 1)} framed), "
                f"{'above the target in every case' if min(allair) > T else 'not above the target in every case'}: at those rates the 1{NB}Hz "
                f"case of the link claim does not hold on any channel. The 1.0{NB}m antennas of the small classes and a report rate tied to motion were "
                f"not run.")
    fill("P3-E53-DRIVING-HOPS-SENTENCE", e53_driving, "E53 driving_split (B-103)")

    def e48_reference():
        fl, lp = r.design(48, "flight"), r.design(48, "laptop")
        return (f"The reference flight processor is the {html.escape(fl['processor'])}, at {num(fl['benchmark'], 1)} {html.escape(fl['benchmark_name'])} "
                f"(source: {html.escape(fl['source'].split(';')[0])}) with {unit(fl['memory_mb'], 'MB')} of memory ({html.escape(fl['memory_flag'])}); the laptop "
                f"is an {html.escape(lp['processor'])} at {num(lp['benchmark'], 0)} {html.escape(lp['benchmark_name'])}, itself assumed "
                f"({html.escape(lp['benchmark_note'])}); the factor is their ratio, {num(fl['factor'], 1)}, with the range "
                f"{num(fl['factor_range'][0], 1)}&ndash;{num(fl['factor_range'][1], 1)} from the laptop's CoreMark range, and the CPU share uses "
                f"the 99th-percentile call time at every call, which overstates the mean load (Assumed). The flight processor's benchmark is quoted as "
                f"the experiment's design file gives it [121]; our research notes do not record that its source was opened.")
    fill("P3-E48-REFERENCE-SENTENCE", e48_reference, "E48 design")

    def e48_mtbf():
        fo = r.design(48, "failover")
        lv = ", ".join(unit(x, "h", 0) for x in fo["mtbf_levels_h"])
        return (f"The failover sweep runs the base computer at an MTBF of {lv}, a repair time of {unit(fo['repair_h'], 'h', 0)} and a re-election delay "
                f"of {unit(fo['reelect_h'], 'h', 1)}, on {words(len(fo['seeds']))} seeds of the leader regime of [60] at the middle load, all three values Assumed; "
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
            check(bytes_st / bytes_all > 0.9, f"the status report is most of the bytes and the events a small share, at {m} times the fleet (3.4)")
            bits.append(f"{pc(st / tot, 2)} of the messages and {pc(bytes_st / bytes_all, 2)} of the bytes at {m} times")

        omitted = "rebroadcasts, team-lift proposals, answers and commits, and ledger entries"
        return (f"The status message at the assumed 1{NB}Hz is " + ", ".join(bits) + f"; the traffic counts reservation requests, grants and releases "
                f"from road traversals, bids, awards and claims from auction rounds, and landing announcements, and omits {omitted}.")
    fill("P3-E48-TRAFFIC-NOTE", e48_traffic_note, "E48")

    def e48_cpu():
        """5.1 (findings M1 and S1): the four class timings are one measurement; the memory is a sum of estimates, not a measurement."""
        s = e48_scaled()
        robots = [c for c in CLASSES if c != "BASE"]
        sc = {c: r.s48("classes", c, "cpu_safety_check_us") for c in robots}
        med = [sc[c]["median"] for c in robots]
        p99 = [sc[c]["p99"] for c in robots]
        mem = {c: _fin(r.s48("classes", c, "peak_memory_mb")) for c in robots}
        note = str(r.s48("classes", robots[0], "peak_memory_note"))
        check(all(x in note for x in ("24 h reservation-table window", "ledger copy", "bid policies", "working data (0.05 MB)")) and len(set(mem.values())) == 1,
              "the on-robot memory figure is a sum of estimates (a day of the reservation table, a year's ledger copy, the policy files, 0.05 MB of working data), the same for every class (5.1)")
        check((max(med) - min(med)) / min(med) < 0.02, "the four class timings of the safety check differ by under 2 % at the median: one measurement (5.1)")
        a = r.s48("classes", robots[0], "cpu_auction_round_ms")
        n_calls = {sc[c]["n"] for c in robots}
        bs = r.s48("classes", "BASE", "cpu_safety_check_us")
        return (f"Timed on {html.escape(s['laptop'])} and scaled to the {html.escape(s['processor'])} by a factor of {num(s['factor'], 1)} "
                f"(range {num(s['range'][0], 1)}&ndash;{num(s['range'][1], 1)}, Assumed): a safety check took "
                f"{unit(min(med), '&micro;s', 0)}&ndash;{unit(max(med), '&micro;s', 0)} at the median and {unit(min(p99), '&micro;s', 0)}&ndash;"
                f"{unit(max(p99), '&micro;s', 0)} at the 99th percentile over {' and '.join(cnt(n) for n in sorted(n_calls))} calls in each of four timings. "
                f"The four timings are labelled by vehicle class and are one measurement: the same function on the same pool of moves from the encounter "
                f"fixtures, with only the class's speed changed and with no reservation entries or heard broadcasts in the call. Their differences are "
                f"timer noise; no class is the worst, and the largest 99th percentile is the value used. The call is Python on single numbers, so it "
                f"measures this implementation and not the rules in a flight language. The simulator's dispatch call for the whole fleet took "
                f"{unit(a['median'], 'ms', 2)} at the median and {unit(a['p99'], 'ms', 1)} at the 99th percentile over {cnt(a['n'])} calls pooled over the fleet "
                f"sizes. The on-robot data are estimated at {unit(max(mem.values()), 'MB', 2)}: the bytes of a 24-hour window of the reservation "
                f"table and of a year's ledger copy at the assumed layouts, the two policy files as stored on disk, and 0.05{NB}MB allowed for working "
                f"data; the program, its interpreter and its stack are not counted. The base computer's reservation check over the shared table, a "
                f"different function from the vehicles' safety check, took {unit(bs['median'], '&micro;s', 0)} at the median and {unit(bs['p99'], '&micro;s', 0)} "
                f"at the 99th percentile, and its data are estimated at {unit(r.s48('classes', 'BASE', 'peak_memory_mb'), 'MB', 2)}, with the full year's table "
                f"(Table 6).")
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
                f"against the {num(s['bps_target'], 0)}{NB}B/s target and {num(s['kbps_20'], 2)}{KBPS} for {cnt(s['air']['robots'])} robots at the sources, "
                f"before authentication and before any relaying (the next paragraph adds both). "
                f"The ledger grows by {unit(led['1'], 'MB', 1)} a year at today's fleet, {unit(led['4'], 'MB', 1)} at four times and {unit(led['8'], 'MB', 1)} at eight, "
                f"extrapolated from each run's jobs per hour. The market's messages come to {unit(r.s48('h10', 'market_mb_per_day'), 'MB', 3)} a day "
                f"at today's fleet.")
    fill("P3-E48-RESULTS-MESSAGES", e48_messages, "E48")

    def sec_sizes(mac):
        """The authenticated sizes per message type, in the file's order, underscores as spaces."""
        return r.s48("messages", "secured", "bytes_per_type", mac)

    def e48_secured_layout():
        """3.4: the authenticated layout as a design input (E48 `messages.secured.header` and `.map`)."""
        sec = r.s48("messages", "secured")
        h = _get(sec, "bytes_per_type", "header")
        mac_n, mac_w = (int(x) for x in h["mac"])
        fixed = int(h["space_packet"]) + int(h["lrip"]) + int(h["security_header"])
        mp = _get(sec, "bytes_per_type", "map")
        check("POSITION 1 Hz + STATUS 0.1 Hz + INTENT 0.1 Hz" in str(mp.get("status (E48, 1 Hz)", "")),
              "the authenticated layout sends position at 1 Hz and status and intent at 0.1 Hz in place of the 1 Hz status message (3.4, 5.2)")
        check("sent once + 3 repeats" in str(mp.get("landing_announcement", "")), "the landing announcement is sent once and repeated three times (3.4, 5.2)")
        check("signed" in str(mp.get("grant", "")) and "signed" in str(mp.get("award", "")), "grants and awards are the signed messages (3.4)")
        check("not on the air" in str(mp.get("ledger_entry", "")), "the ledger entry is not on the air (3.4)")
        s8, s16 = sec_sizes("mac8"), sec_sizes("mac16")
        check(all(s8[k] == s16[k] for k in ("grant", "award")) and all(s16[k] - s8[k] == mac_w - mac_n for k in s8 if k not in ("grant", "award")),
              "the wider code adds its extra bytes to every message but the signed grant and award")
        return (f"The airtime of Section 4.2 uses a second, authenticated layout: around its content every message carries a packet header of "
                f"{unit(h['space_packet'], 'B')}, a protocol header of {unit(h['lrip'], 'B')}, a security header of {unit(h['security_header'], 'B')} "
                f"and a message authentication code of {unit(mac_n, 'B')}, {unit(fixed + mac_n, 'B')} in all ({unit(fixed + mac_w, 'B')} with a code of "
                f"{unit(mac_w, 'B')}); grants and awards carry a signature of {unit(h['signature'], 'B')} in place of the code; the 1{NB}Hz status "
                f"message becomes a position report at 1{NB}Hz with status and intent reports at 0.1{NB}Hz, and a landing announcement is sent four "
                f"times (Design, the interaction-protocol draft in the repository's research notes; not flown, and E48 does not serialise it either).")
    fill("P3-E48-SECURED-LAYOUT-SENTENCE", e48_secured_layout, "E48 secured sizes (B-89)")

    def e48_airtime_method():
        """4.2: how the airtime is computed (E48 `airtime`, `revision.two_ray_in_the_mesh.e40_month`)."""
        a = e48_air()
        mo = a["month"]
        scn = str(_get(mo, "scenario"))
        check(all(x in scn for x in ("C_AUCTION", "30 % load", "loss 0.10", "roads atc", "seed 1", "the 2028 month with the least BASE direct-to-Earth visibility")),
              "the month's trace is the auction regime with roads, 30 % load, message loss 0.10, seed 1, the 2028 month with the least direct-to-Earth visibility (4.2)")
        return (f"The traffic is also stated as airtime on one shared channel, because every relayed copy of a message is another transmission "
                f"in the same band: {cnt(a['robots'])} robots need a channel rate of at least their load at the sources, at the authenticated sizes "
                f"of Section 3.4, times the mean number of hops a message travels, divided by the access efficiency, {num(a['sched']['eta'], 2)} for a "
                f"channel the base schedules in time slots with a 20{PCT} guard time and {num(a['rand']['eta'], 2)} (1/e) for slotted random access "
                f"(Assumed). The hop count is one, two, or the mean number of hops to the base computer, among the robots with a path to it, over the "
                f"{cnt(mo['epochs'])} decision epochs "
                f"of a one-month trace of the auction regime with the road layer on (seed 1, 30{PCT} load, message loss 0.10, the month of 2028 with "
                f"the least direct-to-Earth visibility at the base).")
    fill("P3-E48-AIRTIME-METHOD-SENTENCE", e48_airtime_method, "E48 airtime (B-89)")

    def e48_airtime():
        """5.2: the authenticated load and the airtime it needs, each direction word from its row."""
        a = e48_air()
        sec = r.s48("messages", "secured")
        s8, s16 = sec_sizes("mac8"), sec_sizes("mac16")
        mph = _fin(_get(sec, "per_robot_hour", "1"))
        tg = r.s48("targets")
        bps = a["bph"]["mac8"] / 3600.0
        T = f"{num(a['target'], 0)}{KBPS}"
        types = "; ".join(f"{html.escape(k.replace('_', ' '))} {unit(v, 'B')}" for k, v in s8.items())
        wide = ", ".join(num(v, 0) for v in s16.values())
        hist = a["hist"]
        ob = one_hop_basis()
        three = sum(int(s8[x]) for x in ("position", "status", "intent"))
        hist_txt = ("robot-epochs with a path to it: " + ", ".join(f"{cnt(v)} at {words(k)} hop{'s' if k != 1 else ''}" for k, v in sorted(hist.items())) +
                    f"; {pc(a['cut'], 1)} of the robot-epochs with the base computer up had no path and are not in the mean, and over all route points "
                    f"the median is {words(conn[key]['median_hops'])} hops, Section 3.3")
        return (f"With the authenticated layout of Section 3.4 the types weigh: {types} (with the {unit(r.s48('messages', 'secured', 'bytes_per_type', 'header')['mac'][1], 'B')} "
                f"code, in the same order: {wide}{NB}B). The same event counts then give {num(mph, 1)} messages and {unit(a['bph']['mac8'], 'B', 0)} per robot-hour "
                f"at today's fleet ({unit(a['bph']['mac16'], 'B', 0)} with the wider code): {num(bps, 1)}{NB}B/s per robot against the "
                f"{num(tg['bytes_per_s_per_robot'], 0)}{NB}B/s target, and {num(a['load'], 2)}{KBPS} for {cnt(a['robots'])} robots at the sources "
                f"({num(a['load16'], 2)}{KBPS} with the wider code). On one shared channel, at the mean of {num(a['hops'], 3)} hops to the base computer "
                f"in the month's trace of Section 4.2 ({hist_txt}), {cnt(a['robots'])} robots need {num(a['sched']['need'], 2)}{KBPS} of a channel the base "
                f"schedules, {side(a['sched'], 'the ' + T + ' target')}, and {num(a['rand']['need'], 2)}{KBPS} on slotted random access, {side(a['rand'])}. "
                f"At exactly one hop the scheduled channel needs {num(a['one']['need'], 2)}{KBPS}, {side(a['one'], 'the target')}; if every report is "
                f"relayed two hops it needs {num(a['two']['need'], 2)}{KBPS}, {side(a['two'])}. Every one of these figures is conditional. A base cannot give "
                f"a time slot to, or hear a one-hop report from, a vehicle that has no path to it, and the hop count above is a mean over the robots' "
                f"positions at the decision epochs of one seed's month. In E50's trace of the same seed those positions are parked in "
                f"{pc(ob['parked_share'], 1)} of vehicle-steps ({cnt(ob['parked'])} parked against {cnt(ob['driving'])} driving), while the bytes are reports sent "
                f"once a second by every vehicle. While driving, a vehicle had a radio path to the base in {pc(ob['drive'], 1)} of its steps "
                f"({pc(ob['lo'], 1)} to {pc(ob['hi'], 1)} over the seeds), against {pc(ob['all'], 1)} over all time (E54's contact plan of the month). The "
                f"claim is therefore this: the authenticated traffic of {cnt(a['robots'])} robots, {num(a['load'], 2)}{KBPS} at the sources, would need "
                f"{num(a['sched']['need'], 2)}{KBPS} of a base-scheduled channel if every robot were within one hop of the base; in the recorded month that "
                f"holds for robots standing at sites, and a driving robot has a path to the base {pc(ob['drive'], 0)} of the time. The report rates matter "
                f"as much as the hops. The traffic counted has position at 1{NB}Hz and status and intent at 0.1{NB}Hz; if all three reports went at "
                f"1{NB}Hz a robot would send {' + '.join(cnt(s8[x]) for x in ('position', 'status', 'intent'))} = {cnt(three)}{NB}B/s and {cnt(a['robots'])} "
                f"robots {num(three * a['robots'] * 8 / 1000.0, 2)}{KBPS} at the sources, {'above' if three * a['robots'] * 8 / 1000.0 > a['target'] else 'within'} "
                f"the target before any airtime factor (a calculation from the serialised sizes, not a run).")
    fill("P3-E48-RESULTS-AIRTIME", e48_airtime, "E48 airtime (B-89)")

    def limit_link():
        """Section 7: the link claim's condition and its basis (findings M2 and S16)."""
        a, ob = e48_air(), one_hop_basis()
        three = _fin(r.p6("E53", "lrip_v02", "driving_split", "status_intent_at_1hz", "lrip", "sources_20_rovers_kbps"))
        T = f"{num(a['target'], 0)}{KBPS}"
        return (f"The {T} target is met only on a base-scheduled channel on which every robot is within one hop of the base. That condition is taken "
                f"from positions that are parked in {pc(ob['parked_share'], 0)} of vehicle-steps, while the traffic is that of vehicles reporting once a "
                f"second whether they move or not; a driving vehicle has a radio path to the base {pc(ob['drive'], 0)} of the time (Section 5.2). The "
                f"traffic model gives every rover a 2.5{NB}m antenna, although half the fleet carries 1.0{NB}m, and sends status and intent at "
                f"0.1{NB}Hz; with all three reports at 1{NB}Hz the load at the sources alone, {num(three, 2)}{KBPS}, is "
                f"{'above' if three > a['target'] else 'within'} the target. Drawn from driving steps only, 20 rovers are "
                f"{num(r.p6('E53', 'driving_split', 'e53_auth_20_rovers', 'fleet_driving', '1 Hz')['mean_hops_to_base'], 2)} hops from the base on average and "
                f"not one (Section 5.2).")
    fill("P3-LIMIT-LINK-SENTENCE", limit_link, "E48, E50, E54")

    def horizon_sentence():
        """3.3 (item 1 of the 11 Nov list): the smooth-Moon horizons, recomputed; sqrt(2 R h), Proposition 1."""
        hz = lambda h: math.sqrt(2.0 * R_MOON * h)
        hr, hs, hm = (_fin(r.s48("classes", c, "link", "antenna_m")) for c in ("LTV1", "SMALL", "BASE"))
        check(abs(_fin(r.s48("classes", "LTV1", "link", "mutual_horizon_m")) - 2 * hz(hr)) < 1.0 and
              abs(_fin(r.s48("classes", "SMALL", "link", "mutual_horizon_m")) - 2 * hz(hs)) < 1.0 and
              abs(_fin(r.s48("classes", "BASE", "link", "mutual_horizon_m")) - (hz(hm) + hz(hs))) < 1.0,
              "the horizons of 3.3 are those of the link budget's file (Proposition 1)")
        km = lambda m: f"{num(m / 1000.0, 2)}{NB}km"
        return (f"On a smooth Moon the horizon of a {unit(hr, 'm', 1)} antenna is {km(hz(hr))}, of a {unit(hs, 'm', 1)} antenna {km(hz(hs))} and of a "
                f"{unit(hm, 'm', 0)} mast {km(hz(hm))} (Proposition 1), so two rovers can never see each other beyond {km(2 * hz(hr))}, two small robots "
                f"beyond {km(2 * hz(hs))}, and a rover cannot see the mast beyond {km(hz(hr) + hz(hm))} [63]")
    fill("P3-HORIZON-SENTENCE", horizon_sentence, "E48 link")

    def mesh_horizon_sentence():
        """3.3 against Table 7 (item 5): the DEM mesh keeps 1 m pairs beyond their smooth-Moon horizon; the two-ray budget on the mesh's links."""
        mp = r.s48("revision", "two_ray_in_the_mesh", "mesh_pairs", "by_class")
        sm, ho, lt = (_get(mp, c) for c in ("SMALL", "HOPPER", "LTV1"))
        hz2 = _fin(r.s48("classes", "SMALL", "link", "mutual_horizon_m"))
        check(_fin(sm["default_max_d_m"]) > hz2 and abs(_fin(sm["default_max_d_m"]) - RADIO.DEFAULT_D_MAX_M) < 1e-6,
              "the mesh keeps pairs of 1 m antennas beyond their smooth-Moon horizon, up to its range (3.3)")
        for c, x in (("SMALL", sm), ("HOPPER", ho), ("LTV1", lt)):
            check(_fin(x["16k_m3"]["survive_share"]) == 1.0 and _fin(x["16k_m10"]["survive_share"]) == 1.0, f"{c}: every mesh link closes 16 kbit/s at 3 and 10 dB margins (3.3)")
        check(_fin(lt["16k_m15"]["survive_share"]) == 1.0 and _fin(lt["16k_m10_smooth_horizon"]["survive_share"]) == 1.0, "the rovers' mesh links all survive the 15 dB margin and the horizon check (3.3)")
        check(_fin(sm["16k_m10_smooth_horizon"]["survive_share"]) < 1.0 and _fin(sm["16k_m15"]["survive_share"]) < _fin(ho["16k_m15"]["survive_share"]) < 1.0,
              "with the horizon check on, or at a 15 dB margin, some 1 m links are lost, more for the small rover than for the hopper (3.3)")
        mo = r.s48("revision", "two_ray_in_the_mesh", "e40_month", "variants")
        check(all(int(_get(mo, k, "lost_link_epochs_horizon")) == 0 and int(_get(mo, k, "lost_link_epochs_budget")) == 0 for k in mo),
              "in the month's trace no link in use is lost to the horizon check or to the link budget (3.3)")
        check("ASSUMED" in str(r.s48("revision", "two_ray_in_the_mesh", "mesh_pairs", "flag")), "the two-ray law on terrain-visible paths is flagged Assumed (3.3)")
        return (f"One difference between the mesh and the link budget has to be stated. The mesh keeps pairs of {unit(sm['antenna_m'], 'm', 1)} antennas up "
                f"to {unit(_fin(sm['default_max_d_m']) / 1000.0, 'km', 0)} apart wherever the terrain shows line of sight, although the smooth-Moon horizon of two "
                f"such antennas is {unit(hz2 / 1000.0, 'km', 2)}. Both are right: the ridge is not a sphere, and two antennas on two rises see each other across "
                f"a valley farther than a sphere allows, while two on a plain do not. The horizon check is therefore off on the terrain mesh and on in "
                f"Table 7; switched on in the mesh it would remove {pc(1.0 - _fin(sm['16k_m10_smooth_horizon']['survive_share']), 1)} of the links between "
                f"{unit(sm['antenna_m'], 'm', 1)} antennas and none between rover antennas. Under the two-ray law every link of the mesh closes 16{KBPS} at "
                f"margins of 3 and 10{NB}dB for every class; at 15{NB}dB {pc(sm['16k_m15']['survive_share'], 1)} of the small rover's links and "
                f"{pc(ho['16k_m15']['survive_share'], 1)} of the hopper's do, and in the month's trace of Section 4.2 no link in use is lost either way "
                f"(Assumed on paths the terrain shows as visible: no path loss has been measured on the Moon).")
    fill("P3-MESH-HORIZON-SENTENCE", mesh_horizon_sentence, "E48 revision (B-89)")

    def mesh_hops_sentence():
        """3.3 against 5.2 (item 4): the two-hop median over all route points and the month's mean of about one hop."""
        a = e48_air()
        ob = one_hop_basis()
        check(a["hops"] < 1.1 < float(conn[key]["median_hops"]), "the month's mean hop count is near one and the median over all route points is two (3.3, 5.2)")
        return (f"The median of {words(conn[key]['median_hops'])} hops is over all {cnt(m['n_points'])} route points, each counted once. The fleet does not "
                f"stand on them evenly: in the one-month trace of Section 4.2 the robots with a path to the base computer were {num(a['hops'], 3)} hops from "
                f"it on average, because the work is near the base, and {pc(a['cut'], 1)} of the robot-epochs had no path at all and are in no average. "
                f"Both numbers are true; the first describes the terrain and the second where this fleet stands. The second is a mean over positions at "
                f"decision epochs, and in the recorded month a vehicle is parked in {pc(ob['parked_share'], 0)} of its steps. While it drives it has a radio "
                f"path to the base in {pc(ob['drive'], 1)} of its steps, against {pc(ob['all'], 1)} over all time (E54, Section 5.12). What follows is that "
                f"the one-hop condition of the link claim (Section 5.2) holds for robots standing at sites within reach of the mast, and not for a "
                f"vehicle on the road nor for a fleet spread over the routes.")
    fill("P3-MESH-HOPS-SENTENCE", mesh_hops_sentence, "E48 airtime (B-89)")

    def rate(x):
        """A data rate in kbit/s: whole numbers from 1,000 kbit/s, one decimal below."""
        return f"{num(x, 0 if _fin(x) >= 1000 else 1)}{KBPS}"

    def e48_links():
        """Per class, the flat-ground link (default since B-89) with its free-space upper bound, after the checks that carry the
        words 'beyond the horizon', 'upper bound' and 'two-ray law'."""
        out = {}
        hop = None
        for c in CLASSES:
            lk = r.s48("classes", c, "link")
            fs = r.s48("classes", c, "link_free_space_upper_bound")
            d, hz = _fin(_get(lk, "worst_hop_m")), _fin(_get(lk, "mutual_horizon_m"))
            beyond = bool(_get(lk, "beyond_horizon_at_worst_hop"))
            h1, h2 = _fin(lk["antenna_m"]), _fin(_get(lk, "peer_antenna_m"))
            name = CLASS_NAME[c]
            check("two-ray" in str(_get(lk, "law")) and "free space" in str(fs.get("law", "")), f"{name}: the default link is the flat-ground two-ray law and the bound is free space")
            check(beyond == (d > hz), f"{name}: 'beyond the horizon' is the worst hop against the smooth-Moon mutual horizon")
            check(abs(hz - (math.sqrt(2 * 1737.4e3 * h1) + math.sqrt(2 * 1737.4e3 * h2))) < 1.0, f"{name}: the mutual horizon is sqrt(2 R h1) + sqrt(2 R h2)")
            check(abs(_fin(_get(lk, "longest_hop_m")) - min(d, hz)) < 0.5, f"{name}: the longest hop is the smaller of the worst hop and the horizon")
            check((_fin(lk["worst_hop_kbps"]) == 0) == beyond, f"{name}: the rate at the worst hop is zero only beyond the horizon")
            check(d > 4 * math.pi * h1 * h2 * _fin(lk["freq_ghz"]) * 1e9 / 299792458.0 and
                  abs(_fin(_get(lk, "loss_db_worst_hop")) - (40 * math.log10(d) - 20 * math.log10(h1 * h2))) < 0.1,
                  f"{name}: the loss at the worst hop is 40 log d - 20 log(h1 h2), beyond the breakpoint")
            check(_fin(fs["worst_hop_kbps"]) >= _fin(_get(lk, "worst_hop_kbps_if_visible")) >= _fin(lk["worst_hop_kbps"]),
                  f"{name}: free space is an upper bound on the rate at the worst hop")
            check(beyond or abs(_fin(lk["longest_hop_kbps"]) - _fin(lk["worst_hop_kbps"])) < 1e-9, f"{name}: within the horizon the longest hop is the worst hop")
            hop = d if hop is None else hop
            check(abs(d - hop) < 1e-9 and abs(d - RADIO.DEFAULT_D_MAX_M) < 1e-9, "every class's worst hop is the mesh's range")
            if c != "BASE":
                check(h1 == h2, f"{name}: the worst hop is between two antennas of the class's own height")
                note = str(_get(lk, "reachable_note"))
                check(all(x in note for x in ("line of sight", "within 5 km", "16 kbit/s", "10 dB margin")),
                      f"{name}: the mast-reach share is terrain line of sight within 5 km that closes 16 kbit/s with a 10 dB margin (4.2, Table 7)")
                check(abs(_fin(lk["reachable_share"]) - _fin(_get(lk, "reachable_share_free_space"))) < 0.0005,
                      f"{name}: the mast-reach share is the same under both laws (4.2)")
            else:
                check(str(_get(lk, "reachable_note")) == "the mast itself" and h1 > h2, "the base computer's row is the mast down to a robot antenna")
            out[c] = {"lk": lk, "fs": fs, "beyond": beyond, "d": d, "hz": hz}
        mp = r.s48("revision", "two_ray_in_the_mesh", "mesh_pairs", "by_class")
        check(any(_fin(_get(mp, c, "16k_m10_smooth_horizon", "survive_share")) < _fin(_get(mp, c, "16k_m10", "survive_share")) for c in CLASSES if out[c]["beyond"]),
              "on the terrain some pairs in line of sight lie beyond the smooth-Moon horizon (the note of Table 7)")
        return out

    def e48_link():
        L = e48_links()
        bits = []
        for c in CLASSES:
            x = L[c]
            lk = x["lk"]
            hops = f"{unit(lk['latency_budget_ms'], 'ms')} over {words(lk['latency_hops'])} hop{'s' if int(lk['latency_hops']) != 1 else ''}"
            if c == "BASE":
                bits.append(f"the {CLASS_NAME[c]} (mast {unit(lk['antenna_m'], 'm', 1)}, {unit(lk['tx_power_w'], 'W', 2)}, the downlink to a "
                            f"{unit(lk['peer_antenna_m'], 'm', 1)} robot antenna): {rate(lk['worst_hop_kbps'])} at the worst hop, {hops}")
                continue
            head = f"the {CLASS_NAME[c]} (antenna {unit(lk['antenna_m'], 'm', 1)}, {unit(lk['tx_power_w'], 'W', 2)}): "
            if x["beyond"]:
                what = (f"beyond the {unit(x['hz'] / 1000.0, 'km', 2)} horizon of two such antennas at the worst hop, and "
                        f"{rate(lk['longest_hop_kbps'])} at the longest hop the horizon allows")
            else:
                what = f"{rate(lk['worst_hop_kbps'])} at the worst hop"
            bits.append(head + what + f", {hops}, the mast in reach from {pc(lk['reachable_share'], 1)} of the route samples")
        f0 = L["LTV1"]["lk"]
        ubs = [num(L[c]["fs"]["worst_hop_kbps"], 0) for c in CLASSES]
        ub = ", ".join(ubs[:-1]) + " and " + ubs[-1]
        return (f"Per class, at {num(f0['freq_ghz'], 1)}{NB}GHz under the flat-ground two-ray law with the smooth-Moon horizon check (Section 4.2): "
                f"the data rate at the {unit(f0['worst_hop_m'] / 1000.0, 'km', 0)} worst hop or, where two antennas of the class are beyond their horizon "
                f"at that distance, at the longest hop the horizon allows; the modelled latency of a 100-byte message (10{NB}ms per hop plus transmit "
                f"time at that rate plus the scaled safety check, against the one-second decision the model assumes); and the share of route samples "
                f"from which the mast is in reach. In that order: " + "; ".join(bits) + f". Under free-space loss, which is an upper bound, the "
                f"worst hop would carry {ub}{KBPS}, in the same order of classes (Table 7).")
    fill("P3-E48-RESULTS-LINK", e48_link, "E48")

    def e48_link_law():
        """4.2: the propagation law, the horizon check, the link constants and the mast-reach share (design `radio`, E48 `classes.*.link`)."""
        L = e48_links()
        rd = r.design(48, "radio")
        f0 = L["LTV1"]["lk"]
        check(abs(_fin(rd["worst_hop_m"]) - _fin(f0["worst_hop_m"])) < 1e-9, "the worst hop of the design file is the one the link budget uses")
        return (f"The hop is {unit(f0['worst_hop_m'] / 1000.0, 'km', 0)} long, between two antennas of the class's own height (for the base computer, the mast "
                f"down to a {unit(L['BASE']['lk']['peer_antenna_m'], 'm', 1)} robot antenna). Its loss follows the flat-ground two-ray law: free-space loss "
                f"up to the breakpoint 4h<sub>1</sub>h<sub>2</sub>/&lambda; and, beyond it, 40&nbsp;log<sub>10</sub>&nbsp;d &minus; 20&nbsp;log<sub>10</sub>(h<sub>1</sub>h<sub>2</sub>) "
                f"with the distance d and the antenna heights h<sub>1</sub>, h<sub>2</sub> in metres, never less than free-space loss and independent of "
                f"frequency (Derived from a direct ray and a ground-reflected ray with a reflection coefficient of &minus;1 at grazing incidence; a NASA "
                f"Johnson Space Center model of lunar surface propagation shows the same fourth-power law and its independence of frequency at long range "
                f"[21]). A hop longer than the smooth-Moon horizon of its two antennas, &radic;(2Rh<sub>1</sub>) + &radic;(2Rh<sub>2</sub>) [63], carries "
                f"nothing; for a class in that case the rate is reported at the longest hop the horizon allows. The rate is the Shannon capacity of a "
                f"{unit(rd['bandwidth_mhz'], 'MHz', 0)} channel with {unit(rd['antenna_gain_dbi'], 'dBi', 0)} antennas, a {unit(rd['noise_figure_db'], 'dB', 0)} "
                f"noise figure and a {unit(rd['implementation_margin_db'], 'dB', 0)} margin (Assumed). The rate under free-space loss at the same hop is kept "
                f"beside it as an upper bound.")
    fill("P3-E48-LINK-LAW-SENTENCE", e48_link_law, "E48 link law (B-89)")

    def e48_revision_date():
        y, m, d = (int(x) for x in str(r.s48("revision", "date")).split("-"))
        return f"{d} {('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December')[m - 1]} {y}"
    fill("P3-E48-REVISION-DATE", e48_revision_date, "E48 revision (B-89)")

    def e48_correction():
        """Section 7: what the first version's free-space loss overstated, from the file's two link blocks."""
        L = e48_links()
        gone = [c for c in CLASSES if L[c]["beyond"]]
        kept = [c for c in CLASSES if not L[c]["beyond"] and c != "BASE"]
        if not gone:
            raise Pending("no class is beyond the horizon at the worst hop; the correction paragraph of Section 7 needs rewording")
        ratio = {c: _fin(L[c]["fs"]["worst_hop_kbps"]) / _fin(L[c]["lk"]["worst_hop_kbps_if_visible"]) for c in gone}
        check(min(ratio.values()) > 100, "free-space loss overstated the small classes' rate at the worst hop by more than two orders of magnitude (7)")
        check(len(gone) == 2 and all(L[c]["lk"]["antenna_m"] == min(L[x]["lk"]["antenna_m"] for x in CLASSES) for c in gone),
              "the classes beyond the horizon are the two with the lowest antennas (7)")
        check(len({L[c]["hz"] for c in gone}) == 1 and len({(L[c]["fs"]["worst_hop_kbps"], L[c]["lk"]["worst_hop_kbps"]) for c in kept}) == 1,
              "the classes beyond the horizon share one horizon, and the crew and cargo rovers one pair of rates (7)")
        k0 = kept[0]
        check(_fin(L[k0]["lk"]["worst_hop_kbps"]) < _fin(L[k0]["fs"]["worst_hop_kbps"]) and
              _fin(L["BASE"]["lk"]["worst_hop_kbps"]) < _fin(L["BASE"]["fs"]["worst_hop_kbps"]), "the corrected rates are lower than the first version's (7)")
        return (f"At the {unit(L[k0]['d'] / 1000.0, 'km', 0)} worst hop it gave " + " and ".join(f"the {CLASS_NAME[c]} {rate(L[c]['fs']['worst_hop_kbps'])}" for c in gone) +
                f"; under the flat-ground law that hop would carry " + " and ".join(rate(L[c]["lk"]["worst_hop_kbps_if_visible"]) for c in gone) +
                f" if the two antennas could see each other, " + " and ".join(num(ratio[c], 0) for c in gone) + f" times less, and they cannot: two "
                f"{unit(L[gone[0]]['lk']['antenna_m'], 'm', 1)} antennas are beyond their {unit(L[gone[0]]['hz'] / 1000.0, 'km', 2)} smooth-Moon horizon there. "
                f"For " + " and ".join(f"the {CLASS_NAME[c]}" for c in kept) + f" the rate at that hop fell from {rate(L[k0]['fs']['worst_hop_kbps'])} to "
                f"{rate(L[k0]['lk']['worst_hop_kbps'])}, and for the base mast's downlink from {rate(L['BASE']['fs']['worst_hop_kbps'])} to "
                f"{rate(L['BASE']['lk']['worst_hop_kbps'])}.")
    fill("P3-E48-CORRECTION-SENTENCE", e48_correction, "E48 revision (B-89)")

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
        check(twice == 0, "no job was assigned twice after a rebuild (3.4, 3.10)")
        return "At" + "; ".join(bits)[2:] + f". After every rebuild the table held {words(twice)} job assigned twice."
    fill("P3-E48-RESULTS-FAILOVER", e48_failover, "E48")

    def e48_design():
        ru = r.s48("runs")
        dr, fo = r.design(48, "runs"), r.design(48, "failover")
        n_t, n_f = len(dr["seeds"]) * len(dr["multiples"]), len(fo["seeds"]) * len(fo["mtbf_levels_h"])
        check(n_t + n_f == int(ru["n"]), "E48 runs = timing runs + failover runs")
        check(all(x in str(dr["regime"]) for x in ("C_AUCTION", "message loss 0.1", "roads atc")) and
              all(x in str(fo["regime"]) for x in ("C_LEADER", "message loss 0.1", "30 % load", "1x", "one year")),
              "E48's timing runs are the auction regime with the road layer and its failover runs the leader regime, both at a message loss of 0.1 (4.2)")
        return (f"{cnt(ru['n'])} runs were instrumented: {words(n_t)} timing runs, seeds {', '.join(str(x) for x in dr['seeds'])} at "
                f"{', '.join(str(x) for x in dr['multiples'])} times today's fleet (the auction regime of [60] with the road layer of [61], message loss "
                f"0.1), and {words(n_f)} failover runs, seeds {dr_seeds(fo['seeds'])} at the three MTBF levels (the leader regime of [60], message loss "
                f"0.1, the middle load, today's fleet, one year); the dispatch call is timed in every timing run and pooled, "
                f"and the on-robot data are estimated once, from the runs at today's fleet.")
    fill("P3-E48-DESIGN-SENTENCE", e48_design, "E48")
    fill("P3-E48-COMPUTE-SENTENCE", lambda: f"The instrumented runs of E48 took {unit(r.s48('runs', 'run_s_mean'), 's', 0)} each on average and "
         f"{unit(r.s48('runs', 'cpu_h'), 'h', 1)} of processor time in all.", "E48")

    def e48_round_p99_s():
        s = e48_scaled()
        worst = max((c for c in CLASSES if c != "BASE"), key=lambda c: r.s48("classes", c, "cpu_auction_round_ms")["p99"])
        return r.s48("classes", worst, "cpu_auction_round_ms")["p99"] * s["factor"] / 1000.0

    def e48_clause(kind):
        s = e48_scaled()
        a = s["air"]
        p99s = e48_round_p99_s()
        b5 = b105()
        t5 = b5["t"]
        check(all(t5[m]["central"] == "inside" for m in t5) and t5["1"]["over"] == "inside" and t5["4"]["over"] == t5["8"]["over"] == "straddling",
              "one robot's bid computation is under one second at the central factor in every pass at every fleet size, and over it only at the top of the "
              "factor range at four and eight times the fleet (abstract, 5.1, 6.1, 7, 9)")
        big = [v for m in ("4", "8") for v in t5[m]["passes"]]
        round_txt = (f"one robot's bid computation in an auction round, timed on a laptop in three passes of one month of one seed and scaled by the same "
                     f"factor, takes {num(min(t5['1']['passes']), 2)} to {unit(max(t5['1']['passes']), 's', 2)} at the 99th percentile at today's fleet and "
                     f"{num(min(big), 2)} to {unit(max(big), 's', 2)} at four and eight times the fleet, under the one-second decision at the central factor "
                     f"and over it only towards the top of the factor's range at the larger fleets")
        worst_m = max(t5, key=lambda m: max(t5[m]["passes"]))
        round_short = (f"one robot's bid stays under one second (99th percentile, at most {unit(max(t5[worst_m]['passes']), 's', 2)} at "
                       f"{ {'1': 'today' + chr(39) + 's fleet', '4': 'four times the fleet', '8': 'eight times the fleet'}[worst_m] }) except at the top of the "
                       f"factor's range")
        if kind == "abstract":
            return (f"Scaled by {num(s['factor'], 1)} to flight hardware, the safety check takes {num(s['cpu_share_worst'] * 100, 1)}{PCT} of one core; "
                    f"{round_short}. {cap1(words(a['robots']) if a['robots'] < 10 else {20: 'twenty'}.get(a['robots'], cnt(a['robots'])))} robots' authenticated traffic, "
                    f"{num(a['load'], 2)}{KBPS} at the sources, {link_text(a, 'short')}.")
        if kind == "intro":
            return (f"As implemented, the safety check {'fits' if s['fits']['cpu'] else 'does not fit'} the reference flight processor: it takes "
                    f"{num(s['cpu_share_worst'] * 100, 1)}{PCT} of one core, from one function timed on a laptop and scaled by an assumed factor. The on-robot "
                    f"data are estimated at {unit(s['mem_worst_mb'], 'MB', 1)} and measured on the laptop at {num(max(v['all'] for v in b5['mem'].values()), 2)}{NB}MB "
                    f"at most. The bidding does not fit at every fleet size: {round_txt}. The authenticated radio traffic of {cnt(a['robots'])} robots, {num(a['load'], 2)}{KBPS} at the sources, "
                    f"{link_text(a, 'long')} (Sections 5.1 to 5.3).")
        if kind == "discussion":
            return (f"the safety check {'fits' if s['fits']['cpu'] else 'does not fit'} one core of the reference processor with the stated factor, and the "
                    f"on-robot data are small, by an estimate and by a laptop measurement; {round_txt}; and the authenticated radio traffic of {cnt(a['robots'])} "
                    f"robots {link_text(a, 'long')}.")
        if kind == "comparison":
            bph = r.s48("messages", "bytes_per_robot_hour")
            ratio = 13800.0 / max(_fin(bph["1"]) / 3600.0, 1e-9)
            bps_sec = a["bph"]["mac8"] / 3600.0
            by = r.s48("messages", "per_robot_hour_by_type", "1")
            market = sum(v for k, v in by.items() if k != "status")
            return (f"The radio traffic of Lunar ATC at the sources, {num(s['bps_robot'], 1)}{NB}B/s per robot ({num(bps_sec, 1)}{NB}B/s with "
                    f"authentication), is {num(ratio, 0)} times smaller ({num(13800.0 / bps_sec, 0)} times with authentication) than the "
                    f"13.8{NB}kB/s the two-rover convoy controller of [25] used; the market's own messages come to {num(market, 2)} per robot-hour "
                    f"at today's fleet.")
        if kind == "conclusion":
            return (f"Scaled to flight hardware the safety check {'fits' if s['fits']['cpu'] else 'does not fit'} one core. "
                    f"{cap1({20: 'twenty'}.get(a['robots'], cnt(a['robots'])))} robots' traffic {link_text(a, 'concl')}. {cap1(round_short)}.")
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
        return "Every quantity of Section 4.2 is in E48's results file." if not missing else \
            "E48's results file lacks these quantities of Section 4.2: " + "; ".join(html.escape(x) for x in missing) + "."
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
        check(kinds == int(kinds) and int(kinds) == 1 + 3 * len(d["k_levels"]) + 5, "E46 run count = seeds x splits x run kinds: the pooled run, three owners by the scaling factors, the oracle, the owners alone and three pairs")
        check(all(x in d["rules"] for x in RULES) and len(d["rules"]) == len(RULES), "E46 ran the four rules of 3.9")
        return (f"{cnt(n)} physical runs, {cnt(ns)} seeds by {cnt(nsp)} splits by {cnt(kinds)} run kinds (the pooled market, the oracle, "
                f"the owners alone, the three pair coalitions and one owner at a time scaling its asks by each of the {cnt(len(d['k_levels']))} "
                f"factors); payments are computed afterwards from each run's job log, so the four rules and the {cnt(len(d['q_levels']))} audit "
                f"shares share one allocation per seed and cost no further runs, giving {cnt(r.f46('n_cells'))} cells of {cnt(ns)} seeds. Of the "
                f"{cnt(n)} simulated years, {cnt(ns * nsp * (1 + 3 * len(d['k_levels'])))} are runs of the market (the pooled run and the scaling runs) and "
                f"{cnt(n - ns * nsp * (1 + 3 * len(d['k_levels'])))} are the oracle, the owners alone and the pair coalitions. "
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

    def e46_money():
        """3.9 (finding M7): the three parameters every profit, budget, Shapley value and transfer of this paper is priced with, from the
        scenario file and the experiment's design file, each with its flag."""
        vot = {int(k): _fin(v) for k, v in r.scn["vot_usd_per_h"].items()}
        op = _fin(r.scn["operator_cost_per_h"])
        sv, pc_ = r.design(46, "shipper_value"), r.design(46, "private_costs")
        check(vot == {1: 5000.0, 2: 1000.0, 3: 100.0} and all(x in str(sv["what"]) for x in ("5,000", "1,000", "100 USD/h", "censored at the horizon")),
              "the value of time is 5,000, 1,000 and 100 USD an hour by priority, with undelivered items censored at the horizon, in the scenario and in E46's design (3.9)")
        check(op == 1000.0 and all(x in str(pc_["true_cost"]) for x in ("wear share 0.5 of unit cost per life hour", "1,000 USD/h")),
              "a carrier's true cost is half the unit cost per life hour plus operator time at 1,000 USD an hour (3.9)")
        check("Spec of the scenario" in str(sv["flag"]), "the design file flags the value of time as the scenario's specification (3.9)")
        return (f"Every amount of money in this paper is priced with three parameters of the scenario, none of them swept. The delay of an item is "
                f"priced at the value of time of its priority, {cnt(vot[1])}, {cnt(vot[2])} and {cnt(vot[3])} USD an hour for priorities 1, 2 and 3. An item "
                f"that is not delivered by the end of the year is priced as if it were delivered at that moment, so its delay is censored at the "
                f"horizon. A carrier's true cost is its wear, half the vehicle's unit cost per hour of life used, plus its operator's time at "
                f"{cnt(op)} USD an hour. All three are Assumed: they are the scenario values of [56], which the experiment's design file flags as "
                f"the scenario's specification, and none has an outside source.")
    fill("P3-E46-MONEY-SENTENCE", e46_money, "E46 design, the scenario")

    def e46_parts(split, kind):
        """Per owner, over the seeds of one split: the share of its items delivered within the year and its delay cost, from the run parts
        (results/E46_parts/<split>_s<seed>_<kind>.json.gz, block `owners`)."""
        import glob as _glob
        import gzip as _gzip
        fs = sorted(_glob.glob(os.path.join(RES, "E46_parts", f"{split}_s*_{kind}.json.gz")))
        if not fs:
            raise Pending(f"the run parts of E46 ({split}, {kind}) are not in results/E46_parts")
        check(len(fs) == len(r.f46("design", "seeds")), f"E46 parts: one {kind} run per seed ({split})")
        out = {o: {"share": [], "delay": []} for o in "ABC"}
        for f in fs:
            x = json.load(_gzip.open(f, "rt", encoding="utf-8"))
            for o in "ABC":
                w = x["owners"][o]
                out[o]["share"].append(_fin(w["delivered"]) / _fin(w["items"]))
                out[o]["delay"].append(_fin(w["delay_usd"]))
        return {o: {"share": float(np.mean(v["share"])), "delay": float(np.mean(v["delay"]))} for o, v in out.items()}

    def e46_censor():
        """5.6 (finding M7): how much of each owner's alone loss is delay, and how much of its cargo is never delivered alone and so is
        priced by the censoring rule. The run files hold items and delay per owner, not the delay cost of the undelivered items alone."""
        bits = []
        worst = None
        for sp in SPLITS:
            al, po = e46_parts(sp, "alone"), e46_parts(sp, "pooled")
            loss = {o: -alone_mean(sp, o) for o in "ABC"}
            check(all(0 < al[o]["delay"] <= loss[o] * 1.001 for o in "ABC"), f"each owner's alone loss contains its alone delay cost ({sp})")
            check(al["C"]["share"] < 0.1 < min(al["A"]["share"], al["B"]["share"]) and po["C"]["share"] > 0.9,
                  f"alone, owner C delivers a small share of its items and the others most of theirs; pooled, C's items are delivered ({sp})")
            bits.append(f"with {SPLIT_NAME[sp]} owners A, B and C delivered {pc(al['A']['share'], 1)}, {pc(al['B']['share'], 1)} and {pc(al['C']['share'], 1)} "
                        f"of their items within the year when working alone, and their delay cost was {pc(al['A']['delay'] / loss['A'], 0)}, "
                        f"{pc(al['B']['delay'] / loss['B'], 0)} and {pc(al['C']['delay'] / loss['C'], 0)} of the alone loss")
            if sp == "3eq":
                worst = (al["C"], po["C"], loss["C"])
        return (f"What the alone loss is made of can be read from the run files: " + "; ".join(bits) + f". Owner C's two small rovers and two hoppers "
                f"cannot carry most of its cargo, so alone about {pc(1 - worst[0]['share'], 0)} of its items stand undelivered at the year's end, and its "
                f"alone loss of {musd(worst[2], 0)} with equal shares is almost entirely the assumed hourly rate applied, up to the horizon, to cargo that "
                f"never moves; in the pooled market {pc(worst[1]['share'], 1)} of the same items are delivered. The run files hold items and delay per "
                f"owner, not the delay cost of the undelivered items alone, so the censored part is given as a share of items.")
    fill("P3-E46-CENSOR-SENTENCE", e46_censor, "E46 run parts")

    def e46_shapley_note():
        """5.7 (finding S4): what H5's third clause tests, and the size of the transfers beside the tariff cash."""
        tr = abs(_fin(_get(r.f46("transfers"), "3eq", "C")["mean"]))
        cash = _fin(r.cell46("posted", "3eq")["settled_earth_musd"]) * M
        check(tr > 5 * cash, "the Shapley transfer of owner C is many times the tariff cash settled under the posted price (5.7)")
        return (f"The third clause is a test of pooling and not of a payment rule. Under the posted price the quantity compared with alone is the "
                f"owner's Shapley value, and the transfer is defined as that value less the owner's cash, so the tariff cancels from every owner's "
                f"payoff: the posted price sets the cash that flows before the transfer and nothing else, and the rule is better named Shapley sharing. "
                f"A Shapley value is at least the stand-alone value whenever the coalitions' values are superadditive, so the clause asks whether "
                f"pooling vehicles is superadditive in the simulator, which the companion paper already reports [60]. The transfers are large beside the "
                f"cash: owner C's {musd(tr, 0)} a year with equal shares is {num(tr / cash, 0)} times the {musd(cash, 1)} of tariff cash settled.")
    fill("P3-E46-SHAPLEY-NOTE", e46_shapley_note, "E46")

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
                f"to recover that cost on the calibration seeds (Section 3.9).")
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
                + ", against the tariff cash alone in Table 8.")
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
                f" ({words(len(names))} checks in {cnt(len(have))} rows; outcomes in Section 5.14).")
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
                f"the year's end at most {musd_m(max(open_end), 2)} (Table 8).")
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
                f"costs and its cargo's delay cost, with no receipts). Under every rule and split each owner's mean market profit (Table 8) was above its alone "
                f"profit: the market left an owner below alone in {cnt(viol_truth)} of the {cnt(len(RULES) * len(SPLITS) * 3)} owner-rule-split cases "
                f"with honest bids and in {cnt(viol_all)} of the {cnt(len(c) * 3)} owner-cell cases over every cell. Under the posted price the "
                f"profit of Table 8 is the owner's Shapley value of the coalition's value, true carrier costs plus delay costs with the sign reversed, "
                f"not its cash, and that value is what the Shapley clause of H5 compares with alone. In every tested coalition every owner's Shapley "
                f"value was above its alone profit: the smallest difference was {lo_who} in coalition "
                f"{html.escape(lo_row['coalition'])} with {SPLIT_NAME[lo_row['split']]}, {musd(lo_row['mean'], 1, sign=True)} "
                f"{ci_m(lo_row['lo'], lo_row['hi'], 1)}, and the largest owner {html.escape(hi_row['owner'])}'s in coalition "
                f"{html.escape(hi_row['coalition'])} with {SPLIT_NAME[hi_row['split']]}, {musd(hi_row['mean'], 0, sign=True)} "
                f"{ci_m(hi_row['lo'], hi_row['hi'], 0)} (Table 9).")
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
                    f"owners-alone baseline of Section 3.9 (the comparison against no payments is in Section 5.6; over every "
                    f"owner and coalition the smallest upper bound of Shapley value less alone profit is {musd(c3e['min_upper'], 1, sign=True)} and "
                    f"{musd(c3u['min_upper'], 1, sign=True)}, and the smallest lower bound {musd(c3e['min_lower'], 1, sign=True)} and "
                    f"{musd(c3u['min_lower'], 1, sign=True)}).")
        gmax = max(c1e["gain"], c1u["gain"])
        incl = "includes" if (c1e["lo"] <= 0 <= c1e["hi"] or c1u["lo"] <= 0 <= c1u["hi"]) else "excludes"
        if kind == "abstract":
            rest = f"the other two {v2}" if v2 == v3 else f"the second-price clause {v2}, the Shapley clause {v3}"
            return (f"First-price shading gained at most {musd(gmax, 1)} a year, interval {'including' if incl == 'includes' else 'excluding'} zero "
                    f"(H5's first clause {v1}; {rest}).")
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
            ow, one, worse = e46_vs_none("summary")
            vs = ("" if not worse else (f", but owner {ow[0]} fell below the no-payment market under every paid rule" if one else
                                        f", but {cnt(len(worse))} owner-rule-split cases fell below the no-payment market"))
            return f"Every owner beat working alone under {rules_txt}{vs}."
        if kind == "intro":
            ow, one, worse = e46_vs_none("summary")
            vs = ("" if not worse else (f", though owner {ow[0]} was worse off than under no payments under every paid rule" if one else
                                        f", though {cnt(len(worse))} owner-rule-split cases were worse off than under no payments"))
            return (f"In the market, {rules_txt} made every owner at least as well off as alone in both splits{vs}; the operator ran "
                    f"{sign_word(bud['first']['3eq'])} under first price, {sign_word(bud['second']['3eq'])} under the second price and "
                    f"{sign_word(bud['posted']['3eq'])} under the posted price (Sections 5.5 to 5.7).")
        if kind == "discussion":
            return (f"{rules_txt} left every owner's mean profit above its alone profit; the operator's budget under first price, "
                    f"{musd_m(bud['first']['3eq'], 2, sign=True)} a year with equal shares, is the gap between the calibration seeds and the test seeds "
                    f"and not a property of the rule (Section 7); under the second price the operator ran {sign_word(bud['second']['3eq'])} of "
                    f"{musd_m(abs(bud['second']['3eq']))}, and under the posted price {sign_word(bud['posted']['3eq'])}; the largest gain from scaling bids was {musd(gmax, 2, sign=True)} a year, "
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

    T6 = values_p6(r, V, fill, check, fill_await, landed)
    V["P3-REFERENCES"] = references()
    T = {"vehicles": table_vehicles(r, in_fleet)}
    builders = {"E48_sizing": (lambda: table_e48_sizing(r), "E48", "Table 6, sizing per vehicle class"),
                "E48_link": (lambda: table_e48_link(r), "E48", "Table 7, link budget per class"),
                "E46_rules": (lambda: table_e46_rules(r), "E46", "Table 8, cell means of E46 per rule and split"),
                "E46_owners": (lambda: table_e46_owners(r), "E46", "Table 9, each owner against alone")}
    builders.update(T6)
    for name, (fn, tag, caption) in builders.items():
        try:
            T[name] = fn()
        except Pending as e:
            if not allow_pending:
                raise SystemExit(f"TABLE:{name} pending ({e}); rerun with --allow-pending to build a draft")
            pending.append(f"TABLE:{name}: {e}")
            T[name] = f'<p class="pending">[[PENDING {tag}: {caption}]]</p>'
    if broken:
        raise SystemExit("claims contradicted by the data:\n  " + "\n  ".join(dict.fromkeys(broken)))   # each claim once: a helper may run for several keys
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
    """Table 6 since the referee round: the four class timings are one measurement and print as one row with their range; the
    simulator's dispatch call is one pooled figure and stands in the caption, not in a column; the memory is an estimate."""
    robots = [c for c in CLASSES if c != "BASE"]
    sc = {c: r.s48("classes", c, "cpu_safety_check_us") for c in robots}
    med, p99 = [_fin(sc[c]["median"]) for c in robots], [_fin(sc[c]["p99"]) for c in robots]
    mem = sorted({_fin(r.s48("classes", c, "peak_memory_mb")) for c in robots})
    pw = "; ".join(f"{CLASS_NAME[c]} {num(r.s48('classes', c, 'power_w')['value'], 0)}" for c in robots)
    b = r.s48("classes", "BASE")
    a = b["cpu_auction_round_ms"]
    rows = [["A robot of any class (crew rover, cargo rover, small rover, hopper): one function, timed four times on the same moves",
             f"{num(min(med), 1)}&ndash;{num(max(med), 1)} / {num(min(p99), 1)}&ndash;{num(max(p99), 1)}",
             num(mem[0], 2) if len(mem) == 1 else f"{num(mem[0], 2)}&ndash;{num(mem[-1], 2)}", f"{pw} (Assumed)"],
            ["Base computer: its reservation check over the shared table", f"{num(b['cpu_safety_check_us']['median'], 1)} / {num(b['cpu_safety_check_us']['p99'], 1)}",
             num(b["peak_memory_mb"], 2), f"{num(b['power_w']['value'], 0)} ({html.escape(b['power_w']['flag'])})"]]
    f = r.s48("flight")
    return _tab(f"Table 6. Sizing, timed on our implementation ({html.escape(r.s48('laptop', 'processor'))}) and, where stated in the text, scaled to the "
                f"{html.escape(f['processor'])} by {num(f['factor'], 1)} (Assumed, range {num(f['factor_range'][0], 1)}&ndash;{num(f['factor_range'][1], 1)}). "
                f"Processor time per safety check in microseconds, median / 99th percentile, as the range over the four class timings, which differ by "
                f"timer noise only; the on-robot data in MB, an estimate, with the measured peak in the text (a 24-hour window of the reservation table, a year's ledger "
                f"copy, the policy files and 0.05&nbsp;MB allowed for working data; for the base computer the full year's table); power with its flag. "
                f"The simulator's dispatch call for the whole fleet took {num(a['median'], 2)} / {num(a['p99'], 1)}&nbsp;ms over {cnt(a['n'])} calls pooled "
                f"over one, four and eight times the fleet; it belongs to no class and to no single vehicle and is therefore not a column.",
                ["What was timed", "Safety check; base: reservation check (&micro;s)", "On-robot data, estimated (MB)", "Power (W)"], rows, cls="wide")


def table_e48_link(r: R):
    """Table 7 since B-89: the flat-ground link with its horizon, and the free-space rate as a labelled upper bound. A class beyond
    its horizon at the worst hop prints those words, never a zero rate (the words and the bound are checked in values())."""
    rate = lambda x: num(x, 0 if _fin(x) >= 1000 else 1)
    sph = r.s48("revision_b104", "per_class")
    rows, hop_km, base_up = [], None, None
    for c in CLASSES:
        lk = r.s48("classes", c, "link")
        fs = r.s48("classes", c, "link_free_space_upper_bound")
        beyond = bool(_get(lk, "beyond_horizon_at_worst_hop"))
        hop_km = _fin(_get(lk, "worst_hop_m")) / 1000.0
        if c == "BASE":
            base_up = lk.get("uplink_from_small_kbps_at_worst_hop")
        rows.append([CLASS_NAME[c].capitalize(), num(lk["antenna_m"], 1), num(lk["freq_ghz"], 1), num(lk["tx_power_w"], 2),
                     num(_get(lk, "mutual_horizon_m") / 1000.0, 2),
                     "beyond the horizon" if beyond else rate(lk["worst_hop_kbps"]),
                     f"{rate(_get(lk, 'longest_hop_kbps'))} at {num(_get(lk, 'longest_hop_m') / 1000.0, 2)}{NB}km",
                     f"{rate(sph[c]['longest_hop']['kbps']['spherical_ground'])} ({num(sph[c]['longest_hop']['loss_db']['spherical_ground'], 1)} against "
                     f"{num(sph[c]['longest_hop']['loss_db']['flat_ground'], 1)}{NB}dB)",
                     rate(fs["worst_hop_kbps"]), num(lk["latency_budget_ms"], 0),
                     "&ndash; (the mast itself)" if c == "BASE" else pc(lk["reachable_share"], 1)])
    hop = f"{num(hop_km, 0)}{NB}km"
    m14 = referee_m14(r, lambda cond, claim: None)      # the checks on the spherical-ground block run in values_p6 (Proposition 1)
    note = ("Each hop is between two antennas of the class's own height; the base computer's row is the mast's downlink to a robot antenna"
            + (f", and the uplink from a small rover at the same hop carries {rate(base_up)}{NB}kbit/s" if base_up is not None else "") +
            ". The horizon is that of a smooth Moon; on the terrain a pair can see farther across a valley and less far behind a ridge, which the "
            "mesh of Section 3.3 and the last column take from the terrain model, not from this horizon. The hops used are close to that horizon, "
            "where the ground is not flat on the scale of the antennas. The spherical-ground column is a calculation with the smooth-sphere method of "
            f"[20] at the same hop: the loss is {num(m14['veh_dl'][0], 1)} to {num(m14['veh_dl'][1], 1)}{NB}dB higher for the vehicle hops and "
            f"{num(m14['dl']['BASE'], 1)}{NB}dB for the mast, and the rates are lower by a factor of {num(m14['veh_ratio'][0], 1)} to "
            f"{num(m14['veh_ratio'][1], 1)} and of {num(m14['ratio']['BASE'], 1)} (Proposition 1).")
    return _tab(f"Table 7. Link budget per vehicle class under the flat-ground two-ray law with the smooth-Moon horizon check (Section 4.2): antenna "
                f"height (m), frequency (GHz), transmit power (W), the smooth-Moon horizon of the hop (km), the rate at the {hop} worst hop (kbit/s), "
                f"the rate at the longest hop the horizon allows, the rate at that hop over a spherical ground with its loss against the flat-ground loss, "
                f"the rate at the worst hop under free-space loss, which is an upper bound and was the "
                f"first version's value (Section 7), the modelled latency of a 100-byte message over three hops (one for the base) at the longest hop's "
                f"rate plus the scaled safety check (ms), and the share of the route samples whose link to the base mast is in terrain line of sight "
                f"within {hop} and closes 16{NB}kbit/s on the uplink with a 10{NB}dB margin (multi-hop reach is higher and not measured). Every rate is "
                f"the Shannon bound of the channel after the margin, not the rate of a modem.",
                ["Class", "Antenna (m)", "Frequency (GHz)", "Power (W)", "Horizon of the hop (km)", f"Shannon bound at the {hop} worst hop, flat ground (kbit/s)",
                 "Shannon bound at the longest hop the horizon allows (kbit/s)", "The same hop over a spherical ground (kbit/s; loss)", f"Shannon bound in free space at {hop}, upper bound (kbit/s)", "Modelled latency (ms)",
                 "Mast in reach (share of route samples)"], rows, cls="wide", note=note)


def table_e46_rules(r: R):
    rows = []
    for rule in RULES:
        for split in SPLITS:
            c = r.cell46(rule, split)
            rows.append([RULE_SHORT[rule], SPLIT_NAME[split], int(c["n"]), num(c["profit_A_musd"], 1, sign=True),
                         num(c["profit_B_musd"], 1, sign=True), num(c["profit_C_musd"], 1, sign=True), num(c["operator_budget_musd"], 2, sign=True),
                         pc(c["efficiency_loss_pct"] / 100, 1), num(c["settled_earth_musd"], 1), num(c["open_end_musd"], 3), int(c["ir_violations"])])
    return _tab("Table 8. Cell means over the seeds of E46 per payment rule and share split, honest bids, no audits, in M USD a year. "
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
    return _tab("Table 9. Each owner's Shapley value in every tested coalition under the posted price against working alone on the same seeds, in "
                "M USD a year: the alone profit, the paired difference (Shapley value in the coalition minus alone) and its 95&#8239;% bootstrap "
                "interval over seeds. In a two-owner coalition both owners receive the same difference by construction, half the coalition's gain.",
                ["Split", "Coalition", "Owner", "n", "Alone profit", "Difference", "95&#8239;% CI"], rows, cls="wide")


def link_urls(txt: str) -> str:
    """Wrap every URL of an (already HTML-escaped) reference in a link. Punctuation that ends the sentence or the list item around the
    URL (a semicolon, comma, full stop, or a closing bracket the URL did not open) stays outside the link."""
    def one(u):
        url, tail = u.group(1), ""
        while url:
            if url[-1] in ";,.:" or (url[-1] == ")" and url.count("(") < url.count(")")):
                url, tail = url[:-1], url[-1] + tail
            elif re.search(r"&(#x?[0-9A-Fa-f]+|[A-Za-z]+)$", url) and tail.startswith(";"):     # an HTML entity is part of the URL, not punctuation
                url, tail = url + ";", tail[1:]
                break
            else:
                break
        return f'<a href="{url}">{url}</a>{tail}'
    return re.sub(r"(https?://[^\s<]+)", one, txt)


def references():
    notes = open(os.path.join(HERE, "NOTES.md"), encoding="utf-8").read()
    out = ['<ol class="refs">']
    seen = []
    for m in re.finditer(r"^\[(\d+)\]\s+(.+?)(?=\n\n|\n\[\d+\]|\n## |\Z)", notes, re.S | re.M):
        txt = html.escape(" ".join(m.group(2).split()))
        txt = re.sub(r"\s*\((VCI|MOA|TAS|P1|P2|PWG|LRIP)[^)]*\)\s*$", "", txt)
        txt = re.sub(r"\*(.+?)\*", r"<i>\1</i>", txt)
        txt = link_urls(txt)
        out.append(f'<li value="{m.group(1)}">{txt}</li>')
        seen.append(int(m.group(1)))
    if len(out) < 2:
        raise SystemExit("no references found in NOTES.md")
    if seen != list(range(1, len(seen) + 1)):
        raise SystemExit(f"reference numbers in NOTES.md are not 1..{len(seen)} in order: {seen}")
    if re.search(r'href="[^"]*(?<!&amp)[;,]"', "\n".join(out)):
        raise SystemExit("a reference link ends in punctuation")
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
        if "[[PENDING" in abs_text:          # a marker in the abstract itself changes the count; a pending key elsewhere does not excuse it
            print("note:", msg, "(pending markers change the count)")
        else:
            raise SystemExit(msg)
    else:
        print(f"abstract: {n_abs} words")
    m = re.search(r'<h2 id="p3-sec-conclusion">.*?</h2>(.*?)<h2', doc, re.S)
    con_text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S)))
    n_con = len(con_text.split())
    if not 150 <= n_con <= 250:
        msg = f"conclusion has {n_con} words; the target is 150-250"
        if "[[PENDING" in con_text:
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
    if not allow_pending and re.search(r"\[\[(PENDING|CHECK)", doc):
        raise SystemExit("a [[PENDING or [[CHECK marker would print (decision A4 of the referee round): " +
                         re.search(r".{60}\[\[(PENDING|CHECK).{60}", doc, re.S).group(0))
    print("wrote", out, f"({len(V)} values, {len(used)} placeholders used, {len(pending)} pending, {len(AWAITED)} awaited)")
    for p in pending:
        print("  pending:", p)
    for p in AWAITED:
        print("  awaited:", p)
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
