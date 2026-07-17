import json
import sqlite3
import threading
from datetime import datetime

from .interfaces import MemoryRepository
from .models import Experience, ExperienceStatus, SearchQuery


class SqliteMemoryRepository(MemoryRepository):
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self):
        return self._conn

    def _init_db(self):
        with self._lock, self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS experiences (
                    memory_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    category TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    importance REAL NOT NULL,
                    tags TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    status TEXT NOT NULL
                )
            """)
            conn.commit()

    def save(self, experience: Experience) -> None:
        with self._lock, self._get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO experiences 
                    (memory_id, timestamp, source, category, confidence, 
                     importance, tags, payload, metadata, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        experience.memory_id,
                        experience.timestamp.isoformat(),
                        experience.source,
                        experience.category,
                        experience.confidence,
                        experience.importance,
                        json.dumps(experience.tags),
                        json.dumps(experience.payload),
                        json.dumps(experience.metadata),
                        experience.status.value,
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError as e:
                raise ValueError(
                    f"Memory with ID {experience.memory_id} already exists."
                ) from e

    def get(self, memory_id: str) -> Experience:
        with self._lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM experiences WHERE memory_id = ?", (memory_id,)
            ).fetchone()
            if not row:
                raise KeyError(f"Memory with ID {memory_id} not found.")
            return self._row_to_experience(row)

    def search(self, query: SearchQuery) -> list[Experience]:
        sql = "SELECT * FROM experiences WHERE 1=1"
        params = []

        if query.memory_id:
            sql += " AND memory_id = ?"
            params.append(query.memory_id)
        if query.category:
            sql += " AND category = ?"
            params.append(query.category)
        if query.start_time:
            sql += " AND timestamp >= ?"
            params.append(query.start_time.isoformat())
        if query.end_time:
            sql += " AND timestamp <= ?"
            params.append(query.end_time.isoformat())

        with self._lock, self._get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()

        experiences = [self._row_to_experience(row) for row in rows]

        # Tags are stored as JSON strings, so we filter them in Python for simplicity
        if query.tags:
            query_tags = set(query.tags)
            experiences = [e for e in experiences if query_tags.issubset(set(e.tags))]

        return experiences

    def update_status(self, memory_id: str, status: ExperienceStatus) -> None:
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE experiences SET status = ? WHERE memory_id = ?",
                (status.value, memory_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Memory with ID {memory_id} not found.")
            conn.commit()

    def _row_to_experience(self, row: sqlite3.Row) -> Experience:
        return Experience(
            memory_id=row["memory_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            source=row["source"],
            category=row["category"],
            confidence=row["confidence"],
            importance=row["importance"],
            tags=json.loads(row["tags"]),
            payload=json.loads(row["payload"]),
            metadata=json.loads(row["metadata"]),
            status=ExperienceStatus(row["status"]),
        )
