from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

try:
    import frida
except ImportError:  # pragma: no cover
    frida = None  # type: ignore


@dataclass
class LogEntry:
    ts: float
    level: str
    message: str
    meta: dict[str, Any] = field(default_factory=dict)


class FridaSessionManager:
    """Manages Frida device attachment and AgentBoot RPC control."""

    def __init__(self, log_limit: int = 500) -> None:
        self._device: Any = None
        self._session: Any = None
        self._script: Any = None
        self._logs: deque[LogEntry] = deque(maxlen=log_limit)
        self._lock = threading.Lock()
        self._subscribers: list[asyncio.Queue[LogEntry]] = []
        self._connected_target: str | None = None

    @property
    def connected(self) -> bool:
        return self._session is not None or self._connected_target is not None

    @property
    def live(self) -> bool:
        return self._session is not None and self._script is not None

    @property
    def target(self) -> str | None:
        return self._connected_target

    def log(self, level: str, message: str, **meta: Any) -> None:
        entry = LogEntry(ts=time.time(), level=level, message=message, meta=meta)
        with self._lock:
            self._logs.append(entry)
            for q in self._subscribers:
                try:
                    q.put_nowait(entry)
                except asyncio.QueueFull:
                    pass

    def get_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._logs)[-limit:]
        return [
            {
                "ts": e.ts,
                "level": e.level,
                "message": e.message,
                "meta": e.meta,
            }
            for e in items
        ]

    def subscribe(self) -> asyncio.Queue[LogEntry]:
        q: asyncio.Queue[LogEntry] = asyncio.Queue(maxsize=200)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[LogEntry]) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def _on_message(self, message: dict[str, Any], _data: Any) -> None:
        if message.get("type") == "send":
            payload = message.get("payload")
            if isinstance(payload, dict) and payload.get("type") == "agentboot":
                from gadgetforge.checker.recorder import flow_recorder

                flow_recorder.ingest_agentboot(payload)
                self.log(
                    "event",
                    payload.get("event", "unknown"),
                    payload=payload,
                )
            else:
                self.log("script", json.dumps(payload))
        elif message.get("type") == "error":
            self.log("error", message.get("description", "script error"), stack=message.get("stack"))

    def list_devices(self) -> list[dict[str, str]]:
        if frida is None:
            return [{"id": "sim", "name": "Frida not installed (simulated)", "type": "local"}]
        devices = []
        for d in frida.enumerate_devices():
            devices.append({"id": d.id, "name": d.name, "type": d.type})
        return devices

    def list_processes(self, device_id: str | None = None) -> list[dict[str, Any]]:
        if frida is None:
            return [
                {"pid": 0, "name": "Gadget", "parameters": {"identifier": "re.frida.Gadget"}},
            ]
        device = self._get_device(device_id)
        procs = []
        for p in device.enumerate_processes():
            procs.append({"pid": p.pid, "name": p.name, "parameters": p.parameters})
        return procs

    def _get_device(self, device_id: str | None) -> Any:
        if frida is None:
            raise RuntimeError("frida package is not installed")
        if device_id:
            return frida.get_device(device_id)
        if self._device:
            return self._device
        self._device = frida.get_local_device()
        return self._device

    def attach(
        self,
        *,
        device_id: str | None,
        target: str,
        script_source: str,
        spawn: bool = False,
    ) -> None:
        if frida is None:
            self._connected_target = target
            self.log("info", "Simulated attach to " + target + " (install frida for live sessions)")
            return

        self.detach()
        device = self._get_device(device_id)
        if spawn:
            pid = device.spawn([target])
            self._session = device.attach(pid)
            device.resume(pid)
        else:
            if target.isdigit():
                self._session = device.attach(int(target))
            else:
                self._session = device.attach(target)
        self._script = self._session.create_script(script_source)
        self._script.on("message", self._on_message)
        self._script.load()
        self._connected_target = target
        self.log("info", f"Attached to {target}")

    def detach(self) -> None:
        if self._script:
            try:
                self._script.unload()
            except Exception:
                pass
            self._script = None
        if self._session:
            try:
                self._session.detach()
            except Exception:
                pass
            self._session = None
        self._connected_target = None

    def _rpc_call(self, name: str, *args: Any) -> Any:
        if frida is None:
            return {"ok": True, "simulated": True, "method": name, "args": args}
        if not self._script:
            raise RuntimeError("Not attached")
        exports = self._script.exports_sync
        fn = getattr(exports, name, None)
        if fn is None:
            raise RuntimeError(f"RPC export missing: {name}")
        return fn(*args)

    def ping(self) -> Any:
        return self._rpc_call("ping")

    def list_runtime_actions(self) -> Any:
        return self._rpc_call("listActions")

    def set_runtime_action(self, action_id: str, enabled: bool) -> Any:
        return self._rpc_call("setAction", action_id, enabled)

    def get_runtime_state(self) -> Any:
        return self._rpc_call("getState")


session_manager = FridaSessionManager()
