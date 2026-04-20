"""Capacity analysis based on OpenSearch shard and node diagnostics."""

from __future__ import annotations

import re
from statistics import mean

from app.config import Settings
from app.models.diagnostics import CapacityAnalysis, OpenSearchDiagnostics


def analyze_capacity(diagnostics: OpenSearchDiagnostics, settings: Settings) -> CapacityAnalysis:
    if diagnostics.errors and not any([diagnostics.nodes, diagnostics.allocation, diagnostics.indices, diagnostics.shards]):
        return CapacityAnalysis(source_errors=diagnostics.errors)

    primary_sizes = [
        parse_size_gb(item.get("store", "0"))
        for item in diagnostics.shards
        if item.get("prirep") == "p" and item.get("state") == "STARTED"
    ]
    shard_counts = [parse_int(item.get("shards")) for item in diagnostics.allocation if parse_int(item.get("shards")) > 0]
    storage_values = [parse_percent_or_number(item.get("disk.percent")) for item in diagnostics.allocation]
    heap_by_node = {item.get("name") or item.get("ip"): parse_size_gb(item.get("heap.max", "0")) for item in diagnostics.nodes}

    total_shards = len(diagnostics.shards)
    total_primary = len(primary_sizes)
    avg_primary_size = mean(primary_sizes) if primary_sizes else 0.0
    max_primary_size = max(primary_sizes) if primary_sizes else 0.0
    max_shards = max(shard_counts) if shard_counts else 0
    avg_shards = mean(shard_counts) if shard_counts else 0.0
    shard_skew = max_shards / avg_shards if avg_shards else 0.0
    storage_skew = max(storage_values) / mean(storage_values) if storage_values and mean(storage_values) else 0.0
    shards_per_heap = estimate_max_shards_per_gb_heap(diagnostics, heap_by_node)

    large_shard = max_primary_size > settings.shard_general_max_gb
    small_shard = bool(primary_sizes) and avg_primary_size < settings.shard_search_min_gb and total_primary > len(diagnostics.nodes)
    oversharding = shards_per_heap > settings.max_shards_per_gb_heap
    storage_skew_risk = storage_skew > settings.max_storage_skew_ratio
    shard_skew_risk = shard_skew > settings.max_shard_skew_ratio
    blocked = large_shard or oversharding or storage_skew_risk or shard_skew_risk

    recommendations: list[str] = []
    if large_shard:
        recommendations.append("Use rollover, split, or reindex before data-node scale-in; at least one primary shard exceeds the 50GB guidance.")
    if small_shard:
        recommendations.append("Review oversharding; average primary shard size is below the 10GB search-workload guidance.")
    if oversharding:
        recommendations.append("Reduce shard count or increase heap capacity; shards per GiB heap exceeds the configured threshold.")
    if storage_skew_risk:
        recommendations.append("Investigate allocation balance; storage skew is high across data nodes.")
    if shard_skew_risk:
        recommendations.append("Investigate shard allocation; shard-count skew is high across data nodes.")
    if not recommendations:
        recommendations.append("Shard size, shard count, and storage distribution are within configured guidance.")

    risk_level = "high" if blocked else ("medium" if small_shard else "low")
    return CapacityAnalysis(
        available=True,
        risk_level=risk_level,
        avg_primary_shard_size_gb=round(avg_primary_size, 2),
        max_primary_shard_size_gb=round(max_primary_size, 2),
        total_shards=total_shards,
        total_primary_shards=total_primary,
        max_shards_per_node=max_shards,
        avg_shards_per_node=round(avg_shards, 2),
        shard_skew_ratio=round(shard_skew, 2),
        storage_skew_ratio=round(storage_skew, 2),
        max_shards_per_gb_heap=round(shards_per_heap, 2),
        large_shard_risk=large_shard,
        small_shard_risk=small_shard,
        oversharding_risk=oversharding,
        storage_skew_risk=storage_skew_risk,
        shard_skew_risk=shard_skew_risk,
        data_scale_in_blocked=blocked,
        recommendations=recommendations,
        source_errors=diagnostics.errors,
    )


def estimate_max_shards_per_gb_heap(diagnostics: OpenSearchDiagnostics, heap_by_node: dict[str, float]) -> float:
    if not diagnostics.allocation or not heap_by_node:
        return 0.0
    values: list[float] = []
    for item in diagnostics.allocation:
        node = item.get("node")
        heap = heap_by_node.get(node) or heap_by_node.get(str(node).split()[0])
        shards = parse_int(item.get("shards"))
        if heap and shards:
            values.append(shards / heap)
    return max(values) if values else 0.0


def parse_int(value: object) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def parse_percent_or_number(value: object) -> float:
    text = str(value or "0").strip().rstrip("%")
    try:
        return float(text)
    except ValueError:
        return 0.0


def parse_size_gb(value: object) -> float:
    text = str(value or "0").strip().lower()
    if not text or text == "-":
        return 0.0
    match = re.fullmatch(r"([0-9.]+)\s*([kmgtp]?b?)?", text)
    if not match:
        try:
            return float(text)
        except ValueError:
            return 0.0
    amount = float(match.group(1))
    unit = (match.group(2) or "gb").replace("b", "")
    factors = {"": 1.0, "g": 1.0, "k": 1 / (1024 * 1024), "m": 1 / 1024, "t": 1024.0, "p": 1024.0 * 1024.0}
    return amount * factors.get(unit, 1.0)
