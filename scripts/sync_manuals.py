#!/usr/bin/env python3
"""Mirror all extracted APEA manual text + metadata from the dedi into public/data.

The original page-accurate PDFs remain on the dedi (1.2 GB) and are linked/embedded
directly so builds stay small. The complete searchable text corpus is versioned here.
"""
import json
import urllib.request
from pathlib import Path, PurePosixPath

BASE = "https://giftr.duckdns.org/apea/2026-fnp-manuals"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "data"
TEXT_OUT = OUT / "manuals"
TEXT_OUT.mkdir(parents=True, exist_ok=True)


def get(path):
    with urllib.request.urlopen(f"{BASE}/{path}", timeout=90) as response:
        return response.read()


manifest = json.loads(get("manifest.json"))
fields = ("id", "slug", "title", "pdf_file", "text_file",
          "pdf_bytes", "text_bytes", "text_chars")
modules = []
for module in manifest["modules"]:
    filename = PurePosixPath(module["text_file"]).name
    body = get(module["text_file"])
    (TEXT_OUT / filename).write_bytes(body)
    modules.append({key: module[key] for key in fields})
    print(f"{module['id']} {module['title']}: {len(body):,} bytes")

catalog = {"course": manifest["course"], "year": manifest["year"], "modules": modules}
(OUT / "manuals.json").write_text(json.dumps(catalog, indent=2) + "\n")
print(f"Synced {len(modules)} manuals ({sum(m['text_bytes'] for m in modules):,} source bytes)")
