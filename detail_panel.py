"""Right-hand panel showing every field of the selected entry."""
from PySide6.QtCore import QDateTime, QSize, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QPen
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea, QToolButton, QToolTip,
    QVBoxLayout, QWidget,
)

import charts
import icons
import schema
import theme
from database import parse_date
from fields import format_value
from mapview import MapViewDialog, MapWidget, format_coords
from widgets import FullScreenButton

def esc(text) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br>")


class DetailPanel(QFrame):
    NORMAL_MAX_WIDTH = 520
    MAP_HEIGHT, MAP_HEIGHT_FULL = 200, 420
    edit_requested = Signal(str, str)
    delete_requested = Signal(str, str)
    duplicate_requested = Signal(str, str)
    add_requested = Signal(str, object)         # kind, date
    entry_chosen = Signal(str, str)             # kind, id (clicked in the day view)
    hike_fly_requested = Signal(str, str)
    full_requested = Signal()
    closed = Signal()                           # hidden on purpose (close button, Esc, entry deleted)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.kind = self.entry_id = None
        self.day = None
        self.setObjectName("panel")
        self.setMinimumWidth(360)
        self.setMaximumWidth(self.NORMAL_MAX_WIDTH)
        self.full = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.header = QFrame()
        hl = QVBoxLayout(self.header)
        hl.setContentsMargins(16, 12, 16, 12)
        top = QHBoxLayout()
        self.kind_icon = QLabel()
        self.kind_label = QLabel()
        top.addWidget(self.kind_icon)
        top.addWidget(self.kind_label)
        top.addStretch()
        self.full_btn = FullScreenButton()
        self.full_btn.clicked.connect(self.full_requested)
        top.addWidget(self.full_btn)
        close = QPushButton()
        close.setIcon(icons.icon("close", theme.TEXT_SECONDARY, 14))
        close.setFixedWidth(32)
        close.setToolTip("Close")
        close.clicked.connect(self.hide)
        top.addWidget(close)
        hl.addLayout(top)
        self.title = QLabel()
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-size: 14pt; font-weight: 600;")
        hl.addWidget(self.title)
        self.subtitle = QLabel()
        self.subtitle.setObjectName("muted")
        hl.addWidget(self.subtitle)
        outer.addWidget(self.header)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(16, 8, 16, 16)
        scroll.setWidget(self.body)
        outer.addWidget(scroll, 1)
        self.btn_edit = QPushButton("Edit")
        self.btn_edit.setObjectName("primary")
        self.btn_edit.setIcon(icons.icon("pencil", "#ffffff", 20))
        self.btn_edit.clicked.connect(lambda: self.edit_requested.emit(self.kind, self.entry_id))
        self.btn_dup = QPushButton("Duplicate")
        self.btn_dup.setIcon(icons.icon("copy", theme.TEXT_SECONDARY, 20))
        self.btn_dup.setToolTip("Create a copy with today's date")
        self.btn_dup.clicked.connect(lambda: self.duplicate_requested.emit(self.kind, self.entry_id))
        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setObjectName("danger")
        self.btn_delete.setIcon(icons.icon("trash", "#b3261e", 20))
        self.btn_delete.clicked.connect(lambda: self.delete_requested.emit(self.kind, self.entry_id))
        self.btn_add = QToolButton()
        self.btn_add.setText("Add on this day")
        self.btn_add.setIcon(icons.icon("calendar_plus", theme.TEXT_SECONDARY, 20))
        self.btn_add.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_add.setPopupMode(QToolButton.InstantPopup)
        self.btn_add.setStyleSheet(f"QToolButton {{ background: {theme.SURFACE}; border: 1px solid {theme.BORDER};"
                                   "border-radius: 6px; padding: 5px 12px; } QToolButton::menu-indicator { image: none; }"
                                   "QToolButton:hover { background: #eeede8; }")
        menu = QMenu(self.btn_add)
        for kind in schema.ADDABLE:
            act = menu.addAction(icons.icon(kind, icons.shade(schema.KINDS[kind].color), 28, width=2.3), schema.KINDS[kind].label)
            act.triggered.connect(lambda _=False, k=kind: self.add_requested.emit(k, self._current_day()))
        self.btn_add.setMenu(menu)
        self.btn_hf = QPushButton("Hike && Fly")
        self.btn_hf.setIcon(icons.icon("paragliding", icons.shade(theme.KIND_COLORS["paragliding"]), 24))
        self.btn_hf.setToolTip("Log a paragliding flight (Hike & Fly) for this entry")
        self.btn_hf.clicked.connect(lambda: self.hike_fly_requested.emit(self.kind, self.entry_id))
        row1, row2 = QHBoxLayout(), QHBoxLayout()
        for w in (self.btn_edit, self.btn_dup):
            row1.addWidget(w)
        row1.addStretch()
        row1.addWidget(self.btn_delete)
        for w in (self.btn_add, self.btn_hf):
            row2.addWidget(w)
        row2.addStretch()
        box = QVBoxLayout()
        box.setContentsMargins(12, 8, 12, 12)
        box.setSpacing(6)
        box.addLayout(row1)
        box.addLayout(row2)
        outer.addLayout(box)

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.isHidden():          # not just hidden because the window is minimised
            self.closed.emit()

    def set_full(self, full: bool):
        """Full screen: the panel may use the whole window width and shows a bigger map."""
        if full == self.full:
            return
        self.full = full
        self.setMaximumWidth(16777215 if full else self.NORMAL_MAX_WIDTH)
        self.full_btn.set_active(full)
        if self.isVisible() and self.kind:
            self.show_entry(self.kind, self.entry_id)

    def _current_day(self):
        from datetime import date
        if self.day is not None:
            return self.day
        record = self.db.get(self.kind, self.entry_id) if self.kind else None
        return parse_date(record.get("date")) if record else date.today()

    def _set_mode(self, entry: bool):
        for w in (self.btn_edit, self.btn_dup, self.btn_delete):
            w.setVisible(entry)
        self.btn_hf.setVisible(entry and self.kind in ("mountain_tours", "alpine_climbs"))
        self.btn_add.setVisible(entry)

    def _clear_body(self):
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def show_day(self, day, items):
        """Day view: entries of that day (click to open) and buttons to add new ones."""
        self.kind = self.entry_id = None
        self.day = day
        self._set_mode(False)
        self.header.setStyleSheet(f"QFrame {{ border-bottom: 3px solid {theme.AXIS}; background: transparent; }}"
                                  "QLabel { border: none; }")
        self.kind_icon.setPixmap(icons.pixmap("calendar", theme.TEXT_SECONDARY, 30))
        self.kind_label.setText(f"<span style='color:{theme.TEXT_SECONDARY}'>Day</span>")
        self.title.setText(day.strftime("%A, %d.%m.%Y"))
        n = len(items)
        self.subtitle.setText("No entries on this day" if n == 0 else f"{n} entr{'y' if n == 1 else 'ies'} on this day")
        self._clear_body()
        if n == 0:
            empty = QLabel("Nothing logged for this day yet.")
            empty.setObjectName("muted")
            self.body_layout.addWidget(empty)
        for it in items:
            spec = schema.KINDS[it.kind]
            title = spec.title(it.record) if it.kind != "sport_routes" else " · ".join(it.lines[:2])
            btn = QPushButton(f" {spec.label}: {title}")
            btn.setIcon(icons.icon(it.kind, icons.shade(it.color), 28, width=2.3))
            btn.setIconSize(QSize(28, 28))
            btn.setStyleSheet(f"QPushButton {{ text-align: left; border-left: 5px solid {it.color}; padding: 8px 10px; }}")
            btn.clicked.connect(lambda _=False, k=it.kind, i=it.record["id"]: self.entry_chosen.emit(k, i))
            self.body_layout.addWidget(btn)
        self._section("Add an entry on this day")
        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(0, 0, 0, 0)
        for i, kind in enumerate(schema.ADDABLE):
            b = QPushButton(f" {schema.KINDS[kind].label}")
            b.setIcon(icons.icon(kind, icons.shade(schema.KINDS[kind].color), 28, width=2.3))
            b.setIconSize(QSize(28, 28))
            b.clicked.connect(lambda _=False, k=kind: self.add_requested.emit(k, day))
            grid.addWidget(b, i // 2, i % 2)
        self.body_layout.addWidget(grid_w)
        self.body_layout.addStretch()
        self.show()

    def show_entry(self, kind: str, entry_id: str):
        record = self.db.get(kind, entry_id)
        if record is None:
            self.hide()
            return
        self.kind, self.entry_id = kind, entry_id
        self.day = None
        self._set_mode(True)
        spec = schema.KINDS[kind]
        self.header.setStyleSheet(f"QFrame {{ border-bottom: 3px solid {spec.color}; background: transparent; }}"
                                  "QLabel { border: none; }")
        self.kind_icon.setPixmap(icons.pixmap(kind, icons.shade(spec.color), 32, 2.3))
        self.kind_label.setText(f"<span style='color:{theme.TEXT_SECONDARY}'>{spec.label}</span>")
        self.title.setText(esc(spec.title(record)))
        d, d2 = parse_date(record.get("date")), parse_date(record.get("date_to"))
        when = d.strftime("%A, %d.%m.%Y") if d else ""
        if d2 and d and d2 > d:
            when += f" – {d2:%d.%m.%Y} ({(d2 - d).days + 1} days)"
        self.subtitle.setText(when)
        self._clear_body()
        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        row = 0
        lists = []
        for f in spec.fields:
            if f.key in ("date", "date_to", "gps"):
                continue
            v = record.get(f.key)
            if f.type == "list":
                if v:
                    lists.append((f, v))
                continue
            if v in (None, "", 0, False):
                continue
            label = QLabel(f.label)
            label.setStyleSheet(f"color: {theme.TEXT_MUTED};")
            label.setAlignment(Qt.AlignRight | Qt.AlignTop)
            text = esc(v) if f.type == "multiline" else esc(format_value(f, v))
            value = QLabel(text)
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(label, row, 0)
            grid.addWidget(value, row, 1)
            row += 1
        grid.setColumnStretch(1, 1)
        self.body_layout.addWidget(grid_w)
        self._location_map(record.get("gps"))
        if kind == "climbing_days":
            self._routes_of_day(record)
        for f, items in lists:
            self._list_section(f, items, record)
        self.body_layout.addStretch()
        self.show()

    def _location_map(self, gps):
        if not isinstance(gps, dict) or "lat" not in gps:
            return
        self._section(f"Location  ·  {format_coords(gps['lat'], gps['lon'])}")
        m = MapWidget(wheel_zoom=False)       # the wheel scrolls the panel; use the +/- buttons to zoom
        m.setFixedHeight(self.MAP_HEIGHT_FULL if self.full else self.MAP_HEIGHT)
        m.set_view(gps["lat"], gps["lon"], 13)
        m.set_marker(gps["lat"], gps["lon"])
        m.setCursor(Qt.PointingHandCursor)
        m.setToolTip("Click to open a large map")
        title = schema.KINDS[self.kind].title(self.db.get(self.kind, self.entry_id) or {}) if self.kind else ""
        m.clicked.connect(lambda *_: MapViewDialog(gps["lat"], gps["lon"], title, self.window()).exec())
        self.body_layout.addWidget(m)

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("sectionTitle")
        lbl.setStyleSheet("margin-top: 12px;")
        self.body_layout.addWidget(lbl)

    def _routes_of_day(self, record):
        routes = [r for r in self.db.entries("sport_routes") if r.get("date") == record.get("date")]
        if not routes:
            return
        self._section(f"Routes this day ({len(routes)})")
        for r in routes:
            lbl = QLabel(f"• <b>{esc(r.get('name'))}</b> {esc(r.get('grade') or '')} "
                         f"<span style='color:{theme.TEXT_MUTED}'>{esc(r.get('attempts') or '')}</span>")
            self.body_layout.addWidget(lbl)

    def _list_section(self, f, items, record):
        self._section(f"{f.label} ({len(items)})")
        if f.key == "details":
            for d in items:
                sets = d.get("sets") or []
                sets_txt = ", ".join(
                    f"{s.get('load') or 0}{('+' + format(s.get('weight'), 'g') + ' kg') if s.get('weight') else ''}"
                    f"{(' ' + s['side'][0]) if s.get('side') and s['side'] != 'Beidarmig' else ''}" for s in sets)
                meta = " · ".join(x for x in [
                    f"{d['duration']} min" if d.get("duration") else "", f"{d['repetitions']}×" if d.get("repetitions") else "",
                    f"{d['distance']} m" if d.get("distance") else "",
                    f"rest {d['rest']} s" if d.get("rest") else ""] if x)
                lbl = QLabel(f"<b>{esc(d.get('method') or d.get('discipline') or '')}</b> "
                             f"<span style='color:{theme.TEXT_MUTED}'>{esc(d.get('discipline') or '')}"
                             f"{' · ' + esc(d['hold']) if d.get('hold') else ''}</span>"
                             f"{'<br>' + meta if meta else ''}{'<br>Sets: ' + esc(sets_txt) if sets_txt else ''}"
                             f"{'<br><i>' + esc(d['info']) + '</i>' if d.get('info') else ''}")
                lbl.setWordWrap(True)
                lbl.setStyleSheet("margin-bottom: 6px;")
                self.body_layout.addWidget(lbl)
            return
        cols = f.columns or [s.key for s in f.sub]
        subs = [next(s for s in f.sub if s.key == c) for c in cols]
        table = charts.make_table([s.label for s in subs], [[format_value(s, it.get(s.key)) for s in subs] for it in items])
        table.setSortingEnabled(False)
        table.setMinimumHeight(min(260, 30 + 28 * len(items)))
        self.body_layout.addWidget(table)


__all__ = ["DetailPanel"]
