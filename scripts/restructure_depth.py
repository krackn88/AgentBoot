#!/usr/bin/env python3
"""Restructure "manual depth" around content that survived extraction cleanly.

Reality of the source: the PDF slide extracts are mostly visual-line fragments
(only ~3% of paragraphs are complete sentences). Presenting those as "teaching
text" reads like noise to an experienced clinician. What *did* survive cleanly,
and is genuinely hard to find elsewhere:

  * 165 tables reconstructed from column geometry (headers + real cells)
  * complete high-signal statements: TIP / O (observation) / dosing / criteria lines
  * clinical pearls already scored by enrich_from_manuals.py

This pass writes, per module:
  * reference.tables      - reconstructed tables, deduped, ordered by confidence
  * reference.statements  - complete standalone clinical statements
  * reference.fragments   - raw leftover lines (kept, but labelled honestly)

Run after rebuild_tables.py and reflow_depth.py.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "public/data"
MODULES = DATA / "modules"

TERMINAL = re.compile(r"[.!?]$")
NOISE = re.compile(r"(NOTES$|CONTENT OVERVIEW|CHECK YOUR KNOWLEDGE|EXAM CHECKLIST)", re.I)
# Lines that stand on their own and carry a teaching point.
HIGH_SIGNAL = re.compile(
    r"^(?:TIP|PEARL|NOTE|O|AVOID|NEVER|ALWAYS|FIRST[- ]LINE|REFER|"
    r"GOLD STANDARD|RULE \d|DO NOT|CONSIDER|PREFERRED|CRITERIA)\b", re.I
)
CLINICAL = re.compile(
    r"\b(?:mg|mcg|mL|mEq|IU|kg|first[- ]line|contraindicat|black box|"
    r"gold standard|diagnos|criteria|refer|sensitivity|specificity|"
    r"therapeutic|prophyla|monitor|screen)\b", re.I
)
DANGLING = re.compile(r"^[a-z]\)|^is available\.?$|^benefits$", re.I)


def clean(text: str) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    t = re.sub(r"\s*(?:NOTES|CONTENT OVERVIEW)\s*$", "", t, flags=re.I).strip()
    return t


def is_complete(text: str) -> bool:
    """A statement we would be comfortable showing a clinician as-is."""
    t = text.strip()
    if len(t) < 45 or len(t) > 320:
        return False
    if not TERMINAL.search(t):
        return False
    words = t.split()
    if len(words) < 8:
        return False
    # reject lines that clearly start mid-word / mid-clause
    if t[0].islower() or DANGLING.match(t):
        return False
    if NOISE.search(t):
        return False
    return True


def table_fingerprint(tab: dict) -> str:
    return "|".join(tab.get("headers", [])) + "::" + json.dumps(tab.get("rows", [])[:2])


def dedupe_tables(tables: list) -> list:
    seen = set()
    out = []
    for t in tables:
        if not t.get("rows"):
            continue
        fp = table_fingerprint(t)
        if fp in seen:
            continue
        seen.add(fp)
        out.append(t)
    out.sort(key=lambda t: (-round(t.get("confidence", 0), 1), -len(t.get("rows", []))))
    return out


def main() -> int:
    files = sorted(MODULES.glob("*.json"))
    # tables come straight from the column-geometry rebuild, independent of reflow
    all_tables = {}
    tpath = DATA / "manual-tables.json"
    if tpath.exists():
        all_tables = json.loads(tpath.read_text())

    totals = {"tables": 0, "statements": 0, "fragments": 0}
    for path in files:
        mod = json.loads(path.read_text())

        statements = []
        fragments = []
        for sec in mod.get("sections", []):
            for b in sec.get("blocks", []):
                if b.get("type") != "p":
                    continue
                t = clean(b.get("text"))
                if not t:
                    continue
                # Only single lines that already read as a complete clinical
                # statement. Never join fragments — a joined fragment is exactly
                # the kind of half-sentence that erodes trust.
                if is_complete(t) and (HIGH_SIGNAL.match(t) or len(t) > 70 or CLINICAL.search(t)):
                    statements.append(t)
                elif len(t) > 12:
                    fragments.append(t)

        # dedupe statements, preserve order
        seen = set()
        uniq = []
        for s in statements:
            k = s.lower()
            if k in seen:
                continue
            seen.add(k)
            uniq.append(s)

        mod["reference"] = {
            "tables": dedupe_tables(all_tables.get(mod.get("chapterId"), [])),
            "statements": uniq,
            "fragments": fragments,
        }
        # the flattened tables list is now redundant
        mod.pop("tables", None)
        meta = mod.setdefault("meta", {})
        meta["table_count"] = len(mod["reference"]["tables"])
        meta["statement_count"] = len(uniq)
        meta["fragment_count"] = len(fragments)

        totals["tables"] += len(mod["reference"]["tables"])
        totals["statements"] += len(uniq)
        totals["fragments"] += len(fragments)

        path.write_text(json.dumps(mod, separators=(",", ":")))

    print(
        f"restructured {len(files)} modules · {totals['tables']} tables · "
        f"{totals['statements']} verifiable statements · {totals['fragments']} raw fragments kept"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
