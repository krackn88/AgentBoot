from __future__ import annotations

import secrets
from urllib.parse import quote, unquote, urlparse


def parse_proxy(value: str) -> str:
    """Normalize proxy input to an HTTP proxy URL.

    Supported formats:
    - http://user:pass@host:port
    - host:port:user:pass
    """
    value = value.strip()
    if not value:
        raise ValueError("Proxy string is empty")

    if value.startswith(("http://", "https://", "socks5://")):
        return value

    parts = value.split(":")
    if len(parts) < 4:
        raise ValueError(
            "Proxy must be a URL or host:port:username:password "
            "(password may contain colons)"
        )

    host, port, username = parts[0], parts[1], parts[2]
    password = ":".join(parts[3:])
    return (
        f"http://{quote(username, safe='')}:{quote(password, safe='')}"
        f"@{host}:{port}"
    )


def parse_proxy_lines(lines: list[str]) -> tuple[list[str], list[str]]:
    valid: list[str] = []
    invalid: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            valid.append(parse_proxy(line))
        except ValueError:
            invalid.append(line)
    return valid, invalid


def with_rotating_session(proxy_url: str) -> str:
    """Give each check a fresh residential IP when the provider supports session tags."""
    parsed = urlparse(proxy_url)
    if not parsed.hostname or not parsed.username:
        return proxy_url

    password = unquote(parsed.password or "")
    session = secrets.token_hex(4)
    if "_country" in password:
        password = password.replace("_country", f"_session-{session}_country", 1)
    elif "_session-" not in password:
        password = f"{password}_session-{session}"

    user = quote(unquote(parsed.username), safe="")
    pwd = quote(password, safe="")
    host = parsed.hostname
    port = f":{parsed.port}" if parsed.port else ""
    return f"http://{user}:{pwd}@{host}{port}"
