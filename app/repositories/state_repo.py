"""Agent state persistence."""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


class StateRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def set(self, key: str, value: Any) -> None:
        self.conn.execute(
            """
            INSERT INTO agent_state(key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at
            """,
            (key, json.dumps(value, default=str), datetime.now(timezone.utc).isoformat()),
        )
        self.conn.commit()

    def get(self, key: str) -> Any | None:
        row = self.conn.execute("SELECT value_json FROM agent_state WHERE key = ?", (key,)).fetchone()
        return json.loads(row["value_json"]) if row else None

    def delete(self, key: str) -> None:
        self.conn.execute("DELETE FROM agent_state WHERE key = ?", (key,))
        self.conn.commit()

    def save_scheduler_run(
        self,
        run_id: str,
        trigger_type: str,
        status: str,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        started_at = started_at or datetime.now(timezone.utc)
        finished_at = finished_at or datetime.now(timezone.utc)
        self.conn.execute(
            """
            INSERT INTO scheduler_runs(run_id, started_at, finished_at, trigger_type, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, started_at.isoformat(), finished_at.isoformat(), trigger_type, status),
        )
        self.conn.commit()
