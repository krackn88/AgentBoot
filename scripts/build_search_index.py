#!/usr/bin/env python3
"""Build a real search index over every piece of content on the site.

The previous search-corpus.json was a capped 4,000-snippet sample, so common
high-yield terms were simply absent ("torsades" returned nothing, even though it
appears in the manuals). This builds an index over:

  * study guide sections (paragraphs, lists, tables)
  * every line of every full manual
  * clinical pearls
  * graded questions (stem + options + rationale)

Output is gzip-friendly and loaded lazily by the client:

public/data/search-index.json
  { docs: [ {i, c(chapterId), t(chapterTitle), s(section), x(text), k(kind)} ],
    meta: {...} }
"""
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "public/data"
MANUALS = DATA / "manuals"
OUT = DATA / "search-index.json"
OUT_GZ = DATA / "search-index.json.gz"

NOISE = re.compile(
    r"^(?:NOTES|CONTENT OVERVIEW|©|\d+\s*$|CHAPTER \d+$|FNP/AGPCNP Review|QUESTION\s*#\s*\d+|"
    r"CHECK YOUR KNOWLEDGE|EXAM CHECKLIST)",
    re.I,
)
MIN_LEN = 24
MAX_LEN = 260


def clean(text: str) -> str:
    t = text.replace("\x08", " ").replace("$", "•")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def add(docs, chapter_id, chapter_title, section, text, kind):
    t = clean(text)
    if len(t) < MIN_LEN:
        return
    if len(t) > MAX_LEN:
        # keep the head of a long block; the full text lives in the reader
        t = t[:MAX_LEN].rsplit(" ", 1)[0] + "…"
    if NOISE.match(t):
        return
    docs.append({"c": chapter_id, "t": chapter_title, "s": section[:70], "x": t, "k": kind})


def block_texts(blocks):
    for b in blocks:
        t = b.get("type")
        if t == "p":
            yield b.get("text", "")
        elif t in ("list", "manual-list"):
            for item in b.get("items", []):
                yield item
        elif t == "table":
            headers = b.get("headers", [])
            for row in b.get("rows", []):
                cells = [c for c in row if c]
                if len(cells) >= 2:
                    yield " · ".join(
                        f"{headers[i]}: {c}" if i < len(headers) and headers[i] else c
                        for i, c in enumerate(row)
                        if c
                    )
                elif cells:
                    yield cells[0]


def main() -> int:
    docs = []

    guide = json.loads((DATA / "guide.json").read_text())
    extra_bank = {}
    pq = DATA / "professional-questions.json"
    if pq.exists():
        extra_bank = json.loads(pq.read_text())
    extras = {}
    for q in extra_bank.get("extra", []):
        extras.setdefault(q.get("chapterId"), []).append(q)
    for ch in guide["chapters"]:
        title = ch.get("shortTitle") or ch.get("title")
        for sec in ch.get("sections", []):
            for text in block_texts(sec.get("blocks", [])):
                add(docs, ch["id"], title, sec.get("title", ""), text, "guide")
        for q in ch.get("questions", []):
            add(docs, ch["id"], title, "Practice question", q.get("stem", ""), "question")
            for opt in q.get("options", []):
                add(docs, ch["id"], title, "Answer choice", opt, "question")
            if q.get("explanation"):
                add(docs, ch["id"], title, "Answer rationale", q["explanation"], "rationale")
        for q in extras.get(ch["id"], []):
            add(docs, ch["id"], title, "Practice question", q.get("stem", ""), "question")
            for opt in q.get("options", []):
                add(docs, ch["id"], title, "Answer choice", opt, "question")
            if q.get("explanation"):
                add(docs, ch["id"], title, "Answer rationale", q["explanation"], "rationale")

    # every manual line
    manifest = json.loads((DATA / "manuals.json").read_text())
    by_slug = {}
    for m in manifest.get("modules", []):
        by_slug[m["id"]] = m

    for ch in guide["chapters"]:
        manual_num = f"{ch['number'] + 1:02d}"
        mod = by_slug.get(manual_num)
        if not mod:
            continue
        path = MANUALS / mod["text_file"].split("/")[-1]
        if not path.exists():
            continue
        title = ch.get("shortTitle") or ch.get("title")
        section = ""
        for raw in path.read_text().splitlines():
            line = clean(raw)
            if not line:
                continue
            # a short ALL-CAPS / title line becomes the current section
            if len(line) < 80 and re.match(r"^[A-Z][A-Za-z0-9 ,&/()'’\-–—:]+$", line) and line.isupper() is False:
                if len(line.split()) <= 10 and not re.search(r"[.?!]$", line):
                    section = line
            add(docs, ch["id"], title, section or title, line, "manual")

    pearls = json.loads((DATA / "pearls.json").read_text())
    chapter_titles = {c["id"]: (c.get("shortTitle") or c.get("title")) for c in guide["chapters"]}
    for p in pearls:
        cid = p.get("chapterId", "")
        add(
            docs,
            cid,
            p.get("tag") or chapter_titles.get(cid, ""),
            "Clinical pearl",
            p.get("front") or p.get("text", ""),
            "pearl",
        )

    # backfill any title we could not resolve, so search results always group
    for d in docs:
        if not d["t"]:
            d["t"] = chapter_titles.get(d["c"], "General")

    for i, d in enumerate(docs):
        d["i"] = i

    # --- compact encoding: chapters and sections become indexes -----------
    chapters_meta = []
    chapter_idx = {}
    for d in docs:
        if d["c"] not in chapter_idx:
            chapter_idx[d["c"]] = len(chapters_meta)
            chapters_meta.append({"id": d["c"], "title": d["t"]})

    sections = []
    section_idx = {}
    for d in docs:
        key = d["s"]
        if key not in section_idx:
            section_idx[key] = len(sections)
            sections.append(key)

    compact = []
    for d in docs:
        compact.append([chapter_idx[d["c"]], section_idx[d["s"]], d["k"][0], d["x"]])

    KIND_BY_LETTER = {"g": "guide", "m": "manual", "p": "pearl", "q": "question", "r": "rationale"}
    groups = {
        "core": [r for r in compact if KIND_BY_LETTER[r[2]] in ("guide", "pearl", "question", "rationale")],
        "manual": [r for r in compact if KIND_BY_LETTER[r[2]] == "manual"],
    }

    CHUNKS = DATA / "search-chunks"
    CHUNKS.mkdir(exist_ok=True)
    for old in CHUNKS.glob("*.json"):
        old.unlink()

    manifest_chunks = []
    for name, subset in groups.items():
        path = CHUNKS / f"{name}.json"
        path.write_text(json.dumps({"rows": subset}, separators=(",", ":")))
        manifest_chunks.append({"name": name, "count": len(subset), "bytes": path.stat().st_size})

    (CHUNKS / "manifest.json").write_text(
        json.dumps(
            {
                "chapters": chapters_meta,
                "sections": sections,
                "kinds": KIND_BY_LETTER,
                "chunks": manifest_chunks,
            },
            separators=(",", ":"),
        )
    )

    OUT.unlink(missing_ok=True)
    print(f"search index: {len(docs)} documents")
    for c in manifest_chunks:
        print(f"  chunk {c['name']}: {c['count']} docs · {c['bytes']/1024:.0f} KB")
    print(f"  manifest: {(CHUNKS / 'manifest.json').stat().st_size/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
