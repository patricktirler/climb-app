"""Small slippy map (OpenStreetMap / OpenTopoMap tiles) for picking and showing GPS coordinates.

Tiles are downloaded on demand and cached on disk, so places you looked at once also work offline.
"""
import html
import math
import re
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QUrl, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QToolButton, QVBoxLayout,
)

import config

TILE = 256
MIN_ZOOM = 2
DEFAULT_CENTER = (47.0, 11.5)       # the Alps
STYLES = {
    "Street map": ("https://tile.openstreetmap.org/{z}/{x}/{y}.png", 19, "© OpenStreetMap contributors"),
    "Topographic": ("https://tile.opentopomap.org/{z}/{x}/{y}.png", 17,
                    "© OpenStreetMap contributors, SRTM | © OpenTopoMap (CC-BY-SA)"),
}
USER_AGENT = "ClimbApp/2.0 (personal climbing logbook)"
CACHE_DIR = config.SETTINGS_FILE.parent / "tiles"


# ------------------------------------------------------------------ coordinates
def parse_coords(text: str):
    """'47.123, 11.456' (also ';', spaces, decimal commas) -> (lat, lon) or None."""
    nums = re.findall(r"-?\d+(?:[.,]\d+)?", text or "")
    if len(nums) != 2:
        return None
    lat, lon = (float(n.replace(",", ".")) for n in nums)
    return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None


def format_coords(lat: float, lon: float) -> str:
    return f"{lat:.5f}, {lon:.5f}"


def _to_world(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    n = TILE * (2 ** zoom)
    lat = max(-85.0511, min(85.0511, lat))
    x = (lon + 180.0) / 360.0 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def _from_world(x: float, y: float, zoom: int) -> tuple[float, float]:
    n = TILE * (2 ** zoom)
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lon


def saved_style() -> str:
    style = config.load_settings().get("map_style")
    return style if style in STYLES else "Topographic"


# ------------------------------------------------------------------ the map
class MapWidget(QLabel):
    """Pannable / zoomable tile map with one marker. ``clicked`` fires on a click without dragging."""

    clicked = Signal(float, float)

    def __init__(self, parent=None, wheel_zoom: bool = True):
        super().__init__(parent)
        self.setMinimumSize(160, 120)
        self.setMouseTracking(False)
        self.setCursor(Qt.CrossCursor)
        self.wheel_zoom = wheel_zoom
        self.style_name = saved_style()
        self.zoom = 6
        self.center = DEFAULT_CENTER
        self.marker: tuple[float, float] | None = None
        self.net = QNetworkAccessManager(self)
        self.net.finished.connect(self._tile_loaded)
        self._tiles: dict[tuple, QPixmap] = {}
        self._pending: set[tuple] = set()
        self._failed: set[tuple] = set()
        self._press: QPointF | None = None
        self._dragged = False
        for text, delta, dy in (("+", 1, 8), ("−", -1, 38)):
            b = QToolButton(self)
            b.setText(text)
            b.setFixedSize(28, 28)
            b.setCursor(Qt.ArrowCursor)
            b.move(8, dy)
            b.clicked.connect(lambda _=False, d=delta: self.set_zoom(self.zoom + d))

    # ---- state
    def set_marker(self, lat: float | None, lon: float | None, center: bool = False, zoom: int | None = None):
        self.marker = (lat, lon) if lat is not None and lon is not None else None
        if self.marker and center:
            self.center = self.marker
        if zoom is not None:
            self.zoom = self._clamp(zoom)
        self.update()

    def set_view(self, lat: float, lon: float, zoom: int):
        self.center, self.zoom = (lat, lon), self._clamp(zoom)
        self.update()

    def set_style(self, name: str):
        if name in STYLES:
            self.style_name = name
            self.zoom = self._clamp(self.zoom)
            self.update()

    def _clamp(self, zoom: int) -> int:
        return max(MIN_ZOOM, min(STYLES[self.style_name][1], zoom))

    def set_zoom(self, zoom: int, anchor: QPointF | None = None):
        zoom = self._clamp(zoom)
        if zoom == self.zoom:
            return
        if anchor is not None:      # keep the point under the cursor fixed
            lat, lon = self._pos_to_latlon(anchor)
            self.zoom = zoom
            ax, ay = _to_world(lat, lon, zoom)
            cx, cy = ax - (anchor.x() - self.width() / 2), ay - (anchor.y() - self.height() / 2)
            self.center = _from_world(cx, cy, zoom)
        else:
            self.zoom = zoom
        self.update()

    # ---- geometry
    def _origin(self) -> tuple[float, float]:
        cx, cy = _to_world(*self.center, self.zoom)
        return cx - self.width() / 2, cy - self.height() / 2

    def _pos_to_latlon(self, pos: QPointF) -> tuple[float, float]:
        ox, oy = self._origin()
        return _from_world(ox + pos.x(), oy + pos.y(), self.zoom)

    # ---- tiles
    def _url(self, key) -> QUrl:
        style, z, x, y = key
        return QUrl(STYLES[style][0].format(z=z, x=x, y=y))

    def _tile(self, style: str, z: int, x: int, y: int) -> QPixmap | None:
        key = (style, z, x, y)
        pix = self._tiles.get(key)
        if pix is not None:
            return pix
        path = CACHE_DIR / style.split()[0] / str(z) / str(x) / f"{y}.png"
        if path.exists():
            pix = QPixmap(str(path))
            if not pix.isNull():
                self._tiles[key] = pix
                return pix
        if key not in self._pending and key not in self._failed:
            self._pending.add(key)
            req = QNetworkRequest(self._url(key))
            req.setRawHeader(b"User-Agent", USER_AGENT.encode())
            req.setAttribute(QNetworkRequest.RedirectPolicyAttribute, QNetworkRequest.NoLessSafeRedirectPolicy)
            self.net.get(req).setProperty("key", key)
        return None

    def _tile_loaded(self, reply: QNetworkReply):
        key = reply.property("key")
        self._pending.discard(key)
        if reply.error() == QNetworkReply.NoError:
            pix = QPixmap()
            data = reply.readAll()
            if pix.loadFromData(data):
                self._tiles[key] = pix
                path = CACHE_DIR / key[0].split()[0] / str(key[1]) / str(key[2]) / f"{key[3]}.png"
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(bytes(data))
                except OSError:
                    pass
                self.update()
        else:
            self._failed.add(key)       # offline / blocked: do not hammer the server
        reply.deleteLater()

    # ---- painting
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#e4e2da"))
        ox, oy = self._origin()
        n = 2 ** self.zoom
        x0, x1 = int(math.floor(ox / TILE)), int(math.floor((ox + self.width()) / TILE))
        y0, y1 = int(math.floor(oy / TILE)), int(math.floor((oy + self.height()) / TILE))
        missing = False
        for ty in range(max(0, y0), min(n - 1, y1) + 1):
            for tx in range(x0, x1 + 1):
                pix = self._tile(self.style_name, self.zoom, tx % n, ty)
                target = QRectF(tx * TILE - ox, ty * TILE - oy, TILE, TILE)
                if pix is not None:
                    p.drawPixmap(target, pix, QRectF(pix.rect()))
                else:
                    missing = True
        if missing and self._failed:
            p.setPen(QColor("#6b6a63"))
            p.drawText(self.rect().adjusted(46, 8, -8, -8), Qt.AlignTop | Qt.AlignLeft,
                       "Some map tiles could not be loaded (offline?)")
        if self.marker:
            mx, my = _to_world(*self.marker, self.zoom)
            self._draw_pin(p, mx - ox, my - oy)
        text = STYLES[self.style_name][2]
        font = QFont(self.font())
        font.setPointSizeF(7.5)
        p.setFont(font)
        w = p.fontMetrics().horizontalAdvance(text) + 8
        box = QRectF(self.width() - w, self.height() - 16, w, 16)
        p.fillRect(box, QColor(255, 255, 255, 190))
        p.setPen(QColor("#333333"))
        p.drawText(box, Qt.AlignCenter, text)

    @staticmethod
    def _draw_pin(p: QPainter, x: float, y: float):
        path = QPainterPath()
        path.moveTo(x, y)
        path.cubicTo(x - 14, y - 16, x - 11, y - 34, x, y - 34)
        path.cubicTo(x + 11, y - 34, x + 14, y - 16, x, y)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#ffffff"), 1.5))
        p.setBrush(QColor("#d6342c"))
        p.drawPath(path)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QPointF(x, y - 23), 4, 4)

    # ---- interaction
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press, self._dragged = e.position(), False
            self._last = e.position()

    def mouseMoveEvent(self, e):
        if self._press is None:
            return
        if (e.position() - self._press).manhattanLength() > 4:
            self._dragged = True
        if self._dragged:
            dx, dy = e.position().x() - self._last.x(), e.position().y() - self._last.y()
            cx, cy = _to_world(*self.center, self.zoom)
            self.center = _from_world(cx - dx, cy - dy, self.zoom)
            self.update()
        self._last = e.position()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._press is not None:
            if not self._dragged:
                lat, lon = self._pos_to_latlon(e.position())
                self.clicked.emit(lat, lon)
            self._press = None

    def wheelEvent(self, e):
        if not self.wheel_zoom:
            e.ignore()
            return
        step = 1 if e.angleDelta().y() > 0 else -1
        self.set_zoom(self.zoom + step, e.position())
        e.accept()


# ------------------------------------------------------------------ picker dialog
class MapPickDialog(QDialog):
    """Click on the map (or type coordinates) to choose a position."""

    def __init__(self, start: tuple[float, float] | None, fallback: tuple[float, float] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pick position on map")
        self.resize(820, 620)
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Coordinates:"))
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("latitude, longitude   (e.g. 47.26, 11.39) – or click on the map")
        self.edit.editingFinished.connect(self._typed)
        bar.addWidget(self.edit, 1)
        clear = QPushButton("Remove position")
        clear.setToolTip("Save the entry without a position")
        clear.clicked.connect(self._clear)
        bar.addWidget(clear)
        self.style_box = QComboBox()
        self.style_box.addItems(list(STYLES))
        bar.addWidget(self.style_box)
        layout.addLayout(bar)
        self.map = MapWidget()
        self.style_box.setCurrentText(self.map.style_name)
        self.style_box.currentTextChanged.connect(self._style_changed)
        self.map.clicked.connect(self._picked)
        layout.addWidget(self.map, 1)
        hint = QLabel("Drag to move, mouse wheel to zoom, click to set the position.")
        hint.setObjectName("muted")
        layout.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Use position")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.result: tuple[float, float] | None = None
        self.cleared = False
        if start:
            self.map.set_view(*start, 13)
            self._picked(*start)
        else:
            self.map.set_view(*(fallback or DEFAULT_CENTER), 9 if fallback else 6)

    def _clear(self):
        self.result, self.cleared = None, True
        super().accept()

    def _style_changed(self, name: str):
        self.map.set_style(name)
        settings = config.load_settings()
        settings["map_style"] = name
        try:
            config.save_settings(settings)
        except OSError:
            pass

    def _picked(self, lat: float, lon: float):
        self.cleared = False
        self.result = (round(lat, 5), round(lon, 5))
        self.map.set_marker(*self.result)
        self.edit.setText(format_coords(*self.result))

    def _typed(self):
        pos = parse_coords(self.edit.text())
        if pos:
            self.map.set_view(*pos, max(self.map.zoom, 12))
            self._picked(*pos)

    def accept(self):
        if self.result is None:
            return
        super().accept()


class MapViewDialog(QDialog):
    """Large map of one position: drag to move, wheel to zoom."""

    def __init__(self, lat: float, lon: float, title: str = "", parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint)
        self.setWindowTitle(title or "Map")
        self.resize(900, 650)
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        head = QLabel(f"<b>{html.escape(title)}</b>  ·  {format_coords(lat, lon)}" if title else format_coords(lat, lon))
        head.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bar.addWidget(head, 1)
        style_box = QComboBox()
        style_box.addItems(list(STYLES))
        bar.addWidget(style_box)
        layout.addLayout(bar)
        self.map = MapWidget()
        self.map.set_view(lat, lon, 14)
        self.map.set_marker(lat, lon)
        style_box.setCurrentText(self.map.style_name)
        style_box.currentTextChanged.connect(self.map.set_style)
        layout.addWidget(self.map, 1)


__all__ = ["MapWidget", "MapPickDialog", "MapViewDialog", "parse_coords", "format_coords"]
