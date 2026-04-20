"""build_history_summary node."""

from app.runtime import Runtime
from app.services.history_summary import (
    estimate_low_load_minutes,
    summarize_business_trend,
    summarize_metrics_history,
    summarize_pair,
)
from app.state import AgentState


def build_history_summary_node(runtime: Runtime):
    def node(state: AgentState) -> AgentState:
        recent = runtime.metrics_repo.recent(limit=30)
        pair = summarize_pair(state.last_metrics, state.prev_metrics) if state.last_metrics else ""
        business_trend = summarize_business_trend(
            recent,
            sample_interval_seconds=runtime.settings.resource_check_interval_seconds,
        )
        low_load_minutes = estimate_low_load_minutes(
            recent,
            sample_interval_seconds=runtime.settings.resource_check_interval_seconds,
        )
        action_summary = runtime.actions_repo.summarize_recent_actions(limit=10)
        summary = f"{summarize_metrics_history(recent)} {business_trend} {pair} {action_summary}".strip()
        return state.patch(
            recent_history_summary=summary,
            metadata={
                **state.metadata,
                "estimated_low_load_minutes": low_load_minutes,
                "business_trend_summary": business_trend,
                "recent_action_summary": action_summary,
            },
        )

    return node
