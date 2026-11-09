#!/usr/bin/env python3
"""Reflow the extracted "manual depth" into readable blocks.

The PDF extractor emitted one block per visual line, so most of the depth tab was
sentences chopped mid-thought ("NEVER give; risks always outweigh" / "benefits").
This pass joins those runs back together:

  * short lines that read as discrete items -> a single bullet list
  * short lines that are sentence continuations -> merged into one paragraph
  * real paragraphs are left untouched

Also attaches reconstructed reference tables (manual-tables.json) to each module.

Runs after enrich_from_manuals.py; safe to re-run.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "public/data"
MODULES = DATA / "modules"

TERMINAL = re.compile(r"[.!?:;)\]]$")
BULLET_START = re.compile(r"^[\u2022\u2022\-–]\s*")
SHORT = 95


def is_listish(text: str) -> bool:
    """A line that reads as a discrete item rather than running prose."""
    t = text.strip()
    if not t:
        return False
    if BULLET_START.match(t):
        return True
    if len(t) > SHORT:
        return False
    if re.fullmatch(r"[\w\s.,\-\u2013\u2014/()%×°'’\":+]{1,90}", t) and not TERMINAL.search(t):
        return True
    return False


def reflow_section(blocks: list) -> list:
    out = []
    para = []
    items = []

    def flush_para():
        nonlocal para
        if para:
            text = re.sub(r"\s+", " ", " ".join(para)).strip()
            if text:
                out.append({"type": "p", "text": text})
            para = []

    def flush_items():
        nonlocal items
        if items:
            cleaned = [re.sub(r"\s+", " ", i).strip() for i in items if i.strip()]
            if cleaned:
                out.append({"type": "manual-list", "items": cleaned})
            items = []

    for b in blocks:
        if b.get("type") != "p":
            flush_para()
            flush_items()
            out.append(b)
            continue

        text = (b.get("text") or "").strip()
        if not text:
            continue

        if is_listish(text):
            if para and len(para) > 1:
                flush_para()
            items.append(BULLET_START.sub("", text))
            continue

        if items:
            flush_items()
        para.append(text)
        if len(text) >= SHORT and TERMINAL.search(text):
            flush_para()

    flush_para()
    flush_items()
    return out


def main() -> int:
    tables = {}
    tpath = DATA / "manual-tables.json"
    if tpath.exists():
        tables = json.loads(tpath.read_text())

    files = sorted(MODULES.glob("*.json"))
    for path in files:
        mod = json.loads(path.read_text())
        before = sum(len(s.get("blocks", [])) for s in mod.get("sections", []))
        for sec in mod.get("sections", []):
            sec["blocks"] = reflow_section(sec.get("blocks", []))
        after = sum(len(s.get("blocks", [])) for s in mod.get("sections", []))
        if mod.get("chapterId") in tables:
            mod["tables"] = tables[mod["chapterId"]]
        meta = mod.setdefault("meta", {})
        meta["reflowed"] = True
        meta["blocks_before_reflow"] = before
        meta["blocks_after_reflow"] = after
        meta["table_count"] = len(mod.get("tables", []))
        path.write_text(json.dumps(mod, separators=(",", ":")))

    tb = ta = 0
    for path in files:
        m = json.loads(path.read_text())
        tb += m["meta"].get("blocks_before_reflow", 0)
        ta += m["meta"].get("blocks_after_reflow", 0)
    print(f"reflow: {len(files)} modules · blocks {tb} -> {ta} "
          f"({100 - ta / max(1, tb) * 100:.0f}% consolidation)")
    print(f"tables attached: {sum(len(json.loads(p.read_text()).get('tables', [])) for p in files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
