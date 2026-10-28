"""B-74: the learned bid correction (lunarsim/atc/learned.py, data/policies/atc_bid*_v1.json, tools/atc/train_bid.py)."""
import json, math, os, sys, warnings
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "atc"))
import numpy as np
import pytest

from lunarsim import Simulation
from lunarsim.atc import learned as LR, regimes as G
from lunarsim.config import load_scenario

POL = os.path.join(ROOT, "data", "policies")
L10 = os.path.join(ROOT, "data", "scenarios", "p5", "p5-3eq-L10-T10.json")
RESULT = os.path.join(ROOT, "results", "ATC_learned_eval.json")


def run(regime, kw, seed=3):
    sim = Simulation(load_scenario(L10), G.mechanism(regime), seed=seed, mech_kwargs=dict(kw, trace=True))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        s = sim.run()
    return sim, s


@pytest.mark.parametrize("name", ["atc_bid_v1", "atc_bid_linear_v1"])
def test_policy_files_and_check_vectors(name):
    path = os.path.join(POL, f"{name}.json")
    doc = json.load(open(path, encoding="utf-8"))
    assert doc["format"] == "lunarsim-policy" and doc["obs"]["names"] == list(LR.FEATURES) and len(LR.FEATURES) == 13
    chk = json.load(open(path.replace(".json", ".check.json"), encoding="utf-8"))
    out = LR.Policy(path)(np.array(chk["obs"]))
    assert np.allclose(out, np.array(chk["act"])[:, 0], atol=chk["tolerance"], rtol=0)
    tr = doc["training"]
    assert tr["imitation"]["hand_agreement_val"] == 0.92881 and tr["imitation"]["best_epoch"] == -1
    assert tr["cem"]["selected_tune_h"] < tr["cem"]["hand_tune_h"] and len(tr["cem"]["trace"]) == tr["cem"]["generations"]
    if doc["kind"] == "mlp":
        assert sum(len(L["b"]) + len(L["w"]) * len(L["w"][0]) for L in doc["layers"]) == 13 * 32 + 32 + 32 * 32 + 32 + 32 + 1


def test_zero_correction_is_the_hand_built_auction(tmp_path):
    import train_bid as T
    p = tmp_path / "zero.json"
    p.write_text(json.dumps(T._cem_doc("linear", np.zeros(len(LR.FEATURES)))))
    a, _ = run("C_AUCTION", {"loss": 0.1})
    b, _ = run("C_LEARNED", {"loss": 0.1, "policy": str(p)})
    assert a.trace == b.trace


def test_collection_has_no_side_effects_and_labels_one_item_per_group():
    a, ra = run("C_AUCTION", {"loss": 0.1})
    b, rb = run("C_AUCTION", {"loss": 0.1, "collect": True})
    assert a.trace == b.trace and ra["delivered_kg"] == rb["delivered_kg"]
    X, s, y, g = b.atc.collector.arrays()
    assert X.shape[1] == len(LR.FEATURES) and np.isfinite(X).all()
    assert all(y[g == k].sum() == 1 for k in np.unique(g))


def test_features_are_local_and_bounded():
    sim, _ = run("C_LEARNED", {"loss": 0.1})
    v = sim.vehicles[1]
    c = next(x for x in sim.all_cargo if x.cls == "consumables")
    sim.t = c.t_ready + 5.0
    x = LR.features(sim, v, [c], [c.dest], {"next_landing": LR.next_landings(sim)})
    assert len(x) == 13 and 0 <= x[LR.FEATURES.index("dark_or_low")] <= 1 and 0 <= x[LR.FEATURES.index("landing")] <= 1
    assert x[LR.FEATURES.index("age_d")] == pytest.approx(5.0 / 24)


def test_results_file():
    if not os.path.isfile(RESULT):
        pytest.skip("evaluation not run")
    d = json.load(open(RESULT, encoding="utf-8"))
    for load in ("30", "60"):
        e = d["eval"][load]
        assert set(e) == {"O_ORACLE", "hand", "mlp", "linear"}
        assert e["linear"]["vs_hand_h"]["n"] == 30
    assert 0 < d["eval"]["30"]["hand"]["heldout_agreement"] <= 1
    assert d["imitation"]["groups"] == 37941
