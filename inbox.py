"""Import the entries written by the phone app (pwa/) from the synced inbox folder.

The phone uploads one file per entry to a Google Drive folder that Google Drive for Desktop mirrors to this
computer. Each file looks like::

    {"format": "climbapp-entry", "version": 1, "kind": "sport_routes", "record": {"id": "...", "date": ..., ...}}

* an entry whose id already exists is skipped, so importing twice (or re-uploading from the phone) is harmless
* imported files move to ``imported/``, files that cannot be used to ``rejected/`` (with the reason in the log)
* only the fields of the kind are taken over, converted to the type the form would produce
"""
import json
import shutil
from pathlib import Path

import schema
from database import parse_date

FORMAT = "climbapp-entry"
SOURCE = "mobile"


# ------------------------------------------------------------------ cleaning
def _clean_value(f, value):
    """Coerce a value from the phone to what the desktop form stores for this field; None if unusable."""
    t = f.type
    if t == "date":
        try:
            return parse_date(value).isoformat() if value else None
        except ValueError:
            return None
    if t in ("int", "rating"):
        try:
            n = int(round(float(value or 0)))
        except (TypeError, ValueError):
            return None
        return min(5, max(0, n)) if t == "rating" else max(0, n)
    if t == "float":
        try:
            return round(float(value or 0), f.decimals)
        except (TypeError, ValueError):
            return None
    if t == "bool":
        return bool(value)
    if t == "time":
        h, _, m = str(value or "00:00").partition(":")
        return f"{int(h or 0):02d}:{int(m or 0):02d}" if h.isdigit() and (m.isdigit() or not m) else "00:00"
    if t == "gps":
        try:
            return {"lat": float(value["lat"]), "lon": float(value["lon"])}
        except (TypeError, KeyError, ValueError):
            return None
    if t == "multichoice":
        return [str(v).strip() for v in value or [] if str(v).strip()] if isinstance(value, list) else []
    if t == "list":
        items = value if isinstance(value, list) else []
        return [_clean_record(f.sub, item) for item in items if isinstance(item, dict)]
    return str(value or "").strip()


def _clean_record(fields, raw: dict) -> dict:
    out = {}
    for f in fields:
        if f.key in raw:
            value = _clean_value(f, raw[f.key])
            if value is not None:
                out[f.key] = value
    return out


def clean_entry(payload: dict) -> tuple[str, dict]:
    """Validated (kind, record) of an inbox file; ValueError says why it cannot be used."""
    if not isinstance(payload, dict) or payload.get("format") != FORMAT:
        raise ValueError("not a ClimbApp entry file")
    kind = payload.get("kind")
    if kind not in schema.KINDS:
        raise ValueError(f"unknown kind {kind!r}")
    raw = payload.get("record")
    entry_id = raw.get("id") if isinstance(raw, dict) else None
    if not isinstance(entry_id, str) or not entry_id.strip():
        raise ValueError("entry without id")
    record = _clean_record(schema.KINDS[kind].fields, raw)
    missing = [f.label for f in schema.KINDS[kind].fields if f.required and not record.get(f.key)]
    if missing:
        raise ValueError("missing " + ", ".join(missing))
    return kind, {"id": entry_id.strip(), **record, "source": SOURCE}


# -------------------------------------------------------------------- import
def _move(path: Path, folder: str) -> bool:
    target = path.parent / folder
    try:
        target.mkdir(exist_ok=True)
        shutil.move(str(path), str(target / path.name))
        return True
    except OSError:                       # still being synced / locked: try again at the next scan
        return False


def import_inbox(db, folder: Path) -> tuple[list[tuple[str, str]], list[str]]:
    """Import every new entry file in ``folder``. Returns ([(kind, id) added], [problem texts])."""
    added: list[tuple[str, str]] = []
    problems: list[str] = []
    if not folder.is_dir():
        return added, problems
    known = {(k, r.get("id")) for k, r in db.all_entries()}
    for path in sorted(folder.glob("*.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                kind, record = clean_entry(json.load(fh))
        except (OSError, ValueError) as e:        # json errors are ValueErrors; a half-synced file may fail once
            problems.append(f"{path.name}: {e}")
            if isinstance(e, ValueError) and not isinstance(e, json.JSONDecodeError):
                _move(path, "rejected")
            continue
        if (kind, record["id"]) not in known:
            db.add(kind, record, save=False)
            known.add((kind, record["id"]))
            added.append((kind, record["id"]))
        _move(path, "imported")
    if added:
        db.save()
    return added, problems
