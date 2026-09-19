import os

from tropic_checker.licensing.license_core import (
    LICENSE_PREFIX,
    issue_license,
    parse_license_key,
    validate_license_key,
)


def test_license_roundtrip():
    os.environ["TROPIC_LICENSE_SECRET"] = "test-secret-for-unit-tests-only!!"
    hwid = "A1B2C3D4E5F60718293A4B5C6D7E8F90"
    key = issue_license(hwid, "Test Customer", expires_at=None)
    assert key.startswith(f"{LICENSE_PREFIX}.")
    info = validate_license_key(key, hardware_id=hwid)
    assert info.customer == "Test Customer"
    assert info.hardware_id == hwid


def test_license_wrong_machine():
    os.environ["TROPIC_LICENSE_SECRET"] = "test-secret-for-unit-tests-only!!"
    key = issue_license("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "X")
    try:
        validate_license_key(key, hardware_id="BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB")
        assert False, "should reject wrong hwid"
    except ValueError as exc:
        assert "not valid for this computer" in str(exc)


def test_tampered_signature_rejected():
    os.environ["TROPIC_LICENSE_SECRET"] = "test-secret-for-unit-tests-only!!"
    hwid = "A1B2C3D4E5F60718293A4B5C6D7E8F90"
    key = issue_license(hwid, "Test Customer")
    body = key.split(".")[1]
    # Flip a character in the signed payload; signature must no longer verify.
    tampered_body = body[:-1] + ("A" if body[-1] != "A" else "B")
    tampered = key.replace(body, tampered_body)
    try:
        parse_license_key(tampered)
        assert False, "tampered license should be rejected"
    except ValueError as exc:
        assert "signature" in str(exc).lower() or "format" in str(exc).lower()


def test_forged_key_from_wrong_secret_rejected():
    # A license signed with a *different* private secret must not validate
    # against the real one — this is what asymmetric signing protects.
    hwid = "A1B2C3D4E5F60718293A4B5C6D7E8F90"
    os.environ["TROPIC_LICENSE_SECRET"] = "attacker-secret-not-the-real-one!"
    forged = issue_license(hwid, "Mallory")
    os.environ["TROPIC_LICENSE_SECRET"] = "test-secret-for-unit-tests-only!!"
    try:
        validate_license_key(forged, hardware_id=hwid)
        assert False, "forged license signed with wrong key should be rejected"
    except ValueError as exc:
        assert "signature" in str(exc).lower()
