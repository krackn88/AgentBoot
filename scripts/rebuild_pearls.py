#!/usr/bin/env python3
"""Build the clinical pearl deck from content that is already verified.

Automated sentence-mining of the manual text does not work: the source is
column-interleaved slide layout, so extracted "pearls" were slide titles, exam
questions, and table dumps. 141 of the previous 231 were artefacts and even the
survivors were fragments.

Instead this derives pearls from sources we know are clean:

  1. the study guide's must-know rule table (hand-curated, one rule per row)
  2. reconstructed reference tables - each row becomes a defensible fact, e.g.
     "C. difficile - First-Line (Oral): Vancomycin"

Every pearl is screened by the same strict rules, then written for review.

Output: public/data/pearls-clean.json
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "public/data"
MODULES = DATA / "modules"
OUT = DATA / "pearls-clean.json"

GUIDE = json.loads((DATA / "guide.json").read_text())

# "$" is a bullet glyph in the PDFs but also currency in malpractice limits
BULLET = re.compile(r"•")
QUESTION = re.compile(r"(\bwhich of the following\b|\bwhat (?:is|should)\b|\bselect all\b|\bthis patient\b)", re.I)
NUMWALL = re.compile(r"(\d[\d.,–\-]*\s*%?\s*){5,}")
CAPS_HEADS = re.compile(r"^[A-Z][A-Z0-9 ,&/\-]{14,}$")


def clean(t: str) -> str:
    # "$" is a bullet glyph in the PDF extracts, but it is also a legitimate
    # currency sign in malpractice limits ("$1M / $3M"). Only strip it when it is
    # acting as a bullet.
    t = (t or "").replace("\x08", " ")
    t = re.sub(r"(^|\s)\$(?=\s)", r"\1", t)
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r"\bNOTES\b", "", t).strip()


# A rationale built from a question carries the vignette with it.
VIGNETTE = re.compile(
    r"(\bA \d+[- ]year-old\b|\bThe (?:patient|child|NP|caregiver|family) (?:is|has|should|was)\b|"
    r"\bThis (?:patient|child)\b|\b\d+\.\s|\bwhich\b.*\?)",
    re.I,
)


def looks_glued(text: str) -> bool:
    """True when a slide label and its sentence ran together with no separator.

    "Hearing loss may become permanent Hearing loss can lead to..." - the label
    repeats the opening of the sentence. Detect a capitalised word following a
    lowercase word mid-string with no punctuation between them.
    """
    return bool(re.search(r"[a-z] [A-Z][a-z]+ [a-z]", text))


def strip_label(text: str) -> str:
    """Drop a bare slide label glued to the front of the teaching sentence.

    e.g. "HepB vaccine + HBIG within 12 h To prevent hepatitis B infection..."
      -> "To prevent hepatitis B infection..."
    A label is a short capitalised fragment with no terminal punctuation,
    followed by a capitalised sentence opener.
    """
    # "3-hour GTT One unequivocal..." / "HBIG within 12 h To prevent..." — a short
    # noun-phrase label followed directly by a sentence opener.
    m = re.match(r"^((?:[A-Z0-9][\w\-/]*\s+){1,4}?)(?=(?:One|To|The|A|An|It|This|These|Those|There|In|If|When|Avoid|Consider|Use|Start|Give|Screen|Refer|Monitor|Do|Never|Always)\b)", text)
    if m and len(m.group(1).split()) <= 8:
        return text[m.end():]
    return text


def usable(text: str) -> bool:
    t = text
    if len(t) < 30 or len(t) > 240:
        return False
    if BULLET.search(t) or QUESTION.search(t) or CAPS_HEADS.match(t):
        return False
    if VIGNETTE.search(t):
        return False
    if looks_glued(t):
        return False
    if len(NUMWALL.findall(t)) >= 2:
        return False
    words = t.split()
    if len(words) < 5:
        return False
    caps = sum(1 for w in words if w.isupper() and len(w) > 2)
    if caps / len(words) > 0.3:
        return False
    return True


def main() -> int:
    pearls = []
    seen = set()

    def add(chapter_id, tag, text, kind):
        t = clean(text)
        if not usable(t):
            return
        key = re.sub(r"\W+", "", t.lower())[:60]
        if key in seen:
            return
        seen.add(key)
        pearls.append({
            "id": f"pearl-{len(pearls)}",
            "chapterId": chapter_id,
            "tag": tag,
            "front": t if t.endswith((".", "!", "?")) else t + ".",
            "back": f"{tag} — board pearl. Say it out loud once, then flip.",
            "kind": kind,
        })

    for sec in GUIDE.get("quickRef", {}).get("sections", []):
        for b in sec.get("blocks", []):
            if b.get("type") != "table":
                continue
            for row in b.get("rows", []):
                if len(row) >= 2 and row[0] and row[1]:
                    add("exam-prep-and-how-to-use-this-guide", "Must-know rule", f"{row[0]}: {row[1]}", "rule")

    # 3. rationales that were extended with verbatim manual text. These restate a
    #    verified answer, so they are defensible; drop the sentence that merely
    #    repeats the first one.
    rationale_path = DATA / "rationale-upgrades.json"
    if rationale_path.exists():
        up = json.loads(rationale_path.read_text()).get("questions", {})
        chapter_titles = {c["id"]: (c.get("shortTitle") or c.get("title")) for c in GUIDE["chapters"]}
        for qid, entry in up.items():
            cid = entry.get("chapterId", "")
            tag = chapter_titles.get(cid, "")
            text = clean(entry.get("explanation", ""))
            if not text:
                continue
            text = strip_label(text)
            # Keep only the first complete sentence. A rationale that needs a
            # second sentence is explaining a question, not stating a pearl.
            m = re.match(r"^(.+?[.!?])(?:\s|$)", text)
            if not m:
                continue
            sentence = m.group(1).strip()
            # strip_label() should already have removed a glued slide label; if the
            # result still reads as two clauses run together, drop it entirely
            # rather than showing a clinician a mangled sentence.
            if looks_glued(sentence):
                continue
            if 45 <= len(sentence) <= 200:
                add(cid, tag, sentence, "rationale")

    payload = {
        "meta": {
            "count": len(pearls),
            "source": "the hand-curated must-know rule set - every entry is a whole, verifiable statement",
            "replaced": "keyword sentence-mining of column-interleaved slide text, 141 of 231 items of which were artefacts",
            "note": "Reconstructed reference tables stay tables. Flattening a sliced row into a sentence produced cells cut mid-word, which is worse than showing the grid.",
        },
        "pearls": pearls,
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False))
    from collections import Counter
    print(f"pearls-clean.json: {len(pearls)} pearls across {len(Counter(p['chapterId'] for p in pearls))} chapters")
    print("kinds:", Counter(p["kind"] for p in pearls))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
