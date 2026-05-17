from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import flet as ft

from ...core.reporting import expense_by_category, expense_by_day, totals_for_period
from ..components import card_container, empty_state, metric_card, screen_header
from ..formatting import format_rub, month_bounds_utc, month_title_ru
from ..state import Repos
from ..theme import CHART_PALETTE, GREEN, GREEN_SOFT, RED, RED_SOFT, TEXT_MUTED, page_bgcolor

# Высота области столбцов (px)
_BAR_AREA_H = 160


def _fmt_short(cents: int) -> str:
    v = cents / 100
    if v >= 1_000_000:
        s = f"{v/1_000_000:.1f}".rstrip("0").rstrip(".")
        return f"{s}М"
    if v >= 1_000:
        n = v / 1_000
        return f"{int(n)}К" if n == int(n) else f"{n:.1f}К"
    return f"{int(v)}" if v > 0 else "0"


# ── категории: горизонтальные полосы ─────────────────────────────────────────

def _category_chart(cat_items: list[tuple[str, int]], total: int) -> ft.Control:
    rows: list[ft.Control] = []
    for i, (name, cents) in enumerate(cat_items):
        ratio = cents / total if total > 0 else 0
        color = CHART_PALETTE[i % len(CHART_PALETTE)]
        rows.append(
            ft.Container(
                padding=ft.Padding(0, 6, 0, 6),
                content=ft.Column(
                    spacing=5,
                    controls=[
                        ft.Row(
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(
                                    width=10, height=10, border_radius=5,
                                    bgcolor=color,
                                ),
                                ft.Text(
                                    name, size=13, expand=True,
                                    weight=ft.FontWeight.W_500,
                                ),
                                ft.Text(
                                    f"{int(ratio * 100)}%",
                                    size=12, color=color,
                                    weight=ft.FontWeight.W_600,
                                    width=36,
                                    text_align=ft.TextAlign.RIGHT,
                                ),
                                ft.Text(
                                    f"{format_rub(cents)} ₽",
                                    size=12, color=TEXT_MUTED,
                                    width=120,
                                    text_align=ft.TextAlign.RIGHT,
                                ),
                            ],
                        ),
                        ft.ProgressBar(
                            value=ratio,
                            color=color,
                            bgcolor=ft.Colors.with_opacity(0.1, color),
                            bar_height=8,
                            border_radius=4,
                        ),
                    ],
                ),
            )
        )
    return ft.Column(spacing=0, controls=rows)


# ── дни: кастомный вертикальный столбчатый чарт ──────────────────────────────

def _day_chart(day_items: list[tuple], max_cents: int) -> ft.Control:
    n = len(day_items)
    # ширина столбца и шаг показа дат зависят от количества дней
    bar_w = max(8, min(32, 560 // max(n, 1)))
    show_every = max(1, n // 10)

    columns: list[ft.Control] = []
    for i, (d, cents) in enumerate(day_items):
        ratio = cents / max_cents if max_cents > 0 else 0
        bar_h = max(4, int(ratio * _BAR_AREA_H))
        spacer_h = _BAR_AREA_H - bar_h
        color = "#3B82F6"
        show_label = (i % show_every == 0) or i == n - 1

        # сумма над столбцом — только если влезает (не слишком узко)
        amount_label = _fmt_short(cents) if bar_w >= 14 else ""

        columns.append(
            ft.Column(
                spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    # сумма над столбцом
                    ft.Text(
                        amount_label,
                        size=8, color=TEXT_MUTED,
                        text_align=ft.TextAlign.CENTER,
                        width=bar_w + 8,
                    ),
                    # спейсер (толкает столбец вниз)
                    ft.Container(height=spacer_h),
                    # сам столбец
                    ft.Container(
                        width=bar_w, height=bar_h,
                        bgcolor=ft.Colors.with_opacity(0.85, color),
                        border_radius=ft.BorderRadius(
                            top_left=3, top_right=3,
                            bottom_left=0, bottom_right=0,
                        ),
                    ),
                    # метка даты
                    ft.Text(
                        d.strftime("%d.%m") if show_label else "",
                        size=8, color=TEXT_MUTED,
                        text_align=ft.TextAlign.CENTER,
                        width=bar_w + 8,
                    ),
                ],
            )
        )

    # Y-axis метки (0 и максимум)
    y_axis = ft.Column(
        horizontal_alignment=ft.CrossAxisAlignment.END,
        spacing=0,
        width=44,
        controls=[
            ft.Text(_fmt_short(max_cents), size=9, color=TEXT_MUTED),
            ft.Container(height=_BAR_AREA_H - 28),
            ft.Text("0", size=9, color=TEXT_MUTED),
            ft.Container(height=20),  # отступ под дату
        ],
    )

    bars_row = ft.Row(
        spacing=4,
        vertical_alignment=ft.CrossAxisAlignment.START,
        scroll=ft.ScrollMode.AUTO,
        controls=columns,
        expand=True,
    )

    return ft.Row(
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.START,
        controls=[y_axis, ft.Container(content=bars_row, expand=True)],
        height=_BAR_AREA_H + 44,
    )


# ── экран ─────────────────────────────────────────────────────────────────────

def build_reports(
    page: ft.Page,
    repos: Repos,
    state: dict,
    navigate: Callable[[str], None],
    rebuild: Callable[[], None],
) -> ft.Control:
    current_month: datetime = state.get("ops_month", datetime.now(UTC))
    start, end = month_bounds_utc(current_month)
    stored = repos.tx.list_between(start=start, end=end)
    txs = [s.transaction for s in stored]

    totals = totals_for_period(txs, start=start, end=end)
    by_cat = expense_by_category(txs, start=start, end=end)
    by_day = expense_by_day(txs, start=start, end=end)
    cats = {c.id: c.name for c in repos.cat.list_all()}
    cats[None] = "Без категории"

    def prev_month(_: ft.ControlEvent) -> None:
        dt = state.get("ops_month", datetime.now(UTC))
        state["ops_month"] = (
            datetime(dt.year - 1, 12, 1, tzinfo=UTC) if dt.month == 1
            else datetime(dt.year, dt.month - 1, 1, tzinfo=UTC)
        )
        rebuild()

    def next_month(_: ft.ControlEvent) -> None:
        dt = state.get("ops_month", datetime.now(UTC))
        state["ops_month"] = (
            datetime(dt.year + 1, 1, 1, tzinfo=UTC) if dt.month == 12
            else datetime(dt.year, dt.month + 1, 1, tzinfo=UTC)
        )
        rebuild()

    balance_color = GREEN if totals.balance_cents >= 0 else RED

    month_nav = ft.Row(spacing=4, controls=[
        ft.IconButton(ft.Icons.CHEVRON_LEFT, on_click=prev_month,
                      icon_color=TEXT_MUTED, icon_size=18),
        ft.Text(month_title_ru(current_month), size=13, weight=ft.FontWeight.W_600),
        ft.IconButton(ft.Icons.CHEVRON_RIGHT, on_click=next_month,
                      icon_color=TEXT_MUTED, icon_size=18),
    ])
    header = screen_header(page, "Аналитика", rebuild, actions=[month_nav])

    summary_row = ft.Row(
        spacing=16,
        controls=[
            metric_card(page, "Доходы", f"{format_rub(totals.income_cents)} ₽",
                        "", GREEN, ft.Icons.TRENDING_UP, GREEN_SOFT),
            metric_card(page, "Расходы", f"{format_rub(totals.expense_cents)} ₽",
                        "", RED, ft.Icons.TRENDING_DOWN, RED_SOFT),
            metric_card(page, "Баланс", f"{format_rub(totals.balance_cents)} ₽",
                        "", balance_color, ft.Icons.ACCOUNT_BALANCE_WALLET, GREEN_SOFT),
        ],
    )

    # ── расходы по категориям ─────────────────────────────────────────────────
    cat_items = sorted(
        ((cats.get(cid, str(cid)), v) for cid, v in by_cat.items()),
        key=lambda x: x[1], reverse=True,
    )
    cat_items = [(n, v) for n, v in cat_items if v > 0]
    total_expense = sum(v for _, v in cat_items)

    cat_card = card_container(
        page,
        ft.Column(
            spacing=12,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(spacing=8, controls=[
                            ft.Icon(ft.Icons.DONUT_LARGE, color=TEXT_MUTED, size=16),
                            ft.Text("Расходы по категориям",
                                    weight=ft.FontWeight.W_700, size=14),
                        ]),
                        ft.Text(
                            f"Всего: {format_rub(total_expense)} ₽",
                            size=12, color=TEXT_MUTED,
                        ) if cat_items else ft.Container(),
                    ],
                ),
                _category_chart(cat_items, total_expense)
                if cat_items else
                empty_state("Расходов по категориям нет.", ft.Icons.PIE_CHART_OUTLINE),
            ],
        ),
    )

    # ── расходы по дням ───────────────────────────────────────────────────────
    day_items = [(d, v) for d, v in sorted(by_day.items()) if v > 0]
    max_day = max((v for _, v in day_items), default=0)

    day_card = card_container(
        page,
        ft.Column(
            spacing=12,
            controls=[
                ft.Row(spacing=8, controls=[
                    ft.Icon(ft.Icons.BAR_CHART, color=TEXT_MUTED, size=16),
                    ft.Text("Расходы по дням", weight=ft.FontWeight.W_700, size=14),
                ]),
                _day_chart(day_items, max_day)
                if day_items else
                empty_state("Расходов по дням нет.", ft.Icons.CALENDAR_TODAY),
            ],
        ),
    )

    content = ft.Column(
        spacing=16, expand=True, scroll=ft.ScrollMode.AUTO,
        controls=[header, summary_row, cat_card, day_card],
    )

    return ft.Container(content=content, expand=True, padding=24, bgcolor=page_bgcolor(page))
