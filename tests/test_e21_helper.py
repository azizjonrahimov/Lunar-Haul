"""B-62: the helper's own time (lunarsim/comms.py 'helpers', Stage H in experiments/phase4/run_phase4.py e21h,
analyse_e21.py helper). Engine checks on synthetic parking files; results/E21h_helper_r2.csv against E21_fit_r2.json."""
import json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pandas as pd
import pytest

from lunarsim import Simulation
from lunarsim.comms import CommsModel
from lunarsim.phase3 import _find

LINK = os.path.join(ROOT, "data", "comms", "connecting_ridge", "earth_link-v1.json")
RES = os.path.join(ROOT, "results")


def parking_file(tmp_path, samples=None, windows=None, km=0.0, name="parking.json"):
    """A parking-v1 document: every listed sample (default: all) parks at one grid point with these windows."""
    with open(LINK, encoding="utf-8") as f:
        sf = json.load(f)["samples_file"]
    n = 35064
    ids = range(sf["n_samples"]) if samples is None else samples
    doc = {"format": "lunarsim-parking", "version": 1, "samples_file": {"file": sf["file"], "sha256": sf["sha256"]},
           "points": [{"kind": "grid", "xy_m": [0.0, 0.0], "z_m": 0.0, "near_sample": 0, "access_m": 0.0,
                       "base_drive_km": km, "link_fraction": 1.0, "windows": [0, n] if windows is None else windows}],
           "samples": {str(s): {"top": [{"point": 0}]} for s in ids}}
    p = tmp_path / name
    p.write_text(json.dumps(doc))
    return str(p)


@pytest.fixture(scope="module")
def R():
    from experiments.phase4 import run_phase4 as R
    return R


def run(R, comms_update, h=24.0, seed=1, never=None):
    tag, sc, _, mech, kw = next(c for c in R.e21g2_cells() if c[0]["rescue_h"] == h)
    cm = dict(sc.comms, start_year=R.start_year(seed), **comms_update)
    if never is not None:
        cm = {k: v for k, v in cm.items() if k not in ("rescue_h", "rescue_scope")}
        cm["never_linked"] = never
    sim = Simulation(sc.with_(comms=cm), mech, seed=seed, mech_kwargs=dict(kw))
    return sim, sim.run()


def test_ideal_helper_equals_stage_g2(R, tmp_path):
    """Zero drive, S = 0 and a parking point that is always linked: every call is released at once, as in G2."""
    _, g2 = run(R, {})
    _, hp = run(R, {"helpers": {"n": 1, "service_h": 0.0, "parking": parking_file(tmp_path)}})
    diff = [k for k in g2 if not k.startswith("helper_") and isinstance(g2[k], (int, float))
            and not (isinstance(g2[k], float) and math.isnan(g2[k]) and math.isnan(hp[k])) and hp[k] != g2[k]]
    assert diff == []
    assert hp["helper_helps"] == hp["helper_calls"] == g2["blackout_rescues_never_linked"] > 0
    assert hp["helper_busy_h"] == 0.0 and hp["helper_call_to_release_mean_h"] == 0.0
    csv = pd.read_csv(os.path.join(RES, "E21g2_rescue_any_r2.csv"), float_precision="round_trip")
    row = csv[(csv["rescue_h"] == 24.0) & (csv["seed"] == 1)].iloc[0]
    assert hp["delivered_kg_in_horizon"] / 1000.0 == row["delivered_t_in_year"]


def test_no_parking_point_strands_like_stage_f(R, tmp_path):
    """No working parking point: finite waits run their course, never-linked samples strand (= never_linked 'strand')."""
    _, st = run(R, {}, never="strand")
    _, hp = run(R, {"helpers": {"n": 1, "parking": parking_file(tmp_path, samples=[])}})
    assert hp["delivered_kg_in_horizon"] == st["delivered_kg_in_horizon"]
    assert hp["blackout_wait_vehicle_h"] == st["blackout_wait_vehicle_h"]
    assert hp["helper_strandings"] == st["blackout_strandings_never_linked"] > 0
    assert hp["helper_unserved"] == hp["helper_calls"] and hp["helper_helps"] == 0


def _model(tmp_path, **hp):
    cfg = {"mode": "dte", "supervised_policy": "strategic", "never_linked": "rescue", "rescue_h": 0.0,
           "rescue_scope": "any", "helpers": {"n": 1, "service_h": 1.0, **hp}}
    return CommsModel(cfg, "1", 0, 8760.0, [], find=_find)


def test_first_fit_booking_and_link_wait(tmp_path):
    cm = _model(tmp_path, parking=parking_file(tmp_path, samples=[5], km=6.0))      # LTV 6 km/h: 1 h each way
    cm._hp_pend = []
    assert cm._helper_wait(5, 10.0, 100.0) == pytest.approx(2.0)                   # drive 1 h + S 1 h
    assert cm._helper_wait(5, 10.0, 100.0) == pytest.approx(5.0)                   # waits for the trip [10, 13)
    assert cm._helper_wait(5, 10.0, 1.5) == pytest.approx(1.5)                     # the link comes first by itself
    assert cm._helper_wait(7, 10.0, math.inf) == pytest.approx(8760.0 - 10.0 + 1.0)  # no parking point: strand
    cm._commit_helpers()
    st = cm.hstat
    assert (st["calls"], st["helps"], st["natural_first"], st["unserved"], st["strandings"]) == (4, 2, 1, 1, 1)
    assert st["drive_h"] == pytest.approx(4.0) and st["park_h"] == 0.0 and st["service_h"] == pytest.approx(2.0)
    assert cm._helper_segs[0] == [(10.0, 13.0), (13.0, 16.0)] and st["delays"] == pytest.approx([2.0, 5.0])
    # a parking point linked only from hour 100 of 2028 on (start year 2028): the helper waits there
    cm2 = _model(tmp_path, parking=parking_file(tmp_path, samples=[5], windows=[100, 50], name="p2.json"))
    cm2._hp_pend = []
    assert cm2._helper_wait(5, 10.0, 500.0) == pytest.approx(100.0 - 10.0 + 1.0)
    cm2._commit_helpers()
    assert cm2.hstat["park_h"] == pytest.approx(90.0)


def test_helpers_validation(tmp_path):
    base = {"mode": "dte", "supervised_policy": "strategic", "never_linked": "rescue", "rescue_h": 24.0}
    bad = [dict(base, helpers={"n": 1}),                                           # rescue_scope never_linked
           dict(base, rescue_scope="any", helpers={"n": 0}),
           dict(base, rescue_scope="any", helpers={"n": 1, "home": "ISRU"}),
           dict(base, rescue_scope="any", helpers={"n": 1, "speed": 3}),
           dict(base, rescue_scope="any", criterion="centre+2deg", helpers={"n": 1}),
           dict(base, rescue_scope="any", helpers={"n": 1, "service_h": -1})]
    for cfg in bad:
        with pytest.raises(ValueError):
            CommsModel(cfg, "1", 0, 8760.0, [], find=_find)


def test_from_fleet_takes_the_last_ltv_out(R):
    sim, _ = run(R, {"helpers": {"n": 1, "from_fleet": True}}, h=168.0)
    tag, sc, *_ = next(c for c in R.e21g2_cells() if c[0]["rescue_h"] == 168.0)
    assert len(sc.fleet) == 6 and len(sim.vehicles) == 5
    assert [(v.owner, v.cls.name) for v in sim.vehicles] == [(o, c) for o, c, _, _ in sc.fleet[:5]]
    assert sc.fleet[5][1] == "LTV"


H = os.path.join(RES, "E21h_helper_r2.csv")
FIT = os.path.join(RES, "E21_fit_r2.json")


@pytest.mark.skipif(not (os.path.isfile(H) and os.path.isfile(FIT)), reason="Stage H not run")
def test_stage_h_summary(R):
    h = pd.read_csv(H, float_precision="round_trip")
    assert len(h) == len(R.e21h_cells()) * 20 == 120 and not h.duplicated(["cell", "seed"]).any()
    assert np.allclose(h["helper_busy_h"], h["helper_drive_h"] + h["helper_park_h"] + h["helper_service_h"])
    assert (h["helper_helps"] + h["helper_unserved"] + h["helper_natural_first"] == h["helper_calls"]).all()
    assert np.allclose(h["helper_service_h"], h["helper_helps"] * h["helpers_service_h"])
    with open(FIT, encoding="utf-8") as f:
        doc = json.load(f)["helper"]
    assert len(doc["cells"]) == 6
    for c in doc["cells"]:
        sel = h[(h["helpers_n"] == c["helpers"]) & (h["helpers_from_fleet"] == c["from_fleet"])
                & (h["rescue_h"] == c["call_threshold_h"]) & (h["helpers_service_h"] == c["service_h"])]
        assert len(sel) == 20
        assert c["mean"]["delivered_t_in_year"] == pytest.approx(sel["delivered_t_in_year"].mean(), rel=1e-12)
        sp = c["helper"]["busy_split_share"]
        assert sum(sp.values()) == pytest.approx(1.0)
        assert c["within_5pct_of_always_linked_every_year"] == (min(c["share_of_always_linked_by_year"].values()) >= 0.95)
    t = pd.read_csv(os.path.join(RES, "table_E21h_helper_r2.csv"))
    assert set(t["reference"]) == {"strict", "strict + 1 rover", "always-linked strategic", "G2 same threshold (ideal helper)"}
