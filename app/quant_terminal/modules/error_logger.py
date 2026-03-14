"""Error logger — sets up rotating file logging for the app."""
import logging
import logging.handlers


def setup_file_logging():
    """Attach a rotating file handler to the root logger (idempotent)."""
    try:
        from config import ERROR_LOG_FILE
    except ImportError:
        return

    root = logging.getLogger()
    # Idempotent: don't add duplicate handlers on Streamlit re-runs
    if any(isinstance(h, logging.FileHandler) for h in root.handlers):
        return
    try:
        fh = logging.handlers.RotatingFileHandler(
            ERROR_LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        fh.setLevel(logging.WARNING)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
        ))
        root.addHandler(fh)
        if root.level == logging.NOTSET:
            root.setLevel(logging.WARNING)
    except Exception:
        pass  # silently fail if log file is not writable
