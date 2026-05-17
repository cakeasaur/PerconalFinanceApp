"""CSV export/import for transactions."""
from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from .models import Transaction, TransactionType

HEADERS = ["date", "type", "amount_rub", "category_id", "note"]


def export_csv(transactions: list[Transaction]) -> str:
    """Returns a CSV string of all transactions."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(HEADERS)
    for tx in sorted(transactions, key=lambda t: t.occurred_at):
        writer.writerow([
            tx.occurred_at.strftime("%Y-%m-%d %H:%M"),
            tx.type.value,
            f"{tx.amount_cents / 100:.2f}",
            tx.category_id or "",
            tx.note or "",
        ])
    return buf.getvalue()


def parse_csv(text: str) -> list[Transaction]:
    """Parses CSV text into a list of Transaction objects.

    Raises ValueError with a human-readable message on bad rows.
    """
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != HEADERS:
        raise ValueError(
            f"Неверные заголовки. Ожидается: {', '.join(HEADERS)}"
        )
    result: list[Transaction] = []
    for i, row in enumerate(reader, start=2):
        try:
            occurred_at = datetime.strptime(row["date"].strip(), "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
            tx_type = TransactionType(row["type"].strip())
            amount_cents = round(float(row["amount_rub"].strip()) * 100)
            category_id = int(row["category_id"].strip()) if row["category_id"].strip() else None
            note = row["note"].strip() or None
            result.append(Transaction(
                type=tx_type,
                amount_cents=amount_cents,
                occurred_at=occurred_at,
                category_id=category_id,
                note=note,
            ))
        except (KeyError, ValueError) as exc:
            raise ValueError(f"Строка {i}: {exc}") from exc
    return result
