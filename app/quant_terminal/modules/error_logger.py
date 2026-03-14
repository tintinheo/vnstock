"""
Centralized error / exception logging.
All modules share a single root logger that writes to ERROR_LOG.txt.

Usage
-----
In app.py (once at startup):

    from modules.error_logger import setup_file_logging
    setup_file_logging()

Any module can then use:

    import logging
    _log = logging.getLogger("my_module")
    _log.error("something went wrong: %s", exc)
"""
import logging
from pathlib import Path

from config import ERROR_LOG_FILE


def setup_file_logging(level: int = logging.WARNING) -> None:
    """
    Attach a rotating FileHandler to the root logger so that all WARNING /
    ERROR / CRITICAL messages across every module are written to ERROR_LOG.txt.

    Idempotent: safe to call multiple times (Streamlit re-runs).
    """
    root = logging.getLogger()

    # Guard against duplicate handlers on Streamlit re-runs
    for handler in root.handlers:
        if isinstance(handler, logging.FileHandler):
            if Path(handler.baseFilename).resolve() == Path(ERROR_LOG_FILE).resolve():
                return

    # Ensure parent directory exists
    Path(ERROR_LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

    fh = logging.FileHandler(ERROR_LOG_FILE, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(fh)

    # Raise root level only if it is currently more permissive than our handler
    if root.level == logging.NOTSET or root.level > level:
        root.setLevel(level)
