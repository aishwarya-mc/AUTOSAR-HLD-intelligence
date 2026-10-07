from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT, get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    filename TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    document_id TEXT NOT NULL,
    finding_id TEXT NOT NULL,
    status TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    comment TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (document_id, finding_id)
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    user TEXT NOT NULL,
    role TEXT NOT NULL,
    action TEXT NOT NULL,
    resource TEXT,
    detail TEXT
);
"""


def _sqlite_path(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("Only sqlite:/// database URLs are supported")
    path = Path(database_url[len(prefix):])
    return path if path.is_absolute() else PROJECT_ROOT / path


class DocumentStore:
    """SQLite persistence for processed documents (JSON payload) and review actions."""

    def __init__(self, database_url: str | None = None):
        url = database_url or get_settings().database_url
        if url == "sqlite:///:memory:":
            target = ":memory:"
        else:
            path = _sqlite_path(url)
            path.parent.mkdir(parents=True, exist_ok=True)
            target = str(path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(target, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)

    def save_document(self, metadata: dict, payload: dict[str, Any], status: str = "processed") -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?,?)",
                (
                    metadata["document_id"],
                    metadata["version"],
                    metadata["filename"],
                    status,
                    metadata.get("created_at") or datetime.now(timezone.utc).isoformat(),
                    json.dumps(metadata),
                    json.dumps(payload),
                ),
            )

    def list_documents(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT metadata, status FROM documents ORDER BY created_at DESC"
            ).fetchall()
        return [{**json.loads(r["metadata"]), "status": r["status"]} for r in rows]

    def get_metadata(self, document_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT metadata, status FROM documents WHERE document_id=?", (document_id,)
            ).fetchone()
        return {**json.loads(row["metadata"]), "status": row["status"]} if row else None

    def get_payload(self, document_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM documents WHERE document_id=?", (document_id,)
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def delete_document(self, document_id: str) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute("DELETE FROM documents WHERE document_id=?", (document_id,))
            self._conn.execute("DELETE FROM reviews WHERE document_id=?", (document_id,))
        return cur.rowcount > 0

    def log_audit(self, user: str, role: str, action: str, resource: str = "", detail: str = "") -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO audit_log (ts, user, role, action, resource, detail) VALUES (?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), user, role, action, resource, detail[:500]),
            )

    def list_audit(self, limit: int = 200) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def save_review(
        self, document_id: str, finding_id: str, status: str, reviewer: str, comment: str | None
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO reviews VALUES (?,?,?,?,?,?)",
                (document_id, finding_id, status, reviewer, comment,
                 datetime.now(timezone.utc).isoformat()),
            )

    def list_reviews(self, document_id: str) -> dict[str, dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM reviews WHERE document_id=?", (document_id,)
            ).fetchall()
        return {r["finding_id"]: dict(r) for r in rows}
