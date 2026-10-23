"""B-63: the 2032-2046 link files (tools/comms/later_years.py), the engine's start years against a link file's span
(lunarsim/comms.py), results/E21_later_years.json and Stage J (results/E21j_years_r2.csv, E21_fit_r2.json 'later_years')."""
import gzip, json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pandas as pd
import pytest

from lunarsim import comms as C
from lunarsim.phase3 import _find

D = os.path.join(ROOT, "data", "comms", "connecting_ridge")
V3, S3, P3 = (os.path.join(D, f) for f in ("earth_link-v3.json", "earth_link-v3-samples.json.gz", "parking-v3.json"))
RES = os.path.join(ROOT, "results")
need_v3 = pytest.mark.skipif(not (os.path.isfile(V3) and os.path.isfile(S3)), reason="v3 link files not built")


def load_gz(p):
    with open(p, "rb") as f:
        return json.loads(gzip.decompress(f.read()))


def test_start_year_against_a_files_span():
    h = 15 * 8760 + 4 * 24
    assert C.file_year_start_h("2032-01-01 00:00", h, 2032) == 0.0
    assert C.file_year_start_h("2032-01-01 00:00", h, 2033) == 366 * 24.0
    for bad in (2031, 2047):
        with pytest.raises(ValueError):
            C.file_year_start_h("2032-01-01 00:00", h, bad)
    for y in (2028, 2029, 2030, 2031):                        # the v1 path is unchanged
        assert C.file_year_start_h("2028-01-01 00:00", 35064.0, y) == C.year_start_h(y)


@need_v3
def test_engine_reads_v3_only_when_asked():
    base = {"mode": "dte", "supervised_policy": "strategic"}
    cm = C.CommsModel(dict(base, link_series=V3, start_year=2033), "1", 0, 8760.0, [], find=_find)
    assert cm.start_h == 366 * 24.0 and cm.el.doc["time"]["start_utc"] == "2032-01-01 00:00"
    with pytest.raises(ValueError):                           # the default (v1) file does not cover 2033
        C.CommsModel(dict(base, start_year=2033), "1", 0, 8760.0, [], find=_find)
    with pytest.raises(ValueError):                           # nor does 2028 lie in the v3 file
        C.CommsModel(dict(base, link_series=V3, start_year=2028), "1", 0, 8760.0, [], find=_find)
    with pytest.raises(ValueError):                           # no link file at all
        C.CommsModel({"mode": "always", "start_year": 2040}, "1", 0, 8760.0, [], find=_find)


@need_v3
def test_v3_files_are_valid_and_match_v1_layout():
    v3 = json.load(open(V3, encoding="utf-8"))
    s3, s1 = load_gz(S3), load_gz(os.path.join(D, "earth_link-v1-samples.json.gz"))
    assert C.validate(v3) == [] and C.validate_samples(s3) == []
    assert v3["time"]["start_utc"] == s3["time"]["start_utc"] == "2032-01-01 00:00"
    assert v3["time"]["n"] == 6 * s3["time"]["n"] == 6 * (19 * 8760 + 5 * 24)        # 2032-2050
    assert v3["samples_file"]["sha256"] == C_sha(S3)
    assert s3["legs"] == s1["legs"] and [s["xy_m"] for s in s3["samples"]] == [s["xy_m"] for s in s1["samples"]]
    assert set(v3["points"]) == set(json.load(open(os.path.join(D, "earth_link-v1.json")))["points"])


def C_sha(p):
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


@pytest.mark.skipif(not os.path.isfile(os.path.join(RES, "E21_later_years.json")), reason="predict not run")
def test_prediction_recomputes_from_the_files():
    ly = json.load(open(os.path.join(RES, "E21_later_years.json"), encoding="utf-8"))
    s3 = load_gz(S3)
    w = C.decode_windows(s3["series"][s3["samples"][188]["w"][0]])
    m = C.windows_to_mask(w, s3["time"]["n"])
    assert int(m[: 366 * 24].sum()) == ly["dark_sample_188"]["linked_h_by_year"]["2032"]
    i0 = (366 + 365 + 365) * 24                               # 2035
    assert int(m[i0:i0 + 8760].sum()) == ly["dark_sample_188"]["linked_h_by_year"]["2035"]
    assert ly["continuity_2031_2032"]["samples_same_state"] == ly["continuity_2031_2032"]["of"]
    a = ly["period_188"]["annual"]
    assert a["ci95_yr"][0] <= a["best_period_yr"] <= a["ci95_yr"][1] and a["p_vs_constant"] < 0.01
    yrs = ly["like_2028_regolith_legs"]["dark_whole_year_years"]
    assert all(ly["dark_sample_188"]["linked_h_by_year"][str(y)] == 0 for y in yrs)
    assert ly["never_linked"]["all_2028_2050"] <= ly["never_linked"]["v3_2032_2050"] <= ly["never_linked"]["v1_2028_2031"] + 6
    sp = ly["dark_spells_188_over_180_days"]["spells"]
    assert sp[0]["end"].startswith("2029-07-02") and not sp[0]["censored"]               # its start from back188
    assert all(not x["censored"] for x in sp[:-1])


@pytest.mark.skipif(not os.path.isfile(P3), reason="parking-v3 not built")
def test_parking_v3_keeps_v1_points():
    p1 = json.load(open(os.path.join(D, "parking-v1.json"), encoding="utf-8"))
    p3 = json.load(open(P3, encoding="utf-8"))
    assert [p["xy_m"] for p in p1["points"]] == [p["xy_m"] for p in p3["points"]]
    assert {s: r["top"] for s, r in p1["samples"].items()} == {s: r["top"] for s, r in p3["samples"].items()}
    assert p3["samples_file"]["sha256"] == C_sha(S3) and p3["time"]["start_utc"] == "2032-01-01 00:00"
    n = p3["time"]["n"]
    for p in p3["points"]:
        if p["kind"] == "grid":
            w = C.decode_windows(p["windows"])
            assert len(w) == 0 or w[-1, 1] <= n


J = os.path.join(RES, "E21j_years_r2.csv")


@pytest.mark.skipif(not os.path.isfile(J), reason="Stage J not run")
def test_stage_j_rows_and_fit():
    from experiments.phase4 import run_phase4 as R
    j = pd.read_csv(J, float_precision="round_trip")
    assert len(j) == len(R.e21j_cells()) * 5 == 300 and not j.duplicated(["cell", "seed"]).any()
    assert sorted(j["start_year"].unique()) == list(range(2032, 2047))
    cell = next(c for c in R.e21j_cells() if c[0]["policy_j"] == "strategic" and c[0]["start_year"] == 2033)
    out = R._job((*cell, 0))
    row = j[(j["cell"] == out["cell"]) & (j["seed"] == 0)].iloc[0]
    assert out["delivered_t_in_year"] == row["delivered_t_in_year"] and out["start_year"] == 2033
    fit = json.load(open(os.path.join(RES, "E21_fit_r2.json"), encoding="utf-8")).get("later_years")
    if fit is None:
        pytest.skip("analyse_e21.py years not run")
    for p_, per in fit["by_policy_year"].items():
        for y, rec in per.items():
            sel = j[(j["policy_j"] == p_) & (j["start_year"] == int(y))]
            assert rec["mean_t"] == pytest.approx(sel["delivered_t_in_year"].mean(), rel=1e-12)
