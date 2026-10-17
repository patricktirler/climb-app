"""Line icons for categories and buttons, drawn from small SVG snippets (24x24 grid) and tinted on demand."""
from functools import lru_cache

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# Each value is the inner SVG markup; stroke/fill are applied by the wrapper.
SHAPES = {
    # --- categories
    # rock climbing: climber reaching for a hold (solid silhouette)
    "climbing_days": '<circle cx="10" cy="4.2" r="2.6" fill="{c}" stroke="none"/><path stroke-width="3.6" d="M10.2 8.4L9.6 15"/><path stroke-width="2.7" d="M10.8 9.2L14.2 5.6 17 2.6M9.8 9.6L6.2 10.6 5 7.4M9.6 15L14.2 17.2 12.8 22.2M9.6 15L5.6 18 7.4 22.4"/>',
    "sport_routes": '<path d="M3.5 6l1.7 1.7L8.5 4.5M3.5 12l1.7 1.7L8.5 10.5M3.5 18l1.7 1.7L8.5 16.5M12 6h9M12 12h9M12 18h9"/>',
    # alpine climbing: rock piton - flat steel plate with an eye (solid)
    "alpine_climbs": '<g transform="rotate(42 12 12)"><path fill="{c}" stroke="none" fill-rule="evenodd" d="M8.2 1.8h7.6v6.7c0 1.1-.2 2-.6 3L12.9 22.4h-1.8L8.8 11.5c-.4-1-.6-1.9-.6-3zM12 3.8a2.3 2.3 0 1 0 0 4.6 2.3 2.3 0 0 0 0-4.6z"/></g>',
    "mountain_tours": '<path d="M2.5 20l7-12.5 4 7 3-4.5 5 10z"/><path d="M7.7 11.2l1.8 1.8 1.6-1.4"/>',
    "training_sessions": '<path d="M6 7v10M18 7v10M3 9.5v5M21 9.5v5M6 12h12"/>',                                # dumbbell
    "cycling": '<circle cx="6" cy="16" r="3.8"/><circle cx="18" cy="16" r="3.8"/><path d="M6 16l3.5-7.5h5.5l3 7.5M9.5 8.5L12 16H6M15 8.5l-1-3h-2.5"/>',
    "paragliding": '<path d="M2.5 9.5C4 4 9 3 12 3s8 1 9.5 6.5c-2.5-1.5-5.5-1.5-7.2 0-1.5-1.5-3.1-1.5-4.6 0-1.7-1.5-4.7-1.5-7.2 0z"/><path d="M5 10l7 8.5M19 10l-7 8.5M12 10v8.5"/><circle cx="12" cy="20.5" r="1.4"/>',
    "trips": '<rect x="3" y="7.5" width="18" height="13" rx="2.2"/><path d="M9 7.5V5.5a1.5 1.5 0 0 1 1.5-1.5h3A1.5 1.5 0 0 1 15 5.5v2M3 13h18"/>',
    "competitions": '<path d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H5v1.2A3 3 0 0 0 8 10M16 6h3v1.2A3 3 0 0 1 16 10M12 13v4M9 20h6M10 17h4"/>',
    "body_metrics": '<rect x="4" y="3.5" width="16" height="17" rx="3.5"/><path d="M8 9.5a4 4 0 0 1 8 0M12 9.5l2-2.2"/>',
    "notes": '<path d="M5 3.5h10.5L20 8v12.5H5zM15 3.5V8h5M8.5 12.5h7M8.5 16.5h5"/>',
    # --- interface
    "calendar": '<rect x="3.5" y="5" width="17" height="15.5" rx="2.2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    "calendar_plus": '<rect x="3.5" y="5" width="17" height="15.5" rx="2.2"/><path d="M3.5 10h17M8 3v4M16 3v4M12 13v5M9.5 15.5h5"/>',
    "list": '<path d="M8.5 6h12M8.5 12h12M8.5 18h12M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>',
    "chart": '<path d="M5 20.5V11M12 20.5V4M19 20.5v-6.5"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "sliders": '<path d="M3.5 6h9M18.5 6h2M3.5 12h3M11.5 12h9M3.5 18h11M19.5 18h1"/><circle cx="15.5" cy="6" r="2.2"/><circle cx="8.5" cy="12" r="2.2"/><circle cx="17" cy="18" r="2.2"/>',
    "pencil": '<path d="M4 20.5h4L19.5 9l-4-4L4 16.5zM13 7l4 4"/>',
    "copy": '<rect x="9" y="9" width="11.5" height="11.5" rx="2"/><path d="M5.5 15V6.5a2 2 0 0 1 2-2H15"/>',
    "trash": '<path d="M4 7h16M9.5 7V4h5v3M6.5 7l1 13h9l1-13M10 11v6M14 11v6"/>',
    "chevron_left": '<path d="M14.5 6l-6 6 6 6"/>',
    "chevron_right": '<path d="M9.5 6l6 6-6 6"/>',
    "today": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2.3"/>',
    "fullscreen": '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
    "fullscreen_exit": '<path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5"/>',
    "map_pin": '<path d="M12 21.5s-6.5-6.2-6.5-11.2a6.5 6.5 0 0 1 13 0c0 5-6.5 11.2-6.5 11.2z"/><circle cx="12" cy="10.2" r="2.4"/>',
    "close": '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
}
SHAPES["overview"] = SHAPES["chart"]


def _svg(name: str, color: str, width: float) -> bytes:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">'
            f'{SHAPES[name].replace("{c}", color)}</svg>').encode()


def _scale() -> float:
    screen = QGuiApplication.primaryScreen()
    return max(2.0, screen.devicePixelRatio() if screen else 2.0)


@lru_cache(maxsize=512)
def pixmap(name: str, color: str = "#52514e", size: int = 16, width: float = 2.2) -> QPixmap:
    """Icon as a crisp pixmap of ``size`` logical pixels."""
    dpr = _scale()
    px = int(size * dpr)
    img = QImage(px, px, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    QSvgRenderer(QByteArray(_svg(name, color, width))).render(p)
    p.end()
    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(dpr)
    return pm


def icon(name: str, color: str = "#52514e", size: int = 16, on_color: str | None = None, width: float = 2.2) -> QIcon:
    """QIcon; ``on_color`` is used while a checkable button is checked."""
    ic = QIcon()
    ic.addPixmap(pixmap(name, color, size, width), QIcon.Normal, QIcon.Off)
    ic.addPixmap(pixmap(name, on_color or color, size, width), QIcon.Normal, QIcon.On)
    ic.addPixmap(pixmap(name, on_color or color, size, width), QIcon.Active, QIcon.On)
    ic.addPixmap(pixmap(name, "#b5b4ad", size, width), QIcon.Disabled, QIcon.Off)
    return ic


def shade(color: str, factor: float = 0.62) -> str:
    """Darker variant of a category colour, readable on its own light tint."""
    c = QColor(color)
    return QColor(int(c.red() * factor), int(c.green() * factor), int(c.blue() * factor)).name()
