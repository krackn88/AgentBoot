"""APIGuard header encode/decode (-e, -g, tag)."""

from __future__ import annotations

import base64
import json
import os
import zlib

from southwest_checker.apiguard.cipher import E_PARAMS, G_PARAMS, TAG_PARAMS, decrypt, encrypt

PREFIX = b"X-dUblrIiu-"


def b64u_encode(data: bytes) -> str:
    return base64.b64encode(data).decode().replace("+", "-").replace("/", "_").rstrip("=")


def b64u_decode(text: str) -> bytes:
    t = text.replace("-", "+").replace("_", "/")
    pad = (-len(t)) % 4
    if pad:
        t += "=" * pad
    return base64.b64decode(t)


def shift_seed(seed: bytes, prefix: bytes = PREFIX) -> bytes:
    key = bytearray(seed)
    for i in range(min(len(prefix), len(key))):
        key[i] ^= prefix[i]
    return bytes(key)


def decode_e(token: str) -> dict:
    tag, ct, key_b64 = token.split(";")
    key32 = b64u_decode(key_b64)
    sensor = zlib.decompress(decrypt(b64u_decode(ct), shift_seed(key32), E_PARAMS))
    return {"tag": tag, "key32": key32, "sensor": sensor}


def encode_e(sensor: bytes, key32: bytes | None = None) -> str:
    if key32 is None:
        key32 = os.urandom(32)
    ct = encrypt(zlib.compress(sensor), shift_seed(key32), E_PARAMS)
    return ";".join(["b", b64u_encode(ct), b64u_encode(key32)])


def decode_tag(tag0: str, tag1: str) -> dict:
    raw = decrypt(b64u_decode(tag0), shift_seed(b64u_decode(tag1)), TAG_PARAMS)
    return json.loads(raw.decode("latin1"))


def encode_tag(payload: str | dict, seed: bytes | None = None) -> tuple[str, str]:
    if seed is None:
        seed = os.urandom(32)
    pt = payload if isinstance(payload, str) else json.dumps(payload, separators=(",", ":"))
    tag0 = b64u_encode(encrypt(pt.encode("latin1"), shift_seed(seed), TAG_PARAMS))
    return tag0, b64u_encode(seed)


def decode_g(token: str) -> dict:
    parts = token.replace("x-dublriiu-g:", "").strip().split(";")
    ct_b64, key_b64, ident = parts
    if ident != "g":
        raise ValueError(f"not a -g token (id={ident})")
    key32 = b64u_decode(key_b64)
    pt = decrypt(b64u_decode(ct_b64), shift_seed(key32), G_PARAMS)
    semi = pt.index(0x3B)
    version = pt[:semi].decode("latin1")
    signal = zlib.decompress(b64u_decode(pt[semi + 1 :].decode("latin1")))
    return {"version": version, "key32": key32, "signal": signal}


def encode_g(signal: bytes, key32: bytes | None = None, version: str = "1") -> str:
    if key32 is None:
        key32 = os.urandom(32)
    body = b64u_encode(zlib.compress(signal))
    pt = f"{version};{body}".encode("latin1")
    ct = encrypt(pt, shift_seed(key32), G_PARAMS)
    return ";".join([b64u_encode(ct), b64u_encode(key32), "g"])
