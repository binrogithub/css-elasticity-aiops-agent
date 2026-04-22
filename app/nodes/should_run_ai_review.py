"""should_run_ai_review node."""

from datetime import datetime, timezone

from app.runtime import Runtime
from app.services.strategy_profile import effective_scale_in_low_load_minutes
from app.state import AgentState


def should_run_ai_review_node(runtime: Runtime):
    def node(state: AgentState) -> AgentState:
        now = datetime.now(timezone.utc)
        if state.pending_operation:
            return state.patch(should_run_ai=False)
        if state.spike_detected:
            return state.patch(should_run_ai=True)
        low_load_minutes = int(state.metadata.get("estimated_low_load_minutes", 0))
        data_topology = state.topology.get("node_types", {}).get("ess", {})
        data_limits = state.node_limits.get("ess", {})
        data_count = int(data_topology.get("count", 0))
        data_min = int(data_limits.get("min", 0))
        required_low_load = effective_scale_in_low_load_minutes(runtime.settings)
        if (
            runtime.settings.fast_scale_in_review_enabled
            and data_count > data_min
            and low_load_minutes >= required_low_load
        ):
            return state.patch(should_run_ai=True)
        if state.last_ai_check_time is None:
            return state.patch(should_run_ai=True)
        elapsed = (now - state.last_ai_check_time).total_seconds()
        return state.patch(should_run_ai=elapsed >= runtime.settings.ai_check_interval_seconds)

    return node


def route_after_should_run_ai(state: AgentState) -> str:
    return "ai_decide" if state.should_run_ai else "persist_run"
