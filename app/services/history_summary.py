"""Recent history summarization."""

from app.models.metrics import MetricsSnapshot


def summarize_metrics_history(snapshots: list[dict]) -> str:
    if not snapshots:
        return "No historical metrics available."
    cpus = [float(item.get("cpu_avg", 0)) for item in snapshots]
    qps_values = [float(item.get("qps_avg", 0)) for item in snapshots]
    latencies = [float(item.get("search_latency_avg_ms", 0)) for item in snapshots]
    queues = [int(item.get("search_queue", 0)) for item in snapshots]
    rejected = [int(item.get("search_rejected", 0)) for item in snapshots]
    return (
        f"Recent samples={len(snapshots)}, "
        f"cpu_avg_range={min(cpus):.1f}-{max(cpus):.1f}, "
        f"qps_avg_range={min(qps_values):.1f}-{max(qps_values):.1f}, "
        f"latency_avg_ms_range={min(latencies):.2f}-{max(latencies):.2f}, "
        f"max_search_queue={max(queues)}, "
        f"max_search_rejected={max(rejected)}"
    )


def summarize_business_trend(snapshots: list[dict], *, sample_interval_seconds: int = 300) -> str:
    """Summarize load growth/decline so AI can size scaling deltas.

    Repositories return snapshots newest-first, so reverse before comparing.
    """
    if len(snapshots) < 2:
        return "Insufficient metric history to estimate business growth or decline."
    ordered = list(reversed(snapshots))
    first = ordered[0]
    last = ordered[-1]
    elapsed_minutes = max(1.0, (len(ordered) - 1) * sample_interval_seconds / 60)
    first_qps = float(first.get("qps_avg", 0))
    last_qps = float(last.get("qps_avg", 0))
    first_cpu = float(first.get("cpu_avg", 0))
    last_cpu = float(last.get("cpu_avg", 0))
    first_latency = float(first.get("search_latency_avg_ms", 0))
    last_latency = float(last.get("search_latency_avg_ms", 0))
    qps_delta = last_qps - first_qps
    cpu_delta = last_cpu - first_cpu
    latency_delta = last_latency - first_latency
    qps_pct = (qps_delta / first_qps * 100) if first_qps > 0 else (100.0 if last_qps > 0 else 0.0)
    direction = "stable"
    if qps_pct >= 50 or cpu_delta >= 15 or latency_delta >= 100:
        direction = "growth"
    elif qps_pct <= -50 and cpu_delta <= -10 and latency_delta <= 0:
        direction = "decline"
    return (
        f"Business trend window={elapsed_minutes:.1f} minutes, direction={direction}, "
        f"qps_start={first_qps:.1f}, qps_end={last_qps:.1f}, qps_delta={qps_delta:.1f}, "
        f"qps_change_pct={qps_pct:.1f}, qps_delta_per_minute={qps_delta / elapsed_minutes:.1f}, "
        f"cpu_start={first_cpu:.1f}, cpu_end={last_cpu:.1f}, cpu_delta={cpu_delta:.1f}, "
        f"latency_start_ms={first_latency:.1f}, latency_end_ms={last_latency:.1f}, "
        f"latency_delta_ms={latency_delta:.1f}"
    )


def summarize_pair(current: MetricsSnapshot, previous: MetricsSnapshot | None) -> str:
    if not previous:
        return "No previous snapshot available."
    return (
        f"CPU delta={current.cpu_avg - previous.cpu_avg:.1f}, "
        f"latency delta={current.search_latency_avg_ms - previous.search_latency_avg_ms:.1f}ms, "
        f"QPS delta={current.qps_avg - previous.qps_avg:.1f}, "
        f"rejected delta={current.search_rejected - previous.search_rejected}"
    )


def estimate_low_load_minutes(
    snapshots: list[dict],
    *,
    sample_interval_seconds: int = 300,
    cpu_limit: float = 30.0,
    qps_limit: float = 200.0,
) -> int:
    """Estimate contiguous low-load duration from recent snapshots.

    This is intentionally conservative. If timestamps are missing or the recent
    low-load evidence is sparse, it returns a short duration.
    """
    if not snapshots:
        return 0
    ordered = list(reversed(snapshots))
    low_samples = [
        item
        for item in ordered
        if float(item.get("cpu_avg", 0)) <= cpu_limit
        and float(item.get("qps_avg", 0)) <= qps_limit
        and int(item.get("search_queue", 0)) == 0
        and int(item.get("search_rejected", 0)) == 0
    ]
    if len(low_samples) != len(ordered):
        contiguous = 0
        for item in reversed(ordered):
            if item not in low_samples:
                break
            contiguous += 1
        return int(contiguous * sample_interval_seconds / 60)
    return int(len(low_samples) * sample_interval_seconds / 60)
