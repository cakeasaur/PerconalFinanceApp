from __future__ import annotations

import sqlite3
from collections.abc import Callable

import flet as ft

from ...infra.db.connection import transaction as db_tx
from ...infra.db.repositories import Category
from ...infra.logging import get_logger
from ..components import (
    DEFAULT_COLOR,
    DEFAULT_ICON,
    close_dialog,
    color_picker,
    confirm_dialog,
    empty_state,
    icon_picker,
    open_dialog,
    resolve_icon,
    screen_header,
)
from ..state import Repos
from ..theme import GREEN, RED, TEXT_MUTED, page_bgcolor, show_snack

log = get_logger("pfm.ui.categories")

_KIND_LABELS = {"income": "Доход", "expense": "Расход", "both": "Оба"}
_KIND_COLORS = {"income": "#3B82F6", "expense": RED, "both": TEXT_MUTED}


def _kind_badge(kind: str) -> ft.Container:
    color = _KIND_COLORS.get(kind, TEXT_MUTED)
    label = _KIND_LABELS.get(kind, kind)
    return ft.Container(
        border_radius=20,
        padding=ft.Padding(10, 3, 10, 3),
        bgcolor=ft.Colors.with_opacity(0.12, color),
        content=ft.Text(label, size=11, color=color, weight=ft.FontWeight.W_600),
    )


def _category_dialog(
    page: ft.Page,
    repos: Repos,
    on_saved: Callable[[], None],
    existing: Category | None = None,
) -> None:
    sel = {
        "icon": existing.icon or DEFAULT_ICON if existing else DEFAULT_ICON,
        "color": existing.color or DEFAULT_COLOR if existing else DEFAULT_COLOR,
    }

    name_f = ft.TextField(
        label="Название", autofocus=True, border_radius=10,
        value=existing.name if existing else "",
    )
    kind_dd = ft.Dropdown(
        label="Тип операций",
        border_radius=10,
        value=existing.kind if existing else "both",
        options=[
            ft.dropdown.Option(key="both", text="Оба"),
            ft.dropdown.Option(key="income", text="Доход"),
            ft.dropdown.Option(key="expense", text="Расход"),
        ],
    )
    err = ft.Text("", color=RED, size=12)

    def do_save(_: ft.ControlEvent) -> None:
        err.value = ""
        try:
            name = name_f.value.strip()
            if not name:
                raise ValueError("Введите название")
            kind = kind_dd.value or "both"
            with db_tx(repos.cat.conn):
                if existing is None:
                    repos.cat.create(name=name, kind=kind,
                                     icon=sel["icon"], color=sel["color"])
                else:
                    repos.cat.update(category_id=existing.id, name=name, kind=kind,
                                     icon=sel["icon"], color=sel["color"])
            close_dialog(page, dlg)
            action = "создана" if existing is None else "обновлена"
            show_snack(page, f"Категория «{name}» {action}")
            on_saved()
        except sqlite3.IntegrityError:
            err.value = "Категория с таким названием уже существует."
            page.update()
        except ValueError as exc:
            err.value = str(exc)
            page.update()
        except Exception as exc:
            log.exception("category save failed")
            err.value = f"Ошибка: {exc}"
            page.update()

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("Новая категория" if existing is None else "Редактировать категорию"),
        content=ft.Container(
            width=400,
            content=ft.Column(
                tight=True, spacing=14,
                controls=[
                    name_f,
                    kind_dd,
                    ft.Text("Иконка", size=12, color=TEXT_MUTED),
                    icon_picker(sel["icon"], lambda v: sel.update({"icon": v})),
                    ft.Text("Цвет", size=12, color=TEXT_MUTED),
                    color_picker(sel["color"], lambda v: sel.update({"color": v})),
                    err,
                ],
            ),
        ),
        actions=[
            ft.TextButton("Отмена", on_click=lambda _: close_dialog(page, dlg)),
            ft.FilledButton("Сохранить", on_click=do_save),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    open_dialog(page, dlg)


def _category_row(
    page: ft.Page,
    repos: Repos,
    cat: Category,
    on_refresh: Callable[[], None],
) -> ft.Container:
    def do_delete(_: ft.ControlEvent) -> None:
        confirm_dialog(
            page,
            f"Удалить категорию «{cat.name}»? Операции останутся без категории.",
            on_confirm=lambda: _do_cat_delete(),
        )

    def _do_cat_delete() -> None:
        with db_tx(repos.cat.conn):
            repos.cat.delete(category_id=cat.id)
        show_snack(page, f"Категория «{cat.name}» удалена", color=RED)
        on_refresh()

    icon_val = resolve_icon(cat.icon)
    _kind_fallback = {"income": "#3B82F6", "expense": RED, "both": "#8B5CF6"}
    color = cat.color or _kind_fallback.get(cat.kind, "#8B5CF6")
    return ft.Container(
        padding=ft.Padding(0, 10, 0, 10),
        border=ft.Border(
            bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.07, ft.Colors.ON_SURFACE))
        ),
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=36, height=36, border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.12, color),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Icon(icon_val, size=18, color=color),
                ),
                ft.Container(width=10),
                ft.Text(cat.name, expand=True, weight=ft.FontWeight.W_500, size=14),
                _kind_badge(cat.kind),
                ft.IconButton(
                    ft.Icons.EDIT_OUTLINED, icon_color=TEXT_MUTED, icon_size=18,
                    tooltip="Редактировать",
                    on_click=lambda _, c=cat: _category_dialog(page, repos, on_refresh, c),
                ),
                ft.IconButton(
                    ft.Icons.DELETE_OUTLINE, icon_color=TEXT_MUTED, icon_size=18,
                    tooltip="Удалить",
                    on_click=do_delete,
                ),
            ],
        ),
    )


def build_categories(
    page: ft.Page,
    repos: Repos,
    navigate: Callable[[str], None],
    rebuild: Callable[[], None],
) -> ft.Control:
    categories = repos.cat.list_all()

    add_btn = ft.FilledButton(
        "Новая категория", icon=ft.Icons.ADD,
        on_click=lambda _: _category_dialog(page, repos, rebuild),
        style=ft.ButtonStyle(bgcolor=GREEN, color=ft.Colors.WHITE),
    )
    header = screen_header(page, "Категории", rebuild, actions=[add_btn])

    hint = ft.Text(
        "Категории используются при добавлении операций. "
        "Удаление категории не удаляет связанные операции.",
        color=TEXT_MUTED, size=12,
    )

    if not categories:
        body: list[ft.Control] = [
            empty_state(
                "Категорий нет.",
                ft.Icons.LABEL_OUTLINE,
                cta_text="Создать категорию",
                on_cta=lambda: _category_dialog(page, repos, rebuild),
            )
        ]
    else:
        body = [
            hint,
            ft.Column(
                spacing=0,
                controls=[_category_row(page, repos, c, rebuild) for c in categories],
            ),
        ]

    content = ft.Column(
        spacing=16, expand=True, scroll=ft.ScrollMode.AUTO,
        controls=[header, *body],
    )

    return ft.Container(content=content, expand=True, padding=24, bgcolor=page_bgcolor(page))
