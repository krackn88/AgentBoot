from __future__ import annotations

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
COMBOS_PATH = DATA_DIR / "combos.txt"
PROXIES_PATH = DATA_DIR / "proxies.txt"

# Above this line count we keep combos on disk only (not in SQLite / textarea restore).
LARGE_COMBO_THRESHOLD = 2000


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def write_text_file(path: Path, text: str) -> int:
    ensure_data_dir()
    path.write_text(text, encoding="utf-8")
    return count_lines(path)


async def stream_upload_to_file(upload, path: Path) -> int:
    ensure_data_dir()
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


def iter_nonempty_lines(path: Path):
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                yield stripped


def combo_line_count() -> int:
    return count_lines(COMBOS_PATH)


def has_stored_combos() -> bool:
    return COMBOS_PATH.exists() and COMBOS_PATH.stat().st_size > 0
