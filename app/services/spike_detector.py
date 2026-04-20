"""Spike detection service."""

from dataclasses import dataclass

from app.config import Settings
from app.models.metrics import MetricsSnapshot


@dataclass(frozen=True)
class SpikeResult:
    spike_detected: bool
    spike_reason: str


class SpikeDetector:
    def __init__(self, settings: Settings):
        self.settings = settings

    def detect(self, current: MetricsSnapshot, previous: MetricsSnapshot | None) -> SpikeResult:
        reasons: list[str] = []
        if current.cpu_avg >= self.settings.cpu_spike_threshold:
            reasons.append(f"CPU {current.cpu_avg:.1f} crossed threshold")
        if previous:
            latency_delta = current.search_latency_avg_ms - previous.search_latency_avg_ms
            if latency_delta >= self.settings.latency_spike_threshold:
                reasons.append(f"Latency jumped by {latency_delta:.1f}ms")
            if previous.search_rejected == 0 and current.search_rejected > 0:
                reasons.append("Search rejected changed from zero to positive")
            elif current.search_rejected - previous.search_rejected >= self.settings.rejected_spike_threshold:
                reasons.append("Search rejected increased sharply")
            if previous.qps_avg > 0 and current.qps_avg / previous.qps_avg >= self.settings.qps_spike_threshold:
                reasons.append("QPS jumped sharply")

        return SpikeResult(bool(reasons), "; ".join(reasons) if reasons else "No spike detected")
