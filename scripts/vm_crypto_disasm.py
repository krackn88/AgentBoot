#!/usr/bin/env python3
"""Disassemble APIGuard kernel VM crypto function GI[127] (D-variant cipher)."""

from __future__ import annotations

import json
import re
from pathlib import Path

PREFIX = b"\x10SP\x83"
VM_CRYPTO_FN_INDEX = 127
VM_CRYPTO_OFFSET = 45305


def load_kernel(init_path: Path) -> str:
    return json.loads(init_path.read_text()).get("kernel", "")


def extract_string_table(kernel: str) -> list[str]:
    start = kernel.find("var C=[")
    end = kernel.find("];var", start)
    chunk = kernel[start + 7 : end]
    raw = re.findall(r'"((?:\\.|[^"\\])*)"', chunk)

    def dec(s: str) -> str:
        return re.sub(
            r"\\x([0-9a-fA-F]{2})",
            lambda m: chr(int(m.group(1), 16)),
            s,
        )

    return [dec(s) for s in raw]


def extract_gi_blocks(kernel: str) -> list[dict]:
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


def main() -> int:
    init_path = Path("/tmp/init.json")
    kernel = load_kernel(init_path)
    strings = extract_string_table(kernel)
    blocks = extract_gi_blocks(kernel)
    crypto = blocks[VM_CRYPTO_FN_INDEX]

    print("=== APIGuard D-cipher VM function ===")
    print(f"kernel bytes: {len(kernel)}")
    print(f"GI index: {VM_CRYPTO_FN_INDEX}")
    print(f"file offset: {crypto['offset']} (expected ~{VM_CRYPTO_OFFSET})")
    print(f"jump targets H: {crypto['H']}")
    print(f"locals |L|={len(crypto['L'])}")
    print(f"constants |V|={len(crypto['V'])}")

    print("\n=== string constants referenced by crypto fn ===")
    for idx in crypto["V"]:
        if idx < len(strings):
            val = strings[idx]
            if len(val) <= 72:
                print(f"  [{idx:3}] {val!r}")
            else:
                print(f"  [{idx:3}] len={len(val)} head={val[:48]!r}")

    print("\n=== ck format reminder ===")
    print(f"  zlib(base64(c)) -> {PREFIX!r} + ciphertext[4:]")
    print("  key = shift_seed(bytes.fromhex(d))")
    print("  plaintext = LuaJIT bytecode \\x1bLJ…")
    print("  f5 target keystream[:10] = 51859262afb3edb6b357")
    print("  E/G/TAG mutations + kernel pool windows: no match (score < 6)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
