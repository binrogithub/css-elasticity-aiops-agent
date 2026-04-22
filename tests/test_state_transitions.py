from datetime import datetime, timezone

from app.config import Settings
from app.nodes.should_run_ai_review import route_after_should_run_ai
from app.nodes.should_run_ai_review import should_run_ai_review_node
from app.state import AgentState


class _Runtime:
    settings = Settings(SCALE_IN_LOW_LOAD_MINUTES=30)


class _BalancedRuntime:
    settings = Settings(ELASTICITY_STRATEGY_PROFILE="balanced")


def test_routes_to_ai_when_required():
    assert route_after_should_run_ai(AgentState(should_run_ai=True)) == "ai_decide"


def test_routes_to_persist_when_ai_skipped():
    assert route_after_should_run_ai(AgentState(should_run_ai=False)) == "persist_run"


def test_pending_operation_skips_ai_review():
    node = should_run_ai_review_node(_Runtime())
    state = node(AgentState(pending_operation=True, spike_detected=True))
    assert not state.should_run_ai


def test_fast_scale_in_review_when_extra_data_nodes_and_low_load():
    node = should_run_ai_review_node(_Runtime())
    state = node(
        AgentState(
            topology={"node_types": {"ess": {"count": 80}}},
            node_limits={"ess": {"min": 60}},
            metadata={"estimated_low_load_minutes": 30},
        )
    )
    assert state.should_run_ai


def test_fast_scale_in_review_uses_effective_profile_low_load_window():
    node = should_run_ai_review_node(_BalancedRuntime())
    state = node(
        AgentState(
            topology={"node_types": {"ess": {"count": 80}}},
            node_limits={"ess": {"min": 60}},
            last_ai_check_time=datetime.now(timezone.utc),
            metadata={"estimated_low_load_minutes": 10},
        )
    )
    assert not state.should_run_ai
