"""Logging: rotated file log in ~/.aloth/logs/aloth.log + two-level user errors.

Stack traces go to the log file only — never to the UI. The UI gets a
human phrase with an action; in "advanced" mode the same phrase plus a
technical line and the log path.
"""

from __future__ import annotations

import logging
import logging.handlers
import tempfile
from pathlib import Path

from aloth.home import home_dir

LOG_NAME = "aloth"
LOG_FILE = "aloth.log"
_MAX_BYTES = 1024 * 1024  # 1 MB
_BACKUPS = 5

_FORMAT = "%(asctime)s %(levelname)-7s %(module)s: %(message)s"


def setup_logging(home: Path) -> logging.Logger:
    """Configure the 'aloth' logger with a 1 MB × 5 rotating file handler.

    Idempotent: returns the existing logger if already configured.
    """
    logger = logging.getLogger(LOG_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    (home / "logs").mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        home / "logs" / LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUPS,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(handler)
    return logger


def user_error(ui_level: str, msg_simple: str, technical: str = "") -> str:
    """Present an error: 'simple' = human phrase (+ action); 'advanced' = same + technical.

    The technical detail is always written to the log file (if logging is
    set up) and only shown in the UI when ui_level == "advanced".
    """
    if technical:
        logger = logging.getLogger(LOG_NAME)
        if logger.handlers:
            logger.error("%s | %s", msg_simple, technical)
    if ui_level != "advanced":
        return msg_simple
    out = [msg_simple]
    if technical:
        out.append(f"Технически: {technical}")
    out.append(f"Подробности в логе: {home_dir() / 'logs' / LOG_FILE}")
    return "\n".join(out)


if __name__ == "__main__":  # pragma: no cover — runnable self-check
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        logger = setup_logging(home)
        logger.info("self-check line 1")
        logger.exception("self-check with stack")

        log_file = home / "logs" / LOG_FILE
        assert log_file.exists(), "log file missing"
        text = log_file.read_text(encoding="utf-8")
        assert "self-check line 1" in text, "info line not in log"
        assert "self-check with stack" in text, "stack line not in log"

        handler = logger.handlers[0]
        assert isinstance(handler, logging.handlers.RotatingFileHandler)
        assert handler.maxBytes == _MAX_BYTES, "rotation size != 1 MB"
        assert handler.backupCount == _BACKUPS, "backup count != 5"

        assert user_error("simple", "фраза", "tech") == "фраза"
        advanced = user_error("advanced", "фраза", "tech")
        assert "Технически: tech" in advanced and "aloth.log" in advanced
        logging.shutdown()  # close the handler so Windows can delete the tempdir
    print("logging ok")
