#!/usr/bin/env python3
"""Give every graded question a rationale worth reading.

178 of 277 study-guide questions shipped with a one-line "answer, restated"
rationale (e.g. "Iron deficiency."). That reads as filler to an experienced
clinician and is the single fastest way to lose their trust.

This pass builds an evidence-backed rationale from the manual text:

  * locate the best supporting passage for the question in the manual .md
  * when a usable passage exists, write:
        <existing one-liner>  <supporting sentence(s) from the manual>
    and cite the manual section
  * never invent clinical content — if no supporting text is found, the
    rationale is left exactly as it was

Writes public/data/rationale-upgrades.json  (applied at runtime).
"""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "public/data"
MANUALS = DATA / "manuals"
OUT = DATA / "rationale-upgrades.json"

GUIDE = json.loads((DATA / "guide.json").read_text())
STOP = set(
    """a an the of and or to in on for with is are was were be been being which what who whom
    whose this that these those it its as at by from than then there their they you your
    patient patients following statement true false best next most likely should would could
    can may not no all of""".split()
)


def terms(text: str) -> set:
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower()) if w not in STOP}


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text))
    return [p.strip() for p in parts if 40 <= len(p.strip()) <= 400]


def manual_text_for(chapter_number: int) -> str:
    num = chapter_number + 1
    for p in MANUALS.glob(f"{num:02d}-*.md"):
        return p.read_text()
    return ""


NOISE = re.compile(
    r"(QUESTION\s*#|^\d+\.\s|CHECK YOUR KNOWLEDGE|EXAM CHECKLIST|CONTENT OVERVIEW|"
    r"NOTES$|©|\bFNP/AGPCNP\b)",
    re.I,
)


def is_clean(sentence: str) -> bool:
    """A sentence a clinician would accept as a citation."""
    s = sentence.strip()
    if NOISE.search(s):
        return False
    if not re.search(r"[.!?]$", s):
        return False
    words = s.split()
    if len(words) < 7 or len(words) > 55:
        return False
    if not s[0].isalpha() or s[0].islower():
        return False
    # "$" is a bullet artefact in these extracts; long runs of caps are slide titles
    if "$" in s or re.search(r"[A-Z]{4,}(?:\s+[A-Z]{2,}){2,}", s):
        return False
    # reject label chains like "A B C D" with no verb-ish structure
    if len(re.findall(r"[:•]", s)) >= 2:
        return False
    if re.search(r"\?\s*$", s):
        return False
    if not re.search(r"\b(is|are|was|were|has|have|can|may|should|must|needs?|causes?|"
                     r"indicates?|requires?|avoid|use|used|given|give|occurs?|"
                     r"associated|recommended|consider|treat|screen|monitor)\b", s, re.I):
        return False
    return True


def best_support(question: dict, corpus: str, top: int = 2) -> list[str]:
    """Sentences from the manual that actually discuss this question."""
    correct = question["options"][question["correctIndex"]]
    q_terms = terms(question["stem"]) | terms(correct)
    if not q_terms:
        return []
    scored = []
    for s in sentences(corpus):
        if not is_clean(s):
            continue
        # never cite a sentence that duplicates the question itself
        if SequenceMatcher(None, s.lower()[:120], question["stem"].lower()[:120]).ratio() > 0.7:
            continue
        overlap = len(q_terms & terms(s))
        if overlap < 2:
            continue
        bonus = 2.5 if terms(correct) and len(terms(correct) & terms(s)) >= max(1, len(terms(correct)) // 2) else 0
        score = overlap + bonus
        if score >= 3:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    picked = []
    for _, s in scored[:8]:
        if any(SequenceMatcher(None, s.lower(), p.lower()).ratio() > 0.75 for p in picked):
            continue
        # drop a sentence that says the same thing as another picked one
        if any(
            len(terms(s) & terms(p)) / max(1, len(terms(s) | terms(p))) > 0.55
            for p in picked
        ):
            continue
        picked.append(s)
        if len(picked) >= top:
            break
    return picked


def main() -> int:
    upgrades = {}
    enriched = 0
    for ch in GUIDE["chapters"]:
        corpus = manual_text_for(ch["number"])
        if not corpus:
            continue
        for q in ch["questions"]:
            existing = (q.get("explanation") or "").strip()
            if len(existing) >= 110:
                continue  # already substantive
            support = best_support(q, corpus)
            if not support:
                continue
            body = " ".join(support)
            # A support sentence must add real information, not echo the stem.
            if SequenceMatcher(None, body.lower()[:100], q["stem"].lower()[:100]).ratio() > 0.6:
                continue
            # Skip support that merely restates the existing one-liner.
            if existing:
                ex = existing.rstrip(".").lower()
                if ex and (
                    SequenceMatcher(None, ex, body.lower()[: len(ex) + 20]).ratio() > 0.72
                    or len(terms(ex) & terms(body)) / max(1, len(terms(ex) | terms(body))) > 0.5
                ):
                    continue
            combined = f"{existing} {body}".strip() if existing else body
            # drop dangling bullets / numbered artifacts at the seam
            combined = re.sub(r"\s*[•]\s*", " ", combined)
            combined = re.sub(r"\s+", " ", combined).strip()
            if len(combined) <= len(existing) + 45:
                continue
            upgrades[q["id"]] = {
                "explanation": combined,
                "support": support,
                "chapterId": ch["id"],
            }
            enriched += 1

    payload = {
        "meta": {
            "enriched": enriched,
            "note": "Rationales extended with verbatim supporting sentences from the course manuals.",
        },
        "questions": upgrades,
    }
    OUT.write_text(json.dumps(payload, indent=1))
    print(f"rationale-upgrades.json: enriched {enriched} of {sum(1 for c in GUIDE['chapters'] for q in c['questions'] if len((q.get('explanation') or '')) < 110)} thin rationales")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
