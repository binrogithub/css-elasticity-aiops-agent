"""Structured logging setup."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pythonjsonlogger import jsonlogger

from app.config import Settings


def setup_logging(settings: Settings) -> logging.Logger:
    logger = logging.getLogger("css_elasticity_aiops")
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    logger.handlers = []

    console = logging.StreamHandler()
    console.setLevel(logger.level)
    if settings.json_logs:
        formatter = jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    console.setFormatter(formatter)
    logger.addHandler(console)

    log_file = Path(settings.log_dir) / "agent.log"
    file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
    file_handler.setLevel(logger.level)
    file_handler.setFormatter(jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(file_handler)
    return logger
