"""End-to-end test for the in-memory + encrypted-file storage flow."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from src.core.models import Transaction, TransactionType
from src.infra.db.connection import (
    connect_in_memory,
    serialize_db,
    set_autosave_hook,
    transaction,
)
from src.infra.db.repositories import CategoryRepository, TransactionRepository
from src.infra.db.schema import init_schema
from src.infra.security.crypto import decrypt_file_to_bytes, encrypt_bytes_to_path


def _seed(conn) -> None:
    init_schema(conn)
    cats = CategoryRepository(conn)
    txs = TransactionRepository(conn)
    with transaction(conn):
        cats.ensure_defaults()
        cat = cats.list_all()[0]
        txs.create(Transaction(
            type=TransactionType.EXPENSE,
            amount_cents=12345,
            occurred_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
            category_id=cat.id,
            note="инмемори",
        ))


def test_roundtrip_encrypt_decrypt_in_memory(tmp_path: Path) -> None:
    encrypted = tmp_path / "store.enc"
    passphrase = "test-passphrase-1"

    conn = connect_in_memory()
    _seed(conn)
    encrypt_bytes_to_path(
        plaintext=serialize_db(conn),
        passphrase=passphrase,
        out_path=encrypted,
    )
    conn.close()
    assert encrypted.exists()

    plaintext = decrypt_file_to_bytes(encrypted_path=encrypted, passphrase=passphrase)
    conn2 = connect_in_memory(initial_bytes=plaintext)
    txs2 = TransactionRepository(conn2)
    stored = txs2.list_between(
        start=datetime(2026, 5, 1, tzinfo=UTC),
        end=datetime(2026, 5, 31, 23, 59, 59, tzinfo=UTC),
    )
    assert len(stored) == 1
    assert stored[0].transaction.note == "инмемори"
    conn2.close()


def test_atomic_write_does_not_leave_tmp(tmp_path: Path) -> None:
    encrypted = tmp_path / "store.enc"
    encrypt_bytes_to_path(plaintext=b"hello", passphrase="passphrase!", out_path=encrypted)
    # No .tmp leftovers from the atomic rename.
    assert list(tmp_path.glob("*.tmp")) == []


def test_autosave_hook_fires_on_commit(tmp_path: Path) -> None:
    conn = connect_in_memory()
    init_schema(conn)

    calls: list[int] = []
    set_autosave_hook(lambda: calls.append(1))
    try:
        with transaction(conn):
            conn.execute(
                "INSERT INTO settings(key, value) VALUES ('probe', 'x')"
            )
        assert calls == [1]

        # Nested transactions (already-in-transaction) must not double-fire.
        with transaction(conn):
            with transaction(conn):
                pass
        assert calls == [1, 1]
    finally:
        set_autosave_hook(None)
        conn.close()


def test_autosave_hook_swallows_exceptions(tmp_path: Path) -> None:
    conn = connect_in_memory()
    init_schema(conn)

    def boom() -> None:
        raise RuntimeError("autosave kaboom")

    set_autosave_hook(boom)
    try:
        # COMMIT must succeed even if the hook raises.
        with transaction(conn):
            conn.execute("INSERT INTO settings(key, value) VALUES ('p', 'x')")
        row = conn.execute("SELECT value FROM settings WHERE key='p'").fetchone()
        assert row[0] == "x"
    finally:
        set_autosave_hook(None)
        conn.close()
