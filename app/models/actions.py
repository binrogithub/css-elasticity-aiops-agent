"""Action execution models."""

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


ActionName = Literal["scale_out", "scale_in", "hold"]
ExecutableActionName = Literal["scale_out", "scale_in", "change_flavor", "hold"]
ActionStatus = Literal["success", "skipped", "failed"]
ActionPhase = Literal[
    "proposed",
    "validated",
    "blocked",
    "submitted",
    "polling",
    "verified_success",
    "verified_failed",
    "timeout",
    "rollback_required",
]
NodeType = Literal["ess", "ess-client", "ess-master"]
RiskLevel = Literal["low", "medium", "high", "blocked"]


class ChangePlan(BaseModel):
    risk_level: RiskLevel = "low"
    risk_reasons: list[str] = Field(default_factory=list)
    maintenance_window_required: bool = False
    approval_required: bool = False
    estimated_duration_minutes: int = 30
    pre_checks: list[str] = Field(default_factory=list)
    post_checks: list[str] = Field(default_factory=list)
    rollback_hint: str = ""


class ActionRequest(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid4()))
    action: ExecutableActionName
    node_type: Optional[NodeType] = None
    delta: int
    target_flavor_id: Optional[str] = None
    reason: str
    expected_duration_minutes: int = 30
    validation_status: str = "proposed"
    requires_approval: bool = False
    approved: bool = False
    policy_version: str = "commercial-safety-v1"
    change_plan: ChangePlan = Field(default_factory=ChangePlan)


class ActionResult(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid4()))
    requested_action: ExecutableActionName
    executed_action: ExecutableActionName = "hold"
    node_type: Optional[NodeType] = None
    requested_delta: int = 0
    applied_delta: int = 0
    previous_node_count: int = 0
    new_node_count: int = 0
    previous_flavor_id: Optional[str] = None
    new_flavor_id: Optional[str] = None
    status: ActionStatus = "skipped"
    phase: ActionPhase = "validated"
    message: str = ""
    expected_duration_minutes: int = 30
    validation_status: str = "validated"
    policy_version: str = "commercial-safety-v1"
    risk_level: RiskLevel = "low"
    change_plan: ChangePlan = Field(default_factory=ChangePlan)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VerificationResult(BaseModel):
    success: bool = True
    status: Literal["success", "pending", "failed"] = "success"
    message: str = "verified"
    observed_node_count: int = 0
    expected_node_count: int = 0
    cluster_status: str = ""
    node_type: str = ""
    observed_instances: list[dict[str, Any]] = Field(default_factory=list)
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
