import json
import os
import sys
from pathlib import Path

APP_NAME = "Follow-up Comercial - Soretrac Portuguesa"
APP_VERSION = "3.0.0"
ADMIN_PASSWORD = "soretrac2026"
COMPANY = "Soretrac Portuguesa"
EMPLOYEE_EXE = "Soretrac_Funcionarios.exe"

WINDOW_WIDTH = 1560
WINDOW_HEIGHT = 920

FONT_TITLE = 20
FONT_SUBTITLE = 14
FONT_NORMAL = 13
FONT_BUTTON = 13
FONT_SMALL = 11

# Cores oficiais Soretrac (#005696)
COLORS = {
    "primary": "#005696",
    "primary_dark": "#003d66",
    "primary_light": "#0078c8",
    "header": "#005696",
    "accent": "#0088cc",
    "success": "#28a745",
    "success_bg": "#1a3d2e",
    "warning": "#f0ad4e",
    "warning_bg": "#3d3018",
    "danger": "#dc3545",
    "danger_bg": "#3d1a1a",
    "bg_dark": "#0a1a2e",
    "bg_card": "#0f2840",
    "bg_card_light": "#1a3d55",
    "text": "#ffffff",
    "text_muted": "#a8cce0",
    "border": "#005696",
}

SEGMENTOS = [
    ("todos", "Todos"),
    ("lt30", "Recentes\n(< 30 dias)"),
    ("30_60", "30-60 dias"),
    ("60_90", "60-90 dias"),
    ("90_180", "90-180 dias"),
    ("180_365", "180-365 dias"),
    ("gt365", "Antigos\n(+ 1 ano)"),
]

OPERADORES_TEXTO = ["contém", "igual a", "começa com", "termina com", "não contém"]
OPERADORES_NUM = ["=", "≠", ">", ">=", "<", "<=", "entre"]
OPERADORES_DATA = ["=", ">", ">=", "<", "<=", "entre"]


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def get_runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def get_data_dir() -> Path:
    runtime = get_runtime_dir()
    data = runtime / "data"
    data.mkdir(parents=True, exist_ok=True)
    return data


def get_db_path() -> Path:
    """Funcionario: DB embutida no exe. Admin: ficheiro local."""
    bundled = get_base_dir() / "data" / "sales.db"
    if bundled.exists() and is_employee_build():
        return bundled
    local = get_data_dir() / "sales.db"
    return local


def get_logo_path() -> Path:
    for name in ("logo_header.png", "logo_white.png", "logo_transparent.png", "logo.png"):
        for base in (get_base_dir(), get_runtime_dir()):
            logo = base / "assets" / name
            if logo.exists():
                return logo
    return get_base_dir() / "assets" / "logo.png"


def get_icon_path() -> Path:
    for base in (get_base_dir(), get_runtime_dir()):
        icon = base / "assets" / "icon.ico"
        if icon.exists():
            return icon
    return get_base_dir() / "assets" / "icon.ico"


def is_employee_build() -> bool:
    if getattr(sys, "frozen", False):
        return "admin" not in Path(sys.executable).stem.lower()
    flag = get_base_dir() / "build_config.json"
    if flag.exists():
        try:
            return json.loads(flag.read_text(encoding="utf-8")).get("mode") == "employee"
        except (json.JSONDecodeError, OSError):
            pass
    return False


def get_build_config() -> dict:
    flag = get_base_dir() / "build_config.json"
    if flag.exists():
        try:
            return json.loads(flag.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"mode": "admin", "version": APP_VERSION}
