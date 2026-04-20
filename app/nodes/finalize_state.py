"""finalize_state node."""

from datetime import datetime, timezone

from app.runtime import Runtime
from app.state import AgentState


def finalize_state_node(runtime: Runtime):
    def node(state: AgentState) -> AgentState:
        status = "failed" if state.errors else "success"
        runtime.state_repo.save_scheduler_run(
            state.run_id,
            state.metadata.get("trigger_type", "manual"),
            status,
            started_at=state.now_ts,
            finished_at=datetime.now(timezone.utc),
        )
        return state

    return node
