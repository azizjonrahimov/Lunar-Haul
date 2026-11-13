"""B-100: LRIP v0.2 (95 % bound in POSITION; frame / datum / time-scale declaration in HELLO and the manifest, bound to
the key epoch) and its compatibility with v0.1 (lunarsim/schemas/lrip-v0.2.json, codec.Receiver)."""
import json
import os

import pytest

from lunarsim.atc import lrip as L
from lunarsim.atc.lrip import codec as C, manifest as M

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK, PK = C.ed25519_keys(bytes(range(32)))
KEYS = C.Keys(mac_key=bytes(range(16)), sign_key=SK, verify_key=PK, epoch=3)
POS = {"e": 12.34, "n": -5.67, "h": 1.0, "heading": 90.0, "speed": 1.2, "sigma_h": 1.0, "nav_src": 3, "moving": True}
DECL = {"link_margin": 10, "neighbours": 3, "bundles_queued": 0, "frame_id": 1, "datum_id": 1, "time_scale": 6}


def test_v01_reproduced_and_sizes():
    v01 = json.load(open(os.path.join(ROOT, "lunarsim", "schemas", "lrip-v0.1.json")))
    for m in v01["messages"]:
        assert [f[:5] for f in C.fields_for(m["name"], 1)] == [f[:5] for f in m["fields"]]
    st1, st2 = C.size_table(minor=1), C.size_table()
    moved = {k: (st1[k]["default"], st2[k]["default"]) for k in st2 if st1[k]["default"] != st2[k]["default"]}
    assert moved == {"HELLO": (30, 32)} and st2["POSITION"]["default"] == 41


def test_u95_code_never_understates():
    for b in (0.01, 0.05, 0.3, 1.0, 4.22, 15.2, 643.0, 1900.0):
        c = C.u95_code(b)
        assert C.u95_from_code(c) >= b and (c == 0 or C.u95_from_code(c - 1) < b)
    assert C.u95_from_code(C.u95_code(5000.0)) == float("inf") and C.u95_from_code(C.u95_code(None)) is None


def test_v01_position_decodes_without_bound():
    pkt = L.encode("POSITION", POS, 7, 1.0, keys=KEYS, minor=1)
    d = L.decode(pkt, keys=KEYS)
    assert d.ver == (0, 1) and "u95_code" not in d.fields and d.fields["speed"] == 1.2
    d2 = L.decode(L.encode("POSITION", dict(POS, u95_code=C.u95_code(4.2)), 7, 1.0, keys=KEYS), keys=KEYS)
    assert d2.ver == (0, 2) and C.u95_from_code(d2.fields["u95_code"]) >= 4.2


def test_declaration_rule():
    rx = L.Receiver(KEYS)
    pos = L.encode("POSITION", dict(POS, u95_code=20), 7, 2.0, keys=KEYS)
    with pytest.raises(L.LripRefError):                      # no declaration yet
        rx.accept(pos)
    rx.accept(L.encode("HELLO", DECL, 7, 1.0, auth=None))   # unauthenticated: ignored
    with pytest.raises(L.LripRefError):
        rx.accept(pos)
    rx.accept(L.encode("HELLO", DECL, 7, 1.0, keys=KEYS, minor=1))   # a v0.1 HELLO carries no declaration
    with pytest.raises(L.LripRefError):
        rx.accept(pos)
    rx.accept(L.encode("HELLO", DECL, 7, 1.0, keys=KEYS))   # authenticated v0.2 HELLO: declared under epoch 3
    d = rx.accept(pos)
    assert d.fields["frame_id"] == 1 and d.fields["time_scale"] == 6 and d.fields["u95_m"] >= 0.5
    k4 = C.Keys(mac_key=bytes(range(16)), sign_key=SK, verify_key=PK, epoch=4)
    with pytest.raises(L.LripRefError):                      # a new key epoch needs a new declaration
        rx.accept(L.encode("POSITION", POS, 7, 3.0, keys=k4))
    with pytest.raises(L.LripRefError):                      # an unauthenticated position is refused
        rx.accept(L.encode("POSITION", POS, 7, 3.0, auth=None))
    bad = L.Receiver(KEYS)
    bad.accept(L.encode("HELLO", dict(DECL, frame_id=0), 9, 1.0, keys=KEYS))      # frame 0 is never valid
    with pytest.raises(L.LripRefError):
        bad.accept(L.encode("POSITION", POS, 9, 2.0, keys=KEYS))
    m = M.example("small_rover", "0.2")
    assert not bad.declare_from_manifest(9, m, epoch=3, signed=False)
    assert bad.declare_from_manifest(9, m, epoch=3, signed=True) and bad.accept(L.encode("POSITION", POS, 9, 2.0, keys=KEYS))
    assert rx.refused_positions >= 5


def test_v02_outputs():
    p = os.path.join(ROOT, "data", "atc", "lrip", "conformance-v0.2.json")
    if not os.path.isfile(p):
        pytest.skip("v0.2 conformance not generated")
    v = json.load(open(p))
    keys = C.Keys(mac_key=bytes.fromhex(v["keys"]["aes_cmac_key_hex"]), verify_key=PK)
    for x in v["vectors"]:
        d = L.decode(bytes.fromhex(x["hex"]), auth="auto" if x["auth"] else None, keys=keys, profile=x["profile"])
        assert d.name == x["message"] and d.ver == (0, 2) and len(bytes.fromhex(x["hex"])) == x["bytes"]
