"""Assemble the R-1 paper (round 2): fill every {{R1-...}} placeholder from the E21 round-2 results, insert the result
tables (6-9) and the reference list, move the appendices after the references, write paper/r1/paper.html and render
the PDF with headless Chrome.

    python paper/r1/build_r1.py            (run paper/r1/make_figures_r1.py first; --no-pdf skips Chrome)

Sources (all round 2, read-only): results/table_E21_cells_r2.csv (cell means, Student-t intervals, medians),
table_E21_r2.csv (utilisation and Stage D cells), table_E21_effects_r2.csv (paired effects with medians,
geometric-mean ratios and Wilcoxon p), table_E21_years_r2.csv, table_E21_breakeven_delay_r2.csv,
fig_E21_operator_demand_r2.csv, E21_fit_r2.json, the raw E21{a,a2,b,c,d,e}_*_r2.csv (run times, cell counts, Stage D
real-Sun pairs, the local-feedstock pairs, pickup/backlog bookkeeping), data/comms/connecting_ridge/earth_link-v1.json
via E21_fit_r2.json, data/illumination/connecting_ridge/sun_link-v1.json (sunlit shares) and paper/r1/NOTES.md
(references).

Computed here because the analysis does not write them (light, seconds): the Stage D paired effects (real Sun
against the fixed night share, per seed and start year), the local-feedstock DTE-vs-always loss, and the
model-free break-evens that Section 4.4 promises beyond the analysis's p = 0.5 table (the look-ahead step and the
mast at p = 0.5; one rover and the strategic step at p = 0.2 and 0.8), with the analysis's own bootstrap
(analyse_e21: same curve, same seed, every draw kept). The p = 0.5 rows are recomputed too and checked against
E21_fit_r2.json.

Nothing that depends on which relay levels exist is typed in the text: the lowest relay level, the number of
levels, the knee and every curve phrase come from the data, so the text holds when Stage A's relay 0.05 cells
are added and the analysis is re-run.

The build fails if any placeholder is left unfilled or if a filled value contains nan or inf.
"""
import html
import json
import math
import os
import re
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RES = os.path.join(ROOT, "results")
sys.path.insert(0, ROOT)
from experiments.phase4 import analyse_e21 as AN  # noqa: E402

PARTS = ["part1_front.html", "part2_related.html", "part3_methods.html", "part4_results.html", "part5_back.html"]
PDF = os.path.join(HERE, "what_earths_horizon_costs_r1.pdf")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
RAW = {"A": "E21a_comms_autonomy_r2.csv", "A2": "E21a2_operators_r2.csv", "B": "E21b_breakeven_r2.csv",
       "C": "E21c_pads_criterion_r2.csv", "D": "E21d_sun_r2.csv", "E": "E21e_sensitivity_r2.csv",
       "F": "E21f_bounded_r2.csv", "G": "E21g_rescue_r2.csv", "G2": "E21g2_rescue_any_r2.csv",
       "H": "E21h_helper_r2.csv"}
MINUS, NB, PCT = "&minus;", "&nbsp;", "&#8239;%"
MIX_LABEL = {"teleop_4s": "Teleoperated (4&nbsp;s round trip)", "default": "Reference mix",
             "supervised_strict": "Supervised, strict", "supervised_strategic": "Supervised, strategic",
             "supervised_strategic+avoid": "Supervised, with look-ahead", "autonomous": "Autonomous"}
MIX_ORDER = list(MIX_LABEL)
NEEDS_LINK = ["teleop_4s", "default", "supervised_strict", "supervised_strategic", "supervised_strategic+avoid"]
DRIVES_LINKED = ["teleop_4s", "default", "supervised_strict", "supervised_strategic+avoid"]   # drive only when linked
CRIT_LABEL = {"any_part": "any part", "centre+0.5deg": "centre 0.5&deg; above", "centre+2deg": "centre 2&deg; above"}
WORDS = {0: "none", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
         10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen"}
FLEET_HOURS = 6 * 8760.0


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


def t_(x, nd=0, sign=False):
    return f"{num(x, nd, sign)}{NB}t"


def h_(x, nd=0, sign=False):
    return f"{num(x, nd, sign)}{NB}h"


def pc(x, nd=0, sign=False):
    """x already in percent."""
    return f"{num(x, nd, sign)}{PCT}"


def sh(x, nd=0):
    """A share (0-1) as a percentage."""
    return pc(100 * _fin(x), nd)


def ci(lo, hi, nd=0):
    return f"[{num(lo, nd)}, {num(hi, nd)}]"


def rnd(x):
    """A ratio: two decimals below 10, none above."""
    x = _fin(x)
    return f"{x:,.0f}" if x >= 10 else f"{x:.2f}"


def ratio(r, lo="gm_ratio_lo", hi="gm_ratio_hi", key="gm_ratio"):
    """A ratio and its interval, all with the decimals of the point estimate."""
    nd = 0 if _fin(r[key]) >= 10 else 2
    f = lambda x: f"{_fin(x):,.{nd}f}"
    return f"{f(r[key])} [{f(r[lo])}, {f(r[hi])}]"


def wil(p):
    if p is None or not np.isfinite(p):
        raise ValueError("Wilcoxon p missing")
    if p < 0.001:
        return "<i>p</i>&nbsp;&lt;&nbsp;0.001"
    return f"<i>p</i>&nbsp;=&nbsp;{p:.3f}" if p < 0.05 else f"<i>p</i>&nbsp;=&nbsp;{p:.2f}"


def dci(r, nd=0, unit="t", sign=True):
    """A paired difference with its t interval: '−226 t [−234, −217]'."""
    u = {"t": NB + "t", "h": NB + "h", "": ""}[unit]
    return f"{num(r['diff'], nd, sign)}{u} {ci(r['ci_lo'], r['ci_hi'], nd)}"


def pts(r, nd=1, sign=True):
    """A paired difference of shares in percentage points."""
    return (f"{num(100 * r['diff'], nd, sign)} percentage points "
            f"{ci(100 * r['ci_lo'], 100 * r['ci_hi'], nd)}")


def pts_abs(r, nd=1):
    """The size of a negative paired difference of shares, for 'lowers ... by'."""
    return f"{num(-100 * r['diff'], nd)} percentage points {ci(-100 * r['ci_hi'], -100 * r['ci_lo'], nd)}"


def rng_txt(vals, fmt, unit=""):
    lo, hi = min(vals), max(vals)
    a, b = fmt(lo), fmt(hi)
    return (a if a == b else f"{a}&ndash;{b}") + unit


def pfmt(p):
    return f"{_fin(p):g}"


def words(n):
    return WORDS.get(int(n), f"{int(n)}")


def listing(items):
    items = list(items)
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


# ---------------------------------------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------------------------------------
def _match(df, **kw):
    m = np.ones(len(df), bool)
    for k, v in kw.items():
        col = df[k]
        if v is None:
            m &= col.isna().to_numpy()
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            m &= np.isclose(pd.to_numeric(col, errors="coerce").to_numpy(float), float(v), rtol=0, atol=1e-9)
        else:
            m &= (col == v).to_numpy()
    return df[m]


class R:
    def __init__(self):
        rd = lambda f: pd.read_csv(os.path.join(RES, f))
        self.c = rd("table_E21_cells_r2.csv")
        self.t = rd("table_E21_r2.csv")
        self.e = rd("table_E21_effects_r2.csv")
        self.y = rd("table_E21_years_r2.csv")
        self.bd = rd("table_E21_breakeven_delay_r2.csv")
        self.fb = rd("table_E21f_bounded_r2.csv")
        self.gb = rd("table_E21g_rescue_r2.csv")
        self.g2 = rd("table_E21g2_rescue_any_r2.csv")
        self.ops = rd("fig_E21_operator_demand_r2.csv")
        self.f = json.load(open(os.path.join(RES, "E21_fit_r2.json"), encoding="utf-8"))
        self.raw = {k: AN.prepare(rd(v)) for k, v in RAW.items()}
        for k in ("A", "E"):
            for c in ("landed", "bulk"):
                self.raw[k][f"delivered_{c}_t"] = self.raw[k][f"delivered_{c}_kg_in_horizon"] / 1000.0
        sun = json.load(open(os.path.join(ROOT, "data/illumination/connecting_ridge/sun_link-v1.json"), encoding="utf-8"))
        self.sun = {k: v["summary"]["half"]["fraction"] for k, v in sun["points"].items()}
        a = self.c[self.c["stage"] == "A"]
        self.relay_levels = sorted(float(p) for p in a.loc[a["comms"] == "dte+relay", "p"].unique())

    def cell(self, stage="A", comms="dte", mix="supervised_strict", p=None, **kw):
        c = _match(self.c, stage=stage, comms=comms, mix=mix, **kw)
        if comms == "dte+relay":
            c = _match(c, p=p)
        if len(c) != 1:
            raise ValueError(f"cell {stage} {comms} {mix} {p} {kw}: {len(c)} rows")
        return c.iloc[0]

    def acell(self, mix, p):
        """Stage A cell by coverage: None = always, 0 = DTE only."""
        if p is None:
            return self.cell("A", "always", mix)
        return self.cell("A", "dte", mix) if p == 0 else self.cell("A", "dte+relay", mix, p)

    def eff(self, family, metric, **kw):
        e = _match(self.e[(self.e["family"] == family) & (self.e["metric"] == metric)], **kw)
        if len(e) != 1:
            raise ValueError(f"effect {family} {metric} {kw}: {len(e)} rows")
        return e.iloc[0]

    def year(self, mix, comms, metric, p=None):
        y = self.y[(self.y["mix"] == mix) & (self.y["comms"] == comms) & (self.y["metric"] == metric)]
        if p is not None:
            y = _match(y, p=p)
        return y.set_index("start_year").sort_index()


def cens(c, key="delay_prio1_p90_censored_h"):
    """Median censored p90 of a cell, marked '≥' when it is a lower bound in at least half of the seeds."""
    mark = "&ge;&nbsp;" if c["p90_censored_bound_share"] >= 0.5 else ""
    return f"{mark}{num(c[key + '_median'])}"


# ---------------------------------------------------------------------------------------------------------
# computations the analysis does not write
# ---------------------------------------------------------------------------------------------------------
def paired_raw(ref, cell, metric, key=("seed",)):
    ref, cell = ref.copy(), cell.copy()
    for d in (ref, cell):
        d["seed"] = d[list(key)].astype(int).astype(str).agg("-".join, axis=1) if len(key) > 1 else d["seed"]
    return AN.paired(ref, cell, metric)


def stage_d(r: R):
    d = r.raw["D"]
    out = {}
    for (comms, mix), g in d.groupby(["comms", "mix"]):
        f, x = g[g["sun"] == "night_fraction"], g[g["sun"] == "real"]
        res = {m: paired_raw(f, x, m, ("start_year", "seed")) for m in
               ("delivered_t_in_year", "prio1_completion_share", "delay_prio1_p90_censored_h", "delay_prio1_p90_h")}
        years = {}
        for yr, gy in g.groupby("start_year"):
            years[int(yr)] = AN.paired(gy[gy["sun"] == "night_fraction"], gy[gy["sun"] == "real"], "delay_prio1_p90_h")
        res["years_p90"] = years
        out[(comms, mix)] = res
    return out


def local_feedstock(r: R, mix):
    e = r.raw["E"]
    e = e[(e["sensitivity"] == "isru_local_feedstock") & (e["mix"] == mix)]
    return AN.paired(e[e["comms"] == "always"], e[e["comms"] == "dte"], "delivered_t_in_year")


def breakevens(r: R, p_b, opts, boot=None, seed=1, metric="delay_prio1_p90_h"):
    """analyse_e21.breakeven_r2 with a chosen option list and coverage: model-free curve (the supervised-strict
    Stage A cells), the same seed draw for curve and option, every draw kept, order-statistic intervals."""
    boot = boot or int(r.f["breakeven_delay"]["boot"])
    a, b = r.raw["A"], r.raw["B"]
    s = a[a["p"].notna() & (a["mix"] == "supervised_strict")]
    Yc = AN._pivot(s, metric)
    P = Yc.columns.to_numpy(float)
    ser = {lab: AN.select(b, p=p_b, policy=pol, extra_rovers=n, mast=mast).drop_duplicates("seed").set_index("seed")[metric]
           for lab, pol, n, mast in opts}
    base = AN.select(b, p=p_b, policy="strict", extra_rovers=0, mast="none").drop_duplicates("seed").set_index("seed")[metric]
    seeds = sorted(set(Yc.index) & set(base.index).intersection(*[set(x.index) for x in ser.values()]))
    Y = Yc.loc[seeds].to_numpy(float)

    def one(rows):
        m = AN._means(Y[rows])
        sd = [seeds[i] for i in rows]
        return {lab: AN.mono_inverse(P, m, float(np.nanmean(ser[lab].loc[sd]))) for lab in ser}

    pt = one(np.arange(len(seeds)))
    rg = np.random.default_rng(seed)
    draws = [one(rg.integers(0, len(seeds), len(seeds))) for _ in range(boot)]
    out = {"_p_b": p_b, "_boot": boot}
    for lab in ser:
        pe = np.array([d[lab] for d in draws])
        dp = pe - p_b
        out[lab] = {"p_equiv": pt[lab], "dp": pt[lab] - p_b, "pe_lo": AN._q(pe, 0.025), "pe_hi": AN._q(pe, 0.975),
                    "lo": AN._q(dp, 0.025), "hi": AN._q(dp, 0.975), "beyond": float(np.mean(np.isinf(pe))),
                    "nonpos": float(np.mean(dp <= 0)), "value": float(np.nanmean(ser[lab].loc[seeds])),
                    "base": float(np.nanmean(base.loc[seeds]))}
    if "+1 rover" in ser:
        dp1 = np.array([d["+1 rover"] for d in draws]) - p_b
        price = np.where(dp1 <= 0, np.inf, np.where(np.isinf(dp1), 0.0, 4.5 / np.where(dp1 > 0, dp1, 1.0)))
        out["_price"] = (4.5 / (pt["+1 rover"] - p_b) if np.isfinite(pt["+1 rover"]) and pt["+1 rover"] > p_b else math.inf,
                         AN._q(price, 0.025), AN._q(price, 0.975))
    return out


def dp_txt(o, nd=2):
    """Δp with its bootstrap interval; 'beyond full coverage' where the option beats the p = 1 cell."""
    full = 1.0 - o.get("_p_b", 0.5)
    f = lambda v: ("beyond full coverage" if math.isinf(v) and v > 0 else num(v, nd))
    if math.isinf(o["dp"]):
        return f"beyond full coverage [{f(o['lo'])}, {f(o['hi'])}]"
    return f"{num(o['dp'], nd)} [{f(o['lo'])}, {f(o['hi'])}]"


# ---------------------------------------------------------------------------------------------------------
# values
# ---------------------------------------------------------------------------------------------------------
def values(r: R):
    V = {}
    f = r.f
    raw = r.raw
    low = r.relay_levels[0]

    # ---- counts, compute, design ------------------------------------------------------------------------------
    cells = {k: int(v["cell"].nunique()) for k, v in raw.items()}
    for k in RAW:
        V[f"R1-CELLS-{k}"] = f"{cells[k]}"
    V["R1-N-CELLS"] = f"{sum(cells.values())}"
    V["R1-N-STAGES"] = words(len(RAW))
    V["R1-N-YEARS"] = f"{sum(len(v) for v in raw.values()):,}"
    a, b, c = raw["A"], raw["B"], raw["C"]
    dup, checked = 0, 0
    pol_mix = {"strict": "supervised_strict", "strategic": "supervised_strategic",
               "strategic+avoid": "supervised_strategic+avoid"}
    for (p, pol), g in b[(b["extra_rovers"] == 0) & (b["mast"] == "none")].groupby(["p", "policy"]):
        twin = AN.select(a, p=float(p), mix=pol_mix[pol])
        if len(twin):
            dup += 1
            j = g.set_index("seed")["delivered_t_in_year"].sort_index()
            k = twin.set_index("seed")["delivered_t_in_year"].sort_index()
            checked += int(np.allclose(j.to_numpy(), k.loc[j.index].to_numpy()))
    cb = c[np.isclose(c["pad_standoff_km"], 1.0) & (c["criterion"] == "any_part") & np.isclose(c["defer_wait_h"], 24.0)]
    dup += cb["cell"].nunique()
    if checked != dup - cb["cell"].nunique():
        print(f"WARNING: {dup - cb['cell'].nunique() - checked} Stage B base cells differ from their Stage A twins")
    V["R1-N-DUP-YEARS"] = f"{dup * 20}"
    V["R1-N-EFFECTS"] = f"{len(r.e):,}"
    V["R1-BOOT-DRAWS"] = f"{int(f['breakeven_delay']['boot']):,}"
    V["R1-LAW-BOOT"] = f"{int(f['laws']['supervised_strict']['delay_prio1_p90_h']['boot']):,}"
    run_s = {k: v["run_s"].sum() for k, v in raw.items()}
    V["R1-COMPUTE-H"] = f"{sum(run_s.values()) / 3600:.1f}"
    for k, s in run_s.items():
        V[f"R1-COMPUTE-{k}-MIN"] = f"{s / 60:.0f}"
    ut = r.t[(r.t["stage"] == "A")]
    util = lambda comms, mix: float(ut[(ut["comms"] == comms) & (ut["mix"] == mix)]["utilisation"].iloc[0])
    V["R1-UTIL-ALWAYS"] = sh(util("always", "default"), 1)
    V["R1-UTIL-STRICT-DTE"] = sh(util("dte", "supervised_strict"), 1)
    V["R1-A-RELAY-COUNT"] = words(len(r.relay_levels))
    V["R1-P-LOW"] = pfmt(low)
    V["R1-P-LOW-PCT"] = pc(100 * low, 0)

    # ---- 5.1 ---------------------------------------------------------------------------------------------------
    fr = f["throughput_bound"]["site_link_fraction_dte_any_part"]
    V["R1-FRAC-CREST"] = rng_txt([fr[k] for k in ("BASE", "POWER", "CONSTR", "DEPOT")], lambda x: f"{100 * x:.0f}", PCT)
    V["R1-FRAC-SCI"], V["R1-FRAC-PSR"], V["R1-FRAC-PADB1"] = (sh(fr[k], 1) for k in ("SCI_1", "PSR", "PAD_B@1"))
    assert fr["ISRU"] == 0.0

    # ---- 5.2 throughput ----------------------------------------------------------------------------------------
    S = "supervised_strict"
    al, dt = r.acell(S, None), r.acell(S, 0)
    V["R1-T-ALWAYS"], V["R1-T-DTE"] = t_(al["delivered_t_in_year"]), t_(dt["delivered_t_in_year"])
    V["R1-T-ALWAYS-CI"] = f"{num(al['delivered_t_in_year'])} &plusmn; {num(al['delivered_t_in_year_ci95_t'])}{NB}t"
    V["R1-T-DTE-CI"] = f"{num(dt['delivered_t_in_year'])} &plusmn; {num(dt['delivered_t_in_year_ci95_t'])}{NB}t"
    d = r.eff("dte_vs_always", "delivered_t_in_year", mix=S)
    V["R1-T-LOSS-T"] = dci(d)
    V["R1-T-LOSS-PCT"] = f"{pc(d['rel_pct'])} {ci(100 * d['ci_lo'] / d['ref_mean'], 100 * d['ci_hi'] / d['ref_mean'])}"
    V["R1-T-LOSS-PCT-PLAIN"] = pc(abs(d["rel_pct"]))
    yb = f["year_blocked"][f"dte_vs_always|{S}|0.0|delivered_t_in_year"]
    V["R1-T-LOSS-YB"] = f"{t_(yb['diff'], 0, True)} {ci(yb['ci_lo'], yb['ci_hi'])}"
    others = [abs(r.eff("dte_vs_always", "delivered_t_in_year", mix=m)["rel_pct"]) for m in
              ("teleop_4s", "default", "supervised_strategic+avoid")]
    V["R1-T-LOSS-PCT-RANGE"] = rng_txt(others, lambda x: f"{x:.1f}", PCT)
    ds = r.eff("dte_vs_always", "delivered_t_in_year", mix="supervised_strategic")
    V["R1-T-LOSS-STRAT"] = f"{t_(-ds['diff'])} [{num(-ds['ci_hi'])}, {num(-ds['ci_lo'])}], or {pc(-ds['rel_pct'])}"
    db = r.eff("dte_vs_always", "delivered_bulk_t", mix=S)
    V["R1-BULK-ALWAYS"], V["R1-BULK-DTE"] = t_(db["ref_mean"], 1), t_(db["cell_mean"], 1)
    V["R1-BULK-LOSS-PCT"] = pc(db["rel_pct"], 1)
    tb = f["throughput_bound"]
    pmt = lambda k: f"{num(tb[k]['mean'], 1)} &plusmn; {num(tb[k]['ci95'], 1)}{NB}t"
    V["R1-BOUND-T"], V["R1-LOST-NEVER-T"], V["R1-GAP-T"] = pmt("bound_ready_t"), pmt("lost_at_never_linked_t"), pmt("gap_t")
    V["R1-GAP-ELSE-T"] = pmt("gap_elsewhere_t")
    V["R1-LOSS-SHARE-NEVER"] = pc(100 * tb["lost_at_never_linked_t"]["mean"] / tb["gap_t"]["mean"])
    assert tb["never_linked"] == ["ISRU"] and tb["dte_delivered_to_never_linked_t"]["mean"] == 0.0
    dl = r.eff("dte_vs_always", "delivered_landed_t", mix=S)
    V["R1-LANDED-ALWAYS"], V["R1-LANDED-DTE"] = t_(dl["ref_mean"], 1), t_(dl["cell_mean"], 1)
    V["R1-LANDED-LOSS-PCT"] = f"{pc(dl['rel_pct'])} {ci(100 * dl['ci_lo'] / dl['ref_mean'], 100 * dl['ci_hi'] / dl['ref_mean'])}"
    V["R1-LANDED-LOSS-PCT-PLAIN"] = pc(abs(dl["rel_pct"]))
    V["R1-LANDED-GM"] = ratio(dl)
    yl = f["year_blocked"][f"dte_vs_always|{S}|0.0|delivered_landed_t"]
    V["R1-LANDED-YB"] = f"{t_(yl['diff'], 1, True)} {ci(yl['ci_lo'], yl['ci_hi'], 1)}"
    ret = f["throughput_split"]["dte_vs_always"][S]["delivered_return_t"]
    V["R1-RETURN-LOSS-PCT"] = pc(abs(ret["rel_pct"]))
    lf = local_feedstock(r, S)
    V["R1-LOCAL-ALWAYS"], V["R1-LOCAL-DTE"] = t_(lf["ref_mean"], 1), t_(lf["cell_mean"], 1)
    V["R1-LOCAL-LOSS"] = f"{t_(-lf['diff'], 1)} [{num(-lf['ci_hi'], 1)}, {num(-lf['ci_lo'], 1)}], {pc(-lf['rel_pct'])}"
    ga, gd = AN.select(a, comms="always", mix=S), AN.select(a, p=0.0, mix=S)
    V["R1-PICKED-DTE"] = t_(gd["delivered_kg"].mean() / 1000, 1)
    V["R1-DROPPED-DTE"] = t_(gd["delivered_kg_in_horizon"].mean() / 1000, 1)
    V["R1-BACKLOG-DTE"] = t_(gd["backlog_kg"].mean() / 1000, 1)
    V["R1-READY-GAP"] = t_((ga["ready_kg"].mean() - gd["ready_kg"].mean()) / 1000, 1)
    byd = tb["delivered_t_by_dest"]
    assert byd["dte"]["PAD_B"] == 0.0
    V["R1-PADB-ALWAYS"] = t_(byd["always"]["PAD_B"], 1)

    def restore(mix, p, col="delivered_t_in_year"):
        A0, A1, Ap = r.acell(mix, 0)[col], r.acell(mix, None)[col], r.acell(mix, p)[col]
        return (Ap - A0) / (A1 - A0)

    V["R1-RESTORE-LOW-STRICT"] = sh(restore(S, low))
    V["R1-RELAY-LOW-RESTORE-PCT"] = V["R1-RESTORE-LOW-STRICT"]
    V["R1-RESTORE-LOW-LANDED"] = sh(restore(S, low, "delivered_landed_t"))
    V["R1-RESTORE-MIN"] = sh(min(restore(m, p) for m in NEEDS_LINK for p in r.relay_levels))

    def knee(mix):
        full = r.acell(mix, 1.0)["delivered_t_in_year"]
        ok = [p for p in [0.0] + r.relay_levels if r.acell(mix, p)["delivered_t_in_year"] >= 0.95 * full]
        return min(ok)

    k = knee(S)
    V["R1-A-KNEE-P"] = pfmt(k)
    V["R1-KNEE-REMARK"] = (", the lowest relay level tested, for every fleet that needs a link"
                           if k == low and all(knee(m) == low for m in NEEDS_LINK) else "")
    rc = r.eff("sensitivity_vs_stage_a", "delivered_t_in_year", sensitivity="relay_periodic_rc31", mix="teleop_4s", p=0.1)
    V["R1-E-RC31-TELEOP-T-01"] = f"{dci(rc, 1)} ({pc(rc['rel_pct'], 1)})"
    rv = r.eff("rovers_vs_0", "delivered_t_in_year", p=0.0, policy="strict", extra_rovers=1.0)
    V["R1-ROVER-GAIN-T"] = dci(rv, 1)
    ms = r.eff("mast_vs_none", "delivered_t_in_year", p=0.0, policy="strict")
    V["R1-MAST-GAIN-T"] = dci(ms, 1)
    V["R1-ROVER-COMP-DTE"] = pts(r.eff("rovers_vs_0", "prio1_completion_share", p=0.0, policy="strict", extra_rovers=1.0))
    V["R1-MAST-COMP-DTE"] = pts(r.eff("mast_vs_none", "prio1_completion_share", p=0.0, policy="strict"))
    if min(restore(m, p) for m in NEEDS_LINK for p in r.relay_levels) < 0.95:
        print("WARNING: some relay level restores less than 95 % of the lost tonnage; revisit 'Any relay restores' "
              "(Section 5.2), the Discussion's second paragraph, the Conclusions and the abstract")

    # ---- 5.3 urgent ---------------------------------------------------------------------------------------------
    V["R1-COMP-ALWAYS-STRICT"], V["R1-COMP-DTE-STRICT"] = sh(al["prio1_completion_share"]), sh(dt["prio1_completion_share"])
    V["R1-P1-COMPLETION-DTE"] = V["R1-COMP-DTE-STRICT"]
    dc = r.eff("dte_vs_always", "prio1_completion_share", mix=S)
    V["R1-COMP-CHANGE-STRICT"] = pts(dc)
    V["R1-COMP-DTE-RANGE"] = rng_txt([r.acell(m, 0)["prio1_completion_share"] for m in
                                      ("teleop_4s", "default", "supervised_strategic+avoid")], lambda x: f"{100 * x:.0f}", PCT)
    assert max(r.acell(m, 0)["prio1_completion_share"] for m in DRIVES_LINKED) <= 0.5 + 1e-9
    V["R1-CP90-MED-DTE-STRICT"] = cens(dt) + NB + "h"
    V["R1-CP90-MED-ALWAYS-STRICT"] = cens(al) + NB + "h"
    dcp = r.eff("dte_vs_always", "delay_prio1_p90_censored_h", mix=S)
    V["R1-CP90-GM-STRICT"], V["R1-CP90-W-STRICT"] = ratio(dcp), wil(dcp["wilcoxon_p"])
    yc = f["year_blocked"][f"dte_vs_always|{S}|0.0|delay_prio1_p90_censored_h"]
    V["R1-CP90-YB-STRICT"] = f"{h_(yc['diff'], 0, True)} {ci(yc['ci_lo'], yc['ci_hi'])}"
    assert dt["p90_censored_bound_share"] == 1.0
    V["R1-CP90-BOUND-ALWAYS"] = words(round(al["p90_censored_bound_share"] * al["n_seeds"]))
    V["R1-CP90-MEAN-ALWAYS-STRICT"] = h_(al["delay_prio1_p90_censored_h"])
    V["R1-P90-ALWAYS-STRICT"], V["R1-P90-DTE-STRICT"] = h_(al["delay_prio1_p90_h"]), h_(dt["delay_prio1_p90_h"])
    V["R1-COMP-LOW-STRICT"] = sh(r.acell(S, low)["prio1_completion_share"])
    V["R1-COMP-MIN-RELAY"] = sh(min(r.acell(m, p)["prio1_completion_share"] for m in NEEDS_LINK for p in r.relay_levels))
    curve = [p for p in r.relay_levels if p in (low, 0.1, 0.2, 0.5, 1.0)]
    parts = [f"{cens(r.acell(S, p))}{NB}h at {'full coverage' if p == 1.0 else pfmt(p)}" for p in curve]
    V["R1-STRICT-CP90-CURVE"] = listing(parts)
    r05 = r.eff("relay_vs_always", "delay_prio1_p90_h", mix=S, p=0.5)
    V["R1-REL05-DIFF"] = f"{h_(r05['diff'])} {ci(r05['ci_lo'], r05['ci_hi'])}"
    y5 = f["year_blocked"][f"relay_vs_always|{S}|0.5|delay_prio1_p90_h"]
    V["R1-REL05-YB"] = f"{h_(y5['diff'])} {ci(y5['ci_lo'], y5['ci_hi'])}"
    L = f["laws"]

    def target(mix, key):
        pt, cc = L[mix]["delay_prio1_p90_h"]["point"], L[mix]["delay_prio1_p90_h"]["ci95"]
        g = lambda v: (f"&le;&nbsp;{pfmt(low)}" if v < low - 1e-9 else
                       ("beyond full coverage" if not math.isfinite(v) else f"{v:.2f}"))
        lo, hi = cc[key]
        return f"{g(pt[key])} [{g(lo)}, {g(hi)}]"

    V["R1-P-2X-STRICT"], V["R1-P-15X-STRICT"] = target(S, "p_2x_cells"), target(S, "p_1.5x_cells")
    V["R1-P-2X-STRATEGIC"] = target("supervised_strategic", "p_2x_cells")
    V["R1-P-2X-AVOID"] = target("supervised_strategic+avoid", "p_2x_cells")
    rises = []
    for mix, lab in ((S, "the strict fleet's"), ("default", "the reference mix's")):
        P, M = L[mix]["delay_prio1_p90_h"]["p"], L[mix]["delay_prio1_p90_h"]["cell_mean"]
        for i in range(1, len(P)):
            if P[i] > 0 and P[i - 1] > 0 and M[i] > 1.05 * M[i - 1]:
                rises.append(f"{lab} mean is {h_(M[i - 1], 1)} at {pfmt(P[i - 1])} and {h_(M[i], 1)} at {pfmt(P[i])}")
    V["R1-NONMONO"] = "; ".join(rises) if rises else "none of the strict or reference cells rises by more than 5&#8239;%"
    cv, ins = L[S]["delay_prio1_p90_h"]["cv_rmse_log"], L[S]["delay_prio1_p90_h"]["insample_rmse_log"]
    V["R1-CV-STRICT"] = listing([f"{cv[k]:.3f}" for k in ("hyperbolic", "exponential", "power")])
    V["R1-INS-STRICT"] = f"{ins['hyperbolic']:.3f} and {ins['power']:.3f} against {ins['exponential']:.3f}"

    # ---- 5.4 policies -------------------------------------------------------------------------------------------
    pe = lambda mix, metric, p: r.eff("policy_vs_strict", metric, mix=mix, p=p)
    ST, AV = "supervised_strategic", "supervised_strategic+avoid"
    c0 = pe(ST, "prio1_completion_share", 0.0)
    V["R1-STRAT-COMP-MED"], V["R1-STRICT-COMP-MED"] = sh(c0["cell_median"]), sh(c0["ref_median"])
    V["R1-STRAT-LANDED-GM"] = ratio(pe(ST, "delivered_landed_t", 0.0))
    s0 = pe(ST, "delay_prio1_p90_censored_h", 0.0)
    V["R1-STRAT-CP90-GM"], V["R1-STRAT-CP90-W"] = ratio(s0), wil(s0["wilcoxon_p"])
    yt = r.year(ST, "dte", "delivered_t_in_year")
    ya = r.year(ST, "always", "delivered_t_in_year")
    V["R1-STRAT-T-BY-YEAR"] = listing([num(v) for v in yt["mean"]]) + NB + "t"
    good = int((yt["mean"] >= 0.9 * ya["mean"]).sum())
    V["R1-STRAT-GOOD-YEARS"] = f"{words(good)} of {words(len(yt))}"
    sd = AN.select(a, p=0.0, mix=ST).groupby("start_year")["blackout_wait_vehicle_h"].mean()
    bad = int(yt["mean"].idxmin())
    V["R1-STRAT-WAIT-2028"] = num(sd.loc[bad])
    assert bad == 2028, "the worst strategic DTE year is no longer 2028; reword Section 5.4"
    V["R1-STRAT-WAIT-OTHER"] = rng_txt([sd.loc[y] for y in sd.index if y != bad], num)
    # the 2028 mechanism (results/E21_strategic_years.json, experiments/phase4/strategic_years.py, B-55)
    sy = json.load(open(os.path.join(RES, "E21_strategic_years.json"), encoding="utf-8"))
    st28 = sy["stranding"]["2028"]
    top = sy["stranding_2028_top_samples"][0]
    MON = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"]
    first = next(i for i, x in enumerate(top["monthly_linked_2028_2031"]) if x > 0)
    y0, m0 = map(int, sy["calendar"]["months"][first].split("-"))
    assert y0 > 2028, "Section 5.4 says the dark sample sees Earth at no hour in 2028"
    V["R1-SY-FIRST-LINK"] = f"{MON[m0 - 1]} {y0}"
    V["R1-SY-SHARE"] = sh(top["stranded_rover_hours"] / st28["runs"] / st28["stranded_rover_hours_per_run"])
    legs = sy["stranded_rover_hours_per_run_by_leg"]
    assert max(legs, key=lambda k: legs[k]["2028"]) == "ISRU->CONSTR", "Section 5.4 names the ISRU->CONSTR haul"
    fs = st28["stranded_fleet_share_by_month"]
    V["R1-SY-JAN"], V["R1-SY-LATE"] = sh(fs[0]), sh(sum(fs[4:]) / len(fs[4:]))
    V["R1-SY-NOTRESUME"] = sh(st28["share_not_resuming_in_year"])
    V["R1-SY-NOTRESUME-OTHER"] = rng_txt([100 * sy["stranding"][y]["share_not_resuming_in_year"]
                                          for y in ("2029", "2030", "2031")], lambda v: f"{math.floor(v + 0.5)}", PCT)
    sw = sy["swap"]
    assert sw["seeds_lowest_in_2028"] == len(sw["delivered_t_in_year"]["2028"]) and sw["landings_identical_across_years"]
    V["R1-SY-SWAP-N"] = words(sw["seeds_lowest_in_2028"])
    V["R1-SY-SWAP"] = listing([num(sw["delivered_t_in_year_mean"][y]) for y in ("2028", "2029", "2030", "2031")]) + NB + "t"
    sk = sy["sky"]["earth_at_base"]
    V["R1-SY-MAXEL"] = rng_txt([sk[y]["max_elevation_deg"] for y in sk], lambda v: f"{v:.1f}", "&deg;")
    br = lambda r_: f"{num(r_[0], 1)}&deg; to {num(r_[1], 1)}&deg;"
    V["R1-SY-BEAR-2028"] = br(sk["2028"]["bearing_range_when_above_5.5deg"])
    V["R1-SY-BEAR-2030"] = br(sk["2030"]["bearing_range_when_above_5.5deg"])
    smp = sy["sky"]["samples"][str(top["sample"])]
    bd = smp["bearing_deg_when_linked"]
    assert sk["2028"]["bearing_range_when_above_5.5deg"][1] < bd[0], "Section 5.4: in 2028 high Earth never reaches the sample's window"
    V["R1-SY-SAMPLE-BEAR"] = br((bd[0], bd[-1]))
    V["R1-SY-BOX-HOURS"] = listing([num(x) for x in smp["earth_in_its_sky_box_hours_by_year"]])
    ca = r.acell(AV, 0)
    V["R1-AVOID-COMP-DTE"] = sh(ca["prio1_completion_share"])
    V["R1-AVOID-CP90-GM"] = ratio(pe(AV, "delay_prio1_p90_censored_h", 0.0))
    V["R1-AVOID-T-DIFF"] = dci(pe(AV, "delivered_t_in_year", 0.0), 1, sign=False)
    V["R1-WAIT-AVOID-DTE"] = num(ca["blackout_wait_vehicle_h"])
    V["R1-WAIT-STRAT-DTE"] = num(r.acell(ST, 0)["blackout_wait_vehicle_h"])
    p1 = pe(ST, "delay_prio1_p90_h", 0.1)
    V["R1-STRAT-P90-GM-01"], V["R1-STRAT-P90-W-01"] = ratio(p1), wil(p1["wilcoxon_p"])
    ys = f["year_blocked"][f"policy_vs_strict|{ST}|0.1|delay_prio1_p90_h"]
    V["R1-STRAT-P90-YB-01"] = f"{h_(ys['diff'], 0, True)} {ci(ys['ci_lo'], ys['ci_hi'])}"
    V["R1-STRAT-P90-GM-05"] = ratio(pe(ST, "delay_prio1_p90_h", 0.5))
    q1, q5 = pe(ST, "delay_prio1_p90_censored_h", 0.1), pe(ST, "delay_prio1_p90_censored_h", 0.5)
    V["R1-STRAT-CP90-GM-01"], V["R1-STRAT-CP90-W-01"] = ratio(q1), wil(q1["wilcoxon_p"])
    V["R1-STRAT-CP90-GM-05"], V["R1-STRAT-CP90-W-05"] = ratio(q5), wil(q5["wilcoxon_p"])
    V["R1-STRAT-COMP-DIFF-01"] = pts(pe(ST, "prio1_completion_share", 0.1))
    V["R1-AVOID-P90-GM-01"] = ratio(pe(AV, "delay_prio1_p90_h", 0.1))
    V["R1-AVOID-CP90-GM-01"] = ratio(pe(AV, "delay_prio1_p90_censored_h", 0.1))
    cut = [-pe(m, "blackout_wait_vehicle_h", 0.1)["rel_pct"] for m in (ST, AV)]
    V["R1-STRAT-WAIT-CUT-01"] = f"{pc(cut[0])} and {pc(cut[1])}"

    # the strategic rule's free re-draw at never-linked samples and the bounded rule (Stage F, B-57)
    bz = f["bounded"]
    rdw = {(x["policy"], x["link"]): x for x in bz["redraws"]}
    sr = rdw[("strategic", "DTE")]
    assert all(rdw[("strategic", k)]["refused_per_run"] == 0 for k in ("relay 0.1", "relay 0.5")), "5.4: no re-draws with a relay"
    V["R1-F-REDRAWS"] = num(sr["refused_per_run"])
    V["R1-F-REDRAWS-BY-YEAR"] = listing([num(sr[f"refused_per_run_{y}"]) for y in (2028, 2029, 2030, 2031)])
    nl = bz["never_linked_legs"]
    V["R1-F-NEVER-LEGS"] = f"{nl['main_network_legs_with_never_linked_sample']} of the {nl['main_network_legs']}"
    V["R1-F-NEVER-SAMPLES"] = f"{nl['samples_never_linked']} of {nl['samples']:,}"
    assert sum("ISRU" in k for k in nl["main_network_list"]) == 16, "5.4 names the oxygen plant's legs"
    fc = {(x["link"], x["variant"]): x for x in bz["cells"]}
    SN = "strategic, strand on never-linked"
    sn, sa = fc[("DTE", SN)], fc[("DTE", "strategic (Stage A)")]
    for lk in ("relay 0.1", "relay 0.5"):        # with a relay nothing is never linked: strand = strategic
        assert abs(fc[(lk, SN)]["mean"]["delivered_t_in_year"] - fc[(lk, "strategic (Stage A)")]["mean"]["delivered_t_in_year"]) < 1e-9
    V["R1-F-STRAND-T"] = t_(sn["mean"]["delivered_t_in_year"])
    V["R1-F-STRAND-T-BY-YEAR"] = rng_txt([v["delivered_t_in_year"] for v in sn["by_year"].values()], num, NB + "t")
    V["R1-F-STRAND-COMP"] = sh(sn["mean"]["prio1_completion_share"])
    V["R1-F-STRAND-WAIT"] = num(sn["mean"]["blackout_wait_vehicle_h"])
    fe = lambda ref, cell, metric, y="all": _match(r.fb, family="bounded" if y == "all" else "bounded_by_year", p=0.0,
                                                   reference=ref, cell=cell, metric=metric, start_year=y).iloc[0]
    V["R1-F-STRAND-VS-STRAT"] = dci(fe("strategic", SN, "delivered_t_in_year"))
    fr = AN.select(raw["F"], p=0.0, mix=ST, never_linked="strand")
    ps = paired_raw(AN.select(a, p=0.0, mix="supervised_strict"), fr, "delivered_t_in_year")
    assert ps["n"] == 20 and ps["ci_hi"] < 0, "5.4: the stranding strategic fleet delivers less than the strict fleet"
    V["R1-F-STRAND-VS-STRICT"] = dci(ps)
    pc_ = paired_raw(AN.select(a, p=0.0, mix="supervised_strict"), fr, "prio1_completion_share")
    V["R1-F-STRAND-VS-STRICT-COMP"] = pts(pc_)
    vd = {x["variant"]: x for x in bz["verdict_dte"]}
    BOUNDS = (24, 72, 168, 720)
    ref_ = [vd[f"bound {b} h, never-linked refused"] for b in BOUNDS]
    kee = [vd[f"bound {b} h, never-linked as strategic"] for b in BOUNDS]
    assert all(not v["keeps_isru"] and v["avoids_2028_collapse"] for v in ref_), "5.4: refusing never-linked routes"
    assert all(v["keeps_isru"] and not v["avoids_2028_collapse"] for v in kee), "5.4: leaving them to the re-draw"
    V["R1-F-REFUSE-T"] = rng_txt([fc[("DTE", v["variant"])]["mean"]["delivered_t_in_year"] for v in ref_], num, NB + "t")
    V["R1-F-REFUSE-WAIT"] = rng_txt([fc[("DTE", v["variant"])]["mean"]["blackout_wait_vehicle_h"] for v in ref_], num)
    V["R1-F-KEEP-2028"] = rng_txt([v["t_2028"] for v in kee], num, NB + "t")
    V["R1-F-KEEP-LATER"] = rng_txt([v["t_2029_2031"] for v in kee], num, NB + "t")
    V["R1-F-KEEP-BULK"] = rng_txt([100 * v["bulk_share_of_strategic"] for v in kee], num, PCT)
    k28 = fe("strategic", "bound 24 h, never-linked as strategic", "delivered_t_in_year", "2028")
    V["R1-F-KEEP-2028-VS-STRAT"] = dci(k28)
    V["R1-F-STRAT-2028"] = t_(vd["strategic (Stage A)"]["t_2028"])
    ps_ = bz["pool_starvation"]
    last = ps_["moments"][-1]
    assert last["pool"] == last["pool_blocked"] == ps_["pool_cap"] and max(last["pool_lanes"], key=last["pool_lanes"].get) == "CONSTR->ISRU"
    V["R1-F-POOL-CAP"] = f"{ps_['pool_cap']}"
    V["R1-F-POOL-T"] = num(last["t_h"])
    V["R1-F-POOL-ISRU"] = f"{last['pool_lanes']['CONSTR->ISRU']}"
    V["R1-F-POOL-SERVABLE"] = f"{last['beyond_cap_servable_now']}"
    V["R1-F-POOL-FREE"] = words(last["free_rovers"])
    pa = ps_["all_2028_seeds"]
    assert pa["pool_full_share_mean"] > 0.5 and pa["constr_isru_share_of_slots_mean"] > 0.5
    V["R1-F-POOL-N"] = words(pa["n_runs"])
    V["R1-F-POOL-FULL-ALL"] = sh(pa["pool_full_share_mean"])
    V["R1-F-POOL-ISRU-ALL"] = sh(pa["constr_isru_share_of_slots_mean"])
    ls_ = [x for x in ps_["strict"] + ps_["look_ahead"]]
    assert all(x["pool_full_share"] == 0 for x in ls_), "Section 7: the strict and look-ahead pools are never full"
    V["R1-F-POOL-STRICT"] = rng_txt([100 * x["blocked_share_of_slots"] for x in ls_], num, PCT)

    # how fast help must come where Earth never rises (Stage G, B-59)
    rz = f["rescue"]
    ge = lambda ref, h, metric: _match(r.gb, family="rescue", rescue_h=float(h), start_year="all", reference=ref,
                                       metric=metric).iloc[0]
    LV = [lv["rescue_h"] for lv in rz["levels"]]
    assert LV == [0.0, 24.0, 72.0, 168.0, 720.0], "Section 5.4 names a week (168 h) and a month (720 h)"
    WK = [h for h in LV if h <= 168]
    V["R1-G-WEEK-T"] = rng_txt([lv["mean"]["delivered_t_in_year"] for lv in rz["levels"] if lv["rescue_h"] <= 168], num, NB + "t")
    vs = [ge("strategic", h, "delivered_t_in_year") for h in WK]
    assert all(x["ci_lo"] < 0 < x["ci_hi"] for x in vs), "5.4: help within a week is indistinguishable from the free re-draw"
    assert all(ge("strategic", h, "delay_prio1_p90_censored_h")["wilcoxon_p"] > 0.05 for h in WK)
    V["R1-G-WEEK-VS-STRAT"] = dci(vs[-1])
    V["R1-G-WEEK-CP90-VS-STRAT"] = ratio(ge("strategic", 168, "delay_prio1_p90_censored_h"))
    m7 = ge("strict", 720, "delivered_t_in_year")
    assert m7["ci_lo"] < 0 < m7["ci_hi"], "5.4: help after a month delivers no more tonnage than strict"
    V["R1-G-MONTH-T"], V["R1-G-MONTH-VS-STRICT"] = t_(m7["cell_mean"]), dci(m7)
    mc = ge("strict", 720, "prio1_completion_share")
    assert mc["ci_lo"] > 0, "5.4: help after a month still completes more urgent items than strict"
    V["R1-G-MONTH-COMP"], V["R1-G-MONTH-COMP-VS-STRICT"] = sh(mc["cell_mean"]), pts(mc)
    mp = ge("strict", 720, "delay_prio1_p90_censored_h")
    V["R1-G-MONTH-CP90-GM"], V["R1-G-MONTH-CP90-W"] = ratio(mp), wil(mp["wilcoxon_p"])
    ms = ge("strategic", 720, "delivered_t_in_year")
    assert ms["ci_hi"] < 0
    V["R1-G-MONTH-VS-STRAT"] = dci(ms)
    V["R1-G-MONTH-COMP-VS-STRAT"] = pts_abs(ge("strategic", 720, "prio1_completion_share"))
    mq = ge("strategic", 720, "delay_prio1_p90_censored_h")
    assert mq["gm_ratio_lo"] > 1, "5.4: help after a month lengthens the censored delay against the re-draw"
    V["R1-G-MONTH-CP90-VS-STRAT"], V["R1-G-MONTH-CP90-VS-STRAT-W"] = ratio(mq), wil(mq["wilcoxon_p"])
    hx = lambda v: v if isinstance(v, str) else h_(v)
    be = rz["breakeven_vs_strict"]["delivered_t_in_year"]
    assert be["breakeven_h"] == "beyond 720 h", "5.4 says the tonnage break-even lies at about 720 h or beyond"
    V["R1-G-BE-T-CI"] = f"{hx(be['ci95'][0])} to {hx(be['ci95'][1])}"
    V["R1-G-BE-T-BEYOND"] = sh(be["share_beyond_range"])
    V["R1-G-BE-T-BELOW"] = sh(be["share_below_range"])
    assert rz["breakeven_vs_strict"]["prio1_completion_share"]["share_beyond_range"] == 1.0, "5.4: 'in every draw'"
    y28 = [lv["by_year"]["2028"]["delivered_t_in_year"] for lv in rz["levels"]]
    assert max(y28) < 0.5 * min(lv["by_year"][y]["delivered_t_in_year"] for lv in rz["levels"] if lv["rescue_h"] <= 168
                                for y in ("2029", "2030", "2031")), "5.4: 2028 still collapses with help"
    V["R1-G-2028"] = rng_txt(y28, num, NB + "t")
    V["R1-G-RESCUES"] = f"{num(rz['levels'][0]['rescues_per_run'])} to {num(rz['levels'][-1]['rescues_per_run'])}"

    # help for any long wait (Stage G2, B-60)
    ra = f["rescue_any"]
    g2 = lambda ref, h, metric, y="all": _match(r.g2, family="rescue" if y == "all" else "rescue_by_year", rescue_h=float(h),
                                                start_year=y, reference=ref, metric=metric).iloc[0]
    assert [lv["rescue_h"] for lv in ra["levels"]] == LV
    lv2 = {lv["rescue_h"]: lv for lv in ra["levels"]}
    wk2 = [lv2[h] for h in WK]
    t_always_st = r.acell(ST, None)["delivered_t_in_year"]
    V["R1-T-ALWAYS-STRAT"] = t_(t_always_st)
    assert min(lv["by_year"][y]["delivered_t_in_year"] for lv in wk2 for y in lv["by_year"]) >= 0.95 * t_always_st, \
        "5.4: with help within a week for any wait, every start year is within 5 % of always-linked tonnage"
    V["R1-G2-WEEK-T"] = rng_txt([lv["mean"]["delivered_t_in_year"] for lv in wk2], num, NB + "t")
    V["R1-G2-WEEK-2028"] = rng_txt([lv["by_year"]["2028"]["delivered_t_in_year"] for lv in wk2], num, NB + "t")
    V["R1-G2-2028-VS-STRAT"] = dci(g2("strategic", 168, "delivered_t_in_year", "2028"))
    V["R1-G2-VS-STRICT-168"] = dci(g2("strict", 168, "delivered_t_in_year"))
    V["R1-G2-COMP-168"] = sh(lv2[168.0]["mean"]["prio1_completion_share"])
    m2 = g2("strict", 720, "delivered_t_in_year")
    assert m2["ci_lo"] > 0, "5.4: with help after a month for any wait the fleet still beats strict in tonnage"
    V["R1-G2-MONTH-T"], V["R1-G2-MONTH-VS-STRICT"] = t_(m2["cell_mean"]), dci(m2)
    V["R1-G2-MONTH-2028"] = t_(lv2[720.0]["by_year"]["2028"]["delivered_t_in_year"])
    bt, bc2 = ra["breakeven_vs_strict"]["delivered_t_in_year"], ra["breakeven_vs_strict"]["prio1_completion_share"]
    assert bt["share_beyond_range"] >= 0.99 and bc2["share_beyond_range"] == 1.0, "5.4: break-evens beyond 720 h"
    V["R1-G2-BE-T-SHARE"] = sh(bt["share_beyond_range"], 2)
    assert lv2[0.0]["mean"]["blackout_wait_vehicle_h"] == 0, "5.4: at 0 h no intervention waits at all"
    V["R1-G2-RESCUES-168"] = num(lv2[168.0]["rescues_per_run"])
    V["R1-G2-RESCUES-0"] = num(lv2[0.0]["rescues_per_run"])
    # why urgent cargo survives the 2028 stranding (B-60 diagnostic b)
    su = sy["strategic_2028_urgent"]
    assert su["runs_reproduce_e21"]
    V["R1-SY-URG-N"] = num(sum(su["urgent_ready_by_month"]))
    V["R1-SY-URG-BASE"] = sh(su["urgent_by_dest"]["BASE"] / sum(su["urgent_by_dest"].values()))
    V["R1-SY-URG-COMP"] = sh(su["urgent_completion"])
    V["R1-SY-FREE-LATE"] = rng_txt(su["rovers_not_stranded_by_month"][5:], lambda v: num(v, 1))
    assert sy["swap"]["landings_identical_across_years"] and not sy["swap"]["manifests_identical_across_years"]

    # can a helper park where it sees Earth and the held rover? (B-61, parking-v1.json)
    pk = json.load(open(os.path.join(RES, "E21_parking.json"), encoding="utf-8"))
    assert pk["no_working_point"] == [], "5.4: every held sample has a working parking point"
    V["R1-PK-H-N"] = f"{pk['set_h']['n']}"
    c0 = pk["help_delay"]["call"]["0"]["all"]
    V["R1-PK-ANY-0"], V["R1-PK-ANY-168"] = sh(c0["all"][0]), sh(c0["all"][2])
    V["R1-PK-MARGIN-168"] = sh(c0["all_margin_1m"][2])
    ga = max(max(pk["grid_adds"]["call"][k]["gain_pp"]) for k in ("0", "168"))
    assert ga < 1.0, "5.4: the grid adds under one percentage point"
    V["R1-PK-GRID-GAIN"] = f"at most {num(ga, 1)} percentage points"
    u0 = pk["uncovered_calls"]["0|all"]
    assert u0["earth_below_level_share"] > 0.9 and u0["earth_below_lowest_candidate_horizon_share"] > 0.99
    V["R1-PK-UNCOV"] = sh(u0["uncovered_share"])
    V["R1-PK-UNCOV-BELOW"] = sh(u0["earth_below_level_share"])
    V["R1-PK-UNCOV-BELOW-CAND"] = sh(u0["earth_below_lowest_candidate_horizon_share"], 1)
    V["R1-PK-UNCOV-LIMB"] = f"{num(u0['earth_upper_limb_deg_q10_50_90'][1], 1)}&deg;"
    V["R1-PK-UNCOV-HOR"] = f"{num(u0['lowest_candidate_horizon_deg_q10_50_90'][1], 1)}&deg;"
    V["R1-PK-UNCOV-CLEAR"] = h_(u0["h_until_earth_clears_lowest_horizon_q10_50_90"][1])
    V["R1-PK-2HOP"] = sh(u0["two_hop_candidate_share"])
    V["R1-PK-2HOP-MAST"] = sh(u0["two_hop_mast_linked_within_0_24_168h_share"][2])
    s188, sis = pk["spotlights"]["dark_sample_188"], pk["spotlights"]["isru"]
    V["R1-PK-188-DIST"] = f"{num(s188['best']['dist_m'] / 1000, 2)}{NB}km"
    V["R1-PK-188-LINK"] = sh(s188["best"]["link_fraction"])
    V["R1-PK-188-DARK"] = sh(s188["dark_spell_jan2028_jun2029"]["best"][2])
    V["R1-PK-188-CLEAR"] = f"{num(100 * s188['best']['clear_m'])}{NB}cm"
    assert sis["never_linked"]
    V["R1-PK-ISRU-DIST"] = f"{num(sis['best']['dist_m'] / 1000, 2)}{NB}km"
    V["R1-PK-ISRU-168"] = sh(sis["best"]["share"][2])

    # a real helper (Stage H, B-62)
    hz = f["helper"]
    hc = {x["label"]: x for x in hz["cells"]}
    H24 = ["dedicated k=1, 24 h", "dedicated k=2, 24 h", "from fleet k=1, 24 h", "dedicated k=1, 24 h, S=2 h"]
    H168 = ["dedicated k=1, 168 h", "from fleet k=1, 168 h"]
    assert set(hc) == set(H24 + H168) and sorted(hz["g2_headline_kept_by"]) == sorted(H24)
    assert all(hz["g2_headline_lost_by"][k] == ["2029", "2030", "2031"] for k in H168), "5.4: 168 h keeps 2028 only"
    worst = lambda k: min(hc[k]["share_of_always_linked_by_year"].values())
    d1, d168 = hc["dedicated k=1, 24 h"], hc["dedicated k=1, 168 h"]
    V["R1-H-24-T"] = t_(d1["mean"]["delivered_t_in_year"])
    V["R1-H-24-WORST"] = sh(worst("dedicated k=1, 24 h"))
    V["R1-H-24-WORST-ALL"] = rng_txt([100 * worst(k) for k in H24], num, PCT)
    V["R1-H-24-VS-G2"] = dci(d1["tonnage_vs"]["G2 same threshold (ideal helper)"], 1)
    V["R1-H-24-VS-STRICT"] = dci(d1["tonnage_vs"]["strict"])
    V["R1-H-24-COMP"] = sh(d1["mean"]["prio1_completion_share"])
    V["R1-H-FLEET-24-T"] = t_(hc["from fleet k=1, 24 h"]["mean"]["delivered_t_in_year"])
    h1 = d1["helper"]
    V["R1-H-CALLS"], V["R1-H-HELPS"] = num(h1["calls_per_run"]), num(h1["helps_per_run"])
    V["R1-H-REL-MEAN"] = h_(h1["call_to_release_mean_h"])
    V["R1-H-REL-P90"] = h_(h1["call_to_release_p90_h_median_of_runs"])
    V["R1-H-UTIL"] = sh(h1["utilisation"])
    pk_ = [hc[k]["helper"]["busy_split_share"]["parked_waiting_for_earth"] for k in hc]
    assert min(pk_) > 0.9, "5.4: the helper's busy time is mostly parked"
    V["R1-H-PARKED"] = rng_txt([100 * v for v in pk_], lambda v: num(v), PCT)
    V["R1-H-DRIVE"] = rng_txt([100 * hc[k]["helper"]["busy_split_share"]["driving"] for k in hc], lambda v: num(v, 1), PCT)
    V["R1-H-UNSERVED"] = rng_txt([hc[k]["helper"]["unserved_per_run"] for k in hc], lambda v: num(v, 1))
    rs_ = hz["references"]
    g1 = rs_["strict + 1 rover"]["mean"]["delivered_t_in_year"] - rs_["strict"]["mean"]["delivered_t_in_year"]
    assert 0 <= g1 < 1, "5.4: one more hauler adds under a tonne under strict DTE"
    V["R1-H-ROVER-GAIN"] = t_(g1, 1)
    V["R1-H-168-T"] = t_(d168["mean"]["delivered_t_in_year"])
    V["R1-H-168-2028"] = sh(d168["share_of_always_linked_by_year"]["2028"])
    V["R1-H-168-WORST"] = sh(d168["share_of_always_linked_by_year"]["2029"], 1)
    V["R1-H-168-FLEET-WORST"] = sh(hc["from fleet k=1, 168 h"]["share_of_always_linked_by_year"]["2029"], 1)
    assert min(d168["share_of_always_linked_by_year"], key=d168["share_of_always_linked_by_year"].get) == "2029"
    dg = hz["diagnosis_168h"]
    p29 = dg["paired_by_start_year"]["2029"]
    V["R1-H-168-2029-VS-G2"] = dci(p29["delivered_t_in_year"], 1)
    V["R1-H-168-2029-BULK"] = t_(p29["delivered_bulk_t"]["diff"], 1)
    ex = [dg["by_year"][y]["excess_h_per_run"] for y in ("2028", "2029")]
    assert abs(ex[0] - ex[1]) / ex[0] < 0.01, "5.4: the same held hours in 2028 and 2029"
    V["R1-H-168-HELD"] = listing([num(v) for v in ex])

    # ---- 5.5 break-even -------------------------------------------------------------------------------------------
    bc = lambda p, pol, n, mast="none": _match(r.c[r.c["stage"] == "B"], p=p, policy=pol, extra_rovers=n, mast=mast).iloc[0]
    rov = lambda n, metric, p=0.5: r.eff("rovers_vs_0", metric, p=p, policy="strict", extra_rovers=float(n))
    base = bc(0.5, "strict", 0)
    V["R1-B-BASE-P90"], V["R1-B-ROVER1-P90"] = h_(base["delay_prio1_p90_h"], 1), h_(bc(0.5, "strict", 1)["delay_prio1_p90_h"], 1)
    r1 = rov(1, "delay_prio1_p90_h")
    V["R1-B-ROVER1-DIFF"], V["R1-B-ROVER1-GM"], V["R1-B-ROVER1-W"] = dci(r1, 1, "h"), ratio(r1), wil(r1["wilcoxon_p"])
    yr1 = f["year_blocked"]["rovers_vs_0|supervised|0.5|delay_prio1_p90_h"]
    V["R1-B-ROVER1-YB"] = f"{h_(yr1['diff'], 1, True)} {ci(yr1['ci_lo'], yr1['ci_hi'], 1)}"
    V["R1-B-ROVER1-CP90-GM"] = ratio(rov(1, "delay_prio1_p90_censored_h"))
    V["R1-B-ROVER1-COMP"], V["R1-B-BASE-COMP"] = sh(bc(0.5, "strict", 1)["prio1_completion_share"]), sh(base["prio1_completion_share"])
    V["R1-B-ROVER2-DIFF"], V["R1-B-ROVER3-DIFF"] = dci(rov(2, "delay_prio1_p90_h"), 1, "h"), dci(rov(3, "delay_prio1_p90_h"), 1, "h")
    r2 = rov(2, "delay_prio1_p90_h")
    V["R1-B-ROVER2-GM"], V["R1-B-ROVER2-W"] = ratio(r2), wil(r2["wilcoxon_p"])
    V["R1-B-PEAK0"], V["R1-B-PEAK3"] = f"{base['operator_peak_demand']:.2f}", f"{bc(0.5, 'strict', 3)['operator_peak_demand']:.2f}"
    V["R1-B-MAST-DIFF"] = dci(r.eff("mast_vs_none", "delay_prio1_p90_h", p=0.5, policy="strict"), 1, "h")
    bd = f["breakeven_delay"]
    be5 = breakevens(r, 0.5, [("+1 rover", "strict", 1, "none"), ("+2 rovers", "strict", 2, "none"),
                              ("+3 rovers", "strict", 3, "none"), ("strategic step", "strategic", 0, "none"),
                              ("look-ahead step", "strategic+avoid", 0, "none"),
                              ("strategic step + 1 rover", "strategic", 1, "none"), ("mast", "strict", 0, "BASE 10 m")])
    # the recomputed p = 0.5 rows must equal the analysis's
    for o in bd["options"]:
        x = be5[o["option"]]
        assert abs(x["dp"] - o["delta_p"]) < 1e-9 and abs(x["lo"] - o["delta_p_ci95_lo"]) < 1e-9, o["option"]
    assert abs(be5["_price"][0] - bd["price_musd_per_0.1_coverage"]) < 1e-6
    assert abs(be5["_price"][2] - bd["price_ci95"][1]) < 1e-6
    be2 = breakevens(r, 0.2, [("+1 rover", "strict", 1, "none"), ("strategic step", "strategic", 0, "none")])
    be8 = breakevens(r, 0.8, [("+1 rover", "strict", 1, "none"), ("strategic step", "strategic", 0, "none")])
    V["R1-DP-ONE-LTV"] = dp_txt(be5["+1 rover"])
    V["R1-SHARE-NONPOS"] = pc(100 * bd["share_draws_rover_buys_nothing"], 2)
    V["R1-SHARE-BEYOND"] = pc(100 * bd["share_draws_rover_beyond_full_coverage"], 2)
    pr, plo, phi = bd["price_musd_per_0.1_coverage"], bd["price_ci95"][0], bd["price_ci95"][1]
    if math.isfinite(phi):
        V["R1-MUSD-PER-01"] = f"{num(pr)}{NB}M$ {ci(plo, phi)}"
    else:
        V["R1-MUSD-PER-01"] = f"{num(pr)}{NB}M$ [{num(plo)}, unbounded]"
    if bd["price_upper_poorly_determined"]:
        V["R1-MUSD-PER-01-ABS"] = f"{num(pr)}{NB}M$ ({num(plo)} to over 200{NB}M$)"
        V["R1-PRICE-UPPER-NOTE"] = ("is above 200&nbsp;M$ and poorly determined: it rests on the few draws in which "
                                    "the rover buys almost nothing, where the price 4.5/&Delta;<i>p</i> grows without bound")
    else:
        V["R1-MUSD-PER-01-ABS"] = V["R1-MUSD-PER-01"]
        V["R1-PRICE-UPPER-NOTE"] = f"is {num(phi)}{NB}M$"
    V["R1-DP-STRAT"], V["R1-DP-AVOID"] = dp_txt(be5["strategic step"]), dp_txt(be5["look-ahead step"])
    V["R1-DP-STRAT-ROVER"] = dp_txt(be5["strategic step + 1 rover"])
    V["R1-SHARE-BEYOND-STRATROVER"] = pc(100 * be5["strategic step + 1 rover"]["beyond"])
    sm = bd["strategic_minus_rover"]
    V["R1-DP-DIFF"] = f"{num(sm['point'], 2, True)} [{num(sm['ci95'][0], 2)}, {num(sm['ci95'][1], 2)}]"
    V["R1-DP-DIFF-SHARE"] = pc(100 * sm["share_positive"])
    V["R1-B-ROVER1-DIFF-02"] = dci(rov(1, "delay_prio1_p90_h", 0.2), 1, "h")
    V["R1-B-ROVER1-DIFF-08"] = dci(rov(1, "delay_prio1_p90_h", 0.8), 1, "h")
    bpol = lambda p: r.eff("b_policy_vs_strict", "delay_prio1_p90_h", p=p, policy="strategic", extra_rovers=0.0, mast="none")
    V["R1-B-STRAT-GM-02"], V["R1-B-STRAT-GM-08"] = ratio(bpol(0.2)), ratio(bpol(0.8))
    V["R1-DP-ROVER-02"], V["R1-DP-STRAT-02"] = dp_txt(be2["+1 rover"]), dp_txt(be2["strategic step"])
    a08 = L[S]["delay_prio1_p90_h"]
    m07, m08 = (a08["cell_mean"][a08["p"].index(x)] for x in (0.7, 0.8))
    assert m08 > m07, "the strict 0.8 cell no longer lies above 0.7; reword Section 5.5"

    # ---- 5.6 operators --------------------------------------------------------------------------------------------
    o = r.ops
    ol = o[(o["operators"] == "lenient") & (o["comms"] != "always")].copy()
    ol["x"] = np.where(ol["comms"] == "dte", 0.0, ol["p"])
    tl = ol[ol["mix"] == "teleop_4s"].set_index("x").sort_index()
    V["R1-OP-PEAK-TELEOP-DTE"] = f"{tl.loc[0.0, 'peak_mean']:.1f}"
    V["R1-OP-SEEDS-TELEOP-DTE"] = f"{int(tl.loc[0.0, 'seeds_over_staffing'])}"
    xm = float(tl["peak_mean"].idxmax())
    V["R1-OP-PEAK-TELEOP-MAXP"] = "DTE only" if xm == 0 else pfmt(xm)
    V["R1-OP-PEAK-TELEOP-MAX"] = f"{tl.loc[xm, 'peak_mean']:.1f}"
    V["R1-OP-SEEDS-TELEOP-MAXP"] = f"{int(tl.loc[xm, 'seeds_over_staffing'])}"
    V["R1-OP-PEAK-TELEOP-FULL"] = f"{tl.loc[1.0, 'peak_mean']:.1f}"
    V["R1-OP-SEEDS-TELEOP-FULL"] = f"{int(tl.loc[1.0, 'seeds_over_staffing'])}"
    assert tl["peak_mean"].idxmin() == 1.0
    dl_ = ol[ol["mix"] == "default"]
    assert int(dl_["seeds_over_staffing"].max()) == 0
    V["R1-OP-PEAK-DEFAULT-MAX"] = f"{dl_['peak_mean'].max():.1f}"
    V["R1-OP-MEAN-TELEOP-FULL"], V["R1-OP-MEAN-TELEOP-DTE"] = f"{tl.loc[1.0, 'mean_demand']:.2f}", f"{tl.loc[0.0, 'mean_demand']:.2f}"
    a2 = r.c[(r.c["stage"] == "A2") & (r.c["mix"] == "teleop_4s")].copy()
    a2["x"] = np.where(a2["comms"] == "dte", 0.0, a2["p"])
    a2 = a2.set_index("x").sort_index()
    assert (o[(o["operators"] == "strict") & (o["mix"] == "teleop_4s")]["peak_max"] <= 3.0 + 1e-9).all()
    V["R1-A2-WAIT-DTE"] = num(a2.loc[0.0, "operator_wait_vehicle_h"])
    xw = float(a2["operator_wait_vehicle_h"].idxmax())
    V["R1-A2-WAIT-MAX"], V["R1-A2-WAIT-MAXP"] = num(a2.loc[xw, "operator_wait_vehicle_h"]), pfmt(xw)
    V["R1-A2-WAIT-FULL"] = num(a2.loc[1.0, "operator_wait_vehicle_h"], 1)
    sl = r.e[(r.e["family"] == "strict_vs_lenient")]
    slt = sl[sl["mix"] == "teleop_4s"]
    V["R1-A2-T-MAXABS"] = t_(slt[slt["metric"] == "delivered_t_in_year"]["diff"].abs().max(), 1)
    V["R1-A2-COMP-MAXABS"] = f"{num(100 * slt[slt['metric'] == 'prio1_completion_share']['diff'].abs().max(), 1)} percentage points"
    sp = slt[slt["metric"] == "delay_prio1_p90_h"].sort_values("p")
    sig = sp[sp["wilcoxon_p"] < 0.05]
    big = sp.loc[sp["diff"].idxmax()]
    txt = f"rises by at most {h_(big['diff'], 1)} (at {'DTE only' if big['p'] == 0 else 'coverage ' + pfmt(big['p'])}"
    txt += ", not significant)" if big["wilcoxon_p"] >= 0.05 else ")"
    if len(sig):
        txt += (", and significantly by the Wilcoxon test only at coverage " + listing([pfmt(p) for p in sig["p"]]) +
                ", by " + listing([num(x, 1) for x in sig["diff"]]) + NB + "h")
    V["R1-A2-P90-SUMMARY"] = txt
    scp = slt[slt["metric"] == "delay_prio1_p90_censored_h"]
    assert not ((scp["gm_ratio_lo"] > 1) | (scp["gm_ratio_hi"] < 1)).any(), "censored A2 effect now significant; reword"
    sd_ = sl[sl["mix"] == "default"]
    assert (sd_["diff"].abs().fillna(0) < 1e-9).all(), "hard limit changes the reference mix; reword Section 5.6"
    fr_ = f["full_relay_vs_always"]
    ident = [m for m, v in fr_.items() if all(x["seeds_differing"] == 0 for k, x in v["metrics"].items()
                                              if k != "operator_peak_demand")]
    V["R1-FR-IDENTICAL-N"] = words(len(ident))
    assert set(fr_) - set(ident) == {"teleop_4s"}
    tm = fr_["teleop_4s"]["metrics"]
    V["R1-FR-P90-SEEDS"], V["R1-FR-P90-MAX"] = f"{tm['delay_prio1_p90_h']['seeds_differing']}", h_(tm["delay_prio1_p90_h"]["max_abs_diff"], 1)
    V["R1-FR-CP90-SEEDS"] = f"{tm['delay_prio1_p90_censored_h']['seeds_differing']}"
    V["R1-FR-CP90-MAX"] = h_(tm["delay_prio1_p90_censored_h"]["max_abs_diff"])
    V["R1-FR-T-SEEDS"], V["R1-FR-T-MAX"] = f"{tm['delivered_t_in_year']['seeds_differing']}", t_(tm["delivered_t_in_year"]["max_abs_diff"], 1)
    V["R1-FR-WAITS-SEEDS"] = f"{tm['unmet_operator_waits']['seeds_differing']}"

    # ---- 5.7 Stage C ----------------------------------------------------------------------------------------------
    cc = lambda comms, mix, pad, crit="any_part", dfr=24.0: _match(r.c[r.c["stage"] == "C"], comms=comms, mix=mix,
                                                                   pad_standoff_km=pad, criterion=crit,
                                                                   defer_wait_h=dfr).iloc[0]
    D = "default"
    c05, c1, c3 = cc("dte", D, 0.5), cc("dte", D, 1.0), cc("dte", D, 3.0)
    V["R1-C-LANDED-05"], V["R1-C-LANDED-1"] = t_(c05["delivered_landed_t"], 1), t_(c1["delivered_landed_t"], 1)
    V["R1-C-LANDED-05-DIFF"] = dci(r.eff("pads_vs_1km", "delivered_landed_t", mix=D, p=0.0, pad_standoff_km=0.5,
                                         criterion="any_part"), 1)
    V["R1-C-COMP-05"], V["R1-C-COMP-1"] = sh(c05["prio1_completion_share"]), sh(c1["prio1_completion_share"])
    for kk, v in f["throughput_split"]["pads_3km_dte"].items():
        assert v["landed_t_mean"] == 0.0 and v["seeds_with_landed_cargo"] == 0, kk
    for m in (D, "teleop_4s"):
        for crit in CRIT_LABEL:
            x = cc("dte", m, 3.0, crit)
            assert x["prio1_completion_share"] == 0.0 and x["delay_prio1_p90_h_n"] == 0
    V["R1-C-T-3"] = t_(c3["delivered_t_in_year"], 1)
    V["R1-C-CP90-3"] = cens(c3) + NB + "h"
    pr3 = lambda metric: r.eff("pads_vs_1km", metric, mix=S, p=0.8, pad_standoff_km=3.0, criterion="any_part")
    V["R1-C-RELAY-LANDED-3-DIFF"] = dci(pr3("delivered_landed_t"), 1)
    V["R1-C-RELAY-COMP-3-DIFF"] = pts(pr3("prio1_completion_share"))
    crit = r.e[(r.e["family"] == "criterion_vs_any_part") & (r.e["metric"] == "delivered_t_in_year")]
    V["R1-CRIT-RANGE"] = pc(crit["rel_pct"].abs().max(), 1)
    ce = lambda metric, mix, pad, cr, p=0.0: r.eff("criterion_vs_any_part", metric, mix=mix, p=p, pad_standoff_km=pad,
                                                  criterion=cr)
    V["R1-CRIT-05-05"] = dci(ce("delay_prio1_p90_h", D, 0.5, "centre+0.5deg"), 0, "h", sign=False)
    V["R1-CRIT-05-2"] = dci(ce("delay_prio1_p90_h", D, 0.5, "centre+2deg"), 0, "h", sign=False)
    V["R1-CRIT-1-P90"] = (f"{h_(c1['delay_prio1_p90_h'])} to {h_(cc('dte', D, 1.0, 'centre+0.5deg')['delay_prio1_p90_h'])} "
                          f"and {h_(cc('dte', D, 1.0, 'centre+2deg')['delay_prio1_p90_h'])}")
    V["R1-CRIT-1-COMP"] = (f"{sh(c1['prio1_completion_share'])} to "
                           f"{sh(cc('dte', D, 1.0, 'centre+0.5deg')['prio1_completion_share'])} and "
                           f"{sh(cc('dte', D, 1.0, 'centre+2deg')['prio1_completion_share'])}")
    tc = [ce("prio1_completion_share", "teleop_4s", 1.0, k) for k in ("centre+0.5deg", "centre+2deg")]
    V["R1-CRIT-1-COMP-TELEOP"] = (f"{sh(tc[0]['ref_mean'])} to {sh(tc[0]['cell_mean'])} and {sh(tc[1]['cell_mean'])}, "
                                  f"paired changes {pts(tc[0])} and {pts(tc[1])}")
    V["R1-CRIT-1-CP90"] = listing([ratio(ce("delay_prio1_p90_censored_h", D, 1.0, k)) for k in ("centre+0.5deg", "centre+2deg")])
    cs = r.e[(r.e["family"] == "criterion_vs_any_part") & (r.e["metric"] == "delay_prio1_p90_censored_h")]
    shorter = int((cs["gm_ratio_hi"] < 1).sum())
    V["R1-CRIT-NONE-SHORTER"] = ("In no Stage C cell does a stricter criterion shorten the censored urgent delay "
                                 "significantly." if shorter == 0 else
                                 f"A stricter criterion shortens the censored urgent delay significantly in {shorter} "
                                 "Stage C cells.")
    de = lambda metric, mix, w, p=0.0: r.eff("defer_vs_24h", metric, mix=mix, p=p, defer_wait_h=w)
    dd = [de("delay_prio1_p90_censored_h", D, w) for w in (12.0, 72.0, math.inf)]
    V["R1-DEFER-DTE-CP90-RANGE"] = rng_txt([x["gm_ratio"] for x in dd], lambda v: f"{v:.2f}")
    wmin = min([x["wilcoxon_p"] for x in dd] + [de("prio1_completion_share", D, w)["wilcoxon_p"] for w in (12.0, 72.0, math.inf)])
    V["R1-DEFER-DTE-W-MIN"] = f"<i>p</i>&nbsp;&ge;&nbsp;{math.floor(wmin * 100) / 100:.2f}"
    nd_ = de("delay_prio1_p90_h", D, math.inf)
    V["R1-DEFER24-P90"], V["R1-NODEFER-P90"] = h_(nd_["ref_mean"]), h_(nd_["cell_mean"])
    V["R1-NODEFER-GM"], V["R1-NODEFER-W"] = ratio(nd_), wil(nd_["wilcoxon_p"])
    d12 = de("prio1_completion_share", "teleop_4s", 12.0)
    assert d12["ci_hi"] < 0
    V["R1-DEFER12-TELEOP-COMP"] = pts_abs(d12)
    rp = de("delay_prio1_p90_h", S, 72.0, 0.8)
    rpi = de("delay_prio1_p90_h", S, math.inf, 0.8)
    assert abs(rp["diff"] - rpi["diff"]) < 1e-9, "72 h and no limit now differ at relay 0.8; reword Section 5.7"
    V["R1-DEFER-REL-P90"] = f"{h_(-rp['diff'], 1)} [{num(-rp['ci_hi'], 1)}, {num(-rp['ci_lo'], 1)}]"
    V["R1-DEFER-REL-COMP"] = pts_abs(de("prio1_completion_share", S, 72.0, 0.8))

    # ---- 5.8 Stage D and E -------------------------------------------------------------------------------------------
    sun = r.sun
    V["R1-SUN-BASE"], V["R1-SUN-ISRU"] = sh(sun["BASE"]), sh(sun["ISRU"])
    V["R1-SUN-MID"] = rng_txt([sun[k] for k in ("DEPOT", "CONSTR", "PAD_A@1", "PAD_B@1")], lambda x: f"{100 * x:.0f}", PCT)
    assert sun["PSR"] == 0.0
    sd_ = stage_d(r)
    x = sd_[("dte", S)]
    V["R1-D-DTE-T"] = dci(x["delivered_t_in_year"], 1)
    V["R1-D-DTE-CP90-GM"] = ratio(x["delay_prio1_p90_censored_h"])
    V["R1-D-DTE-P90-GM"] = ratio(x["delay_prio1_p90_h"])
    x = sd_[("dte+relay", S)]
    V["R1-D-REL-P90-FIXED"], V["R1-D-REL-P90-REAL"] = h_(x["delay_prio1_p90_h"]["ref_mean"]), h_(x["delay_prio1_p90_h"]["cell_mean"])
    V["R1-D-REL-P90-GM"] = ratio(x["delay_prio1_p90_h"])
    V["R1-D-REL-P90-GM-YEARS"] = rng_txt([v["gm_ratio"] for v in x["years_p90"].values()], rnd)
    V["R1-D-REL-CP90-GM"], V["R1-D-REL-CP90-W"] = ratio(x["delay_prio1_p90_censored_h"]), wil(x["delay_prio1_p90_censored_h"]["wilcoxon_p"])
    V["R1-D-REL-T"] = dci(x["delivered_t_in_year"], 1)
    V["R1-D-REL-CP90-GM-DEF"] = ratio(sd_[("dte+relay", "default")]["delay_prio1_p90_censored_h"])
    se = lambda sens, mix, p, metric="delay_prio1_p90_h": r.eff("sensitivity_vs_stage_a", metric, sensitivity=sens, mix=mix, p=p)
    for key, sens in (("GAP2", "relay_gap_2h"), ("GAP24", "relay_gap_24h"), ("DRM0", "relay_periodic_drm0"),
                      ("RC31", "relay_periodic_rc31")):
        for p, tag in ((0.1, "01"), (0.5, "05")):
            V[f"R1-E-{key}-STRICT-{tag}"] = ratio(se(sens, S, p))
    V["R1-E-GAP24-TELEOP-01"] = ratio(se("relay_gap_24h", "teleop_4s", 0.1))
    V["R1-E-RC31-STRICT-COMP-05"] = pts(se("relay_periodic_rc31", S, 0.5, "prio1_completion_share"))
    V["R1-E-RC31-STRICT-CP90-05"] = "ratio " + ratio(se("relay_periodic_rc31", S, 0.5, "delay_prio1_p90_censored_h"))
    rel = r.e[(r.e["family"] == "sensitivity_vs_stage_a") & (r.e["metric"] == "delivered_t_in_year") &
              r.e["sensitivity"].str.startswith("relay_")]
    rel = rel[~((rel["sensitivity"] == "relay_periodic_rc31") & (rel["mix"] == "teleop_4s") & np.isclose(rel["p"], 0.1))]
    V["R1-E-RELAY-T-OTHER-MAX"] = t_(rel["diff"].abs().max(), 1)
    V["R1-E-INTX05-STRAT-T"] = dci(se("interventions_x0.5", ST, 0.0, "delivered_t_in_year"), 1)
    V["R1-E-INTX2-STRAT-T"] = dci(se("interventions_x2", ST, 0.0, "delivered_t_in_year"), 1)
    V["R1-E-INTX05-STRAT-CP90-05"] = ratio(se("interventions_x0.5", ST, 0.5, "delay_prio1_p90_censored_h"))
    V["R1-E-INTX2-STRAT-CP90-05"] = ratio(se("interventions_x2", ST, 0.5, "delay_prio1_p90_censored_h"))
    V["R1-E-PLUME-DTE-CP90"] = ratio(se("plume_1km_0.5h", D, 0.0, "delay_prio1_p90_censored_h"))
    V["R1-E-PLUME-05-P90"] = dci(se("plume_1km_0.5h", S, 0.5), 1, "h")
    pw = se("plume_1km_0.5h", D, 0.0, "blackout_wait_vehicle_h")
    V["R1-E-PLUME-DTE-WAIT"] = f"from {num(pw['ref_mean'])} to {num(pw['cell_mean'])} rover-hours a year (ratio {ratio(pw)})"
    lc = se("isru_local_feedstock", S, 0.0, "prio1_completion_share")
    V["R1-E-LOCAL-COMP-DTE"], V["R1-E-LOCAL-COMP-DIFF"] = sh(lc["cell_mean"]), pts(lc)

    # ---- Discussion ----------------------------------------------------------------------------------------------
    full = L[S]["delay_prio1_p90_h"]
    fl = full["cell_mean"][full["p"].index(1.0)]
    V["R1-LCRNS-RATIO"] = rng_txt([full["cell_mean"][full["p"].index(x)] / fl for x in (0.6, 0.7)], lambda v: f"{v:.1f}")
    # ---- Limitations: equal-cost routes (results/E21_route_ties.json, tools/comms/earth_link.py ties) ----------
    rt = json.load(open(os.path.join(RES, "E21_route_ties.json"), encoding="utf-8"))
    assert rt["length"]["max_abs_diff_m"] < 0.1, "the route-ties wording assumes equally long routes"
    V["R1-TIES-LEGS"] = f"{rt['geometry']['legs_differing_gt_20m']} of the {rt['legs_compared']}"
    V["R1-TIES-MAX-M"] = f"{num(rt['geometry']['max_m'])}{NB}m"
    V["R1-TIES-SHARE-MAX"] = f"{num(rt['linked_share']['max_abs_diff_pp'], 1)} percentage points"
    V["R1-TIES-SHARE-GT5"] = num(rt["linked_share"]["legs_gt_5pp"])
    return V, {"be5": be5, "be2": be2, "be8": be8}


# ---------------------------------------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------------------------------------
NW = " style='white-space:nowrap'"
TAB_LABEL = {"teleop_4s": "Teleoperated", "default": "Reference mix", "supervised_strict": "Strict",
             "supervised_strategic": "Strategic", "supervised_strategic+avoid": "Look-ahead", "autonomous": "Autonomous"}
TAB_FLEETS = ("Fleets: teleoperated (4&nbsp;s round trip); the reference mix; all supervised under the strict, strategic or "
              "look-ahead policy; autonomous.")


def table_dte(r: R):
    rows = ['<p class="tabcap" id="r1-tab-dte"><b>Table 6.</b> DTE only against Earth always in view, by fleet (Stage A; '
            'primary comparisons 1 and 2). ' + TAB_FLEETS + ' Delivered: cell means over 20 seeds. Change: paired '
            'difference, in tonnes and percent, with its Student-<i>t</i> 95&#8239;% interval. Bulk is regolith, of which '
            '200&nbsp;t a year is assumed hauled to the oxygen plant, which never sees Earth; lander cargo excludes '
            'returns. Completion: mean share of the urgent items ready in the year that are delivered in it. Censored '
            '90th percentile: urgent delay with undelivered items counted to the end of the year, median over seeds '
            '(&ge;: a lower bound in at least half of the seeds). Ratio: geometric-mean ratio of the censored 90th '
            'percentile, DTE only over always linked, with its <i>t</i> interval on the log scale.</p>',
            '<table class="small wide"><tr><th>Fleet</th><th class="num">Delivered (t), always / DTE</th>'
            '<th class="num">Change (t)</th><th class="num">Bulk change (t)</th>'
            '<th class="num">Lander cargo (t), always / DTE</th><th class="num">Urgent completion, always / DTE</th>'
            '<th class="num">Censored 90th pct. (h), always / DTE</th><th class="num">Ratio</th></tr>']
    for mix in MIX_ORDER:
        al, dt = r.acell(mix, None), r.acell(mix, 0)
        d = r.eff("dte_vs_always", "delivered_t_in_year", mix=mix)
        b = r.eff("dte_vs_always", "delivered_bulk_t", mix=mix)
        g = r.eff("dte_vs_always", "delay_prio1_p90_censored_h", mix=mix)
        rows.append(
            f"<tr><td>{TAB_LABEL[mix]}</td>"
            f"<td class='num'{NW}>{num(al['delivered_t_in_year'])} / {num(dt['delivered_t_in_year'])}</td>"
            f"<td class='num'{NW}>{num(d['diff'])} ({pc(d['rel_pct'])})<br>{ci(d['ci_lo'], d['ci_hi'])}</td>"
            f"<td class='num'{NW}>{num(b['diff'])}</td>"
            f"<td class='num'{NW}>{num(al['delivered_landed_t'], 1)} / {num(dt['delivered_landed_t'], 1)}</td>"
            f"<td class='num'{NW}>{sh(al['prio1_completion_share'])} / {sh(dt['prio1_completion_share'])}</td>"
            f"<td class='num'{NW}>{cens(al)} / {cens(dt)}</td>"
            f"<td class='num'{NW}>{ratio(g).replace(' [', '<br>[')}</td></tr>")
    return "\n".join(rows + ["</table>"])


def table_coverage(r: R, V):
    L = r.f["laws"]
    low = r.relay_levels[0]
    boot = V["R1-LAW-BOOT"]
    rows = [f'<p class="tabcap" id="r1-tab-coverage"><b>Table 7.</b> Relay coverage at which urgent delay falls to twice '
            f'and to 1.5 times its full-coverage value (Stage A; primary comparison 3 for the strict fleet). {TAB_FLEETS} '
            f'Urgent delay here is the 90th percentile of delivered priority-1 items, cell means; the coverage is read '
            f'model-free (non-increasing envelope, log-linear between levels) with bootstrap 95&#8239;% intervals over '
            f'seeds ({boot} draws). &ldquo;&le;&nbsp;{pfmt(low)}&rdquo;: below the lowest relay level tested. Full '
            f'coverage: cell mean with its Student-<i>t</i> interval, and the completion share. Lowest completion: the '
            f'lowest mean completion share at any relay level. The teleoperated fleet uses the soft operator pool '
            f'(Section 5.6).</p>',
            '<table class="small"><tr><th>Fleet</th><th class="num">Full coverage: urgent 90th pct. (h)</th>'
            '<th class="num">Full coverage: completion</th><th class="num">Coverage for 2&times;</th>'
            '<th class="num">Coverage for 1.5&times;</th><th class="num">Lowest completion with a relay</th></tr>']
    g = lambda v: (f"&le;&nbsp;{pfmt(low)}" if v < low - 1e-9 else
                   ("beyond full coverage" if not math.isfinite(v) else f"{v:.2f}"))
    for mix in MIX_ORDER:
        full = r.acell(mix, 1.0)
        lowest = min(r.acell(mix, p)["prio1_completion_share"] for p in r.relay_levels)
        m, h = full["delay_prio1_p90_h"], full["delay_prio1_p90_h_ci95_t"]
        fc = f"{num(m, 1)} {ci(m - h, m + h, 1)}"
        if mix == "autonomous":
            t2 = t15 = "not affected"
        else:
            pt, cc = L[mix]["delay_prio1_p90_h"]["point"], L[mix]["delay_prio1_p90_h"]["ci95"]
            t2 = f"{g(pt['p_2x_cells'])} [{g(cc['p_2x_cells'][0])}, {g(cc['p_2x_cells'][1])}]"
            t15 = f"{g(pt['p_1.5x_cells'])} [{g(cc['p_1.5x_cells'][0])}, {g(cc['p_1.5x_cells'][1])}]"
        rows.append(f"<tr><td>{TAB_LABEL[mix]}</td><td class='num'>{fc}</td>"
                    f"<td class='num'>{sh(full['prio1_completion_share'])}</td><td class='num'>{t2}</td>"
                    f"<td class='num'>{t15}</td><td class='num'>{sh(lowest)}</td></tr>")
    return "\n".join(rows + ["</table>"])


def table_breakeven(r: R, V, B):
    be5, be2, be8 = B["be5"], B["be2"], B["be8"]
    rows = [f'<p class="tabcap" id="r1-tab-breakeven"><b>Table 8.</b> Options on the all-supervised fleet and the relay '
            f'coverage each is worth in urgent delay (Stage B; primary comparison 5). Urgent 90th pct.: delivered '
            f'priority-1 items, cell mean with its Student-<i>t</i> interval; completion: mean share of urgent items '
            f'delivered. Change: paired difference against the strict fleet with no extra rover and no mast at the same '
            f'coverage, with its <i>t</i> interval; ratio: geometric-mean ratio with its interval, and the Wilcoxon '
            f'<i>p</i>. Equivalent coverage: the point on the strict fleet\'s Stage A curve (model-free) with the same '
            f'delay; &Delta;<i>p</i> is that coverage minus the row\'s coverage. Both carry bootstrap 95&#8239;% '
            f'intervals ({V["R1-BOOT-DRAWS"]} draws, every draw kept; &ldquo;beyond 1&rdquo;: better than full '
            f'coverage). Last column: share of draws in which the option buys nothing (&Delta;<i>p</i>&nbsp;&le;&nbsp;0) '
            f'and in which it beats full coverage. The rows at 0.2 and 0.8 test the choice of 0.5; at 0.8 the strict '
            f'cell lies above its 0.7 neighbour, so &Delta;<i>p</i> there is not informative.</p>',
            '<table class="small wide"><tr><th>Coverage, option</th><th class="num">Urgent 90th pct. (h)</th>'
            '<th class="num">Completion</th><th class="num">Change (h)</th><th class="num">Ratio; Wilcoxon</th>'
            '<th class="num">Equivalent coverage</th><th class="num">&Delta;<i>p</i></th>'
            '<th class="num">Draws: nothing / beyond 1</th></tr>']
    b = r.raw["B"]
    sel = lambda p, pol, n, mast: AN.select(b, p=p, policy=pol, extra_rovers=n, mast=mast)
    bc = lambda p, pol, n, mast="none": _match(r.c[r.c["stage"] == "B"], p=p, policy=pol, extra_rovers=n, mast=mast).iloc[0]
    f2 = lambda v: "beyond 1" if math.isinf(v) else num(v, 2)

    def row(p, label, pol, n, mast, o):
        cell = bc(p, pol, n, mast)
        m, h = cell["delay_prio1_p90_h"], cell["delay_prio1_p90_h_ci95_t"]
        v = f"{num(m, 1)}<br>{ci(m - h, m + h, 1)}"
        if o is None:
            return (f"<tr><td>{pfmt(p)}, strict fleet as it is</td><td class='num'{NW}>{v}</td>"
                    f"<td class='num'{NW}>{sh(cell['prio1_completion_share'])}</td>"
                    f"<td class='num'{NW}>&ndash;</td><td class='num'{NW}>&ndash;</td><td class='num'{NW}>{pfmt(p)}</td>"
                    f"<td class='num'{NW}>&ndash;</td><td class='num'{NW}>&ndash;</td></tr>")
        e = AN.paired(sel(p, "strict", 0, "none"), sel(p, pol, n, mast), "delay_prio1_p90_h")
        return (f"<tr><td>{pfmt(p)}, {label}</td><td class='num'{NW}>{v}</td>"
                f"<td class='num'{NW}>{sh(cell['prio1_completion_share'])}</td>"
                f"<td class='num'{NW}>{num(e['diff'], 1, True)}<br>{ci(e['ci_lo'], e['ci_hi'], 1)}</td>"
                f"<td class='num'{NW}>{ratio(e)}<br>{wil(e['wilcoxon_p'])}</td>"
                f"<td class='num'{NW}>{f2(o['p_equiv'])}<br>[{f2(o['pe_lo'])}, {f2(o['pe_hi'])}]</td>"
                f"<td class='num'{NW}>{f2(o['dp'])}<br>[{f2(o['lo'])}, {f2(o['hi'])}]</td>"
                f"<td class='num'{NW}>{pc(100 * o['nonpos'], 2)} / {pc(100 * o['beyond'], 2)}</td></tr>")

    rows.append(row(0.5, "", "strict", 0, "none", None))
    for lab, pol, n, mast, key in (("+1 rover", "strict", 1, "none", "+1 rover"),
                                   ("+2 rovers", "strict", 2, "none", "+2 rovers"),
                                   ("+3 rovers", "strict", 3, "none", "+3 rovers"),
                                   ("10 m mast at the base", "strict", 0, "BASE 10 m", "mast"),
                                   ("strategic step", "strategic", 0, "none", "strategic step"),
                                   ("look-ahead step", "strategic+avoid", 0, "none", "look-ahead step"),
                                   ("strategic step + 1 rover", "strategic", 1, "none", "strategic step + 1 rover")):
        rows.append(row(0.5, lab, pol, n, mast, be5[key]))
    for p, bx in ((0.2, be2), (0.8, be8)):
        rows.append(row(p, "", "strict", 0, "none", None))
        rows.append(row(p, "+1 rover", "strict", 1, "none", bx["+1 rover"]))
        rows.append(row(p, "strategic step", "strategic", 0, "none", bx["strategic step"]))
    return "\n".join(rows + ["</table>"])


def table_stagec(r: R):
    c = r.c[r.c["stage"] == "C"].copy()
    rows = ['<p class="tabcap" id="r1-tab-stagec"><b>Table 9.</b> Stage C: pad standoff and link criterion (deferral '
            '24&nbsp;h), and the deferral limit (pads 1&nbsp;km, any part of the disc). Delivered and lander cargo: cell '
            'means over 20 seeds, t a year. Completion: mean share of urgent items delivered. Censored 90th pct.: '
            'median over seeds (&ge;: a lower bound in at least half of the seeds). Delivered-item 90th pct.: cell mean '
            'over the seeds with a delivered urgent item; &ldquo;none delivered&rdquo; where no seed delivered one.</p>',
            '<table class="small wide"><tr><th>Cell</th><th class="num">Pads (km)</th><th>Criterion</th>'
            '<th class="num">Deferral (h)</th><th class="num">Delivered (t)</th><th class="num">Lander cargo (t)</th>'
            '<th class="num">Urgent completion</th><th class="num">Censored 90th pct. (h)</th>'
            '<th class="num">Delivered-item 90th pct. (h)</th></tr>']
    lab = {("dte", "default"): "DTE only, reference mix", ("dte", "teleop_4s"): "DTE only, teleoperated",
           ("dte+relay", "supervised_strict"): "Relay 0.8, strict"}
    c["defer"] = c["defer_wait_h"].fillna(np.inf)
    c["co"] = c["comms"].map({"dte": 0, "dte+relay": 1})
    c["mo"] = c["mix"].map({"default": 0, "teleop_4s": 1, "supervised_strict": 2})
    c["cr"] = c["criterion"].map({"any_part": 0, "centre+0.5deg": 1, "centre+2deg": 2})
    c["df"] = c["defer"].map(lambda v: 0 if v == 24 else (1 if v == 12 else (2 if v == 72 else 3)))
    c = c.sort_values(["co", "mo", "df", "pad_standoff_km", "cr"])
    last = None
    for _, x in c.iterrows():
        key = (x["comms"], x["mix"])
        name = lab[key] if key != last else ""
        last = key
        dfr = "none" if not np.isfinite(x["defer"]) else f"{x['defer']:g}"
        n = int(x["delay_prio1_p90_h_n"])
        if n == 0:
            p90 = "none delivered"
        else:
            p90 = num(x["delay_prio1_p90_h"]) + ("" if n == int(x["n_seeds"]) else f" ({n} seeds)")
        rows.append(f"<tr><td>{name}</td><td class='num'{NW}>{x['pad_standoff_km']:g}</td>"
                    f"<td{NW}>{CRIT_LABEL[x['criterion']]}</td><td class='num'{NW}>{dfr}</td>"
                    f"<td class='num'{NW}>{num(x['delivered_t_in_year'], 1)}</td>"
                    f"<td class='num'{NW}>{num(x['delivered_landed_t'], 1)}</td>"
                    f"<td class='num'{NW}>{sh(x['prio1_completion_share'])}</td>"
                    f"<td class='num'{NW}>{cens(x)}</td><td class='num'{NW}>{p90}</td></tr>")
    return "\n".join(rows + ["</table>"])


def references():
    notes = open(os.path.join(HERE, "NOTES.md"), encoding="utf-8").read()
    sec = notes.split("## References", 1)[1].split("\n## ", 1)[0]
    out = ['<ol class="refs">']
    for m in re.finditer(r"^\[(\d+)\]\s+(.+?)(?=\n\n|\n\[\d+\]|\Z)", sec, re.S | re.M):
        txt = html.escape(" ".join(m.group(2).split()))
        txt = re.sub(r"\*(.+?)\*", r"<i>\1</i>", txt)
        txt = re.sub(r"(https?://[^\s<]+)", lambda u: f'<a href="{u.group(1)}">{u.group(1)}</a>', txt)
        out.append(f'<li value="{m.group(1)}">{txt}</li>')
    return "\n".join(out + ["</ol>"])


def build():
    r = R()
    V, B = values(r)
    bad = {k: v for k, v in V.items() if re.search(r"\b(nan|inf|NaN|None)\b", v)}
    if bad:
        raise SystemExit(f"non-finite values: {bad}")
    V.update({"R1-TABLE-DTE": table_dte(r), "R1-TABLE-COVERAGE": table_coverage(r, V),
              "R1-TABLE-BREAKEVEN": table_breakeven(r, V, B), "R1-TABLE-STAGEC": table_stagec(r),
              "R1-REFERENCES": references()})
    doc = "\n".join(open(os.path.join(HERE, p), encoding="utf-8").read() for p in PARTS)
    # the appendices sit at the end of part 3; move them after the references (NOTES.md, "Numbering")
    m = re.search(r"<!-- APPENDICES START.*?-->(.*?)<!-- APPENDICES END -->", doc, re.S)
    if m:
        doc = doc[:m.start()] + doc[m.end():]
        doc = doc.replace("{{R1-REFERENCES}}", "{{R1-REFERENCES}}\n" + m.group(1).strip(), 1)
    used = set(re.findall(r"\{\{(R1-[A-Z0-9.-]+)\}\}", doc))
    doc = re.sub(r"\{\{(R1-[A-Z0-9.-]+)\}\}", lambda x: V[x.group(1)] if x.group(1) in V else x.group(0), doc)
    left = sorted(set(re.findall(r"\{\{R1-[^}]*\}\}", re.sub(r"<!--.*?-->", "", doc, flags=re.S))))
    if left:
        raise SystemExit(f"unfilled placeholders: {left}")
    body = re.sub(r"<[^>]+>", " ", re.sub(r"<!--.*?-->", "", doc, flags=re.S))
    if re.search(r"\b(nan|NaN|inf)\b", body):
        raise SystemExit("nan/inf in the assembled text: " + re.search(r".{40}\b(nan|NaN|inf)\b.{40}", body).group(0))
    unused = sorted(k for k in V if k not in used and not k.startswith("R1-TABLE") and k != "R1-REFERENCES")
    if unused:
        print("note: values not used in the text:", ", ".join(unused))
    out = os.path.join(HERE, "paper.html")
    open(out, "w", encoding="utf-8", newline="\n").write(doc)
    json.dump({k: v for k, v in V.items() if not k.startswith("R1-TABLE") and k != "R1-REFERENCES"},
              open(os.path.join(HERE, "values.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("wrote", out, f"({len(V)} values, {len(used)} placeholders used)")
    if os.path.exists(CHROME) and "--no-pdf" not in sys.argv:
        cmd = [CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--allow-file-access-from-files",
               f"--print-to-pdf={PDF}", "file:///" + out.replace("\\", "/")]
        rc = subprocess.run(cmd, capture_output=True, timeout=180).returncode
        print("chrome exit", rc, "pdf", os.path.exists(PDF), os.path.getsize(PDF) if os.path.exists(PDF) else 0)


if __name__ == "__main__":
    build()
