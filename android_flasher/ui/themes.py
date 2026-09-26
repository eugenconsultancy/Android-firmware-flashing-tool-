"""Application themes.

Provides a professional dark and light theme using Qt stylesheets.
Themes are applied at the QApplication level so every widget inherits
the styling.

The stylesheet exposes the following hooks used by the redesigned
main window and its panels:

    Object names:
        #main_window             — the QMainWindow
        #toolbar_card            — top toolbar card
        #platform_tools_banner   — platform tools banner card
        #platform_tools_banner_title
        #app_title               — app name in the toolbar
        #app_subtitle            — version label in the toolbar
        #progress_container      — compact progress wrapper

    Label roles (set via setProperty("role", ...)):
        panel-title, field-label, field-value, field-value-mono,
        muted, hint, heading, pill

    Pill states (set via setProperty("state", ...)):
        readonly (amber), armed (green), idle (blue), error (red)

    Button kinds (set via setProperty("kind", ...)):
        primary, danger

    Compatibility label states (set via setProperty("state", ...)):
        pass, warning, fail, blocked, unknown

Design goals:

    * Clear font hierarchy.
    * Legible contrast for secondary label text.
    * Rounded "card" surfaces with a subtle elevation against the window.
    * Distinct tab styling with an accent underline on the active tab.
    * Status pills for state indicators.
    * Buttons with primary / secondary styling plus hover and pressed states.

No widget uses absolute positioning; all layouts are responsive.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication


class ThemeName(str, Enum):
    DARK = "dark"
    LIGHT = "light"
    SYSTEM = "system"


# ---------------------------------------------------------------------------
# Palettes
# ---------------------------------------------------------------------------

_DARK_PALETTE = {
    "window": "#181818",          # deepest background
    "surface": "#202020",         # panel / card background
    "surface_alt": "#262626",     # subtle elevation
    "surface_raised": "#2d2d2d",  # inputs, table rows
    "border": "#3a3a3a",
    "border_strong": "#4a4a4a",
    "fg": "#f0f0f0",              # primary text
    "fg_muted": "#c8c8c8",        # secondary text
    "fg_dim": "#909090",          # tertiary / placeholder
    "fg_disabled": "#5a5a5a",
    "accent": "#0d7dd1",
    "accent_hover": "#1a92e6",
    "accent_pressed": "#085c9c",
    "accent_soft": "#0d7dd122",
    "success": "#4ec9b0",
    "success_soft": "#4ec9b022",
    "warning": "#e2b341",
    "warning_soft": "#e2b34122",
    "error": "#f08a7a",
    "error_soft": "#f08a7a22",
    "critical": "#f44747",
    "critical_soft": "#f4474722",
    "info": "#6bb6f0",
    "mono": "#e8e8e8",
}

_LIGHT_PALETTE = {
    "window": "#eaeaec",
    "surface": "#ffffff",
    "surface_alt": "#f5f5f7",
    "surface_raised": "#ffffff",
    "border": "#d0d0d5",
    "border_strong": "#b6b6bc",
    "fg": "#16161a",
    "fg_muted": "#3f3f46",
    "fg_dim": "#70707a",
    "fg_disabled": "#a0a0aa",
    "accent": "#0d6fbf",
    "accent_hover": "#0e83dd",
    "accent_pressed": "#0a5596",
    "accent_soft": "#0d6fbf1f",
    "success": "#0f7a3d",
    "success_soft": "#0f7a3d1a",
    "warning": "#9a6b00",
    "warning_soft": "#9a6b001a",
    "error": "#b0301c",
    "error_soft": "#b0301c1a",
    "critical": "#9a1f1f",
    "critical_soft": "#9a1f1f1a",
    "info": "#0d6fbf",
    "mono": "#1a1a1a",
}


# ---------------------------------------------------------------------------
# Stylesheet builder
# ---------------------------------------------------------------------------

def _build_stylesheet(p: dict) -> str:
    return f"""
/* ------------------------------- Global ---------------------------------- */

QWidget {{
    background-color: {p['window']};
    color: {p['fg']};
    font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 10pt;
}}

QMainWindow, QDialog {{
    background-color: {p['window']};
}}

QToolTip {{
    background-color: {p['surface_alt']};
    color: {p['fg']};
    border: 1px solid {p['border_strong']};
    padding: 6px 8px;
    border-radius: 4px;
}}

/* -------------------------- Menu bar & menus ----------------------------- */

QMenuBar {{
    background-color: {p['surface']};
    color: {p['fg']};
    padding: 4px 6px;
    border-bottom: 1px solid {p['border']};
}}

QMenuBar::item {{
    background: transparent;
    padding: 6px 12px;
    border-radius: 4px;
}}

QMenuBar::item:selected {{
    background-color: {p['accent_soft']};
    color: {p['fg']};
}}

QMenu {{
    background-color: {p['surface']};
    color: {p['fg']};
    border: 1px solid {p['border_strong']};
    border-radius: 6px;
    padding: 6px;
}}

QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {p['accent']};
    color: #ffffff;
}}

QMenu::separator {{
    height: 1px;
    background: {p['border']};
    margin: 4px 8px;
}}

/* --------------------------------- Cards --------------------------------- */

QGroupBox {{
    background-color: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 8px;
    margin-top: 16px;
    padding: 14px 12px 12px 12px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 2px;
    padding: 2px 8px;
    color: {p['accent']};
    background-color: {p['surface']};
    font-size: 10.5pt;
    font-weight: 700;
    letter-spacing: 0.4px;
    text-transform: uppercase;
    border-radius: 4px;
}}

/* ------------------------------ Typography ------------------------------- */

QLabel {{
    background-color: transparent;
    color: {p['fg']};
}}

QLabel[role="panel-title"] {{
    color: {p['fg_muted']};
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
}}

QLabel[role="field-label"] {{
    color: {p['fg_dim']};
    font-weight: 600;
}}

QLabel[role="field-value"] {{
    color: {p['fg']};
    font-weight: 500;
}}

QLabel[role="field-value-mono"] {{
    color: {p['mono']};
    font-family: "Consolas", "JetBrains Mono", "Cascadia Mono", monospace;
    font-weight: 500;
}}

QLabel[role="muted"] {{
    color: {p['fg_dim']};
}}

QLabel[role="hint"] {{
    color: {p['fg_dim']};
    font-style: italic;
}}

QLabel[role="heading"] {{
    color: {p['fg']};
    font-size: 12pt;
    font-weight: 700;
}}

/* ------------------------ Status pills (badges) -------------------------- */

QLabel[role="pill"] {{
    padding: 4px 12px;
    border-radius: 12px;
    font-weight: 700;
    font-size: 9pt;
    letter-spacing: 0.6px;
}}

QLabel[role="pill"][state="readonly"] {{
    background-color: {p['warning_soft']};
    color: {p['warning']};
    border: 1px solid {p['warning']};
}}

QLabel[role="pill"][state="armed"] {{
    background-color: {p['success_soft']};
    color: {p['success']};
    border: 1px solid {p['success']};
}}

QLabel[role="pill"][state="idle"] {{
    background-color: {p['accent_soft']};
    color: {p['info']};
    border: 1px solid {p['info']};
}}

QLabel[role="pill"][state="error"] {{
    background-color: {p['error_soft']};
    color: {p['error']};
    border: 1px solid {p['error']};
}}

/* -------------------------- Compatibility states ------------------------- */

QLabel[state="pass"]    {{ color: {p['success']};  font-weight: 700; }}
QLabel[state="warning"] {{ color: {p['warning']};  font-weight: 700; }}
QLabel[state="fail"]    {{ color: {p['error']};    font-weight: 700; }}
QLabel[state="blocked"] {{ color: {p['critical']}; font-weight: 700; }}
QLabel[state="unknown"] {{ color: {p['fg_dim']};   font-weight: 700; }}

/* -------------------------------- Buttons -------------------------------- */

QPushButton {{
    background-color: {p['surface_alt']};
    color: {p['fg']};
    border: 1px solid {p['border_strong']};
    border-radius: 6px;
    padding: 8px 16px;
    min-height: 22px;
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: {p['surface_raised']};
    border-color: {p['accent']};
}}

QPushButton:pressed {{
    background-color: {p['accent_pressed']};
    color: #ffffff;
    border-color: {p['accent_pressed']};
}}

QPushButton:focus {{
    outline: none;
    border-color: {p['accent']};
}}

QPushButton:disabled {{
    background-color: {p['surface']};
    color: {p['fg_disabled']};
    border-color: {p['border']};
}}

QPushButton[kind="primary"] {{
    background-color: {p['accent']};
    color: #ffffff;
    border-color: {p['accent']};
}}

QPushButton[kind="primary"]:hover {{
    background-color: {p['accent_hover']};
    border-color: {p['accent_hover']};
}}

QPushButton[kind="primary"]:pressed {{
    background-color: {p['accent_pressed']};
    border-color: {p['accent_pressed']};
}}

QPushButton[kind="primary"]:disabled {{
    background-color: {p['surface']};
    color: {p['fg_disabled']};
    border-color: {p['border']};
}}

QPushButton[kind="danger"] {{
    background-color: {p['error_soft']};
    color: {p['error']};
    border-color: {p['error']};
}}

QPushButton[kind="danger"]:hover {{
    background-color: {p['error']};
    color: #ffffff;
}}

QPushButton[kind="danger"]:pressed {{
    background-color: {p['critical']};
    color: #ffffff;
    border-color: {p['critical']};
}}

QPushButton[kind="danger"]:disabled {{
    background-color: {p['surface']};
    color: {p['fg_disabled']};
    border-color: {p['border']};
}}

/* -------------------------------- Inputs --------------------------------- */

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {{
    background-color: {p['surface_raised']};
    color: {p['fg']};
    border: 1px solid {p['border_strong']};
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: {p['accent']};
    selection-color: #ffffff;
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QComboBox:focus, QSpinBox:focus {{
    border-color: {p['accent']};
}}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
QComboBox:disabled, QSpinBox:disabled {{
    background-color: {p['surface']};
    color: {p['fg_disabled']};
    border-color: {p['border']};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {p['surface']};
    color: {p['fg']};
    border: 1px solid {p['border_strong']};
    border-radius: 6px;
    selection-background-color: {p['accent']};
    selection-color: #ffffff;
    padding: 4px;
}}

/* -------------------------------- Tables --------------------------------- */

QTableWidget, QTableView {{
    background-color: {p['surface']};
    alternate-background-color: {p['surface_alt']};
    gridline-color: {p['border']};
    color: {p['fg']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    selection-background-color: {p['accent_soft']};
    selection-color: {p['fg']};
    padding: 2px;
}}

QTableWidget::item, QTableView::item {{
    padding: 6px 8px;
    border: none;
}}

QTableWidget::item:selected, QTableView::item:selected {{
    background-color: {p['accent_soft']};
    color: {p['fg']};
}}

QHeaderView::section {{
    background-color: {p['surface_alt']};
    color: {p['fg_muted']};
    padding: 8px 10px;
    border: none;
    border-right: 1px solid {p['border']};
    border-bottom: 1px solid {p['border_strong']};
    font-weight: 700;
    font-size: 9pt;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}

QHeaderView::section:last {{
    border-right: none;
}}

QTableCornerButton::section {{
    background-color: {p['surface_alt']};
    border: none;
}}

/* --------------------------------- Tabs ---------------------------------- */

QTabWidget::pane {{
    background-color: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 8px;
    top: -1px;
}}

QTabBar {{
    background: transparent;
    qproperty-drawBase: 0;
}}

QTabBar::tab {{
    background-color: transparent;
    color: {p['fg_dim']};
    padding: 10px 18px;
    margin-right: 4px;
    border: 1px solid transparent;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 600;
}}

QTabBar::tab:hover:!selected {{
    color: {p['fg']};
    background-color: {p['surface_alt']};
}}

QTabBar::tab:selected {{
    background-color: {p['surface']};
    color: {p['fg']};
    border-color: {p['border']};
    border-bottom-color: {p['surface']};
    border-bottom: 2px solid {p['accent']};
}}

/* -------------------------------- Progress ------------------------------- */

QProgressBar {{
    background-color: {p['surface_alt']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    text-align: center;
    color: {p['fg_muted']};
    height: 20px;
    font-weight: 600;
}}

QProgressBar::chunk {{
    background-color: {p['accent']};
    border-radius: 5px;
    margin: 1px;
}}

/* ------------------------------- Splitter -------------------------------- */

QSplitter::handle {{
    background-color: transparent;
}}

QSplitter::handle:horizontal {{
    width: 8px;
}}

QSplitter::handle:vertical {{
    height: 8px;
}}

QSplitter::handle:hover {{
    background-color: {p['accent_soft']};
}}

/* ------------------------------ Scroll bars ------------------------------ */

QScrollBar:vertical {{
    background-color: transparent;
    width: 12px;
    margin: 4px 2px 4px 2px;
}}

QScrollBar::handle:vertical {{
    background-color: {p['border_strong']};
    min-height: 32px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {p['fg_dim']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 12px;
    margin: 2px 4px 2px 4px;
}}

QScrollBar::handle:horizontal {{
    background-color: {p['border_strong']};
    min-width: 32px;
    border-radius: 5px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {p['fg_dim']};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}

/* ----------------------------- Status bar -------------------------------- */

QStatusBar {{
    background-color: {p['surface']};
    color: {p['fg_muted']};
    border-top: 1px solid {p['border']};
    padding: 4px 8px;
}}

QStatusBar::item {{
    border: none;
}}

/* ----------------------------- Check boxes ------------------------------- */

QCheckBox {{
    background-color: transparent;
    spacing: 8px;
    color: {p['fg_muted']};
}}

QCheckBox:hover {{
    color: {p['fg']};
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {p['border_strong']};
    border-radius: 4px;
    background-color: {p['surface_raised']};
}}

QCheckBox::indicator:hover {{
    border-color: {p['accent']};
}}

QCheckBox::indicator:checked {{
    background-color: {p['accent']};
    border-color: {p['accent']};
    image: none;
}}

/* -------------------------------- Lists ---------------------------------- */

QListWidget, QListView {{
    background-color: {p['surface']};
    color: {p['fg']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    padding: 4px;
}}

QListWidget::item {{
    padding: 6px 8px;
    border-radius: 4px;
}}

QListWidget::item:selected {{
    background-color: {p['accent_soft']};
    color: {p['fg']};
}}

/* -------------------------- Custom class hooks --------------------------- */
/* The redesigned main window and its panels tag specific widgets with
   these object names. */

QMainWindow#main_window {{
    background-color: {p['window']};
}}

QWidget#toolbar_card {{
    background-color: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 8px;
}}

QWidget#platform_tools_banner {{
    background-color: {p['surface_alt']};
    border: 1px solid {p['border']};
    border-radius: 8px;
}}

QLabel#platform_tools_banner_title {{
    color: {p['fg_muted']};
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 1.0px;
    text-transform: uppercase;
}}

QLabel#app_title {{
    color: {p['fg']};
    font-size: 13pt;
    font-weight: 700;
    letter-spacing: 0.4px;
}}

QLabel#app_subtitle {{
    color: {p['fg_dim']};
    font-size: 9pt;
}}

QWidget#progress_container {{
    background-color: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 8px;
}}
"""


# ---------------------------------------------------------------------------
# Theme manager
# ---------------------------------------------------------------------------

class ThemeManager(QObject):
    """Applies and tracks the active application theme."""

    theme_changed = Signal(str)

    def __init__(self, initial: ThemeName = ThemeName.DARK) -> None:
        super().__init__()
        self._current = initial

    @property
    def current(self) -> ThemeName:
        return self._current

    def apply(self, app: QApplication, theme: Optional[ThemeName] = None) -> None:
        """Apply a theme to the QApplication."""
        target = theme or self._current
        if target == ThemeName.SYSTEM:
            palette = app.palette()
            bg = palette.window().color()
            is_dark = bg.lightness() < 128
            target = ThemeName.DARK if is_dark else ThemeName.LIGHT

        if target == ThemeName.LIGHT:
            stylesheet = _build_stylesheet(_LIGHT_PALETTE)
        else:
            stylesheet = _build_stylesheet(_DARK_PALETTE)

        app.setStyleSheet(stylesheet)
        self._current = target
        self.theme_changed.emit(self._current.value)


def apply_theme(app: QApplication, theme: str = "dark") -> ThemeManager:
    """Convenience: create a ThemeManager and apply the theme."""
    try:
        name = ThemeName(theme)
    except ValueError:
        name = ThemeName.DARK
    manager = ThemeManager(name)
    manager.apply(app, name)
    return manager
