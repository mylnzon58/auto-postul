"""Logging estructurado y sin datos personales innecesarios."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

import structlog

from auto_postul.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configura structlog para consola y archivo local rotado por tamaño."""
    log_dir = settings.data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "auto_postul.log"

    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO if settings.app_env == "local" else logging.WARNING,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=2_000_000,
                backupCount=3,
                encoding="utf-8",
            ),
        ],
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def redact(value: str, keep: int = 4) -> str:
    """Redacta un secreto dejando solo una pista mínima."""
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return f"{'*' * (len(value) - keep)}{value[-keep:]}"


def ensure_directories(settings: Settings) -> None:
    """Crea los directorios de datos con permisos razonables."""
    for path in (settings.data_dir, settings.artifacts_dir, settings.documents_dir):
        path.mkdir(parents=True, exist_ok=True)
    _chmod_private(settings.data_dir)


def _chmod_private(path: Path) -> None:
    try:
        path.chmod(0o700)
    except OSError:
        # Windows no implementa los bits POSIX; no es un error funcional.
        return
