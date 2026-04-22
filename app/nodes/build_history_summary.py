"""build_history_summary node."""

from app.runtime import Runtime
from app.services.history_summary import (
    estimate_low_load_minutes,
    summarize_business_trend,
    summarize_metrics_history,
    summarize_pair,
)
from app.services.scaling_advisor import (
    data_node_count,
    data_node_limits,
    recommend_data_scale_in_delta,
    recommend_data_scale_out_delta,
)
from app.services.strategy_profile import strategy_summary
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
        current_data_nodes = data_node_count(state.topology, state.current_nodes)
        data_limits = data_node_limits(state.node_limits, runtime.settings)
        data_scale_out_advice = recommend_data_scale_out_delta(
            recent,
            current_data_nodes=current_data_nodes,
            node_limits=data_limits,
            settings=runtime.settings,
            sample_interval_seconds=runtime.settings.resource_check_interval_seconds,
        )
        recent_actions = runtime.actions_repo.recent_actions(limit=50)
        data_scale_in_advice = recommend_data_scale_in_delta(
            recent_actions=recent_actions,
            current_data_nodes=current_data_nodes,
            node_limits=data_limits,
            low_load_minutes=low_load_minutes,
            settings=runtime.settings,
        )
        action_summary = runtime.actions_repo.summarize_recent_actions(limit=10)
        summary = f"{summarize_metrics_history(recent)} {business_trend} {pair} {action_summary}".strip()
        return state.patch(
            recent_history_summary=summary,
            metadata={
                **state.metadata,
                "estimated_low_load_minutes": low_load_minutes,
                "business_trend_summary": business_trend,
                "data_scale_out_advice": data_scale_out_advice,
                "data_scale_in_advice": data_scale_in_advice,
                "elasticity_strategy": strategy_summary(runtime.settings),
                "recent_action_summary": action_summary,
            },
        )

    return node
