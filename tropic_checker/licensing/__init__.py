"""Customer edition licensing (hardware-bound activation)."""

from .hwid import format_hwid, get_hardware_id

__all__ = ["ensure_activated", "format_hwid", "get_hardware_id", "activate_online", "api_url"]


def ensure_activated() -> None:
    from .activation import ensure_activated as _run

    _run()


def activate_online(activation_code: str) -> str:
    from .online import activate_online as _activate

    return _activate(activation_code)


def api_url() -> str:
    from .online import api_url as _url

    return _url()
