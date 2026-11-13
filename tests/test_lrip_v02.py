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
    """The v0.2 declaration rule under the receive rules of B-119: every packet authenticated, the sequence number
    rising per sender and key, the receiver's key epoch."""
    rx = L.Receiver(KEYS)
    seq = iter(range(1, 100))
    pos = lambda: L.encode("POSITION", dict(POS, u95_code=20), 7, 2.0, keys=KEYS, seq=next(seq))
    with pytest.raises(L.LripRefError):                      # no declaration yet
        rx.accept(pos())
    with pytest.raises(C.LripAuthError):                     # unauthenticated: refused (B-119 C1; was ignored)
        rx.accept(L.encode("HELLO", DECL, 7, 1.0, auth=None))
    with pytest.raises(L.LripRefError):
        rx.accept(pos())
    rx.accept(L.encode("HELLO", DECL, 7, 1.0, keys=KEYS, minor=1, seq=next(seq)))   # v0.1 HELLO: no declaration
    with pytest.raises(L.LripRefError):
        rx.accept(pos())
    rx.accept(L.encode("HELLO", DECL, 7, 1.0, keys=KEYS, seq=next(seq)))   # authenticated v0.2 HELLO: declared
    d = rx.accept(pos())
    assert d.fields["frame_id"] == 1 and d.fields["time_scale"] == 6 and d.fields["u95_m"] >= 0.5
    k4 = C.Keys(mac_key=bytes(range(16)), sign_key=SK, verify_key=PK, epoch=4)
    with pytest.raises(C.LripAuthError):                     # another key epoch than the receiver's (B-119 C3)
        rx.accept(L.encode("POSITION", POS, 7, 3.0, keys=k4, seq=next(seq)))
    rx4 = L.Receiver(k4)
    with pytest.raises(L.LripRefError):                      # under the new epoch the declaration must be renewed
        rx4.accept(L.encode("POSITION", POS, 7, 3.0, keys=k4, seq=1))
    with pytest.raises(L.LripRefError):                      # an unauthenticated position is refused
        rx.accept(L.encode("POSITION", POS, 7, 3.0, auth=None))
    bad = L.Receiver(KEYS)
    bad.accept(L.encode("HELLO", dict(DECL, frame_id=0), 9, 1.0, keys=KEYS, seq=1))   # frame 0 is never valid
    with pytest.raises(L.LripRefError):
        bad.accept(L.encode("POSITION", POS, 9, 2.0, keys=KEYS, seq=2))
    m = M.example("small_rover", "0.2")
    assert not bad.declare_from_manifest(9, m, epoch=3, signed=False)
    assert bad.declare_from_manifest(9, m, epoch=3, signed=True) and bad.accept(L.encode("POSITION", POS, 9, 2.0, keys=KEYS, seq=3))
    assert rx.refused_positions >= 4 and rx4.refused_positions == 1


def test_unauthenticated_packets_are_refused():
    """B-119 C1: every message type, not only HELLO and POSITION; and a message the schema signs must be signed."""
    rx = L.Receiver(KEYS)
    for i, nm in enumerate(n for n in C.size_table() if C.message(n)["fields"]):
        with pytest.raises((C.LripAuthError, L.LripRefError)):
            rx.accept(L.encode(nm, {}, 5, 1.0, auth=None, seq=i + 1))
    with pytest.raises(C.LripAuthError):                     # RESERVE_GRANT is signed in the schema
        rx.accept(L.encode("RESERVE_GRANT", {}, 5, 1.0, keys=KEYS, auth="mac8", seq=100))
    assert rx.accept(L.encode("RESERVE_GRANT", {}, 5, 1.0, keys=KEYS, auth="sig", seq=101)).auth == "sig"
    assert rx.refused_unauthenticated > 0 and rx.refused_unsigned == 1


def test_replay_and_freshness_are_refused():
    """B-119 C2 (note 03 E4): s > s_max per sender and key, and |t_valid - now| <= 10 s when the clock is given."""
    rx = L.Receiver(KEYS)
    st = lambda seq, t: L.encode("STATUS", {}, 4, t, keys=KEYS, seq=seq)
    assert rx.accept(st(5, 100.0), now=100.0)
    with pytest.raises(C.LripReplayError):
        rx.accept(st(5, 100.0), now=100.5)                   # the same packet again
    with pytest.raises(C.LripReplayError):
        rx.accept(st(4, 100.0), now=100.5)                   # an older counter
    with pytest.raises(C.LripReplayError):
        rx.accept(st(6, 100.0), now=111.0)                   # 11 s late
    assert rx.accept(st(6, 100.0), now=109.0)                # a stale refusal does not move the counter
    assert rx.refused_replay == 2 and rx.refused_stale == 1


def test_other_key_epoch_is_refused():
    """B-119 C3."""
    rx = L.Receiver(KEYS)
    k9 = C.Keys(mac_key=bytes(range(16)), sign_key=SK, verify_key=PK, epoch=9)
    with pytest.raises(C.LripAuthError):
        rx.accept(L.encode("STATUS", {}, 4, 1.0, keys=k9, seq=1))
    assert rx.refused_epoch == 1


def test_short_and_malformed_packets_raise_value_error():
    """B-119 C4 and C7: short input, a bad Space Packet length, malformed CBOR (truncated, wrong types, deep nesting)
    raise ValueError, never struct.error, KeyError, IndexError, TypeError or RecursionError."""
    good = L.encode("POSITION", POS, 7, 1.0, keys=KEYS)
    goodb = L.encode("POSITION", POS, 7, 1.0, keys=KEYS, profile="B")
    cases = [b"", b"\x00", good[:5], good[:13], good[:-1], good + b"\x00", bytes(40)]
    cases += [goodb[:7], goodb[:6] + b"\x9f" + goodb[7:], goodb[:6] + b"\x84\x41\x00\x00\x00\x00" + goodb[12:]]
    deep = b"\x81" * 5000 + b"\x00"
    import struct as _s
    cases.append(_s.pack(">HHH", (1 << 11) | 0x100, 3 << 14, len(deep) - 1) + deep)
    for i in range(60):                                       # every truncation and a byte flip of each packet
        cases.append(goodb[:6] + bytes([goodb[6 + i % (len(goodb) - 6)] ^ 0xFF]) + goodb[7:])
    for c in cases:
        for prof in ("N", "B"):
            try:
                L.decode(c, keys=KEYS, profile=prof)
            except ValueError:
                pass
    with pytest.raises(ValueError):
        L.decode("not bytes", keys=KEYS)


def test_cbor_rejects_malformed_input():
    from lunarsim.atc.lrip import cbor
    for bad in (b"\x82\x01", b"\x5a\xff\xff\xff\xff", b"\x7a\x00\x00\x00\x10ab", b"\xa1\x80\x01", b"\xf7",
                b"\x81" * 200 + b"\x00", b"\x9b" + b"\xff" * 8, b"\x1c"):
        with pytest.raises(ValueError):
            cbor.loads(bad)
    assert cbor.loads(cbor.dumps([1, -2, b"x", "y", {1: [True, None]}])) == [1, -2, b"x", "y", {1: [True, None]}]


def test_hello_newer_replaces_older_and_invalid_revokes():
    """B-119 C2 and C8 (the stricter reading): an older HELLO does not replace a newer declaration; an authenticated
    HELLO with invalid codes revokes the declaration in force."""
    rx = L.Receiver(KEYS)
    rx.accept(L.encode("HELLO", dict(DECL, frame_id=2), 7, 5.0, keys=KEYS, seq=1))
    rx.accept(L.encode("HELLO", dict(DECL, frame_id=1), 7, 4.0, keys=KEYS, seq=2))     # older: kept frame 2
    assert rx.decl[7].frame_id == 2
    rx.accept(L.encode("HELLO", dict(DECL, frame_id=1), 7, 6.0, keys=KEYS, seq=3))     # newer: frame 1
    assert rx.decl[7].frame_id == 1
    rx.accept(L.encode("HELLO", dict(DECL, frame_id=0), 7, 7.0, keys=KEYS, seq=4))     # invalid: revoked
    assert 7 not in rx.decl and rx.revoked_declarations == 1
    with pytest.raises(L.LripRefError):
        rx.accept(L.encode("POSITION", POS, 7, 7.5, keys=KEYS, seq=5))


def test_no_keys_warns():
    """B-119 C6: the all-zero test key and the fixed seed are never used silently."""
    with pytest.warns(C.LripInsecureKeyWarning):
        L.encode("STATUS", {}, 1, 1.0)
    with pytest.warns(C.LripInsecureKeyWarning):
        C.ed25519_keys()
    with pytest.warns(C.LripInsecureKeyWarning):
        L.Receiver()


def test_v02_outputs():
    p = os.path.join(ROOT, "data", "atc", "lrip", "conformance-v0.2.json")
    if not os.path.isfile(p):
        pytest.skip("v0.2 conformance not generated")
    v = json.load(open(p))
    keys = C.Keys(mac_key=bytes.fromhex(v["keys"]["aes_cmac_key_hex"]), verify_key=PK)
    for x in v["vectors"]:
        d = L.decode(bytes.fromhex(x["hex"]), auth="auto" if x["auth"] else None, keys=keys, profile=x["profile"])
        assert d.name == x["message"] and d.ver == (0, 2) and len(bytes.fromhex(x["hex"])) == x["bytes"]


def test_manifest_round_trip_full_and_free_text():
    """B-119 C9: both example manifests in both versions round-trip exactly, and so does a manifest whose free text
    (under a key that is not an enumerated-string key) equals a registry string, or is not in the registry at all."""
    r = M._reg()
    word = r["strings"][0]
    for v in ("0.1", "0.2"):
        for n in ("small_rover", "hopper"):
            m = M.example(n, v)
            assert M.decode(M.encode(m)) == m
            m2 = dict(m, note=word, owner_text="free text not in the registry")
            assert M.decode(M.encode(m2)) == m2
