#!/usr/bin/env python3
"""Build per-chapter module content from original APEA manual text extracts."""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "public/data/guide.json"
MANIFEST = ROOT / "public/data/manuals.json"
MANUALS = ROOT / "public/data/manuals"
OUT_DIR = ROOT / "public/data/modules"
SUMMARY = ROOT / "public/data/content-index.json"

# Guide chapter N -> manual module id (01 intro skipped; ch1 = exam prep 02)
def manual_id(chapter_number: int) -> str:
    return f"{chapter_number + 1:02d}"

PEARL_RE = re.compile(
    r"\b(first[- ]line|never |always |rule \d|must not|do not |contraindic|gold standard|"
    r"culture when|refer (?:to |if )|diagnostic criteria|sensitivity|specificity|"
    r"wait \d+ (?:day|week|year)|×\s*\d+|\d+ mg|\d+ mcg|≥|≤)\b",
    re.I,
)
HEADER_RE = re.compile(
    r"^(?:#{1,3}\s+)?([A-Z][A-Za-z0-9 ',\-–—/|]{4,90})$"
)
SKIP_HEADERS = re.compile(r"content overview|notes$|chapter \d", re.I)


def strip_frontmatter(text: str) -> str:
    return re.sub(r"^---[\s\S]*?---\s*", "", text)


def clean_line(line: str) -> str:
    line = line.replace("$", "•").strip()
    line = re.sub(r"\s+", " ", line)
    return line


def is_bullet(line: str) -> bool:
    return bool(re.match(r"^[\-•]\s+", line) or line.startswith("•"))


def extract_pearls(text: str, limit=36):
    pearls = []
    for chunk in re.split(r"\n{2,}", text):
        chunk = re.sub(r"\s+", " ", chunk).strip()
        if len(chunk) < 35 or len(chunk) > 320:
            continue
        if PEARL_RE.search(chunk):
            pearls.append(chunk)
    # Also sentence-level for dense paragraphs
    for sent in re.split(r"(?<=[.!?])\s+", text):
        sent = re.sub(r"\s+", " ", sent).strip()
        if 40 < len(sent) < 260 and PEARL_RE.search(sent):
            pearls.append(sent)
    out, seen = [], set()
    for p in pearls:
        k = p.lower()[:80]
        if k not in seen:
            seen.add(k)
            out.append(p)
        if len(out) >= limit:
            break
    return out


def parse_manual(text: str):
    text = strip_frontmatter(text).replace("\f", "\n")
    lines = [clean_line(l) for l in text.splitlines()]
    sections = []
    cur_title = "Overview"
    paras, bullets = [], []

    def flush():
        nonlocal paras, bullets
        blocks = []
        if bullets:
            blocks.append({"type": "list", "items": bullets[:80]})
            bullets = []
        for p in paras:
            if p:
                blocks.append({"type": "p", "text": p})
        paras = []
        if blocks:
            sections.append({"title": cur_title, "blocks": blocks})

    for line in lines:
        if not line:
            if paras and len(paras[-1]) > 20:
                flush()
            continue
        if len(line) < 4:
            continue
        if HEADER_RE.match(line) and not SKIP_HEADERS.search(line) and len(line) < 95:
            flush()
            cur_title = line if not line.startswith("#") else line.lstrip("# ").strip()
            continue
        if is_bullet(line):
            bullets.append(re.sub(r"^[\-•]\s+", "", line))
        elif len(line) > 1800:
            paras.append(line[:1800] + "…")
        else:
            paras.append(line)
    flush()
    return sections


def word_count(blocks):
    n = 0
    for b in blocks:
        if b["type"] == "p":
            n += len(b["text"].split())
        elif b["type"] == "list":
            n += sum(len(x.split()) for x in b["items"])
    return n


def main():
    guide = json.loads(GUIDE.read_text())
    manifest = json.loads(MANIFEST.read_text())
    by_id = {m["id"]: m for m in manifest["modules"]}
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    index = {"chapters": [], "pearls_total": 0, "generated": True}
    for ch in guide["chapters"]:
        if "number" not in ch:
            continue
        mid = manual_id(ch["number"])
        mod = by_id.get(mid)
        if not mod:
            print("skip", ch["number"], "no manual", mid)
            continue
        md_path = MANUALS / Path(mod["text_file"]).name
        raw = md_path.read_text()
        sections = parse_manual(raw)
        pearls = extract_pearls(raw)
        # drop tiny sections
        sections = [s for s in sections if word_count(s["blocks"]) >= 12][:45]
        payload = {
            "chapterId": ch["id"],
            "chapterNumber": ch["number"],
            "title": ch["shortTitle"],
            "manualId": mid,
            "manualTitle": mod["title"],
            "sections": sections,
            "pearls": pearls,
            "meta": {
                "source_chars": mod["text_chars"],
                "section_count": len(sections),
                "pearl_count": len(pearls),
            },
        }
        out = OUT_DIR / f"{ch['id']}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False))
        index["chapters"].append({
            "id": ch["id"],
            "number": ch["number"],
            "title": ch["shortTitle"],
            "sections": len(sections),
            "pearls": len(pearls),
            "words": sum(word_count(s["blocks"]) for s in sections),
        })
        index["pearls_total"] += len(pearls)
        print(f"{ch['number']:2} {ch['shortTitle'][:28]:28} sections={len(sections):2} pearls={len(pearls):2} words={index['chapters'][-1]['words']}")

    SUMMARY.write_text(json.dumps(index, indent=2) + "\n")
  # Lightweight full-corpus search snippets for the app
    snippets = []
    for ch in guide["chapters"]:
        if "number" not in ch:
            continue
        path = OUT_DIR / f"{ch['id']}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for s in data["sections"]:
            for b in s["blocks"]:
                texts = b["items"] if b["type"] == "list" else [b["text"]]
                for t in texts:
                    t = re.sub(r"\s+", " ", t).strip()
                    if len(t) > 40:
                        snippets.append({"chapterId": ch["id"], "chapter": ch["shortTitle"], "section": s["title"], "text": t[:420]})
        for p in data["pearls"]:
            snippets.append({"chapterId": ch["id"], "chapter": ch["shortTitle"], "section": "Clinical pearl", "text": p})
    (ROOT / "public/data/search-corpus.json").write_text(json.dumps(snippets, ensure_ascii=False))
    pearls_flat = []
    for ch in guide["chapters"]:
        if "number" not in ch:
            continue
        path = OUT_DIR / f"{ch['id']}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for i, p in enumerate(data["pearls"]):
            pearls_flat.append({"id": f"pearl-{ch['id']}-{i}", "front": p, "back": f"{ch['shortTitle']} — know this cold.", "tag": ch["shortTitle"]})
    (ROOT / "public/data/pearls.json").write_text(json.dumps(pearls_flat, ensure_ascii=False))
    print(f"Wrote {OUT_DIR} ({len(index['chapters'])} modules), pearls={index['pearls_total']}, search={len(snippets)} snippets")


if __name__ == "__main__":
    main()
