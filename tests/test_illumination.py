"""Real sun per site and leg (B-44): the data file, the window model and the engine's night rule."""
import json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pytest

from lunarsim import illumination as IL
from lunarsim.comms import encode_windows, summarize

DATA = os.path.join(ROOT, "data", "illumination", "connecting_ridge", "sun_link-v1.json")
SITES = ["BASE", "DEPOT", "POWER", "CONSTR", "ISRU", "SCI_1", "PSR", "PAD_A@1", "PAD_B@1"]


def _doc(lit_by_point, legs=None, n=35064):
    """A synthetic sun-link document: each point lit over the given [start, end) hour windows (all criteria)."""
    def ent(w):
        w = np.array(w, dtype=np.int64).reshape(-1, 2)
        s = summarize(w, n, 1.0)
        return {"lit": {c: encode_windows(w) for c in IL.CRITERIA}, "summary": {**{c: s for c in IL.CRITERIA},
                                                                               "mean_disc_fraction": s["fraction"]}}
    return {"format": IL.FORMAT, "version": 1, "terrain": "t", "time": {"start_utc": "2028-01-01 00:00", "step_min": 60, "n": n},
            "criteria": {}, "default_criterion": "half", "leg_rules": {}, "provenance": {},
            "points": {k: ent(w) for k, w in lit_by_point.items()},
            "legs": {k: {"worst": ent(w), "most": ent(w), "samples": 3} for k, w in (legs or {}).items()}}


def _write(tmp_path, doc, name="sun.json"):
    p = tmp_path / name
    p.write_text(json.dumps(doc))
    IL._DOCS.clear()
    return str(p)


def test_committed_file_is_valid_and_small():
    doc = IL.load(DATA)
    assert IL.validate(doc) == [] and os.path.getsize(DATA) < 2 * 2**20
    assert set(SITES) <= set(doc["points"]) and len(doc["legs"]) == 182
    base = doc["points"]["BASE"]["summary"]
    assert 0.7 < base["half"]["fraction"] < 0.95 and doc["points"]["PSR"]["summary"]["any_part"]["fraction"] == 0.0
    c = doc["checks"]
    assert c["ephem"]["max_abs_el_deg"] < 1e-6 and c["avgvisib"]["map_way_minus_map"]["mean_abs"] < 0.1
    assert 85.0 < c["glaser"]["best_point_2p5m"]["mean_disc_pct"] < 95.0
    for leg in doc["legs"].values():                       # "most" is never darker than "worst"
        assert leg["most"]["summary"]["half"]["fraction"] >= leg["worst"]["summary"]["half"]["fraction"] - 1e-9


def test_committed_file_schema():
    jsonschema = pytest.importorskip("jsonschema")
    from lunarsim.formats import load_schema
    assert list(jsonschema.Draft202012Validator(load_schema("sun-link-v1")).iter_errors(IL.load(DATA))) == []


def test_disc_fraction():
    sys.path.insert(0, os.path.join(ROOT, "tools", "illumination"))
    import sun_link as S
    r = 0.267
    assert S.disc_fraction(5.0, 0.0, r) == 1.0 and S.disc_fraction(-5.0, 0.0, r) == 0.0
    assert S.disc_fraction(0.0, 0.0, r) == pytest.approx(0.5)
    f = S.disc_fraction(np.linspace(-0.3, 0.3, 61), 0.0, r)
    assert np.all(np.diff(f) >= 0) and f[30] == pytest.approx(0.5)
    assert S.disc_fraction(0.1, 0.0, r) + S.disc_fraction(-0.1, 0.0, r) == pytest.approx(1.0)      # symmetric


def test_window_queries(tmp_path):
    lit = {s: [[0, 35064]] for s in SITES}
    lit["BASE"] = [[10, 20], [30, 40]]
    lit["DEPOT"] = [[15, 35]]
    path = _write(tmp_path, _doc(lit, legs={"BASE->POWER": [[12, 18]]}))
    m = IL.Illumination({"file": path}, "1", 8760.0, ["PAD_A", "PAD_B"])
    assert m.dark(5.0, "BASE") and m.lit(10.0, "BASE") and m.dark(20.0, "BASE")
    assert m.next_dark(12.0, "BASE") == 20.0 and m.next_dark(25.0, "BASE") == 25.0
    assert m.light_after(25.0, "BASE") == 30.0 and m.light_after(12.0, "BASE") == 12.0
    assert m.lit(13.0, "POWER", "BASE") and m.dark(19.0, "BASE", "POWER")          # the reverse key is used
    assert m.lit(16.0, "BASE", "DEPOT") and m.dark(22.0, "BASE", "DEPOT")           # no leg: both ends lit
    assert "BASE->DEPOT" in m.missing_legs
    assert m.first_dark([["BASE", "BASE", 12.0, 14.0, 0], ["BASE", "POWER", 14.0, 19.0, 0]]) == (18.0, 35064.0 - 0.0 + 12.0)
    assert m.first_dark([["BASE", "BASE", 31.0, 39.0, 0]]) is None
    assert m.dark_windows("BASE", 50.0) == [[0.0, 10.0], [20.0, 30.0], [40.0, 50.0]]
    assert 10.0 in m.light_returns(["BASE", "DEPOT"], 100.0) and 15.0 in m.light_returns(["BASE", "DEPOT"], 100.0)


def test_start_year_follows_comms(tmp_path):
    lit = {s: [[0, 35064]] for s in SITES}
    lit["BASE"] = [[8784, 8800]]                              # lit 16 h starting 1 January 2029
    path = _write(tmp_path, _doc(lit))
    m = IL.Illumination({"file": path}, "1", 8760.0, ["PAD_A", "PAD_B"], comms_start_year=2029)
    assert m.lit(0.0, "BASE") and m.dark(16.0, "BASE")
    m = IL.Illumination({"file": path, "start_year": 2028}, "1", 8760.0, ["PAD_A", "PAD_B"], comms_start_year=2029)
    assert m.dark(0.0, "BASE") and m.lit(8784.0, "BASE")
    with pytest.raises(ValueError):
        IL.Illumination({"file": path, "colour": 1}, "1", 8760.0, [])


def _run(sc, seed=0, trace=False):
    from lunarsim import Simulation, dispatch
    sim = Simulation(sc, dispatch.MECHANISMS["marketplace"], seed=seed, mech_kwargs={"trace": trace})
    return sim, sim.run()


def test_engine_off_is_unchanged_and_on_differs():
    from lunarsim.config import library
    sc = library()["P2-default"]
    _, a = _run(sc)
    _, b = _run(sc.with_(illumination=None))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)          # NaN-safe equality
    _, c = _run(sc.with_(illumination={}))
    assert c["jobs"] != a["jobs"] or c["delay_prio1_mean_h"] != a["delay_prio1_mean_h"]


def test_engine_parks_in_the_dark(tmp_path):
    """Every site and leg dark for the first 500 h: no rover without night operations starts a job before then."""
    from lunarsim.config import library
    lit = {s: [[500, 35064]] for s in SITES}
    path = _write(tmp_path, _doc(lit))
    sc = library()["P2-default"].with_(illumination={"file": path})
    sim, r = _run(sc, trace=True)
    night_ops = {v.id for v in sim.vehicles if v.cls.night_ops}
    starts = [j["t0"] for j in sim.trace if j["veh"] not in night_ops]
    assert starts and min(starts) >= 500.0 - 1e-6
    tr = sim.trace_export()
    assert tr["nights"][0] == [0.0, 500.0]


def test_engine_dark_spells(tmp_path):
    """A 4 h dark spell at every site and leg every 100 h: no job of a rover without night operations starts in a
    spell or runs into one (the marketplace's plans avoid the dark), and the year still delivers."""
    from lunarsim.config import library
    w = [[k * 100 + 4, k * 100 + 100] for k in range(351)]
    path = _write(tmp_path, _doc({s: w for s in SITES}))
    sc = library()["P2-default"].with_(illumination={"file": path})
    sim, r = _run(sc, trace=True)
    night_ops = {v.id for v in sim.vehicles if v.cls.night_ops}
    jobs = [j for j in sim.trace if j["veh"] not in night_ops and j["kind"] != "reposition"]
    assert jobs and r["delivered_kg"] > 0
    for j in jobs:
        assert j["t0"] % 100.0 >= 4.0 - 1e-6, j["t0"]
        k = math.floor(j["t0"] / 100.0)
        assert j["t1"] <= (k + 1) * 100.0 + 1e-6 or r["night_strandings"] > 0


def test_scenario_roundtrip_and_cli(tmp_path):
    from lunarsim.config import library, scenario_to_dict, load_scenario
    sc = library()["P2-default"].with_(illumination={"criterion": "any_part", "leg_rule": "worst"})
    p = tmp_path / "s.json"
    p.write_text(json.dumps(scenario_to_dict(sc)))
    assert load_scenario(str(p)).illumination == {"criterion": "any_part", "leg_rule": "worst"}
    assert "illumination" not in scenario_to_dict(library()["P2-default"])
    from lunarsim.cli import _add_phase3_args, _with_phase3
    import argparse
    ap = argparse.ArgumentParser()
    _add_phase3_args(ap)
    assert _with_phase3(library()["P2-default"], ap.parse_args(["--illumination", "on"])).illumination == {}
    assert _with_phase3(library()["P2-default"], ap.parse_args(["--illumination", "full"])).illumination == {"criterion": "full"}
