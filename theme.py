"""Colours, stylesheet and small shared widgets."""
from pathlib import Path

import icons

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

# Surfaces & ink
PAGE = "#f4f4f1"
SURFACE = "#fcfcfb"
BORDER = "#e1e0d9"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
TEXT_MUTED = "#898781"
TEXT_ON_FILL = "#0b0b0b"
ACCENT = "#2f3b4a"          # UI chrome is neutral slate: hues are reserved for categories
HEADER = "#1f2a36"

# One colour per activity kind, used by the calendar, the charts and the legends.
# The hues follow V1 (rock red, training amber, alpine blue, tours violet, trips
# cyan); competitions got the orange slot. Order = stacking order in charts and validated
# for colour-blind separation of neighbours.
KIND_COLORS = {
    "climbing_days": "#c62f3e",       # red
    "sport_routes": "#f08ab4",        # pink (tick list: the red family, lighter)
    "alpine_climbs": "#3a86e0",       # blue
    "mountain_tours": "#5a46c8",      # indigo-violet
    "paragliding": "#b03fd0",         # magenta-purple
    "competitions": "#f2b705",        # gold
    "training_sessions": "#f07a2a",   # orange
    "cycling": "#008300",             # green
    "trips": "#0fb5ae",               # teal
    "fitness_sessions": "#008300",
    "body_metrics": "#7a7a72",
    "notes": "#898781",
}

_ASSETS = Path(__file__).resolve().parent / "assets"
ARROW_DOWN = (_ASSETS / "arrow_down.png").as_posix()
PLUS = (_ASSETS / "plus.png").as_posix()
MINUS = (_ASSETS / "minus.png").as_posix()

STYLESHEET = f"""
QMainWindow, QDialog {{ background: {PAGE}; }}
QWidget {{ font-family: "Segoe UI"; font-size: 10pt; color: {TEXT}; }}
QFrame#header {{ background: {HEADER}; }}
QFrame#header QLabel {{ color: white; }}
QLabel#appTitle {{ font-size: 15pt; font-weight: 600; color: white; }}
QLabel#calendarTitle {{ font-size: 15pt; font-weight: 600; }}
QLabel#sectionTitle {{ font-size: 12pt; font-weight: 600; }}
QLabel#muted {{ color: {TEXT_MUTED}; }}
QPushButton {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px; padding: 5px 12px;
}}
QPushButton:hover {{ background: #eeede8; }}
QPushButton:pressed {{ background: #e4e3dc; }}
QPushButton:checked {{ background: {HEADER}; color: white; border-color: {HEADER}; }}
QPushButton#primary {{ background: {ACCENT}; color: white; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: #1f2a36; }}
QPushButton#danger {{ color: #b3261e; }}
QFrame#header QPushButton {{ background: transparent; color: white; border: 1px solid #3b4a5a; }}
QFrame#header QPushButton:hover {{ background: #2c3a4a; }}
QFrame#header QPushButton:checked {{ background: {SURFACE}; color: {HEADER}; border-color: {SURFACE}; }}
QFrame#header QPushButton#primary {{ background: {ACCENT}; border: none; }}
QWidget#formCard {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
QWidget#formCard QLineEdit, QWidget#formCard QComboBox, QWidget#formCard QAbstractSpinBox {{
    min-height: 18px; padding-top: 3px; padding-bottom: 3px;
}}
QWidget#formCard QDateEdit {{ border-radius: 0; }}
QFrame#card, QFrame#panel {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px;
}}
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QAbstractSpinBox {{
    background: white; border: 1px solid {BORDER}; border-radius: 5px; padding: 4px 6px; min-height: 22px;
}}
QPlainTextEdit, QTextEdit {{ min-height: 80px; }}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QAbstractSpinBox:focus {{ border: 1px solid {ACCENT}; }}

/* dropdowns: the list opens BELOW the box (Fusion's default overlay popup closed again on the button release) */
QComboBox {{ combobox-popup: 0; padding-right: 26px; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: 24px; border: none;
    border-left: 1px solid {BORDER}; }}
QComboBox::down-arrow {{ image: url({ARROW_DOWN}); width: 10px; height: 10px; }}
QComboBox QAbstractItemView {{
    background: white; border: 1px solid {AXIS}; outline: 0; padding: 2px;
    selection-background-color: #e6eaf0; selection-color: {TEXT};
}}
QToolButton#dayMinus, QToolButton#dayPlus {{
    background: #f2f1ec; border: 1px solid {BORDER}; min-width: 26px; max-width: 26px; padding: 0;
}}
QToolButton#dayMinus {{ border-top-left-radius: 5px; border-bottom-left-radius: 5px; border-right: none; }}
QToolButton#dayPlus {{ border-top-right-radius: 5px; border-bottom-right-radius: 5px; border-left: none; }}
QToolButton#dayMinus:hover, QToolButton#dayPlus:hover {{ background: #e4e3dc; }}
QToolButton#dayMinus:pressed, QToolButton#dayPlus:pressed {{ background: #d6d5cc; }}
QDateEdit {{ padding-right: 26px; }}
QDateEdit::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: 24px; border: none;
    border-left: 1px solid {BORDER}; }}
QDateEdit::down-arrow {{ image: url({ARROW_DOWN}); width: 10px; height: 10px; }}

/* number / time boxes: minus on the left, plus on the right, value centred */
QSpinBox, QDoubleSpinBox, QTimeEdit {{ padding: 4px 30px; qproperty-alignment: AlignCenter; }}
QSpinBox::down-button, QDoubleSpinBox::down-button, QTimeEdit::down-button {{
    subcontrol-origin: border; subcontrol-position: center left; width: 26px; height: 100%;
    border: none; border-right: 1px solid {BORDER}; background: #f2f1ec;
    border-top-left-radius: 5px; border-bottom-left-radius: 5px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button, QTimeEdit::up-button {{
    subcontrol-origin: border; subcontrol-position: center right; width: 26px; height: 100%;
    border: none; border-left: 1px solid {BORDER}; background: #f2f1ec;
    border-top-right-radius: 5px; border-bottom-right-radius: 5px;
}}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover, QTimeEdit::down-button:hover,
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover, QTimeEdit::up-button:hover {{ background: #e4e3dc; }}
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed, QTimeEdit::down-button:pressed,
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed, QTimeEdit::up-button:pressed {{ background: #d6d5cc; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow, QTimeEdit::down-arrow {{ image: url({MINUS}); width: 10px; height: 10px; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow, QTimeEdit::up-arrow {{ image: url({PLUS}); width: 10px; height: 10px; }}
QTableView {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; gridline-color: transparent;
    alternate-background-color: #fafaf7; selection-background-color: #e6eaf0; selection-color: {TEXT}; outline: 0;
}}
QTableView::item {{ padding: 0 10px; border: none; }}
QTableView::item:hover {{ background: #f1f3f6; }}
QTableView::item:selected {{ background: #e6eaf0; color: {TEXT}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: #f5f4ef; color: {TEXT_SECONDARY}; border: none; border-bottom: 1px solid {BORDER};
    padding: 9px 10px; font-weight: 600; font-size: 9pt;
}}
QHeaderView::section:hover {{ background: #ecebe4; }}
QTableCornerButton::section {{ background: #f5f4ef; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #cfcdc4; border-radius: 4px; min-height: 36px; margin: 0 2px; }}
QScrollBar::handle:vertical:hover {{ background: #b3b0a4; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #cfcdc4; border-radius: 4px; min-width: 36px; margin: 2px 0; }}
QScrollBar::handle:horizontal:hover {{ background: #b3b0a4; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 6px; background: {SURFACE}; top: -1px; }}
QTabBar::tab {{ padding: 6px 14px; color: {TEXT_SECONDARY}; border: none; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; font-weight: 600; }}
QListWidget#nav {{ background: {SURFACE}; border: none; border-right: 1px solid {BORDER}; outline: 0; }}
QListWidget#nav::item {{ padding: 8px 10px; border-radius: 6px; margin: 1px 6px; }}
QListWidget#nav::item:selected {{ background: #e6eaf0; color: {TEXT}; font-weight: 600; }}
QListWidget#nav::item:hover {{ background: #efeee9; }}
QScrollArea {{ border: none; background: transparent; }}
QToolTip {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px; }}
"""


def swatch(color: str, size: int = 10) -> QFrame:
    box = QFrame()
    box.setFixedSize(size, size)
    box.setStyleSheet(f"background: {color}; border-radius: 2px; border: none;")
    return box


def legend_widget(kinds: list[str], labels: dict[str, str] | None = None) -> QWidget:
    import schema
    w = QWidget()
    layout = QHBoxLayout(w)
    layout.setContentsMargins(6, 6, 6, 2)
    layout.setSpacing(6)
    for kind in kinds:
        mark = QLabel()
        mark.setPixmap(icons.pixmap(kind, icons.shade(KIND_COLORS[kind], 0.85), 26, 2.3))
        layout.addWidget(mark)
        label = QLabel((labels or {}).get(kind) or schema.KINDS[kind].plural)
        label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        layout.addWidget(label)
        layout.addSpacing(10)
    layout.addStretch()
    return w
