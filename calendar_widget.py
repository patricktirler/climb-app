"""Custom painted calendar: a month grid of day tiles and a 12-month year overview.

Both views get their content from ``schema.day_index(db)``: a mapping
``date -> [DayItem]``, where each item knows its colour and the text lines to show.
"""
import calendar as pycal
from datetime import date, timedelta

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLabel, QMenu, QPushButton, QStackedWidget, QToolTip,
    QVBoxLayout, QWidget,
)

import icons
import schema
import theme

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def tint(color: str, alpha: float) -> QColor:
    c = QColor(color)
    c.setAlphaF(alpha)
    return c


class MonthGrid(QWidget):
    """Weeks Mon–Sun as rows, one tile per day, entries stacked inside the tile."""

    entry_clicked = Signal(str, str)          # kind, id
    entry_activated = Signal(str, str)        # double click: edit
    add_requested = Signal(str, object)       # kind, date
    day_activated = Signal(object)
    day_clicked = Signal(object)              # single click on a day (empty area of the tile)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.index: dict[date, list] = {}
        self.year, self.month = date.today().year, date.today().month
        self.selected: tuple[str, str] | None = None
        self.selected_day: date | None = None
        self._hit: list[tuple[QRectF, object, date]] = []   # (rect, DayItem|None, day)
        self.setMinimumSize(560, 420)

    def set_month(self, year: int, month: int):
        self.year, self.month = year, month
        self.update()

    def weeks(self) -> list[list[date]]:
        first = date(self.year, self.month, 1)
        start = first - timedelta(days=first.weekday())
        last = date(self.year, self.month, pycal.monthrange(self.year, self.month)[1])
        end = last + timedelta(days=6 - last.weekday())
        days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        return [days[i:i + 7] for i in range(0, len(days), 7)]

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(theme.PAGE))
        self._hit = []
        weeks = self.weeks()
        header_h = 26
        gap = 6
        w = (self.width() - gap * 8) / 7
        h = (self.height() - header_h - gap * (len(weeks) + 1)) / len(weeks)
        small = QFont(self.font())
        small.setPointSizeF(max(7.5, min(9.0, h / 14)))
        bold = QFont(small)
        bold.setBold(True)
        p.setFont(bold)
        p.setPen(QColor(theme.TEXT_MUTED))
        for i, name in enumerate(WEEKDAYS):
            p.drawText(QRectF(gap + i * (w + gap), 0, w, header_h), Qt.AlignCenter, name)
        today = date.today()
        for r, week in enumerate(weeks):
            for c, day in enumerate(week):
                rect = QRectF(gap + c * (w + gap), header_h + gap + r * (h + gap), w, h)
                self._paint_day(p, rect, day, day.month == self.month, day == today, small, bold)
        p.end()

    def _paint_day(self, p: QPainter, rect: QRectF, day: date, in_month: bool, is_today: bool,
                   small: QFont, bold: QFont):
        items = self.index.get(day, [])
        is_selected = day == self.selected_day and self.selected is None
        p.setPen(QPen(QColor(theme.ACCENT if (is_today or is_selected) else theme.BORDER),
                      2 if (is_today or is_selected) else 1))
        p.setBrush(QColor(theme.SURFACE if in_month else theme.PAGE))
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)
        self._hit.append((rect, None, day))
        fm = QFontMetrics(small)
        line_h = fm.height()
        p.setFont(bold)
        p.setPen(QColor(theme.TEXT if in_month else theme.TEXT_MUTED))
        weekend = day.weekday() >= 5
        label = str(day.day) if day.day != 1 else f"{day.day} {MONTHS[day.month - 1][:3]}"
        p.drawText(rect.adjusted(7, 4, -7, 0), Qt.AlignLeft | Qt.AlignTop, label)
        if weekend and in_month:
            p.setPen(QColor(theme.TEXT_MUTED))
            p.setFont(small)
            p.drawText(rect.adjusted(7, 4, -7, 0), Qt.AlignRight | Qt.AlignTop, WEEKDAYS[day.weekday()])
        y = rect.top() + line_h + 8
        bottom = rect.bottom() - 4
        notes = [it for it in items if it.kind == "notes"]
        blocks = [it for it in items if it.kind != "notes"]
        alpha = 0.22 if in_month else 0.10
        for n, it in enumerate(blocks):
            remaining = len(blocks) - n
            space = bottom - y - (line_h if notes else 0)
            # how many lines this block may use so later blocks still get one line
            max_lines = max(1, int((space - (remaining - 1) * (line_h + 4)) // line_h))
            lines = it.lines[:max_lines] if remaining == 1 else it.lines[:max(1, min(len(it.lines), max_lines))]
            if space < line_h + 2:
                p.setPen(QColor(theme.TEXT_MUTED))
                p.setFont(small)
                p.drawText(QRectF(rect.left() + 6, bottom - line_h, rect.width() - 12, line_h),
                           Qt.AlignRight, f"+{remaining} more")
                break
            bh = max(len(lines) * line_h + 4, 28)
            block = QRectF(rect.left() + 4, y, rect.width() - 8, bh)
            path = QPainterPath()
            # multi-day entries: square edges towards the neighbouring days
            path.addRoundedRect(block, 4, 4)
            p.setPen(Qt.NoPen)
            p.setBrush(tint(it.color, alpha))
            p.drawPath(path)
            p.setBrush(QColor(it.color))
            stripe = QRectF(block.left(), block.top(), 4, block.height())
            p.drawRoundedRect(stripe, 2, 2)
            if self.selected == (it.kind, it.record.get("id")):
                p.setPen(QPen(QColor(theme.TEXT), 1.5))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(block, 4, 4)
            show_icon = block.width() >= 100
            if show_icon:                                   # category icon, top right of the entry
                p.save()
                p.setOpacity(1.0 if in_month else 0.45)
                p.drawPixmap(QPointF(block.right() - 27, block.top() + 1.5), icons.pixmap(it.kind, icons.shade(it.color), 23, 2.4))
                p.restore()
            p.setPen(QColor(theme.TEXT if in_month else theme.TEXT_MUTED))
            for k, line in enumerate(lines):
                p.setFont(bold if k == 0 else small)
                text_rect = QRectF(block.left() + 9, block.top() + 2 + k * line_h,
                                   block.width() - 12 - (29 if (k == 0 and show_icon) else 0), line_h)
                prefix = "… " if (k == 0 and it.continued) else ""
                p.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter,
                           QFontMetrics(p.font()).elidedText(prefix + line, Qt.ElideRight, int(text_rect.width())))
            self._hit.append((block, it, day))
            y += bh + 4
        if notes:
            p.setFont(small)
            p.setPen(QColor(theme.TEXT_SECONDARY))
            text = " · ".join(n.lines[0] for n in notes if n.lines)
            space = bottom - y
            if space >= line_h:
                lines_fit = max(1, int(space // line_h))
                note_rect = QRectF(rect.left() + 7, bottom - min(lines_fit, 3) * line_h, rect.width() - 14,
                                   min(lines_fit, 3) * line_h)
                note_font = QFont(small)
                note_font.setItalic(True)
                p.setFont(note_font)
                p.drawText(note_rect, Qt.AlignLeft | Qt.AlignBottom | Qt.TextWordWrap, text)
                self._hit.append((note_rect, notes[0], day))

    def _at(self, pos):
        found = None
        for rect, item, day in self._hit:
            if rect.contains(QPointF(pos)):
                found = (item, day) if item is not None or found is None else found
        return found

    def mousePressEvent(self, e):
        hit = self._at(e.position())
        if not hit:
            return
        item, day = hit
        if e.button() == Qt.RightButton:
            self._context_menu(e.globalPosition().toPoint(), day, item)
            return
        if item is not None:
            self.selected = (item.kind, item.record["id"])
            self.selected_day = None
            self.entry_clicked.emit(item.kind, item.record["id"])
        else:
            self.selected = None
            self.selected_day = day
            self.day_clicked.emit(day)
        self.update()

    def mouseDoubleClickEvent(self, e):
        hit = self._at(e.position())
        if not hit:
            return
        item, day = hit
        if item is not None:
            self.entry_activated.emit(item.kind, item.record["id"])
        else:
            self.day_activated.emit(day)

    def mouseMoveEvent(self, e):
        hit = self._at(e.position())
        if hit and hit[0] is not None:
            it = hit[0]
            text = f"<b>{schema.KINDS[it.kind].label}</b><br>" + "<br>".join(it.lines)
            QToolTip.showText(e.globalPosition().toPoint(), text, self)
        else:
            QToolTip.hideText()

    def _context_menu(self, pos, day: date, item):
        menu = QMenu(self)
        if item is not None:
            menu.addAction("Edit…", lambda: self.entry_activated.emit(item.kind, item.record["id"]))
            menu.addSeparator()
        sub = menu.addMenu(f"Add on {day.strftime('%d.%m.%Y')}")
        for kind in schema.ADDABLE:
            sub.addAction(schema.KINDS[kind].label, lambda k=kind: self.add_requested.emit(k, day))
        menu.exec(pos)


class YearGrid(QWidget):
    """12 mini months; each day cell is filled with the colours of its entries."""

    month_chosen = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.index: dict[date, list] = {}
        self.year = date.today().year
        self._cells: list[tuple[QRectF, date]] = []
        self._months: list[tuple[QRectF, int]] = []

    def set_year(self, year: int):
        self.year = year
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(theme.PAGE))
        self._cells, self._months = [], []
        cols, rows = 4, 3
        pad = 14
        mw = (self.width() - pad * (cols + 1)) / cols
        mh = (self.height() - pad * (rows + 1)) / rows
        title_font = QFont(self.font())
        title_font.setBold(True)
        small = QFont(self.font())
        small.setPointSizeF(7.5)
        today = date.today()
        for m in range(12):
            r, c = divmod(m, cols)
            box = QRectF(pad + c * (mw + pad), pad + r * (mh + pad), mw, mh)
            self._months.append((box, m + 1))
            p.setPen(QPen(QColor(theme.BORDER), 1))
            p.setBrush(QColor(theme.SURFACE))
            p.drawRoundedRect(box, 8, 8)
            month_days = [date(self.year, m + 1, d) for d in range(1, pycal.monthrange(self.year, m + 1)[1] + 1)]
            n_entries = sum(1 for d in month_days for it in self.index.get(d, []) if it.kind != "notes" and not it.continued)
            p.setFont(title_font)
            p.setPen(QColor(theme.TEXT))
            p.drawText(box.adjusted(10, 6, -10, 0), Qt.AlignLeft | Qt.AlignTop, MONTHS[m])
            p.setFont(small)
            p.setPen(QColor(theme.TEXT_MUTED))
            p.drawText(box.adjusted(10, 8, -10, 0), Qt.AlignRight | Qt.AlignTop,
                       f"{n_entries} entr{'y' if n_entries == 1 else 'ies'}")
            grid = box.adjusted(8, 30, -8, -8)
            cw = grid.width() / 7
            ch = (grid.height() - 14) / 6
            for i, wd in enumerate(WEEKDAYS):
                p.drawText(QRectF(grid.left() + i * cw, grid.top(), cw, 12), Qt.AlignCenter, wd[0])
            offset = month_days[0].weekday()
            for d in month_days:
                k = offset + d.day - 1
                row, col = divmod(k, 7)
                cell = QRectF(grid.left() + col * cw + 1, grid.top() + 14 + row * ch + 1, cw - 2, ch - 2)
                self._cells.append((cell, d))
                kinds = []
                for it in self.index.get(d, []):
                    if it.kind != "notes" and it.color not in kinds:
                        kinds.append(it.color)
                if kinds:
                    seg = cell.width() / len(kinds)
                    p.setPen(Qt.NoPen)
                    for i, col_hex in enumerate(kinds):
                        p.setBrush(QColor(col_hex))
                        p.drawRect(QRectF(cell.left() + i * seg, cell.top(), seg, cell.height()))
                elif self.index.get(d):
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(theme.GRID))
                    p.drawRect(cell)
                p.setPen(QPen(QColor(theme.ACCENT), 2) if d == today else Qt.NoPen)
                p.setBrush(Qt.NoBrush)
                if d == today:
                    p.drawRect(cell)
                p.setPen(QColor(theme.TEXT_ON_FILL if kinds else theme.TEXT_SECONDARY))
                p.drawText(cell, Qt.AlignCenter, str(d.day))
        p.end()

    def mouseMoveEvent(self, e):
        for cell, d in self._cells:
            if cell.contains(e.position()):
                items = self.index.get(d, [])
                if items:
                    text = f"<b>{d.strftime('%a %d.%m.%Y')}</b>" + "".join(
                        f"<br>■ <b>{schema.KINDS[it.kind].label}</b>: {' · '.join(it.lines[:3])}" for it in items)
                    QToolTip.showText(e.globalPosition().toPoint(), text, self)
                    return
        QToolTip.hideText()

    def mousePressEvent(self, e):
        for box, m in self._months:
            if box.contains(e.position()):
                self.month_chosen.emit(self.year, m)
                return


class CalendarWidget(QWidget):
    """Month/year calendar with navigation bar and legend."""

    entry_clicked = Signal(str, str)
    entry_activated = Signal(str, str)
    add_requested = Signal(str, object)
    day_clicked = Signal(object)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.mode = "month"
        today = date.today()
        self.year, self.month = today.year, today.month
        self.filter_kinds: set[str] | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.prev_btn = QPushButton()
        self.next_btn = QPushButton()
        self.today_btn = QPushButton("Today")
        self.prev_btn.setIcon(icons.icon("chevron_left", theme.TEXT_SECONDARY, 20))
        self.next_btn.setIcon(icons.icon("chevron_right", theme.TEXT_SECONDARY, 20))
        self.today_btn.setIcon(icons.icon("today", theme.TEXT_SECONDARY, 20))
        self.prev_btn.setToolTip("Previous (PgUp)")
        self.next_btn.setToolTip("Next (PgDown)")
        for b in (self.prev_btn, self.next_btn):
            b.setFixedWidth(36)
        self.title = QLabel()
        self.title.setObjectName("calendarTitle")
        self.prev_btn.clicked.connect(lambda: self.step(-1))
        self.next_btn.clicked.connect(lambda: self.step(1))
        self.today_btn.clicked.connect(self.go_today)
        bar.addWidget(self.prev_btn)
        bar.addWidget(self.next_btn)
        bar.addWidget(self.today_btn)
        bar.addSpacing(12)
        bar.addWidget(self.title)
        bar.addStretch()
        self.mode_group = QButtonGroup(self)
        for i, (text, mode) in enumerate([("Month", "month"), ("Year", "year")]):
            b = QPushButton(text)
            b.setCheckable(True)
            b.setChecked(mode == self.mode)
            b.setObjectName("segment")
            self.mode_group.addButton(b, i)
            b.clicked.connect(lambda _=False, m=mode: self.set_mode(m))
            bar.addWidget(b)
        layout.addLayout(bar)

        self.stack = QStackedWidget()
        self.month_grid = MonthGrid()
        self.year_grid = YearGrid()
        self.stack.addWidget(self.month_grid)
        self.stack.addWidget(self.year_grid)
        layout.addWidget(self.stack, 1)
        layout.addWidget(theme.legend_widget([k for k in schema.LEGEND_KINDS]))

        self.month_grid.entry_clicked.connect(self.entry_clicked)
        self.month_grid.entry_activated.connect(self.entry_activated)
        self.month_grid.add_requested.connect(self.add_requested)
        self.month_grid.day_activated.connect(self._day_activated)
        self.month_grid.day_clicked.connect(self.day_clicked)
        self.year_grid.month_chosen.connect(self._month_chosen)
        self.refresh()

    def _day_activated(self, day: date):
        menu = QMenu(self)
        for kind in schema.ADDABLE:
            menu.addAction(f"Add {schema.KINDS[kind].label}", lambda k=kind: self.add_requested.emit(k, day))
        from PySide6.QtGui import QCursor
        menu.exec(QCursor.pos())

    def _month_chosen(self, year, month):
        self.year, self.month = year, month
        self.set_mode("month")

    def set_mode(self, mode: str):
        self.mode = mode
        self.mode_group.button(0 if mode == "month" else 1).setChecked(True)
        self.stack.setCurrentIndex(0 if mode == "month" else 1)
        self._update_title()

    def step(self, delta: int):
        if self.mode == "month":
            m = self.month - 1 + delta
            self.year += m // 12
            self.month = m % 12 + 1
        else:
            self.year += delta
        self._apply()

    def go_today(self):
        today = date.today()
        self.year, self.month = today.year, today.month
        self._apply()

    def go_to(self, d: date):
        self.year, self.month = d.year, d.month
        self._apply()

    def _apply(self):
        self.month_grid.set_month(self.year, self.month)
        self.year_grid.set_year(self.year)
        self._update_title()

    def _update_title(self):
        if self.mode == "month":
            self.title.setText(f"{MONTHS[self.month - 1]} {self.year}")
        else:
            self.title.setText(str(self.year))

    def select(self, kind: str, entry_id: str):
        self.month_grid.selected = (kind, entry_id)
        self.month_grid.selected_day = None
        self.month_grid.update()

    def refresh(self):
        index = schema.day_index(self.db, self.filter_kinds)
        self.month_grid.index = index
        self.year_grid.index = index
        self._apply()
