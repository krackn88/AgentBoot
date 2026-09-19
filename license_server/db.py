"""SQLite storage for license activations."""

from __future__ import annotations

import secrets
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _now() -> int:
    return int(time.time())


def _code() -> str:
    raw = secrets.token_hex(4).upper()
    return f"TROPIC-{raw[:4]}-{raw[4:]}"


def normalize_hwid(hardware_id: str) -> str:
    return hardware_id.replace("-", "").replace(" ", "").upper()


def validate_hwid(hardware_id: str) -> str:
    hwid = normalize_hwid(hardware_id)
    if len(hwid) < 16:
        raise ValueError("hardware_id must be at least 16 characters")
    return hwid


@dataclass
class LicenseRow:
    id: str
    customer_name: str
    email: str
    activation_code: str
    hardware_id: str | None
    status: str
    expires_at: int | None
    created_at: int
    activated_at: int | None
    last_seen_at: int | None
    notes: str
    license_key: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "customer_name": self.customer_name,
            "email": self.email,
            "activation_code": self.activation_code,
            "hardware_id": self.hardware_id,
            "status": self.effective_status(),
            "expires_at": self.expires_at,
            "created_at": self.created_at,
            "activated_at": self.activated_at,
            "last_seen_at": self.last_seen_at,
            "notes": self.notes,
            "has_license_key": bool(self.license_key),
        }

    def effective_status(self) -> str:
        if self.status == "revoked":
            return "revoked"
        if self.expires_at and _now() > self.expires_at:
            return "expired"
        if self.hardware_id and self.license_key:
            return "active"
        if self.hardware_id:
            return "locked"
        return "pending"


class LicenseDB:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS licenses (
                    id TEXT PRIMARY KEY,
                    customer_name TEXT NOT NULL,
                    email TEXT DEFAULT '',
                    activation_code TEXT NOT NULL UNIQUE,
                    hardware_id TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    expires_at INTEGER,
                    created_at INTEGER NOT NULL,
                    activated_at INTEGER,
                    last_seen_at INTEGER,
                    notes TEXT DEFAULT '',
                    license_key TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_licenses_code ON licenses(activation_code);
                CREATE INDEX IF NOT EXISTS idx_licenses_hwid ON licenses(hardware_id);

                CREATE TABLE IF NOT EXISTS activation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_id TEXT,
                    hardware_id TEXT,
                    ip TEXT,
                    success INTEGER NOT NULL,
                    message TEXT,
                    created_at INTEGER NOT NULL
                );
                """
            )

    def _row(self, r: sqlite3.Row) -> LicenseRow:
        return LicenseRow(
            id=r["id"],
            customer_name=r["customer_name"],
            email=r["email"] or "",
            activation_code=r["activation_code"],
            hardware_id=r["hardware_id"],
            status=r["status"],
            expires_at=r["expires_at"],
            created_at=r["created_at"],
            activated_at=r["activated_at"],
            last_seen_at=r["last_seen_at"],
            notes=r["notes"] or "",
            license_key=r["license_key"],
        )

    def create_license(
        self,
        customer_name: str,
        *,
        email: str = "",
        days: int | None = None,
        notes: str = "",
        hardware_id: str = "",
    ) -> LicenseRow:
        license_id = str(uuid.uuid4())
        created = _now()
        expires_at = created + days * 86400 if days and days > 0 else None
        code = _code()
        hwid = validate_hwid(hardware_id)
        existing = self.get_by_hardware(hwid)
        if existing and existing.effective_status() not in {"revoked", "expired"}:
            raise ValueError("This hardware ID already has a license")
        with self._connect() as conn:
            while True:
                try:
                    conn.execute(
                        """
                        INSERT INTO licenses (
                            id, customer_name, email, activation_code, hardware_id, status,
                            expires_at, created_at, notes
                        ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                        """,
                        (
                            license_id,
                            customer_name.strip(),
                            email.strip(),
                            code,
                            hwid,
                            expires_at,
                            created,
                            notes,
                        ),
                    )
                    break
                except sqlite3.IntegrityError:
                    code = _code()
            conn.commit()
        return self.get_license(license_id)

    def get_license(self, license_id: str) -> LicenseRow:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM licenses WHERE id = ?", (license_id,)).fetchone()
        if not row:
            raise KeyError(license_id)
        return self._row(row)

    def get_by_code(self, activation_code: str) -> LicenseRow | None:
        code = activation_code.strip().upper().replace(" ", "")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM licenses WHERE UPPER(activation_code) = ?",
                (code,),
            ).fetchone()
        return self._row(row) if row else None

    def get_by_hardware(self, hardware_id: str) -> LicenseRow | None:
        hwid = hardware_id.replace("-", "").upper()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM licenses WHERE REPLACE(UPPER(hardware_id), '-', '') = ?",
                (hwid,),
            ).fetchone()
        return self._row(row) if row else None

    def list_licenses(self) -> list[LicenseRow]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM licenses ORDER BY created_at DESC").fetchall()
        return [self._row(r) for r in rows]

    def log_activation(
        self,
        license_id: str | None,
        hardware_id: str,
        ip: str,
        success: bool,
        message: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO activation_log (license_id, hardware_id, ip, success, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (license_id, hardware_id, ip, 1 if success else 0, message, _now()),
            )
            conn.commit()

    def activate(
        self,
        license_id: str,
        hardware_id: str,
        license_key: str,
    ) -> LicenseRow:
        hwid = hardware_id.replace("-", "").upper()
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE licenses SET
                    hardware_id = ?,
                    status = 'active',
                    activated_at = COALESCE(activated_at, ?),
                    last_seen_at = ?,
                    license_key = ?
                WHERE id = ?
                """,
                (hwid, now, now, license_key, license_id),
            )
            conn.commit()
        return self.get_license(license_id)

    def touch(self, license_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE licenses SET last_seen_at = ? WHERE id = ?",
                (_now(), license_id),
            )
            conn.commit()

    def revoke(self, license_id: str) -> LicenseRow:
        with self._connect() as conn:
            conn.execute(
                "UPDATE licenses SET status = 'revoked' WHERE id = ?",
                (license_id,),
            )
            conn.commit()
        return self.get_license(license_id)

    def reset_hardware(self, license_id: str) -> LicenseRow:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE licenses SET
                    hardware_id = NULL,
                    status = 'pending',
                    license_key = NULL,
                    activated_at = NULL
                WHERE id = ?
                """,
                (license_id,),
            )
            conn.commit()
        return self.get_license(license_id)

    def extend(self, license_id: str, days: int) -> LicenseRow:
        lic = self.get_license(license_id)
        base = lic.expires_at if lic.expires_at and lic.expires_at > _now() else _now()
        new_exp = base + days * 86400
        with self._connect() as conn:
            conn.execute(
                "UPDATE licenses SET expires_at = ?, status = 'active' WHERE id = ?",
                (new_exp, license_id),
            )
            conn.commit()
        return self.get_license(license_id)

    def stats(self) -> dict[str, int]:
        rows = self.list_licenses()
        counts = {
            "total": 0,
            "pending": 0,
            "locked": 0,
            "active": 0,
            "expired": 0,
            "revoked": 0,
            "expiring_soon": 0,
        }
        soon = _now() + 7 * 86400
        for lic in rows:
            counts["total"] += 1
            status = lic.effective_status()
            counts[status] = counts.get(status, 0) + 1
            if (
                lic.expires_at
                and status == "active"
                and lic.expires_at <= soon
            ):
                counts["expiring_soon"] += 1
        return counts

    def recent_log(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT l.*, lic.customer_name, lic.activation_code
                FROM activation_log l
                LEFT JOIN licenses lic ON lic.id = l.license_id
                ORDER BY l.created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
