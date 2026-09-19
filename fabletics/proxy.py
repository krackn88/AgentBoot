from __future__ import annotations

from urllib.parse import quote


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
