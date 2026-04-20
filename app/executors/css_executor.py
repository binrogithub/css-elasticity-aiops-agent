"""Huawei Cloud CSS executor scaffold."""

import logging
import time
from datetime import datetime, timezone
from typing import Any

from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkcore.http.http_config import HttpConfig
from huaweicloudsdkcss.v1 import (
    AddIndependentNodeRequest,
    CssClient,
    IndependentBodyReq,
    IndependentReq,
    ListFlavorsRequest,
    RoleExtendGrowReq,
    RoleExtendReq,
    ShowClusterDetailRequest,
    ShowResizeFlavorsRequest,
    ShrinkClusterReq,
    ShrinkNodeReq,
    UpdateFlavorByTypeReq,
    UpdateFlavorByTypeRequest,
    UpdateExtendInstanceStorageRequest,
    UpdateShrinkClusterRequest,
)
from huaweicloudsdkcss.v1.region.css_region import CssRegion

from app.config import Settings
from app.executors.base import ElasticityExecutor
from app.models.actions import ActionRequest, ActionResult, VerificationResult


class CSSExecutor(ElasticityExecutor):
    """Execute CSS client-node elasticity through Huawei Cloud CSS APIs."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.client = self._build_client()

    def current_nodes(self) -> int:
        state = self._get_cluster_runtime_state()
        return len(self._target_instances(state, self.settings.css_node_type))

    def current_topology(self) -> dict[str, Any]:
        state = self._get_cluster_runtime_state()
        node_types: dict[str, Any] = {}
        for node_type in ("ess", "ess-client", "ess-master"):
            instances = self._target_instances(state, node_type)
            spec_codes = sorted({item.get("spec_code", "") for item in instances if item.get("spec_code")})
            az_counts: dict[str, int] = {}
            for item in instances:
                az = item.get("az_code") or "unknown"
                az_counts[az] = az_counts.get(az, 0) + 1
            node_types[node_type] = {
                "count": len(instances),
                "stable_count": sum(1 for item in instances if item.get("status") == "200"),
                "spec_codes": spec_codes,
                "az_counts": az_counts,
                "instances": instances,
            }
        return {
            "cluster_id": state.get("cluster_id"),
            "cluster_name": state.get("name"),
            "cluster_status": state.get("status"),
            "node_types": node_types,
        }

    def available_flavors(self) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {"ess": [], "ess-client": [], "ess-master": []}
        try:
            response = self.client.show_resize_flavors(
                ShowResizeFlavorsRequest(cluster_id=self.settings.cluster_id)
            )
        except Exception as exc:
            self.logger.warning("css_resize_flavors_query_failed", extra={"error": str(exc)})
            response = None

        self._append_flavors_from_versions(grouped, getattr(response, "versions", []) or [])
        if not grouped["ess-client"] or not grouped["ess-master"]:
            try:
                all_flavors = self.client.list_flavors(ListFlavorsRequest())
                self._append_flavors_from_versions(grouped, getattr(all_flavors, "versions", []) or [])
            except Exception as exc:
                self.logger.warning("css_list_flavors_query_failed", extra={"error": str(exc)})
        return grouped

    def _append_flavors_from_versions(self, grouped: dict[str, list[dict[str, Any]]], versions: list[Any]) -> None:
        seen = {node_type: {item.get("id") for item in items} for node_type, items in grouped.items()}
        for version in versions:
            version_type = getattr(version, "type", None) or getattr(version, "name", None) or getattr(version, "id", None) or ""
            for flavor in getattr(version, "flavors", []) or []:
                typename = getattr(flavor, "typename", "") or getattr(flavor, "flavor_type_en", "") or version_type
                item = {
                    "id": getattr(flavor, "str_id", "") or getattr(flavor, "flavor_id", "") or getattr(flavor, "name", ""),
                    "name": getattr(flavor, "name", ""),
                    "cpu": getattr(flavor, "cpu", None),
                    "ram": getattr(flavor, "ram", None),
                    "typename": typename,
                    "diskrange": getattr(flavor, "diskrange", ""),
                }
                target = self._normalize_flavor_node_type(typename)
                if target in grouped and item["id"] and item["id"] not in seen[target]:
                    grouped[target].append(item)
                    seen[target].add(item["id"])

    def execute(self, request: ActionRequest) -> ActionResult:
        started_at = datetime.now(timezone.utc)
        node_type = request.node_type or self.settings.css_node_type
        previous_count = len(self._target_instances(self._get_cluster_runtime_state(), node_type))
        applied_delta = max(0, request.delta)

        if request.action == "hold" or (applied_delta <= 0 and request.action != "change_flavor"):
            return ActionResult(
                action_id=request.action_id,
                requested_action=request.action,
                executed_action="hold",
                node_type=request.node_type,
                requested_delta=request.delta,
                applied_delta=0,
                previous_node_count=previous_count,
                new_node_count=previous_count,
                status="skipped",
                phase="validated",
                message="No CSS scaling action required or allowed by node boundaries.",
                expected_duration_minutes=request.expected_duration_minutes,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        if not self.settings.css_mutation_enabled:
            return ActionResult(
                action_id=request.action_id,
                requested_action=request.action,
                executed_action="hold",
                node_type=request.node_type,
                requested_delta=request.delta,
                applied_delta=0,
                previous_node_count=previous_count,
                new_node_count=previous_count,
                previous_flavor_id=self._current_flavor_id(node_type),
                new_flavor_id=request.target_flavor_id,
                status="skipped",
                phase="blocked",
                message="CSS mutation is disabled by CSS_MUTATION_ENABLED=false.",
                expected_duration_minutes=request.expected_duration_minutes,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        try:
            if request.action == "scale_out":
                self._scale_out(node_type, applied_delta, request.target_flavor_id)
                new_count = previous_count + applied_delta
            elif request.action == "scale_in":
                self._scale_in(node_type, applied_delta)
                new_count = previous_count - applied_delta
            elif request.action == "change_flavor":
                previous_flavor = self._current_flavor_id(node_type)
                self._change_flavor(node_type, request.target_flavor_id or "")
                return ActionResult(
                    action_id=request.action_id,
                    requested_action=request.action,
                    executed_action=request.action,
                    node_type=node_type,
                    requested_delta=0,
                    applied_delta=0,
                    previous_node_count=previous_count,
                    new_node_count=previous_count,
                    previous_flavor_id=previous_flavor,
                    new_flavor_id=request.target_flavor_id,
                    status="success",
                    phase="submitted",
                    message="CSS flavor change request submitted.",
                    expected_duration_minutes=request.expected_duration_minutes,
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                )
            else:
                new_count = previous_count

            return ActionResult(
                action_id=request.action_id,
                requested_action=request.action,
                executed_action=request.action,
                node_type=node_type,
                requested_delta=request.delta,
                applied_delta=applied_delta,
                previous_node_count=previous_count,
                new_node_count=new_count,
                status="success",
                phase="submitted",
                message="CSS scaling request submitted.",
                expected_duration_minutes=request.expected_duration_minutes,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
        except exceptions.ClientRequestException as exc:
            message = f"CSS API request failed: {exc.status_code} {exc.error_code} {exc.error_msg}"
            if "CSS.5042" in str(exc.error_msg) and node_type == "ess-client":
                message = (
                    f"{message}. CSS returned CSS.5042 while scaling ess-client. "
                    "This usually means the cluster has no existing Client node to clone; "
                    "create the first Client node through a supported CSS path before using role-based Client scaling."
                )
            self.logger.error("css_scaling_failed", extra={"status_code": exc.status_code, "error_code": exc.error_code})
        except Exception as exc:
            message = f"CSS scaling failed: {exc}"
            self.logger.error("css_scaling_failed", extra={"error": str(exc)})

        return ActionResult(
            action_id=request.action_id,
            requested_action=request.action,
            executed_action="hold",
            node_type=request.node_type,
            requested_delta=request.delta,
            applied_delta=0,
            previous_node_count=previous_count,
            new_node_count=previous_count,
            status="failed",
            phase="verified_failed",
            message=message,
            expected_duration_minutes=request.expected_duration_minutes,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
        )

    def verify(self, result: ActionResult, wait: bool = False) -> VerificationResult:
        if result.status == "skipped":
            return VerificationResult(
                success=True,
                status="success",
                message=result.message,
                observed_node_count=result.new_node_count,
                expected_node_count=result.new_node_count,
                node_type=result.node_type or self.settings.css_node_type,
            )
        if result.status == "failed":
            return VerificationResult(
                success=False,
                status="failed",
                message=result.message,
                observed_node_count=result.previous_node_count,
                expected_node_count=result.new_node_count,
                node_type=result.node_type or self.settings.css_node_type,
            )

        expected = result.new_node_count
        if not wait and not self.settings.css_blocking_verification:
            return self._verify_once(result)

        deadline = time.monotonic() + max(0, self.settings.css_verify_timeout_seconds)
        while True:
            verification = self._verify_once(result)
            self.logger.info(
                "css_verification_poll",
                extra=verification.model_dump(mode="json"),
            )
            if verification.status == "success":
                return verification
            if time.monotonic() >= deadline:
                break
            time.sleep(max(1, self.settings.css_verify_poll_interval_seconds))

        verification = self._verify_once(result)
        return verification.model_copy(
            update={
                "success": False,
                "status": "failed",
                "message": (
                    "CSS node count did not reach a stable target before timeout: "
                    f"observed={verification.observed_node_count}, expected={result.new_node_count}."
                ),
                "verified_at": datetime.now(timezone.utc),
            }
        )

    def _build_client(self) -> CssClient:
        credentials = BasicCredentials(
            ak=self.settings.huaweicloud_sdk_ak,
            sk=self.settings.huaweicloud_sdk_sk,
            project_id=self.settings.huaweicloud_project_id or None,
        )
        if self.settings.huaweicloud_iam_endpoint:
            credentials = credentials.with_iam_endpoint(self.settings.huaweicloud_iam_endpoint)

        http_config = HttpConfig.get_default_config()
        http_config.timeout = (30, 60)
        builder = CssClient.new_builder().with_http_config(http_config).with_credentials(credentials)
        if self.settings.huaweicloud_css_endpoint:
            builder = builder.with_endpoint(self.settings.huaweicloud_css_endpoint)
        else:
            builder = builder.with_region(CssRegion.value_of(self.settings.huaweicloud_region))
        return builder.build()

    def _get_cluster_runtime_state(self) -> dict[str, Any]:
        request = ShowClusterDetailRequest(cluster_id=self.settings.cluster_id)
        response = self.client.show_cluster_detail(request)
        if not response or not getattr(response, "id", None):
            raise RuntimeError(f"CSS cluster is not accessible: {self.settings.cluster_id}")

        instances = []
        for instance in getattr(response, "instances", []) or []:
            volume = getattr(instance, "volume", None)
            instances.append(
                {
                    "id": getattr(instance, "id", ""),
                    "name": getattr(instance, "name", ""),
                    "type": getattr(instance, "type", ""),
                    "status": getattr(instance, "status", ""),
                    "ip": getattr(instance, "ip", ""),
                    "spec_code": getattr(instance, "spec_code", ""),
                    "az_code": getattr(instance, "az_code", ""),
                    "volume": {
                        "type": getattr(volume, "type", ""),
                        "size": getattr(volume, "size", None),
                        "resource_ids": getattr(volume, "resource_ids", None),
                    }
                    if volume
                    else None,
                }
            )

        return {
            "cluster_id": getattr(response, "id", self.settings.cluster_id),
            "name": getattr(response, "name", ""),
            "status": getattr(response, "status", ""),
            "instances": instances,
        }

    def _target_instances(self, state: dict[str, Any], node_type: str) -> list[dict[str, Any]]:
        return [
            instance
            for instance in state.get("instances", [])
            if instance.get("type") == node_type
        ]

    def _verify_once(self, result: ActionResult) -> VerificationResult:
        state = self._get_cluster_runtime_state()
        node_type = result.node_type or self.settings.css_node_type
        instances = self._target_instances(state, node_type)
        observed = len(instances)
        target_stable = state.get("status") == "200" and all(
            instance.get("status") == "200" for instance in instances
        )
        flavor_ok = (
            result.executed_action != "change_flavor"
            or not result.new_flavor_id
            or all(instance.get("spec_code") == result.new_flavor_id for instance in instances)
        )
        success = observed == result.new_node_count and target_stable and flavor_ok
        status = "success" if success else "pending"
        message = (
            "CSS node count matches submitted scaling target and target nodes are stable."
            if success
            else f"CSS operation still pending: observed={observed}, expected={result.new_node_count}, cluster_status={state.get('status')}."
        )
        return VerificationResult(
            success=success,
            status=status,
            message=message,
            observed_node_count=observed,
            expected_node_count=result.new_node_count,
            cluster_status=str(state.get("status", "")),
            node_type=node_type,
            observed_instances=instances,
        )

    def _bounded_delta(
        self,
        action: str,
        requested_delta: int,
        current_nodes: int,
        min_nodes: int,
        max_nodes: int,
    ) -> int:
        requested = max(0, int(requested_delta))
        if action == "scale_out":
            return min(requested, max(0, max_nodes - current_nodes))
        if action == "scale_in":
            allowed = max(0, current_nodes - min_nodes)
            if self.settings.css_node_type == "ess":
                allowed = min(allowed, self._max_data_nodes_removable(current_nodes))
            return min(requested, allowed)
        return 0

    def _max_data_nodes_removable(self, current_nodes: int) -> int:
        """CSS rejects normal data-node shrink batches that remove half or more of data nodes."""
        return max(0, ((current_nodes - 1) // 2))

    def _scale_out(self, node_type: str, delta: int, target_flavor_id: str | None = None) -> None:
        current = len(self._target_instances(self._get_cluster_runtime_state(), node_type))
        if current == 0 and node_type in {"ess-client", "ess-master"} and self.settings.css_allow_add_independent_nodes:
            self._add_independent_node(node_type, delta, target_flavor_id)
            return

        grow_req = RoleExtendGrowReq(
            type=node_type,
            nodesize=delta,
            disksize=0 if node_type in {"ess-client", "ess-master"} else 0,
        )
        body = RoleExtendReq(
            grow=[grow_req],
            is_auto_pay=1,
        )
        request = UpdateExtendInstanceStorageRequest(
            cluster_id=self.settings.cluster_id,
            body=body,
        )
        self.client.update_extend_instance_storage(request)

    def _scale_in(self, node_type: str, delta: int) -> None:
        shrink_node = ShrinkNodeReq(
            type=node_type,
            reduced_node_num=delta,
        )
        body = ShrinkClusterReq(
            shrink=[shrink_node],
            agency_name="",
            operation_type="",
            cluster_load_check=True,
        )
        request = UpdateShrinkClusterRequest(
            cluster_id=self.settings.cluster_id,
            body=body,
        )
        self.client.update_shrink_cluster(request)

    def _add_independent_node(self, node_type: str, delta: int, target_flavor_id: str | None = None) -> None:
        flavor_ref = target_flavor_id or self._default_flavor_for_new_node(node_type)
        body_req = IndependentBodyReq(
            flavor_ref=flavor_ref,
            node_size=delta,
            volume_type=self.settings.css_default_volume_type,
            volume_size=(
                self.settings.css_default_master_volume_size
                if node_type == "ess-master"
                else self.settings.css_default_client_volume_size
            ),
        )
        body = IndependentReq(type=body_req, is_auto_pay=1)
        request = AddIndependentNodeRequest(cluster_id=self.settings.cluster_id, type=node_type, body=body)
        self.client.add_independent_node(request)

    def _change_flavor(self, node_type: str, flavor_id: str) -> None:
        body = UpdateFlavorByTypeReq(
            new_flavor_id=flavor_id,
            operation_type="",
            need_check_replica=True,
            is_auto_pay=1,
            need_check_cluster_status=True,
            cluster_load_check=True,
        )
        request = UpdateFlavorByTypeRequest(cluster_id=self.settings.cluster_id, types=node_type, body=body)
        self.client.update_flavor_by_type(request)

    def _current_flavor_id(self, node_type: str) -> str | None:
        instances = self._target_instances(self._get_cluster_runtime_state(), node_type)
        return instances[0].get("spec_code") if instances else None

    def _default_flavor_for_new_node(self, node_type: str) -> str:
        flavors = self.available_flavors().get(node_type, [])
        if flavors:
            return str(flavors[0].get("id") or flavors[0].get("name"))
        existing = self._current_flavor_id("ess")
        if existing:
            return existing
        raise RuntimeError(f"No flavor available to add independent node type {node_type}")

    def _normalize_flavor_node_type(self, raw: str) -> str:
        text = raw.lower()
        if "client" in text:
            return "ess-client"
        if "master" in text:
            return "ess-master"
        return "ess"
