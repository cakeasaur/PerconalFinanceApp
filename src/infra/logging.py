"""Централизованное логирование приложения.

Использование:

    from src.infra.logging import setup_logging, get_logger
    setup_logging()                  # один раз при старте процесса
    log = get_logger(__name__)
    log.info("started")

Поведение по умолчанию:
- файл `<DATA_DIR>/logs/app.log`, ротация 1 МБ × 5 копий,
- stderr-handler уровня WARNING и выше,
- уровень файлового хендлера — INFO; меняется через `PF_LOG_LEVEL`
  (DEBUG/INFO/WARNING/ERROR).
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False
_LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_DEFAULT_LEVEL = "INFO"
_MAX_BYTES = 1_048_576  # 1 MiB
_BACKUP_COUNT = 5


def _resolve_level(value: str | None) -> int:
    if not value:
        return logging.INFO
    name = value.strip().upper()
    level = logging.getLevelName(name)
    return level if isinstance(level, int) else logging.INFO


def setup_logging(log_dir: Path | None = None) -> Path | None:
    """Инициализирует root-логгер. Идемпотентна.

    Возвращает путь к файлу лога, или None если файловый хендлер не удалось
    создать (тогда логи идут только в stderr).
    """
    global _CONFIGURED
    if _CONFIGURED:
        return getattr(logging.getLogger(), "_pf_log_path", None)

    level = _resolve_level(os.environ.get("PF_LOG_LEVEL", _DEFAULT_LEVEL))
    root = logging.getLogger()
    root.setLevel(min(level, logging.WARNING))

    formatter = logging.Formatter(_LOG_FORMAT, _DATE_FORMAT)

    stderr_handler = logging.StreamHandler(stream=sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(formatter)
    root.addHandler(stderr_handler)

    log_path: Path | None = None
    if log_dir is not None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "app.log"
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=_MAX_BYTES,
                backupCount=_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError as exc:
            root.warning("cannot open log file in %s: %s", log_dir, exc)
            log_path = None

    root._pf_log_path = log_path  # type: ignore[attr-defined]
    _CONFIGURED = True
    return log_path


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
