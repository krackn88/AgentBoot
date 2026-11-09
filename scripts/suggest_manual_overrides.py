#!/usr/bin/env python3
"""Print high-margin ambiguous/low-confidence manual questions for override curation."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from extract_manual_questions import score_option, collect_follow, read_multiline_option  # noqa: E402

DATA = ROOT / "public/data/manual-questions.json"


def main():
    data = json.loads(DATA.read_text())
    for q in data["questions"]:
        if q["correctIndex"] is not None:
            continue
        scores = [score_option(o, q.get("explanation", "") + " " + q["stem"]) for o in q["options"]]
        if not scores:
            continue
        ranked = sorted(enumerate(scores), key=lambda x: -x[1])
        margin = ranked[0][1] - ranked[1][1] if len(ranked) > 1 else ranked[0][1]
        if margin < 0.15:
            continue
        print(
            q["id"],
            f"margin={margin:.2f}",
            f"suggest={ranked[0][0]}",
            q["options"][ranked[0][0]][:55],
        )


if __name__ == "__main__":
    main()
