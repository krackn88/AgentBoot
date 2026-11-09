#!/usr/bin/env python3
"""Merge high-confidence guide→manual answer mappings into manual-question-overrides.json."""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "public/data/guide.json"
MANUAL = ROOT / "public/data/manual-questions.json"
OVERRIDES = ROOT / "public/data/manual-question-overrides.json"

CHAPTER_BY_NUM = {}


def norm(s: str) -> str:
    s = re.sub(r"\s+", " ", s.lower())
    s = re.sub(r"[^\w\s]", "", s)
    return s


def map_correct_index(guide_correct: str, manual_options: list[str]) -> int | None:
    g = norm(guide_correct)
    best_i, best_r = None, 0.0
    for i, opt in enumerate(manual_options):
        o = norm(opt)
        r = SequenceMatcher(None, g[:80], o[:80]).ratio()
        if g in o or o in g:
            r = max(r, 0.92)
        # first few words
        gw = g.split()[:4]
        if gw and all(w in o for w in gw if len(w) > 3):
            r = max(r, 0.75)
        if r > best_r:
            best_r = r
            best_i = i
    return best_i if best_r >= 0.52 else None


def main():
    guide = json.loads(GUIDE.read_text())
    manual = json.loads(MANUAL.read_text())
    overrides = json.loads(OVERRIDES.read_text()) if OVERRIDES.exists() else {"set": []}
    existing = {x["id"] for x in overrides.get("set", [])}

    by_ch = {ch["id"]: ch.get("questions", []) for ch in guide["chapters"]}
    added = []
    for mq in manual["questions"]:
        if mq.get("correctIndex") is not None or mq["id"] in existing:
            continue
        gqs = by_ch.get(mq["chapterId"], [])
        best_gq, best_r = None, 0.0
        for gq in gqs:
            if gq.get("correctIndex") is None or len(gq.get("options", [])) < 2:
                continue
            r = SequenceMatcher(None, norm(mq["stem"][:140]), norm(gq["stem"][:140])).ratio()
            if r > best_r:
                best_r = r
                best_gq = gq
        if not best_gq or best_r < 0.43:
            continue
        g_corr = best_gq["options"][best_gq["correctIndex"]]
        idx = map_correct_index(g_corr, mq["options"])
        if idx is None and len(mq["options"]) == len(best_gq["options"]):
            idx = best_gq["correctIndex"]
        if idx is None:
            continue
        entry = {
            "id": mq["id"],
            "correctIndex": idx,
            "explanation": (best_gq.get("explanation") or "")[:500],
            "source": f"guide-sync r={best_r:.2f}",
        }
        overrides["set"].append(entry)
        existing.add(mq["id"])
        added.append(entry)
        print(f"+ {mq['id']} → {idx} (guide r={best_r:.2f})")

    OVERRIDES.write_text(json.dumps(overrides, ensure_ascii=False, indent=2) + "\n")
    print(f"Added {len(added)} overrides → {OVERRIDES}")


if __name__ == "__main__":
    main()
