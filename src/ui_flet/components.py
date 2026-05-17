from __future__ import annotations

from collections.abc import Callable
from typing import Any

import flet as ft

from ..core.models import Transaction, TransactionType
from .formatting import format_rub
from .theme import (
    GREEN,
    GREEN_SOFT,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    RADIUS_XL,
    RED,
    RED_SOFT,
    TEXT_MUTED,
    card_bgcolor,
    card_shadow,
    muted_color,
    sidebar_bgcolor,
)

# ── иконки и цвета для пикеров ───────────────────────────────────────────────

# Имена иконок хранятся как строки — sqlite3 сохраняет IntEnum как int,
# который ft.Icon() не принимает. Строку безопасно round-trip через DB.
ICON_OPTIONS: list[tuple[str, str]] = [
    ("Дом",          "HOME_OUTLINED"),
    ("Еда",          "LOCAL_PIZZA_OUTLINED"),
    ("Транспорт",    "DIRECTIONS_CAR_OUTLINED"),
    ("Здоровье",     "FAVORITE_OUTLINE"),
    ("Развлечения",  "SPORTS_ESPORTS_OUTLINED"),
    ("Красота",      "FACE_OUTLINED"),
    ("Образование",  "MENU_BOOK_OUTLINED"),
    ("Путешествия",  "FLIGHT_OUTLINED"),
    ("Питомцы",      "PETS_OUTLINED"),
    ("Одежда",       "CHECKROOM_OUTLINED"),
    ("Фитнес",       "FITNESS_CENTER_OUTLINED"),
    ("Покупки",      "SHOPPING_CART_OUTLINED"),
    ("ЖКХ",          "BOLT_OUTLINED"),
    ("Телефон",      "PHONE_ANDROID_OUTLINED"),
    ("Техника",      "LAPTOP_OUTLINED"),
    ("Подарки",      "CARD_GIFTCARD_OUTLINED"),
    ("Банк",         "ACCOUNT_BALANCE_OUTLINED"),
    ("Хобби",        "PALETTE_OUTLINED"),
    ("Кафе",         "LOCAL_CAFE_OUTLINED"),
    ("Цель",         "FLAG_OUTLINED"),
]

COLOR_OPTIONS: list[str] = [
    "#22C55E",  # зелёный
    "#EF4444",  # красный
    "#3B82F6",  # синий
    "#F59E0B",  # жёлтый
    "#8B5CF6",  # фиолетовый
    "#F97316",  # оранжевый
    "#14B8A6",  # бирюзовый
    "#EC4899",  # розовый
    "#64748B",  # серый
    "#0EA5E9",  # голубой
]

DEFAULT_ICON = "LABEL_OUTLINE"  # строка-имя, не enum — безопасно для DB
DEFAULT_COLOR = "#8B5CF6"


def resolve_icon(name: str | None) -> object:
    """Конвертирует имя иконки из БД в ft.Icons значение."""
    if not name:
        return getattr(ft.Icons, DEFAULT_ICON)
    # Если это уже enum (IntEnum) — вернуть как есть
    if isinstance(name, int):
        try:
            return ft.Icons(name)
        except ValueError:
            return getattr(ft.Icons, DEFAULT_ICON)
    return getattr(ft.Icons, str(name), getattr(ft.Icons, DEFAULT_ICON))

# ── диалоги ───────────────────────────────────────────────────────────────────

def open_dialog(page: ft.Page, dlg: ft.AlertDialog) -> None:
    page.show_dialog(dlg)


def close_dialog(page: ft.Page, _dlg: ft.AlertDialog) -> None:
    page.pop_dialog()


def confirm_dialog(
    page: ft.Page,
    message: str,
    on_confirm: Callable[[], None],
    *,
    confirm_label: str = "Удалить",
    confirm_color: str = RED,
) -> None:
    def _do(_: ft.ControlEvent) -> None:
        close_dialog(page, dlg)
        on_confirm()

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("Подтвердите действие"),
        content=ft.Text(message),
        actions=[
            ft.TextButton("Отмена", on_click=lambda _: close_dialog(page, dlg)),
            ft.FilledButton(
                confirm_label,
                on_click=_do,
                style=ft.ButtonStyle(bgcolor=confirm_color, color=ft.Colors.WHITE),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    open_dialog(page, dlg)


# ── header экрана ─────────────────────────────────────────────────────────────

def screen_header(
    page: ft.Page,
    title: str,
    rebuild: Callable[[], None],
    *,
    actions: list[ft.Control] | None = None,
) -> ft.Row:
    def _toggle_theme(_: ft.ControlEvent) -> None:
        page.theme_mode = (
            ft.ThemeMode.DARK if page.theme_mode == ft.ThemeMode.LIGHT
            else ft.ThemeMode.LIGHT
        )
        rebuild()

    icon = ft.Icons.DARK_MODE_OUTLINED if page.theme_mode == ft.ThemeMode.LIGHT else ft.Icons.LIGHT_MODE_OUTLINED
    right: list[ft.Control] = list(actions or [])
    right.append(
        ft.IconButton(icon, on_click=_toggle_theme, icon_color=muted_color(page), icon_size=20)
    )
    return ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Text(title, size=26, weight=ft.FontWeight.W_700),
            ft.Row(spacing=4, controls=right),
        ],
    )


# ── empty state ───────────────────────────────────────────────────────────────

def empty_state(
    message: str,
    icon: str = ft.Icons.INBOX,
    *,
    cta_text: str | None = None,
    on_cta: Callable[[], None] | None = None,
) -> ft.Container:
    controls: list[ft.Control] = [
        ft.Icon(icon, size=56, color=ft.Colors.with_opacity(0.25, TEXT_MUTED)),
        ft.Text(
            message,
            color=ft.Colors.with_opacity(0.5, TEXT_MUTED),
            size=14,
            text_align=ft.TextAlign.CENTER,
        ),
    ]
    if cta_text and on_cta:
        controls.append(
            ft.FilledButton(
                cta_text,
                on_click=lambda _: on_cta(),
                style=ft.ButtonStyle(bgcolor=GREEN, color=ft.Colors.WHITE),
            )
        )
    return ft.Container(
        expand=True,
        alignment=ft.Alignment(0, 0),
        padding=40,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=16,
            controls=controls,
        ),
    )


# ── карточки ──────────────────────────────────────────────────────────────────

def card_container(
    page: ft.Page,
    content: ft.Control,
    *,
    expand: bool | int = True,
    padding: int = 20,
) -> ft.Container:
    return ft.Container(
        bgcolor=card_bgcolor(page),
        border_radius=RADIUS_LG,
        padding=padding,
        expand=expand,
        shadow=card_shadow(),
        content=content,
    )


def metric_card(
    page: ft.Page,
    title: str,
    value: str,
    delta: str,
    delta_color: str,
    icon: str,
    icon_bg: str,
) -> ft.Container:
    controls: list[ft.Control] = [
        ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Text(title, color=muted_color(page), size=12),
                ft.Container(
                    bgcolor=icon_bg, border_radius=RADIUS_XL,
                    width=34, height=34,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, color=delta_color, size=18),
                ),
            ],
        ),
        ft.Text(value, size=22, weight=ft.FontWeight.W_700),
    ]
    if delta:
        controls.append(
            ft.Text(delta, color=delta_color, size=12, weight=ft.FontWeight.W_500)
        )
    return card_container(page, ft.Column(spacing=6, controls=controls))


def section_card(
    page: ft.Page,
    title: str,
    controls: list[ft.Control],
    *,
    action_text: str | None = None,
    on_action: Callable[[], None] | None = None,
) -> ft.Container:
    header_controls: list[ft.Control] = [
        ft.Text(title, weight=ft.FontWeight.W_700, size=14)
    ]
    if action_text and on_action:
        header_controls.append(
            ft.TextButton(
                action_text,
                style=ft.ButtonStyle(color=GREEN),
                on_click=lambda _: on_action(),
            )
        )
    return card_container(
        page,
        ft.Column(
            spacing=8,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=header_controls,
                ),
                *controls,
            ],
        ),
    )


def progress_row(
    name: str,
    icon: str,
    icon_color: str,
    current_cents: int,
    target_cents: int,
) -> ft.Container:
    ratio = min(1.0, current_cents / target_cents) if target_cents else 0.0
    return ft.Container(
        padding=ft.Padding(0, 6, 0, 6),
        content=ft.Column(
            spacing=6,
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            bgcolor=ft.Colors.with_opacity(0.1, icon_color),
                            border_radius=RADIUS_SM, width=28, height=28,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(icon, size=16, color=icon_color),
                        ),
                        ft.Column(
                            spacing=2, expand=True,
                            controls=[
                                ft.Text(name, weight=ft.FontWeight.W_600, size=13),
                                ft.Text(
                                    f"{format_rub(current_cents)} / {format_rub(target_cents)} ₽",
                                    color=TEXT_MUTED, size=11,
                                ),
                            ],
                        ),
                        ft.Text(f"{int(ratio * 100)}%", color=TEXT_MUTED, size=12),
                    ],
                ),
                ft.ProgressBar(
                    value=ratio, color=icon_color,
                    bgcolor=ft.Colors.with_opacity(0.15, icon_color),
                    bar_height=6, border_radius=3,
                ),
            ],
        ),
    )


def tx_row(tx: Transaction, cat_name: str | None, cat_color: str | None = None) -> ft.Container:
    is_income = tx.type == TransactionType.INCOME
    sign = "+" if is_income else "−"
    color = GREEN if is_income else RED
    icon = ft.Icons.ARROW_UPWARD if is_income else ft.Icons.ARROW_DOWNWARD
    icon_bg = GREEN_SOFT if is_income else RED_SOFT
    accent = cat_color or (GREEN if is_income else RED)

    left: ft.Control = (
        ft.Column(
            spacing=2, expand=True,
            controls=[
                ft.Text(
                    tx.note if tx.note else (cat_name or "Без категории"),
                    weight=ft.FontWeight.W_600, size=13,
                ),
                ft.Text(cat_name or "", color=TEXT_MUTED, size=11),
            ],
        ) if cat_name and tx.note else
        ft.Text(
            tx.note or cat_name or "Без категории",
            weight=ft.FontWeight.W_600, size=13, expand=True,
        )
    )

    return ft.Container(
        padding=ft.Padding(0, 10, 0, 10),
        content=ft.Row(
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(width=3, height=36, bgcolor=accent, border_radius=2),
                ft.Container(width=8),
                ft.Container(
                    bgcolor=icon_bg, border_radius=RADIUS_SM, width=32, height=32,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Icon(icon, size=16, color=color),
                ),
                ft.Container(width=10),
                left,
                ft.Container(width=10),
                ft.Column(
                    spacing=2, horizontal_alignment=ft.CrossAxisAlignment.END,
                    controls=[
                        ft.Text(
                            f"{sign}{format_rub(tx.amount_cents)} ₽",
                            weight=ft.FontWeight.W_700, color=color, size=13,
                        ),
                        ft.Text(tx.occurred_at.strftime("%d.%m"), color=TEXT_MUTED, size=11),
                    ],
                ),
            ],
        ),
    )


# ── date group header ─────────────────────────────────────────────────────────

def date_group_header(label: str) -> ft.Container:
    return ft.Container(
        padding=ft.Padding(0, 12, 0, 4),
        content=ft.Text(label, size=12, weight=ft.FontWeight.W_600, color=TEXT_MUTED),
    )


# ── сайдбар ───────────────────────────────────────────────────────────────────

_NAV_ITEMS = [
    ("overview",    "Главная",      ft.Icons.HOME_OUTLINED),
    ("operations",  "Операции",     ft.Icons.SWAP_HORIZ),
    ("reports",     "Аналитика",    ft.Icons.PIE_CHART_OUTLINE),
    ("goals",       "Цели",         ft.Icons.FLAG_OUTLINED),
    ("reminders",   "Напоминания",  ft.Icons.NOTIFICATIONS_OUTLINED),
    ("categories",  "Категории",    ft.Icons.LABEL_OUTLINE),
    ("settings",    "Настройки",    ft.Icons.SETTINGS_OUTLINED),
]


def _sidebar_item(
    page: ft.Page,
    label: str,
    icon: str,
    *,
    selected: bool = False,
    on_click: Callable[[Any], None] | None = None,
) -> ft.Container:
    selected_bg = ft.Colors.with_opacity(0.12, GREEN)

    return ft.Container(
        padding=ft.Padding(12, 10, 12, 10),
        border_radius=RADIUS_MD,
        bgcolor=selected_bg if selected else None,
        on_click=on_click,
        ink=on_click is not None,
        animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        content=ft.Row(
            spacing=12,
            controls=[
                ft.Container(
                    width=4, height=20,
                    bgcolor=GREEN if selected else ft.Colors.TRANSPARENT,
                    border_radius=2,
                    animate=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
                ),
                ft.Icon(
                    icon,
                    color=GREEN if selected else muted_color(page),
                    size=18,
                ),
                ft.Text(
                    label,
                    color=GREEN if selected else muted_color(page),
                    weight=ft.FontWeight.W_600 if selected else ft.FontWeight.W_400,
                    size=14,
                    expand=True,
                ),
            ],
        ),
    )


def build_sidebar(
    page: ft.Page,
    current_route: str,
    navigate: Callable[[str], None],
) -> ft.Container:
    return ft.Container(
        width=224,
        bgcolor=sidebar_bgcolor(page),
        padding=ft.Padding(12, 16, 12, 16),
        shadow=ft.BoxShadow(
            spread_radius=0, blur_radius=16,
            color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
            offset=ft.Offset(2, 0),
        ),
        content=ft.Column(
            spacing=2,
            controls=[
                ft.Container(
                    padding=ft.Padding(8, 4, 8, 20),
                    content=ft.Row(
                        spacing=10,
                        controls=[
                            ft.Container(
                                bgcolor=GREEN, border_radius=RADIUS_MD,
                                width=34, height=34,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(
                                    ft.Icons.ACCOUNT_BALANCE_WALLET,
                                    color=ft.Colors.WHITE, size=18,
                                ),
                            ),
                            ft.Text("Finance", size=17, weight=ft.FontWeight.W_700),
                        ],
                    ),
                ),
                *[
                    _sidebar_item(
                        page, label, icon,
                        selected=(current_route == route),
                        on_click=lambda _, r=route: navigate(r),
                    )
                    for route, label, icon in _NAV_ITEMS
                ],
            ],
        ),
    )


# ── icon picker ───────────────────────────────────────────────────────────────

def icon_picker(
    current: str | None,
    on_select: Callable[[str], None],
) -> ft.Control:
    """Сетка 5×4 кликабельных иконок. Выбранная подсвечена."""
    state = {"value": current or DEFAULT_ICON}

    cells: list[ft.Control] = []

    def _make_cell(name: str, ico: str) -> ft.Container:
        def _click(_: ft.ControlEvent, _ico: str = ico) -> None:
            state["value"] = _ico
            on_select(_ico)
            for c in cells:
                sel = c.data == _ico
                c.bgcolor = ft.Colors.with_opacity(0.15, GREEN) if sel else None
                c.border = ft.Border.all(2, GREEN) if sel else ft.Border.all(1, ft.Colors.with_opacity(0.1, TEXT_MUTED))
                c.content.color = GREEN if sel else TEXT_MUTED
            # force update по родителю
            cells[0].page.update() if cells and cells[0].page else None

        is_sel = ico == state["value"]
        cell = ft.Container(
            data=ico,
            width=44, height=44,
            border_radius=RADIUS_MD,
            bgcolor=ft.Colors.with_opacity(0.15, GREEN) if is_sel else None,
            border=ft.Border.all(2, GREEN) if is_sel else ft.Border.all(1, ft.Colors.with_opacity(0.1, TEXT_MUTED)),
            alignment=ft.Alignment(0, 0),
            tooltip=name,
            on_click=_click,
            ink=True,
            content=ft.Icon(getattr(ft.Icons, ico), size=20, color=GREEN if is_sel else TEXT_MUTED),
        )
        cells.append(cell)
        return cell

    grid = ft.GridView(
        runs_count=5,
        max_extent=48,
        child_aspect_ratio=1.0,
        spacing=6,
        run_spacing=6,
        controls=[_make_cell(name, ico) for name, ico in ICON_OPTIONS],
        height=210,
    )
    return grid


# ── color picker ──────────────────────────────────────────────────────────────

def color_picker(
    current: str | None,
    on_select: Callable[[str], None],
) -> ft.Control:
    """Ряд цветных кружков. Выбранный отмечен галочкой."""
    state = {"value": current or DEFAULT_COLOR}
    dots: list[ft.Container] = []

    def _make_dot(hex_color: str) -> ft.Container:
        def _click(_: ft.ControlEvent, _c: str = hex_color) -> None:
            state["value"] = _c
            on_select(_c)
            for d in dots:
                sel = d.data == _c
                d.content = ft.Icon(ft.Icons.CHECK, size=14, color=ft.Colors.WHITE) if sel else None
            dots[0].page.update() if dots and dots[0].page else None

        is_sel = hex_color == state["value"]
        dot = ft.Container(
            data=hex_color,
            width=32, height=32,
            border_radius=16,
            bgcolor=hex_color,
            alignment=ft.Alignment(0, 0),
            tooltip=hex_color,
            on_click=_click,
            ink=True,
            content=ft.Icon(ft.Icons.CHECK, size=14, color=ft.Colors.WHITE) if is_sel else None,
        )
        dots.append(dot)
        return dot

    return ft.Row(
        spacing=8,
        wrap=True,
        controls=[_make_dot(c) for c in COLOR_OPTIONS],
    )
