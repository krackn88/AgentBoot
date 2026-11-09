#!/usr/bin/env python3
"""Extract structured content directly from the APEA PDFs.

The markdown in public/data/manuals was produced by a PDF-to-text converter that
flattened the page into lines of spaces. That is why tables had to be guessed back
out of whitespace runs, and why 141 of 231 "pearls" were slide debris.

A PDF carries real geometry. PyMuPDF exposes every word with its bounding box, so
column boundaries, row bands and reading order are measured rather than inferred.

This script reads the PDFs (downloaded from the dedi) and emits, per chapter:

  public/data/pdf-extract/<chapterId>.json
    {
      pages: [{n, width, height}],
      blocks: [ {type: 'heading'|'para'|'list'|'table'|'question'|'tip',
                 text?, items?, headers?, rows?, page} ],
      tables: [ {headers, rows, page, columns} ],
      tips:   [ "..." ],           # TIP / PEARL lines, verbatim and whole
      questions: [ {stem, options, page} ],
      quality: {pages, tables, tips, questions, chars}
    }

Run:  python3 scripts/pdf_extract.py --src /tmp/pdfs --out public/data/pdf-extract
"""
import argparse
import json
import re
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "public/data"
GUIDE = json.loads((DATA / "guide.json").read_text())
MANIFEST = json.loads((DATA / "manuals.json").read_text())

FOOTER = re.compile(r"(?:\d+\s*)?FNP/AGPCNP Review$|©\s*\d{4}|Advanced Practice Education", re.I)
NOISE = re.compile(r"^(?:NOTES|CONTENT OVERVIEW|CHECK YOUR KNOWLEDGE|EXAM CHECKLIST)$", re.I)
BULLET_ONLY = re.compile(r"^[•✓\-]$")
QUESTION_START = re.compile(r"^QUESTION\s*#\s*(\d+)", re.I)
OPTION = re.compile(r"^(\d)\.\s+(.*)$")
TIP = re.compile(r"^(?:TIP|PEARL)\s*:\s*(.+)$", re.I)

# how close two x positions must be to count as the same column
COL_TOL = 14
# how close two baselines must be to count as the same row
ROW_TOL = 4


def chapter_for(pdf_name: str):
    m = re.match(r"(\d+)-", pdf_name)
    if not m:
        return None
    num = int(m.group(1))
    for ch in GUIDE["chapters"]:
        if ch["number"] == num - 1:
            return ch
    return None


def page_lines(page):
    """Words grouped into visual lines with their x/y spans, footer removed."""
    words = page.get_text("words")
    if not words:
        return []
    h = page.rect.height
    keep = [w for w in words if not FOOTER.search(w[4]) and w[1] < h - 30]
    keep.sort(key=lambda w: (round(w[1], 1), w[0]))
    lines = []
    for w in keep:
        x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
        if lines and abs(y0 - lines[-1]["y"]) <= ROW_TOL:
            lines[-1]["words"].append((x0, text))
            lines[-1]["x1"] = max(lines[-1]["x1"], x1)
            lines[-1]["y1"] = max(lines[-1]["y1"], y1)
        else:
            lines.append({"y": y0, "y1": y1, "x0": x0, "x1": x1, "words": [(x0, text)]})
    for ln in lines:
        ln["text"] = " ".join(t for _, t in sorted(ln["words"]))
        ln["x0"] = min(x for x, _ in ln["words"])
    return lines


def column_of(x, columns):
    for i, c in enumerate(columns):
        if x >= c - COL_TOL:
            return i
    return 0


def find_columns(lines):
    """Column starts from recurring x positions, validated by even spacing.

    A real slide table places its columns at regular intervals (the
    fluoroquinolone table sits at 127.6 / 277.5 / 427.5 - a 150pt pitch). Words
    inside a cell also repeat, but at irregular offsets, so requiring a consistent
    pitch separates the two far more reliably than raw frequency.
    """
    from collections import Counter
    counts = Counter()
    rows = max(1, len(lines))
    for ln in lines:
        for x, _ in ln["words"]:
            counts[round(x)] += 1

    # candidates: x values present on at least a third of the rows
    cands = sorted(x for x, n in counts.items() if n >= max(2, rows * 0.34))
    if len(cands) < 2:
        cands = sorted(x for x, n in counts.items() if n >= 2)
    if len(cands) < 2:
        return []

    # Try every plausible pitch and keep the longest evenly-spaced chain. Real
    # columns sit on a consistent pitch; cell text lands at arbitrary offsets.
    gaps = [b - a for a, b in zip(cands, cands[1:])]
    if not gaps:
        return []
    pitches = {g for g in gaps if g > 40}
    pitches |= {g * 2 for g in gaps if 20 < g <= 40}

    best = []
    for pitch in pitches:
        for start in cands:
            chain = [start]
            for x in cands:
                if x > chain[-1] and abs((x - chain[-1]) - pitch) <= COL_TOL * 1.8:
                    chain.append(x)
            if len(chain) > len(best) or (len(chain) == len(best) and chain and best and
                                          sum(1 for v in chain if counts.get(round(v), 0) >= 3) >
                                          sum(1 for v in best if counts.get(round(v), 0) >= 3)):
                best = chain
    return [float(x) for x in best]


def row_cells(ln, cols):
    cells = [""] * len(cols)
    for x, t in ln["words"]:
        ci = 0
        for k, c in enumerate(cols):
            if x >= c - COL_TOL:
                ci = k
        cells[ci] = (cells[ci] + " " + t).strip()
    return cells


def table_score(headers, body, cols):
    """Score how much a block looks like a real printed table (0-1)."""
    hdr = [h for h in headers if h and not h.startswith("Col ")]
    if len(hdr) < 2 or not body:
        return 0.0
    score = 0.0
    all_cells = [c for r in body for c in r if c]

    # 1. header quality: short labels, no sentences, no furniture
    good_hdr = 0
    for h in hdr:
        words = h.split()
        if len(h) <= 42 and len(words) <= 5 and not h.endswith(("?", ".", ":")):
            good_hdr += 1
    score += 0.30 * (good_hdr / len(hdr))

    # 2. rows must be mostly populated
    width = len(headers)
    filled = sum(1 for r in body if sum(1 for c in r if c) >= max(2, width - 1))
    score += 0.25 * (filled / len(body))

    # 3. cells are values, not paragraphs
    short = sum(1 for c in all_cells if len(c) <= 70)
    score += 0.20 * (short / max(1, len(all_cells)))

    # 4. column pitch is regular (real tables are laid out on a grid)
    if len(cols) >= 2:
        gaps = [b - a for a, b in zip(cols, cols[1:])]
        if gaps:
            mean = sum(gaps) / len(gaps)
            spread = max(abs(g - mean) for g in gaps) / mean if mean else 1
            score += 0.15 * max(0.0, 1 - spread)

    # 5. enough rows to be worth showing
    score += 0.10 * min(1.0, len(body) / 4)

    # hard rejects
    joined = " ".join(all_cells + hdr)
    if re.search(r"©|Advanced Practice Education|FNP/AGPCNP", joined):
        return 0.0
    if any(re.match(r"^\d\.\s", c) for c in all_cells):      # answer choices
        return 0.0
    if any(c.strip() in ("•", "-", "✓") for c in all_cells):     # bullet runs
        return 0.0
    if any("$" in c or "•" in c for c in all_cells):             # PDF bullet glyph
        return 0.0
    if any(re.search(r"\bQUESTION\b", c, re.I) for c in all_cells + hdr):
        return 0.0
    # running headers and chapter titles are furniture, not columns
    if any(re.search(r"Chapter \d|Sensitivity & Specificity|Pulmonary Disorders \|", h) for h in hdr):
        return 0.0
    if any(h.startswith("Col ") for h in headers) and len(hdr) < len(headers):
        score -= 0.15
    # a header cell holding a whole sentence (or a case vignette) is not a column
    if any(len(h.split()) > 7 for h in hdr):
        return 0.0
    if any(re.search(r"\b(reports|presents|diagnosed|patient with)\b", h, re.I) for h in hdr):
        return 0.0
    return round(max(0.0, score), 3)


def valid_table(headers, body, cols=None):
    return table_score(headers, body, cols or []) >= 0.55


def detect_table(lines, i):
    """Grow a table downward from its header row.

    Only lines that actually land in the established columns are absorbed, so a
    following prose paragraph cannot widen the window and destroy the pitch.
    """
    if i + 2 >= len(lines):
        return None

    # seed the window with the header plus the next few rows only
    seed = lines[i:i + 6]
    cols = find_columns(seed)
    if len(cols) < 2:
        seed = lines[i:i + 4]
        cols = find_columns(seed)
    if len(cols) < 2:
        return None

    rows = []
    used = 0
    for ln in lines[i:]:
        cells = row_cells(ln, cols)
        populated = [c for c in cells if c]
        if len(populated) < 2:
            break
        # every word must sit inside the column band, not off to the left
        if any(x < cols[0] - COL_TOL for x, _ in ln["words"]):
            break
        rows.append(cells)
        used += 1
        if used >= 24:
            break
    if used < 3:
        return None

    headers, body = rows[0], rows[1:]
    headers = [h or f"Col {k+1}" for k, h in enumerate(headers)]
    # keep only columns that carry data
    keep = [k for k in range(len(cols)) if headers[k].startswith("Col ") is False or any(r[k] for r in body)]
    headers = [headers[k] for k in keep]
    body = [[r[k] for k in keep] for r in body]
    if len(headers) < 2 or len(body) < 2:
        return None
    score = table_score(headers, body, [cols[k] for k in keep])
    if score < 0.55:
        return None
    return {"headers": headers, "rows": body, "columns": [cols[k] for k in keep]}, i + used


def extract_page(page, page_no):
    lines = page_lines(page)
    blocks = []
    tables = []
    tips = []
    questions = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        text = ln["text"].strip()
        if not text or NOISE.match(text):
            i += 1
            continue

        m = QUESTION_START.match(text)
        if m:
            stem_parts, opts = [], []
            j = i + 1
            while j < len(lines) and len(opts) < 6:
                t = lines[j]["text"].strip()
                if not t or NOISE.match(t):
                    break
                if QUESTION_START.match(t) or TIP.match(t):
                    break
                om = OPTION.match(t)
                if om:
                    opts.append(om.group(2).strip())
                elif opts:
                    # A wrapped continuation of the previous answer choice. Slide
                    # text following the last option runs into it, so only accept
                    # text that continues the sentence (no terminal punctuation).
                    if opts[-1].endswith((".", "?", "!")):
                        break
                    if len(opts[-1]) + len(t) < 150:
                        opts[-1] = (opts[-1] + " " + t).strip()
                    else:
                        break
                elif len(stem_parts) < 6:
                    stem_parts.append(t)
                else:
                    break
                j += 1
            stem = " ".join(stem_parts).strip()
            questions.append({"stem": stem, "options": opts, "page": page_no})
            blocks.append({"type": "question", "text": stem, "items": opts, "page": page_no})
            i = j
            continue

        tm = TIP.match(text)
        if tm:
            tips.append(tm.group(1).strip())
            blocks.append({"type": "tip", "text": tm.group(1).strip(), "page": page_no})
            i += 1
            continue

        table = detect_table(lines, i)
        if table:
            spec, nxt = table
            tables.append({**spec, "page": page_no})
            blocks.append({"type": "table", **spec, "page": page_no})
            i = nxt
            continue

        # bullets and short items become a list run
        if text.startswith(("•", "✓", "-")) or (len(text) < 70 and not text.endswith((".", "?", "!"))):
            items, j = [], i
            while j < len(lines) and len(items) < 20:
                t = lines[j]["text"].strip()
                if not t or NOISE.match(t):
                    break
                if len(t) > 70 and not t.startswith(("•", "✓")):
                    break
                items.append(re.sub(r"^[•✓\-]\s*", "", t))
                j += 1
            if len(items) >= 3:
                blocks.append({"type": "list", "items": items, "page": page_no})
                i = j
                continue

        blocks.append({"type": "para", "text": text, "page": page_no})
        i += 1
    return blocks, tables, tips, questions


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="/tmp/pdfs")
    ap.add_argument("--out", default=str(DATA / "pdf-extract"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(src.glob("*.pdf"))
    if args.limit:
        pdfs = pdfs[: args.limit]
    if not pdfs:
        print(f"no PDFs in {src}")
        return 1

    summary = []
    for pdf in pdfs:
        ch = chapter_for(pdf.name)
        if not ch:
            continue
        doc = pymupdf.open(pdf)
        all_blocks, all_tables, all_tips, all_questions = [], [], [], []
        pages = []
        for n in range(doc.page_count):
            page = doc[n]
            pages.append({"n": n, "width": round(page.rect.width, 1), "height": round(page.rect.height, 1)})
            b, t, tp, q = extract_page(page, n)
            all_blocks += b
            all_tables += t
            all_tips += tp
            all_questions += q
        payload = {
            "chapterId": ch["id"],
            "title": ch.get("shortTitle") or ch.get("title"),
            "pdf": pdf.name,
            "pages": pages,
            "blocks": all_blocks,
            "tables": all_tables,
            "tips": all_tips,
            "questions": all_questions,
            "quality": {
                "pages": len(pages),
                "tables": len(all_tables),
                "tips": len(all_tips),
                "questions": len(all_questions),
                "chars": sum(len(b.get("text", "")) for b in all_blocks),
            },
        }
        (out / f"{ch['id']}.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False))
        summary.append((ch["number"], ch["id"], payload["quality"]))
        print(f"  {ch['number']:>2} {ch['id'][:38]:<38} pages={len(pages):>3} "
              f"tables={len(all_tables):>3} tips={len(all_tips):>3} questions={len(all_questions):>3}")

    total = {
        "chapters": len(summary),
        "tables": sum(s[2]["tables"] for s in summary),
        "tips": sum(s[2]["tips"] for s in summary),
        "questions": sum(s[2]["questions"] for s in summary),
        "pages": sum(s[2]["pages"] for s in summary),
    }
    (out / "_summary.json").write_text(json.dumps(total, indent=1))
    print("TOTAL", total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
