import os

import tropic_checker.licensing._secret as secret_mod
from tropic_checker.licensing.license_core import issue_license, validate_license_key


def test_license_roundtrip():
    secret_mod._LICENSE_SECRET = b"test-secret-for-unit-tests-only!!"
    os.environ["TROPIC_LICENSE_SECRET"] = "test-secret-for-unit-tests-only!!"
    hwid = "A1B2C3D4E5F60718293A4B5C6D7E8F90"
    key = issue_license(hwid, "Test Customer", expires_at=None)
    info = validate_license_key(key, hardware_id=hwid)
    assert info.customer == "Test Customer"
    assert info.hardware_id == hwid


def test_license_wrong_machine():
    secret_mod._LICENSE_SECRET = b"test-secret-for-unit-tests-only!!"
    key = issue_license("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "X")
    try:
        validate_license_key(key, hardware_id="BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB")
        assert False, "should reject wrong hwid"
    except ValueError as exc:
        assert "not valid for this computer" in str(exc)
