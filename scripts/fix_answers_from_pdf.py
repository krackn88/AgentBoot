#!/usr/bin/env python3
"""Repair contaminated answer options using the PDFs' clean text layer.

The markdown pipeline often glued slide body text onto an answer choice:

    "Hearing loss may become permanent. Auditory Emergency Refer to ENT or ER for: He…"

The PDF text layer contains the same option *without* that trailing noise, because
it is positioned as a discrete cell. When a PDF option is a clean prefix (or close
superset) of a contaminated bank answer, this pass rewrites the bank answer from
the PDF and marks it verified — the PDF is the authoritative print source.

Only touches answers whose current text is longer than the PDF's, so a short
correct answer can never be replaced by a longer, noisier one.

Writes public/data/answer-fixes.json  (applied as an overlay at runtime).
"""
import glob
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "public/data"
OUT = DATA / "answer-fixes.json"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()


FOOTER = re.compile(r"\s*\d*\s*FNP/AGPCNP Review\s*$", re.I)


def main() -> int:
    manual = json.loads((DATA / "manual-questions.json").read_text())["questions"]
    by_stem = {}
    for q in manual:
        by_stem.setdefault(norm(q["stem"])[:80], q)

    pdf_questions = []
    for path in sorted(glob.glob(str(DATA / "pdf-extract" / "*.json"))):
        if path.endswith("_summary.json"):
            continue
        doc = json.loads(Path(path).read_text())
        for pq in doc.get("questions", []):
            pdf_questions.append((doc["chapterId"], pq))

    fixes = {}
    for cid, pq in pdf_questions:
        key = norm(pq["stem"])[:80]
        q = by_stem.get(key)
        if not q:
            best, ratio = None, 0.0
            for cand in manual:
                r = SequenceMatcher(None, key, norm(cand["stem"])[:80]).ratio()
                if r > ratio:
                    ratio, best = r, cand
            if ratio < 0.9:
                continue
            q = best
        if q is None or q.get("correctIndex") is None:
            continue
        if len(pq.get("options", [])) < 2:
            continue

        bank = q["options"][q["correctIndex"]]
        bank_n = norm(bank)
        if len(bank_n) < 8:
            continue

        best_opt, best_len = None, 0
        for opt in pq["options"]:
            opt_clean = FOOTER.sub("", opt).strip()
            opt_n = norm(opt_clean)
            if len(opt_n) < 8 or len(opt_n) > len(bank_n):
                # never replace with something longer - that is how contamination grows
                continue
            # the PDF option must be the head of the bank text, or near-identical
            if bank_n.startswith(opt_n) and len(opt_n) >= len(bank_n) * 0.4:
                if len(opt_n) > best_len:
                    best_opt, best_len = opt_clean, len(opt_n)
            elif opt_n == bank_n:
                best_opt, best_len = opt_clean, len(opt_n)

        # the replacement must itself look like a clean answer choice, not slide text
        if best_opt:
            clean_candidate = (
                len(best_opt) <= 90
                and not re.search(r"\b(TIP|NOTES|QUESTION)\b", best_opt, re.I)
                and best_opt.count("•") == 0
                and "  " not in best_opt
            )
        else:
            clean_candidate = False
        if clean_candidate and best_len >= 12 and best_len < len(bank_n) - 8:
            fixes[q["id"]] = {
                "from": bank,
                "to": best_opt,
                "chapterId": cid,
                "why": "PDF text layer holds this option without the slide text the markdown pipeline glued on",
            }

    payload = {
        "meta": {
            "count": len(fixes),
            "source": "answer choices re-read from the PDF text layer",
        },
        "fixes": fixes,
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False))
    print(f"answer-fixes.json: repaired {len(fixes)} contaminated answers from the PDFs")
    for k, v in list(fixes.items())[:5]:
        print(f"  {k}\n    was: {v['from'][:70]}\n    now: {v['to'][:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
