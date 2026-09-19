from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .combo_store import (
    COMBOS_PATH,
    LARGE_COMBO_THRESHOLD,
    PROXIES_PATH,
    combo_line_count,
    has_stored_combos,
    stream_upload_to_file,
    write_text_file,
)
from .db import (
    clear_checked_combos,
    clear_hits,
    clear_saved_combos,
    count_saved_combos,
    delete_hits,
    delete_saved_combos,
    export_saved_combos_text,
    get_session,
    init_db,
    list_hits,
    list_saved_combos,
    save_session,
)
from .worker import worker

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Fabletics Checker")
init_db()


class DeleteHitsRequest(BaseModel):
    ids: list[int]


class DeleteSavedCombosRequest(BaseModel):
    ids: list[int]


class SaveSessionRequest(BaseModel):
    combos: str = ""
    proxies: str = ""
    threads: int = 5


def _lines_from_text(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


async def _read_upload(file: UploadFile | None) -> str:
    if not file or not file.filename:
        return ""
    raw = await file.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _count_nonempty_lines(text: str) -> int:
    return len(_lines_from_text(text))


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/session")
async def session() -> dict[str, Any]:
    data = get_session()
    data.update(worker.snapshot())
    return data


@app.post("/api/session")
async def save_session_state(body: SaveSessionRequest) -> dict[str, Any]:
    combo_text = body.combos or ""
    line_count = _count_nonempty_lines(combo_text)
    combos_stored = False

    if line_count > LARGE_COMBO_THRESHOLD:
        write_text_file(COMBOS_PATH, combo_text)
        combos_stored = True
        combo_text = ""
    elif line_count > 0:
        write_text_file(COMBOS_PATH, combo_text)

    if body.proxies.strip():
        write_text_file(PROXIES_PATH, body.proxies)

    save_session(
        combo_text,
        body.proxies,
        body.threads,
        combo_count=line_count or combo_line_count(),
        combos_stored=combos_stored or line_count > LARGE_COMBO_THRESHOLD,
    )
    return {
        "ok": True,
        "combo_count": line_count or combo_line_count(),
        "combos_stored": combos_stored or line_count > LARGE_COMBO_THRESHOLD,
    }


@app.get("/api/status")
async def status() -> dict[str, Any]:
    data = worker.snapshot()
    session_data = get_session()
    data["checked_count"] = session_data["checked_count"]
    data["combo_count"] = session_data["combo_count"]
    data["combos_stored"] = session_data["combos_stored"]
    data["saved_combo_count"] = count_saved_combos()
    return data


@app.post("/api/jobs/start")
async def start_job(
    combos: str = Form(default=""),
    proxies: str = Form(default=""),
    threads: str = Form(default="5"),
    combo_file: UploadFile | None = File(default=None),
    proxy_file: UploadFile | None = File(default=None),
    use_stored_combos: str = Form(default="false"),
) -> dict[str, Any]:
    if worker.is_running():
        raise HTTPException(409, "A job is already running")

    try:
        thread_count = max(1, min(int(threads or "3"), 20))
    except ValueError:
        thread_count = 5

    combo_lines: list[str] | None = None
    combo_file_path: Path | None = None
    combo_count = 0
    combos_stored = False

    if combo_file and combo_file.filename:
        combo_count = await stream_upload_to_file(combo_file, COMBOS_PATH)
        combo_file_path = COMBOS_PATH
        combos_stored = True
    elif combos.strip():
        line_count = _count_nonempty_lines(combos)
        if line_count > LARGE_COMBO_THRESHOLD:
            combo_count = write_text_file(COMBOS_PATH, combos)
            combo_file_path = COMBOS_PATH
            combos_stored = True
        else:
            combo_lines = _lines_from_text(combos)
            combo_count = len(combo_lines)
            write_text_file(COMBOS_PATH, combos)
    elif use_stored_combos.lower() in {"1", "true", "yes"} or has_stored_combos():
        combo_count = combo_line_count()
        combo_file_path = COMBOS_PATH
        combos_stored = True
    else:
        raise HTTPException(400, "No combos provided")

    if combo_count == 0 and combo_lines is None:
        raise HTTPException(400, "No valid combo lines found")

    proxy_lines = _lines_from_text(proxies)
    proxy_upload = await _read_upload(proxy_file)
    proxy_lines.extend(_lines_from_text(proxy_upload))

    if not proxy_lines and PROXIES_PATH.exists():
        proxy_lines = list(_lines_from_text(PROXIES_PATH.read_text(encoding="utf-8", errors="replace")))

    proxies_text = "\n".join(proxy_lines) if proxy_lines else proxies
    if proxy_lines:
        try:
            write_text_file(PROXIES_PATH, proxies_text)
        except OSError as exc:
            raise HTTPException(500, f"Cannot write proxy file: {exc}") from exc

    save_session(
        "" if combos_stored else combos,
        proxies_text,
        thread_count,
        combo_count=combo_count,
        combos_stored=combos_stored,
    )

    result = worker.start(
        combo_lines=combo_lines,
        combo_file=combo_file_path,
        proxies=proxy_lines,
        threads=thread_count,
    )
    if not result.get("ok"):
        error = result.get("error", "unknown")
        if error == "no_combos":
            raise HTTPException(400, "No valid combos found")
        if error == "already_running":
            raise HTTPException(409, "A job is already running")
        raise HTTPException(400, "Failed to start job")

    return {
        "ok": True,
        "status": "preparing",
        "combo_count": combo_count,
        **worker.snapshot(),
    }


@app.post("/api/jobs/stop")
async def stop_job() -> dict[str, bool]:
    worker.stop()
    return {"ok": True}


@app.post("/api/progress/reset")
async def reset_progress() -> dict[str, int]:
    if worker.is_running():
        raise HTTPException(409, "Stop the job before resetting progress")
    cleared = clear_checked_combos()
    return {"cleared": cleared}


@app.get("/api/hits")
async def get_hits() -> list[dict[str, Any]]:
    return list_hits()


@app.post("/api/hits/delete")
async def remove_hits(body: DeleteHitsRequest) -> dict[str, int]:
    deleted = delete_hits(body.ids)
    return {"deleted": deleted}


@app.post("/api/hits/clear")
async def remove_all_hits() -> dict[str, int]:
    deleted = clear_hits()
    return {"deleted": deleted}


@app.get("/api/saved-combos")
async def get_saved_combos() -> dict[str, Any]:
    return {
        "count": count_saved_combos(),
        "items": list_saved_combos(),
    }


@app.get("/api/saved-combos/export")
async def export_saved_combos() -> PlainTextResponse:
    return PlainTextResponse(export_saved_combos_text(), media_type="text/plain")


@app.post("/api/saved-combos/delete")
async def remove_saved_combos(body: DeleteSavedCombosRequest) -> dict[str, int]:
    deleted = delete_saved_combos(body.ids)
    return {"deleted": deleted}


@app.post("/api/saved-combos/clear")
async def remove_all_saved_combos() -> dict[str, int]:
    deleted = clear_saved_combos()
    return {"deleted": deleted}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
