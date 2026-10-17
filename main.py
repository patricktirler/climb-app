"""ClimbApp V2 — climbing logbook. Entry point and main window."""
import csv
import os
import sys
import traceback
from datetime import date
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QImage, QKeySequence, QPainter, QShortcut, QColor
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QDialog, QDialogButtonBox, QFileDialog, QFrame, QGroupBox,
    QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMenu, QMessageBox, QPushButton, QSplitter,
    QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

import config
import icons
import inbox
import schema
import theme
from calendar_widget import CalendarWidget, MonthGrid
from database import Database, new_id
from detail_panel import DetailPanel
from entry_dialog import EntryDialog, TrainingSettingsDialog
from fields import format_value
from list_view import ListView
from stats_view import StatsView


INBOX_POLL_MS = 60_000


class ShrinkStack(QStackedWidget):
    """Pages never force the window wider than the screen: showing the detail panel next to a page whose
    own minimum width was large used to grow the window and drop it out of full screen."""

    def minimumSizeHint(self):
        return QSize(380, 300)


class MainWindow(QMainWindow):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.setWindowTitle(f"ClimbApp — {db.path.name}")
        self.setWindowIcon(QIcon(str(config.ICON_PATH)))
        self.resize(1500, 900)
        self._full: str | None = None          # "list" / "stats" / "detail" while shown full screen
        self._was_maximized = True

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.header_frame = self._header()
        root.addWidget(self.header_frame)

        body = QSplitter(Qt.Horizontal)
        body.setContentsMargins(12, 12, 12, 12)
        self.stack = ShrinkStack()
        self.calendar = CalendarWidget(db)
        self.list_view = ListView(db)
        self.stats = StatsView(db)
        for w in (self.calendar, self.list_view, self.stats):
            self.stack.addWidget(w)
        self.detail = DetailPanel(db)
        self.detail.hide()
        body.addWidget(self.stack)
        body.addWidget(self.detail)
        body.setStretchFactor(0, 1)
        holder = QWidget()
        hl = QVBoxLayout(holder)
        hl.setContentsMargins(12, 10, 12, 8)
        hl.addWidget(body)
        root.addWidget(holder, 1)

        self.calendar.entry_clicked.connect(self.show_detail)
        self.calendar.entry_activated.connect(self.edit_entry)
        self.calendar.add_requested.connect(self.add_entry)
        self.calendar.day_clicked.connect(self.show_day)
        self.detail.add_requested.connect(self.add_entry)
        self.detail.entry_chosen.connect(self.pick_entry)
        self.detail.hike_fly_requested.connect(self.add_hike_fly)
        self.list_view.entry_selected.connect(self.show_detail)
        self.list_view.entry_activated.connect(self.edit_entry)
        self.stats.open_entry.connect(self.open_entry)
        self.detail.edit_requested.connect(self.edit_entry)
        self.detail.delete_requested.connect(self.delete_entry)
        self.detail.duplicate_requested.connect(self.duplicate_entry)
        self.detail.full_requested.connect(lambda: self.toggle_full("detail"))
        self.detail.closed.connect(self._detail_closed)
        self.list_view.full_btn.clicked.connect(lambda: self.toggle_full("list"))
        self.stats.full_btn.clicked.connect(lambda: self.toggle_full("stats"))

        QShortcut(QKeySequence.New, self, activated=lambda: self.add_entry(self._default_kind()))
        QShortcut(QKeySequence("Ctrl+1"), self, activated=lambda: self.switch(0))
        QShortcut(QKeySequence("Ctrl+2"), self, activated=lambda: self.switch(1))
        QShortcut(QKeySequence("Ctrl+3"), self, activated=lambda: self.switch(2))
        QShortcut(QKeySequence.Find, self, activated=self._focus_search)
        QShortcut(QKeySequence("PgUp"), self.calendar, activated=lambda: self.calendar.step(-1))
        QShortcut(QKeySequence("PgDown"), self.calendar, activated=lambda: self.calendar.step(1))
        QShortcut(QKeySequence("Escape"), self, activated=self._escape)
        QShortcut(QKeySequence("F11"), self, activated=self._toggle_full_current)
        self._update_status()
        self._inbox_logged: set[str] = set()
        self.inbox_timer = QTimer(self)                     # entries from the phone app arrive via Drive
        self.inbox_timer.timeout.connect(lambda: self.import_inbox(quiet=True))
        self.inbox_timer.start(INBOX_POLL_MS)
        QTimer.singleShot(0, lambda: self.import_inbox(quiet=True))

    # -------------------------------------------------------------- header
    def _header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 10, 16, 10)
        icon = QLabel()
        icon.setPixmap(QIcon(str(config.ICON_PATH)).pixmap(30, 30))
        layout.addWidget(icon)
        title = QLabel("ClimbApp")
        title.setObjectName("appTitle")
        layout.addWidget(title)
        layout.addSpacing(24)
        self.view_group = QButtonGroup(self)
        for i, (text, tip, ico) in enumerate([("Calendar", "Ctrl+1", "calendar"), ("List", "Ctrl+2", "list"),
                                              ("Statistics", "Ctrl+3", "chart")]):
            b = QPushButton(text)
            b.setIcon(icons.icon(ico, "#ffffff", 24, on_color=theme.HEADER))
            b.setIconSize(QSize(24, 24))
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.setToolTip(tip)
            self.view_group.addButton(b, i)
            b.clicked.connect(lambda _=False, i=i: self.switch(i))
            layout.addWidget(b)
        layout.addStretch()
        add = QToolButton()
        add.setText("New entry")
        add.setObjectName("primary")
        add.setIcon(icons.icon("plus", theme.HEADER, 24))
        add.setIconSize(QSize(24, 24))
        add.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        add.setStyleSheet(f"QToolButton {{ background: {theme.SURFACE}; color: {theme.HEADER}; border: none; border-radius: 6px;"
                          "padding: 6px 14px; font-weight: 700; } QToolButton:hover { background: #e9e8e2; }"
                          "QToolButton::menu-indicator { image: none; }")
        add.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(add)
        for kind in schema.ADDABLE:
            act = menu.addAction(icons.icon(kind, icons.shade(schema.KINDS[kind].color), 28, width=2.3), schema.KINDS[kind].label)
            act.triggered.connect(lambda _=False, k=kind: self.add_entry(k))
        add.setMenu(menu)
        layout.addWidget(add)
        training = QPushButton("Training setup")
        training.setIcon(icons.icon("training_sessions", "#ffffff", 24))
        training.setIconSize(QSize(24, 24))
        training.setToolTip("Training methods and their devices / holds")
        training.clicked.connect(self.training_settings)
        layout.addWidget(training)
        settings = QPushButton("Settings")
        settings.setIcon(icons.icon("sliders", "#ffffff", 24))
        settings.setIconSize(QSize(24, 24))
        settings.clicked.connect(self.open_settings)
        layout.addWidget(settings)
        return header

    # ---------------------------------------------------------- full screen
    def _toggle_full_current(self):
        """F11: leave full screen, or show the current view (list / statistics, else the open entry) full screen."""
        if self._full:
            self.exit_full()
        elif self.stack.currentIndex() == 1:
            self.toggle_full("list")
        elif self.stack.currentIndex() == 2:
            self.toggle_full("stats")
        elif self.detail.isVisible():
            self.toggle_full("detail")

    def _escape(self):
        if self._full:
            self.exit_full()
        else:
            self.detail.hide()

    def toggle_full(self, which: str):
        if self._full == which:
            self.exit_full()
        else:
            self.enter_full(which)

    def enter_full(self, which: str):
        if which == "detail" and not self.detail.isVisible():
            return
        if self._full is None:
            self._was_maximized = self.isMaximized()
            self.showFullScreen()
        self._full = which
        self.header_frame.hide()
        self.statusBar().hide()
        if which == "detail":
            self.stack.hide()
            self.detail.set_full(True)
        else:
            self.stack.show()
            self.detail.set_full(False)
            self.detail.hide()
            self.switch(1 if which == "list" else 2)
        self._sync_full_buttons()

    def exit_full(self):
        if self._full is None:
            return
        self._full = None
        self.header_frame.show()
        self.statusBar().show()
        self.stack.show()
        self.detail.set_full(False)
        self.showMaximized() if self._was_maximized else self.showNormal()
        self._sync_full_buttons()

    def _sync_full_buttons(self):
        self.list_view.full_btn.set_active(self._full == "list")
        self.stats.full_btn.set_active(self._full == "stats")
        self.detail.full_btn.set_active(self._full == "detail")

    def _detail_closed(self):
        if self._full == "detail":
            self.exit_full()

    def switch(self, index: int):
        self.stack.setCurrentIndex(index)
        self.view_group.button(index).setChecked(True)

    def _focus_search(self):
        self.switch(1)
        self.list_view.search.setFocus()
        self.list_view.search.selectAll()

    def _default_kind(self):
        return self.list_view.kind if self.stack.currentIndex() == 1 else "climbing_days"

    def _update_status(self):
        n = sum(1 for _ in self.db.all_entries())
        self.statusBar().showMessage(f"{n} entries  ·  {self.db.path}")

    # ------------------------------------------------------------- actions
    def refresh(self, kind: str | None = None, select: str | None = None):
        self.calendar.refresh()
        if kind and kind != self.list_view.kind and self.stack.currentIndex() == 1:
            self.list_view.set_kind(kind)
        self.list_view.refresh(select)
        self.stats.refresh()
        self._update_status()

    def show_detail(self, kind: str, entry_id: str):
        if self._full in ("list", "stats"):      # these views own the whole window
            return
        self.detail.show_entry(kind, entry_id)

    def open_entry(self, kind: str, entry_id: str):
        if self._full == "stats":
            self.exit_full()
        self.show_detail(kind, entry_id)

    def show_day(self, day):
        self.detail.show_day(day, self.calendar.month_grid.index.get(day, []))

    def pick_entry(self, kind: str, entry_id: str):
        """Entry chosen in the day view: show it and mark it in the calendar."""
        self.calendar.select(kind, entry_id)
        self.show_detail(kind, entry_id)

    def add_hike_fly(self, kind: str, entry_id: str):
        record = self.db.get(kind, entry_id)
        if record is None:
            return
        dlg = EntryDialog(self.db, "paragliding", initial=schema.hike_fly_prefill(kind, record), parent=self)
        if dlg.exec():
            self.db.add("paragliding", dlg.record)
            self.refresh("paragliding", dlg.record["id"])
            self.show_detail("paragliding", dlg.record["id"])
            self.statusBar().showMessage("Added paragliding entry (Hike & Fly)", 4000)

    def _save_extra(self, dlg: "EntryDialog"):
        """Apply the Hike & Fly entries added / edited / removed inside a tour or alpine dialog."""
        for rec in dlg.extra:
            self.db.add("paragliding", rec, save=False)
        for rec in dlg.updated:
            entries = self.db.entries("paragliding")
            for i, old in enumerate(entries):
                if old["id"] == rec["id"]:
                    entries[i] = rec
        if dlg.removed:
            self.db.data["entries"]["paragliding"] = [r for r in self.db.entries("paragliding")
                                                      if r["id"] not in dlg.removed]
        if dlg.extra or dlg.updated or dlg.removed:
            self.db.save()

    def add_entry(self, kind: str, day=None):
        dlg = EntryDialog(self.db, kind, day=day if isinstance(day, date) else None, parent=self)
        if dlg.exec():
            self.db.add(kind, dlg.record)
            self._save_extra(dlg)
            self.refresh(kind, dlg.record["id"])
            self.calendar.select(kind, dlg.record["id"])
            self.show_detail(kind, dlg.record["id"])
            self.statusBar().showMessage(f"Added {schema.KINDS[kind].label.lower()}", 4000)

    def edit_entry(self, kind: str, entry_id: str):
        record = self.db.get(kind, entry_id)
        if record is None:
            return
        dlg = EntryDialog(self.db, kind, record, parent=self)
        if dlg.exec():
            self.db.update(kind, dlg.record)
            self._save_extra(dlg)
            self.refresh(kind, entry_id)
            self.show_detail(kind, entry_id)
            self.statusBar().showMessage("Saved", 4000)

    def duplicate_entry(self, kind: str, entry_id: str):
        record = self.db.get(kind, entry_id)
        if record is None:
            return
        copy = dict(record, id=new_id(), date=date.today().isoformat(), date_to=None)
        dlg = EntryDialog(self.db, kind, copy, parent=self)
        dlg.setWindowTitle("Duplicate entry")
        if dlg.exec():
            self.db.add(kind, dlg.record)
            self.refresh(kind, dlg.record["id"])
            self.show_detail(kind, dlg.record["id"])

    def delete_entry(self, kind: str, entry_id: str):
        record = self.db.get(kind, entry_id)
        if record is None:
            return
        spec = schema.KINDS[kind]
        if QMessageBox.question(self, "Delete entry",
                                f"Delete this {spec.label.lower()}?\n\n{spec.title(record)}  ({record.get('date')})"
                                ) != QMessageBox.Yes:
            return
        self.db.delete(kind, entry_id)
        self.detail.hide()
        self.refresh()
        self.statusBar().showMessage("Deleted", 4000)

    def import_inbox(self, quiet: bool = False) -> int:
        """Take over the entries the phone app put into the synced inbox folder."""
        folder = config.inbox_path()
        added, problems = inbox.import_inbox(self.db, folder)
        if added:
            self.refresh(added[-1][0])
            self.statusBar().showMessage(f"Imported {len(added)} entries from the phone", 8000)
        new_problems = [p for p in problems if p not in self._inbox_logged]      # a stuck file would repeat every minute
        if new_problems:
            self._inbox_logged.update(new_problems)
            log = config.SETTINGS_FILE.parent / "inbox.log"
            try:
                log.parent.mkdir(parents=True, exist_ok=True)
                with open(log, "a", encoding="utf-8") as f:
                    f.write("\n".join(new_problems) + "\n")
            except OSError:
                pass
        if not quiet:
            note = "\n\nProblems (see inbox.log):\n" + "\n".join(problems[:5]) if problems else ""
            QMessageBox.information(self, "Phone inbox", (f"{len(added)} new entries imported." if added else
                                    "No new entries." if folder.is_dir() else f"Folder not found:\n{folder}") + note)
        return len(added)

    def training_settings(self):
        if TrainingSettingsDialog(self.db, self).exec():
            self.refresh()

    def open_settings(self):
        SettingsDialog(self).exec()


class SettingsDialog(QDialog):
    def __init__(self, win: MainWindow):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)

        box = QGroupBox("Database")
        bl = QVBoxLayout(box)
        self.path_label = QLabel(str(win.db.path))
        self.path_label.setWordWrap(True)
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bl.addWidget(self.path_label)
        info = QLabel("All data lives in this single file. A backup copy is written to the 'Backups' folder "
                      "next to it every time the app saves for the first time in a session.")
        info.setWordWrap(True)
        info.setObjectName("muted")
        bl.addWidget(info)
        row = QHBoxLayout()
        for text, slot in [("Open folder", self.open_folder), ("Use another file…", self.change_db)]:
            b = QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch()
        bl.addLayout(row)
        layout.addWidget(box)

        box = QGroupBox("Import")
        bl = QVBoxLayout(box)
        lbl = QLabel("Import a data file of the old ClimbApp (V1, *.clmb). All its entries and training methods "
                     "are imported.")
        lbl.setWordWrap(True)
        bl.addWidget(lbl)
        b = QPushButton("Import V1 file…")
        b.clicked.connect(self.import_v1)
        bl.addWidget(b, alignment=Qt.AlignLeft)
        layout.addWidget(box)

        box = QGroupBox("Import sport climbing ticks from 8a.nu")
        bl = QVBoxLayout(box)
        lbl = QLabel("Export your logbook on 8a.nu (profile → logbook export, CSV) and import the file here. "
                     "Gym routes are ignored and ticks you already have are skipped, so you can import a fresh "
                     "export whenever you like and only new ticks are added.")
        lbl.setWordWrap(True)
        bl.addWidget(lbl)
        b = QPushButton("Import 8a.nu CSV…")
        b.clicked.connect(self.import_8a)
        bl.addWidget(b, alignment=Qt.AlignLeft)
        layout.addWidget(box)

        box = QGroupBox("Phone app inbox")
        bl = QVBoxLayout(box)
        self.inbox_label = QLabel(str(config.inbox_path()))
        self.inbox_label.setWordWrap(True)
        self.inbox_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bl.addWidget(self.inbox_label)
        lbl = QLabel("Entries created in the phone app (pwa/) are uploaded to this Google Drive folder and imported "
                     "here automatically, at startup and every minute. Imported files move to 'imported'.")
        lbl.setWordWrap(True)
        lbl.setObjectName("muted")
        bl.addWidget(lbl)
        row = QHBoxLayout()
        for text, slot in [("Import now", lambda: win.import_inbox()), ("Choose folder…", self.change_inbox)]:
            b = QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch()
        bl.addLayout(row)
        layout.addWidget(box)

        box = QGroupBox("Places")
        bl = QVBoxLayout(box)
        lbl = QLabel("Reorganize your mountains (country, region, mountain range, mountain) and rock climbing places "
                     "(country, region, area, crag, sector): rename them, merge them or move them to another parent.")
        lbl.setWordWrap(True)
        bl.addWidget(lbl)
        b = QPushButton("Reorganize places…")
        b.clicked.connect(self.reorganize_places)
        bl.addWidget(b, alignment=Qt.AlignLeft)
        layout.addWidget(box)

        box = QGroupBox("Export")
        bl = QHBoxLayout(box)
        for text, slot in [("Tables as CSV…", self.export_csv), ("Calendar year as image…", self.export_calendar)]:
            b = QPushButton(text)
            b.clicked.connect(slot)
            bl.addWidget(b)
        bl.addStretch()
        layout.addWidget(box)

        about = QLabel(f"ClimbApp {config.APP_VERSION}  ·  © Patrick Tirler")
        about.setObjectName("muted")
        layout.addWidget(about)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def reorganize_places(self):
        from places import PlacesDialog
        dlg = PlacesDialog(self.win.db, self)
        if dlg.exec() and dlg.dirty:
            self.win.refresh()
            self.win.statusBar().showMessage("Places reorganized", 5000)

    def open_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.win.db.path.parent)))

    def change_db(self):
        path, _ = QFileDialog.getSaveFileName(self, "Open or create database", str(self.win.db.path.parent),
                                              "ClimbApp database (*.json)",
                                              options=QFileDialog.DontConfirmOverwrite)
        if not path:
            return
        config.set_database_path(Path(path))
        QMessageBox.information(self, "Database", "The app now uses this file. Restart the app to load it.")
        self.path_label.setText(path)

    def change_inbox(self):
        path = QFileDialog.getExistingDirectory(self, "Inbox folder of the phone app", str(config.inbox_path()))
        if path:
            config.set_inbox_path(Path(path))
            self.inbox_label.setText(path)
            self.win.import_inbox()

    def import_v1(self):
        from import_v1 import import_v1_file
        start = str(config.v1_file()) if config.v1_file().exists() else ""
        path, _ = QFileDialog.getOpenFileName(self, "ClimbApp V1 data file", start, "ClimbApp V1 (*.clmb *.txt);;All files (*)")
        if not path:
            return
        try:
            data = import_v1_file(path)
        except Exception as e:  # noqa: BLE001 - report any parse problem to the user
            QMessageBox.critical(self, "Import failed", f"Could not read the file:\n{e}")
            return
        counts = ", ".join(f"{len(v)} {schema.KINDS[k].plural.lower()}" for k, v in data["entries"].items() if v)
        box = QMessageBox(self)
        box.setWindowTitle("Import V1 data")
        box.setText(f"Found {counts}.\n\nReplace the current data, or add to it?")
        replace = box.addButton("Replace all", QMessageBox.DestructiveRole)
        merge = box.addButton("Add (skip duplicates)", QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        db = self.win.db
        if box.clickedButton() is replace:
            db.data["entries"] = data["entries"]
            db.data["training"] = data["training"]
        elif box.clickedButton() is merge:
            from import_v1 import merge_into
            added = merge_into(db, data)
            QMessageBox.information(self, "Import", f"{added} new entries added.")
        else:
            return
        db.save()
        self.win.refresh()

    def import_8a(self):
        import import_8a
        downloads = Path.home() / "Downloads"
        start = next((str(p) for p in (Path("D:/Downloads/data.csv"), downloads / "data.csv") if p.exists()),
                     str(downloads if downloads.exists() else Path.home()))
        path, _ = QFileDialog.getOpenFileName(self, "8a.nu logbook export (CSV)", start, "CSV files (*.csv);;All files (*)")
        if not path:
            return
        try:
            plan = import_8a.build_plan(self.win.db, path)
        except Exception as e:  # noqa: BLE001 - show any parse problem instead of crashing
            QMessageBox.critical(self, "Import failed", f"Could not read the file:\n{e}")
            return
        text = import_8a.summary_text(plan)
        if not plan.records:
            QMessageBox.information(self, "8a.nu import", text + "\n\nNothing to import.")
            return
        if QMessageBox.question(self, "8a.nu import", text + "\n\nImport them now?") != QMessageBox.Yes:
            return
        added = import_8a.apply_plan(self.win.db, plan)
        self.win.refresh("sport_routes")
        self.win.statusBar().showMessage(f"Imported {added} ticks from 8a.nu", 6000)
        QMessageBox.information(self, "8a.nu import", f"{added} ticks added to the tick list.")

    def export_csv(self):
        folder = QFileDialog.getExistingDirectory(self, "Export CSV files to folder")
        if not folder:
            return
        for kind, spec in schema.KINDS.items():
            records = sorted(self.win.db.entries(kind), key=lambda r: r.get("date", ""))
            if not records:
                continue
            fields = [f for f in spec.fields if f.type != "list"]
            with open(Path(folder) / f"{kind}.csv", "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.writer(fh, delimiter=";")
                w.writerow([f.label for f in fields])
                for r in records:
                    w.writerow([r.get(f.key) if f.type in ("multiline", "text", "choice", "partners")
                                else format_value(f, r.get(f.key)) for f in fields])
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def export_calendar(self):
        year, ok = QInputDialog.getInt(self, "Calendar image", "Year:", date.today().year, 1990, 2100)
        if not ok:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save calendar image", f"Calendar_{year}.png", "PNG (*.png)")
        if not path:
            return
        grid = MonthGrid()
        grid.index = self.win.calendar.month_grid.index
        w, h, title_h = 2000, 1250, 70
        image = QImage(w, (h + title_h) * 12, QImage.Format_RGB32)
        image.fill(QColor(theme.PAGE))
        p = QPainter(image)
        font = p.font()
        font.setPointSize(26)
        font.setBold(True)
        for m in range(1, 13):
            grid.set_month(year, m)
            grid.resize(w, h)
            pix = grid.grab()
            y = (m - 1) * (h + title_h)
            p.setFont(font)
            p.setPen(QColor(theme.TEXT))
            from calendar_widget import MONTHS
            p.drawText(24, y + 50, f"{MONTHS[m - 1]} {year}")
            p.drawPixmap(0, y + title_h, pix)
        p.end()
        image.save(path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def first_run(db: Database):
    """Offer to import the old V1 data when the database is still empty."""
    if any(True for _ in db.all_entries()) or not config.v1_file().exists():
        return
    if QMessageBox.question(None, "Welcome to ClimbApp V2",
                            f"Import your data from the old app?\n\n{config.v1_file()}") == QMessageBox.Yes:
        from import_v1 import import_v1_file
        data = import_v1_file(str(config.v1_file()))
        db.data["entries"], db.data["training"] = data["entries"], data["training"]
        db.save()


def excepthook(exc_type, exc, tb):
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    log = config.SETTINGS_FILE.parent / "error.log"
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError:
        pass
    QMessageBox.critical(None, "Unexpected error", f"{exc}\n\nDetails were written to:\n{log}")


def main():
    if sys.platform == "win32":  # own taskbar icon instead of the python one
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PatrickTirler.ClimbApp.2")
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setWindowIcon(QIcon(str(config.ICON_PATH)))
    app.setStyle("Fusion")
    app.setStyleSheet(theme.STYLESHEET)
    sys.excepthook = excepthook
    db = Database(config.database_path())
    first_run(db)
    window = MainWindow(db)
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
