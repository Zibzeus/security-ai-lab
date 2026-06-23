import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = Lock()
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self.connect()) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    detail_json TEXT NOT NULL
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge USING fts5(
                    source UNINDEXED,
                    title,
                    content,
                    tokenize='porter unicode61'
                );
                """
            )
            db.commit()

    def audit(self, case_id: str, event: str, detail: dict[str, Any]) -> None:
        with self._lock, closing(self.connect()) as db:
            db.execute(
                "INSERT INTO audit_log(created_at, case_id, event, detail_json) VALUES (?, ?, ?, ?)",
                (
                    datetime.now(UTC).isoformat(),
                    case_id,
                    event,
                    json.dumps(detail, ensure_ascii=True, default=str),
                ),
            )
            db.commit()

    def index_document(self, source: str, title: str, content: str) -> None:
        with self._lock, closing(self.connect()) as db:
            db.execute("DELETE FROM knowledge WHERE source = ?", (source,))
            db.execute(
                "INSERT INTO knowledge(source, title, content) VALUES (?, ?, ?)",
                (source, title, content),
            )
            db.commit()

    def search(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        terms = [term for term in query.replace('"', " ").split() if len(term) > 2]
        if not terms:
            return []
        fts_query = " OR ".join(f'"{term}"' for term in terms[:12])
        with closing(self.connect()) as db:
            rows = db.execute(
                """
                SELECT source, title, snippet(knowledge, 2, '[', ']', '...', 32) AS excerpt
                FROM knowledge WHERE knowledge MATCH ? ORDER BY rank LIMIT ?
                """,
                (fts_query, limit),
            ).fetchall()
        return [dict(row) for row in rows]
