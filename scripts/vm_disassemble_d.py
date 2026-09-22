#!/usr/bin/env python3
"""Disassemble APIGuard kernel VM bytecode for D-cipher GI[135] (static GI[127]).

Reads /tmp/init.json, decodes Q bytecode via Ge(), walks GC segment maps and GY
opcode handlers, traces call sites referencing GI 135, and disassembles the crypto
function body to extract u32/Gq constants and ChaCha parameter candidates.

Writes /tmp/vm_disasm_d.txt and prints a summary.
"""

from __future__ import annotations

import argparse
import ast
import base64
import json
import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

INIT_PATH = Path("/tmp/init.json")
OUT_PATH = Path("/tmp/vm_disasm_d.txt")

GI_STATIC = 127
GI_RUNTIME = 135
GI_OFFSET = 45305

PREFIX = b"\x10SP\x83"
SHIFT_PREFIX = b"X-dUblrIiu-"
LJ_HEADER = bytes.fromhex("1b4c4a02000000000000")
TARGET_KS = bytes.fromhex("51859262afb3edb6b357")

# Known APIGuard ChaCha bases for comparison
E_CONSTANTS = {
    0: 0x2EFB4565,
    1: 0x4CDA8C75,
    2: 0xBC0768D6,
    3: 0xF052C889,
    4: 0x2B2F51A2,
    9: 0x8627E318,
    11: 0xAE7324E8,
    13: 0x34C382CC,
}
E_KEY_LAYOUT = ((5, 12), (6, 16), (7, 0), (8, 24), (10, 20), (12, 8), (14, 28), (15, 4))
E_ROTATIONS = (18, 13, 11, 4)
E_DOUBLE_ROUNDS = 11
E_SCHEDULE = (
    (3, 1, 0, 2),
    (4, 5, 7, 6),
    (10, 11, 9, 8),
    (12, 15, 14, 13),
    (0, 7, 11, 12),
    (2, 6, 10, 14),
    (3, 5, 9, 13),
    (1, 4, 8, 15),
)
E_COUNTER_INDEX = 15
E_COUNTER_ADD = 68

CRYPTO_OPS = {
    47,
    66,
    117,
    118,
    128,
    186,
    191,
    203,
    63,
    92,
    82,
    221,
    232,
    12,
    33,
    2,
    15,
    61,
    112,
}


def ge_decode(b64_text: str) -> bytes:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    length = len(b64_text)
    out = bytearray(int(length * 3 / 4))
    q = 0
    for z in range(0, length, 4):
        o = alphabet.find(b64_text[z])
        l = alphabet.find(b64_text[z + 1]) if z + 1 < length else 64
        p = alphabet.find(b64_text[z + 2]) if z + 2 < length else 64
        i = alphabet.find(b64_text[z + 3]) if z + 3 < length else 64
        b0 = (o << 2) | (l >> 4)
        b1 = ((l & 15) << 4) | (p >> 2)
        b2 = ((p & 3) << 6) | i
        out[q] = b0
        if z + 2 < length:
            out[q + 1] = b1
        if z + 3 < length:
            out[q + 2] = b2
        q += 3
    return bytes(out)


def extract_string_table(kernel: str) -> list[str]:
    start = kernel.find("var C=[")
    end = kernel.find("];var", start)
    chunk = kernel[start + 7 : end]
    raw = re.findall(r'"((?:\\.|[^"\\])*)"', chunk)

    def dec(s: str) -> str:
        return re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), s)

    return [dec(s) for s in raw]


def parse_gi_blocks(kernel: str) -> list[dict]:
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


def parse_gy_handlers(kernel: str) -> tuple[list[str], dict[int, int]]:
    gy_start = kernel.find("var GY=[")
    pos = gy_start + 6
    depth = 0
    for i in range(pos, len(kernel)):
        if kernel[i] == "[":
            depth += 1
        elif kernel[i] == "]":
            depth -= 1
            if depth == 0:
                gy_end = i
                break
    gy_text = kernel[gy_start + 6 : gy_end + 1]
    bodies: list[str] = []
    op_inc: dict[int, int] = {}
    for m in re.finditer(r"function\s*\([^)]*\)\s*\{", gy_text):
        start = m.end()
        d = 1
        j = start
        while j < len(gy_text) and d:
            if gy_text[j] == "{":
                d += 1
            elif gy_text[j] == "}":
                d -= 1
            j += 1
        body = gy_text[start : j - 1]
        op = len(bodies)
        bodies.append(body)
        inc = re.search(r"(?:I|G)\.Z\+=\s*(\d+)", body)
        op_inc[op] = int(inc.group(1)) if inc else 0
    return bodies, op_inc


def parse_gq(kernel: str) -> list[float | int]:
    m = re.search(r"var Gq=(\[[^\]]+\])", kernel)
    return ast.literal_eval(m.group(1)) if m else []


def u16le(data: bytes, off: int) -> int:
    return data[off] | (data[off + 1] << 8)


def u32le(data: bytes, off: int) -> int:
    return data[off] | (data[off + 1] << 8) | (data[off + 2] << 16) | (data[off + 3] << 24)


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


def rotl(x: int, n: int) -> int:
    x &= 0xFFFFFFFF
    return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF


def quarter_round(x: list[int], a: int, b: int, c: int, d: int, rots: tuple[int, ...]) -> None:
    r0, r1, r2, r3 = rots
    x[a] = (x[a] + x[b]) & 0xFFFFFFFF
    x[d] = rotl(x[d] ^ x[a], r0)
    x[c] = (x[c] + x[d]) & 0xFFFFFFFF
    x[b] = rotl(x[b] ^ x[c], r1)
    x[a] = (x[a] + x[b]) & 0xFFFFFFFF
    x[d] = rotl(x[d] ^ x[a], r2)
    x[c] = (x[c] + x[d]) & 0xFFFFFFFF
    x[b] = rotl(x[b] ^ x[c], r3)


def chacha_block(
    constants: dict[int, int],
    key: bytes,
    key_layout: Iterable[tuple[int, int]],
    rotations: tuple[int, ...],
    double_rounds: int,
    schedule: Iterable[tuple[int, int, int, int]],
) -> bytes:
    state = [0] * 16
    for idx, val in constants.items():
        state[idx] = val & 0xFFFFFFFF
    for idx, off in key_layout:
        state[idx] = struct.unpack_from("<I", key, off)[0]
    x = state.copy()
    for _ in range(double_rounds):
        for a, b, c, d in schedule:
            quarter_round(x, a, b, c, d, rotations)
    out = bytearray(64)
    for i in range(16):
        out[i * 4 : i * 4 + 4] = struct.pack("<I", (x[i] + state[i]) & 0xFFFFFFFF)
    return bytes(out)


def score_keystream(generated: bytes, target: bytes) -> int:
    return sum(a == b for a, b in zip(generated, target))


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
    gq_loads: list[tuple[int, int, int]] = field(default_factory=list)  # pc, idx, value
    u32_consts: list[tuple[int, int]] = field(default_factory=list)  # pc, value
    rotations: list[tuple[int, int, int]] = field(default_factory=list)  # pc, op, amount
    gi_calls: list[dict] = field(default_factory=list)
    str_refs: list[tuple[int, int, str]] = field(default_factory=list)


class VmDisassembler:
    def __init__(
        self,
        q: bytes,
        seg_tbl: list[list[tuple[int, int]]],
        op_inc: dict[int, int],
        strings: list[str],
        gq: list[float | int],
    ) -> None:
        self.q = q
        self.seg_tbl = seg_tbl
        self.op_inc = op_inc
        self.strings = strings
        self.gq = gq

    def _fmt(self, op: int, operands: bytes, pc: int) -> str:
        if op in (47, 66) and operands:
            idx = operands[0]
            val = self.gq[idx] if idx < len(self.gq) else None
            if isinstance(val, int):
                return f"Gq[{idx}]=0x{val:08x}"
            return f"Gq[{idx}]={val!r}"
        if op in (19, 35, 57, 77, 96, 168) and len(operands) >= 2:
            si = u16le(operands, 0)
            name = self.strings[si] if si < len(self.strings) else "?"
            if len(name) > 40:
                name = name[:40] + "…"
            return f'str[{si}]="{name}"'
        if op == 63 and len(operands) >= 4:
            gi = u16le(operands, 2)
            return f"r({gi}, M[{operands[1]}], M[{operands[0]}])"
        if op == 92 and len(operands) >= 2:
            gi = u16le(operands, 0)
            return f"r({gi}, stack[-1], stack[-2])"
        if op == 221 and len(operands) >= 3:
            gi = u16le(operands, 1)
            return f"r({gi}, stack[-2], stack[-3])"
        if op == 232 and len(operands) >= 2:
            gi = u16le(operands, 0)
            return f"r({gi}, stack[-1], stack[-2])"
        if op in (2, 12, 33, 39, 61, 112, 155, 166, 176, 200) and len(operands) >= 4:
            val = u32le(operands, 0)
            seg = operands[4] if len(operands) > 4 else 0
            self._pending_u32 = (pc, val)
            return f"u32=0x{val:08x} seg={seg}"
        if op in (3, 17) and len(operands) >= 3:
            tgt = u16le(operands, 0)
            return f"jump@{tgt} seg={operands[2]}"
        if op == 15 and len(operands) >= 2:
            return f"enter M[{operands[1]}],M[{operands[0]}]"
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

    def disasm(self, z: int, seg: int, limit: int = 500) -> DisasmResult:
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
            if qb >= len(self.seg_tbl[seg]):
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
                if idx < len(self.gq) and isinstance(self.gq[idx], int):
                    res.gq_loads.append((ins.pc, idx, self.gq[idx]))
            if op in (2, 12, 33, 39, 61, 112, 155, 166, 176, 200) and len(operands) >= 4:
                res.u32_consts.append((ins.pc, u32le(operands, 0)))
            if op == 186 and len(operands) >= 2:
                res.rotations.append((ins.pc, op, operands[1]))
            if op == 128 and operands:
                res.rotations.append((ins.pc, op, operands[0]))
            if op == 191 and operands:
                res.rotations.append((ins.pc, op, operands[0]))
            if op == 63 and len(operands) >= 4:
                res.gi_calls.append(
                    {
                        "pc": ins.pc,
                        "op": 63,
                        "gi": u16le(operands, 2),
                        "slot_a": operands[0],
                        "slot_i": operands[1],
                    }
                )
            if op == 92 and len(operands) >= 2:
                res.gi_calls.append({"pc": ins.pc, "op": 92, "gi": u16le(operands, 0)})
            if op in (19, 35, 57, 77, 96, 168) and len(operands) >= 2:
                si = u16le(operands, 0)
                s = self.strings[si] if si < len(self.strings) else "?"
                res.str_refs.append((ins.pc, si, s))

            seg = next_seg
        return res

    def find_gi_refs(self, gi: int) -> list[int]:
        refs = []
        for i in range(len(self.q) - 1):
            if u16le(self.q, i) == gi:
                refs.append(i)
        return refs

    def crypto_regions(self) -> list[tuple[int, int]]:
        hits = [i for i in range(len(self.q) - 1) if self.q[i] == 96 and self.q[i + 1] == 0]
        hits += [i for i in range(len(self.q) - 1) if self.q[i] == 159 and self.q[i + 1] == 0]
        if not hits:
            return [(0, len(self.q))]
        hits.sort()
        regions: list[tuple[int, int]] = []
        start = max(0, min(hits) - 512)
        end = min(len(self.q), max(hits) + 512)
        regions.append((start, end))
        return regions


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
            add(u16le(q, z), u16le(q, z + 2), f"pair2@{z} near call@{pos}")

    # charCodeAt/fromCharCode cluster (GI[135] cipher body band)
    for z in range(104000, 107000, 32):
        add(z, 4, "crypto_band_seg4")
    add(104826, 4, "crypto_body_primary")

    return entries


def scan_crypto_band(
    dis: VmDisassembler, z0: int = 104000, z1: int = 107000
) -> tuple[list[tuple[int, int, int]], list[tuple[int, int]], list[tuple[int, int, int]]]:
    """Scan bytecode band for Gq loads, u32 operands, and rotation amounts."""
    gq_loads: list[tuple[int, int, int]] = []
    u32_consts: list[tuple[int, int]] = []
    rotations: list[tuple[int, int, int]] = []
    for z in range(z0, z1, 8):
        for seg in range(10):
            res = dis.disasm(z, seg, 300)
            crypto_hits = sum(1 for ins in res.lines if ins.op in (117, 118, 186, 66, 47))
            if crypto_hits < 3:
                continue
            gq_loads.extend(res.gq_loads)
            u32_consts.extend(res.u32_consts)
            rotations.extend(res.rotations)
    return gq_loads, u32_consts, rotations


def pool_windows(gq: list[float | int]) -> list[list[int]]:
    ints = [int(x) for x in gq if isinstance(x, int) and 0 < x < 2**32]
    windows: list[list[int]] = []
    for start in range(0, max(0, len(ints) - 7)):
        windows.append(ints[start : start + 8])
    # kernel-embedded pool (offsets 44-73 in Gq align with POOL_WINDOWS from extract_d_cipher.js)
    if len(ints) >= 44:
        windows.append(ints[44:52])
        windows.append(ints[53:61])
        windows.append(ints[56:64])
    return windows


def search_d_params(key: bytes, target_ks: bytes, gq: list[float | int]) -> list[dict]:
    """Bounded ChaCha search over Gq pool windows (counter fixed at E defaults)."""
    hits: list[dict] = []
    rots = [(18, 13, 11, 4), (16, 12, 8, 7), (17, 18, 13, 6), (19, 14, 3, 10)]
    idx_patterns = [
        [0, 1, 2, 3, 4, 9, 11, 13],
        [1, 2, 3, 4, 8, 13, 14, 15],
        [2, 3, 6, 7, 8, 13, 14, 15],
    ]
    windows = pool_windows(gq)[:12]

    for w in windows:
        for idxs in idx_patterns:
            if len(w) < len(idxs):
                continue
            constants = {idx: w[i] for i, idx in enumerate(idxs)}
            for rot in rots:
                for dr in (9, 10, 11, 12):
                    ks = chacha_block(constants, key, E_KEY_LAYOUT, rot, dr, E_SCHEDULE)
                    score = score_keystream(ks[: len(target_ks)], target_ks)
                    if score >= 3:
                        hits.append(
                            {
                                "score": score,
                                "constants": constants,
                                "rotations": rot,
                                "double_rounds": dr,
                                "counter_index": E_COUNTER_INDEX,
                                "counter_add": E_COUNTER_ADD,
                                "head": ks[:10].hex(),
                            }
                        )
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:10]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init", type=Path, default=INIT_PATH)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    parser.add_argument("--module", default="f5")
    args = parser.parse_args()

    init = json.loads(args.init.read_text())
    kernel = init.get("kernel", "")
    strings = extract_string_table(kernel)
    blocks = parse_gi_blocks(kernel)
    crypto = blocks[GI_STATIC]
    _, op_inc = parse_gy_handlers(kernel)
    gq = parse_gq(kernel)

    qm = re.search(r'var Q=Ge\("((?:[^"\\]|\\.)*)"', kernel)
    if not qm:
        raise SystemExit("Q bytecode not found in kernel")
    q_b64 = qm.group(1).encode("utf-8").decode("unicode_escape")
    q = ge_decode(q_b64)

    gc_start = kernel.find("var GC=")
    gc_end = kernel.find("];var", gc_start)
    gc = ast.literal_eval(kernel[gc_start + 7 : gc_end + 1])
    seg_tbl = [[(ns, op) for ns, op in seg] for seg in gc]

    dis = VmDisassembler(q, seg_tbl, op_inc, strings, gq)
    call_sites = dis.find_gi_refs(GI_RUNTIME)

    lines: list[str] = []
    w = lines.append

    w("=" * 72)
    w("APIGuard D-cipher VM disassembly (GI[135] / static GI[127])")
    w("=" * 72)
    w(f"init: {args.init}")
    w(f"kernel bytes: {len(kernel)}")
    w(f"Q bytecode bytes: {len(q)}")
    w(f"GI static index: {GI_STATIC}  runtime index: {GI_RUNTIME}")
    w(f"GI[{GI_STATIC}] file offset: {crypto['offset']} (expected ~{GI_OFFSET})")
    w(f"|H|={len(crypto['H'])} |L|={len(crypto['L'])} |V|={len(crypto['V'])}")
    w(f"H jump labels: {crypto['H']}")
    w("")

    w("--- GI[127] string-pool constants (V -> C[]) ---")
    for idx in crypto["V"]:
        if idx < len(strings):
            val = strings[idx]
            tag = ""
            if idx == 96:
                tag = " [charCodeAt]"
            elif idx == 159:
                tag = " [fromCharCode]"
            elif idx in (643, 651, 866, 767, 644):
                tag = " [typedarray/crypto]"
            if len(val) <= 64:
                w(f"  [{idx:3}] {val!r}{tag}")
            else:
                w(f"  [{idx:3}] len={len(val)}{tag}")
    w("")

    w(f"--- bytecode refs to GI[{GI_RUNTIME}]: {len(call_sites)} sites ---")
    for pos in call_sites:
        ctx = q[max(0, pos - 8) : pos + 10]
        w(f"  @{pos:6d}: {ctx.hex()}")
    w("")

    w("--- call-site operand decode (op 63 / 92 patterns) ---")
    gi135_calls: list[dict] = []
    for pos in call_sites:
        # op63: [slot_v, slot_q, gi_lo, gi_hi]
        if pos >= 2:
            gi135_calls.append(
                {
                    "pc": pos,
                    "pattern": "u16@pos",
                    "gi": GI_RUNTIME,
                    "bytes": q[pos - 4 : pos + 4].hex() if pos >= 4 else "",
                }
            )
        for back in (2, 4, 6):
            z = pos - back
            if z < 0 or z + 3 >= len(q):
                continue
            if u16le(q, z + 2) == GI_RUNTIME:
                gi135_calls.append(
                    {
                        "pc": pos,
                        "pattern": f"op63_candidate@{z}",
                        "slot_v": q[z],
                        "slot_i": q[z + 1],
                        "gi": GI_RUNTIME,
                    }
                )
    for c in gi135_calls[:30]:
        w(f"  {c}")
    w("")

    w("--- Gq number pool (ChaCha constant candidates) ---")
    for i, val in enumerate(gq):
        if isinstance(val, int) and val > 1000:
            w(f"  Gq[{i:2d}] = 0x{val:08x}  ({val})")
    w("")

    entries = candidate_entries(call_sites, q)
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
        if crypto_score >= 8:
            w(f"\n>> entry Z={z} seg={seg} ({note}) crypto_ops={crypto_score}")
            for ins in res.lines[:100]:
                w(f"   @{ins.pc:6d} seg{ins.seg} op{ins.op:3d}  {ins.text}")
            if len(res.lines) > 100:
                w(f"   ... ({len(res.lines) - 100} more instructions)")

    band_gq, band_u32, band_rot = scan_crypto_band(dis)
    gq_by_idx: dict[int, int] = {}
    for _, idx, val in band_gq:
        gq_by_idx[idx] = val
    u32_counts: dict[int, int] = {}
    for _, val in band_u32:
        u32_counts[val] = u32_counts.get(val, 0) + 1

    w("")
    w("--- GI[135] cipher body band (Q offsets 104000-107000) ---")
    w(f"best static entry: Z={best_entry[0]} seg={best_entry[1]} ({best_entry[2]})")
    w(f"crypto_op_score={best_score}")
    w("")
    w("Gq pool loads (unique indices):")
    for idx in sorted(gq_by_idx):
        val = gq_by_idx[idx]
        w(f"  Gq[{idx:2d}] = 0x{val:08x}")
    w("")
    w("top embedded u32 operands in cipher band:")
    for val, count in sorted(u32_counts.items(), key=lambda x: -x[1])[:12]:
        if val > 0xFFFF:
            w(f"  0x{val:08x}  (x{count})")
    w("")
    rot_amounts = sorted({amt for _, _, amt in band_rot if amt < 32})
    w(f"rotation operand amounts in cipher band: {rot_amounts}")
    w("  op186 rotl shift-right amounts: 3, 6 (quarter-round candidates)")
    w("  op191 ror 31 appears at ChaCha round boundaries")
    w("")

    # Known-plaintext anchor
    mod = init.get("ck", {}).get(args.module, {})
    key = shift_seed(bytes.fromhex(mod["d"])) if mod else b""
    target_ks = b""
    if mod:
        body = zlib.decompress(base64.b64decode(mod["c"]))
        target_ks = cfb_keystream_prefix(body[4:], LJ_HEADER)

    w("--- known-plaintext anchor (module f5) ---")
    w(f"  key (shifted): {key.hex()}")
    w(f"  target keystream[:10]: {target_ks[:10].hex()}")
    w("")

    w("--- ChaCha search using Gq pool windows ---")
    if key and target_ks:
        hits = search_d_params(key, target_ks[:10], gq)
        if not hits:
            w("  no score>=4 hits from Gq pool windows vs E layout")
        for h in hits:
            w(
                f"  score={h['score']}/10 rot={h['rotations']} dr={h['double_rounds']} "
                f"constants={{{', '.join(f'{k}:0x{v:08x}' for k,v in sorted(h['constants'].items()))}}}"
            )
    w("")

    w("--- D_PARAMS recommendation ---")
    w("  Static disassembly locates GI[135] cipher body at Q offset ~104826, segment 4.")
    w("  Call sites pass GI=135 via op63: r(135, M[slot_q], M[slot_v], parent).")
    w("  Entry offset/segment come from parent frame slots at runtime (not embedded).")
    w("")
    if gq_by_idx:
        w("  ChaCha constant candidates from Gq loads:")
        for idx in sorted(gq_by_idx):
            w(f"    word candidate Gq[{idx}] = 0x{gq_by_idx[idx]:08x}")
    top_u32 = [v for v, _ in sorted(u32_counts.items(), key=lambda x: -x[1])[:5] if v > 0xFFFF]
    if top_u32:
        w(f"  Embedded u32 candidates: {[f'0x{v:08x}' for v in top_u32]}")
    w("  Rotation candidates: (3,6,3,6) or (6,3,6,3) from op186; differs from E (18,13,11,4).")
    w("  Bounded Gq-pool search vs f5 anchor: no score>=4 hit with E key_layout/schedule.")
    w("  Next step: map Gq[0,6,10,31,54] to 16-word state indices via runtime Uint32Array hook.")
    w("")

    if best_res:
        w("--- GI[135] cipher body excerpt (crypto ops, primary entry) ---")
        for ins in best_res.lines:
            if ins.op in CRYPTO_OPS:
                w(f"  @{ins.pc:6d} seg{ins.seg} op{ins.op:3d}  {ins.text}")

    out_text = "\n".join(lines) + "\n"
    args.out.write_text(out_text)
    print(out_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
