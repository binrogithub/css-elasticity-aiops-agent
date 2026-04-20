"""verify_result node."""

from app.runtime import Runtime
from app.state import AgentState


def verify_result_node(runtime: Runtime):
    def node(state: AgentState) -> AgentState:
        if not state.action_result:
            return state
        result = runtime.executor.verify(state.action_result, wait=False)
        action_result = state.action_result.model_copy(
            update={
                "phase": "polling"
                if result.status == "pending"
                else ("verified_success" if result.status == "success" else "verified_failed")
            }
        )
        return state.patch(
            action_result=action_result,
            verification_result=result,
            current_nodes=result.observed_node_count,
            pending_operation=result.status == "pending",
            pending_operation_reason=result.message if result.status == "pending" else "",
        )

    return node
