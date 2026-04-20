from app.nodes.should_run_ai_review import route_after_should_run_ai
from app.nodes.should_run_ai_review import should_run_ai_review_node
from app.state import AgentState


class _Runtime:
    class _Settings:
        ai_check_interval_seconds = 1800
        fast_scale_in_review_enabled = True
        scale_in_low_load_minutes = 30

    settings = _Settings()


def test_routes_to_ai_when_required():
    assert route_after_should_run_ai(AgentState(should_run_ai=True)) == "ai_decide"


def test_routes_to_persist_when_ai_skipped():
    assert route_after_should_run_ai(AgentState(should_run_ai=False)) == "persist_run"


def test_pending_operation_skips_ai_review():
    node = should_run_ai_review_node(_Runtime())
    state = node(AgentState(pending_operation=True, spike_detected=True))
    assert not state.should_run_ai


def test_fast_scale_in_review_when_extra_clients_and_low_load():
    node = should_run_ai_review_node(_Runtime())
    state = node(
        AgentState(
            topology={"node_types": {"ess-client": {"count": 4}}},
            node_limits={"ess-client": {"min": 2}},
            metadata={"estimated_low_load_minutes": 30},
        )
    )
    assert state.should_run_ai
