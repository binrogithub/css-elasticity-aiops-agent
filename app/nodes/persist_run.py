"""persist_run node."""

from app.runtime import Runtime
from app.state import AgentState
from app.nodes.check_pending_operation import PENDING_ACTION_KEY


def persist_run_node(runtime: Runtime):
    def node(state: AgentState) -> AgentState:
        try:
            if state.last_metrics:
                runtime.metrics_repo.save(state.run_id, state.last_metrics)
            if state.ai_decision:
                runtime.decisions_repo.save(state.run_id, state.ai_raw_response, state.ai_decision)
            if state.action_result and not state.metadata.get("pending_action_loaded"):
                runtime.actions_repo.save_action(state.run_id, state.action_result)
            elif state.action_result and state.metadata.get("pending_action_loaded"):
                runtime.actions_repo.save_action_event(state.run_id, state.action_result)
            if state.verification_result:
                runtime.actions_repo.save_verification(state.run_id, state.verification_result)
            if state.action_result and state.verification_result and state.verification_result.status == "pending":
                runtime.state_repo.set(PENDING_ACTION_KEY, state.action_result.model_dump(mode="json"))
            elif state.verification_result and state.verification_result.status in {"success", "failed"}:
                runtime.state_repo.delete(PENDING_ACTION_KEY)
            runtime.state_repo.set("agent_state", state.model_dump(mode="json"))
            return state.patch(persist_result="success")
        except Exception as exc:
            return state.patch(persist_result="failed", errors=[*state.errors, f"persist failed: {exc}"])

    return node
