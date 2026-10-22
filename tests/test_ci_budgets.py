"""CI gates (B-38, tools/ci/budgets.py): per-page budgets on a synthetic build, schema validation targets."""
import json, os, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "ci"))
import pytest

import budgets as B


def _site(tmp):
    d = tmp / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "world").mkdir()
    (d / "terrain").mkdir()
    (d / "assets" / "main-abc.js").write_bytes(b"console.log('x');" * 2000)
    (d / "assets" / "dep-def.js").write_bytes(b"export const a = 1;" * 500)
    (d / "assets" / "style-1.css").write_text("body{color:red}" * 300)
    (d / "terrain" / "h.png").write_bytes(os.urandom(30000))             # incompressible, like a PNG
    (d / "index.html").write_text('<html><head><script type="module" crossorigin src="/Lunar-Haul/assets/main-abc.js">'
                                  '</script><link rel="modulepreload" href="/Lunar-Haul/assets/dep-def.js">'
                                  '<link rel="stylesheet" href="/Lunar-Haul/assets/style-1.css"></head></html>')
    (d / "world" / "index.html").write_text('<script type="module" src="../assets/main-abc.js"></script>')
    return d


def test_measure_page_js_css_and_declared_data(tmp_path):
    d = _site(tmp_path)
    budgets = {"defaults": {"js_gzip_kb": 100, "css_gzip_kb": 100}, "site_total_mb": 10,
               "pages": {"index.html": {"data": ["terrain/*.png"], "data_gzip_kb": 100}}}
    rows, errs = B.check_pages(str(d), budgets)
    r = {x["page"]: x for x in rows}
    assert errs == []
    assert r["index.html"]["n_js"] == 2 and r["index.html"]["css_gzip_kb"] > 0
    assert r["index.html"]["data_gzip_kb"] == pytest.approx(B.gz(str(d / "terrain" / "h.png")) / 1024)
    assert r["world/index.html"]["n_js"] == 1 and r["world/index.html"]["data_gzip_kb"] == 0     # relative src resolves


def test_violations_missing_files_and_stale_entries(tmp_path):
    d = _site(tmp_path)
    budgets = {"defaults": {"js_gzip_kb": 0.01, "css_gzip_kb": 100}, "site_total_mb": 0.001,
               "pages": {"index.html": {"data": ["terrain/none.bin"], "data_gzip_kb": 1}, "gone/index.html": {}}}
    _, errs = B.check_pages(str(d), budgets)
    text = "\n".join(errs)
    assert "index.html: js_gzip_kb" in text and "missing terrain/none.bin" in text
    assert "gone/index.html, which the build does not have" in text and "site total" in text
    assert B.main(["pages", "--dist", str(d), "--budgets", _write(tmp_path, budgets)]) == 1


def _write(tmp, doc):
    p = tmp / "b.json"
    p.write_text(json.dumps(doc))
    return str(p)


def test_propose_rounds_up_with_margin(tmp_path):
    rows = [{"page": "a/index.html", "js_gzip_kb": 41.0, "css_gzip_kb": 0.2, "data_gzip_kb": 0, "spec": {}},
            {"page": "(site total)", "total_mb": 1, "spec": {}}]
    p = B.propose(rows)
    assert p == {"a/index.html": {"js_gzip_kb": 55, "css_gzip_kb": 5}}


def test_committed_budgets_file_is_consistent():
    b = json.load(open(B.BUDGETS, encoding="utf-8"))
    assert b["version"] == 1 and b["site_total_mb"] <= 1000
    for page, s in b["pages"].items():
        assert page.endswith(".html")
        if "data" in s:
            assert "data_gzip_kb" in s and all(isinstance(g, str) for g in s["data"])
        if "lazy" in s:
            assert "lazy_gzip_kb" in s and all(isinstance(g, str) for g in s["lazy"])
    dist = os.path.join(ROOT, "site", "dist")
    if os.path.isdir(dist):                                   # a local build exists: today's site meets its budgets
        if not os.path.isdir(os.path.join(dist, "simulator", "engine")):
            pytest.skip("site/dist is a bare `vite build` (no simulator/engine): run `npm run build` for the full site")
        _, errs = B.check_pages(dist, b)
        assert errs == [], errs


def test_classic_scripts_and_lazy_chunks(tmp_path):
    """Classic <script src> files count with the page JS; a declared lazy entry chunk is measured with its static
    imports (minus files the page already loaded), reported and budgeted separately."""
    d = _site(tmp_path)
    (d / "simulator" / "engine").mkdir(parents=True)
    (d / "simulator" / "engine" / "sim.js").write_bytes(b"var a=1;" * 3000)
    (d / "assets" / "plot-marks-abc.js").write_text('import{x}from"./src-def.js";import"./dep-def.js";export const p=x;')
    (d / "assets" / "src-def.js").write_bytes(b"export const x=1;" * 4000)
    (d / "simulator" / "index.html").write_text('<script defer src="/Lunar-Haul/simulator/engine/sim.js"></script>'
                                                '<script>inline()</script><script type="module" src="/assets/dep-def.js">'
                                                '</script>')
    budgets = {"defaults": {"js_gzip_kb": 100, "css_gzip_kb": 100}, "site_total_mb": 10,
               "pages": {"simulator/index.html": {"lazy": ["assets/plot-marks-*.js"], "lazy_gzip_kb": 100}}}
    rows, errs = B.check_pages(str(d), budgets)
    r = next(x for x in rows if x["page"] == "simulator/index.html")
    assert errs == [] and r["n_classic"] == 1 and r["n_js"] == 2          # base prefix stripped; inline ignored
    assert r["js_gzip_kb"] == pytest.approx((B.gz(str(d / "simulator/engine/sim.js")) + B.gz(str(d / "assets/dep-def.js"))) / 1024)
    want = (B.gz(str(d / "assets/plot-marks-abc.js")) + B.gz(str(d / "assets/src-def.js"))) / 1024     # dep-def already loaded
    assert r["n_lazy"] == 2 and r["lazy_gzip_kb"] == pytest.approx(want)
    budgets["pages"]["simulator/index.html"]["lazy_gzip_kb"] = 0.01
    _, errs = B.check_pages(str(d), budgets)
    assert any("lazy_gzip_kb" in e for e in errs)
    assert B.propose(rows)["simulator/index.html"]["lazy"] == ["assets/plot-marks-*.js"]
    budgets["pages"]["simulator/index.html"]["lazy"] = ["assets/none-*.js"]
    _, errs = B.check_pages(str(d), budgets)
    assert any("missing assets/none-*.js" in e for e in errs)
    (d / "simulator" / "engine" / "sim.js").unlink()
    _, errs = B.check_pages(str(d), {"defaults": {"js_gzip_kb": 100, "css_gzip_kb": 100}, "pages": {}})
    assert any("missing" in e and "sim.js" in e for e in errs)


def test_schema_targets_cover_every_format():
    names = {s for _, s in B.schema_targets()}
    assert {"catalog-v1", "routes-v1", "trajectories-v1", "earth-link-v1", "scene-v1", "scenario-v1", "trace-v1",
            "trace-v2"} <= names


def test_schema_check_catches_a_broken_file(tmp_path):
    pytest.importorskip("jsonschema")
    (tmp_path / "lunarsim").mkdir()
    doc = json.load(open(os.path.join(ROOT, "lunarsim", "catalog-v1.json"), encoding="utf-8"))
    doc["entries"][0]["dims"]["height_m"]["flag"] = "Guess"
    (tmp_path / "lunarsim" / "catalog-v1.json").write_text(json.dumps(doc))
    done, errs = B.check_schemas(str(tmp_path))
    assert done == [("lunarsim/catalog-v1.json", "catalog-v1", done[0][2])] and done[0][2] >= 2
    assert any("[catalog-v1]" in e for e in errs) and any("Python validator" in e for e in errs)
