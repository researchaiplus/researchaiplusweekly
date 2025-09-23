"""Task repository implementations used by the API layer."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Protocol
from uuid import uuid4

from newsletter.api.models import ResultMetadata, TaskProgress, TaskRecord, TaskStatus


class TaskStore(Protocol):
    """Interface for persisting task state."""

    def create(self, *, url_count: int, payload: dict | None = None) -> TaskRecord:
        ...

    def get(self, task_id: str) -> TaskRecord | None:
        ...

    def mark_processing(self, task_id: str) -> TaskRecord:
        ...

    def mark_completed(
        self,
        task_id: str,
        *,
        markdown_content: str,
        metadata: ResultMetadata,
        progress: TaskProgress,
    ) -> TaskRecord:
        ...

    def mark_failed(self, task_id: str, *, error: str, progress: TaskProgress | None = None) -> TaskRecord:
        ...


class InMemoryTaskStore:
    """Thread-safe in-memory implementation of ``TaskStore``."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._tasks: dict[str, TaskRecord] = {}

    def create(self, *, url_count: int, payload: dict | None = None) -> TaskRecord:
        now = datetime.utcnow()
        task_id = str(uuid4())
        progress = TaskProgress(total_urls=url_count, processed=0, failed=0)
        record = TaskRecord(
            task_id=task_id,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
            progress=progress,
            original_payload=payload or {},
        )
        with self._lock:
            self._tasks[task_id] = record
        return record

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return None
            return record.model_copy(deep=True)

    def _update(self, task_id: str, **updates) -> TaskRecord:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                raise KeyError(task_id)
            for key, value in updates.items():
                setattr(record, key, value)
            record.updated_at = datetime.utcnow()
            self._tasks[task_id] = record
            return record.model_copy(deep=True)

    def mark_processing(self, task_id: str) -> TaskRecord:
        return self._update(task_id, status=TaskStatus.PROCESSING)

    def mark_completed(
        self,
        task_id: str,
        *,
        markdown_content: str,
        metadata: ResultMetadata,
        progress: TaskProgress,
    ) -> TaskRecord:
        return self._update(
            task_id,
            status=TaskStatus.COMPLETED,
            markdown_content=markdown_content,
            metadata=metadata,
            progress=progress,
            completed_at=datetime.utcnow(),
            error=None,
        )

    def mark_failed(self, task_id: str, *, error: str, progress: TaskProgress | None = None) -> TaskRecord:
        kwargs = {
            "status": TaskStatus.FAILED,
            "error": error,
            "completed_at": datetime.utcnow(),
        }
        if progress is not None:
            kwargs["progress"] = progress
        return self._update(task_id, **kwargs)


class SQLiteTaskStore:
    """SQLite-backed implementation of ``TaskStore`` for multi-process safety."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path, detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialise(self) -> None:
        create_sql = """
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT,
            total_urls INTEGER NOT NULL DEFAULT 0,
            processed INTEGER NOT NULL DEFAULT 0,
            failed INTEGER NOT NULL DEFAULT 0,
            markdown_content TEXT,
            metadata_json TEXT,
            error TEXT,
            original_payload_json TEXT NOT NULL
        )
        """
        with self._connect() as conn:
            conn.execute(create_sql)
            conn.commit()

    def create(self, *, url_count: int, payload: dict | None = None) -> TaskRecord:
        now = datetime.utcnow().isoformat()
        task_id = str(uuid4())
        payload_json = json.dumps(payload or {}, separators=(",", ":"))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks (task_id, status, created_at, updated_at, total_urls, processed, failed, original_payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    TaskStatus.PENDING.value,
                    now,
                    now,
                    url_count,
                    0,
                    0,
                    payload_json,
                ),
            )
            conn.commit()

        progress = TaskProgress(total_urls=url_count, processed=0, failed=0)
        return TaskRecord(
            task_id=task_id,
            status=TaskStatus.PENDING,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
            completed_at=None,
            progress=progress,
            markdown_content=None,
            metadata=None,
            error=None,
            original_payload=json.loads(payload_json),
        )

    def get(self, task_id: str) -> TaskRecord | None:
        with self._connect() as conn:
            cursor = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def mark_processing(self, task_id: str) -> TaskRecord:
        return self._update(task_id, status=TaskStatus.PROCESSING.value, completed_at=None)

    def mark_completed(
        self,
        task_id: str,
        *,
        markdown_content: str,
        metadata: ResultMetadata,
        progress: TaskProgress,
    ) -> TaskRecord:
        metadata_json = json.dumps(metadata.model_dump(), default=str, separators=(",", ":"))
        return self._update(
            task_id,
            status=TaskStatus.COMPLETED.value,
            markdown_content=markdown_content,
            metadata_json=metadata_json,
            processed=progress.processed,
            failed=progress.failed,
            total_urls=progress.total_urls,
            completed_at=datetime.utcnow().isoformat(),
            error=None,
        )

    def mark_failed(
        self, task_id: str, *, error: str, progress: TaskProgress | None = None
    ) -> TaskRecord:
        updates: dict[str, object] = {
            "status": TaskStatus.FAILED.value,
            "error": error,
            "completed_at": datetime.utcnow().isoformat(),
        }
        if progress is not None:
            updates.update(
                {
                    "processed": progress.processed,
                    "failed": progress.failed,
                    "total_urls": progress.total_urls,
                }
            )
        return self._update(task_id, **updates)

    def _update(self, task_id: str, **updates: object) -> TaskRecord:
        if not updates:
            record = self.get(task_id)
            if record is None:
                raise KeyError(task_id)
            return record

        columns = ", ".join(f"{column} = ?" for column in updates)
        values = list(updates.values())
        now = datetime.utcnow().isoformat()
        query = f"UPDATE tasks SET {columns}, updated_at = ? WHERE task_id = ?"
        values.append(now)
        values.append(task_id)

        with self._connect() as conn:
            cursor = conn.execute(query, values)
            if cursor.rowcount == 0:
                raise KeyError(task_id)
            conn.commit()

        record = self.get(task_id)
        if record is None:
            raise KeyError(task_id)
        return record

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> TaskRecord:
        progress = TaskProgress(
            total_urls=row["total_urls"], processed=row["processed"], failed=row["failed"]
        )
        metadata = None
        if row["metadata_json"]:
            data = json.loads(row["metadata_json"])
            metadata = ResultMetadata(**data)
        original_payload = json.loads(row["original_payload_json"])
        created_at = datetime.fromisoformat(row["created_at"])
        updated_at = datetime.fromisoformat(row["updated_at"])
        completed_at = (
            datetime.fromisoformat(row["completed_at"])
            if row["completed_at"] is not None
            and row["completed_at"] != ""
            else None
        )

        return TaskRecord(
            task_id=row["task_id"],
            status=TaskStatus(row["status"]),
            created_at=created_at,
            updated_at=updated_at,
            completed_at=completed_at,
            progress=progress,
            markdown_content=row["markdown_content"],
            metadata=metadata,
            error=row["error"],
            original_payload=original_payload,
        )


__all__ = ["InMemoryTaskStore", "SQLiteTaskStore", "TaskStore"]
