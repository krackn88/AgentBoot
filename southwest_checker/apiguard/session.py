"""Bootstrap APIGuard session headers by executing the init kernel JS."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from southwest_checker.constants import BASE_URL, HEADER_FAMILY, TOKEN_PATH
from southwest_checker.proxy import parse_proxy

KERNEL_RUNNER = Path(__file__).with_name("kernel_runner.js")


def normalize_headers(raw: dict[str, str]) -> dict[str, str]:
    """Convert lowercase x-dublriiu-* keys to canonical X-dUblrIiu-* form."""
    out: dict[str, str] = {}
    for key, value in raw.items():
        lower = key.lower()
        if lower.startswith("x-dublriiu-") and value:
            suffix = lower.rsplit("-", 1)[-1]
            out[f"{HEADER_FAMILY}-{suffix}"] = value
    return out


def run_kernel_bootstrap(
    request_url: str | None = None,
    proxy: str | None = None,
    timeout: int = 45,
) -> dict[str, Any]:
    """Execute kernel_runner.js and return init session headers."""
    if not KERNEL_RUNNER.exists():
        raise FileNotFoundError(f"kernel runner not found: {KERNEL_RUNNER}")

    env = dict(os.environ)
    env["SW_REQUEST_URL"] = request_url or f"{BASE_URL}{TOKEN_PATH}"
    if proxy:
        env["SW_PROXY"] = parse_proxy(proxy)

    proc = subprocess.run(
        ["node", str(KERNEL_RUNNER)],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        cwd=str(KERNEL_RUNNER.parent.parent.parent),
    )

    stdout = proc.stdout.strip()
    if not stdout:
        raise RuntimeError(proc.stderr.strip() or "kernel runner produced no output")

    start = stdout.find("{")
    if start < 0:
        raise RuntimeError(f"kernel runner output is not JSON: {stdout[:200]}")

    data = json.loads(stdout[start:])
    if proc.returncode != 0 and not data.get("headers"):
        detail = data.get("errors") or data.get("error") or proc.stderr.strip()
        raise RuntimeError(detail or "kernel bootstrap failed")

    data["headers"] = normalize_headers(data.get("headers") or {})
    return data


def bootstrap_session_headers(
    request_url: str | None = None,
    proxy: str | None = None,
) -> dict[str, str]:
    """Run kernel bootstrap and return canonical APIGuard session headers."""
    data = run_kernel_bootstrap(request_url=request_url, proxy=proxy)
    headers = dict(data.get("headers") or {})
    kernel_id = data.get("kernelId")
    if kernel_id:
        headers[f"{HEADER_FAMILY}-f"] = kernel_id
    return headers
