"""Learned rover driver (B-13/B-18): the exported ONNX reproduces its check vectors, and the F-17 parity fixture
(tests/fixtures/rover_driver_parity.json, made by tests/fixtures/make_rover_driver_parity.py) reproduces.
Skipped cleanly when onnxruntime or the policy files are absent."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pytest

pytest.importorskip("onnxruntime")

CARD = os.path.join(ROOT, "data", "policies", "rover_bc_s0.json")
CHECK = os.path.join(ROOT, "data", "policies", "rover_bc_s0.check.json")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "rover_driver_parity.json")
if not os.path.exists(CARD):
    pytest.skip("data/policies/rover_bc_s0.json not present", allow_module_level=True)


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def driver():
    from lunarsim.rover.onnx_driver import OnnxDriver
    return OnnxDriver(CARD)                      # also verifies the card's onnx_sha256


def test_card_is_a_cnn_policy(driver):
    from lunarsim.rover.env import PATCH, SCALAR_NAMES
    c = driver.card
    assert (c["format"], c["kind"], c["id"]) == ("lunarsim-policy", "cnn", "rover_bc_s0")
    assert len(SCALAR_NAMES) == 5 and PATCH == 32


def test_check_vectors_reproduce(driver):
    chk = _load(CHECK)
    assert chk["policy"] == driver.id
    out = driver.act_batch(np.asarray(chk["patch"], np.float32), np.asarray(chk["scalars"], np.float32))
    np.testing.assert_allclose(out, np.asarray(chk["action"]), rtol=0, atol=chk.get("tolerance", 1e-5))


@pytest.mark.skipif(not os.path.exists(FIXTURE), reason="parity fixture not generated yet")
def test_parity_fixture_actions(driver):
    fx = _load(FIXTURE)
    assert fx["format"] == "lunarsim-rover-driver-parity" and fx["policy"] == driver.id
    assert fx["onnx_sha256"] == driver.card.get("onnx_sha256")
    assert len(fx["steps"]) == 40 and os.path.getsize(FIXTURE) < 1.5e6
    tol = fx["tolerance"]["action_given_stored_obs"]
    for st in fx["steps"]:
        a = driver.act({"patch": np.asarray(st["patch"], np.float32), "scalars": np.asarray(st["scalars"], np.float32)})
        np.testing.assert_allclose(a, st["action"], rtol=0, atol=tol, err_msg=f"step {st['k']}")


@pytest.mark.skipif(not os.path.exists(FIXTURE), reason="parity fixture not generated yet")
def test_parity_fixture_first_observations_and_final():
    """The env still produces the stored observations; the closed-loop drive still ends with the stored telemetry."""
    pytest.importorskip("gymnasium")
    sys.path.insert(0, os.path.join(ROOT, "tests", "fixtures"))
    import make_rover_driver_parity as M
    fx = _load(FIXTURE)
    doc = M.build(CARD)
    for a, b in zip(doc["steps"][:5], fx["steps"][:5]):
        np.testing.assert_allclose(a["scalars"], b["scalars"], rtol=0, atol=2e-6)
        np.testing.assert_allclose(a["patch"], b["patch"], rtol=0, atol=2e-6)
    assert doc["final"]["steps"] == fx["final"]["steps"]
    assert doc["final"]["interventions"] == fx["final"]["interventions"]
    for k in ("elapsed_s", "path_m", "energy_wh", "slip_mean"):
        assert doc["final"][k] == pytest.approx(fx["final"][k], rel=1e-6, abs=1e-6), k
