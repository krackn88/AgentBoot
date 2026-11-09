#!/usr/bin/env python3
"""Build recall drills from Docling's structured markdown.

Docling preserves document structure that naive text extraction destroys: headings
become `##`, bullets stay bullets, and definition-style runs (`Term: definition`)
keep their pairing. That makes far better study material than the flattened line
runs the previous pass had to guess at.

Each drill is a prompt plus the items a student should be able to reproduce.

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

FOOTER = re.compile(r"\d*\s*FNP/AGPCNP Review|©\s*\d{4}|Advanced Practice Education Associates", re.I)
RUNNING_HEAD = re.compile(r"^#+\s*Chapter\s+\d+", re.I)
BAD_HEAD = re.compile(r"^(NOTES|CONTENT OVERVIEW|CHECK YOUR KNOWLEDGE|EXAM CHECKLIST)$", re.I)
BULLET = re.compile(r"^\s*[-*]\s+(.*)$")
NUMBERED = re.compile(r"^\s*\d+\.\s+(.*)$")
IMAGE = re.compile(r"^<!--.*-->$")


def clean(t: str) -> str:
    t = (t or "").replace("\x08", " ").replace("$", "")
    t = re.sub(r"&gt;", ">", t)
    t = re.sub(r"&lt;", "<", t)
    t = re.sub(r"&amp;", "&", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t.strip(" ,;")


def usable_item(t: str) -> bool:
    if len(t) < 12 or len(t) > 180:
        return False
    if FOOTER.search(t) or IMAGE.match(t):
        return False
    words = t.split()
    if len(words) < 3:
        return False
    caps = sum(1 for w in words if w.isupper() and len(w) > 2)
    if caps / len(words) > 0.4:
        return False
    if re.fullmatch(r"[\d\s.,%<>≤≥–\-]+", t):
        return False
    return True


def parse_markdown(md: str):
    """Yield (heading, items) runs, plus definition runs without bullets."""
    heading = ""
    block = []
    out = []

    def flush():
        nonlocal block
        if len(block) >= 3:
            out.append((heading, list(block)))
        block = []

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        hm = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if hm:
            flush()
            title = clean(hm.group(2))
            if not RUNNING_HEAD.match(line.strip()) and not BAD_HEAD.match(title):
                heading = title
            continue
        bm = BULLET.match(line)
        nm = NUMBERED.match(line)
        if bm or nm:
            t = clean((bm or nm).group(1))
            if usable_item(t):
                block.append(t)
            continue
        # a definition-style line: "Term: definition"
        t = clean(line)
        if usable_item(t) and ":" in t and len(t.split()) >= 4:
            block.append(t)
        else:
            flush()
    flush()
    return out


def main() -> int:
    lists = []
    for path in sorted(glob.glob(str(DATA / "docling" / "*.json"))):
        if path.endswith("_summary.json"):
            continue
        doc = json.loads(Path(path).read_text())
        cid = doc.get("chapterId", "")
        md = doc.get("markdown", "")
        if not md:
            continue
        title = TITLES.get(cid, doc.get("title", ""))
        for heading, items in parse_markdown(md):
            # de-duplicate while preserving order
            seen, uniq = set(), []
            for it in items:
                k = it.lower()
                if k in seen:
                    continue
                seen.add(k)
                uniq.append(it)
            if len(uniq) < 3:
                continue
            prompt = heading or uniq[0].split(":")[0][:48] or "Recall this list"
            prompt = re.sub(r"^NOTES\s*", "", prompt, flags=re.I).strip()
            prompt = re.sub(r"\s+", " ", prompt)
            lists.append({
                "id": f"pdf-list-{len(lists)}",
                "chapterId": cid,
                "chapter": title,
                "section": heading,
                "prompt": prompt[:90],
                "items": uniq[:14],
            })

    payload = {
        "meta": {
            "count": len(lists),
            "items": sum(len(x["items"]) for x in lists),
            "source": "Docling structured markdown from the 22 APEA PDFs",
        },
        "lists": lists,
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False))
    from collections import Counter
    print(f"pdf-lists.json: {len(lists)} drills, {payload['meta']['items']} items "
          f"across {len(Counter(x['chapterId'] for x in lists))} chapters")
    for x in lists[:6]:
        print(f"  [{x['chapter'][:18]:<18}] {x['prompt'][:48]} ({len(x['items'])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
