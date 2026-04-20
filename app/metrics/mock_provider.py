"""Mock metrics provider."""

import itertools

from app.metrics.base import MetricsProvider
from app.models.metrics import MetricsSnapshot


class MockMetricsProvider(MetricsProvider):
    """Deterministic synthetic metrics for local runs."""

    def __init__(self):
        self._counter = itertools.count(1)

    def collect(self, cluster_id: str) -> MetricsSnapshot:
        tick = next(self._counter)
        pressure = tick % 4 == 0
        return MetricsSnapshot(
            cluster_health="green",
            cpu_avg=86 if pressure else 35,
            jvm_heap_avg=72 if pressure else 45,
            search_latency_avg_ms=850 if pressure else 120,
            qps_avg=900 if pressure else 150,
            search_queue=30 if pressure else 0,
            search_rejected=2 if pressure else 0,
            disk_usage_pct=41,
        )
