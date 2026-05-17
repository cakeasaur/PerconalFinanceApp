"""Schema-version migrations for the SQLite database.

Each migration is a tuple `(from_version, to_version, name, apply)`. The runner
reads `settings.schema_version`, applies all pending migrations in order, and
commits each one in its own transaction. A failed migration rolls back and
leaves the stored version untouched.

To add a new migration:
1. Bump :data:`src.infra.db.schema.SCHEMA_VERSION`.
2. Append a :class:`Migration` here that takes the DB from the previous version
   to the new one. Keep DDL idempotent where reasonable (``IF NOT EXISTS``).
3. Update :func:`src.infra.db.schema.init_schema`'s bootstrap to reflect the
   new latest schema, so fresh databases skip migrations.
4. Add a test that exercises the new migration on a database snapshot of the
   previous version.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

from ..logging import get_logger

log = get_logger("pfm.db.migrations")


class MigrationError(RuntimeError):
    """Raised when the schema version cannot be brought to the target value."""


@dataclass(frozen=True, slots=True)
class Migration:
    from_version: int
    to_version: int
    name: str
    apply: Callable[[sqlite3.Connection], None]


def _v3_to_v4(conn: sqlite3.Connection) -> None:
    conn.execute("ALTER TABLE goals     ADD COLUMN icon  TEXT NULL;")
    conn.execute("ALTER TABLE goals     ADD COLUMN color TEXT NULL;")
    conn.execute("ALTER TABLE reminders ADD COLUMN icon  TEXT NULL;")
    conn.execute("ALTER TABLE reminders ADD COLUMN color TEXT NULL;")


MIGRATIONS: list[Migration] = [
    Migration(
        from_version=3, to_version=4,
        name="add_icon_color_to_goals_reminders",
        apply=_v3_to_v4,
    ),
]


def get_current_version(conn: sqlite3.Connection) -> int:
    """Reads the stored schema version. Returns 0 for a fresh DB.

    The `settings` table must exist before calling this. Returns 0 if the
    table exists but no `schema_version` row is present.
    """
    row = conn.execute(
        "SELECT value FROM settings WHERE key='schema_version'"
    ).fetchone()
    if row is None:
        return 0
    try:
        return int(row[0])
    except (TypeError, ValueError) as exc:
        raise MigrationError(
            f"corrupted schema_version value: {row[0]!r}"
        ) from exc


def set_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "INSERT INTO settings(key, value) VALUES ('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value;",
        (str(version),),
    )


def apply_pending(
    conn: sqlite3.Connection,
    target_version: int,
    migrations: list[Migration] | None = None,
) -> int:
    """Brings the DB from its current version up to `target_version`.

    Returns the number of migrations applied. Raises :class:`MigrationError`
    if the DB is ahead of the target, or if no migration path exists from the
    current version to the target.
    """
    registered = MIGRATIONS if migrations is None else migrations
    current = get_current_version(conn)

    if current > target_version:
        raise MigrationError(
            f"db schema_version={current} is ahead of code target={target_version}; "
            "downgrade is not supported"
        )
    if current == target_version:
        return 0

    by_from: dict[int, Migration] = {}
    for m in registered:
        if m.from_version in by_from:
            raise MigrationError(
                f"duplicate migration registered for version {m.from_version}"
            )
        by_from[m.from_version] = m

    applied = 0
    while current < target_version:
        step = by_from.get(current)
        if step is None:
            raise MigrationError(
                f"no migration registered for version {current} "
                f"(target {target_version})"
            )
        log.info(
            "applying migration %s (%d -> %d)",
            step.name, step.from_version, step.to_version,
        )
        try:
            conn.execute("BEGIN;")
            step.apply(conn)
            set_version(conn, step.to_version)
            conn.execute("COMMIT;")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK;")
            log.exception("migration %s failed; rolled back", step.name)
            raise
        current = step.to_version
        applied += 1
    return applied
