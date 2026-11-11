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


def test_model_forward_shape_and_causality():
    import torch
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
    import torch
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
    import torch
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
