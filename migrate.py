"""One-time data migrations, keyed by database version (see Database.load)."""
import json
from pathlib import Path

from database import new_id

CYCLING_METHOD = "Radfahren"

# Personal data of the one-time migrations (partner names and nicknames, home gyms) lives in migrate_private.json
# next to this file; it is not part of the repository. Without it those migrations leave the names alone.
PRIVATE_FILE = Path(__file__).resolve().parent / "migrate_private.json"


def _load_private() -> dict:
    try:
        with open(PRIVATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


_PRIVATE = _load_private()
# "partner_aliases": {"Full Name": "Nickname"}, both spellings used in the old app; the short one is canonical
PARTNER_ALIASES: dict[str, str] = _PRIVATE.get("partner_aliases", {})
# "partner_rules": [{"kind": ..., "before": "YYYY-MM-DD", "if_all": [names], "replace": {old: new}}], applied in order;
# a rule applies when its kind / date limit / names (all optional) match the record
PARTNER_RULES: list[dict] = _PRIVATE.get("partner_rules", [])
# "training_where": {old value: [place, gym, country, region]}
TRAINING_WHERE: dict[str, tuple] = {k: tuple(v) for k, v in _PRIVATE.get("training_where", {}).items()}
# "default_where": [country, region] the old bulk import put on every training session (replaced when TRAINING_WHERE knows better)
DEFAULT_WHERE: tuple = tuple(_PRIVATE.get("default_where", ("", "")))


def cycling_type(date_iso: str) -> str:
    """Rides up to 2023 were on the indoor trainer, later ones on the road bike."""
    return "Rennrad" if date_iso >= "2024-01-01" else "Indoor"


def split_cycling(data: dict) -> int:
    """Move 'Fitness / Radfahren' sets out of training sessions into the 'cycling' category.

    A training session that only contained cycling sets is removed (its info moves to the
    cycling entry); sessions with other exercises just lose the cycling set.
    Returns the number of cycling entries created.
    """
    entries = data["entries"]
    created, kept = [], []
    for session in entries.get("training_sessions", []):
        details = session.get("details") or []
        bikes = [d for d in details if d.get("discipline") == "Fitness" and d.get("method") == CYCLING_METHOD]
        if not bikes:
            kept.append(session)
            continue
        for d in bikes:
            notes = [t.strip() for t in (d.get("info"), session.get("info")) if t and t.strip()]
            info = "\n".join(dict.fromkeys(notes))     # de-duplicate identical set/session notes
            km = round((d.get("distance") or 0) / 1000, 1)
            created.append({"id": new_id(), "date": session["date"], "date_to": None, "name": "",
                            "type": cycling_type(session["date"]),
                            "duration": d.get("duration") or 0, "distance": km, "elevation_gain": 0,
                            "partner": "", "info": info})
        rest = [d for d in details if d not in bikes]
        if rest:
            session["details"] = rest
            kept.append(session)
    entries["training_sessions"] = kept
    entries.setdefault("cycling", []).extend(created)
    entries["cycling"].sort(key=lambda r: r["date"])
    methods = data["training"]["methods"]
    data["training"]["methods"] = [m for m in methods if not (m.get("discipline") == "Fitness"
                                                              and m.get("name") == CYCLING_METHOD)]
    return len(created)


def strip_attachments(data: dict) -> None:
    for records in data["entries"].values():
        for r in records:
            r.pop("attachments", None)


def normalize_partners(data: dict) -> int:
    """Replace aliased partner names (comma separated lists) and drop duplicates. Returns changed records."""
    changed = 0
    for kind, records in data["entries"].items():
        for r in records:
            text = r.get("partner")
            if not text or not isinstance(text, str):
                continue
            names = [n.strip() for n in text.split(",") if n.strip()]
            for rule in PARTNER_RULES:
                if rule.get("kind", kind) == kind and r.get("date", "") < rule.get("before", "9999")                         and all(n in names for n in rule.get("if_all", [])):
                    names = [rule["replace"].get(n, n) for n in names]
            names = [PARTNER_ALIASES.get(n, n) for n in names]
            new = ", ".join(dict.fromkeys(names))
            if new != text:
                r["partner"] = new
                changed += 1
    return changed


def unify_mountain_fields(data: dict) -> None:
    """Alpine climbs: massif -> range, wall -> mountain. Tours: mountain defaults to the tour/summit name."""
    for r in data["entries"].get("alpine_climbs", []):
        if "massif" in r:
            r["range"] = r.pop("massif")
        if "wall" in r:
            r["mountain"] = r.pop("wall")
    for r in data["entries"].get("mountain_tours", []):
        r.setdefault("mountain", r.get("name", ""))


def drop_route_logs_and_entry_maneuvers(data: dict) -> None:
    """v5: waypoints / route logs are gone; paragliding maneuvers live on the flights only."""
    for r in data["entries"].get("alpine_climbs", []):
        r.pop("route", None)
    for r in data["entries"].get("mountain_tours", []):
        r.pop("waypoints", None)
    for r in data["entries"].get("paragliding", []):
        moves = r.pop("maneuvers", None) or []
        flights = r.get("flights") or []
        if moves and flights:                      # keep what was logged: attach to every flight
            for f in flights:
                f["maneuvers"] = list(dict.fromkeys((f.get("maneuvers") or []) + moves))


def drop_seasons(data: dict) -> None:
    """v6: training seasons and goals were removed."""
    data["training"].pop("seasons", None)


# training sessions used to have one 'gym' field holding the place: split into place + gym (+ real location);
# the mapping old value -> (place, gym, country, region) is TRAINING_WHERE above


def split_training_place(data: dict) -> int:
    changed = 0
    for r in data["entries"].get("training_sessions", []):
        if "place" in r:
            continue
        old = r.pop("gym", "") or ""
        place, gym, country, region = TRAINING_WHERE.get(old, (old, "", None, None))
        r["place"], r["gym"] = place, gym
        if country and (r.get("country"), r.get("region")) in ((None, None), ("", ""), DEFAULT_WHERE):
            r["country"], r["region"] = country, region      # the bulk default was wrong for these places
        changed += 1
    return changed


def migrate(data: dict) -> bool:
    """Bring loaded data up to the current version. Returns True if anything changed."""
    version = data.get("version", 2)
    if version >= 11:
        return False
    if version < 3:
        split_cycling(data)
        strip_attachments(data)
        data["entries"].setdefault("paragliding", [])
    if version < 4:
        for r in data["entries"].get("cycling", []):      # rides up to 2023 indoor, from 2024 road bike
            r["type"] = cycling_type(r["date"])
        unify_mountain_fields(data)
        normalize_partners(data)
    if version < 5:
        drop_route_logs_and_entry_maneuvers(data)
    if version < 6:
        drop_seasons(data)
    if version in (6, 7, 8, 9):
        normalize_partners(data)           # aliases and rules from migrate_private.json
    if version < 11:
        split_training_place(data)
    data["version"] = 11
    return True
