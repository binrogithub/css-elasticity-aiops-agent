from datetime import datetime, timezone, timedelta

from app.models.metrics import MetricsSnapshot
from app.nodes.collect_metrics import merge_realtime_node_metrics, merge_realtime_opensearch_metrics


def test_realtime_opensearch_metrics_override_stale_cloud_eye_qps():
    now = datetime.now(timezone.utc)
    snapshot = MetricsSnapshot(timestamp=now, qps_avg=80, search_latency_avg_ms=1, search_queue=0)
    previous = {
        "timestamp": (now - timedelta(seconds=60)).isoformat(),
        "query_total": 1000,
        "query_time_in_millis": 10000,
        "search_rejected": 0,
    }
    current = {
        "query_total": 61000,
        "query_time_in_millis": 130000,
        "search_queue": 2,
        "search_rejected": 3,
        "search_active": 10,
        "search_current": 10,
    }

    merged, summary = merge_realtime_opensearch_metrics(snapshot, current, previous)

    assert merged.qps_avg == 1000
    assert merged.search_latency_avg_ms == 2
    assert merged.search_queue == 2
    assert merged.search_rejected == 3
    assert "realtime_qps=1000.0" in summary


def test_realtime_node_metrics_merge_data_cpu_and_heap():
    snapshot = MetricsSnapshot(cpu_avg=0, jvm_heap_avg=20)
    nodes = [
        {"node.role": "dimr", "cpu": "24", "heap.percent": "60"},
        {"node.role": "dimr", "cpu": "30", "heap.percent": "50"},
        {"node.role": "ir", "cpu": "99", "heap.percent": "70"},
    ]

    merged, summary = merge_realtime_node_metrics(snapshot, nodes)

    assert merged.cpu_avg == 27
    assert merged.jvm_heap_avg == 55
    assert "Data nodes=2" in summary
