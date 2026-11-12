"""B-99: the /protocol/ and /network/ site data (data/atc/protocol): every file matches its index entry."""
import gzip
import hashlib
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data", "atc", "protocol")


def test_index_matches_files():
    p = os.path.join(D, "index.json")
    if not os.path.isfile(p):
        pytest.skip("not exported")
    idx = json.load(open(p))
    assert idx["format"] == "lunarsim-protocol-data-index"
    assert set(idx["files"]) == {"e50_layers.json", "e53_bitrate.json", "e54_timeline.json", "e55_detectors.json",
                                 "b96_landscape.json"}
    for name, e in idx["files"].items():
        b = open(os.path.join(D, name), "rb").read()
        assert len(b) == e["bytes"] and hashlib.sha256(b).hexdigest() == e["sha256"]
        assert len(gzip.compress(b, 9, mtime=0)) == e["bytes_gzip"] < 40_000
        doc = json.loads(b)
        assert doc["format"] == "lunarsim-protocol-data" and doc["version"] == 1
    e50 = json.load(open(os.path.join(D, "e50_layers.json")))
    assert set(e50["sets"]) == {"dr", "dr+ranging", "dr+ranging+fixes", "lans@2030"}
    assert all(len(v["err_m"]) == len(e50["t_h"]) for v in e50["sets"].values())
    e55 = json.load(open(os.path.join(D, "e55_detectors.json")))
    for pts in e55["curves"].values():                      # a higher threshold never raises false alarms or recall
        fa = [p[1] for p in pts]
        rc = [p[2] for p in pts]
        assert fa == sorted(fa, reverse=True) and rc == sorted(rc, reverse=True)
