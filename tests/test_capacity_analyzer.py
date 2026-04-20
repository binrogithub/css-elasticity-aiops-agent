from app.config import Settings
from app.models.diagnostics import OpenSearchDiagnostics
from app.services.capacity_analyzer import analyze_capacity, parse_size_gb


def test_parse_size_gb_units():
    assert parse_size_gb("50gb") == 50
    assert parse_size_gb("1tb") == 1024
    assert round(parse_size_gb("512mb"), 2) == 0.5


def test_large_shard_blocks_data_scale_in():
    diagnostics = OpenSearchDiagnostics(
        nodes=[{"name": "n1", "heap.max": "16gb"}],
        allocation=[{"node": "n1", "shards": "10", "disk.percent": "60"}],
        shards=[
            {"index": "i1", "prirep": "p", "state": "STARTED", "store": "61gb", "node": "n1"},
            {"index": "i1", "prirep": "r", "state": "STARTED", "store": "61gb", "node": "n1"},
        ],
    )
    analysis = analyze_capacity(diagnostics, Settings())
    assert analysis.available
    assert analysis.large_shard_risk
    assert analysis.data_scale_in_blocked
    assert analysis.risk_level == "high"


def test_storage_skew_detected():
    diagnostics = OpenSearchDiagnostics(
        nodes=[{"name": "n1", "heap.max": "16gb"}, {"name": "n2", "heap.max": "16gb"}],
        allocation=[
            {"node": "n1", "shards": "10", "disk.percent": "90"},
            {"node": "n2", "shards": "10", "disk.percent": "30"},
        ],
        shards=[
            {"index": "i1", "prirep": "p", "state": "STARTED", "store": "20gb", "node": "n1"},
            {"index": "i2", "prirep": "p", "state": "STARTED", "store": "20gb", "node": "n2"},
        ],
    )
    analysis = analyze_capacity(diagnostics, Settings(MAX_STORAGE_SKEW_RATIO=1.4))
    assert analysis.storage_skew_risk
    assert analysis.data_scale_in_blocked
