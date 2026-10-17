"""Generates pwa/kinds.json (the entry forms, from schema.py) and the app icons. Run after changing schema.py:
python make_pwa.py"""
import json
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPolygonF

import grades
import schema
import theme

OUT = Path(__file__).resolve().parent / "pwa"


def field_spec(f) -> dict:
    spec = {"key": f.key, "label": f.label, "type": f.type}
    if f.required:
        spec["required"] = True
    if f.choices:
        spec["choices"] = list(f.choices)
    if f.type in ("int", "float", "rating"):
        spec.update(maximum=f.maximum, minimum=f.minimum, step=f.step)
    if f.type == "float":
        spec["decimals"] = f.decimals
    if f.suffix:
        spec["suffix"] = f.suffix
    if f.sub:
        spec.update(sub=[field_spec(s) for s in f.sub], item_label=f.item_label,
                    columns=f.columns or [s.key for s in f.sub][:6])
    return spec


class _Probe:
    """Stands in for the database: pools list where their records come from instead of the records."""

    def entries(self, kind):
        return [{"_kind": kind}]

    def catalog(self, name):
        return [{"_catalog": name}]


def cascade_spec(kind: str) -> dict | None:
    """Dependent dropdowns of a kind: the chain of field keys and, per key, the kinds / place catalogues whose
    records the suggestions are taken from (derived from schema.cascade_for, so both apps agree)."""
    found = schema.cascade_for(kind, _Probe())
    if not found:
        return None
    chain, pool = found
    pools = {}
    for key in chain:
        records = pool(key)
        pools[key] = {"kinds": sorted({r["_kind"] for r in records if "_kind" in r}),
                      "catalogs": sorted({r["_catalog"] for r in records if "_catalog" in r})}
    return {"chain": chain, "pools": pools}


def kinds_json() -> dict:
    kinds = {}
    for k in schema.ADDABLE:
        spec = schema.KINDS[k]
        kinds[k] = {"label": spec.label, "plural": spec.plural, "color": theme.KIND_COLORS.get(k, theme.ACCENT),
                    "fields": [field_spec(f) for f in spec.fields]}
        if cascade_spec(k):
            kinds[k]["cascade"] = cascade_spec(k)
    return {"order": schema.ADDABLE, "kinds": kinds, "grades": {"french": grades.FRENCH, "uiaa": grades.UIAA}}


def icon(size: int, path: Path):
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(QColor(theme.HEADER))                  # iOS rounds the corners itself, so fill the whole square
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 100
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#ffffff"))
    p.drawPolygon(QPolygonF([QPointF(14 * s, 74 * s), QPointF(42 * s, 28 * s), QPointF(58 * s, 54 * s),
                             QPointF(68 * s, 40 * s), QPointF(88 * s, 74 * s)]))
    p.setBrush(QColor(theme.KIND_COLORS.get("sport_routes", "#d9822b")))
    p.drawEllipse(QRectF(66 * s, 16 * s, 14 * s, 14 * s))
    p.end()
    img.save(str(path))


if __name__ == "__main__":
    app = QGuiApplication([])
    (OUT / "icons").mkdir(parents=True, exist_ok=True)
    (OUT / "kinds.json").write_text(json.dumps(kinds_json(), ensure_ascii=False, indent=1), encoding="utf-8")
    for size in (180, 192, 512):
        icon(size, OUT / "icons" / f"icon-{size}.png")
    print("written to", OUT)
