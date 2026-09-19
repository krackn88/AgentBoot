#!/usr/bin/env python3
"""Print hardware ID (same as shown in customer activation screen)."""

from tropic_checker.licensing.hwid import format_hwid, get_hardware_id

if __name__ == "__main__":
    print(format_hwid(get_hardware_id()))
