"""Definition of every kind of entry: fields, table columns, calendar text and colour.

Everything else (forms, tables, detail panel, calendar, statistics) is driven by
these definitions, so adding a field here makes it appear everywhere.
"""
from dataclasses import dataclass, field as dc_field
from datetime import date, timedelta
from typing import Callable

import grades
from database import parse_date
from fields import Field, format_value
from theme import KIND_COLORS


# --------------------------------------------------------------- suggestions
def s(kind: str, key: str):
    return lambda db: db.distinct(kind, key)


def s_multi(*pairs):
    """Suggestions merged from several (kind, key) pairs, e.g. crags from days and routes."""
    def fn(db):
        out = []
        for kind, key in pairs:
            out += [v for v in db.distinct(kind, key) if v not in out]
        return out
    return fn


def s_partners(db):
    out = []
    for kind in ("climbing_days", "alpine_climbs", "mountain_tours", "trips", "training_sessions"):
        out += [v for v in db.distinct(kind, "partner", split_partners=True) if v not in out]
    return out


def s_methods(db):
    """Methods of the catalogue plus every method already used in a session."""
    names = {m.get("name", "") for m in db.methods if m.get("name")}
    names.update(db.distinct_nested("training_sessions", "details", "method"))
    return sorted(names)


def s_holds(db):
    holds = set()
    for m in db.methods:
        holds.update(m.get("holds") or [])
    holds.update(v for v in db.distinct_nested("training_sessions", "details", "hold"))
    return sorted(h for h in holds if h)


LOCATION_KINDS = ["climbing_days", "sport_routes", "alpine_climbs", "mountain_tours", "training_sessions",
                  "cycling", "paragliding", "trips", "competitions"]
COUNTRY = s_multi(*[(k, "country") for k in LOCATION_KINDS])
REGION = s_multi(*[(k, "region") for k in LOCATION_KINDS])
# alpine climbs, mountain tours and paragliding share the same mountain range / mountain fields
RANGE = s_multi(("alpine_climbs", "range"), ("mountain_tours", "range"), ("paragliding", "range"))
MOUNTAIN = s_multi(("alpine_climbs", "mountain"), ("mountain_tours", "mountain"), ("mountain_tours", "name"),
                   ("paragliding", "mountain"))

def s_maneuvers(db):
    """Maneuvers you have logged before (nothing is pre-defined)."""
    counts: dict[str, int] = {}
    for r in db.entries("paragliding"):
        for f in r.get("flights") or []:
            for m in f.get("maneuvers") or []:
                counts[m] = counts.get(m, 0) + 1
    return sorted(counts, key=lambda m: (-counts[m], m.lower()))


AREA = s_multi(("climbing_days", "area"), ("sport_routes", "area"))
CRAG = s_multi(("climbing_days", "crag"), ("sport_routes", "crag"))
SECTOR = s_multi(("climbing_days", "sector"), ("sport_routes", "sector"))

METER_STEP = 50       # spin boxes for heights / climbing metres move in steps of 50 m

# ---------------------------------------------------------------- kind spec
@dataclass
class Kind:
    key: str
    label: str
    plural: str
    fields: list[Field]
    columns: list[str]
    tile: Callable[[dict], list[str]]
    subtype: str | None = None          # field that splits the kind into sub types
    multi_day: bool = False
    icon: str = ""
    sort_key: str = "date"

    @property
    def color(self) -> str:
        return KIND_COLORS[self.key]

    def field(self, key: str) -> Field | None:
        return next((f for f in self.fields if f.key == key), None)

    def title(self, record: dict) -> str:
        lines = self.tile(record)
        return " · ".join(l for l in lines[:2] if l) or self.label


def _j(*parts, sep=" · "):
    return sep.join(str(p) for p in parts if p not in (None, "", 0))


def _mins(minutes) -> str:
    if not minutes:
        return ""
    return f"{minutes // 60}:{minutes % 60:02d} h" if minutes >= 60 else f"{minutes} min"


def _hm(record):
    gain, top = record.get("elevation_gain"), record.get("elevation")
    if gain and top:
        return f"{gain} Hm ({top} m)"
    if gain:
        return f"{gain} Hm"
    return f"{top} m" if top else ""


def _training_tile(r):
    disciplines = []
    for d in r.get("details") or []:
        disc = d.get("discipline")
        if disc and disc not in disciplines:
            disciplines.append(disc)
    return [training_where(r) or "Training", r.get("phase", ""), ", ".join(disciplines)]


def training_where(r: dict) -> str:
    """'City · Gym': place and gym of a training session."""
    return " · ".join(x for x in (r.get("place"), r.get("gym")) if x)


def _alpine_tile(r):
    return [r.get("name") or "Alpine climb", _j(r.get("range"), r.get("mountain")),
            _j(grades.alpine_display(r), f"{r['meters']} m" if r.get("meters") else "")]


KINDS: dict[str, Kind] = {}


def _add(kind: Kind):
    KINDS[kind.key] = kind


_add(Kind(
    "climbing_days", "Climbing day", "Climbing days", icon="Gesamt.png", subtype="discipline",
    fields=[
        Field("date", "Date", "date", required=True),
        Field("discipline", "Discipline", "choice", choices=["Sportklettern", "Boulder", "Trad"]),
        Field("area", "Climbing area", "choice", suggest=AREA, required=True),
        Field("crag", "Crag", "choice", suggest=CRAG),
        Field("sector", "Sector", "choice", suggest=SECTOR),
        Field("partner", "Partner", "partners", suggest=s_partners),
        Field("info", "Notes", "multiline"),
    ],
    columns=["date", "discipline", "area", "crag", "sector", "partner", "info"],
    tile=lambda r: [r.get("area") or "Climbing", r.get("crag", ""), r.get("sector", "")],
))

_add(Kind(
    "sport_routes", "Route (tick list)", "Tick list", icon="Sportkletterroute.png", subtype="discipline",
    fields=[
        Field("date", "Date", "date", required=True),
        Field("discipline", "Discipline", "choice", choices=["Sportklettern", "Trad", "Boulder"]),
        Field("name", "Route name", required=True,
              suggest=s("sport_routes", "name")),
        Field("grade", "Grade", "choice", choices=grades.ROCK_CHOICES),
        Field("attempts", "Ascent style", "choice", choices=grades.ATTEMPTS),
        Field("area", "Climbing area", "choice", suggest=AREA),
        Field("crag", "Crag", "choice", suggest=CRAG),
        Field("sector", "Sector", "choice", suggest=SECTOR),
        Field("first_ascent", "First ascent", "bool"),
        Field("rating", "Rating", "rating"),
        Field("info", "Notes", "multiline"),
    ],
    columns=["date", "name", "grade", "attempts", "discipline", "area", "crag", "sector", "rating"],
    tile=lambda r: [_j(r.get("name"), r.get("grade")), r.get("attempts", ""), r.get("crag", "")],
))

_add(Kind(
    "alpine_climbs", "Alpine climb", "Alpine climbs", icon="Alpintouren.png", subtype="type", multi_day=True,
    fields=[
        Field("date", "Date", "date", required=True),
        Field("date_to", "Until", "date"),
        Field("range", "Mountain range", "choice", suggest=RANGE),
        Field("mountain", "Mountain", "choice", suggest=MOUNTAIN),
        Field("name", "Route name", required=True, suggest=s("alpine_climbs", "name")),
        Field("type", "Type", "choice", choices=["Alpinklettertour", "Mehrseillängen", "Eisklettern", "Kombiniert"]),
        Field("grade", "Grade (rock)", "choice", choices=grades.ROCK_CHOICES),
        Field("grade_wi", "Grade (ice)", "choice", choices=grades.WI),
        Field("grade_m", "Grade (mixed)", "choice", choices=grades.M),
        Field("style", "Style", "choice", choices=["onsight", "rotpunkt", "A0", "A1", "A2", "A3", "A4"]),
        Field("orientation", "Orientation", "choice", choices=["N", "NO", "O", "SO", "S", "SW", "W", "NW"]),
        Field("meters", "Climbing meters", "int", suffix="m", step=METER_STEP),
        Field("pitches", "Pitches", "int", maximum=200),
        Field("climbing_time", "Climbing time", "time"),
        Field("rating", "Rating", "rating"),
        Field("first_ascent", "First ascent", "bool"),
        Field("partner", "Partner", "partners", suggest=s_partners),
        Field("info", "Notes", "multiline"),
    ],
    columns=["date", "name", "type", "range", "mountain", "grade", "grade_wi", "grade_m", "meters", "pitches",
             "style", "partner", "rating"],
    tile=_alpine_tile,
))

_add(Kind(
    "mountain_tours", "Mountain tour", "Mountain tours", icon="Bergtouren.png", subtype="type", multi_day=True,
    fields=[
        Field("date", "Date", "date", required=True),
        Field("date_to", "Until", "date"),
        Field("range", "Mountain range", "choice", suggest=RANGE),
        Field("mountain", "Mountain", "choice", suggest=MOUNTAIN),
        Field("name", "Tour / summit", required=True, suggest=s("mountain_tours", "name")),
        Field("type", "Type", "choice", choices=["Wanderung", "Hochtour", "Skitour"]),
        Field("start", "Trailhead", "choice", suggest=s("mountain_tours", "start")),
        Field("elevation_gain", "Elevation gain", "int", suffix="Hm", step=METER_STEP),
        Field("elevation", "Summit elevation", "int", suffix="m", maximum=9000, step=METER_STEP),
        Field("duration", "Duration", "time"),
        Field("partner", "Partner", "partners", suggest=s_partners),
        Field("info", "Notes", "multiline"),
    ],
    columns=["date", "name", "type", "range", "mountain", "start", "elevation_gain", "elevation", "duration", "partner"],
    tile=lambda r: [r.get("range") or r.get("type") or "Tour", r.get("name") or r.get("mountain", ""), _hm(r)],
))

_add(Kind(
    "trips", "Trip", "Trips", icon="Reisen.png", subtype="type", multi_day=True,
    fields=[
        Field("date", "From", "date", required=True),
        Field("date_to", "Until", "date"),
        Field("destination", "Destination", required=True, suggest=s("trips", "destination")),
        Field("type", "Type", "choice", choices=["Mehrtagesausflug", "Kletterreise", "Expedition"]),
        Field("partner", "Partner", "partners", suggest=s_partners),
        Field("info", "Notes", "multiline"),
    ],
    columns=["date", "date_to", "destination", "type", "partner", "info"],
    tile=lambda r: [r.get("destination") or "Trip", r.get("type", "")],
))

_add(Kind(
    "training_sessions", "Training", "Training", icon="Training.png", subtype="phase",
    fields=[
        Field("date", "Date", "date", required=True),
        Field("place", "Place", "choice", suggest=s("training_sessions", "place"), required=True),
        Field("gym", "Gym", "choice", suggest=s("training_sessions", "gym")),
        Field("phase", "Training phase", "choice",
              choices=["Basis", "Aufbau", "Maximalkraft", "Schnellkraft", "Kraftausdauer", "Ausdauer", "Ausgleich"]),
        Field("partner", "Partner", "partners", suggest=s_partners),
        Field("info", "Notes", "multiline"),
        Field("details", "Exercises", "list", item_label="Exercise", tab="Exercises",
              columns=["discipline", "method", "hold", "duration", "repetitions", "sets"], sub=[
                  Field("discipline", "Discipline", "choice", choices=["Boulder", "Lead", "Kraft", "Fitness", "Dehnen"]),
                  Field("method", "Method", "choice", suggest=s_methods),
                  Field("hold", "Device / hold", "choice", suggest=s_holds),
                  Field("duration", "Duration", "int", suffix="min", maximum=10000),
                  Field("distance", "Distance / height", "int", suffix="m", maximum=1000000),
                  Field("rest", "Rest", "int", suffix="s", maximum=100000),
                  Field("repetitions", "Repetitions", "int"),
                  Field("mode", "Sets measured in", "choice", choices=["Wiederholung", "Zeit"]),
                  Field("info", "Info", "multiline"),
                  Field("sets", "Sets", "list", item_label="Set", columns=["load", "weight", "side"], sub=[
                      Field("load", "Reps or seconds", "int", maximum=100000),
                      Field("weight", "Extra weight", "float", suffix="kg", maximum=500, minimum=-500),
                      Field("side", "Side", "choice", choices=["Beidarmig", "Links", "Rechts"]),
                  ]),
              ]),
    ],
    columns=["date", "place", "gym", "phase", "partner", "details", "info"],
    tile=_training_tile,
))

_add(Kind(
    "cycling", "Cycling", "Cycling", subtype="type", multi_day=True,
    fields=[
        Field("date", "Date", "date", required=True),
        Field("date_to", "Until", "date"),
        Field("name", "Route / tour", "choice", suggest=s("cycling", "name")),
        Field("type", "Bike", "choice", choices=["Rennrad", "Mountainbike", "Gravel", "E-Bike", "Indoor"]),
        Field("duration", "Duration", "int", suffix="min", maximum=100000),
        Field("distance", "Distance", "float", suffix="km", maximum=10000),
        Field("elevation_gain", "Elevation gain", "int", suffix="Hm", maximum=100000, step=METER_STEP),
        Field("partner", "Partner", "partners", suggest=s_partners),
        Field("info", "Notes", "multiline"),
    ],
    columns=["date", "name", "type", "distance", "duration", "elevation_gain", "partner", "info"],
    tile=lambda r: [r.get("name") or r.get("type") or "Cycling",
                    _j(f"{r['distance']:g} km" if r.get("distance") else "",
                       f"{r['elevation_gain']} Hm" if r.get("elevation_gain") else ""),
                    _mins(r.get("duration"))],
))

_add(Kind(
    "paragliding", "Paragliding", "Paragliding", subtype="type", multi_day=True,
    fields=[
        Field("date", "Date", "date", required=True),
        Field("date_to", "Until", "date"),
        Field("type", "Type", "choice", choices=["Training", "Hike & Fly", "Cross Country"]),
        Field("range", "Mountain range", "choice", suggest=RANGE),
        Field("mountain", "Mountain", "choice", suggest=MOUNTAIN),
        Field("site", "Launch site", "choice", suggest=s("paragliding", "site")),
        Field("landing", "Landing site", "choice", suggest=s("paragliding", "landing")),
        Field("glider", "Wing", "choice", suggest=s("paragliding", "glider")),
        Field("harness", "Harness", "choice", suggest=s("paragliding", "harness")),
        Field("partner", "Partner", "partners", suggest=s_partners),
        Field("info", "Notes", "multiline"),
        Field("flights", "Flights", "list", item_label="Flight", tab="Flights",
              columns=["airtime", "distance", "max_altitude", "altitude_gain", "maneuvers"], sub=[
                  Field("airtime", "Airtime", "int", suffix="min", maximum=100000),
                  Field("distance", "Distance", "float", suffix="km", maximum=1000),
                  Field("max_altitude", "Max. altitude", "int", suffix="m", maximum=9000, step=METER_STEP),
                  Field("altitude_gain", "Elevation gain", "int", suffix="m", maximum=9000, step=METER_STEP),
                  Field("maneuvers", "Maneuvers", "multichoice", suggest=s_maneuvers),
                  Field("info", "Info", "multiline"),
              ]),
    ],
    columns=["date", "type", "mountain", "site", "landing", "flights", "glider", "harness", "partner"],
    tile=lambda r: [r.get("site") or r.get("mountain") or "Paragliding", r.get("type", ""),
                    _j(_flights_text(r), _mins(para_totals(r)["airtime"]))],
))

_add(Kind(
    "competitions", "Competition", "Competitions", icon="Wettkampf.png", subtype="discipline", multi_day=True,
    fields=[
        Field("date", "Date", "date", required=True),
        Field("date_to", "Until", "date"),
        Field("gym", "Venue", "choice", suggest=s("competitions", "gym"), required=True),
        Field("level", "Level", "choice",
              choices=["Juniorcup", "ItaMeisterschaften", "Italiencup", "JustForFun"]),
        Field("discipline", "Discipline", "choice", choices=["Boulder", "Seilklettern", "Speed", "Combined"]),
        Field("result", "Result (rank)", "int", maximum=1000),
        Field("info", "Notes", "multiline"),
    ],
    columns=["date", "gym", "level", "discipline", "result", "info"],
    tile=lambda r: [r.get("gym") or "Competition", _j(r.get("discipline"), r.get("level")),
                    f"Rank {r['result']}" if r.get("result") else ""],
))

_add(Kind(
    "body_metrics", "Body weight", "Body", subtype=None,
    fields=[
        Field("date", "Date", "date", required=True),
        Field("weight", "Weight", "float", suffix="kg", maximum=300, required=True),
        Field("info", "Notes"),
    ],
    columns=["date", "weight", "info"],
    tile=lambda r: [f"{format_value(Field('w', '', 'float', suffix='kg'), r.get('weight'))}"],
))

_add(Kind(
    "notes", "Note", "Notes", multi_day=True,
    fields=[
        Field("date", "Date", "date", required=True),
        Field("date_to", "Until", "date"),
        Field("text", "Note", "multiline", required=True),
    ],
    columns=["date", "date_to", "text"],
    tile=lambda r: [r.get("text", "").replace("\n", " ")],
))

# ---- dependent dropdowns (see fields.RecordForm): top -> bottom
MOUNTAIN_CHAIN = ["country", "region", "range", "mountain"]
TRAINING_CHAIN = ["country", "region", "place", "gym"]
MOUNTAIN_KINDS = ["alpine_climbs", "mountain_tours", "paragliding"]
CLIMBING_CHAIN = ["country", "region", "area", "crag", "sector"]
CLIMBING_KINDS = ["climbing_days", "sport_routes"]


def cascade_for(kind: str, db):
    """(chain, pool) for the dependent dropdowns of a kind, or None."""
    if kind == "training_sessions":
        chain, group = TRAINING_CHAIN, ["training_sessions"]
    elif kind in MOUNTAIN_KINDS:
        chain, group = MOUNTAIN_CHAIN, MOUNTAIN_KINDS
    elif kind in CLIMBING_KINDS:
        chain, group = CLIMBING_CHAIN, CLIMBING_KINDS
    elif kind in LOCATION_KINDS:
        chain, group = ["country", "region"], LOCATION_KINDS
    else:
        return None

    catalog = "mountains" if kind in MOUNTAIN_KINDS else "climbing" if kind in CLIMBING_KINDS else None

    def pool(key: str):
        shared = key in ("country", "region")         # place names are shared by all kinds
        kinds = LOCATION_KINDS if shared else group
        places = db.catalog("mountains") + db.catalog("climbing") if shared or catalog is None else db.catalog(catalog)
        records = sorted((r for k in kinds for r in db.entries(k)), key=lambda r: r.get("date") or "", reverse=True)
        return records + places      # newest first (recent entries are the most probable); catalogue places last
    return chain, pool


def para_totals(record: dict) -> dict:
    """Sums over the independent flights of a paragliding entry."""
    flights = record.get("flights") or []
    return {"flights": len(flights),
            "airtime": sum(f.get("airtime") or 0 for f in flights),
            "distance": round(sum(f.get("distance") or 0 for f in flights), 1),
            "max_altitude": max((f.get("max_altitude") or 0 for f in flights), default=0),
            "altitude_gain": sum(f.get("altitude_gain") or 0 for f in flights)}


def _flights_text(record: dict) -> str:
    n = len(record.get("flights") or [])
    return f"{n} flight{'s' if n != 1 else ''}" if n else ""


def hike_fly_prefill(kind: str, record: dict) -> dict:
    """Starting values for a Hike & Fly paragliding entry created from a tour or alpine climb."""
    mountain = record.get("mountain") or (record.get("name") if kind == "mountain_tours" else "")
    return {"date": record.get("date"), "date_to": record.get("date_to"), "type": "Hike & Fly",
            "country": record.get("country", ""), "region": record.get("region", ""),
            "range": record.get("range", ""), "mountain": mountain, "partner": record.get("partner", ""),
            "source_kind": kind, "source_id": record.get("id")}


def _inject_location_fields():
    """Every dated activity (not notes / body weight) also has a country, a region and an optional GPS position."""
    for key in LOCATION_KINDS:
        spec = KINDS[key]
        idx = max(i for i, f in enumerate(spec.fields) if f.key in ("date", "date_to"))
        spec.fields[idx + 1:idx + 1] = [Field("country", "Country", "choice", suggest=COUNTRY, new_row=True),
                                        Field("region", "Region", "choice", suggest=REGION)]
        # position (shown on a map in the detail view) goes right before partner / notes
        if key != "training_sessions":          # gym sessions have no use for a position
            at = next((i for i, f in enumerate(spec.fields) if f.key in ("partner", "info")), len(spec.fields))
            spec.fields.insert(at, Field("gps", "GPS position", "gps"))
        pos = spec.columns.index("info") if "info" in spec.columns else len(spec.columns)
        spec.columns[pos:pos] = ["country", "region"]


_inject_location_fields()

# kinds offered in "Add" menus, legend and calendar (body weight is not shown as a tile)
ADDABLE = ["climbing_days", "sport_routes", "alpine_climbs", "mountain_tours", "training_sessions",
           "cycling", "paragliding", "trips", "competitions", "body_metrics", "notes"]
LEGEND_KINDS = ["climbing_days", "sport_routes", "alpine_climbs", "mountain_tours", "training_sessions",
                "cycling", "paragliding", "trips", "competitions"]
CALENDAR_KINDS = LEGEND_KINDS + ["notes"]
# order inside a day tile: the main activity first
TILE_ORDER = ["trips", "alpine_climbs", "mountain_tours", "paragliding", "climbing_days", "competitions",
              "sport_routes", "cycling", "training_sessions", "notes"]


@dataclass
class DayItem:
    kind: str
    record: dict
    color: str
    lines: list[str]
    continued: bool = False      # multi-day entry, not its first day
    span: tuple = dc_field(default_factory=tuple)


MAX_SPAN_DAYS = 120


def record_days(record: dict) -> list[date]:
    start = parse_date(record.get("date"))
    if not start:
        return []
    end = parse_date(record.get("date_to")) or start
    if end < start or (end - start).days > MAX_SPAN_DAYS:
        end = start
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def day_index(db, kinds: set[str] | None = None) -> dict[date, list[DayItem]]:
    """date -> DayItems; sport routes of a day are folded into one item."""
    index: dict[date, list[DayItem]] = {}
    route_days: dict[date, list[dict]] = {}
    for kind in CALENDAR_KINDS:
        if kinds is not None and kind not in kinds and kind != "notes":
            continue
        spec = KINDS[kind]
        for record in db.entries(kind):
            days = record_days(record)
            if kind == "sport_routes":
                if days:
                    route_days.setdefault(days[0], []).append(record)
                continue
            lines = [l for l in spec.tile(record) if l]
            for i, d in enumerate(days):
                index.setdefault(d, []).append(DayItem(kind, record, spec.color, lines or [spec.label],
                                                       continued=i > 0, span=(days[0], days[-1])))
    for d, routes in route_days.items():
        routes.sort(key=lambda r: -grades.rock_index(r.get("grade")))
        lines = [f"{len(routes)} route{'s' if len(routes) > 1 else ''}"] + \
                [_j(r.get("name"), r.get("grade"), r.get("attempts")) for r in routes]
        index.setdefault(d, []).append(DayItem("sport_routes", routes[0], KINDS["sport_routes"].color, lines))
    for items in index.values():
        items.sort(key=lambda it: TILE_ORDER.index(it.kind))
    return index


def search_text(kind: str, record: dict) -> str:
    parts = []
    for f in KINDS[kind].fields:
        v = record.get(f.key)
        if f.type == "gps":
            continue
        if isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    parts += [str(x) for x in item.values() if not isinstance(x, list)]
        elif v not in (None, ""):
            parts.append(str(v))
    return " ".join(parts).lower()
