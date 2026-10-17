"""Import the sport-climbing ticks of an 8a.nu logbook export (CSV) into the tick list.

8a.nu: profile -> logbook export (CSV). Columns used: route_boulder, name, location_name (crag), sector_name,
country_code, date, type (os / f / rp), tries, rating, difficulty (grade), comment.

* gym routes / gym boulders are ignored
* ticks already in the tick list are skipped (same route name on the same day, or within 2 days with the same
  grade); the file itself is de-duplicated the same way, so importing again later only adds new ticks
* area / country / region are filled from your existing entries of the same crag
"""
import csv
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date

from database import new_id

COUNTRIES = {"IT": "Italy", "AT": "Austria", "SI": "Slovenia", "FR": "France", "OM": "Oman", "ES": "Spain",
             "GR": "Greece", "MA": "Morocco", "NO": "Norway", "AO": "Angola", "DE": "Germany", "CH": "Switzerland",
             "HR": "Croatia", "PT": "Portugal", "GB": "United Kingdom", "US": "United States", "TR": "Turkey",
             "CZ": "Czechia", "SK": "Slovakia", "BG": "Bulgaria", "JO": "Jordan", "TH": "Thailand", "ZA": "South Africa"}
DISCIPLINES = {"ROUTE": "Sportklettern", "BOULDER": "Boulder"}
ATTEMPTS = {"os": "onsight", "f": "flash"}
AUTO_COMMENT = re.compile(r"^\s*Name:.*Schwierigkeit:", re.I)     # 8a's own "Name: x; Schwierigkeit: y" filler
FONT_GRADE = re.compile(r"^([3-9])([ABC])(\+?)$")
NEAR_DAYS = 2


def norm(text) -> str:
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", text)


def clean_grade(raw: str) -> str:
    g = (raw or "").strip()
    if not g or g == "1":                       # '1' is 8a's placeholder for "no grade"
        return ""
    m = FONT_GRADE.match(g)
    if m:                                       # Fontainebleau capitals -> the lowercase scale used in this app
        return f"{m.group(1)}{m.group(2).lower()}{m.group(3)}"
    return g


def attempts_of(kind: str, tries: str) -> str:
    if kind in ATTEMPTS:
        return ATTEMPTS[kind]
    n = int(tries) if str(tries).isdigit() else 2
    return "10+" if n > 10 else str(max(2, n))


@dataclass
class Plan:
    records: list[dict] = field(default_factory=list)
    rows: int = 0
    gym: int = 0
    invalid: int = 0
    dup_exact: int = 0
    dup_near: int = 0
    dup_in_file: int = 0

    @property
    def skipped(self) -> int:
        return self.dup_exact + self.dup_near + self.dup_in_file

    def by_year(self) -> dict[int, int]:
        years = Counter(int(r["date"][:4]) for r in self.records)
        return dict(sorted(years.items()))


def read_rows(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _place_lookup(db):
    """normalised crag -> most common (area, country, region) among your existing entries."""
    seen = defaultdict(lambda: defaultdict(Counter))
    for kind in ("sport_routes", "climbing_days"):
        for r in db.entries(kind):
            crag = norm(r.get("crag"))
            if not crag:
                continue
            for key in ("area", "country", "region"):
                if r.get(key):
                    seen[crag][key][r[key]] += 1
    return {crag: {k: c.most_common(1)[0][0] for k, c in d.items()} for crag, d in seen.items()}


def build_plan(db, path: str) -> Plan:
    plan = Plan()
    existing = defaultdict(list)                      # normalised name -> [(date, normalised grade)]
    for r in db.entries("sport_routes"):
        try:
            d = date.fromisoformat(r["date"])
        except (KeyError, ValueError):
            continue
        existing[norm(r.get("name"))].append((d, norm(r.get("grade"))))
    places = _place_lookup(db)
    accepted = defaultdict(list)                      # same structure for rows taken from this file

    def duplicate_of(name_key, d, grade_key, pool):
        for other_d, other_grade in pool.get(name_key, []):
            gap = abs((other_d - d).days)
            grades_agree = not grade_key or not other_grade or grade_key == other_grade
            if gap == 0 and grades_agree:
                return "exact"
            if 0 < gap <= NEAR_DAYS and grade_key and grade_key == other_grade:
                return "near"
        return None

    for row in read_rows(path):
        plan.rows += 1
        kind = (row.get("route_boulder") or "").strip().upper()
        if kind not in DISCIPLINES:                   # GYM_ROUTE / GYM_BOULDER and anything unknown
            plan.gym += 1
            continue
        name = (row.get("name") or "").strip()
        try:
            d = date.fromisoformat((row.get("date") or "")[:10])
        except ValueError:
            plan.invalid += 1
            continue
        if not name:
            plan.invalid += 1
            continue
        grade = clean_grade(row.get("difficulty"))
        nkey, gkey = norm(name), norm(grade)
        hit = duplicate_of(nkey, d, gkey, existing)
        if hit == "exact":
            plan.dup_exact += 1
            continue
        if hit == "near":
            plan.dup_near += 1
            continue
        if duplicate_of(nkey, d, gkey, accepted):
            plan.dup_in_file += 1
            continue
        accepted[nkey].append((d, gkey))
        crag = (row.get("location_name") or "").strip()
        place = places.get(norm(crag), {})
        comment = (row.get("comment") or "").strip()
        rating = int(row["rating"]) if str(row.get("rating", "")).isdigit() else 0
        plan.records.append({
            "id": new_id(), "date": d.isoformat(), "discipline": DISCIPLINES[kind], "name": name, "grade": grade,
            "attempts": attempts_of((row.get("type") or "").strip().lower(), row.get("tries", "")),
            "country": COUNTRIES.get((row.get("country_code") or "").strip().upper(),
                                     (row.get("country_code") or "").strip().upper()) or place.get("country", ""),
            "region": place.get("region", ""), "area": place.get("area", ""), "crag": crag,
            "sector": (row.get("sector_name") or "").strip(), "first_ascent": False,
            "rating": min(5, max(0, rating)), "info": "" if AUTO_COMMENT.match(comment) else comment,
            "source": "8a.nu",
        })
    plan.records.sort(key=lambda r: (r["date"], r["name"].lower()))
    return plan


def apply_plan(db, plan: Plan) -> int:
    for r in plan.records:
        db.entries("sport_routes").append(r)
    if plan.records:
        db.save()                                      # first save of a session writes a backup copy
    return len(plan.records)


def summary_text(plan: Plan) -> str:
    years = plan.by_year()
    span = f"{min(years)} – {max(years)}" if years else "–"
    return (f"{plan.rows} rows in the file\n"
            f"• {plan.gym} gym routes / gym boulders ignored\n"
            f"• {plan.skipped} already in your tick list "
            f"({plan.dup_exact} same day, {plan.dup_near} within {NEAR_DAYS} days, {plan.dup_in_file} repeated in the file)\n"
            f"• {plan.invalid} rows without a valid name or date\n\n"
            f"{len(plan.records)} new ticks to import ({span}).")
