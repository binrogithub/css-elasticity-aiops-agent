"""Action and verification persistence."""

import sqlite3
from datetime import datetime, timedelta, timezone

from app.models.actions import ActionResult, VerificationResult


class ActionsRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def save_action(self, run_id: str, result: ActionResult) -> None:
        self.conn.execute(
            "INSERT INTO actions(run_id, created_at, payload_json) VALUES (?, ?, ?)",
            (run_id, datetime.now(timezone.utc).isoformat(), result.model_dump_json()),
        )
        self.save_action_event(run_id, result)
        self.conn.commit()

    def save_action_event(self, run_id: str, result: ActionResult) -> None:
        self.conn.execute(
            """
            INSERT INTO action_events(action_id, run_id, created_at, phase, status, message, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.action_id,
                run_id,
                datetime.now(timezone.utc).isoformat(),
                result.phase,
                result.status,
                result.message,
                result.model_dump_json(),
            ),
        )

    def save_verification(self, run_id: str, result: VerificationResult) -> None:
        self.conn.execute(
            "INSERT INTO verifications(run_id, created_at, payload_json) VALUES (?, ?, ?)",
            (run_id, datetime.now(timezone.utc).isoformat(), result.model_dump_json()),
        )
        self.conn.commit()

    def successful_scaling_count_since(self, since: datetime) -> int:
        rows = self.conn.execute(
            "SELECT payload_json FROM actions WHERE created_at >= ?",
            (since.isoformat(),),
        ).fetchall()
        count = 0
        for row in rows:
            result = ActionResult.model_validate_json(row["payload_json"])
            if result.status == "success" and result.executed_action in {"scale_out", "scale_in", "change_flavor"}:
                count += 1
        return count

    def successful_scaling_count_last_24h(self) -> int:
        return self.successful_scaling_count_since(datetime.now(timezone.utc) - timedelta(days=1))

    def recent_actions(self, limit: int = 10) -> list[ActionResult]:
        rows = self.conn.execute(
            "SELECT payload_json FROM actions ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [ActionResult.model_validate_json(row["payload_json"]) for row in rows]

    def summarize_recent_actions(self, limit: int = 10) -> str:
        actions = self.recent_actions(limit=limit)
        if not actions:
            return "No historical scaling actions available."
        parts: list[str] = []
        scale_out_count = 0
        scale_in_count = 0
        scale_out_delta = 0
        scale_in_delta = 0
        for item in actions:
            if item.status != "success" or item.executed_action not in {"scale_out", "scale_in"}:
                continue
            if item.executed_action == "scale_out":
                scale_out_count += 1
                scale_out_delta += item.applied_delta
            elif item.executed_action == "scale_in":
                scale_in_count += 1
                scale_in_delta += item.applied_delta
            parts.append(
                f"{item.executed_action} {item.node_type} delta={item.applied_delta} "
                f"from={item.previous_node_count} to={item.new_node_count} "
                f"status={item.status} finished_at={item.finished_at.isoformat()}"
            )
        if not parts:
            return "Recent actions exist, but no successful scale-out or scale-in action is available."
        return (
            f"Recent successful scaling summary: scale_out_actions={scale_out_count}, "
            f"scale_out_delta_total={scale_out_delta}, scale_in_actions={scale_in_count}, "
            f"scale_in_delta_total={scale_in_delta}. Recent actions: "
            + " | ".join(parts[:limit])
        )
