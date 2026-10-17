"""Field specifications and the widgets that edit them.

A kind of entry (see schema.py) is described by a list of ``Field``s. From that
list the generic ``RecordForm`` builds the input widgets, reads/writes the record
dict and offers autocomplete suggestions taken from the existing data.
"""
from dataclasses import dataclass, field as dc_field
from datetime import date
from typing import Callable

import icons
import theme
from mapview import MapPickDialog, format_coords
from widgets import ComboBox, DateField

from PySide6.QtCore import QDate, QSize, QStringListModel, QTime, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QCompleter, QDateEdit, QDialog,
    QDialogButtonBox, QDoubleSpinBox, QFormLayout, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QTimeEdit, QVBoxLayout, QWidget,
)


@dataclass
class Field:
    key: str
    label: str
    type: str = "text"        # text multiline int float date bool choice partners time rating list gps
    choices: list[str] | None = None        # fixed options for 'choice'
    suggest: Callable | None = None         # db -> list[str] for autocomplete
    sub: list["Field"] | None = None        # item fields for 'list'
    maximum: float = 100000
    minimum: float = 0
    step: float = 1                         # spin box increment (e.g. 50 for metres)
    wide: bool = False                      # always use the full form width (default: only long inputs do)
    new_row: bool = False                   # start a new row even if the previous row has a free half
    decimals: int = 1
    suffix: str = ""
    default: object = None
    required: bool = False
    columns: list[str] | None = None        # 'list': keys shown in the sub-table
    item_label: str = "Item"               # 'list': name of one item
    tab: str = ""                           # optional tab name in the dialog


WIDE_TYPES = {"text", "partners", "multiline", "list", "multichoice"}    # long inputs fill a whole row, the rest pairs up


def default_value(f: Field):
    if f.default is not None:
        return f.default() if callable(f.default) else f.default
    return {"int": 0, "float": 0.0, "bool": False, "list": [], "multichoice": [], "rating": 0,
            "date": None, "gps": None}.get(f.type, "")


def format_value(f: Field, value) -> str:
    """Human readable short text for a table cell."""
    if value is None or value == "" or (f.type == "time" and value == "00:00"):
        return ""
    if f.type == "bool":
        return "✓" if value else ""
    if f.type == "date":
        try:
            return date.fromisoformat(str(value)[:10]).strftime("%d.%m.%Y")
        except ValueError:
            return str(value)
    if f.type == "float":
        if not value:
            return ""
        return f"{float(value):.{f.decimals}f}".rstrip("0").rstrip(".") + (f" {f.suffix}" if f.suffix else "")
    if f.type in ("int", "rating"):
        if not value:
            return ""
        return ("★" * int(value)) if f.type == "rating" else f"{value}{(' ' + f.suffix) if f.suffix else ''}"
    if f.type == "multichoice":
        return ", ".join(value) if value else ""
    if f.type == "gps":
        return f"{value['lat']:.5f}, {value['lon']:.5f}" if isinstance(value, dict) and "lat" in value else ""
    if f.type == "list":
        return f"{len(value)} × {f.item_label}" if value else ""
    text = str(value).replace("\n", " ")
    return text if len(text) <= 80 else text[:77] + "…"


class PartnerCompleter(QCompleter):
    """Completes the last name in a comma separated list."""

    def pathFromIndex(self, index):
        current = self.widget().text()
        head = current.rsplit(",", 1)[0] + ", " if "," in current else ""
        return head + super().pathFromIndex(index)

    def splitPath(self, path):
        return [path.rsplit(",", 1)[-1].strip()]


def make_widget(f: Field, db, parent=None, extra: list[str] | None = None) -> QWidget:
    """``extra``: more suggestions, e.g. values typed in the other items of the same list in the open dialog."""
    t = f.type
    if t == "multiline":
        w = QPlainTextEdit(parent)
        w.setStyleSheet("QPlainTextEdit { min-height: 30px; }")      # the global style asks for 80 px
        w.setFixedHeight(62)
        w.setTabChangesFocus(True)
    elif t == "int" or t == "rating":
        w = QSpinBox(parent)
        w.setMaximum(5 if t == "rating" else int(f.maximum))
        w.setMinimum(0)
        w.setSingleStep(int(f.step))
        if f.suffix:
            w.setSuffix(" " + f.suffix)
        if t == "rating":
            w.setSpecialValueText("–")
    elif t == "float":
        w = QDoubleSpinBox(parent)
        w.setDecimals(f.decimals)
        w.setMaximum(f.maximum)
        w.setMinimum(f.minimum)
        w.setSingleStep(f.step)
        if f.suffix:
            w.setSuffix(" " + f.suffix)
    elif t == "date":
        w = DateField(parent)
        w.setDate(QDate.currentDate())
    elif t == "time":
        w = QTimeEdit(parent)
        w.setDisplayFormat("HH:mm")
    elif t == "bool":
        w = QCheckBox(parent)
    elif t == "choice":
        w = ComboBox(parent)
        w.setEditable(True)
        options = list(f.choices or [])
        if f.suggest and db is not None:
            options += [o for o in f.suggest(db) if o not in options]
        options += [o for o in extra or [] if o not in options]
        w.addItems([""] + options)
        w.setInsertPolicy(QComboBox.NoInsert)
        w.completer().setCaseSensitivity(Qt.CaseInsensitive)
        w.completer().setFilterMode(Qt.MatchContains)
    elif t == "list":
        w = ListEditor(f, db, parent)
    elif t == "multichoice":
        w = MultiChoice(f, db, parent)
    elif t == "gps":
        w = GpsEdit(db, parent)
    else:  # text / partners
        w = QLineEdit(parent)
        if f.suggest and db is not None:
            words = list(f.suggest(db)) + [o for o in extra or []]
            completer = PartnerCompleter(words, w) if t == "partners" else QCompleter(words, w)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
            w.setCompleter(completer)
    return w


def set_combo(combo: QComboBox, text: str):
    """Show ``text`` in an editable combo AND select its item, so Up / Down continue from there."""
    i = combo.findText(text, Qt.MatchExactly)
    if i >= 0:
        combo.setCurrentIndex(i)
    else:
        combo.setCurrentText(text)


def set_widget_value(f: Field, w: QWidget, value):
    t = f.type
    if value is None:
        value = default_value(f)
    if t == "multiline":
        w.setPlainText(str(value or ""))
    elif t in ("int", "rating"):
        w.setValue(int(value or 0))
    elif t == "float":
        w.setValue(float(value or 0))
    elif t == "date":
        if value:
            d = date.fromisoformat(str(value)[:10])
            w.setDate(QDate(d.year, d.month, d.day))
    elif t == "time":
        h, _, m = str(value or "00:00").partition(":")
        w.setTime(QTime(int(h or 0), int(m or 0)))
    elif t == "bool":
        w.setChecked(bool(value))
    elif t == "choice":
        set_combo(w, str(value or ""))
    elif t == "list":
        w.set_items(value or [])
    elif t == "multichoice":
        w.set_values(value or [])
    elif t == "gps":
        w.set_position(value)
    else:
        w.setText(str(value or ""))


def get_widget_value(f: Field, w: QWidget):
    t = f.type
    if t == "multiline":
        return w.toPlainText().strip()
    if t in ("int", "rating"):
        return w.value()
    if t == "float":
        return round(w.value(), f.decimals)
    if t == "date":
        return w.date().toPython().isoformat()
    if t == "time":
        return w.time().toString("HH:mm")
    if t == "bool":
        return w.isChecked()
    if t == "choice":
        return w.currentText().strip()
    if t == "list":
        return w.items()
    if t == "multichoice":
        return w.values()
    if t == "gps":
        return w.position()
    return w.text().strip()


class MultiChoice(QWidget):
    """Checkable list of options (e.g. maneuvers) plus a box to add your own."""

    def __init__(self, f: Field, db, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QListView, QListWidget, QListWidgetItem
        self._Item = QListWidgetItem
        self.f = f
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.setFlow(QListView.LeftToRight)
        self.list.setWrapping(True)
        self.list.setResizeMode(QListView.Adjust)
        self.list.setSpacing(2)
        self.list.setMinimumHeight(64)
        self.list.setMaximumHeight(150)
        self.list.setSelectionMode(QAbstractItemView.NoSelection)
        self.list.itemClicked.connect(lambda it: it.setCheckState(
            Qt.Unchecked if it.checkState() == Qt.Checked else Qt.Checked))
        layout.addWidget(self.list)
        row = QHBoxLayout()
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Add a maneuver …")
        add = QPushButton("Add")
        row.addWidget(self.entry, 1)
        row.addWidget(add)
        layout.addLayout(row)
        add.clicked.connect(self._add_custom)
        self.entry.returnPressed.connect(self._add_custom)
        options = list(f.choices or [])
        if f.suggest and db is not None:
            options += [o for o in f.suggest(db) if o not in options]
        for o in options:
            self._add(o, False)

    def _add(self, text: str, checked: bool):
        for i in range(self.list.count()):
            if self.list.item(i).text() == text:
                self.list.item(i).setCheckState(Qt.Checked if checked else self.list.item(i).checkState())
                return
        item = self._Item(text)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.list.addItem(item)

    def _add_custom(self):
        text = self.entry.text().strip()
        if text:
            self._add(text, True)
            self.entry.clear()

    def set_values(self, values: list[str]):
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(Qt.Unchecked)
        for v in values:
            self._add(v, True)

    def values(self) -> list[str]:
        return [self.list.item(i).text() for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.Checked]


class GpsEdit(QWidget):
    """A single map-pin button: opens the map to pick, change or remove the position (coordinates are typed /
    cleared there). The pin is red while a position is set."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._pos: dict | None = None
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.button = QPushButton()
        self.button.setFixedSize(56, 32)
        self.button.setIconSize(QSize(22, 22))
        self.button.clicked.connect(self.pick)
        row.addWidget(self.button)
        row.addStretch()
        self._refresh()

    def _refresh(self):
        has = self._pos is not None
        self.button.setIcon(icons.icon("map_pin", "#c62f3e" if has else "#52514e", 22))
        self.button.setToolTip(f"Position: {format_coords(self._pos['lat'], self._pos['lon'])}\nClick to change or remove"
                               if has else "Pick the position on a map")

    def set_position(self, value):
        self._pos = {"lat": value["lat"], "lon": value["lon"]} if isinstance(value, dict) and "lat" in value else None
        self._refresh()

    def position(self):
        return dict(self._pos) if self._pos else None

    def _fallback(self):
        """Where to open the map without a position: the mean of the positions already logged."""
        pts = [(r["gps"]["lat"], r["gps"]["lon"]) for _, r in self.db.all_entries()
               if isinstance(r.get("gps"), dict)] if self.db is not None else []
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)) if pts else None

    def pick(self):
        cur = self.position()
        dlg = MapPickDialog((cur["lat"], cur["lon"]) if cur else None, self._fallback(), self.window())
        if dlg.exec():
            if dlg.cleared:
                self.set_position(None)
            elif dlg.result:
                self.set_position({"lat": dlg.result[0], "lon": dlg.result[1]})


NO_PREFILL = {"grade", "grade_wi", "grade_m", "style", "attempts", "orientation"}    # differ from route to route
RECENCY = 30           # an entry this many entries back counts half as much as the newest one
MIN_SHARE = 0.3        # a prefilled value must hold at least this share of the weight, else the field stays empty


class RecordForm(QWidget):
    """Form for a list of fields; groups fields with a ``tab`` into a QTabWidget."""

    def __init__(self, fields: list[Field], db, parent=None, cascade=None, extra: dict | None = None,
                 card: bool = False):
        """cascade = (chain, pool): chain lists field keys from top to bottom (country, region, range, ...);
        pool(key) returns the records the suggestions for that key are taken from."""
        super().__init__(parent)
        from PySide6.QtWidgets import QTabWidget
        self.fields = fields
        self._chain: list[str] = []
        self._pool = None
        self._busy = False
        self._auto: set[str] = set()         # chain fields still holding a prefilled value (follow their parents)
        self._hist_ids: set[int] = set()     # ids of the previous entries of this kind (see prefill)
        self.widgets: dict[str, QWidget] = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        if card:                       # the form sits on a white card
            self.setObjectName("formCard")
            self.setAttribute(Qt.WA_StyledBackground, True)
            outer.setContentsMargins(20, 2, 20, 10)
        main_form = QGridLayout()
        main_form.setHorizontalSpacing(16)
        main_form.setVerticalSpacing(2)
        main_form.setColumnStretch(0, 1)
        main_form.setColumnStretch(1, 1)
        outer.addLayout(main_form)
        self._row = 0
        self._half = 0            # 1: the next compact field fills the right half of the current row
        tabs = None
        tab_forms: dict[str, QFormLayout] = {}
        for f in fields:
            w = make_widget(f, db, self, (extra or {}).get(f.key))
            self.widgets[f.key] = w
            if f.tab:
                if tabs is None:
                    tabs = QTabWidget(self)
                    outer.addWidget(tabs, 1)
                if f.tab not in tab_forms:
                    page = QWidget()
                    tab_forms[f.tab] = QFormLayout(page) if f.type != "list" else QVBoxLayout(page)
                    tabs.addTab(page, f.tab)
                layout = tab_forms[f.tab]
                if isinstance(layout, QFormLayout):
                    layout.addRow(f.label + ":", w)
                else:
                    layout.addWidget(w)
            elif f.type == "list":
                self._finish_row()
                main_form.addWidget(w, 2 * self._row, 0, 2, 2)
                self._row += 1
            elif f.type not in WIDE_TYPES and not f.wide:       # short inputs pair up, two per row
                if f.new_row:
                    self._finish_row()
                self._cell(main_form, f, w, self._half, 1)
                if self._half:
                    self._row += 1
                self._half ^= 1
            else:                                                # long inputs: partner, names, notes
                self._finish_row()
                self._cell(main_form, f, w, 0, 2)
                self._row += 1
        self._finish_row()
        order = [self.widgets[f.key] for f in fields]       # Tab walks through the fields top to bottom
        for a, b in zip(order, order[1:]):
            QWidget.setTabOrder(a, b)
        if cascade:
            self._setup_cascade(*cascade)

    def _cell(self, grid: QGridLayout, f: Field, w: QWidget, col: int, span: int):
        """Small label above its input; ``col`` / ``span`` place it in the two-column grid."""
        label = QLabel(f.label + (" *" if f.required else ""))
        label.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 9pt; padding-top: 6px;")
        grid.addWidget(label, 2 * self._row, col, 1, span)
        grid.addWidget(w, 2 * self._row + 1, col, 1, span)

    def _finish_row(self):
        """A lone compact field keeps the left half; the next field starts on a new row."""
        if self._half:
            self._half = 0
            self._row += 1

    # ---- dependent dropdowns: each level only offers values seen under the selected parents
    def _setup_cascade(self, chain: list[str], pool):
        self._chain = [k for k in chain if k in self.widgets and isinstance(self.widgets[k], QComboBox)]
        self._pool = pool
        for i, key in enumerate(self._chain):
            combo = self.widgets[key]
            combo.currentTextChanged.connect(lambda _t, i=i: self._refresh_below(i))
            combo.activated.connect(lambda _ix, key=key: self._auto.discard(key))     # chosen by the user
            combo.activated.connect(lambda _ix, i=i: self._autofill_parents(i))
            if combo.lineEdit() is not None:
                combo.lineEdit().editingFinished.connect(lambda i=i: self._autofill_parents(i))
                combo.lineEdit().textEdited.connect(lambda _t, key=key: self._auto.discard(key))
        self._refresh_below(-1)

    def _text(self, key: str) -> str:
        return self.widgets[key].currentText().strip()

    def _matching(self, i: int, upto: int):
        """Records of the pool of level i consistent with the selected values of levels 0..upto-1."""
        key = self._chain[i]
        selected = [(j, self._text(self._chain[j])) for j in range(upto) if self._text(self._chain[j])]
        out = []
        for r in self._pool(key):
            ok = True
            for n, (j, txt) in enumerate(selected):
                value = r.get(self._chain[j])
                nearest = n == len(selected) - 1
                # nearest selected parent must match exactly; higher ones only if the record has a value
                if value != txt and (nearest or value):
                    ok = False
                    break
            if ok:
                out.append(r)
        return out

    def _refresh_below(self, changed: int):
        if self._busy:
            return
        self._busy = True
        try:
            for i in range(changed + 1, len(self._chain)):
                key = self._chain[i]
                combo = self.widgets[key]
                matching = self._matching(i, i)
                counts: dict[str, float] = {}
                for idx, r in enumerate(matching):          # newest first: recent entries weigh more
                    v = r.get(key)
                    if v:
                        counts[str(v)] = counts.get(str(v), 0) + 0.5 ** (idx / RECENCY)
                options = sorted(counts, key=lambda v: (-counts[v], v.lower()))
                text = combo.currentText()
                if key in self._auto:                       # prefilled value follows a changed parent
                    text = self._probable(key, matching, 0.0)
                combo.blockSignals(True)
                combo.clear()
                combo.addItems([""] + options)
                set_combo(combo, text)
                combo.blockSignals(False)
        finally:
            self._busy = False

    def _probable(self, key: str, candidates: list[dict], min_share: float) -> str:
        """Most probable value of a field among newest-first records; entries of this kind count first.
        Empty if no value reaches ``min_share`` of the total weight (too uncertain to prefill)."""
        own = [r for r in candidates if id(r) in self._hist_ids]
        score: dict[str, float] = {}
        for idx, r in enumerate(own or candidates):
            v = r.get(key)
            if v:
                score[str(v)] = score.get(str(v), 0) + 0.5 ** (idx / RECENCY)
        if not score:
            return ""
        best = max(score, key=score.get)
        return best if score[best] >= min_share * sum(score.values()) else ""

    def prefill(self, history: list[dict]):
        """New entry: empty choice fields get their most probable value (recent entries count more),
        so Tab accepts it and Up / Down step through the other options."""
        self._hist_ids = {id(r) for r in history}
        for i, key in enumerate(self._chain):
            if self._text(key):
                continue
            best = self._probable(key, self._matching(i, i), 0.0 if i < 2 else MIN_SHARE)
            if best:
                set_combo(self.widgets[key], best)
                self._auto.add(key)
        for f in self.fields:
            w = self.widgets[f.key]
            if f.type == "choice" and f.key not in self._chain and f.key not in NO_PREFILL                     and not w.currentText().strip():
                best = self._probable(f.key, history, MIN_SHARE)
                if best:
                    set_combo(w, best)

    def first_input(self) -> QWidget | None:
        """First field after the dates: where the cursor starts in a new entry."""
        return next((self.widgets[f.key] for f in self.fields if f.type != "date" and not f.tab), None)

    def _autofill_parents(self, i: int):
        """A chosen value fixes its empty parents when the existing data says unambiguously where it belongs."""
        key = self._chain[i]
        txt = self._text(key)
        if not txt or self._busy:
            return
        recs = [r for r in self._pool(key) if r.get(key) == txt]
        for j in range(i):
            pk = self._chain[j]
            if self._text(pk):
                recs = [r for r in recs if not r.get(pk) or r.get(pk) == self._text(pk)]
                continue
            values = {r.get(pk) for r in recs if r.get(pk)}
            if len(values) == 1:
                set_combo(self.widgets[pk], values.pop())
        self._refresh_below(-1)

    def set_record(self, record: dict):
        for f in self.fields:
            set_widget_value(f, self.widgets[f.key], record.get(f.key))
        if self._chain:
            self._refresh_below(-1)

    def update_record(self, record: dict) -> dict:
        for f in self.fields:
            record[f.key] = get_widget_value(f, self.widgets[f.key])
        return record

    def missing_required(self, record: dict) -> list[str]:
        return [f.label for f in self.fields if f.required and not record.get(f.key)]


class ItemDialog(QDialog):
    """Edits one item of a nested list (e.g. a waypoint or a training set)."""

    def __init__(self, f: Field, db, item: dict | None, parent=None, extra: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle(f.item_label)
        self.setMinimumWidth(480)
        self.item = dict(item or {})
        layout = QVBoxLayout(self)
        self.form = RecordForm(f.sub, db, self, extra=extra)
        self.form.set_record(self.item)
        layout.addWidget(self.form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def result_item(self) -> dict:
        return self.form.update_record(self.item)


class ListEditor(QWidget):
    """Table + add/edit/remove/move buttons for a nested list field."""

    def __init__(self, f: Field, db, parent=None):
        super().__init__(parent)
        self.f, self.db = f, db
        self._items: list[dict] = []
        self.base_date: Callable | None = None   # -> ISO date used as default for new items
        cols = f.columns or [s.key for s in f.sub][:6]
        self.cols = [next(s for s in f.sub if s.key == c) for c in cols]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, len(self.cols), self)
        self.table.setHorizontalHeaderLabels([c.label for c in self.cols])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMinimumHeight(110)
        self.table.doubleClicked.connect(self.edit_item)
        layout.addWidget(self.table)
        row = QHBoxLayout()
        for text, slot in [(f"+ {f.item_label}", self.add_item), ("Edit", self.edit_item),
                           ("Remove", self.remove_item), ("▲", lambda: self.move(-1)),
                           ("▼", lambda: self.move(1))]:
            b = QPushButton(text, self)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch()
        layout.addLayout(row)

    def set_items(self, items: list[dict]):
        self._items = [dict(i) for i in items]
        self.refresh()

    def items(self) -> list[dict]:
        return [dict(i) for i in self._items]

    def refresh(self):
        self.table.setRowCount(len(self._items))
        for r, item in enumerate(self._items):
            for c, col in enumerate(self.cols):
                self.table.setItem(r, c, QTableWidgetItem(format_value(col, item.get(col.key))))

    def _extra_options(self) -> dict:
        """Values typed in this (unsaved) list: selectable in the next item right away."""
        out = {}
        for s in self.f.sub:
            if s.type in ("choice", "text"):
                values = list(dict.fromkeys(i[s.key] for i in self._items if i.get(s.key)))
                if values:
                    out[s.key] = values
        return out

    def current(self) -> int:
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def add_item(self):
        defaults = {s.key: default_value(s) for s in self.f.sub}
        if self._items:  # pre-fill from the previous item, handy for series of sets
            last = self._items[-1]
            for s in self.f.sub:
                if s.type in ("choice", "text", "date") and s.key in last:
                    defaults[s.key] = last[s.key]
        if "date" in defaults and not defaults["date"] and self.base_date:
            defaults["date"] = self.base_date()
        dlg = ItemDialog(self.f, self.db, defaults, self, self._extra_options())
        if dlg.exec():
            self._items.append(dlg.result_item())
            self.refresh()

    def edit_item(self):
        i = self.current()
        if i < 0:
            return
        dlg = ItemDialog(self.f, self.db, self._items[i], self, self._extra_options())
        if dlg.exec():
            self._items[i] = dlg.result_item()
            self.refresh()

    def remove_item(self):
        i = self.current()
        if i >= 0 and QMessageBox.question(self, "Remove", f"Remove this {self.f.item_label}?") == QMessageBox.Yes:
            del self._items[i]
            self.refresh()

    def move(self, step: int):
        i = self.current()
        j = i + step
        if i < 0 or not 0 <= j < len(self._items):
            return
        self._items[i], self._items[j] = self._items[j], self._items[i]
        self.refresh()
        self.table.selectRow(j)


__all__ = ["Field", "RecordForm", "ListEditor", "format_value", "default_value"]
_ = dc_field, QStringListModel  # re-exported names kept for type hints
