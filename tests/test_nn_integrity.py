"""Fast tests of lunarsim.nn (B-96 / E56): the dataset builder, the baselines' calibration, the network, its policy
file and the loss-landscape geometry. No training and no cached dataset is needed."""
import json
import math
import os

import numpy as np
import pytest

from lunarsim.nn import baselines as B
from lunarsim.nn import dataset as D
from lunarsim.nn import faults as F
from lunarsim.nn import landscape as L
from lunarsim.nn import model as M

ROOT = D.ROOT
SMALL = {"fault": 2, "ff_design": 2, "ff_natural": 1}
LIMIT_S = 150000                       # the first 42 hours of the committed seed-1 trace


@pytest.fixture(scope="module")
def small():
    return D.build_trace("train", 1, "with", quota=SMALL, t_limit_s=LIMIT_S)


def test_dataset_is_deterministic(small):
    again = D.build_trace("train", 1, "with", quota=SMALL, t_limit_s=LIMIT_S)
    for k in ("Xf", "yf", "mf", "Xn", "mn"):
        assert small[k].shape == again[k].shape and np.array_equal(small[k], again[k]), k
    assert small["Xf"].shape[1:] == (D.PRE + D.FAULT_T, len(F.FEATURES))
    assert len(small["Xf"]) >= 6 and len(small["Xn"]) >= 2
    assert np.isfinite(small["Xf"]).all() and np.isfinite(small["Xn"]).all()


def test_split_has_no_shared_seed_or_pair():
    seeds = [set(D.SPLIT_SEEDS[s]) for s in ("train", "val", "test", "ood")]
    for i in range(4):
        for j in range(i + 1, 4):
            assert not seeds[i] & seeds[j]
    un = {s: {frozenset(p) for p in D.pairs_of(s)} for s in ("train", "val", "test")}
    assert not un["train"] & un["val"] and not un["train"] & un["test"] and not un["val"] & un["test"]
    assert len(un["train"] | un["val"] | un["test"]) == 28


def test_fault_streams_carry_one_labelled_fault(small):
    mf, yf = small["mf"], small["yf"]
    on, end = D.META.index("onset"), D.META.index("end")
    for i in np.flatnonzero(mf[:, 0] > 0):
        a, b = int(mf[i, on]), int(mf[i, end])
        assert D.PRE <= a < b <= D.PRE + D.FAULT_T - F.GUARD_S
        assert F.EVENT_S[0] <= b - a <= F.EVENT_S[1]
        assert yf[i, a:b].all() and yf[i].sum() == b - a
    assert not yf[mf[:, 0] == 0].any()
    m = D.score_mask(yf, mf)
    assert not m[:, :D.PRE].any()
    i = int(np.flatnonzero(mf[:, 0] > 0)[0])
    assert not m[i, int(mf[i, end]):int(mf[i, end]) + F.GUARD_S].any()


def test_named_faults():
    rng = np.random.default_rng(0)
    nav = np.cumsum(rng.normal(0, 0.5, (300, 2)), axis=0)
    noise = rng.normal(0, 0.5, (300, 2))
    clean = nav + noise
    for name in F.FAULT_TYPES:
        mag, direction = F.sample_fault(name, rng)
        f = F.FAULTS[name]
        assert f.lo <= mag <= f.hi
        rep = F.inject(name, nav, noise, 100, 200, mag, direction)
        assert np.allclose(rep[:100], clean[:100]) and np.allclose(rep[200:], clean[200:])
        off = rep[100:200] - clean[100:200]
        if name in ("jump", "frame"):
            assert np.allclose(np.hypot(*off.T), mag)
        elif name == "drift":
            assert np.allclose(np.hypot(*off.T), mag * np.arange(1, 101))
        elif name == "frozen":
            assert np.allclose(rep[100:200] - noise[100:200], nav[100])
        elif name == "noise":
            assert np.allclose(off, (mag - 1.0) * noise[100:200])
    mag, _ = F.sample_fault("jump", rng, ood=True)
    assert F.FAULTS["jump"].ood_lo <= mag <= F.FAULTS["jump"].ood_hi < F.FAULTS["jump"].lo + 1e-9


def test_params_file_has_value_sweep_unit_source():
    doc = json.load(open(F.PARAMS_FILE, encoding="utf-8"))
    for k, v in doc["params"].items():
        assert {"value", "sweep", "unit", "source"} <= set(v), k
    p = F.true_params(F.load_params(), ood=True)
    assert p["uwb_range_noise_true_m"] == 2 * p["uwb_range_noise_m"] and p["dr_error_frac_true"] == 0.05
    assert 3700 < F.range_limit_m(1.0, 1.0, p) < 3760 and F.range_limit_m(2.5, 2.5, p) == p["long_range_cap_m"]


def test_calibration_gives_the_requested_false_alarm_rate():
    rng = np.random.default_rng(1)
    score = rng.normal(size=(120, D.PRE + D.FF_T)).astype(np.float32)
    weight = rng.uniform(0.2, 3.0, 120)
    bm = B.bin_max(score)
    assert bm.shape == (120, D.FF_T // B.BIN_S)
    days = B.pair_days(bm, weight)
    for per_day in (24.0, 240.0):
        thr = B.calibrate(bm, weight, per_day)
        fa = B.fa_per_day(bm, weight, thr)
        assert fa <= per_day * (1 + 1e-9)
        assert fa >= per_day - weight.max() / days - 1e-9          # within one (heaviest) bin of the target
        assert B.fa_per_day(bm, weight, thr - 1e-3) >= fa          # monotone


def test_baselines_on_real_fault_free_blocks(small):
    Xn = small["Xn"]
    w = np.ones(len(Xn))
    for score in (B.chi2_step(Xn), B.chi2_window(Xn, 10), B.cusum(Xn, 3.0)):
        assert score.shape == Xn.shape[:2] and np.isfinite(score).all() and (score >= 0).all()
        bm = B.bin_max(score)
        target = 24.0 * 6                                          # 6 false alarms per pair-hour
        thr = B.calibrate(bm, w, target)
        assert B.fa_per_day(bm, w, thr) <= target + 1e-9
        # the lowest such threshold: one float lower and the rate is above the target (ties cannot be split)
        below = float(np.nextafter(np.float32(thr), np.float32(-np.inf)))
        assert thr < bm.min() or B.fa_per_day(bm, w, below) > target
    feats = B.hand_features(small["Xf"][:2])
    assert feats.shape[:2] == small["Xf"][:2].shape[:2] and np.isfinite(feats).all()
    x = np.random.default_rng(0).normal(size=(3, 200))
    slow = np.array([[x[i, max(0, t - 15):t + 1].max() for t in range(200)] for i in range(3)])
    assert np.allclose(B._roll_max(x, 16), slow)


def test_detect_counts_events_and_delays():
    n, t = 2, D.PRE + D.FAULT_T
    meta = np.zeros((n, len(D.META)))
    meta[:, D.META.index("onset")] = [400, -1]
    meta[:, D.META.index("end")] = [600, -1]
    meta[:, 0] = [1, 0]
    score = np.zeros((n, t), np.float32)
    score[0, 437] = 5.0            # inside the fault: found after 37 s
    score[0, 300] = 5.0            # a false alarm before it
    score[0, 650] = 5.0            # after the fault: not counted
    score[0, 1300] = 5.0
    score[1, 1000] = 5.0
    found, delay, fp = B.detect(score, meta, 1.0)
    assert found.tolist() == [True, False] and delay[0] == 37.0 and math.isnan(delay[1])
    assert fp.tolist() == [1, 1]


def test_onset_context_flags_alarms_already_on():
    """B-118 N10: an alarm that is on before the onset makes detect() count the event at once (delay 0); onset_context
    says so, and a quiet minute before the onset is reported apart."""
    n, t = 3, D.PRE + D.FAULT_T
    meta = np.zeros((n, len(D.META)))
    meta[:, D.META.index("onset")] = [400, 400, 400]
    meta[:, D.META.index("end")] = [600, 600, 600]
    meta[:, 0] = [1, 1, 1]
    score = np.zeros((n, t), np.float32)
    score[0, 380:420] = 5.0        # on across the onset: found at once
    score[1, 350] = 5.0            # one alarm 50 s before, then a real detection
    score[1, 430] = 5.0
    score[2, 300] = 5.0            # 100 s before: still a quiet minute
    found, delay, _ = B.detect(score, meta, 1.0)
    on, quiet = B.onset_context(score, meta, 1.0)
    assert found.tolist() == [True, True, False] and delay[0] == 0.0
    assert on.tolist() == [True, False, False]
    assert quiet.tolist() == [False, False, True]


def test_model_forward_shape_and_causality():
    torch = pytest.importorskip("torch")
    torch.manual_seed(0)
    m = M.make_model({"arch": "tcn", "channels": 8, "kernel": 3, "dilations": [1, 2, 4], "residual": True})
    assert m.rf == 15
    x = torch.randn(2, 60, len(F.FEATURES))
    y = m(x)
    assert tuple(y.shape) == (2, 60)
    x2 = x.clone()
    x2[:, 40:] += 1.0
    assert torch.allclose(m(x2)[:, :40], y[:, :40])                # the future does not change the past
    x3 = x.clone()
    x3[:, :20] += 1.0
    assert torch.allclose(m(x3)[:, 20 + m.rf - 1:], y[:, 20 + m.rf - 1:], atol=1e-6)   # nor anything beyond W
    assert 5000 <= M.n_params(M.make_model({"arch": "tcn", "channels": 24, "kernel": 3,
                                            "dilations": [1, 2, 4, 8, 16, 32]})) <= 30000


def test_policy_json_round_trip():
    torch = pytest.importorskip("torch")
    torch.manual_seed(1)
    m = M.make_model({"arch": "tcn", "channels": 8, "kernel": 3, "dilations": [1, 2, 4], "residual": True})
    doc = json.loads(json.dumps(M.to_doc(m, "test")))
    pol = M.Policy(doc=doc)
    x = (np.random.default_rng(2).normal(size=(5, 40, len(F.FEATURES))) * 3).astype(np.float32)
    ref = M.score_streams(m, x)[:, -1]
    assert np.allclose(pol(x[:, -pol.window:]), ref, atol=1e-5)
    assert abs(pol(x[0, -pol.window:]) - ref[0]) < 1e-5
    m2 = M.from_doc(doc)
    assert np.array_equal(M.get_flat(m), M.get_flat(m2))
    v = M.get_flat(m) + 0.5
    M.set_flat(m, v)
    assert np.array_equal(M.get_flat(m), v)


def test_committed_policy_matches_its_check_file():
    path = os.path.join(ROOT, "data", "policies", "integrity_net_v1.json")
    if not os.path.isfile(path):
        pytest.skip("integrity_net_v1.json not exported yet")
    pol = M.Policy(path)
    chk = json.load(open(path.replace(".json", ".check.json"), encoding="utf-8"))
    out = pol(np.array(chk["obs"]))
    assert np.allclose(out, chk["expected"], atol=chk["tolerance"])
    assert 5000 <= pol.doc["n_params"] <= 30000


def test_landscape_grid_centre_is_the_final_loss():
    torch = pytest.importorskip("torch")
    torch.manual_seed(3)
    m = M.make_model({"arch": "tcn", "channels": 4, "kernel": 3, "dilations": [1, 2], "residual": True})
    rng = np.random.default_rng(4)
    X = rng.normal(size=(4, 80, len(F.FEATURES))).astype(np.float32)
    y = (rng.random((4, 80)) < 0.3).astype(np.float32)
    opt = torch.optim.SGD(m.parameters(), lr=0.05)
    W = [M.get_flat(m)]
    for _ in range(6):
        opt.zero_grad()
        torch.nn.functional.binary_cross_entropy_with_logits(m(torch.from_numpy(X)), torch.from_numpy(y)).backward()
        opt.step()
        W.append(M.get_flat(m))
    W = np.array(W, np.float64)

    def loss(vec):
        M.set_flat(m, vec)
        with torch.no_grad():
            return float(torch.nn.functional.binary_cross_entropy_with_logits(m(torch.from_numpy(X)),
                                                                              torch.from_numpy(y)))

    pca = L.pca_plane(W)
    assert abs(np.dot(pca["e1"], pca["e2"])) < 1e-9 and abs(np.linalg.norm(pca["e1"]) - 1) < 1e-9
    assert np.allclose(pca["xy"][-1], 0.0) and 0 < pca["explained"].sum() <= 1 + 1e-12
    xs = L.axis_through_zero(pca["xy"][:, 0].min(), pca["xy"][:, 0].max(), n=7)
    ys = L.axis_through_zero(pca["xy"][:, 1].min(), pca["xy"][:, 1].max(), n=7)
    assert len(xs) >= 7 and 0.0 in xs and 0.0 in ys
    assert xs[0] <= pca["xy"][:, 0].min() and xs[-1] >= pca["xy"][:, 0].max()
    Z = L.grid_loss(loss, W[-1], pca["e1"], pca["e2"], xs, ys)
    final = loss(W[-1])
    assert abs(L.nearest_node(xs, ys, Z, 0.0, 0.0) - final) < 1e-7
    # with one straight step the path lies in the plane: the plane's loss at a projected point is the recorded loss
    for k in range(len(W)):
        on_plane = loss(W[-1] + pca["xy"][k, 0] * pca["e1"] + pca["xy"][k, 1] * pca["e2"])
        assert abs(on_plane - loss(W[k])) < 0.05 + 5 * pca["resid_rel"][k]
    shapes = [tuple(p.shape) for p in m.parameters()]
    d = L.filter_normalised_direction(shapes, W[-1], rng)
    i = 0
    for shp in shapes:
        n = int(np.prod(shp))
        if len(shp) > 1:
            assert np.allclose(np.linalg.norm(d[i:i + n].reshape(shp[0], -1), axis=1),
                               np.linalg.norm(W[-1][i:i + n].reshape(shp[0], -1), axis=1))
        else:
            assert not d[i:i + n].any()
        i += n


def test_exported_landscape_file():
    path = os.path.join(D.DATA_DIR, "landscape.json")
    if not os.path.isfile(path):
        pytest.skip("landscape.json not exported yet")
    assert os.path.getsize(path) < 300_000
    doc = json.load(open(path, encoding="utf-8"))
    p = doc["pca"]
    assert len(p["x"]) >= 41 and len(p["y"]) >= 41 and 0.0 in p["x"] and 0.0 in p["y"]
    centre = p["val"][p["y"].index(0.0)][p["x"].index(0.0)]
    assert abs(centre - p["path"][-1]["val_loss"]) <= 2e-3 * abs(centre)       # equal up to 4-digit rounding
    assert p["path"][-1]["x"] == 0.0 and p["path"][-1]["y"] == 0.0
    assert len(doc["random"]["val"]) == 41 and len(doc["interp"]["alpha"]) == len(doc["interp"]["val"])


def test_policy_refuses_other_files():
    """The review's nn test: the integrity Policy loads its own file and refuses any other policy or a doc whose
    features differ (its two guard clauses)."""
    import copy
    p = os.path.join(D.ROOT, "data", "policies", "integrity_net_v1.json")
    if not os.path.isfile(p):
        pytest.skip("integrity policy not exported")
    pol = M.Policy(p)
    assert np.isfinite(pol(np.zeros((pol.window, len(F.FEATURES))))).all()
    with pytest.raises(ValueError):
        M.Policy(os.path.join(D.ROOT, "data", "policies", "atc_bid_v1.json"))   # the auction's bid policy
    doc = json.load(open(p, encoding="utf-8"))
    for bad in (dict(doc, format="other"), dict(doc, env="other")):
        with pytest.raises(ValueError):
            M.Policy(doc=bad)
    d2 = copy.deepcopy(doc)
    d2["obs"]["names"] = list(reversed(d2["obs"]["names"]))
    with pytest.raises(ValueError):
        M.Policy(doc=d2)


def test_evaluate_addenda_checked_before_writing(monkeypatch, tmp_path):
    """B-120 E: --resample-counts and --onset-fa write only reproduced addenda, one key at a time; a rerun of the
    evaluation carries the B-118 addenda over (before, it kept only "landscape")."""
    from lunarsim.nn import evaluate as E
    path = tmp_path / "E56.json"
    path.write_text(json.dumps({"test": {"x": 1}, "h15_resample_counts_b118": {"old": True}}))
    monkeypatch.setattr(E, "RESULT", str(path))
    E._store("h15_resample_counts_b118", {"new": True})
    doc = json.loads(path.read_text())
    assert doc == {"test": {"x": 1}, "h15_resample_counts_b118": {"new": True}}
    ok = {"sets": {"test": {"a|b|c": {"reproduces_stored_interval": True}}}}
    bad = {"sets": {"test": {"a|b|c": {"reproduces_stored_interval": False}}}}
    assert E.resample_counts_not_reproduced(ok) == [] and E.resample_counts_not_reproduced(bad) == ["test:a|b|c"]
    ev = {"events": {"all": {"recall_reproduces_stored": True}}, "fa_ci95_200_reproduces_stored": False}
    assert E.onset_fa_not_reproduced({"sets": {"test": {"net": {"day": ev}}}}) == [("test", "net", "day", "fa")]
    assert {"landscape", "h15_resample_counts_b118", "onset_context_and_fa_interval_b118"} <= set(E.CARRY_KEYS)


def test_old_checkpoint_is_refused_with_its_name(small, monkeypatch, tmp_path):
    """B-120 H: a checkpoint written before 13 Nov 2026 (numpy arrays inside) cannot be resumed with
    weights_only=True; fit stops with a message that names the file and says what to do, not an UnpicklingError,
    and does not fall back to loading it unsafely."""
    import torch
    from lunarsim.nn import train as T
    monkeypatch.setattr(T, "STATE", str(tmp_path))
    os.makedirs(tmp_path / "old_run")
    ck = tmp_path / "old_run" / "ckpt.pt"
    torch.save({"model": {}, "opt": {}, "st": {"epoch": 1, "hist": np.zeros(3)}}, str(ck))
    with pytest.raises(SystemExit, match="ckpt.pt cannot be resumed .* delete it"):
        T.fit("old_run", {"epochs": 1}, 0, data={"train": small, "val": small}, log=False)
    assert ck.exists()                                   # nothing deleted or rewritten behind the user's back


def _e56_doc():
    """A minimal E56 results file with both B-118 addenda, every check passed."""
    ev = {"all": {"recall": {"mean": 0.5}}, "drift": {"recall": {"mean": 0.25}}}
    s = {"net": {"day": {"fa_per_pair_day": {"ci95": [0.3, 0.8]}, "events": ev}},
         "h15_net_against": {"chi2_step": {"drift": {"delay_median_diff_s": {"ci95": [-9.0, -1.0], "boot_n": 1000,
                                                                              "boot_at_or_above_0": 2}}}}}
    return {"dataset_sha256": "d", "thresholds_from_validation": {"net": {"day": [1.0]}}, "test": s,
            "landscape": {"x": 1}, "superseded_old": {"y": 2},
            "h15_resample_counts_b118": {"sets": {"test": {"chi2_step|drift|delay_median_diff_s": {
                "boot_n": 1000, "at_or_above_0": 2, "reproduces_stored_interval": True}}}},
            "onset_context_and_fa_interval_b118": {"sets": {"test": {"net": {"day": {
                "events": {"all": {"recall_reproduces_stored": True}, "drift": {"recall_reproduces_stored": True}},
                "fa_ci95_200_reproduces_stored": True, "fa_per_pair_day_ci95_1000": [0.31, 0.79]}}}}}}


def test_rerun_carries_an_addendum_only_while_it_still_matches():
    """B-121 2: a rerun keeps h15_resample_counts_b118 only while every set's h15_net_against (intervals and counts)
    is unchanged, and onset_context_and_fa_interval_b118 only while the dataset, the thresholds, every recall and the
    200-resample false-alarm interval are unchanged, and only if their own checks passed; otherwise it drops the
    block and names the command to run (before, both were copied with their flags unchecked)."""
    import copy
    from lunarsim.nn import evaluate as E
    prev = _e56_doc()
    out = {k: copy.deepcopy(prev[k]) for k in ("dataset_sha256", "thresholds_from_validation", "test")}
    kept, todo = E.carry_over(prev, out)
    assert set(kept) == {"landscape", "superseded_old", "h15_resample_counts_b118",
                         "onset_context_and_fa_interval_b118"} and todo == []
    o2 = copy.deepcopy(out)
    o2["test"]["h15_net_against"]["chi2_step"]["drift"]["delay_median_diff_s"]["boot_at_or_above_0"] = 3
    kept, todo = E.carry_over(prev, o2)
    assert "h15_resample_counts_b118" not in kept and "onset_context_and_fa_interval_b118" in kept
    assert len(todo) == 1 and "--resample-counts" in todo[0]
    o3 = copy.deepcopy(out)
    o3["test"]["net"]["day"]["fa_per_pair_day"]["ci95"] = [0.31, 0.79]        # e.g. the 1,000-resample interval
    kept, todo = E.carry_over(prev, o3)
    assert "onset_context_and_fa_interval_b118" not in kept and "h15_resample_counts_b118" in kept
    assert len(todo) == 1 and "--onset-fa" in todo[0]
    o4 = copy.deepcopy(out)
    o4["test"]["net"]["day"]["events"]["drift"]["recall"]["mean"] = 0.26
    assert "onset_context_and_fa_interval_b118" not in E.carry_over(prev, o4)[0]
    p2 = copy.deepcopy(prev)
    p2["h15_resample_counts_b118"]["sets"]["test"]["chi2_step|drift|delay_median_diff_s"][
        "reproduces_stored_interval"] = False
    p2["onset_context_and_fa_interval_b118"]["sets"]["test"]["net"]["day"]["fa_ci95_200_reproduces_stored"] = False
    kept, todo = E.carry_over(p2, out)
    assert not {"h15_resample_counts_b118", "onset_context_and_fa_interval_b118"} & set(kept) and len(todo) == 2
    nan = copy.deepcopy(prev)
    nan["test"]["net"]["day"]["fa_per_pair_day"]["ci95"] = [float("nan"), float("nan")]
    o5 = copy.deepcopy(nan)
    assert "onset_context_and_fa_interval_b118" in E.carry_over(nan, o5)[0]     # NaN equals NaN here
    real = os.path.join(D.ROOT, "results", "E56_integrity.json")
    if os.path.isfile(real):                       # the stored file: a rerun that reproduces it keeps both addenda
        doc = json.load(open(real, encoding="utf-8"))
        kept, todo = E.carry_over(doc, doc)
        assert {"h15_resample_counts_b118", "onset_context_and_fa_interval_b118"} <= set(kept) and todo == []


def test_resample_counts_refuses_an_empty_cache(monkeypatch, tmp_path):
    """B-121 6: --resample-counts with no <set>__kinds in EVAL_CACHE is refused and writes nothing (before, it
    passed vacuously, printed 'reproduced; written' and overwrote a good addendum with an empty one)."""
    from lunarsim.nn import evaluate as E
    path = tmp_path / "E56.json"
    path.write_text(json.dumps(_e56_doc(), indent=1))
    before = path.read_bytes()
    cache = tmp_path / "eval_arrays.npz"
    np.savez(cache, other=np.zeros(1))
    monkeypatch.setattr(E, "RESULT", str(path))
    monkeypatch.setattr(E, "EVAL_CACHE", str(cache))
    assert E.addendum_cli(["--resample-counts"]) == 1
    assert path.read_bytes() == before
    assert E.resample_counts_not_reproduced({"sets": {}}) and E.resample_counts_not_reproduced({"sets": {"test": {}}})
    assert E.onset_fa_not_reproduced({"sets": {}}) and E.onset_fa_not_reproduced({"sets": {"test": {}}})


def test_onset_fa_score_files_pass_the_fingerprint_gate(monkeypatch, tmp_path):
    """B-121 6: --onset-fa reads scores_final_*.npz through the same gate as the evaluation: an unstamped file only
    with --accept-unstamped-scores, a file with another fingerprint never; nothing is written either way."""
    from lunarsim.nn import evaluate as E
    from lunarsim.nn import train as T
    path = tmp_path / "E56.json"
    path.write_text(json.dumps(_e56_doc(), indent=1))
    before = path.read_bytes()
    monkeypatch.setattr(E, "RESULT", str(path))
    monkeypatch.setattr(T, "STATE", str(tmp_path))
    monkeypatch.setattr(E, "scores_fingerprint", lambda names: "fp")
    mf = np.zeros((2, len(D.META)))
    np.savez(tmp_path / "test.npz", mf=mf, mn=mf)
    monkeypatch.setattr(D, "cache_path", lambda split: str(tmp_path / f"{split}.npz"))
    np.savez(tmp_path / "scores_final_test_fault.npz", net=np.zeros((1, 2, 3)))
    with pytest.raises(SystemExit, match="no fingerprint"):
        E.addendum_cli(["--onset-fa"])
    np.savez(tmp_path / "scores_final_test_fault.npz", _code=np.array("other"), net=np.zeros((1, 2, 3)))
    with pytest.raises(SystemExit, match="other models or code"):
        E.addendum_cli(["--onset-fa", "--accept-unstamped-scores"])
    assert path.read_bytes() == before
    z = {"_code": np.array("fp")}
    E.score_gate(z_files(z), "x.npz", "fp", False)                  # the current fingerprint passes
    E.score_gate(z_files({}), "x.npz", "fp", True)                  # unstamped, accepted on request


class z_files(dict):
    """A stand-in for an open np.load: .files and item access."""
    @property
    def files(self):
        return list(self)
