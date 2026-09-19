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
    hwid = "A1B2C3D4E5F60718293A4B5C6D7E8F90"
    create = client.post(
        "/admin/api/licenses",
        json={"customer_name": "Alice", "days": 30, "hardware_id": hwid},
        headers=headers,
    )
    assert create.status_code == 200
    lic = create.get_json()["license"]
    code = lic["activation_code"]
    assert lic["status"] == "locked"
    assert lic["hardware_id"] == hwid

    act = client.post("/api/v1/activate", json={"activation_code": code, "hardware_id": hwid})
    assert act.status_code == 200
    key = act.get_json()["license_key"]
    assert key.startswith("TROPIC1.")

    again = client.post(
        "/api/v1/activate",
        json={"activation_code": code, "hardware_id": "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"},
    )
    assert again.status_code == 403
    assert "another PC" in again.get_json()["error"]

    val = client.post("/api/v1/validate", json={"license_key": key, "hardware_id": hwid})
    assert val.get_json()["valid"] is True


def test_create_requires_hwid(client):
    headers = {"X-Admin-Token": "admin-test-token"}
    missing = client.post(
        "/admin/api/licenses",
        json={"customer_name": "No HWID"},
        headers=headers,
    )
    assert missing.status_code == 400


def test_prelocked_hwid_rejects_wrong_machine(client):
    headers = {"X-Admin-Token": "admin-test-token"}
    hwid = "11111111111111111111111111111111"
    create = client.post(
        "/admin/api/licenses",
        json={"customer_name": "Carol", "hardware_id": hwid},
        headers=headers,
    )
    code = create.get_json()["license"]["activation_code"]
    wrong = client.post(
        "/api/v1/activate",
        json={"activation_code": code, "hardware_id": "22222222222222222222222222222222"},
    )
    assert wrong.status_code == 403
    assert "locked to a different PC" in wrong.get_json()["error"]


def test_dashboard_stats(client):
    headers = {"X-Admin-Token": "admin-test-token"}
    client.post(
        "/admin/api/licenses",
        json={"customer_name": "Bob", "hardware_id": "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"},
        headers=headers,
    )
    stats = client.get("/admin/api/stats", headers=headers).get_json()
    assert stats["total"] >= 1
    assert stats["locked"] >= 1


def test_portal_home_and_download(client, tmp_path):
    import license_server.app as ls_app
    import license_server.portal_files as portal

    downloads = tmp_path / "customer"
    downloads.mkdir()
    sample = downloads / "TropicChecker-Customer-windows-x64.zip"
    sample.write_bytes(b"fake-zip-content")

    portal.DOWNLOADS_DIR = downloads
    ls_app.PUBLIC_API_URL = "http://test.example:8082"

    page = client.get("/")
    assert page.status_code == 200
    assert b"Tropic Time Checker" in page.data
    assert b"Windows (64-bit)" in page.data

    dl = client.get("/portal/files/TropicChecker-Customer-windows-x64.zip")
    assert dl.status_code == 200
    assert dl.data == b"fake-zip-content"

    assert client.get("/portal/files/../etc/passwd").status_code == 404
