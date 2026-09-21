"""ChaCha-CFB cipher variants used by APIGuard (-e, tag, -g)."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Sequence


def _rotl(x: int, n: int) -> int:
    x &= 0xFFFFFFFF
    return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF


def _read_u32le(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


@dataclass(frozen=True)
class CipherParams:
    constants: dict[int, int]
    key_layout: Sequence[tuple[int, int]]
    rotations: tuple[int, int, int, int]
    double_rounds: int
    schedule: Sequence[tuple[int, int, int, int]]
    counter_index: int
    counter_add: int


def _init_state(key: bytes, params: CipherParams) -> list[int]:
    state = [0] * 16
    for idx, val in params.constants.items():
        state[idx] = val & 0xFFFFFFFF
    for idx, off in params.key_layout:
        state[idx] = _read_u32le(key, off)
    return state


def _quarter_round(
    x: list[int],
    a: int,
    b: int,
    c: int,
    d: int,
    rotations: tuple[int, int, int, int],
) -> None:
    r0, r1, r2, r3 = rotations
    x[a] = (x[a] + x[b]) & 0xFFFFFFFF
    x[d] = _rotl(x[d] ^ x[a], r0)
    x[c] = (x[c] + x[d]) & 0xFFFFFFFF
    x[b] = _rotl(x[b] ^ x[c], r1)
    x[a] = (x[a] + x[b]) & 0xFFFFFFFF
    x[d] = _rotl(x[d] ^ x[a], r2)
    x[c] = (x[c] + x[d]) & 0xFFFFFFFF
    x[b] = _rotl(x[b] ^ x[c], r3)


def _block(state: list[int], params: CipherParams) -> bytes:
    x = state.copy()
    for _ in range(params.double_rounds):
        for a, b, c, d in params.schedule:
            _quarter_round(x, a, b, c, d, params.rotations)
    ks = bytearray(64)
    for i in range(16):
        w = (x[i] + state[i]) & 0xFFFFFFFF
        ks[i * 4 : i * 4 + 4] = struct.pack("<I", w)
    return bytes(ks)


def _cfb(data: bytes, key: bytes, params: CipherParams, decrypting: bool) -> bytes:
    state = _init_state(key, params)
    out = bytearray(len(data))
    for off in range(0, len(data), 64):
        ks = _block(state, params)
        n = min(64, len(data) - off)
        for i in range(n):
            g = off + i
            v = data[g] ^ ks[i]
            if g > 0:
                v ^= out[g - 1] if decrypting else data[g - 1]
            out[g] = v & 0xFF
        state[params.counter_index] = (
            state[params.counter_index] + params.counter_add
        ) & 0xFFFFFFFF
    return bytes(out)


def encrypt(data: bytes, key: bytes, params: CipherParams) -> bytes:
    return _cfb(data, key, params, False)


def decrypt(data: bytes, key: bytes, params: CipherParams) -> bytes:
    return _cfb(data, key, params, True)


E_PARAMS = CipherParams(
    constants={
        0: 0x2EFB4565,
        1: 0x4CDA8C75,
        2: 0xBC0768D6,
        3: 0xF052C889,
        4: 0x2B2F51A2,
        9: 0x8627E318,
        11: 0xAE7324E8,
        13: 0x34C382CC,
    },
    key_layout=((5, 12), (6, 16), (7, 0), (8, 24), (10, 20), (12, 8), (14, 28), (15, 4)),
    rotations=(18, 13, 11, 4),
    double_rounds=11,
    schedule=(
        (3, 1, 0, 2),
        (4, 5, 7, 6),
        (10, 11, 9, 8),
        (12, 15, 14, 13),
        (0, 7, 11, 12),
        (2, 6, 10, 14),
        (3, 5, 9, 13),
        (1, 4, 8, 15),
    ),
    counter_index=15,
    counter_add=68,
)

TAG_PARAMS = CipherParams(
    constants={
        2: 0x9C4244A2,
        3: 0x14279E1A,
        6: 0x04AD9CD8,
        7: 0xDA87DFC0,
        8: 0xA9AE6A6D,
        13: 0x41286005,
        14: 0x2E1F1E12,
        15: 0x0854AA1C,
    },
    key_layout=((0, 8), (1, 28), (4, 0), (5, 12), (9, 24), (10, 16), (11, 4), (12, 20)),
    rotations=(19, 14, 3, 10),
    double_rounds=9,
    schedule=(
        (7, 6, 4, 5),
        (1, 0, 3, 2),
        (9, 8, 10, 11),
        (12, 15, 14, 13),
        (2, 7, 10, 12),
        (0, 6, 9, 13),
        (1, 4, 8, 15),
        (3, 5, 11, 14),
    ),
    counter_index=9,
    counter_add=0x3A,
)

G_PARAMS = CipherParams(
    constants={
        1: 0x11684EA6,
        2: 0x48BA7FCB,
        3: 0xCE327325,
        4: 0xF57EB8E5,
        8: 0x29DD5414,
        13: 0xE8C0DE57,
        14: 0xD929F6B7,
        15: 0xECA1E163,
    },
    key_layout=((10, 0), (9, 4), (0, 8), (5, 12), (11, 16), (12, 20), (6, 24), (7, 28)),
    rotations=(17, 18, 13, 6),
    double_rounds=10,
    schedule=(
        (1, 0, 2, 3),
        (6, 5, 7, 4),
        (11, 9, 8, 10),
        (14, 12, 13, 15),
        (1, 6, 11, 14),
        (0, 5, 9, 12),
        (2, 7, 8, 13),
        (3, 4, 10, 15),
    ),
    counter_index=5,
    counter_add=41,
)
