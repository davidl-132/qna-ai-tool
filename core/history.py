"""Lưu lịch sử hỏi–đáp vào SQLite (file data/history.db, không đưa lên git)."""
import sqlite3
import time
from contextlib import closing

from . import config

DB_PATH = config.ROOT / "data" / "history.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  REAL    NOT NULL,
    page_title  TEXT,
    mode        TEXT,
    selection   TEXT    NOT NULL,
    question    TEXT,            -- câu hỏi tiếp (nếu có), rỗng với câu hỏi đầu tiên
    answer      TEXT    NOT NULL,
    provider    TEXT,
    model       TEXT
)
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def save(selection: str, answer: str, mode: str = "", page_title: str = "",
         question: str = "", provider: str = "", model: str = "") -> int:
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO history (created_at, page_title, mode, selection, question, answer, provider, model)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (time.time(), page_title, mode, selection, question, answer, provider, model),
        )
        return cur.lastrowid


def recent(limit: int = 20) -> list[dict]:
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def clear() -> int:
    with closing(_connect()) as conn, conn:
        return conn.execute("DELETE FROM history").rowcount
