#!/usr/bin/env python3
"""Extract structured content from the APEA PDFs using Docling.

The hand-rolled PyMuPDF coordinate heuristic found 88 tables and misread many of
them. Docling runs a layout model plus TableFormer, which scores 0.86 F1(TEDS) on
the 2026 KDD table-extraction benchmark versus 0.27 for raw PyMuPDF text - it
recovers cell spans, empty cells, and header bands that geometry alone misses.

Emits per chapter:

  public/data/docling/<chapterId>.json
    { chapterId, title, tables:[{headers, rows, page, caption}],
      items:[{kind, text/page}], tips:[...], questions:[...], quality:{...} }

Run:  python3 scripts/docling_extract.py --src /tmp/pdfs --out public/data/docling
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "public/data"
GUIDE = json.loads((DATA / "guide.json").read_text())

QUESTION = re.compile(r"^QUESTION\s*#\s*(\d+)", re.I)
OPTION = re.compile(r"^(\d)\.\s+(.*)$")
TIP = re.compile(r"^(?:TIP|PEARL)\s*:\s*(.+)$", re.I)
FOOTER = re.compile(r"\d*\s*FNP/AGPCNP Review|©\s*\d{4}|Advanced Practice Education", re.I)
CHAPTER_LINE = re.compile(r"^Chapter\s+\d+\b.*\|", re.I)


def chapter_for(pdf_name: str):
    m = re.match(r"(\d+)-", pdf_name)
    if not m:
        return None
    num = int(m.group(1))
    for ch in GUIDE["chapters"]:
        if ch["number"] == num - 1:
            return ch
    return None


def clean(text: str) -> str:
    t = (text or "").replace("\x08", " ").replace("$", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def table_payload(item, doc):
    """Convert a Docling TableItem into headers + rows."""
    try:
        df = item.export_to_dataframe(doc)
    except Exception:
        return None
    if df is None or df.empty:
        return None
    grid = [[clean(str(c)) for c in row] for row in df.values.tolist()]
    grid = [r for r in grid if any(r)]
    if len(grid) < 2:
        return None
    headers = grid[0]
    # Docling sometimes emits the header twice as the first data row
    body = grid[1:]
    if body and [clean(str(c)).lower() for c in body[0]] == [clean(str(h)).lower() for h in headers]:
        body = body[1:]
    if not body:
        return None
    # drop wholly empty columns
    keep = [i for i in range(len(headers)) if headers[i] or any(r[i] if i < len(r) else "" for r in body)]
    headers = [headers[i] if i < len(headers) else "" for i in keep]
    body = [[r[i] if i < len(r) else "" for i in keep] for r in body]
    if len(headers) < 2:
        return None
    return {
        "headers": headers,
        "rows": body[:40],
        "caption": clean(getattr(item, "caption", "") or ""),
        "page": (item.prov[0].page_no - 1) if getattr(item, "prov", None) else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="/tmp/pdfs")
    ap.add_argument("--out", default=str(DATA / "docling"))
    args = ap.parse_args()

    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
    from docling.datamodel.base_models import InputFormat

    opts = PdfPipelineOptions()
    opts.do_table_structure = True
    opts.table_structure_options.mode = TableFormerMode.ACCURATE
    opts.do_ocr = False
    conv = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    summary = []
    for pdf in sorted(Path(args.src).glob("*.pdf")):
        ch = chapter_for(pdf.name)
        if not ch:
            continue
        doc = conv.convert(str(pdf)).document

        tables = []
        for item in doc.tables:
            payload = table_payload(item, doc)
            if payload:
                tables.append(payload)

        # walk the text for tips, questions and clean list lines
        text = doc.export_to_text()
        lines = [clean(l) for l in text.splitlines()]
        lines = [l for l in lines if l and not FOOTER.search(l) and not CHAPTER_LINE.match(l)]

        tips, questions = [], []
        i = 0
        while i < len(lines):
            ln = lines[i]
            tm = TIP.match(ln)
            if tm:
                tips.append(tm.group(1).strip())
                i += 1
                continue
            qm = QUESTION.match(ln)
            if qm:
                stem, opts_, j = [], [], i + 1
                while j < len(lines) and len(opts_) < 6:
                    t = lines[j]
                    om = OPTION.match(t)
                    if om:
                        opts_.append(om.group(2).strip())
                    elif opts_ and not opts_[-1].endswith((".", "?", "!")):
                        opts_[-1] += " " + t
                    elif not opts_ and len(stem) < 6:
                        stem.append(t)
                    else:
                        break
                    j += 1
                questions.append({"stem": " ".join(stem).strip(), "options": opts_})
                i = j
                continue
            i += 1

        payload = {
            "chapterId": ch["id"],
            "title": ch.get("shortTitle") or ch.get("title"),
            "pdf": pdf.name,
            "markdown": doc.export_to_markdown(),
            "tables": tables,
            "tips": tips,
            "questions": questions,
            "quality": {
                "tables": len(tables),
                "tips": len(tips),
                "questions": len(questions),
                "rows": sum(len(t["rows"]) for t in tables),
            },
        }
        (out / f"{ch['id']}.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False))
        summary.append(payload["quality"])
        print(f"  {ch['number']:>2} {ch['id'][:36]:<36} tables={len(tables):>3} "
              f"rows={payload['quality']['rows']:>4} tips={len(tips):>3} q={len(questions):>3}", flush=True)

    total = {
        "chapters": len(summary),
        "tables": sum(s["tables"] for s in summary),
        "rows": sum(s["rows"] for s in summary),
        "tips": sum(s["tips"] for s in summary),
        "questions": sum(s["questions"] for s in summary),
    }
    (out / "_summary.json").write_text(json.dumps(total, indent=1))
    print("TOTAL", total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
