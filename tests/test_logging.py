"""Smoke tests for src.infra.logging."""
from __future__ import annotations

import logging
from pathlib import Path

import src.infra.logging as pf_logging
from src.infra.logging import get_logger, setup_logging


def _reset() -> None:
    pf_logging._CONFIGURED = False
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()


def test_setup_logging_creates_file_and_writes(tmp_path: Path) -> None:
    _reset()
    try:
        log_dir = tmp_path / "logs"
        log_path = setup_logging(log_dir)
        assert log_path is not None
        assert log_path.parent == log_dir
        get_logger("pfm.test").info("hello world")
        for handler in logging.getLogger().handlers:
            handler.flush()
        assert log_path.exists()
        content = log_path.read_text(encoding="utf-8")
        assert "hello world" in content
        assert "pfm.test" in content
    finally:
        _reset()


def test_setup_logging_is_idempotent(tmp_path: Path) -> None:
    _reset()
    try:
        first = setup_logging(tmp_path / "logs")
        handlers_after_first = list(logging.getLogger().handlers)
        second = setup_logging(tmp_path / "other")
        handlers_after_second = list(logging.getLogger().handlers)
        assert first == second
        assert handlers_after_first == handlers_after_second
    finally:
        _reset()


def test_setup_logging_without_file_falls_back_to_stderr() -> None:
    _reset()
    try:
        log_path = setup_logging(None)
        assert log_path is None
        handlers = logging.getLogger().handlers
        assert any(isinstance(h, logging.StreamHandler) for h in handlers)
    finally:
        _reset()
