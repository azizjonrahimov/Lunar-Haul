"""Minimal deterministic CBOR (RFC 8949) for LRIP profile B and the compact manifest: unsigned / negative integers,
byte and text strings, arrays, maps, false / true / null. Shortest-form integer heads (an integer below 24 takes one
byte, below 256 two, below 65,536 three, below 2^32 five: RFC 8949 section 3), so sizes match note 03 E2."""
from __future__ import annotations

import struct
from typing import Any, Tuple


def _head(major: int, n: int) -> bytes:
    if n < 24:
        return bytes([(major << 5) | n])
    if n < 0x100:
        return bytes([(major << 5) | 24, n])
    if n < 0x10000:
        return bytes([(major << 5) | 25]) + struct.pack(">H", n)
    if n < 0x100000000:
        return bytes([(major << 5) | 26]) + struct.pack(">I", n)
    return bytes([(major << 5) | 27]) + struct.pack(">Q", n)


def dumps(x: Any) -> bytes:
    if x is False:
        return b"\xf4"
    if x is True:
        return b"\xf5"
    if x is None:
        return b"\xf6"
    if isinstance(x, int):
        return _head(0, x) if x >= 0 else _head(1, -1 - x)
    if isinstance(x, bytes):
        return _head(2, len(x)) + x
    if isinstance(x, str):
        b = x.encode("utf-8")
        return _head(3, len(b)) + b
    if isinstance(x, (list, tuple)):
        return _head(4, len(x)) + b"".join(dumps(v) for v in x)
    if isinstance(x, dict):
        return _head(5, len(x)) + b"".join(dumps(k) + dumps(v) for k, v in x.items())
    raise TypeError(f"cbor: unsupported type {type(x).__name__}")


def _arg(buf: bytes, i: int, info: int) -> Tuple[int, int]:
    if info < 24:
        return info, i
    size = {24: 1, 25: 2, 26: 4, 27: 8}.get(info)
    if size is None:
        raise ValueError("cbor: indefinite lengths and floats are not used by LRIP")
    return int.from_bytes(buf[i:i + size], "big"), i + size


def _load(buf: bytes, i: int) -> Tuple[Any, int]:
    b = buf[i]
    major, info = b >> 5, b & 31
    i += 1
    if major == 7:
        return {20: False, 21: True, 22: None}[info], i
    n, i = _arg(buf, i, info)
    if major == 0:
        return n, i
    if major == 1:
        return -1 - n, i
    if major == 2:
        return bytes(buf[i:i + n]), i + n
    if major == 3:
        return buf[i:i + n].decode("utf-8"), i + n
    if major == 4:
        out = []
        for _ in range(n):
            v, i = _load(buf, i)
            out.append(v)
        return out, i
    if major == 5:
        d = {}
        for _ in range(n):
            k, i = _load(buf, i)
            v, i = _load(buf, i)
            d[k] = v
        return d, i
    raise ValueError(f"cbor: major type {major} not used by LRIP")


def loads(buf: bytes) -> Any:
    v, i = _load(bytes(buf), 0)
    if i != len(buf):
        raise ValueError("cbor: trailing bytes")
    return v
