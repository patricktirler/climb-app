"""Single-file JSON database for all climbing data.

Layout of the file::

    {
      "version": 2,
      "entries":  {"<kind>": [record, ...], ...},   # dated activities, see schema.KINDS
      "training": {"methods": [...]},
      "settings": {...}
    }

Every record is a plain dict with a unique ``id`` (uuid4) and a ``date``
(ISO ``YYYY-MM-DD``); multi-day kinds also carry ``date_to``.
Saves are atomic (write temp file + replace) and a dated backup is kept.
"""
import json
import os
import shutil
import uuid
from datetime import date, datetime
from pathlib import Path

DB_VERSION = 11
MAX_BACKUPS = 30


def new_id() -> str:
    return uuid.uuid4().hex


def parse_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def empty_data() -> dict:
    return {"version": DB_VERSION, "entries": {}, "training": {"methods": []},
            "settings": {}, "places": {}}


class Database:
    """Loads, edits and persists the single JSON database file."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data = empty_data()
        self._backup_done = False
        self.load()
        from migrate import migrate
        if self.path.exists() and migrate(self.data):
            self.save()        # backs up the old file first

    # ------------------------------------------------------------------ io
    def load(self):
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = empty_data()
        base = empty_data()
        for key, value in base.items():
            self.data.setdefault(key, value)
        for key, value in base["training"].items():
            self.data["training"].setdefault(key, value)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self._backup_done:
            self._backup()
            self._backup_done = True
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    def _backup(self):
        """Copy the current file to Backups/ once per session (first save)."""
        if not self.path.exists():
            return
        folder = self.path.parent / "Backups"
        folder.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        shutil.copy2(self.path, folder / f"{stamp}_{self.path.name}")
        backups = sorted(folder.glob(f"*_{self.path.name}"))
        for old in backups[:-MAX_BACKUPS]:
            old.unlink()

    # ------------------------------------------------------------- entries
    def entries(self, kind: str) -> list[dict]:
        return self.data["entries"].setdefault(kind, [])

    def all_entries(self):
        """Yield (kind, record) for every dated entry."""
        for kind, records in self.data["entries"].items():
            for record in records:
                yield kind, record

    def get(self, kind: str, entry_id: str) -> dict | None:
        return next((r for r in self.entries(kind) if r.get("id") == entry_id), None)

    def add(self, kind: str, record: dict, save: bool = True) -> dict:
        record.setdefault("id", new_id())
        self.entries(kind).append(record)
        if save:
            self.save()
        return record

    def update(self, kind: str, record: dict):
        records = self.entries(kind)
        for i, existing in enumerate(records):
            if existing.get("id") == record.get("id"):
                records[i] = record
                break
        else:
            records.append(record)
        self.save()

    def delete(self, kind: str, entry_id: str):
        self.data["entries"][kind] = [r for r in self.entries(kind) if r.get("id") != entry_id]
        self.save()

    def date_range(self) -> tuple[date, date] | None:
        dates = [parse_date(r.get("date")) for _, r in self.all_entries() if r.get("date")]
        if not dates:
            return None
        ends = [parse_date(r.get("date_to")) for _, r in self.all_entries() if r.get("date_to")]
        return min(dates), max(dates + ends)

    # -------------------------------------------------------------- places
    def catalog(self, name: str) -> list[dict]:
        """Places added in the settings without an entry yet ('mountains' / 'climbing'): dicts with the
        location fields (country, region, range, ...). Offered by the entry form like places of real entries."""
        return self.data["places"].setdefault(name, [])

    # ------------------------------------------------------------ training
    @property
    def methods(self) -> list[dict]:
        return self.data["training"]["methods"]

    # ---------------------------------------------------------- suggestions
    def distinct(self, kind: str, key: str, split_partners: bool = False) -> list[str]:
        """Distinct non-empty values of a field, most frequent first (for autocomplete)."""
        counts: dict[str, int] = {}
        for record in self.entries(kind):
            value = record.get(key)
            if not value:
                continue
            values = split_list(value) if split_partners else [str(value)]
            for v in values:
                counts[v] = counts.get(v, 0) + 1
        return sorted(counts, key=lambda v: (-counts[v], v.lower()))

    def distinct_nested(self, kind: str, list_key: str, key: str) -> list[str]:
        counts: dict[str, int] = {}
        for record in self.entries(kind):
            for item in record.get(list_key) or []:
                value = item.get(key)
                if value:
                    counts[str(value)] = counts.get(str(value), 0) + 1
        return sorted(counts, key=lambda v: (-counts[v], v.lower()))


def split_list(value: str) -> list[str]:
    """Split a free-text partner field like 'Anna, Ben & Chris' into names."""
    text = str(value)
    for sep in [";", "&", "/", " und ", " and ", "+"]:
        text = text.replace(sep, ",")
    return [p.strip() for p in text.split(",") if p.strip()]
