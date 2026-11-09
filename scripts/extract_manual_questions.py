#!/usr/bin/env python3
"""Extract multiple-choice questions from APEA manual text and infer answers from slide follow-up."""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "public/data/manuals.json"
MANUALS = ROOT / "public/data/manuals"
GUIDE = ROOT / "public/data/guide.json"
OUT = ROOT / "public/data/manual-questions.json"
OVERRIDES = ROOT / "public/data/manual-question-overrides.json"

QSTART = re.compile(r"QUESTION\s*#\s*(\d+)", re.I)
OPT = re.compile(r"^\s*(\d+)\.\s+(.+)$")
STOP = re.compile(r"^(CHECK YOUR KNOWLEDGE|EXAM CHECKLIST|©)\b", re.I)
SKIP_FOLLOW = re.compile(r"^(NOTES|CONTENT OVERVIEW)$", re.I)


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
    s = s.replace("$", "").replace("\x08", "")
    s = re.sub(r"©.*", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def is_slide_break(c: str) -> bool:
    if not c:
        return True
    if re.match(r"^[A-Z][A-Z\s&:/\-–]{10,}$", c):
        return True
    if re.search(r"\b(SENSITIVITY|SPECIFICITY):", c):
        return True
    return False


def score_option(option: str, corpus: str) -> float:
    o = option.lower()
    f = corpus.lower()
    if len(o) > 20 and o in f:
        return 60.0
    words = [w for w in re.findall(r"[a-z]{4,}", o)]
    if not words:
        return 0.0
    hit = sum(1.2 for w in words if w in f)
    bigrams = [f"{words[i]} {words[i + 1]}" for i in range(len(words) - 1)]
    hit += sum(2.5 for bg in bigrams if bg in f)
    # Negation penalties from teaching slides
    if re.search(r"\(not\s+[\w\s]{2,30}\)", f):
        for frag in re.findall(r"\(not\s+([\w\s]{2,30})\)", f):
            if frag.strip() in o:
                hit -= 4
    if "not mucus" in f and "mucous" in o:
        hit -= 5
    if "drug-disease" in o and "not considered" in o and "allergic" in f:
        hit -= 4
    if "always appears" in o and "24" in o:
        hit -= 2
    if "penicillin" in o and "cephalosporin" in o and ("antibiotics are a common cause" in f or "beta-lactam" in f):
        hit += 5
    if "rest and fluids" in o and "bronchitis" in f:
        hit += 4
    if "high sensitivity" in o and "screen" in f and "influenza" in f:
        hit += 3
    if "lobar infiltrate" in o and "pneumonia" in f:
        hit += 2
    if re.search(rf"\bnot\s+{re.escape(words[0])}\b", f) if words else False:
        hit -= 3
    # Boost first-line / common cause language near option drug names
    for w in words:
        if len(w) > 5 and re.search(rf"(first[- ]line|most common|preferred|treatment of choice).{{0,80}}{w}", f):
            hit += 3
    return hit / max(1, len(words) * 0.85)


def infer_correct(options: list[str], corpus: str) -> tuple[int | None, str, list[float]]:
    scores = [score_option(o, corpus) for o in options]
    if not scores:
        return None, "no-options", scores
    best = max(scores)
    if best < 0.32:
        return None, "low-confidence", scores
    ranked = sorted(enumerate(scores), key=lambda x: -x[1])
    tops = [i for i, s in enumerate(scores) if s >= best * 0.9]
    if len(tops) > 1:
        if ranked[0][1] - ranked[1][1] >= 0.22:
            return ranked[0][0], "inferred", scores
        return None, "ambiguous", scores
    return ranked[0][0], "inferred", scores


def read_multiline_option(lines: list[str], start: int) -> tuple[str, int]:
    om = OPT.match(lines[start])
    if not om:
        return "", start
    opt = clean(om.group(2))
    j = start + 1
    while j < len(lines):
        if QSTART.search(lines[j]) or OPT.match(lines[j]):
            break
        c = clean(lines[j])
        if not c:
            j += 1
            if j - start > 8:
                break
            continue
        if STOP.match(c) or c.startswith("Chapter ") or "FNP/AGPCNP" in c or is_slide_break(c):
            break
        if SKIP_FOLLOW.match(c):
            j += 1
            continue
        opt += " " + c
        j += 1
    return opt, j


def collect_follow(lines: list[str], start: int, max_chars: int = 14000) -> str:
    parts: list[str] = []
    j = start
    while j < len(lines):
        if QSTART.search(lines[j]):
            break
        c = clean(lines[j])
        if c and "FNP/AGPCNP" not in c and not c.startswith("Chapter "):
            if not SKIP_FOLLOW.match(c):
                parts.append(c)
        j += 1
        if len(" ".join(parts)) >= max_chars:
            break
    return " ".join(parts)


def guide_match(guide_questions: list[dict], stem: str, options: list[str]) -> tuple[int | None, str]:
    best = None
    best_r = 0.0
    for gq in guide_questions:
        if gq.get("correctIndex") is None or len(gq.get("options", [])) < 2:
            continue
        r = SequenceMatcher(None, stem[:160].lower(), gq["stem"][:160].lower()).ratio()
        if r < 0.46:
            continue
        if len(gq["options"]) == len(options):
            if r > best_r:
                best_r = r
                best = gq["correctIndex"]
        else:
            # Map by option text overlap
            go = [x.lower() for x in gq["options"]]
            for idx, opt in enumerate(options):
                if any(SequenceMatcher(None, opt.lower()[:50], g[:50]).ratio() > 0.7 for g in go):
                    if gq["options"][gq["correctIndex"]].lower()[:30] in opt.lower() or any(
                        SequenceMatcher(None, gq["options"][gq["correctIndex"]].lower(), opt.lower()).ratio() > 0.6
                        for _ in [0]
                    ):
                        if r > best_r:
                            best_r = r
                            best = idx
    expl = ""
    if best is not None:
        for gq in guide_questions:
            if gq.get("correctIndex") == best and SequenceMatcher(None, stem[:80], gq["stem"][:80]).ratio() > 0.5:
                expl = gq.get("explanation", "")
                break
    return best, expl


def extract_from_text(
    text: str,
    module_id: str,
    chapter_id: str,
    chapter_title: str,
    guide_questions: list[dict],
) -> list[dict]:
    lines = text.splitlines()
    out: list[dict] = []
    i = 0
    while i < len(lines):
        m = QSTART.search(lines[i])
        if not m:
            i += 1
            continue
        qnum = m.group(1)
        q_start_line = i
        i += 1
        stem_parts: list[str] = []
        options: list[str] = []
        while i < len(lines):
            line = lines[i]
            if QSTART.search(line):
                break
            if STOP.match(clean(line)):
                break
            if OPT.match(line):
                opt, i = read_multiline_option(lines, i)
                if opt:
                    options.append(opt)
                continue
            c = clean(line)
            if c and not c.startswith("Chapter ") and "FNP/AGPCNP" not in c:
                if options:
                    break
                if len(c) > 6 and not SKIP_FOLLOW.match(c):
                    stem_parts.append(c)
            i += 1
        stem = " ".join(stem_parts).strip()
        if len(options) < 2 or len(stem) < 12:
            continue
        follow = collect_follow(lines, i)
        char_off = sum(len(lines[k]) + 1 for k in range(q_start_line))
        global_ctx = collect_follow(lines, i) + " " + text[char_off : char_off + 18000]

        corpus = f"{stem} {follow} {global_ctx}"
        correct_index, method, _ = infer_correct(options, corpus)
        expl = follow[:650] + ("…" if len(follow) > 650 else "")

        if correct_index is None:
            g_idx, g_expl = guide_match(guide_questions, stem, options)
            if g_idx is not None:
                correct_index = g_idx
                method = "guide-match"
                if g_expl:
                    expl = g_expl[:650]

        if not expl.strip() or expl.startswith("NOTES"):
            expl = "Review the matching section in the original course manual slide."

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


def rescore_with_manual(questions: list[dict], manual_text: str) -> int:
    fixed = 0
    for q in questions:
        if q["correctIndex"] is not None:
            continue
        needle = q["stem"][: min(60, len(q["stem"]))].lower()
        pos = manual_text.lower().find(needle)
        window = manual_text[pos : pos + 14000] if pos >= 0 else manual_text[:20000]
        idx, method, _ = infer_correct(q["options"], window)
        if idx is not None and method == "inferred":
            q["correctIndex"] = idx
            q["grading"] = "corpus-rescore"
            fixed += 1
    return fixed


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

    by_ch = {ch["id"]: ch.get("questions", []) for ch in guide["chapters"]}
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
        raw = path.read_text()
        extracted = extract_from_text(
            raw,
            mid,
            chapter_id,
            short_title(chapter_id, guide),
            by_ch.get(chapter_id, []),
        )
        rescore_with_manual(extracted, raw)
        all_q.extend(extracted)

    apply_overrides(all_q, overrides)
    graded = sum(1 for q in all_q if q["correctIndex"] is not None)
    by_method = {}
    for q in all_q:
        by_method[q["grading"]] = by_method.get(q["grading"], 0) + 1
    payload = {
        "meta": {
            "total": len(all_q),
            "graded": graded,
            "methods": by_method,
            "source": "APEA course manual slide questions",
        },
        "questions": all_q,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"Wrote {OUT}: total={len(all_q)} graded={graded} ({graded*100//max(1,len(all_q))}%) methods={by_method}")


if __name__ == "__main__":
    main()
