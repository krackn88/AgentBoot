#!/usr/bin/env python3
"""Post-extraction quality pass.

Produces public/data/question-quality.json — an overlay the app applies at runtime so
content rebuilds (content:build) never clobber it.

  * drops slide-header debris that bled into answer options
  * flags manual-slide questions that duplicate a study-guide question (same stem)
  * attaches a source anchor (manual module + section) to every question
"""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "public/data"
OUT = DATA / "question-quality.json"

# Trailing slide titles that ran into option text during PDF extraction.
HEADER_TAIL = re.compile(
    r"[\s.]*(?:Hives vs\.? Morbilliform Rash|-Line Treatment(?: Nonpregnant)?|"
    r"Cryopreservation of sperm|Ottawa Knee Rules|Cryopreservation|"
    r"[A-Z][A-Za-z]+(?: [A-Za-z]+){0,4}\s+(?:Rules|Rash|Treatment|Sperm))\s*$"
)
SENTENCE_END = re.compile(r"(?:[.?!])\s*$")


def clean_option(text: str) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    t = re.sub(r"\s*•\s*", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > 110 and HEADER_TAIL.search(t):
        t = HEADER_TAIL.sub("", t).strip()
    # Strip a dangling bullet fragment like "imaging! Follow the rules" tails
    t = re.sub(r"\s*(?:•|—)\s*[A-Z][a-z]+(?: [a-z]+){0,3}\.?$", "", t).strip()
    return t


def truncate_contaminated(options: list[str]) -> list[str]:
    """Slide titles/body often ran into the last option during extraction.

    Real options in this bank are short. If one option is far longer than its
    siblings, keep only the leading clinical phrase.
    """
    lens = sorted(len(o) for o in options if o)
    if not lens:
        return options
    median = lens[len(lens) // 2]
    cap = max(90, int(median * 1.8))
    out = []
    for o in options:
        if len(o) > cap:
            # 1) a sentence end followed by a capitalized slide title
            m = re.search(r"[.?!]\s+[A-Z]", o)
            if m and m.start() >= 24:
                o = o[: m.start() + 1].strip()
            else:
                # 2) lowercase word immediately followed by a capitalized run
                m2 = re.search(r"(?<=[a-z\)]) (?=[A-Z])", o)
                if m2 and m2.start() >= 12:
                    o = o[: m2.start()].strip()
                    if o and o[-1] not in ".?!":
                        o += "."
                else:
                    o = o[:cap].rsplit(" ", 1)[0].strip()
                    if o and o[-1] not in ".?!":
                        o += "."
        out.append(o.strip())
    # Final guard: nothing in this bank is a paragraph. Hard-cap at 200 chars.
    return [o if len(o) <= 200 else o[:200].rsplit(" ", 1)[0].rstrip(".,;:") + "." for o in out]


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower())


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


STOP = set(
    """a an the of and or to in on for with is are was were be been being which what who whom whose
    this that these those it its as at by from than then there their they you your patient patients
    following statement true false best next most likely should would could can may""".split()
)


def terms(text: str) -> set:
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower()) if w not in STOP}


def load(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def main() -> int:
    guide = load(DATA / "guide.json", {})
    manual = load(DATA / "manual-questions.json", {})
    guide_qs = [q for c in guide.get("chapters", []) for q in c.get("questions", [])]
    manual_qs = manual.get("questions", [])

    modules = {}
    for p in sorted((DATA / "modules").glob("*.json")):
        mod = load(p, {})
        if mod:
            modules[mod.get("chapterId")] = mod

    # --- 1. option cleanup -------------------------------------------------
    fixed = {}
    dirty_count = 0
    for q in guide_qs + manual_qs:
        new_opts = truncate_contaminated([clean_option(o) for o in q.get("options", [])])
        if new_opts != q.get("options", []):
            dirty_count += 1
            fixed[q["id"]] = {"options": new_opts}

    # --- 2. duplicate detection (manual vs guide) ---------------------------
    duplicates = {}
    for mq in manual_qs:
        m_norm = norm(mq.get("stem", ""))
        best = (0.0, None)
        for gq in guide_qs:
            if gq.get("chapterId") != mq.get("chapterId"):
                continue
            r = SequenceMatcher(None, m_norm, norm(gq.get("stem", ""))).ratio()
            if r > best[0]:
                best = (r, gq)
        if best[0] >= 0.80:
            duplicates[mq["id"]] = {"dupOf": best[1]["id"], "similarity": round(best[0], 3)}

    # --- 3. source anchors -------------------------------------------------
    anchors = {}
    for q in guide_qs + manual_qs:
        mod = modules.get(q.get("chapterId"))
        if not mod:
            continue
        target = terms(q.get("stem", "")) | terms(
            q.get("options", [])[q["correctIndex"]] if isinstance(q.get("correctIndex"), int)
            and q.get("correctIndex") < len(q.get("options", [])) else ""
        )
        best = (0.0, None)
        for sec in mod.get("sections", []):
            body = " ".join(
                b.get("text", "")
                if b.get("type") == "p"
                else " ".join(b.get("items", []))
                if b.get("type") in ("list", "manual-list")
                else " ".join(" ".join(r) for r in b.get("rows", []))
                for b in sec.get("blocks", [])
            )
            score = jaccard(target, terms(body + " " + sec.get("title", "")))
            if score > best[0]:
                best = (score, sec)
        if best[1] and best[0] >= 0.08:
            anchors[q["id"]] = {
                "manualId": mod.get("manualId"),
                "manualTitle": mod.get("manualTitle") or mod.get("title"),
                "section": best[1].get("title"),
                "score": round(best[0], 3),
            }

    payload = {
        "meta": {
            "generated": __import__("datetime").datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "optionsCleaned": dirty_count,
            "duplicates": len(duplicates),
            "anchored": len(anchors),
            "guideQuestions": len(guide_qs),
            "manualQuestions": len(manual_qs),
        },
        "options": fixed,
        "duplicates": duplicates,
        "anchors": anchors,
    }
    OUT.write_text(json.dumps(payload, indent=1))
    print(
        f"question-quality.json: {dirty_count} options cleaned · {len(duplicates)} duplicates flagged · "
        f"{len(anchors)} source anchors"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
