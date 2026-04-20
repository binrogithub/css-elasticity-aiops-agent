"""Elasticity executor interface."""

from abc import ABC, abstractmethod

from app.models.actions import ActionRequest, ActionResult, VerificationResult


class ElasticityExecutor(ABC):
    def current_topology(self) -> dict:
        """Return cluster topology by node type."""
        return {}

    def available_flavors(self) -> dict:
        """Return available resize flavors by node type."""
        return {}

    @abstractmethod
    def current_nodes(self) -> int:
        """Return current default node count."""

    @abstractmethod
    def execute(self, request: ActionRequest) -> ActionResult:
        """Execute an elasticity action."""

    @abstractmethod
    def verify(self, result: ActionResult, wait: bool = False) -> VerificationResult:
        """Verify execution result."""
