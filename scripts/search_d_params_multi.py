#!/usr/bin/env python3
"""Multi-module constrained D_PARAMS search using all ck keystream anchors.

Any valid D ChaCha params must reproduce keystream prefixes for every ck module.
Writes /tmp/d_params_multi.json (or --out path).
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
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
from southwest_checker.apiguard.ck_decrypt import (
    LJ_HEADERS,
    cfb_keystream,
    decompress_ck_module,
    module_key,
    split_ck_body,
)

GQ_CORE5 = [0x2E6C6DEA, 0x17ACECDB, 0x0F86D1DB, 0x780B0A1B, 0x5260E60B]
GQ_FILL = [0x4E0C1F17, 0xD8238B63, 0xC0F5C68A]
CONST_IDX = [0, 1, 2, 3, 4, 9, 11, 13]
ROTATIONS = [(3, 6, 6, 1), (3, 6, 3, 6), (6, 3, 6, 3)]
LAYOUTS = {"E": E_PARAMS, "G": G_PARAMS, "TAG": TAG_PARAMS}
COUNTER_IDX = (0, 4, 5, 9, 12, 15)
COUNTER_ADD = (0, 1, 41, 64, 68)


def module_targets(init: dict) -> list[tuple[str, bytes, bytes]]:
    rows: list[tuple[str, bytes, bytes]] = []
    hdr = LJ_HEADERS[0]
    for name, entry in sorted(init.get("ck", {}).items()):
        body = decompress_ck_module(entry)
        _, ct = split_ck_body(body)
        key = module_key(entry)
        target = cfb_keystream(ct, hdr)[:10]
        rows.append((name, key, target))
    return rows


def score_all(params: CipherParams, modules: list[tuple[str, bytes, bytes]]) -> tuple[int, int, list[int]]:
    per_mod: list[int] = []
    for _, key, target in modules:
        ks = _block(_init_state(key, params), params)
        per_mod.append(sum(a == b for a, b in zip(ks, target)))
    return min(per_mod), sum(per_mod), per_mod


def _modules_payload(modules: list[tuple[str, bytes, bytes]]) -> list[tuple[str, bytes, bytes]]:
    return modules


def search_chunk(
    perm_chunk: list[tuple[int, ...]],
    modules: list[tuple[str, bytes, bytes]],
) -> dict[str, Any]:
    best: dict[str, Any] = {"min_score": 0, "total_score": 0}
    searched = 0
    byte0_hits = 0
    mod_names = [m[0] for m in modules]

    for perm in perm_chunk:
        constants = dict(zip(CONST_IDX, perm))
        for layout_name, base in LAYOUTS.items():
            layout = base.key_layout
            for rot in ROTATIONS:
                for dr in range(7, 13):
                    for ci in COUNTER_IDX:
                        for ca in COUNTER_ADD:
                            params = CipherParams(
                                constants=constants,
                                key_layout=layout,
                                rotations=rot,
                                double_rounds=dr,
                                schedule=base.schedule,
                                counter_index=ci,
                                counter_add=ca,
                            )
                            mn, total, per = score_all(params, modules)
                            searched += 1
                            if mn == 0:
                                continue
                            if mn >= 1:
                                byte0_hits += 1
                            if mn > best["min_score"] or (
                                mn == best["min_score"] and total > best.get("total_score", 0)
                            ):
                                best = {
                                    "min_score": mn,
                                    "total_score": total,
                                    "per_module": dict(zip(mod_names, per)),
                                    "layout": layout_name,
                                    "rotations": rot,
                                    "double_rounds": dr,
                                    "counter_index": ci,
                                    "counter_add": ca,
                                    "constants": {str(k): f"0x{v:08x}" for k, v in constants.items()},
                                }
                            if mn >= 10:
                                return {"best": best, "searched": searched, "byte0_hits": byte0_hits}

    return {"best": best, "searched": searched, "byte0_hits": byte0_hits}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init", default="/tmp/init.json")
    parser.add_argument("--out", default="/tmp/d_params_multi.json")
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    args = parser.parse_args()

    init = json.loads(Path(args.init).read_text())
    modules = module_targets(init)
    pool8 = list(dict.fromkeys(GQ_CORE5 + GQ_FILL))[:8]
    perms = list(set(itertools.permutations(pool8)))

    jobs = max(1, min(args.jobs, len(perms)))
    chunk_size = (len(perms) + jobs - 1) // jobs
    chunks = [perms[i : i + chunk_size] for i in range(0, len(perms), chunk_size)]

    print(f"modules={len(modules)} permutations={len(perms)} chunks={len(chunks)} jobs={jobs}")

    best: dict[str, Any] = {"min_score": 0, "total_score": 0}
    searched = 0
    byte0_hits = 0

    if jobs == 1:
        result = search_chunk(perms, modules)
        best = result["best"]
        searched = result["searched"]
        byte0_hits = result["byte0_hits"]
    else:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            futures = [pool.submit(search_chunk, chunk, modules) for chunk in chunks]
            for fut in as_completed(futures):
                result = fut.result()
                searched += result["searched"]
                byte0_hits += result["byte0_hits"]
                rb = result["best"]
                if rb["min_score"] > best["min_score"] or (
                    rb["min_score"] == best["min_score"]
                    and rb.get("total_score", 0) > best.get("total_score", 0)
                ):
                    best = rb
                if best.get("min_score", 0) >= 10:
                    for f in futures:
                        f.cancel()
                    break

    output = {
        "init": args.init,
        "modules": len(modules),
        "searched": searched,
        "byte0_hits": byte0_hits,
        "best": best,
        "module_targets_byte0": {name: target[0] for name, _, target in modules},
        "jobs": jobs,
    }
    Path(args.out).write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
