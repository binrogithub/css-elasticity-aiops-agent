"""execute_action node."""

from datetime import datetime, timezone

from app.models.actions import ActionResult
from app.runtime import Runtime
from app.services.policy_engine import apply_execution_policy
from app.services.validation import decision_to_action
from app.state import AgentState


def execute_action_node(runtime: Runtime):
    def node(state: AgentState) -> AgentState:
        request, cooldown_until, _ = decision_to_action(
            decision=state.ai_decision,
            current_nodes=state.current_nodes,
            min_nodes=state.min_nodes,
            max_nodes=state.max_nodes,
            cooldown_until=state.cooldown_until,
            topology=state.topology,
            node_limits=state.node_limits,
            available_flavors=state.available_flavors,
            settings=runtime.settings,
            pending_operation=state.pending_operation,
        )
        policy = apply_execution_policy(
            request,
            runtime.settings,
            approval_payload=runtime.state_repo.get("approved_action"),
            capacity_analysis=state.capacity_analysis,
            recent_action_count=runtime.actions_repo.successful_scaling_count_last_24h(),
            last_action_time=state.last_action_time,
            low_load_minutes=int(state.metadata.get("estimated_low_load_minutes", 0)),
        )
        if policy.status not in {"approved", "validated"}:
            now = datetime.now(timezone.utc)
            result = ActionResult(
                action_id=policy.request.action_id,
                requested_action=policy.request.action,
                executed_action="hold",
                node_type=policy.request.node_type,
                requested_delta=policy.request.delta,
                applied_delta=0,
                previous_node_count=state.current_nodes,
                new_node_count=state.current_nodes,
                status="skipped",
                phase="blocked",
                message=policy.message,
                expected_duration_minutes=policy.request.expected_duration_minutes,
                validation_status=policy.status,
                policy_version=runtime.settings.policy_version,
                risk_level=policy.request.change_plan.risk_level,
                change_plan=policy.request.change_plan,
                started_at=now,
                finished_at=now,
            )
            return state.patch(
                action_result=result,
                cooldown_until=state.cooldown_until,
                last_action=state.last_action,
                last_action_time=state.last_action_time,
                metadata={**state.metadata, "policy_status": policy.status},
            )

        result = runtime.executor.execute(policy.request)
        result = result.model_copy(
            update={
                "policy_version": runtime.settings.policy_version,
                "risk_level": policy.request.change_plan.risk_level,
                "change_plan": policy.request.change_plan,
                "validation_status": policy.status,
            }
        )
        return state.patch(
            action_result=result,
            current_nodes=result.new_node_count,
            cooldown_until=cooldown_until
            if result.status == "success" and result.executed_action != "hold"
            else state.cooldown_until,
            last_action=result.executed_action
            if result.status == "success" and result.executed_action != "hold"
            else state.last_action,
            last_action_time=result.finished_at
            if result.status == "success" and result.executed_action != "hold"
            else state.last_action_time,
            metadata={**state.metadata, "policy_status": policy.status},
        )

    return node
