#!/usr/bin/env python3
"""Analyze APIGuard init kernel for D-variant ChaCha-CFB parameters (ck/sk decryption).

Reads /tmp/init.json by default, searches the embedded JS VM for cipher-related
patterns, computes known-plaintext keystream from ck modules, and runs a bounded
parameter search against E/G/TAG bases.

Usage:
  python scripts/analyze_kernel_d_cipher.py
  python scripts/analyze_kernel_d_cipher.py --init /tmp/init.json --module f5
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import struct
import zlib
from pathlib import Path

from southwest_checker.apiguard.cipher import (
    E_PARAMS,
    G_PARAMS,
    TAG_PARAMS,
    CipherParams,
    _block,
    _init_state,
)
from southwest_checker.apiguard.headers import shift_seed

PREFIX = b"\x10SP\x83"
LJ_HEADER = bytes.fromhex("1b4c4a02000000000000")

# VM string-table indices (init kernel A9eCEcWg…)
STR_IDX = {
    "global": 131,
    "charCodeAt": 96,
    "fromCharCode": 159,
    "crypto": 644,
    "Int8Array": 643,
    "Uint8Array": 866,
    "Uint32Array": 651,
    "TextDecoder": 767,
    "LN2": 799,
    "initCustomEvent": 281,
    "CustomEvent": 506,
}

# Offsets in current /tmp/init.json kernel (252_627 bytes)
KERNEL_OFFSETS = {
    "vm_block_charcode": 45305,  # uses charCodeAt + fromCharCode
    "vm_constant_pool": 64100,
    "bootstrap_custom_event": 252005,
    "bootstrap_ints_array": 252257,
    "key_layout_5_12": 31773,
    "key_layout_8_24": 33457,
    "key_layout_6_16": 40653,
}


def load_kernel(init_path: Path) -> tuple[dict, str]:
    init = json.loads(init_path.read_text())
    return init, init.get("kernel", "")


def extract_string_table(kernel: str) -> list[str]:
    start = kernel.find("var C=[")
    end = kernel.find("];var", start)
    if start < 0 or end < 0:
        return []
    chunk = kernel[start + 7 : end]
    raw = re.findall(r'"((?:\\.|[^"\\])*)"', chunk)

    def dec(s: str) -> str:
        return re.sub(
            r"\\x([0-9a-fA-F]{2})",
            lambda m: chr(int(m.group(1), 16)),
            s,
        )

    return [dec(s) for s in raw]


def parse_bootstrap(kernel: str) -> dict:
    m = re.search(
        r'createEvent\("CustomEvent"\),\["([^"]+)","([^"]+)",(\[[^\]]*\]),(\[\d+(?:,\d+){7}\])',
        kernel,
    )
    if not m:
        return {}
    ints = [int(x) for x in m.group(4).strip("[]").split(",")]
    return {
        "kernelId": m.group(1),
        "sessionKey": m.group(2),
        "ck_placeholder": m.group(3),
        "ints": ints,
        "ints_hex": [f"{x:08x}" for x in ints],
    }


def cfb_keystream_prefix(ciphertext: bytes, plaintext: bytes) -> bytes:
    out = bytearray(len(plaintext))
    for i in range(len(plaintext)):
        if i == 0:
            out[i] = ciphertext[i] ^ plaintext[i]
        else:
            out[i] = ciphertext[i] ^ plaintext[i] ^ plaintext[i - 1]
    return bytes(out)


def decompress_ck(ck_entry: dict) -> tuple[bytes, bytes]:
    body = zlib.decompress(base64.b64decode(ck_entry["c"]))
    if not body.startswith(PREFIX):
        raise ValueError(f"unexpected ck prefix {body[:4]!r}")
    return body[:4], body[4:]


def find_vm_blocks(kernel: str) -> list[dict]:
    blocks = []
    for m in re.finditer(r"\{H:\[([^\]]*)\],L:\[([^\]]*)\],V:\[([^\]]*)\]\}", kernel):
        blocks.append(
            {
                "offset": m.start(),
                "H": [int(x) for x in m.group(1).split(",") if x],
                "L": [int(x) for x in m.group(2).split(",") if x],
                "V": [int(x) for x in m.group(3).split(",") if x],
            }
        )
    return blocks


def blocks_using_strings(blocks: list[dict], strings: list[str], indices: set[int]) -> list[dict]:
    hits = []
    for b in blocks:
        used = [i for i in b["V"] if i in indices]
        if used:
            hits.append({**b, "string_hits": {i: strings[i] for i in used if i < len(strings)}})
    return hits


def bounded_search(target_ks: bytes, key: bytes) -> list[tuple[int, str, CipherParams]]:
    results: list[tuple[int, str, CipherParams]] = []
    bases = {"E": E_PARAMS, "G": G_PARAMS, "TAG": TAG_PARAMS}
    rots = [(16, 12, 8, 7), (18, 13, 11, 4), (17, 18, 13, 6), (19, 14, 3, 10)]

    for bname, base in bases.items():
        for rot in rots:
            for dr in range(max(6, base.double_rounds - 3), base.double_rounds + 4):
                for ca in range(max(0, base.counter_add - 16), base.counter_add + 17):
                    for ci in range(16):
                        params = CipherParams(
                            constants=base.constants,
                            key_layout=base.key_layout,
                            rotations=rot,
                            double_rounds=dr,
                            schedule=base.schedule,
                            counter_index=ci,
                            counter_add=ca,
                        )
                        ks = _block(_init_state(key, params), params)
                        score = sum(a == b for a, b in zip(ks, target_ks))
                        if score >= 3:
                            results.append((score, bname, params))
    results.sort(key=lambda x: x[0], reverse=True)
    return results[:10]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init", default="/tmp/init.json")
    parser.add_argument("--module", default="f5")
    args = parser.parse_args()

    init, kernel = load_kernel(Path(args.init))
    strings = extract_string_table(kernel)
    bootstrap = parse_bootstrap(kernel)
    blocks = find_vm_blocks(kernel)

    ck = init.get("ck", {})
    mod = ck.get(args.module, {})
    prefix, ciphertext = decompress_ck(mod) if mod else (b"", b"")
    key = shift_seed(bytes.fromhex(mod["d"])) if mod else b""
    target_ks = cfb_keystream_prefix(ciphertext, LJ_HEADER) if ciphertext else b""

    print("=== init summary ===")
    print(f"kernelId: {init.get('kernelId', '')[:48]}…")
    print(f"kernel bytes: {len(kernel)}")
    print(f"ck modules: {sorted(ck.keys())}")
    print(f"sk suffix: {init.get('sk', '').split(';')[-1] if init.get('sk') else ''}")

    print("\n=== known-plaintext (module", args.module, ") ===")
    print(f"prefix: {prefix!r}")
    print(f"ct head: {ciphertext[:8].hex() if ciphertext else ''}")
    print(f"d key (shifted): {key.hex()}")
    print(f"target keystream[:10]: {target_ks[:10].hex()}")

    print("\n=== bootstrap CustomEvent args ===")
    for k, v in bootstrap.items():
        print(f"  {k}: {v}")

    print("\n=== string table (cipher-related) ===")
    for name, idx in STR_IDX.items():
        val = strings[idx] if idx < len(strings) else "?"
        print(f"  [{idx}] {name}: {val!r}")

    print("\n=== kernel offsets (current build) ===")
    for name, off in KERNEL_OFFSETS.items():
        print(f"  {name}: {off}")

    crypto_blocks = blocks_using_strings(blocks, strings, {96, 159, 644, 866, 767})
    print(f"\n=== VM blocks referencing byte/crypto strings: {len(crypto_blocks)} ===")
    for b in crypto_blocks[:5]:
        print(
            f"  off={b['offset']} |H|={len(b['H'])} |V|={len(b['V'])} "
            f"hits={list(b['string_hits'].keys())}"
        )
    print("  GI[127] @ offset 45305 is the sole charCodeAt+fromCharCode block (D cipher)")

    if target_ks and key:
        print("\n=== bounded E/G/TAG mutation search (best scores) ===")
        hits = bounded_search(target_ks, key)
        if not hits:
            print("  no score>=3 hits — D variant is not a nearby E/G/TAG mutation")
        for score, bname, params in hits:
            print(
                f"  score={score} base={bname} rot={params.rotations} "
                f"dr={params.double_rounds} ci={params.counter_index} ca={params.counter_add}"
            )

    print("\n=== sk blob ===")
    sk = init.get("sk", "")
    if sk:
        parts = sk.split(";")
        print(f"  parts: {len(parts)} ident={parts[-1] if parts else ''}")
        if len(parts) >= 2:
            ct = base64.b64decode(parts[0].replace("-", "+").replace("_", "/") + "==")
            print(f"  ct len={len(ct)} head={ct[:8].hex()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
