"""B-93: LRIP v0.1 codec, versioning, security, capability manifest, the auction's opt-in filter and E53 files."""
import json
import os

import numpy as np
import pytest

from lunarsim.atc import lrip as L
from lunarsim.atc.lrip import cbor, codec as C, manifest as M

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK, PK = C.ed25519_keys(bytes(range(32)))
KEYS = C.Keys(mac_key=bytes(range(16)), sign_key=SK, verify_key=PK, epoch=3)


def random_values(name, rng):
    vals = {}
    for f in C.message(name)["fields"]:
        n, typ, bits, scale = f[0], f[1], f[2], f[3]
        if typ == "spare":
            continue
        if typ == "flag":
            vals[n] = bool(rng.integers(0, 2))
        elif typ == "flags":
            vals[n] = int(rng.integers(0, 1 << bits))
        elif typ.startswith("enum"):
            vals[n] = int(rng.choice([int(k) for k in C.schema()["enums"][typ.split(":")[1]] if k.isdigit()]))
        elif typ == "int":
            q = int(rng.integers(-(1 << (bits - 1)), 1 << (bits - 1)))
            vals[n] = q * scale
        else:
            vals[n] = int(rng.integers(0, 1 << bits)) * scale
    return vals


def close(a, b):
    return all(abs(float(a[k]) - float(b[k])) < 1e-9 for k in a)


def test_sizes_match_note03():
    """Note 03 C2 / Table B5: secured bytes on the air (MAC 8 B; awards and grants signed), v0.1 packets."""
    st = C.size_table(minor=1)
    want = {"POSITION": 41, "STATUS": 43, "INTENT": 38, "ALERT": 42, "TASK_ANNOUNCE": 44, "TASK_BID": 37,
            "TASK_AWARD": 92, "TASK_STATE": 33, "RESERVE_REQ": 35, "RESERVE_GRANT": 94, "RESERVE_RELEASE": 31,
            "CAP_QUERY": 31, "MAP_NOTICE": 38, "HELLO": 30}
    assert {k: st[k]["default"] for k in want} == want
    assert st["POSITION"]["mac16"] == 49 and st["ALERT"]["signed"] == 98 and st["POSITION"]["unsecured"] == 27
    assert {k: C.payload_bits(k, 1) for k in ("POSITION", "STATUS", "TASK_BID", "ALERT")} == \
        {"POSITION": 104, "STATUS": 120, "TASK_BID": 72, "ALERT": 112}


@pytest.mark.parametrize("profile", ["N", "B"])
def test_round_trip_every_message(profile):
    rng = np.random.default_rng(7)
    for m in C.schema()["messages"]:
        nm = m["name"]
        if not m["fields"]:
            continue
        for auth in (C.default_auth(nm), None, "mac16"):
            for _ in range(20):
                v = random_values(nm, rng)
                pkt = L.encode(nm, v, sender=int(rng.integers(0, 65536)), t_valid_s=123.4, seq=9, auth=auth, keys=KEYS,
                               profile=profile)
                if profile == "N":
                    assert len(pkt) == C.packet_bytes(nm, auth)
                d = L.decode(pkt, auth=auth, keys=KEYS, profile=profile)
                assert d.name == nm and d.auth == auth and close(v, d.fields) and d.t_valid_s == pytest.approx(123.4)


def test_tamper_and_auto_detection():
    v = {"e": 1.0, "n": 2.0, "h": 0.0, "heading": 10.0, "speed": 0.5, "sigma_h": 1.0, "nav_src": 1, "moving": True}
    pkt = bytearray(L.encode("POSITION", v, 7, 1.0, seq=1, keys=KEYS))
    assert L.decode(bytes(pkt), keys=KEYS).fields["speed"] == 0.5
    pkt[16] ^= 1
    with pytest.raises(L.LripAuthError):
        L.decode(bytes(pkt), keys=KEYS)
    rng = np.random.default_rng(1)
    for _ in range(50):                                 # signed packets are found by "auto" even when the signature's
        a = L.encode("TASK_AWARD", random_values("TASK_AWARD", rng), 1, 2.0, seq=3, auth="sig", keys=KEYS)
        assert L.decode(a, keys=KEYS).auth == "sig"       # bytes happen to look like a MAC trailer's SPI
    bad = C.Keys(mac_key=b"\x01" * 16, verify_key=PK)
    with pytest.raises(L.LripAuthError):
        L.decode(L.encode("HELLO", {"link_margin": 3}, 1, 0.0, keys=KEYS), auth="mac8", keys=bad)


def test_versioning_rule():
    """Note 03 C4: appended fields of a later minor version are skipped; an unknown type is counted and dropped; an
    unknown enumeration value reads as the most cautious one; another major version is refused."""
    v = {"alert_id": 1, "type": 2, "severity": 1, "e": 0.0, "n": 0.0, "radius": 50, "valid": 60, "subject_id": 0,
         "ack": False, "repeat": 0}
    pkt = L.encode("ALERT", v, 5, 10.0, auth=None, minor=2, extra=b"\xab\xcd\xef")
    d = L.decode(pkt, auth=None)
    assert d.ver == (0, 2) and d.skipped_bytes == 3 and d.fields["radius"] == 50
    pkt_b = L.encode("ALERT", v, 5, 10.0, auth=None, profile="B", extra=b"")
    assert L.decode(pkt_b, auth=None, profile="B").fields["valid"] == 60
    unk = dict(v, type=63)                               # a type code a later minor version may add
    assert L.decode(L.encode("ALERT", unk, 5, 10.0, auth=None), auth=None).fields["type"] == 3      # hazard
    st = {"mode": 15}
    assert L.decode(L.encode("STATUS", st, 5, 0.0, auth=None), auth=None).fields["mode"] == 8      # fault
    raw = bytearray(L.encode("HELLO", {}, 5, 0.0, auth=None))
    raw[6] = (1 << 4) | 0                                # major 1
    with pytest.raises(L.LripVersionError):
        L.decode(bytes(raw), auth=None)
    cnt = L.Counters()
    raw = bytearray(L.encode("HELLO", {}, 5, 0.0, auth=None))
    raw[1] = (raw[1] & 0x00) | 0x50                      # APID 0x550 = an unknown message type 80
    raw[7] = 80
    assert L.decode(bytes(raw), auth=None, counters=cnt) is None and cnt.unknown_type == 1


def test_cbor_shortest_heads():
    """RFC 8949: below 24 one byte, below 256 two, below 65,536 three, below 2^32 five (note 03 E2)."""
    assert [len(cbor.dumps(x)) for x in (23, 24, 255, 256, 65535, 65536, -1, -25)] == [1, 2, 2, 3, 3, 5, 1, 2]
    x = {1: [1, -2, "a", b"\x00", True, None], "k": {2: 3}}
    assert cbor.loads(cbor.dumps(x)) == x


def test_manifest_examples_compact_and_can_do():
    for nm, js in (("small_rover", 1200), ("hopper", 1210)):
        m = M.example(nm)
        assert len(M.minified_json(m)) == js                       # note 03 C3 minified JSON sizes
        d = M.decode(M.encode(m))
        assert d["vehicle"] == m["vehicle"] and d["rev"] == m["rev"]
        assert [c["name"] for c in d["capabilities"]] == [c["name"] for c in m["capabilities"]]
        assert len(M.encode(m)) < 300
    sr, hp = M.example("small_rover"), M.example("hopper")
    carry = {"capability": "transport.carry", "ver": "1.0", "params": {"mass_kg": 150, "interface": ["tray-A"]}}
    assert M.can_do(carry, sr) and not M.can_do(carry, hp)
    assert not M.can_do(dict(carry, params={"mass_kg": 250}), sr)
    assert not M.can_do(dict(carry, params={"interface": ["tray-B"]}), sr)
    assert not M.can_do(dict(carry, ver="2.0"), sr) and not M.can_do(dict(carry, ver="1.1"), sr)
    assert M.can_do({"capability": "survey.image", "ver": "1.0", "params": {"gsd_mm": 3}}, sr)
    assert not M.can_do({"capability": "survey.image", "ver": "1.0", "params": {"gsd_mm": 1}}, sr)
    assert M.can_do({"capability": "transport.hop", "ver": "1.0", "params": {"mass_kg": 8}}, hp)
    assert not M.can_do(carry, None)


def test_channel_byte_count_is_opt_in():
    from lunarsim.atc.messages import Channel
    a = Channel(0.0)
    a.send(3)
    assert a.bytes_sent == 0
    b = Channel(0.0, sizes="lrip_mac8")
    b.send(3, msg="POSITION")
    b.send(1, msg="TASK_AWARD")
    assert b.bytes_sent == 3 * 41 + 92


def test_channel_signs_what_the_schema_signs():
    """B-118 N13: every message the codec signs is counted at its signed size (CAP_MANIFEST 84 B, not 28 B)."""
    from lunarsim.atc.lrip import codec as C
    from lunarsim.atc.messages import Channel
    t = C.size_table()
    ch = Channel(0.0, sizes="lrip_mac8")
    for k in t:
        assert ch._size[k] == (t[k]["signed"] if C.default_auth(k) == "sig" else t[k]["mac8"]), k
    assert ch._size["CAP_MANIFEST"] == 84


def test_capability_filter_catalog_changes_nothing():
    """The catalogue-derived manifests offer exactly the capacity the engine checks, so the filter is a no-op there;
    a manifest set without carrying capability leaves the robots without bids."""
    import sys
    sys.path.insert(0, os.path.join(ROOT, "experiments", "phase5"))
    from lunarsim import Simulation
    from lunarsim.atc import regimes as G
    from lunarsim.atc import p5 as P5
    import math
    import warnings
    sc = P5.build("3eq", k=2.806, team_lift_share=0.10).with_(horizon_h=24.0 * 45)
    mech = G.mechanism("C_AUCTION")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        base = Simulation(sc, mech, seed=3, mech_kwargs={"loss": 0.1}).run()
        filt = Simulation(sc, mech, seed=3, mech_kwargs={"loss": 0.1, "capability_filter": "catalog"}).run()
        none = Simulation(sc, mech, seed=3, mech_kwargs={"loss": 0.1, "capability_filter": {"none": None}}).run()
    assert base.keys() == filt.keys()
    for k in base:                                           # every summary value identical (NaN = NaN)
        assert base[k] == filt[k] or (isinstance(base[k], float) and math.isnan(base[k]) and math.isnan(filt[k])), k
    assert base["delivered_items"] > 50 and none["delivered_items"] < 0.1 * base["delivered_items"]


def test_e53_outputs():
    p = os.path.join(ROOT, "results", "E53_bitrate.json")
    if not os.path.isfile(p):
        pytest.skip("E53 not run")
    d = json.load(open(p))
    # B-119: the verdict recomputed from the rows (fleet geometry, auth on, 20 rovers: p95 <= 16 kbit/s at 1 Hz,
    # > 16 kbit/s at 10 Hz)
    cell = {(r["geometry"], r["auth"], r["position_hz"], r["rovers"]): r for r in d["rows"]}
    a1, a10 = cell[("fleet", "on", 1.0, 20)]["busiest_link_kbps_p95"], cell[("fleet", "on", 10.0, 20)]["busiest_link_kbps_p95"]
    assert d["h13"]["supported"] is bool(a1 <= 16.0 and a10 > 16.0)
    assert d["h13"]["at_1hz_kbps_p95"] == a1 and d["h13"]["at_10hz_kbps_p95"] == a10
    v = json.load(open(os.path.join(ROOT, "data", "atc", "lrip", "conformance-v0.1.json")))
    for x in v["vectors"]:                                   # every golden packet decodes to its recorded fields
        pkt = bytes.fromhex(x["hex"])
        d2 = L.decode(pkt, auth="auto" if x["auth"] else None, keys=C.Keys(
            mac_key=bytes.fromhex(v["keys"]["aes_cmac_key_hex"]), verify_key=PK), profile=x["profile"])
        assert d2.name == x["message"] and len(pkt) == x["bytes"]
        if "manifest_cbor_hex" not in x["fields"]:
            assert close(x["fields"], d2.fields)
