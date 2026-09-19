"""Signed license keys bound to a hardware id.

Security model
--------------
License keys are signed with **Ed25519 (asymmetric)**. The vendor's *private*
signing key never leaves the license server / build machine. Customer builds
embed only the corresponding *public* key (see ``_secret.py``), so a leaked or
reverse-engineered client cannot forge licenses for arbitrary hardware ids —
forging a key requires the private key, which customers never receive.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from Crypto.Signature import eddsa

from ._secret import _LICENSE_PUBLIC_KEY_HEX
from .hwid import get_hardware_id

LICENSE_PREFIX = "TROPIC2"
LICENSE_VERSION = 2

_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class LicenseInfo:
    hardware_id: str
    customer: str
    issued_at: int
    expires_at: int | None
    raw_key: str

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return int(time.time()) > self.expires_at


def _seed_from_secret(secret: str) -> bytes:
    """Derive a deterministic 32-byte Ed25519 seed from a vendor secret.

    Accepts a 64-char hex string (used verbatim), any exactly-32-byte value
    (used verbatim), or any other string (hashed to 32 bytes with SHA-256).
    """
    secret = secret.strip()
    raw = secret.encode("utf-8")
    try:
        if len(secret) == 64:
            return bytes.fromhex(secret)
    except ValueError:
        pass
    if len(raw) == 32:
        return raw
    return hashlib.sha256(raw).digest()


def _private_secret() -> str:
    """Return the vendor signing secret from env or license_secret.txt, or ''."""
    secret = os.environ.get("TROPIC_LICENSE_SECRET", "").strip()
    if secret and not secret.startswith("DEV-ONLY"):
        return secret
    secret_file = Path(
        os.environ.get("LICENSE_SECRET_FILE", str(_ROOT / "license_secret.txt"))
    )
    if secret_file.is_file():
        file_secret = secret_file.read_text(encoding="utf-8").strip()
        if file_secret and not file_secret.startswith("DEV-ONLY"):
            return file_secret
    return ""


def _signer() -> eddsa.EdDSASigScheme | None:
    """Build an Ed25519 signer from the private secret, if one is configured."""
    secret = _private_secret()
    if not secret:
        return None
    key = eddsa.import_private_key(_seed_from_secret(secret))
    return eddsa.new(key, "rfc8032")


def _verifier() -> eddsa.EdDSASigScheme:
    """Build an Ed25519 verifier.

    Prefer deriving the public key from a locally-configured private secret
    (server / build machine / tests). Otherwise fall back to the public key
    embedded in the shipped client.
    """
    secret = _private_secret()
    if secret:
        priv = eddsa.import_private_key(_seed_from_secret(secret))
        return eddsa.new(priv.public_key(), "rfc8032")

    pub_hex = (_LICENSE_PUBLIC_KEY_HEX or "").strip()
    if not pub_hex:
        raise ValueError("No license public key configured in this build")
    pub = eddsa.import_public_key(bytes.fromhex(pub_hex))
    return eddsa.new(pub, "rfc8032")


def public_key_hex() -> str:
    """Return the vendor public key (hex) derived from the private secret.

    Used at customer-build time to embed the correct public key in the client.
    """
    secret = _private_secret()
    if not secret:
        raise ValueError("Set TROPIC_LICENSE_SECRET or create license_secret.txt")
    priv = eddsa.import_private_key(_seed_from_secret(secret))
    return priv.public_key().export_key(format="raw").hex()


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _canonical_body(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def issue_license(
    hardware_id: str,
    customer: str,
    *,
    expires_at: int | None = None,
    issued_at: int | None = None,
) -> str:
    signer = _signer()
    if signer is None:
        raise ValueError(
            "License signing key not configured (set TROPIC_LICENSE_SECRET "
            "or create license_secret.txt)"
        )
    hwid = hardware_id.replace("-", "").upper()
    payload = {
        "v": LICENSE_VERSION,
        "hwid": hwid,
        "customer": customer.strip(),
        "issued_at": int(issued_at or time.time()),
        "expires_at": expires_at,
    }
    body = _canonical_body(payload)
    signature = signer.sign(body)
    return f"{LICENSE_PREFIX}.{_b64url_encode(body)}.{_b64url_encode(signature)}"


def parse_license_key(key: str) -> LicenseInfo:
    key = key.strip()
    parts = key.split(".")
    if len(parts) != 3 or parts[0] != LICENSE_PREFIX:
        raise ValueError("Invalid license format")

    body = _b64url_decode(parts[1])
    signature = _b64url_decode(parts[2])
    try:
        _verifier().verify(body, signature)
    except ValueError:
        raise ValueError("License signature mismatch")

    payload = json.loads(body.decode("utf-8"))
    if int(payload.get("v", 0)) != LICENSE_VERSION:
        raise ValueError("Unsupported license version")

    return LicenseInfo(
        hardware_id=str(payload["hwid"]).upper(),
        customer=str(payload.get("customer", "")),
        issued_at=int(payload.get("issued_at", 0)),
        expires_at=payload.get("expires_at"),
        raw_key=key,
    )


def validate_license_key(key: str, *, hardware_id: str | None = None) -> LicenseInfo:
    info = parse_license_key(key)
    current = (hardware_id or get_hardware_id()).replace("-", "").upper()
    if info.hardware_id != current:
        raise ValueError("License is not valid for this computer")
    if info.is_expired:
        raise ValueError("License has expired")
    return info
