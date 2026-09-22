"""Native APIGuard probe response candidates using init session key and sk."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sys
from typing import Any

from southwest_checker.apiguard.cipher import E_PARAMS, G_PARAMS, TAG_PARAMS, decrypt, encrypt
from southwest_checker.apiguard.headers import shift_seed

PREFIX = b"X-dUblrIiu-"


def _b64u(data: bytes) -> str:
    return base64.b64encode(data).decode().replace("+", "-").replace("/", "_").rstrip("=")


def _b64u_decode(text: str) -> bytes:
    t = text.replace("-", "+").replace("_", "/")
    pad = (-len(t)) % 4
    if pad:
        t += "=" * pad
    return base64.b64decode(t)


def _parse_sk(sk: str) -> tuple[bytes, bytes, str]:
    parts = sk.split(";")
    if len(parts) < 2:
        return b"", b"", ""
    try:
        ident = parts[2] if len(parts) > 2 else ""
        return _b64u_decode(parts[0]), _b64u_decode(parts[1]), ident
    except Exception:
        return b"", b"", parts[2] if len(parts) > 2 else ""


def _split_session_key(value: str) -> tuple[str, str]:
    if "=" in value:
        left, _, right = value.partition("=")
        return left, right
    return value, ""


def _resp_digest(data: bytes, size: int = 43) -> str:
    return _b64u(data)[:size]


def _xor_prefix(key: bytes) -> bytes:
    out = bytearray(key)
    for i in range(min(len(PREFIX), len(out))):
        out[i] ^= PREFIX[i]
    return bytes(out)


def _probe_triple(
    name: str,
    out: dict[str, list[str]],
    tokens: list[str],
    platform: str,
    build,
) -> None:
    t0, t1, t2 = (tokens + ["", "", ""])[:3]
    vals = [build(i, tok) for i, tok in enumerate([t0, t1, t2])]
    out[name] = vals + [platform or tokens[3] if len(tokens) > 3 else "ios"]


def _algorithms(
    tokens: list[str],
    sk: str,
    session_key: str,
    ints: list[int],
) -> dict[str, list[str]]:
    t0, t1, t2 = (tokens + ["", "", ""])[:3]
    platform = tokens[3] if len(tokens) > 3 else "ios"
    sk_ct, sk_key, sk_ident = _parse_sk(sk)
    sess_a, sess_b = _split_session_key(session_key)
    sess_b_bytes = _b64u_decode(sess_b) if sess_b else b""
    out: dict[str, list[str]] = {}

    # Session-key HMAC variants
    for name, key in [
        ("sess-a", sess_a.encode()),
        ("sess-b", sess_b.encode()),
        ("sess-ab", f"{sess_a}={sess_b}".encode()),
        ("sess-b64", sess_b_bytes),
    ]:
        _probe_triple(
            name,
            out,
            tokens,
            platform,
            lambda idx, tok, key=key: _resp_digest(
                hmac.new(key, f"{tok}|{idx}".encode(), hashlib.sha256).digest()
            ),
        )

    # Concat / ordering variants on session key material
    for name, key in [
        ("sess-a-tok", sess_a.encode()),
        ("sess-b-tok", sess_b.encode()),
    ]:
        _probe_triple(
            name,
            out,
            tokens,
            platform,
            lambda idx, tok, key=key: _resp_digest(
                hmac.new(key, tok.encode(), hashlib.sha256).digest()
            ),
        )

    _probe_triple(
        "sess-all",
        out,
        tokens,
        platform,
        lambda idx, tok: _resp_digest(
            hmac.new(
                sess_a.encode(),
                f"{t0}|{t1}|{t2}|{idx}|{platform}".encode(),
                hashlib.sha256,
            ).digest()
        ),
    )

    # sk key32 HMAC / hash variants
    if sk_key:
        for name, key in [
            ("sk-key-hmac", sk_key),
            ("sk-key-xor", _xor_prefix(sk_key)),
            ("sk-key-shift", shift_seed(sk_key)),
        ]:
            _probe_triple(
                name,
                out,
                tokens,
                platform,
                lambda idx, tok, key=key: _resp_digest(
                    hmac.new(key, tok.encode() + bytes([idx]), hashlib.sha256).digest()
                ),
            )

        _probe_triple(
            "sk-key-chain",
            out,
            tokens,
            platform,
            lambda idx, tok: _resp_digest(
                hmac.new(sk_key, f"{t0}{t1}{t2}{idx}{platform}".encode(), hashlib.sha256).digest()
            ),
        )

        for pname, params in [
            ("sk-e", E_PARAMS),
            ("sk-g", G_PARAMS),
            ("sk-tag", TAG_PARAMS),
        ]:
            xkey = shift_seed(sk_key)
            _probe_triple(
                pname,
                out,
                tokens,
                platform,
                lambda idx, tok, params=params, xkey=xkey: _resp_digest(
                    encrypt(tok.encode(), xkey, params)
                ),
            )

    # sk blob slice / digest
    if sk_ct:
        def _sk_slice(idx: int, tok: str) -> str:
            seed = hashlib.sha256(f"{tok}|{idx}|{session_key}".encode()).digest()
            off = int.from_bytes(seed[:4], "big") % max(1, len(sk_ct) - 32)
            return _resp_digest(sk_ct[off : off + 32])

        _probe_triple("sk-slice", out, tokens, platform, _sk_slice)

        _probe_triple(
            "sk-sha",
            out,
            tokens,
            platform,
            lambda idx, tok: _resp_digest(
                hashlib.sha256(sk_ct + tok.encode() + bytes([idx])).digest()
            ),
        )

    # init ints mixed
    if ints:
        _probe_triple(
            "init-int",
            out,
            tokens,
            platform,
            lambda idx, tok: _resp_digest(
                hashlib.sha256(f"{sess_a}|{sess_b}|{tok}|{ints[idx % len(ints)]}".encode()).digest()
            ),
        )

        _probe_triple(
            "init-int-hmac",
            out,
            tokens,
            platform,
            lambda idx, tok: _resp_digest(
                hmac.new(
                    str(ints[idx % len(ints)]).encode(),
                    f"{sess_b}{tok}{idx}".encode(),
                    hashlib.sha256,
                ).digest()
            ),
        )

    # Short suffix token embedded in -c/-d
    _probe_triple(
        "suffix-7",
        out,
        tokens,
        platform,
        lambda idx, tok: _resp_digest(
            hashlib.sha256(f"{sess_b}{tok}{idx}".encode()).digest(),
            7,
        ),
    )

    # Combined session + sk
    if sk_key:
        combo = hashlib.sha256(sk_key + sess_b.encode()).digest()
        _probe_triple(
            "combo-sk-sess",
            out,
            tokens,
            platform,
            lambda idx, tok: _resp_digest(
                hmac.new(combo, f"{tok}|{platform}|{idx}".encode(), hashlib.sha256).digest()
            ),
        )

    if sk_ident:
        _probe_triple(
            f"ident-{sk_ident}",
            out,
            tokens,
            platform,
            lambda idx, tok: _resp_digest(
                hashlib.sha256(f"{sk_ident}|{sess_a}|{tok}|{idx}".encode()).digest()
            ),
        )

    return out


def main() -> int:
    payload = json.loads(sys.stdin.read())
    tokens = payload["tokens"]
    sk = payload.get("sk", "")
    session_key = payload.get("sessionKey", "")
    ints = payload.get("ints") or []
    mode = payload.get("mode", "auto")

    algos = _algorithms(tokens, sk, session_key, ints)
    if mode != "auto" and mode in algos:
        print(json.dumps(algos[mode]))
        return 0

    if mode == "list":
        print(json.dumps(sorted(algos.keys())))
        return 0

    print(json.dumps(algos))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
