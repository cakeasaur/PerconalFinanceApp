from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from itertools import groupby
from typing import Any

MONTH_NAMES_RU = (
    "", "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
)

RECURRENCE_LABELS = ["Не повторять", "Ежедневно", "Еженедельно", "Ежемесячно"]
RECURRENCE_VALUES = ["none", "daily", "weekly", "monthly"]
RECURRENCE_UI_TO_VALUE = dict(zip(RECURRENCE_LABELS, RECURRENCE_VALUES, strict=True))
RECURRENCE_VALUE_TO_UI = {v: k for k, v in RECURRENCE_UI_TO_VALUE.items()}

FILTER_UI_TO_KIND = {"Все": "all", "Расходы": "expense", "Доходы": "income"}
KIND_UI_TO_KIND = {"Расход": "expense", "Доход": "income"}
KIND_KIND_TO_UI = {v: k for k, v in KIND_UI_TO_KIND.items()}


def format_rub(cents: int) -> str:
    return f"{cents / 100:,.2f}".replace(",", " ")


def _ops_word(n: int) -> str:
    """Russian plural for 'операция'."""
    if 11 <= n % 100 <= 19:
        return "операций"
    if n % 10 == 1:
        return "операция"
    if 2 <= n % 10 <= 4:
        return "операции"
    return "операций"


def month_title_ru(dt: datetime) -> str:
    return f"{MONTH_NAMES_RU[dt.month]} {dt.year}".capitalize()


def month_bounds_utc(dt: datetime) -> tuple[datetime, datetime]:
    start = datetime(dt.year, dt.month, 1, tzinfo=UTC)
    if dt.month == 12:
        next_month = datetime(dt.year + 1, 1, 1, tzinfo=UTC)
    else:
        next_month = datetime(dt.year, dt.month + 1, 1, tzinfo=UTC)
    return start, next_month - timedelta(seconds=1)


def recurrence_display(value: str) -> str:
    return RECURRENCE_VALUE_TO_UI.get(value, value)


def kind_to_ui(kind: str) -> str:
    return KIND_KIND_TO_UI.get(kind, kind)


def parse_money(text: str) -> int:
    try:
        cents = (Decimal(text.strip().replace(",", ".")) * 100).to_integral_value()
        return int(cents)
    except InvalidOperation as exc:
        raise ValueError("Некорректная сумма") from exc


def date_group_label(dt: datetime) -> str:
    """Returns «Сегодня», «Вчера» or «15 мая» for a transaction datetime."""
    today = datetime.now(UTC).date()
    tx_date = dt.date()
    if tx_date == today:
        return "Сегодня"
    if tx_date == today - timedelta(days=1):
        return "Вчера"
    month_short = ("", "янв", "фев", "мар", "апр", "мая", "июн",
                   "июл", "авг", "сен", "окт", "ноя", "дек")
    return f"{tx_date.day} {month_short[tx_date.month]}"


def group_by_date(items: Sequence[Any], key_fn: Any) -> list[tuple[str, list[Any]]]:
    """Groups a sequence by date label using key_fn(item) -> datetime.

    Returns list of (label, [items]) in descending date order.
    """
    def _date_key(item: Any) -> date:
        return key_fn(item).date()

    sorted_items = sorted(items, key=_date_key, reverse=True)
    result: list[tuple[str, list[Any]]] = []
    for d, group in groupby(sorted_items, key=_date_key):
        label = date_group_label(datetime(d.year, d.month, d.day, tzinfo=UTC))
        result.append((label, list(group)))
    return result
