"""Settings form to organize places: country > region > mountain range > mountain, and
country > region > climbing area > crag > sector.

A place is a *path* of location values. The paths come from the entries (their country / region /
range / mountain ... fields) and from places added here without an entry ("catalogue", see
Database.catalog; the entry form offers them as well). Renaming or moving a place rewrites those
fields in every entry and catalogue path below it.

A range can span several regions or countries: the same name simply exists as a path under each of
them ("Also in…" lists a place and everything below it under another parent without touching the
entries). Renaming can be applied to every occurrence of a name at once.
"""
import copy
from collections import Counter

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMenu, QMessageBox, QPushButton, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget,
)

import schema

LABELS = {"country": "Country", "region": "Region", "range": "Mountain range", "mountain": "Mountain",
          "area": "Climbing area", "crag": "Crag", "sector": "Sector"}
UNSET = "(not set)"
PATH_ROLE = Qt.UserRole + 1


class PlaceTree(QTreeWidget):
    """Drag & drop does not reorder items: it asks the panel to move the dragged places onto the target."""

    dropped = Signal(object, object)      # dragged paths, target path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def dropEvent(self, event):
        sources = [it.data(0, PATH_ROLE) for it in self.selectedItems()]
        target = self.itemAt(event.position().toPoint())
        event.ignore()                      # the data is changed by the panel, then the tree is rebuilt
        if sources and target is not None:
            self.dropped.emit(sources, target.data(0, PATH_ROLE))


class PathDialog(QDialog):
    """Editable drop-downs for the first ``levels`` levels of the chain (type a new name to create a place)."""

    def __init__(self, panel: "PlacesPanel", title: str, intro: str, levels: int, preset: tuple = (), parent=None):
        super().__init__(parent)
        self.panel = panel
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        text = QLabel(intro)
        text.setWordWrap(True)
        layout.addWidget(text)
        form = QFormLayout()
        self.combos: list[QComboBox] = []
        for j in range(levels):
            combo = QComboBox()
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.NoInsert)
            combo.setCurrentText(preset[j] if j < len(preset) else "")
            combo.currentTextChanged.connect(lambda _t, j=j: self._refresh(j + 1))
            self.combos.append(combo)
            form.addRow(LABELS[panel.chain[j]] + ":", combo)
        layout.addLayout(form)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self._refresh(0)
        first_blank = next((c for c in self.combos if not c.currentText()), self.combos[-1])
        first_blank.setFocus()

    def _refresh(self, start: int):
        for j in range(start, len(self.combos)):
            combo = self.combos[j]
            text = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(self.panel.options(j, tuple(c.currentText().strip() for c in self.combos[:j])))
            combo.setCurrentText(text)
            combo.blockSignals(False)

    def values(self) -> tuple:
        return tuple(c.currentText().strip() for c in self.combos)


class RenameDialog(QDialog):
    def __init__(self, label: str, old: str, everywhere: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Rename {label.lower()}")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"New name of the {label.lower()} '{old or UNSET}':"))
        self.edit = QLineEdit(old)
        self.edit.selectAll()
        layout.addWidget(self.edit)
        self.everywhere = QCheckBox("Rename everywhere (also where it is listed under other regions / countries)")
        self.everywhere.setChecked(everywhere)
        layout.addWidget(self.everywhere)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class PlacesPanel(QWidget):
    changed = Signal()

    def __init__(self, db, name: str, chain: list[str], kinds: list[str], parent=None):
        super().__init__(parent)
        self.db, self.name, self.chain, self.kinds = db, name, chain, kinds
        self._open: set[tuple] = set()
        self._first = True
        self._counts: Counter = Counter()          # entries per path (entries only, not catalogue paths)
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter places …")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        top.addWidget(self.search, 1)
        for text, tip, slot in (
                ("+ Add…", "Add a new place (e.g. a new range or mountain)", self.add_place),
                ("Rename…", "Rename the selected place", self.rename),
                ("Move to…", "Move the selected places under another parent", self.move_dialog),
                ("Also in…", "List the selected places (and everything below) under a second parent as well, "
                             "e.g. a range spanning two regions", self.also_dialog),
                ("Remove", "Remove places that have no entries", self.remove)):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            top.addWidget(b)
        layout.addLayout(top)
        self.tree = PlaceTree()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Place", "Entries"])
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.setColumnWidth(1, 70)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        self.tree.itemDoubleClicked.connect(lambda *_: self.rename())
        self.tree.itemExpanded.connect(lambda it: self._open.add(it.data(0, PATH_ROLE)))
        self.tree.itemCollapsed.connect(lambda it: self._open.discard(it.data(0, PATH_ROLE)))
        self.tree.dropped.connect(self._dropped)
        layout.addWidget(self.tree, 1)
        self.status = QLabel("Drag places onto a new parent to move them, or right-click for all actions.")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.rebuild()

    # ---- data
    def _catalog(self) -> list[dict]:
        return self.db.catalog(self.name)

    def _entries(self, level: int) -> list[dict]:
        """Entries an operation on a place of this level changes: country / region are shared by all kinds."""
        kinds = schema.LOCATION_KINDS if level <= 1 else self.kinds
        return [r for k in kinds for r in self.db.entries(k)]

    def _catalogs(self, level: int) -> list[dict]:
        return self.db.catalog("mountains") + self.db.catalog("climbing") if level <= 1 else self._catalog()

    def _matches(self, r: dict, path: tuple) -> bool:
        return all((r.get(self.chain[j]) or "") == path[j] for j in range(len(path)))

    def _path_of(self, r: dict) -> tuple:
        path = [(r.get(k) or "") for k in self.chain]
        while path and not path[-1]:
            path.pop()
        return tuple(path)

    def options(self, level: int, prefix: tuple) -> list[str]:
        """Existing values of a level below the given parents, most used first."""
        counts = Counter((r.get(self.chain[level]) or "") for r in self._entries(level) + self._catalogs(level)
                         if self._matches(r, prefix))
        counts.pop("", None)
        return sorted(counts, key=lambda v: (-counts[v], v.lower()))

    def _clean_catalog(self):
        seen, out = set(), []
        for d in self.db.catalog(self.name):
            key = self._path_of(d)
            if key and key not in seen:
                seen.add(key)
                out.append({k: v for k, v in zip(self.chain, key)})
        self.db.data["places"][self.name] = out
        other = "climbing" if self.name == "mountains" else "mountains"
        self.db.data["places"][other] = [d for d in self.db.catalog(other) if self._path_of(d)]

    def rebuild(self):
        selected = [it.data(0, PATH_ROLE) for it in self.tree.selectedItems()]
        self._counts = Counter()
        paths: set[tuple] = set()
        for r in self._entries(len(self.chain)):
            p = self._path_of(r)
            for n in range(len(p)):
                self._counts[p[:n + 1]] += 1
        for key in list(self._counts):
            paths.add(key)
        for d in self._catalog():
            p = self._path_of(d)
            paths.update(p[:n + 1] for n in range(len(p)))
        self.tree.blockSignals(True)
        self.tree.clear()
        items: dict[tuple, QTreeWidgetItem] = {}
        for key in sorted(paths, key=lambda k: tuple(x.lower() for x in k)):
            parent = items.get(key[:-1], self.tree.invisibleRootItem())
            item = QTreeWidgetItem(parent, [key[-1] or UNSET, str(self._counts[key])])
            item.setData(0, PATH_ROLE, key)
            item.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
            if not key[-1] or not self._counts[key]:
                item.setForeground(0, Qt.gray)        # not set / no entries yet
            items[key] = item
        if self._first:
            self._open = {k for k in items if len(k) == 1}
            self._first = False
        for key, item in items.items():
            item.setExpanded(key in self._open)
        self.tree.blockSignals(False)
        for key in selected:
            if key in items:
                items[key].setSelected(True)
        if selected and selected[0] in items:
            self.tree.setCurrentItem(items[selected[0]])
        self._filter(self.search.text())

    def _selected(self) -> list[tuple]:
        return [it.data(0, PATH_ROLE) for it in self.tree.selectedItems()]

    def _filter(self, text: str):
        text = text.strip().lower()

        def visit(item: QTreeWidgetItem) -> bool:
            own = not text or text in item.text(0).lower()
            child_hit = False
            for i in range(item.childCount()):
                child_hit |= visit(item.child(i))
            item.setHidden(not (own or child_hit))
            if text and child_hit:
                item.setExpanded(True)
            return own or child_hit

        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            visit(root.child(i))

    def _menu(self, pos):
        if self.tree.itemAt(pos) is None:
            return
        menu = QMenu(self)
        for text, slot in (("Add place…", self.add_place), ("Rename…", self.rename), ("Move to…", self.move_dialog),
                           ("Also in…", self.also_dialog), ("Remove", self.remove)):
            menu.addAction(text, slot)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    # ---- operations
    def _done(self, message: str, select: list[tuple] | None = None):
        self._clean_catalog()
        self.status.setText(message)
        self.tree.clearSelection()
        for p in select or []:
            self._open.update(p[:i + 1] for i in range(len(p) - 1))
        self.rebuild()
        for p in select or []:
            item = self._find(p)
            if item is not None:
                item.setSelected(True)
                self.tree.scrollToItem(item)
        self.changed.emit()

    def add_place(self):
        sel = self._selected()
        preset = sel[0] if sel else ()
        dlg = PathDialog(self, "Add place",
                         "Fill in the levels from the top; the last filled-in level is the new place. A name that "
                         "does not exist yet is created (e.g. a new range below an existing region).",
                         len(self.chain), preset, self)
        if not dlg.exec():
            return
        values = list(dlg.values())
        while values and not values[-1]:
            values.pop()
        if not values:
            return
        self._catalog().append(dict(zip(self.chain, values)))
        self._done(f"Added {' › '.join(v or UNSET for v in values)}.", [tuple(values)])

    def rename(self):
        item = self.tree.currentItem()
        if item is None:
            return
        path = item.data(0, PATH_ROLE)
        level = len(path) - 1
        key, label = self.chain[level], LABELS[self.chain[level]]
        dlg = RenameDialog(label, path[-1], everywhere=level >= 2, parent=self)
        if not dlg.exec():
            return
        new = dlg.edit.text().strip()
        if new == path[-1]:
            return
        everywhere = dlg.everywhere.isChecked()
        entries = set(map(id, self._entries(level)))
        n = 0
        for r in self._entries(level) + self._catalogs(level):
            hit = (r.get(key) or "") == path[-1] if everywhere else self._matches(r, path)
            if hit:
                r[key] = new
                n += id(r) in entries
        self._done(f"'{path[-1] or UNSET}' renamed to '{new}' ({n} entries).", [path[:-1] + (new,)])

    def _same_level(self, paths: list[tuple], action: str):
        if not paths:
            self.status.setText(f"Select the places you want to {action} first.")
            return None
        level = len(paths[0]) - 1
        if any(len(p) - 1 != level for p in paths):
            self.status.setText("Select places of the same level (e.g. only mountains).")
            return None
        if level == 0:
            self.status.setText("Top level places (countries) cannot be moved - rename them instead.")
            return None
        return level

    def move_dialog(self):
        self._ask_parents(copy_mode=False)

    def also_dialog(self):
        self._ask_parents(copy_mode=True)

    def _ask_parents(self, copy_mode: bool):
        paths = self._selected()
        level = self._same_level(paths, "also list" if copy_mode else "move")
        if level is None:
            return
        names = ", ".join(p[-1] or UNSET for p in paths[:3]) + ("…" if len(paths) > 3 else "")
        title = f"{'Also list' if copy_mode else 'Move'} {names}"
        intro = ("Also list these places (with everything below them) under this parent. They stay where they are - "
                 "use this for a range that spans several regions or countries."
                 if copy_mode else
                 "New parent of the selected places. All their entries get these values; type a new name to create "
                 "a new parent.")
        dlg = PathDialog(self, title, intro, level, paths[0][:level], self)
        if dlg.exec():
            self._move(paths, dlg.values(), copy_mode)

    def _dropped(self, sources: list[tuple], target: tuple):
        level = self._same_level(sources, "move")
        if level is None:
            return
        if len(target) != level:
            self.status.setText(f"Drop {LABELS[self.chain[level]].lower()}s onto a "
                                f"{LABELS[self.chain[level - 1]].lower()}.")
            return
        self._move(sources, target, False)

    def _move(self, paths: list[tuple], parents: tuple, copy_mode: bool):
        level = len(paths[0]) - 1
        n = 0
        if copy_mode:
            added = []
            for path in paths:
                tails = {self._path_of(r)[level:] for r in self._entries(level) + self._catalog()
                         if self._matches(r, path)}
                for tail in tails:
                    added.append(dict(zip(self.chain, parents + tail)))
            self._catalog().extend(added)
            message = f"Also listed {', '.join(p[-1] or UNSET for p in paths[:3])} under {self._fmt(parents)}."
        else:
            entries = set(map(id, self._entries(level)))
            for path in paths:
                if parents == path[:level]:
                    continue
                for r in self._entries(level) + self._catalogs(level):
                    if self._matches(r, path):
                        for j, value in enumerate(parents):
                            r[self.chain[j]] = value
                        n += id(r) in entries
            message = f"Moved {', '.join(p[-1] or UNSET for p in paths[:3])} under {self._fmt(parents)} ({n} entries)."
        self._done(message, [parents + (p[-1],) for p in paths])

    @staticmethod
    def _fmt(path: tuple) -> str:
        return " › ".join(p or UNSET for p in path)

    def remove(self):
        paths = self._selected()
        if not paths:
            return
        blocked = [p for p in paths if self._counts[p]]
        if blocked:
            self.status.setText(f"'{blocked[0][-1] or UNSET}' has {self._counts[blocked[0]]} entries - move or rename "
                                "them first. Only places without entries can be removed.")
            return
        for p in paths:
            self.db.data["places"][self.name] = [d for d in self._catalog() if not self._matches(d, p)]
        self._done(f"Removed {len(paths)} place(s).")

    def _find(self, path: tuple):
        stack = [self.tree.invisibleRootItem()]
        while stack:
            node = stack.pop()
            for i in range(node.childCount()):
                child = node.child(i)
                if child.data(0, PATH_ROLE) == path:
                    return child
                stack.append(child)
        return None


class PlacesDialog(QDialog):
    """Mountains and rock climbing places in two tabs; Save writes the changes, Cancel drops all edits."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._snapshot = copy.deepcopy((db.data["entries"], db.data["places"]))
        self.dirty = False
        self.setWindowTitle("Organize places")
        self.resize(900, 680)
        layout = QVBoxLayout(self)
        intro = QLabel("Places are taken from your entries and from places you add here. Renaming or moving a place "
                       "changes all entries below it; country and region are shared by every kind of entry. A mountain "
                       "range that spans several regions or countries is listed under each of them (\"Also in…\"). "
                       "Nothing is written until you press Save.")
        intro.setWordWrap(True)
        intro.setObjectName("muted")
        layout.addWidget(intro)
        self.tabs = QTabWidget()
        for title, name, chain, kinds in (("Mountains", "mountains", schema.MOUNTAIN_CHAIN, schema.MOUNTAIN_KINDS),
                                          ("Rock climbing", "climbing", schema.CLIMBING_CHAIN, schema.CLIMBING_KINDS)):
            panel = PlacesPanel(db, name, chain, kinds)
            panel.changed.connect(self._mark_dirty)
            self.tabs.addTab(panel, title)
        layout.addWidget(self.tabs, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _mark_dirty(self):
        self.dirty = True
        for i in range(self.tabs.count()):         # country / region are shared: keep both trees consistent
            if self.tabs.widget(i) is not self.sender():
                self.tabs.widget(i).rebuild()

    def accept(self):
        if self.dirty:
            self.db.save()
        super().accept()

    def reject(self):
        if self.dirty:
            self.db.data["entries"], self.db.data["places"] = self._snapshot
        super().reject()


__all__ = ["PlacesDialog", "QMessageBox"]
