"""Static scenario gallery (B-36, experiments/phase4/gallery.py): packages, settings, budget and the index."""
import importlib.util, json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pytest

_spec = importlib.util.spec_from_file_location("gallery", os.path.join(ROOT, "experiments", "phase4", "gallery.py"))
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)
GALLERY = os.path.join(ROOT, "data", "scenes", "gallery.json")


def test_cells_are_unique_and_grouped():
    ids = [c["id"] for c in G.CELLS]
    pkgs = [c["package"] for c in G.CELLS]
    assert len(G.CELLS) == 14 and len(set(ids)) == 14 and len(set(pkgs)) == 14
    assert {c["group"] for c in G.CELLS} <= {g["id"] for g in G.GROUPS}


@pytest.mark.parametrize("cell", G.CELLS, ids=[c["id"] for c in G.CELLS])
def test_package_matches_its_cell(cell):
    """Each package is the replay of its cell: scenario, job rule, seed, pad distance and Earth link as stated."""
    with open(os.path.join(ROOT, "data", "scenes", cell["package"], "scene.json"), encoding="utf-8") as f:
        idx = json.load(f)
    sc, _, _ = G.scenario_of(cell)
    assert idx["mechanism"] == cell["mechanism"] and idx["seed"] == G.REPLAY_SEED
    assert idx["pad_standoff_km"] == sc.pad_standoff_km == cell["standoff"]
    assert idx["scenario"] == cell["scenario"].split("-")[0] or idx["scenario"] == cell["scenario"]
    want = G.flags_of(cell)["earth_link"]
    got = "always" if not idx.get("comms") else idx["comms"]["mode"]
    assert want.split()[0] == got
    if cell.get("fleet_autonomy"):
        assert {v["autonomy"] for v in idx["vehicles"]} == {cell["fleet_autonomy"]}
    c = cell.get("comms")
    if isinstance(c, dict) and c.get("supervised_policy"):
        assert idx["comms"]["supervised_policy"] == c["supervised_policy"]
    yr = G.start_year_of(cell, G.REPLAY_SEED)                       # B-54: E21's year of the replay seed
    if yr is not None:
        assert idx["comms"]["start_h"] == sum(8784 if y % 4 == 0 else 8760 for y in range(2028, yr))
    assert len(idx["vehicles"]) == len(sc.fleet)
    c = idx["checks"]
    assert c["trips"] == c["trips_summary"] and abs(c["delivered_kg_cargo_table"] - c["delivered_kg_summary"]) < 1.0


def test_budget():
    from lunarsim import scene as SCN
    total = sum(SCN.gz_size(os.path.join(ROOT, "data", "scenes", c["package"])) for c in G.CELLS)
    assert total <= G.BUDGET_GZ_BYTES


def test_headline_numbers(tmp_path):
    import pandas as pd
    rows = [{"cell": "p2-marketplace", "seed": s, "delivered_kg": 1000.0 * (500 + s), "delay_prio1_mean_h": 5.0 + s,
             "delay_prio1_p90_h": 15.0, "sl24_prio1": 0.95, "cost_per_landed_kg_usd": 100.0} for s in range(4)]
    df = pd.DataFrame(rows)
    h = G.headline_numbers(df, "p2-marketplace", 4)
    assert h["n_seeds"] == 4 and h["delivered_t"]["mean"] == pytest.approx(501.5)
    assert h["delay_prio1_mean_h"]["ci95"] == pytest.approx(1.96 * pd.Series([5.0, 6, 7, 8]).std() / 2)
    assert h["sl24_prio1"]["mean"] == pytest.approx(95.0) and "blackout_wait_vehicle_h" not in h
    assert G.headline_numbers(df, "p2-marketplace", 5) is None          # a seed missing: pending, not a short mean


def close(a, b, path="") -> list:
    """Paths where two JSON documents differ, floats compared to 1e-9 relative (machines differ in the last bit)."""
    if isinstance(a, dict) and isinstance(b, dict):
        return [p for k in set(a) | set(b) for p in close(a.get(k), b.get(k), f"{path}/{k}")]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: length {len(a)} != {len(b)}"]
        return [p for i, (x, y) in enumerate(zip(a, b)) for p in close(x, y, f"{path}[{i}]")]
    if isinstance(a, float) or isinstance(b, float):
        ok = (isinstance(a, (int, float)) and isinstance(b, (int, float))
              and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12))
        return [] if ok else [f"{path}: {a!r} != {b!r}"]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def test_close_tolerates_last_bit_only():
    assert close({"a": [1.5255050330593534]}, {"a": [1.5255050330593531]}) == []
    assert close({"a": 1.0}, {"a": 1.001}) and close({"a": "x"}, {"a": "y"}) and close([1], [1, 2])


def test_committed_index_is_current_and_valid():
    if not os.path.isfile(GALLERY):
        pytest.skip("gallery.json not built yet")
    with open(GALLERY, encoding="utf-8") as f:
        doc = json.load(f)
    seeds = doc["common"]["seeds"]
    diff = close(doc, json.loads(json.dumps(G.build_index(seeds=seeds))))
    assert not diff, f"stale (run gallery.py index): {diff[:5]}"
    jsonschema = pytest.importorskip("jsonschema")
    from lunarsim.formats import load_schema
    assert list(jsonschema.Draft202012Validator(load_schema("scene-gallery-v1")).iter_errors(doc)) == []


def test_earth_story_cells_use_the_e21_settings():
    """B-54: the two cells the Earth story quotes have E21's comms settings; B-55: every earth cell has E21's year rule."""
    sys.path.insert(0, ROOT)
    from experiments.phase4.run_phase4 import comms_cfg, start_year
    cells = {c["id"]: c for c in G.CELLS}
    assert cells["p2-earth-relay-0.1"]["comms"] == comms_cfg("dte+relay", 0.1, "strict")
    assert cells["p2-earth-strategic"]["comms"] == comms_cfg("dte", None, "strategic")
    for cid in ("p2-earth-relay-0.1", "p2-earth-strategic"):
        cell = cells[cid]
        assert [G.start_year_of(cell, s) for s in range(8)] == [start_year(s) for s in range(8)]
        sc, _, _ = G.scenario_for_seed(cell, 5)
        assert sc.comms["start_year"] == 2029 and {a for _, _, a, _ in sc.fleet} == {"supervised"}
    assert all(G.start_year_of(c, 5) == 2029 for c in G.CELLS if c["group"] == "earth")   # B-55: every earth cell
    assert G.start_year_of(cells["p2-marketplace"], 5) is None                # the others keep the default year


def test_earth_headlines_equal_the_e21_cells():
    """B-55: every earth scene reproduces its E21 r2 stage A cell, so its 20-seed headline is E21's mean."""
    if not os.path.isfile(GALLERY):
        pytest.skip("gallery.json not built yet")
    import pandas as pd
    e21 = os.path.join(ROOT, "results", "E21a_comms_autonomy_r2.csv")
    if not os.path.isfile(e21):
        pytest.skip("E21 r2 table missing")
    a = pd.read_csv(e21, float_precision="round_trip")
    want = {"p2-earth-direct": ("default", "dte", None), "p2-earth-relay": ("default", "dte+relay", 0.8),
            "p2-earth-autonomous": ("autonomous", "dte", None), "p2-earth-relay-0.1": ("supervised_strict", "dte+relay", 0.1),
            "p2-earth-strategic": ("supervised_strategic", "dte", None)}
    assert set(want) == {c["id"] for c in G.CELLS if c["group"] == "earth"}
    with open(GALLERY, encoding="utf-8") as f:
        scenes = {s["id"]: s for s in json.load(f)["scenes"]}
    for cid, (mix, mode, p) in want.items():
        t = a[(a["mix"] == mix) & (a["comms"] == mode) & ((a["coverage"] == p) if p else a["coverage"].isna())]
        h = scenes[cid]["headline"]
        assert scenes[cid]["flags"]["plume"] is None and h["n_seeds"] == len(t) == 20
        for key, col, scale in (("delivered_t", "delivered_t_in_year", 1.0), ("delay_prio1_mean_h", "delay_prio1_mean_h", 1.0),
                                ("blackout_wait_vehicle_h", "blackout_wait_vehicle_h", 1.0), ("sl24_prio1", "sl24_prio1", 100.0)):
            assert h[key]["mean"] == pytest.approx(t[col].mean() * scale, rel=1e-9, abs=1e-9), (cid, key)
