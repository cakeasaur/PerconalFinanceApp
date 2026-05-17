from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import flet as ft

from ...infra.db.connection import transaction as db_tx
from ...infra.db.repositories import Reminder
from ...infra.logging import get_logger
from ..components import (
    DEFAULT_COLOR,
    DEFAULT_ICON,
    close_dialog,
    color_picker,
    empty_state,
    icon_picker,
    open_dialog,
    resolve_icon,
    screen_header,
)
from ..formatting import RECURRENCE_LABELS, RECURRENCE_UI_TO_VALUE, format_rub, parse_money
from ..state import Repos
from ..theme import GREEN, PURPLE, RED, TEXT_MUTED, page_bgcolor, show_snack

log = get_logger("pfm.ui.reminders")

_ORANGE = "#F97316"


def _reminder_dialog(
    page: ft.Page,
    repos: Repos,
    on_saved: Callable[[], None],
) -> None:
    sel = {"icon": DEFAULT_ICON, "color": DEFAULT_COLOR}
    name_f = ft.TextField(label="Название", autofocus=True, border_radius=10)
    due_f = ft.TextField(
        label="Дата и время (ГГГГ-ММ-ДД ЧЧ:ММ)",
        value=datetime.now(UTC).strftime("%Y-%m-%d %H:%M"),
        border_radius=10,
    )
    recurrence_dd = ft.Dropdown(
        label="Повторение",
        value=RECURRENCE_LABELS[0],
        options=[ft.dropdown.Option(v) for v in RECURRENCE_LABELS],
        border_radius=10,
    )
    amount_f = ft.TextField(
        label="Сумма (₽, необязательно)", keyboard_type=ft.KeyboardType.NUMBER,
        border_radius=10,
    )
    note_f = ft.TextField(label="Заметка (необязательно)", border_radius=10)
    err = ft.Text("", color=RED, size=12)

    def do_save(_: ft.ControlEvent) -> None:
        err.value = ""
        try:
            name = name_f.value.strip()
            if not name:
                raise ValueError("Введите название")
            due_dt = datetime.strptime(
                (due_f.value or "").strip(), "%Y-%m-%d %H:%M"
            ).replace(tzinfo=UTC)
            recurrence = RECURRENCE_UI_TO_VALUE.get(recurrence_dd.value or "", "none")
            amount_text = (amount_f.value or "").strip()
            amount_cents = parse_money(amount_text) if amount_text else None
            note = note_f.value.strip() or None
            with db_tx(repos.reminder.conn):
                repos.reminder.create(
                    name=name, due_at=due_dt, recurrence=recurrence,
                    amount_cents=amount_cents, note=note,
                    icon=sel["icon"], color=sel["color"],
                )
            close_dialog(page, dlg)
            on_saved()
        except ValueError as exc:
            err.value = str(exc)
            page.update()
        except Exception as exc:
            log.exception("reminder save failed")
            err.value = f"Ошибка: {exc}"
            page.update()

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("Новое напоминание"),
        content=ft.Container(
            width=420,
            content=ft.Column(
                tight=True, spacing=12,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    name_f, due_f, recurrence_dd, amount_f, note_f,
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


def _reminder_card(
    page: ft.Page,
    repos: Repos,
    r: Reminder,
    now: datetime,
    on_refresh: Callable[[], None],
) -> ft.Container:
    icon = resolve_icon(r.icon)
    accent = r.color or _ORANGE
    overdue = r.due_at < now
    due_color = RED if overdue else (_ORANGE if (r.due_at - now).days < 3 else TEXT_MUTED)
    due_label = r.due_at.strftime("%d.%m.%Y %H:%M") + (" · Просрочено" if overdue else "")

    rec_map = {"none": "", "daily": "· Ежедневно", "weekly": "· Еженедельно",
               "monthly": "· Ежемесячно"}
    rec_label = rec_map.get(r.recurrence, "")

    amount_label = f"{format_rub(r.amount_cents)} ₽" if r.amount_cents else ""

    def do_done(_: ft.ControlEvent) -> None:
        with db_tx(repos.reminder.conn):
            repos.reminder.mark_done(reminder_id=r.id)
        show_snack(page, f"✓ «{r.name}» отмечено выполненным")
        on_refresh()

    def do_delete(_: ft.ControlEvent) -> None:
        with db_tx(repos.reminder.conn):
            repos.reminder.delete(reminder_id=r.id)
        show_snack(page, "Напоминание удалено", color=RED)
        on_refresh()

    return ft.Container(
        bgcolor=page.theme_mode == ft.ThemeMode.DARK and "#1E293B" or "#FFFFFF",
        border_radius=12,
        padding=16,
        shadow=ft.BoxShadow(blur_radius=8,
                            color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
                            offset=ft.Offset(0, 2)),
        content=ft.Row(
            controls=[
                ft.Container(
                    bgcolor=ft.Colors.with_opacity(0.12, accent), border_radius=8,
                    width=36, height=36, alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, size=18, color=accent),
                ),
                ft.Column(spacing=2, expand=True, controls=[
                    ft.Row(controls=[
                        ft.Text(r.name, weight=ft.FontWeight.W_600, size=14),
                        *([ ft.Text(amount_label, color=PURPLE, size=13,
                                   weight=ft.FontWeight.W_600)] if amount_label else []),
                    ]),
                    ft.Text(
                        f"{due_label} {rec_label}".strip(),
                        color=due_color, size=11,
                    ),
                    *([ ft.Text(r.note, color=TEXT_MUTED, size=11)] if r.note else []),
                ]),
                ft.Row(spacing=4, controls=[
                    ft.IconButton(
                        ft.Icons.CHECK_CIRCLE_OUTLINE, icon_color=GREEN,
                        tooltip="Отметить выполненным",
                        on_click=do_done,
                    ),
                    ft.IconButton(
                        ft.Icons.DELETE_OUTLINE, icon_color=TEXT_MUTED,
                        tooltip="Удалить",
                        on_click=do_delete,
                    ),
                ]),
            ],
        ),
    )


def build_reminders(
    page: ft.Page,
    repos: Repos,
    navigate: Callable[[str], None],
    rebuild: Callable[[], None],
) -> ft.Control:
    reminders = repos.reminder.list_due_sorted()
    now = datetime.now(UTC)

    add_btn = ft.FilledButton(
        "Добавить", icon=ft.Icons.ADD,
        on_click=lambda _: _reminder_dialog(page, repos, rebuild),
        style=ft.ButtonStyle(bgcolor=GREEN, color=ft.Colors.WHITE),
    )
    header = screen_header(page, "Напоминания", rebuild, actions=[add_btn])

    body: list[ft.Control] = (
        [empty_state(
            "Напоминаний пока нет.\nДобавьте дату платежа и повтор.",
            ft.Icons.ALARM_OFF,
            cta_text="Добавить напоминание",
            on_cta=lambda: _reminder_dialog(page, repos, rebuild),
        )]
        if not reminders else
        [_reminder_card(page, repos, r, now, rebuild) for r in reminders]
    )

    content = ft.Column(
        spacing=16, expand=True, scroll=ft.ScrollMode.AUTO,
        controls=[header, *body],
    )

    return ft.Container(content=content, expand=True, padding=24, bgcolor=page_bgcolor(page))
