from __future__ import annotations

import re
import time
from threading import Lock
from typing import Any
from urllib.parse import urlparse

from gadgetforge.checker.models import CaptureEvent, CheckerRecipe, ClassifyRule, CheckOutcome, FlowStep, HeaderExtract


class FlowRecorder:
    """Accumulates login-related HTTP events from Gadget hooks."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._events: list[CaptureEvent] = []
        self._url_filter: str = ""
        self._pending: dict[str, CaptureEvent] = {}

    def set_url_filter(self, pattern: str) -> None:
        with self._lock:
            self._url_filter = pattern.strip()

    def get_url_filter(self) -> str:
        with self._lock:
            return self._url_filter

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._pending.clear()

    def ingest_agentboot(self, payload: dict[str, Any]) -> None:
        event = payload.get("event", "")
        if not str(event).startswith("checker:"):
            return
        data = payload.get("payload") or {}
        self.ingest_capture(data)

    def ingest_capture(self, data: dict[str, Any]) -> None:
        phase = data.get("phase")
        if phase not in ("request", "response"):
            return
        url = str(data.get("url") or "")
        if self._url_filter and not re.search(self._url_filter, url, re.I):
            return
        ev = CaptureEvent(
            ts=float(data.get("ts") or time.time()),
            phase=phase,
            url=url,
            method=str(data.get("method") or "GET"),
            status=data.get("status"),
            request_headers=dict(data.get("request_headers") or {}),
            request_body=data.get("request_body"),
            response_headers=dict(data.get("response_headers") or {}),
            response_body=data.get("response_body"),
            source=str(data.get("source") or "gadget"),
        )
        with self._lock:
            if phase == "request":
                key = f"{ev.method}:{ev.url}"
                self._pending[key] = ev
            else:
                key = f"{ev.method}:{ev.url}"
                req = self._pending.pop(key, None)
                if req:
                    ev.request_headers = req.request_headers
                    ev.request_body = req.request_body
                self._events.append(ev)

    def list_events(self, limit: int = 200) -> list[CaptureEvent]:
        with self._lock:
            return list(self._events[-limit:])

    def suggest_recipe(self, name: str = "discovered-login-flow") -> CheckerRecipe:
        events = self.list_events(500)
        if not events:
            return CheckerRecipe(name=name, notes="No captured traffic yet.")

        base_url = ""
        parsed = urlparse(events[0].url)
        if parsed.scheme and parsed.netloc:
            base_url = f"{parsed.scheme}://{parsed.netloc}"

        steps: list[FlowStep] = []
        classify: list[ClassifyRule] = []
        seen_paths: set[str] = set()

        for idx, ev in enumerate(events):
            p = urlparse(ev.url)
            path = p.path or "/"
            if path in seen_paths and ev.method == "GET":
                continue
            seen_paths.add(path)

            step_id = self._step_id_from_path(path, idx)
            tags: list[str] = []
            body_template: dict[str, Any] | str | None = None
            extracts: list[HeaderExtract] = []

            if ev.request_body:
                body_template = self._sanitize_body(ev.request_body)

            if "auth" in path.lower() or "login" in path.lower() or "signin" in path.lower():
                tags.append("login")
                if isinstance(body_template, dict):
                    for key in list(body_template.keys()):
                        lk = key.lower()
                        if lk in ("email", "username", "user", "login"):
                            body_template[key] = "{{email}}"
                        if lk in ("password", "pass", "pwd"):
                            body_template[key] = "{{password}}"

            auth_hdr = ev.request_headers.get("Authorization") or ev.request_headers.get(
                "authorization"
            )
            auth_from = None
            if auth_hdr and steps:
                auth_from = steps[-1].extracts[-1].store_as if steps[-1].extracts else "token"

            if ev.response_headers.get("Authorization"):
                extracts.append(
                    HeaderExtract(
                        from_="response_header",
                        name="Authorization",
                        store_as="auth_token",
                    )
                )
            elif ev.status == 200 and ev.response_body:
                extracts.extend(self._guess_token_extracts(ev.response_body, step_id))

            step = FlowStep(
                id=step_id,
                method=ev.method,
                path=path,
                url=ev.url if not base_url else None,
                headers=self._sanitize_headers(ev.request_headers),
                body_template=body_template,
                auth_header="Authorization" if auth_hdr else None,
                auth_from=auth_from,
                extracts=extracts,
                tags=tags,
            )
            steps.append(step)

        login_id = None
        for s in steps:
            if "login" in s.tags:
                login_id = s.id
                break
        login_id = login_id or (steps[-1].id if steps else "login")

        classify = [
            ClassifyRule(
                outcome=CheckOutcome.HIT,
                step_id=login_id,
                status_codes=[200, 201],
                json_path="accessToken",
                priority=10,
            ),
            ClassifyRule(
                outcome=CheckOutcome.HIT,
                step_id=login_id,
                status_codes=[200, 201],
                json_path="access_token",
                priority=11,
            ),
            ClassifyRule(
                outcome=CheckOutcome.BAD,
                step_id=login_id,
                status_codes=[401, 400],
                priority=20,
            ),
            ClassifyRule(
                outcome=CheckOutcome.BAN,
                step_id=login_id,
                status_codes=[403],
                body_contains=["blocked", "forbidden"],
                priority=30,
            ),
            ClassifyRule(
                outcome=CheckOutcome.CAPTCHA,
                step_id=login_id,
                status_codes=[403, 429],
                body_contains=["captcha", "challenge"],
                priority=40,
            ),
            ClassifyRule(
                outcome=CheckOutcome.RETRY,
                step_id=login_id,
                status_codes=[429, 500, 502, 503],
                priority=50,
            ),
        ]

        return CheckerRecipe(
            name=name,
            base_url=base_url,
            steps=steps,
            classify=classify,
            notes="Auto-generated from Gadget capture. Review extracts and auth chain before scale runs.",
        )

    def _step_id_from_path(self, path: str, idx: int) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", path.strip("/")).strip("_").lower()
        return slug or f"step_{idx}"

    def _sanitize_headers(self, headers: dict[str, str]) -> dict[str, str]:
        out: dict[str, str] = {}
        skip = {"content-length", "host", "connection", ":authority"}
        for k, v in headers.items():
            if k.lower() in skip:
                continue
            if k.lower() == "authorization" and v.lower().startswith("bearer "):
                out[k] = "Bearer {{extract.auth_token}}"
            else:
                out[k] = v
        return out

    def _sanitize_body(self, body: str) -> dict[str, Any] | str:
        import json

        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return body

    def _guess_token_extracts(self, body: str, step_id: str) -> list[HeaderExtract]:
        import json

        extracts: list[HeaderExtract] = []
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return extracts
        for key in ("accessToken", "access_token", "token", "jwt", "id_token"):
            if key in data:
                extracts.append(
                    HeaderExtract(
                        from_="response_body",
                        name=key,
                        json_path=key,
                        store_as="auth_token" if "auth" in key or "token" in key else key,
                    )
                )
        if not extracts and step_id:
            extracts.append(
                HeaderExtract(
                    from_="response_body",
                    name="token",
                    json_path="token",
                    store_as="auth_token",
                )
            )
        return extracts


flow_recorder = FlowRecorder()
