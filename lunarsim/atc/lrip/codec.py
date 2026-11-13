"""LRIP codec (B-93 v0.1; B-100 v0.2): bit-packed binary packets (profile N) and CBOR packets (profile B), with the
security header and an AES-CMAC or Ed25519 trailer; the versioning rule; byte counts per message.

Schema: lunarsim/schemas/lrip-v0.2.json (research note 03 section C; v0.2 adds the 95 % position bound in POSITION and
the frame / datum / time-scale declaration in HELLO, lunarsim/schemas/lrip-v0.2.json changes_from). Packets of minor
version 1 encode and decode exactly as v0.1 defined them (fields marked "since": 2 are absent there); `minor=1` gives
v0.1 packets and v0.1 sizes. Receiver applies the v0.2 declaration rule. A packet is

    Space Packet primary header (6 B) | LRIP header (8 B) | payload | security header (6 B) | MAC (8 / 16 B) or signature (64 B)

and, unauthenticated, only the first three parts (used for the "authentication off" rows of E53 and for decoding
legacy captures). Field values are given and returned in their units (metres, degrees, ...), quantised by each
field's scale; enumerations by code (int).
"""
from __future__ import annotations

import json
import os
import struct
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import cbor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SCHEMA_FILE = os.path.join(ROOT, "lunarsim", "schemas", "lrip-v0.2.json")
SCHEMA_FILE_V01 = os.path.join(ROOT, "lunarsim", "schemas", "lrip-v0.1.json")   # kept: the v0.1 catalogue as published
SPP_B, HDR_B, SEC_B = 6, 8, 6
TRAILER_B = {"mac8": 8, "mac16": 16, "sig": 64, None: 0}
SPI_KIND = {"mac8": 0, "mac16": 1, "sig": 2}
KIND_OF = {v: k for k, v in SPI_KIND.items()}


class LripVersionError(ValueError):
    """A packet of another major version (refused, note 03 C4 rule 5)."""


class LripAuthError(ValueError):
    """The MAC or signature does not verify."""


class LripRefError(ValueError):
    """A POSITION from a sender with no frame / datum / time-scale declaration under its key epoch (v0.2 rule)."""


_SCHEMA: Dict[str, Any] = {}


def schema() -> Dict[str, Any]:
    if not _SCHEMA:
        with open(SCHEMA_FILE, encoding="utf-8") as f:
            _SCHEMA.update(json.load(f))
        _SCHEMA["_by_id"] = {m["id"]: m for m in _SCHEMA["messages"]}
        _SCHEMA["_by_name"] = {m["name"]: m for m in _SCHEMA["messages"]}
    return _SCHEMA


def message(name_or_id) -> Dict[str, Any]:
    s = schema()
    return s["_by_name"][name_or_id] if isinstance(name_or_id, str) else s["_by_id"][int(name_or_id)]


def fields_for(name, minor: Optional[int] = None) -> List[list]:
    """The message's fields as packets of that minor version carry them (default: this schema's). A field marked
    {"since": N} is absent below N; one that replaced spare bits ({"was": "spare"}) is spare there."""
    s = schema()
    minor = s["ver_minor"] if minor is None else min(int(minor), s["ver_minor"])
    out = []
    for f in message(name)["fields"]:
        meta = f[5] if len(f) > 5 and isinstance(f[5], dict) else {}
        if minor >= meta.get("since", 1):
            out.append(f)
        elif meta.get("was") == "spare":
            out.append(["spare", "spare", f[2], 1, ""])
    return out


def payload_bits(name, minor: Optional[int] = None) -> int:
    return sum(f[2] for f in fields_for(name, minor))


def payload_bytes(name, minor: Optional[int] = None) -> int:
    b = payload_bits(name, minor)
    assert b % 8 == 0, f"{name}: {b} bits"
    return b // 8


# ------------------------------------------------------------------------------------------------ bit packing
class _Bits:
    def __init__(self, data: bytes = b""):
        self.v, self.n = int.from_bytes(data, "big"), len(data) * 8
        self.pos = 0

    def put(self, value: int, bits: int):
        if value < 0 or value >= (1 << bits):
            raise ValueError(f"value {value} does not fit {bits} bits")
        self.v = (self.v << bits) | value
        self.n += bits

    def get(self, bits: int) -> int:
        shift = self.n - self.pos - bits
        if shift < 0:
            raise ValueError("read past the end of the payload")
        self.pos += bits
        return (self.v >> shift) & ((1 << bits) - 1)

    def bytes(self) -> bytes:
        assert self.n % 8 == 0
        return self.v.to_bytes(self.n // 8, "big")


def _raw(field, value) -> int:
    name, typ, bits, scale = field[0], field[1], field[2], field[3]
    if typ == "spare":
        return 0
    if typ in ("flag",):
        return 1 if value else 0
    if typ in ("flags",) or typ.startswith("enum"):
        return int(value)
    q = int(round(float(value) / scale))
    if typ == "int":
        lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
        if not lo <= q <= hi:
            raise ValueError(f"{name}={value} out of range")
        return q & ((1 << bits) - 1)
    if not 0 <= q < (1 << bits):
        raise ValueError(f"{name}={value} out of range")
    return q


def _value(field, raw: int):
    name, typ, bits, scale = field[0], field[1], field[2], field[3]
    if typ == "flag":
        return bool(raw)
    if typ == "flags":
        return raw
    if typ.startswith("enum"):
        enum = schema()["enums"][typ.split(":", 1)[1]]
        if str(raw) not in enum:                      # rule 3: unknown enumeration value -> most cautious known value
            return int(enum.get("unknown_as", raw))
        return raw
    if typ == "int" and raw >= (1 << (bits - 1)):
        raw -= 1 << bits
    v = raw * scale
    return int(v) if float(scale).is_integer() else round(v, 10)


def encode_payload(name, values: Dict[str, Any], minor: Optional[int] = None) -> bytes:
    b = _Bits()
    for f in fields_for(name, minor):
        b.put(_raw(f, values.get(f[0], 0)), f[2])
    return b.bytes()


def decode_payload(name, data: bytes, minor: Optional[int] = None) -> Dict[str, Any]:
    """Known fields only; trailing bytes (fields a later minor version appended) are skipped (rule 3)."""
    fields = fields_for(name, minor)
    nb = payload_bytes(name, minor)
    if len(data) < nb:
        raise ValueError(f"{name}: payload {len(data)} B, need {nb}")
    b = _Bits(data[:nb])
    out = {}
    for f in fields:
        raw = b.get(f[2])
        if f[1] != "spare":
            out[f[0]] = _value(f, raw)
    return out


# ------------------------------------------------------------------------------------------------ security
@dataclass
class Keys:
    """mac_key: 16-byte AES key (site broadcast or pairwise); sign_key: an Ed25519 private key (cryptography) whose
    public half verifies; epoch: the key epoch carried in the SPI."""
    mac_key: bytes = b"\x00" * 16
    sign_key: Any = None
    verify_key: Any = None
    epoch: int = 0


def cmac(key: bytes, data: bytes, n: int) -> bytes:
    from cryptography.hazmat.primitives import cmac as _c
    from cryptography.hazmat.primitives.ciphers import algorithms
    c = _c.CMAC(algorithms.AES(key))
    c.update(data)
    return c.finalize()[:n]


def ed25519_keys(seed: bytes = b"\x07" * 32):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    sk = Ed25519PrivateKey.from_private_bytes(seed)
    return sk, sk.public_key()


# ------------------------------------------------------------------------------------------------ packets
def _spp(apid: int, seq_count: int, data_len: int) -> bytes:
    w1 = (0 << 13) | (0 << 12) | (1 << 11) | (apid & 0x7FF)
    w2 = (3 << 14) | (seq_count & 0x3FFF)
    return struct.pack(">HHH", w1, w2, data_len - 1)


def _hdr(msg_type: int, sender: int, t_valid: int, major: int, minor: int) -> bytes:
    return struct.pack(">BBHI", (major << 4) | minor, msg_type, sender, t_valid & 0xFFFFFFFF)


def encode(name, values: Dict[str, Any], sender: int, t_valid_s: float, seq: int = 0, auth: Optional[str] = "mac8",
           keys: Optional[Keys] = None, profile: str = "N", seq_count: int = 0, minor: Optional[int] = None,
           extra: bytes = b"", body: Optional[bytes] = None) -> bytes:
    """One packet. auth: None (no security), "mac8", "mac16" or "sig" (Ed25519; the default for signed messages is the
    caller's choice: `default_auth(name)`). profile "N": bit-packed payload; "B": CBOR array of the header and the
    fields. extra: bytes appended after the payload (a later minor version's fields; tests). body: a ready payload
    (CAP_MANIFEST)."""
    s = schema()
    m = message(name)
    minor = s["ver_minor"] if minor is None else minor
    tv = int(round(t_valid_s / s["framing"]["lrip_header"]["t_valid_unit_s"]))
    if profile == "N":
        pay = (body if body is not None else encode_payload(name, values, minor)) + extra
        inner = _hdr(m["id"], sender, tv, s["ver_major"], minor) + pay
    elif profile == "B":
        arr = [(s["ver_major"] << 4) | minor, m["id"], sender, tv]
        if body is not None:
            arr.append(body)
        else:
            for f in fields_for(name, minor):
                if f[1] != "spare":
                    arr.append(_raw_signed(f, values.get(f[0], 0)))
        inner = cbor.dumps(arr) + extra
    else:
        raise ValueError("profile must be 'N' or 'B'")
    keys = keys or Keys()
    sec = b""
    if auth is not None:
        sec = struct.pack(">HI", (SPI_KIND[auth] << 14) | (keys.epoch & 0x3FFF), seq & 0xFFFFFFFF)
    tl = TRAILER_B[auth]
    head = _spp(s["framing"]["space_packet"]["apid_base"] + m["id"], seq_count, len(inner) + len(sec) + tl)
    pkt = head + inner + sec
    if auth in ("mac8", "mac16"):
        pkt += cmac(keys.mac_key, pkt, tl)
    elif auth == "sig":
        if keys.sign_key is None:
            raise ValueError("a signed packet needs Keys.sign_key")
        pkt += keys.sign_key.sign(pkt)
    return pkt


def _raw_signed(f, value) -> int:
    """CBOR carries integers with their sign (major type 1 for negative): the quantised value, not two's complement."""
    typ = f[1]
    if typ in ("flag", "flags") or typ.startswith("enum"):
        return _raw(f, value)
    q = int(round(float(value) / f[3]))
    _raw(f, value)                                     # range check
    return q


@dataclass
class Decoded:
    name: str
    msg_type: int
    sender: int
    t_valid_s: float
    ver: Tuple[int, int]
    fields: Dict[str, Any]
    auth: Optional[str]
    seq: Optional[int]
    epoch: Optional[int]
    skipped_bytes: int
    body: Optional[bytes] = None


class Counters:
    def __init__(self):
        self.unknown_type = 0
        self.refused_major = 0
        self.bad_auth = 0


def decode(pkt: bytes, auth: Optional[str] = "auto", keys: Optional[Keys] = None, profile: str = "N",
           counters: Optional[Counters] = None, verify: bool = True) -> Optional[Decoded]:
    """Decode one packet. auth "auto": a security header is present when the packet is longer than an unsecured one
    (the kind is then read from the SPI); None: unsecured. Returns None for an unknown message type (counted, rule 3);
    raises LripVersionError on another major version (rule 5) and LripAuthError when the MAC / signature fails."""
    s = schema()
    counters = counters or Counters()
    w1, w2, dl = struct.unpack(">HHH", pkt[:SPP_B])
    total = SPP_B + dl + 1
    if total != len(pkt):
        raise ValueError(f"packet length {len(pkt)} != {total} from the Space Packet header")
    apid = w1 & 0x7FF
    msg_type = apid - s["framing"]["space_packet"]["apid_base"]
    if profile == "N":
        vb, mt, sender, tv = struct.unpack(">BBHI", pkt[SPP_B:SPP_B + HDR_B])
        major, minor = vb >> 4, vb & 15
        body_start = SPP_B + HDR_B
    else:
        arr0, _ = cbor._load(pkt, SPP_B)
        major, minor = arr0[0] >> 4, arr0[0] & 15
        mt, sender, tv = arr0[1], arr0[2], arr0[3]
        body_start = None
    if major != s["ver_major"]:
        counters.refused_major += 1
        raise LripVersionError(f"LRIP major {major}, this decoder speaks {s['ver_major']}")
    if mt not in s["_by_id"] or mt != msg_type:
        counters.unknown_type += 1
        return None
    m = s["_by_id"][mt]
    # security: find the trailer
    kind, seq, epoch, tl = None, None, None, 0
    if auth is not None:
        if profile == "N":
            known = SPP_B + HDR_B + (payload_bytes(m["name"], minor) if m["fields"] else 0)
        else:
            _, end = cbor._load(pkt, SPP_B)
            known = end
        # candidates whose SPI kind bits match; with "auto" a signature's random bytes can look like a shorter
        # trailer's SPI, so try the longest trailer first and, when verifying, keep the first that verifies
        cands = []
        for k in ("sig", "mac16", "mac8"):
            if auth != "auto" and k != auth:
                continue
            cut = len(pkt) - TRAILER_B[k] - SEC_B
            if cut >= known and cut >= SPP_B + 1:
                spi, sq = struct.unpack(">HI", pkt[cut:cut + SEC_B])
                if KIND_OF.get(spi >> 14) == k:
                    cands.append((k, sq, spi & 0x3FFF))
        if verify and len(cands) > 1:
            keys_ = keys or Keys()
            good = []
            for k, sq, ep in cands:
                tl_ = TRAILER_B[k]
                body_, tag = pkt[:len(pkt) - tl_], pkt[len(pkt) - tl_:]
                try:
                    if k == "sig":
                        keys_.verify_key.verify(tag, body_)
                        good.append((k, sq, ep))
                    elif cmac(keys_.mac_key, body_, tl_) == tag:
                        good.append((k, sq, ep))
                except Exception:
                    pass
            cands = good[:1] or cands[:1]
        if cands:
            kind, seq, epoch = cands[0]
            tl = TRAILER_B[kind]
        if auth != "auto" and kind is None:
            raise LripAuthError("no security header of the expected kind")
    end_payload = len(pkt) - tl - (SEC_B if kind else 0)
    if kind and verify:
        keys = keys or Keys()
        signed = pkt[:len(pkt) - tl]
        if kind == "sig":
            try:
                keys.verify_key.verify(pkt[len(pkt) - tl:], signed)
            except Exception:
                counters.bad_auth += 1
                raise LripAuthError("signature does not verify")
        elif cmac(keys.mac_key, signed, tl) != pkt[len(pkt) - tl:]:
            counters.bad_auth += 1
            raise LripAuthError("MAC does not verify")
    body = None
    if profile == "N":
        data = pkt[body_start:end_payload]
        if m["fields"]:
            fields = decode_payload(m["name"], data, minor)
            skipped = len(data) - payload_bytes(m["name"], minor)
        else:
            fields, body, skipped = {}, bytes(data), 0
    else:
        arr, end = cbor._load(pkt, SPP_B)
        skipped = end_payload - end
        names = [f for f in fields_for(m["name"], minor) if f[1] != "spare"]
        fields = {}
        if m["fields"]:
            for f, raw in zip(names, arr[4:4 + len(names)]):
                fields[f[0]] = _value_signed(f, raw)
            skipped += max(0, len(arr) - 4 - len(names))  # appended CBOR items of a later minor version
        else:
            body = arr[4] if len(arr) > 4 else None
    return Decoded(m["name"], mt, sender, tv * s["framing"]["lrip_header"]["t_valid_unit_s"], (major, minor), fields,
                   kind, seq, epoch, skipped, body)


def _value_signed(f, raw: int):
    typ = f[1]
    if typ in ("flag", "flags") or typ.startswith("enum"):
        return _value(f, raw)
    v = raw * f[3]
    return int(v) if float(f[3]).is_integer() else round(v, 10)


# ------------------------------------------------------------------------------------------------ sizes
def default_auth(name, alert_signed: bool = False) -> str:
    m = message(name)
    if m.get("signed") or (alert_signed and name == "ALERT"):
        return "sig"
    return "mac8"


def packet_bytes(name, auth: Optional[str] = "mac8", body_bytes: int = 0, minor: Optional[int] = None) -> int:
    """Bytes on the air for one profile-N packet: 6 + 8 + payload (+ 6 + trailer when authenticated); before link
    framing (a Proximity-1 frame adds framing.proximity1_frame_bytes)."""
    pay = payload_bytes(name, minor) if message(name)["fields"] else body_bytes
    return SPP_B + HDR_B + pay + ((SEC_B + TRAILER_B[auth]) if auth else 0)


def size_table(manifest_bytes: int = 0, minor: Optional[int] = None) -> Dict[str, Dict[str, int]]:
    """Per message: payload, unsecured, MAC 8 B, MAC 16 B, signed (profile N) for packets of that minor version
    (default this schema's); + Proximity-1 and bundle overheads are per message constants in the schema."""
    out = {}
    for m in schema()["messages"]:
        nm = m["name"]
        pb = payload_bytes(nm, minor) if m["fields"] else manifest_bytes
        out[nm] = {"payload": pb, "unsecured": packet_bytes(nm, None, pb, minor), "mac8": packet_bytes(nm, "mac8", pb, minor),
                   "mac16": packet_bytes(nm, "mac16", pb, minor), "signed": packet_bytes(nm, "sig", pb, minor),
                   "default": packet_bytes(nm, default_auth(nm), pb, minor)}
    return out


# ------------------------------------------------------------------------------------------------ v0.2: bound, declarations
U95_BASE_M, U95_UNKNOWN = 0.05, 63


def u95_code(bound_m: Optional[float]) -> int:
    """POSITION.u95_code for a 95 % horizontal bound (m): the smallest code c <= 61 with 0.05 x 2^(c/4) >= bound (coded
    upward, so the decoded bound never understates); 62 for a bound above 0.05 x 2^(61/4) = 1.95 km; None or not
    finite: 63 unknown."""
    import math
    if bound_m is None or not math.isfinite(float(bound_m)):
        return U95_UNKNOWN
    if bound_m <= U95_BASE_M:
        return 0
    c = int(math.ceil(4.0 * math.log2(float(bound_m) / U95_BASE_M) - 1e-9))
    return c if c <= 61 else 62


def u95_from_code(code: int) -> Optional[float]:
    """The 95 % bound (m) a u95_code stands for (an upper value): inf for 62 (above 1.95 km), None for 63 (unknown)."""
    c = int(code)
    if c == U95_UNKNOWN:
        return None
    return float("inf") if c == 62 else U95_BASE_M * 2.0 ** (c / 4.0)


@dataclass
class RefDecl:
    frame_id: int
    datum_id: int
    time_scale: int
    epoch: int
    source: str                       # "hello" or "manifest"
    t_valid_s: float


class Receiver:
    """v0.2 declaration rule: frame, datum and time scale are declared per sender in an authenticated HELLO (minor >= 2)
    or a signed capability manifest (nav.frame, nav.datum, nav.time_scale), bound to the key epoch they were
    authenticated under; a POSITION from a sender without a declaration under its current key epoch is refused
    (LripRefError, counted). Codes outside the schema's enums are refused, not read as a cautious value."""

    def __init__(self, keys: Optional[Keys] = None, profile: str = "N"):
        self.keys, self.profile = keys or Keys(), profile
        self.decl: Dict[int, RefDecl] = {}
        self.counters = Counters()
        self.refused_positions = 0
        self.ignored_declarations = 0

    def _valid(self, frame, datum, ts) -> bool:
        e = schema()["enums"]
        return str(int(frame)) in e["frame"] and str(int(datum)) in e["datum"] and str(int(ts)) in e["time_scale"]

    def declare_from_manifest(self, sender: int, manifest: Dict[str, Any], epoch: int, signed: bool) -> bool:
        nav = (manifest or {}).get("nav") or {}
        if not signed or not all(k in nav for k in ("frame", "datum", "time_scale")) or \
                not self._valid(nav["frame"], nav["datum"], nav["time_scale"]):
            self.ignored_declarations += 1
            return False
        self.decl[int(sender)] = RefDecl(int(nav["frame"]), int(nav["datum"]), int(nav["time_scale"]), int(epoch),
                                         "manifest", float("nan"))
        return True

    def accept(self, pkt: bytes) -> Optional[Decoded]:
        """Decode (verifying), apply the rule; a POSITION comes back with frame_id, datum_id, time_scale and the
        decoded 95 % bound (u95_m) added to its fields."""
        d = decode(pkt, keys=self.keys, profile=self.profile, counters=self.counters)
        if d is None:
            return None
        if d.name == "HELLO" and d.ver[1] >= 2:
            f = d.fields
            if d.auth is not None and self._valid(f.get("frame_id", 0), f.get("datum_id", 0), f.get("time_scale", 0)):
                self.decl[d.sender] = RefDecl(int(f["frame_id"]), int(f["datum_id"]), int(f["time_scale"]), int(d.epoch),
                                              "hello", d.t_valid_s)
            else:
                self.ignored_declarations += 1
        elif d.name == "POSITION":
            dec = self.decl.get(d.sender)
            if d.auth is None or dec is None or dec.epoch != d.epoch:
                self.refused_positions += 1
                raise LripRefError(f"POSITION from sender {d.sender}: no frame / datum / time-scale declaration under "
                                   f"key epoch {d.epoch}")
            d.fields.update(frame_id=dec.frame_id, datum_id=dec.datum_id, time_scale=dec.time_scale,
                            u95_m=u95_from_code(d.fields["u95_code"]) if "u95_code" in d.fields else None)
        return d
