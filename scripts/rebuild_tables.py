#!/usr/bin/env python3
"""Rebuild real tables from the column-aligned APEA manual extracts.

The manual .md files keep the PDF's column geometry as runs of spaces. The old
extractor collapsed every run of whitespace, which welded adjacent columns into
single clinically-wrong sentences (e.g. "NEVER give; risks always outweigh ONLY
if benefits outweigh risks..."). This pass detects column blocks by their
offsets and slices each row back into cells.

Writes public/data/manual-tables.json.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "public/data"
MANUALS = DATA / "manuals"
OUT = DATA / "manual-tables.json"

GUIDE = json.loads((DATA / "guide.json").read_text())

NOISE = re.compile(
    r"^(?:NOTES|CONTENT OVERVIEW|©|CHAPTER \d+$|FNP/AGPCNP Review|\d+\s*$|QUESTION\s*#\s*\d+)",
    re.I,
)


def column_starts(line: str) -> list[int]:
    """Indexes where a new column begins: after a run of >=2 spaces."""
    starts = [0]
    for m in re.finditer(r" {2,}", line):
        nxt = m.end()
        if nxt < len(line) and line[nxt] != " ":
            starts.append(nxt)
    return starts


def is_header_candidate(line: str) -> bool:
    if len(line.strip()) < 12:
        return False
    starts = align_starts(slice_row(line, column_starts(line)), column_starts(line))
    if len(starts) < 2:
        return False
    words = line.split()
    if len(words) < 3 or len(words) > 22:
        return False
    caps = sum(1 for w in words if w[:1].isupper())
    return caps / len(words) >= 0.55


def slice_row(line: str, starts: list[int]) -> list[str]:
    cells = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(line)
        cells.append(re.sub(r"\s+", " ", line[s:e]).strip())
    return cells


def align_starts(header: list[str], starts: list[int]) -> list[int]:
    """Drop a leading empty cell created by block indentation."""
    if starts and not header[0]:
        return starts[1:]
    return starts


def norm_cols(headers: list[str], rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    """Remove wholly-empty columns and pad rows to header width."""
    width = len(headers)
    keep = [i for i in range(width) if headers[i] or any(r[i] for r in rows)]
    h = [headers[i] for i in keep]
    r = [[row[i] if i < len(row) else "" for i in keep] for row in rows]
    return h, r


def collect_block(lines: list[str], start: int):
    starts = align_starts(slice_row(lines[start], column_starts(lines[start])), column_starts(lines[start]))
    headers = slice_row(lines[start], starts)
    rows = []
    i = start + 1
    blanks = 0
    while i < len(lines):
        raw = lines[i]
        if not raw.strip():
            blanks += 1
            if blanks >= 2:
                break
            i += 1
            continue
        blanks = 0
        if NOISE.match(raw.strip()):
            i += 1
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent > starts[0] + 2:
            break
        # skip lines that are a wrapped continuation of a title/caption, not a row
        if len(starts) >= 2 and len(raw.strip()) < 8:
            i += 1
            continue
        if len(raw.strip()) > 150 and len(column_starts(raw)) < len(starts):
            break
        cells = slice_row(raw, starts)
        if not any(cells):
            break
        if all(len(c) > 90 for c in cells if c):
            break
        # A cell that ends with a question is the next slide's prompt bleeding in.
        if any(re.search(r"\?\s*$", c) for c in cells if c):
            i += 1
            continue
        # A row that is only a footnote/caption (one populated cell, starts with a
        # label colon) belongs to the slide, not the table body.
        populated = [c for c in cells if c]
        if len(populated) == 1 and re.match(r"^[A-Za-z ]{1,24}:$", populated[0]):
            break
        # A header-less all-caps sub-row continues the caption, not the table.
        if populated and all(re.match(r"^[A-Z][A-Za-z ]{1,24}:$", c) for c in populated):
            break
        # Stop once rows turn into running prose (wrapped columns).
        if len(rows) >= 2 and sum(1 for c in cells if len(c) > 55) >= 2:
            break
        rows.append(cells)
        i += 1
        if len(rows) >= 40:
            break
    h, r = norm_cols(headers, rows)
    return h, r, i


def confidence(headers, rows) -> float:
    if not rows:
        return 0.0
    filled = sum(1 for r in rows if sum(1 for c in r if c) >= max(2, len(headers) - 1))
    cells = [c for r in rows for c in r if c]
    density = len(cells) / max(1, len(rows) * len(headers))
    return round(min(1.0, 0.45 * (filled / len(rows)) + 0.55 * min(1.0, density * 1.6)), 2)


SENTENCE_TAIL = re.compile(r"\b(?:of|to|the|a|an|and|or|in|is|are|for|with|from|by|at|on)$", re.I)
LOWER_WORD = re.compile(r"^[a-z][a-z\-]{1,}$")
DISCRETE_VALUE = re.compile(r"[\d<>≥≤%±°]|^[A-Z]|^[•\-–]|\(|\)|/", )


def looks_like_wrapped_sentence(headers: list[str], rows: list[list[str]]) -> bool:
    """Reject blocks that are really one sentence chopped by wide word gaps.

    Example: a slide line "Asthma diagnosis support or PEF?" spaced out far
    enough to look like 3 columns, yielding header cells
    ['Symptoms','HPI & PE','Is spirometry'] and rows of lowercase continuations.
    """
    hdr = [h for h in headers if h]
    if not hdr:
        return True

    # header cells that are sentence fragments rather than labels
    frag_headers = sum(1 for h in hdr if SENTENCE_TAIL.search(h) or LOWER_WORD.match(h))
    if frag_headers >= max(1, len(hdr) // 2):
        return True

    # data rows made mostly of lowercase bare words = wrapped prose
    bare = total = 0
    for r in rows:
        for c in r:
            if not c:
                continue
            total += 1
            if LOWER_WORD.match(c) and not DISCRETE_VALUE.search(c):
                bare += 1
    if total and bare / total > 0.5:
        return True

    # a "table" whose every row has only one populated cell is a text block
    single = sum(1 for r in rows if sum(1 for c in r if c) <= 1)
    if single / len(rows) > 0.6:
        return True

    # Cells that begin mid-word ("ble", "als") mean a wrapped line, not a column.
    truncated = sum(1 for r in rows for c in r if c and LOWER_WORD.match(c) and len(c) <= 6)
    if total and truncated / total > 0.15:
        return True

    # Header cells that are questions, or that continue a sentence, are fragments.
    if any(h.strip().endswith("?") for h in hdr):
        return True
    if any(SENTENCE_TAIL.search(h) for h in hdr):
        return True
    # A header cell that is only a determiner/auxiliary verb ("Is spirometry")
    # is the tail of a wrapped question line.
    if any(re.match(r"^(is|are|was|were|does|do|can|should|will|has|have)\b", h, re.I) for h in hdr):
        return True
    return False


def chapter_for_file(path: Path):
    m = re.match(r"(\d+)-", path.name)
    if not m:
        return None
    manual_num = int(m.group(1))
    for ch in GUIDE["chapters"]:
        if ch["number"] == manual_num - 1:
            return ch
    return None


def main() -> int:
    out = {}
    total = 0
    for path in sorted(MANUALS.glob("*.md")):
        ch = chapter_for_file(path)
        if not ch:
            continue
        lines = path.read_text().splitlines()
        found = []
        section = ch.get("shortTitle") or ch["title"]
        i = 0
        while i < len(lines):
            raw = lines[i]
            if not raw.strip() or NOISE.match(raw.strip()):
                i += 1
                continue
            if is_header_candidate(raw):
                headers, rows, nxt = collect_block(lines, i)
                conf = confidence(headers, rows)
                if len(rows) >= 2 and conf >= 0.6 and not looks_like_wrapped_sentence(headers, rows):
                    found.append({
                        "section": section,
                        "title": " / ".join(h for h in headers if h)[:120],
                        "headers": [h or f"Col {j + 1}" for j, h in enumerate(headers)],
                        "rows": rows,
                        "confidence": conf,
                    })
                    i = nxt
                    continue
            i += 1
        if found:
            out[ch["id"]] = found
            total += len(found)

    OUT.write_text(json.dumps(out, indent=1))
    print(f"manual-tables.json: {total} tables across {len(out)} chapters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
