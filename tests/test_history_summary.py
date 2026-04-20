from app.services.history_summary import estimate_low_load_minutes, summarize_business_trend


def _low_sample() -> dict:
    return {
        "cpu_avg": 10,
        "qps_avg": 10,
        "search_queue": 0,
        "search_rejected": 0,
    }


def test_low_load_estimate_uses_configured_sample_interval():
    snapshots = [_low_sample(), _low_sample(), _low_sample()]

    assert estimate_low_load_minutes(snapshots, sample_interval_seconds=60) == 3
    assert estimate_low_load_minutes(snapshots, sample_interval_seconds=300) == 15


def test_business_trend_reports_growth():
    snapshots = [
        {"cpu_avg": 50, "qps_avg": 500, "search_latency_avg_ms": 150},
        {"cpu_avg": 20, "qps_avg": 100, "search_latency_avg_ms": 20},
    ]

    summary = summarize_business_trend(snapshots, sample_interval_seconds=60)

    assert "direction=growth" in summary
    assert "qps_change_pct=400.0" in summary
