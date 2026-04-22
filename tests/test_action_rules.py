from app.models.decisions import AIDecision
from app.services.validation import decision_to_action
from app.config import Settings
from app.executors.css_executor import CSSExecutor, _is_data_half_shrink_error


def test_scale_out_clamped_to_max_nodes():
    action, _, status = decision_to_action(
        AIDecision(decision="scale_out", node_type="ess-client", delta=5, reason="test", cooldown_minutes=30),
        current_nodes=4,
        min_nodes=1,
        max_nodes=5,
        cooldown_until=None,
        topology={"node_types": {"ess-client": {"count": 4}}},
        node_limits={"ess-client": {"min": 0, "max": 5}},
    )
    assert status == "validated"
    assert action.action == "scale_out"
    assert action.node_type == "ess-client"
    assert action.delta == 1


def test_client_scale_out_uses_ai_delta():
    action, _, status = decision_to_action(
        AIDecision(decision="scale_out", node_type="ess-client", delta=1, reason="pressure", cooldown_minutes=30),
        current_nodes=4,
        min_nodes=1,
        max_nodes=10,
        cooldown_until=None,
        topology={"node_types": {"ess-client": {"count": 4}}},
        node_limits={"ess-client": {"min": 0, "max": 10}},
        settings=Settings(),
    )
    assert status == "validated"
    assert action.action == "scale_out"
    assert action.delta == 1


def test_client_scale_out_ai_delta_respects_node_max_limit():
    action, _, _ = decision_to_action(
        AIDecision(decision="scale_out", node_type="ess-client", delta=5, reason="pressure", cooldown_minutes=30),
        current_nodes=8,
        min_nodes=1,
        max_nodes=10,
        cooldown_until=None,
        topology={"node_types": {"ess-client": {"count": 8}}},
        node_limits={"ess-client": {"min": 0, "max": 10}},
        settings=Settings(),
    )
    assert action.delta == 2


def test_client_scale_out_max_delta_caps_ai_recommendation():
    action, _, status = decision_to_action(
        AIDecision(decision="scale_out", node_type="ess-client", delta=10, reason="pressure", cooldown_minutes=30),
        current_nodes=4,
        min_nodes=1,
        max_nodes=20,
        cooldown_until=None,
        topology={"node_types": {"ess-client": {"count": 4}}},
        node_limits={"ess-client": {"min": 0, "max": 20}},
        settings=Settings(CSS_CLIENT_SCALE_OUT_MAX_DELTA=5),
    )
    assert status == "validated"
    assert action.action == "scale_out"
    assert action.delta == 5


def test_data_scale_out_min_and_max_delta_are_configurable():
    action, _, status = decision_to_action(
        AIDecision(decision="scale_out", node_type="ess", delta=1, reason="pressure", cooldown_minutes=30),
        current_nodes=20,
        min_nodes=1,
        max_nodes=200,
        cooldown_until=None,
        topology={"node_types": {"ess": {"count": 20}}},
        node_limits={"ess": {"min": 1, "max": 200}},
        settings=Settings(CSS_DATA_SCALE_OUT_MIN_DELTA=5, CSS_DATA_SCALE_OUT_MAX_DELTA=10),
    )
    assert status == "validated"
    assert action.action == "scale_out"
    assert action.delta == 5

    capped, _, _ = decision_to_action(
        AIDecision(decision="scale_out", node_type="ess", delta=50, reason="pressure", cooldown_minutes=30),
        current_nodes=20,
        min_nodes=1,
        max_nodes=200,
        cooldown_until=None,
        topology={"node_types": {"ess": {"count": 20}}},
        node_limits={"ess": {"min": 1, "max": 200}},
        settings=Settings(CSS_DATA_SCALE_OUT_MIN_DELTA=1, CSS_DATA_SCALE_OUT_MAX_DELTA=10),
    )
    assert capped.delta == 10


def test_scale_in_clamped_to_min_nodes():
    action, _, _ = decision_to_action(
        AIDecision(decision="scale_in", node_type="ess-client", delta=3, reason="test", cooldown_minutes=30),
        current_nodes=2,
        min_nodes=1,
        max_nodes=5,
        cooldown_until=None,
        topology={"node_types": {"ess-client": {"count": 2}}},
        node_limits={"ess-client": {"min": 1, "max": 5}},
        settings=Settings(CSS_TRAFFIC_ENTRY_MODE="load_balancer", CSS_CLIENT_SCALE_IN_ALLOWED=True),
    )
    assert action.action == "scale_in"
    assert action.delta == 1


def test_client_scale_in_uses_ai_delta():
    action, _, _ = decision_to_action(
        AIDecision(decision="scale_in", node_type="ess-client", delta=1, reason="low", cooldown_minutes=30),
        current_nodes=8,
        min_nodes=1,
        max_nodes=10,
        cooldown_until=None,
        topology={"node_types": {"ess-client": {"count": 8}}},
        node_limits={"ess-client": {"min": 3, "max": 10}},
        settings=Settings(
            CSS_TRAFFIC_ENTRY_MODE="load_balancer",
            CSS_CLIENT_SCALE_IN_ALLOWED=True,
        ),
    )
    assert action.action == "scale_in"
    assert action.delta == 1


def test_client_scale_in_blocked_without_load_balancer():
    action, _, status = decision_to_action(
        AIDecision(decision="scale_in", node_type="ess-client", delta=1, reason="low load", cooldown_minutes=30),
        current_nodes=2,
        min_nodes=1,
        max_nodes=5,
        cooldown_until=None,
        topology={"node_types": {"ess-client": {"count": 2}}},
        node_limits={"ess-client": {"min": 1, "max": 5}},
        settings=Settings(CSS_TRAFFIC_ENTRY_MODE="direct_ip", CSS_CLIENT_SCALE_IN_ALLOWED=True),
    )
    assert status == "blocked"
    assert action.action == "hold"


def test_data_scale_in_allowed_by_default():
    action, _, status = decision_to_action(
        AIDecision(decision="scale_in", node_type="ess", delta=1, reason="low load", cooldown_minutes=30),
        current_nodes=4,
        min_nodes=3,
        max_nodes=5,
        cooldown_until=None,
        topology={"node_types": {"ess": {"count": 4}}},
        node_limits={"ess": {"min": 3, "max": 5}},
        settings=Settings(),
    )
    assert status == "validated"
    assert action.action == "scale_in"
    assert action.delta == 1


def test_data_node_shrink_not_limited_by_half_rule():
    executor = CSSExecutor.__new__(CSSExecutor)
    executor.settings = Settings(CSS_NODE_TYPE="ess")
    assert executor._bounded_delta("scale_in", 1, current_nodes=2, min_nodes=1, max_nodes=3) == 1
    assert executor._bounded_delta("scale_in", 4, current_nodes=5, min_nodes=1, max_nodes=6) == 4
    assert executor._max_css_data_scale_in_delta(current_nodes=6, requested_delta=3) == 2


def test_css_half_shrink_error_detection():
    class Error:
        error_code = "CSS.0001"
        error_msg = '{"externalMessage":"the reduced instances number has exceeded the half of the size of data instances"}'

        def __str__(self):
            return self.error_msg

    assert _is_data_half_shrink_error(Error())


def test_client_zero_to_one_allowed_for_independent_add():
    action, _, _ = decision_to_action(
        AIDecision(
            decision="scale_out",
            node_type="ess-client",
            delta=1,
            target_flavor_id="client-large",
            reason="add client",
            cooldown_minutes=30,
        ),
        current_nodes=0,
        min_nodes=0,
        max_nodes=64,
        cooldown_until=None,
        topology={"node_types": {"ess-client": {"count": 0}}},
        node_limits={"ess-client": {"min": 0, "max": 64}},
    )
    assert action.action == "scale_out"
    assert action.node_type == "ess-client"
    assert action.delta == 1
    assert action.target_flavor_id == "client-large"


def test_flavor_change_requires_available_flavor():
    action, _, _ = decision_to_action(
        AIDecision(
            decision="change_flavor",
            node_type="ess",
            target_flavor_id="ess.large",
            reason="need more capacity",
            cooldown_minutes=30,
        ),
        current_nodes=2,
        min_nodes=1,
        max_nodes=32,
        cooldown_until=None,
        topology={"node_types": {"ess": {"count": 2, "spec_codes": ["ess.small"]}}},
        node_limits={"ess": {"min": 1, "max": 32}},
        available_flavors={"ess": [{"id": "ess.large", "name": "ess.large"}]},
    )
    assert action.action == "change_flavor"
    assert action.node_type == "ess"
    assert action.target_flavor_id == "ess.large"


def test_pending_operation_forces_hold():
    action, _, status = decision_to_action(
        AIDecision(decision="scale_out", node_type="ess-client", delta=1, reason="pressure", cooldown_minutes=30),
        current_nodes=0,
        min_nodes=0,
        max_nodes=64,
        cooldown_until=None,
        topology={"node_types": {"ess-client": {"count": 0}}},
        node_limits={"ess-client": {"min": 0, "max": 64}},
        pending_operation=True,
    )
    assert status == "pending"
    assert action.action == "hold"
