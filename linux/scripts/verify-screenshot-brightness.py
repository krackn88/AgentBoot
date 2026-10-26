#!/usr/bin/env python3
"""Verify Runner PNG is not a black frame (avg brightness > 40, <95% near-black)."""
from __future__ import annotations

import sys

try:
    from PIL import Image
except ImportError:
    print("PIL missing: pip install pillow", file=sys.stderr)
    sys.exit(2)


def analyze(path: str) -> tuple[float, float, int, int, int]:
    img = Image.open(path).convert("RGB")
    w, h = img.size
    pixels = list(img.getdata())
    total = w * h
    if total == 0:
        return 0.0, 100.0, 0, w, h
    sum_lum = 0
    near_black = 0
    bright = 0
    for r, g, b in pixels:
        lum = (r * 299 + g * 587 + b * 114) // 1000
        sum_lum += lum
        if lum < 12:
            near_black += 1
        if lum > 80:
            bright += 1
    avg = sum_lum / total
    black_pct = 100.0 * near_black / total
    return avg, black_pct, bright, w, h


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: verify-screenshot-brightness.py <png> [min_avg] [max_black_pct]", file=sys.stderr)
        return 2
    path = sys.argv[1]
    min_avg = float(sys.argv[2]) if len(sys.argv) > 2 else 40.0
    max_black = float(sys.argv[3]) if len(sys.argv) > 3 else 95.0
    avg, black_pct, bright, w, h = analyze(path)
    ok = black_pct < max_black and (avg > min_avg or bright > 500)
    print(f"{path}: {w}x{h} avg_brightness={avg:.2f} black_pct={black_pct:.2f} bright_pixels={bright} pass={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
