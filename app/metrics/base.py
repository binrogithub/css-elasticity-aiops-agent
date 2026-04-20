"""Metrics provider interface."""

from abc import ABC, abstractmethod

from app.models.metrics import MetricsSnapshot


class MetricsProvider(ABC):
    @abstractmethod
    def collect(self, cluster_id: str) -> MetricsSnapshot:
        """Collect one metrics snapshot."""
