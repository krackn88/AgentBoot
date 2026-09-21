"""Proxy configuration helpers."""

from __future__ import annotations

import os
from urllib.parse import quote


def parse_proxy(value: str) -> str:
    """
    Normalize a proxy string to a full URL.

    Accepts:
      - Full URL:  http://user:pass@host:port
      - Shorthand: host:port:user:pass
    """
    value = value.strip()
    if not value:
        raise ValueError("Empty proxy value")

    if "://" in value:
        return value

    parts = value.split(":")
    if len(parts) < 4:
        raise ValueError(
            "Proxy must be a URL or host:port:username:password "
            "(password may contain colons)"
        )

    host, port, username = parts[0], parts[1], parts[2]
    password = ":".join(parts[3:])
    user_enc = quote(username, safe="")
    pass_enc = quote(password, safe="")
    return f"http://{user_enc}:{pass_enc}@{host}:{port}"


def resolve_proxy(
    cli_value: str | None = None,
    config_value: str | None = None,
) -> str | None:
    """Resolve proxy from CLI flag, config file, or SW_PROXY env var."""
    for source in (cli_value, config_value, os.environ.get("SW_PROXY")):
        if source:
            return parse_proxy(source)
    return None
