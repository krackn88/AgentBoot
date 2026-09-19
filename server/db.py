from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "checker.db"

FINAL_STATUSES = {"hit", "fail"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def combo_key(email: str, password: str) -> str:
    normalized = f"{email.strip().lower()}:{password}"
    return hashlib.sha256(normalized.encode()).hexdigest()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS hits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                line TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                points INTEGER DEFAULT 0,
                member_credits INTEGER DEFAULT 0,
                store_credit_balance REAL DEFAULT 0,
                cc TEXT,
                address TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_hits_created ON hits(created_at DESC);

            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS checked_combos (
                combo_key TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                status TEXT NOT NULL,
                checked_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_checked_at ON checked_combos(checked_at DESC);
            """
        )


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_state(key: str, default: str = "") -> str:
    with connect() as conn:
        row = conn.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_state(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO app_state (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_session() -> dict[str, Any]:
    return {
        "combos": get_state("combos"),
        "proxies": get_state("proxies"),
        "threads": int(get_state("threads", "5") or "5"),
        "checked_count": count_checked_combos(),
    }


def save_session(combos: str, proxies: str, threads: int | str) -> None:
    set_state("combos", combos)
    set_state("proxies", proxies)
    set_state("threads", str(threads))


def count_checked_combos() -> int:
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM checked_combos").fetchone()
        return int(row["n"])


def is_combo_checked(email: str, password: str) -> bool:
    key = combo_key(email, password)
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM checked_combos WHERE combo_key = ?",
            (key,),
        ).fetchone()
        return row is not None


def mark_combo_checked(email: str, password: str, status: str) -> None:
    key = combo_key(email, password)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO checked_combos (combo_key, email, password, status, checked_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(combo_key) DO UPDATE SET
                status = excluded.status,
                checked_at = excluded.checked_at
            """,
            (key, email, password, status, _utc_now()),
        )


def clear_checked_combos() -> int:
    with connect() as conn:
        cur = conn.execute("DELETE FROM checked_combos")
        return cur.rowcount


def insert_hit(line: str, email: str, password: str, data: dict[str, Any]) -> int | None:
    with connect() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO hits (line, email, password, points, member_credits,
                                  store_credit_balance, cc, address, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    line,
                    email,
                    password,
                    int(data.get("points") or 0),
                    int(data.get("member_credits") or 0),
                    float(data.get("store_credit_balance") or 0),
                    data.get("cc"),
                    data.get("address"),
                    _utc_now(),
                ),
            )
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None


def list_hits() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM hits ORDER BY created_at DESC, id DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def delete_hits(ids: list[int]) -> int:
    if not ids:
        return 0
    placeholders = ",".join("?" * len(ids))
    with connect() as conn:
        cur = conn.execute(f"DELETE FROM hits WHERE id IN ({placeholders})", ids)
        return cur.rowcount


def clear_hits() -> int:
    with connect() as conn:
        cur = conn.execute("DELETE FROM hits")
        return cur.rowcount
