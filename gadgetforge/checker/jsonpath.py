from __future__ import annotations

from typing import Any


def get_path(obj: Any, path: str) -> Any:
    """Simple dotted path with optional [index] segments."""
    if not path:
        return obj
    cur = obj
    for part in path.replace("]", "").split("."):
        if not part:
            continue
        if "[" in part:
            key, idx_s = part.split("[", 1)
            if key:
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(key)
            try:
                idx = int(idx_s)
                if isinstance(cur, list) and 0 <= idx < len(cur):
                    cur = cur[idx]
                else:
                    return None
            except ValueError:
                return None
        else:
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                return None
        if cur is None:
            return None
    return cur
