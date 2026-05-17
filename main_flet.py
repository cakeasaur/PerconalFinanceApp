"""Flet entrypoint для приложения «Личные финансы».

    py -3.12 main_flet.py

При первом запуске предложит придумать пароль → создаст зашифрованную БД.
БД работает только в памяти процесса; после каждого коммита и при закрытии
содержимое сериализуется, шифруется и атомарно пишется на диск.

Отключить шифрование (для отладки): PF_DISABLE_ENCRYPTION=1 py -3.12 main_flet.py
В этом режиме используется plaintext-файл на диске (без in-memory).
"""

from __future__ import annotations

import atexit
import glob
import os
import sqlite3
import tempfile

import flet as ft

from src.infra.db.connection import (
    connect,
    connect_in_memory,
    serialize_db,
    set_autosave_hook,
)
from src.infra.db.connection import transaction as db_tx
from src.infra.db.repositories import (
    CategoryRepository,
    GoalRepository,
    ReminderRepository,
    TransactionRepository,
)
from src.infra.db.schema import init_schema
from src.infra.logging import get_logger, setup_logging
from src.infra.security.crypto import (
    MIN_PASSPHRASE_LEN,
    InvalidPasswordError,
    decrypt_file_to_bytes,
    encrypt_bytes_to_path,
)
from src.ui_flet.components import build_sidebar, close_dialog, open_dialog
from src.ui_flet.screens.categories import build_categories
from src.ui_flet.screens.goals import build_goals
from src.ui_flet.screens.operations import build_operations
from src.ui_flet.screens.overview import build_overview
from src.ui_flet.screens.reminders import build_reminders
from src.ui_flet.screens.reports import build_reports
from src.ui_flet.screens.settings import build_settings
from src.ui_flet.state import Repos
from src.ui_flet.theme import (
    DATA_DIR,
    ENCRYPTED_DB_PATH,
    GREEN,
    PLAINTEXT_DB_PATH,
    RED,
    make_theme,
    page_bgcolor,
)

setup_logging(DATA_DIR / "logs")
log = get_logger("pfm.app")

# ── шифрование ────────────────────────────────────────────────────────────────

def encryption_enabled() -> bool:
    if str(os.environ.get("PF_DISABLE_ENCRYPTION", "")).strip() in {"1", "true", "yes", "on"}:
        return False
    return True


def _cleanup_legacy_temp_dbs() -> None:
    """Removes plaintext SQLite files from previous app versions."""
    for leftover in glob.glob(os.path.join(tempfile.gettempdir(), "pfm_*.sqlite3")):
        try:
            os.unlink(leftover)
            log.info("removed legacy plaintext db: %s", leftover)
        except OSError as exc:
            log.warning("cannot remove legacy temp db %s: %s", leftover, exc)


# ── основной entrypoint ───────────────────────────────────────────────────────

def main(page: ft.Page) -> None:
    log.info("app start: encryption=%s data_dir=%s", encryption_enabled(), DATA_DIR)
    page.title = "Finance"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = make_theme(dark=False)
    page.dark_theme = make_theme(dark=True)
    page.padding = 0
    page.window.width = 1280
    page.window.height = 820

    _cleanup_legacy_temp_dbs()

    app_state: dict = {}
    ctx: dict = {"repos": None, "passphrase": "", "conn": None}

    # ── layout: sidebar + AnimatedSwitcher ───────────────────────────────────
    content_switcher = ft.AnimatedSwitcher(
        content=ft.Container(expand=True),
        transition=ft.AnimatedSwitcherTransition.FADE,
        duration=160,
        switch_in_curve=ft.AnimationCurve.EASE_OUT,
        switch_out_curve=ft.AnimationCurve.EASE_IN,
        expand=True,
    )
    layout_row = ft.Row(spacing=0, expand=True, controls=[content_switcher])

    def rebuild() -> None:
        if ctx["repos"] is None:
            return
        repos: Repos = ctx["repos"]
        route: str = app_state.get("route", "overview")
        page.bgcolor = page_bgcolor(page)
        sidebar = build_sidebar(page, route, navigate)
        content_switcher.content = _build_route(route, repos)
        layout_row.controls = [sidebar, content_switcher]
        page.update()

    def navigate(route: str) -> None:
        app_state["route"] = route
        rebuild()

    def change_password(old: str, new: str) -> str | None:
        if old != ctx["passphrase"]:
            return "Неверный текущий пароль"
        ctx["passphrase"] = new
        autosave()
        return None

    def _build_route(route: str, repos: Repos) -> ft.Control:
        if route == "overview":
            return build_overview(page, repos, app_state, navigate, rebuild)
        if route == "operations":
            return build_operations(page, repos, app_state, navigate, rebuild)
        if route == "goals":
            return build_goals(page, repos, navigate, rebuild)
        if route == "reminders":
            return build_reminders(page, repos, navigate, rebuild)
        if route == "reports":
            return build_reports(page, repos, app_state, navigate, rebuild)
        if route == "categories":
            return build_categories(page, repos, navigate, rebuild)
        if route == "settings":
            return build_settings(
                page, navigate, rebuild,
                repos=repos,
                on_change_password=change_password if encryption_enabled() else None,
            )
        return build_overview(page, repos, app_state, navigate, rebuild)

    # ── autosave ──────────────────────────────────────────────────────────────

    def autosave() -> None:
        conn = ctx.get("conn")
        passphrase = ctx.get("passphrase", "")
        if conn is None or not passphrase or not encryption_enabled():
            return
        try:
            encrypt_bytes_to_path(
                plaintext=serialize_db(conn),
                passphrase=passphrase,
                out_path=ENCRYPTED_DB_PATH,
            )
        except Exception:
            log.exception("autosave failed")

    # ── диалог пароля ─────────────────────────────────────────────────────────

    def show_password_dialog() -> None:
        first_run = not ENCRYPTED_DB_PATH.exists() and encryption_enabled()

        err = ft.Text("", color=RED, size=12)
        pwd = ft.TextField(
            label="Новый пароль" if first_run else "Пароль для БД",
            password=True, can_reveal_password=True,
            autofocus=True, border_radius=10,
        )
        pwd2 = ft.TextField(
            label="Повторите пароль",
            password=True, can_reveal_password=True,
            border_radius=10,
            visible=first_run,
        )
        hint = ft.Text(
            ("Первый запуск: придумайте пароль для шифрования локальной БД.\n"
             "Пароль не восстанавливается — сохраните его!")
            if first_run else
            "Введите пароль для расшифровки локальной БД.",
            color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE),
            size=13,
        )

        def do_unlock(_: ft.ControlEvent) -> None:
            err.value = ""
            try:
                passphrase = pwd.value or ""
                if not passphrase:
                    raise ValueError("Введите пароль")
                if first_run:
                    if pwd2.value != passphrase:
                        raise ValueError("Пароли не совпадают")
                    if len(passphrase) < MIN_PASSPHRASE_LEN:
                        raise ValueError(
                            f"Пароль слишком короткий (минимум {MIN_PASSPHRASE_LEN} символов)"
                        )

                initial: bytes | None = None
                if ENCRYPTED_DB_PATH.exists():
                    initial = decrypt_file_to_bytes(
                        encrypted_path=ENCRYPTED_DB_PATH,
                        passphrase=passphrase,
                    )

                conn = connect_in_memory(initial_bytes=initial)
                init_schema(conn)
                repos = Repos(
                    cat=CategoryRepository(conn),
                    tx=TransactionRepository(conn),
                    goal=GoalRepository(conn),
                    reminder=ReminderRepository(conn),
                )
                with db_tx(conn):
                    repos.cat.ensure_defaults()

                ctx["repos"] = repos
                ctx["passphrase"] = passphrase
                ctx["conn"] = conn

                autosave()
                set_autosave_hook(autosave)

                close_dialog(page, dlg)
                app_state["route"] = "overview"
                page.add(layout_row)
                rebuild()

            except InvalidPasswordError:
                log.warning("password rejected by decryption")
                err.value = "Неверный пароль (или файл БД повреждён)."
                page.update()
            except ValueError as exc:
                log.info("password dialog validation: %s", exc)
                err.value = str(exc)
                page.update()
            except Exception:
                log.exception("unexpected error while unlocking db")
                err.value = "Неожиданная ошибка. См. логи в data/logs/app.log."
                page.update()

        def do_exit(_: ft.ControlEvent) -> None:
            if not page.web:
                page.window.close()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Создание пароля" if first_run else "Разблокировка БД"),
            content=ft.Container(
                width=380,
                content=ft.Column(
                    tight=True, spacing=12,
                    controls=[hint, pwd, *([] if not first_run else [pwd2]), err],
                ),
            ),
            actions=[
                ft.TextButton("Выход", on_click=do_exit),
                ft.FilledButton(
                    "Открыть",
                    on_click=do_unlock,
                    style=ft.ButtonStyle(bgcolor=GREEN, color=ft.Colors.WHITE),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.bgcolor = page_bgcolor(page)
        page.update()
        open_dialog(page, dlg)

    # ── shutdown ──────────────────────────────────────────────────────────────

    shutdown_flag = {"done": False}

    def shutdown_save() -> None:
        if shutdown_flag["done"]:
            return
        shutdown_flag["done"] = True
        set_autosave_hook(None)

        conn: sqlite3.Connection | None = ctx.get("conn")
        passphrase = ctx.get("passphrase", "")
        log.info(
            "shutdown: conn=%s passphrase=%s",
            conn is not None,
            "set" if passphrase else "empty",
        )

        if conn is not None and encryption_enabled() and passphrase:
            try:
                encrypt_bytes_to_path(
                    plaintext=serialize_db(conn),
                    passphrase=passphrase,
                    out_path=ENCRYPTED_DB_PATH,
                )
                log.info("shutdown: encrypted db saved to %s", ENCRYPTED_DB_PATH)
            except Exception:
                log.exception("shutdown: final save FAILED")

        if conn is not None:
            try:
                conn.close()
            except Exception:
                log.exception("shutdown: error closing db connection")

    atexit.register(shutdown_save)

    def on_window_event(e: ft.WindowEvent) -> None:
        if e.type != ft.WindowEventType.CLOSE.value:
            return
        shutdown_save()
        page.window.destroy()

    if not page.web:
        page.window.prevent_close = True
        page.window.on_event = on_window_event

    # ── Ctrl+N: быстрое добавление операции ──────────────────────────────────
    def on_keyboard(e: ft.KeyboardEvent) -> None:
        if e.key == "N" and e.ctrl and ctx.get("repos"):
            from src.ui_flet.screens.operations import open_add_tx_dialog
            open_add_tx_dialog(page, ctx["repos"], rebuild)

    page.on_keyboard_event = on_keyboard

    # ── старт ────────────────────────────────────────────────────────────────

    if encryption_enabled():
        show_password_dialog()
    else:
        conn = connect(PLAINTEXT_DB_PATH)
        init_schema(conn)
        repos = Repos(
            cat=CategoryRepository(conn),
            tx=TransactionRepository(conn),
            goal=GoalRepository(conn),
            reminder=ReminderRepository(conn),
        )
        with db_tx(conn):
            repos.cat.ensure_defaults()
        ctx["repos"] = repos
        ctx["conn"] = conn
        app_state["route"] = "overview"
        page.add(layout_row)
        rebuild()


if __name__ == "__main__":
    import sys
    _web = "--web" in sys.argv
    ft.app(
        target=main,
        view=ft.AppView.WEB_BROWSER if _web else ft.AppView.FLET_APP,
        port=8550 if _web else 0,
    )
