"""Parse APIGuard init kernel (current IIFE format with B/bA/bC/bK/n/h)."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class KernelVm:
    kernel: str
    strings: list[str]
    blocks: list[dict[str, Any]]
    bytecode: bytes
    segment_table: list[list[tuple[int, int]]]
    handlers: list[str]
    pool: list[float | int]
    dispatch_fn: str = "F"
    blocks_name: str = "B"
    strings_name: str = "n"
    bytecode_name: str = "h"
    pool_name: str = "bK"


def _bracket_slice(text: str, open_idx: int) -> str:
    depth = 0
    for i in range(open_idx, len(text)):
        c = text[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return text[open_idx : i + 1]
    raise ValueError("unclosed bracket")


def _extract_js_string(text: str, marker: str) -> str:
    start = text.find(marker)
    if start < 0:
        raise ValueError(f"marker not found: {marker}")
    start += len(marker)
    out: list[str] = []
    esc = False
    i = start
    while i < len(text):
        c = text[i]
        if esc:
            out.append(c)
            esc = False
        elif c == "\\":
            esc = True
        elif c == '"':
            break
        else:
            out.append(c)
        i += 1
    return "".join(out)


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
        for val in (o, l, p, i):
            if val < 0:
                val = 0
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


def _decode_strings(chunk: str) -> list[str]:
    raw = re.findall(r'"((?:\\.|[^"\\])*)"', chunk)

    def dec(s: str) -> str:
        return re.sub(
            r"\\x([0-9a-fA-F]{2})",
            lambda m: chr(int(m.group(1), 16)),
            s,
        )

    return [dec(s) for s in raw]


def _parse_object_array(arr_text: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    i = 1
    while i < len(arr_text) - 1:
        if arr_text[i] in " \n\r\t,":
            i += 1
            continue
        if arr_text[i] != "{":
            break
        depth = 0
        j = i
        while j < len(arr_text):
            if arr_text[j] == "{":
                depth += 1
            elif arr_text[j] == "}":
                depth -= 1
                if depth == 0:
                    body = arr_text[i + 1 : j]
                    entry: dict[str, Any] = {}
                    for key in ("p", "H", "X", "S", "G"):
                        km = re.search(rf"{key}:(\[([^\]]*)\]|(\d+))", body)
                        if km:
                            if km.group(2) is not None:
                                entry[key] = [
                                    int(x) for x in km.group(2).split(",") if x
                                ]
                            else:
                                entry[key] = int(km.group(3))
                    blocks.append(entry)
                    i = j + 1
                    break
            j += 1
        else:
            break
    return blocks


def _parse_handlers(arr_text: str) -> list[str]:
    bodies: list[str] = []
    for m in re.finditer(r"function\s*\([^)]*\)\s*\{", arr_text):
        start = m.end()
        depth = 1
        j = start
        while j < len(arr_text) and depth:
            if arr_text[j] == "{":
                depth += 1
            elif arr_text[j] == "}":
                depth -= 1
            j += 1
        bodies.append(arr_text[start : j - 1])
    return bodies


def _handler_operand_inc(body: str) -> int:
    m = re.search(r"(\w+)\.(\w+)\+=\s*(\d+)", body)
    return int(m.group(3)) if m else 0


def parse_kernel(kernel: str) -> KernelVm:
    """Parse a current-format APIGuard kernel into VM structures."""
    if 'function F(b,K,g,W)' not in kernel and "var B=[" not in kernel:
        raise ValueError("kernel is not the current B/bA/bC format")

    ni = kernel.find("var n=")
    if ni < 0:
        raise ValueError("string table var n= not found")
    str_arr = _bracket_slice(kernel, kernel.index("[", ni))
    strings = _decode_strings(str_arr)

    bi = kernel.find("var B=")
    block_arr = _bracket_slice(kernel, kernel.index("[", bi))
    blocks = _parse_object_array(block_arr)

    b64 = _extract_js_string(kernel, 'bj("')
    bytecode = ge_decode(b64)

    ci = kernel.find("var bC=")
    seg_arr = _bracket_slice(kernel, kernel.index("[", ci))
    seg_raw = ast.literal_eval(seg_arr)
    segment_table = [[(ns, op) for ns, op in seg] for seg in seg_raw]

    ai = kernel.find("var bA=")
    handler_arr = _bracket_slice(kernel, kernel.index("[", ai))
    handlers = _parse_handlers(handler_arr)

    pi = kernel.find("4294967296")
    pv = kernel.rfind("var ", 0, pi)
    pool_arr = _bracket_slice(kernel, kernel.index("[", pv))
    pool = ast.literal_eval(pool_arr)

    return KernelVm(
        kernel=kernel,
        strings=strings,
        blocks=blocks,
        bytecode=bytecode,
        segment_table=segment_table,
        handlers=handlers,
        pool=pool,
    )


def load_kernel_vm(init_path: str | Path) -> KernelVm:
    init = json.loads(Path(init_path).read_text())
    kernel = init.get("kernel", "")
    if not kernel:
        raise ValueError("init JSON missing kernel")
    return parse_kernel(kernel)


def find_crypto_blocks(vm: KernelVm) -> list[tuple[int, dict[str, Any]]]:
    """Return B indices whose string refs include fromCharCode (D-cipher family)."""
    fc = vm.strings.index("fromCharCode") if "fromCharCode" in vm.strings else -1
    cc = vm.strings.index("charCodeAt") if "charCodeAt" in vm.strings else -1
    hits: list[tuple[int, dict[str, Any]]] = []
    for i, block in enumerate(vm.blocks):
        refs = block.get("X", [])
        names = {vm.strings[r] for r in refs if r < len(vm.strings)}
        if fc in refs or cc in refs or "fromCharCode" in names or "Uint32Array" in names:
            if "fromCharCode" in names or fc in refs:
                hits.append((i, block))
    return hits


def handler_operand_increments(vm: KernelVm) -> dict[int, int]:
    return {i: _handler_operand_inc(body) for i, body in enumerate(vm.handlers)}
