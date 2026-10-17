"""Import the data file of ClimbApp V1 (C#, *.clmb) into the V2 database layout.

Parsing is done by ``clmb_format.parse_clmb`` (verified to read the real file to EOF);
this module maps every V1 field onto the V2 schema (see schema.py).

V1 quirks handled here:
  * the hour of an activity date is the 'session' (order within the day), not a time
  * durations (Kletterzeit, Bergtour Zeit) are DateTimes whose time of day is the duration
  * difficulties are indices: shared UIAA/French rock index, WI and M indices
  * "no date" is 01.01.0001; enum value "_null" means empty
"""
from datetime import datetime

from clmb_format import parse_clmb
from database import new_id
import grades

NO_DATE_YEAR = 1


def _d(dt: datetime | None) -> str | None:
    if dt is None or dt.year <= NO_DATE_YEAR:
        return None
    return dt.date().isoformat()


def _until(start: datetime, end: datetime | None) -> str | None:
    """date_to only for real multi-day entries."""
    e = _d(end)
    return e if e and e > _d(start) else None


def _enum(value: str) -> str:
    return "" if value in ("_null", None) else value


def _duration(dt: datetime) -> str:
    return "" if dt.hour == 0 and dt.minute == 0 else f"{dt.hour:02d}:{dt.minute:02d}"


def _time(dt: datetime) -> str:
    return f"{dt.hour:02d}:{dt.minute:02d}"


def _rock(index: int, scale: str) -> str:
    if index < 0:
        return ""
    return (grades.french(index) if scale == "French" else grades.uiaa(index)) or \
        grades.french(index) or grades.uiaa(index)


def convert(v1: dict) -> dict:
    """Return {'entries': {kind: [...]}, 'training': {...}} from parsed V1 data."""
    e: dict[str, list] = {k: [] for k in ("climbing_days", "sport_routes", "alpine_climbs", "mountain_tours",
                                          "trips", "training_sessions", "competitions", "body_metrics", "notes")}

    for k in v1["koerperinfos"]:
        e["body_metrics"].append({"id": new_id(), "date": _d(k["datum"]), "weight": round(k["gewicht"], 1),
                                  "info": ""})

    for u in v1["trainingseinheiten"]:
        details = []
        for s in u["sets"]:
            details.append({
                "discipline": _enum(s["methode_disziplin"]),
                "method": s["methode_name"],
                "hold": s["geraet_griff"],
                "duration": s["zeit"],
                "distance": s["strecke"],
                "rest": s["pause"],
                "repetitions": s["wiederholungen_effektiv"],
                "mode": _enum(s["belastungsart"]),
                "info": s["info"],
                "sets": [{"load": r["belastung"], "weight": float(r["gewicht"]), "side": _enum(r["seite"])}
                         for r in s["reps"]],
            })
        e["training_sessions"].append({"id": new_id(), "date": _d(u["datum"]), "session": u["session"],
                                       "place": u["ort"], "gym": "", "phase": _enum(u["trainingsphase"]), "info": u["info"],
                                       "details": details})

    for w in v1["wettkaempfe"]:
        e["competitions"].append({"id": new_id(), "date": _d(w["datum"]), "date_to": _until(w["datum"], w["datum_bis"]),
                                  "session": w["session"], "gym": w["kletterhalle"], "level": _enum(w["ebene"]),
                                  "discipline": _enum(w["disziplin"]), "result": w["ergebnis"], "info": w["info"]})

    for k in v1["klettertage"]:
        e["climbing_days"].append({"id": new_id(), "date": _d(k["datum"]), "session": k["session"],
                                   "discipline": _enum(k["disziplin"]), "area": k["klettergebiet"],
                                   "crag": k["klettergarten"], "sector": k["sektor"], "partner": k["partner"],
                                   "info": k["info"]})

    for t in v1["sportklettertouren"]:
        g = t["schwierigkeit"]
        e["sport_routes"].append({"id": new_id(), "date": _d(t["datum"]), "discipline": _enum(t["art"]),
                                  "name": t["name"], "grade": _rock(g["ind_fels"], "French"),
                                  "attempts": t["versuche"], "area": t["klettergebiet"], "crag": t["klettergarten"],
                                  "sector": t["sektor"], "first_ascent": t["first_ascent"],
                                  "rating": max(0, t["bewertung"]), "info": t["info"]})

    for t in v1["alpinklettertouren"]:
        g = t["schwierigkeit"]
        art = _enum(t["art"])
        e["alpine_climbs"].append({
            "id": new_id(), "date": _d(t["datum"]), "date_to": _until(t["datum"], t["datum_bis"]),
            "session": t["session"], "type": art, "name": t["name"], "range": t["bergmassiv"],
            "mountain": t["berg_wand"],
            # V1 shows multi-pitch sport routes in French, everything else alpine in UIAA
            "grade": _rock(g["ind_fels"], "French" if art == "Mehrseillängen" else "UIAA"),
            "grade_wi": g["wi"], "grade_m": g["m"], "style": _enum(t["stil"]), "meters": t["klettermeter"],
            "pitches": t["seillaengen"], "orientation": t["ausrichtung"], "climbing_time": _duration(t["kletterzeit"]),
            "partner": t["partner"], "first_ascent": t["first_ascent"], "rating": max(0, t["bewertung"]),
            "info": t["info"],
        })

    for t in v1["bergtouren"]:
        e["mountain_tours"].append({
            "id": new_id(), "date": _d(t["datum"]), "date_to": _until(t["datum"], t["datum_bis"]),
            "session": t["session"], "type": _enum(t["art"]), "name": t["name_tour"], "mountain": t["name_tour"],
            "range": t["gebirgsgruppe"],
            "start": t["ausgangsort"], "elevation_gain": t["hoehenmeter"], "elevation": t["hoehe"],
            "duration": _duration(t["zeit"]), "partner": t["partner"], "info": t["info"],
        })

    for t in v1["reisen"]:
        e["trips"].append({"id": new_id(), "date": _d(t["datum_von"]), "date_to": _until(t["datum_von"], t["datum_bis"]),
                           "destination": t["name"], "type": _enum(t["art"]), "partner": t["partner"],
                           "info": t["info"]})

    for n in v1["tagesnotizen"]:
        e["notes"].append({"id": new_id(), "date": _d(n["datum"]), "date_to": _until(n["datum"], n["datum_bis"]),
                           "text": n["info"]})

    for kind in e:
        e[kind] = [r for r in e[kind] if r.get("date")]
        e[kind].sort(key=lambda r: (r["date"], r.get("session", 0)))

    methods = [{"discipline": _enum(m["disziplin"]), "name": m["name"], "description": m["beschreibung"],
                "holds": [h for h in m["geraete_griffe"] if h]} for m in v1["trainingsmethoden_derived"]]
    return {"entries": e, "training": {"methods": methods}}


def import_v1_file(path: str) -> dict:
    from migrate import normalize_partners, split_cycling
    data = convert(parse_clmb(path))
    data["entries"].setdefault("paragliding", [])
    split_cycling(data)
    normalize_partners(data)
    return data


def _fingerprint(kind: str, r: dict) -> tuple:
    keys = {"climbing_days": ("area", "crag"), "sport_routes": ("name",), "alpine_climbs": ("name",),
            "mountain_tours": ("name",), "trips": ("destination",), "training_sessions": ("place",),
            "competitions": ("gym", "discipline"), "cycling": ("distance",), "paragliding": ("site",), "body_metrics": ("weight",), "notes": ("text",)}
    return (r.get("date"),) + tuple(str(r.get(k, "")).strip().lower() for k in keys.get(kind, ()))


def merge_into(db, data: dict) -> int:
    """Add imported entries that are not already present (same date + key fields). Returns count added."""
    added = 0
    for kind, records in data["entries"].items():
        existing = {_fingerprint(kind, r) for r in db.entries(kind)}
        for r in records:
            fp = _fingerprint(kind, r)
            if fp not in existing:
                db.entries(kind).append(r)
                existing.add(fp)
                added += 1
    names = {(m.get("discipline"), m.get("name")) for m in db.methods}
    for m in data["training"]["methods"]:
        if (m["discipline"], m["name"]) not in names:
            db.methods.append(m)
    return added
