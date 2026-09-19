from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .db import clear_checked_combos, clear_hits, delete_hits, get_session, init_db, list_hits, save_session
from .worker import worker

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Fabletics Checker")
init_db()


class DeleteHitsRequest(BaseModel):
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


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/session")
async def session() -> dict[str, Any]:
    data = get_session()
    data.update(worker.snapshot())
    return data


@app.post("/api/session")
async def save_session_state(body: SaveSessionRequest) -> dict[str, bool]:
    save_session(body.combos, body.proxies, body.threads)
    return {"ok": True}


@app.get("/api/status")
async def status() -> dict[str, Any]:
    data = worker.snapshot()
    data["checked_count"] = get_session()["checked_count"]
    return data


@app.post("/api/jobs/start")
async def start_job(
    combos: str = Form(default=""),
    proxies: str = Form(default=""),
    threads: str = Form(default="5"),
    combo_file: UploadFile | None = File(default=None),
    proxy_file: UploadFile | None = File(default=None),
) -> dict[str, Any]:
    if worker.is_running():
        raise HTTPException(409, "A job is already running")

    combo_lines = _lines_from_text(combos)
    proxy_lines = _lines_from_text(proxies)

    combo_upload = await _read_upload(combo_file)
    proxy_upload = await _read_upload(proxy_file)

    combo_lines.extend(_lines_from_text(combo_upload))
    proxy_lines.extend(_lines_from_text(proxy_upload))

    try:
        thread_count = max(1, min(int(threads or "5"), 50))
    except ValueError:
        thread_count = 5

    combos_text = "\n".join(combo_lines) if combo_lines else combos
    proxies_text = "\n".join(proxy_lines) if proxy_lines else proxies
    save_session(combos_text, proxies_text, thread_count)

    result = worker.start(combo_lines, proxy_lines, threads=thread_count)
    if not result:
        raise HTTPException(400, "No valid combos found")

    return {"ok": True, **result}


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


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
