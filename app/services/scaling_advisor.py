"""Heuristic scaling advice for AI prompt context."""

from __future__ import annotations

import math
from typing import Any

from app.config import Settings
from app.models.actions import ActionResult
from app.services.strategy_profile import (
    effective_data_burst_cpu_min,
    effective_data_burst_node_fraction,
    effective_data_burst_qps_multiplier,
    effective_scale_in_low_load_minutes,
)


def data_node_count(topology: dict[str, Any], fallback: int = 0) -> int:
    return int(topology.get("node_types", {}).get("ess", {}).get("count", fallback))


def data_node_limits(node_limits: dict[str, Any], settings: Settings) -> dict[str, int]:
    limits = node_limits.get("ess", {})
    return {
        "min": int(limits.get("min", settings.css_default_data_min)),
        "max": int(limits.get("max", settings.css_default_data_max)),
    }


def recommend_data_scale_out_delta(
    snapshots: list[dict],
    *,
    current_data_nodes: int,
    node_limits: dict[str, int],
    settings: Settings,
    sample_interval_seconds: int,
) -> dict[str, Any]:
    """Estimate a Data node scale-out delta from CPU and QPS growth rates.

    This is deliberately advisory. The AI still decides, and validation still
    clamps by configured delta and node-count limits.
    """
    min_delta = max(1, int(settings.css_data_scale_out_min_delta))
    max_delta = max(min_delta, int(settings.css_data_scale_out_max_delta))
    target_cpu = max(1.0, float(settings.css_data_scale_out_target_cpu))
    configured_projection_minutes = max(
        1,
        int(settings.css_data_scale_out_projection_minutes or settings.css_count_scale_timeout_minutes),
        int(settings.css_count_scale_timeout_minutes),
    )

    if len(snapshots) < 2 or current_data_nodes <= 0:
        return {
            "recommended_delta": 0,
            "min_delta": min_delta,
            "max_delta": max_delta,
            "target_cpu": target_cpu,
            "projection_minutes": configured_projection_minutes,
            "effective_projection_minutes": configured_projection_minutes,
            "reason": "Insufficient history or missing Data node count; AI should hold or use conservative evidence.",
        }

    ordered = list(reversed(snapshots))
    first = ordered[0]
    last = ordered[-1]
    elapsed_minutes = max(1.0, (len(ordered) - 1) * sample_interval_seconds / 60)
    first_qps = max(0.0, float(first.get("qps_avg", 0)))
    last_qps = max(0.0, float(last.get("qps_avg", 0)))
    first_cpu = max(0.0, float(first.get("cpu_avg", 0)))
    last_cpu = max(0.0, float(last.get("cpu_avg", 0)))
    effective_projection_minutes = min(configured_projection_minutes, max(1.0, elapsed_minutes * 2.0))

    qps_growth_per_min = (last_qps - first_qps) / elapsed_minutes
    cpu_growth_per_min = (last_cpu - first_cpu) / elapsed_minutes
    qps_multiplier = (last_qps / first_qps) if first_qps > 0 else (float("inf") if last_qps > 0 else 1.0)
    projected_qps = max(0.0, last_qps + max(0.0, qps_growth_per_min) * effective_projection_minutes)
    projected_cpu = max(0.0, last_cpu + max(0.0, cpu_growth_per_min) * effective_projection_minutes)

    needed_by_cpu = 0
    if projected_cpu > target_cpu:
        needed_by_cpu = math.ceil(current_data_nodes * (projected_cpu / target_cpu - 1.0))

    needed_by_qps = 0
    if last_qps > 0 and last_cpu > 0 and projected_qps > last_qps:
        per_node_qps_at_target_cpu = (last_qps / current_data_nodes) * (target_cpu / last_cpu)
        if per_node_qps_at_target_cpu > 0:
            required_nodes = math.ceil(projected_qps / per_node_qps_at_target_cpu)
            needed_by_qps = max(0, required_nodes - current_data_nodes)

    burst_floor_delta = 0
    if (
        qps_multiplier >= effective_data_burst_qps_multiplier(settings)
        and last_cpu >= effective_data_burst_cpu_min(settings)
        and qps_growth_per_min > 0
    ):
        fraction = max(0.0, effective_data_burst_node_fraction(settings))
        burst_floor_delta = math.ceil(current_data_nodes * fraction)

    raw_delta = max(needed_by_cpu, needed_by_qps, burst_floor_delta)
    available_headroom = max(0, int(node_limits.get("max", current_data_nodes)) - current_data_nodes)
    if raw_delta > 0 and available_headroom > 0:
        recommended_delta = min(max(raw_delta, min_delta), max_delta, available_headroom)
    else:
        recommended_delta = 0

    return {
        "recommended_delta": recommended_delta,
        "raw_delta": raw_delta,
        "min_delta": min_delta,
        "max_delta": max_delta,
        "target_cpu": target_cpu,
        "projection_minutes": configured_projection_minutes,
        "effective_projection_minutes": round(effective_projection_minutes, 2),
        "current_data_nodes": current_data_nodes,
        "data_node_max": int(node_limits.get("max", current_data_nodes)),
        "available_headroom": available_headroom,
        "qps_growth_per_minute": round(qps_growth_per_min, 2),
        "cpu_growth_per_minute": round(cpu_growth_per_min, 2),
        "projected_qps": round(projected_qps, 2),
        "projected_cpu": round(projected_cpu, 2),
        "qps_multiplier": round(qps_multiplier, 2) if math.isfinite(qps_multiplier) else "inf",
        "burst_qps_multiplier_threshold": effective_data_burst_qps_multiplier(settings),
        "burst_cpu_min_threshold": effective_data_burst_cpu_min(settings),
        "burst_node_fraction": effective_data_burst_node_fraction(settings),
        "needed_by_cpu": needed_by_cpu,
        "needed_by_qps": needed_by_qps,
        "burst_floor_delta": burst_floor_delta,
        "reason": (
            "Estimate Data node scale-out from projected CPU and QPS growth during CSS provisioning. "
            "Use this as AI guidance, not a hard decision."
        ),
    }


def recommend_data_scale_in_delta(
    *,
    recent_actions: list[ActionResult],
    current_data_nodes: int,
    node_limits: dict[str, int],
    low_load_minutes: int,
    settings: Settings,
) -> dict[str, Any]:
    """Advise Data scale-in after a recent temporary scale-out has cooled down."""
    min_nodes = int(node_limits.get("min", settings.css_default_data_min))
    max_delta = int(settings.css_data_scale_in_max_delta)
    required_low_load_minutes = effective_scale_in_low_load_minutes(settings)
    removable = max(0, current_data_nodes - min_nodes)
    provider_safe_delta = max(0, (current_data_nodes - 1) // 2)
    if removable <= 0:
        target_delta = 0
        recommended_delta = 0
    else:
        net_recent_data_scale_out = 0
        for action in reversed(recent_actions):
            if action.status != "success" or action.node_type != "ess":
                continue
            if action.executed_action == "scale_out":
                net_recent_data_scale_out += action.applied_delta
            elif action.executed_action == "scale_in":
                net_recent_data_scale_out -= action.applied_delta
        target_delta = min(max(0, net_recent_data_scale_out), removable)
        candidate = target_delta
        if max_delta > 0:
            candidate = min(candidate, max_delta)
        if provider_safe_delta > 0:
            candidate = min(candidate, provider_safe_delta)
        recommended_delta = candidate
        if low_load_minutes < required_low_load_minutes:
            recommended_delta = 0

    return {
        "recommended_delta": recommended_delta,
        "target_delta": target_delta,
        "provider_safe_delta": provider_safe_delta,
        "current_data_nodes": current_data_nodes,
        "data_node_min": min_nodes,
        "removable_nodes": removable,
        "low_load_minutes": low_load_minutes,
        "required_low_load_minutes": required_low_load_minutes,
        "max_delta": max_delta,
        "reason": (
            "Estimate Data node scale-in from sustained low load and recent net Data scale-out. "
            "recommended_delta is the provider-safe batch for the next action; target_delta is the remaining "
            "surge capacity to reclaim across one or more workflow cycles."
        ),
    }
