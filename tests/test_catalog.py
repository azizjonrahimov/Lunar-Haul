"""Vehicle and site catalogue (lunarsim-catalog v1, B-30): schema, sources, and the link to the engine."""
import copy, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pytest

from lunarsim import catalog
from lunarsim.formats import load_schema
from lunarsim.entities import VEHICLE_CLASSES
from lunarsim.scenario import LANDER_TYPES
from lunarsim.lander.classes import CLASSES

REQUIRED_IDS = {
    "lander": {"CLPS", "MK1", "LARGE"},
    "rover": {"LTV", "HAUL", "MICRO"},
    "base": {"habitat", "pad", "solar_tower", "comms_mast", "cargo_pallet"},
    "reference": {"apollo_lrv", "nova_c", "griffin", "viper"},
}


@pytest.fixture(scope="module")
def doc():
    with open(catalog.CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_catalogue_validates(doc):
    assert catalog.validate(doc) == []
    assert doc["format"] == "lunarsim-catalog" and doc["version"] == 1


def test_required_entries_by_kind(doc):
    for kind, ids in REQUIRED_IDS.items():
        have = {e["id"] for e in catalog.entries(kind, doc)}
        assert ids <= have, f"{kind}: missing {sorted(ids - have)}"


def test_every_number_is_flagged_and_sourced(doc):
    qs = list(catalog.iter_quantities(doc))
    assert len(qs) > 100
    for eid, path, q in qs:
        assert q["flag"] in catalog.FLAGS, (eid, path)
        assert q["source"].strip(), (eid, path)
        if q["flag"] in ("Spec", "Measured"):
            assert "http" in q["source"], (eid, path, q["source"])
    for e in doc["entries"]:
        assert e["reference_vehicle"]["url"].startswith("http"), e["id"]


def test_engine_link_rovers(doc):
    """capacity, speed and night operation of every rover class equal the engine's VehicleClass."""
    for cls, vc in VEHICLE_CLASSES.items():
        e = catalog.get(cls, doc)
        assert e["kind"] == "rover"
        assert e["capacity_kg"]["value"] == vc.capacity_kg
        assert e["speed_kmh"]["value"] == vc.speed_kmh
        assert e["night_ops"]["value"] is vc.night_ops


def test_engine_link_landers(doc):
    """Gate masses and thrusts equal lunarsim/lander/classes.py; payloads equal LANDER_TYPES."""
    for cls, lc in CLASSES.items():
        g = catalog.get(cls, doc)["gate"]
        for k in catalog.GATE_KEYS:
            assert g[k]["value"] == getattr(lc, k), (cls, k)
            assert g[k]["flag"] == lc.flags[k], (cls, k)
    for cls, lt in LANDER_TYPES.items():
        e = catalog.get(cls, doc)
        assert e["capacity_kg"]["value"] == lt.payload_kg[1]
        assert e["max_item_kg"]["value"] == lt.max_item_kg


def test_engine_mismatches_empty_and_detects_drift(doc):
    assert catalog.engine_mismatches(doc) == []
    bad = copy.deepcopy(doc)
    catalog.get("LTV", bad)["capacity_kg"]["value"] = 800
    catalog.get("MK1", bad)["gate"]["t_max_n"]["value"] = 40000.0
    mism = catalog.engine_mismatches(bad)
    assert any(m.startswith("LTV.capacity_kg") for m in mism)
    assert any(m.startswith("MK1.gate.t_max_n") for m in mism)


def test_plume_classes_and_flags_for_3d(doc):
    plume = {e["id"]: e["plume_class"] for e in catalog.entries("lander", doc)}
    assert plume["MK1"] == "hydrolox"          # BE-7, nearly invisible plume
    assert plume["LARGE"] == "methalox"
    for e in catalog.entries("rover", doc):
        assert e["plume_class"] == "none"
    assert catalog.get("HAUL", doc)["representative"] is True
    assert catalog.get("HAUL", doc)["reference_vehicle"]["status"] == "concept"
    assert catalog.get("MK1", doc)["representative"] is True
    assert catalog.get("LARGE", doc)["representative"] is True


def test_dimensions_are_plausible(doc):
    """Cheap physical sanity: true-scale numbers the 3D kit builds from."""
    v = lambda i, p: catalog.value(i, p, doc)
    assert v("MK1", "dims.height_m") == 8.05 and v("MK1", "dims.diameter_m") == 3.08
    assert v("LARGE", "dims.height_m") == 52 and v("LARGE", "dims.diameter_m") == 9
    assert v("apollo_lrv", "dims.wheel_d_m") == 0.818 and v("apollo_lrv", "dims.wheelbase_m") == 2.3
    for e in catalog.entries(doc=doc):
        d = e["dims"]
        if "leg_span_m" in d and "diameter_m" in d:
            assert d["leg_span_m"]["value"] >= d["diameter_m"]["value"], e["id"]
        if "wheelbase_m" in d and "length_m" in d:
            assert d["wheelbase_m"]["value"] <= d["length_m"]["value"], e["id"]
        if "track_m" in d and "width_m" in d:
            assert d["track_m"]["value"] <= d["width_m"]["value"], e["id"]
        if "wheel_d_m" in d and "height_m" in d:
            assert d["wheel_d_m"]["value"] < d["height_m"]["value"], e["id"]


def test_accessors(doc):
    assert catalog.get("MK1")["kind"] == "lander"
    assert catalog.value("LTV", "capacity_kg") == VEHICLE_CLASSES["LTV"].capacity_kg
    assert catalog.quantity("MK1", "dims.height_m")["flag"] in catalog.FLAGS
    with pytest.raises(KeyError):
        catalog.get("NOPE")
    with pytest.raises(KeyError):
        catalog.value("MK1", "dims.no_such_dim")
    assert all(q["flag"] == "Assumed" for _, _, q in catalog.flagged("Assumed"))


@pytest.mark.parametrize("mutate,expect", [
    (lambda d: d["entries"][0]["dims"]["height_m"].pop("source"), "quantity missing"),
    (lambda d: d["entries"][0]["dims"]["height_m"].__setitem__("flag", "Guess"), "flag 'Guess'"),
    (lambda d: d["entries"][0].__setitem__("kind", "ship"), "kind 'ship'"),
    (lambda d: d["entries"].append(copy.deepcopy(d["entries"][0])), "duplicate id"),
    (lambda d: d["entries"][0]["dims"].__setitem__("height_m", 3.9), "expected a quantity"),
    (lambda d: d["entries"][0].__setitem__("extra_number", 7), "unknown keys"),
    (lambda d: d["entries"][0]["dims"].__setitem__("leg_count", {"value": 4.5, "unit": "", "flag": "Spec",
                                                                "source": "https://x"}), "non-negative integer"),
    (lambda d: d["entries"][0]["dims"]["height_m"].update(flag="Spec", source="from memory"), "needs a URL"),
    (lambda d: d["entries"][0]["materials"].append("unobtainium"), "unknown material tags"),
    (lambda d: d["entries"][0].__setitem__("notes", {"n": 3}), "bare number"),
])
def test_validator_catches(doc, mutate, expect):
    bad = copy.deepcopy(doc)
    mutate(bad)
    errs = catalog.validate(bad)
    assert any(expect in e for e in errs), errs


def test_schema_file_and_optional_jsonschema(doc):
    schema = load_schema("catalog-v1")
    assert schema["title"] == "lunarsim-catalog v1"
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(doc, schema)


def test_cli_lists_assumed(capsys):
    assert catalog.main(["--flag", "Assumed"]) == 0
    out = capsys.readouterr().out
    assert "engine link OK" in out and "-- Assumed --" in out
