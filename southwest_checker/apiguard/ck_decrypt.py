"""APIGuard ck/sk blob decryption research helpers.

The init endpoint returns ck modules as zlib-compressed blobs prefixed with
``\\x10SP\\x83`` (plaintext magic, not encrypted).  The ChaCha-CFB payload
starts at offset 4.  Plaintext is LuaJIT bytecode (``\\x1bLJ``).  The ``;d``
sk/ck cipher ("D variant") lives in kernel VM function GI[127] (offset ~45305)
and is not a mutation of the known E/G/TAG parameter sets.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from southwest_checker.apiguard.cipher import (
    CipherParams,
    E_PARAMS,
    G_PARAMS,
    TAG_PARAMS,
    _block,
    _init_state,
    decrypt,
)
from southwest_checker.apiguard.headers import shift_seed

PREFIX = b"\x10SP\x83"
LJ_HEADERS = (
    bytes.fromhex("1b4c4a02000000000000"),  # LuaJIT 2.1, flags=0
    bytes.fromhex("1b4c4a02080000000000"),  # LuaJIT 2.1, flags=BE
    bytes.fromhex("1b4c4a01000000000000"),  # LuaJIT 2.0
)

# Kernel VM crypto function index (GI array) — only block using charCodeAt+fromCharCode.
VM_CRYPTO_FN_INDEX = 127
VM_CRYPTO_OFFSET = 45305

# u32 constants from kernel numeric pool tail (/tmp/init.json build A9eCEcWg…).
KERNEL_POOL_WINDOWS: tuple[tuple[int, ...], ...] = (
    (3626208099, 3022957240, 3237332618, 92629711, 1465041174, 260493787, 2902037745, 397208795),
    (1615452909, 784054202, 817987752, 453530294, 709842148, 644128859, 4198458437, 1643968964),
    (1643968964, 2013989403, 536870911, 2315245188, 1342646579, 1028213265, 1633026571, 1875227069),
    (1432042122, 371880221, 3925374456, 2910793789, 62232978, 1913507172, 69747568, 2153858718),
)


@dataclass(frozen=True)
class DecryptAttempt:
    module: str
    params_name: str
    key_name: str
    score: int
    head: bytes
    params: CipherParams | None = None


@dataclass(frozen=True)
class ModuleSample:
    name: str
    prefix: bytes
    ciphertext: bytes
    key_shifted: bytes
    target_keystream: bytes


def _b64u_decode(text: str) -> bytes:
    t = text.replace("-", "+").replace("_", "/")
    pad = (-len(t)) % 4
    if pad:
        t += "=" * pad
    return base64.b64decode(t)


def load_init(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def split_ck_body(body: bytes) -> tuple[bytes, bytes]:
    if not body.startswith(PREFIX):
        raise ValueError(f"unexpected ck prefix {body[:4]!r}")
    return body[:4], body[4:]


def decompress_ck_module(ck_entry: dict) -> bytes:
    raw = base64.b64decode(ck_entry["c"])
    return zlib.decompress(raw)


def module_key(ck_entry: dict, *, shifted: bool = True) -> bytes:
    key = bytes.fromhex(ck_entry["d"])
    return shift_seed(key) if shifted else key


def cfb_keystream(ciphertext: bytes, plaintext: bytes, *, feedback: str = "plaintext") -> bytes:
    """Recover ChaCha-CFB keystream bytes for a known plaintext prefix."""
    out = bytearray(len(plaintext))
    for i in range(len(plaintext)):
        fb = 0 if i == 0 else (plaintext[i - 1] if feedback == "plaintext" else ciphertext[i - 1])
        out[i] = ciphertext[i] ^ plaintext[i] ^ fb
    return bytes(out)


def keystream_score(generated: bytes, target: bytes) -> int:
    return sum(a == b for a, b in zip(generated, target))


def candidate_keys(ck_entry: dict, sk: str = "") -> dict[str, bytes]:
    keys: dict[str, bytes] = {}
    d_raw = bytes.fromhex(ck_entry["d"])
    keys["d-shift"] = shift_seed(d_raw)
    keys["d-raw"] = d_raw
    keys["sha256-d"] = hashlib.sha256(d_raw).digest()
    keys["sha256-d-shift"] = hashlib.sha256(keys["d-shift"]).digest()
    if sk:
        parts = sk.split(";")
        if len(parts) >= 2:
            sk_key = _b64u_decode(parts[1])
            keys["sk-shift"] = shift_seed(sk_key)
            keys["xor-d-sk"] = shift_seed(bytes(a ^ b for a, b in zip(d_raw, sk_key)))
    return keys


def candidate_param_bases() -> dict[str, CipherParams]:
    return {"E": E_PARAMS, "G": G_PARAMS, "TAG": TAG_PARAMS}


def constant_index_patterns() -> list[list[int]]:
    return [
        [0, 1, 2, 3, 4, 9, 11, 13],
        [1, 2, 3, 4, 8, 13, 14, 15],
        [2, 3, 6, 7, 8, 13, 14, 15],
        [0, 1, 2, 3, 4, 5, 6, 7],
        [8, 9, 10, 11, 12, 13, 14, 15],
    ]


def params_from_window(
    window: Iterable[int],
    idxs: list[int],
    base: CipherParams,
    *,
    rotations: tuple[int, int, int, int] | None = None,
    double_rounds: int | None = None,
    counter_index: int | None = None,
    counter_add: int | None = None,
) -> CipherParams:
    const = dict(zip(idxs, [w & 0xFFFFFFFF for w in window]))
    return CipherParams(
        constants=const,
        key_layout=base.key_layout,
        rotations=rotations or base.rotations,
        double_rounds=double_rounds if double_rounds is not None else base.double_rounds,
        schedule=base.schedule,
        counter_index=counter_index if counter_index is not None else base.counter_index,
        counter_add=counter_add if counter_add is not None else base.counter_add,
    )


def mutate_constants(base: CipherParams, delta: int, index: int) -> CipherParams:
    const = dict(base.constants)
    idx = sorted(const.keys())[index % len(const)]
    const[idx] = (const[idx] + delta) & 0xFFFFFFFF
    return CipherParams(
        constants=const,
        key_layout=base.key_layout,
        rotations=base.rotations,
        double_rounds=base.double_rounds,
        schedule=base.schedule,
        counter_index=base.counter_index,
        counter_add=base.counter_add,
    )


def module_sample(mod_name: str, ck_entry: dict, hdr: bytes | None = None) -> ModuleSample:
    body = decompress_ck_module(ck_entry)
    prefix, ciphertext = split_ck_body(body)
    header = hdr or LJ_HEADERS[0]
    return ModuleSample(
        name=mod_name,
        prefix=prefix,
        ciphertext=ciphertext,
        key_shifted=module_key(ck_entry),
        target_keystream=cfb_keystream(ciphertext, header),
    )


def search_d_params(
    ciphertext: bytes,
    key: bytes,
    target_ks: bytes,
    base: CipherParams,
    *,
    rounds_range: range | None = None,
    counter_add_range: range | None = None,
    const_deltas: Iterable[int] | None = None,
) -> tuple[int, CipherParams | None]:
    """Return best keystream match score and matching params if any."""
    best_score = 0
    best_params: CipherParams | None = None
    rounds_range = rounds_range or range(max(6, base.double_rounds - 2), base.double_rounds + 3)
    counter_add_range = counter_add_range or range(max(0, base.counter_add - 8), base.counter_add + 9)
    const_deltas = list(const_deltas or [0])

    for rounds in rounds_range:
        for counter_add in counter_add_range:
            for delta in const_deltas:
                for idx in range(len(base.constants)):
                    params = mutate_constants(base, delta, idx)
                    params = CipherParams(
                        constants=params.constants,
                        key_layout=base.key_layout,
                        rotations=base.rotations,
                        double_rounds=rounds,
                        schedule=base.schedule,
                        counter_index=base.counter_index,
                        counter_add=counter_add,
                    )
                    ks = _block(_init_state(key, params), params)
                    score = keystream_score(ks, target_ks)
                    if score > best_score:
                        best_score = score
                        best_params = params
                        if score >= len(target_ks):
                            return score, params
    return best_score, best_params


def search_kernel_pool(
    key: bytes,
    target_ks: bytes,
    *,
    min_score: int = 6,
) -> list[DecryptAttempt]:
    attempts: list[DecryptAttempt] = []
    for window in KERNEL_POOL_WINDOWS:
        for idxs in constant_index_patterns():
            for base_name, base in candidate_param_bases().items():
                params = params_from_window(window, idxs, base)
                ks = _block(_init_state(key, params), params)
                score = keystream_score(ks, target_ks)
                if score >= min_score:
                    attempts.append(
                        DecryptAttempt(
                            module="pool",
                            params_name=f"{base_name}+pool",
                            key_name="d-shift",
                            score=score,
                            head=ks[:8],
                            params=params,
                        )
                    )
    attempts.sort(key=lambda item: item.score, reverse=True)
    return attempts


def analyze_module(mod_name: str, ck_entry: dict, sk: str = "") -> list[DecryptAttempt]:
    sample = module_sample(mod_name, ck_entry)
    attempts: list[DecryptAttempt] = []
    for hdr in LJ_HEADERS:
        target_ks = cfb_keystream(sample.ciphertext, hdr)
        for key_name, key in candidate_keys(ck_entry, sk).items():
            for base_name, base in candidate_param_bases().items():
                score, params = search_d_params(
                    sample.ciphertext,
                    key,
                    target_ks[:16],
                    base,
                    const_deltas=[0, 1, -1, 0x100, -0x100, 0x1000, -0x1000],
                )
                if score >= 4 and params:
                    pt = decrypt(sample.ciphertext[: len(hdr)], key, params)
                    attempts.append(
                        DecryptAttempt(
                            module=mod_name,
                            params_name=base_name,
                            key_name=key_name,
                            score=score,
                            head=pt[:8],
                            params=params,
                        )
                    )
                for pname, p in candidate_param_bases().items():
                    pt = decrypt(sample.ciphertext[:8], key, p)
                    if pt[:3] == b"\x1bLJ":
                        attempts.append(
                            DecryptAttempt(
                                module=mod_name,
                                params_name=pname,
                                key_name=key_name,
                                score=100,
                                head=pt[:8],
                                params=p,
                            )
                        )
    attempts.sort(key=lambda item: item.score, reverse=True)
    return attempts


def cross_module_keystreams(init: dict, hdr: bytes | None = None) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    header = hdr or LJ_HEADERS[0]
    for name, entry in sorted(init.get("ck", {}).items()):
        sample = module_sample(name, entry, header)
        rows.append((name, sample.target_keystream[:8].hex()))
    return rows


def analyze_sk(sk: str) -> list[DecryptAttempt]:
    parts = sk.split(";")
    if len(parts) < 2:
        return []
    ct = _b64u_decode(parts[0])
    attempts: list[DecryptAttempt] = []
    sk_key = _b64u_decode(parts[1])
    keys = {"sk-shift": shift_seed(sk_key), "sk-raw": sk_key}
    for hdr in LJ_HEADERS:
        target_ks = cfb_keystream(ct, hdr)
        for key_name, key in keys.items():
            for base_name, base in candidate_param_bases().items():
                score, params = search_d_params(ct, key, target_ks[:16], base)
                if score >= 4 and params:
                    pt = decrypt(ct[: len(hdr)], key, params)
                    attempts.append(
                        DecryptAttempt(
                            module="sk",
                            params_name=base_name,
                            key_name=key_name,
                            score=score,
                            head=pt[:8],
                            params=params,
                        )
                    )
    attempts.sort(key=lambda item: item.score, reverse=True)
    return attempts


def dump_modules(init_path: str | Path, out_dir: str | Path) -> Path:
    init = load_init(init_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, entry in init["ck"].items():
        body = decompress_ck_module(entry)
        (out / f"{name}.bin").write_bytes(body)
        prefix, ciphertext = split_ck_body(body)
        (out / f"{name}.ct.bin").write_bytes(ciphertext)
    return out


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init", default="/tmp/init.json")
    parser.add_argument("--module", default="f5")
    parser.add_argument("--dump", default="")
    parser.add_argument("--cross", action="store_true", help="print per-module keystream prefixes")
    parser.add_argument("--pool", action="store_true", help="search kernel pool constant windows")
    args = parser.parse_args()

    init = load_init(args.init)
    if args.dump:
        path = dump_modules(args.init, args.dump)
        print(f"dumped ck modules to {path}")
        return 0

    if args.cross:
        print("=== cross-module keystream[:8] (LuaJIT 2.1 header) ===")
        for name, ks in cross_module_keystreams(init):
            print(f"  {name}: {ks}")
        return 0

    ck = init["ck"]
    mods = [args.module] if args.module != "all" else sorted(ck.keys())
    for name in mods:
        sample = module_sample(name, ck[name])
        print(f"=== {name} ===")
        print(f"  prefix: {sample.prefix!r}")
        print(f"  ct head: {sample.ciphertext[:8].hex()}")
        print(f"  key (shifted): {sample.key_shifted.hex()}")
        print(f"  target ks[:10]: {sample.target_keystream[:10].hex()}")
        if args.pool:
            hits = search_kernel_pool(sample.key_shifted, sample.target_keystream[:10])
            if not hits:
                print("  pool search: no hits")
            for attempt in hits[:5]:
                print(f"  pool score={attempt.score} base={attempt.params_name}")
        for attempt in analyze_module(name, ck[name], init.get("sk", ""))[:8]:
            print(
                f"  score={attempt.score:3} key={attempt.key_name:10} "
                f"base={attempt.params_name} head={attempt.head.hex()}"
            )

    print("=== sk ===")
    for attempt in analyze_sk(init.get("sk", ""))[:8]:
        print(
            f"  score={attempt.score:3} key={attempt.key_name:10} "
            f"base={attempt.params_name} head={attempt.head.hex()}"
        )
    print(
        f"\nNote: D cipher is VM GI[{VM_CRYPTO_FN_INDEX}] @ offset {VM_CRYPTO_OFFSET}; "
        "not matched by E/G/TAG mutations or kernel pool windows yet."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
