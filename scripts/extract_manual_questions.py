#!/usr/bin/env python3
"""Extract multiple-choice questions from APEA manual text and infer answers from slide follow-up."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "public/data/manuals.json"
MANUALS = ROOT / "public/data/manuals"
GUIDE = ROOT / "public/data/guide.json"
OUT = ROOT / "public/data/manual-questions.json"
OVERRIDES = ROOT / "public/data/manual-question-overrides.json"

QSTART = re.compile(r"QUESTION\s*#\s*(\d+)", re.I)
OPT = re.compile(r"^\s*(\d+)\.\s+(.+)$")
STOP = re.compile(r"^(QUESTION|CHECK YOUR KNOWLEDGE|EXAM CHECKLIST|©)", re.I)


def chapter_id_for_module(module_id: str, guide: dict) -> str | None:
    try:
        num = int(module_id) - 1
    except ValueError:
        return None
    for ch in guide["chapters"]:
        if ch.get("number") == num:
            return ch["id"]
    return None


def short_title(chapter_id: str, guide: dict) -> str:
    for ch in guide["chapters"]:
        if ch["id"] == chapter_id:
            return ch["shortTitle"]
    return chapter_id


def clean(s: str) -> str:
    s = re.sub(r"\s+", " ", s.replace("$", "").replace("\x08", "")).strip()
    return s


def score_option(option: str, follow: str) -> float:
    o = option.lower()
    f = follow.lower()
    if o in f:
        return 50.0
    words = [w for w in re.findall(r"[a-z]{4,}", o)]
    if not words:
        return 0.0
    hit = sum(1 for w in words if w in f)
    # Bigrams from option
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]
    hit += sum(2 for bg in bigrams if bg in f)
    return hit / max(1, len(words))


def infer_correct(options: list[str], follow: str) -> tuple[int | None, str]:
    scores = [score_option(o, follow) for o in options]
    if not scores:
        return None, "no-options"
    best = max(scores)
    if best < 0.45:
        return None, "low-confidence"
    tops = [i for i, s in enumerate(scores) if s >= best - 0.05]
    if len(tops) > 1:
        return None, "ambiguous"
    return tops[0], "inferred"


def extract_from_text(text: str, module_id: str, chapter_id: str, chapter_title: str) -> list[dict]:
    lines = text.splitlines()
    out: list[dict] = []
    i = 0
    while i < len(lines):
        m = QSTART.search(lines[i])
        if not m:
            i += 1
            continue
        qnum = m.group(1)
        i += 1
        stem_parts: list[str] = []
        options: list[str] = []
        while i < len(lines):
            line = lines[i]
            if QSTART.search(line) or STOP.match(clean(line)):
                break
            om = OPT.match(line)
            if om:
                options.append(clean(om.group(2)))
                i += 1
                continue
            c = clean(line)
            if c and not c.startswith("Chapter ") and "FNP/AGPCNP" not in c:
                if options:
                    break
                if len(c) > 8:
                    stem_parts.append(c)
            i += 1
        stem = " ".join(stem_parts).strip()
        if len(options) < 2 or len(stem) < 15:
            continue
        follow_lines: list[str] = []
        j = i
        while j < len(lines) and j < i + 80:
            if QSTART.search(lines[j]) or STOP.match(clean(lines[j])):
                break
            c = clean(lines[j])
            if c and "FNP/AGPCNP" not in c and not c.startswith("Chapter "):
                follow_lines.append(c)
            j += 1
        follow = " ".join(follow_lines)
        correct_index, method = infer_correct(options, follow)
        expl = follow[:500] + ("…" if len(follow) > 500 else "")
        if not expl:
            expl = "Review the matching section in the original course manual."
        out.append(
            {
                "id": f"manual-{module_id}-q{qnum}",
                "chapterId": chapter_id,
                "chapterTitle": chapter_title,
                "source": "manual",
                "moduleId": module_id,
                "n": int(qnum),
                "stem": stem,
                "options": options[:6],
                "correctIndex": correct_index,
                "explanation": expl,
                "grading": method,
            }
        )
    return out


def apply_overrides(questions: list[dict], overrides: dict) -> None:
    by_id = {q["id"]: q for q in questions}
    for item in overrides.get("set", []):
        q = by_id.get(item["id"])
        if q:
            q["correctIndex"] = item["correctIndex"]
            q["grading"] = "override"
            if item.get("explanation"):
                q["explanation"] = item["explanation"]


def main():
    guide = json.loads(GUIDE.read_text())
    manifest = json.loads(MANIFEST.read_text())
    overrides = {}
    if OVERRIDES.exists():
        overrides = json.loads(OVERRIDES.read_text())

    all_q: list[dict] = []
    for mod in manifest["modules"]:
        mid = mod["id"]
        if mid == "01":
            continue
        chapter_id = chapter_id_for_module(mid, guide)
        if not chapter_id:
            continue
        path = MANUALS / Path(mod["text_file"]).name
        if not path.exists():
            continue
        extracted = extract_from_text(path.read_text(), mid, chapter_id, short_title(chapter_id, guide))
        all_q.extend(extracted)

    apply_overrides(all_q, overrides)
    graded = sum(1 for q in all_q if q["correctIndex"] is not None)
    payload = {
        "meta": {"total": len(all_q), "graded": graded, "source": "APEA course manual slide questions"},
        "questions": all_q,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"Wrote {OUT}: total={len(all_q)} graded={graded} ({graded*100//max(1,len(all_q))}%)")


if __name__ == "__main__":
    main()
