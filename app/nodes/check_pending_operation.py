"""check_pending_operation node."""

from app.models.actions import ActionResult
from app.runtime import Runtime
from app.state import AgentState


PENDING_ACTION_KEY = "pending_action"


def check_pending_operation_node(runtime: Runtime):
    def node(state: AgentState) -> AgentState:
        payload = runtime.state_repo.get(PENDING_ACTION_KEY)
        if not payload:
            return state.patch(pending_operation=False, pending_operation_reason="")

        pending_action = ActionResult.model_validate(payload)
        verification = runtime.executor.verify(pending_action, wait=False)
        if verification.status == "pending":
            pending_action = pending_action.model_copy(update={"phase": "polling"})
            return state.patch(
                action_result=pending_action,
                verification_result=verification,
                current_nodes=verification.observed_node_count,
                pending_operation=True,
                pending_operation_reason=verification.message,
                metadata={**state.metadata, "pending_action_loaded": True},
            )

        runtime.state_repo.delete(PENDING_ACTION_KEY)
        pending_action = pending_action.model_copy(
            update={"phase": "verified_success" if verification.status == "success" else "verified_failed"}
        )
        return state.patch(
            action_result=pending_action,
            verification_result=verification,
            current_nodes=verification.observed_node_count,
            pending_operation=False,
            pending_operation_reason=verification.message,
            metadata={**state.metadata, "pending_action_loaded": True},
        )

    return node
