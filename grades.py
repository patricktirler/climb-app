"""Climbing grades: lists, scale detection and the common rock index from V1.

UIAA and French grades share one index (V1 convention): UIAA 3 = 22 … 12 = 58,
French 5a = 30 … 9c = 58, so UIAA 5 = 5a, UIAA 8 = 7a, UIAA 9+/10- = 8a.
"""
FRENCH = [f"{n}{l}{p}" for n in (5, 6, 7, 8, 9) for l in "abc" for p in ("", "+")][:29]  # 5a … 9c
UIAA = ["3", "3+", "3+/4-", "4-", "4", "4+", "4+/5-", "5-", "5", "5+", "5+/6-", "6-", "6", "6+", "6+/7-",
        "7-", "7", "7+", "7+/8-", "8-", "8", "8+", "8+/9-", "9-", "9", "9+", "9+/10-", "10-", "10", "10+",
        "10+/11-", "11-", "11", "11+", "11+/12-", "12-", "12"]
WI = ["WI1", "WI2", "WI3", "WI3+", "WI4", "WI4+", "WI5", "WI5+", "WI6", "WI6+", "WI7"]
M = ["M1", "M2", "M3", "M3+"] + [f"M{n}{p}" for n in range(4, 15) for p in ("-", "", "+")][:-1]
ATTEMPTS = ["onsight", "flash"] + [str(i) for i in range(2, 11)] + ["10+"]
ROCK_CHOICES = FRENCH + UIAA

_FRENCH_INDEX = {g: 30 + i for i, g in enumerate(FRENCH)}
_UIAA_INDEX = {g: 22 + i for i, g in enumerate(UIAA)}
_INDEX_FRENCH = {v: k for k, v in _FRENCH_INDEX.items()}
_INDEX_UIAA = {v: k for k, v in _UIAA_INDEX.items()}


def scale(grade: str | None) -> str | None:
    if not grade:
        return None
    g = str(grade).strip()
    if "WI" in g.upper():
        return "WI"
    if "M" in g.upper():
        return "M"
    if any(c in g for c in "abc"):
        return "French"
    return "UIAA"


def rock_index(grade: str | None) -> int:
    """Common index for UIAA/French grades, -1 if unknown."""
    if not grade:
        return -1
    g = str(grade).strip()
    return _FRENCH_INDEX.get(g, _UIAA_INDEX.get(g, -1))


def wi_index(grade) -> int:
    return WI.index(grade) if grade in WI else -1


def m_index(grade) -> int:
    return M.index(grade) if grade in M else -1


def french(index: int) -> str:
    return _INDEX_FRENCH.get(index, "")


def uiaa(index: int) -> str:
    return _INDEX_UIAA.get(index, "")


def rock_label(index: int) -> str:
    """'6+ (6a)' style label for an index, used on chart axes."""
    u, f = uiaa(index), french(index)
    if u and f:
        return f"{f} / {u}"
    return f or u


def as_french(grade: str | None) -> str:
    i = rock_index(grade)
    return french(i) if i >= 0 else (grade or "")


def alpine_display(record: dict) -> str:
    """Grade summary of an alpine climb depending on its type (as V1 'Gesamtschwierigkeit')."""
    parts = [record.get("grade"), record.get("grade_wi"), record.get("grade_m")]
    return " ".join(p for p in parts if p)
