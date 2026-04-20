"""Deterministic policy layer between AI recommendations and CSS execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone

from app.config import Settings
from app.models.actions import ActionRequest, ChangePlan


@dataclass(frozen=True)
class PolicyDecision:
    request: ActionRequest
    status: str
    message: str


def apply_execution_policy(
    request: ActionRequest,
    settings: Settings,
    *,
    approval_payload: dict | None = None,
    capacity_analysis: object | None = None,
    recent_action_count: int = 0,
    last_action_time: datetime | None = None,
    low_load_minutes: int = 0,
    now: datetime | None = None,
) -> PolicyDecision:
    """Apply product safety gates after AI/rule validation.

    AI and validation may decide that an action is technically valid. This layer
    decides whether the product mode allows it to be submitted to CSS.
    """
    now = now or datetime.now(timezone.utc)
    request = request.model_copy(
        update={
            "policy_version": settings.policy_version,
            "change_plan": build_change_plan(
                request,
                settings,
                low_load_minutes=low_load_minutes,
                capacity_analysis=capacity_analysis,
            ),
        }
    )
    if request.action == "hold":
        return PolicyDecision(request=request, status="validated", message="No scaling action requested.")

    preflight_status, preflight_message = evaluate_enterprise_guards(
        request,
        settings,
        recent_action_count=recent_action_count,
        last_action_time=last_action_time,
        low_load_minutes=low_load_minutes,
        capacity_analysis=capacity_analysis,
        now=now,
    )
    if preflight_status != "approved":
        return PolicyDecision(
            request=request.model_copy(
                update={
                    "requires_approval": preflight_status == "approval_required",
                    "approved": False,
                }
            ),
            status=preflight_status,
            message=preflight_message,
        )

    if settings.agent_run_mode in {"observe-only", "recommend-only"}:
        return PolicyDecision(
            request=request.model_copy(update={"requires_approval": False, "approved": False}),
            status="dry_run",
            message=f"Agent run mode {settings.agent_run_mode} records recommendation without CSS mutation.",
        )

    if settings.agent_run_mode == "approval-required":
        approved = bool(
            approval_payload
            and approval_payload.get("action_id") == request.action_id
            and approval_payload.get("approved") is True
        )
        if not approved:
            return PolicyDecision(
                request=request.model_copy(update={"requires_approval": True, "approved": False}),
                status="approval_required",
                message="Action requires explicit approval before CSS mutation.",
            )
        return PolicyDecision(
            request=request.model_copy(update={"requires_approval": True, "approved": True}),
            status="approved",
            message="Action approved for CSS mutation.",
        )

    if not settings.css_mutation_enabled:
        return PolicyDecision(
            request=request,
            status="mutation_disabled",
            message="CSS mutation is disabled by CSS_MUTATION_ENABLED=false.",
        )

    return PolicyDecision(request=request, status="approved", message="Action approved by policy.")


def build_change_plan(
    request: ActionRequest,
    settings: Settings,
    *,
    low_load_minutes: int = 0,
    capacity_analysis: object | None = None,
) -> ChangePlan:
    risk_reasons: list[str] = []
    pre_checks = ["cluster health is green", "no pending CSS operation", "node limits are respected"]
    post_checks = ["target node count reached", "target nodes are stable", "search queue and rejected count remain healthy"]
    maintenance_required = False
    approval_required = False
    risk_level = "low"
    rollback_hint = "Return to previous node count if verification or workload health fails."

    if request.action == "scale_in":
        risk_level = "medium"
        risk_reasons.append("scale-in removes capacity and can affect active traffic")
        pre_checks.append(f"low load sustained for at least {settings.scale_in_low_load_minutes} minutes")
        if low_load_minutes and low_load_minutes < settings.scale_in_low_load_minutes:
            risk_level = "high"
            risk_reasons.append("low-load observation window is not long enough")

    if request.node_type == "ess":
        if request.action == "scale_in":
            risk_level = "high"
            maintenance_required = True
            approval_required = True
            risk_reasons.append("data-node scale-in may trigger shard relocation")
            pre_checks.extend(["disk watermarks are safe", "relocating shards are zero", "pending tasks are zero"])
            post_checks.extend(["shard relocation is complete", "disk and JVM pressure remain healthy"])
            if capacity_blocks_data_scale_in(capacity_analysis):
                risk_reasons.append("capacity analysis blocks data-node scale-in")
        elif request.action == "scale_out":
            risk_level = "medium"
            risk_reasons.append("data-node scale-out can trigger shard rebalance")

    if request.node_type == "ess-master":
        risk_level = "high"
        maintenance_required = True
        approval_required = True
        risk_reasons.append("master node changes affect cluster coordination")
        pre_checks.extend(["cluster state updates are healthy", "master count remains a valid odd count"])

    if request.action == "change_flavor":
        risk_level = "high"
        maintenance_required = True
        approval_required = True
        risk_reasons.append("flavor changes are long-running capacity mutations")

    if request.node_type == "ess-client" and request.action == "scale_in":
        pre_checks.extend(["traffic entry mode is load_balancer", "client drain or health-check removal is available"])
        post_checks.append("application traffic no longer targets removed Client node")

    return ChangePlan(
        risk_level=risk_level,  # type: ignore[arg-type]
        risk_reasons=risk_reasons,
        maintenance_window_required=maintenance_required,
        approval_required=approval_required,
        estimated_duration_minutes=request.expected_duration_minutes,
        pre_checks=pre_checks,
        post_checks=post_checks,
        rollback_hint=rollback_hint,
    )


def evaluate_enterprise_guards(
    request: ActionRequest,
    settings: Settings,
    *,
    recent_action_count: int,
    last_action_time: datetime | None,
    low_load_minutes: int,
    capacity_analysis: object | None,
    now: datetime,
) -> tuple[str, str]:
    if recent_action_count >= settings.max_scaling_actions_per_day:
        return "blocked", "Daily scaling action limit reached."

    if request.action == "scale_in" and low_load_minutes < settings.scale_in_low_load_minutes:
        return (
            "approval_required",
            f"Scale-in requires {settings.scale_in_low_load_minutes} minutes of low-load evidence.",
        )

    if request.node_type == "ess" and request.action == "scale_in" and capacity_blocks_data_scale_in(capacity_analysis):
        return "blocked", "OpenSearch capacity analysis blocks data-node scale-in due to shard or skew risk."

    if request.action == "scale_out" and last_action_time:
        elapsed = (now - last_action_time).total_seconds() / 60
        if elapsed < settings.scale_out_observation_minutes:
            return (
                "blocked",
                f"Scale-out observation window active for {settings.scale_out_observation_minutes} minutes.",
            )

    if request.change_plan.maintenance_window_required and not is_in_maintenance_window(
        settings.maintenance_window_utc, now
    ):
        return "approval_required", "Action requires a maintenance window or explicit approval."

    if action_requires_approval(request, settings):
        return "approval_required", "Action is configured as approval-required."

    if request.node_type not in parse_csv(settings.auto_execute_node_types):
        return "approval_required", "Node type is not enabled for auto execution."

    return "approved", "Enterprise guards passed."


def action_requires_approval(request: ActionRequest, settings: Settings) -> bool:
    entries = parse_csv(settings.approval_required_actions)
    if request.action == "change_flavor" and "change_flavor" in entries:
        return True
    return f"{request.node_type}:{request.action}" in entries


def parse_csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def is_in_maintenance_window(window: str, now: datetime) -> bool:
    if not window:
        return False
    try:
        start_raw, end_raw = window.split("-", 1)
        start = time.fromisoformat(start_raw)
        end = time.fromisoformat(end_raw)
    except ValueError:
        return False
    current = now.astimezone(timezone.utc).time()
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def capacity_blocks_data_scale_in(capacity_analysis: object | None) -> bool:
    if not capacity_analysis:
        return False
    return bool(getattr(capacity_analysis, "data_scale_in_blocked", False))
