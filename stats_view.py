"""Statistics page: per-topic dashboards built from the schema data."""
from collections import Counter, defaultdict
from datetime import date

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

import grades
import icons
from widgets import ComboBox, FullScreenButton
import schema
import theme
from charts import tints, Point, StatTile, bar_chart, gantt, slot_colors, timeline, compact
from database import parse_date, split_list

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
TOPICS = [("overview", "Overview"), ("climbing_days", "Rock"), ("sport_routes", "Tick list"),
          ("alpine_climbs", "Alpine"), ("mountain_tours", "Tours"), ("training_sessions", "Training"),
          ("cycling", "Cycling"), ("paragliding", "Paragliding"), ("trips", "Trips"), ("competitions", "Competitions"), ("body_metrics", "Body")]
STYLE_ORDER = ["onsight", "flash", "redpoint"]
PARTNER_KINDS = ["climbing_days", "alpine_climbs", "mountain_tours", "paragliding", "cycling", "trips"]


def style_of(attempts: str) -> str:
    return attempts if attempts in ("onsight", "flash") else "redpoint"


def tint_colors(kind: str, names: list[str]) -> dict[str, str]:
    """Colour per sub type: shades of the category colour in the order of ``names`` (slots when there are many).
    Used by the statistics charts and the list view so a sub type has the same colour everywhere."""
    if len(names) <= 8:
        return dict(zip(names, tints(schema.KINDS[kind].color, len(names))))
    return slot_colors(names)


def subtype_names(kind: str, records: list[dict]) -> list[str]:
    """Stable order: the field's choice list first, then any other values seen."""
    spec = schema.KINDS[kind]
    f = spec.field(spec.subtype) if spec.subtype else None
    names = list(f.choices or []) if f else []
    seen = Counter(r.get(spec.subtype) or "—" for r in records) if spec.subtype else Counter()
    names = [n for n in names if n in seen] + sorted(n for n in seen if n not in names)
    return names


def esc(text) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;")


class StatsView(QWidget):
    open_entry = Signal(str, str)     # kind, id

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.topic = "overview"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        tabs = QHBoxLayout()               # topic buttons: scrolls sideways when the window is narrow
        tabs.setContentsMargins(0, 0, 0, 0)
        self.group = QButtonGroup(self)
        for i, (key, label) in enumerate(TOPICS):
            b = QPushButton(label)
            tint = icons.shade(schema.KINDS[key].color) if key in schema.KINDS else theme.TEXT_SECONDARY
            b.setIcon(icons.icon(key, tint, 24, on_color="#ffffff", width=2.3))
            b.setIconSize(QSize(24, 24))
            b.setCheckable(True)
            b.setChecked(key == self.topic)
            self.group.addButton(b, i)
            b.clicked.connect(lambda _=False, k=key: self.set_topic(k))
            tabs.addWidget(b)
        tabs.addStretch()
        tab_holder = QWidget()
        tab_holder.setLayout(tabs)
        tab_scroll = QScrollArea()
        tab_scroll.setWidget(tab_holder)
        tab_scroll.setWidgetResizable(True)
        tab_scroll.setFrameShape(QFrame.NoFrame)
        tab_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tab_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        tab_scroll.setFixedHeight(58)
        tab_holder.setObjectName("tabHolder")
        tab_scroll.setObjectName("tabScroll")
        tab_scroll.setStyleSheet("QScrollArea#tabScroll { background: transparent; } QWidget#tabHolder { background: transparent; }")
        tab_scroll.viewport().setAutoFillBackground(False)
        bar.addWidget(tab_scroll, 1)
        bar.addWidget(QLabel("Year:"))
        self.year_combo = ComboBox()
        self.year_combo.currentIndexChanged.connect(lambda _: self.rebuild())
        bar.addWidget(self.year_combo)
        self.full_btn = FullScreenButton()
        bar.addWidget(self.full_btn)
        layout.addLayout(bar)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        layout.addWidget(self.scroll, 1)
        self.refresh()

    # ------------------------------------------------------------ plumbing
    def refresh(self):
        current = self.year_combo.currentData()
        rng = self.db.date_range()
        years = list(range(rng[1].year, rng[0].year - 1, -1)) if rng else []
        self.year_combo.blockSignals(True)
        self.year_combo.clear()
        self.year_combo.addItem("All years", None)
        for y in years:
            self.year_combo.addItem(str(y), y)
        idx = self.year_combo.findData(current)
        self.year_combo.setCurrentIndex(max(0, idx))
        self.year_combo.blockSignals(False)
        self.rebuild()

    def set_topic(self, key: str):
        self.topic = key
        self.rebuild()

    @property
    def year(self) -> int | None:
        return self.year_combo.currentData()

    def records(self, kind: str) -> list[dict]:
        out = []
        for r in self.db.entries(kind):
            d = parse_date(r.get("date"))
            if d and (self.year is None or d.year == self.year):
                out.append(r)
        return out

    def periods(self) -> tuple[list[str], callable]:
        """Categories + function date -> category index for the current year filter."""
        if self.year is not None:
            return MONTHS, lambda d: d.month - 1
        rng = self.db.date_range()
        if not rng:
            return [], lambda d: 0
        years = list(range(rng[0].year, rng[1].year + 1))
        return [str(y) for y in years], lambda d: d.year - years[0]

    def tint_map(self, kind: str, names: list[str]) -> dict[str, str]:
        """Colours for the series inside one category: shades of its colour (categorical slots when there are many)."""
        return tint_colors(kind, names)

    def per_period(self, kind: str, records, split_key=None, value=lambda r: 1, names=None,
                   colors=None) -> tuple[list[str], list]:
        cats, idx = self.periods()
        if split_key:
            names = names or subtype_names(kind, records)
            colors = colors or self.tint_map(kind, names)
        else:
            names = [schema.KINDS[kind].plural]
            colors = {names[0]: schema.KINDS[kind].color}
        data = {n: [0] * len(cats) for n in names}
        for r in records:
            d = parse_date(r.get("date"))
            n = (r.get(split_key) or "—") if split_key else names[0]
            if n not in data or not cats:
                continue
            data[n][idx(d)] += value(r)
        series = [(n, colors[n], data[n]) for n in names]
        return self.trim(cats, series)

    def trim(self, cats, series):
        """Drop empty years at both ends (only for the all-years view)."""
        if self.year is not None or not cats:
            return cats, series
        used = [i for i in range(len(cats)) if any(s[2][i] for s in series)]
        if not used:
            return cats, series
        lo, hi = used[0], used[-1] + 1
        return cats[lo:hi], [(n, c, v[lo:hi]) for n, c, v in series]

    def period_word(self) -> str:
        return "per month" if self.year is not None else "per year"

    def click(self, kind: str):
        return lambda payload: self.open_entry.emit(kind, payload)

    def rebuild(self):
        page = QWidget()
        self.grid = QGridLayout(page)
        self.grid.setContentsMargins(0, 8, 8, 8)
        self.grid.setSpacing(12)
        self.row = 0
        builder = getattr(self, f"build_{self.topic}")
        builder()
        self.grid.setRowStretch(self.row, 1)
        self.scroll.setWidget(page)

    def add(self, widget, span=2):
        if span == 2:
            if getattr(self, "_half", False):
                self.row += 1
                self._half = False
            self.grid.addWidget(widget, self.row, 0, 1, 2)
            self.row += 1
        else:
            col = 1 if getattr(self, "_half", False) else 0
            self.grid.addWidget(widget, self.row, col)
            if col == 1:
                self.row += 1
            self._half = col == 0

    def tiles(self, items: list[tuple]):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(12)
        for it in items:
            h.addWidget(StatTile(*it))
        self.add(row)

    # -------------------------------------------------------------- topics
    def build_overview(self):
        days = self.records("climbing_days")
        routes = self.records("sport_routes")
        alpine = self.records("alpine_climbs")
        tours = self.records("mountain_tours")
        training = self.records("training_sessions")
        trips = self.records("trips")
        active_days = set()
        for kind in schema.LEGEND_KINDS:
            for r in self.records(kind):
                active_days.update(schema.record_days(r))
        self.tiles([
            ("Active days", len(active_days), "with any activity"),
            ("Climbing days", len(days), "", schema.KINDS["climbing_days"].color),
            ("Alpine climbs", len(alpine), f"{compact(sum(r.get('meters') or 0 for r in alpine))} m climbed",
             schema.KINDS["alpine_climbs"].color),
            ("Mountain tours", len(tours), f"{compact(sum(r.get('elevation_gain') or 0 for r in tours))} Hm",
             schema.KINDS["mountain_tours"].color),
            ("Training sessions", len(training), "", schema.KINDS["training_sessions"].color),
            ("Cycling", len(self.records("cycling")),
             f"{compact(sum(r.get('distance') or 0 for r in self.records('cycling')))} km",
             schema.KINDS["cycling"].color),
            ("Paragliding", sum(schema.para_totals(r)["flights"] for r in self.records("paragliding")), "flights",
             schema.KINDS["paragliding"].color),
            ("Trip days", sum(len(schema.record_days(r)) for r in trips), f"{len(trips)} trips",
             schema.KINDS["trips"].color),
        ])
        kinds = ["alpine_climbs", "competitions", "trips", "training_sessions", "sport_routes",
                 "mountain_tours", "climbing_days", "cycling", "paragliding"]   # validated colour order
        cats, idx = self.periods()
        series = []
        for kind in kinds:
            values = [0] * len(cats)
            for r in self.records(kind):
                if cats:
                    values[idx(parse_date(r["date"]))] += 1
            if any(values):
                series.append((schema.KINDS[kind].plural, schema.KINDS[kind].color, values))
        cats, series = self.trim(cats, series)
        self.add(bar_chart(cats, series, title=f"Entries {self.period_word()}",
                           subtitle="Stacked by kind of activity; hover a bar for the breakdown"))
        # timeline of everything (V1 'Zeitstrahl Gesamt')
        rows = ["climbing_days", "sport_routes", "alpine_climbs", "mountain_tours", "training_sessions",
                "cycling", "paragliding", "competitions", "trips"]
        groups = []
        for i, kind in enumerate(rows):
            spec = schema.KINDS[kind]
            pts = [Point(parse_date(r["date"]), i, f"<b>{esc(spec.title(r))}</b><br>{parse_date(r['date']):%d.%m.%Y}",
                         r["id"], 9) for r in self.records(kind)]
            groups.append((spec.plural, spec.color, pts, kind))
        if self.year is not None:
            card = timeline([(g[0], g[1], g[2]) for g in groups], "Timeline", "Every entry of the year; click a dot to open it",
                            y_labels={i: schema.KINDS[k].plural for i, k in enumerate(rows)},
                            on_click=lambda p: self._open_any(p), min_height=360)
            self.add(card)
        else:
            hint = QLabel("Pick a year to see the timeline of every single entry.")
            hint.setObjectName("muted")
            self.add(hint)
        # partners, one colour per category
        per_kind: dict[str, Counter] = {k: Counter() for k in PARTNER_KINDS}
        for kind in PARTNER_KINDS:
            for r in self.records(kind):
                for p in set(split_list(r.get("partner") or "")):
                    per_kind[kind][p] += 1
        totals = Counter()
        for c in per_kind.values():
            totals.update(c)
        top = [p for p, _ in totals.most_common(15)][::-1]
        series = [(schema.KINDS[k].plural, schema.KINDS[k].color, [per_kind[k][p] for p in top])
                  for k in PARTNER_KINDS if any(per_kind[k][p] for p in top)]
        self.add(bar_chart(top, series, horizontal=True, title="Most frequent partners",
                           subtitle="Entries together, coloured by category"), span=1)
        areas = Counter(r.get("area") for r in days if r.get("area")).most_common(15)[::-1]
        self.add(bar_chart([a for a, _ in areas], [("Climbing days", schema.KINDS["climbing_days"].color,
                                                    [c for _, c in areas])],
                           horizontal=True, title="Top climbing areas", subtitle="Number of climbing days"), span=1)
        self.partners_section(PARTNER_KINDS, ' (all categories)')

    def year_table(self, kind: str, title: str, value=None, value_label="", partners=True, trip_days=False):
        """V1 'Statistik' table: per year counts by sub type (+ total, sums, top partners)."""
        from charts import ChartCard, make_table
        from database import split_list
        records = self.db.entries(kind)          # always all years
        names = subtype_names(kind, records)
        years = sorted({parse_date(r["date"]).year for r in records}, reverse=True)
        headers = ["Year"] + names + ["Total"] + ([value_label] if value else []) +                   (["Days on trips"] if trip_days else []) + (["Top partners"] if partners else [])
        trip_set = set()
        if trip_days:
            for t in self.db.entries("trips"):
                trip_set.update(schema.record_days(t))
        sub_key = schema.KINDS[kind].subtype
        rows = []
        for y in years:
            rs = [r for r in records if parse_date(r["date"]).year == y]
            row = [str(y)] + [sum(1 for r in rs if (r.get(sub_key) or "—") == n) for n in names] + [len(rs)]
            if value:
                row.append(round(sum(value(r) for r in rs), 1))
            if trip_days:
                row.append(sum(1 for r in rs if parse_date(r["date"]) in trip_set))
            if partners:
                c = Counter(p for r in rs for p in split_list(r.get("partner") or ""))
                row.append(", ".join(f"{p} ({n})" for p, n in c.most_common(3)))
            rows.append(row)
        table = make_table(headers, rows)
        table.setMinimumHeight(min(420, 40 + 28 * len(rows)))
        self.add(ChartCard(title, table, subtitle="All years, like the V1 statistics window", min_height=200))

    def _open_any(self, entry_id):
        for kind, r in self.db.all_entries():
            if r.get("id") == entry_id:
                self.open_entry.emit(kind, entry_id)
                return

    def build_climbing_days(self):
        days = self.records("climbing_days")
        self.tiles([("Climbing days", len(days), "", schema.KINDS["climbing_days"].color)] +
                   [(n, sum(1 for r in days if r.get("discipline") == n), "")
                    for n in subtype_names("climbing_days", days)[:4]])
        cats, series = self.per_period("climbing_days", days, "discipline")
        self.add(bar_chart(cats, series, title=f"Climbing days {self.period_word()}", subtitle="By discipline"))
        crags = Counter(f"{r.get('crag')} ({r.get('area')})" for r in days if r.get("crag")).most_common(20)[::-1]
        self.add(bar_chart([c for c, _ in crags], [("Days", schema.KINDS["climbing_days"].color, [n for _, n in crags])],
                           horizontal=True, title="Top crags", subtitle="Number of climbing days"), span=1)
        areas = Counter(r.get("area") for r in days if r.get("area")).most_common(20)[::-1]
        self.add(bar_chart([c for c, _ in areas], [("Days", schema.KINDS["climbing_days"].color, [n for _, n in areas])],
                           horizontal=True, title="Top areas", subtitle="Number of climbing days"), span=1)
        weekday = [0] * 7
        for r in days:
            weekday[parse_date(r["date"]).weekday()] += 1
        self.add(bar_chart(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                           [("Days", schema.KINDS["climbing_days"].color, weekday)],
                           title="Climbing days by weekday"), span=1)
        month = [0] * 12
        for r in days:
            month[parse_date(r["date"]).month - 1] += 1
        self.add(bar_chart(MONTHS, [("Days", schema.KINDS["climbing_days"].color, month)],
                           title="Climbing days by month of year", subtitle="Seasonality"), span=1)
        self.year_table("climbing_days", "Climbing days per year", trip_days=True)
        self.partners_section(["climbing_days"])

    def build_sport_routes(self):
        routes = self.records("sport_routes")
        disciplines = subtype_names("sport_routes", routes)
        colors = self.tint_map("sport_routes", STYLE_ORDER)
        best = max((grades.rock_index(r.get("grade")) for r in routes), default=-1)
        os_best = max((grades.rock_index(r.get("grade")) for r in routes if r.get("attempts") == "onsight"),
                      default=-1)
        self.tiles([("Routes", len(routes), "", schema.KINDS["sport_routes"].color),
                    ("Hardest", grades.rock_label(best) if best >= 0 else "–", "any style"),
                    ("Hardest onsight", grades.rock_label(os_best) if os_best >= 0 else "–", ""),
                    ("Onsight / flash", sum(1 for r in routes if style_of(r.get("attempts")) != "redpoint"), "")])
        for disc in disciplines or ["—"]:
            sub = [r for r in routes if (r.get("discipline") or "—") == disc]
            idxs = [grades.rock_index(r.get("grade")) for r in sub if grades.rock_index(r.get("grade")) >= 0]
            if not idxs:
                continue
            levels = list(range(min(idxs), max(idxs) + 1))[::-1]
            labels = [grades.rock_label(i) for i in levels]
            data = {s: [0] * len(levels) for s in STYLE_ORDER}
            for r in sub:
                i = grades.rock_index(r.get("grade"))
                if i >= 0:
                    data[style_of(r.get("attempts"))][levels.index(i)] += 1
            self.add(bar_chart(labels[::-1], [(s, colors[s], data[s][::-1]) for s in STYLE_ORDER], horizontal=True,
                               title=f"Grade pyramid · {disc}", subtitle="Routes per grade by ascent style"), span=1)
        groups = []
        for s in STYLE_ORDER:
            pts = []
            for r in routes:
                i = grades.rock_index(r.get("grade"))
                if i < 0 or style_of(r.get("attempts")) != s:
                    continue
                pts.append(Point(parse_date(r["date"]), i,
                                 f"<b>{esc(r.get('name'))}</b> {esc(r.get('grade'))}<br>{esc(r.get('attempts'))} · "
                                 f"{esc(r.get('crag'))}<br>{parse_date(r['date']):%d.%m.%Y}", r["id"],
                                 13 if s != "redpoint" else 9))
            groups.append((s, colors[s], pts))
        all_idx = [p.y for g in groups for p in g[2]]
        if all_idx:
            labels = {i: grades.rock_label(i) for i in range(int(min(all_idx)), int(max(all_idx)) + 1)}
            self.add(timeline(groups, "Routes over time", "Grade of every route; click to open",
                              y_labels=labels, on_click=self.click("sport_routes")))
        cats, series = self.per_period("sport_routes", routes, "discipline")
        self.add(bar_chart(cats, series, title=f"Routes {self.period_word()}", subtitle="By discipline"))
        self.year_table("sport_routes", "Routes per year", partners=False)

    def build_alpine_climbs(self):
        tours = self.records("alpine_climbs")
        names = subtype_names("alpine_climbs", tours)
        colors = self.tint_map("alpine_climbs", names)
        self.tiles([("Alpine climbs", len(tours), "", schema.KINDS["alpine_climbs"].color),
                    ("Climbing meters", sum(r.get("meters") or 0 for r in tours), "m"),
                    ("Pitches", sum(r.get("pitches") or 0 for r in tours), ""),
                    ("First ascents", sum(1 for r in tours if r.get("first_ascent")), "")])
        cats, series = self.per_period("alpine_climbs", tours, "type")
        self.add(bar_chart(cats, series, title=f"Alpine climbs {self.period_word()}", subtitle="By type"), span=1)
        cats, series = self.per_period("alpine_climbs", tours, "type", value=lambda r: r.get("meters") or 0)
        self.add(bar_chart(cats, series, unit=" m", title=f"Climbing meters {self.period_word()}", subtitle="By type"),
                 span=1)
        # grade pyramid on the rock scale
        idxs = [grades.rock_index(r.get("grade")) for r in tours if grades.rock_index(r.get("grade")) >= 0]
        if idxs:
            levels = list(range(min(idxs), max(idxs) + 1))
            data = {n: [0] * len(levels) for n in names}
            for r in tours:
                i = grades.rock_index(r.get("grade"))
                if i >= 0:
                    data[r.get("type") or "—"][levels.index(i)] += 1
            self.add(bar_chart([grades.rock_label(i) for i in levels], [(n, colors[n], data[n]) for n in names],
                               horizontal=True, title="Grade pyramid (rock)", subtitle="Alpine climbs per grade by type"),
                     span=1)
        for key, scale_list, label in (("grade_wi", grades.WI, "ice"), ("grade_m", grades.M, "mixed")):
            vals = [r.get(key) for r in tours if r.get(key) in scale_list]
            if vals:
                c = Counter(vals)
                cats = [g for g in scale_list if g in c]
                self.add(bar_chart(cats, [("Climbs", colors.get("Eisklettern", schema.KINDS["alpine_climbs"].color), [c[g] for g in cats])],
                                   horizontal=True, title=f"Grades ({label})"), span=1)
        groups = []
        for n in names:
            pts = []
            for r in tours:
                i = grades.rock_index(r.get("grade"))
                if i < 0 or (r.get("type") or "—") != n:
                    continue
                pts.append(Point(parse_date(r["date"]), i,
                                 f"<b>{esc(r.get('name'))}</b> {esc(grades.alpine_display(r))}<br>"
                                 f"{esc(r.get('range'))} · {r.get('pitches') or '?'} pitches<br>"
                                 f"{parse_date(r['date']):%d.%m.%Y}", r["id"], 7 + min(16, (r.get("pitches") or 0) * 0.8)))
            groups.append((n, colors[n], pts))
        all_idx = [p.y for g in groups for p in g[2]]
        if all_idx:
            labels = {i: grades.rock_label(i) for i in range(int(min(all_idx)), int(max(all_idx)) + 1)}
            self.add(timeline(groups, "Alpine climbs over time", "Rock grade; dot size = pitches; click to open",
                              y_labels=labels, on_click=self.click("alpine_climbs")))
        massifs = Counter(r.get("range") for r in tours if r.get("range")).most_common(15)[::-1]
        self.add(bar_chart([m for m, _ in massifs], [("Climbs", schema.KINDS["alpine_climbs"].color, [c for _, c in massifs])],
                           horizontal=True, title="Top mountain ranges"), span=1)
        self.year_table("alpine_climbs", "Alpine climbs per year", value=lambda r: r.get("meters") or 0,
                        value_label="Climbing meters")
        self.partners_section(["alpine_climbs"])

    def build_mountain_tours(self):
        tours = self.records("mountain_tours")
        names = subtype_names("mountain_tours", tours)
        colors = self.tint_map("mountain_tours", names)
        highest = max(tours, key=lambda r: r.get("elevation") or 0, default=None)
        self.tiles([("Tours", len(tours), "", schema.KINDS["mountain_tours"].color),
                    ("Elevation gain", sum(r.get("elevation_gain") or 0 for r in tours), "Hm in total"),
                    ("Highest summit", f"{highest.get('elevation')} m" if highest and highest.get("elevation") else "–",
                     highest.get("name", "") if highest else ""),
                    ("Biggest day", f"{max((r.get('elevation_gain') or 0 for r in tours), default=0)} Hm", "")])
        cats, series = self.per_period("mountain_tours", tours, "type")
        self.add(bar_chart(cats, series, title=f"Tours {self.period_word()}", subtitle="By type"), span=1)
        cats, series = self.per_period("mountain_tours", tours, "type", value=lambda r: r.get("elevation_gain") or 0)
        self.add(bar_chart(cats, series, unit=" Hm", title=f"Elevation gain {self.period_word()}", subtitle="By type"),
                 span=1)
        for key, title, unit in (("elevation", "Summit elevation over time", "m"),
                                 ("elevation_gain", "Elevation gain over time", "Hm")):
            groups = []
            for n in names:
                pts = [Point(parse_date(r["date"]), r.get(key),
                             f"<b>{esc(r.get('name'))}</b> ({esc(r.get('range'))})<br>{r.get('elevation_gain') or 0} Hm · "
                             f"{r.get('elevation') or '?'} m<br>{parse_date(r['date']):%d.%m.%Y}", r["id"])
                       for r in tours if (r.get("type") or "—") == n and r.get(key)]
                groups.append((n, colors[n], pts))
            self.add(timeline(groups, title, "Click a dot to open the tour", y_unit=unit,
                              on_click=self.click("mountain_tours")))
        ranges = Counter(r.get("range") for r in tours if r.get("range")).most_common(15)[::-1]
        self.add(bar_chart([m for m, _ in ranges], [("Tours", schema.KINDS["mountain_tours"].color, [c for _, c in ranges])],
                           horizontal=True, title="Top mountain ranges"), span=1)
        self.year_table("mountain_tours", "Tours per year", value=lambda r: r.get("elevation_gain") or 0,
                        value_label="Elevation gain (Hm)")
        self.partners_section(["mountain_tours"])

    def build_training_sessions(self):
        sessions = self.records("training_sessions")
        fitness = [d for r in sessions for d in r.get("details") or [] if d.get("discipline") in ("Fitness", "Dehnen")]
        phases = subtype_names("training_sessions", sessions)
        self.tiles([("Training sessions", len(sessions), "", schema.KINDS["training_sessions"].color),
                    ("Exercises logged", sum(len(r.get("details") or []) for r in sessions), ""),
                    ("Fitness & stretching", len(fitness), f"{sum(d.get('duration') or 0 for d in fitness)} min"),
                    ("Gyms / places", len({schema.training_where(r) for r in sessions if schema.training_where(r)}), "")])
        cats, series = self.per_period("training_sessions", sessions, "phase", names=phases)
        self.add(bar_chart(cats, series, title=f"Training sessions {self.period_word()}", subtitle="By training phase"))
        disc_names = ["Boulder", "Lead", "Kraft", "Fitness", "Dehnen"]
        disc_colors = self.tint_map("training_sessions", disc_names)
        cats, idx = self.periods()
        data = {n: [0] * len(cats) for n in disc_names}
        for r in sessions:
            for d in {x.get("discipline") for x in r.get("details") or []}:
                if d in data and cats:
                    data[d][idx(parse_date(r["date"]))] += 1
        dcats, dseries = self.trim(cats, [(n, disc_colors[n], data[n]) for n in disc_names])
        self.add(bar_chart(dcats, dseries,
                           title=f"Sessions containing … {self.period_word()}", subtitle="One session can count for several"),
                 span=1)
        gyms = Counter(schema.training_where(r) for r in sessions if schema.training_where(r)).most_common(12)[::-1]
        self.add(bar_chart([g for g, _ in gyms], [("Sessions", schema.KINDS["training_sessions"].color, [c for _, c in gyms])],
                           horizontal=True, title="Gyms / places"), span=1)
        self.add(ExerciseProgress(self.db, sessions, self.click("training_sessions")))
        if fitness:
            methods = [m for m, _ in Counter(d.get("method") or "—" for d in fitness).most_common()]
            colors = self.tint_map("training_sessions", methods)
            data = {m: [0] * len(cats) for m in methods}
            for r in sessions:
                for d in r.get("details") or []:
                    if d.get("discipline") in ("Fitness", "Dehnen") and cats:
                        data[d.get("method") or "—"][idx(parse_date(r["date"]))] += d.get("duration") or 0
            fcats, fseries = self.trim(cats, [(m, colors[m], data[m]) for m in methods])
            self.add(bar_chart(fcats, fseries, unit=" min",
                               title=f"Fitness & stretching minutes {self.period_word()}", subtitle="By activity"))

    def partners_section(self, kinds: list[str], where: str = ""):
        """Partners per year (per month when a single year is selected): stacked top partners + full heat table."""
        from charts import ChartCard, make_table
        records = [r for k in kinds for r in self.records(k) if r.get("partner")]
        cats, idx = self.periods()
        counts: dict[str, list[int]] = {}
        for r in records:
            when = parse_date(r["date"])
            for p in set(split_list(r["partner"])):
                counts.setdefault(p, [0] * len(cats))[idx(when)] += 1
        if not counts or not cats:
            return
        ranked = sorted(counts, key=lambda p: (-sum(counts[p]), p.lower()))
        top = ranked[:8]
        colors = slot_colors(top)
        series = [(p, colors[p], counts[p]) for p in top]
        shown_cats, series = self.trim(cats, series)
        self.add(bar_chart(shown_cats, series, title=f"Top partners {self.period_word()}{where}",
                           subtitle=f"Entries together; the {len(top)} most frequent partners of {len(ranked)}"))
        lo = cats.index(shown_cats[0]) if shown_cats else 0
        hi = lo + len(shown_cats)
        headers = ["Partner"] + shown_cats + ["Total"]
        rows = [[p] + counts[p][lo:hi] + [sum(counts[p])] for p in ranked]
        color = schema.KINDS[kinds[0]].color if len(kinds) == 1 else theme.ACCENT
        table = make_table(headers, rows, heat=color)
        table.sortItems(len(headers) - 1, Qt.DescendingOrder)          # most frequent partner first
        table.setMinimumHeight(min(520, 44 + 34 * len(rows)))
        self.add(ChartCard(f"Partners {self.period_word()}{where}", table,
                           subtitle="Number of entries together; darker = more. Sort by clicking a header.",
                           min_height=240))

    def hint_if_empty(self, kind: str) -> bool:
        if self.db.entries(kind):
            return False
        lbl = QLabel(f"No {schema.KINDS[kind].plural.lower()} entries yet. Add one with '+ New entry'.")
        lbl.setObjectName("muted")
        self.add(lbl)
        return True

    def build_cycling(self):
        if self.hint_if_empty("cycling"):
            return
        rides = self.records("cycling")
        color = schema.KINDS["cycling"].color
        km = sum(r.get("distance") or 0 for r in rides)
        longest = max(rides, key=lambda r: r.get("distance") or 0, default=None)
        self.tiles([("Rides", len(rides), "", color),
                    ("Distance", f"{km:,.0f} km".replace(",", "'"), ""),
                    ("Time", f"{sum(r.get('duration') or 0 for r in rides) / 60:.0f} h", ""),
                    ("Elevation gain", sum(r.get("elevation_gain") or 0 for r in rides), "Hm"),
                    ("Longest ride", f"{longest.get('distance') or 0:g} km" if longest else "-",
                     (longest.get("name") or longest["date"]) if longest else "")])
        cats, series = self.per_period("cycling", rides, "type", value=lambda r: r.get("distance") or 0)
        self.add(bar_chart(cats, series, unit=" km", title=f"Distance {self.period_word()}", subtitle="By bike"),
                 span=1)
        cats, series = self.per_period("cycling", rides, "type")
        self.add(bar_chart(cats, series, title=f"Rides {self.period_word()}", subtitle="By bike"), span=1)
        names = subtype_names("cycling", rides)
        colors = self.tint_map("cycling", names)
        groups = [(n, colors[n], [Point(parse_date(r["date"]), r["distance"],
                                        f"<b>{esc(r.get('name') or n)}</b><br>{r['distance']:g} km, "
                                        f"{r.get('duration') or 0} min<br>{parse_date(r['date']):%d.%m.%Y}", r["id"])
                                  for r in rides if (r.get("type") or "—") == n and r.get("distance")])
                  for n in names]
        self.add(timeline(groups, "Rides over time", "Distance of every ride; click to open", y_unit="km",
                          on_click=self.click("cycling")))
        self.year_table("cycling", "Cycling per year", value=lambda r: r.get("distance") or 0,
                        value_label="Distance (km)", partners=False)
        self.partners_section(["cycling"])

    def build_paragliding(self):
        if self.hint_if_empty("paragliding"):
            return
        days = self.records("paragliding")
        color = schema.KINDS["paragliding"].color
        tot = [schema.para_totals(r) for r in days]
        flights = sum(t["flights"] for t in tot)
        high = max((t["max_altitude"] for t in tot), default=0)
        far = max((f.get("distance") or 0 for r in days for f in r.get("flights") or []), default=0)
        self.tiles([("Flying days", len(days), "", color),
                    ("Flights", flights, ""),
                    ("Airtime", f"{sum(t['airtime'] for t in tot) / 60:.1f} h", ""),
                    ("Highest", f"{high} m" if high else "-", "max. altitude"),
                    ("Longest flight", f"{far:g} km" if far else "-", "distance")])
        cats, series = self.per_period("paragliding", days, "type", value=lambda r: schema.para_totals(r)["flights"])
        self.add(bar_chart(cats, series, title=f"Flights {self.period_word()}", subtitle="By type"), span=1)
        cats, series = self.per_period("paragliding", days, "type",
                                       value=lambda r: round(schema.para_totals(r)["airtime"] / 60, 1))
        self.add(bar_chart(cats, series, unit=" h", title=f"Airtime {self.period_word()}", subtitle="By type"), span=1)
        names = subtype_names("paragliding", days)
        colors = self.tint_map("paragliding", names)
        groups = []
        for n in names:
            pts = []
            for r in days:
                if (r.get("type") or "—") != n:
                    continue
                for i, f in enumerate(r.get("flights") or [], 1):
                    if f.get("max_altitude"):
                        pts.append(Point(parse_date(r["date"]), f["max_altitude"],
                                         f"<b>{esc(r.get('mountain') or r.get('site'))}</b> flight {i}<br>"
                                         f"max {f['max_altitude']} m, {f.get('airtime') or 0} min<br>"
                                         f"{parse_date(r['date']):%d.%m.%Y}", r["id"]))
            groups.append((n, colors[n], pts))
        self.add(timeline(groups, "Maximum altitude per flight", "Click a dot to open the entry", y_unit="m",
                          on_click=self.click("paragliding")))
        moves = Counter()
        for r in days:
            for f in r.get("flights") or []:
                moves.update(f.get("maneuvers") or [])
        top = moves.most_common(15)[::-1]
        if top:
            self.add(bar_chart([m for m, _ in top], [("Times", color, [c for _, c in top])], horizontal=True,
                               title="Maneuvers", subtitle="Times logged across all flights"), span=1)
        sites = Counter(r.get("mountain") or r.get("site") for r in days if r.get("mountain") or r.get("site"))
        sites = sites.most_common(15)[::-1]
        self.add(bar_chart([x for x, _ in sites], [("Days", color, [c for _, c in sites])], horizontal=True,
                           title="Mountains / launch sites", subtitle="Flying days"), span=1)
        self.year_table("paragliding", "Paragliding per year", value=lambda r: schema.para_totals(r)["flights"],
                        value_label="Flights")
        self.partners_section(["paragliding"])

    def build_trips(self):
        trips = sorted(self.records("trips"), key=lambda r: r["date"])
        names = subtype_names("trips", trips)
        colors = self.tint_map("trips", names)
        self.tiles([("Trips", len(trips), "", schema.KINDS["trips"].color),
                    ("Trip days", sum(len(schema.record_days(r)) for r in trips), ""),
                    ("Destinations", len({r.get('destination') for r in trips}), "")])
        cats, series = self.per_period("trips", trips, "type", value=lambda r: len(schema.record_days(r)))
        self.add(bar_chart(cats, series, unit=" days", title=f"Trip days {self.period_word()}", subtitle="By type"))
        bars = []
        for r in trips:
            days = schema.record_days(r)
            n = r.get("type") or "—"
            bars.append((names.index(n), days[0], days[-1], colors[n],
                         f"<b>{esc(r.get('destination'))}</b><br>{days[0]:%d.%m.%Y} – {days[-1]:%d.%m.%Y} "
                         f"({len(days)} days)<br>{esc(r.get('partner') or '')}", r["id"]))
        self.add(gantt(names, bars, "Trips over time", "Each bar spans the trip; click to open",
                       on_click=self.click("trips")))
        self.partners_section(["trips"])

    def build_competitions(self):
        comps = self.records("competitions")
        names = subtype_names("competitions", comps)
        colors = self.tint_map("competitions", names)
        self.tiles([("Competitions", len(comps), "", schema.KINDS["competitions"].color),
                    ("Best result", min((r["result"] for r in comps if r.get("result")), default="–"), "rank"),
                    ("Podiums", sum(1 for r in comps if 0 < (r.get("result") or 0) <= 3), "")])
        cats, series = self.per_period("competitions", comps, "discipline")
        self.add(bar_chart(cats, series, title=f"Competitions {self.period_word()}", subtitle="By discipline"))
        groups = [(n, colors[n], [Point(parse_date(r["date"]), r["result"],
                                        f"<b>{esc(r.get('gym'))}</b><br>{esc(r.get('level'))} · {esc(n)}<br>Rank {r['result']}",
                                        r["id"]) for r in comps if (r.get("discipline") or "—") == n and r.get("result")])
                  for n in names]
        self.add(timeline(groups, "Results over time", "Rank (1 at the top); click to open", reverse_y=True,
                          on_click=self.click("competitions")))

    def build_body_metrics(self):
        body = sorted(self.records("body_metrics"), key=lambda r: r["date"])
        weights = [r.get("weight") for r in body if r.get("weight")]
        self.tiles([("Measurements", len(body), ""),
                    ("Latest", f"{weights[-1]:.1f} kg" if weights else "–", body[-1]["date"] if body else ""),
                    ("Min", f"{min(weights):.1f} kg" if weights else "–", ""),
                    ("Max", f"{max(weights):.1f} kg" if weights else "–", "")])
        pts = [Point(parse_date(r["date"]), r["weight"], f"<b>{r['weight']:.1f} kg</b><br>{parse_date(r['date']):%d.%m.%Y}",
                     r["id"]) for r in body if r.get("weight")]
        self.add(timeline([("Body weight", schema.KINDS["body_metrics"].color, pts)], "Body weight", "kg over time",
                          y_unit="kg", line=True, on_click=self.click("body_metrics"), min_height=380))


class ExerciseProgress(QWidget):
    """Progress of one training method: best load / weight / volume per session (V1 Set/Reps chart)."""

    METRICS = {
        "Best extra weight (kg)": lambda sets: max((s.get("weight") or 0) for s in sets),
        "Best load (reps or seconds)": lambda sets: max((s.get("load") or 0) for s in sets),
        "Total load (sum of sets)": lambda sets: sum((s.get("load") or 0) for s in sets),
        "Number of sets": lambda sets: len(sets),
    }

    def __init__(self, db, sessions, on_click):
        super().__init__()
        self.sessions, self.on_click = sessions, on_click
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Exercise progress:"))
        self.method_combo = ComboBox()
        counts = Counter()
        for r in sessions:
            for d in r.get("details") or []:
                if d.get("method") and d.get("sets"):
                    counts[d["method"]] += 1
        for m, c in counts.most_common():
            self.method_combo.addItem(f"{m}  ({c}×)", m)
        self.metric_combo = ComboBox()
        self.metric_combo.addItems(list(self.METRICS))
        bar.addWidget(self.method_combo, 1)
        bar.addWidget(self.metric_combo)
        layout.addLayout(bar)
        self.holder = QVBoxLayout()
        layout.addLayout(self.holder)
        self.method_combo.currentIndexChanged.connect(self.draw)
        self.metric_combo.currentIndexChanged.connect(self.draw)
        self.draw()

    def draw(self):
        while self.holder.count():
            w = self.holder.takeAt(0).widget()
            if w:
                w.deleteLater()
        method = self.method_combo.currentData()
        metric = self.metric_combo.currentText()
        fn = self.METRICS[metric]
        by_hold = defaultdict(list)
        for r in self.sessions:
            for d in r.get("details") or []:
                if d.get("method") == method and d.get("sets"):
                    hold = d.get("hold") or "—"
                    v = fn(d["sets"])
                    if not v:
                        continue
                    sets_txt = ", ".join(f"{s.get('load') or 0}{'+' + str(s.get('weight')) + 'kg' if s.get('weight') else ''}"
                                         for s in d["sets"])
                    by_hold[hold].append(Point(parse_date(r["date"]), v,
                                               f"<b>{esc(method)}</b> · {esc(hold)}<br>{parse_date(r['date']):%d.%m.%Y}<br>"
                                               f"{metric}: {v:g}<br>Sets: {esc(sets_txt)}", r["id"]))
        holds = sorted(by_hold, key=lambda h: -len(by_hold[h]))
        colors = ({h: c for h, c in zip(holds, tints(schema.KINDS["training_sessions"].color, len(holds)))} if len(holds) <= 8 else slot_colors(holds))
        card = timeline([(h, colors[h], by_hold[h]) for h in holds], method or "No exercises with sets recorded",
                        f"{metric} per session, one line per device/hold", line=True, on_click=self.on_click,
                        min_height=340)
        self.holder.addWidget(card)


__all__ = ["StatsView", "date", "Qt"]
