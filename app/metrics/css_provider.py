"""Huawei Cloud CSS/CES metrics provider."""

import logging
from datetime import datetime, timezone

from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkcore.http.http_config import HttpConfig
from huaweicloudsdkces.v1 import CesClient, ShowMetricDataRequest
from huaweicloudsdkces.v1.region.ces_region import CesRegion

from app.config import Settings
from app.metrics.base import MetricsProvider
from app.models.metrics import MetricsSnapshot


class CSSMetricsProvider(MetricsProvider):
    """Collect CSS metrics from Cloud Eye."""

    NAMESPACE = "SYS.ES"
    METRIC_NAME_MAP = {
        "cpu_avg": "avg_cpu_usage",
        "jvm_heap_avg": "avg_jvm_heap_usage",
        "search_latency_avg_ms": "SearchLatency",
        "qps_avg": "SearchRate",
        "search_queue": "avg_thread_pool_search_queue",
        "search_rejected": "sum_thread_pool_search_rejected",
        "disk_usage_pct": "avg_disk_usage",
    }

    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.client = self._build_client()

    def _build_client(self) -> CesClient:
        credentials = BasicCredentials(
            ak=self.settings.huaweicloud_sdk_ak,
            sk=self.settings.huaweicloud_sdk_sk,
            project_id=self.settings.huaweicloud_project_id or None,
        )
        if self.settings.huaweicloud_iam_endpoint:
            credentials = credentials.with_iam_endpoint(self.settings.huaweicloud_iam_endpoint)

        http_config = HttpConfig.get_default_config()
        http_config.timeout = (30, 60)
        builder = CesClient.new_builder().with_http_config(http_config).with_credentials(credentials)
        if self.settings.huaweicloud_ces_endpoint:
            builder = builder.with_endpoint(self.settings.huaweicloud_ces_endpoint)
        else:
            builder = builder.with_region(CesRegion.value_of(self.settings.huaweicloud_region))
        return builder.build()

    def _query_metric(self, cluster_id: str, metric_name: str, period: int = 60) -> float:
        now = int(datetime.now(timezone.utc).timestamp() * 1000)
        request = ShowMetricDataRequest(
            namespace=self.NAMESPACE,
            metric_name=metric_name,
            dim_0=f"cluster_id,{cluster_id}",
            _from=now - (30 * 60 * 1000),
            to=now,
            period=period,
            filter="average",
        )
        try:
            response = self.client.show_metric_data(request)
            datapoints = sorted(response.datapoints or [], key=lambda item: item.timestamp or 0, reverse=True)
            for point in datapoints:
                if point.average is not None:
                    return float(point.average)
        except exceptions.ClientRequestException as exc:
            self.logger.warning(
                "cloud_eye_metric_query_failed",
                extra={
                    "metric_name": metric_name,
                    "status_code": exc.status_code,
                    "error_code": exc.error_code,
                    "error_msg": exc.error_msg,
                },
            )
        except Exception as exc:
            self.logger.warning(
                "cloud_eye_metric_query_failed",
                extra={"metric_name": metric_name, "error": str(exc)},
            )
        return 0.0

    def collect(self, cluster_id: str) -> MetricsSnapshot:
        return MetricsSnapshot(
            cluster_health="unknown",
            cpu_avg=self._query_metric(cluster_id, self.METRIC_NAME_MAP["cpu_avg"]),
            jvm_heap_avg=self._query_metric(cluster_id, self.METRIC_NAME_MAP["jvm_heap_avg"]),
            search_latency_avg_ms=self._query_metric(
                cluster_id, self.METRIC_NAME_MAP["search_latency_avg_ms"]
            ),
            qps_avg=self._query_metric(cluster_id, self.METRIC_NAME_MAP["qps_avg"]),
            search_queue=int(self._query_metric(cluster_id, self.METRIC_NAME_MAP["search_queue"])),
            search_rejected=int(self._query_metric(cluster_id, self.METRIC_NAME_MAP["search_rejected"])),
            disk_usage_pct=self._query_metric(cluster_id, self.METRIC_NAME_MAP["disk_usage_pct"]),
        )
