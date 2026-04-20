"""Metric domain models."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


ClusterHealth = Literal["green", "yellow", "red", "unknown"]


class MetricsSnapshot(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cluster_health: ClusterHealth = "unknown"
    cpu_avg: float = 0
    jvm_heap_avg: float = 0
    search_latency_avg_ms: float = 0
    qps_avg: float = 0
    search_queue: int = 0
    search_rejected: int = 0
    disk_usage_pct: float = 0


class MetricsTrend(BaseModel):
    cpu_delta: float = 0
    latency_delta_ms: float = 0
    qps_ratio: float = 1
    rejected_delta: int = 0
