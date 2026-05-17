from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from ..logging import get_logger

log = get_logger("pfm.db.connection")

# Autosave hook fired after every successful COMMIT issued through
# `transaction()`. Used by the application to persist the in-memory DB to
# its encrypted on-disk file. Tests leave it unset (None).
_AUTOSAVE_HOOK: Callable[[], None] | None = None


def set_autosave_hook(fn: Callable[[], None] | None) -> None:
    """Registers a callback to run after each committed transaction.

    Exceptions raised by the hook are logged and swallowed — autosave must
    not break the user's write flow.
    """
    global _AUTOSAVE_HOOK
    _AUTOSAVE_HOOK = fn


def connect(db_path: Path) -> sqlite3.Connection:
    """Opens a file-backed connection. Used only when encryption is disabled."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = DELETE;")
    return conn


def connect_in_memory(initial_bytes: bytes | None = None) -> sqlite3.Connection:
    """Opens a `:memory:` connection, optionally seeded from a serialized DB.

    Plaintext data never touches the disk: the byte buffer is consumed by
    `Connection.deserialize` and lives in process memory. Use
    :func:`serialize_db` to snapshot it back to bytes for encryption.
    """
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    if initial_bytes is not None:
        conn.deserialize(initial_bytes)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def serialize_db(conn: sqlite3.Connection) -> bytes:
    """Returns a serialized snapshot of the connection's main database."""
    return conn.serialize()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    if conn.in_transaction:
        yield conn
        return
    try:
        conn.execute("BEGIN;")
        yield conn
        conn.execute("COMMIT;")
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK;")
        raise
    if _AUTOSAVE_HOOK is not None:
        try:
            _AUTOSAVE_HOOK()
        except Exception:
            log.exception("autosave hook failed")
