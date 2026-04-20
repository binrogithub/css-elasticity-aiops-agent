"""Runtime dependency container."""

from dataclasses import dataclass
import sqlite3

from app.ai_client import AIClient
from app.config import Settings
from app.diagnostics.base import DiagnosticsProvider
from app.executors.base import ElasticityExecutor
from app.metrics.base import MetricsProvider
from app.repositories.actions_repo import ActionsRepository
from app.repositories.decisions_repo import DecisionsRepository
from app.repositories.metrics_repo import MetricsRepository
from app.repositories.state_repo import StateRepository


@dataclass
class Runtime:
    settings: Settings
    metrics_provider: MetricsProvider
    diagnostics_provider: DiagnosticsProvider
    executor: ElasticityExecutor
    ai_client: AIClient
    conn: sqlite3.Connection
    metrics_repo: MetricsRepository
    decisions_repo: DecisionsRepository
    actions_repo: ActionsRepository
    state_repo: StateRepository
