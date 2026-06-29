import json
import logging
import logging.handlers
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_DIM = "\x1b[2m"
_BLUE = "\x1b[34m"
_LEVEL_COLOR = {
    "DEBUG": "\x1b[36m",
    "INFO": "\x1b[32m",
    "WARNING": "\x1b[33m",
    "ERROR": "\x1b[31m",
    "CRITICAL": "\x1b[35m\x1b[1m",
}

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\u2600-\u27BF"
    "\uFE0F"
    "]+",
    flags=re.UNICODE,
)


def _strip_emoji(text: str) -> str:
    return _EMOJI_RE.sub("", text).strip()


def _display_logger(name: str, root: str) -> str:
    prefix = f"{root}."
    if name.startswith(prefix):
        return name[len(prefix) :]
    if name.startswith("uvicorn"):
        return "server"
    return name


class _ColorFormatter(logging.Formatter):
    root_name: str = "data_miner"

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        color = _LEVEL_COLOR.get(record.levelname, "\x1b[37m")
        short = _display_logger(record.name, self.root_name)
        msg = _strip_emoji(record.getMessage())
        return (
            f"{_DIM}{ts}{_RESET}  "
            f"{color}{_BOLD}{record.levelname:<8}{_RESET}  "
            f"{_BLUE}{short:<24}{_RESET}  "
            f"{color}{msg}{_RESET}"
        )


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _strip_emoji(record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_data"):
            data["extra"] = record.extra_data
        return json.dumps(data, ensure_ascii=False)


class Logger:
    _root: str = "data_miner"
    _configured: bool = False

    @classmethod
    def setup(
        cls,
        level: str = "INFO",
        log_dir: str = "logs",
        max_bytes: int = 10 * 1024 * 1024,
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
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        formatter = _ColorFormatter()
        formatter.root_name = cls._root
        console.setFormatter(formatter)
        root.addHandler(console)
        app_file = logging.handlers.RotatingFileHandler(
            log_path / "app.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        app_file.setLevel(logging.DEBUG)
        app_file.setFormatter(_JSONFormatter())
        root.addHandler(app_file)
        err_file = logging.handlers.RotatingFileHandler(
            log_path / "error.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        err_file.setLevel(logging.ERROR)
        err_file.setFormatter(_JSONFormatter())
        root.addHandler(err_file)
        cls._configure_uvicorn(level)
        cls._configured = True

    @classmethod
    def sync_uvicorn(cls, level: str = "INFO") -> None:
        cls._configure_uvicorn(level)

    @classmethod
    def _configure_uvicorn(cls, level: str) -> None:
        log_level = getattr(logging, level.upper(), logging.INFO)
        formatter = _ColorFormatter()
        formatter.root_name = cls._root
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        for name in ("uvicorn", "uvicorn.error"):
            uv_log = logging.getLogger(name)
            uv_log.handlers.clear()
            uv_log.propagate = False
            uv_log.addHandler(handler)
            uv_log.setLevel(log_level)
        access_log = logging.getLogger("uvicorn.access")
        access_log.handlers.clear()
        access_log.propagate = False
        access_log.addHandler(handler)
        access_log.setLevel(logging.WARNING)

    @classmethod
    def get(cls, name: str) -> logging.Logger:
        short = name.removeprefix("app.")
        return logging.getLogger(f"{cls._root}.{short}")
