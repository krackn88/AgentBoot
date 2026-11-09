#!/usr/bin/env python3
"""Build per-chapter module content from original APEA manual text extracts."""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "public/data/guide.json"
QUESTION_SUPP = ROOT / "public/data/question-supplements.json"
MANIFEST = ROOT / "public/data/manuals.json"
MANUALS = ROOT / "public/data/manuals"
OUT_DIR = ROOT / "public/data/modules"
SUMMARY = ROOT / "public/data/content-index.json"


def manual_id(chapter_number: int) -> str:
    return f"{chapter_number + 1:02d}"


PEARL_RE = re.compile(
    r"\b(first[- ]line|never |always |rule \d|must not|do not |contraindic|gold standard|"
    r"culture when|refer (?:to |if )|diagnostic criteria|sensitivity|specificity|"
    r"wait \d+ (?:day|week|year)|×\s*\d+|\d+ mg|\d+ mcg|≥|≤|ESKAPE|stewardship)\b",
    re.I,
)
CAPS_HEADER = re.compile(r"^[A-Z][A-Z0-9 ',\-–—/|&]{5,80}$")
TITLE_HEADER = re.compile(r"^#{1,3}\s+(.+)$")
CHAPTER_LINE = re.compile(r"^Chapter \d+\s+\w+", re.I)
SKIP_HEADERS = re.compile(r"content overview|notes$|chapter \d|check your knowledge|exam checklist", re.I)
NOISE_LINE = re.compile(
    r"^(?:NOTES|CONTENT OVERVIEW|©|CHAPTER \d+$|FNP/AGPCNP Review|\d+\s*$)",
    re.I,
)
FOOTER_LINE = re.compile(r"FNP/AGPCNP Review", re.I)
QUESTION_START = re.compile(r"^QUESTION\s*#\s*\d+", re.I)
OPTION_LINE = re.compile(r"^\s*\d+\.\s+")


def strip_frontmatter(text: str) -> str:
    return re.sub(r"^---[\s\S]*?---\s*", "", text)


def clean_line(raw: str) -> str:
    line = raw.replace("\x08", "").strip()
    line = re.sub(r"^\d+\s+(?=FNP)", "", line)
    line = line.replace("$", "•").strip()
    line = re.sub(r"\s+", " ", line)
    return line


def preprocess_lines(text: str) -> list[str]:
    text = strip_frontmatter(text).replace("\f", "\n")
    out: list[str] = []
    prev = ""
    in_question = False
    for raw in text.splitlines():
        line = clean_line(raw)
        if not line:
            if in_question:
                in_question = False
            if out and out[-1] != "":
                out.append("")
            continue
        if NOISE_LINE.match(line) or FOOTER_LINE.search(line):
            continue
        if CHAPTER_LINE.match(line) and "|" in line:
            continue
        if QUESTION_START.match(line):
            in_question = True
            continue
        if in_question:
            if OPTION_LINE.match(raw) or (line.endswith("?") and len(line) > 20):
                continue
            if not OPTION_LINE.match(raw) and not line[0].isdigit():
                in_question = False
            else:
                continue
        if line == prev:
            continue
        prev = line
        out.append(line)
    return out


def is_bullet(line: str) -> bool:
    return bool(re.match(r"^[\-•]\s+", line) or line.startswith("•"))


def looks_like_header(line: str) -> bool:
    if line.startswith("#"):
        return True
    if SKIP_HEADERS.search(line):
        return False
    if CAPS_HEADER.match(line) and not line.endswith("."):
        return True
    if TITLE_HEADER.match(line):
        return True
  # Title case short headers from slides
    if (
        len(line) < 72
        and line[0].isupper()
        and "?" not in line
        and not is_bullet(line)
        and not line.endswith(".")
        and sum(1 for w in line.split() if w[0].isupper()) >= max(2, len(line.split()) // 2)
    ):
        return True
    return False


def header_title(line: str) -> str:
    m = TITLE_HEADER.match(line)
    if m:
        return m.group(1).strip()
    return line.lstrip("# ").strip()


def merge_sections(sections: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for sec in sections:
        if merged and merged[-1]["title"].lower() == sec["title"].lower():
            merged[-1]["blocks"].extend(sec["blocks"])
        else:
            merged.append(sec)
    return merged


def parse_manual(text: str) -> list[dict]:
    lines = preprocess_lines(text)
    sections: list[dict] = []
    cur_title = "Overview"
    paras: list[str] = []
    bullets: list[str] = []

    def flush():
        nonlocal paras, bullets
        blocks = []
        if bullets:
            # Dedupe bullet list while preserving order
            seen = set()
            uniq = []
            for b in bullets:
                k = b.lower()[:60]
                if k not in seen:
                    seen.add(k)
                    uniq.append(b)
            if uniq:
                blocks.append({"type": "list", "items": uniq[:60]})
            bullets = []
        for p in paras:
            if len(p) > 12:
                blocks.append({"type": "p", "text": p})
        paras = []
        if blocks and word_count(blocks) >= 6:
            sections.append({"title": cur_title, "blocks": blocks})

    for line in lines:
        if not line:
            continue
        if looks_like_header(line):
            flush()
            cur_title = header_title(line)
            if SKIP_HEADERS.search(cur_title):
                cur_title = "Overview"
            continue
        if is_bullet(line):
            bullets.append(re.sub(r"^[\-•]\s+", "", line))
        elif len(line) > 1600:
            paras.append(line[:1600] + "…")
        else:
            paras.append(line)
    flush()
    return merge_sections(sections)


def word_count(blocks) -> int:
    n = 0
    for b in blocks:
        if b["type"] == "p":
            n += len(b["text"].split())
        elif b["type"] == "list":
            n += sum(len(x.split()) for x in b["items"])
    return n


def section_words(sections: list[dict]) -> int:
    return sum(word_count(s["blocks"]) for s in sections)


def clean_pearl(text: str) -> str:
    text = re.sub(r"\s+", " ", text.replace("$", "•")).strip()
    text = re.sub(r"\d+\s+FNP/AGPCNP Review.*", "", text)
    text = re.sub(r"©.*", "", text).strip()
    return text


def extract_pearls(text: str, limit=48):
    pearls = []
    body = "\n".join(preprocess_lines(text))
    for chunk in re.split(r"\n{2,}", body):
        chunk = clean_pearl(chunk)
        if 35 < len(chunk) < 340 and PEARL_RE.search(chunk):
            pearls.append(chunk)
    for sent in re.split(r"(?<=[.!?])\s+", body):
        sent = clean_pearl(sent)
        if 42 < len(sent) < 280 and PEARL_RE.search(sent):
            pearls.append(sent)
    out, seen = [], set()
    for p in pearls:
        k = re.sub(r"\W+", "", p.lower())[:90]
        if k not in seen:
            seen.add(k)
            out.append(p)
        if len(out) >= limit:
            break
    return out


def title_similarity(a: str, b: str) -> float:
    a, b = a.lower(), b.lower()
    if a in b or b in a:
        return 0.92
    return SequenceMatcher(None, a, b).ratio()


def pick_manual_excerpt(
    manual_sections: list[dict],
    section_title: str,
    max_words=220,
    exclude_titles: set[str] | None = None,
) -> tuple[str, str] | None:
    exclude_titles = exclude_titles or set()
    ranked = []
    for sec in manual_sections:
        if sec["title"].lower() in exclude_titles:
            continue
        score = title_similarity(section_title, sec["title"])
        parts = []
        for b in sec["blocks"]:
            if b["type"] == "p":
                parts.append(b["text"])
            elif b["type"] == "list":
                parts.extend(b["items"][:8])
        text = " ".join(parts)
        if len(text.split()) >= 35:
            ranked.append((score, text, sec["title"]))
    ranked.sort(key=lambda x: x[0], reverse=True)
    if not ranked or ranked[0][0] < 0.42:
        return None
    best = ranked[0][1]
    words = best.split()
    if len(words) > max_words:
        best = " ".join(words[:max_words]) + "…"
    return best, ranked[0][2]


def pick_manual_list_block(manual_sections: list[dict], section_title: str):
    for sec in manual_sections:
        if title_similarity(section_title, sec["title"]) < 0.38:
            continue
        for b in sec["blocks"]:
            if b["type"] != "list" or len(b["items"]) < 5:
                continue
            items = [re.sub(r"\s+", " ", x).strip() for x in b["items"] if len(x.strip()) > 3][:18]
            rows = []
            for it in items:
                if ":" in it:
                    left, right = it.split(":", 1)
                    rows.append([left.strip(), right.strip()])
            if len(rows) >= 3:
                return {"type": "table", "headers": ["Topic", "Detail"], "rows": rows[:14]}
            return {"type": "manual-list", "items": items}
    return None


def apply_question_supplements(guide: dict) -> int:
    if not QUESTION_SUPP.exists():
        return 0
    data = json.loads(QUESTION_SUPP.read_text())
    patches = {p["id"]: p for p in data.get("patches", [])}
    n = 0
    for ch in guide["chapters"]:
        for q in ch.get("questions", []):
            p = patches.get(q["id"])
            if not p:
                continue
            if p.get("stem"):
                q["stem"] = p["stem"]
            if p.get("options"):
                q["options"] = p["options"]
            if p.get("correctIndex") is not None:
                q["correctIndex"] = p["correctIndex"]
            if p.get("explanation"):
                q["explanation"] = p["explanation"]
            n += 1
        for extra in data.get("extra", []):
            if extra.get("chapterId") == ch["id"]:
                ch["questions"].append(extra)
                n += 1
    guide["meta"]["questions"] = sum(len(c.get("questions", [])) for c in guide["chapters"])
    return n


def guide_section_words(sec: dict) -> int:
    w = 0
    for b in sec.get("blocks", []):
        if b["type"] in ("p", "manual-note"):
            w += len(b.get("text", "").split())
        elif b["type"] == "list":
            w += sum(len(x.split()) for x in b.get("items", []))
        elif b["type"] == "manual-list":
            w += sum(len(x.split()) for x in b.get("items", []))
        elif b["type"] == "table":
            for r in b.get("rows", []):
                w += sum(len(str(c).split()) for c in r)
    return w


def augment_guide(guide: dict, chapter_payloads: dict[str, dict]) -> int:
    """Append manual notes/tables to thin study-guide sections."""
    added = 0
    for ch in guide["chapters"]:
        payload = chapter_payloads.get(ch["id"])
        if not payload:
            continue
        manual_secs = payload["sections"]
        for sec in ch.get("sections", []):
            w = guide_section_words(sec)
            if w >= 130:
                continue
            used_titles: set[str] = set()
            note_count = sum(1 for b in sec["blocks"] if b.get("type") == "manual-note")
            while w < 130 and note_count < 2:
                hit = pick_manual_excerpt(manual_secs, sec["title"], exclude_titles=used_titles)
                if not hit:
                    break
                excerpt, manual_title = hit
                sec.setdefault("blocks", []).append(
                    {
                        "type": "manual-note",
                        "text": excerpt,
                        "source": payload["manualTitle"],
                    }
                )
                used_titles.add(manual_title.lower())
                note_count += 1
                added += 1
                w = guide_section_words(sec)
            if w < 90 and not any(b.get("type") in ("table", "manual-list") for b in sec["blocks"]):
                block = pick_manual_list_block(manual_secs, sec["title"])
                if block:
                    block["source"] = payload["manualTitle"]
                    sec.setdefault("blocks", []).append(block)
                    added += 1
    return added


def main():
    guide = json.loads(GUIDE.read_text())
    manifest = json.loads(MANIFEST.read_text())
    by_id = {m["id"]: m for m in manifest["modules"]}
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    chapter_payloads: dict[str, dict] = {}
    index = {"chapters": [], "pearls_total": 0, "generated": True, "supplements_added": 0}

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
        sections = [s for s in sections if word_count(s["blocks"]) >= 10]
        # Keep the richest sections, prioritizing longer content
        sections.sort(key=lambda s: word_count(s["blocks"]), reverse=True)
        sections = sorted(sections[:70], key=lambda s: s["title"].lower())

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
                "depth_words": section_words(sections),
            },
        }
        chapter_payloads[ch["id"]] = payload
        out = OUT_DIR / f"{ch['id']}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False))
        index["chapters"].append(
            {
                "id": ch["id"],
                "number": ch["number"],
                "title": ch["shortTitle"],
                "sections": len(sections),
                "pearls": len(pearls),
                "words": payload["meta"]["depth_words"],
            }
        )
        index["pearls_total"] += len(pearls)
        print(
            f"{ch['number']:2} {ch['shortTitle'][:28]:28} "
            f"sections={len(sections):2} pearls={len(pearls):2} words={payload['meta']['depth_words']}"
        )

    supp = augment_guide(guide, chapter_payloads)
    q_patched = apply_question_supplements(guide)
    index["supplements_added"] = supp
    index["questions_patched"] = q_patched
    # Recompute chapter word counts for the app
    for c in guide["chapters"]:
        c["wordCount"] = sum(
            len(b.get("text", "").split())
            + sum(len(x.split()) for x in b.get("items", []))
            + (
                sum(len(str(cell).split()) for row in b.get("rows", []) for cell in row)
                if b.get("type") == "table"
                else 0
            )
            for s in c.get("sections", [])
            for b in s.get("blocks", [])
        )
    GUIDE.write_text(json.dumps(guide, ensure_ascii=False))

    SUMMARY.write_text(json.dumps(index, indent=2) + "\n")

    snippets = []
    for ch in guide["chapters"]:
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
                        snippets.append(
                            {
                                "chapterId": ch["id"],
                                "chapter": ch["shortTitle"],
                                "section": s["title"],
                                "text": t[:420],
                            }
                        )
        for p in data["pearls"]:
            snippets.append(
                {
                    "chapterId": ch["id"],
                    "chapter": ch["shortTitle"],
                    "section": "Clinical pearl",
                    "text": p,
                }
            )

    # search-corpus.json is superseded by build_search_index.py (full index).
    # Keep the variable for the modules build below; do not emit the old sample file.
    pearls_flat = []
    for ch in guide["chapters"]:
        path = OUT_DIR / f"{ch['id']}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for i, p in enumerate(data["pearls"]):
            pearls_flat.append(
                {
                    "id": f"pearl-{ch['id']}-{i}",
                    "chapterId": ch["id"],
                    "front": p,
                    "back": f"{ch['shortTitle']} — board pearl. Say it out loud once, then flip.",
                    "tag": ch["shortTitle"],
                }
            )
    (ROOT / "public/data/pearls.json").write_text(json.dumps(pearls_flat, ensure_ascii=False))
    print(
        f"Wrote {OUT_DIR} ({len(index['chapters'])} modules), "
        f"pearls={index['pearls_total']}, search={len(snippets)} snippets, "
        f"guide supplements={supp}"
    )


if __name__ == "__main__":
    main()
