"""Pytest wrapper for smoke checks."""

from __future__ import annotations

import os

from tropic_checker.smoke import (
    check_crypto,
    check_device_id,
    check_api_reachable,
    check_api_login,
)


def test_crypto():
    result = check_crypto()
    assert result.ok, result.detail


def test_device_id():
    result = check_device_id()
    assert result.ok, result.detail


def test_api_reachable():
    if os.environ.get("TROPIC_SKIP_LIVE") == "1":
        return
    result = check_api_reachable()
    assert result.ok, result.detail


def test_api_login():
    if os.environ.get("TROPIC_SKIP_LIVE") == "1":
        return
    if not os.environ.get("TROPIC_SMOKE_EMAIL") or not os.environ.get("TROPIC_SMOKE_PASSWORD"):
        return
    result = check_api_login()
    assert result.ok, result.detail
