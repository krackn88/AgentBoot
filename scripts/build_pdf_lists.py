#!/usr/bin/env python3
"""Build recall drills from Docling's structured markdown.

Docling preserves structure that naive extraction destroys: headings become `##`,
bullets stay bullets, definition runs keep their pairing. But a bare heading is not
a question, and the slides interleave exam questions with teaching lists, so this
pass does more than copy headings:

  * every drill gets a real cue ("Name the gram-negative organisms" / "What are the
    features of hives?") instead of a bare heading
  * blocks that are really exam questions (a "QUESTION #n" heading, or items that
    are all answer choices) are dropped - they belong in the question bank, and
    showing their options as list items is nonsense
  * a list must be plausibly recallable: 3+ short, distinct items

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
QUESTION_HEAD = re.compile(r"^QUESTION\s*#?\s*\d*", re.I)
BULLET = re.compile(r"^\s*[-*]\s+(.*)$")
NUMBERED = re.compile(r"^\s*\d+\.\s+(.*)$")
IMAGE = re.compile(r"^<!--.*-->$")

COLLECTION = re.compile(
    r"\b(bugs|organisms|agents|drugs|classes|examples|types|symptoms|signs|features|"
    r"criteria|indications|contraindications|causes|risk factors|complications|"
    r"side effects|adverse effects|categories|generations|options|steps|rules)\b",
    re.I,
)


def clean(t: str) -> str:
    t = (t or "").replace("\x08", " ").replace("$", "")
    t = re.sub(r"&gt;", ">", t)
    t = re.sub(r"&lt;", "<", t)
    t = re.sub(r"&amp;", "&", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t.strip(" ,;")


def usable_item(t: str) -> bool:
    if len(t) < 12 or len(t) > 170:
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


def looks_like_answer_choices(items):
    """Exam options shown as list items belong in the question bank, not here."""
    if any(re.match(r"^\d+\.", i) for i in items):
        return True
    if len(items) == 4 and all(len(i) < 120 for i in items):
        return True
    return False


def make_cue(heading: str) -> str:
    """Turn a slide heading into a cue a student can act on.

    A bare heading ("Gram-Negative Bugs") leaves the student guessing what is being
    asked. The cue always states the topic and, separately, how many items to
    recall, so the task is unambiguous.
    """
    h = clean(heading)
    h = QUESTION_HEAD.sub("", h).strip(" :#-")
    h = re.sub(r"\bNOTES\b", "", h, flags=re.I).strip(" :#-")
    h = re.sub(r"^the\s+", "", h, flags=re.I)
    if not h:
        return ""
    low = h.lower()

    if h.endswith("?"):
        return h
    if COLLECTION.search(low):
        return f"Name the {low}."
    if ":" in h:
        head, tail = [p.strip() for p in h.split(":", 1)]
        if tail and len(tail) < 60:
            return f"What are the {tail.lower()} for {head.lower()}?"
        return f"What are the {head.lower()}?"
    # a topic rather than a collection: ask for its key points by name
    return f"List the key points for {low}."


def parse_markdown(md: str):
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
        t = clean(line)
        if usable_item(t) and ":" in t and len(t.split()) >= 4:
            block.append(t)
        else:
            flush()
    flush()
    return out


def main() -> int:
    lists = []
    dropped_q = 0
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
            if QUESTION_HEAD.match(heading or "") or looks_like_answer_choices(items):
                dropped_q += 1
                continue
            seen, uniq = set(), []
            for it in items:
                k = it.lower()
                if k in seen:
                    continue
                seen.add(k)
                uniq.append(it)
            if len(uniq) < 3:
                continue
            cue = make_cue(heading)
            if not cue or len(cue) < 12:
                continue
            lists.append({
                "id": f"pdf-list-{len(lists)}",
                "chapterId": cid,
                "chapter": title,
                "section": heading,
                "prompt": cue[:140],
                "itemCount": len(uniq[:14]),
                "items": uniq[:14],
            })

    payload = {
        "meta": {
            "count": len(lists),
            "items": sum(len(x["items"]) for x in lists),
            "source": "Docling structured markdown from the 22 APEA PDFs",
            "dropped_question_blocks": dropped_q,
        },
        "lists": lists,
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False))
    from collections import Counter
    print(f"pdf-lists.json: {len(lists)} drills, {payload['meta']['items']} items "
          f"across {len(Counter(x['chapterId'] for x in lists))} chapters "
          f"(dropped {dropped_q} question blocks)")
    for x in lists[:8]:
        print(f"  [{x['chapter'][:14]:<14}] {x['prompt'][:72]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
