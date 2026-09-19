"""Customer edition licensing (hardware-bound activation)."""

from .activation import ensure_activated
from .hwid import format_hwid, get_hardware_id
from .online import activate_online, api_url

__all__ = ["ensure_activated", "format_hwid", "get_hardware_id", "activate_online", "api_url"]
