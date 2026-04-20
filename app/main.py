"""CLI entrypoint."""

import argparse

from app.ai_client import AIClient
from app.config import get_settings
from app.db import connect, init_db
from app.diagnostics.base import DisabledDiagnosticsProvider
from app.diagnostics.opensearch_provider import OpenSearchDiagnosticsProvider
from app.executors.css_executor import CSSExecutor
from app.executors.mock_css_executor import MockCSSExecutor
from app.logging_utils import setup_logging
from app.metrics.css_provider import CSSMetricsProvider
from app.metrics.mock_provider import MockMetricsProvider
from app.repositories.actions_repo import ActionsRepository
from app.repositories.decisions_repo import DecisionsRepository
from app.repositories.metrics_repo import MetricsRepository
from app.repositories.state_repo import StateRepository
from app.runtime import Runtime
from app.scheduler import Scheduler


def build_runtime() -> Runtime:
    settings = get_settings()
    logger = setup_logging(settings)
    init_db(settings.sqlite_db_path)
    conn = connect(settings.sqlite_db_path)
    metrics_provider = CSSMetricsProvider(settings) if settings.metrics_provider == "css" else MockMetricsProvider()
    diagnostics_provider = (
        OpenSearchDiagnosticsProvider(settings)
        if settings.diagnostics_provider == "opensearch"
        else DisabledDiagnosticsProvider()
    )
    executor = CSSExecutor(settings) if settings.executor_provider == "css" else MockCSSExecutor(settings.initial_nodes)
    runtime = Runtime(
        settings=settings,
        metrics_provider=metrics_provider,
        diagnostics_provider=diagnostics_provider,
        executor=executor,
        ai_client=AIClient(settings),
        conn=conn,
        metrics_repo=MetricsRepository(conn),
        decisions_repo=DecisionsRepository(conn),
        actions_repo=ActionsRepository(conn),
        state_repo=StateRepository(conn),
    )
    logger.info("Runtime initialized")
    return runtime


def main() -> int:
    parser = argparse.ArgumentParser(description="CSS Elasticity AIOps Agent")
    parser.add_argument("--once", action="store_true", help="Run a single workflow cycle")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    args = parser.parse_args()

    if args.once == args.loop:
        parser.error("choose exactly one of --once or --loop")

    runtime = build_runtime()
    scheduler = Scheduler(runtime)
    if args.once:
        state = scheduler.run_once(trigger_type="manual")
        print(state.model_dump_json(indent=2))
    else:
        scheduler.run_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
