"""Complete parser for ClimbApp V1 ".clmb" data files (C# WinForms ClimbApp, exe build 2021-07-16).

Format reverse engineered from the decompiled ClimbApp.exe (bin/Debug, the build that writes
ClimbData.clmb in the Google Drive folder) and verified against the real data.

Line semantics are those of .NET StreamReader.ReadLine(): a line ends at "\\r\\n", "\\r" or "\\n".
The file mixes CRLF (written by WriteLine) with lone LF (embedded inside multiline text values,
because the app joins multiline text with "\\n" when reading and writes it back verbatim).
=> We read with Python universal newlines (newline=None) and split on "\\n". Never use
   str.splitlines() (it also splits on \\x0b, \\x0c, \\x1c-\\x1e, \\x85, \\u2028, \\u2029).

Usage:  python clmb_parser.py <file.clmb> [--json out.json] [--stats]
API:    data = parse_clmb(path)   -> dict with all sections (see SECTION ORDER below)
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, date

DT_FMT = "%d.%m.%Y %H:%M:%S"   # DateTime.ToString() under de-AT/de-DE culture


class ClmbFormatError(Exception):
    pass


class Reader:
    def __init__(self, text: str):
        lines = text.split("\n")
        if lines and lines[-1] == "":      # file ends with a newline -> no extra line
            lines.pop()
        self.lines = lines
        self.pos = 0                       # 0-based index of next line

    @property
    def lineno(self) -> int:               # 1-based number of the NEXT line to be read
        return self.pos + 1

    def eof(self) -> bool:
        return self.pos >= len(self.lines)

    # --- primitive readers -------------------------------------------------
    def line(self) -> str:
        if self.pos >= len(self.lines):
            raise ClmbFormatError(f"unexpected EOF at line {self.lineno}")
        s = self.lines[self.pos]
        self.pos += 1
        return s

    def int(self) -> int:
        n = self.lineno
        s = self.line()
        try:
            return int(s.strip())          # Convert.ToInt32 (accepts negative, e.g. -1, -15)
        except ValueError:
            raise ClmbFormatError(f"line {n}: expected int, got {s!r}") from None

    def float(self) -> float:
        n = self.lineno
        s = self.line()
        try:
            return float(s.strip().replace(",", "."))   # Convert.ToDouble, de culture: "67,2"
        except ValueError:
            raise ClmbFormatError(f"line {n}: expected decimal (comma), got {s!r}") from None

    def bool(self) -> bool:
        n = self.lineno
        s = self.line().strip()
        if s == "True":
            return True
        if s == "False":
            return False
        raise ClmbFormatError(f"line {n}: expected True/False, got {s!r}")

    def dt(self) -> datetime:
        n = self.lineno
        s = self.line().strip()
        try:
            return datetime.strptime(s, DT_FMT)
        except ValueError:
            raise ClmbFormatError(f"line {n}: expected datetime dd.MM.yyyy HH:mm:ss, got {s!r}") from None

    def multiline(self) -> str:
        """Count line N (= number of '\\n' in the text = lines-1), then N+1 text lines, joined by '\\n'."""
        n = self.int()
        if n < 0:
            raise ClmbFormatError(f"line {self.lineno - 1}: negative multiline count {n}")
        return "\n".join(self.line() for _ in range(n + 1))

    def count(self, what: str) -> int:
        n0 = self.lineno
        n = self.int()
        if n < 0:
            raise ClmbFormatError(f"line {n0}: negative count for {what}: {n}")
        return n


# ---------------------------------------------------------------------------
# Helpers for derived values
# ---------------------------------------------------------------------------
FELS_UIAA = {22: "3", 23: "3+", 24: "3+/4-", 25: "4-", 26: "4", 27: "4+", 28: "4+/5-", 29: "5-",
             30: "5", 31: "5+", 32: "5+/6-", 33: "6-", 34: "6", 35: "6+", 36: "6+/7-", 37: "7-",
             38: "7", 39: "7+", 40: "7+/8-", 41: "8-", 42: "8", 43: "8+", 44: "8+/9-", 45: "9-",
             46: "9", 47: "9+", 48: "9+/10-", 49: "10-", 50: "10", 51: "10+", 52: "10+/11-",
             53: "11-", 54: "11", 55: "11+", 56: "11+/12-", 57: "12-", 58: "12"}
FELS_FRENCH = {30: "5a", 31: "5a+", 32: "5b", 33: "5b+", 34: "5c", 35: "5c+", 36: "6a", 37: "6a+",
               38: "6b", 39: "6b+", 40: "6c", 41: "6c+", 42: "7a", 43: "7a+", 44: "7b", 45: "7b+",
               46: "7c", 47: "7c+", 48: "8a", 49: "8a+", 50: "8b", 51: "8b+", 52: "8c", 53: "8c+",
               54: "9a", 55: "9a+", 56: "9b", 57: "9b+", 58: "9c"}


def grade_wi(i: int) -> str:
    if i < 0:
        return ""
    return f"WI{i // 2}" + ("+" if i % 2 == 1 else "")


def grade_m(i: int) -> str:
    # Encoding (Schwierigkeitsgrad.Index): "Mn-" = 3n-3, "Mn" = 3n-2, "Mn+" = 3n-1.
    # (The C# M getter is buggy - it tests ind_WI - this is the correct inverse.)
    if i < 0:
        return ""
    return f"M{i // 3 + 1}" + {0: "-", 1: "", 2: "+"}[i % 3]


def read_schwierigkeit(r: Reader) -> dict:
    """Schwierigkeitsgrad: 3 int lines ind_fels, ind_WI, ind_M (-1 = not set)."""
    fels, wi, m = r.int(), r.int(), r.int()
    return {
        "ind_fels": fels, "ind_wi": wi, "ind_m": m,
        "uiaa": FELS_UIAA.get(fels, ""), "french": FELS_FRENCH.get(fels, ""),
        "wi": grade_wi(wi), "m": grade_m(m),
    }


def duration_minutes(t: datetime) -> int:
    """Kletterzeit / Bergtour.zeit are DateTimes; only the time of day is meaningful (h:mm)."""
    return t.hour * 60 + t.minute


def with_session(d: datetime) -> dict:
    """Activity dates carry the 'Session' (index of the activity on that day) in the hour field."""
    return {"datum": d, "date": d.date(), "session": d.hour}


# ---------------------------------------------------------------------------
# Nested structures
# ---------------------------------------------------------------------------
def read_anhang(r: Reader) -> list:
    """Anhang: count, then per element 3 lines: art (Dateiordner|Link|_null), info, pfad."""
    out = []
    for _ in range(r.count("Anhang")):
        out.append({"art": r.line(), "info": r.line(), "pfad": r.line()})
    return out


def read_training_set(r: Reader) -> dict:
    ln = r.lineno
    s = {"_line": ln}
    # TrainingsMethode.DatenAbspeichern(pGeraeteGriffeAbspeichern:false)
    s["methode_disziplin"] = r.line()          # OptTraining: Alle|Boulder|Lead|Kraft|Fitness|Dehnen|_null
    s["methode_name"] = r.line()
    s["methode_beschreibung"] = r.multiline()
    s["geraet_griff"] = r.line()               # device / grip, free text
    s["zeit"] = r.int()                        # minutes
    s["strecke"] = r.int()                     # metres (Fitness: distance or Höhenmeter)
    s["pause"] = r.int()                       # seconds
    s["wiederholungen"] = r.int()              # nominal reps/sets (overridden by len(reps) if reps exist)
    s["info"] = r.multiline()
    # TrainingSetReps
    s["belastungsart"] = r.line()              # Wiederholung|Zeit|_null
    reps = []
    for _ in range(r.count("TrainingSetReps")):
        reps.append({"belastung": r.int(),     # reps (Wiederholung) or seconds (Zeit)
                     "gewicht": r.int(),       # kg; negative = assistance (e.g. -15 = 15 kg relief)
                     "seite": r.line()})       # Links|Rechts|Beidarmig|_null
    s["reps"] = reps
    s["wiederholungen_effektiv"] = len(reps) if reps else s["wiederholungen"]
    return s


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------
def read_koerperinfo(r: Reader) -> dict:
    ln = r.lineno
    return {"_line": ln, "datum": r.dt(), "gewicht": r.float()}


def read_trainingseinheit(r: Reader) -> dict:
    ln = r.lineno
    d = r.dt()
    e = {"_line": ln, **with_session(d)}
    e["ort"] = r.line()                        # Kletterhalle / location
    e["trainingsphase"] = r.line()             # Basis|Aufbau|Maximalkraft|Schnellkraft|Kraftausdauer|Ausdauer|Ausgleich|_null
    e["info"] = r.multiline()
    e["sets"] = [read_training_set(r) for _ in range(r.count("TrainingSets"))]
    return e


def read_saison_ziel(r: Reader) -> dict:
    return {"option": r.line(),                # ClimbOptionen name
            "datum": r.dt(),
            "unbestimmt": r.bool(),            # True = no target date (datum then 01.01.0001)
            "beschreibung": r.multiline()}


def read_trainings_saison(r: Reader) -> dict:
    ln = r.lineno
    s = {"_line": ln, "name": r.line(), "datum_von": r.dt(), "datum_bis": r.dt(),
         "beschreibung": r.multiline()}
    s["ziele"] = [read_saison_ziel(r) for _ in range(r.count("TrainingSaisonsZiele"))]
    return s


def read_wettkampf(r: Reader) -> dict:
    ln = r.lineno
    d = r.dt()
    w = {"_line": ln, **with_session(d)}
    w["datum_bis"] = r.dt()
    w["kletterhalle"] = r.line()
    w["ebene"] = r.line()                      # WettkampfEbene: JustForFun|Juniorcup|ItaMeisterschaften|Italiencup|_null
    # NOTE: C# bug - 'ItaMeisterschaften' is written but the reader only recognises the old name
    # 'Jugenditalienmeisterschaften', so such entries become '_null' after one save/load cycle.
    # The 12 '_null' entries in the real data (Arco, June, 4 disciplines) are almost certainly
    # Youth Italian Championships.
    w["disziplin"] = r.line()                  # WettkampfDisziplin
    w["ergebnis"] = r.int()                    # rank (int in this build)
    w["info"] = r.multiline()
    w["anhang"] = read_anhang(r)
    return w


def read_klettertag(r: Reader) -> dict:
    ln = r.lineno
    d = r.dt()
    k = {"_line": ln, **with_session(d)}
    k["disziplin"] = r.line()                  # OptFelsklettern: Boulder|Sportklettern|Trad|...
    k["klettergebiet"] = r.line()
    k["klettergarten"] = r.line()
    k["sektor"] = r.line()
    k["info"] = r.multiline()
    k["partner"] = r.line()
    k["anhang"] = read_anhang(r)
    return k


def read_sportklettertour(r: Reader) -> dict:
    ln = r.lineno
    d = r.dt()
    t = {"_line": ln, **with_session(d)}
    t["art"] = r.line()                        # OptSportkletterrouten: Sportklettern|Trad|Boulder
    t["klettergebiet"] = r.line()
    t["klettergarten"] = r.line()
    t["sektor"] = r.line()
    t["name"] = r.line()
    t["schwierigkeit"] = read_schwierigkeit(r)
    t["first_ascent"] = r.bool()
    t["versuche"] = r.line()                   # free text (e.g. "Onsight", "Flash", "2")
    t["bewertung"] = r.int()                   # star rating
    t["info"] = r.multiline()
    t["anhang"] = read_anhang(r)
    return t


def read_alpinklettertour(r: Reader) -> dict:
    ln = r.lineno
    t = {"_line": ln}
    t["art"] = r.line()                        # OptAlpintouren: Mehrseillängen|Alpinklettertour|Eisklettern|Kombiniert
    t.update(with_session(r.dt()))
    t["datum_bis"] = r.dt()
    t["bergmassiv"] = r.line()
    t["berg_wand"] = r.line()
    t["name"] = r.line()
    t["schwierigkeit"] = read_schwierigkeit(r)
    t["first_ascent"] = r.bool()
    t["ausrichtung"] = r.line()                # orientation (N, S, SW ...), free text
    t["klettermeter"] = r.int()
    t["seillaengen"] = r.int()
    t["kletterzeit"] = r.dt()                  # duration encoded as time-of-day
    t["kletterzeit_min"] = duration_minutes(t["kletterzeit"])
    t["stil"] = r.line()                       # AlpintourStil: onsight|rotpunkt|A0..A4|_null
    t["partner"] = r.line()
    t["info"] = r.multiline()
    t["bewertung"] = r.int()
    verlauf = []
    for _ in range(r.count("TourverlaufAlpin")):
        verlauf.append({"art": r.line(),       # Startpunkt|Einstieg|Sonstiges|Ziel|Endpunkt|_null
                        "hoehe": r.int(),
                        "zeitpunkt": r.dt(),
                        "info": r.line()})     # single line (NOT multiline-encoded)
    t["verlauf"] = verlauf
    t["anhang"] = read_anhang(r)
    return t


def read_bergtour(r: Reader) -> dict:
    ln = r.lineno
    t = {"_line": ln}
    t["art"] = r.line()                        # OptBergtouren: Wanderung|Hochtour|Skitour
    t.update(with_session(r.dt()))
    t["datum_bis"] = r.dt()
    t["gebirgsgruppe"] = r.line()
    t["name_tour"] = r.line()
    t["ausgangsort"] = r.line()                # starting point / trailhead
    t["hoehenmeter"] = r.int()                 # elevation gain (m)
    t["hoehe"] = r.int()                       # max altitude / summit height (m)
    t["zeit"] = r.dt()                         # duration encoded as time-of-day
    t["zeit_min"] = duration_minutes(t["zeit"])
    t["partner"] = r.line()
    t["info"] = r.multiline()
    weg = []
    for _ in range(r.count("Wegverlauf")):
        weg.append({"art": r.line(),           # WegpunktArt: Startpunkt|Tagesziel(=old 'Ziel')|Gipfel|Übernachtung|Endpunkt|Sonstiges|_null
                    "name": r.line(),
                    "hoehe": r.int(),
                    "zeitpunkt": r.dt(),
                    "info": r.line()})         # single line
    t["wegverlauf"] = weg
    t["anhang"] = read_anhang(r)
    return t


def read_reise(r: Reader) -> dict:
    ln = r.lineno
    t = {"_line": ln}
    t["name"] = r.line()
    t["art"] = r.line()                        # OptReisen: Mehrtagesausflug|Kletterreise|Expedition
    t["partner"] = r.line()
    t["datum_von"] = r.dt()
    t["datum_bis"] = r.dt()
    t["info"] = r.multiline()
    t["anhang"] = read_anhang(r)
    return t


def read_notiz(r: Reader) -> dict:
    ln = r.lineno
    d = r.dt()
    return {"_line": ln, **with_session(d), "datum_bis": r.dt(), "info": r.multiline()}


# --- export/sync filter settings (FilterAlleOptionen) -----------------------
def read_filter_training(r):
    return {"filter_aktiv": r.bool(), "schwerpunkt": r.line(), "trainingseinheiten": r.bool(),
            "methode_boulder": r.bool(), "methode_kraft": r.bool(), "methode_seil": r.bool(),
            "fitnesseinheiten": r.bool(), "fitness_zeit_min": r.bool(), "fitness_zeit": r.line(),
            "fitness_strecke_min": r.bool(), "fitness_strecke": r.line(),
            "datum_am": r.line(), "datum_von": r.line(), "datum_bis": r.line()}


def read_filter_wettkampf(r):
    return {"filter_aktiv": r.bool(), "ebene": r.line(), "disziplin": r.line(), "ergebnis": r.line(),
            "datum_am": r.line(), "datum_von": r.line(), "datum_bis": r.line()}


def read_filter_klettern(r):
    return {"filter_aktiv": r.bool(), "disziplin": r.line(),
            "datum_am": r.line(), "datum_von": r.line(), "datum_bis": r.line()}


def read_filter_sport(r):
    return {"filter_aktiv": r.bool(), "option": r.line(), "schwierigkeit_min": r.bool(),
            "schwierigkeit": r.line(), "fa": r.line(), "versuche": r.line(), "bewertung": r.int(),
            "datum_am": r.line(), "datum_von": r.line(), "datum_bis": r.line()}


def read_filter_alpin(r):
    return {"filter_aktiv": r.bool(), "ausrichtung": r.line(), "schwierigkeit_min": r.bool(),
            "schwierigkeit": r.line(), "seillaengen_min": r.line(), "seillaengen_max": r.line(),
            "fa": r.line(), "bewertung": r.int(), "kletterzeit_min": r.line(),
            "kletterzeit_max": r.line(), "datum_am": r.line(), "datum_von": r.line(),
            "datum_bis": r.line()}


def read_filter_berg(r):
    return {"filter_aktiv": r.bool(), "option": r.line(), "hoehe_von": r.line(), "hoehe_bis": r.line(),
            "hoehenmeter_von": r.line(), "hoehenmeter_bis": r.line(), "zeit_von": r.line(),
            "zeit_bis": r.line(), "datum_am": r.line(), "datum_von": r.line(), "datum_bis": r.line()}


def read_filter_gesamt(r):
    return {"filter_aktiv": r.bool(), "training": r.bool(), "wettkaempfe": r.bool(),
            "klettern": r.bool(), "routen": r.bool(), "alpintouren": r.bool(),
            "bergtouren": r.bool(), "datum_am": r.line(), "datum_von": r.line(), "datum_bis": r.line()}


def read_filter_alle_optionen(r: Reader) -> dict:
    f = {"_line": r.lineno}
    for k in ("training", "wettkaempfe", "klettern", "routen", "alpintouren", "bergtouren"):
        f["show_" + k] = r.bool()
    flags = {}
    for k in ("training", "wettkampf", "felsklettern", "sportkletterrouten", "alpintouren", "wanderungen"):
        flags[k] = r.bool()
    f["use_filter"] = flags
    readers = {"training": read_filter_training, "wettkampf": read_filter_wettkampf,
               "felsklettern": read_filter_klettern, "sportkletterrouten": read_filter_sport,
               "alpintouren": read_filter_alpin, "wanderungen": read_filter_berg}
    for k, fn in readers.items():          # sub-filters present ONLY if their flag is True
        f["filter_" + k] = fn(r) if flags[k] else None
    f["filter_gesamt"] = read_filter_gesamt(r)
    return f


# ---------------------------------------------------------------------------
# Top level
# ---------------------------------------------------------------------------
def _section(r: Reader, name: str, fn):
    ln = r.lineno
    n = r.count(name)
    items = [fn(r) for _ in range(n)]
    return items, ln


def parse_text(text: str) -> dict:
    r = Reader(text)
    out: dict = {"_count_lines": {}}
    out["header"] = [r.line() for _ in range(4)]   # "ClimbApp Data" | "ClimbApp BackupData", 2 warnings, ""
    if not out["header"][0].startswith("ClimbApp"):
        raise ClmbFormatError(f"not a ClimbApp file: {out['header'][0]!r}")

    def sec(key, name, fn):
        items, ln = _section(r, name, fn)
        out[key] = items
        out["_count_lines"][key] = ln

    sec("koerperinfos", "Koerperinfos", read_koerperinfo)               # 1
    sec("trainingseinheiten", "TrainingsEinheiten", read_trainingseinheit)  # 2
    sec("trainings_saisonen", "TrainingsSaisonen", read_trainings_saison)   # 3
    sec("wettkaempfe", "Wettkaempfe", read_wettkampf)                   # 4
    sec("klettertage", "Klettertage", read_klettertag)                  # 5
    sec("sportklettertouren", "Sportklettertouren", read_sportklettertour)  # 6
    sec("alpinklettertouren", "Alpinklettertouren", read_alpinklettertour)  # 7
    sec("bergtouren", "Bergtouren", read_bergtour)                      # 8
    sec("reisen", "Reisen", read_reise)                                 # 9
    sec("tagesnotizen", "TagesNotizen", read_notiz)                     # 10

    # 11 ClimbSynchronisierung (auto-export targets + their filters)
    sync = {"_line": r.lineno, "filename_kalender": r.line(), "filename_tabelle": r.line()}
    sync["filter_kalender"] = read_filter_alle_optionen(r)
    sync["filter_tabelle"] = read_filter_alle_optionen(r)
    out["synchronisierung"] = sync

    # 12 Settings_ClimbAppMobile
    out["settings_mobile"] = {"_line": r.lineno, "auto_import": r.bool(), "auto_export": r.bool(),
                              "pfad": r.line()}

    # 13 lastBackup (DateTime of the last weekly backup) - main file only (backups lack this line)
    if not r.eof():
        out["last_backup"] = r.dt()
    else:
        out["last_backup"] = None

    if not r.eof():
        raise ClmbFormatError(f"{len(r.lines) - r.pos} leftover lines starting at line {r.lineno}: "
                              f"{r.lines[r.pos:r.pos + 5]!r}")
    out["_total_lines"] = len(r.lines)
    out["_lines_consumed"] = r.pos
    # Training method catalogue: NOT stored as its own section in this format; the app rebuilds it
    # from all sets (TrainingDatenbank.DatenEinlesen(Einheiten)). Rebuild it the same way:
    methods = {}
    for e in out["trainingseinheiten"]:
        for s in e["sets"]:
            key = (s["methode_disziplin"], s["methode_name"])
            m = methods.setdefault(key, {"disziplin": key[0], "name": key[1],
                                         "beschreibung": s["methode_beschreibung"], "geraete_griffe": []})
            if s["geraet_griff"] not in m["geraete_griffe"]:
                m["geraete_griffe"].append(s["geraet_griff"])
    out["trainingsmethoden_derived"] = list(methods.values())
    return out


def parse_clmb(path: str) -> dict:
    # newline=None -> universal newlines: "\r\n", "\r", "\n" all become "\n" (== .NET ReadLine)
    with open(path, "r", encoding="utf-8-sig", newline=None) as f:
        return parse_text(f.read())


# ---------------------------------------------------------------------------
def _json_default(o):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    raise TypeError(type(o))


def stats(d: dict) -> None:
    print("Counts / count-line numbers:")
    for k, ln in d["_count_lines"].items():
        print(f"  {k:22s} {len(d[k]):5d}   (count line {ln})")
    print(f"  lines consumed {d['_lines_consumed']} / {d['_total_lines']}; last_backup={d['last_backup']}")
    sets = [s for e in d["trainingseinheiten"] for s in e["sets"]]
    reps = [r for s in sets for r in s["reps"]]
    print(f"  training sets {len(sets)}, reps {len(reps)}, derived methods {len(d['trainingsmethoden_derived'])}")
    print(f"  saison ziele {sum(len(s['ziele']) for s in d['trainings_saisonen'])}")
    print(f"  alpin verlauf points {sum(len(t['verlauf']) for t in d['alpinklettertouren'])}")
    print(f"  bergtour wegpunkte {sum(len(t['wegverlauf']) for t in d['bergtouren'])}")
    allanh = [a for k in ("wettkaempfe", "klettertage", "sportklettertouren", "alpinklettertouren",
                          "bergtouren", "reisen") for x in d[k] for a in x["anhang"]]
    print(f"  attachments total {len(allanh)}")

    def show(title, values):
        c = Counter(values)
        print(f"\n{title}:")
        for v, n in c.most_common():
            print(f"    {v!r}: {n}")

    show("Trainingsphase", [e["trainingsphase"] for e in d["trainingseinheiten"]])
    show("Training session (hour)", [e["session"] for e in d["trainingseinheiten"]])
    show("Set methode_disziplin", [s["methode_disziplin"] for s in sets])
    show("Set belastungsart", [s["belastungsart"] for s in sets])
    show("Rep seite", [x["seite"] for x in reps])
    show("Derived method disziplin", [m["disziplin"] for m in d["trainingsmethoden_derived"]])
    show("Saison ziel option", [z["option"] for s in d["trainings_saisonen"] for z in s["ziele"]])
    show("Wettkampf ebene", [w["ebene"] for w in d["wettkaempfe"]])
    show("Wettkampf disziplin", [w["disziplin"] for w in d["wettkaempfe"]])
    show("Felsklettern disziplin", [k["disziplin"] for k in d["klettertage"]])
    show("Klettertag session", [k["session"] for k in d["klettertage"]])
    show("Sportroute art", [t["art"] for t in d["sportklettertouren"]])
    show("Sportroute versuche", [t["versuche"] for t in d["sportklettertouren"]])
    show("Sportroute bewertung", [t["bewertung"] for t in d["sportklettertouren"]])
    show("Sportroute first_ascent", [t["first_ascent"] for t in d["sportklettertouren"]])
    show("Sportroute ind_fels", [t["schwierigkeit"]["ind_fels"] for t in d["sportklettertouren"]])
    show("Alpintour art", [t["art"] for t in d["alpinklettertouren"]])
    show("Alpintour stil", [t["stil"] for t in d["alpinklettertouren"]])
    show("Alpintour ausrichtung", [t["ausrichtung"] for t in d["alpinklettertouren"]])
    show("Alpintour bewertung", [t["bewertung"] for t in d["alpinklettertouren"]])
    show("Alpintour (fels,wi,m)", [(t["schwierigkeit"]["ind_fels"], t["schwierigkeit"]["ind_wi"],
                                    t["schwierigkeit"]["ind_m"]) for t in d["alpinklettertouren"]])
    show("Alpintour kletterzeit date part", [t["kletterzeit"].date().isoformat() for t in d["alpinklettertouren"]])
    show("Alpin verlauf art", [p["art"] for t in d["alpinklettertouren"] for p in t["verlauf"]])
    show("Bergtour art", [t["art"] for t in d["bergtouren"]])
    show("Bergtour zeit date part", [t["zeit"].date().isoformat() for t in d["bergtouren"]])
    show("Bergtour session", [t["session"] for t in d["bergtouren"]])
    show("Wegpunkt art", [p["art"] for t in d["bergtouren"] for p in t["wegverlauf"]])
    show("Reise art", [t["art"] for t in d["reisen"]])
    show("Anhang art", [a["art"] for a in allanh])


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    data = parse_clmb(args[0])
    if "--json" in args:
        with open(args[args.index("--json") + 1], "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, default=_json_default)
    if "--stats" in args or "--json" not in args:
        stats(data)
