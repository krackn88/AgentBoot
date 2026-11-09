#!/usr/bin/env python3
"""Turn the PDFs' bullet lists into active-recall drills.

The site ignored the single largest body of structured content in the source: the
slides carry 1,010 bullet lists (11,094 items) covering lesion definitions,
criteria, red flags, dosing and differentials. None of it reached a study surface
because the markdown pipeline flattened it and the pearl extractor rejected it.

Each list becomes a recall drill of the form

    prompt: "Dermatology: primary skin lesions"
    items:  ["Nodule: solid lesion >0.5–2.0 cm", ...]

so a student can try to reproduce the list before revealing it — the same
mechanic the workbook already uses for tables, applied to content that previously
had none.

Output: public/data/pdf-lists.json
"""
import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "public/data"
OUT = DATA / "pdf-lists.json"

GUIDE = json.loads((DATA / "guide.json").read_text())
TITLES = {c["id"]: (c.get("shortTitle") or c.get("title")) for c in GUIDE["chapters"]}

FOOTER = re.compile(r"\d*\s*FNP/AGPCNP Review", re.I)
CHAPTER_LINE = re.compile(r"^Chapter\s+\d+\s*\w*.*\|.*$", re.I)
# running headers look like "Chapter 11  Women's Health | Tanner Stages"
RUNNING_HEAD = re.compile(r"\bChapter\s+\d+\b.*\|", re.I)
NOTES = re.compile(r"\bNOTES\b", re.I)
CAPS_HEAD = re.compile(r"^[A-Z][A-Z0-9 ,&/\-\(\)]{6,}$")


def clean_item(t: str) -> str:
    t = t.replace("\x08", " ")
    t = re.sub(r"^\s*[\$•✓\-]\s*", "", t)      # bullet glyphs, incl. the PDF's "$"
    t = FOOTER.sub("", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t.strip(" ,;")


def usable(item: str) -> bool:
    if len(item) < 14 or len(item) > 180:
        return False
    if CHAPTER_LINE.match(item) or FOOTER.search(item) or RUNNING_HEAD.search(item):
        return False
    if NOTES.search(item):
        return False
    if "$" in item:
        return False
    if re.fullmatch(r"[\d\s.,%–\-]+", item):
        return False
    # copyright / publisher furniture
    if re.search(r"©|Advanced Practice Education Associates|All rights reserved", item, re.I):
        return False
    words = item.split()
    if len(words) < 3:
        return False
    # mostly-caps slide headings are not list items
    caps = sum(1 for w in words if w.isupper() and len(w) > 2)
    if caps / len(words) > 0.4:
        return False
    return True


BAD_PROMPT = re.compile(r"(FNP/AGPCNP|Chapter \d|Review$|^\d+$|NOTES)", re.I)


def derive_prompt(items: list[str], section: str) -> str:
    """Name the list from its own first item when no heading survives."""
    head = ""
    for it in items:
        if re.match(r"^[A-Z][a-z]", it) and ":" in it and len(it) < 60:
            head = it.split(":")[0]
            break
    if not head and section and not BAD_PROMPT.search(section):
        head = section
    if not head and items:
        head = items[0].split(":")[0][:48]
    head = head.strip(" •-$")
    if BAD_PROMPT.search(head) or len(head) < 6:
        return ""
    return head


def main() -> int:
    out = []
    for path in sorted(glob.glob(str(DATA / "pdf-extract" / "*.json"))):
        if path.endswith("_summary.json"):
            continue
        doc = json.loads(Path(path).read_text())
        cid = doc.get("chapterId", "")
        title = TITLES.get(cid, doc.get("title", ""))
        section = ""
        for b in doc.get("blocks", []):
            if b.get("type") == "para":
                t = (b.get("text") or "").strip()
                if 3 <= len(t.split()) <= 8 and not re.search(r"[.?!]$", t):
                    section = t
                continue
            if b.get("type") != "list":
                continue
            items, seen = [], set()
            for raw in b.get("items", []):
                it = clean_item(raw)
                if not usable(it):
                    continue
                k = it.lower()
                if k in seen:
                    continue
                seen.add(k)
                items.append(it)
            prompt = derive_prompt(items, section)
            if len(items) < 3 or not prompt:
                continue
            out.append({
                "id": f"pdf-list-{len(out)}",
                "chapterId": cid,
                "chapter": title,
                "section": section,
                "prompt": prompt,
                "items": items[:14],
                "page": b.get("page"),
            })

    payload = {
        "meta": {
            "count": len(out),
            "items": sum(len(x["items"]) for x in out),
            "source": "bullet lists recovered from the 22 APEA PDFs, one recall drill per list",
        },
        "lists": out,
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False))
    from collections import Counter
    print(f"pdf-lists.json: {len(out)} drills, {payload['meta']['items']} items "
          f"across {len(Counter(x['chapterId'] for x in out))} chapters")
    for x in out[:5]:
        print(f"  [{x['chapter'][:20]:<20}] {x['prompt'][:46]} ({len(x['items'])} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
