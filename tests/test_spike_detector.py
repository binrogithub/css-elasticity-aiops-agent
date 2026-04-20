from app.config import Settings
from app.models.metrics import MetricsSnapshot
from app.services.spike_detector import SpikeDetector


def test_cpu_spike_detected():
    settings = Settings(CPU_SPIKE_THRESHOLD=80)
    result = SpikeDetector(settings).detect(MetricsSnapshot(cpu_avg=90), None)
    assert result.spike_detected
    assert "CPU" in result.spike_reason


def test_qps_jump_detected():
    settings = Settings(QPS_SPIKE_THRESHOLD=2)
    prev = MetricsSnapshot(qps_avg=100)
    curr = MetricsSnapshot(qps_avg=250)
    result = SpikeDetector(settings).detect(curr, prev)
    assert result.spike_detected
    assert "QPS" in result.spike_reason
