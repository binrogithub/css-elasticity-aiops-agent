from app.config import Settings
from app.models.actions import ActionResult
from app.services.scaling_advisor import recommend_data_scale_in_delta, recommend_data_scale_out_delta


def test_data_scale_out_advisor_uses_cpu_and_qps_growth():
    snapshots = [
        {"cpu_avg": 75, "qps_avg": 900, "search_latency_avg_ms": 100},
        {"cpu_avg": 45, "qps_avg": 300, "search_latency_avg_ms": 50},
    ]

    advice = recommend_data_scale_out_delta(
        snapshots,
        current_data_nodes=10,
        node_limits={"min": 1, "max": 50},
        settings=Settings(
            CSS_DATA_SCALE_OUT_MIN_DELTA=1,
            CSS_DATA_SCALE_OUT_MAX_DELTA=200,
            CSS_DATA_SCALE_OUT_TARGET_CPU=65,
            CSS_DATA_SCALE_OUT_PROJECTION_MINUTES=30,
        ),
        sample_interval_seconds=60,
    )

    assert advice["recommended_delta"] > 1
    assert advice["needed_by_cpu"] > 0
    assert advice["needed_by_qps"] > 0


def test_data_scale_out_advisor_uses_burst_floor_for_large_qps_jump_with_cpu_pressure():
    snapshots = [
        {"cpu_avg": 24, "qps_avg": 4800, "search_latency_avg_ms": 130},
        {"cpu_avg": 0, "qps_avg": 80, "search_latency_avg_ms": 1},
    ]

    advice = recommend_data_scale_out_delta(
        snapshots,
        current_data_nodes=3,
        node_limits={"min": 1, "max": 200},
        settings=Settings(
            CSS_DATA_SCALE_OUT_MIN_DELTA=1,
            CSS_DATA_SCALE_OUT_MAX_DELTA=3,
            CSS_DATA_SCALE_OUT_TARGET_CPU=65,
            CSS_DATA_SCALE_OUT_BURST_QPS_MULTIPLIER=10,
            CSS_DATA_SCALE_OUT_BURST_CPU_MIN=20,
            CSS_DATA_SCALE_OUT_BURST_NODE_FRACTION=1.0,
        ),
        sample_interval_seconds=60,
    )

    assert advice["burst_floor_delta"] == 3
    assert advice["recommended_delta"] == 3


def test_data_scale_out_advisor_respects_min_max_delta_and_headroom():
    snapshots = [
        {"cpu_avg": 95, "qps_avg": 2000, "search_latency_avg_ms": 200},
        {"cpu_avg": 50, "qps_avg": 500, "search_latency_avg_ms": 80},
    ]

    advice = recommend_data_scale_out_delta(
        snapshots,
        current_data_nodes=8,
        node_limits={"min": 1, "max": 10},
        settings=Settings(
            CSS_DATA_SCALE_OUT_MIN_DELTA=5,
            CSS_DATA_SCALE_OUT_MAX_DELTA=200,
            CSS_DATA_SCALE_OUT_TARGET_CPU=65,
            CSS_DATA_SCALE_OUT_PROJECTION_MINUTES=30,
        ),
        sample_interval_seconds=60,
    )

    assert advice["recommended_delta"] == 2


def test_data_scale_out_advisor_returns_zero_without_growth():
    snapshots = [
        {"cpu_avg": 20, "qps_avg": 100, "search_latency_avg_ms": 20},
        {"cpu_avg": 25, "qps_avg": 120, "search_latency_avg_ms": 25},
    ]

    advice = recommend_data_scale_out_delta(
        snapshots,
        current_data_nodes=20,
        node_limits={"min": 1, "max": 200},
        settings=Settings(),
        sample_interval_seconds=300,
    )

    assert advice["recommended_delta"] == 0


def test_data_scale_in_advisor_reclaims_recent_data_scale_out_after_low_load_window():
    actions = [
        ActionResult(
            requested_action="scale_out",
            executed_action="scale_out",
            node_type="ess",
            requested_delta=2,
            applied_delta=2,
            previous_node_count=3,
            new_node_count=5,
            status="success",
        )
    ]

    advice = recommend_data_scale_in_delta(
        recent_actions=actions,
        current_data_nodes=5,
        node_limits={"min": 1, "max": 200},
        low_load_minutes=12,
        settings=Settings(CSS_DATA_SCALE_IN_MAX_DELTA=3, SCALE_IN_LOW_LOAD_MINUTES=10),
    )

    assert advice["recommended_delta"] == 2
    assert advice["target_delta"] == 2
    assert advice["provider_safe_delta"] == 2


def test_data_scale_in_advisor_uses_provider_safe_batch_for_half_shrink_limit():
    actions = [
        ActionResult(
            requested_action="scale_out",
            executed_action="scale_out",
            node_type="ess",
            requested_delta=3,
            applied_delta=3,
            previous_node_count=3,
            new_node_count=6,
            status="success",
        )
    ]

    advice = recommend_data_scale_in_delta(
        recent_actions=actions,
        current_data_nodes=6,
        node_limits={"min": 1, "max": 200},
        low_load_minutes=12,
        settings=Settings(CSS_DATA_SCALE_IN_MAX_DELTA=10, SCALE_IN_LOW_LOAD_MINUTES=10),
    )

    assert advice["target_delta"] == 3
    assert advice["provider_safe_delta"] == 2
    assert advice["recommended_delta"] == 2


def test_data_scale_in_advisor_waits_for_low_load_window():
    actions = [
        ActionResult(
            requested_action="scale_out",
            executed_action="scale_out",
            node_type="ess",
            requested_delta=2,
            applied_delta=2,
            previous_node_count=3,
            new_node_count=5,
            status="success",
        )
    ]

    advice = recommend_data_scale_in_delta(
        recent_actions=actions,
        current_data_nodes=5,
        node_limits={"min": 1, "max": 200},
        low_load_minutes=6,
        settings=Settings(CSS_DATA_SCALE_IN_MAX_DELTA=3, SCALE_IN_LOW_LOAD_MINUTES=10),
    )

    assert advice["recommended_delta"] == 0


def test_data_scale_in_advisor_uses_profile_low_load_window():
    actions = [
        ActionResult(
            requested_action="scale_out",
            executed_action="scale_out",
            node_type="ess",
            requested_delta=2,
            applied_delta=2,
            previous_node_count=3,
            new_node_count=5,
            status="success",
        )
    ]

    advice = recommend_data_scale_in_delta(
        recent_actions=actions,
        current_data_nodes=5,
        node_limits={"min": 1, "max": 200},
        low_load_minutes=20,
        settings=Settings(ELASTICITY_STRATEGY_PROFILE="balanced", CSS_DATA_SCALE_IN_MAX_DELTA=3),
    )

    assert advice["required_low_load_minutes"] == 30
    assert advice["recommended_delta"] == 0
