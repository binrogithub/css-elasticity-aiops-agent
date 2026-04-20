"""Metrics persistence."""

import json
import sqlite3

from app.models.metrics import MetricsSnapshot


class MetricsRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def save(self, run_id: str, snapshot: MetricsSnapshot) -> None:
        self.conn.execute(
            "INSERT INTO metrics_snapshots(run_id, timestamp, payload_json) VALUES (?, ?, ?)",
            (run_id, snapshot.timestamp.isoformat(), snapshot.model_dump_json()),
        )
        self.conn.commit()

    def recent(self, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            "SELECT payload_json FROM metrics_snapshots ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]
