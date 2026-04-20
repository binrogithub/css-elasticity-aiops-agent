"""Lightweight in-process scheduler."""

import signal
import time
from datetime import datetime, timezone
from typing import Any

from app.graph import build_graph
from app.runtime import Runtime
from app.state import AgentState


class Scheduler:
    def __init__(self, runtime: Runtime):
        self.runtime = runtime
        self.graph = build_graph(runtime)
        self.running = True
        self.last_ai_check_time = self._restore_last_ai_check_time()
        signal.signal(signal.SIGINT, self._stop)
        signal.signal(signal.SIGTERM, self._stop)

    def _stop(self, signum, frame):
        self.running = False

    def initial_state(self, trigger_type: str = "manual") -> AgentState:
        topology = self.runtime.executor.current_topology()
        restored = self._restore_state_values()
        return AgentState(
            cluster_id=self.runtime.settings.cluster_id,
            cluster_name=self.runtime.settings.cluster_name,
            current_nodes=self.runtime.executor.current_nodes(),
            min_nodes=self.runtime.settings.min_nodes,
            max_nodes=self.runtime.settings.max_nodes,
            topology=topology,
            last_ai_check_time=self.last_ai_check_time,
            last_action=restored.get("last_action"),
            last_action_time=restored.get("last_action_time"),
            cooldown_until=restored.get("cooldown_until"),
            metadata={
                "trigger_type": trigger_type,
                "count_scale_timeout_minutes": self.runtime.settings.css_count_scale_timeout_minutes,
                "flavor_change_timeout_minutes": self.runtime.settings.css_flavor_change_timeout_minutes,
            },
        )

    def run_once(self, trigger_type: str = "manual") -> AgentState:
        result = self.graph.invoke(self.initial_state(trigger_type=trigger_type))
        state = AgentState.model_validate(result)
        self.last_ai_check_time = state.last_ai_check_time
        return state

    def run_loop(self) -> None:
        next_resource = 0.0
        while self.running:
            now = time.time()
            if now >= next_resource:
                state = self.run_once(trigger_type="resource_check")
                if state.spike_detected:
                    self.last_ai_check_time = datetime.now(timezone.utc)
                next_resource = now + self.runtime.settings.resource_check_interval_seconds
            time.sleep(1)

    def _restore_state_values(self) -> dict[str, Any]:
        payload = self.runtime.state_repo.get("agent_state") or {}
        return {
            "last_action": payload.get("last_action"),
            "last_action_time": payload.get("last_action_time"),
            "cooldown_until": payload.get("cooldown_until"),
        }

    def _restore_last_ai_check_time(self):
        payload = self.runtime.state_repo.get("agent_state") or {}
        value = payload.get("last_ai_check_time")
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
