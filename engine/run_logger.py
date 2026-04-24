import logging
from datetime import datetime, timezone
from pathlib import Path

_engine_logger: logging.Logger | None = None


def setup(run_id: str) -> logging.Logger:
    """Configure file logging for a run. Call once from cli.py before the loop starts."""
    global _engine_logger
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    log_file = logs_dir / f"engine_{run_id}.log"
    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)-40s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(fmt)

    logger = logging.getLogger("engine")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.propagate = False

    _engine_logger = logger
    logger.info("Run started. Log file: %s", log_file)
    return logger


def get() -> logging.Logger:
    if _engine_logger is not None:
        return _engine_logger
    return logging.getLogger("engine")
