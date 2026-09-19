import os
from pathlib import Path

import pytest

from license_server.app import app
from license_server.db import LicenseDB


@pytest.fixture()
def client(tmp_path):
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
    assert key.startswith("TROPIC2.")

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


def test_admin_page_does_not_leak_token(client):
    page = client.get("/admin")
    assert page.status_code == 200
    # The real admin token must never be embedded in the served HTML.
    assert b"admin-test-token" not in page.data
    assert b"admin-token" not in page.data


def test_admin_query_param_token_rejected(client):
    # Token via query string must NOT authenticate (would leak into logs).
    resp = client.get("/admin/api/stats?token=admin-test-token")
    assert resp.status_code == 401


def test_admin_wrong_token_rejected(client):
    resp = client.get("/admin/api/stats", headers={"X-Admin-Token": "nope"})
    assert resp.status_code == 401


def test_admin_ip_allowlist_blocks_and_allows(client):
    import ipaddress

    import license_server.app as ls_app

    headers = {"X-Admin-Token": "admin-test-token"}
    # Allowlist that excludes the test client's 127.0.0.1 -> hidden as 404.
    ls_app.ADMIN_IP_ALLOWLIST = [ipaddress.ip_network("10.0.0.0/8")]
    try:
        assert client.get("/admin", headers=headers).status_code == 404
        assert client.get("/admin/api/stats", headers=headers).status_code == 404
        # Public activation endpoints stay reachable.
        assert client.get("/health").status_code == 200
        # Allowlist that includes localhost -> admin reachable again.
        ls_app.ADMIN_IP_ALLOWLIST = [ipaddress.ip_network("127.0.0.0/8")]
        assert client.get("/admin", headers=headers).status_code == 200
        assert client.get("/admin/api/stats", headers=headers).status_code == 200
    finally:
        ls_app.ADMIN_IP_ALLOWLIST = []


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
