"""LRIP v0.1 codec (B-93): bit-packed binary packets (profile N) and CBOR packets (profile B), with the security
header and an AES-CMAC or Ed25519 trailer; the versioning rule; byte counts per message.

Schema: lunarsim/schemas/lrip-v0.1.json (research note 03 section C). A packet is

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
SCHEMA_FILE = os.path.join(ROOT, "lunarsim", "schemas", "lrip-v0.1.json")
SPP_B, HDR_B, SEC_B = 6, 8, 6
TRAILER_B = {"mac8": 8, "mac16": 16, "sig": 64, None: 0}
SPI_KIND = {"mac8": 0, "mac16": 1, "sig": 2}
KIND_OF = {v: k for k, v in SPI_KIND.items()}


class LripVersionError(ValueError):
    """A packet of another major version (refused, note 03 C4 rule 5)."""


class LripAuthError(ValueError):
    """The MAC or signature does not verify."""


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


def payload_bits(name) -> int:
    return sum(f[2] for f in message(name)["fields"])


def payload_bytes(name) -> int:
    b = payload_bits(name)
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


def encode_payload(name, values: Dict[str, Any]) -> bytes:
    b = _Bits()
    for f in message(name)["fields"]:
        b.put(_raw(f, values.get(f[0], 0)), f[2])
    return b.bytes()


def decode_payload(name, data: bytes) -> Dict[str, Any]:
    """Known fields only; trailing bytes (fields a later minor version appended) are skipped (rule 3)."""
    fields = message(name)["fields"]
    nb = payload_bytes(name)
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
        pay = (body if body is not None else encode_payload(name, values)) + extra
        inner = _hdr(m["id"], sender, tv, s["ver_major"], minor) + pay
    elif profile == "B":
        arr = [(s["ver_major"] << 4) | minor, m["id"], sender, tv]
        if body is not None:
            arr.append(body)
        else:
            for f in m["fields"]:
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
            known = SPP_B + HDR_B + (payload_bytes(m["name"]) if m["fields"] else 0)
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
            fields = decode_payload(m["name"], data)
            skipped = len(data) - payload_bytes(m["name"])
        else:
            fields, body, skipped = {}, bytes(data), 0
    else:
        arr, end = cbor._load(pkt, SPP_B)
        skipped = end_payload - end
        names = [f for f in m["fields"] if f[1] != "spare"]
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


def packet_bytes(name, auth: Optional[str] = "mac8", body_bytes: int = 0) -> int:
    """Bytes on the air for one profile-N packet: 6 + 8 + payload (+ 6 + trailer when authenticated)."""
    pay = payload_bytes(name) if message(name)["fields"] else body_bytes
    return SPP_B + HDR_B + pay + ((SEC_B + TRAILER_B[auth]) if auth else 0)


def size_table(manifest_bytes: int = 0) -> Dict[str, Dict[str, int]]:
    """Per message: payload, unsecured, MAC 8 B, MAC 16 B, signed (profile N); + Proximity-1 and bundle overheads are
    per message constants in the schema."""
    out = {}
    for m in schema()["messages"]:
        nm = m["name"]
        pb = payload_bytes(nm) if m["fields"] else manifest_bytes
        out[nm] = {"payload": pb, "unsecured": packet_bytes(nm, None, pb), "mac8": packet_bytes(nm, "mac8", pb),
                   "mac16": packet_bytes(nm, "mac16", pb), "signed": packet_bytes(nm, "sig", pb),
                   "default": packet_bytes(nm, default_auth(nm), pb)}
    return out
