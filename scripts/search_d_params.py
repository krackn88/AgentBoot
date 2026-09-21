#!/usr/bin/env python3
"""Expanded D_PARAMS search for APIGuard ck module decryption.

Uses VM disassembly anchors (Gq loads, op186 rotations) and brute-forces
CipherParams against the f5 known-plaintext keystream prefix.

Writes /tmp/d_params_search.json
"""

from __future__ import annotations

import argparse
import ast
import base64
import itertools
import json
import re
import zlib
from dataclasses import asdict
from pathlib import Path
from typing import Any

from southwest_checker.apiguard.cipher import (
    CipherParams,
    E_PARAMS,
    G_PARAMS,
    TAG_PARAMS,
    _block,
    _init_state,
)
from southwest_checker.apiguard.headers import b64u_decode, shift_seed

LJ_HEADER = bytes.fromhex("1b4c4a02000000000000")
TARGET_KS = bytes.fromhex("51859262afb3edb6b357")

# GI[135] cipher body @ Q~104700-105400 (load order by PC)
GQ_CORE5_ORDER = [
    0x2E6C6DEA,  # Gq[31]
    0x17ACECDB,  # Gq[10]
    0x0F86D1DB,  # Gq[6]
    0x780B0A1B,  # Gq[54]
    0x5260E60B,  # Gq[0]
]

GQ_FILL_CANDIDATES = [
    0x4E0C1F17,  # embedded u32 in cipher band
    0xD8238B63,  # Gq[1] elsewhere in kernel
    0xC0F5C68A,  # Gq[3]
    0x2140F7E7,  # Gq[23]
    0x6156020B,  # Gq[61]
    0x05856ACF,  # Gq[4]
]

CONST_INDEX_PATTERNS = [
    [0, 1, 2, 3, 4, 9, 11, 13],
    [1, 2, 3, 4, 8, 13, 14, 15],
    [2, 3, 6, 7, 8, 13, 14, 15],
    [0, 1, 2, 3, 4, 5, 6, 7],
    [8, 9, 10, 11, 12, 13, 14, 15],
]

KEY_LAYOUTS = {
    "E": E_PARAMS.key_layout,
    "G": G_PARAMS.key_layout,
    "TAG": TAG_PARAMS.key_layout,
}

SCHEDULES = {
    "E": E_PARAMS.schedule,
    "G": G_PARAMS.schedule,
    "TAG": TAG_PARAMS.schedule,
}

# op186 rotl amounts 3,6 + op191 ror31 (=rotl 1) in cipher body
ROTATIONS = [
    (3, 6, 6, 1),
    (3, 6, 3, 6),
    (6, 3, 6, 3),
    (3, 6, 6, 3),
    (6, 6, 3, 6),
    (3, 6, 6, 6),
    (10, 10, 10, 10),
    E_PARAMS.rotations,
    G_PARAMS.rotations,
    TAG_PARAMS.rotations,
]


def cfb_keystream(ciphertext: bytes, plaintext: bytes, *, feedback: str = "plaintext") -> bytes:
    out = bytearray(len(plaintext))
    for i in range(len(plaintext)):
        if i == 0:
            fb = 0
        elif feedback == "plaintext":
            fb = plaintext[i - 1]
        else:
            fb = ciphertext[i - 1]
        out[i] = ciphertext[i] ^ plaintext[i] ^ fb
    return bytes(out)


def score(params: CipherParams, key: bytes, target: bytes) -> tuple[int, bytes]:
    ks = _block(_init_state(key, params), params)
    n = min(len(target), len(ks))
    return sum(a == b for a, b in zip(ks[:n], target[:n])), ks


def params_to_dict(p: CipherParams) -> dict[str, Any]:
    return {
        "constants": {str(k): f"0x{v:08x}" for k, v in sorted(p.constants.items())},
        "key_layout": [list(pair) for pair in p.key_layout],
        "rotations": list(p.rotations),
        "double_rounds": p.double_rounds,
        "schedule": [list(q) for q in p.schedule],
        "counter_index": p.counter_index,
        "counter_add": p.counter_add,
    }


def parse_gq_ints(kernel: str) -> list[int]:
    m = re.search(r"var Gq=(\[[^\]]+\])", kernel)
    if not m:
        return []
    gq = ast.literal_eval(m.group(1))
    return [int(x) for x in gq if isinstance(x, int) and 0 < x < 2**32]


def candidate_keys(ck_entry: dict, sk: str) -> dict[str, bytes]:
    keys: dict[str, bytes] = {}
    d_raw = bytes.fromhex(ck_entry["d"])
    keys["d-shift"] = shift_seed(d_raw)
    keys["d-raw"] = d_raw
    if sk:
        parts = sk.split(";")
        if len(parts) >= 2:
            sk_key = b64u_decode(parts[1])
            keys["xor-d-sk-shift"] = shift_seed(bytes(a ^ b for a, b in zip(d_raw, sk_key)))
    return keys


def update_best(
    best: dict[str, Any],
    s: int,
    ks: bytes,
    params: CipherParams,
    meta: dict[str, Any],
) -> dict[str, Any]:
    if s > best["score"]:
        best = {
            "score": s,
            "target_len": len(TARGET_KS),
            "generated_keystream_prefix": ks[:10].hex(),
            "params": params_to_dict(params),
            "meta": meta,
        }
    return best


def search_phase_base_mut(key: bytes, target: bytes, best: dict[str, Any]) -> tuple[dict[str, Any], int]:
    searched = 0
    for base_name, base in {"E": E_PARAMS, "G": G_PARAMS, "TAG": TAG_PARAMS}.items():
        for rot in ROTATIONS:
            for dr in range(6, 14):
                for ci in range(16):
                    for ca in range(0, 129):
                        p = CipherParams(
                            constants=base.constants,
                            key_layout=base.key_layout,
                            rotations=rot,
                            double_rounds=dr,
                            schedule=base.schedule,
                            counter_index=ci,
                            counter_add=ca,
                        )
                        s, ks = score(p, key, target)
                        searched += 1
                        best = update_best(best, s, ks, p, {"phase": "base_mut", "base": base_name})
                        if s >= len(target):
                            return best, searched
    return best, searched


def search_phase_gq_pool(
    key: bytes,
    target: bytes,
    gq_ints: list[int],
    best: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    searched = 0
    idx = [0, 1, 2, 3, 4, 9, 11, 13]
    for start in range(0, max(0, len(gq_ints) - 7)):
        window = gq_ints[start : start + 8]
        constants = dict(zip(idx, window))
        for layout_name, layout in KEY_LAYOUTS.items():
            for sched_name, sched in SCHEDULES.items():
                for rot in ROTATIONS[:6]:
                    for dr in range(8, 12):
                        for ci in (0, 5, 9, 12, 15):
                            for ca in (0, 1, 41, 64, 68, 0x3A):
                                p = CipherParams(
                                    constants=constants,
                                    key_layout=layout,
                                    rotations=rot,
                                    double_rounds=dr,
                                    schedule=sched,
                                    counter_index=ci,
                                    counter_add=ca,
                                )
                                s, ks = score(p, key, target)
                                searched += 1
                                best = update_best(
                                    best,
                                    s,
                                    ks,
                                    p,
                                    {
                                        "phase": "gq_sliding_window",
                                        "window_start": start,
                                        "layout": layout_name,
                                        "schedule": sched_name,
                                    },
                                )
                                if s >= len(target):
                                    return best, searched
    return best, searched


def search_phase_core8_perms(key: bytes, target: bytes, best: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Permute 8-word pool (core5 + 3 fill) on E-like index pattern; coarse inner grid."""
    searched = 0
    idx = [0, 1, 2, 3, 4, 9, 11, 13]
    pool8 = GQ_CORE5_ORDER + GQ_FILL_CANDIDATES[:3]
    perms_first_byte = []
    for perm in set(itertools.permutations(pool8)):
        constants = dict(zip(idx, perm))
        p = CipherParams(
            constants=constants,
            key_layout=E_PARAMS.key_layout,
            rotations=(3, 6, 6, 1),
            double_rounds=10,
            schedule=E_PARAMS.schedule,
            counter_index=15,
            counter_add=68,
        )
        ks = _block(_init_state(key, p), p)
        searched += 1
        if ks[0] == target[0]:
            perms_first_byte.append(perm)

    for perm in perms_first_byte:
        constants = dict(zip(idx, perm))
        for layout_name, layout in KEY_LAYOUTS.items():
            base = {"E": E_PARAMS, "G": G_PARAMS, "TAG": TAG_PARAMS}[layout_name]
            for rot in ROTATIONS[:6]:
                for dr in range(7, 13):
                    for ci in (0, 4, 5, 9, 12, 15):
                        for ca in (0, 1, 41, 64, 68, 0x3A):
                            p = CipherParams(
                                constants=constants,
                                key_layout=layout,
                                rotations=rot,
                                double_rounds=dr,
                                schedule=base.schedule,
                                counter_index=ci,
                                counter_add=ca,
                            )
                            s, ks = score(p, key, target)
                            searched += 1
                            best = update_best(
                                best,
                                s,
                                ks,
                                p,
                                {"phase": "core8_perm", "layout": layout_name, "perm": [f"0x{x:08x}" for x in perm]},
                            )
                            if s >= len(target):
                                return best, searched
    return best, searched


def run_search(key: bytes, target: bytes, gq_ints: list[int]) -> tuple[dict[str, Any], int]:
    best: dict[str, Any] = {"score": 0, "target_len": len(target)}
    total = 0
    for fn in (search_phase_base_mut, search_phase_gq_pool, search_phase_core8_perms):
        if fn is search_phase_gq_pool:
            best, n = fn(key, target, gq_ints, best)
        else:
            best, n = fn(key, target, best)
        total += n
        if best["score"] >= len(target):
            break
    return best, total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init", default="/tmp/init.json")
    parser.add_argument("--module", default="f5")
    parser.add_argument("--out", default="/tmp/d_params_search.json")
    args = parser.parse_args()

    init = json.loads(Path(args.init).read_text())
    mod = init["ck"][args.module]
    body = zlib.decompress(base64.b64decode(mod["c"]))
    ct = body[4:]
    gq_ints = parse_gq_ints(init.get("kernel", ""))
    keys = candidate_keys(mod, init.get("sk", ""))

    targets = {
        "plaintext_fb": cfb_keystream(ct, LJ_HEADER, feedback="plaintext"),
        "ciphertext_fb": cfb_keystream(ct, LJ_HEADER, feedback="ciphertext"),
    }

    overall_best: dict[str, Any] = {"score": 0}
    total_searched = 0
    per_target: dict[str, Any] = {}

    for fb_name, target in targets.items():
        for key_name, key in keys.items():
            label = f"{fb_name}/{key_name}"
            best, searched = run_search(key, target[:10], gq_ints)
            total_searched += searched
            per_target[label] = best
            if best["score"] > overall_best.get("score", 0):
                overall_best = {**best, "target_label": label}

    found = overall_best.get("score", 0) >= len(TARGET_KS)
    result = {
        "module": args.module,
        "anchor": {
            "ciphertext_head": ct[:10].hex(),
            "key_shifted": keys["d-shift"].hex(),
            "target_keystream": TARGET_KS.hex(),
            "lua_header": LJ_HEADER.hex(),
        },
        "vm_disasm": {
            "cipher_body_pc": 104826,
            "gq_load_order_hex": [f"0x{x:08x}" for x in GQ_CORE5_ORDER],
            "gq_indices": [31, 10, 6, 54, 0],
            "rotation_operands_op186": [3, 6],
            "rotation_operands_ror31": "rotl 1 at quarter-round boundary",
            "rotation_candidates": [list(r) for r in ROTATIONS[:6]],
        },
        "best_score": overall_best.get("score", 0),
        "best_target_len": len(TARGET_KS),
        "best": overall_best if overall_best.get("score", 0) else None,
        "per_target": per_target,
        "searched": total_searched,
        "found_10_10": found,
        "recommended_next_step": (
            "Add D_PARAMS to southwest_checker/apiguard/cipher.py and verify full ck decrypt."
            if found
            else (
                f"Static ChaCha-CFB search peaked at {overall_best.get('score', 0)}/10. "
                "GI[135] bootstrap call r(135,91131,5) returns an instrumentation closure "
                "{init,teardown}, not decrypted bytes; ck stays encrypted in JSDOM through "
                "bootstrap+probe callback (0 LuaJIT fromCharCode events). "
                "D params require either: (1) static VM emulation of GI[135] body at Q~104826 "
                "with custom key_layout/schedule decoded from op186 quarter-round indices, or "
                "(2) native runtime capture (Frida/device) during real ck lazy-load."
            )
        ),
    }

    Path(args.out).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
