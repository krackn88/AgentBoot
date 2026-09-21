from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
COMBOS_DIR = DATA_DIR / "combos"
COMBOS_PATH = DATA_DIR / "combos.txt"
PROXIES_PATH = DATA_DIR / "proxies.txt"

# Above this line count we keep combos on disk only (not in SQLite / textarea restore).
LARGE_COMBO_THRESHOLD = 2000

_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    COMBOS_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_combo_filename(name: str) -> str:
    name = (name or "").strip().replace("\\", "/").split("/")[-1]
    if not name:
        raise ValueError("Filename is required")
    if not name.lower().endswith((".txt", ".csv")):
        name = f"{name}.txt"
    safe = _SAFE_NAME_RE.sub("_", name)
    if safe in {".", ".."} or safe.startswith("."):
        raise ValueError("Invalid filename")
    return safe


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def file_info(path: Path) -> dict:
    stat = path.stat()
    return {
        "name": path.name,
        "size": stat.st_size,
        "lines": count_lines(path),
        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


def write_text_file(path: Path, text: str) -> int:
    ensure_data_dir()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return count_lines(path)


async def stream_upload_to_file(upload, path: Path) -> int:
    ensure_data_dir()
    path.parent.mkdir(parents=True, exist_ok=True)
    line_count = 0
    with path.open("wb") as handle:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.strip():
                line_count += 1
    return line_count


def iter_nonempty_lines(path: Path, start_line: int = 1):
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            if line_no < start_line:
                continue
            stripped = line.strip()
            if stripped:
                yield stripped


def combo_line_count(path: Path | None = None) -> int:
    target = path or COMBOS_PATH
    return count_lines(target)


def has_stored_combos() -> bool:
    return COMBOS_PATH.exists() and COMBOS_PATH.stat().st_size > 0


def list_combo_files() -> list[dict]:
    ensure_data_dir()
    files: list[dict] = []
    for path in sorted(COMBOS_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".txt", ".csv"}:
            continue
        files.append(file_info(path))
    return files


def get_library_path(name: str) -> Path:
    safe = sanitize_combo_filename(name)
    path = (COMBOS_DIR / safe).resolve()
    if COMBOS_DIR.resolve() not in path.parents and path != COMBOS_DIR.resolve():
        raise ValueError("Invalid combo path")
    return path


def delete_combo_file(name: str) -> bool:
    path = get_library_path(name)
    if not path.exists():
        return False
    path.unlink()
    return True


def copy_to_active(name: str) -> tuple[Path, int]:
    src = get_library_path(name)
    if not src.exists():
        raise FileNotFoundError(f"Combo file not found: {name}")
    ensure_data_dir()
    shutil.copy2(src, COMBOS_PATH)
    return COMBOS_PATH, count_lines(COMBOS_PATH)


async def import_combo_from_url(url: str, filename: str | None = None) -> dict:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL must be http or https")

    suggested = filename
    if not suggested:
        suggested = Path(parsed.path).name or "imported.txt"

    safe_name = sanitize_combo_filename(suggested)
    dest = get_library_path(safe_name)

    async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(600.0)) as client:
        async with client.stream("GET", url) as response:
            if response.status_code != 200:
                raise ValueError(f"Download failed: HTTP {response.status_code}")
            ensure_data_dir()
            with dest.open("wb") as handle:
                async for chunk in response.aiter_bytes(1024 * 1024):
                    handle.write(chunk)

    info = file_info(dest)
    return {"ok": True, **info}
