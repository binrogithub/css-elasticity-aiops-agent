"""Mock CSS executor."""

from datetime import datetime, timezone

from app.executors.base import ElasticityExecutor
from app.models.actions import ActionRequest, ActionResult, VerificationResult


class MockCSSExecutor(ElasticityExecutor):
    def __init__(self, initial_nodes: int):
        self._nodes = {"ess": initial_nodes, "ess-client": 0, "ess-master": 0}
        self._flavors = {"ess": "mock.data", "ess-client": "mock.client", "ess-master": "mock.master"}

    def current_nodes(self) -> int:
        return self._nodes["ess"]

    def current_topology(self) -> dict:
        return {
            "cluster_status": "200",
            "node_types": {
                node_type: {
                    "count": count,
                    "stable_count": count,
                    "spec_codes": [self._flavors[node_type]] if count else [],
                    "instances": [
                        {"id": f"{node_type}-{idx}", "name": f"{node_type}-{idx}", "type": node_type, "status": "200"}
                        for idx in range(count)
                    ],
                }
                for node_type, count in self._nodes.items()
            },
        }

    def available_flavors(self) -> dict:
        return {
            "ess": [{"id": "mock.data.large", "name": "mock.data.large"}],
            "ess-client": [{"id": "mock.client.large", "name": "mock.client.large"}],
            "ess-master": [{"id": "mock.master.large", "name": "mock.master.large"}],
        }

    def execute(self, request: ActionRequest) -> ActionResult:
        started = datetime.now(timezone.utc)
        node_type = request.node_type or "ess"
        previous = self._nodes.get(node_type, 0)
        if request.action == "hold" or (request.delta == 0 and request.action != "change_flavor"):
            return ActionResult(
                action_id=request.action_id,
                requested_action=request.action,
                executed_action="hold",
                node_type=request.node_type,
                requested_delta=request.delta,
                previous_node_count=previous,
                new_node_count=previous,
                status="skipped",
                phase="validated",
                message="No scaling action requested",
                started_at=started,
            )

        if request.action == "scale_out":
            new_count = previous + request.delta
        elif request.action == "scale_in":
            new_count = max(0, previous - request.delta)
        else:
            old_flavor = self._flavors.get(node_type)
            self._flavors[node_type] = request.target_flavor_id or old_flavor
            return ActionResult(
                action_id=request.action_id,
                requested_action=request.action,
                executed_action=request.action,
                node_type=node_type,
                previous_node_count=previous,
                new_node_count=previous,
                previous_flavor_id=old_flavor,
                new_flavor_id=self._flavors[node_type],
                status="success",
                phase="submitted",
                message="Mock flavor change completed",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )

        applied = abs(new_count - previous)
        self._nodes[node_type] = new_count
        return ActionResult(
            action_id=request.action_id,
            requested_action=request.action,
            executed_action=request.action if applied else "hold",
            node_type=node_type,
            requested_delta=request.delta,
            applied_delta=applied,
            previous_node_count=previous,
            new_node_count=new_count,
            status="success" if applied else "skipped",
            phase="submitted" if applied else "validated",
            message="Mock execution completed" if applied else "Action clamped by node boundaries",
            started_at=started,
            finished_at=datetime.now(timezone.utc),
        )

    def verify(self, result: ActionResult, wait: bool = False) -> VerificationResult:
        node_type = result.node_type or "ess"
        observed = self._nodes.get(node_type, 0)
        return VerificationResult(
            success=observed == result.new_node_count,
            status="success" if observed == result.new_node_count else "pending",
            message="Mock verification completed",
            observed_node_count=observed,
            expected_node_count=result.new_node_count,
            node_type=node_type,
        )
