"""Application-side action validation."""

import json
from datetime import datetime, timezone, timedelta
from typing import Any

from app.config import Settings
from app.models.actions import ActionRequest
from app.models.decisions import AIDecision


DEFAULT_NODE_TYPES = ("ess", "ess-client", "ess-master")


def build_node_limits(settings: Settings) -> dict[str, dict[str, Any]]:
    limits: dict[str, dict[str, Any]] = {
        "ess": {"min": settings.css_default_data_min, "max": settings.css_default_data_max},
        "ess-client": {"min": settings.css_default_client_min, "max": settings.css_default_client_max},
        "ess-master": {
            "allowed_counts": [
                int(item.strip())
                for item in settings.css_default_master_allowed_counts.split(",")
                if item.strip()
            ]
        },
    }
    if settings.css_node_limits_json:
        overrides = json.loads(settings.css_node_limits_json)
        for node_type, values in overrides.items():
            if node_type in limits and isinstance(values, dict):
                limits[node_type].update(values)
    return limits


def current_count(topology: dict[str, Any], node_type: str) -> int:
    return int(topology.get("node_types", {}).get(node_type, {}).get("count", 0))


def current_flavor(topology: dict[str, Any], node_type: str) -> str | None:
    specs = topology.get("node_types", {}).get(node_type, {}).get("spec_codes", [])
    return specs[0] if specs else None


def allowed_scale_out_delta(node_type: str, current: int, requested: int, limits: dict[str, Any]) -> int:
    requested = max(0, requested)
    if node_type == "ess-master":
        allowed_counts = sorted(set(int(item) for item in limits.get("allowed_counts", [0, 3, 5, 7, 9])))
        targets = [count for count in allowed_counts if count > current]
        if not targets:
            return 0
        return max(0, min(requested, targets[0] - current))
    return min(requested, max(0, int(limits.get("max", current)) - current))


def allowed_scale_in_delta(node_type: str, current: int, requested: int, limits: dict[str, Any]) -> int:
    requested = max(0, requested)
    if node_type == "ess-master":
        allowed_counts = sorted(set(int(item) for item in limits.get("allowed_counts", [0, 3, 5, 7, 9])))
        targets = [count for count in allowed_counts if count < current]
        if not targets:
            return 0
        return max(0, min(requested, current - targets[-1]))
    allowed = max(0, current - int(limits.get("min", 0)))
    if node_type == "ess":
        allowed = min(allowed, max(0, (current - 1) // 2))
    return min(requested, allowed)


def apply_delta_cap(action: str, node_type: str, requested: int, settings: Settings | None) -> int:
    if not settings or requested <= 0:
        return requested
    max_deltas = {
        ("scale_out", "ess-client"): settings.css_client_scale_out_max_delta,
        ("scale_in", "ess-client"): settings.css_client_scale_in_max_delta,
        ("scale_out", "ess"): settings.css_data_scale_out_max_delta,
        ("scale_in", "ess"): settings.css_data_scale_in_max_delta,
    }
    max_delta = int(max_deltas.get((action, node_type), 0))
    if max_delta <= 0:
        return requested
    return min(requested, max_delta)


def cooldown_minutes_for_action(decision: AIDecision, settings: Settings | None) -> int:
    if not settings or decision.decision not in {"scale_out", "scale_in"}:
        return decision.cooldown_minutes
    overrides = {
        ("scale_out", "ess-client"): settings.css_client_scale_out_cooldown_minutes,
        ("scale_in", "ess-client"): settings.css_client_scale_in_cooldown_minutes,
        ("scale_out", "ess"): settings.css_data_scale_out_cooldown_minutes,
        ("scale_in", "ess"): settings.css_data_scale_in_cooldown_minutes,
    }
    return max(0, int(overrides.get((decision.decision, decision.node_type), decision.cooldown_minutes)))


def client_scale_in_safe(settings: Settings | None) -> bool:
    return bool(
        settings
        and settings.css_client_scale_in_allowed
        and settings.css_traffic_entry_mode == "load_balancer"
    )


def flavor_available(available_flavors: dict[str, Any], node_type: str, flavor_id: str | None) -> bool:
    if not flavor_id:
        return False
    for item in available_flavors.get(node_type, []):
        if flavor_id in {item.get("id"), item.get("name"), item.get("str_id"), item.get("flavor_id")}:
            return True
    return False


def decision_to_action(
    decision: AIDecision | None,
    current_nodes: int,
    min_nodes: int,
    max_nodes: int,
    cooldown_until: datetime | None,
    *,
    topology: dict[str, Any] | None = None,
    node_limits: dict[str, Any] | None = None,
    available_flavors: dict[str, Any] | None = None,
    settings: Settings | None = None,
    pending_operation: bool = False,
) -> tuple[ActionRequest, datetime | None, str]:
    if decision is None:
        return ActionRequest(action="hold", delta=0, reason="No AI decision"), cooldown_until, "hold"

    if pending_operation:
        return ActionRequest(action="hold", delta=0, reason="Pending CSS operation active"), cooldown_until, "pending"

    if cooldown_until and datetime.now(timezone.utc) < cooldown_until:
        return (
            ActionRequest(action="hold", delta=0, reason="Cooldown active"),
            cooldown_until,
            "cooldown",
        )

    topology = topology or {}
    node_limits = node_limits or {}
    available_flavors = available_flavors or {}

    if decision.decision == "hold":
        return ActionRequest(action="hold", delta=0, reason=decision.reason), cooldown_until, "validated"

    node_type = decision.node_type
    if node_type not in DEFAULT_NODE_TYPES:
        return ActionRequest(action="hold", delta=0, reason="Invalid or missing node_type"), cooldown_until, "invalid"

    current = current_count(topology, node_type) if topology else current_nodes
    limits = node_limits.get(node_type, {"min": min_nodes, "max": max_nodes})

    if decision.decision == "scale_out":
        requested_delta = apply_delta_cap(decision.decision, node_type, decision.delta, settings)
        delta = allowed_scale_out_delta(node_type, current, requested_delta, limits)
    elif decision.decision == "scale_in":
        if node_type == "ess-client" and not client_scale_in_safe(settings):
            return (
                ActionRequest(
                    action="hold",
                    delta=0,
                    reason=(
                        "Client node scale-in requires CSS_TRAFFIC_ENTRY_MODE=load_balancer "
                        "and CSS_CLIENT_SCALE_IN_ALLOWED=true"
                    ),
                ),
                cooldown_until,
                "blocked",
            )
        if node_type == "ess" and settings and not settings.css_data_scale_in_allowed:
            return (
                ActionRequest(
                    action="hold",
                    delta=0,
                    reason="Data node scale-in requires CSS_DATA_SCALE_IN_ALLOWED=true because shard relocation can affect workload latency.",
                ),
                cooldown_until,
                "blocked",
            )
        requested_delta = apply_delta_cap(decision.decision, node_type, decision.delta, settings)
        delta = allowed_scale_in_delta(node_type, current, requested_delta, limits)
    elif decision.decision == "change_flavor":
        if settings and not settings.css_allow_flavor_change:
            return ActionRequest(action="hold", delta=0, reason="Flavor change disabled"), cooldown_until, "disabled"
        if not flavor_available(available_flavors, node_type, decision.target_flavor_id):
            return ActionRequest(action="hold", delta=0, reason="Target flavor is not available"), cooldown_until, "invalid"
        if decision.target_flavor_id == current_flavor(topology, node_type):
            return ActionRequest(action="hold", delta=0, reason="Target flavor already active"), cooldown_until, "validated"
        delta = 0
    else:
        delta = 0

    action = decision.decision if decision.decision == "change_flavor" or delta > 0 else "hold"
    request = ActionRequest(
        action=action,
        node_type=node_type if action != "hold" else None,
        delta=delta,
        target_flavor_id=decision.target_flavor_id if action in {"change_flavor", "scale_out"} else None,
        reason=decision.reason,
        expected_duration_minutes=decision.expected_duration_minutes,
        validation_status="validated",
    )
    cooldown_minutes = cooldown_minutes_for_action(decision, settings)
    next_cooldown = (
        datetime.now(timezone.utc) + timedelta(minutes=cooldown_minutes)
        if action != "hold"
        else cooldown_until
    )
    return request, next_cooldown, "validated"
