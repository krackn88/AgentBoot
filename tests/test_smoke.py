"""Pytest wrapper for run_smoke.py checks."""

from __future__ import annotations

import os

import run_smoke


def test_crypto():
    _, ok, detail = run_smoke.test_crypto()
    assert ok, detail


def test_device_id_randomized():
    _, ok, detail = run_smoke.test_device_id_randomized()
    assert ok, detail


def test_api_reachable():
    if os.environ.get("TROPIC_SKIP_LIVE") == "1":
        return
    _, ok, detail = run_smoke.test_api_reachable()
    assert ok, detail


def test_api_login():
    if os.environ.get("TROPIC_SKIP_LIVE") == "1":
        return
    if not os.environ.get("TROPIC_SMOKE_EMAIL") or not os.environ.get("TROPIC_SMOKE_PASSWORD"):
        return
    _, ok, detail = run_smoke.test_api_login()
    assert ok, detail
