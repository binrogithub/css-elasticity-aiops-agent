"""OpenSearch diagnostics and capacity analysis models."""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class OpenSearchDiagnostics(BaseModel):
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cluster_health: dict[str, Any] = Field(default_factory=dict)
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    allocation: list[dict[str, Any]] = Field(default_factory=list)
    indices: list[dict[str, Any]] = Field(default_factory=list)
    shards: list[dict[str, Any]] = Field(default_factory=list)
    search_stats: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class CapacityAnalysis(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    available: bool = False
    risk_level: str = "unknown"
    avg_primary_shard_size_gb: float = 0.0
    max_primary_shard_size_gb: float = 0.0
    total_shards: int = 0
    total_primary_shards: int = 0
    max_shards_per_node: int = 0
    avg_shards_per_node: float = 0.0
    shard_skew_ratio: float = 0.0
    storage_skew_ratio: float = 0.0
    max_shards_per_gb_heap: float = 0.0
    large_shard_risk: bool = False
    small_shard_risk: bool = False
    oversharding_risk: bool = False
    storage_skew_risk: bool = False
    shard_skew_risk: bool = False
    data_scale_in_blocked: bool = False
    recommendations: list[str] = Field(default_factory=list)
    source_errors: list[str] = Field(default_factory=list)
