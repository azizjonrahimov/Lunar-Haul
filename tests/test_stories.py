"""Guided stories (B-35): the number check, sources, formatting, references, and the committed stories."""
import json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pytest

from lunarsim import stories as S


def _story(numbers, text, status="published", **step):
    return {"format": "lunarsim-story", "version": 1, "id": "t", "title": "T", "status": status, "summary": "S",
            "numbers": numbers, "steps": [{"id": "a", "title": "A", "text": text, "visual": "V",
                                           "camera": {"shot": "overview"}, **step}]}


@pytest.fixture
def root(tmp_path):
    (tmp_path / "results").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "results" / "t.csv").write_text("phase,rule,delay,share,coef\nP2,a,16.2 ± 4.5,0.818,0.3\n"
                                              "P2,b,5.95 ± 1.7,0.952,-0.005\nP3,a,9.4,0.9,1\n", encoding="utf-8")
    (tmp_path / "results" / "f.json").write_text(json.dumps({"x": {"y": [1.5, 2500.0]}}))
    (tmp_path / "data" / "site_graph.json").write_text(json.dumps({"sites": [{"name": "BASE"}, {"name": "PAD_A"}]}))
    return str(tmp_path)


def _check(doc, root):
    return S.check(doc, root)


def test_typed_digits():
    assert S.typed_digits("adds {{r:x}} per km, a 3 km standoff") == ["3"]
    assert S.typed_digits("in 2028, the 3D view of P2 and P3.") == []
    assert S.typed_digits("about 1,000 rovers or 0.5 km") == ["1,000", "0.5"]
    assert S.typed_digits("E21 and LTV2") == ["E21", "LTV2"]
    assert S.typed_digits("m² and a second phase") == []          # superscripts are not typed numbers


def test_table_json_and_derive(root):
    nums = {"a": {"table": "results/t.csv", "where": {"phase": "P2", "rule": "a"}, "column": "delay", "unit": "h"},
            "b": {"table": "results/t.csv", "where": {"phase": "P2", "rule": "b"}, "column": "delay", "digits": 2, "unit": "h"},
            "pm": {"table": "results/t.csv", "where": {"phase": "P2", "rule": "a"}, "column": "delay", "part": "pm"},
            "cut": {"derive": "pct_change", "of": ["a", "b"], "transform": "neg", "digits": 0, "unit": "%"},
            "sh": {"table": "results/t.csv", "where": {"phase": "P2", "rule": "b"}, "column": "share", "scale": 100, "unit": "%"},
            "ep": {"table": "results/t.csv", "where": {"phase": "P2", "rule": "a"}, "column": "coef", "transform": "exp_pct"},
            "neg": {"table": "results/t.csv", "where": {"phase": "P2", "rule": "b"}, "column": "coef", "scale": 100, "digits": 1},
            "j": {"json": "results/f.json", "path": ["x", "y", 1], "digits": 0, "unit": "m"},
            "num": {"table": "results/t.csv", "where": {"coef": 1}, "column": "share", "digits": 2}}
    text = " ".join(f"{{{{r:{k}}}}}" for k in nums)
    doc = _story(nums, text)
    errs, pend = _check(doc, root)
    assert errs == [] and pend == []
    r = S.resolve(doc, root)["numbers"]
    assert r["a"]["text"] == "16.2 h" and r["b"]["text"] == "5.95 h" and r["pm"]["value"] == 4.5
    assert r["cut"]["text"] == "63 %" and r["cut"]["value"] == pytest.approx(100 * (16.2 - 5.95) / 16.2)
    assert r["sh"]["text"] == "95.2 %" and r["ep"]["value"] == pytest.approx(100 * (2.718281828459045 ** 0.3 - 1))
    assert r["neg"]["text"] == "−0.5" and r["j"]["text"] == "2,500 m" and r["num"]["text"] == "0.90"
    assert "results/t.csv, row phase = P2, rule = a, column delay" in r["a"]["source"]
    assert r["a"]["flag"] == "Modelled"


def test_errors_are_reported(root):
    nums = {"two": {"table": "results/t.csv", "where": {"rule": "a"}, "column": "delay"},
            "nocol": {"table": "results/t.csv", "where": {"phase": "P3"}, "column": "nope"},
            "nopm": {"table": "results/t.csv", "where": {"phase": "P3"}, "column": "delay", "part": "pm"},
            "badpath": {"json": "results/f.json", "path": ["x", "z"]},
            "unused": {"json": "results/f.json", "path": ["x", "y", 0]}}
    doc = _story(nums, "{{r:two}} {{r:nocol}} {{r:nopm}} {{r:badpath}} {{r:undeclared}} and a typed 42 km",
                 highlight=["NOWHERE"])
    errs, _ = _check(doc, root)
    text = "\n".join(errs)
    assert "2 rows match rule = a" in text and "no column nope" in text and "no ± part" in text
    assert "no x/z" in text and "{{r:undeclared}} is not declared" in text and "numbers.unused: declared but not used" in text
    assert "typed number '42'" in text and "unknown id NOWHERE" in text


def test_missing_source_is_pending_in_a_draft_only(root):
    nums = {"later": {"table": "results/table_E99.csv", "where": {"x": "y"}, "column": "v"}}
    errs, pend = _check(_story(nums, "{{r:later}}", status="draft"), root)
    assert errs == [] and pend == ["later"]
    res = S.resolve(_story(nums, "it is {{r:later}}", status="draft"), root)
    assert res["steps"][0]["text_plain"] == "it is (pending)" and res["pending"] == ["later"]
    errs, _ = _check(_story(nums, "{{r:later}}"), root)
    assert any("unresolved in a published story" in e for e in errs)


def test_derive_of_a_pending_input_is_pending(root):
    nums = {"a": {"table": "results/t.csv", "where": {"phase": "P3"}, "column": "share"},
            "later": {"table": "results/none.csv", "column": "v"},
            "d": {"derive": "diff", "of": ["a", "later"]}}
    errs, pend = _check(_story(nums, "{{r:a}} {{r:d}}", status="draft"), root)
    assert errs == [] and set(pend) == {"later", "d"}


def test_catalogue_number():
    doc = _story({"cap": {"catalog": "LTV", "quantity": "capacity_kg", "digits": 0, "unit": "kg"},
                  "h": {"catalog": "CLPS", "quantity": "dims.height_m", "digits": 2, "unit": "m"}}, "{{r:cap}} {{r:h}}")
    r = S.resolve(doc)["numbers"]
    cat = json.load(open(os.path.join(ROOT, "lunarsim", "catalog-v1.json"), encoding="utf-8"))
    ltv = next(e for e in cat["entries"] if e["id"] == "LTV")
    assert r["cap"]["value"] == ltv["capacity_kg"]["value"] and r["cap"]["flag"] == ltv["capacity_kg"]["flag"]
    assert r["h"]["text"] == "3.94 m" and r["h"]["flag"] == "Spec" and "Nova-C" in r["h"]["source"]


def test_scene_references():
    assert S.check_scene("world:P2", ROOT) is None
    assert S.check_scene("lander:CLPS/classical/p50", ROOT) is None
    assert S.check_scene("rover:BASE->DEPOT", ROOT) is None
    assert "no scene package" in S.check_scene("world:P9", ROOT)
    assert "no episode" in S.check_scene("lander:CLPS/classical/p99", ROOT)
    assert "no leg" in S.check_scene("rover:BASE->MARS", ROOT)


def test_committed_stories_check():
    results, built = S.check_all()
    assert {"pads-distance", "sharing-rovers", "learned-landing", "earth-horizon"} <= set(results)
    for stem, (errs, pend) in results.items():
        assert errs == [], (stem, errs)
        if built[stem]["status"] == "published":
            assert pend == [], stem
    assert built["earth-horizon"]["status"] == "published"   # E21 results final (stages A-C), 22 Oct 2026


def test_committed_stories_schema():
    jsonschema = pytest.importorskip("jsonschema")
    from lunarsim.formats import load_schema
    v = jsonschema.Draft202012Validator(load_schema("story-v1"))
    for p in S.story_files():
        assert list(v.iter_errors(S.load(p))) == [], p
    bad = S.load(S.story_files()[0])
    bad["numbers"]["x"] = {"table": "results/t.csv", "column": "c", "json": "results/f.json", "path": ["a"]}
    bad["steps"][0]["camera"] = {"shot": "Wide Shot"}
    assert len(list(v.iter_errors(bad))) >= 2


def test_resolved_files_are_current_for_published_stories(tmp_path):
    """data/stories/resolved/ must be rebuilt (python -m lunarsim.stories build) whenever a story or a source changes."""
    _, files = S.build(ROOT, str(tmp_path))
    committed = os.path.join(ROOT, "data", "stories", "resolved")
    for name, b in files.items():
        if name == "index.json":
            continue
        doc = json.loads(b)
        if doc["status"] != "published":
            continue
        with open(os.path.join(committed, name), encoding="utf-8") as f:
            diff = close(json.load(f), doc)
        assert not diff, f"{name} is stale (run python -m lunarsim.stories build): {diff[:5]}"


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


def test_text_sources_hash_with_lf(tmp_path):
    """A CRLF working copy hashes like the LF bytes git stores (and CI checks out)."""
    for name, eol in (("lf", b"\n"), ("crlf", b"\r\n")):
        d = tmp_path / name / "results"
        d.mkdir(parents=True)
        (d / "t.csv").write_bytes(eol.join([b"a,b", b"x,1.5", b""]))
    shas = []
    for name in ("lf", "crlf"):
        src = S.Sources(str(tmp_path / name))
        assert src.table("results/t.csv") == [{"a": "x", "b": "1.5"}]
        shas.append(src.used["results/t.csv"])
    assert shas[0] == shas[1]
