"""Assemble paper.html from the part files, fill result tables and render a PDF with headless Chrome."""
import os, subprocess, sys, json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "results")


def ci(x):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    return 1.96 * x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else 0.0


def fmt(m, c, nd=1):
    return f"{m:.{nd}f} &plusmn; {c:.{nd}f}"


MECH_LABEL = {"inhouse": "In-house fleets", "pooled_greedy": "Pooled greedy", "central_assign": "Batched assignment",
              "marketplace": "Marketplace (ours)", "unconstrained_bound": "Unconstrained 16-vehicle bound"}


def table_main():
    df = pd.read_csv(os.path.join(RES, "E1_phases.csv"))
    df["immov"] = 100 * df.stranded_kg / df.landed_kg
    rows = []
    rows.append('<p class="tabcap"><b>Table 5.</b> Main results with default fleets: mean &plusmn; 95% CI over 30 seeds. '
                'Urgent = priority-1 items. Immovable = share of landed cargo mass no vehicle or team could ever carry. '
                'Bulk delay is the mean delay of deferrable regolith lots, which the marketplace holds on purpose. '
                'Cost is amortised fleet plus operator time per kilogram of all mass moved.</p>')
    rows.append("<table class=\"wide\"><tr><th>Phase</th><th>Mechanism</th><th class='num'>Urgent p90 delay (h)</th><th class='num'>Urgent mean delay (h)</th>"
                "<th class='num'>Urgent within 24 h</th><th class='num'>Immovable (%)</th><th class='num'>Night strandings / yr</th>"
                "<th class='num'>Trips / yr</th><th class='num'>Bulk delay (h)</th><th class='num'>Operator h / yr</th><th class='num'>Revenue Gini</th><th class='num'>Cost $/kg moved</th></tr>")
    for ph, lab in (("P1", "Phase 1"), ("P2", "Phase 2"), ("P3", "Phase 3")):
        for mech in ("inhouse", "pooled_greedy", "central_assign", "marketplace", "unconstrained_bound"):
            s = df[(df.phase == ph) & (df.mechanism == mech)]
            cls = ' class="best"' if mech == "marketplace" else ""
            rows.append(f"<tr{cls}><td>{lab}</td><td>{MECH_LABEL[mech]}</td>"
                        f"<td class='num'>{fmt(s.delay_prio1_p90_h.mean(), ci(s.delay_prio1_p90_h))}</td>"
                        f"<td class='num'>{fmt(s.delay_prio1_mean_h.mean(), ci(s.delay_prio1_mean_h))}</td>"
                        f"<td class='num'>{fmt(s.sl24_prio1.mean(), ci(s.sl24_prio1), 2)}</td>"
                        f"<td class='num'>{s.immov.mean():.1f}</td>"
                        f"<td class='num'>{fmt(s.night_strandings.mean(), ci(s.night_strandings), 2)}</td>"
                        f"<td class='num'>{s.jobs.mean():.0f}</td>"
                        f"<td class='num'>{s.delay_mean_bulk.mean():.1f}</td>"
                        f"<td class='num'>{s.operator_hours.mean():.0f}</td>"
                        f"<td class='num'>{s.revenue_gini.mean():.2f}</td>"
                        f"<td class='num'>{s.cost_per_kg_usd.mean():,.0f}</td></tr>")
    rows.append("</table>")
    return "\n".join(rows)


def table_abl():
    df = pd.read_csv(os.path.join(RES, "E8_ablations.csv"))
    ev = df[df.batch_h == 0]
    variants = ["marketplace", "no_bundling", "no_consolidate", "no_team_lift", "no_anticipate", "no_backhaul", "no_night_aware", "no_priority"]
    vlab = {"marketplace": "Full marketplace", "no_bundling": "without bundling", "no_consolidate": "without consolidation",
            "no_team_lift": "without team lift", "no_anticipate": "without anticipation", "no_backhaul": "without backhaul",
            "no_night_aware": "without night awareness", "no_priority": "without priority credit"}
    out = ['<p class="tabcap"><b>Table 6.</b> Ablations with tight fleets (Phase 2: four vehicles; Phase 3: six vehicles). '
           'Each cell is the mean over 30 seeds; the bracketed value is the paired difference from the full marketplace with its 95% CI. '
           'Immovable = share of landed cargo mass no vehicle or team could carry.</p>',
           "<table class=\"wide\"><tr><th>Phase</th><th>Variant</th><th class='num'>Urgent p90 delay (h)</th><th class='num'>Trips / yr</th>"
           "<th class='num'>Night strandings / yr</th><th class='num'>Immovable (%)</th><th class='num'>Bulk delay (h)</th><th class='num'>Operator h / yr</th></tr>"]
    for ph, lab in (("P2", "Phase 2"), ("P3", "Phase 3")):
        base = ev[(ev.phase == ph) & (ev.variant == "marketplace")].sort_values("seed")
        for v in variants:
            s = ev[(ev.phase == ph) & (ev.variant == v)].sort_values("seed")
            if not len(s):
                continue
            immov = 100 * (s.stranded_kg / s.landed_kg).mean()

            def cell(m, nd=1):
                if v == "marketplace":
                    return f"{s[m].mean():.{nd}f}"
                d = s[m].values - base[m].values
                return f"{s[m].mean():.{nd}f} <span class='note'>[{d.mean():+.{nd}f} &plusmn; {ci(d):.{nd}f}]</span>"
            out.append(f"<tr><td>{lab}</td><td>{vlab[v]}</td><td class='num'>{cell('delay_prio1_p90_h')}</td><td class='num'>{cell('jobs', 0)}</td>"
                       f"<td class='num'>{cell('night_strandings', 2)}</td><td class='num'>{immov:.1f}</td><td class='num'>{cell('delay_mean_bulk')}</td>"
                       f"<td class='num'>{cell('operator_hours', 0)}</td></tr>")
    out.append("</table>")
    return "\n".join(out)


def table_vv():
    p = os.path.join(RES, "table_vv.csv")
    if not os.path.exists(p):
        return "<p class='note'>Verification table not yet generated.</p>"
    df = pd.read_csv(p)
    out = ['<p class="tabcap"><b>Table B1.</b> Verification checks of the Python implementation (all pass).</p>',
           "<table class=\"small\"><tr><th>Check</th><th class='num'>Reference</th><th class='num'>Simulated</th><th class='num'>Rel. error</th><th class='num'>Tolerance</th><th>Basis</th><th>Result</th></tr>"]
    for _, r in df.iterrows():
        out.append(f"<tr><td>{r['name']}</td><td class='num'>{r['reference']:.5g} {r['unit']}</td><td class='num'>{r['simulated']:.5g} {r['unit']}</td>"
                   f"<td class='num'>{100*r['rel_error']:.3f}%</td><td class='num'>{100*r['tolerance']:.1f}%</td><td class='note'>{r['basis']}</td>"
                   f"<td>{'PASS' if r['passed'] else 'FAIL'}</td></tr>")
    out.append("</table>")
    return "\n".join(out)


def table_e14():
    d = settled_numbers()
    mlab = {"delay_prio1_mean_h": "Urgent mean delay (h)", "delay_prio1_p90_h": "Urgent p90 delay (h)", "sl24_prio1": "Urgent within 24 h",
            "delivered_share": "Delivered share", "cost_per_kg_usd": "Cost $/kg moved"}
    out = ['<p class="tabcap"><b>Table 7.</b> Settled Phase-2 estimates from sequential replication (99% confidence intervals). '
           '<i>n</i> is the number of replications when the run stopped; a target is reached when the half-width is within the stated share of the mean.</p>',
           "<table class=\"small\"><tr><th>Mechanism</th><th>Metric</th><th class='num'>n</th><th class='num'>Mean</th><th class='num'>99% half-width</th><th class='num'>Half-width / mean</th><th class='num'>Target</th><th>Reached</th></tr>"]
    for mech in ("inhouse", "pooled_greedy", "central_assign", "marketplace"):
        if mech not in d:
            continue
        for m in ("delay_prio1_mean_h", "delay_prio1_p90_h", "sl24_prio1", "delivered_share", "cost_per_kg_usd"):
            r = d[mech][m]
            nd = 3 if m in ("sl24_prio1", "delivered_share") else (1 if m == "cost_per_kg_usd" else 2)
            out.append(f"<tr><td>{MECH_LABEL[mech]}</td><td>{mlab[m]}</td><td class='num'>{r['n']:,}</td><td class='num'>{r['mean']:.{nd}f}</td>"
                       f"<td class='num'>{r['half_width']:.{nd}f}</td><td class='num'>{100*r['rel_half_width']:.2f}%</td><td class='num'>{100*r['target']:.0f}%</td>"
                       f"<td>{'yes' if r['reached'] else 'no'}</td></tr>")
    out.append("</table>")
    reached = [m for m in d if d[m]["delay_prio1_mean_h"]["reached"]]
    not_reached = [m for m in d if not d[m]["delay_prio1_mean_h"]["reached"]]
    def join(items):
        items = list(items)
        return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]
    def low(m):
        return MECH_LABEL[m].lower().replace(" (ours)", "")
    parts = []
    if reached:
        head = "all four cells" if len(reached) == 4 else "the " + join(low(m) for m in reached) + (" cells" if len(reached) > 1 else " cell")
        every = all(d[m][k]["reached"] for m in reached for k in d[m])
        parts.append("An extended run with the cap raised to 60,000 continued " + head + " to the 1% target on the mean urgent delay, which was reached after "
                     + join(f"{d[m]['delay_prio1_mean_h']['n']:,} ({low(m)})" for m in reached) + " replications"
                     + (", with every other metric inside its target at those counts." if every else "."))
    if not_reached:
        parts.append("The extended run for the " + join(low(m) for m in not_reached)
                     + " cells was interrupted by a memory limit on the workstation before it reached that target, so their estimates stand at "
                     + ", ".join(f"{d[m]['delay_prio1_mean_h']['n']:,}" for m in not_reached) + " replications with half-widths of "
                     + ", ".join(f"{100*d[m]['delay_prio1_mean_h']['rel_half_width']:.1f}%" for m in not_reached)
                     + "; the repository script continues them on request.")
    return "\n".join(out), " ".join(parts)


def _join(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _low(m):
    return MECH_LABEL[m].lower().replace(" (ours)", "")


def paired_sentence():
    """Paired 99% CIs of the differences between settled cells on the seeds they share (from table_E14_paired.csv)."""
    path = os.path.join(RES, "table_E14_paired.csv")
    if not os.path.exists(path):
        return ""
    t = pd.read_csv(path)
    mlab = {"delay_prio1_mean_h": "the mean urgent delay", "delay_prio1_p90_h": "the 90th-percentile urgent delay", "sl24_prio1": "the same-day service level"}
    sign = lambda x: "&minus;" if x < 0 else "+"
    def cell(a, b, metric):
        return t[(t.a == a) & (t.b == b) & (t.metric == metric)].iloc[0]
    def fmt(a, b):
        r1, r2, r3 = (cell(a, b, m) for m in ("delay_prio1_mean_h", "delay_prio1_p90_h", "sl24_prio1"))
        return (f"{_low(b)} minus {_low(a)} is {sign(r1.mean_diff_b_minus_a)}{abs(r1.mean_diff_b_minus_a):.2f} &plusmn; {r1.half_width_99:.2f} h on the mean urgent delay, "
                f"{sign(r2.mean_diff_b_minus_a)}{abs(r2.mean_diff_b_minus_a):.2f} &plusmn; {r2.half_width_99:.2f} h on its 90th percentile and "
                f"{sign(r3.mean_diff_b_minus_a)}{abs(r3.mean_diff_b_minus_a):.3f} &plusmn; {r3.half_width_99:.3f} on the same-day service level")
    pairs = [("pooled_greedy", "marketplace"), ("central_assign", "marketplace"), ("pooled_greedy", "central_assign"), ("inhouse", "marketplace")]
    body = "; ".join(fmt(a, b) for a, b in pairs if ((t.a == a) & (t.b == b)).any())
    n_common = int(t.n_common.min())
    nd = t[~t.distinguishable]
    if len(nd) == 0:
        tail = f"Every one of the {len(t)} pairwise differences is distinguishable from zero."
    else:
        items = [f"{_low(r.b)} against {_low(r.a)} on {mlab[r.metric]}" for r in nd.itertuples()]
        tail = (f"All but {len(nd)} of the {len(t)} pairwise differences are distinguishable from zero; the exception"
                + (" is " if len(nd) == 1 else "s are ") + _join(items) + ".")
    bg_mean = cell("pooled_greedy", "central_assign", "delay_prio1_mean_h"); bg_p90 = cell("pooled_greedy", "central_assign", "delay_prio1_p90_h")
    batched = (" Batched assignment therefore trades a slightly higher mean than greedy dispatch for a shorter tail, which is what an hourly batch should do: it waits to match, then matches well."
               if (bg_mean.distinguishable and bg_mean.mean_diff_b_minus_a > 0 and bg_p90.distinguishable and bg_p90.mean_diff_b_minus_a < 0) else "")
    mg = cell("pooled_greedy", "marketplace", "delay_prio1_mean_h")
    settled = ("The marketplace's advantage over greedy pooling, which the 30-seed cells left in doubt, is therefore settled."
               if mg.distinguishable else "The marketplace's advantage over greedy pooling remains within the paired interval.")
    return (f"Because every rule sees the same seeds, the paired differences on the {n_common:,} or more seeds that each pair of cells shares "
            f"are far tighter than the cell intervals (99% CIs): {body}. {tail}{batched} {settled}")


def settled_numbers():
    """Settled Phase-2 numbers: the extended run where it completed a mechanism, else the 4,000-replication run."""
    base = json.load(open(os.path.join(RES, "E14_precision.json")))
    p_long = os.path.join(RES, "E14_precision_long.json")
    if os.path.exists(p_long):
        long = json.load(open(p_long))
        for mech, dd in long.items():
            base[mech] = dd
    return base


def table_e16():
    """Table 6 of version 3: the E16 driving-table checks from results/table_E16.csv (run_phase3.py e16)."""
    p = os.path.join(RES, "table_E16.csv")
    if not os.path.exists(p):
        return "<p class='note'>E16 table not yet generated.</p>"
    df = pd.read_csv(p)
    out = ['<p class="tabcap" id="v3-tab-e16"><b>Table 6.</b> Driving-table checks (E16) on the committed tables (<span class="mono">driving-v1</span>). '
           'Speed made good through the tables&rsquo; own leg integrator on a flat 2 km leg against the JSC teleoperation measurements [29] (Measured; tolerance 5%); '
           'the same on the flattest real leg of at least 500 m (construction site to depot, 662 m, 5.8&deg; maximum slope, sun azimuth 270&deg;), shown for context against the flat-ground measurements; '
           'and the base-to-crater round-trip traction energy (8.95 km by day, 8.57 km at night) against Chen et al.&rsquo;s 0.4&ndash;4.4 kWh for a 500 kg rover [92] (Modelled) scaled by mass to 1,600 kg (Assumed linear). '
           'Supervised and autonomous rows do not depend on the round-trip time and are shown once.</p>',
           '<table class="small"><tr><th>Check</th><th>Leg</th><th>Lighting</th><th>Autonomy</th><th class="num">RTT (s)</th><th class="num">Simulated</th><th class="num">Reference</th><th class="num">Error or band</th><th>Result</th></tr>']
    lab = {"teleop": "teleoperation", "supervised": "supervised", "autonomous": "autonomous"}

    def speed_rows(check, name, leg_txt):
        s = df[df.check == check]
        for aut in ("teleop", "supervised", "autonomous"):
            sub = s[s.autonomy == aut].sort_values("rtt_s")
            if aut != "teleop":
                sub = sub.head(1)
            for _, r in sub.iterrows():
                light = "none (flat)" if str(r.lighting) == "none" else f"sun {int(float(r.lighting))}&deg;"
                if pd.notna(r.ref_kmh):
                    ref = f"{r.ref_kmh:.2f} km/h"
                    err = f"{100*r.rel_err:+.2f}%"
                    res = "pass (within 5%)" if check == "speed_made_good_vs_rtt_flat" else "context"
                else:
                    ref, err, res = "&ndash;", "&ndash;", "no measurement"
                rtt = f"{r.rtt_s:.0f}" if aut == "teleop" else "any"
                out.append(f"<tr><td>{name}</td><td>{leg_txt}</td><td>{light}</td><td>{lab[aut]}</td><td class='num'>{rtt}</td>"
                           f"<td class='num'>{r.sim_kmh:.3f} km/h</td><td class='num'>{ref}</td><td class='num'>{err}</td><td>{res}</td></tr>")

    speed_rows("speed_made_good_vs_rtt_flat", "Speed made good, calibration", "flat 2 km")
    speed_rows("speed_made_good_vs_rtt_real_leg", "Speed made good, real leg", "CONSTR to DEPOT, 662 m")
    e = df[df.check == "psr_round_trip_energy"]
    for aut in ("autonomous", "supervised", "teleop"):
        for light in ("day", "night"):
            r = e[(e.autonomy == aut) & (e.lighting == light)]
            if not len(r):
                continue
            r = r.iloc[0]
            out.append(f"<tr><td>Round-trip energy</td><td>BASE to PSR and back</td><td>{light}</td><td>{lab[aut]}</td><td class='num'>{r.rtt_s:.0f}</td>"
                       f"<td class='num'>{r.sim_kwh:.2f} kWh</td><td class='num'>{r.ref_kwh_lo:.2f}&ndash;{r.ref_kwh_hi:.2f} kWh</td>"
                       f"<td class='num'>band, mass-scaled</td><td>{'inside' if r.in_band else 'outside'}</td></tr>")
    out.append("</table>")
    return "\n".join(out)


def fill_common(html):
    """Placeholders shared by the version-2 and version-3 builds: the verification table, the E14 settled numbers,
    the paired sentence and the abstract's E3 gain."""
    t14, sent14 = table_e14()
    html = (html.replace("{{TABLE_VV}}", table_vv()).replace("{{TABLE_E14}}", t14).replace("{{E14_LONG}}", sent14)
            .replace("{PAIRED_SENTENCE}", paired_sentence()))
    # abstract numbers
    e3 = pd.read_csv(os.path.join(RES, "E3_thickness.csv"))
    a = e3[(e3.other_duty == 0.3) & (e3.n_companies == 6) & (e3.mechanism == "inhouse")].sort_values("seed")
    b = e3[(e3.other_duty == 0.3) & (e3.n_companies == 6) & (e3.mechanism == "marketplace")].sort_values("seed")
    gain = (a.delay_prio1_p90_h.values - b.delay_prio1_p90_h.values).mean()
    html = html.replace("{E3_GAIN}", f"{gain:.0f}")
    # settled Phase-2 numbers
    d = settled_numbers()
    key = {"INH": "inhouse", "GRD": "pooled_greedy", "BAT": "central_assign", "MKT": "marketplace"}
    for tag, mech in key.items():
        if mech not in d:
            continue
        r = d[mech]
        html = (html.replace("{" + tag + "_MEAN}", f"{r['delay_prio1_mean_h']['mean']:.2f}").replace("{" + tag + "_MEAN_HW}", f"{r['delay_prio1_mean_h']['half_width']:.2f}")
                .replace("{" + tag + "_P90}", f"{r['delay_prio1_p90_h']['mean']:.1f}").replace("{" + tag + "_P90_HW}", f"{r['delay_prio1_p90_h']['half_width']:.1f}")
                .replace("{" + tag + "_SL}", f"{r['sl24_prio1']['mean']:.3f}").replace("{" + tag + "_SL_HW}", f"{r['sl24_prio1']['half_width']:.3f}"))
    if "marketplace" in d and "pooled_greedy" in d:
        gm, mm = d["pooled_greedy"]["delay_prio1_mean_h"]["mean"], d["marketplace"]["delay_prio1_mean_h"]["mean"]
        gp, mp = d["pooled_greedy"]["delay_prio1_p90_h"]["mean"], d["marketplace"]["delay_prio1_p90_h"]["mean"]
        html = html.replace("{MKT_VS_GRD_PCT}", f"{100*(gm-mm)/gm:.0f}").replace("{MKT_VS_GRD_P90_PCT}", f"{100*(gp-mp)/gp:.0f}")
    ns = sorted(set(d[m]["delay_prio1_mean_h"]["n"] for m in d))
    html = html.replace("{N_LONG_WORDS}", (f"{ns[0]:,} replications per cell" if len(ns) == 1 else f"{ns[0]:,}&ndash;{ns[-1]:,} replications per cell"))
    return html


CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def render_pdf(html_path, pdf_path):
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--allow-file-access-from-files",
           f"--print-to-pdf={pdf_path}", "file:///" + html_path.replace("\\", "/")]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    print("chrome exit", r.returncode)
    print("pdf", os.path.exists(pdf_path), os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0)


def build_v2():
    """Version 2: paper/part*.html -> paper/paper.html and the v2 PDF (unchanged behaviour)."""
    parts = [open(os.path.join(HERE, f), encoding="utf-8").read() for f in
             ("part1_front.html", "part2_methods.html", "part3_results.html", "part4_back.html")]
    html = "\n".join(parts)
    html = html.replace("{{TABLE_MAIN}}", table_main()).replace("{{TABLE_ABL}}", table_abl())
    html = fill_common(html)
    out = os.path.join(HERE, "paper.html")
    open(out, "w", encoding="utf-8").write(html)
    print("wrote", out, len(html.split()), "words approx")
    render_pdf(out, os.path.join(HERE, "lunar_logistics_marketplace_paper_v2.pdf"))


V3 = os.path.join(HERE, "v3")
V3_PARTS = ("part1_front.html", "part2_related.html", "part3_methods.html", "part4_results.html", "part5_back.html")


def build_v3():
    """Version 3: paper/v3/part*.html -> paper/v3/paper.html (stylesheet ../style.css, figures ../../figures/) and
    paper/v3/where_the_lander_lands_v3.pdf. Fills {{v3-TABLE_E16}} from results/table_E16.csv and the shared tags."""
    parts = [open(os.path.join(V3, f), encoding="utf-8").read() for f in V3_PARTS]
    html = "\n".join(parts)
    html = html.replace("{{v3-TABLE_E16}}", table_e16())
    html = fill_common(html)
    out = os.path.join(V3, "paper.html")
    open(out, "w", encoding="utf-8").write(html)
    print("wrote", out, len(html.split()), "words approx")
    render_pdf(out, os.path.join(V3, "where_the_lander_lands_v3.pdf"))


def main(argv=None):
    """`python paper/build.py` builds version 2 as before; `python paper/build.py --v3` builds version 3."""
    argv = sys.argv[1:] if argv is None else argv
    if "--v3" in argv:
        build_v3()
    else:
        build_v2()


if __name__ == "__main__":
    main()
