"""ai_decide node."""

from datetime import datetime, timezone

from app.runtime import Runtime
from app.state import AgentState


def ai_decide_node(runtime: Runtime):
    def node(state: AgentState) -> AgentState:
        raw, decision = runtime.ai_client.decide(state)
        return state.patch(
            ai_raw_response=raw,
            ai_decision=decision,
            last_ai_check_time=datetime.now(timezone.utc),
        )

    return node
