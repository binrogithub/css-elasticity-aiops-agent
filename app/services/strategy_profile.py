"""Elasticity strategy profile defaults.

Specific environment variables still win over the profile. The profile supplies
operational defaults when a field is not explicitly configured.
"""

from __future__ import annotations

from typing import Any

from app.config import Settings


PROFILE_DEFAULTS: dict[str, dict[str, Any]] = {
    "aggressive": {
        "max_scaling_actions_per_day": 12,
        "scale_out_observation_minutes": 0,
        "scale_in_low_load_minutes": 10,
        "css_data_scale_out_cooldown_minutes": 10,
        "css_data_scale_in_cooldown_minutes": 10,
        "css_data_scale_out_burst_qps_multiplier": 8.0,
        "css_data_scale_out_burst_cpu_min": 15.0,
        "css_data_scale_out_burst_node_fraction": 1.0,
    },
    "balanced": {
        "max_scaling_actions_per_day": 6,
        "scale_out_observation_minutes": 15,
        "scale_in_low_load_minutes": 30,
        "css_data_scale_out_cooldown_minutes": 20,
        "css_data_scale_in_cooldown_minutes": 20,
        "css_data_scale_out_burst_qps_multiplier": 10.0,
        "css_data_scale_out_burst_cpu_min": 20.0,
        "css_data_scale_out_burst_node_fraction": 0.75,
    },
    "conservative": {
        "max_scaling_actions_per_day": 2,
        "scale_out_observation_minutes": 60,
        "scale_in_low_load_minutes": 120,
        "css_data_scale_out_cooldown_minutes": 45,
        "css_data_scale_in_cooldown_minutes": 60,
        "css_data_scale_out_burst_qps_multiplier": 20.0,
        "css_data_scale_out_burst_cpu_min": 35.0,
        "css_data_scale_out_burst_node_fraction": 0.5,
    },
}


def effective_setting(settings: Settings, field_name: str):
    if field_name in settings.model_fields_set:
        return getattr(settings, field_name)
    profile = PROFILE_DEFAULTS.get(settings.elasticity_strategy_profile, PROFILE_DEFAULTS["aggressive"])
    return profile.get(field_name, getattr(settings, field_name))


def effective_max_scaling_actions_per_day(settings: Settings) -> int:
    return int(effective_setting(settings, "max_scaling_actions_per_day"))


def effective_scale_out_observation_minutes(settings: Settings) -> int:
    return int(effective_setting(settings, "scale_out_observation_minutes"))


def effective_scale_in_low_load_minutes(settings: Settings) -> int:
    return int(effective_setting(settings, "scale_in_low_load_minutes"))


def effective_data_scale_out_cooldown_minutes(settings: Settings) -> int:
    return int(effective_setting(settings, "css_data_scale_out_cooldown_minutes"))


def effective_data_scale_in_cooldown_minutes(settings: Settings) -> int:
    return int(effective_setting(settings, "css_data_scale_in_cooldown_minutes"))


def effective_data_burst_qps_multiplier(settings: Settings) -> float:
    return float(effective_setting(settings, "css_data_scale_out_burst_qps_multiplier"))


def effective_data_burst_cpu_min(settings: Settings) -> float:
    return float(effective_setting(settings, "css_data_scale_out_burst_cpu_min"))


def effective_data_burst_node_fraction(settings: Settings) -> float:
    return float(effective_setting(settings, "css_data_scale_out_burst_node_fraction"))


def strategy_summary(settings: Settings) -> dict[str, Any]:
    return {
        "profile": settings.elasticity_strategy_profile,
        "max_scaling_actions_per_day": effective_max_scaling_actions_per_day(settings),
        "scale_out_observation_minutes": effective_scale_out_observation_minutes(settings),
        "scale_in_low_load_minutes": effective_scale_in_low_load_minutes(settings),
        "data_scale_out_cooldown_minutes": effective_data_scale_out_cooldown_minutes(settings),
        "data_scale_in_cooldown_minutes": effective_data_scale_in_cooldown_minutes(settings),
        "data_burst_qps_multiplier": effective_data_burst_qps_multiplier(settings),
        "data_burst_cpu_min": effective_data_burst_cpu_min(settings),
        "data_burst_node_fraction": effective_data_burst_node_fraction(settings),
    }
