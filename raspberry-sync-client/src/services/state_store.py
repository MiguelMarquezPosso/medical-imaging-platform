"""SQLite-backed local queue.

Tracks files that have been observed but not yet successfully uploaded, so the
device survives reboots and long offline windows without re-uploading already
sent files.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_files_status ON files(status);
CREATE UNIQUE INDEX IF NOT EXISTS ix_files_sha ON files(sha256);
"""


class StateStore:
    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False)
        self._conn.executescript(_SCHEMA)

    def enqueue(self, path: str, sha256: str, size_bytes: int) -> bool:
        cur = self._conn.execute(
            "INSERT OR IGNORE INTO files(path, sha256, size_bytes) VALUES(?, ?, ?)",
            (path, sha256, size_bytes),
        )
        return cur.rowcount > 0

    def mark_uploaded(self, path: str) -> None:
        self._conn.execute(
            "UPDATE files SET status='uploaded', last_error=NULL, updated_at=CURRENT_TIMESTAMP WHERE path=?",
            (path,),
        )

    def mark_failed(self, path: str, error: str) -> None:
        self._conn.execute(
            """
            UPDATE files SET
                status='failed',
                last_error=?,
                attempts=attempts+1,
                updated_at=CURRENT_TIMESTAMP
            WHERE path=?
            """,
            (error[:512], path),
        )

    def mark_quarantined(self, path: str, error: str) -> None:
        self._conn.execute(
            "UPDATE files SET status='quarantined', last_error=?, updated_at=CURRENT_TIMESTAMP WHERE path=?",
            (error[:512], path),
        )

    def list_pending(self, limit: int = 100) -> list[tuple[str, str, int, int]]:
        cur = self._conn.execute(
            """
            SELECT path, sha256, size_bytes, attempts
            FROM files
            WHERE status IN ('pending', 'failed')
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,),
        )
        return cur.fetchall()
