"""Tests for the migration runner."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.infra.db.connection import connect
from src.infra.db.migrations import (
    MIGRATIONS,
    Migration,
    MigrationError,
    apply_pending,
    get_current_version,
    set_version,
)
from src.infra.db.schema import SCHEMA_VERSION, init_schema


def _open(tmp_path: Path) -> sqlite3.Connection:
    return connect(tmp_path / "test.sqlite3")


def test_fresh_init_sets_target_version(tmp_path: Path) -> None:
    conn = _open(tmp_path)
    init_schema(conn)
    assert get_current_version(conn) == SCHEMA_VERSION


def test_init_schema_is_idempotent(tmp_path: Path) -> None:
    conn = _open(tmp_path)
    init_schema(conn)
    init_schema(conn)
    assert get_current_version(conn) == SCHEMA_VERSION


def test_db_ahead_of_code_raises(tmp_path: Path) -> None:
    conn = _open(tmp_path)
    init_schema(conn)
    set_version(conn, SCHEMA_VERSION + 1)
    with pytest.raises(MigrationError, match="newer than app's"):
        init_schema(conn)


def test_no_migration_path_raises(tmp_path: Path) -> None:
    conn = _open(tmp_path)
    init_schema(conn)
    # Pretend the DB is at v1, but no migrations registered to take it forward.
    set_version(conn, 1)
    with pytest.raises(MigrationError, match="no migration registered"):
        apply_pending(conn, SCHEMA_VERSION)


def test_apply_pending_runs_chain(tmp_path: Path) -> None:
    conn = _open(tmp_path)
    init_schema(conn)

    applied: list[str] = []

    def step_a(c: sqlite3.Connection) -> None:
        applied.append("a")
        c.execute("CREATE TABLE _probe_a (x INTEGER);")

    def step_b(c: sqlite3.Connection) -> None:
        applied.append("b")
        c.execute("CREATE TABLE _probe_b (x INTEGER);")

    chain = [
        Migration(from_version=10, to_version=11, name="add_a", apply=step_a),
        Migration(from_version=11, to_version=12, name="add_b", apply=step_b),
    ]
    set_version(conn, 10)
    n = apply_pending(conn, 12, migrations=chain)
    assert n == 2
    assert applied == ["a", "b"]
    assert get_current_version(conn) == 12
    # Re-running is a no-op once we've reached the target.
    assert apply_pending(conn, 12, migrations=chain) == 0


def test_failed_migration_rolls_back(tmp_path: Path) -> None:
    conn = _open(tmp_path)
    init_schema(conn)
    set_version(conn, 20)

    def boom(c: sqlite3.Connection) -> None:
        c.execute("CREATE TABLE _will_be_rolled_back (x INTEGER);")
        raise RuntimeError("kaboom")

    chain = [Migration(from_version=20, to_version=21, name="boom", apply=boom)]
    with pytest.raises(RuntimeError, match="kaboom"):
        apply_pending(conn, 21, migrations=chain)
    assert get_current_version(conn) == 20
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='_will_be_rolled_back'"
    ).fetchone()
    assert table is None


def test_get_current_version_handles_corruption(tmp_path: Path) -> None:
    conn = _open(tmp_path)
    init_schema(conn)
    conn.execute(
        "UPDATE settings SET value='not-a-number' WHERE key='schema_version';"
    )
    with pytest.raises(MigrationError, match="corrupted schema_version"):
        get_current_version(conn)


def test_migrations_list_matches_schema_version() -> None:
    """MIGRATIONS must have exactly (SCHEMA_VERSION - 3) entries starting from v3."""
    assert len(MIGRATIONS) == SCHEMA_VERSION - 3
    if MIGRATIONS:
        assert MIGRATIONS[0].from_version == 3
        assert MIGRATIONS[-1].to_version == SCHEMA_VERSION
