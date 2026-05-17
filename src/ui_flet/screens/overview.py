from __future__ import annotations

import calendar
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import flet as ft

from ...core.reporting import expense_by_category, expense_by_day, income_by_day, totals_for_period
from ..components import card_container, metric_card, screen_header, tx_row
from ..formatting import format_rub, month_bounds_utc
from ..state import Repos
from ..theme import (
    BLUE_SOFT,
    CHART_PALETTE,
    GREEN,
    GREEN_SOFT,
    PURPLE,
    RED,
    RED_SOFT,
    TEXT_MUTED,
    card_bgcolor,
    page_bgcolor,
)

__all__ = ["build_overview"]

_MONTH_SHORT = {
    1: "янв", 2: "фев", 3: "мар", 4: "апр", 5: "мая", 6: "июн",
    7: "июл", 8: "авг", 9: "сен", 10: "окт", 11: "ноя", 12: "дек",
}

_GOAL_ICONS = {
    "море": ft.Icons.BEACH_ACCESS, "ноутбук": ft.Icons.LAPTOP_MAC,
    "машин": ft.Icons.DIRECTIONS_CAR, "квартир": ft.Icons.HOME,
    "телефон": ft.Icons.PHONE_ANDROID, "отпуск": ft.Icons.BEACH_ACCESS,
}

_CAT_COLORS = CHART_PALETTE


# ── helpers ───────────────────────────────────────────────────────────────────

def _pct_delta(current: int, previous: int) -> tuple[str, str]:
    if previous == 0:
        return "", TEXT_MUTED
    diff = (current - previous) / previous * 100
    arrow = "↑" if diff >= 0 else "↓"
    color = GREEN if diff >= 0 else RED
    return f"{arrow} {abs(diff):.1f}%", color


def _days_word(n: int) -> str:
    if 11 <= n % 100 <= 19:
        return "дней"
    r = n % 10
    if r == 1:
        return "день"
    if 2 <= r <= 4:
        return "дня"
    return "дней"


# ── chart ─────────────────────────────────────────────────────────────────────

def _fmt_short(cents: int) -> str:
    v = cents / 100
    if v >= 1_000_000:
        s = f"{v/1_000_000:.1f}".rstrip("0").rstrip(".")
        return f"{s}М"
    if v >= 1_000:
        n = v / 1_000
        return f"{int(n)}К" if n == int(n) else f"{n:.1f}К"
    return f"{int(v)}"


def _mini_bars(
    by_day: dict[int, int],
    days: list[int],
    color: str,
    bar_w: int,
    bar_area_h: int,
    x_ticks: set[int],
    mon: str,
    fg: str,
) -> list[ft.Control]:
    """Строит список Column для одной серии (доходы ИЛИ расходы).

    Каждый Column содержит: пустой спейсер + столбик + метку дня.
    Все Column одинаковой высоты → Row с alignment=START выглядит корректно.
    """
    max_val = max((by_day.get(d, 0) for d in days), default=0)
    cols: list[ft.Control] = []
    for d in days:
        cents = by_day.get(d, 0)
        ratio = cents / max_val if max_val > 0 else 0
        bar_h = max(2, int(ratio * bar_area_h)) if cents > 0 else 0
        spacer_h = bar_area_h - bar_h
        label = f"{d} {mon}" if d in x_ticks else ""
        tooltip = f"{d} {mon}: {_fmt_short(cents)} ₽" if cents > 0 else ""
        cols.append(
            ft.Column(
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tooltip=tooltip,
                controls=[
                    ft.Container(height=spacer_h),
                    ft.Container(
                        width=bar_w, height=bar_h,
                        bgcolor=ft.Colors.with_opacity(0.85, color),
                        border_radius=ft.BorderRadius(
                            top_left=2, top_right=2,
                            bottom_left=0, bottom_right=0,
                        ),
                    ),
                    ft.Container(height=4),
                    ft.Text(label, size=8, color=fg,
                            text_align=ft.TextAlign.CENTER, width=bar_w + 6),
                ],
            )
        )
    return cols


def _dynamics_chart(
    by_day_income: dict[int, int],
    by_day_expense: dict[int, int],
    days_in_month: int,
    month_num: int,
    is_dark: bool,
) -> ft.Control:
    fg = "#94A3B8" if is_dark else TEXT_MUTED
    mon = _MONTH_SHORT.get(month_num, "")
    days = list(range(1, days_in_month + 1))
    bar_area_h = 70
    bar_w = max(5, min(14, 560 // days_in_month))
    spacing = max(1, bar_w // 3)
    x_ticks = {1, 8, 15, 22, days_in_month}

    max_inc = max((by_day_income.get(d, 0) for d in days), default=1)
    max_exp = max((by_day_expense.get(d, 0) for d in days), default=1)

    def _series_row(
        by_day: dict[int, int],
        color: str,
        label: str,
        max_val: int,
        show_x: bool,
    ) -> ft.Control:
        cols = _mini_bars(
            by_day, days, color, bar_w, bar_area_h,
            x_ticks if show_x else set(), mon, fg if show_x else ft.Colors.TRANSPARENT,
        )
        max_label = _fmt_short(max_val) if max_val > 0 else "0"
        x_label_h = 14
        total_h = bar_area_h + x_label_h
        y_axis = ft.Container(
            width=44, height=total_h,
            content=ft.Stack([
                ft.Container(
                    top=0, right=0,
                    content=ft.Text(
                        max_label, size=8, color=fg,
                        no_wrap=True, text_align=ft.TextAlign.RIGHT,
                    ),
                ),
                ft.Container(
                    top=bar_area_h - 10, right=0,
                    content=ft.Text(
                        "0", size=8, color=fg,
                        text_align=ft.TextAlign.RIGHT,
                    ),
                ),
            ]),
        )
        return ft.Row(
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                y_axis,
                ft.Container(width=4),
                ft.Row(
                    spacing=spacing,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=cols,
                    expand=True,
                ),
            ],
        )

    return ft.Column(
        spacing=4,
        controls=[
            _series_row(by_day_income, GREEN, "Доходы", max_inc, show_x=False),
            _series_row(by_day_expense, RED, "Расходы", max_exp, show_x=True),
        ],
    )


# ── sub-widgets ───────────────────────────────────────────────────────────────

def _cat_row(
    name: str,
    amount_cents: int,
    total_cents: int,
    color: str,
) -> ft.Container:
    ratio = min(1.0, amount_cents / total_cents) if total_cents else 0.0
    return ft.Container(
        padding=ft.Padding(0, 8, 0, 8),
        content=ft.Column(
            spacing=6,
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            bgcolor=ft.Colors.with_opacity(0.12, color),
                            border_radius=6, width=10, height=10,
                        ),
                        ft.Container(width=8),
                        ft.Text(name, expand=True, size=13, weight=ft.FontWeight.W_500),
                        ft.Text(
                            f"{format_rub(amount_cents)} ₽",
                            color=TEXT_MUTED, size=12,
                        ),
                        ft.Container(width=8),
                        ft.Text(
                            f"{int(ratio * 100)}%",
                            color=color, size=12, weight=ft.FontWeight.W_600,
                            width=32, text_align=ft.TextAlign.RIGHT,
                        ),
                    ],
                ),
                ft.ProgressBar(
                    value=ratio, color=color,
                    bgcolor=ft.Colors.with_opacity(0.12, color),
                    bar_height=5, border_radius=3,
                ),
            ],
        ),
    )


def _goal_icon(name: str) -> str:
    nl = name.lower()
    for kw, ico in _GOAL_ICONS.items():
        if kw in nl:
            return ico
    return ft.Icons.FLAG_OUTLINED


# ── main builder ──────────────────────────────────────────────────────────────

def build_overview(
    page: ft.Page,
    repos: Repos,
    app_state: dict,
    navigate: Callable[[str], None],
    rebuild: Callable[[], None],
) -> ft.Control:
    now = datetime.now(UTC)
    start, end = month_bounds_utc(now)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    is_dark = page.theme_mode == ft.ThemeMode.DARK

    # current month
    stored = repos.tx.list_between(start=start, end=end)
    txs = [s.transaction for s in stored]
    totals = totals_for_period(txs, start=start, end=end)
    by_day_exp = {dt.day: c for dt, c in expense_by_day(txs, start=start, end=end).items()}
    by_day_inc = {dt.day: c for dt, c in income_by_day(txs, start=start, end=end).items()}
    categories = {c.id: c.name for c in repos.cat.list_all()}
    goals = repos.goal.list_all()

    # previous month for deltas
    prev_end_dt = start - timedelta(seconds=1)
    prev_start, prev_end = month_bounds_utc(prev_end_dt)
    prev_txs = [s.transaction for s in repos.tx.list_between(start=prev_start, end=prev_end)]
    prev_totals = totals_for_period(prev_txs, start=prev_start, end=prev_end)

    # top-3 expense categories
    cat_spending = expense_by_category(txs, start=start, end=end)
    top_cats = sorted(cat_spending.items(), key=lambda x: x[1], reverse=True)[:3]

    # deltas
    bal_delta, bal_color = _pct_delta(totals.balance_cents, prev_totals.balance_cents)
    inc_delta, inc_color = _pct_delta(totals.income_cents, prev_totals.income_cents)
    exp_delta, exp_color = _pct_delta(totals.expense_cents, prev_totals.expense_cents)
    balance_color = GREEN if totals.balance_cents >= 0 else RED

    days_left = days_in_month - now.day

    # ── header ────────────────────────────────────────────────────────────────
    mon = _MONTH_SHORT[now.month]
    date_range = f"{start.day}–{end.day} {mon} {now.year}"

    date_chip = ft.Container(
        bgcolor=card_bgcolor(page), border_radius=8,
        padding=ft.Padding(12, 6, 12, 6),
        content=ft.Row(spacing=6, controls=[
            ft.Text(date_range, size=12, color=TEXT_MUTED),
            ft.Icon(ft.Icons.CALENDAR_MONTH_OUTLINED, size=14, color=TEXT_MUTED),
        ]),
    )
    header = screen_header(page, "Главная", rebuild, actions=[date_chip])

    # ── metric row ────────────────────────────────────────────────────────────
    metric_row = ft.Row(
        spacing=16,
        controls=[
            metric_card(page, "Баланс",
                         f"{format_rub(totals.balance_cents)} ₽",
                         bal_delta, balance_color,
                         ft.Icons.ACCOUNT_BALANCE_WALLET, GREEN_SOFT),
            metric_card(page, "Доходы",
                         f"{format_rub(totals.income_cents)} ₽",
                         inc_delta, inc_color,
                         ft.Icons.TRENDING_UP, GREEN_SOFT),
            metric_card(page, "Расходы",
                         f"{format_rub(totals.expense_cents)} ₽",
                         exp_delta, exp_color,
                         ft.Icons.TRENDING_DOWN, RED_SOFT),
            metric_card(page, "До конца месяца",
                         f"{days_left} {_days_word(days_left)}",
                         f"из {days_in_month} дней в месяце", "#3B82F6",
                         ft.Icons.CALENDAR_TODAY, BLUE_SOFT),
        ],
    )

    # ── chart card ────────────────────────────────────────────────────────────
    chart_card = card_container(
        page,
        ft.Column(
            spacing=12,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Динамика за период", weight=ft.FontWeight.W_700, size=14),
                        ft.Row(spacing=14, controls=[
                            ft.Row(spacing=6, controls=[
                                ft.Container(width=10, height=10, bgcolor=GREEN, border_radius=5),
                                ft.Text("Доходы", size=12, color=TEXT_MUTED),
                            ]),
                            ft.Row(spacing=6, controls=[
                                ft.Container(width=10, height=10, bgcolor=RED, border_radius=5),
                                ft.Text("Расходы", size=12, color=TEXT_MUTED),
                            ]),
                        ]),
                    ],
                ),
                _dynamics_chart(by_day_inc, by_day_exp, days_in_month, now.month, is_dark),
            ],
        ),
    )

    # ── recent operations card ─────────────────────────────────────────────
    recent_card = card_container(
        page,
        ft.Column(
            spacing=4,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Последние операции", weight=ft.FontWeight.W_700, size=14),
                        ft.TextButton("Показать все",
                                      style=ft.ButtonStyle(color=GREEN),
                                      on_click=lambda _: navigate("operations")),
                    ],
                ),
                *(
                    [ft.Text("Операций пока нет", color=TEXT_MUTED, size=13)]
                    if not stored else
                    [tx_row(s.transaction, categories.get(s.transaction.category_id))
                     for s in stored[:5]]
                ),
            ],
        ),
    )

    # ── top categories card ────────────────────────────────────────────────
    if top_cats:
        cat_controls: list[ft.Control] = [
            _cat_row(
                categories.get(cat_id, "Без категории"),
                amount,
                totals.expense_cents,
                _CAT_COLORS[i % len(_CAT_COLORS)],
            )
            for i, (cat_id, amount) in enumerate(top_cats)
        ]
    else:
        cat_controls = [ft.Text("Расходов пока нет", color=TEXT_MUTED, size=13)]

    categories_card = card_container(
        page,
        ft.Column(
            spacing=4,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Расходы по категориям", weight=ft.FontWeight.W_700, size=14),
                        ft.TextButton("Аналитика",
                                      style=ft.ButtonStyle(color=GREEN),
                                      on_click=lambda _: navigate("reports")),
                    ],
                ),
                *cat_controls,
            ],
        ),
    )

    # ── goals card ────────────────────────────────────────────────────────────
    goals_card = card_container(
        page,
        ft.Column(
            spacing=4,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Цели", weight=ft.FontWeight.W_700, size=14),
                        ft.TextButton("Все цели",
                                      style=ft.ButtonStyle(color=GREEN),
                                      on_click=lambda _: navigate("goals")),
                    ],
                ),
                *(
                    [ft.Text("Целей пока нет", color=TEXT_MUTED, size=13)]
                    if not goals else
                    [
                        ft.Container(
                            padding=ft.Padding(0, 6, 0, 6),
                            content=ft.Row(
                                spacing=12,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(
                                        bgcolor=ft.Colors.with_opacity(0.1, PURPLE),
                                        border_radius=8, width=32, height=32,
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Icon(_goal_icon(g.name), size=16, color=PURPLE),
                                    ),
                                    ft.Column(
                                        spacing=3, expand=True,
                                        controls=[
                                            ft.Text(g.name, size=13, weight=ft.FontWeight.W_600),
                                            ft.Text(
                                                f"{format_rub(g.current_cents)} / "
                                                f"{format_rub(g.target_cents)} ₽",
                                                size=11, color=TEXT_MUTED,
                                            ),
                                            ft.ProgressBar(
                                                value=g.progress_ratio, color=PURPLE,
                                                bgcolor=ft.Colors.with_opacity(0.12, PURPLE),
                                                bar_height=4, border_radius=2,
                                            ),
                                        ],
                                    ),
                                    ft.Text(
                                        f"{int(g.progress_ratio * 100)}%",
                                        size=12, color=TEXT_MUTED,
                                    ),
                                ],
                            ),
                        )
                        for g in goals[:3]
                    ]
                ),
                ft.TextButton("+ Новая цель",
                              style=ft.ButtonStyle(color=GREEN),
                              on_click=lambda _: navigate("goals")),
            ],
        ),
    )

    # ── layout ────────────────────────────────────────────────────────────────
    content = ft.Column(
        spacing=16, expand=True, scroll=ft.ScrollMode.AUTO,
        controls=[
            header,
            metric_row,
            ft.Row(
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    ft.Column(spacing=16, expand=3,
                              controls=[chart_card, recent_card]),
                    ft.Column(spacing=16, expand=2,
                              controls=[categories_card, goals_card]),
                ],
            ),
        ],
    )

    return ft.Container(content=content, expand=True, padding=24, bgcolor=page_bgcolor(page))
