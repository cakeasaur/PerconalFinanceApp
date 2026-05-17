from __future__ import annotations

from collections.abc import Callable

import flet as ft

from ...core.csv_io import export_csv, parse_csv
from ...infra.db.connection import transaction as db_tx
from ...infra.logging import get_logger
from ..components import close_dialog, open_dialog, screen_header
from ..state import Repos
from ..theme import GREEN, GREEN_SOFT, RED, TEXT_MUTED, page_bgcolor, show_snack

MIN_PASSPHRASE_LEN = 8  # зеркало из crypto.py — не импортируем чтобы не тянуть flet в тесты

log = get_logger("pfm.ui.settings")


def _section(title: str, controls: list[ft.Control]) -> ft.Column:
    return ft.Column(
        spacing=12,
        controls=[
            ft.Text(title, size=14, weight=ft.FontWeight.W_700, color=TEXT_MUTED),
            *controls,
        ],
    )


def _change_password_dialog(
    page: ft.Page,
    on_change_password: Callable[[str, str], str | None],
) -> None:
    old_f = ft.TextField(
        label="Текущий пароль", password=True, can_reveal_password=True,
        autofocus=True, border_radius=10,
    )
    new_f = ft.TextField(
        label="Новый пароль", password=True, can_reveal_password=True,
        border_radius=10,
    )
    confirm_f = ft.TextField(
        label="Повторите новый пароль", password=True, can_reveal_password=True,
        border_radius=10,
    )
    err = ft.Text("", color=RED, size=12)

    def do_save(_: ft.ControlEvent) -> None:
        err.value = ""
        old = old_f.value or ""
        new = new_f.value or ""
        confirm = confirm_f.value or ""
        if not old:
            err.value = "Введите текущий пароль"
            page.update()
            return
        if len(new) < MIN_PASSPHRASE_LEN:
            err.value = f"Новый пароль слишком короткий (минимум {MIN_PASSPHRASE_LEN} символов)"
            page.update()
            return
        if new != confirm:
            err.value = "Пароли не совпадают"
            page.update()
            return
        error = on_change_password(old, new)
        if error:
            err.value = error
            page.update()
            return
        close_dialog(page, dlg)
        show_snack(page, "Пароль изменён.")

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("Смена пароля"),
        content=ft.Container(
            width=380,
            content=ft.Column(
                tight=True, spacing=12,
                controls=[old_f, new_f, confirm_f, err],
            ),
        ),
        actions=[
            ft.TextButton("Отмена", on_click=lambda _: close_dialog(page, dlg)),
            ft.FilledButton("Сохранить", on_click=do_save),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    open_dialog(page, dlg)


def _csv_export(page: ft.Page, repos: Repos) -> None:
    try:
        stored = repos.tx.list_all()
        txs = [s.transaction for s in stored]
        csv_bytes = export_csv(txs).encode("utf-8")
        fp = ft.FilePicker()
        page.overlay.append(fp)
        page.update()
        fp.save_file(
            file_name="transactions.csv",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["csv"],
            src_bytes=csv_bytes,
        )
        page.overlay.remove(fp)
        show_snack(page, f"Экспортировано {len(txs)} операций")
    except Exception:
        log.exception("csv export failed")
        show_snack(page, "Ошибка экспорта", color=RED)


def _csv_import(page: ft.Page, repos: Repos, rebuild: Callable[[], None]) -> None:
    try:
        fp = ft.FilePicker()
        page.overlay.append(fp)
        page.update()
        files = fp.pick_files(
            dialog_title="Выбрать CSV файл с транзакциями",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["csv"],
            with_data=True,
        )
        page.overlay.remove(fp)
        if not files:
            return
        raw = files[0].bytes
        if raw is None:
            show_snack(page, "Не удалось прочитать файл", color=RED)
            return
        text = raw.decode("utf-8")
        txs = parse_csv(text)
        with db_tx(repos.tx.conn):
            for tx in txs:
                repos.tx.create(tx)
        show_snack(page, f"Импортировано {len(txs)} операций")
        rebuild()
    except ValueError as exc:
        show_snack(page, f"Ошибка формата: {exc}", color=RED)
    except Exception:
        log.exception("csv import failed")
        show_snack(page, "Ошибка импорта", color=RED)


def build_settings(
    page: ft.Page,
    navigate: Callable[[str], None],
    rebuild: Callable[[], None],
    *,
    repos: Repos | None = None,
    on_change_password: Callable[[str, str], str | None] | None,
) -> ft.Control:
    if on_change_password is not None:
        security_controls: list[ft.Control] = [
            ft.Container(
                bgcolor=GREEN_SOFT if page.theme_mode == ft.ThemeMode.LIGHT else "#1A2E1A",
                border_radius=12,
                padding=16,
                content=ft.Row(
                    spacing=16,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            bgcolor=ft.Colors.with_opacity(0.15, GREEN),
                            border_radius=10, width=40, height=40,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.LOCK_OUTLINE, color=GREEN, size=20),
                        ),
                        ft.Column(
                            spacing=2, expand=True,
                            controls=[
                                ft.Text("Шифрование БД включено", weight=ft.FontWeight.W_600, size=14),
                                ft.Text(
                                    "База данных зашифрована AES-256-GCM. "
                                    "Данные недоступны без пароля.",
                                    color=TEXT_MUTED, size=12,
                                ),
                            ],
                        ),
                    ],
                ),
            ),
            ft.OutlinedButton(
                "Сменить пароль",
                icon=ft.Icons.KEY_OUTLINED,
                on_click=lambda _: _change_password_dialog(page, on_change_password),
            ),
        ]
    else:
        security_controls = [
            ft.Container(
                border_radius=12, padding=16,
                border=ft.Border(
                    top=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                    bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                    left=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                    right=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                ),
                content=ft.Row(
                    spacing=12,
                    controls=[
                        ft.Icon(ft.Icons.LOCK_OPEN_OUTLINED, color=TEXT_MUTED, size=20),
                        ft.Text(
                            "Шифрование отключено (PF_DISABLE_ENCRYPTION=1)",
                            color=TEXT_MUTED, size=13,
                        ),
                    ],
                ),
            ),
        ]

    author_controls: list[ft.Control] = [
        ft.Container(
            border_radius=12, padding=16,
            border=ft.Border(
                top=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                left=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                right=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            ),
            content=ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        bgcolor=ft.Colors.with_opacity(0.1, GREEN),
                        border_radius=20, width=36, height=36,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Icon(ft.Icons.PERSON_OUTLINE, color=GREEN, size=18),
                    ),
                    ft.Column(
                        spacing=2,
                        controls=[
                            ft.Text("Автор", color=TEXT_MUTED, size=12),
                            ft.Text("@cakeasaur", size=14, weight=ft.FontWeight.W_600),
                        ],
                    ),
                ],
            ),
        ),
    ]

    about_controls: list[ft.Control] = [
        ft.Container(
            border_radius=12, padding=16,
            border=ft.Border(
                top=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                left=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                right=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            ),
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Row(controls=[
                        ft.Text("Приложение", color=TEXT_MUTED, size=13, expand=True),
                        ft.Text("Личные финансы (вариант 43)", size=13),
                    ]),
                    ft.Row(controls=[
                        ft.Text("Версия", color=TEXT_MUTED, size=13, expand=True),
                        ft.Text("v0.1.0", size=13),
                    ]),
                    ft.Row(controls=[
                        ft.Text("Стек", color=TEXT_MUTED, size=13, expand=True),
                        ft.Text("Python 3.12 · Flet 0.85 · SQLite", size=13),
                    ]),
                ],
            ),
        ),
    ]

    data_controls: list[ft.Control] = [
        ft.Row(spacing=12, controls=[
            ft.OutlinedButton(
                "Экспорт CSV",
                icon=ft.Icons.DOWNLOAD_OUTLINED,
                on_click=lambda _: _csv_export(page, repos) if repos else None,
                disabled=repos is None,
            ),
            ft.OutlinedButton(
                "Импорт CSV",
                icon=ft.Icons.UPLOAD_OUTLINED,
                on_click=lambda _: _csv_import(page, repos, rebuild) if repos else None,
                disabled=repos is None,
            ),
        ]),
        ft.Text(
            "Экспорт: сохраняет все транзакции в CSV-файл.\n"
            "Импорт: добавляет транзакции из CSV (дубли не проверяются).",
            color=TEXT_MUTED, size=12,
        ),
    ]

    header = screen_header(page, "Настройки", rebuild)

    content = ft.Column(
        spacing=28, expand=True, scroll=ft.ScrollMode.AUTO,
        controls=[
            header,
            _section("Безопасность", security_controls),
            _section("Данные", data_controls),
            _section("О приложении", about_controls),
            _section("Разработчик", author_controls),
        ],
    )

    return ft.Container(content=content, expand=True, padding=24, bgcolor=page_bgcolor(page))
