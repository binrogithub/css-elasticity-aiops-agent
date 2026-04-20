"""AI decision persistence."""

import sqlite3
from datetime import datetime, timezone

from app.models.decisions import AIDecision


class DecisionsRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def save(self, run_id: str, raw_response: str | None, decision: AIDecision) -> None:
        self.conn.execute(
            "INSERT INTO ai_decisions(run_id, created_at, raw_response, parsed_json) VALUES (?, ?, ?, ?)",
            (run_id, datetime.now(timezone.utc).isoformat(), raw_response, decision.model_dump_json()),
        )
        self.conn.commit()
