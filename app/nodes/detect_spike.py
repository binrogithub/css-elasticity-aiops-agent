"""detect_spike node."""

from app.runtime import Runtime
from app.services.spike_detector import SpikeDetector
from app.state import AgentState


def detect_spike_node(runtime: Runtime):
    detector = SpikeDetector(runtime.settings)

    def node(state: AgentState) -> AgentState:
        if not state.last_metrics:
            return state.patch(spike_detected=False, spike_reason="No metrics")
        result = detector.detect(state.last_metrics, state.prev_metrics)
        return state.patch(spike_detected=result.spike_detected, spike_reason=result.spike_reason)

    return node
