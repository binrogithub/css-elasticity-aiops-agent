from app.db import init_db, connect
from app.models.actions import ActionResult
from app.models.metrics import MetricsSnapshot
from app.repositories.actions_repo import ActionsRepository
from app.repositories.metrics_repo import MetricsRepository


def test_metrics_persistence_roundtrip(tmp_path):
    db_path = tmp_path / "agent.sqlite3"
    init_db(str(db_path))
    conn = connect(str(db_path))
    repo = MetricsRepository(conn)
    repo.save("run-1", MetricsSnapshot(cpu_avg=12))
    rows = repo.recent()
    assert rows[0]["cpu_avg"] == 12


def test_action_event_persistence(tmp_path):
    db_path = tmp_path / "agent.sqlite3"
    init_db(str(db_path))
    conn = connect(str(db_path))
    repo = ActionsRepository(conn)
    result = ActionResult(
        requested_action="scale_out",
        executed_action="scale_out",
        node_type="ess-client",
        applied_delta=2,
        status="success",
    )
    repo.save_action("run-1", result)
    row = conn.execute("SELECT action_id, phase, status FROM action_events").fetchone()
    assert row["action_id"] == result.action_id
    assert row["phase"] == result.phase
    assert row["status"] == result.status
    assert "scale_out_delta_total" in repo.summarize_recent_actions()
