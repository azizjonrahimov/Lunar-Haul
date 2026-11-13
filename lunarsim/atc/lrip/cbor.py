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


MAX_DEPTH = 16                        # B-119 C4: LRIP nests at most a few levels (manifest maps in arrays)


def _need(buf: bytes, i: int, n: int) -> None:
    if n < 0 or i + n > len(buf):
        raise ValueError(f"cbor: {n} byte(s) needed at offset {i}, {max(0, len(buf) - i)} left")


def _arg(buf: bytes, i: int, info: int) -> Tuple[int, int]:
    if info < 24:
        return info, i
    size = {24: 1, 25: 2, 26: 4, 27: 8}.get(info)
    if size is None:
        raise ValueError("cbor: indefinite lengths, reserved values and floats are not used by LRIP")
    _need(buf, i, size)
    return int.from_bytes(buf[i:i + size], "big"), i + size


def _load(buf: bytes, i: int, depth: int = 0) -> Tuple[Any, int]:
    if depth > MAX_DEPTH:
        raise ValueError(f"cbor: nested deeper than {MAX_DEPTH}")
    _need(buf, i, 1)
    b = buf[i]
    major, info = b >> 5, b & 31
    i += 1
    if major == 7:
        if info not in (20, 21, 22):
            raise ValueError(f"cbor: simple value {info} is not used by LRIP")
        return {20: False, 21: True, 22: None}[info], i
    n, i = _arg(buf, i, info)
    if major == 0:
        return n, i
    if major == 1:
        return -1 - n, i
    if major in (2, 3):
        _need(buf, i, n)
        raw = bytes(buf[i:i + n])
        return (raw if major == 2 else raw.decode("utf-8")), i + n
    if major in (4, 5):
        _need(buf, i, n * (1 if major == 4 else 2))        # every item takes at least one byte
        if major == 4:
            out = []
            for _ in range(n):
                v, i = _load(buf, i, depth + 1)
                out.append(v)
            return out, i
        d = {}
        for _ in range(n):
            k, i = _load(buf, i, depth + 1)
            if not isinstance(k, (int, str, bytes)) or isinstance(k, bool):
                raise ValueError(f"cbor: map key of type {type(k).__name__}")
            v, i = _load(buf, i, depth + 1)
            d[k] = v
        return d, i
    raise ValueError(f"cbor: major type {major} not used by LRIP")


def loads(buf: bytes) -> Any:
    v, i = _load(bytes(buf), 0)
    if i != len(buf):
        raise ValueError("cbor: trailing bytes")
    return v
