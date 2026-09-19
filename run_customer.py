#!/usr/bin/env python3
"""Customer edition entry point (hardware-locked, obfuscated build)."""

from tropic_checker.licensing.activation import ensure_activated
from tropic_checker.gui import run_app

if __name__ == "__main__":
    ensure_activated()
    run_app()
