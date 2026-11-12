"""Phase 6 values of paper P2 (position uncertainty in the margin, clocks and the reservation guard, lost link,
integrity of position reports, the propositions of Appendix A and the "proved, tested, assumed" table).

Called by build_p2.py: add(ctx) fills V (placeholders), T (tables) and F (figures) from

    results/E50_summary.json                      E50 (B-90): position error by layer set, violations, margin delay, H9', H10'
    results/E51_clocks.json, E51b_clocks.json     E51 (B-91, B-91b): clock classes, resync intervals, guards, H11
    results/E54_dtn.json                          E54 (B-94): lost link, custody, stuck reservations, H14
    results/E56_integrity.json                    E56 (B-96): detectors of wrong position reports, H15
    lunarsim/atc/safety.py, pnt.py, clocks.py     rule and model parameters (read, never retyped)

and follows the rules of build_p2.py: every number comes from a file, every sentence whose wording depends on an
outcome is composed here with the direction words chosen from the data, and every fixed phrase in the parts that
asserts a direction has a check() here. After the referee round of 11 Nov 2026 (reports/referee_phase6_p2.md;
decisions in reports/referee_phase6_decisions.md): E50b is read from results/E50b_summary.json; the eight-times cells of
E50 compose themselves when they are in the summary file; analyses not yet run (overlap durations, uphill encounters,
fresh seeds, the readings of "near the base") have one plain sentence each through ctx.awaited (build_p2.AWAITED), never
a marker; and a result that could not have come out otherwise is called a calculation or a property, not a test.
"H9'" and "H10'" are H9 and H10 of the Phase 6 pre-registration (paper/atc/PREREG6.md); the prime keeps them apart
from H9 (Mars) and H10 (sizing) of paper/atc/PREREG.md, which this paper already uses.
"""
import json
import math
import os
from statistics import NormalDist
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RES = os.path.join(ROOT, "results")
ND = NormalDist()
C_M_S = 299792458.0
MIN_DAY = 1440.0                                  # 60 s bins in a day: a false alarm (E56) is a bin with an alarm

LAYER_KEYS = ["dr", "dr+ranging", "dr+ranging+fixes", "lans@2030"]
LAYER_NAMES = {"dr": "dead reckoning alone", "dr+ranging": "+ ranging", "dr+ranging+fixes": "+ terrain fixes",
               "lans@2030": "+ navigation service as planned for 2030"}
DETECTORS = [("chi2_step", "chi-square, per step"), ("chi2_window", "chi-square, windowed"), ("cusum", "CUSUM"),
             ("logreg", "logistic regression"), ("net", "network (5 seeds)")]
PROSE = {"chi2_step": "per-step chi-square test", "chi2_window": "windowed chi-square test", "cusum": "CUSUM",
         "logreg": "logistic regression", "net": "network"}
FAULTS = ["jump", "drift", "frozen", "frame", "noise"]
FAULT_NAMES = {"jump": "jump", "drift": "slow drift", "frozen": "frozen report", "frame": "frame error",
               "noise": "noise inflation", "all": "all"}


def _load(name):
    path = os.path.join(RES, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def chi2_1_quantile(alpha):
    """(1 - alpha) quantile of the chi-square law with one degree of freedom: the square of the two-sided normal
    quantile."""
    return ND.inv_cdf(1.0 - alpha / 2.0) ** 2


def chi2_1_power(delta, alpha):
    """Probability that a one-degree-of-freedom test at level alpha flags an innovation whose mean is delta sigmas."""
    z = ND.inv_cdf(1.0 - alpha / 2.0)
    return ND.cdf(delta - z) + ND.cdf(-delta - z)


def k_of_n(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


def interval_name(s):
    """A resync interval in seconds as words: 10 s, 1 min, 10 min, 1 h, 6 h, 1 day, never."""
    if s in (None, "never", ""):
        return "never"
    s = float(s)
    for unit, size in (("day", 86400.0), ("h", 3600.0), ("min", 60.0)):
        if s >= size and abs(s / size - round(s / size)) < 1e-9:
            n = int(round(s / size))
            return f"{n}&nbsp;{unit}" + ("s" if unit == "day" and n > 1 else "")
    return f"{int(s)}&nbsp;s"


def add(ctx):
    """ctx: V, T, F, fill, pend, check, Pending, and the formatters of build_p2 (num, h_, pc, ci, cnt, words, sci, tab,
    NB, MINUS, PCT)."""
    c = SimpleNamespace(**ctx)
    c.e50 = _load("E50_summary.json")
    c.e51 = _load("E51_clocks.json")
    c.e51b = _load("E51b_clocks.json")
    c.e54 = _load("E54_dtn.json")
    c.e56 = _load("E56_integrity.json")
    c.e55 = _load("E55_integrity.json")
    c.m_ = lambda x, nd=1: f"{c.num(x, nd)}{c.NB}m"
    c.cim = lambda st, nd=1: c.ci(st["ci"][0], st["ci"][1], nd, unit="m")
    c.cih = lambda st, nd=2: c.ci(st["ci"][0], st["ci"][1], nd, unit="h")
    add_e50(c)
    add_e51(c)
    add_e54(c)
    add_e56(c)
    add_e55(c)
    add_b97(c)
    add_family(c)
    add_props(c)
    add_front(c)
    add_pta(c)


# ---------------------------------------------------------------------------------------------------------
# E50: position error by layer set, the widened margin, H9' and H10'
# ---------------------------------------------------------------------------------------------------------
def add_e50(c):
    V, fill, check, Pending = c.V, c.fill, c.check, c.Pending
    num, h_, pc, cnt, words, NB, PCT, MINUS = c.num, c.h_, c.pc, c.cnt, c.words, c.NB, c.PCT, c.MINUS
    m_, cim, cih = c.m_, c.cim, c.cih
    from lunarsim.atc import pnt as PN
    from lunarsim.atc import safety as S
    D = PN.DEFAULTS

    def e50(mult=None):
        if c.e50 is None:
            raise Pending("results/E50_summary.json (B-90) has not landed")
        if mult is not None and str(mult) not in c.e50["errors"]:
            raise Pending(f"E50 at {mult}x has no finished seeds in results/E50_summary.json")
        return c.e50

    c.e50f = e50

    def frames():
        """The per-run and per-region tables of E50 (results/E50_runs.csv, E50_errors.csv), for the quantities the
        summary file does not hold: driving time, the share of driving steps near the base, per-seed differences."""
        import pandas as pd
        fr, fe = os.path.join(RES, "E50_runs.csv"), os.path.join(RES, "E50_errors.csv")
        if not (os.path.exists(fr) and os.path.exists(fe)):
            raise Pending("results/E50_runs.csv or E50_errors.csv is missing")
        return pd.read_csv(fr), pd.read_csv(fe)

    def near_facts(mult=1):
        """'Near the base' as the analysis read it (two or more beacons in line of sight): its share of the driving
        steps, the fleet's driving hours in the month and the largest per-seed 95th percentile with ranging."""
        s = e50(mult)
        runs, err = frames()
        check("at least 2 of the 4 beacons" in s["design"]["region_rule"], "E50's region rule is two or more of four beacons in line of sight")
        a = err[(err["mult"] == mult) & (err["layer_set"] == "dr+ranging")]
        al, ne = a[a["region"] == "all"].set_index("seed")["n_steps"], a[a["region"] == "near"].set_index("seed")["n_steps"]
        check(len(al) == len(s["seeds"][str(mult)]), "E50_errors.csv holds every seed of the cell")
        p95 = a[a["region"] == "near"]["p95_m"]
        check(abs(float(p95.mean()) - s["h9"][str(mult)]["ranging_near_p95_m"]["mean"]) < 1e-3, "the per-seed table gives the summary's 95th percentile near the base")
        return SimpleNamespace(share=float(ne.sum() / al.sum()), drive_h=float(al.mean()) * s["design"]["dt_s"] / 3600.0,
                               seed_max=float(p95.max()), all_inside=bool((p95 < S.D0_M).all()))
    c.e50near, c.e50frames = near_facts, frames

    def readings(mult=1):
        """B-101 (results/E50_near_base.json): the second clause of H9' under five readings of 'near the base', for
        the ranging layer set. Checked against E50: reading (a) is the one used so far, (d) and (e) cover all driving."""
        n = _load("E50_near_base.json")
        if n is None:
            raise Pending("results/E50_near_base.json (B-101) is missing")
        s = e50(mult)
        b = n["multiples"][str(mult)]
        rd, sh = b["sets"]["dr+ranging"], b["share_of_driving"]
        nf = near_facts(mult)
        check(b["e50_reproduced_all"] is True and b["seeds"] == s["seeds"][str(mult)] and n["budget_m"] == S.D0_M,
              f"B-101 reproduces E50's cells at {mult}x on the same seeds, against the same budget")
        check(abs(rd["a"]["in_p95_m_mean"] - s["h9"][str(mult)]["ranging_near_p95_m"]["mean"]) < 1e-3 and abs(sh["a"]["mean"] - nf.share) < 0.005,
              "reading (a) of B-101 is the reading E50 used (two or more beacons in line of sight)")
        check(sh["d"]["mean"] == 1.0 and sh["e"]["mean"] == 1.0 and abs(rd["e"]["in_p95_m_mean"] - st(mult, "dr+ranging")["mean"]) < 1e-2
              and abs(rd["d"]["in_p95_m_mean"] - rd["e"]["in_p95_m_mean"]) < 1e-6,
              "readings (d) and (e), radio range by distance, cover all driving and give the error over all driving steps")
        ns = len(b["seeds"])
        check(rd["a"]["seeds_inside_budget"] == ns and all(rd[k]["seeds_inside_budget"] == 0 for k in "bcde"),
              "the clause holds in every seed under reading (a) and in no seed under the other four")
        check("PREREG6's words" in n["readings"]["e"] and "depends on the reading" in n["verdict"], "reading (e) is the registered wording; the file's verdict is 'depends on the reading'")
        return SimpleNamespace(rd=rd, sh=sh, ns=ns, n=n)
    c.e50readings = readings

    def readings_sentence():
        q = readings(1)
        rd, sh, ns = q.rd, q.sh, q.ns
        row = lambda k: f"{pc(sh[k]['mean'], 0)} of the driving, {m_(rd[k]['in_p95_m_mean'], 1 if k != 'a' else 2)}"
        out = (f"The clause was then computed under five readings on the same {cnt(ns)} seeds (simulation; the cells "
               f"reproduce E50's). (a) Two or more beacons in line of sight, the reading used: {row('a')}, inside the "
               f"budget in {cnt(rd['a']['seeds_inside_budget'])} of {cnt(ns)} seeds. (b) One or more beacons in line "
               f"of sight: {row('b')}, inside in no seed. (c) Within 1{NB}km of the base mast: {row('c')}, in no "
               f"seed. (d) Within the 5{NB}km radio range of the mast, and (e) within radio range of any base beacon, "
               f"which is the registered wording read by distance: all of the driving, "
               f"{m_(rd['e']['in_p95_m_mean'], 1)}, in no seed. Under the registered wording the clause fails in "
               f"every seed; it holds only under the reading that was chosen after the results.")
        try:
            q4 = readings(4)
            out += (f" At four times the fleet the pattern is the same on {cnt(q4.ns)} seeds: "
                    f"{m_(q4.rd['a']['in_p95_m_mean'], 2)} under (a), inside in every seed, and "
                    f"{m_(q4.rd['e']['in_p95_m_mean'], 1)} under the registered wording, inside in none. The "
                    f"eight-times cells were not run under the readings.")
        except (Pending, KeyError):
            pass
        return out

    def model_sentence():
        check(D["budget_m"] == S.D0_M, "the separation budget of H9' is R1's static margin d0")
        check(D["lans_availability"][2028] == 0.0, "the navigation service offers no fix in 2028")
        first = min(y for y, a in D["lans_availability"].items() if a > 0)
        return (f"Dead reckoning from wheel odometry, an inertial unit, a star tracker and visual odometry drifts by "
                f"{pc(D['dr_firm'], 0)} of the distance driven on firm level ground (Measured [60]; a requirement "
                f"in [62, 63]), {pc(D['dr_shadow'], 0)} in shadow (Assumed) and {pc(D['dr_loose'], 0)} on loose "
                f"soil or on slopes above {num(D['slope_loose_deg'], 0)}&deg; (Measured on Earth [61]). Two-way "
                f"radio ranging to {words(len(D['beacons']))} surveyed beacons at the base and to as many as "
                f"{words(D['max_peers'])} other vehicles in line of sight is good to {m_(D['uwb_sigma_m'], 1)} "
                f"(Measured on Earth [64, 65]) within {m_(D['uwb_range_m'], 0)} and to "
                f"{m_(D['radio_sigma_m'], 0)} beyond that (both ranges Assumed). A terrain fix against the orbital "
                f"map, taken at a stop of {num(D['fix_stop_s'], 0)}{NB}s (Assumed), is good to "
                f"{m_(D['fix_sigma_lit_m'], 1)} in sunlight (a requirement of [62]) and to "
                f"{m_(D['fix_sigma_dark_m'], 0)} in the dark, where {pc(D['fix_fail_dark'], 0)} of attempts are "
                f"taken to fail [63]; the lunar navigation service would add a fix of "
                f"{m_(D['lans_95_m'], 0)} (95{PCT}) but offers none before {first} [67, 68]. A filter on each vehicle "
                f"fuses the four, carries the bias of the current drive leg as a state, takes ranges to beacons as "
                f"Kalman updates and ranges to other vehicles by covariance intersection, and gives the vehicle a "
                f"95{PCT} bound on its own horizontal error, b = {num(PN.R95, 2)}{NB}&sigma;<sub>max</sub>.")
    fill("P2-E50-MODEL-SENTENCE", model_sentence, "E50")
    V["P2-E50-BUDGET"] = m_(S.D0_M, 0)

    def design_sentence():
        s = e50(1)
        d = s["design"]
        check(d["regime"] == "C_AUCTION" and d["roads"] == "atc", "E50 runs the on-robot auction with the shared table")
        check(d["budget_m"] == S.D0_M and d["k_pos"] == 1.0, "E50's budget is d0 and its margin multiplier is 1")
        n1, n4 = len(s["seeds"]["1"]), len(s["seeds"].get("4", []))
        n8 = len(s["seeds"].get("8", []))
        check(n1 == 30 and n4 == 10, "E50 ran 30 seeds at 1x and 10 at 4x, as the dated change of [59] states")
        return (f"The logistics model at its middle load in the ATC mode, with jobs awarded by the on-robot auction "
                f"of [44] at a message loss of {num(d['regime_kw']['loss'], 2)}, over the month of "
                f"{d['regime_kw']['start_year']} in which the base sees Earth least (July), at one, four and eight "
                f"times the fleet. A cell takes 1.5, 11 and 42 minutes at the three sizes, so the cells run "
                f"{cnt(n1)}, {cnt(n4)} and 5 seeds (a dated change of [59], decided on run time alone); "
                + (f"{cnt(n8)} of the 5 eight-times seeds have finished. " if 0 < n8 < 5 else
                   "the eight-times cells have not finished. " if n8 == 0 else "")
                + f"Each cell is one run with perfect position, whose recorded trajectories feed the position model at "
                f"each layer set (dead reckoning alone; with ranging; with terrain fixes; with the navigation service "
                f"as in {d['regime_kw']['start_year']} and, as a variant, as planned for {d['lans_variant_year']}), "
                f"and then one run for each of two margins with k = {num(d['k_pos'], 0)}: the bound of dead reckoning "
                f"alone and the bound of the layered scheme. The bound a vehicle files with is its hourly maximum "
                f"from the perfect-position run, and position errors start at zero at the start of the month "
                f"(Assumed: every vehicle surveyed then).")
    fill("P2-E50-DESIGN-SENTENCE", design_sentence, "E50")

    def st(mult, ls, region="all", key="p95_m"):
        return e50(mult)["errors"][str(mult)][ls][region][key]

    def errors_paragraph():
        s = e50(1)
        check(s["errors"]["1"]["dr+ranging+fixes"]["all"] == s["errors"]["1"]["dr+ranging+fixes+lans"]["all"],
              "in 2028 the navigation-service layer changes nothing (its rows equal the terrain-fix rows)")
        hrs = s["errors"]["1"]["dr"]["shift_p95_m_mean_over_seeds"]
        first = s["h9"]["1"]["dr_first_driving_hour_p95_over_budget"]
        check(first == 1 and hrs[0] > S.D0_M, "dead reckoning alone passes the budget in the first driving hour")
        check(st(1, "dr")["mean"] > st(1, "dr+ranging")["mean"] > st(1, "dr+ranging+fixes")["mean"] > st(1, "lans@2030")["mean"],
              "each added layer lowers the 95th percentile of the error at 1x")
        rn, ra = st(1, "dr+ranging", "near"), st(1, "dr+ranging", "away")
        fn, fa = st(1, "dr+ranging+fixes", "near"), st(1, "dr+ranging+fixes", "away")
        check(rn["ci"][1] < S.D0_M < ra["ci"][0], "ranging holds the budget near the base and not away from it")
        check(fa["ci"][0] > S.D0_M, "terrain fixes do not hold the budget away from the base")
        share = st(1, "dr+ranging+fixes", "away", "share_b95_over_budget")
        stop1 = s["errors"]["1"]["dr+ranging+fixes"]["fix_stop_h_per_month"]
        nf = near_facts(1)
        check(0.15 < nf.share < 0.35, "two or more beacons are in line of sight in about a quarter of the driving steps")
        check(0.1 < stop1["mean"] / nf.drive_h < 0.4, "the fix stops are a large share of the fleet's driving time")
        out = (f"Table 9 gives the position error while driving for each layer set. With dead reckoning alone the "
               f"95th percentile of the error at today's fleet was {m_(st(1, 'dr')['mean'], 0)} "
               f"{cim(st(1, 'dr'), 0)} over the month, and it had passed the {m_(S.D0_M, 0)} budget in the first "
               f"hour of driving ({m_(hrs[0], 0)}). Ranging brought it to {m_(st(1, 'dr+ranging')['mean'], 1)}: "
               f"{m_(rn['mean'], 2)} {cim(rn, 2)} where at least two of the four beacons were in line of sight, "
               f"which is {pc(nf.share, 0)} of the driving steps, and {m_(ra['mean'], 1)} "
               f"elsewhere. Terrain fixes brought it to {m_(st(1, 'dr+ranging+fixes')['mean'], 1)}: "
               f"{m_(fn['mean'], 2)} near the base and {m_(fa['mean'], 1)} {cim(fa, 1)} away from it, where the "
               f"vehicle's own 95{PCT} bound was above the budget in {pc(share['mean'], 0)} of driving steps. The "
               f"navigation service has no fix to offer in 2028, so the fourth layer changed nothing; at the "
               f"availability planned for {s['design']['lans_variant_year']} the error away from the base would be "
               f"{m_(st(1, 'lans@2030', 'away')['mean'], 2)}. The fixes cost stops: {h_(stop1['mean'], 1)} a month "
               f"across the fleet at today's size, {pc(stop1['mean'] / nf.drive_h, 0)} of the "
               f"{h_(nf.drive_h, 0)} the fleet drives in the month,")
        try:
            e50(4)
            stop4 = s["errors"]["4"]["dr+ranging+fixes"]["fix_stop_h_per_month"]
            n4 = len(s["seeds"]["4"])
            out += (f" and {h_(stop4['mean'], 0)} at four times. At four times the fleet ({cnt(n4)} seeds) ranging "
                    f"gave {m_(st(4, 'dr+ranging', 'near')['mean'], 2)} near the base and terrain fixes "
                    f"{m_(st(4, 'dr+ranging+fixes', 'away')['mean'], 1)} "
                    f"{cim(st(4, 'dr+ranging+fixes', 'away'), 1)} away from it.")
        except Pending:
            out += "."
        return out
    fill("P2-E50-ERRORS-PARAGRAPH", errors_paragraph, "E50")
    c.e50st = st

    def verdict(flag):
        return "supported" if flag else "not supported"

    def h9_sentence():
        s = e50(1)
        h = s["h9"]["1"]
        check(h["budget_m"] == S.D0_M, "H9' is judged against d0")
        nf = near_facts(1)
        check(h["ranging_near_supported"] and nf.all_inside, "under the reading used, ranging holds the budget near the base in every seed")
        out = (f"H9&prime; has three clauses, each judged by the side of the {m_(S.D0_M, 0)} budget on which the "
               f"95th percentile of the error falls [59]. Dead reckoning alone exceeds the budget within one "
               f"8-hour shift of driving: {verdict(h['dr_supported'])} (in driving hour "
               f"{cnt(h['dr_first_driving_hour_p95_over_budget'])}). With ranging the error stays inside the budget "
               f"within radio range of the base beacons: the verdict depends on the reading. The registered text does "
               f"not say what &ldquo;within radio range of the base beacons&rdquo; is. The analysis read it as a "
               f"route sample in line of sight of two or more of the four beacons, a rule that was written with the "
               f"results and not before them [59]. That reading covers {pc(nf.share, 0)} of the driving steps, and "
               f"under it the error is {m_(h['ranging_near_p95_m']['mean'], 2)}, inside the budget in every seed "
               f"(largest {m_(nf.seed_max, 2)}); over all driving steps it is "
               f"{m_(st(1, 'dr+ranging')['mean'], 1)}, outside it. " + readings_sentence() + " With absolute fixes "
               f"it stays inside the budget away "
               f"from the base: {verdict(h['fixes_away_supported'])} ({m_(h['fixes_away_p95_m']['mean'], 1)}")
        lans = st(1, "lans@2030", "away")
        if not h["fixes_away_supported"]:
            check(lans["ci"][0] > S.D0_M, "the 2030 navigation service does not hold the budget away from the base either")
            out += f", and still {m_(lans['mean'], 1)} with the navigation service as planned for 2030"
        out += ")."
        try:
            h4 = e50(4)["h9"]["4"]
            same = all(h4[k] == h[k] for k in ("dr_supported", "ranging_near_supported", "fixes_away_supported"))
            out += (f" At four times the fleet the three readings are "
                    f"{'the same' if same else 'not all the same'} ({m_(h4['ranging_near_p95_m']['mean'], 2)} with "
                    f"ranging where two beacons are in line of sight, {m_(h4['fixes_away_p95_m']['mean'], 1)} away "
                    f"from the base with fixes).")
        except Pending:
            pass
        return out
    fill("P2-E50-H9-SENTENCE", h9_sentence, "E50")

    def margin_paragraph():
        s = e50(1)
        v1, d1 = s["violations"]["1"], s["delay"]["1"]
        nm = v1["no_margin"]
        rng = [nm[k]["mean"] for k in ("dr+ranging", "dr+ranging+fixes", "lans@2030")]
        check(nm["dr"]["mean"] > max(rng), "without a margin dead reckoning alone gives the most overlaps at 1x")
        wm = v1["with_margin"]
        check(wm["dr"]["mean"] < nm["dr"]["mean"] and wm["layered"]["mean"] < nm["dr+ranging+fixes"]["mean"],
              "the margin lowers the number of true-time overlaps at 1x")
        n1 = nm["dr"]["n"]
        per = lambda x: f"{num(x * n1, 0)} in {cnt(n1)} seeds"
        # the count without a margin does not follow the size of the error (the referee's M2): at 4x it is the same
        # for layer sets whose errors differ a hundredfold
        runs, _ = frames()
        ov = runs[(runs["violations"] > 0) & runs["variant"].isin(["margin_dr", "margin_layered"])]["overlap_s"]
        check(len(ov) > 0, "some runs with the margin still hold an overlap")
        byc = ""
        try:
            s4 = e50(4)
            n4c = [s4["violations"]["4"]["no_margin"][k]["mean"] for k in LAYER_KEYS]
            p4 = [st(4, k)["mean"] for k in LAYER_KEYS]
            check(max(n4c) / min(n4c) < 1.15 and max(p4) / min(p4) > 50,
                  "at 4x the overlap count without a margin is the same within 15 % for position errors that differ more than fiftyfold")
            byc = (f" The counts show it: at four times the fleet they were {num(min(n4c), 0)} to {num(max(n4c), 0)} a "
                   f"month for layer sets whose 95th-percentile errors run from {m_(max(p4), 0)} down to "
                   f"{m_(min(p4), 1)}.")
        except Pending:
            pass
        out = (f"Table 10 gives the overlaps and the delay. An overlap is a pair of conflicting reservations whose "
               f"windows overlap in true time. Its count without a margin is fixed by the design and is not a "
               f"measure of safety: a waiting vehicle's window is filed to start where the conflicting window ends, "
               f"so the two windows of such a back-to-back pair overlap whenever the two position errors shift them "
               f"in the unfavourable order, about half the time, however small the errors are.{byc} At today's "
               f"fleet the count was {num(nm['dr']['mean'], 2)} a month with dead reckoning alone and "
               f"{num(min(rng), 2)} to {num(max(rng), 2)} with the other layer sets; it says how many back-to-back "
               f"pairs the month held. " + c.awaited("overlaps") + f" With each window widened by the vehicle's own "
               f"bound an overlap remains only where an error was larger than the bound that was filed: "
               f"{num(wm['dr']['mean'], 2)} a month under the dead-reckoning "
               f"margin ({per(wm['dr']['mean'])}) and {num(wm['layered']['mean'], 2)} under the layered margin "
               f"({per(wm['layered']['mean'])}), with {num(float(ov.min()), 0)} to {num(float(ov.max()), 0)}{NB}s of "
               f"overlapping time in a run that had one, over all fleet sizes. That is the rate at which the filed "
               f"bound was exceeded; it is not a test of Proposition 2, because the simulation shifts each window "
               f"by error over speed, which is the proposition's own premise (Section 3.9). "
               f"The two margins differ in size: {h_(d1['margin_dr_margin_h_mean']['mean'], 2)} "
               f"at each end of a window for dead reckoning alone and {h_(d1['margin_layered_margin_h_mean']['mean'], 3)} "
               f"({num(d1['margin_layered_margin_h_mean']['mean'] * 3600, 0)}{NB}s) for the layered scheme. Delay per "
               f"delivery with perfect position was {h_(d1['perfect']['mean'], 2)} {cih(d1['perfect'])}. The layered "
               f"margin changed it by {h_(d1['margin_layered_minus_perfect']['mean'], 3, sign=True)} "
               f"{cih(d1['margin_layered_minus_perfect'], 3)} and the dead-reckoning margin by "
               f"{h_(d1['margin_dr_minus_perfect']['mean'], 2, sign=True)} {cih(d1['margin_dr_minus_perfect'])}, "
               f"with the fleet's waiting on the roads at {h_(d1['perfect_road_wait_h']['mean'], 2)}, "
               f"{h_(d1['margin_layered_road_wait_h']['mean'], 2)} and {h_(d1['margin_dr_road_wait_h']['mean'], 2)} "
               f"a month for perfect position, the layered margin and the dead-reckoning margin.")
        try:
            s4 = e50(4)
            v4, d4 = s4["violations"]["4"], s4["delay"]["4"]
            nm4 = [v4["no_margin"][k]["mean"] for k in LAYER_KEYS]
            out += (f" At four times the fleet the overlaps with the margin were "
                    f"{num(v4['with_margin']['dr']['mean'], 1)} a month (dead reckoning) and "
                    f"{num(v4['with_margin']['layered']['mean'], 1)} "
                    f"{c.ci(*v4['with_margin']['layered']['ci'], 1, unit='')} (layered). Perfect position gave "
                    f"{h_(d4['perfect']['mean'], 2)} {cih(d4['perfect'])}; the dead-reckoning margin changed it by "
                    f"{h_(d4['margin_dr_minus_perfect']['mean'], 2, sign=True)} {cih(d4['margin_dr_minus_perfect'])} "
                    f"and the layered margin by {h_(d4['margin_layered_minus_perfect']['mean'], 2, sign=True)} "
                    f"{cih(d4['margin_layered_minus_perfect'])}, with road waiting of "
                    f"{h_(d4['perfect_road_wait_h']['mean'], 1)}, {h_(d4['margin_layered_road_wait_h']['mean'], 1)} "
                    f"and {h_(d4['margin_dr_road_wait_h']['mean'], 1)} in the same order.")
        except Pending:
            pass
        return out
    fill("P2-E50-MARGIN-PARAGRAPH", margin_paragraph, "E50")

    def gap4_reading():
        """(not_supported, clause) for H10' clause 2 at 4x, with the wording chosen from the data."""
        s = e50(4)
        g1, g4 = s["h10"]["gap_by_mult"]["1"], s["h10"]["gap_by_mult"]["4"]
        d4 = s["delay"]["4"]
        grows = g4["mean"] > g1["mean"] and g4["ci"][0] > 0
        if grows:
            return True, (f"supported at four times, where the layered margin's cost is "
                          f"{h_(g4['mean'], 2, sign=True)} {cih(g4)} against {h_(g1['mean'], 3, sign=True)} at today's fleet")
        if g4["mean"] < 0:
            more_wait = d4["margin_layered_road_wait_h"]["mean"] >= d4["perfect_road_wait_h"]["mean"]
            check(more_wait, "at 4x the layered run waited no less on the roads than the perfect run (the negative "
                             "gap is not a gain on the roads)")
            check(g4["ci"][1] > -0.25 * abs(g4["mean"]) - 0.1, "the 4x interval of the layered gap only just excludes zero")
            runs, _ = frames()
            p4 = runs[(runs["mult"] == 4) & (runs["variant"] == "perfect")]["delay_mean_h"]
            check(len(p4) == g4["n"] and float(p4.std(ddof=1)) > 5 * abs(g4["mean"]),
                  "at 4x the spread of the perfect-position delay between seeds is many times the layered margin's difference")
            return False, (f"not supported at four times, and not resolved either: the difference is "
                           f"{h_(g4['mean'], 2, sign=True)} {cih(g4)} on {cnt(g4['n'])} seeds whose perfect-position "
                           f"delays run from {h_(float(p4.min()), 1)} to {h_(float(p4.max()), 1)} (standard deviation "
                           f"{h_(float(p4.std(ddof=1)), 1)}), so ten seeds cannot settle a difference of this size, "
                           f"and we do not read it as a gain. The same runs waited slightly longer on the roads "
                           f"({h_(d4['margin_layered_road_wait_h']['mean'], 1)} against "
                           f"{h_(d4['perfect_road_wait_h']['mean'], 1)}), and a margin of "
                           f"{num(d4['margin_layered_margin_h_mean']['mean'] * 3600, 0)}{NB}s changes the order in "
                           f"which the auction awards jobs, which moves the delay either way")
        return False, (f"not supported at four times, where the layered margin's difference is "
                       f"{h_(g4['mean'], 2, sign=True)} {cih(g4)}, no larger than at today's fleet")
    c.e50gap4 = gap4_reading

    def h10_sentence():
        s = e50(1)
        h, d1 = s["h10"], s["delay"]["1"]
        check(abs(h["tost_margin_h"] - 0.5 * h["perfect_delay_1x_h"]) < 1e-9, "the equivalence margin is 50 % of the perfect-position delay")
        lo, hi = h["layered_minus_perfect_1x_90ci"]
        check(h["layered_within_supported"] == (-h["tost_margin_h"] < lo and hi < h["tost_margin_h"]),
              "H10' clause 1 follows from the 90 % interval and the margin")
        dlo, dhi = h["dr_minus_perfect_1x_95ci"]
        check(h["dr_larger_supported"] == (dlo > 0), "H10' clause 3 follows from the 95 % interval at 1x")
        runs, _ = frames()
        r1 = runs[runs["mult"] == 1]
        pf = r1[r1["variant"] == "perfect"].set_index("seed")["delay_mean_h"]
        dd = r1[r1["variant"] == "margin_dr"].set_index("seed")["delay_mean_h"] - pf
        check(abs(float(dd.mean()) - d1["margin_dr_minus_perfect"]["mean"]) < 1e-6 and abs(float(pf.mean()) - h["perfect_delay_1x_h"]) < 1e-6,
              "E50_runs.csv gives the summary's perfect-position delay and dead-reckoning difference at 1x")
        from scipy.stats import wilcoxon
        n_pos, p_w = int((dd > 0).sum()), float(wilcoxon(dd).pvalue)
        sd1 = float(pf.std(ddof=1))
        check(h["tost_margin_h"] > sd1 and h["tost_margin_h"] > 100 * hi, "the registered equivalence margin is larger than the spread between seeds and more than a hundred times the difference")
        out = (f"H10&prime; has three clauses [59]. With the layered margin the delay is within 1.5 times the "
               f"perfect-position delay at today's fleet (equivalence margin 50{PCT} of that delay, "
               f"{h_(h['tost_margin_h'], 2)}): {verdict(h['layered_within_supported'])} (90{PCT} interval of the "
               f"difference {c.ci(lo, hi, 3)}, ratio {num(h['ratio_layered_over_perfect_1x'], 4)}). The registered "
               f"margin is larger than the standard deviation of the delay between seeds ({h_(sd1, 1)}) and "
               f"{cnt(round(h['tost_margin_h'] / d1['margin_layered_minus_perfect']['mean'], -2))} times the "
               f"difference, so passing it says little; the smallest margin the same test would pass is the upper "
               f"end of the interval, {h_(hi, 3)}, {pc(hi / h['perfect_delay_1x_h'], 2)} of the perfect-position "
               f"delay. This comparison is without the stops for terrain fixes, which the next paragraph adds. The "
               f"gap grows at four and eight times: ")
        try:
            out += gap4_reading()[1]
        except Pending:
            out += "the four-times cells have not finished"
        x8 = V["P2-E50-X8-CLAUSE"]
        out += (f"; at eight times the gap is {x8}. " if x8 else ". The eight-times cells have not finished. ")
        check(n_pos > len(dd) / 2 and p_w < 0.05 and not h["dr_larger_supported"],
              "the dead-reckoning margin cost more in most seeds while the registered interval on the mean includes zero")
        out += (f"With dead reckoning alone and the widened margin the delay is larger, by an interval that excludes "
                f"zero. The registered text names no fleet for this clause; it is read at today's fleet, like the "
                f"first clause, by a change dated after the results at today's fleet were seen [59]: "
                f"{verdict(h['dr_larger_supported'])} by the registered rule "
                f"({h_(d1['margin_dr_minus_perfect']['mean'], 2, sign=True)} {cih(d1['margin_dr_minus_perfect'])}). "
                f"The mean could not be told from zero, but most seeds moved the same way: the dead-reckoning margin "
                f"was the costlier in {cnt(n_pos)} of the {cnt(len(dd))} seeds (Wilcoxon signed-rank p = "
                f"{num(p_w, 3)}, a test chosen after the results)")
        try:
            d4 = e50(4)["delay"]["4"]["margin_dr_minus_perfect"]
            out += (f". At four times the same difference is {h_(d4['mean'], 2, sign=True)} {cih(d4)}, "
                    f"{'which excludes zero' if d4['ci'][0] > 0 else 'which does not exclude zero'} and is "
                    f"reported as exploratory.")
        except Pending:
            out += "."
        return out

    def has8():
        """Whether the eight-times cells of E50 are in the summary file. They are awaited (decision A4): while they
        are absent the text says so in one plain sentence; when they land the sentences below compose themselves."""
        return c.e50 is not None and "8" in c.e50["errors"] and "8" in c.e50["h10"]["gap_by_mult"]
    c.e50has8 = has8

    def x8_clause():
        if not has8():
            return ""
        s = e50(8)
        g8 = s["h10"]["gap_by_mult"]["8"]
        return (f"{h_(g8['mean'], 2, sign=True)} {cih(g8)} on {cnt(g8['n'])} seeds")
    fill("P2-E50-X8-CLAUSE", x8_clause, "E50 8x: the layered margin's delay gap at eight times the fleet")
    fill("P2-E50-H10-SENTENCE", h10_sentence, "E50")

    def x8_sentence():
        if not has8():
            return "The eight-times cells of E50 have not finished."
        s = e50(8)
        h8, d8 = s["h9"]["8"], s["delay"]["8"]
        return (f"At eight times the fleet ({cnt(len(s['seeds']['8']))} seeds) ranging gave "
                f"{m_(h8['ranging_near_p95_m']['mean'], 2)} near the base and terrain fixes "
                f"{m_(h8['fixes_away_p95_m']['mean'], 1)} away from it; perfect position gave "
                f"{h_(d8['perfect']['mean'], 2)}, the dead-reckoning margin changed it by "
                f"{h_(d8['margin_dr_minus_perfect']['mean'], 2, sign=True)} {cih(d8['margin_dr_minus_perfect'])} and "
                f"the layered margin by {h_(d8['margin_layered_minus_perfect']['mean'], 2, sign=True)} "
                f"{cih(d8['margin_layered_minus_perfect'])}.")
    fill("P2-E50-X8-SENTENCE", x8_sentence,
         "E50 8x: position error near and away from the base, and the delay cost of the two margins, at eight times the fleet")

    def e50b():
        """E50b (B-90b, run after the referee round): the layered-margin run with the terrain-fix stops inside the
        logistics model, at 1x on E50's 30 seeds. results/E50b_summary.json, checked against E50."""
        b = _load("E50b_summary.json")
        if b is None:
            raise Pending("results/E50b_summary.json (B-90b) has not landed")
        s = e50(1)
        m = b["metrics"]["delay_mean_h"]
        check(b["seeds"] == s["seeds"]["1"] and m["n_seeds"] == len(s["seeds"]["1"]) and "fleet x1" in b["design"]["base"],
              "E50b runs E50's seeds at today's fleet")
        check(b["e50_reproduced_all_seeds"] is True and abs(m["without_stop_time"] - s["delay"]["1"]["margin_layered"]["mean"]) < 1e-6,
              "E50b's arm without stop time reproduces E50's layered-margin cell")
        check(abs(b["stops"]["perfect_run_fix_stop_h_mean"] - s["errors"]["1"]["dr+ranging+fixes"]["fix_stop_h_per_month"]["mean"]) < 1e-6,
              "E50b's stop time of the position run is E50's")
        check(b["design"]["stop_s"] == D["fix_stop_s"] and b["design"]["defer_in_single"] is True,
              "E50b uses the position model's stop of a terrain fix and takes no stop inside a one-lane segment")
        check(abs(m["diff_mean"] - (m["with_stop_time"] - m["without_stop_time"])) < 1e-9, "E50b's difference is the difference of its two arms")
        check("exploratory" in b["h10_primary_with_stop_time"]["note"], "E50b is exploratory, outside the confirmatory family (the file says so)")
        return b
    c.e50bf = e50b

    def e50b_sentence():
        b = e50b()
        s = e50(1)
        m, st_, hp = b["metrics"], b["stops"], b["h10_primary_with_stop_time"]
        d, rw, vi = m["delay_mean_h"], m["road_wait_h"], m["violations"]
        runs, _ = frames()
        deliv = float(runs[(runs["mult"] == 1) & (runs["variant"] == "perfect")]["delivered"].mean())
        stop1 = s["errors"]["1"]["dr+ranging+fixes"]["fix_stop_h_per_month"]["mean"]
        frac = st_["engine_fix_stop_h_mean"] / st_["perfect_run_fix_stop_h_mean"]
        lo, hi = d["diff_ci95_bootstrap"]
        check(d["diff_mean"] > 0 and d["seeds_higher"] > d["seeds_lower"], "with the stops in the model the delay per delivery rose")
        check(rw["diff_ci95_bootstrap"][0] < 0 < rw["diff_ci95_bootstrap"][1], "the stops did not change the waiting on the roads")
        check(vi["with_stop_time"] == 0.0, "with the stops in the model no overlap occurred in any seed")
        check(0.5 < frac < 1.0, "the model inserted a part of the position run's stop time, so the delay is a lower bound")
        check(0.2 < st_["fixes_inside_single_lane_share"] < 0.3, "about a quarter of the fixes were taken inside one-lane segments")
        check(hp["ratio_to_perfect"] < 1.5 and abs(hp["margin_h"] - s["h10"]["tost_margin_h"]) < 1e-9, "with the stops the delay is still within 1.5 times the perfect-position delay")
        check(d["diff_mean"] > 20 * s["delay"]["1"]["margin_layered_minus_perfect"]["mean"], "the stops cost far more delay than the widened windows")
        excl = lo > 0
        return (f"A follow-up run, E50b, made after these results and therefore exploratory, puts the stops into the "
                f"logistics model at today's fleet on the same {cnt(d['n_seeds'])} seeds: each stop of "
                f"{num(b['design']['stop_s'], 0)}{NB}s lengthens its leg and shifts the reservations after it, and a "
                f"stop that would fall inside a one-lane segment is taken just after the segment's exit, since a "
                f"vehicle may not stand in one (R3). That was the case for "
                f"{pc(st_['fixes_inside_single_lane_share'], 0)} of the fixes: in E50 a quarter of the fixes behind "
                f"Table 9 were taken where the rules allow no stop. The arm without stop time reproduced E50's "
                f"layered-margin cell in every seed. With the stops, delay per delivery was "
                f"{h_(d['with_stop_time'], 2)} against {h_(d['without_stop_time'], 2)}, a difference of "
                f"{h_(d['diff_mean'], 2, sign=True)} {c.ci(lo, hi, 2)} or {pc(d['diff_mean'] / d['without_stop_time'], 1)}, "
                f"higher in {cnt(d['seeds_higher'])} seeds and lower in {cnt(d['seeds_lower'])}; the bootstrap "
                f"interval {'excludes' if excl else 'includes'} zero"
                + (f" and a paired t test gives p = {num(d['paired_t_p'], 2)}, so the size of the cost is poorly "
                   f"determined" if excl and d["paired_t_p"] > 0.05 else f" (paired t test p = {num(d['paired_t_p'], 3)})")
                + f". The ratio to perfect position was {num(hp['ratio_to_perfect'], 3)}, still inside the 1.5 of "
                f"H10&prime;'s first clause. Waiting on the roads did not change ({h_(rw['diff_mean'], 2, sign=True)} "
                f"{c.ci(*rw['diff_ci95_bootstrap'], 2)}), and no overlap occurred in any seed. The figure is a lower "
                f"bound: the model inserted {h_(st_['engine_fix_stop_h_mean'], 1)} of stops a month, "
                f"{pc(frac, 0)} of the {h_(st_['perfect_run_fix_stop_h_mean'], 1)} of the position run, because the "
                f"other fixes fall on repositioning drives, which do not pass through the road layer. By arithmetic "
                f"alone, {h_(stop1, 1)} of stops over the month's {cnt(deliv)} deliveries is "
                f"{h_(stop1 / deliv, 2)} per delivery before any queueing. The cost of the layered scheme at today's "
                f"fleet is therefore that of its stops, not the "
                f"{h_(s['delay']['1']['margin_layered_minus_perfect']['mean'], 3)} of its widened windows.")
    fill("P2-E50B-SENTENCE", e50b_sentence,
         "E50b: delay per delivery with the terrain-fix stops inside the engine, against perfect position")

    def stop_clause():
        s = e50(1)
        stop1 = s["errors"]["1"]["dr+ranging+fixes"]["fix_stop_h_per_month"]["mean"]
        check("not in the engine's delay" in s["h10"]["note"], "E50's delay leaves out the terrain-fix stops (the file says so)")
        return f"about {h_(stop1, 0)} a month for today's fleet"
    fill("P2-E50-STOP-CLAUSE", stop_clause, "E50")
    add_e50_tables(c)


def add_e50_tables(c):
    """Table 9 (position error by layer set), Table 10 (overlaps and delay) and Figure 2."""
    num, pc, cnt = c.num, c.pc, c.cnt
    Pending = c.Pending

    def table_errors():
        s = c.e50f(1)
        rows = []
        for mult in ("1", "4", "8"):
            if mult not in s["errors"]:
                continue
            for ls in LAYER_KEYS:
                e = s["errors"][mult][ls]
                p = e["all"]["p95_m"]
                rows.append([f"&times;{mult}", cnt(p["n"]), LAYER_NAMES[ls], num(e["all"]["median_m"]["mean"], 2),
                             f"{num(p['mean'], 1)} {c.ci(p['ci'][0], p['ci'][1], 1, unit='')}",
                             num(e["near"]["p95_m"]["mean"], 2), num(e["away"]["p95_m"]["mean"], 1),
                             pc(e["all"]["share_b95_over_budget"]["mean"], 0),
                             num(e["fix_stop_h_per_month"]["mean"], 1)])
        note = ("Near the base: the vehicle's route sample is in radio line of sight of at least two of the four "
                "beacons, the reading of the registered wording that the analysis chose after the results (Section "
                "5.9). In 2028 the navigation service offers no fix, so the layer set with it equals the "
                "terrain-fix row and is not repeated. Intervals are 95&#8239;% bootstrap intervals over seeds."
                + ("" if "8" in s["errors"] else " The eight-times cells have not finished."))
        return c.tab("Table 9. E50, horizontal position error while driving, by layer set and fleet size: the mean "
                     "over seeds of each run's median and 95th percentile (m), the 95th percentile near the base "
                     "and away from it, the share of driving steps in which the vehicle's own 95&#8239;% bound "
                     "exceeds the 5&nbsp;m budget, and the fleet's time stopped for terrain fixes (h a month).",
                     ["Fleet", "Seeds", "Layer set", "Median (m)", "p95 (m)", "p95 near base (m)",
                      "p95 away (m)", "Bound over 5 m", "Fix stops (h)"], rows, "wide", note)

    def table_margin():
        s = c.e50f(1)
        mults = [m for m in ("1", "4", "8") if m in s["delay"]]
        st = lambda x, nd=2: f"{num(x['mean'], nd)} {c.ci(x['ci'][0], x['ci'][1], nd, unit='')}"
        sg = lambda x, nd=2: f"{num(x['mean'], nd, sign=True)} {c.ci(x['ci'][0], x['ci'][1], nd, unit='')}"
        vio = lambda m, a, b: s["violations"][m][a][b]
        dly = lambda m, k: s["delay"][m][k]
        spec = [("Seeds", lambda m: cnt(dly(m, "perfect")["n"])),
                ("Overlaps a month, no margin: dead reckoning alone", lambda m: st(vio(m, "no_margin", "dr"))),
                ("&nbsp;&nbsp;+ ranging", lambda m: st(vio(m, "no_margin", "dr+ranging"))),
                ("&nbsp;&nbsp;+ terrain fixes", lambda m: st(vio(m, "no_margin", "dr+ranging+fixes"))),
                ("&nbsp;&nbsp;+ navigation service, 2030", lambda m: st(vio(m, "no_margin", "lans@2030"))),
                ("Overlaps a month, dead-reckoning margin", lambda m: st(vio(m, "with_margin", "dr"))),
                ("Overlaps a month, layered margin", lambda m: st(vio(m, "with_margin", "layered"))),
                ("Margin at each end (h): dead reckoning", lambda m: num(dly(m, "margin_dr_margin_h_mean")["mean"], 3)),
                ("Margin at each end (h): layered", lambda m: num(dly(m, "margin_layered_margin_h_mean")["mean"], 3)),
                ("Delay per delivery, perfect position (h)", lambda m: st(dly(m, "perfect"))),
                ("Dead-reckoning margin minus perfect (h)", lambda m: sg(dly(m, "margin_dr_minus_perfect"))),
                ("Layered margin minus perfect (h)", lambda m: sg(dly(m, "margin_layered_minus_perfect"), 3)),
                ("Road waiting (h a month): perfect", lambda m: num(dly(m, "perfect_road_wait_h")["mean"], 1)),
                ("&nbsp;&nbsp;dead-reckoning margin", lambda m: num(dly(m, "margin_dr_road_wait_h")["mean"], 1)),
                ("&nbsp;&nbsp;layered margin", lambda m: num(dly(m, "margin_layered_road_wait_h")["mean"], 1))]
        rows = [[name] + [fn(m) for m in mults] for name, fn in spec]
        note = ("An overlap is a pair of conflicting one-lane reservations of different vehicles whose windows "
                "overlap in true time. Without a margin a back-to-back pair overlaps about half the time by "
                "construction, whatever the size of the position error, so those rows count such pairs and are not a "
                "measure of safety. The delay leaves out the time stopped for terrain fixes (Table 9); with the "
                "stops in the logistics model it is higher (E50b, in the text)."
                + ("" if "8" in mults else " The eight-times cells have not finished."))
        return c.tab("Table 10. E50, true-time overlaps of conflicting reservations with and without the widened "
                     "margin, the size of the margin, and the delay per delivery against perfect position; means "
                     "over seeds with 95&#8239;% bootstrap intervals.",
                     ["Quantity"] + [f"&times;{m} fleet" for m in mults], rows, "", note)

    for name, fn, what in (("E50_errors", table_errors, "Table 9, position error by layer set"),
                           ("E50_margin", table_margin, "Table 10, overlaps and delay with the widened margin")):
        try:
            c.T[name] = fn()
        except Pending as e:
            c.table_pending(c.T, name, f"E50: {what}", e)
    try:
        c.F["E50_layers"] = fig_e50_layers(c)
    except Pending as e:
        c.table_pending(c.F, "E50_layers", "E50: Figure 2, position error by layer set", e)


# ---------------------------------------------------------------------------------------------------------
# E51: clocks and the reservation guard, H11
# ---------------------------------------------------------------------------------------------------------
def add_e51(c):
    V, fill, check, Pending = c.V, c.fill, c.check, c.Pending
    num, pc, cnt, words, NB, PCT = c.num, c.pc, c.cnt, c.words, c.NB, c.PCT
    GUARDS = [("0.01", "conflicts_guard_0.01"), ("0.1", "conflicts_guard_0.1"), ("1", "conflicts_guard_1")]

    def dist(m):
        """A range error in the unit that reads best: mm, m or km, three significant figures."""
        m = float(m)
        if m >= 1000.0:
            km = m / 1000.0
            return f"{num(km, 0 if km >= 100 else 1 if km >= 10 else 2)}{NB}km"
        if m >= 0.01:
            return f"{num(m, 0 if m >= 100 else 1 if m >= 10 else 2 if m >= 1 else 3)}{NB}m"
        return f"{num(m * 1000.0, 2)}{NB}mm"

    def e51():
        if c.e51 is None:
            raise Pending("results/E51_clocks.json (B-91) has not landed")
        return c.e51

    def row(cls, interval, scale="lunar"):
        g = [r for r in e51()["rows"] if r["class"] == cls and r["scale"] == scale and r["interval_s"] == interval]
        if len(g) != 1:
            raise KeyError(f"E51 row {cls} / {scale} / {interval}: {len(g)} rows")
        return g[0]

    def intervals():
        return [i if i is not None else "never" for i in e51()["design"]["intervals_s"]]

    c.e51f, c.e51row, c.e51intervals, c.dist = e51, row, intervals, dist

    def model_sentence():
        k = e51()["constants"]
        cr, cs = k["classes"]["crystal"], k["classes"]["csac"]
        check(cr["y_lo"] == 0.0 and cr["ageing_per_month"] == 0.0, "the crystal's frequency error is uniform from zero, without ageing")
        e = lambda x: f"{num(x / 10 ** math.floor(math.log10(x)), 0)}{NB}&times;{NB}10<sup>{c.MINUS}{abs(math.floor(math.log10(x)))}</sup>"
        return (f"Each vehicle's clock error against the base's time server is followed from its last two-way time "
                f"transfer, which leaves a residual of {num(k['tt_sigma_s'] * 1e9, 0)}{NB}ns (Assumed) and corrects "
                f"the offset but not the frequency. Two oscillator classes are compared: a temperature-compensated "
                f"crystal whose frequency error is drawn uniformly from 0 to {e(cr['y_hi'])}, the range the crystal "
                f"of the LuGRE receiver moved through on the lunar surface (Measured [69]), and a chip-scale atomic "
                f"clock at {e(cs['y_sigma'])} with ageing of {e(cs['ageing_per_month'])} a month (Spec [70]; the "
                f"part is not space-rated). A transfer succeeds only while the vehicle has a radio path to the base "
                f"mast, directly or through other vehicles. Each reservation carries a guard g at both ends, "
                f"{num(k['guard_s'], 1)}{NB}s by default (Assumed), and a conflict caused by clocks alone is a pair "
                f"of conflicting reservations whose clock errors close their stamped gap by more than 2g "
                f"(Proposition 6). Ranging between vehicles is two-way, so the clock offset cancels and only the "
                f"difference of the two clock rates over the {num(k['t_reply_s'] * 1e3, 0)}{NB}ms reply delay "
                f"remains [71].")
    fill("P2-E51-MODEL-SENTENCE", model_sentence, "E51")

    def design_sentence():
        d = e51()["design"]
        iv = [interval_name(i) for i in intervals()]
        gs = sorted(g for g in d["guards_s"] if g > 0)
        check(len(d["seeds"]) == 30 and "fleet x 1" in d["scenario"], "E51 uses 30 seeds at today's fleet")
        return (f"The perfect-position runs of E50 at today's fleet, {cnt(len(d['seeds']))} seeds, with every "
                f"logged reservation stamped by its holder's clock after the run, so the logistics results do not "
                f"change. Oscillator class by resync interval ({', '.join(iv[:-1])} and {iv[-1]}) by guard "
                f"({', '.join(num(g, 2 if g < 0.1 else 1 if g < 1 else 0) for g in gs)}{NB}s and none); the baseline "
                f"is perfect clocks. Three variants were added after the first results and are not pre-registered: "
                f"frequency steering under a daily thermal cycle, a fleet in which half the vehicles count Earth "
                f"seconds [79], and the guard sweep itself.")
    fill("P2-E51-DESIGN-SENTENCE", design_sentence, "E51")

    def safe_until(cls, gkey):
        """The longest resync interval such that it and every shorter one show zero conflicts at this guard."""
        last = None
        for i in intervals():
            if row(cls, i)[gkey] != 0:
                break
            last = i
        return last

    def results_paragraph():
        d = e51()
        iv = intervals()
        pairs = {row("crystal", i)["conflict_pairs_checked"] for i in iv}
        check(len(pairs) == 1, "every crystal row checks the same reservation pairs")
        fail = row("crystal", 600)["sync_fail_share"]
        ng_cr = [row("crystal", i)["conflicts_guard_0"] for i in iv]
        ng_cs = [row("csac", i)["conflicts_guard_0"] for i in iv]
        check(min(ng_cr) > 0 and min(ng_cs) > 0, "without a guard conflicts appear at every resync interval, for both classes")
        until = {g: safe_until("crystal", key) for g, key in GUARDS}
        check(until["0.1"] == 21600, "with the 0.1 s guard the crystal is conflict-free up to a 6 h resync")
        check(all(row("csac", i)[key] == 0 for i in iv for _, key in GUARDS), "the atomic clock causes no conflict with any guard")
        after = [(interval_name(i), row("crystal", i)["conflicts_guard_0.1"]) for i in iv if iv.index(i) > iv.index(21600)]
        cr10, cr1h = row("crystal", 10), row("crystal", 3600)
        cs10, cs1h, csd = row("csac", 10), row("csac", 3600), row("csac", 86400)
        check(cr10["one_way_m_p95"] > 100 * cs10["one_way_m_p95"] and cs10["one_way_m_p95"] > 1e3 * d["design"]["uwb_sigma_m"],
              "one-way ranging: the crystal's added error is far above the atomic clock's, which is far above the radio's noise")
        check(cr10["two_way_single_sided_m_p95"] < d["design"]["uwb_sigma_m"], "two-way ranging stays inside the radio's own noise")

        def guard_words(g):
            u = until[g]
            if u == "never":
                return "left no conflict even for a crystal that was never resynced in the month"
            if u is None:
                return "left conflicts at every interval"
            return f"needed a resync within {interval_name(u)}"
        n_pairs = pairs.pop()
        g = d["constants"]["guard_s"]
        c6 = row("crystal", 21600)
        check(c6["conflicts_guard_0.1"] == 0 and c6["max_abs_clock_s"] > 5 * g and 0.5 * (2 * g) < c6["worst_close_s"] < 2 * g,
              "at the six-hour resync the crystal's clocks are far outside the guard, no pair conflicts, and the worst pair closes more than half of the two guards")
        in_prem = [i for i in iv if row("crystal", i)["max_abs_clock_s"] <= g]
        check(not in_prem, "no crystal cell with the 0.1 s guard meets Proposition 6's premise (every clock within the guard)")
        ub = 1.0 - 0.05 ** (1.0 / n_pairs)
        s = (f"Table 11 gives the rows on the lunar time scale. Over {cnt(len(d['seeds']))} seeds, "
             f"{cnt(n_pairs)} conflicting pairs of reservations lay within an hour of each other and were "
             f"checked, and {pc(fail, 1)} of resync attempts found no radio path. With the "
             f"{num(g, 1)}{NB}s guard the crystal caused no conflict at any resync interval "
             f"from {interval_name(iv[0])} to {interval_name(until['0.1'])}, in any seed; it caused "
             + " and ".join(f"{cnt(n)} with " + ("no resync" if name == "never" else "a daily resync"
                                                  if name == interval_name(86400) else f"a resync every {name}")
                            for name, n in after)
             + f". These zeros are observations and lie outside Proposition 6, whose premise is that every clock "
             f"is within the guard: no crystal cell meets it. At the {interval_name(21600)} resync, clocks on "
             f"vehicles out of radio reach were up to {num(c6['max_abs_clock_s'], 2)}{NB}s off, more than eight "
             f"times the guard, and the worst of the {cnt(n_pairs)} pairs closed {num(c6['worst_close_s'], 3)}{NB}s "
             f"of the {num(2 * g, 1)}{NB}s that the two guards put between the windows, "
             f"{pc(c6['worst_close_s'] / (2 * g), 0)}. No event in {cnt(n_pairs)} pairs leaves a 95{PCT} upper "
             f"bound of {pc(ub, 1)} per pair. With no guard, conflicts appeared at every interval and in both "
             f"classes: {cnt(min(ng_cr))} to "
             f"{cnt(max(ng_cr))} for the crystal and {cnt(min(ng_cs))} to {cnt(max(ng_cs))} for the atomic clock, "
             f"whose largest error in any cell was {num(max(row('csac', i)['max_abs_clock_s'] for i in iv) * 1e3, 1)}{NB}ms. "
             f"That column counts signs and not sizes: with no guard the stamped gap between a waiting vehicle's "
             f"window and the one before it is zero, so a pair counts as soon as its two clocks differ in the "
             f"unfavourable direction by any amount, and it is a property of the count, not a result. "
             f"In the guard sweep a guard of 1{NB}s {guard_words('1')} (largest error "
             f"{num(row('crystal', 'never')['max_abs_clock_s'], 2)}{NB}s), 0.1{NB}s {guard_words('0.1')} and "
             f"0.01{NB}s {guard_words('0.01')}. The crystal's largest error was "
             f"{num(cr10['max_abs_clock_s'], 2)}{NB}s even at a {interval_name(10)} resync, on vehicles out of "
             f"radio reach. Used for one-way ranging against the base clock, the crystal added "
             f"{dist(cr10['one_way_m_p95'])} of range error (95th percentile) at a {interval_name(10)} resync and "
             f"{dist(cr1h['one_way_m_p95'])} at {interval_name(3600)}; the atomic clock added "
             f"{dist(cs10['one_way_m_p95'])} and {dist(cs1h['one_way_m_p95'])}, and {dist(csd['one_way_m_p95'])} "
             f"at {interval_name(86400)}. Two-way ranging between vehicles was off by "
             f"{dist(cr10['two_way_single_sided_m_p95'])} with crystals and {dist(cs10['two_way_single_sided_m_p95'])} "
             f"with atomic clocks at the 95th percentile, with no shared clock.")
        return s
    fill("P2-E51-RESULTS-PARAGRAPH", results_paragraph, "E51")

    def h11_sentence():
        h = e51()["h11"]
        ok = h["intervals_meeting_both"]
        mine = [i for i in intervals() if row("crystal", i)["seeds_with_conflict_guard_0.1"] == 0
                and row("crystal", i)["one_way_m_p95"] > e51()["design"]["uwb_sigma_m"]]
        check(mine == ok and h["supported"] == bool(ok), "H11's verdict follows from the crystal rows")
        s = (f"H11 asks for a resync interval at which the cheaper oscillator causes no reservation conflict while "
             f"its clock error still adds more than the ranging radio's own noise "
             f"({c.m_(e51()['design']['uwb_sigma_m'], 1)}) to one-way ranging [59]: ")
        ns_m = 1e-9 * C_M_S
        check(abs(ns_m - e51()["design"]["uwb_sigma_m"]) < 0.01, "one nanosecond of clock error is the radio's own ranging noise in one-way range")
        if h["supported"]:
            s += (f"the registered rule is met at every interval from {interval_name(ok[0])} to "
                  f"{interval_name(ok[-1])}." if len(ok) > 1 else f"the registered rule is met at {interval_name(ok[0])}.")
            s += (f" We report it as an observation and not as a test passed. Its second condition could not have "
                  f"failed: one nanosecond of clock error is {c.m_(ns_m, 1)} of one-way range, so any crystal exceeds "
                  f"the radio's noise, and the protocol ranges two-way. Its first condition is the zero count above, "
                  f"which lies outside the guarantee.")
        else:
            s += "not supported: no interval in the sweep meets both conditions."
        return s
    fill("P2-E51-H11-SENTENCE", h11_sentence, "E51")

    def variants_sentence():
        if c.e51b is None:
            raise Pending("results/E51b_clocks.json (B-91b) has not landed")
        rows = c.e51b["rows"]

        def rb(part, cls, interval, variant):
            g = [r for r in rows if r["part"] == part and r["class"] == cls and r["interval_s"] == interval
                 and r["variant"] == variant]
            if len(g) != 1:
                raise KeyError(f"E51b row {part} / {cls} / {interval} / {variant}: {len(g)} rows")
            return g[0]
        ivs = c.e51b["design"]["intervals_s"]
        gain = [rb("steering", "crystal", i, "offset")["one_way_m_p95"] / rb("steering", "crystal", i, "steer")["one_way_m_p95"] for i in ivs]
        check(min(gain) > 1.0, "frequency steering lowers the crystal's one-way ranging error at every interval")
        c_off, c_st = rb("steering", "csac", 60, "offset"), rb("steering", "csac", 60, "steer")
        worse = c_st["one_way_m_p95"] > c_off["one_way_m_p95"]
        check(worse, "steering on 1-minute intervals makes the atomic clock's ranging worse")
        check(all(rb("steering", "csac", i, "steer")["one_way_m_p95"] < rb("steering", "csac", i, "offset")["one_way_m_p95"]
                  for i in ivs if i >= 600), "from 10 minutes on steering helps the atomic clock")
        mix = "half Earth seconds, no conversion"
        cor = "lunar for all (corrected)"
        m10, c10 = rb("mixed", "csac", 600, mix), rb("mixed", "csac", 600, cor)
        add = m10["cross_scale_one_way_m_p95"] / c10["cross_scale_one_way_m_p95"] - 1.0
        check(add > 0.05, "the scale mismatch adds visibly to the atomic clocks' ranging error between vehicles")
        same = all(rb("mixed", cls, i, mix)[k] == rb("mixed", cls, i, cor)[k]
                   for cls in ("crystal", "csac") for i in c.e51b["design"]["mixed_intervals_s"] + ["never"]
                   if i is not None for k in ("cross_scale_conflicts_guard_0.01", "cross_scale_conflicts_guard_0.1"))
        check(same, "the mixed time scales cause no reservation conflict beyond those of clock drift")
        return (f"In the variants, steering the frequency from successive transfers cut the crystal's one-way "
                f"ranging error {num(min(gain), 1)} to {num(max(gain), 1)} times, and made the atomic clock's worse "
                f"at {interval_name(60)} intervals ({dist(c_st['one_way_m_p95'])} against "
                f"{dist(c_off['one_way_m_p95'])}) and better from {interval_name(600)} on. With half the fleet "
                f"counting Earth seconds, one-way ranging between atomic-clock vehicles on different scales was "
                f"{pc(add, 0)} worse at a {interval_name(600)} resync than with the 56{NB}&micro;s a day corrected "
                f"[79], and the count of reservation conflicts was the same with and without the correction.")
    fill("P2-E51-VARIANTS-SENTENCE", variants_sentence, "E51b")

    def table_e51():
        d = e51()
        rows = []
        for cls, name in (("crystal", "crystal"), ("csac", "chip-scale atomic")):
            for i in intervals():
                r = row(cls, i)
                rows.append([name, interval_name(i), dist(r["one_way_m_p95"]), dist(r["two_way_single_sided_m_p95"]),
                             f"{num(r['max_abs_clock_s'] * 1e3, 1 if r['max_abs_clock_s'] < 0.1 else 0)}",
                             cnt(r["conflicts_guard_0.01"]), cnt(r["conflicts_guard_0.1"]), cnt(r["conflicts_guard_1"]),
                             cnt(r["conflicts_guard_0"])])
        n = row("crystal", 10)["conflict_pairs_checked"]
        return c.tab(f"Table 11. E51, lunar time scale, {cnt(len(d['seeds']))} seeds at today's fleet: range error "
                     "added by the clock to one-way ranging against the base clock and to two-way ranging between "
                     "vehicles (95th percentiles), the largest clock error in any seed, and reservation conflicts "
                     f"caused by clock error alone, of {cnt(n)} conflicting pairs checked, by guard.",
                     ["Oscillator", "Resync every", "One-way ranging", "Two-way ranging", "Largest error (ms)",
                      "Guard 0.01 s", "Guard 0.1 s", "Guard 1 s", "No guard"], rows, "wide",
                     "Perfect clocks (the baseline) give zero in every column. A transfer is attempted at each "
                     "interval and fails when the vehicle has no radio path to the base mast. The largest error is "
                     "on vehicles out of radio reach; a cell meets the premise of Proposition 6 only where it is no "
                     "larger than the guard. The last column counts signs: with no guard any clock difference in "
                     "the unfavourable direction is a conflict, however small.")
    try:
        c.T["E51"] = table_e51()
    except Pending as e:
        c.table_pending(c.T, "E51", "E51: Table 11, clocks by resync interval and guard", e)


# ---------------------------------------------------------------------------------------------------------
# E54: lost link, message custody and stuck reservations, H14
# ---------------------------------------------------------------------------------------------------------
def add_e54(c):
    fill, check, Pending = c.fill, c.check, c.Pending
    num, pc, cnt, NB = c.num, c.pc, c.cnt, c.NB

    def e54():
        if c.e54 is None:
            raise Pending("results/E54_dtn.json (B-94) has not landed")
        return c.e54

    def row(loss, proto):
        g = [r for r in e54()["rows"] if abs(r["loss"] - loss) < 1e-9 and r["protocol"] == proto]
        if len(g) != 1:
            raise KeyError(f"E54 row loss {loss} / {proto}: {len(g)} rows")
        return g[0]
    c.e54f, c.e54row = e54, row

    def model_sentence():
        p = e54()["parameters"]
        check(p["return_speed_factor"] == 0.5, "a vehicle on the lost-link return drives at half speed")
        src = open(os.path.join(ROOT, "tools", "atc", "run_e54.py"), encoding="utf-8").read()
        check('sz["RESERVE_GRANT"], 60.0)' in src and p["retry_s"] > 60.0,
              "a reservation grant lives 60 s and the retry interval of drop and retry is longer, so a grant is sent once")
        return (f"Drop and retry sends a message end to end, tries again every {num(p['retry_s'], 0)}{NB}s and "
                f"gives up after {cnt(p['max_tries'])} tries or at the message's lifetime (Assumed). Store and "
                f"forward passes custody hop by hop: the holder sends again after {num(p['custody_timer_s'], 0)}{NB}s "
                f"while the link lasts and keeps the message while there is no path. A reservation grant lives "
                f"60{NB}s and a job award for its lease of {num(p['lease_s'] / 3600.0, 0)}{NB}h (Assumed [80]); "
                f"because the retry interval is longer than a grant's lifetime, drop and retry sends each grant "
                f"once. In the replay a vehicle that has heard nothing for {num(p['t_hold_s'], 0)}{NB}s "
                f"retraces its path at half speed to the last point where it had a link. The replay was run with "
                f"the rule as first written, in which the base released a silent holder's reservation at its "
                f"timeout; what it counts, the reservations whose holder was unheard "
                f"{num(p['grace_s'], 0)}{NB}s after the window ended, are under the rule as stated above the "
                f"segments marked unconfirmed.")
    fill("P2-E54-MODEL-SENTENCE", model_sentence, "E54")

    def design_sentence():
        d = e54()
        losses = sorted({r["loss"] for r in d["rows"]})
        check(losses == [0.1, 0.25, 0.4] and len(d["seeds"]) == 30, "E54 runs three loss rates on 30 seeds")
        b0, b1 = d["blackout_days"]
        return (f"A replay of the month's messages over its contact plan, on the {cnt(len(d['seeds']))} seeds of "
                f"E50's perfect-position runs at today's fleet: the vehicles and the base mast linked by line of "
                f"sight on the terrain within radio range, step by step along the recorded trajectories, with a "
                f"{num(b1 - b0, 0)}-day Earth blackout imposed. Three ways of carrying messages (drop and retry; "
                f"store and forward with custody; the same with the lost-link rule) at a loss per hop of "
                f"{', '.join(num(x, 2) for x in losses[:-1])} and {num(losses[-1], 2)}. The logistics model is not "
                f"run again, so a returning vehicle's detour does not change later dispatch (Section 7).")
    fill("P2-E54-DESIGN-SENTENCE", design_sentence, "E54")

    def results_paragraph():
        d = e54()
        h = d["h14"]
        dr, sf, ll = row(0.25, "drop_retry"), row(0.25, "sf"), row(0.25, "sf_ll")
        check(dr["grant_lost_share"] > 100 * sf["grant_lost_share"], "custody cuts the loss of reservation grants by more than a hundred times at loss 0.25")
        check(ll["stuck_reservations"] == 0 and h["stuck_reservations_sf_ll"] == 0, "no reservation is stuck under the lost-link rule")
        check(dr["stuck_reservations"] == sf["stuck_reservations"] == h["stuck_reservations_drop_retry"] > 0,
              "without the lost-link rule the stuck reservations do not depend on how messages are carried")
        src = open(os.path.join(ROOT, "tools", "atc", "run_e54.py"), encoding="utf-8").read()
        check('0 if proto == "sf_ll" else n_st' in src,
              "the zero of stuck reservations under the rule is set by construction in tools/atc/run_e54.py, not measured")
        sd = d.get("stuck_definition", "")
        check("UNCONFIRMED release" in sd and "every vehicle leaves on schedule" in sd,
              "E54's stuck reservations are unconfirmed releases; in the replay every vehicle leaves on schedule (the file's stuck_definition)")
        dj, lj, df = h["lost_jobs_drop_retry_per_seed"], h["lost_jobs_sf_ll_per_seed"], h["difference_sf_ll_minus_drop_retry"]
        check(h["supported"] == (df["ci"][1] < 0 and h["stuck_reservations_sf_ll"] == 0), "H14's verdict follows from its rule")
        n_res = d["reservations_per_seed"] * len(d["seeds"])
        check(abs(n_res - round(n_res)) < 1e-6 and dr["stuck_reservations"] <= n_res, "the stuck count is a part of the month's logged reservations")
        d10, d40 = row(0.1, "drop_retry"), row(0.4, "drop_retry")
        check(d10["grant_lost_share"] < dr["grant_lost_share"] < d40["grant_lost_share"], "grant loss under drop and retry rises with the loss per hop")
        first = df["ci"][1] < 0
        check(first, "custody with the lost-link rule lost fewer jobs than drop and retry, by an interval that excludes zero")
        # the grants lost by drop and retry are the per-hop loss (the referee's M7): a property of the assumed timing
        for rr_ in (d10, dr, d40):
            check(abs(rr_["grant_lost_share"] - rr_["loss"]) < 0.01 and rr_["grant_delay_mean_s"] < 1.0,
                  f"at a loss of {rr_['loss']} drop and retry loses that share of the grants: each grant is sent once")
        ls = d["link_shares"]
        fact = c.e54facts = SimpleNamespace(
            returns=d["lost_link_returns_per_seed"], jobs=d["jobs_per_seed"], linked=ls["linked_share_driving_time"],
            saved_h=d["lost_link_isolation_h_saved_per_seed"], unconf=dr["stuck_reservations"], n_res=n_res,
            unconf_h=dr["stuck_hours"], three=dr["loss"] ** 3, lost=dr["grant_lost_share"])
        check(0.3 < fact.returns / fact.jobs < 0.6 and 0.4 < fact.linked < 0.7,
              "in the replay a vehicle turns back about once for every two or three jobs, and vehicles have a radio path for about half of their driving time")
        return (f"Over the {cnt(len(d['seeds']))} seeds the month held {cnt(dr['grant_n'])} reservation grants and "
                f"{cnt(dr['award_n'])} job awards. At a loss of 0.25 per hop, drop and retry lost "
                f"{cnt(dr['grant_lost'])} grants, {pc(dr['grant_lost_share'], 0)}; with custody "
                f"{cnt(sf['grant_lost'])} were lost, {pc(sf['grant_lost_share'], 2)}. A lost grant is a vehicle "
                f"stopped before a one-lane entry, because an unconfirmed reservation is never assumed. At losses "
                f"of 0.10 and 0.40 drop and retry lost {pc(d10['grant_lost_share'], 0)} and "
                f"{pc(d40['grant_lost_share'], 0)}. These shares are the per-hop loss itself and are a calculation "
                f"on two assumed inputs, not a measurement: the retry interval ({num(d['parameters']['retry_s'], 0)}{NB}s) "
                f"is longer than a grant's lifetime (60{NB}s), so each grant was sent once, with a mean delay of "
                f"{num(dr['grant_delay_mean_s'], 2)}{NB}s. Three tries inside the lifetime would by the same "
                f"arithmetic lose 0.25<sup>3</sup>, {pc(fact.three, 1)}; that baseline was not run, so the replay "
                f"does not show that custody is needed, only that a grant sent once is lost as often as a hop "
                f"fails. Lost jobs, awards that expired before they arrived, were "
                f"{num(dj['mean'], 2)} a seed {c.ci(*dj['ci'], 2, unit='')} with drop and retry and "
                f"{'none' if lj['mean'] == 0 else num(lj['mean'], 2)} with custody and the lost-link rule, a paired difference of "
                f"{num(df['mean'], 2, sign=True)} {c.ci(*df['ci'], 2, unit='')}. H14 [59] has two clauses. The first, "
                f"fewer lost jobs by an interval that excludes zero, is {'supported' if first else 'not supported'}. "
                f"The second, no reservation left stuck past its timeout, is not testable as written and is "
                f"withdrawn as a result [59]: the zero followed from the rule's definition, and the rule as first "
                f"written released a silent vehicle's reservation, which is unsafe when the vehicle is silent "
                f"because it has failed inside the segment. Under the rule as it now stands (Section 3.11) the "
                f"reservation is not released and the segment is marked unconfirmed. What the replay gives is how "
                f"many those are: {cnt(dr['stuck_reservations'])} of the "
                f"{cnt(n_res)} reservations of the month had a holder with no radio path to the base "
                f"{num(d['parameters']['grace_s'], 0)}{NB}s after the window ended, {cnt(dr['stuck_hours'])}{NB}h "
                f"of unconfirmed segment in all, although in the replay every one of those vehicles had left its "
                f"segment on schedule. An unconfirmed segment is the usual case, then, and the delay that entering "
                f"it at caution speed costs has not been priced. Nor has the rest of the ladder. Along the month's "
                f"contact plan vehicles had a radio path to the base mast in {pc(fact.linked, 1)} of their driving "
                f"time; the replay holds {num(fact.returns, 0)} lost-link returns a seed against "
                f"{num(fact.jobs, 0)} jobs, and credits {cnt(fact.saved_h)}{NB}h a seed as spent waiting, linked, "
                f"at the return point; but it applies the return to the contact plan only, and the recorded job "
                f"still completes. No logistics run of this paper contains the ladder (Section 7). The "
                f"base's knowledge of a vehicle was {num(ll['aoi_mean_s'], 0)}{NB}s old on average with the rule "
                f"(worst vehicle {num(ll['aoi_worst_vehicle_s'], 0)}{NB}s) and "
                f"{num(dr['aoi_mean_s'] / 60.0, 0)}{NB}min without it (worst {num(dr['aoi_worst_vehicle_s'] / 3600.0, 0)}{NB}h), "
                f"in a replay in which a returning vehicle is given a direct link.")
    fill("P2-E54-RESULTS-PARAGRAPH", results_paragraph, "E54")


# ---------------------------------------------------------------------------------------------------------
# E56: integrity of position reports, H15 (E55 pending)
# ---------------------------------------------------------------------------------------------------------
def add_e56(c):
    fill, check, Pending = c.fill, c.check, c.Pending
    num, pc, cnt, words, NB, PCT = c.num, c.pc, c.cnt, c.words, c.NB, c.PCT

    def e56():
        if c.e56 is None:
            raise Pending("results/E56_integrity.json (B-96) has not landed")
        if not c.e56.get("test_evaluated") or c.e56.get("PROVISIONAL"):
            raise Pending("E56's test set has not been scored")
        return c.e56

    def ev(st, det, fault, rate="day"):
        return e56()[st][det][rate]["events"][fault]

    def rec(st, det, fault, rate="day"):
        return ev(st, det, fault, rate)["recall"]["mean"]

    def fa(st, det, rate="day"):
        return e56()[st][det][rate]["fa_per_pair_day"]["mean"]

    def h15(base, fault, st="test"):
        return e56()[st]["h15_net_against"][base][fault]
    c.e56f, c.e56rec, c.e56fa, c.e56h15, c.e56ev = e56, rec, fa, h15, ev
    _t56 = {}

    def cls(st, rc, det, fault, col="recall", rate="1/pair-day"):
        """One cell of results/table_E56.csv, which holds what the JSON does not: the rows by ranging class (uwb: the
        short-range radio within 100 m; long: beyond it). The class 'all' is checked against the JSON."""
        import pandas as pd
        if "t" not in _t56:
            path = os.path.join(RES, "table_E56.csv")
            if not os.path.exists(path):
                raise Pending("results/table_E56.csv is missing")
            _t56["t"] = pd.read_csv(path)
            t = _t56["t"]
            a = t[(t["set"] == "ood") & (t["range_class"] == "all") & (t["detector"] == "cusum") & (t["rate"] == "1/pair-day") & (t["fault"] == "jump")]
            check(len(a) == 1 and abs(float(a.iloc[0]["recall"]) - rec("ood", "cusum", "jump")) < 5e-4
                  and abs(float(a.iloc[0]["fa_per_pair_day"]) - fa("ood", "cusum")) < 5e-3, "table_E56.csv and E56_integrity.json hold the same cell")
        t = _t56["t"]
        g = t[(t["set"] == st) & (t["range_class"] == rc) & (t["detector"] == det) & (t["rate"] == rate) & (t["fault"] == fault)]
        if len(g) != 1:
            raise KeyError(f"table_E56 row {st} / {rc} / {det} / {fault}: {len(g)} rows")
        return float(g.iloc[0][col])
    c.e56cls = cls
    fill("P2-E56-PAIR-DAYS", lambda: num(e56()["test"]["fault_free_pair_days_represented"], 0), "E56")
    s_ = lambda x, nd=0: f"{num(x, nd)}{NB}s"
    civ = lambda v, nd=1, key="ci95": c.ci(v[key][0], v[key][1], nd, unit="")

    def data_sentence():
        from lunarsim.nn import faults as FL
        d = e56()
        ds, F = d["dataset"], FL.FAULTS
        check(d["simulated_data"] is True, "E56's data are simulated")
        seeds = [set(ds[k]["seeds"]) for k in ("train", "val", "test", "ood")]
        check(all(not (a & b) for i, a in enumerate(seeds) for b in seeds[i + 1:]), "no simulator seed is in two splits")
        pairs = [set(ds[k]["pair_abs_id_difference"]) for k in ("train", "val", "test")]
        check(all(not (a & b) for i, a in enumerate(pairs) for b in pairs[i + 1:]), "no vehicle pair is in two of train, validation and test")
        check(ds["ood"]["pair_abs_id_difference"] == ds["test"]["pair_abs_id_difference"], "the out-of-distribution set uses the test pairs")
        n_months = len(set().union(*seeds))
        rng = lambda k: f"{min(ds[k]['seeds'])} to {max(ds[k]['seeds'])}"
        o = d["ood_setting"]
        pr = d["params"]
        check(sorted(map(tuple, (ds[k]["pair_abs_id_difference"] for k in ("train", "val", "test")))) == [(1, 4, 5), (2, 6), (3, 7)],
              "pairs are assigned to the three sets by the difference of the two vehicle numbers, so every vehicle is in all three")
        return (f"A's own position estimate in this experiment is simpler than the filter of Section 3.9: its error "
                f"grows by {pc(pr['dr_error_frac'], 0)} of the distance driven and collapses to "
                f"{num(pr['fix_sigma_m'], 1)}{NB}m at a terrain fix, taken at every stop and about every "
                f"{num(pr['fix_spacing_m'], 0)}{NB}m of driving, with no filter and no terrain; the range is good to "
                f"{num(pr['uwb_range_noise_m'], 1)}{NB}m within {num(pr['uwb_range_max_m'], 0)}{NB}m (the short-range "
                f"class) and to {num(pr['long_range_noise_m'], 0)}{NB}m beyond (the long-range class). "
                f"Five fault types are put into B's reports (sizes Assumed): a jump of {num(F['jump'].lo, 0)} to "
                f"{num(F['jump'].hi, 0)}{NB}m, a slow drift of {num(F['drift'].lo, 2)} to {num(F['drift'].hi, 1)}{NB}m/s, "
                f"a frozen report, a frame error of {num(F['frame'].lo, 0)} to {num(F['frame'].hi, 0)}{NB}m and "
                f"report noise inflated {num(F['noise'].lo, 0)} to {num(F['noise'].hi, 0)} times. Fault-free data "
                f"keep the honest disturbances: stops and starts, navigation error that grows and then collapses "
                f"at a fix, dropouts beyond radio range, the change of ranging class at "
                f"{num(d['params']['uwb_range_max_m'], 0)}{NB}m and bursts of blocked-path bias. True motion comes "
                f"from {cnt(n_months)} simulated months of the logistics model, one per seed, rebuilt at 1{NB}Hz. "
                f"The data are split by month and by vehicle pair, so that no month and no pair is in two of the "
                f"training, validation and test sets; every vehicle is in all three, because a pair is assigned by "
                f"the difference of its two vehicle numbers: months {rng('train')} with {cnt(ds['train']['ordered_pairs'])} "
                f"ordered pairs for training ({cnt(ds['train']['fault_streams'])} fault streams), months "
                f"{rng('val')} with {cnt(ds['val']['ordered_pairs'])} pairs for validation "
                f"({cnt(ds['val']['fault_streams'])} fault streams and {cnt(ds['val']['fault_free_natural_blocks'])} "
                f"fault-free hours) and months {rng('test')} with {cnt(ds['test']['ordered_pairs'])} pairs for the "
                f"test ({cnt(ds['test']['fault_streams'])} fault streams, "
                f"{cnt(ds['test']['fault_streams_by_type']['drift'])} per type, and "
                f"{cnt(ds['test']['fault_free_natural_blocks'])} fault-free hours). An out-of-distribution set, "
                f"months {rng('ood')} on the test pairs, has ranging noise multiplied by "
                f"{num(o['range_noise_mult'], 0)} and dead reckoning drifting {pc(o['dr_error_frac_true'], 0)} while "
                f"A's filter still assumes the nominal values, with jumps of {num(F['jump'].ood_lo, 0)} to "
                f"{num(F['jump'].ood_hi, 0)}{NB}m and drifts of {num(F['drift'].ood_lo, 3)} to "
                f"{num(F['drift'].ood_hi, 2)}{NB}m/s, below the training range. It is one shift, chosen by us, and "
                f"not a sample of the ways a sensor model can be wrong.")
    fill("P2-E56-DATA-SENTENCE", data_sentence, "E56")

    def search_rows():
        import csv
        with open(os.path.join(RES, "E56_runs.csv"), encoding="utf-8") as f:
            return [r for r in csv.DictReader(f) if r["stage"] == "search"]

    def model_sentence():
        d = e56()
        m, cf, b = d["model"], d["config"], d["baselines"]
        layers = [a for a in m["architecture"] if a.get("kernel", 1) > 1]
        check(len(layers) == len(cf["dilations"]) and m["n_params"] == sum(a["params"] for a in m["architecture"]),
              "the parameter count is the sum over the listed layers")
        sr = search_rows()
        chosen = [r for r in sr if int(r["n_params"]) == m["n_params"] and int(r["epochs"]) == cf["epochs"]
                  and abs(float(json.loads(r["config"])["lr"]) - cf["lr"]) < 1e-12][0]
        wide = max(sr, key=lambda r: int(r["n_params"]))
        gain = float(wide["val_recall_day_macro"]) - float(chosen["val_recall_day_macro"])
        check(0 <= gain < 0.005, "the wider network's validation gain is under the 0.005 margin of the search rule")
        t = d["timing"]["torch_1thread_ms"]
        return (f"The classical test is the squared range innovation divided by its predicted variance, compared "
                f"with a chi-square threshold (Proposition 5), per step and as a mean over {cnt(b['chi2_window_W'])}{NB}s. "
                f"The other baselines are a two-sided CUSUM on the innovation and a logistic regression on "
                f"{cnt(b['logreg_features'])} hand-made statistics of the last {cnt(b['logreg_windows'][0])} and "
                f"{cnt(b['logreg_windows'][1])}{NB}s. The learned detector is a causal convolutional network: "
                f"{words(len(layers))} dilated one-dimensional convolutions of {cnt(cf['channels'])} channels over "
                f"the last {cnt(m['window_s'])}{NB}s of {words(layers[0]['in'])} inputs that A can know, "
                f"{cnt(m['n_params'])} parameters in all, {num(m['float32_bytes'] / 1000.0, 0)}{NB}kB as 32-bit "
                f"floats. It is small for three reasons. It has to run beside the safety program on a flight "
                f"computer: one window takes {num(t['median'], 2)}{NB}ms on one thread of a desktop processor, and a "
                f"radiation-tolerant processor is slower by a factor we did not measure. A network of this size "
                f"can be shipped as a table of weights and replayed exactly. And the search rule, fixed before the "
                f"first training run, kept the smallest configuration within 0.005 of the best validation recall: "
                f"the wider network tried, {cnt(int(wide['n_params']))} parameters, gained "
                f"{num(gain, 4)}.")
    fill("P2-E56-MODEL-SENTENCE", model_sentence, "E56")

    def design_sentence():
        d = e56()
        v = d["validation_fa_per_pair_day_at_threshold"]
        check(all(v[k]["day"] <= 1.0 + 1e-9 for k, _ in DETECTORS), "every validation threshold keeps false alarms at or below one per pair-day")
        check("60 s bin" in d["false_alarm_definition"], "a false alarm is a 60 s bin of fault-free stream")
        return (f"Five detectors on the same streams: the per-step and windowed chi-square tests, the CUSUM, the "
                f"logistic regression and the network ({words(len(d['seeds']))} training seeds). A pair-day is one "
                f"ordered pair of vehicles, observer and reporter, followed for one day. For each detector the "
                f"threshold is the lowest that keeps false alarms at or below one per pair-day on the validation "
                f"fault-free data, a false alarm being a 60{NB}s bin of fault-free stream with at least one alarm; "
                f"a second threshold is set for one per pair-hour. Nothing is set on the test data, which were "
                f"scored once. A fault is found if an alarm falls inside it, and its delay is the first alarm "
                f"minus the onset.")
    fill("P2-E56-DESIGN-SENTENCE", design_sentence, "E56")

    def results_paragraph():
        d = e56()
        n = d["dataset"]["test"]["fault_streams_by_type"]["drift"]
        fas = {k: fa("test", k) for k, _ in DETECTORS}
        check(fas["net"] == min(fas.values()), "the network's realised false-alarm rate on the test set is the lowest of the five")
        alls = {k: rec("test", k, "all") for k, _ in DETECTORS}
        check(alls["net"] > alls["logreg"] > alls["cusum"] > max(alls["chi2_step"], alls["chi2_window"]),
              "overall recall on the test set: network, then regression, then CUSUM, then the chi-square tests")
        frame = [rec("test", k, "frame") for k, _ in DETECTORS]
        drift = {k: rec("test", k, "drift") for k, _ in DETECTORS}
        best = max(drift, key=drift.get)
        check(max(drift.values()) < 0.7, "no detector finds seven in ten slow drifts")
        lr = h15("logreg", "jump")["recall_diff"]
        check(lr["ci95"][1] < 0, "the network finds fewer jumps than the logistic regression")
        hr = lambda det, fault: rec("test", det, fault, "hour")
        check(hr("logreg", "all") >= hr("net", "all") and hr("logreg", "drift") >= hr("net", "drift"),
              "at one false alarm per pair-hour the regression is level with or ahead of the network")
        ld = h15("logreg", "drift")["delay_median_diff_s"]
        cd = h15("cusum", "drift")["delay_median_diff_s"]
        check(ld["ci95"][0] < 0 < ld["ci95"][1] and cd["ci95"][0] < 0 < cd["ci95"][1],
              "on slow drifts the network is not earlier than the regression or the CUSUM")
        fci = lambda k: civ(d["test"][k]["day"]["fa_per_pair_day"], 2)
        tds = d["dataset"]["test"]
        blocks, pop = tds["natural_blocks_by_stratum"], tds["natural_population_blocks"]
        big = max(pop, key=pop.get)
        one_bin = pop[big] / sum(pop.values()) / blocks[big] * 24.0     # one alarm-minute in the heaviest stratum
        check(sum(blocks.values()) == tds["fault_free_natural_blocks"] and 0.05 < one_bin < 0.2,
              "one alarm-minute in the heaviest stratum of the test fault-free data is about a tenth of a false alarm per pair-day")
        return (f"Table 12 gives recall and the median detection delay per fault type on the test set, "
                f"{cnt(n)} faults per type, at the thresholds set on validation data for one false alarm per "
                f"pair-day. The realised rates on the test set were {num(fas['net'], 2)} per "
                f"pair-day for the network {fci('net')}, "
                f"{num(fas['chi2_step'], 2)} {fci('chi2_step')} for the per-step chi-square, {num(fas['logreg'], 2)} "
                f"{fci('logreg')} for the regression, {num(fas['chi2_window'], 2)} {fci('chi2_window')} for the "
                f"windowed chi-square and {num(fas['cusum'], 2)} {fci('cusum')} for the CUSUM. The intervals are wide "
                f"because the rates rest on few alarms: the fault-free test data are "
                f"{cnt(tds['fault_free_natural_blocks'])} one-hour blocks drawn from four strata and weighted back to "
                f"{num(d['test']['fault_free_pair_days_represented'], 0)} pair-days, and one alarm-minute in the "
                f"heaviest stratum ({pc(pop[big] / sum(pop.values()), 0)} of natural time, {cnt(blocks[big])} blocks) "
                f"is {num(one_bin, 2)} per pair-day. The recalls below are therefore at one nominal rate and not at "
                f"exactly equal realised rates. Over all faults the network found {pc(alls['net'], 0)}, the regression "
                f"{pc(alls['logreg'], 0)}, the CUSUM {pc(alls['cusum'], 0)} and the two chi-square tests "
                f"{pc(alls['chi2_step'], 0)} and {pc(alls['chi2_window'], 0)}. Every detector found frame errors "
                f"({pc(min(frame), 1)} or more). The network found {pc(rec('test', 'net', 'noise'), 1)} of the "
                f"noise-inflation faults against the per-step chi-square's {pc(rec('test', 'chi2_step', 'noise'), 1)}, "
                f"and {pc(rec('test', 'net', 'jump'), 1)} of jumps against {pc(rec('test', 'chi2_step', 'jump'), 1)}. "
                f"Slow drifts were the hard type: the best recall was {pc(drift[best], 0)} (the "
                f"{PROSE[best]}), so every detector missed at "
                f"least {pc(1 - drift[best], 0)} of them. The network did not beat the logistic regression "
                f"everywhere. On jumps it found {pc(rec('test', 'net', 'jump'), 1)} against "
                f"{pc(rec('test', 'logreg', 'jump'), 1)} (difference {num(lr['value'], 3, sign=True)} "
                f"{civ(lr, 3)}). On slow drifts its median delay was {s_(ev('test', 'net', 'drift')['delay_median_s']['mean'])} "
                f"against the regression's {s_(ev('test', 'logreg', 'drift')['delay_median_s']['mean'])} and the "
                f"CUSUM's {s_(ev('test', 'cusum', 'drift')['delay_median_s']['mean'])}, differences whose "
                f"intervals include zero. At the looser rate of one false alarm per pair-hour the regression found "
                f"{pc(hr('logreg', 'all'), 0)} of all faults and {pc(hr('logreg', 'drift'), 0)} of drifts, the "
                f"network {pc(hr('net', 'all'), 0)} and {pc(hr('net', 'drift'), 0)}.")
    fill("P2-E56-RESULTS-PARAGRAPH", results_paragraph, "E56")
    add_e56_h15(c)


def add_e56_h15(c):
    fill, check, Pending = c.fill, c.check, c.Pending
    num, pc, cnt, NB, PCT = c.num, c.pc, c.cnt, c.NB, c.PCT
    e56, rec, fa, h15, ev = c.e56f, c.e56rec, c.e56fa, c.e56h15, c.e56ev
    s_ = lambda x, nd=0: f"{num(x, nd)}{NB}s"
    civ = lambda v, nd=1, key="ci95": c.ci(v[key][0], v[key][1], nd, unit="")

    def h15_paragraph():
        d = e56()
        # (a) slow drifts: the network's median delay shorter than the per-step chi-square's, CI excludes zero
        a = h15("chi2_step", "drift")
        da = a["delay_median_diff_s"]
        held_a = da["ci95"][1] < 0
        lower_fa = fa("test", "net") < fa("test", "chi2_step")
        pdf = a["paired_diff_s"]
        check(pdf["ci95"][1] < 0, "on the slow drifts both detectors found, the network is also the earlier")
        out = (f"H15 is four tests at one false alarm per pair-day [59]. (a) On slow drifts the network's median "
               f"detection delay is shorter than the per-step chi-square test's: "
               f"{'held' if held_a else 'failed'}. The delays were {s_(a['delay_median_s']['net'])} and "
               f"{s_(a['delay_median_s']['base'])}, a difference of {s_(da['value'], 1)} {civ(da, 1)}"
               + (f", at the lower realised false-alarm rate ({num(fa('test', 'net'), 2)} against "
                  f"{num(fa('test', 'chi2_step'), 2)} per pair-day)" if lower_fa else "")
               + f"; recall was {pc(a['recall']['net'], 1)} against {pc(a['recall']['base'], 1)}. Each median is "
               f"over the faults that detector found; on the faults both found the paired difference was "
               f"{s_(pdf['value'], 1)} {civ(pdf, 1)}. ")
        # (b) jumps: within one second (TOST margin 1 s, 90 % interval)
        b = h15("chi2_step", "jump")
        db, rb = b["delay_median_diff_s"], b["recall_diff"]
        within = -1.0 < db["ci90"][0] and db["ci90"][1] < 1.0
        more = rb["ci95"][0] > 0
        if within:
            out += (f"(b) On jumps the two are within one second: held (difference {s_(db['value'], 1)}, 90{PCT} "
                    f"interval {civ(db, 1, 'ci90')}). ")
        else:
            check(db["value"] > 0 and more, "H15 (b) failed in both directions: the network is later and finds more jumps")
            out += (f"(b) On jumps the two are within one second: failed, in both directions. The network was "
                    f"{s_(db['value'], 1)} later (90{PCT} interval {civ(db, 1, 'ci90')}, which reaches past the "
                    f"1{NB}s margin), and it found more jumps, {pc(b['recall']['net'], 0)} against "
                    f"{pc(b['recall']['base'], 0)} ({num(rb['value'], 2, sign=True)} {civ(rb, 2)}). The registered "
                    f"expectation, no better on jumps, was wrong. ")
        # (c) CUSUM, exploratory
        cd, cr = h15("cusum", "drift"), h15("cusum", "jump")
        dd = cd["delay_median_diff_s"]
        nodiff = dd["ci95"][0] < 0 < dd["ci95"][1]
        out += (f"(c) Against the CUSUM, with no predicted direction: on slow drifts the delay differed by "
                f"{s_(dd['value'], 1)} {civ(dd, 1)}, {'no difference' if nodiff else 'a difference'}, and recall by "
                f"{num(cd['recall_diff']['value'], 3, sign=True)} {civ(cd['recall_diff'], 3)}; on jumps recall "
                f"differed by {num(cr['recall_diff']['value'], 2, sign=True)}. The CUSUM's realised false-alarm "
                f"rate was {num(fa('test', 'cusum'), 1)} per pair-day. ")
        # (d) out of distribution
        nj, nd_ = rec("ood", "net", "jump"), rec("ood", "net", "drift")
        cj, cd_ = rec("ood", "cusum", "jump"), rec("ood", "cusum", "drift")
        below = nj < cj and nd_ < cd_
        inno = [fa("ood", k) for k in ("chi2_step", "chi2_window", "cusum")]
        check(all(fa("ood", k) > 5 * max(1.0, fa("test", k)) for k, _ in DETECTORS),
              "out of distribution no detector keeps its false-alarm rate")
        check(fa("ood", "net") < fa("ood", "logreg") < min(inno), "out of distribution the network's false-alarm rate is the lowest and the innovation tests' the highest")
        rc = lambda det, f: rec("ood_recalibrated", det, f)
        small = [rc(k, f) for k, _ in DETECTORS for f in ("jump", "drift")]
        check(max(small) < 0.05, "with thresholds reset no detector finds the small jumps and slow drifts")
        fa_rc = [fa("ood_recalibrated", k) for k, _ in DETECTORS]
        kept = [rec("ood", "net", f) for f in ("frozen", "frame", "noise")]
        check(min(kept) > 0.9, "out of distribution the network keeps frozen, frame and noise faults")
        cls = c.e56cls
        cu_l, cu_u = cls("ood", "long", "cusum", "jump", "fa_per_pair_day"), cls("ood", "uwb", "cusum", "jump", "fa_per_pair_day")
        ne_u = cls("ood", "uwb", "net", "jump", "fa_per_pair_day")
        check(cu_l / MIN_DAY > 0.5 and cls("ood", "long", "chi2_step", "jump", "fa_per_pair_day") / MIN_DAY > 0.25,
              "out of distribution the CUSUM and the per-step test alarm in a large share of fault-free minutes in the long-range class")
        check(cls("ood", "long", "cusum", "jump") > 0.9 and cls("ood", "uwb", "cusum", "jump") < 0.3,
              "the CUSUM's out-of-distribution recall on small jumps is high only in the class where it alarms most of the time")
        check(cls("ood", "long", "cusum", "jump", "delay_median_s") > 10 and ev("test", "cusum", "jump")["delay_median_s"]["mean"] < 1,
              "the CUSUM's median delay on jumps is zero on the test set and many seconds in the long-range class out of distribution")
        check(abs(cls("ood", "uwb", "net", "jump") - cls("ood", "uwb", "cusum", "jump")) < 0.05 and ne_u < cu_u / 4,
              "in the short-range class the network finds as many small jumps as the CUSUM, at a fraction of its false alarms")
        ratio = {k: fa("ood", k) / fa("test", k) for k, _ in DETECTORS}
        check(ratio["chi2_step"] > 10 * ratio["net"], "out of distribution the per-step chi-square test loses more of its calibration than the network")
        out += (f"(d) Out of distribution the network's recall may fall below the CUSUM's: by the numbers "
                f"{'it did' if below else 'it did not'}, and the comparison means little. At the deployed thresholds "
                f"the network found {pc(nj, 1)} of the small jumps and {pc(nd_, 1)} of the slow drifts, the CUSUM "
                f"{pc(cj, 1)} and {pc(cd_, 1)}. These recalls are not at one false-alarm rate, because no detector "
                f"kept its rate: the network gave {num(fa('ood', 'net'), 1)} false alarms per pair-day, "
                f"{num(ratio['net'], 0)} times its test rate, the regression "
                f"{num(fa('ood', 'logreg'), 1)}, and the three innovation tests {num(min(inno), 0)} to "
                f"{num(max(inno), 0)}; the per-step chi-square test's rate rose {cnt(round(ratio['chi2_step'], -2))} "
                f"times. A false alarm is a minute with an alarm, so the CUSUM's {cnt(cu_l)} per pair-day in the "
                f"long-range class is {pc(cu_l / MIN_DAY, 0)} of all fault-free minutes, and a detector that alarms "
                f"that often meets most faults by coincidence: there it &ldquo;found&rdquo; "
                f"{pc(cls('ood', 'long', 'cusum', 'jump'), 0)} of the small jumps with a median delay of "
                f"{s_(cls('ood', 'long', 'cusum', 'jump', 'delay_median_s'))}, against "
                f"{s_(ev('test', 'cusum', 'jump')['delay_median_s']['mean'])} on the test set. In the short-range "
                f"class, where it gave {num(cu_u, 0)} false alarms per pair-day, it found "
                f"{pc(cls('ood', 'uwb', 'cusum', 'jump'), 0)} of the small jumps and "
                f"{pc(cls('ood', 'uwb', 'cusum', 'drift'), 0)} of the drifts; the network found "
                f"{pc(cls('ood', 'uwb', 'net', 'jump'), 0)} and {pc(cls('ood', 'uwb', 'net', 'drift'), 0)} at "
                f"{num(ne_u, 1)} (Table 12, by ranging class). The detections of the innovation tests out of "
                f"distribution cannot be told from their false alarms. With thresholds reset on half of the "
                f"out-of-distribution fault-free data "
                f"(realised rates {num(min(fa_rc), 1)} to {num(max(fa_rc), 1)} per pair-day on the other half), "
                f"no detector found these two fault types ({pc(min(small), 0)} to {pc(max(small), 0)}), so nothing "
                f"separates the detectors there. The "
                f"network kept the frozen, frame and noise faults ({', '.join(pc(x, 0) for x in kept)} at the "
                f"deployed thresholds).")
        return out
    fill("P2-E56-H15-PARAGRAPH", h15_paragraph, "E56")

    def table_e56():
        d = e56()
        rows = []
        sets = (("test", "Test"), ("ood", "Out of distribution, deployed thresholds"),
                ("ood_recalibrated", "Out of distribution, thresholds reset"))
        for st, label in sets:
            for det, name in DETECTORS:
                cells = [label, name, num(fa(st, det), 2 if fa(st, det) < 10 else 0)]
                for f in FAULTS + ["all"]:
                    e = ev(st, det, f)
                    cells.append(f"{num(e['recall']['mean'], 2)} / {num(e['delay_median_s']['mean'], 0)}")
                rows.append(cells)
            if c.e55 is not None and st in c.e55["integrity"]["sets"]:
                e5 = c.e55["integrity"]["sets"][st]["3of5@0.001"]
                rows.append([label, "protocol rule as written: 3 of 5 at &gamma; = 10.83 (E55)",
                             num(e5["fa_per_pair_day"], 2 if e5["fa_per_pair_day"] < 10 else 0)]
                            + [f"{num(e5['per_type'][f]['recall'], 2)} / {num(e5['per_type'][f]['median_delay_s'], 0)}"
                               for f in FAULTS + ["all"]])
        for rc, label in (("uwb", "Out of distribution, deployed thresholds, short-range class"),
                          ("long", "Out of distribution, deployed thresholds, long-range class")):
            for det, name in DETECTORS:
                f_ = c.e56cls("ood", rc, det, "jump", "fa_per_pair_day")
                rows.append([label, name, num(f_, 2 if f_ < 10 else 0)]
                            + [f"{num(c.e56cls('ood', rc, det, f), 2)} / {num(c.e56cls('ood', rc, det, f, 'delay_median_s'), 0)}"
                               for f in FAULTS + ["all"]])
        n = d["dataset"]["test"]["fault_streams_by_type"]["drift"]
        return c.tab("Table 12. E56, event-level recall and median detection delay (s) of the faults found, per "
                     f"fault type ({cnt(n)} faults per type in each set), with the realised false alarms per "
                     "pair-day. Thresholds are those set on validation data for one false alarm per pair-day, "
                     "except in the third block, where they are reset on half of the out-of-distribution fault-free "
                     "data and the false alarms are counted on the other half. The last two blocks split the "
                     "second by ranging class: the short-range radio within 100&nbsp;m and long-range ranging beyond.",
                     ["Set", "Detector", "False alarms per pair-day"] + [FAULT_NAMES[f].capitalize() for f in FAULTS]
                     + ["All faults"], rows, "wide",
                     "Simulated motion, sensors and faults. Out of distribution at the deployed thresholds no "
                     "detector keeps its false-alarm rate, so those recalls are not at one rate and must not be "
                     "compared as if they were; a false alarm is a minute with an alarm, so 1,440 per pair-day is "
                     "every minute. Each delay is the median over the faults that detector found. The "
                     "network's numbers are means over five training seeds. The protocol rule (E55) has no tuned "
                     "threshold, so it has no row in the reset block, and it was not scored by class.")
    try:
        c.T["E56"] = table_e56()
    except Pending as e:
        c.table_pending(c.T, "E56", "E56: Table 12, recall and delay per fault type", e)
    try:
        c.F["E56_recall"] = fig_e56_recall(c)
    except Pending as e:
        c.table_pending(c.F, "E56_recall", "E56: Figure 3, recall per fault type on the test and out-of-distribution sets", e)


def fig_e56_recall(c):
    """Figure 3: recall per fault type for three detectors, test set against the out-of-distribution set at the
    deployed thresholds, with the realised false alarms per pair-day printed (inline SVG)."""
    rec, fa = c.e56rec, c.e56fa
    c.e56f()
    dets = [("chi2_step", "chi-square, per step", "#0072B2"), ("cusum", "CUSUM", "#E69F00"), ("net", "network", "#D55E00")]
    W, H, L, B, TOP = 560, 300, 52, 64, 34
    gw = (W - L - 14) / len(FAULTS)
    bw = gw / 8.0
    Y = lambda v: H - B - v * (H - B - TOP)
    out = [f'<figure id="p2-fig-e56"><svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
           'aria-label="Recall per fault type on the test set and out of distribution, three detectors">',
           f'<line x1="{L}" y1="{H - B}" x2="{W - 10}" y2="{H - B}" stroke="#333"/>',
           f'<line x1="{L}" y1="{TOP}" x2="{L}" y2="{H - B}" stroke="#333"/>',
           f'<text x="{L - 36}" y="{(H - B + TOP) / 2:.0f}" font-size="11" text-anchor="middle" '
           f'transform="rotate(-90 {L - 36} {(H - B + TOP) / 2:.0f})">faults found (share)</text>']
    for t in (0, 0.25, 0.5, 0.75, 1.0):
        out.append(f'<line x1="{L - 4}" y1="{Y(t):.1f}" x2="{W - 10}" y2="{Y(t):.1f}" stroke="#ddd"/>')
        out.append(f'<text x="{L - 7}" y="{Y(t) + 3.5:.1f}" font-size="10" text-anchor="end">{t:.2f}</text>')
    for i, f in enumerate(FAULTS):
        x0 = L + i * gw + gw / 2 - 3.5 * bw
        for j, (det, _, col) in enumerate(dets):
            for k, st in enumerate(("test", "ood")):
                v = rec(st, det, f)
                x = x0 + (2 * j + k) * bw + j * bw * 0.5
                style = f'fill="{col}"' if st == "test" else f'fill="#fff" stroke="{col}" stroke-width="1.4"'
                out.append(f'<rect x="{x:.1f}" y="{Y(v):.1f}" width="{bw - 1.2:.1f}" height="{max(Y(0) - Y(v), 0.5):.1f}" {style}/>')
        out.append(f'<text x="{L + i * gw + gw / 2:.0f}" y="{H - B + 15}" font-size="10.5" text-anchor="middle">{FAULT_NAMES[f]}</text>')
    out.append(f'<text x="{(L + W) / 2:.0f}" y="{H - B + 31}" font-size="11" text-anchor="middle">fault type</text>')
    lx = L + 6
    for det, name, col in dets:
        out.append(f'<rect x="{lx}" y="{TOP - 28}" width="9" height="9" fill="{col}"/>')
        out.append(f'<rect x="{lx + 11}" y="{TOP - 28}" width="9" height="9" fill="#fff" stroke="{col}" stroke-width="1.4"/>')
        out.append(f'<text x="{lx + 25}" y="{TOP - 20}" font-size="10.5">{name}</text>')
        lx += 30 + 6.2 * len(name) + 16
    out.append(f'<text x="{L + 6}" y="{TOP - 5}" font-size="10">filled: test set; open: out of distribution, same thresholds</text>')
    fas = "; ".join(f"{name} {c.num(fa('test', det), 2)} and {c.num(fa('ood', det), 0)}" for det, name, _ in dets)
    out.append("</svg><figcaption>Figure 3. E56: the share of faults found, per fault type, by the per-step "
               "chi-square test, the CUSUM and the network, on the test set (filled) and on the "
               "out-of-distribution set at the same thresholds (open). The thresholds were set on validation data "
               "for one false alarm per pair-day. The realised false alarms per pair-day on the two sets were: "
               f"{fas}. The open bars are therefore not at one false-alarm rate. Simulated data; "
               f"{c.cnt(c.e56f()['dataset']['test']['fault_streams_by_type']['drift'])} faults per type and set."
               "</figcaption></figure>")
    return "\n".join(out)


# ---------------------------------------------------------------------------------------------------------
# E55: the protocol's integrity rule as written (3 of 5 at the theoretical threshold) and trimmed-mean agreement, H16
# ---------------------------------------------------------------------------------------------------------
def add_e55(c):
    fill, check, Pending = c.fill, c.check, c.Pending
    num, pc, cnt, words, NB, PCT, MINUS = c.num, c.pc, c.cnt, c.words, c.NB, c.PCT, c.MINUS
    RULE, SINGLE = "3of5@0.001", "single@0.001"

    def e55():
        if c.e55 is None:
            raise Pending("results/E55_integrity.json (B-95) has not landed")
        return c.e55

    def rule(st, det=RULE):
        return e55()["integrity"]["sets"][st][det]

    def cells(pred=lambda x: True):
        return [x for x in e55()["consensus"]["cells"] if pred(x)]
    c.e55f, c.e55rule, c.e55cells = e55, rule, cells

    def design_sentence():
        d = e55()
        cs = cells()
        ns = sorted({x["N"] for x in cs})
        fs = sorted({x["f"] for x in cs})
        runs = {x["runs"] for x in cs}
        check(len(runs) == 1 and all(x["F"] in (1, max(x["f"], 1)) for x in cs), "every consensus cell has the same number of runs, with F = 1 or F = f")
        check(abs(rule("test")["gamma"] - chi2_1_quantile(1e-3)) < 0.005, "E55's threshold is the chi-square quantile for a false alarm of one in a thousand")
        check("3 of the last 5" in d["integrity"]["rule"], "E55 scores the rule with three of the last five tests")
        return (f"The protocol's rule exactly as written [80]: the per-step chi-square test at the theoretical "
                f"threshold &gamma; = {num(rule('test')['gamma'], 2)} (&alpha; = 10<sup>{MINUS}3</sup>, Proposition 5), "
                f"a report declared suspect when three of the last five tests are flagged, and nothing tuned on any "
                f"data; scored on the validation, test and out-of-distribution streams of E56 with E56's event "
                f"scoring, beside the single test at the same threshold. Because no parameter of the rule is chosen "
                f"on data, scoring it on the test set chooses nothing there, and the set stays scored once for "
                f"every tuned detector. For agreement, the trimmed-mean rule of Proposition 7 runs on the radio "
                f"mesh of the terrain: {', '.join(cnt(n) for n in ns[:-1])} and {cnt(ns[-1])} rovers, at positions "
                f"drawn from the fleet's trajectories or spread evenly over the route samples; honest values with a "
                f"spread of 1{NB}m; {cnt(fs[0])} to {cnt(fs[-1])} faulty rovers that send values 50{NB}m off in "
                f"opposite directions (Assumed); the rule's parameter F set to 1 and to the number of faulty "
                f"rovers; 60 steps and {cnt(runs.pop())} runs a cell.")
    fill("P2-E55-DESIGN-SENTENCE", design_sentence, "E55")

    def rule_paragraph():
        d = e55()
        t, single, o, osingle = rule("test"), rule("test", SINGLE), rule("ood"), rule("ood", SINGLE)
        rec = lambda x, f="all": x["per_type"][f]["recall"]
        chi, net = c.e56rec("test", "chi2_step", "all"), c.e56rec("test", "net", "all")
        check(rec(t) < chi < net, "on the test set the rule as written finds fewer faults than the calibrated chi-square test, which finds fewer than the network")
        check(t["fa_per_pair_day"] < 1.0 < single["fa_per_pair_day"], "the persistence rule brings the theoretical threshold under one false alarm per pair-day; the single test is far above it")
        # what alpha = 1e-3 means at one test a second, in E56's unit (60 s bins with at least one alarm)
        a3 = 1e-3
        bins_single = 1440.0 * (1.0 - (1.0 - a3) ** 60)
        k35 = d["integrity"]["k_of_n_false_alarm"]["0.001"]
        check(abs(k35 - k_of_n(3, 5, a3)) < 1e-15, "E55's k-of-n false-alarm probability is the binomial tail")
        per_day_indep = 86400.0 * k35
        check(single["fa_per_pair_day"] < bins_single, "the single test's false alarms are no more than independent Gaussian tests at one a second would give")
        check(t["fa_per_pair_day"] > 20 * per_day_indep, "the 3-of-5 rule's false alarms are far above the value for independent tests (flags arrive in runs)")
        check(o["fa_per_pair_day"] > 100 * t["fa_per_pair_day"], "out of distribution the rule's false-alarm rate rises more than a hundredfold")
        mc = d["integrity"]["detectable_error_check"]
        # how much the rule's small rate can carry (the referee's S5): the heaviest stratum of the fault-free test data
        tds = c.e56f()["dataset"]["test"]
        blocks, pop = tds["natural_blocks_by_stratum"], tds["natural_population_blocks"]
        big = max(pop, key=pop.get)
        w_big = pop[big] / sum(pop.values())
        one_bin = w_big / blocks[big] * 24.0
        ub_big = (1.0 - 0.05 ** (1.0 / blocks[big])) * w_big * 24.0
        check(t["fa_per_pair_day"] < one_bin, "the rule's test rate is below what one alarm-minute in the heaviest stratum would give, so it had none there")
        s4 = rule("test", "single@0.0001")
        bins4 = 1440.0 * (1.0 - (1.0 - 1e-4) ** 60)
        check(single["fa_per_pair_day"] < 0.75 * bins_single and s4["fa_per_pair_day"] < 0.75 * bins4,
              "at both thresholds the single test alarms in fewer minutes than independent Gaussian innovations would: the innovations are not Gaussian with the claimed variance")
        return (f"E55 scored the protocol's rule as written on the same streams. On the test set it gave "
                f"{num(t['fa_per_pair_day'], 2)} false alarms per pair-day and found {pc(rec(t), 1)} of all faults "
                f"({pc(rec(t, 'jump'), 1)} of jumps, {pc(rec(t, 'drift'), 1)} of slow drifts and "
                f"{pc(rec(t, 'noise'), 1)} of noise inflation), against {pc(chi, 1)} for the per-step test "
                f"calibrated on validation data and {pc(net, 1)} for the network (Table 12). The single test at the "
                f"same threshold, without the persistence rule, gave {num(single['fa_per_pair_day'], 0)} false "
                f"alarms per pair-day. A false alarm of 10<sup>{MINUS}3</sup> per test, at one test a second, is "
                f"up to {num(bins_single, 0)} minutes with an alarm in a day for independent Gaussian "
                f"innovations, so the persistence clause is what brings the theoretical threshold under one false "
                f"alarm per pair-day on these data. The single test alarmed in fewer minutes than that, here and at "
                f"the next threshold ({num(s4['fa_per_pair_day'], 1)} against {num(bins4, 1)} at &gamma; = "
                f"{num(s4['gamma'], 2)}), and the rule's own rate is far above the {num(per_day_indep, 4)} a day "
                f"that independent tests would give: the innovations are neither independent nor Gaussian with the "
                f"claimed variance, and flags arrive in runs. The rule's rate is a handful of alarm-minutes in "
                f"{cnt(tds['fault_free_natural_blocks'])} fault-free hours; the results file keeps neither their "
                f"count nor an interval. No alarm-minute fell in the heaviest stratum, where a single one would be "
                f"{num(one_bin, 2)} per pair-day, and no alarm in that stratum's {cnt(blocks[big])} hours still "
                f"allows up to {num(ub_big, 2)} per pair-day from it at 95{PCT}. Out of distribution the rule gave "
                f"{num(o['fa_per_pair_day'], 0)} false alarms per pair-day and found {pc(rec(o, 'jump'), 0)} of the "
                f"small jumps and {pc(rec(o, 'drift'), 0)} of the slow drifts; the single test gave "
                f"{cnt(osingle['fa_per_pair_day'])}. A Monte Carlo check of Proposition 5 in the same code flagged "
                f"an error of {num(mc['bias_sigma'], 2)}{NB}&sigma;<sub>v</sub> with probability "
                f"{num(mc['detect_prob'], 3)} at a false alarm of {num(mc['false_alarm'] * 1e3, 2)}{NB}&times;{NB}10<sup>{MINUS}3</sup>.")
    fill("P2-E55-RULE-PARAGRAPH", rule_paragraph, "E55")

    def facts16():
        d = e55()
        h = d["h16"]
        ok = cells(lambda x: x["F"] >= x["f"])
        over = cells(lambda x: x["f"] > x["F"])
        all_safe = all(x["safe_share"] == 1.0 for x in ok)
        check(h["robust_cells_all_safe"] and all_safe, "with F at least the number of liars every run stayed inside the honest range")
        check(h["nonrobust_cells_with_a_run_leaving_the_range"] == 0 and h["nonrobust_cells"] > 0 and not h["supported"],
              "on non-robust meshes no run left the honest range, so H16's second half fails")
        check(all(x["safe_share"] < 1.0 for x in over) and len(over) > 0, "with more liars than F some runs leave the honest range, in every such cell")
        rng = lambda g, key, cs: (min(x[key] for x in cs if x["geometry"] == g), max(x[key] for x in cs if x["geometry"] == g))
        return SimpleNamespace(h=h, ok=ok, over=over, rng=rng, all=cells())

    def h16_paragraph():
        f = facts16()
        sf, ss = f.rng("fleet", "safe_share", f.over), f.rng("spread", "safe_share", f.over)
        ag = (min(x["agreement_share"] for x in f.ok), max(x["agreement_share"] for x in f.ok))
        ag_all = max(x["agreement_share"] for x in f.all)
        ag0 = max(x["agreement_share"] for x in f.all if x["f"] == 0)
        top = [x for x in f.all if x["agreement_share"] == ag_all]
        check(ag_all > ag[1] and all(x["f"] > x["F"] for x in top), "the largest agreement share is in a cell with more faulty rovers than F, where the rule is not safe")
        dg = f.rng("fleet", "degree_condition_share", f.all)
        dgs = f.rng("spread", "degree_condition_share", f.all)
        check(ag[1] < 0.5, "agreement is reached in a minority of runs in every cell")
        fo = sorted({(x["f"], x["F"]) for x in f.over})
        check(fo == [(2, 1)], "the cells with more liars than F are f = 2, F = 1")
        return (f"For agreement, in all {cnt(len(f.ok))} cells in which F was at least the number of faulty rovers, "
                f"every honest value stayed inside the initial honest range at every step of every run, on meshes "
                f"that met the robustness condition and on meshes that did not ({cnt(f.h['nonrobust_cells'])} cells "
                f"without it, none with a run that left the range). With more faulty rovers than F (two against "
                f"F = 1) the range held in {pc(sf[0], 0)} to {pc(sf[1], 0)} of runs at fleet positions and in "
                f"{pc(ss[0], 0)} to {pc(ss[1], 0)} of spread runs. Agreement, the honest range shrinking below "
                f"1{PCT} of its first width in 60 steps, was reached in {pc(ag[0], 0)} to {pc(ag[1], 0)} of runs "
                f"where F covered the faulty rovers, and in no more than {pc(ag0, 0)} with no faulty rover at all; "
                f"the largest share in any cell, {pc(ag_all, 0)}, is with two faulty rovers and F = 1, where the "
                f"rule is not safe. The mesh is sparse: every honest "
                f"rover heard the 2F + 1 others the rule needs in {pc(dg[0], 0)} to {pc(dg[1], 0)} of fleet runs "
                f"and in {pc(dgs[1], 0) if dgs[1] > 0 else 'none'} of the spread runs. H16 as registered has two "
                f"halves [59]: on a (2f+1)-robust mesh every run stays inside the honest range, and on a mesh that "
                f"is not, at least one run leaves it. The first half held and the second did not, so H16 is not "
                f"supported as written. The second half mis-stated the theory, which a dated change of [59] "
                f"records: the rule's safety needs no more than F faulty neighbours of each honest rover, on any "
                f"graph, and robustness decides whether the honest rovers converge (Proposition 7). That "
                f"restatement was written after the result and is exploratory.")
    fill("P2-E55-H16-PARAGRAPH", h16_paragraph, "E55")
    c.e55facts16 = facts16

    def mast_sentence():
        d = e55()
        if "consensus_with_base_mast" not in d:
            raise Pending("the E55 variant with the base mast as a well-connected honest node has not landed")
        ok = lambda x: x["F"] >= x["f"]
        rr = lambda cs, g, key: (min(x[key] for x in cs if x["geometry"] == g and ok(x)),
                                 max(x[key] for x in cs if x["geometry"] == g and ok(x)))
        base, mast = d["consensus"]["cells"], d["consensus_with_base_mast"]["cells"]
        check(len(mast) == len(base), "the mast variant runs the same cells")
        c0, c1 = rr(base, "fleet", "connected_share"), rr(mast, "fleet", "connected_share")
        a0, a1 = rr(base, "fleet", "agreement_share"), rr(mast, "fleet", "agreement_share")
        s1 = rr(mast, "fleet", "safe_share")
        sp0, sp1 = rr(base, "spread", "agreement_share"), rr(mast, "spread", "agreement_share")
        spc = rr(mast, "spread", "connected_share")
        check(c1[0] > 5 * max(c0[1], 0.01), "the mast connects the fleet graph in most runs, where it was almost never connected")
        check(a1[1] < 0.25 and a1[1] - a0[1] < 0.1, "the mast does not buy agreement: it stays rare")
        check(s1 == (1.0, 1.0), "with the mast every run with F at least the number of faulty rovers stays in range")
        check(sp0 == sp1 == (0.0, 0.0), "the spread geometry reaches no agreement with or without the mast")
        over = lambda cs: sorted((x["N"], x["safe_share"]) for x in cs if x["geometry"] == "fleet" and x["f"] > x["F"])
        o0, o1 = over(base), over(mast)
        check([n for n, _ in o0] == [n for n, _ in o1] and all(b < a for (_, a), (_, b) in zip(o0, o1)),
              "with more faulty rovers than F the mast lowers the share of safe runs in every fleet cell")
        check({(x["f"], x["F"]) for x in mast if x["f"] > x["F"]} == {(2, 1)}, "the cells with more liars than F are f = 2, F = 1")
        ov0 = (min(s for _, s in o0), max(s for _, s in o0))
        ov1 = (min(s for _, s in o1), max(s for _, s in o1))
        n12 = (dict(o0)[12], dict(o1)[12])
        return (f"A variant run after these results adds the base mast to the mesh as one more honest node, linked "
                f"to every rover it can see. At fleet positions the graph was then connected in {pc(c1[0], 0)} to "
                f"{pc(c1[1], 0)} of runs, against {pc(c0[0], 0)} to {pc(c0[1], 0)} without it, and agreement was "
                f"reached in {pc(a1[0], 0)} to {pc(a1[1], 0)} of runs against {pc(a0[0], 0)} to {pc(a0[1], 0)} "
                f"(cells with F at least the number of faulty rovers); every run stayed inside the honest range. "
                f"With the rovers spread over the routes nothing changed: the graph was connected in at most "
                f"{pc(spc[1], 0)} of runs and no run agreed. The mast makes the graph a star, and a rover that "
                f"hears the mast and one or two others can have every value it hears trimmed away. More links "
                f"help only while F covers the faulty rovers. With two faulty rovers and F = 1 at fleet positions "
                f"the range held in {pc(ov1[0], 0)} to {pc(ov1[1], 0)} of runs with the mast, against "
                f"{pc(ov0[0], 0)} to {pc(ov0[1], 0)} without it ({pc(n12[1], 0)} against {pc(n12[0], 0)} with "
                f"12 rovers): the mast connects the faulty rovers to more honest ones.")
    fill("P2-E55-MAST-SENTENCE", mast_sentence,
         "E55 mast variant: the share of runs that reach agreement when the base mast joins the mesh as a "
         "well-connected honest node")


# ---------------------------------------------------------------------------------------------------------
# The confirmatory family of PREREG6 with the Holm correction (results/phase6_family.json, B-98a) and the Phase 6
# verification rows tagged to this paper (results/vv_phase6.json, B-98)
# ---------------------------------------------------------------------------------------------------------
def add_family(c):
    fill, check, Pending = c.fill, c.check, c.Pending
    num, pc, cnt, words, NB, PCT, MINUS = c.num, c.pc, c.cnt, c.words, c.NB, c.PCT, c.MINUS

    def fam():
        d = _load("phase6_family.json")
        if d is None:
            raise Pending("results/phase6_family.json (B-98a) has not landed")
        h = d["hypotheses"]
        # Holm, recomputed from the unadjusted p values of the three hypotheses with a sampling test
        ps = {"H10": h["H10"]["p_intersection_union"], "H14": h["H14"]["p"], "H15a": h["H15a"]["p"]}
        order = sorted(ps, key=ps.get)
        adj, run = {}, 0.0
        for i, k in enumerate(order):
            run = max(run, min(1.0, (len(order) - i) * ps[k]))
            adj[k] = run
        check(all(abs(adj[k] - h[k]["holm"]["p_adjusted"]) < 1e-12 for k in ps), "the Holm-adjusted p values in the family file are reproduced")
        check(all(h[k]["holm"]["rejected_at_0.05"] == (adj[k] < d["alpha"]) for k in ps), "each Holm decision follows from its adjusted p value")
        cl = h["H10"]["clauses"]
        gk = [k for k in cl if k.startswith("the gap grows")]
        check(len(gk) == 1, "the family file holds one clause on the gap growing with the fleet")
        gcl = cl[gk[0]]
        pcl = [cl["layered within 1.5x of perfect at 1x (TOST)"]["p"], gcl["p_one_sided"],
               cl["dead reckoning with the margin larger at 1x"]["p_one_sided"]]
        check(abs(max(pcl) - ps["H10"]) < 1e-12, "H10's joined p value is the largest of its three clause p values")
        # the family file and the experiment files tell the same story
        s = c.e50f(1)
        check(abs(gcl["gap_4x_h"] - s["h10"]["gap_by_mult"]["4"]["mean"]) < 1e-9
              and abs(cl["dead reckoning with the margin larger at 1x"]["mean_diff_h"] - s["delay"]["1"]["margin_dr_minus_perfect"]["mean"]) < 1e-9,
              "the family file's H10 clauses use E50's differences")
        check((pcl[0] < d["alpha"]) == s["h10"]["layered_within_supported"] and (pcl[2] < d["alpha"]) == s["h10"]["dr_larger_supported"],
              "the clause-level verdicts of H10' agree between the family file and E50")
        check(abs(h["H14"]["mean_diff_jobs"] - c.e54f()["h14"]["difference_sf_ll_minus_drop_retry"]["mean"]) < 1e-9,
              "the family file's H14 uses E54's difference")
        check(abs(h["H15a"]["delay_median_diff_s"] - c.e56h15("chi2_step", "drift")["delay_median_diff_s"]["value"]) < 1e-9,
              "the family file's H15a uses E56's difference")
        return SimpleNamespace(d=d, h=h, adj=adj, pcl=pcl, gcl=gcl)
    c.famf = fam

    def pv(p, nd=3):
        return f"below {num(10 ** -nd, nd)}" if p < 10 ** -nd else num(p, nd if p < 0.1 else 2)

    def stats_sentence():
        f = fam()
        check("Holm" in f.d["family"] and f.d["alpha"] == 0.05, "the family is corrected by Holm at 0.05")
        check("no sampling test" in f.h["H9"]["test"] and "no sampling test" in f.h["H13"]["test"], "H9 and H13 are threshold comparisons without a sampling test")
        check("sign test" in f.h["H14"]["test"] and "TOST" in f.h["H10"]["test"] and "bootstrap" in f.h["H15a"]["test"],
              "the three sampling tests are the ones the text names")
        return (f"[59] names a family of confirmatory hypotheses, H9&prime;, H10&prime;, H13, H14 and H15 (a), for a "
                f"Holm correction at &alpha; = {num(f.d['alpha'], 2)}. H9&prime; and H13 are comparisons with a "
                f"threshold and have no sampling test; they are reported by the share of seeds or draws on the "
                f"predicted side, and H13 belongs to the companion papers. The correction is applied over the three "
                f"that have a test: H10&prime; by paired two one-sided tests at today's fleet, joined with its other "
                f"two clauses by intersection and union, so that its p value is the largest of the three; H14 by an "
                f"exact sign test on the lost jobs per seed; and H15 (a) by the bootstrap over events, whose p value "
                f"is an upper bound when no resample reaches zero. These p values are not registered: [59] gives "
                f"its decision rules by interval, and the three tests were constructed after the results so that "
                f"the correction could be applied. The sign test is one-sided (two-sided p = "
                f"{num(2 * f.h['H14']['p'], 4)}), and the registered rule for H14, a paired interval that excludes "
                f"zero, gives the same verdict. Over the registered family of five, counting the two hypotheses "
                f"that have no test, the adjusted values would be at most {num(5 * f.h['H15a']['p'], 3)} for H15 (a) "
                f"and {num(4 * f.h['H14']['p'], 3)} for H14, and no verdict changes.")
    fill("P2-FAMILY-STATS-SENTENCE", stats_sentence, "B-98a")

    def h9_sentence():
        f = fam()
        cl = list(f.h["H9"]["clauses"].values())
        check([x["supported"] for x in cl] == [True, True, False] and [x["seeds_on_predicted_side"] for x in cl] == [1.0, 1.0, 0.0],
              "in H9' every seed is on the predicted side in the first two clauses and none in the third")
        return ("Seed by seed, every seed lay on the predicted side of the budget in the first clause; in the "
                "second every seed did under the reading used and none under the registered wording; and none did "
                "in the third.")
    fill("P2-FAMILY-H9-SENTENCE", h9_sentence, "B-98a")

    def h10_sentence():
        f = fam()
        rej = f.h["H10"]["holm"]["rejected_at_0.05"]
        check(not rej and f.pcl[0] < 0.001 and f.pcl[1] > 0.05 and f.pcl[2] > 0.05,
              "H10' is not supported as a whole: the first clause holds and the other two do not")
        return (f"Taken as one hypothesis of the confirmatory family, H10&prime; is not supported. Its first clause "
                f"holds (p {pv(f.pcl[0])}), but the one-sided p value is {pv(f.gcl.get('p_one_sided_4x', f.pcl[1]))} for a larger gap at four "
                f"times the fleet" + (f", {pv(f.gcl['p_one_sided_8x'])} at eight times," if "p_one_sided_8x" in f.gcl else "")
                + f" and {pv(f.pcl[2])} for a costlier dead-reckoning margin at today's fleet, and the "
                f"three clauses joined have a Holm-adjusted p of {pv(f.adj['H10'])}.")
    fill("P2-FAMILY-H10-SENTENCE", h10_sentence, "B-98a")

    def h14_sentence():
        f = fam()
        h = f.h["H14"]
        check(h["holm"]["rejected_at_0.05"] and h["seeds_more"] == 0, "H14 stands after the Holm correction, with no seed losing more jobs under the rule")
        return (f"By an exact sign test, custody with the lost-link rule lost fewer jobs in {cnt(h['seeds_fewer'])} "
                f"seeds, more in {'none' if h['seeds_more'] == 0 else cnt(h['seeds_more'])} and the same number in "
                f"{cnt(h['seeds_tied'])} (one-sided p {pv(h['p'])}; Holm-adjusted {pv(f.adj['H14'])}), so the first "
                f"clause stands in the confirmatory family; the test was added after the results (Section 4.5).")
    fill("P2-FAMILY-H14-SENTENCE", h14_sentence, "B-98a")

    def h15a_sentence():
        f = fam()
        h = f.h["H15a"]
        check(h["holm"]["rejected_at_0.05"] and "upper bound" in h["p_note"], "H15a stands after the Holm correction; its p value is an upper bound")
        return (f"In the confirmatory family (a) stands after the Holm correction: no bootstrap resample reached "
                f"zero, so p is at most {num(h['p'], 3)} and the adjusted value at most {num(f.adj['H15a'], 3)}.")
    fill("P2-FAMILY-H15A-SENTENCE", h15a_sentence, "B-98a")

    def limitation():
        f = fam()
        n4 = f.gcl["n_4x"]
        n8 = f.gcl.get("n_8x")
        check((n8 is not None) == c.e50has8(), "the family file and E50 agree on whether the eight-times cells are in")
        return (f"The Holm correction of [59] covers the three confirmatory hypotheses that have a sampling test "
                f"(Section 4.5). H9&prime; is a comparison with a threshold and has none, and the clause of "
                f"H10&prime; on larger fleets rests on {cnt(n4)} seeds at four times the fleet, which do not "
                f"resolve it" + (f", and {cnt(n8)} at eight times. " if n8 else "; the eight-times cells have not finished. ")
                + f"The p values were constructed after the "
                f"results.")
    fill("P2-FAMILY-LIMITATION", limitation, "B-98a")

    # --- the Phase 6 verification rows tagged to this paper (the phase-5 format; summary recounted from the rows) ---
    def vv6():
        d = _load("vv_phase6.json")
        if d is None:
            raise Pending("results/vv_phase6.json (B-98) has not landed")
        allr = d["rows"]
        s = d["summary"]
        check(s["rows"] == len(allr) and s["passed"] == sum(1 for x in allr if x["passed"] and not x["skipped"])
              and s["failed"] == sum(1 for x in allr if not x["passed"] and not x["skipped"]),
              "the summary of results/vv_phase6.json is the count of its rows")
        return d, [x for x in allr if "P2" in x["papers"]]

    def checks_sentence():
        d, rows = vv6()
        tech = {}
        for x in rows:
            tech[x["technique"]] = tech.get(x["technique"], 0) + 1
        check(all(x["kind"] == "V" for x in rows), "the Phase 6 rows tagged to this paper are verifications")
        lst = ", ".join(f"{k} ({cnt(v)})" for k, v in sorted(tech.items(), key=lambda kv: -kv[1]))
        return (f"For the models of Sections 3.9 to 3.12, {cnt(len(rows))} rows of the Phase 6 verification suite "
                f"(<code>lunarsim/vv6.py</code>, results in <code>results/vv_phase6.json</code>) bear on this paper, "
                f"all of them verifications that the code does what the research notes derive, by technique {lst}: "
                f"the growth of dead-reckoning error with distance, the chi-square thresholds, the detectable error "
                f"and the three-of-five probability of Proposition 5, the trimmed mean with one faulty rover, the "
                f"zero-fault behaviour of the test and of the rule, a zero error for perfect position, and the "
                f"identity of the logistics model with every Phase 6 option switched off; the rows ran at commit "
                f"{d['commit'][:7]}. Their outcomes are in Section 5.13.")
    fill("P2-CHECKS6-SENTENCE", checks_sentence, "B-98")

    def checks_outcome():
        import re as _re
        d, rows = vv6()
        ran = [x for x in rows if not x["skipped"]]
        bad = [x for x in ran if not x["passed"]]
        g1 = [x for x in rows if x["id"] == "G1" and x["sub"] == "options off"]
        check(len(g1) == 1 and g1[0]["passed"] and g1[0]["simulated"] == 0.0, "with every Phase 6 option off the Phase 5 run is reproduced")
        n_cmp = int(_re.search(r"(\d+) summary values compared", g1[0]["basis"]).group(1))
        out = (f"All {cnt(len(ran))} Phase 6 verification rows tagged to this paper passed." if not bad else
               f"Of the {cnt(len(ran))} Phase 6 verification rows tagged to this paper, {cnt(len(bad))} failed: "
               + "; ".join(x["name"] for x in bad) + ".")
        out += (f" With every Phase 6 option off, the logistics model reproduces the Phase 5 run: "
                f"{cnt(g1[0]['simulated'])} of {cnt(n_cmp)} summary values differ.")
        return out
    fill("P2-CHECKS6-OUTCOME", checks_outcome, "B-98")


# ---------------------------------------------------------------------------------------------------------
# B-97: the detector family on real spacecraft telemetry (SMAP, MSL); not rover position data
# ---------------------------------------------------------------------------------------------------------
def add_b97(c):
    fill, check, Pending = c.fill, c.check, c.Pending
    num, cnt, words, NB = c.num, c.cnt, c.words, c.NB
    import re as _re
    ORDER = [("zscore", "z-score"), ("chi2_step", "chi-square, per step"), ("chi2_window_16", "chi-square, windowed"),
             ("cusum_k0.5", "CUSUM")]

    def b97():
        d, dl = _load("B97_realdata.json"), _load("B97_downloads.json")
        if d is None or dl is None or "telemetry" not in d:
            raise Pending("results/B97_realdata.json (B-97) has not landed")
        return d["telemetry"], dl

    def row(t, sc, resid, det):
        g = [r for r in t["rows"] if r["spacecraft"] == sc and r["residual"] == resid and r["detector"] == det]
        if len(g) != 1:
            raise KeyError(f"B97 row {sc} / {resid} / {det}: {len(g)} rows")
        return g[0]
    c.b97f, c.b97row = b97, row

    def paragraph():
        t, dl = b97()
        src = dl["sources"]["telemanom (SMAP / MSL)"]
        chk = " ".join(src["checks_passed"])
        check(src["is_mirror"] and "byte-identical" in chk, "the telemetry comes from a mirror whose label file is byte-identical to the original")
        n_ch = int(_re.search(r"(\d+) channels", chk).group(1))
        n_an = int(_re.search(r"(\d+) labelled anomalies", chk).group(1))
        per = {sc: row(t, sc, "level", "chi2_step") for sc in ("MSL", "SMAP")}
        used_ch = sum(r["channels"] for r in per.values())
        used_ev = sum(r["events"] for r in per.values())
        check(used_ch == len(t["channels"]), "the channels used are the listed ones")
        check("training" in t["threshold_rule"], "the thresholds come from the training data only")
        acc = {(sc, d): row(t, sc, "level", d) for sc in ("MSL", "SMAP") for d in ("chi2_window_16", "cusum_k0.5")}
        check(all(acc[(sc, d)]["found"] > per[sc]["found"] for sc, d in acc),
              "on the level residual both accumulating detectors find more labelled events than the per-step test, on both spacecraft")
        diff_more = any(row(t, sc, "diff", d)["found"] > row(t, sc, "diff", "chi2_step")["found"]
                        for sc in ("MSL", "SMAP") for d in ("chi2_window_16", "cusum_k0.5"))
        prec = [r["precision"] for r in acc.values()]
        f = lambda sc, d, resid="level": row(t, sc, resid, d)["found"]
        # the referee's S7: not E56's settings, not at one false-alarm rate, and two columns are one detector
        b56 = c.e56f()["baselines"]
        check(b56["chi2_window_W"] == 5 and b56["cusum_k"] == 3.0 and b56["cusum_ref_s"] > 0,
              "E56's windowed test averages 5 s and its CUSUM uses k = 3 on a centred innovation; the telemetry check uses a window of 16 and k = 0.5 without centring")
        check(all(row(t, sc, rs, "zscore")[k] == row(t, sc, rs, "chi2_step")[k] for sc in ("MSL", "SMAP")
                  for rs in ("level", "diff") for k in ("found", "fp_runs")),
              "on one channel the z-score and the per-step chi-square test are the same detector (identical rows)")
        fp = lambda sc, d: row(t, sc, "level", d)["fp_runs"]
        check(fp("SMAP", "chi2_window_16") > 5 * fp("SMAP", "chi2_step") and fp("SMAP", "cusum_k0.5") > 5 * fp("SMAP", "chi2_step"),
              "on SMAP the accumulating detectors' gain comes with several times the false-alarm runs of the per-step test")
        check(t["channels"] == sorted(t["channels"]), "the channels used are the first of each spacecraft in the file listing's order")
        out = (f"One check uses real data. The same detector family, with none of its thresholds and without the "
               f"network, was run on the labelled SMAP and MSL telemetry of the telemanom data release [82], taken "
               f"from a public mirror whose label file is byte-identical to the original: {cnt(n_ch)} channels and "
               f"{cnt(n_an)} labelled anomalies in all, of which the first {cnt(per['MSL']['channels'])} channels of "
               f"each spacecraft, with {cnt(used_ev)} labelled events, were used. This is housekeeping telemetry of "
               f"a satellite and a Mars rover. It is not lunar rover position data, and it tests one thing only: "
               f"whether a detector that accumulates evidence finds more than a per-step test on real signals. The "
               f"channels are the first {cnt(per['MSL']['channels'])} of each spacecraft in the order of the file "
               f"listing, a subset set by download size and not by any property of the channels. The detectors are "
               f"of E56's family and not at E56's settings: the window is 16 steps against "
               f"{cnt(b56['chi2_window_W'])}, and the CUSUM has a reference of 0.5 without centring against "
               f"{num(b56['cusum_k'], 0)} with centring. Each "
               f"channel is standardised on its own training data, and each detector's threshold is its largest "
               f"score on that training data, so nothing is set on the labelled events. On the level of the signal "
               f"the windowed chi-square and the CUSUM found {cnt(f('MSL', 'chi2_window_16'))} and "
               f"{cnt(f('MSL', 'cusum_k0.5'))} of the {cnt(per['MSL']['events'])} MSL events against the per-step "
               f"test's {cnt(per['MSL']['found'])}, and {cnt(f('SMAP', 'chi2_window_16'))} and "
               f"{cnt(f('SMAP', 'cusum_k0.5'))} of the {cnt(per['SMAP']['events'])} SMAP events against "
               f"{cnt(per['SMAP']['found'])} (Table 13). Their precision was {num(min(prec), 2)} to "
               f"{num(max(prec), 2)}, with thresholds that were not tuned per channel. The comparison is not at one "
               f"false-alarm rate: on SMAP the two accumulating detectors raised {cnt(fp('SMAP', 'chi2_window_16'))} "
               f"and {cnt(fp('SMAP', 'cusum_k0.5'))} runs of alarms that touch no labelled event, against the "
               f"per-step test's {cnt(fp('SMAP', 'chi2_step'))}. The z-score and per-step columns of Table 13 are "
               f"one detector on a single channel and print the same numbers. ")
        if not diff_more:
            out += (f"On the first difference of the signal the accumulating detectors found no more than the "
                    f"per-step test ({cnt(f('MSL', 'chi2_window_16', 'diff'))} and {cnt(f('MSL', 'cusum_k0.5', 'diff'))} "
                    f"against {cnt(f('MSL', 'chi2_step', 'diff'))} on MSL; {cnt(f('SMAP', 'chi2_window_16', 'diff'))} "
                    f"and {cnt(f('SMAP', 'cusum_k0.5', 'diff'))} against {cnt(f('SMAP', 'chi2_step', 'diff'))} on "
                    f"SMAP). ")
        out += ("The first difference is the residual closest to an innovation, so on the signal that most "
                "resembles the one the traffic rules test, accumulation gained nothing. The check supports no "
                "choice of detector, and we draw none from it. The logistic regression and the network take the "
                "ten features of a vehicle pair and do not apply "
                "to a single telemetry channel. The published results of the study that released the data are not "
                "quoted: we did not open that paper, and these numbers do not reproduce it.")
        return out
    fill("P2-B97-PARAGRAPH", paragraph, "B-97")

    def table():
        t, dl = b97()
        rows = []
        for sc in ("MSL", "SMAP"):
            for resid, name in (("level", "level"), ("diff", "first difference")):
                cells = [sc, cnt(row(t, sc, resid, "chi2_step")["events"]), name]
                for det, _ in ORDER:
                    r = row(t, sc, resid, det)
                    cells.append(f"{cnt(r['found'])} / {cnt(r['fp_runs'])} ({num(r['precision'], 2)})")
                rows.append(cells)
        return c.tab("Table 13. The detector family on real spacecraft telemetry (labelled SMAP and MSL channels; not "
                     "rover position data): labelled events found / runs of alarms that touch no labelled event "
                     "(precision), per detector, on the standardised signal and on its first difference. Thresholds "
                     "are each channel's largest score on its training data.",
                     ["Spacecraft", "Labelled events", "Residual"] + [n for _, n in ORDER], rows, "",
                     "An event is found if an alarm falls inside it. The first two detector columns are the same "
                     "detector on a single channel. The detectors are not at one false-alarm rate. The logistic "
                     "regression and the network need the ten pair features of E56 and are not applicable.")
    try:
        c.T["B97"] = table()
    except Pending as e:
        c.table_pending(c.T, "B97", "B-97: Table 13, the detector family on real spacecraft telemetry", e)


# ---------------------------------------------------------------------------------------------------------
# Appendix A: the numbers the propositions quote, each recomputed here and checked against a file where one exists
# ---------------------------------------------------------------------------------------------------------
def add_props(c):
    V, fill, check, Pending = c.V, c.fill, c.check, c.Pending
    num, pc, cnt, NB, PCT, MINUS = c.num, c.pc, c.cnt, c.NB, c.PCT, c.MINUS
    m_ = c.m_
    import numpy as np
    from lunarsim.atc import pnt as PN
    from lunarsim.atc import safety as S
    D = PN.DEFAULTS
    kmh = lambda v: f"{num(v * 3.6, 1)}{NB}km/h"

    def prop1():
        m, e_firm, e_loose = S.D0_M, D["dr_firm"], D["dr_loose"]
        z = ND.inv_cdf(0.975)
        d_firm, d_loose = m / e_firm, m / e_loose
        beta = math.radians(D["heading_sigma_deg"])
        b = math.radians(D["gyro_drift_deg_h"]) / 3600.0
        v_fast, v_slow = 15.0 / 3.6, 4.0 / 3.6            # the class limits of Table 2 (R2): crew rovers, cargo rovers
        out = (f"With m = d<sub>0</sub> = {m_(m, 0)} and the drift of Section 3.9, &sigma;<sub>&epsilon;</sub> = "
               f"{pc(e_firm, 0)} gives d* &le; {m_(d_firm, 0)} and {pc(e_loose, 0)} gives {m_(d_loose, 0)}; the "
               f"two-sided 95{PCT} level, {num(z, 2)}{NB}&sigma;, is reached after at most {m_(d_firm / z, 0)} and "
               f"{m_(d_loose / z, 0)}. A crew rover at 15{NB}km/h covers {m_(d_firm, 0)} in {num(d_firm / v_fast, 0)}{NB}s "
               f"and a cargo rover at 4{NB}km/h in {num(d_firm / v_slow, 0)}{NB}s. Across the track a bounded heading "
               f"error &beta; adds &beta;d, {pc(beta, 2)} of the distance at the star tracker's "
               f"{num(D['heading_sigma_deg'], 1)}&deg;, and a gyro bias b alone adds v{NB}b{NB}t<sup>2</sup>/2, "
               f"{pc(b * 3600.0 / 2.0, 1)} of the distance after an hour at {num(D['gyro_drift_deg_h'], 0)}&deg;/h [60], "
               f"so the heading reference decides whether the odometer's figure is kept.")
        try:
            s = c.e50f(1)
            hrs = s["errors"]["1"]["dr"]["shift_p95_m_mean_over_seeds"][:8]
            check(hrs[0] > m, "E50 agrees with Proposition 1: dead reckoning alone is past the margin within the first driving hour")
            check(all(b2 > a2 for a2, b2 in zip(hrs, hrs[1:])), "E50: the dead-reckoning error grows with every driving hour of the shift")
            out += (f" E50 illustrates the growth and does not test the formula: with dead reckoning alone the 95th "
                    f"percentile of the error was {m_(hrs[0], 0)} after one hour of driving and {m_(hrs[-1], 0)} "
                    f"after eight (30 seeds).")
        except Pending:
            pass
        return out
    fill("P2-PROP1-NUMBERS", prop1, "E50")

    def prop2():
        """The constant-speed premise of Proposition 2 (the referee's S11): what happens for a vehicle that starts
        from rest, and for one that waits at the mouth of the segment."""
        beta = c.e50st(1, "dr+ranging", "near")["mean"]          # the 95th-percentile error near the base with ranging
        a, v = S.A_ACC, 15.0 / 3.6
        t_rest, t_margin = math.sqrt(2.0 * beta / a), beta / v
        check(t_rest > 3 * t_margin, "a vehicle starting from rest needs several times the margin k b / v to cover its error bound")
        src = open(os.path.join(ROOT, "lunarsim", "atc", "roads.py"), encoding="utf-8").read()
        check("v_ms = self.leg_length_m(key) / max(dur * 3600.0, 1e-9)" in src,
              "the logistics model takes the mean speed of the whole leg as v in the reservation margin")
        return (f"The premise is about speed as well as position. A vehicle is at each end of the segment within "
                f"&beta;/v of the time it believes only if it covers the stretch of length &beta; there at the speed "
                f"v. A vehicle that starts from rest at a bay, as every waiting vehicle does, needs "
                f"&radic;(2&beta;/a) to cover &beta; at its acceleration a: {num(t_rest, 1)}{NB}s for &beta; = "
                f"{m_(beta, 1)} and a = {num(a, 1)}{NB}m/s<sup>2</sup>, against a margin &beta;/v of "
                f"{num(t_margin, 1)}{NB}s at 15{NB}km/h. And a waiting vehicle whose position is wrong by &beta; "
                f"may stand up to &beta; inside the mouth of the segment for as long as it waits, which no margin "
                f"in time covers; a stop line set back from the entry by &beta; does. Neither is in the rule as it "
                f"was run: the logistics model takes v as the mean speed of the whole leg and has no stop line. "
                f"Errors of opposite sign on the two vehicles are covered by the proof.")
    fill("P2-PROP2-NUMBERS", prop2, "E50")

    def prop3():
        mu, g = S.MU_DEFAULT, S.G_MOON
        a_fric = mu * g
        a_r2 = float(S.b_guaranteed(0.0, mu, g))
        check(abs(a_r2 - min(S.B_MIN_FLAT, a_fric)) < 1e-12 and a_r2 == S.B_MIN_FLAT,
              "on the flat at the default friction the service brake, not friction, limits R2's braking")

        def vmax(a, tr, dp, d0=0.0):
            return -a * tr + math.sqrt(a * a * tr * tr + 2.0 * a * (dp - d0))
        for tr in (1.0, 6.0):
            for dp in (10.0, 20.0, 40.0):
                code = float(S.v_max_r2(0.0, mu, dp, 1e9, rho=tr, g=g))
                check(abs(code - vmax(a_r2, tr, dp)) < 1e-9, f"Proposition 3's formula is the one R2 runs (t_r {tr:g} s, sight {dp:g} m)")
        check(abs(vmax(0.45 * 1.62, 6.0, 20.0, 2.0) * 3.6 - 8.5) < 0.05, "the worked cell of research note 04 E.3 is reproduced (8.5 km/h)")
        on, earth = S.RHO_S, 6.0
        check(vmax(a_r2, earth, 20.0) < vmax(a_r2, on, 20.0), "a longer reaction delay lowers the safe speed")
        for dp in (10.0, 20.0):
            check(0.45 < vmax(a_r2, earth, dp) / vmax(a_r2, on, dp) < 0.65,
                  f"with Earth in the loop the safe speed is about half to three-fifths of the on-board value ({dp:g} m of sight)")
        v15 = 15.0 / 3.6
        dp15 = v15 * on + v15 ** 2 / (2.0 * a_r2) + S.D0_M     # perception range at which the caution speed is the class limit
        check(abs(vmax(a_r2, on, dp15, S.D0_M) - v15) < 1e-9 and vmax(a_r2, on, 10.0, S.D0_M) < vmax(a_r2, on, 20.0, S.D0_M) < v15,
              "the caution speed rises with the perception range and reaches the class limit at the stated range")
        measured_kmh = 2.03                                  # NASA/TM-20240001217, mean speed at a 6 s delay [78]
        check(measured_kmh < vmax(a_r2, earth, 10.0) * 3.6, "NASA's measured teleoperation speed at 6 s lies inside the cap")
        return (f"On the Moon g = {num(g, 2)}{NB}m/s<sup>2</sup>, so friction allows a = &mu;g = "
                f"{num(a_fric, 2)}{NB}m/s<sup>2</sup> on the flat at &mu; = {num(mu, 2)}; R2 uses the smaller of that "
                f"and the {num(S.B_MIN_FLAT, 1)}{NB}m/s<sup>2</sup> service brake, and d<sub>0</sub> = 0 inside the "
                f"sight distance. With {num(S.B_MIN_FLAT, 1)}{NB}m/s<sup>2</sup> and 20{NB}m of clear sight, a vehicle "
                f"that reacts on board after {num(on, 0)}{NB}s may drive at {kmh(vmax(a_r2, on, 20.0))}; one whose driver "
                f"is on Earth and reacts after {num(earth, 0)}{NB}s, the middle of the 4 to 8{NB}s delays NASA tested "
                f"[78], at {kmh(vmax(a_r2, earth, 20.0))}. With 10{NB}m of sight the two caps are "
                f"{kmh(vmax(a_r2, on, 10.0))} and {kmh(vmax(a_r2, earth, 10.0))}, and with the friction limit alone "
                f"(a = {num(a_fric, 2)}{NB}m/s<sup>2</sup>) at 20{NB}m they are {kmh(vmax(a_fric, on, 20.0))} and "
                f"{kmh(vmax(a_fric, earth, 20.0))}. NASA's simulator study measured a mean of {num(measured_kmh, 2)}{NB}km/h "
                f"at a 6{NB}s delay [78], below these caps, which is consistent with them and validates nothing. "
                f"At long delays the term a{NB}t<sub>r</sub> dominates and "
                f"friction hardly matters; at short delays it does. R2 computes the distance as the proposition "
                f"does, at constant speed through the reaction time; R1's gap lets the follower accelerate at "
                f"a<sub>acc</sub> through it, which is the more cautious. The same formula gives the caution speed "
                f"of the lost-link rule (Section 3.11). A vehicle that enters a segment marked unconfirmed may find "
                f"a stopped vehicle in it, so it drives no faster than v<sub>max</sub> for its own perception range "
                f"d<sub>p</sub>, with the static margin d<sub>0</sub> = {m_(S.D0_M, 0)} kept: "
                f"{kmh(vmax(a_r2, on, 10.0, S.D0_M))} for d<sub>p</sub> = 10{NB}m, {kmh(vmax(a_r2, on, 20.0, S.D0_M))} "
                f"for 20{NB}m, and the 15{NB}km/h class limit from {m_(dp15, 0)} on, with the on-board reaction time "
                f"and the service brake on the flat. No model in this paper has run that speed.")
    fill("P2-PROP3-NUMBERS", prop3, "safety.py")

    def prop4():
        rho, aacc, bmin, bmax, d0 = S.RHO_S, S.A_ACC, S.B_MIN_FLAT, S.B_MAX, S.D0_M
        v_crit = math.sqrt(2.0 * bmax * d0)
        v15 = 15.0 / 3.6
        brick = v15 * rho + 0.5 * aacc * rho ** 2 + (v15 + rho * aacc) ** 2 / (2.0 * bmin)
        dmin = float(S.rss_dmin(v15, v15, bmin)) - d0
        check(abs((brick - dmin) - v15 ** 2 / (2.0 * bmax)) < 1e-9, "the dead-stop shortfall is the leader's braking distance")
        check(abs(dmin - 12.5) < 0.05, "Table 2's gap at 15 km/h (12.5 m + d0) is reproduced")
        out = (f"With b<sub>max</sub> = {num(bmax, 1)}{NB}m/s<sup>2</sup> and d<sub>0</sub> = {m_(d0, 0)} the final "
               f"gap is negative for a leader faster than {num(v_crit, 2)}{NB}m/s ({kmh(v_crit)}); at 15{NB}km/h the "
               f"shortfall is {m_(v15 ** 2 / (2.0 * bmax) - d0, 1)}. A follower that keeps its own full stopping "
               f"distance, {m_(brick, 1)} + d<sub>0</sub> at 15{NB}km/h in place of {m_(dmin, 1)} + d<sub>0</sub>, "
               f"needs no assumption about the leader; we did not run that rule.")
        j = getattr(c.r, "e44j", None)
        if j is not None:
            t9 = j["types"]["9"]
            others = [k for k in j["types"] if k != "9" and j["types"][k]["violations"] > 0]
            check(not others and t9["violations"] > 0, "the only encounter type with violations is type 9, the case outside assumption (vii)")
            out += (f" E44 found the case: in {cnt(t9['violations'])} of {cnt(t9['n'])} encounters with a nonconforming "
                    f"vehicle the follower came inside the {m_(d0, 0)} static margin, and in "
                    f"{cnt(t9['violations_by_kind']['viol_contact'])} it touched, all "
                    f"with a leader stopped dead by a fault (Section 5.6).")
        # (vii) also fails for a conforming leader that brakes on an uphill grade (the referee's M9)
        up = uphill()
        out += (f"</p>" + chr(10) + chr(10) + f"<p>Assumption (vii) also fails for a vehicle that breaks no rule. "
                f"Guaranteed braking is b = min(b<sub>service</sub>, &mu;g{NB}cos{NB}&theta;) &minus; g{NB}sin{NB}&theta; "
                f"with &theta; positive downhill, so a leader that brakes fully on an uphill grade decelerates at "
                f"b<sub>service</sub> + g{NB}sin|&theta;|, which exceeds b<sub>max</sub> = {num(bmax, 1)}{NB}m/s<sup>2</sup> "
                f"on grades steeper than {num(up.lim_moon, 1)}&deg; on the Moon and {num(up.lim_mars, 1)}&deg; on Mars "
                f"(where the service brake binds; at &mu; = {num(up.mu_lo, 1)} on the Moon friction binds and the "
                f"grade is {num(up.lim_moon_fric, 1)}&deg;). The steepest slope on the base's routes is "
                f"{num(up.slope_max, 1)}&deg;. By the formulas above, at 15{NB}km/h a follower at exactly "
                f"d<sub>min</sub> behind a leader that brakes fully on that grade ends {m_(up.gap_moon, 1)} from it "
                f"on the Moon: inside the {m_(d0, 0)} static margin, which is a hard violation by this paper's own "
                f"definition, with no fault and no rule broken. At Mars gravity on the same grade the final gap is "
                f"{m_(up.gap_mars, 1)}. This is a calculation; " + c.awaited("uphill").replace("No encounter", "no encounter")
                + f" Part (b) is therefore established for the flat and for downhill grades only, which is where the "
                f"encounters were driven, and the remedy, b<sub>max</sub> taken on the slope or the full-stopping-"
                f"distance gap above, is not in the rule. Two more things are assumed without being listed. Part (b) "
                f"takes the follower to know the true gap and the leader's speed; under position error the widened "
                f"gap d<sub>0</sub> + k{NB}b<sub>AB</sub> of Section 3.9 is meant to cover that, and the encounters "
                f"did not exercise it. And part (a) is close to the definition of the rule: (iii) assumes that a "
                f"vehicle has left by the end of its window, which a vehicle disabled inside the segment has not. "
                f"That case is outside (a) as well as (b). What covers it is the lost-link rule of Section 3.11: the "
                f"segment stays reserved, is marked unconfirmed, and is entered only at the caution speed of "
                f"Proposition 3.")
        return out

    def uphill():
        """Where assumption (vii) of Proposition 4 fails for a conforming leader: the uphill grade above which full
        braking exceeds b_max, and the final gap of a follower at exactly d_min at 15 km/h on the steepest route slope.
        Everything from lunarsim/atc/safety.py and results/ATC_roads_corridor.json."""
        rho, aacc, bsv, bmax, d0 = S.RHO_S, S.A_ACC, S.B_MIN_FLAT, S.B_MAX, S.D0_M
        slope_max = float(c.r.k["slope_at_sample_percentiles_deg"]["1.0"])
        v = 15.0 / 3.6

        def b_up(theta, g, mu):
            return float(S.b_guaranteed(-theta, mu, g))           # theta > 0 is downhill in safety.py

        def limit(g, mu):
            lo, hi = 0.0, 45.0
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                lo, hi = (mid, hi) if b_up(mid, g, mu) <= bmax else (lo, mid)
            return lo

        def gap(theta, g, mu):
            b = b_up(theta, g, mu)
            dmin = float(S.rss_dmin(v, v, b))                      # the follower's own guaranteed braking on the grade
            stop_f = v * rho + 0.5 * aacc * rho ** 2 + (v + rho * aacc) ** 2 / (2.0 * b)
            return dmin + v * v / (2.0 * b) - stop_f
        mu, mu_lo = S.MU_DEFAULT, 0.3
        f = SimpleNamespace(lim_moon=limit(S.G_MOON, mu), lim_mars=limit(S.G_MARS, mu), mu_lo=mu_lo,
                            lim_moon_fric=limit(S.G_MOON, mu_lo), slope_max=slope_max,
                            gap_moon=gap(slope_max, S.G_MOON, mu), gap_mars=gap(slope_max, S.G_MARS, mu))
        check(abs(f.lim_moon - math.degrees(math.asin((bmax - bsv) / S.G_MOON))) < 0.01
              and abs(f.lim_mars - math.degrees(math.asin((bmax - bsv) / S.G_MARS))) < 0.01,
              "the uphill grade at which full braking reaches b_max is asin((b_max - b_service) / g)")
        check(f.lim_mars < f.lim_moon < f.lim_moon_fric < slope_max, "the base's steepest route slope is above the grade at which assumption (vii) fails")
        check(abs(gap(f.lim_moon, S.G_MOON, mu) - d0) < 1e-3 and gap(0.0, S.G_MOON, mu) > d0,
              "at the grade where full braking equals b_max the same computation gives the static margin, as the proof says, and more on the flat")
        check(0 < f.gap_mars < f.gap_moon < d0, "on the steepest route slope uphill the final gap is inside the static margin on both bodies, without contact")
        return f
    c.uphill = uphill
    fill("P2-PROP4-NUMBERS", prop4, "safety.py")

    def prop5():
        a3 = 1e-3
        z = ND.inv_cdf(1.0 - a3 / 2.0)
        g1, g2 = chi2_1_quantile(a3), -2.0 * math.log(a3)
        d90, d99 = z + ND.inv_cdf(0.9), z + ND.inv_cdf(0.99)
        check(abs(chi2_1_power(d90, a3) - 0.9) < 1e-3 and abs(chi2_1_power(d99, a3) - 0.99) < 1e-3,
              "the detectable errors of Proposition 5 give the stated detection probabilities")
        check(abs(g1 - 10.83) < 0.005 and abs(g2 - 13.82) < 0.005, "the thresholds of research note 03 E5 are reproduced")
        s_nav, s_r = 2.0, D["uwb_sigma_m"]                    # sigma_nav of R9 (Table 2: 3 sigma_nav + 5 m = 11 m)
        s_v = math.sqrt(s_r ** 2 + 2.0 * s_nav ** 2)
        e_conf = 3.0 * s_nav + 5.0
        check(z * s_v < e_conf < d90 * s_v, "R9's fixed tolerance lies between the test's threshold and its 90 % detectable error")
        fa35, det35 = k_of_n(3, 5, a3), k_of_n(3, 5, 0.9)
        out = (f"For one range and &alpha; = 10<sup>{MINUS}3</sup>, &gamma; = {num(g1, 2)} (z = {num(z, 2)}); for a range "
               f"and a bearing, &gamma; = {MINUS}2{NB}ln{NB}&alpha; = {num(g2, 2)}. A report wrong by b along the line "
               f"of sight is flagged with probability 0.9 once b reaches {num(d90, 2)}{NB}&sigma;<sub>v</sub> and with "
               f"0.99 at {num(d99, 2)}{NB}&sigma;<sub>v</sub>. With navigation errors of {m_(s_nav, 0)} on both "
               f"vehicles and a ranging error of {m_(s_r, 1)}, &sigma;<sub>v</sub> = {m_(s_v, 2)}: the threshold is "
               f"{m_(z * s_v, 1)} and the error found nine times in ten is {m_(d90 * s_v, 1)}; R9's fixed tolerance "
               f"of {m_(e_conf, 0)} lies between them. If three of the last five tests must be flagged, and the "
               f"tests are independent, a false alarm has probability {c.sci(fa35)} per window and an error flagged "
               f"with 0.9 per test is declared with {num(det35, 3)}.")
        try:
            d = c.e56f()
            thr = d["thresholds_from_validation"]["chi2_step"]["day"][0]
            theory = chi2_1_quantile(1.0 / 86400.0)
            check(abs(thr - theory) / theory < 0.05, "E56's validation threshold for one false alarm per pair-day is within 5 % of the chi-square law's value for one exceedance in 86,400 tests")
            check(c.e56fa("ood", "chi2_step") > 100, "with a wrong claimed variance the per-step test's false alarms rise a hundredfold")
            out += (f" E56 bears on the assumption twice. At one report a second, one false alarm a day is "
                    f"&alpha; = 1/86,400 and &gamma; = {num(theory, 1)}; the threshold found on validation data, "
                    f"with none of the Gaussian argument, was {num(thr, 1)}. That is one point at which the two "
                    f"tails cross and not a test of the law: at the lower thresholds the same test alarmed less "
                    f"often than Gaussian innovations would (Section 5.11). And when the true errors were larger "
                    f"than the variance the filter claimed, the same threshold gave "
                    f"{num(c.e56fa('ood', 'chi2_step'), 0)} false alarms per pair-day (Section 5.11): the false-alarm "
                    f"rate is only as good as S.")
        except Pending:
            pass
        try:
            d5 = c.e55f()
            t = c.e55rule("test")
            indep = 86400.0 * d5["integrity"]["k_of_n_false_alarm"]["0.001"]
            check(t["fa_per_pair_day"] > 20 * indep, "E55: the 3-of-5 rule's false alarms exceed the independent-test value (Proposition 5's last clause assumes independence)")
            out += (f" The independence in the three-of-five clause does not hold on those streams either: E55 "
                    f"measured {num(t['fa_per_pair_day'], 2)} false alarms per pair-day for the rule, against "
                    f"{num(indep, 4)} for independent tests.")
        except Pending:
            pass
        return out
    fill("P2-PROP5-NUMBERS", prop5, "E56")

    def prop7():
        f = c.e55facts16()
        runs_ok = sum(x["runs"] for x in f.ok)
        lo = min(x["safe_share"] for x in f.over)
        hi = max(x["safe_share"] for x in f.over)
        ag = max(x["agreement_share"] for x in f.ok)
        robust_runs = sum(x["runs_robust"] for x in f.all if str(x["robust_basis"]).startswith("exact"))
        exact_runs = sum(x["runs"] for x in f.all if str(x["robust_basis"]).startswith("exact"))
        return (f"E55 tested part (a). In all {cnt(runs_ok)} runs with F at least the number of faulty rovers, "
                f"every honest value stayed inside the first honest range at every step, whether or not the mesh "
                f"was robust; with two faulty rovers and F = 1, where the premise can fail, the range held in only "
                f"{pc(lo, 0)} to {pc(hi, 0)} of runs, by cell. Part (b) is stated from [72] and E55 does not test "
                f"its sufficiency: only {cnt(robust_runs)} of the {cnt(exact_runs)} meshes small enough for an "
                f"exact check were (2F+1)-robust, and agreement was reached in at most {pc(ag, 0)} of runs in any "
                f"cell in which F covered the faulty rovers (Section 5.11).")
    fill("P2-PROP7-NUMBERS", prop7, "E55")

    def prop6():
        d = c.e51f()
        k = d["constants"]
        g = k["guard_s"]
        y_hi = k["classes"]["crystal"]["y_hi"]
        hold = d["holdover"]["crystal"]["road-segment reservation (0.1 s)"]
        check(abs(hold["budget_s"] - g) < 1e-12 and abs(g / (0.95 * y_hi) - hold["analytic_y95_s"]) / hold["analytic_y95_s"] < 1e-3,
              "the holdover in the E51 file is the guard divided by the 95th-percentile frequency error")
        guards = {"conflicts_guard_0.01": 0.01, "conflicts_guard_0.1": 0.1, "conflicts_guard_1": 1.0}
        n_in, bad, by = 0, 0, {}
        for r in d["rows"]:
            if r["class"] == "perfect":
                continue
            for key, gg in guards.items():
                if r["max_abs_clock_s"] <= gg:
                    n_in += 1
                    bad += int(r[key] != 0)
                    by[(r["class"], gg)] = by.get((r["class"], gg), 0) + 1
        n_cs = sum(v for (k, _), v in by.items() if k == "csac")
        n_cr1 = by.get(("crystal", 1.0), 0)
        check(n_cs + n_cr1 == n_in and not any(k == "crystal" and gg < 1.0 for k, gg in by),
              "the cells that meet Proposition 6's premise are atomic-clock cells and crystal cells with the 1 s guard; none is a crystal cell with the 0.1 s guard")
        c6 = c.e51row("crystal", 21600)
        check(n_in > 0 and bad == 0, "in every E51 cell whose largest clock error is within the guard, no conflict occurs (Proposition 6)")
        cr10 = c.e51row("crystal", 10)
        beyond = cr10["max_abs_clock_s"] > g and cr10["conflicts_guard_0.1"] == 0
        out = (f"A clock with frequency error y, resynced every &tau; to a residual r, has |x| &le; |r| + |y|&tau;, so "
               f"it stays within g while &tau; &le; (g {MINUS} |r|)/|y|: for g = {num(g, 1)}{NB}s and the crystal's "
               f"95th-percentile frequency error that is {num(hold['analytic_y95_s'] / 3600.0, 1)}{NB}h, and the "
               f"drawn clocks of E51 held it for {num(hold['p5_over_vehicles_s'] / 3600.0, 1)}{NB}h. In all "
               f"{cnt(n_in)} cells of E51 in which the largest clock error was within the guard, on the two time "
               f"scales, no conflict occurred, as the proposition requires: {cnt(n_cs)} atomic-clock cells and "
               f"{cnt(n_cr1)} crystal cells with the 1{NB}s guard. No crystal cell with the {num(g, 1)}{NB}s guard "
               f"is among them, because vehicles out of radio reach miss their resyncs, so the zero conflicts that "
               f"Section 5.10 reports for that guard lie outside this proposition: at the "
               f"{interval_name(21600)} resync the largest error was {num(c6['max_abs_clock_s'], 2)}{NB}s and the "
               f"worst pair closed {num(c6['worst_close_s'], 3)}{NB}s of the {num(2 * g, 1)}{NB}s between its windows.")
        if beyond:
            out += (f" The premise is sufficient, not necessary: at a {interval_name(10)} resync the crystal's largest "
                    f"error was {num(cr10['max_abs_clock_s'], 2)}{NB}s, on vehicles out of radio reach, yet the "
                    f"clocks closed no gap between two conflicting reservations by more than "
                    f"{num(cr10['worst_close_s'] * 1e6, 0)}{NB}&micro;s, because those vehicles held no reservation "
                    f"next to an opposing one at the time. That zero is an observation on {cnt(len(d['seeds']))} "
                    f"seeds; the guarantee is the proposition's.")
        return out
    fill("P2-PROP6-NUMBERS", prop6, "E51")


# ---------------------------------------------------------------------------------------------------------
# abstract, introduction, discussion, limitations and conclusion: the clauses that carry Phase 6
# ---------------------------------------------------------------------------------------------------------
def add_front(c):
    V, fill, check, Pending = c.V, c.fill, c.check, c.Pending
    num, h_, pc, cnt, words, NB, PCT = c.num, c.h_, c.pc, c.cnt, c.words, c.NB, c.PCT
    m_ = c.m_
    from lunarsim.atc import pnt as PN
    from lunarsim.atc import safety as S
    D = PN.DEFAULTS

    def e44_facts():
        j, mc = getattr(c.r, "e44j", None), getattr(c.r, "e45j", None)
        if j is None or mc is None:
            raise Pending("E44 or E45 has not landed")
        viol = sorted(int(k) for k, t in j["types"].items() if t["violations"] > 0)
        states = sum(m["states"] for m in mc["models"].values())
        check(viol == [9], "the one encounter type with violations in the main run is type 9, the dead-stopped vehicle")
        check(c.fresh_types() == [6] and c.fresh()["types"]["6"]["fresh_seeds"]["violations"] == 1,
              "on fresh seeds one landing-closure encounter (type 6) left a vehicle inside a closed zone")
        rf = c.ring("E44")
        check(rf["rate"][False] > 0, "the ring of one-lane segments deadlocked under the exit rule as written")
        return 12 - len(viol) - len(c.fresh_types()), rf, states

    def h7_short():
        clean, rf, states = e44_facts()
        up = c.uphill()
        check(up.gap_moon < S.D0_M, "by calculation the gap rule fails behind a leader braking uphill")
        n6 = c.fresh()["types"]["6"]["fresh_seeds"]["n"]
        return (f"The safety program allowed no violation in {words(clean)} of twelve encounter types, all flat or "
                f"downhill: a vehicle that stops dead in a one-lane segment defeats the gap rule, as does, "
                f"by calculation, a leader braking uphill, and one landing closure in {cnt(n6)} left a vehicle "
                f"inside the zone. One-lane rings deadlocked in "
                f"{pc(rf['rate'][False], 1)} of encounters.")
    fill("P2-H7-ABSTRACT-SHORT", h7_short, "E44")

    def facts():
        """The Phase 6 numbers the summary clauses share, with the checks their fixed wording needs."""
        s, d51, d56 = c.e50f(1), c.e51f(), c.e56f()
        f = SimpleNamespace()
        f.near = c.e50st(1, "dr+ranging", "near")
        f.away = c.e50st(1, "dr+ranging+fixes", "away")
        f.nf = c.e50near(1)
        f.rd = c.e50readings(1)
        f.all_p95 = f.rd.rd["e"]["in_p95_m_mean"]
        check(f.all_p95 > 5 * S.D0_M and f.rd.rd["e"]["seeds_inside_budget"] == 0,
              "within radio range of the base beacons, the registered wording, ranging does not hold the margin in any seed")
        f.h9, f.h10 = s["h9"]["1"], s["h10"]
        check(f.h9["ranging_near_supported"] and not f.h9["fixes_away_supported"],
              "ranging holds the margin where two beacons are in line of sight and terrain fixes do not hold it away from the base (abstract, introduction, conclusion)")
        f.gap = s["delay"]["1"]["margin_layered_minus_perfect"]
        check(0 < f.gap["mean"] < 0.05, "the widened windows of the layered margin cost under 0.05 h per delivery at 1x")
        f.stop = s["errors"]["1"]["dr+ranging+fixes"]["fix_stop_h_per_month"]["mean"]
        f.b = c.e50bf()
        f.bd = f.b["metrics"]["delay_mean_h"]
        f.bpct = f.bd["diff_mean"] / f.bd["without_stop_time"]
        check(f.bd["diff_mean"] > 20 * f.gap["mean"], "with the terrain-fix stops in the model the delay cost is far above that of the widened windows")
        f.guard = d51["constants"]["guard_s"]
        f.c6 = c.e51row("crystal", 21600)
        check(d51["h11"]["supported"] and d51["h11"]["intervals_meeting_both"][-1] == 21600 and f.c6["conflicts_guard_0.1"] == 0
              and f.c6["max_abs_clock_s"] > f.guard,
              "with the 0.1 s guard a crystal resynced within six hours causes no reservation conflict, with clocks outside the guard")
        f.npar = d56["model"]["n_params"]
        a = c.e56h15("chi2_step", "drift")
        f.drift_gain = -a["delay_median_diff_s"]["value"]
        check(a["delay_median_diff_s"]["ci95"][1] < 0, "the network finds slow drifts earlier than the per-step chi-square test")
        f.miss = 1.0 - max(c.e56rec("test", k, "drift") for k, _ in DETECTORS)
        f.ood_j, f.ood_d = c.e56rec("ood", "net", "jump"), c.e56rec("ood", "net", "drift")
        f.fa_mult = {k: c.e56fa("ood", k) / c.e56fa("test", k) for k, _ in DETECTORS}
        check(min(f.fa_mult.values()) > 5, "out of distribution no detector keeps its false-alarm rate (each rises more than fivefold)")
        return f

    def abstract_clause():
        f = facts()
        return (f"Without satellites, ranging held position error inside the {m_(S.D0_M, 0)} margin where "
                f"two beacons were in sight ({pc(f.nf.share, 0)} of driving) but not over the registered radio "
                f"range ({m_(f.all_p95, 0)}); terrain fixes left "
                f"{m_(f.away['mean'], 0)} elsewhere, and their stops, not the reservation margins, set the cost: "
                f"{h_(f.bd['diff_mean'], 2)} per delivery ({pc(f.bpct, 1)}, a lower bound). With a "
                f"{num(f.guard, 1)}{NB}s guard, clocks up to {num(f.c6['max_abs_clock_s'], 2)}{NB}s off caused no "
                f"conflict in {cnt(f.c6['conflict_pairs_checked'])} reservation pairs, outside "
                f"the guarantee. A small network found slow position "
                f"drifts {num(f.drift_gain, 0)}{NB}s sooner than a chi-square test, but every detector missed at "
                f"least {pc(f.miss, 0)} of them and none kept its false-alarm rate with noisier sensors, so none "
                f"qualifies for the safety path.")
    fill("P2-P6-ABSTRACT-CLAUSE", abstract_clause, "E50, E51, E56")

    def ag_ok():
        """The largest share of runs that reached agreement among the cells in which F covers the faulty rovers,
        without and with the base mast (the referee's S11: the overall maximum is in a cell where the rule is unsafe)."""
        f16 = c.e55facts16()
        ag = max(x["agreement_share"] for x in f16.ok)
        mast = c.e55f().get("consensus_with_base_mast", {"cells": f16.all})["cells"]
        return ag, max(x["agreement_share"] for x in mast if x["F"] >= x["f"])

    def intro_paragraph():
        f = facts()
        s = c.e50f(1)
        d1 = s["delay"]["1"]
        e55 = ""
        try:
            t55, o55 = c.e55rule("test"), c.e55rule("ood")
            f16 = c.e55facts16()
            check(t55["fa_per_pair_day"] < 1.0 and not f16.h["supported"], "the rule as written stays under one false alarm per pair-day on the test set and H16 is not supported as written")
            ag, _ = ag_ok()
            e55 = (f" The protocol's own rule, the same test at its theoretical threshold with three of the last "
                   f"five tests flagged, gave {num(t55['fa_per_pair_day'], 2)} false alarms per pair-day on the test "
                   f"set without tuning and {num(o55['fa_per_pair_day'], 0)} with the noisier sensors; and trimmed "
                   f"averaging among rovers never left the range of the honest values while its parameter covered "
                   f"the faulty rovers, but converged in at most {pc(ag, 0)} of runs on our sparse mesh, so one "
                   f"registered hypothesis about it failed as written.")
        except Pending:
            pass
        e54 = c.e54facts
        out = (f"The second set of experiments removes four assumptions of the first: that every vehicle knows "
               f"where it is, that all clocks agree, that every message arrives and that every reported position "
               f"is true. They are replays of one recorded month; the encounters and the exhaustive check were not "
               f"run again. Without a navigation satellite service, ranging to four beacons kept the 95th "
               f"percentile of position error at {m_(f.near['mean'], 1)}, inside the {m_(S.D0_M, 0)} the rules set "
               f"aside, where two or more beacons were in line of sight. That is {pc(f.nf.share, 0)} of the driving, "
               f"and a reading of the registered &ldquo;within radio range of the base beacons&rdquo; that we chose "
               f"after the results; within radio range as registered, which is all of the driving, the error was "
               f"{m_(f.all_p95, 1)} and the clause failed in every seed. "
               f"Terrain fixes left {m_(f.away['mean'], 0)} away from the base, so one clause of the positioning "
               f"hypothesis failed and the verdict on another depends on the reading (Section 5.9). A reservation "
               f"widened by the vehicle's own 95{PCT} bound, "
               f"{num(d1['margin_layered_margin_h_mean']['mean'] * 3600, 0)}{NB}s at each end with the layered "
               f"estimate, changed delay per delivery by {h_(f.gap['mean'], 3, sign=True)}. The stops for terrain "
               f"fixes that the estimate needs, {h_(f.stop, 0)} a month or {pc(f.stop / f.nf.drive_h, 0)} of the "
               f"fleet's driving time, raised it by {h_(f.bd['diff_mean'], 2)} ({pc(f.bpct, 1)}) when a follow-up "
               f"run put them into the logistics model, and that figure is a lower bound. The count of reservation "
               f"overlaps, which we first read as a safety result, is fixed by the design and is reported only as a "
               f"count. With a guard of {num(f.guard, 1)}{NB}s on each reservation a crystal clock resynced within "
               f"six hours caused no conflict in {cnt(f.c6['conflict_pairs_checked'])} conflicting pairs; this is an "
               f"observation outside the guarantee we prove, since clocks out of radio reach were up to "
               f"{num(f.c6['max_abs_clock_s'], 2)}{NB}s off (Section 5.10).</p>" + chr(10) + chr(10)
               + f"<p>Message custody kept reservation grants from being lost, against a baseline that by its "
               f"assumed timing sent each grant once. A silent vehicle's segment is not released: it is marked "
               f"unconfirmed and may be entered only at caution speed, a rule adopted after an internal review and "
               f"not yet run, and {cnt(e54.unconf)} of the month's {cnt(e54.n_res)} reservations ended with their "
               f"holder unheard (Section 5.12). A network of {cnt(f.npar)} parameters found wrong position reports "
               f"sooner and more often than the chi-square test on held-out data at the same nominal false-alarm "
               f"rate; every detector missed at least {pc(f.miss, 0)} of slow drifts; and when the sensors were "
               f"noisier than in training no detector kept its false-alarm rate, so none is qualified for the "
               f"safety path on this evidence (Section 5.11).{e55} Seven propositions in Appendix A state what "
               f"follows from the rules by argument alone, each with its assumption, and Section 8 lists every "
               f"claim as proved, tested, calculated from assumed inputs, assumed or not yet tested.")
        return out
    fill("P2-P6-INTRO-PARAGRAPH", intro_paragraph, "E50, E51, E56")

    def discussion_position():
        f = facts()
        s = c.e50f(1)
        d1 = s["delay"]["1"]
        check(2.5 < f.away["mean"] / S.D0_M < 3.5, "away from the base the error with terrain fixes is about three times the margin")
        out = (f"The later experiments asked what the rules need from navigation, from clocks and from the honesty "
               f"of reports. On position the answer divides at the edge of the beacons' coverage. Where two or more "
               f"beacons are in line of sight, {pc(f.nf.share, 0)} of the driving, two-way ranging keeps a vehicle "
               f"within the {m_(S.D0_M, 0)} that R1 already sets aside. That is a reading we chose after the "
               f"results. Under the registered wording, within radio range of the base beacons, the error is "
               f"{m_(f.all_p95, 1)} and the second clause of H9&prime; fails in every seed; with one or more "
               f"beacons in sight it is {m_(f.rd.rd['b']['in_p95_m_mean'], 1)} and within 1{NB}km of the mast "
               f"{m_(f.rd.rd['c']['in_p95_m_mean'], 1)}. Ranging to four beacons at the base, then, holds the "
               f"margin only where two of them are seen at once. Elsewhere terrain fixes leave a 95th-percentile error three times the "
               f"margin (Table 9); the weak places are the dark legs, where fix opportunities are "
               f"{m_(D['fix_spacing_dark_m'], 0)} apart and {pc(D['fix_fail_dark'], 0)} of fixes fail, and the "
               f"loose slopes, where dead reckoning drifts {pc(D['dr_loose'], 0)}. What a margin sized by each "
               f"vehicle's own bound buys in safety we cannot yet say. Proposition 2 guarantees disjoint windows "
               f"while each error stays inside its bound and the vehicle passes the ends of the segment at speed, "
               f"and E50 counted how often the filed bound was exceeded (Table 10). The count of overlaps without a "
               f"margin is fixed by the way back-to-back windows are filed and measures no hazard, and the "
               f"durations and distances that would measure one have not been computed. What the margin costs is "
               f"clearer. With the layered estimate it is "
               f"{num(d1['margin_layered_margin_h_mean']['mean'] * 3600, 0)}{NB}s at each end and the widened "
               f"windows cost {h_(f.gap['mean'], 3)} per delivery at today's fleet")
        try:
            grows, cl = c.e50gap4()
            d4 = s["delay"]["4"]
            check(d4["margin_dr_minus_perfect"]["ci"][0] > 0, "at 4x the dead-reckoning margin costs delay, by an interval that excludes zero")
            out += (f"; with dead reckoning alone it is {num(d1['margin_dr_margin_h_mean']['mean'] * 60, 0)}{NB}min "
                    f"at today's fleet, where its cost of {h_(d1['margin_dr_minus_perfect']['mean'], 2)} was not "
                    f"resolved, and {num(d4['margin_dr_margin_h_mean']['mean'] * 60, 0)}{NB}min at four times the "
                    f"fleet, where it cost {h_(d4['margin_dr_minus_perfect']['mean'], 1)} per delivery. ")
        except Pending:
            out += ". "
        out += (f"The layered estimate, though, depends on stops for terrain fixes, {h_(f.stop, 0)} a month, and with "
                f"those in the logistics model the delay per delivery rose by {h_(f.bd['diff_mean'], 2)}, "
                f"{pc(f.bpct, 1)}, a lower bound because the model inserted only part of the stop time (Section "
                f"5.9). The cost of positioning without satellites is the stops, not the margins. ")
        failed = [not f.h10["layered_within_supported"], None, not f.h10["dr_larger_supported"]]
        try:
            failed[1] = not c.e50gap4()[0]
        except Pending:
            pass
        if failed[0] is False and failed[1] and failed[2]:
            runs, _ = c.e50frames()
            r1 = runs[runs["mult"] == 1]
            dd = (r1[r1["variant"] == "margin_dr"].set_index("seed")["delay_mean_h"]
                  - r1[r1["variant"] == "perfect"].set_index("seed")["delay_mean_h"])
            n_pos = int((dd > 0).sum())
            check(n_pos > 0.7 * len(dd), "the dead-reckoning margin was the costlier in most seeds at 1x")
            out += (f"Two of the three clauses of H10&prime; were not supported, and the experiment resolved "
                    f"neither: at four times the fleet ten seeds do not settle the layered margin's difference, and "
                    f"at today's fleet the dead-reckoning margin cost more in {cnt(n_pos)} of {cnt(len(dd))} seeds "
                    f"while its mean could not be told from zero. The pre-registration said that a failure of "
                    f"H10&prime; would mean that position error sets traffic capacity [59]; these runs neither show "
                    f"that nor exclude it.")
        return out.strip()
    fill("P2-P6-DISCUSSION-POSITION", discussion_position, "E50")

    def discussion_time_integrity():
        f = facts()
        d51 = c.e51f()
        s = c.e50f(1)
        margin_s = s["delay"]["1"]["margin_layered_margin_h_mean"]["mean"] * 3600
        check(margin_s > 100 * f.guard, "the position margin is more than a hundred times the clock guard")
        ok1 = [i for i in c.e51intervals() if c.e51row("crystal", i)["max_abs_clock_s"] <= 1.0]
        check(ok1 and ok1[-1] == 21600, "a guard of 1 s covers the crystal's largest clock error up to a six-hour resync")
        cls, fa, rec = c.e56cls, c.e56fa, c.e56rec
        inno = [fa("ood", k) for k in ("chi2_step", "chi2_window", "cusum")]
        cu_l, cu_u = cls("ood", "long", "cusum", "jump", "fa_per_pair_day"), cls("ood", "uwb", "cusum", "jump", "fa_per_pair_day")
        ne_u = cls("ood", "uwb", "net", "jump", "fa_per_pair_day")
        small = [rec("ood_recalibrated", k, ft) for k, _ in DETECTORS for ft in ("jump", "drift")]
        e54 = ""
        try:
            x = c.e54facts
            e54 = (f" The lost-link experiment shows two things and prices neither in delay. A lost grant is a "
                   f"stopped vehicle, because R3 never assumes an unconfirmed reservation. The {pc(x.lost, 0)} of "
                   f"grants that drop and retry lost at a loss of 0.25 per hop is that loss itself: its retry "
                   f"interval is longer than a grant's lifetime, both assumed, so each grant was sent once, and "
                   f"three tries inside the lifetime would by arithmetic lose {pc(x.three, 1)}. Custody removes the "
                   f"loss; the replay does not show that it is needed. And a silent vehicle is the usual case: "
                   f"along the month's contact plan vehicles had a radio path to the base in {pc(x.linked, 0)} of "
                   f"their driving time, and {cnt(x.unconf)} of {cnt(x.n_res)} reservations ended with their holder "
                   f"unheard. Under the rule as first written the base released those segments, which is unsafe when "
                   f"the holder is silent because it has failed inside one; under the rule as it now stands they "
                   f"are marked unconfirmed and entered only at caution speed. No logistics run contains the "
                   f"lost-link ladder. The fleets of E43 and E50 never turn back, the replay holds "
                   f"{num(x.returns, 0)} returns a month against {num(x.jobs, 0)} jobs, and the nearest thing that "
                   f"was priced, the strict reading of R7, cost {V['P2-R7-ATC-DIFF']} per delivery. The delay cost "
                   f"of the ladder and of caution-speed entry is therefore unknown and probably large.")
        except (Pending, AttributeError):
            pass
        e55 = ""
        try:
            t55, o55 = c.e55rule("test"), c.e55rule("ood")
            single = c.e55rule("test", "single@0.001")["fa_per_pair_day"]
            check(single > 10, "without persistence the theoretical threshold alarms many times a day")
            ag, mast_ag = ag_ok()
            check(max(ag, mast_ag) < 0.25, "agreement by trimmed averaging is rare on this mesh, with or without the base mast")
            e55 = (f" E55 adds two observations. The protocol's rule as written gave "
                   f"{num(t55['fa_per_pair_day'], 2)} false alarms per pair-day on the test set without tuning, "
                   f"because of its persistence clause: the same threshold alone alarmed in "
                   f"{num(single, 0)} minutes of a day. That rate rests on a handful of alarm-minutes and has no "
                   f"interval, and with the noisier sensors it was {num(o55['fa_per_pair_day'], 0)}. And "
                   f"agreement among rovers by trimmed averaging does not work on this terrain: the rule cannot be "
                   f"pushed outside the honest range while F covers the faulty rovers, and more links do not make "
                   f"up for an F that is too small (Section 5.11), but the honest rovers "
                   f"converged in at most {pc(ag, 0)} of runs, {pc(mast_ag, 0)} with the base mast as a "
                   f"node, because few of them hear three others. On this mesh a shared estimate, such as the "
                   f"position of a beacon or a hazard, cannot be left to averaging among rovers. Computing it at "
                   f"the base, with the trimmed mean kept as a fallback that cannot be pushed outside the honest "
                   f"range, is the design these results point to; it was not run.")
        except Pending:
            pass
        return (f"On time, clock quality matters for one-way ranging long before it matters on the roads, and the "
                f"protocol ranges two-way. The guard of {num(f.guard, 1)}{NB}s is less than a hundredth of the "
                f"position margin. With it a crystal resynced within six hours caused no conflict in "
                f"{cnt(f.c6['conflict_pairs_checked'])} pairs, but that is an observation and not the guarantee: "
                f"Proposition 6 needs every clock within the guard, clocks out of radio reach were up to "
                f"{num(f.c6['max_abs_clock_s'], 2)}{NB}s off, and the worst pair used "
                f"{pc(f.c6['worst_close_s'] / (2 * f.guard), 0)} of the two guards between its windows. A design "
                f"that wants the guarantee must size the guard to the largest clock error it tolerates; in this "
                f"sweep a guard of 1{NB}s covered the crystal's largest error up to a six-hour resync.{e54}</p>"
                + chr(10) + chr(10) + f"<p>On integrity, the network did what H15 (a) asked and more on "
                f"jumps and noise, at the same nominal false-alarm rate on held-out data. Out of distribution, when "
                f"the true sensor errors were larger than the filter claimed, no detector kept its false-alarm "
                f"rate, so their recalls there cannot be compared and no choice of detector follows from them. The "
                f"three innovation tests gave {num(min(inno), 0)} to {num(max(inno), 0)} false alarms per pair-day "
                f"and the network {num(fa('ood', 'net'), 0)}. A detector that alarms in most minutes meets most "
                f"faults by coincidence: in the long-range class, where the CUSUM alarmed in "
                f"{pc(cu_l / MIN_DAY, 0)} of fault-free minutes, it found {pc(cls('ood', 'long', 'cusum', 'jump'), 0)} "
                f"of the small jumps; in the short-range class, where it gave {num(cu_u, 0)} false alarms per "
                f"pair-day, it found {pc(cls('ood', 'uwb', 'cusum', 'jump'), 0)}, against the network's "
                f"{pc(cls('ood', 'uwb', 'net', 'jump'), 0)} at {num(ne_u, 1)}. The classical tests lost more of "
                f"their calibration than the network (the per-step test's rate rose "
                f"{cnt(round(f.fa_mult['chi2_step'], -2))} times, the network's {num(f.fa_mult['net'], 0)}), and "
                f"with thresholds reset to the nominal rate every detector found {pc(min(small), 0)} to "
                f"{pc(max(small), 0)} of the small jumps and slow drifts. R9 turns each false alarm into an "
                f"inflated volume and a delay, and no run prices false alarms at these rates, so failing towards "
                f"alarms is not shown to be the safe direction. On this evidence none of the detectors is "
                f"qualified for the safety path. What the chi-square test has is a threshold that follows from a "
                f"stated assumption (Proposition 5); what the experiment shows is that the assumption, the claimed "
                f"variance, is the thing to monitor. No detector helps with slow drifts, of which every one missed "
                f"{pc(f.miss, 0)} or more: a single range sees only the error along the line of "
                f"sight, and a second witness at another bearing is needed. No experiment here has two witnesses "
                f"cross-check one report.{e55}")
    fill("P2-P6-DISCUSSION-TIME", discussion_time_integrity, "E51, E54, E56")

    def conclusion_clause():
        f = facts()
        return (f"Without satellite navigation, ranging held position error inside the {m_(S.D0_M, 0)} margin "
                f"only where two beacons were in sight, not over the registered radio range; the stops for terrain fixes, not the widened "
                f"reservations, set the cost, {h_(f.bd['diff_mean'], 2)} per delivery as a lower bound; and no "
                f"detector of wrong position reports kept its false-alarm rate with noisier sensors.")
    fill("P2-P6-CONCLUSION-CLAUSE", conclusion_clause, "E50, E51, E56")

    def conclusion_safety_short():
        clean, rf, states = e44_facts()
        return (f"One safety program enforcing ten rules, tested in simulation, allowed no violation in "
                f"{words(clean)} of twelve encounter types, all flat or downhill; a vehicle that stops dead in a "
                f"one-lane segment and, by calculation, a leader braking uphill defeat the gap rule, one landing "
                f"closure in {cnt(c.fresh()['types']['6']['fresh_seeds']['n'])} left a vehicle inside the closed "
                f"zone, and a ring of one-lane segments can deadlock.")
    fill("P2-CONCLUSION-SAFETY-SHORT", conclusion_safety_short, "E44")

    def awaited_items():
        """The analyses that the referee round asked for and that have not landed: one phrase each (build_p2.AWAITED),
        plus the eight-times cells of E50 while results/E50_summary.json does not hold them."""
        items = [c.awaited(k, "phrase") for k in c.AWAITED]
        if not c.e50has8():
            items.append("the eight-times cells of E50")
        return items

    def join_list(items):
        return items[0] if len(items) == 1 else "; ".join(items[:-1]) + "; and " + items[-1]

    def awaited_limitation():
        items = awaited_items()
        if not items:
            return "Every analysis that the internal review of this paper asked for has been run."
        return (f"{words(len(items)).capitalize()} analyses that an internal review of this paper asked for have "
                f"not been run: {join_list(items)}. Each is named where its result belongs, and the claims that "
                f"depend on them are stated as open.")
    fill("P2-P6-AWAITED-LIMITATION", awaited_limitation, "status")

    def awaited_future():
        items = awaited_items()
        if not items:
            return "The analyses that the internal review asked for have all been run."
        return (f"The first items are the analyses named in the text as not run: {join_list(items)}.")
    fill("P2-P6-AWAITED-FUTURE", awaited_future, "status")

    def failed_sentence():
        s = c.e50f(1)
        h9, h10 = s["h9"]["1"], s["h10"]
        failed, other = [], []
        check(h9["dr_supported"] and not h9["fixes_away_supported"], "H9': the first clause is supported and the third is not")
        check(c.e50readings(1).rd["e"]["seeds_inside_budget"] == 0, "H9' clause 2 fails in every seed under the registered wording")
        failed.append("the third clause of H9&prime;, and its second under the registered wording, where it fails "
                      "in every seed and holds only under a reading chosen after the results (Section 5.9)")
        n10 = [not h10["layered_within_supported"], None, not h10["dr_larger_supported"]]
        try:
            n10[1] = not c.e50gap4()[0]
        except Pending:
            pass
        k10 = sum(1 for x in n10 if x)
        if k10:
            failed.append(f"{words(k10)} of the three clauses of H10&prime;, which the runs did not resolve (Section 5.9)")
        if c.e51f()["h11"]["supported"]:
            other.append("H11's registered rule was met, and it is reported as an observation, because one of its "
                         "two conditions could not have failed (Section 5.10).")
        else:
            failed.append("H11 (Section 5.10)")
        try:
            h14 = c.e54f()["h14"]
            if h14["difference_sf_ll_minus_drop_retry"]["ci"][1] < 0:
                other.append("H14's first clause was supported; its second is not testable as written and is "
                             "withdrawn as a result (Section 5.12).")
            else:
                failed.append("H14 (Section 5.12)")
        except Pending:
            pass
        b = c.e56h15("chi2_step", "jump")["delay_median_diff_s"]
        a = c.e56h15("chi2_step", "drift")["delay_median_diff_s"]
        bad15 = []
        if not a["ci95"][1] < 0:
            bad15.append("(a)")
        if not (-1.0 < b["ci90"][0] and b["ci90"][1] < 1.0):
            bad15.append("(b)")
        if bad15:
            failed.append("H15 " + " and ".join(bad15) + ", and out of distribution no detector kept its "
                          "false-alarm rate, so (d) compares recalls that are not comparable (Section 5.11)")
        try:
            if not c.e55f()["h16"]["supported"]:
                failed.append("H16 as written (Section 5.11)")
        except Pending:
            pass
        out = (f"Of the later hypotheses, these failed in whole or in part and are reported where they belong: "
               f"{join_list(failed)}. " + " ".join(other))
        return out.strip()
    fill("P2-P6-FAILED-SENTENCE", failed_sentence, "E50, E51, E54, E55, E56")


# ---------------------------------------------------------------------------------------------------------
# Table 13: proved, tested, assumed, not yet tested (one row per claim; statuses that depend on results are read)
# ---------------------------------------------------------------------------------------------------------
def add_pta(c):
    V, check, Pending = c.V, c.check, c.Pending
    num, h_, pc, cnt, NB, PCT = c.num, c.h_, c.pc, c.cnt, c.NB, c.PCT
    m_ = c.m_
    from lunarsim.atc import safety as S
    sup = lambda flag: "supported" if flag else "not supported"
    rows = []

    def add(claim, status, basis, where):
        rows.append([claim, status, basis, where])

    def tested(flag):
        return "Tested: " + sup(flag)

    def build():
        r = c.r
        j, mc = getattr(r, "e44j", None), getattr(r, "e45j", None)
        if j is None or mc is None:
            raise Pending("E44 or E45 has not landed")
        states = sum(m["states"] for m in mc["models"].values())
        n_drv = sum(t["n_driven"] for t in j["types"].values())
        clean = [k for k, t in j["types"].items() if t["violations"] == 0]
        t9, t5 = j["types"]["9"], j["types"]["5"]
        worst = max(j["types"][k]["bonferroni_bound"] for k in clean)
        # --- the rules, as checked in Phase 5 ---
        add("The rules allow no unsafe state, deadlock or livelock, and each of the three rule clauses removed (of R3, R5, R7) gives a counterexample; R6 and R10 were not removed",
            "Proved, by exhaustive search",
            f"E45: {cnt(states)} reachable states of four layouts with up to three vehicles. Assumption: the discrete model "
            "(cells, one landing, one crew member); larger layouts are not covered", "5.7")
        add(f"No hard violation in {c.words(len(clean))} of twelve encounter types in the main run",
            "Tested, on the flat and downhill only",
            f"E44: {cnt(n_drv)} driven encounters, one seed each; per-type bound at most {c.sci(worst)} (Bonferroni, 95{PCT}), "
            "for the generated distributions only. A hard violation is defined in Section 3.5 (for a following vehicle: "
            "contact or a gap inside the 5&nbsp;m static margin). The bounds of types 4, 5 and 6 are on the seeds used to "
            "find and fix defects, so those types were rerun on fresh seeds (next row)", "3.5, 5.6")
        fr = c.fresh()["types"]
        f6 = fr["6"]["fresh_seeds"]
        add("Types 4, 5 and 6 allow no hard violation on seeds never used before",
            "Tested: holds for types 4 and 5, fails for type 6",
            f"Rerun in simulation, {cnt(f6['n'])} encounters per type: types 4 and 5 none, bound "
            f"{c.sci(fr['4']['fresh_seeds']['bonferroni_bound'])} (Bonferroni) as in the main run; type 6 one encounter "
            f"with a vehicle inside a closed zone (a hold-and-wait between R5 and R3), limit on the weighted share "
            f"{c.sci(f6['bound_weighted'])} ({c.sci(f6['bonferroni_bound_weighted'])} Bonferroni). The request rule of "
            "change 9 of [43] was rerun on that one encounter only, which was then clean", "5.6, 6.1")
        add("A follower does not touch a leader that stops dead in a one-lane segment",
            "Tested: fails",
            f"E44 type 9: {cnt(t9['violations'])} of {cnt(t9['n'])} inside the static margin, {cnt(t9['violations_by_kind']['viol_contact'])} "
            "contacts. Proposition 4 names the assumption that fails (the leader brakes at no more than b<sub>max</sub>); "
            "the full-stopping-distance gap that would close it was not run", "5.6, A.4")
        up = c.uphill()
        add("A follower keeps clear of a conforming leader that brakes on an uphill grade",
            "Calculated from the rule's formulas: fails; not yet tested",
            f"Full braking uphill exceeds b<sub>max</sub> above {num(up.lim_moon, 1)}&deg; (Moon) and {num(up.lim_mars, 1)}&deg; "
            f"(Mars); on the {num(up.slope_max, 1)}&deg; route maximum the final gap at 15{NB}km/h is {m_(up.gap_moon, 1)} "
            f"(Moon), inside the static margin. " + c.awaited("uphill"), "A.4")
        rf = c.ring("E44")
        add("The exit-bay rule does not deadlock",
            "Proved for unbounded bays; tested with finite bays: fails on a ring",
            f"Logistics model: zero by construction ({V['P2-DEADLOCKS-TOTAL-N']} in {V['P2-N-RUNS-E43']} runs is a check of "
            f"the code). E44 type 5, ring encounters in which deadlock is judged: {pc(rf['rate'][False], 1)} under R3 as "
            f"written ({cnt(rf[False]['dl'])} of {cnt(rf[False]['judged'])}), {pc(rf['rate'][True], 1)} under a "
            f"keep-one-slot-free variant ({cnt(rf[True]['dl'])} of {cnt(rf[True]['judged'])}). Whether this "
            "base's roads hold such a ring: not determined", "5.1, 5.6, 6.1")
        h8 = r.f["H8"]["1"]["supported"]
        add("The rules add less than 5&#8239;% to delay per delivery at today's fleet (H8)",
            tested(h8), f"E43: 30 seeds, one year, &times;1 fleet; {V['P2-H8-X1-PCT']}, upper bound {V['P2-H8-X1-UPPER']}. "
            "Conditions: oracle dispatcher, reservations filed at commit and kept exactly, no lost-link procedure on the road", "3.4, 5.2")
        add("The cost of the rules rises with the fleet",
            "Tested (reported, not a confirmatory test)",
            f"E43: &times;2 (30 seeds, one year), &times;4 and &times;8 (10 seeds, {V['P2-HORIZON-X4-D']} and "
            f"{V['P2-HORIZON-X8-D']} days): {V['P2-H8-X2-PCT']}, {V['P2-H8-X4-PCT']}", "5.3")
        add("Referring cross-owner conflicts to Earth multiplies delay",
            "Tested; the two hours of staff time per conflict are assumed",
            f"E43: 30 seeds, two start years, &times;1 fleet: {V['P2-UNC-X1-RATIO-2028']} and {V['P2-UNC-X1-RATIO-2038']} "
            f"times the baseline. The staff time was not swept; the wait per conflict, {V['P2-UNC-X1-WAIT-PER-CONFLICT-H']}, "
            "is the gap between Earth windows; no local fallback", "5.4")
        add("Share of one-lane road, bay spacing", "Assumed, swept",
            f"Share 0 to {V['P2-SHARE-MAX-PCT']}, bays every 0.5 to 2{NB}km (E43, 30 seeds each)", "3.1, 5.5")
        add("Regolith braking friction, service brake, response time", "Assumed; friction swept",
            "Friction 0.3, 0.45 and 0.6 in E44; the service brake and the response time were not swept", "3.5")
        add("The rules hold at Mars gravity", "Tested on the flat only, where the encounters repeat the lunar ones",
            "E47: the lunar vehicles' brakes hold no steep downhill at Mars gravity, so sloped encounters were not driven",
            "5.8")
        # --- Phase 6 ---
        s = c.e50f(1)
        h9, h10 = s["h9"]["1"], s["h10"]
        n1 = len(s["seeds"]["1"])
        n4 = len(s["seeds"].get("4", []))
        n8 = len(s["seeds"].get("8", []))
        fleets = (f"{cnt(n1)} seeds at &times;1" + (f", {cnt(n4)} at &times;4" if n4 else "")
                  + (f", {cnt(n8)} at &times;8" if n8 else "; the &times;8 cells have not finished"))
        add("The standard deviation of dead-reckoning error reaches a margin m within a distance m/&sigma;<sub>&epsilon;</sub> (Proposition 1)",
            "Proved; illustrated",
            f"Assumption: a constant scale error and an independent random walk. E50, {fleets}: the 95th percentile is past "
            f"{m_(S.D0_M, 0)} in the first driving hour (H9&prime;, first clause: {sup(h9['dr_supported'])}); the run does "
            "not test the formula", "A.1, 5.9")
        nf = c.e50near(1)
        add("Ranging keeps position error inside the margin near the base (H9&prime;)",
            "Tested: depends on the reading of &ldquo;near the base&rdquo;",
            f"E50, {fleets}: {m_(h9['ranging_near_p95_m']['mean'], 2)} at the 95th percentile where two or more beacons are "
            f"in line of sight ({pc(nf.share, 0)} of driving steps), a reading chosen after the results; "
            f"{m_(c.e50st(1, 'dr+ranging')['mean'], 1)} within radio range of the base beacons, the registered wording "
            f"(all of the driving), where it fails in every seed; {m_(c.e50readings(1).rd['b']['in_p95_m_mean'], 1)} with "
            f"one or more beacons in sight and {m_(c.e50readings(1).rd['c']['in_p95_m_mean'], 1)} within 1{NB}km of the "
            "mast, inside in no seed", "5.9")
        try:
            fam = c.famf()
        except Pending:
            fam = None
        holm = lambda k: f"; Holm-adjusted p {num(fam.adj[k], 3 if fam.adj[k] < 0.1 else 2)}" if fam else ""
        none9 = fam is not None and list(fam.h["H9"]["clauses"].values())[2]["seeds_on_predicted_side"] == 0.0
        add("Absolute fixes keep position error inside the margin away from the base (H9&prime;)",
            tested(h9["fixes_away_supported"]),
            f"E50, {fleets}: {m_(h9['fixes_away_p95_m']['mean'], 1)} at the 95th percentile"
            + (", above the budget in every seed" if none9 else ""), "5.9")
        v1 = s["violations"]["1"]
        add("Reservations widened by k&times;bound/speed stay disjoint in true time (Proposition 2)",
            "Proved; the exceedance of the filed bound counted, not a test",
            f"Assumptions: each along-track error inside its bound at both ends of the window, and the vehicle passes each "
            f"end at the speed v (not true of a vehicle starting from rest). E50, {fleets}: "
            f"{num(v1['with_margin']['layered']['mean'], 2)} overlaps a month with the margin at &times;1. The simulation "
            "shifts windows by error over speed, the proposition's premise, so this is how often the filed bound was "
            "exceeded; whether each remaining overlap is an error outside a correctly computed bound is not shown", "A.2, 5.9")
        add("The count of reservation overlaps without a margin",
            "Calculated: a property of the count, not a safety measure",
            "A waiting vehicle's window starts where the conflicting one ends, so a back-to-back pair overlaps about half "
            f"the time whatever the error: {num(v1['no_margin']['dr+ranging+fixes']['mean'], 2)} a month at &times;1. "
            + c.awaited("overlaps"), "3.9, 5.9")
        add("The layered margin's delay is within 1.5 times the perfect-position delay at today's fleet (H10&prime;)",
            tested(h10["layered_within_supported"]),
            f"E50, {cnt(n1)} seeds, &times;1: ratio {num(h10['ratio_layered_over_perfect_1x'], 4)}; the registered margin "
            f"is larger than the spread between seeds; the delay leaves out the stops for terrain fixes", "5.9")
        try:
            grows, _ = c.e50gap4()
            add("The layered margin's cost grows at larger fleets (H10&prime;)",
                tested(grows) + "; not resolved",
                f"E50, {cnt(n4)} seeds, &times;4: {h_(h10['gap_by_mult']['4']['mean'], 2, sign=True)}"
                + (f"; {cnt(n8)} seeds, &times;8: {h_(h10['gap_by_mult']['8']['mean'], 2, sign=True)}" if n8 else
                   "; the &times;8 cells have not finished")
                + "; the spread between seeds is many times these differences", "5.9")
        except Pending:
            add("The layered margin's cost grows at larger fleets (H10&prime;)", "Not yet tested", "E50 at &times;4 and &times;8 not finished", "5.9")
        add("With dead reckoning alone the widened margin costs delay (H10&prime;)",
            tested(h10["dr_larger_supported"]) + " at &times;1 by the registered rule",
            f"E50, {cnt(n1)} seeds: {h_(s['delay']['1']['margin_dr_minus_perfect']['mean'], 2, sign=True)}, interval "
            "includes zero, though most seeds moved the same way; the &times;4 value excludes zero and is exploratory", "5.9")
        if fam:
            add("H10&prime; as one hypothesis of the confirmatory family",
                tested(fam.h["H10"]["holm"]["rejected_at_0.05"]),
                f"The three clauses joined (the largest clause p){holm('H10')}: the first clause holds, the other two do not",
                "5.9")
        try:
            bd = c.e50bf()["metrics"]["delay_mean_h"]
            add("The terrain-fix stops of the layered scheme raise delay per delivery",
                "Tested (exploratory, run after the first results)",
                f"E50b, {cnt(bd['n_seeds'])} seeds, &times;1: {h_(bd['diff_mean'], 2, sign=True)} "
                f"{c.ci(*bd['diff_ci95_bootstrap'], 2)}, {pc(bd['diff_mean'] / bd['without_stop_time'], 1)}; a lower bound, "
                "because the stops on repositioning drives are not in the model", "5.9, 7")
        except Pending:
            add("Delay with the terrain-fix stops counted", "Not yet tested", "E50b has not been run", "5.9, 7")
        add("R1's gap widened to d<sub>0</sub> + k&times;bound keeps followers apart under position error",
            "Not yet tested",
            "Implemented in the safety program and unit-tested (with a zero bound the check is unchanged); the encounters "
            "of E44 were not rerun with position error", "3.9")
        add("Maximum safe speed for a sight distance, braking and reaction delay (Proposition 3)",
            "Proved",
            "Assumption: constant guaranteed braking and an honest sight distance. The formula is the one R2 runs (checked "
            "by the build); driving with Earth in the loop and entry at caution speed were not simulated", "A.3")
        add("Non-overlapping reservations and the gap rule give no head-on meeting inside a one-lane segment and no rear-end contact (Proposition 4)",
            "Proved for the flat and downhill; tested there",
            "Assumptions (i) to (viii) of the proposition; E44 and E45 as above, with the failure of (vii) in type 9. (vii) "
            "also fails uphill for a conforming vehicle (row above), and a vehicle disabled inside a segment breaks (iii). "
            "Junctions, crew, merging and lateral contact are outside the proposition", "A.4")
        d56 = c.e56f()
        thr = d56["thresholds_from_validation"]["chi2_step"]["day"][0]
        add("Chi-square innovation test: threshold for a false-alarm rate, smallest error found (Proposition 5)",
            "Proved; the assumption does not hold on the simulated streams",
            f"Assumption: independent Gaussian errors with the claimed variance. E56: validation threshold {num(thr, 1)} "
            f"against {num(chi2_1_quantile(1 / 86400.0), 1)} from the law (one crossing point); at lower thresholds the "
            f"test alarms less often than the law gives; {num(c.e56fa('ood', 'chi2_step'), 0)} false "
            "alarms per pair-day when the claimed variance is wrong", "A.5, 5.11")
        d51 = c.e51f()
        add("Clocks within g of the base scale and a guard g cannot cause a reservation conflict (Proposition 6)",
            "Proved; no conflict in the cells that meet the premise",
            f"E51, {cnt(len(d51['seeds']))} seeds, &times;1: atomic-clock cells and crystal cells with the 1{NB}s guard. No "
            f"crystal cell with the {num(d51['constants']['guard_s'], 1)}{NB}s guard meets the premise", "A.6, 5.10")
        c6 = c.e51row("crystal", 21600)
        add("With a 0.1&nbsp;s guard a crystal clock resynced within six hours causes no reservation conflict (H11, first condition)",
            "Observed; outside Proposition 6",
            f"E51, {cnt(len(d51['seeds']))} seeds, &times;1: no conflict in {cnt(c6['conflict_pairs_checked'])} pairs with "
            f"clocks up to {num(c6['max_abs_clock_s'], 2)}{NB}s off; the worst pair used "
            f"{pc(c6['worst_close_s'] / (2 * d51['constants']['guard_s']), 0)} of the two guards", "5.10")
        add("A crystal's clock error adds more than the radio's noise to one-way ranging (H11, second condition)",
            "Calculated; could not have failed",
            "One nanosecond of clock error is 0.3&nbsp;m of one-way range; the protocol ranges two-way", "5.10")
        a = c.e56h15("chi2_step", "drift")["delay_median_diff_s"]
        b = c.e56h15("chi2_step", "jump")["delay_median_diff_s"]
        n = d56["dataset"]["test"]["fault_streams_by_type"]["drift"]
        basis56 = f"E56 test set: {cnt(n)} simulated faults per type, {c.words(len(d56['seeds']))} training seeds, one site"
        add("The network finds slow drifts sooner than the per-step chi-square test (H15 a)",
            "Tested: " + ("held" if a["ci95"][1] < 0 else "failed"), basis56 + holm("H15a"), "5.11")
        add("On jumps the network and the chi-square test are within one second (H15 b)",
            "Tested: " + ("held" if (-1 < b["ci90"][0] and b["ci90"][1] < 1) else "failed"), basis56, "5.11")
        below = c.e56rec("ood", "net", "jump") < c.e56rec("ood", "cusum", "jump")
        add("A detector keeps its false-alarm rate out of distribution (bears on H15 d)",
            "Tested: fails for every detector",
            "E56 out-of-distribution set (one shift: noisier sensors, smaller faults). The recalls there are not at one "
            "false-alarm rate and are not compared; with thresholds reset no detector finds the small faults. No detector "
            "is qualified for the safety path on this evidence", "5.11")
        try:
            d54 = c.e54f()
            add("Custody and the lost-link rule lose fewer jobs than drop and retry (H14)",
                tested(d54["h14"]["supported"]),
                f"E54: a message-level replay of {cnt(len(d54['seeds']))} recorded months at &times;1, not a run of the "
                "logistics model" + holm("H14"), "5.12")
            add("Under the lost-link rule no reservation stays blocked past its timeout (H14, second clause)",
                "Withdrawn: not testable as written",
                "The zero followed from the rule's definition, and the rule as first written released a silent vehicle's "
                "reservation, which is unsafe if the vehicle has failed inside the segment. The reservation is now kept "
                f"and the segment marked unconfirmed: {cnt(d54['h14']['stuck_reservations_drop_retry'])} such segments in "
                "the replay", "3.11, 5.12")
            add("Entry into an unconfirmed segment at caution speed, and the rest of the lost-link ladder",
                "Not yet tested; not priced",
                "No encounter, model-check or logistics run contains the rule as it now stands; its delay cost is unknown", "3.11, 7")
            x = c.e54facts
            add("Drop and retry loses a quarter of the reservation grants at a loss of 0.25 per hop",
                "Calculated from assumed inputs",
                f"The retry interval (180{NB}s) is longer than a grant's lifetime (60{NB}s), both assumed, so a grant is sent "
                f"once and the share lost is the per-hop loss ({pc(x.lost, 0)}); three tries would lose {pc(x.three, 1)} by "
                "the same arithmetic; that baseline was not run", "5.12")
        except Pending:
            add("Custody and the lost-link rule lose fewer jobs than drop and retry (H14)", "Not yet tested", "E54 pending", "5.12")
        try:
            f16 = c.e55facts16()
            t55, o55 = c.e55rule("test"), c.e55rule("ood")
            add("The protocol's rule as written (chi-square at the theoretical threshold, three of the last five) stays under one false alarm per pair-day without tuning",
                "Observed on the test set; fails out of distribution",
                f"E55 on E56's test streams: {num(t55['fa_per_pair_day'], 2)} false alarms per pair-day (a handful of "
                f"alarm-minutes; no interval), {pc(t55['per_type']['all']['recall'], 0)} of faults found; "
                f"{num(o55['fa_per_pair_day'], 0)} false alarms per pair-day out of distribution", "5.11")
            add("The trimmed mean keeps honest values inside the honest range when no honest vehicle has more than F faulty neighbours (Proposition 7 a)",
                "Proved; tested",
                f"E55: every run of {cnt(len(f16.ok))} cells (50 runs each) with F at least the number of faulty rovers, "
                "on robust and non-robust meshes; fails with more faulty rovers than F", "A.7, 5.11")
            add("The honest vehicles converge when the mesh is robust (Proposition 7 b)",
                "Stated from [72]; not tested",
                "Proved in [72] for a continuous-time form of the rule. On our sparse mesh too few runs met the condition to "
                "test it, with or without the base mast as a node", "A.7, 5.11")
            add("H16 as registered (in range on robust meshes; at least one run out of range otherwise)",
                tested(f16.h["supported"]) + " as written",
                "E55: the first half held, the second did not; the second half mis-stated the theory (dated change of [59])", "5.11")
        except Pending:
            add("Trimmed-mean agreement stays inside the honest vehicles' range and converges on a robust mesh (Proposition 7, H16)",
                "Safety part proved; agreement stated from [72]; not yet tested", "E55 pending", "A.7")
        try:
            t97, _ = c.b97f()
            m, sm = c.b97row(t97, "MSL", "level", "cusum_k0.5"), c.b97row(t97, "SMAP", "level", "cusum_k0.5")
            m0, s0 = c.b97row(t97, "MSL", "level", "chi2_step"), c.b97row(t97, "SMAP", "level", "chi2_step")
            add("Detectors that accumulate evidence find more events than a per-step test on real signals",
                "Tested on real spacecraft telemetry (not rover position data): mixed, and not at one false-alarm rate",
                f"Labelled SMAP and MSL channels, thresholds from training data only: CUSUM {cnt(m['found'])} against "
                f"{cnt(m0['found'])} of {cnt(m['events'])} (MSL) and {cnt(sm['found'])} against {cnt(s0['found'])} of "
                f"{cnt(sm['events'])} (SMAP) on the signal level, with {cnt(sm['fp_runs'])} false-alarm runs against "
                f"{cnt(s0['fp_runs'])} on SMAP; no gain on the first difference; settings differ from E56's; the "
                "regression and the network do not apply", "5.11")
        except Pending:
            pass
        add("Position and clock parameters marked Assumed (ranging reach, long-range ranging error, fix spacing and stop, "
            "shadow drift, transfer residual, guard)", "Assumed; nominal values only",
            "Not swept, except the guard (E51) and, in E56, one out-of-distribution set; the registration asked for sweeps", "3.9 to 3.11")
        add("Real sensors, radios and faults; a second site; three-dimensional position; terrain blocking of ranging in the integrity data",
            "Not tested", "Everything in this paper is simulated, at one base", "7")
        head = ["Claim", "Status", "Evidence, assumption or sweep", "Section"]
        return c.tab("Table 14. What is proved, what is tested, what is observed, what is calculated from assumed inputs, "
                     "what is assumed and what is not yet tested, one row per "
                     "claim. &ldquo;Proved&rdquo; is by argument or exhaustive search under the stated assumption; "
                     "&ldquo;tested&rdquo; is in simulation, with the experiment, seeds and fleet, for a result that could "
                     "have come out otherwise; &ldquo;calculated&rdquo; is arithmetic on assumed inputs or a property of a "
                     "rule or a count; statuses that depend "
                     "on a result are read from the results files when the paper is built.", head, rows, "wide")
    try:
        c.T["PTA"] = build()
    except Pending as e:
        c.table_pending(c.T, "PTA", "Table 14, proved / tested / assumed", e)


def _marker(x, y, shape, col, filled):
    f = col if filled else "#fff"
    if shape == "circle":
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{f}" stroke="{col}" stroke-width="1.5"/>'
    return (f'<rect x="{x - 3.6:.1f}" y="{y - 3.6:.1f}" width="7.2" height="7.2" fill="{f}" stroke="{col}" '
            f'stroke-width="1.5"/>')


def fig_e50_layers(c):
    """Figure 2: p95 position error by layer set, near and away from the base, at 1x and 4x, on a log axis (inline
    SVG, the mechanism of build_p2.fig_density). Colours from the Okabe-Ito set; shape and fill repeat the coding."""
    s = c.e50f(1)
    W, H, L, B, TOP = 560, 320, 64, 58, 16
    lo, hi = 1.0, 1000.0
    X0, X1 = L + 56, W - 60
    xs = {k: X0 + i * (X1 - X0) / (len(LAYER_KEYS) - 1) for i, k in enumerate(LAYER_KEYS)}

    def Y(v):
        v = min(max(v, lo), hi)
        return H - B - (math.log10(v) - math.log10(lo)) / (math.log10(hi) - math.log10(lo)) * (H - B - TOP)

    mid = (H - B + TOP) / 2
    out = [f'<figure id="p2-fig-e50"><svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
           'aria-label="95th percentile of position error by layer set, near and away from the base">',
           f'<line x1="{L}" y1="{H - B}" x2="{W - 10}" y2="{H - B}" stroke="#333"/>',
           f'<line x1="{L}" y1="{TOP}" x2="{L}" y2="{H - B}" stroke="#333"/>',
           f'<text x="{L - 46}" y="{mid:.0f}" font-size="11" text-anchor="middle" '
           f'transform="rotate(-90 {L - 46} {mid:.0f})">95th percentile of position error (m)</text>']
    for t in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000):
        out.append(f'<line x1="{L - 4}" y1="{Y(t):.1f}" x2="{L}" y2="{Y(t):.1f}" stroke="#333"/>')
        out.append(f'<text x="{L - 7}" y="{Y(t) + 3.5:.1f}" font-size="10" text-anchor="end">{t:,}</text>')
    budget = s["design"]["budget_m"]
    yb = Y(budget)
    out.append(f'<line x1="{L}" y1="{yb:.1f}" x2="{W - 10}" y2="{yb:.1f}" stroke="#333" stroke-dasharray="5 4"/>')
    out.append(f'<text x="{L + 6}" y="{yb + 12:.1f}" font-size="10">budget {c.num(budget, 0)} m</text>')
    short = {"dr": ["dead reckoning", "alone"], "dr+ranging": ["+ ranging", ""],
             "dr+ranging+fixes": ["+ terrain fixes", "(2028)"], "lans@2030": ["+ navigation", "service (2030)"]}
    for k in LAYER_KEYS:
        for j, line in enumerate(short[k]):
            out.append(f'<text x="{xs[k]:.0f}" y="{H - B + 15 + 12 * j}" font-size="10.5" text-anchor="middle">{line}</text>')
    out.append(f'<text x="{(X0 + X1) / 2:.0f}" y="{H - 6}" font-size="11" text-anchor="middle">layer set</text>')
    series = [("near", "1", "#0072B2", -15, "near the base, &times;1 fleet"),
              ("away", "1", "#D55E00", -5, "away from the base, &times;1"),
              ("near", "4", "#0072B2", 5, "near the base, &times;4"),
              ("away", "4", "#D55E00", 15, "away from the base, &times;4")]
    ly, lx = TOP + 8, W - 178
    for region, mult, col, dx, label in series:
        if mult not in s["errors"]:
            continue
        shape = "circle" if region == "near" else "square"
        pts = []
        for k in LAYER_KEYS:
            p = s["errors"][mult][k][region]["p95_m"]
            x, y = xs[k] + dx, Y(p["mean"])
            pts.append(f"{x:.1f},{y:.1f}")
            out.append(f'<line x1="{x:.1f}" y1="{Y(p["ci"][0]):.1f}" x2="{x:.1f}" y2="{Y(p["ci"][1]):.1f}" stroke="{col}"/>')
        dash = "" if mult == "1" else ' stroke-dasharray="3 3"'
        out.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{col}" stroke-width="1" opacity="0.6"{dash}/>')
        for pt in pts:
            x, y = (float(v) for v in pt.split(","))
            out.append(_marker(x, y, shape, col, mult == "1"))
        out.append(_marker(lx, ly - 3.5, shape, col, mult == "1"))
        out.append(f'<text x="{lx + 10}" y="{ly}" font-size="10.5">{label}</text>')
        ly += 14
    n1, n4 = len(s["seeds"]["1"]), len(s["seeds"].get("4", []))
    out.append("</svg><figcaption>Figure 2. E50: the 95th percentile of the horizontal position error while driving, "
               "by layer set, near the base (at least two of four beacons in view; circles) and away from it "
               f"(squares), at today's fleet (filled, {c.cnt(n1)} seeds)"
               + (f" and at four times the fleet (open, {c.cnt(n4)} seeds)" if n4 else "")
               + ". Means over seeds with 95&#8239;% bootstrap intervals, on a logarithmic axis; the dashed line is "
               "the 5&nbsp;m separation budget. Simulated month of July 2028; the last layer set is a variant with "
               "the navigation service at its planned 2030 availability.</figcaption></figure>")
    return "\n".join(out)
