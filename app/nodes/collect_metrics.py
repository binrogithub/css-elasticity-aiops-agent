"""collect_metrics node."""

from app.models.metrics import MetricsSnapshot
from app.runtime import Runtime
from app.services.capacity_analyzer import analyze_capacity
from app.services.strategy_profile import effective_scale_in_low_load_minutes
from app.services.validation import build_node_limits
from app.state import AgentState


def collect_metrics_node(runtime: Runtime):
    def node(state: AgentState) -> AgentState:
        previous_snapshot = state.last_metrics
        if previous_snapshot is None:
            persisted = runtime.state_repo.get("last_metrics")
            if persisted:
                previous_snapshot = MetricsSnapshot.model_validate(persisted)
        snapshot = runtime.metrics_provider.collect(state.cluster_id)
        topology = runtime.executor.current_topology()
        available_flavors = runtime.executor.available_flavors()
        node_limits = build_node_limits(runtime.settings)
        diagnostics = runtime.diagnostics_provider.collect()
        snapshot, node_summary = merge_realtime_node_metrics(snapshot, diagnostics.nodes)
        snapshot, realtime_summary = merge_realtime_opensearch_metrics(
            snapshot,
            diagnostics.search_stats,
            runtime.state_repo.get("opensearch_search_stats"),
        )
        if diagnostics.search_stats:
            runtime.state_repo.set(
                "opensearch_search_stats",
                {
                    "timestamp": snapshot.timestamp.isoformat(),
                    "query_total": diagnostics.search_stats.get("query_total", 0),
                    "query_time_in_millis": diagnostics.search_stats.get("query_time_in_millis", 0),
                    "search_rejected": diagnostics.search_stats.get("search_rejected", 0),
                },
            )
        capacity_analysis = analyze_capacity(diagnostics, runtime.settings)
        runtime.settings.ensure_dirs()
        runtime.state_repo.set("last_metrics", snapshot.model_dump())
        return state.patch(
            prev_metrics=previous_snapshot,
            last_metrics=snapshot,
            last_resource_check_time=snapshot.timestamp,
            current_nodes=runtime.executor.current_nodes(),
            topology=topology,
            available_flavors=available_flavors,
            node_limits=node_limits,
            diagnostics=diagnostics,
            capacity_analysis=capacity_analysis,
            metadata={
                **state.metadata,
                "traffic_entry_mode": runtime.settings.css_traffic_entry_mode,
                "client_scale_in_allowed": runtime.settings.css_client_scale_in_allowed,
                "enterprise_policy_profile": runtime.settings.enterprise_policy_profile,
                "opensearch_realtime_summary": f"{node_summary} {realtime_summary}".strip(),
                "scale_in_low_load_minutes": effective_scale_in_low_load_minutes(runtime.settings),
            },
        )

    return node


def merge_realtime_node_metrics(snapshot: MetricsSnapshot, nodes: list[dict]) -> tuple[MetricsSnapshot, str]:
    if not nodes:
        return snapshot, "OpenSearch realtime node CPU unavailable."

    data_nodes = [
        item
        for item in nodes
        if "d" in str(item.get("node.role", "")) or "data" in str(item.get("roles", ""))
    ]
    if not data_nodes:
        return snapshot, "OpenSearch realtime Data node CPU unavailable."

    cpus = [_safe_float(item.get("cpu")) for item in data_nodes]
    heaps = [_safe_float(item.get("heap.percent")) for item in data_nodes]
    cpus = [item for item in cpus if item is not None]
    heaps = [item for item in heaps if item is not None]
    if not cpus and not heaps:
        return snapshot, "OpenSearch realtime Data node CPU/JVM values unavailable."

    realtime_cpu = sum(cpus) / len(cpus) if cpus else snapshot.cpu_avg
    realtime_heap = sum(heaps) / len(heaps) if heaps else snapshot.jvm_heap_avg
    merged = snapshot.model_copy(
        update={
            "cpu_avg": max(snapshot.cpu_avg, realtime_cpu),
            "jvm_heap_avg": max(snapshot.jvm_heap_avg, realtime_heap),
        }
    )
    return (
        merged,
        f"OpenSearch realtime Data nodes={len(data_nodes)}, "
        f"data_cpu_avg={realtime_cpu:.1f}, data_cpu_max={max(cpus) if cpus else 0:.1f}, "
        f"data_jvm_avg={realtime_heap:.1f}.",
    )


def _safe_float(value) -> float | None:
    try:
        if value in {None, ""}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def merge_realtime_opensearch_metrics(
    snapshot: MetricsSnapshot,
    current_stats: dict,
    previous_stats: dict | None,
) -> tuple[MetricsSnapshot, str]:
    if not current_stats:
        return snapshot, "OpenSearch realtime search stats unavailable."
    queue = int(current_stats.get("search_queue", 0) or 0)
    rejected_total = int(current_stats.get("search_rejected", 0) or 0)
    active = int(current_stats.get("search_active", 0) or 0)
    current = int(current_stats.get("search_current", 0) or 0)
    if not previous_stats:
        merged = snapshot.model_copy(update={"search_queue": max(snapshot.search_queue, queue)})
        return (
            merged,
            f"OpenSearch realtime totals captured; queue={queue}, active={active}, current={current}, "
            "need one more sample for realtime QPS delta.",
        )

    prev_total = int(previous_stats.get("query_total", 0) or 0)
    prev_time = int(previous_stats.get("query_time_in_millis", 0) or 0)
    prev_rejected = int(previous_stats.get("search_rejected", 0) or 0)
    query_total = int(current_stats.get("query_total", 0) or 0)
    query_time = int(current_stats.get("query_time_in_millis", 0) or 0)
    elapsed = max((snapshot.timestamp - MetricsSnapshot.model_validate({"timestamp": previous_stats["timestamp"]}).timestamp).total_seconds(), 1)
    query_delta = max(0, query_total - prev_total)
    query_time_delta = max(0, query_time - prev_time)
    rejected_delta = max(0, rejected_total - prev_rejected)
    realtime_qps = query_delta / elapsed
    realtime_latency = query_time_delta / query_delta if query_delta else snapshot.search_latency_avg_ms
    merged = snapshot.model_copy(
        update={
            "qps_avg": max(snapshot.qps_avg, realtime_qps),
            "search_latency_avg_ms": max(snapshot.search_latency_avg_ms, realtime_latency),
            "search_queue": max(snapshot.search_queue, queue),
            "search_rejected": max(snapshot.search_rejected, rejected_delta),
        }
    )
    return (
        merged,
        f"OpenSearch realtime window={elapsed:.1f}s, query_delta={query_delta}, "
        f"realtime_qps={realtime_qps:.1f}, realtime_latency_ms={realtime_latency:.2f}, "
        f"queue={queue}, active={active}, current={current}, rejected_delta={rejected_delta}.",
    )
