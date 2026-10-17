"""QtCharts building blocks: stacked bars, timeline scatter, lines, Gantt bars.

Conventions: hairline recessive grid, legend only for >= 2 series, hover tooltips,
clicking a point emits the underlying entry, and every chart card can flip to a
table of the same numbers.
"""
from datetime import date, datetime, time

from PySide6.QtCharts import (
    QBarCategoryAxis, QBarSet, QCategoryAxis, QChart, QChartView, QDateTimeAxis,
    QHorizontalStackedBarSeries, QLineSeries, QScatterSeries, QStackedBarSeries, QValueAxis,
    QXYSeries,
)
from PySide6.QtCore import QDateTime, QMargins, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton, QStackedWidget, QStyle, QStyledItemDelegate, QTableWidget,
    QTableWidgetItem, QToolTip, QVBoxLayout, QWidget,
)

import icons
import theme

# categorical slots (validated order) for sub types inside one chart
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6", "#e34948", "#008300"]
OTHER = "#b5b4ad"


def tints(color: str, n: int) -> list[str]:
    """n shades of one colour, darkest first: series inside a category stay in the category's hue."""
    if n <= 1:
        return [color]
    c = QColor(color)
    h, sat, light, _ = c.getHslF()
    lo = max(0.30, min(light - 0.10, 0.50))          # light base colours (pink) still get a clearly darker end
    hi = min(0.86, max(light + 0.28, 0.74))
    out = []
    for i in range(n):
        li = lo + (hi - lo) * i / (n - 1)
        out.append(QColor.fromHslF(max(h, 0.0), min(1.0, sat * (1.0 - 0.12 * i / (n - 1))), li).name())
    return out


def slot_colors(names: list[str]) -> dict[str, str]:
    """Fixed colour per name by position in a stable list (never by rank)."""
    out = {}
    for i, n in enumerate(names):
        out[n] = SLOTS[i] if i < len(SLOTS) else OTHER
    return out


def to_ms(d) -> float:
    if isinstance(d, date) and not isinstance(d, datetime):
        d = datetime.combine(d, time(12))
    return float(QDateTime(d).toMSecsSinceEpoch())


def compact(v: float) -> str:
    v = float(v)
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:.1f}M".replace(".0M", "M")
    if abs(v) >= 10_000:
        return f"{v / 1000:.0f}K"
    if abs(v) >= 1000:
        return f"{v / 1000:.1f}K".replace(".0K", "K")
    return f"{v:g}"


def _style_axis(axis, grid=True):
    axis.setLabelsColor(QColor(theme.TEXT_MUTED))
    axis.setLinePen(QPen(QColor(theme.AXIS), 1))
    axis.setGridLinePen(QPen(QColor(theme.GRID), 1))
    axis.setGridLineVisible(grid)
    axis.setMinorGridLineVisible(False)
    font = QFont("Segoe UI", 8)
    axis.setLabelsFont(font)
    axis.setTitleBrush(QColor(theme.TEXT_MUTED))
    axis.setTitleFont(font)


def new_chart(legend: bool) -> QChart:
    chart = QChart()
    chart.setBackgroundBrush(QColor(theme.SURFACE))
    chart.setBackgroundRoundness(0)
    chart.setMargins(QMargins(4, 4, 4, 4))
    chart.setAnimationOptions(QChart.NoAnimation)
    chart.legend().setVisible(legend)
    if legend:
        chart.legend().setAlignment(Qt.AlignTop)
        chart.legend().setLabelColor(QColor(theme.TEXT_SECONDARY))
        chart.legend().setFont(QFont("Segoe UI", 9))
        chart.legend().setMarkerShape(chart.legend().MarkerShape.MarkerShapeRectangle)
    return chart


class ChartView(QChartView):
    point_clicked = Signal(object)        # payload of the clicked point

    def __init__(self, chart: QChart):
        super().__init__(chart)
        self.setRenderHint(QPainter.Antialiasing)
        self.setMinimumHeight(260)
        self.setStyleSheet("background: transparent; border: none;")


class ChartCard(QFrame):
    """Titled card holding a chart; 'Table' flips to the underlying numbers."""

    def __init__(self, title: str, view: QWidget, table: tuple[list[str], list[list]] | None = None,
                 subtitle: str = "", min_height: int = 300):
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        head = QHBoxLayout()
        title_box = QVBoxLayout()
        t = QLabel(title)
        t.setObjectName("sectionTitle")
        title_box.addWidget(t)
        if subtitle:
            st = QLabel(subtitle)
            st.setObjectName("muted")
            title_box.addWidget(st)
        head.addLayout(title_box)
        head.addStretch()
        self.title_text = title
        self.stack = QStackedWidget()
        self.stack.addWidget(view)
        self.table_btn = None
        if table:
            btn = self.table_btn = QPushButton("Table")
            btn.setCheckable(True)
            btn.setToolTip("Show the numbers behind the chart")
            btn.toggled.connect(lambda on: self.stack.setCurrentIndex(1 if on else 0))
            head.addWidget(btn)
            self.stack.addWidget(make_table(*table))
        expand = QPushButton()
        expand.setFixedWidth(38)
        expand.setIcon(icons.icon("fullscreen", theme.TEXT_SECONDARY, 20))
        expand.setToolTip("Show this plot full screen")
        expand.clicked.connect(self.show_full)
        head.addWidget(expand)
        layout.addLayout(head)
        layout.addWidget(self.stack, 1)
        self.setMinimumHeight(max(min_height, view.minimumHeight() + 70))


    def show_full(self):
        """The plot (or its table) fills the screen until Esc / the close button; the widgets are borrowed
        from the card for that time."""
        dlg = QDialog(self)
        dlg.setWindowFlag(Qt.Window)
        layout = QVBoxLayout(dlg)
        head = QHBoxLayout()
        t = QLabel(self.title_text)
        t.setObjectName("sectionTitle")
        head.addWidget(t)
        head.addStretch()
        if self.table_btn is not None:
            btn = QPushButton("Table")
            btn.setCheckable(True)
            btn.setChecked(self.table_btn.isChecked())
            btn.toggled.connect(self.table_btn.setChecked)
            head.addWidget(btn)
        close = QPushButton()
        close.setFixedWidth(38)
        close.setIcon(icons.icon("fullscreen_exit", theme.TEXT_SECONDARY, 20))
        close.setToolTip("Leave full screen (Esc)")
        close.clicked.connect(dlg.accept)
        head.addWidget(close)
        layout.addLayout(head)
        self.layout().removeWidget(self.stack)
        layout.addWidget(self.stack, 1)
        view = self.stack.widget(0)
        if hasattr(view, "point_clicked"):          # opening an entry from the plot closes the full screen
            view.point_clicked.connect(dlg.accept)
        dlg.setWindowState(Qt.WindowFullScreen)
        try:
            dlg.exec()
        finally:
            self.layout().addWidget(self.stack, 1)
            self.stack.setParent(self)
            self.stack.show()


class HeatDelegate(QStyledItemDelegate):
    """Paints cell shading itself (the table stylesheet would otherwise ignore item backgrounds)."""

    def paint(self, p, option, index):
        p.save()
        brush = index.data(Qt.BackgroundRole)
        if option.state & QStyle.State_Selected:
            p.fillRect(option.rect, QColor("#e6eaf0"))
        elif brush is not None:
            p.fillRect(option.rect, brush)
        else:
            p.fillRect(option.rect, QColor("#fafaf7" if index.row() % 2 else theme.SURFACE))
        fg = index.data(Qt.ForegroundRole)
        p.setPen(fg.color() if fg is not None else QColor(theme.TEXT))
        font = index.data(Qt.FontRole)
        p.setFont(font if font is not None else option.font)
        align = int(index.data(Qt.TextAlignmentRole) or int(Qt.AlignLeft | Qt.AlignVCenter))
        text = p.fontMetrics().elidedText(str(index.data(Qt.DisplayRole) or ""), Qt.ElideRight,
                                          option.rect.width() - 20)
        p.drawText(option.rect.adjusted(10, 0, -10, 0), align, text)
        p.restore()


def make_table(headers: list[str], rows: list[list], heat: str | None = None) -> QTableWidget:
    """heat = colour: shade the count cells (all numeric columns except the first and a trailing Total)."""
    tbl = QTableWidget(len(rows), len(headers))
    tbl.setHorizontalHeaderLabels(headers)
    tbl.verticalHeader().setVisible(False)
    tbl.verticalHeader().setDefaultSectionSize(34)
    tbl.horizontalHeader().setMinimumHeight(36)
    tbl.horizontalHeader().setHighlightSections(False)
    tbl.setEditTriggers(QTableWidget.NoEditTriggers)
    tbl.setAlternatingRowColors(True)
    tbl.setShowGrid(False)
    tbl.setSelectionBehavior(QTableWidget.SelectRows)
    tbl.setWordWrap(False)
    if heat:
        tbl.setItemDelegate(HeatDelegate(tbl))
    numeric = [any(isinstance(r[c], (int, float)) for r in rows) for c in range(len(headers))]
    peak = max([v for r in rows for c, v in enumerate(r) if c > 0 and headers[c] != "Total"
                and isinstance(v, (int, float))] or [1])
    bold = QFont()
    bold.setWeight(QFont.DemiBold)
    for c, is_num in enumerate(numeric):
        hi = tbl.horizontalHeaderItem(c)
        hi.setTextAlignment((Qt.AlignRight if is_num else Qt.AlignLeft) | Qt.AlignVCenter)
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            item = QTableWidgetItem()
            if isinstance(v, (int, float)):
                item.setData(Qt.DisplayRole, v)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            else:
                item.setText(str(v))
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            if c == 0 or headers[c] == "Total":
                item.setFont(bold)
            if heat and isinstance(v, (int, float)) and not v and c > 0 and headers[c] != "Total":
                item.setForeground(QColor("#d3d1c8"))                  # zeros recede
            if heat and isinstance(v, (int, float)) and v and headers[c] != "Total" and c > 0:
                a = 0.16 + 0.62 * min(1.0, v / peak)            # blend over the surface (opaque: Qt ignores alpha here)
                base, surf = QColor(heat), QColor(theme.SURFACE)
                item.setBackground(QColor(int(surf.red() + (base.red() - surf.red()) * a),
                                          int(surf.green() + (base.green() - surf.green()) * a),
                                          int(surf.blue() + (base.blue() - surf.blue()) * a)))
            tbl.setItem(r, c, item)
    hh = tbl.horizontalHeader()
    hh.setSectionResizeMode(QHeaderView.ResizeToContents)
    tbl.resizeColumnsToContents()
    for c in range(len(headers)):
        tbl.setColumnWidth(c, max(150 if c == 0 and not numeric[0] else 88, tbl.columnWidth(c) + 22))
    if headers and numeric[-1]:
        hh.setSectionResizeMode(QHeaderView.Stretch)      # all-numeric tables fill the card evenly
        if not numeric[0]:                                  # label column keeps room for long names
            hh.setSectionResizeMode(0, QHeaderView.Fixed)
            tbl.setColumnWidth(0, 200)
    else:
        hh.setStretchLastSection(True)
    tbl.setSortingEnabled(True)
    return tbl


def empty_view(text="No data for this selection") -> QWidget:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setObjectName("muted")
    return lbl


# ------------------------------------------------------------------ bars
def bar_chart(categories: list[str], series: list[tuple[str, str, list[float]]], horizontal=False,
              unit: str = "", title: str = "", subtitle: str = "", min_height=300) -> ChartCard:
    """Stacked bars. series = [(name, colour, values per category)]."""
    series = [s for s in series if any(s[2])]
    headers = [""] + [s[0] for s in series] + (["Total"] if len(series) > 1 else [])
    rows = []
    for i, cat in enumerate(categories):
        vals = [s[2][i] for s in series]
        rows.append([cat] + vals + ([round(sum(vals), 1)] if len(series) > 1 else []))
    if not series:
        return ChartCard(title, empty_view(), subtitle=subtitle, min_height=min_height)
    chart = new_chart(legend=len(series) > 1)
    bars = QHorizontalStackedBarSeries() if horizontal else QStackedBarSeries()
    bars.setBarWidth(0.62)
    for name, color, values in series:
        s = QBarSet(name)
        s.setColor(QColor(color))
        s.setBorderColor(QColor(theme.SURFACE))
        s.setPen(QPen(QColor(theme.SURFACE), 1))
        s.append([float(v) for v in values])
        bars.append(s)

    def hovered(status, index, barset):
        if status:
            total = sum(b.at(index) for b in bars.barSets())
            lines = [f"<b>{categories[index]}</b>"]
            for b in bars.barSets():
                if b.at(index):
                    mark = "■" if b is barset else "□"
                    lines.append(f"{mark} {b.label()}: {b.at(index):g}{unit}")
            if len(bars.barSets()) > 1:
                lines.append(f"Total: {total:g}{unit}")
            QToolTip.showText(QCursor.pos(), "<br>".join(lines))
        else:
            QToolTip.hideText()
    bars.hovered.connect(hovered)
    chart.addSeries(bars)
    cat_axis = QBarCategoryAxis()
    cat_axis.append(categories)
    val_axis = QValueAxis()
    totals = [sum(s[2][i] for s in series) for i in range(len(categories))]
    val_axis.setRange(0, nice_max(max(totals) if totals else 1))
    val_axis.setTickCount(6)
    val_axis.setLabelFormat("%.0f")
    _style_axis(cat_axis, grid=False)
    _style_axis(val_axis)
    if horizontal:
        chart.addAxis(cat_axis, Qt.AlignLeft)
        chart.addAxis(val_axis, Qt.AlignBottom)
    else:
        chart.addAxis(cat_axis, Qt.AlignBottom)
        chart.addAxis(val_axis, Qt.AlignLeft)
    bars.attachAxis(cat_axis)
    bars.attachAxis(val_axis)
    view = ChartView(chart)
    if horizontal:
        view.setMinimumHeight(max(260, 26 * len(categories) + 80))
    return ChartCard(title, view, (headers, rows), subtitle, min_height)


def nice_max(v: float) -> float:
    """Smallest 'round' axis maximum >= v that is divisible by 5 (5 even tick intervals)."""
    if v <= 5:
        return 5
    k = 1
    while True:
        for m in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8):
            cand = m * 10 ** k
            if cand >= v:
                return cand
        k += 1


# -------------------------------------------------------------- timeline
class Point:
    __slots__ = ("when", "y", "size", "label", "payload")

    def __init__(self, when, y, label="", payload=None, size=10.0):
        self.when, self.y, self.label, self.payload, self.size = when, y, label, payload, size


def _date_axis(chart, xs: list[float]):
    axis = QDateTimeAxis()
    span_days = (max(xs) - min(xs)) / 86400000 if xs else 0
    axis.setFormat("MMM yyyy" if span_days < 900 else "yyyy")
    pad = max(86400000 * 10, (max(xs) - min(xs)) * 0.03) if xs else 0
    if xs:
        axis.setRange(QDateTime.fromMSecsSinceEpoch(int(min(xs) - pad)),
                      QDateTime.fromMSecsSinceEpoch(int(max(xs) + pad)))
    axis.setTickCount(min(12, max(3, int(span_days / 365) + 2)) if span_days > 700 else 7)
    _style_axis(axis)
    chart.addAxis(axis, Qt.AlignBottom)
    return axis


def timeline(groups: list[tuple[str, str, list[Point]]], title: str, subtitle: str = "",
             y_labels: dict[float, str] | None = None, y_unit: str = "", y_range=None,
             line=False, on_click=None, reverse_y=False, min_height=320) -> ChartCard:
    """Scatter (or line) over time. groups = [(name, colour, points)].

    y_labels: value -> label for category/grade axes; otherwise a numeric axis.
    """
    groups = [g for g in groups if g[2]]
    if not groups:
        return ChartCard(title, empty_view(), subtitle=subtitle, min_height=min_height)
    chart = new_chart(legend=len(groups) > 1)
    xs, ys = [], []
    lookup: dict = {}
    series_list = []
    for name, color, points in groups:
        points = sorted(points, key=lambda p: p.when)
        if line:
            s = QLineSeries()
            pen = QPen(QColor(color), 2)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            s.setPen(pen)
            s.setPointsVisible(len(points) < 60)
            s.setMarkerSize(7)
        else:
            s = QScatterSeries()
            s.setMarkerShape(QScatterSeries.MarkerShapeCircle)
            s.setMarkerSize(11)
            s.setColor(QColor(color))
            s.setBorderColor(QColor(theme.SURFACE))
        s.setName(name)
        for p in points:
            x = to_ms(p.when)
            s.append(x, p.y)
            xs.append(x)
            ys.append(p.y)
            lookup[(round(x), round(p.y, 3), name)] = p
        if not line:
            try:   # per-point marker size (Qt >= 6.2)
                for i, p in enumerate(points):
                    if p.size != 10.0:
                        s.setPointConfiguration(i, {QXYSeries.PointConfiguration.Size: float(p.size)})
            except (AttributeError, TypeError):
                pass

        def find(pt, series_name=name):
            return lookup.get((round(pt.x()), round(pt.y(), 3), series_name))

        def hovered(pt, state, find=find):
            p = find(pt)
            if state and p:
                QToolTip.showText(QCursor.pos(), p.label)
            else:
                QToolTip.hideText()

        def clicked(pt, find=find):
            p = find(pt)
            if p and on_click and p.payload:
                on_click(p.payload)
        s.hovered.connect(hovered)
        s.clicked.connect(clicked)
        chart.addSeries(s)
        series_list.append(s)
    x_axis = _date_axis(chart, xs)
    if y_labels:
        y_axis = QCategoryAxis()
        y_axis.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
        lo = min(ys + list(y_labels)) if not y_range else y_range[0]
        hi = max(ys + list(y_labels)) if not y_range else y_range[1]
        # thin out labels so they never overlap
        keys = [k for k in sorted(y_labels) if lo <= k <= hi]
        step = max(1, len(keys) // 14 + (1 if len(keys) % 14 else 0)) if len(keys) > 14 else 1
        for k in keys[::step]:
            y_axis.append(y_labels[k], k)
        y_axis.setRange(lo - 0.8, hi + 0.8)
        y_axis.setStartValue(lo - 0.8)
    else:
        y_axis = QValueAxis()
        lo, hi = (min(ys), max(ys)) if not y_range else y_range
        pad = (hi - lo) * 0.08 or 1
        y_axis.setRange(max(0, lo - pad) if lo >= 0 else lo - pad, hi + pad)
        y_axis.setTickCount(6)
        y_axis.setLabelFormat("%.0f" + (f" {y_unit}" if y_unit else ""))
    if reverse_y:
        y_axis.setReverse(True)
    _style_axis(y_axis)
    chart.addAxis(y_axis, Qt.AlignLeft)
    for s in series_list:
        s.attachAxis(x_axis)
        s.attachAxis(y_axis)
    view = ChartView(chart)
    if y_labels:
        view.setMinimumHeight(max(260, 17 * len([k for k in y_labels if min(ys) - 1 <= k <= max(ys) + 1]) + 120))
    table = (["Date", "Series", "Value", "Entry"],
             [[p.when.strftime("%Y-%m-%d"), name, round(p.y, 1) if not y_labels else y_labels.get(p.y, p.y),
               p.label.split("<br>")[0].replace("<b>", "").replace("</b>", "")]
              for name, _, pts in groups for p in pts])
    return ChartCard(title, view, table, subtitle, min_height)


def gantt(rows: list[str], bars: list[tuple[int, date, date, str, str, object]], title: str,
          subtitle: str = "", on_click=None, min_height=300) -> ChartCard:
    """Horizontal time bars. bars = [(row index, start, end, colour, label, payload)]."""
    if not bars:
        return ChartCard(title, empty_view(), subtitle=subtitle, min_height=min_height)
    chart = new_chart(legend=False)
    xs = []
    series = []
    for row, start, end, color, label, payload in bars:
        s = QLineSeries()
        pen = QPen(QColor(color), 12)
        pen.setCapStyle(Qt.FlatCap)
        s.setPen(pen)
        x1, x2 = to_ms(start) - 43200000, to_ms(end) + 43200000
        s.append(x1, row)
        s.append(x2, row)
        xs += [x1, x2]
        s.hovered.connect(lambda pt, state, label=label: QToolTip.showText(QCursor.pos(), label)
                          if state else QToolTip.hideText())
        if on_click:
            s.clicked.connect(lambda pt, payload=payload: on_click(payload))
        chart.addSeries(s)
        series.append(s)
    x_axis = _date_axis(chart, xs)
    y_axis = QCategoryAxis()
    y_axis.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
    for i, r in enumerate(rows):
        y_axis.append(r, i)
    y_axis.setRange(-0.8, len(rows) - 0.2)
    y_axis.setStartValue(-0.8)
    _style_axis(y_axis)
    chart.addAxis(y_axis, Qt.AlignLeft)
    for s in series:
        s.attachAxis(x_axis)
        s.attachAxis(y_axis)
    table = (["From", "Until", "Row", "Entry"],
             [[b[1].isoformat(), b[2].isoformat(), rows[b[0]], b[4].split("<br>")[0].replace("<b>", "").replace("</b>", "")]
              for b in bars])
    return ChartCard(title, ChartView(chart), table, subtitle, min_height)


# ------------------------------------------------------------ stat tiles
class StatTile(QFrame):
    def __init__(self, label: str, value, sub: str = "", color: str | None = None):
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)
        head = QHBoxLayout()
        if color:
            kind = next((k for k, c in theme.KIND_COLORS.items() if c == color), None)
            if kind:
                mark = QLabel()
                mark.setPixmap(icons.pixmap(kind, icons.shade(color, 0.85), 26, 2.3))
                head.addWidget(mark)
            else:
                head.addWidget(theme.swatch(color, 9))
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {theme.TEXT_SECONDARY};")
        head.addWidget(lbl)
        head.addStretch()
        layout.addLayout(head)
        v = QLabel(f"{value:,}".replace(",", "'") if isinstance(value, int) else str(value))
        v.setStyleSheet("font-size: 20pt; font-weight: 600;")
        layout.addWidget(v)
        s = QLabel(sub or " ")
        s.setObjectName("muted")
        layout.addWidget(s)


__all__ = ["tints", "bar_chart", "timeline", "gantt", "ChartCard", "StatTile", "Point", "slot_colors", "compact",
           "QPointF"]
