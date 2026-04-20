from app.config import Settings
from app.models.actions import ActionRequest
from app.models.diagnostics import CapacityAnalysis
from app.services.policy_engine import apply_execution_policy


def test_recommend_only_records_without_mutation():
    request = ActionRequest(action="scale_out", node_type="ess-client", delta=1, reason="pressure")
    decision = apply_execution_policy(request, Settings(AGENT_RUN_MODE="recommend-only"))
    assert decision.status == "dry_run"
    assert not decision.request.approved


def test_auto_execute_requires_mutation_enabled():
    request = ActionRequest(action="scale_out", node_type="ess-client", delta=1, reason="pressure")
    decision = apply_execution_policy(
        request,
        Settings(AGENT_RUN_MODE="auto-execute", CSS_MUTATION_ENABLED=False),
    )
    assert decision.status == "mutation_disabled"


def test_approval_required_accepts_matching_payload():
    request = ActionRequest(action="scale_out", node_type="ess-client", delta=1, reason="pressure")
    decision = apply_execution_policy(
        request,
        Settings(AGENT_RUN_MODE="approval-required"),
        approval_payload={"action_id": request.action_id, "approved": True},
    )
    assert decision.status == "approved"
    assert decision.request.approved


def test_large_cluster_allows_client_scale_out_auto_execute():
    request = ActionRequest(action="scale_out", node_type="ess-client", delta=1, reason="qps surge")
    decision = apply_execution_policy(
        request,
        Settings(
            AGENT_RUN_MODE="auto-execute",
            CSS_MUTATION_ENABLED=True,
            ENTERPRISE_POLICY_PROFILE="large-cluster",
        ),
    )
    assert decision.status == "approved"
    assert decision.request.change_plan.risk_level == "low"


def test_large_cluster_data_scale_in_requires_approval():
    request = ActionRequest(action="scale_in", node_type="ess", delta=1, reason="low load")
    decision = apply_execution_policy(
        request,
        Settings(
            AGENT_RUN_MODE="auto-execute",
            CSS_MUTATION_ENABLED=True,
            ENTERPRISE_POLICY_PROFILE="large-cluster",
            CSS_DATA_SCALE_IN_ALLOWED=True,
        ),
        low_load_minutes=180,
    )
    assert decision.status == "approval_required"
    assert decision.request.change_plan.risk_level == "high"
    assert decision.request.change_plan.maintenance_window_required


def test_scale_in_requires_low_load_window():
    request = ActionRequest(action="scale_in", node_type="ess-client", delta=1, reason="low load")
    decision = apply_execution_policy(
        request,
        Settings(
            AGENT_RUN_MODE="auto-execute",
            CSS_MUTATION_ENABLED=True,
            CSS_TRAFFIC_ENTRY_MODE="load_balancer",
            CSS_CLIENT_SCALE_IN_ALLOWED=True,
        ),
        low_load_minutes=30,
    )
    assert decision.status == "approval_required"


def test_daily_action_limit_blocks_execution():
    request = ActionRequest(action="scale_out", node_type="ess-client", delta=1, reason="qps surge")
    decision = apply_execution_policy(
        request,
        Settings(AGENT_RUN_MODE="auto-execute", CSS_MUTATION_ENABLED=True, MAX_SCALING_ACTIONS_PER_DAY=1),
        recent_action_count=1,
    )
    assert decision.status == "blocked"


def test_capacity_analysis_blocks_data_scale_in():
    request = ActionRequest(action="scale_in", node_type="ess", delta=1, reason="low load")
    decision = apply_execution_policy(
        request,
        Settings(
            AGENT_RUN_MODE="auto-execute",
            CSS_MUTATION_ENABLED=True,
            CSS_DATA_SCALE_IN_ALLOWED=True,
            APPROVAL_REQUIRED_ACTIONS="",
            AUTO_EXECUTE_NODE_TYPES="ess",
        ),
        capacity_analysis=CapacityAnalysis(available=True, data_scale_in_blocked=True),
        low_load_minutes=180,
    )
    assert decision.status == "blocked"
    assert "capacity analysis" in decision.message
