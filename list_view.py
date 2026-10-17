"""List view: one searchable, sortable table per kind of entry."""
from PySide6.QtCore import QRect, QRectF, QSize, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QStackedWidget, QStyle, QStyledItemDelegate, QTableView, QVBoxLayout, QWidget,
)

import icons
import schema
from charts import tints
from stats_view import subtype_names, tint_colors
from widgets import ComboBox, FullScreenButton
import theme
from database import parse_date
from fields import format_value

ID_ROLE = Qt.UserRole + 1
SORT_ROLE = Qt.UserRole + 2
KEY_ROLE = Qt.UserRole + 3
SUB_ROLE = Qt.UserRole + 4          # sub-type colour of the row (stored on the first cell)

CATEGORY_PILLS = {"type", "discipline", "phase", "level", "style", "orientation"}   # tinted with the category colour
ATTEMPT_ORDER = ["onsight", "flash", "redpoint"]                                      # darkest -> lightest tint
NEUTRAL_PILLS = {"grade", "grade_wi", "grade_m"}


class RowDelegate(QStyledItemDelegate):
    """Draws list rows: category stripe, hover / selection, pill badges, right-aligned numbers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = "#3a86e0"
        self.subtype_key: str | None = None
        self.sub_colors: dict[str, str] = {}
        self.date_font = QFont()
        self.date_font.setWeight(QFont.DemiBold)
        self.pill_font = QFont()
        self.pill_font.setPointSizeF(8.5)
        self.pill_font.setWeight(QFont.DemiBold)

    def sizeHint(self, option, index):
        return QSize(super().sizeHint(option, index).width() + 24, 38)

    def paint(self, p: QPainter, option, index):
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        rect = option.rect
        selected = bool(option.state & QStyle.State_Selected)
        hover = bool(option.state & QStyle.State_MouseOver)
        if selected:
            bg = QColor("#e6eaf0")
        elif hover:
            bg = QColor("#f1f3f6")
        else:
            bg = QColor("#fafaf7" if index.row() % 2 else theme.SURFACE)
        p.fillRect(rect, bg)
        p.setPen(QColor("#efeee9"))
        p.drawLine(rect.bottomLeft(), rect.bottomRight())
        col = index.column()
        if col == 0:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(index.data(SUB_ROLE) or self.color))
            p.drawRoundedRect(QRectF(rect.left() + 3, rect.top() + 7, 4, rect.height() - 14), 2, 2)
        text = index.data(Qt.DisplayRole) or ""
        key = index.data(KEY_ROLE)
        left = rect.left() + (18 if col == 0 else 10)
        inner = QRect(left, rect.top(), max(0, rect.right() - left - 10), rect.height())
        align = index.data(Qt.TextAlignmentRole)
        right_aligned = bool(align is not None and int(align) & int(Qt.AlignRight))
        if text and (key in CATEGORY_PILLS or key in NEUTRAL_PILLS or key == "attempts"):
            if key == self.subtype_key and text in self.sub_colors:
                base = QColor(self.sub_colors[text])                  # same sub-shade as in the statistics
            elif key in CATEGORY_PILLS:
                base = QColor(self.color)
            elif key == "attempts":
                shades = tints(schema.KINDS["sport_routes"].color, 3)          # ascent styles: tints of the tick-list pink
                base = QColor(shades[ATTEMPT_ORDER.index(text) if text in ("onsight", "flash") else 2])
            else:
                base = QColor("#8a877c")
            p.setFont(self.pill_font)
            fm = p.fontMetrics()           # painter metrics: matches what is actually drawn
            label = fm.elidedText(text, Qt.ElideRight, max(20, inner.width() - 18))
            w = fm.horizontalAdvance(label) + 18
            pill = QRectF(inner.left(), rect.center().y() - 11, w, 22)
            fill = QColor(base)
            fill.setAlphaF(0.16)
            p.setPen(Qt.NoPen)
            p.setBrush(fill)
            p.drawRoundedRect(pill, 11, 11)
            p.setPen(QColor(icons.shade(base.name(), 0.7)))
            p.drawText(pill, Qt.AlignCenter, label)
        else:
            font = self.date_font if (col == 0 and key == "date") else option.font
            p.setFont(font)
            p.setPen(QColor(theme.TEXT if text else theme.TEXT_MUTED))
            shown = p.fontMetrics().elidedText(text, Qt.ElideRight, inner.width())
            flags = (Qt.AlignRight if right_aligned else Qt.AlignLeft) | Qt.AlignVCenter
            p.drawText(inner, flags, shown)
        p.restore()


class FilterProxy(QSortFilterProxyModel):
    """Shows only the source rows listed in ``accepted`` (None = all)."""

    accepted: set[int] | None = None

    def filterAcceptsRow(self, row, parent):
        return self.accepted is None or row in self.accepted


class ListView(QWidget):
    entry_selected = Signal(str, str)
    entry_activated = Signal(str, str)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.kind = "climbing_days"
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(225)
        self.nav.setIconSize(QSize(28, 28))
        for kind in schema.ADDABLE:
            item = QListWidgetItem(schema.KINDS[kind].plural)
            item.setData(Qt.UserRole, kind)
            item.setIcon(icons.icon(kind, icons.shade(schema.KINDS[kind].color), 28, width=2.3))
            self.nav.addItem(item)
        self.nav.currentItemChanged.connect(self._kind_changed)
        layout.addWidget(self.nav)

        right = QVBoxLayout()
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search (name, area, partner, notes …)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        self.year = ComboBox()
        self.year.currentIndexChanged.connect(self._filter)
        self.subtype = ComboBox()
        self.subtype.setMinimumWidth(190)
        self.year.setMinimumWidth(90)
        self.subtype.currentIndexChanged.connect(self._filter)
        self.count = QLabel()
        self.count.setObjectName("muted")
        bar.addWidget(self.search, 1)
        bar.addWidget(QLabel("Year:"))
        bar.addWidget(self.year)
        bar.addWidget(self.subtype)
        bar.addWidget(self.count)
        self.full_btn = FullScreenButton()
        bar.addWidget(self.full_btn)
        right.addLayout(bar)

        self.model = QStandardItemModel(self)
        self.proxy = FilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.delegate = RowDelegate(self.table)
        self.table.setItemDelegate(self.delegate)
        self.table.setShowGrid(False)
        self.table.setMouseTracking(True)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideRight)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.horizontalHeader().setMinimumHeight(38)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.selectionModel().currentRowChanged.connect(self._row_changed)
        self.table.doubleClicked.connect(self._activated)
        self.empty = QLabel("No entries match.")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setObjectName("muted")
        self.empty.setMinimumHeight(160)
        self.pages = QStackedWidget()
        self.pages.addWidget(self.table)
        self.pages.addWidget(self.empty)
        right.addWidget(self.pages, 1)
        layout.addLayout(right, 1)
        self._rows: list[tuple[dict, str]] = []
        self.nav.setCurrentRow(0)

    def set_kind(self, kind: str):
        for i in range(self.nav.count()):
            if self.nav.item(i).data(Qt.UserRole) == kind:
                self.nav.setCurrentRow(i)
                return

    def _kind_changed(self, item, _prev=None):
        if item is None:
            return
        self.kind = item.data(Qt.UserRole)
        self.refresh()

    def refresh(self, select_id: str | None = None):
        spec = schema.KINDS[self.kind]
        records = sorted(self.db.entries(self.kind), key=lambda r: r.get("date", ""), reverse=True)
        cols = [spec.field(c) for c in spec.columns]
        self.model.clear()
        self.model.setHorizontalHeaderLabels([c.label for c in cols])
        self.delegate.color = spec.color
        names = subtype_names(self.kind, records) if spec.subtype else []
        self.delegate.subtype_key = spec.subtype
        self.delegate.sub_colors = tint_colors(self.kind, names)
        numeric = [c.type in ("int", "float", "rating") for c in cols]
        for i, is_num in enumerate(numeric):
            align = (Qt.AlignRight if is_num else Qt.AlignLeft) | Qt.AlignVCenter
            self.model.setHeaderData(i, Qt.Horizontal, int(align), Qt.TextAlignmentRole)
        self._rows = []
        for r in records:
            row = []
            for c in cols:
                v = r.get(c.key)
                item = QStandardItem(format_value(c, v))
                sort_v = v if isinstance(v, (int, float)) else (len(v) if isinstance(v, list) else str(v or ""))
                if c.key in ("grade",):
                    import grades
                    sort_v = grades.rock_index(v)
                item.setData(sort_v, SORT_ROLE)
                item.setData(c.key, KEY_ROLE)
                item.setTextAlignment((Qt.AlignRight if c.type in ("int", "float", "rating") else Qt.AlignLeft)
                                          | Qt.AlignVCenter)
                row.append(item)
            row[0].setData(r["id"], ID_ROLE)
            if spec.subtype:
                row[0].setData(self.delegate.sub_colors.get(r.get(spec.subtype) or "—"), SUB_ROLE)
            self.model.appendRow(row)
            self._rows.append((r, schema.search_text(self.kind, r)))
        # filters
        years = sorted({parse_date(r["date"]).year for r in records if r.get("date")}, reverse=True)
        cur_year = self.year.currentData()
        self.year.blockSignals(True)
        self.year.clear()
        self.year.addItem("All", None)
        for y in years:
            self.year.addItem(str(y), y)
        self.year.setCurrentIndex(max(0, self.year.findData(cur_year)))
        self.year.blockSignals(False)
        self.subtype.blockSignals(True)
        cur_sub = self.subtype.currentData()
        self.subtype.clear()
        if spec.subtype:
            self.subtype.addItem(f"All {spec.field(spec.subtype).label.lower()}s", None)
            for v in sorted({r.get(spec.subtype) for r in records if r.get(spec.subtype)}):
                self.subtype.addItem(v, v)
            self.subtype.setCurrentIndex(max(0, self.subtype.findData(cur_sub)))
        self.subtype.setVisible(bool(spec.subtype))
        self.subtype.blockSignals(False)
        self.table.resizeColumnsToContents()
        for i in range(self.model.columnCount()):
            self.table.setColumnWidth(i, max(92, min(self.table.columnWidth(i) + 34, 340)))
        self._filter()
        if select_id:
            self.select(select_id)

    def _filter(self):
        text = self.search.text().lower().split()
        year = self.year.currentData()
        sub = self.subtype.currentData() if self.subtype.isVisible() else None
        spec = schema.KINDS[self.kind]
        accepted = set()
        for i, (r, blob) in enumerate(self._rows):
            ok = all(t in blob for t in text)
            if ok and year is not None:
                ok = parse_date(r["date"]).year == year
            if ok and sub is not None:
                ok = r.get(spec.subtype) == sub
            if ok:
                accepted.add(i)
        self.proxy.accepted = accepted
        self.proxy.invalidateFilter()
        self.count.setText(f"{len(accepted)} of {len(self._rows)}")
        self.pages.setCurrentIndex(0 if accepted else 1)
        self.empty.setText("No entries yet." if not self._rows else "No entries match the current search / filters.")

    def select(self, entry_id: str):
        for i, (r, _) in enumerate(self._rows):
            if r["id"] == entry_id:
                idx = self.proxy.mapFromSource(self.model.index(i, 0))
                self.table.selectRow(idx.row())
                self.table.scrollTo(idx)
                return

    def _id_at(self, proxy_index):
        src = self.proxy.mapToSource(proxy_index)
        return self.model.item(src.row(), 0).data(ID_ROLE) if src.isValid() else None

    def _row_changed(self, current, _prev):
        entry_id = self._id_at(current)
        if entry_id:
            self.entry_selected.emit(self.kind, entry_id)

    def _activated(self, index):
        entry_id = self._id_at(index)
        if entry_id:
            self.entry_activated.emit(self.kind, entry_id)

    def current_id(self):
        return self._id_at(self.table.currentIndex())


__all__ = ["ListView", "theme"]
