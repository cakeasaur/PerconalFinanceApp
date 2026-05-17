from __future__ import annotations

import sys
from pathlib import Path

import flet as ft


def _runtime_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent.parent


def _runtime_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "data"
    return _runtime_root() / "data"


PROJECT_ROOT = _runtime_root()
DATA_DIR = _runtime_data_dir()
PLAINTEXT_DB_PATH = DATA_DIR / "personal_finance.sqlite3"
ENCRYPTED_DB_PATH = DATA_DIR / "personal_finance.sqlite3.enc"

# ── основная палитра ──────────────────────────────────────────────────────────
GREEN = "#22C55E"
GREEN_SOFT = "#DCFCE7"
RED = "#EF4444"
RED_SOFT = "#FEE2E2"
BLUE_SOFT = "#DBEAFE"
PURPLE = "#8B5CF6"
ORANGE = "#F97316"
TEXT_MUTED = "#64748B"
CARD_LIGHT = "#FFFFFF"
BG_LIGHT = "#F8FAFC"
CARD_DARK = "#1E293B"
BG_DARK = "#0F172A"
SIDEBAR_DARK = "#0F172A"
SIDEBAR_LIGHT = "#FFFFFF"

# ── border-radius константы ───────────────────────────────────────────────────
RADIUS_SM = 8
RADIUS_MD = 12
RADIUS_LG = 16
RADIUS_XL = 24

# ── палитра для графиков ──────────────────────────────────────────────────────
CHART_PALETTE = [
    PURPLE,
    "#3B82F6",
    "#F59E0B",
    "#EC4899",
    "#14B8A6",
    "#F97316",
    "#64748B",
    "#EF4444",
]

# ── Material 3 seed для page.theme ───────────────────────────────────────────
THEME_SEED = GREEN


def make_theme(dark: bool = False) -> ft.Theme:
    return ft.Theme(color_scheme_seed=THEME_SEED, use_material3=True)


# ── цветовые хелперы ──────────────────────────────────────────────────────────

def card_bgcolor(page: ft.Page) -> str:
    return CARD_DARK if page.theme_mode == ft.ThemeMode.DARK else CARD_LIGHT


def sidebar_bgcolor(page: ft.Page) -> str:
    return SIDEBAR_DARK if page.theme_mode == ft.ThemeMode.DARK else SIDEBAR_LIGHT


def page_bgcolor(page: ft.Page) -> str:
    return BG_DARK if page.theme_mode == ft.ThemeMode.DARK else BG_LIGHT


def muted_color(page: ft.Page) -> str:
    return "#94A3B8" if page.theme_mode == ft.ThemeMode.DARK else TEXT_MUTED


# ── тени ─────────────────────────────────────────────────────────────────────

def card_shadow() -> ft.BoxShadow:
    return ft.BoxShadow(
        spread_radius=0, blur_radius=8,
        color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
        offset=ft.Offset(0, 2),
    )


def card_shadow_lg() -> ft.BoxShadow:
    return ft.BoxShadow(
        spread_radius=0, blur_radius=24,
        color=ft.Colors.with_opacity(0.12, ft.Colors.BLACK),
        offset=ft.Offset(0, 8),
    )


# ── SnackBar ──────────────────────────────────────────────────────────────────

def show_snack(
    page: ft.Page,
    message: str,
    *,
    color: str = GREEN,
    action_label: str | None = None,
    on_action: ft.ControlEventCallable | None = None,
) -> None:
    action = None
    if action_label and on_action:
        action = ft.SnackBarAction(label=action_label, on_click=on_action, text_color=ft.Colors.WHITE)
    page.snack_bar = ft.SnackBar(
        content=ft.Text(message, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500),
        bgcolor=color,
        duration=3000,
        behavior=ft.SnackBarBehavior.FLOATING,
        action=action,
        open=True,
    )
    page.update()
