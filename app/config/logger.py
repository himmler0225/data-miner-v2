"""
Centralized logger.

Usage:
    from app.config.logger import Logger
    logger = Logger.get(__name__)

Setup (once, in main.py):
    Logger.setup(level="INFO")
"""
import logging
import logging.handlers
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

_RESET   = "\033[0m"
_BOLD    = "\033[1m"
_DIM     = "\033[2m"
_BLUE    = "\033[34m"

_LEVEL_COLOR = {
    "DEBUG":    "\033[36m",
    "INFO":     "\033[32m",
    "WARNING":  "\033[33m",
    "ERROR":    "\033[31m",
    "CRITICAL": "\033[35m\033[1m",
}

class _ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts    = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        color = _LEVEL_COLOR.get(record.levelname, "\033[37m")

        parts     = record.name.split(".")
        short     = ".".join(parts[-2:]) if len(parts) >= 2 else record.name
        msg       = record.getMessage()
        if record.levelno >= logging.WARNING:
            msg = f"{color}{msg}{_RESET}"

        return (
            f"{_DIM}{ts}{_RESET}  "
            f"{color}{_BOLD}{record.levelname:<8}{_RESET}  "
            f"{_BLUE}{short}{_RESET}  "
            f"{msg}"
        )

class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
            "module":    record.module,
            "function":  record.funcName,
            "line":      record.lineno,
        }
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_data"):
            data["extra"] = record.extra_data
        return json.dumps(data, ensure_ascii=False)

class Logger:

    _root:       str  = "data_miner"
    _configured: bool = False

    @classmethod
    def setup(
        cls,
        level:        str = "INFO",
        log_dir:      str = "logs",
        max_bytes:    int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ) -> None:
        if cls._configured:
            return

        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)

        root = logging.getLogger(cls._root)
        root.setLevel(getattr(logging, level.upper(), logging.INFO))
        root.handlers.clear()
        root.propagate = False

        # Console — colored
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        console.setFormatter(_ColorFormatter())
        root.addHandler(console)

        # app.log — JSON, rotating
        app_file = logging.handlers.RotatingFileHandler(
            log_path / "app.log",
            maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8",
        )
        app_file.setLevel(logging.DEBUG)
        app_file.setFormatter(_JSONFormatter())
        root.addHandler(app_file)

        # error.log — errors only
        err_file = logging.handlers.RotatingFileHandler(
            log_path / "error.log",
            maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8",
        )
        err_file.setLevel(logging.ERROR)
        err_file.setFormatter(_JSONFormatter())
        root.addHandler(err_file)

        cls._configured = True

    @classmethod
    def get(cls, name: str) -> logging.Logger:
        """
        Return the child logger for a module.
        Strips 'app.' prefix from __name__ to keep logger names clean:
          app.api.tiktok  →  data_miner.api.tiktok
        """
        short = name.removeprefix("app.")
        return logging.getLogger(f"{cls._root}.{short}")
