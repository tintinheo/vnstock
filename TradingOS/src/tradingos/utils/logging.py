"""Utility: structured logging for TradingOS."""
from __future__ import annotations

import io
import logging
import sys
from functools import lru_cache

_FMT = "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s"
_DATE_FMT = "%H:%M:%S"


def _utf8_stream() -> io.TextIOWrapper:
    """Return a UTF-8 stream for stdout — avoids charmap errors on Windows."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            return sys.stdout
    except Exception:
        pass
    return sys.stdout


@lru_cache(maxsize=None)
def get_logger(name: str = "tradingos") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(_utf8_stream())
        handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATE_FMT))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


log = get_logger("tradingos")
