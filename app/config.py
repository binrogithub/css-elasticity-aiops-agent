"""Runtime configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class Settings(BaseSettings):
    """Environment-driven settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    ai_max_retries: int = Field(default=2, alias="AI_MAX_RETRIES")
    ai_retry_backoff_seconds: float = Field(default=1.0, alias="AI_RETRY_BACKOFF_SECONDS")

    resource_check_interval_seconds: int = Field(default=300, alias="RESOURCE_CHECK_INTERVAL_SECONDS")
    ai_check_interval_seconds: int = Field(default=1800, alias="AI_CHECK_INTERVAL_SECONDS")

    cpu_spike_threshold: float = Field(default=80, alias="CPU_SPIKE_THRESHOLD")
    latency_spike_threshold: float = Field(default=500, alias="LATENCY_SPIKE_THRESHOLD")
    rejected_spike_threshold: int = Field(default=1, alias="REJECTED_SPIKE_THRESHOLD")
    qps_spike_threshold: float = Field(default=2.0, alias="QPS_SPIKE_THRESHOLD")

    min_nodes: int = Field(default=1, alias="MIN_NODES")
    max_nodes: int = Field(default=5, alias="MAX_NODES")
    initial_nodes: int = Field(default=2, alias="INITIAL_NODES")
    default_cooldown_minutes: int = Field(default=30, alias="DEFAULT_COOLDOWN_MINUTES")
    css_node_limits_json: str = Field(default="", alias="CSS_NODE_LIMITS_JSON")
    css_default_data_min: int = Field(default=1, alias="CSS_DEFAULT_DATA_MIN")
    css_default_data_max: int = Field(default=200, alias="CSS_DEFAULT_DATA_MAX")
    css_default_client_min: int = Field(default=0, alias="CSS_DEFAULT_CLIENT_MIN")
    css_default_client_max: int = Field(default=64, alias="CSS_DEFAULT_CLIENT_MAX")
    css_default_master_allowed_counts: str = Field(default="0,3,5,7,9", alias="CSS_DEFAULT_MASTER_ALLOWED_COUNTS")
    css_allow_flavor_change: bool = Field(default=True, alias="CSS_ALLOW_FLAVOR_CHANGE")
    css_allow_add_independent_nodes: bool = Field(default=True, alias="CSS_ALLOW_ADD_INDEPENDENT_NODES")
    css_mutation_enabled: bool = Field(default=False, alias="CSS_MUTATION_ENABLED")
    agent_run_mode: Literal["observe-only", "recommend-only", "approval-required", "auto-execute"] = Field(
        default="recommend-only", alias="AGENT_RUN_MODE"
    )
    enterprise_policy_profile: Literal["standard", "large-cluster"] = Field(
        default="standard", alias="ENTERPRISE_POLICY_PROFILE"
    )
    elasticity_strategy_profile: Literal["aggressive", "balanced", "conservative"] = Field(
        default="aggressive", alias="ELASTICITY_STRATEGY_PROFILE"
    )
    policy_version: str = Field(default="enterprise-policy-v1", alias="POLICY_VERSION")
    maintenance_window_utc: str = Field(default="", alias="MAINTENANCE_WINDOW_UTC")
    max_scaling_actions_per_day: int = Field(default=12, alias="MAX_SCALING_ACTIONS_PER_DAY")
    max_scale_out_percent: float = Field(default=20.0, alias="MAX_SCALE_OUT_PERCENT")
    scale_out_observation_minutes: int = Field(default=0, alias="SCALE_OUT_OBSERVATION_MINUTES")
    scale_in_low_load_minutes: int = Field(default=10, alias="SCALE_IN_LOW_LOAD_MINUTES")
    fast_scale_in_review_enabled: bool = Field(default=True, alias="FAST_SCALE_IN_REVIEW_ENABLED")
    css_client_scale_out_max_delta: int = Field(default=0, alias="CSS_CLIENT_SCALE_OUT_MAX_DELTA")
    css_client_scale_in_max_delta: int = Field(default=0, alias="CSS_CLIENT_SCALE_IN_MAX_DELTA")
    css_data_scale_out_min_delta: int = Field(default=1, alias="CSS_DATA_SCALE_OUT_MIN_DELTA")
    css_data_scale_out_max_delta: int = Field(default=200, alias="CSS_DATA_SCALE_OUT_MAX_DELTA")
    css_data_scale_in_max_delta: int = Field(default=0, alias="CSS_DATA_SCALE_IN_MAX_DELTA")
    css_data_scale_out_target_cpu: float = Field(default=65.0, alias="CSS_DATA_SCALE_OUT_TARGET_CPU")
    css_data_scale_out_projection_minutes: int = Field(default=30, alias="CSS_DATA_SCALE_OUT_PROJECTION_MINUTES")
    css_data_scale_out_burst_qps_multiplier: float = Field(
        default=8.0, alias="CSS_DATA_SCALE_OUT_BURST_QPS_MULTIPLIER"
    )
    css_data_scale_out_burst_cpu_min: float = Field(default=15.0, alias="CSS_DATA_SCALE_OUT_BURST_CPU_MIN")
    css_data_scale_out_burst_node_fraction: float = Field(
        default=1.0, alias="CSS_DATA_SCALE_OUT_BURST_NODE_FRACTION"
    )
    css_client_scale_out_cooldown_minutes: int = Field(default=30, alias="CSS_CLIENT_SCALE_OUT_COOLDOWN_MINUTES")
    css_client_scale_in_cooldown_minutes: int = Field(default=10, alias="CSS_CLIENT_SCALE_IN_COOLDOWN_MINUTES")
    css_data_scale_out_cooldown_minutes: int = Field(default=10, alias="CSS_DATA_SCALE_OUT_COOLDOWN_MINUTES")
    css_data_scale_in_cooldown_minutes: int = Field(default=10, alias="CSS_DATA_SCALE_IN_COOLDOWN_MINUTES")
    auto_execute_node_types: str = Field(default="ess", alias="AUTO_EXECUTE_NODE_TYPES")
    approval_required_actions: str = Field(
        default="ess-client:scale_out,ess-client:scale_in,ess-master:scale_out,ess-master:scale_in,change_flavor",
        alias="APPROVAL_REQUIRED_ACTIONS",
    )
    css_data_scale_in_allowed: bool = Field(default=True, alias="CSS_DATA_SCALE_IN_ALLOWED")
    css_traffic_entry_mode: Literal["unknown", "direct_ip", "load_balancer"] = Field(
        default="unknown", alias="CSS_TRAFFIC_ENTRY_MODE"
    )
    css_client_scale_in_allowed: bool = Field(default=False, alias="CSS_CLIENT_SCALE_IN_ALLOWED")
    css_default_volume_type: str = Field(default="COMMON", alias="CSS_DEFAULT_VOLUME_TYPE")
    css_default_master_volume_size: int = Field(default=40, alias="CSS_DEFAULT_MASTER_VOLUME_SIZE")
    css_default_client_volume_size: int = Field(default=40, alias="CSS_DEFAULT_CLIENT_VOLUME_SIZE")

    sqlite_db_path: str = Field(default="data/agent.sqlite3", alias="SQLITE_DB_PATH")
    log_dir: str = Field(default="data/logs", alias="LOG_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    json_logs: bool = Field(default=False, alias="JSON_LOGS")

    cluster_id: str = Field(default="mock-cluster", alias="CLUSTER_ID")
    cluster_name: str = Field(default="mock-css-cluster", alias="CLUSTER_NAME")

    metrics_provider: Literal["mock", "css"] = Field(default="mock", alias="METRICS_PROVIDER")
    executor_provider: Literal["mock", "css"] = Field(default="mock", alias="EXECUTOR_PROVIDER")
    diagnostics_provider: Literal["disabled", "opensearch"] = Field(default="disabled", alias="DIAGNOSTICS_PROVIDER")
    opensearch_endpoint: str = Field(default="", alias="OPENSEARCH_ENDPOINT")
    opensearch_username: str = Field(default="", alias="OPENSEARCH_USERNAME")
    opensearch_password: str = Field(default="", alias="OPENSEARCH_PASSWORD")
    opensearch_verify_tls: bool = Field(default=False, alias="OPENSEARCH_VERIFY_TLS")
    opensearch_timeout_seconds: int = Field(default=10, alias="OPENSEARCH_TIMEOUT_SECONDS")
    shard_search_min_gb: float = Field(default=10.0, alias="SHARD_SEARCH_MIN_GB")
    shard_search_max_gb: float = Field(default=30.0, alias="SHARD_SEARCH_MAX_GB")
    shard_general_max_gb: float = Field(default=50.0, alias="SHARD_GENERAL_MAX_GB")
    max_shards_per_gb_heap: float = Field(default=25.0, alias="MAX_SHARDS_PER_GB_HEAP")
    max_storage_skew_ratio: float = Field(default=1.5, alias="MAX_STORAGE_SKEW_RATIO")
    max_shard_skew_ratio: float = Field(default=1.5, alias="MAX_SHARD_SKEW_RATIO")

    huaweicloud_region: str = Field(default="", alias="HUAWEICLOUD_REGION")
    huaweicloud_project_id: str = Field(default="", alias="HUAWEICLOUD_PROJECT_ID")
    huaweicloud_sdk_ak: str = Field(default="", alias="HUAWEICLOUD_SDK_AK")
    huaweicloud_sdk_sk: str = Field(default="", alias="HUAWEICLOUD_SDK_SK")
    huaweicloud_iam_endpoint: str = Field(default="https://iam.myhuaweicloud.com", alias="HUAWEICLOUD_IAM_ENDPOINT")
    huaweicloud_css_endpoint: str = Field(default="", alias="HUAWEICLOUD_CSS_ENDPOINT")
    huaweicloud_ces_endpoint: str = Field(default="", alias="HUAWEICLOUD_CES_ENDPOINT")
    css_node_type: str = Field(default="ess", alias="CSS_NODE_TYPE")
    css_verify_timeout_seconds: int = Field(default=900, alias="CSS_VERIFY_TIMEOUT_SECONDS")
    css_verify_poll_interval_seconds: int = Field(default=30, alias="CSS_VERIFY_POLL_INTERVAL_SECONDS")
    css_blocking_verification: bool = Field(default=False, alias="CSS_BLOCKING_VERIFICATION")
    css_count_scale_timeout_minutes: int = Field(default=30, alias="CSS_COUNT_SCALE_TIMEOUT_MINUTES")
    css_flavor_change_timeout_minutes: int = Field(default=60, alias="CSS_FLAVOR_CHANGE_TIMEOUT_MINUTES")

    def ensure_dirs(self) -> None:
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        Path(self.sqlite_db_path).parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
