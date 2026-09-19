import os
from pathlib import Path

import pytest

import tropic_checker.licensing._secret as secret_mod
from license_server.app import app
from license_server.db import LicenseDB


@pytest.fixture()
def client(tmp_path):
    secret_mod._LICENSE_SECRET = b"test-secret-for-unit-tests-only!!"
    os.environ["TROPIC_LICENSE_SECRET"] = "test-secret-for-unit-tests-only!!"
    os.environ["LICENSE_ADMIN_TOKEN"] = "admin-test-token"

    import license_server.app as ls_app

    ls_app.db = LicenseDB(tmp_path / "test.db")
    ls_app.ADMIN_TOKEN = "admin-test-token"
    ls_app.app.config["TESTING"] = True
    return ls_app.app.test_client()


def test_create_and_activate(client):
    headers = {"X-Admin-Token": "admin-test-token"}
    create = client.post(
        "/admin/api/licenses",
        json={"customer_name": "Alice", "days": 30},
        headers=headers,
    )
    assert create.status_code == 200
    code = create.get_json()["license"]["activation_code"]
    hwid = "A1B2C3D4E5F60718293A4B5C6D7E8F90"

    act = client.post("/api/v1/activate", json={"activation_code": code, "hardware_id": hwid})
    assert act.status_code == 200
    key = act.get_json()["license_key"]
    assert key.startswith("TROPIC1.")

    again = client.post(
        "/api/v1/activate",
        json={"activation_code": code, "hardware_id": "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"},
    )
    assert again.status_code == 403

    val = client.post("/api/v1/validate", json={"license_key": key, "hardware_id": hwid})
    assert val.get_json()["valid"] is True


def test_dashboard_stats(client):
    headers = {"X-Admin-Token": "admin-test-token"}
    client.post("/admin/api/licenses", json={"customer_name": "Bob"}, headers=headers)
    stats = client.get("/admin/api/stats", headers=headers).get_json()
    assert stats["total"] >= 1
    assert stats["pending"] >= 1
