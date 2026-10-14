"""
EcoPackAI - Structured Logging
Module: Flask Backend - Observability

Applies config/logging.yaml. Every log line is a single JSON object, so logs
can be searched and filtered by any field (request_id, event, status, ...).

Loggers
    ecopackai            application events      -> console + logs/app.log
    ecopackai.access     one line per request    -> console + logs/app.log
    ecopackai.security   auth/security events    -> console + logs/security.log
"""

import json
import logging
import logging.config
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LOGGING_CONFIG = ROOT / "config" / "logging.yaml"

app_log = logging.getLogger("ecopackai")
access_log = logging.getLogger("ecopackai.access")
security_log = logging.getLogger("ecopackai.security")

# Attributes every LogRecord has; anything else was passed via extra={...}
_STANDARD = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime", "request_id"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        entry.update({k: v for k, v in vars(record).items() if k not in _STANDARD})
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str, ensure_ascii=False)


class RequestContextFilter(logging.Filter):
    """Adds the current request's ID to every log line written while handling it."""

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "request_id", None) is None:
            try:
                from flask import g, has_request_context
                record.request_id = g.get("request_id") if has_request_context() else None
            except ImportError:
                record.request_id = None
        return True


def setup_logging(log_dir: str, level: str = "INFO") -> None:
    """Load config/logging.yaml with the log folder and level filled in."""
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    text = LOGGING_CONFIG.read_text(encoding="utf-8")
    text = text.replace("{LOG_DIR}", Path(log_dir).as_posix()).replace("{LOG_LEVEL}", level)
    for logger in (app_log, security_log):      # close files of a previous configuration
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)
    logging.config.dictConfig(yaml.safe_load(text))
