import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any, Iterable


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
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY,
                    profile TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS case_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    evidence_json TEXT NOT NULL DEFAULT '[]',
                    tool_results_json TEXT NOT NULL DEFAULT '[]',
                    citations_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(case_id) REFERENCES cases(id)
                );
                CREATE INDEX IF NOT EXISTS idx_case_messages_case
                    ON case_messages(case_id, id);
                CREATE TABLE IF NOT EXISTS pending_approvals (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    justification TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(case_id) REFERENCES cases(id)
                );
                CREATE INDEX IF NOT EXISTS idx_pending_approvals_case
                    ON pending_approvals(case_id, created_at);
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

    def replace_document_chunks(
        self,
        source_root: str,
        chunks: list[dict[str, str]],
    ) -> int:
        with self._lock, closing(self.connect()) as db:
            db.execute(
                "DELETE FROM knowledge WHERE source = ? OR source LIKE ?",
                (source_root, f"{source_root}#%"),
            )
            db.executemany(
                "INSERT INTO knowledge(source, title, content) VALUES (?, ?, ?)",
                [
                    (chunk["source"], chunk["title"], chunk["content"])
                    for chunk in chunks
                ],
            )
            db.commit()
        return len(chunks)

    def rebuild_knowledge(
        self,
        documents: Iterable[list[dict[str, str]]],
    ) -> tuple[int, int]:
        document_count = 0
        chunk_count = 0
        with self._lock, closing(self.connect()) as db:
            try:
                db.execute("DELETE FROM knowledge")
                for chunks in documents:
                    db.executemany(
                        """
                        INSERT INTO knowledge(source, title, content)
                        VALUES (?, ?, ?)
                        """,
                        [
                            (
                                chunk["source"],
                                chunk["title"],
                                chunk["content"],
                            )
                            for chunk in chunks
                        ],
                    )
                    document_count += 1
                    chunk_count += len(chunks)
                db.commit()
            except Exception:
                db.rollback()
                raise
        return document_count, chunk_count

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

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _decode_json(value: str, fallback: Any) -> Any:
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return fallback

    def create_case(
        self, case_id: str, profile: str, title: str
    ) -> dict[str, Any]:
        now = self._now()
        with self._lock, closing(self.connect()) as db:
            db.execute(
                """
                INSERT INTO cases(id, profile, title, status, created_at, updated_at)
                VALUES (?, ?, ?, 'open', ?, ?)
                """,
                (case_id, profile, title, now, now),
            )
            db.commit()
        return self.get_case(case_id) or {}

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        with closing(self.connect()) as db:
            row = db.execute(
                """
                SELECT id, profile, title, status, created_at, updated_at
                FROM cases WHERE id = ?
                """,
                (case_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_cases(self, limit: int = 100) -> list[dict[str, Any]]:
        with closing(self.connect()) as db:
            rows = db.execute(
                """
                SELECT
                    c.id, c.profile, c.title, c.status, c.created_at, c.updated_at,
                    COUNT(m.id) AS message_count
                FROM cases c
                LEFT JOIN case_messages m ON m.case_id = c.id
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_message(
        self,
        case_id: str,
        role: str,
        content: str,
        *,
        evidence: list[str] | None = None,
        tool_results: list[dict[str, Any]] | None = None,
        citations: list[str] | None = None,
    ) -> dict[str, Any]:
        now = self._now()
        with self._lock, closing(self.connect()) as db:
            cursor = db.execute(
                """
                INSERT INTO case_messages(
                    case_id, role, content, evidence_json,
                    tool_results_json, citations_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case_id,
                    role,
                    content,
                    json.dumps(evidence or [], ensure_ascii=True),
                    json.dumps(tool_results or [], ensure_ascii=True, default=str),
                    json.dumps(citations or [], ensure_ascii=True),
                    now,
                ),
            )
            db.execute(
                "UPDATE cases SET updated_at = ? WHERE id = ?",
                (now, case_id),
            )
            db.commit()
            message_id = int(cursor.lastrowid)
        return self.get_message(message_id) or {}

    def get_message(self, message_id: int) -> dict[str, Any] | None:
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT * FROM case_messages WHERE id = ?",
                (message_id,),
            ).fetchone()
        return self._message_row(row) if row else None

    def list_messages(
        self, case_id: str, limit: int = 500
    ) -> list[dict[str, Any]]:
        with closing(self.connect()) as db:
            rows = db.execute(
                """
                SELECT * FROM case_messages
                WHERE case_id = ? ORDER BY id ASC LIMIT ?
                """,
                (case_id, limit),
            ).fetchall()
        return [self._message_row(row) for row in rows]

    def recent_conversation(
        self, case_id: str, limit: int, max_chars: int
    ) -> list[dict[str, str]]:
        with closing(self.connect()) as db:
            rows = db.execute(
                """
                SELECT role, content FROM case_messages
                WHERE case_id = ? AND role IN ('user', 'assistant')
                ORDER BY id DESC LIMIT ?
                """,
                (case_id, limit),
            ).fetchall()
        return [
            {"role": str(row["role"]), "content": str(row["content"])[:max_chars]}
            for row in reversed(rows)
        ]

    def _message_row(self, row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["evidence"] = self._decode_json(
            result.pop("evidence_json"), []
        )
        result["tool_results"] = self._decode_json(
            result.pop("tool_results_json"), []
        )
        result["citations"] = self._decode_json(
            result.pop("citations_json"), []
        )
        return result

    def create_approval(
        self,
        approval_id: str,
        case_id: str,
        capability: str,
        arguments: dict[str, Any],
        justification: str,
    ) -> dict[str, Any]:
        now = self._now()
        with self._lock, closing(self.connect()) as db:
            db.execute(
                """
                INSERT INTO pending_approvals(
                    id, case_id, capability, arguments_json,
                    justification, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    approval_id,
                    case_id,
                    capability,
                    json.dumps(arguments, ensure_ascii=True, default=str),
                    justification,
                    now,
                    now,
                ),
            )
            db.execute(
                "UPDATE cases SET status = 'pending_approval', updated_at = ? WHERE id = ?",
                (now, case_id),
            )
            db.commit()
        return self.get_approval(approval_id) or {}

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT * FROM pending_approvals WHERE id = ?",
                (approval_id,),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["arguments"] = self._decode_json(
            result.pop("arguments_json"), {}
        )
        return result

    def list_approvals(
        self, case_id: str, status: str | None = None
    ) -> list[dict[str, Any]]:
        query = "SELECT id FROM pending_approvals WHERE case_id = ?"
        params: list[Any] = [case_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        with closing(self.connect()) as db:
            rows = db.execute(query, params).fetchall()
        return [
            item
            for row in rows
            if (item := self.get_approval(str(row["id"]))) is not None
        ]

    def claim_approval(self, approval_id: str) -> dict[str, Any] | None:
        now = self._now()
        with self._lock, closing(self.connect()) as db:
            cursor = db.execute(
                """
                UPDATE pending_approvals
                SET status = 'executing', updated_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (now, approval_id),
            )
            db.commit()
        if cursor.rowcount != 1:
            return None
        return self.get_approval(approval_id)

    def set_approval_status(self, approval_id: str, status: str) -> None:
        now = self._now()
        with self._lock, closing(self.connect()) as db:
            row = db.execute(
                "SELECT case_id FROM pending_approvals WHERE id = ?",
                (approval_id,),
            ).fetchone()
            if not row:
                return
            case_id = str(row["case_id"])
            db.execute(
                """
                UPDATE pending_approvals SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, now, approval_id),
            )
            pending = db.execute(
                """
                SELECT COUNT(*) FROM pending_approvals
                WHERE case_id = ? AND status IN ('pending', 'executing')
                """,
                (case_id,),
            ).fetchone()[0]
            db.execute(
                "UPDATE cases SET status = ?, updated_at = ? WHERE id = ?",
                ("pending_approval" if pending else "open", now, case_id),
            )
            db.commit()

    def list_audit(
        self, case_id: str | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        query = """
            SELECT id, created_at, case_id, event, detail_json
            FROM audit_log
        """
        params: list[Any] = []
        if case_id:
            query += " WHERE case_id = ?"
            params.append(case_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with closing(self.connect()) as db:
            rows = db.execute(query, params).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["detail"] = self._decode_json(item.pop("detail_json"), {})
            result.append(item)
        return result
