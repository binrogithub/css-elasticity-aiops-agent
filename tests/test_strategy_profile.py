from app.config import Settings
from app.services.strategy_profile import (
    effective_data_burst_cpu_min,
    effective_data_burst_node_fraction,
    effective_data_burst_qps_multiplier,
    effective_data_scale_in_cooldown_minutes,
    effective_data_scale_out_cooldown_minutes,
    effective_max_scaling_actions_per_day,
    effective_scale_in_low_load_minutes,
    effective_scale_out_observation_minutes,
)


def test_aggressive_profile_is_default():
    settings = Settings()

    assert settings.elasticity_strategy_profile == "aggressive"
    assert effective_scale_in_low_load_minutes(settings) == 10
    assert effective_scale_out_observation_minutes(settings) == 0
    assert effective_data_scale_out_cooldown_minutes(settings) == 10
    assert effective_data_scale_in_cooldown_minutes(settings) == 10
    assert effective_max_scaling_actions_per_day(settings) == 12
    assert effective_data_burst_qps_multiplier(settings) == 8.0
    assert effective_data_burst_cpu_min(settings) == 15.0
    assert effective_data_burst_node_fraction(settings) == 1.0


def test_balanced_profile_defaults():
    settings = Settings(ELASTICITY_STRATEGY_PROFILE="balanced")

    assert effective_scale_in_low_load_minutes(settings) == 30
    assert effective_scale_out_observation_minutes(settings) == 15
    assert effective_data_scale_out_cooldown_minutes(settings) == 20
    assert effective_data_scale_in_cooldown_minutes(settings) == 20
    assert effective_max_scaling_actions_per_day(settings) == 6
    assert effective_data_burst_qps_multiplier(settings) == 10.0
    assert effective_data_burst_cpu_min(settings) == 20.0
    assert effective_data_burst_node_fraction(settings) == 0.75


def test_conservative_profile_defaults():
    settings = Settings(ELASTICITY_STRATEGY_PROFILE="conservative")

    assert effective_scale_in_low_load_minutes(settings) == 120
    assert effective_scale_out_observation_minutes(settings) == 60
    assert effective_data_scale_out_cooldown_minutes(settings) == 45
    assert effective_data_scale_in_cooldown_minutes(settings) == 60
    assert effective_max_scaling_actions_per_day(settings) == 2
    assert effective_data_burst_qps_multiplier(settings) == 20.0
    assert effective_data_burst_cpu_min(settings) == 35.0
    assert effective_data_burst_node_fraction(settings) == 0.5


def test_explicit_setting_overrides_profile_default():
    settings = Settings(
        ELASTICITY_STRATEGY_PROFILE="conservative",
        SCALE_IN_LOW_LOAD_MINUTES=15,
        CSS_DATA_SCALE_OUT_BURST_QPS_MULTIPLIER=6,
    )

    assert effective_scale_in_low_load_minutes(settings) == 15
    assert effective_data_burst_qps_multiplier(settings) == 6
    assert effective_scale_out_observation_minutes(settings) == 60
