"""结构化日志与 trace：每条查询可复现（命中、分数、耗时）。"""
from __future__ import annotations

import logging
import sys
import time
import uuid
from contextlib import contextmanager

LOGGER_NAME = "ragforge"

_configured = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    global _configured
    logger = logging.getLogger(LOGGER_NAME)
    if not _configured:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.setLevel(level)
        _configured = True
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def new_trace_id() -> str:
    return uuid.uuid4().hex[:12]


@contextmanager
def timer(label: str, logger: logging.Logger):
    """耗时计时器，用于观测（检索耗时/生成耗时）。"""
    start = time.monotonic()
    try:
        yield
    finally:
        cost_ms = (time.monotonic() - start) * 1000
        logger.info("[timer] %s=%.1fms", label, cost_ms)