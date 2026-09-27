from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from gadgetforge.ai import chat_completion
from gadgetforge.catalog import list_actions, load_catalog
from gadgetforge.composer import ComposeRequest, EnabledAction, compose_script
from gadgetforge.gadget_config import (
    ConnectInteraction,
    GadgetConfig,
    ListenInteraction,
    OnLoad,
    OnPortConflict,
    ScriptInteraction,
    android_packaging_notes,
    default_listen_config,
)
from gadgetforge.session import session_manager


class GadgetConfigRequest(BaseModel):
    mode: str = "listen"
    address: str = "127.0.0.1"
    port: int = 27042
    on_load: OnLoad = OnLoad.WAIT
    on_port_conflict: OnPortConflict = OnPortConflict.FAIL
    script_path: str | None = None
    gadget_binary_name: str = "libfrida-gadget"


class AttachRequest(BaseModel):
    device_id: str | None = None
    target: str = "Gadget"
    spawn: bool = False
    script: str | None = None
    actions: list[EnabledAction] = Field(default_factory=list)


class ActionToggleRequest(BaseModel):
    action_id: str
    enabled: bool


class ChatRequest(BaseModel):
    messages: list[dict[str, str]]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    session_manager.detach()


app = FastAPI(title="AgentBoot GadgetForge API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "agentboot-gadgetforge"}


@app.get("/api/actions")
def api_list_actions(platform: str | None = None) -> dict[str, Any]:
    actions = list_actions(platform)
    return {"actions": [a.model_dump() for a in actions]}


@app.get("/api/catalog")
def api_catalog() -> dict[str, Any]:
    return load_catalog().model_dump()


@app.post("/api/compose")
def api_compose(req: ComposeRequest) -> dict[str, str]:
    script = compose_script(req.actions, custom_script=req.custom_script)
    return {"script": script}


@app.post("/api/gadget-config")
def api_gadget_config(req: GadgetConfigRequest) -> dict[str, Any]:
    if req.mode == "listen":
        config = GadgetConfig(
            interaction=ListenInteraction(
                address=req.address,
                port=req.port,
                on_load=req.on_load,
                on_port_conflict=req.on_port_conflict,
            )
        )
    elif req.mode == "connect":
        config = GadgetConfig(
            interaction=ConnectInteraction(
                address=req.address,
                port=req.port,
                on_load=req.on_load,
                on_port_conflict=req.on_port_conflict,
            )
        )
    elif req.mode == "script":
        if not req.script_path:
            raise HTTPException(400, "script_path required for script mode")
        config = GadgetConfig(
            interaction=ScriptInteraction(path=req.script_path, on_load=req.on_load)
        )
    else:
        raise HTTPException(400, f"Unknown mode: {req.mode}")

    return {
        "config": config.model_dump(mode="json"),
        "json": config.to_json(),
        "filename": config.suggested_filename(req.gadget_binary_name),
        "notes": android_packaging_notes(),
    }


@app.get("/api/gadget-config/default")
def api_default_gadget_config() -> dict[str, Any]:
    config = default_listen_config()
    return {"config": config.model_dump(mode="json"), "json": config.to_json()}


@app.get("/api/devices")
def api_devices() -> dict[str, Any]:
    return {"devices": session_manager.list_devices()}


@app.get("/api/processes")
def api_processes(device_id: str | None = None) -> dict[str, Any]:
    return {"processes": session_manager.list_processes(device_id)}


@app.post("/api/session/attach")
def api_attach(req: AttachRequest) -> dict[str, Any]:
    script = req.script
    if not script:
        script = compose_script(req.actions)
    try:
        session_manager.attach(
            device_id=req.device_id,
            target=req.target,
            script_source=script,
            spawn=req.spawn,
        )
    except Exception as e:
        raise HTTPException(500, str(e)) from e
    return {
        "connected": session_manager.connected,
        "target": session_manager.target,
        "live": session_manager.live,
    }


@app.post("/api/session/detach")
def api_detach() -> dict[str, bool]:
    session_manager.detach()
    return {"connected": False}


@app.get("/api/session/status")
def api_session_status() -> dict[str, Any]:
    return {
        "connected": session_manager.connected,
        "target": session_manager.target,
        "logs": session_manager.get_logs(50),
    }


@app.post("/api/session/ping")
def api_ping() -> Any:
    try:
        return session_manager.ping()
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/session/actions")
def api_runtime_actions() -> Any:
    try:
        return session_manager.list_runtime_actions()
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/session/actions/toggle")
def api_toggle_action(req: ActionToggleRequest) -> Any:
    try:
        return session_manager.set_runtime_action(req.action_id, req.enabled)
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/session/logs")
def api_logs(limit: int = 100) -> dict[str, Any]:
    return {"logs": session_manager.get_logs(limit)}


@app.post("/api/ai/chat")
async def api_ai_chat(req: ChatRequest) -> dict[str, Any]:
    try:
        return await chat_completion(req.messages)
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = session_manager.subscribe()
    try:
        while True:
            try:
                entry = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(
                    {
                        "ts": entry.ts,
                        "level": entry.level,
                        "message": entry.message,
                        "meta": entry.meta,
                    }
                )
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        session_manager.unsubscribe(queue)


# Optional: serve built frontend from frontend/dist
import os
from pathlib import Path

_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="static")
