"""Typed shared LangGraph state."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from app.models.actions import ActionResult, VerificationResult
from app.models.decisions import AIDecision
from app.models.diagnostics import CapacityAnalysis, OpenSearchDiagnostics
from app.models.metrics import MetricsSnapshot


class AgentState(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    now_ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    cluster_id: str = ""
    cluster_name: str = ""
    current_nodes: int = 0
    min_nodes: int = 1
    max_nodes: int = 5
    topology: Dict[str, Any] = Field(default_factory=dict)
    available_flavors: Dict[str, Any] = Field(default_factory=dict)
    node_limits: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Optional[OpenSearchDiagnostics] = None
    capacity_analysis: Optional[CapacityAnalysis] = None

    last_metrics: Optional[MetricsSnapshot] = None
    prev_metrics: Optional[MetricsSnapshot] = None

    spike_detected: bool = False
    spike_reason: str = ""
    should_run_ai: bool = False

    last_resource_check_time: Optional[datetime] = None
    last_ai_check_time: Optional[datetime] = None

    last_action: Optional[str] = None
    last_action_time: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None

    ai_raw_response: Optional[str] = None
    ai_decision: Optional[AIDecision] = None

    action_result: Optional[ActionResult] = None
    verification_result: Optional[VerificationResult] = None
    pending_operation: bool = False
    pending_operation_reason: str = ""
    recent_history_summary: str = ""
    persist_result: str = ""
    errors: List[str] = Field(default_factory=list)

    metadata: Dict[str, Any] = Field(default_factory=dict)

    def patch(self, **kwargs: Any) -> "AgentState":
        data = self.model_dump()
        data.update(kwargs)
        return AgentState.model_validate(data)
