#!/usr/bin/env python3
"""Disassemble APIGuard D-cipher VM for the current kernel format (B/bA/bC/bK).

Targets B[624] (static D cipher — fromCharCode + Uint32Array) and scans bytecode
call sites, Gq pool loads, rotation operands, and known-plaintext anchor for f5.

Writes /tmp/vm_disasm_new.txt and prints a summary.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from southwest_checker.apiguard.kernel_parse import (
    find_crypto_blocks,
    handler_operand_increments,
    load_kernel_vm,
)

INIT_PATH = Path("/tmp/init.json")
OUT_PATH = Path("/tmp/vm_disasm_new.txt")

# Primary static D-cipher block in current kernels.
D_BLOCK_STATIC = 624
D_BLOCK_RUNTIME = 135

PREFIX = b"\x10SP\x83"
SHIFT_PREFIX = b"X-dUblrIiu-"
LJ_HEADER = bytes.fromhex("1b4c4a02000000000000")

CRYPTO_OPS = {47, 66, 117, 118, 128, 186, 191, 203, 63, 92, 82, 221, 232, 12, 33, 2, 15, 61, 112}


def u16le(data: bytes, off: int) -> int:
    return data[off] | (data[off + 1] << 8)


def u32le(data: bytes, off: int) -> int:
    return (
        data[off]
        | (data[off + 1] << 8)
        | (data[off + 2] << 16)
        | (data[off + 3] << 24)
    )


def shift_seed(seed: bytes) -> bytes:
    key = bytearray(seed)
    for i in range(min(len(SHIFT_PREFIX), len(key))):
        key[i] ^= SHIFT_PREFIX[i]
    return bytes(key)


def cfb_keystream_prefix(ciphertext: bytes, plaintext: bytes) -> bytes:
    out = bytearray(len(plaintext))
    for i in range(len(plaintext)):
        fb = plaintext[i - 1] if i else 0
        out[i] = ciphertext[i] ^ plaintext[i] ^ fb
    return bytes(out)


@dataclass
class Instr:
    pc: int
    seg: int
    op: int
    operands: bytes
    next_seg: int
    text: str = ""


@dataclass
class DisasmResult:
    lines: list[Instr] = field(default_factory=list)
    pool_loads: list[tuple[int, int, int]] = field(default_factory=list)
    u32_consts: list[tuple[int, int]] = field(default_factory=list)
    rotations: list[tuple[int, int, int]] = field(default_factory=list)
    block_calls: list[dict] = field(default_factory=list)


class VmDisassembler:
    def __init__(self, vm) -> None:
        self.vm = vm
        self.q = vm.bytecode
        self.seg_tbl = vm.segment_table
        self.op_inc = handler_operand_increments(vm)
        self.strings = vm.strings
        self.pool = vm.pool

    def _fmt(self, op: int, operands: bytes, pc: int) -> str:
        if op in (47, 66) and operands:
            idx = operands[0]
            val = self.pool[idx] if idx < len(self.pool) else None
            if isinstance(val, int):
                return f"bK[{idx}]=0x{val:08x}"
            return f"bK[{idx}]={val!r}"
        if op in (19, 35, 57, 77, 96, 168) and len(operands) >= 2:
            si = u16le(operands, 0)
            name = self.strings[si] if si < len(self.strings) else "?"
            if len(name) > 40:
                name = name[:40] + "…"
            return f'str[{si}]="{name}"'
        if op == 63 and len(operands) >= 4:
            gi = u16le(operands, 2)
            return f"F({gi}, M[{operands[1]}], M[{operands[0]}])"
        if op == 92 and len(operands) >= 2:
            gi = u16le(operands, 0)
            return f"F({gi}, stack[-1], stack[-2])"
        if op in (2, 12, 33, 39, 61, 112, 155, 166, 176, 200) and len(operands) >= 4:
            val = u32le(operands, 0)
            return f"u32=0x{val:08x}"
        if op == 186 and len(operands) >= 2:
            return f"rotl(>>>{operands[1]})"
        if op == 128 and operands:
            return f"shl {operands[0]}"
        if op == 191 and operands:
            return f"ror {operands[0]}"
        if op in (117, 118):
            return "charCodeAt"
        if operands:
            return " ".join(f"{b:02x}" for b in operands)
        return ""

    def disasm(self, z: int, seg: int, limit: int = 400) -> DisasmResult:
        res = DisasmResult()
        seen: set[tuple[int, int]] = set()
        for _ in range(limit):
            if z >= len(self.q):
                break
            key = (z, seg)
            if key in seen:
                res.lines.append(Instr(z, seg, -1, b"", seg, "LOOP"))
                break
            seen.add(key)

            qb = self.q[z]
            z += 1
            if seg >= len(self.seg_tbl) or qb >= len(self.seg_tbl[seg]):
                res.lines.append(Instr(z - 1, seg, -1, b"", seg, f"byte={qb} OOR"))
                break
            next_seg, op = self.seg_tbl[seg][qb]
            inc = self.op_inc.get(op, 0)
            operands = self.q[z : z + inc]
            z += inc
            text = self._fmt(op, operands, z - inc - 1)
            ins = Instr(z - inc - 1, seg, op, operands, next_seg, text)
            res.lines.append(ins)

            if op in (47, 66) and operands:
                idx = operands[0]
                if idx < len(self.pool) and isinstance(self.pool[idx], int):
                    res.pool_loads.append((ins.pc, idx, self.pool[idx]))
            if op in (2, 12, 33, 39, 61, 112, 155, 166, 176, 200) and len(operands) >= 4:
                res.u32_consts.append((ins.pc, u32le(operands, 0)))
            if op == 186 and len(operands) >= 2:
                res.rotations.append((ins.pc, op, operands[1]))
            if op == 128 and operands:
                res.rotations.append((ins.pc, op, operands[0]))
            if op == 191 and operands:
                res.rotations.append((ins.pc, op, operands[0]))
            if op in (63, 92, 221, 232) and len(operands) >= 2:
                gi = u16le(operands, 2 if op == 63 else 0)
                res.block_calls.append({"pc": ins.pc, "op": op, "block": gi})

            seg = next_seg
        return res

    def find_block_refs(self, block_idx: int) -> list[int]:
        refs = []
        for i in range(len(self.q) - 1):
            if u16le(self.q, i) == block_idx:
                refs.append(i)
        return refs


def candidate_entries(call_sites: list[int], q: bytes) -> list[tuple[int, int, str]]:
    entries: list[tuple[int, int, str]] = []
    seen: set[tuple[int, int]] = set()

    def add(z: int, seg: int, note: str) -> None:
        if (z, seg) not in seen and 0 <= z < len(q) and 0 <= seg < 10:
            seen.add((z, seg))
            entries.append((z, seg, note))

    for pos in call_sites:
        for dz in (0, -2, -4, -6, 2, 4):
            z = pos + dz
            if z < 0 or z + 3 >= len(q):
                continue
            add(u16le(q, z), q[z + 2], f"pair@{z} near call@{pos}")

    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init", type=Path, default=INIT_PATH)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    parser.add_argument("--block", type=int, default=D_BLOCK_STATIC)
    parser.add_argument("--module", default="f5")
    args = parser.parse_args()

    init = json.loads(args.init.read_text())
    vm = load_kernel_vm(args.init)
    dis = VmDisassembler(vm)
    crypto_blocks = find_crypto_blocks(vm)
    call_sites = dis.find_block_refs(args.block)

    lines: list[str] = []
    w = lines.append

    w("=" * 72)
    w("APIGuard D-cipher VM disassembly (current B/bA/bC format)")
    w("=" * 72)
    w(f"init: {args.init}")
    w(f"kernel bytes: {len(vm.kernel)}")
    w(f"bytecode bytes: {len(vm.bytecode)}")
    w(f"B blocks: {len(vm.blocks)}  strings: {len(vm.strings)}")
    w(f"segments: {len(vm.segment_table)}  handlers: {len(vm.handlers)}")
    w(f"pool bK: {len(vm.pool)} entries")
    w("")
    w("--- crypto-related B blocks (fromCharCode in X refs) ---")
    for idx, block in crypto_blocks:
        refs = block.get("X", [])
        names = [vm.strings[r] for r in refs if r < len(vm.strings)][:8]
        w(f"  B[{idx}] p={block.get('p')} |H|={len(block.get('H', []))} X={names}")
    w("")
    w(f"--- bytecode refs to B[{args.block}]: {len(call_sites)} ---")
    for pos in call_sites[:20]:
        ctx = dis.q[max(0, pos - 8) : pos + 10]
        w(f"  @{pos:6d}: {ctx.hex()}")
    w("")

    entries = candidate_entries(call_sites, dis.q)
    best_entry: tuple[int, int, str] | None = None
    best_score = -1
    best_res: DisasmResult | None = None

    w("--- disassembly from candidate entries ---")
    for z, seg, note in entries:
        res = dis.disasm(z, seg, limit=500)
        crypto_score = sum(1 for ins in res.lines if ins.op in CRYPTO_OPS)
        if crypto_score > best_score:
            best_score = crypto_score
            best_entry = (z, seg, note)
            best_res = res
        if crypto_score >= 6:
            w(f"\n>> entry Z={z} seg={seg} ({note}) crypto_ops={crypto_score}")
            for ins in res.lines[:80]:
                w(f"   @{ins.pc:6d} seg{ins.seg} op{ins.op:3d}  {ins.text}")

    if best_res and best_entry:
        w("")
        w(f"best entry: Z={best_entry[0]} seg={best_entry[1]} ({best_entry[2]}) score={best_score}")
        pool_by_idx = {idx: val for _, idx, val in best_res.pool_loads}
        w("pool loads:")
        for idx in sorted(pool_by_idx):
            w(f"  bK[{idx:2d}] = 0x{pool_by_idx[idx]:08x}")
        rot_amounts = sorted({amt for _, _, amt in best_res.rotations if amt < 32})
        w(f"rotation operands: {rot_amounts}")

    mod = init.get("ck", {}).get(args.module, {})
    if mod:
        body = zlib.decompress(base64.b64decode(mod["c"]))
        key = shift_seed(bytes.fromhex(mod["d"]))
        target_ks = cfb_keystream_prefix(body[4:], LJ_HEADER)
        w("")
        w(f"--- f5 anchor ---")
        w(f"  key: {key.hex()}")
        w(f"  target ks[:10]: {target_ks[:10].hex()}")

    w("")
    w("--- next steps ---")
    w("  1. Run scripts/extract_d_new_kernel.js to capture 16-word ChaCha state at runtime")
    w("  2. Map bK pool indices from disassembly to D_PARAMS.constants")
    w("  3. Derive quarter-round schedule from op186 rotation sequence in cipher body")

    out_text = "\n".join(lines) + "\n"
    args.out.write_text(out_text)
    print(out_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
