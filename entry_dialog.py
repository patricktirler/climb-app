"""Add / edit dialog for any kind of entry, plus the training settings dialog."""
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QFrame, QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QScrollArea, QTabWidget, QToolButton, QVBoxLayout, QWidget,
)

import icons
import schema
import theme
from database import new_id
from fields import Field, ListEditor, RecordForm


class EntryDialog(QDialog):
    def __init__(self, db, kind: str, record: dict | None = None, day: date | None = None, parent=None,
                 initial: dict | None = None):
        super().__init__(parent)
        self.db, self.kind = db, kind
        # Hike & Fly paragliding entries managed from this dialog (tours / alpine climbs only):
        self.extra: list[dict] = []        # new records to add when this dialog is saved
        self.updated: list[dict] = []      # already saved linked records that were edited
        self.removed: list[str] = []       # ids of linked records to delete
        self._paras: list[dict] = []       # {"rec": record, "existing": bool}
        spec = schema.KINDS[kind]
        self.record = dict(record) if record else dict(initial or {})
        is_new = record is None
        if is_new:
            self.record.setdefault("id", new_id())       # needed early: linked flights point back to it
        self.setWindowTitle(f"{'New' if is_new else 'Edit'} {spec.label.lower()}")
        self.setMinimumSize(600, 440)
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.addWidget(self._header_band(spec, is_new))
        scroll = self._scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.form = RecordForm(spec.fields, db, cascade=schema.cascade_for(kind, db), card=True)
        self._holder = QWidget()                 # margin around the card
        hl = QVBoxLayout(self._holder)
        hl.setContentsMargins(1, 1, 8, 0)
        hl.addWidget(self.form)
        hl.addStretch()
        scroll.setWidget(self._holder)
        layout.addWidget(scroll, 1)
        if is_new:
            self.record.setdefault("date", (day or date.today()).isoformat())
            if day is not None:
                self.record["date"] = day.isoformat()
        self.form.set_record(self.record)
        if is_new:        # most probable values from the recent entries; Tab accepts, Up / Down change
            history = sorted(db.entries(kind), key=lambda r: r.get("date") or "", reverse=True)[:80]
            self.form.prefill(history)
            first = self.form.first_input()
            if first is not None:
                first.setFocus()
        date_w = self.form.widgets.get("date")
        to_w = self.form.widgets.get("date_to")
        if to_w is not None:
            if not self.record.get("date_to"):
                to_w.setDate(date_w.date())
            # keep 'until' >= 'from' while editing the start date
            date_w.dateChanged.connect(lambda d: to_w.setDate(d) if to_w.date() < d else None)
        for w in self.form.widgets.values():
            if isinstance(w, ListEditor):
                w.base_date = lambda: date_w.date().toPython().isoformat()
        foot = QHBoxLayout()
        if kind in ("mountain_tours", "alpine_climbs"):
            strip = self._build_para_box(record)
            layout.addWidget(self.para_list)              # only visible while there are entries
            foot.addWidget(strip)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setObjectName("primary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        foot.addStretch()
        foot.addWidget(buttons)
        layout.addLayout(foot)
        self._fit_to_form()

    @staticmethod
    def _header_band(spec, is_new: bool) -> QFrame:
        """Title with the category icon on a light tint of the category colour."""
        color = QColor(spec.color)
        tint = QColor(*(int(c * 0.12 + 255 * 0.88) for c in (color.red(), color.green(), color.blue()))).name()
        band = QFrame()
        band.setObjectName("entryHeader")
        band.setStyleSheet(f"QFrame#entryHeader {{ background: {tint}; border: none; border-bottom: 3px solid "
                           f"{spec.color}; border-radius: 8px; }} QFrame#entryHeader QLabel {{ background: transparent; }}")
        row = QHBoxLayout(band)
        row.setContentsMargins(14, 4, 14, 4)
        mark = QLabel()
        mark.setPixmap(icons.pixmap(spec.key, icons.shade(spec.color), 34, 2.3))
        title = QLabel(f"{'New' if is_new else 'Edit'} {spec.label.lower()}")
        title.setObjectName("calendarTitle")
        row.addWidget(mark)
        row.addWidget(title)
        row.addStretch()
        if is_new:
            hint = QLabel("Tab: next field  ·  ↑ ↓: other suggestion")
            hint.setStyleSheet(f"color: {icons.shade(spec.color, 0.7)}; font-size: 9pt;")
            row.addWidget(hint)
        return band

    def _fit_to_form(self):
        """Open large enough to show every field without scrolling (as far as the screen allows)."""
        screen = (self.screen() or QGuiApplication.primaryScreen()).availableGeometry()
        form = self._holder.sizeHint()
        bar = self._scroll.verticalScrollBar().sizeHint().width()
        # let the dialog's own size hint include the whole form, then drop the constraint again
        self._scroll.setMinimumSize(form.width() + bar + 4, form.height() + 4)
        want = self.sizeHint()
        self._scroll.setMinimumSize(0, 0)
        self.resize(min(max(want.width(), self.minimumWidth()), screen.width() - 40),
                    min(max(want.height(), self.minimumHeight()), screen.height() - 40))

    # ---------------------------------------------------- Hike & Fly entries
    def _build_para_box(self, record: dict | None) -> QFrame:
        """Slim strip: title, number of linked flight entries and the buttons; the list shows below when needed."""
        color = QColor(theme.KIND_COLORS["paragliding"])
        tint = QColor(*(int(c * 0.12 + 255 * 0.88) for c in (color.red(), color.green(), color.blue()))).name()
        strip = QFrame()
        strip.setObjectName("paraStrip")
        strip.setStyleSheet(f"QFrame#paraStrip {{ background: {tint}; border: none; border-radius: 8px; }}"
                            "QFrame#paraStrip QLabel { background: transparent; }"
                            "QFrame#paraStrip QPushButton, QFrame#paraStrip QToolButton { background: white; "
                            f"border: 1px solid {theme.BORDER}; border-radius: 6px; padding: 3px 10px; }}"
                            "QFrame#paraStrip QToolButton { padding: 3px 6px; }"
                            "QFrame#paraStrip QPushButton:hover, QFrame#paraStrip QToolButton:hover "
                            "{ background: #f3eef6; }")
        row = QHBoxLayout(strip)
        row.setContentsMargins(10, 4, 8, 4)
        row.setSpacing(6)
        mark = QLabel()
        mark.setPixmap(icons.pixmap("paragliding", icons.shade(theme.KIND_COLORS["paragliding"]), 26, 2.2))
        title = QLabel("Hike & Fly")
        title.setStyleSheet("font-weight: 600;")
        self.para_count = QLabel()
        self.para_count.setObjectName("muted")
        add = QPushButton("+ Flight entry")
        add.setToolTip("Log a paragliding flight (Hike & Fly) for this entry")
        add.clicked.connect(self.add_hike_fly)
        self.para_edit = QToolButton()
        self.para_edit.setIcon(icons.icon("pencil", theme.TEXT_SECONDARY, 18))
        self.para_edit.setToolTip("Edit the selected flight entry")
        self.para_edit.clicked.connect(self.edit_hike_fly)
        self.para_remove = QToolButton()
        self.para_remove.setIcon(icons.icon("trash", "#b3261e", 18))
        self.para_remove.setToolTip("Remove the selected flight entry")
        self.para_remove.clicked.connect(self.remove_hike_fly)
        for w in (mark, title, self.para_count, add, self.para_edit, self.para_remove):
            row.addWidget(w)
        self.para_list = QListWidget()
        self.para_list.setStyleSheet("QListWidget { min-height: 0; }")
        self.para_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.para_list.itemDoubleClicked.connect(lambda _i: self.edit_hike_fly())
        if record is not None:      # editing: show the paragliding entries already linked to this one
            for r in self.db.entries("paragliding"):
                if r.get("source_id") == record.get("id"):
                    self._paras.append({"rec": dict(r), "existing": True})
        self._refresh_paras()
        return strip

    def _refresh_paras(self):
        keep = self.para_list.currentRow()
        self.para_list.clear()
        for p in self._paras:
            r = p["rec"]
            tot = schema.para_totals(r)
            text = " · ".join(x for x in [r.get("date", ""), r.get("mountain") or r.get("site") or "Paragliding",
                                          r.get("type", ""), f"{tot['flights']} flight(s)" if tot["flights"] else "",
                                          f"{tot['airtime']} min" if tot["airtime"] else ""] if x)
            item = QListWidgetItem(text + ("" if p["existing"] else "   (new)"))
            self.para_list.addItem(item)
        n = len(self._paras)
        if n:
            self.para_list.setCurrentRow(min(max(keep, 0), n - 1))
        self.para_list.setVisible(bool(n))
        self.para_list.setFixedHeight(min(n, 3) * 24 + 8)
        self.para_count.setText(f"{n} entr{'y' if n == 1 else 'ies'}" if n else "no entries yet")
        for b in (self.para_edit, self.para_remove):
            b.setEnabled(bool(n))

    def _selected_para(self):
        row = self.para_list.currentRow()
        return (row, self._paras[row]) if 0 <= row < len(self._paras) else (None, None)

    def add_hike_fly(self):
        """Paragliding entry pre-filled from the current (unsaved) form values; saved together with this entry."""
        current = self.form.update_record(dict(self.record))
        current.setdefault("date", date.today().isoformat())
        dlg = EntryDialog(self.db, "paragliding", initial=schema.hike_fly_prefill(self.kind, current), parent=self)
        if dlg.exec():
            self._paras.append({"rec": dlg.record, "existing": False})
            self._refresh_paras()
            self.para_list.setCurrentRow(len(self._paras) - 1)

    def edit_hike_fly(self):
        row, p = self._selected_para()
        if p is None:
            QMessageBox.information(self, "Edit", "Select a paragliding entry in the list first.")
            return
        dlg = EntryDialog(self.db, "paragliding", p["rec"], parent=self)
        if dlg.exec():
            p["rec"] = dlg.record
            p["changed"] = True
            self._refresh_paras()
            self.para_list.setCurrentRow(row)

    def remove_hike_fly(self):
        row, p = self._selected_para()
        if p is None:
            QMessageBox.information(self, "Remove", "Select a paragliding entry in the list first.")
            return
        if QMessageBox.question(self, "Remove", "Remove this paragliding entry?") != QMessageBox.Yes:
            return
        if p["existing"]:
            self.removed.append(p["rec"]["id"])
        del self._paras[row]
        self._refresh_paras()

    def accept(self):
        record = self.form.update_record(dict(self.record))
        missing = self.form.missing_required(record)
        if missing:
            QMessageBox.warning(self, "Missing fields", "Please fill in: " + ", ".join(missing))
            return
        if record.get("date_to") and record["date_to"] <= record["date"]:
            record["date_to"] = None
        record.setdefault("id", new_id())
        self.record = record
        for p in self._paras:
            p["rec"]["source_id"], p["rec"]["source_kind"] = record["id"], self.kind
        self.extra = [p["rec"] for p in self._paras if not p["existing"]]
        self.updated = [p["rec"] for p in self._paras if p["existing"] and p.get("changed")]
        super().accept()


METHOD_FIELDS = [
    Field("discipline", "Discipline", "choice", choices=["Boulder", "Lead", "Kraft"]),
    Field("name", "Name", required=True),
    Field("description", "Description", "multiline"),
    Field("holds_text", "Devices / holds", default=""),
]
class TrainingSettingsDialog(QDialog):
    """Edit the catalogue of training methods (with their devices / holds)."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Training methods")
        self.setMinimumSize(760, 560)
        layout = QVBoxLayout(self)
        methods = [dict(m, holds_text=", ".join(m.get("holds") or [])) for m in db.methods]
        self.methods = ListEditor(Field("methods", "Methods", "list", item_label="Method",
                                        columns=["discipline", "name", "holds_text"], sub=METHOD_FIELDS), db)
        self.methods.set_items(methods)
        layout.addWidget(self.methods)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        methods = []
        for m in self.methods.items():
            text = m.pop("holds_text", "")
            m["holds"] = [h.strip() for h in text.split(",") if h.strip()]
            methods.append(m)
        self.db.data["training"]["methods"] = methods
        self.db.save()
        super().accept()


__all__ = ["EntryDialog", "TrainingSettingsDialog", "QDate"]
