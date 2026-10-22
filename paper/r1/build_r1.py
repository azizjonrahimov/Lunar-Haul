"""Assemble the R-1 paper: fill every {{R1-...}} placeholder from the E21 results, insert the result tables and the
reference list, write paper/r1/paper.html and render the PDF with headless Chrome.

    python paper/r1/build_r1.py            (run paper/r1/make_figures_r1.py first)

Sources: results/table_E21.csv, table_E21_effects.csv, table_E21_breakeven.csv, table_E21_breakeven_delay.csv,
E21_fit.json, fig_E21_operator_demand.csv, the raw E21a/b/c CSVs (run times), paper/r1/NOTES.md (references).
The build fails if any placeholder is left unfilled.
"""
import html
import json
import os
import re
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RES = os.path.join(ROOT, "results")
PARTS = ["part1_front.html", "part2_related.html", "part3_methods.html", "part4_results.html", "part5_back.html"]
PDF = os.path.join(HERE, "what_earths_horizon_costs_r1.pdf")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
MINUS = "&minus;"
MIX_LABEL = {"teleop_4s": "Teleoperated, 4 s round trip", "default": "Phase-2 mix (reference)",
             "supervised_strict": "Supervised, strict", "supervised_strategic": "Supervised, strategic",
             "supervised_strategic+avoid": "Supervised, strategic with look-ahead", "autonomous": "Autonomous"}
MIX_ORDER = list(MIX_LABEL)


def num(x, nd=0):
    s = f"{abs(x):,.{nd}f}"
    return (MINUS if x < 0 and float(s.replace(',', '')) != 0 else "") + s


def pm(m, c, nd=0, unit=""):
    return f"{num(m, nd)} &plusmn; {num(c, nd)}{unit}"


def ci(lo, hi, nd=0):
    return f"[{num(lo, nd)}, {num(hi, nd)}]"


class R:
    def __init__(self):
        self.t = pd.read_csv(os.path.join(RES, "table_E21.csv"))
        self.e = pd.read_csv(os.path.join(RES, "table_E21_effects.csv"))
        self.b = pd.read_csv(os.path.join(RES, "table_E21_breakeven.csv"))
        self.bd = pd.read_csv(os.path.join(RES, "table_E21_breakeven_delay.csv"))
        self.f = json.load(open(os.path.join(RES, "E21_fit.json"), encoding="utf-8"))
        self.ops = pd.read_csv(os.path.join(RES, "fig_E21_operator_demand.csv"))

    def cell(self, stage="A", comms="dte", mix="default", coverage=None, **kw):
        t = self.t[(self.t["stage"] == stage) & (self.t["comms"] == comms) & (self.t["mix"] == mix)]
        if coverage is not None:
            t = t[np.isclose(t["coverage"], coverage)]
        for k, v in kw.items():
            t = t[(t[k] == v) | (t[k].isna() & (v is None))] if v is None else t[t[k] == v]
        if len(t) != 1:
            raise ValueError(f"cell {stage} {comms} {mix} {coverage} {kw}: {len(t)} rows")
        return t.iloc[0]

    def eff(self, family, metric, **kw):
        e = self.e[(self.e["family"] == family) & (self.e["metric"] == metric)]
        for k, v in kw.items():
            e = e[np.isclose(e[k], v)] if isinstance(v, float) else e[e[k] == v]
        if len(e) != 1:
            raise ValueError(f"effect {family} {metric} {kw}: {len(e)} rows")
        return e.iloc[0]


def values(r: R):
    V = {}
    al, dt = r.cell(comms="always"), r.cell(comms="dte")
    V["R1-T-ALWAYS"] = pm(al["delivered_t_in_year"], al["delivered_t_in_year_ci95"])
    V["R1-T-DTE"] = pm(dt["delivered_t_in_year"], dt["delivered_t_in_year_ci95"])
    d = r.eff("dte_vs_always", "delivered_t_in_year", mix="default")
    V["R1-T-LOSS-PCT"] = f"{num(d['rel_pct'], 0)}&nbsp;% {ci(100 * d['ci_lo'] / d['ref_mean'], 100 * d['ci_hi'] / d['ref_mean'], 0)}"
    V["R1-T-LOSS-PCT-PLAIN"] = f"{abs(d['rel_pct']):.0f}&nbsp;%"
    V["R1-P90-ALWAYS"] = f"{al['delay_prio1_p90_h']:.0f}&nbsp;h"
    V["R1-P90-DTE"] = pm(dt["delay_prio1_p90_h"], dt["delay_prio1_p90_h_ci95"], 0, "&nbsp;h")
    th = r.f["throughput"]
    V["R1-ISRU-BOUND-T"] = pm(th["bound_ready_t"]["mean"], th["bound_ready_t"]["ci95"], 1, "&nbsp;t")
    V["R1-LOST-ISRU-T"] = pm(th["lost_at_never_linked_t"]["mean"], th["lost_at_never_linked_t"]["ci95"], 1, "&nbsp;t")
    V["R1-GAP-T"] = pm(th["gap_t"]["mean"], th["gap_t"]["ci95"], 1, "&nbsp;t")
    V["R1-GAP-ELSE-T"] = pm(th["gap_elsewhere_t"]["mean"], th["gap_elsewhere_t"]["ci95"], 1, "&nbsp;t")
    V["R1-LOSS-SHARE-ISRU"] = f"{100 * th['lost_at_never_linked_t']['mean'] / th['gap_t']['mean']:.0f}&nbsp;%"
    rv = r.eff("rovers_vs_0", "delivered_t_in_year", p=0.0, policy="strict", extra_rovers=1.0)
    V["R1-ROVER-GAIN-T"] = f"{num(rv['diff'], 1)}&nbsp;t {ci(rv['ci_lo'], rv['ci_hi'], 1)}"
    ms = r.eff("mast_vs_none", "delivered_t_in_year", p=0.0, policy="strict")
    V["R1-MAST-GAIN-T"] = f"{num(ms['diff'], 1)}&nbsp;t {ci(ms['ci_lo'], ms['ci_hi'], 1)}"
    r01 = r.cell(comms="dte+relay", coverage=0.1)
    V["R1-RELAY01-RESTORE-PCT"] = f"{100 * (r01['delivered_t_in_year'] - dt['delivered_t_in_year']) / (al['delivered_t_in_year'] - dt['delivered_t_in_year']):.0f}&nbsp;%"
    sys.path.insert(0, ROOT)
    from experiments.phase4.run_phase4 import knee_coverage   # noqa: E402
    V["R1-A-KNEE-P"] = f"p&nbsp;=&nbsp;{knee_coverage(r.t):g}"
    L = r.f["laws"]
    for key, mix in (("STRICT", "supervised_strict"), ("STRATEGIC", "supervised_strategic")):
        pt, cc = L[mix]["delay_prio1_p90_h"]["point"], L[mix]["delay_prio1_p90_h"]["ci95"]
        V[f"R1-P-2X-{key}"] = f"{pt['p_2x_cells']:.2f} {ci(cc['p_2x_cells'][0], cc['p_2x_cells'][1], 2)}"
    bd = r.f["breakeven_delay"]
    V["R1-DP-ONE-LTV"] = f"{bd['delta_p_one_ltv']:.2f} {ci(*bd['delta_p_one_ltv_ci95'], 2)}"
    V["R1-MUSD-PER-01"] = f"{bd['musd_per_year_per_0.1_coverage']:.0f}&nbsp;M$ {ci(*bd['musd_per_year_per_0.1_coverage_ci95'], 0)}"
    V["R1-SHARE-NONPOS"] = f"{100 * bd['share_draws_one_ltv_not_positive']:.1f}&nbsp;%"
    st, sa, ss = r.cell(mix="supervised_strategic"), r.cell(mix="supervised_strategic+avoid"), r.cell(mix="supervised_strict")
    V["R1-T-STRATEGIC-DTE"] = pm(st["delivered_t_in_year"], st["delivered_t_in_year_ci95"], 0, "&nbsp;t")
    V["R1-WAIT-STRATEGIC-DTE"] = pm(st["blackout_wait_vehicle_h"], st["blackout_wait_vehicle_h_ci95"], 0, " rover-hours")
    V["R1-WAIT-STRICT-DTE"] = pm(ss["blackout_wait_vehicle_h"], ss["blackout_wait_vehicle_h_ci95"], 0, "")
    V["R1-WAIT-AVOID-DTE"] = pm(sa["blackout_wait_vehicle_h"], sa["blackout_wait_vehicle_h_ci95"], 0, " rover-hours")
    c = r.t[r.t["stage"] == "C"]
    dd = c[(c["comms"] == "dte") & (c["mix"] == "default") & (c["pad_standoff_km"] == 1) & (c["criterion"] == "any_part")]
    d24, dinf = dd[dd["defer_wait_h"] == 24].iloc[0], dd[~np.isfinite(dd["defer_wait_h"].fillna(np.inf))].iloc[0]
    V["R1-DEFER24-P90"] = pm(d24["delay_prio1_p90_h"], d24["delay_prio1_p90_h_ci95"], 0, "&nbsp;h")
    V["R1-NODEFER-P90"] = pm(dinf["delay_prio1_p90_h"], dinf["delay_prio1_p90_h_ci95"], 0, "&nbsp;h")
    crit = r.e[(r.e["family"] == "criterion_vs_any_part") & (r.e["metric"] == "delivered_t_in_year")]
    V["R1-CRIT-RANGE"] = f"{crit['rel_pct'].abs().max():.1f}&nbsp;%"
    p05 = r.eff("pads_vs_1km", "delivered_t_in_year", mix="default", pad_standoff_km=0.5, criterion="any_part")
    p3 = r.eff("pads_vs_1km", "delivered_t_in_year", mix="default", pad_standoff_km=3.0, criterion="any_part")
    V["R1-PADS-05-GAIN"] = f"{p05['diff']:.0f}&nbsp;t {ci(p05['ci_lo'], p05['ci_hi'], 0)}"
    V["R1-PADS-3-LOSS"] = f"{abs(p3['diff']):.0f}&nbsp;t {ci(-p3['ci_hi'], -p3['ci_lo'], 0)}"
    op = r.ops[r.ops["mix"] == "teleop_4s"]
    full = op[(op["comms"] == "dte+relay") & np.isclose(op["p"].fillna(-1), 1.0)].iloc[0]
    dte = op[op["comms"] == "dte"].iloc[0]
    V["R1-PTM-FULL"] = pm(full["peak_to_mean"], full["peak_to_mean_ci95"], 0)
    V["R1-PTM-DTE"] = pm(dte["peak_to_mean"], dte["peak_to_mean_ci95"], 0)
    V["R1-OP-PEAK-TELEOP-DTE"] = V["R1-PTM-DTE"]
    run_s = {k: pd.read_csv(os.path.join(RES, f))["run_s"].sum() for k, f in
             (("A", "E21a_comms_autonomy.csv"), ("B", "E21b_breakeven.csv"), ("C", "E21c_pads_criterion.csv"))}
    V["R1-COMPUTE-H"] = f"{sum(run_s.values()) / 3600:.1f}"
    for k in "ABC":
        V[f"R1-COMPUTE-{k}-MIN"] = f"{run_s[k] / 60:.0f}"
    return V


def table_dte(r: R):
    rows = ['<p class="tabcap"><b>Table 7.</b> Direct-to-Earth links only against Earth always in view, by fleet '
            '(Stage A). Cargo delivered inside the year and urgent delay (90&nbsp;% of priority-1 items within), cell '
            'means &plusmn; 95&nbsp;% interval over 20 seeds; change = paired difference with its 95&nbsp;% interval.</p>',
            '<table class="small"><tr><th>Fleet</th><th class="num">Delivered, always (t)</th><th class="num">Delivered, '
            'DTE only (t)</th><th class="num">Change (t)</th><th class="num">Urgent 90&nbsp;%, always (h)</th>'
            '<th class="num">Urgent 90&nbsp;%, DTE only (h)</th></tr>']
    for mix in MIX_ORDER:
        al, dt = r.cell(comms="always", mix=mix), r.cell(comms="dte", mix=mix)
        d = r.eff("dte_vs_always", "delivered_t_in_year", mix=mix)
        rows.append(f"<tr><td>{MIX_LABEL[mix]}</td><td class='num'>{pm(al['delivered_t_in_year'], al['delivered_t_in_year_ci95'])}</td>"
                    f"<td class='num'>{pm(dt['delivered_t_in_year'], dt['delivered_t_in_year_ci95'])}</td>"
                    f"<td class='num'>{num(d['diff'], 0)} {ci(d['ci_lo'], d['ci_hi'], 0)}</td>"
                    f"<td class='num'>{pm(al['delay_prio1_p90_h'], al['delay_prio1_p90_h_ci95'])}</td>"
                    f"<td class='num'>{pm(dt['delay_prio1_p90_h'], dt['delay_prio1_p90_h_ci95'])}</td></tr>")
    return "\n".join(rows + ["</table>"])


def table_coverage(r: R):
    rows = ['<p class="tabcap"><b>Table 8.</b> Relay coverage needed for the urgent delay (90&nbsp;% within) to reach '
            'twice and one and a half times its full-coverage value, read from the Stage A cells (non-increasing '
            'envelope, log-linear between grid points), with bootstrap 95&nbsp;% intervals over seeds. Law: the form '
            'chosen by five-fold cross-validation over seeds.</p>',
            '<table class="small"><tr><th>Fleet</th><th class="num">Full coverage (h)</th><th class="num">Coverage for 2&times;</th>'
            '<th class="num">Coverage for 1.5&times;</th><th>Law</th></tr>']
    for mix in MIX_ORDER:
        if mix not in r.f["laws"]:
            continue
        L = r.f["laws"][mix]["delay_prio1_p90_h"]; pt, cc = L["point"], L["ci95"]
        def cell(k):
            v = pt.get(k)
            if v is None or not np.isfinite(v):
                return "&ndash;"
            lo, hi = cc.get(k, [np.nan, np.nan])
            return f"{v:.2f} {ci(lo, hi, 2)}" if np.isfinite(lo) else f"{v:.2f}"
        full = f"{pt['cell_full']:.1f}" if pt.get("cell_full") is not None else "&ndash;"
        rows.append(f"<tr><td>{MIX_LABEL[mix]}</td><td class='num'>{full}</td><td class='num'>{cell('p_2x_cells')}</td>"
                    f"<td class='num'>{cell('p_1.5x_cells')}</td><td>{L['form']}</td></tr>")
    return "\n".join(rows + ["</table>"])


def table_breakeven(r: R):
    rows = ['<p class="tabcap"><b>Table 9.</b> Options at relay coverage 0.5 (Stage B) and the relay coverage that gives '
            'the same urgent delay on the strict fleet\'s Stage A curve (model-free; law-based in brackets). Value: '
            'urgent delay, 90&nbsp;% within, mean with 95&nbsp;% interval over seeds. Strict fleet as it is: '
            f'{r.bd["base_value"].iloc[0]:.1f}&nbsp;h.</p>',
            '<table class="small"><tr><th>Option</th><th class="num">Urgent 90&nbsp;% (h)</th><th class="num">Equivalent coverage</th>'
            '<th class="num">Coverage gained</th><th class="num">Law-based</th></tr>']
    for _, b in r.bd.iterrows():
        law = f"{b['p_equiv_law']:.2f}" if np.isfinite(b["p_equiv_law"]) else "&gt; 1"      # beyond full coverage
        rows.append(f"<tr><td>{html.escape(b['option'])}</td><td class='num'>{b['value']:.1f} {ci(b['value_ci95_lo'], b['value_ci95_hi'], 1)}</td>"
                    f"<td class='num'>{b['p_equiv']:.2f} {ci(b['p_equiv_ci95_lo'], b['p_equiv_ci95_hi'], 2)}</td>"
                    f"<td class='num'>{b['delta_p']:+.2f}</td><td class='num'>{law}</td></tr>")
    return "\n".join(rows + ["</table>"])


def table_stagec(r: R):
    c = r.t[r.t["stage"] == "C"].copy()
    rows = ['<p class="tabcap"><b>Table 10.</b> Stage C: pad standoff and link criterion (deferral 24&nbsp;h), and the '
            'deferral limit (pads 1&nbsp;km, any part of the disc). Means &plusmn; 95&nbsp;% interval over 20 seeds.</p>',
            '<table class="small"><tr><th>Cell</th><th>Pads (km)</th><th>Criterion</th><th class="num">Deferral (h)</th>'
            '<th class="num">Delivered (t)</th><th class="num">Urgent 90&nbsp;% (h)</th></tr>']
    lab = {("dte", "default"): "DTE only, Phase-2 mix", ("dte", "teleop_4s"): "DTE only, teleoperated",
           ("dte+relay", "supervised_strict"): "relay 0.8, supervised strict"}
    c["defer"] = c["defer_wait_h"].fillna(np.inf)
    c = c.sort_values(["comms", "mix", "defer", "pad_standoff_km", "criterion"])
    for _, x in c.iterrows():
        dfr = "none" if not np.isfinite(x["defer"]) else f"{x['defer']:g}"
        p90 = pm(x["delay_prio1_p90_h"], x["delay_prio1_p90_h_ci95"]) if np.isfinite(x["delay_prio1_p90_h"]) else "&ndash;"
        rows.append(f"<tr><td>{lab.get((x['comms'], x['mix']), x['mix'])}</td><td>{x['pad_standoff_km']:g}</td><td>{x['criterion']}</td>"
                    f"<td class='num'>{dfr}</td><td class='num'>{pm(x['delivered_t_in_year'], x['delivered_t_in_year_ci95'])}</td>"
                    f"<td class='num'>{p90}</td></tr>")
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
    r = R(); V = values(r)
    V.update({"R1-TABLE-DTE": table_dte(r), "R1-TABLE-COVERAGE": table_coverage(r), "R1-TABLE-BREAKEVEN": table_breakeven(r),
              "R1-TABLE-STAGEC": table_stagec(r), "R1-REFERENCES": references()})
    doc = "\n".join(open(os.path.join(HERE, p), encoding="utf-8").read() for p in PARTS)
    doc = re.sub(r"\{\{(R1-[A-Z0-9-]+)\}\}", lambda m: V[m.group(1)] if m.group(1) in V else m.group(0), doc)
    left = sorted(set(re.findall(r"\{\{R1-[A-Z0-9-]+\}\}", doc)))
    if left:
        raise SystemExit(f"unfilled placeholders: {left}")
    out = os.path.join(HERE, "paper.html")
    open(out, "w", encoding="utf-8", newline="\n").write(doc)
    json.dump({k: v for k, v in V.items() if not k.startswith("R1-TABLE") and k != "R1-REFERENCES"},
              open(os.path.join(HERE, "values.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("wrote", out, f"({len(V)} values)")
    if os.path.exists(CHROME) and "--no-pdf" not in sys.argv:
        cmd = [CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--allow-file-access-from-files",
               f"--print-to-pdf={PDF}", "file:///" + out.replace("\\", "/")]
        rc = subprocess.run(cmd, capture_output=True, timeout=180).returncode
        print("chrome exit", rc, "pdf", os.path.exists(PDF), os.path.getsize(PDF) if os.path.exists(PDF) else 0)


if __name__ == "__main__":
    build()
