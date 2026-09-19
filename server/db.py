from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "checker.db"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
