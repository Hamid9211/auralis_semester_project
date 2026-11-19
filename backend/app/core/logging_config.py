"""Structured logging setup shared by all modules."""

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    """Configure the root logger once; repeated calls are harmless."""
    logging.basicConfig(level=level, format=LOG_FORMAT)


def get_logger(name: str) -> logging.Logger:
    """Return a module logger under the 'auralis' namespace."""
    return logging.getLogger(f"auralis.{name}")
