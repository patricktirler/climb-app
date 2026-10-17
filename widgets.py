"""Small widget subclasses shared by the forms.

TapSafe*: a touchpad "soft click" (tap-to-click) delivers mouse press and release almost
simultaneously. Qt opens a combo / date popup on *press*, so the release that follows can
close it again right away. These subclasses swallow the press and open the popup only after
the release, deferred to the next event-loop turn, so nothing trailing from the same tap
can close it. A click on the box while its popup is open still closes it (no re-open flicker).
"""
import time

from PySide6.QtCore import QDate, QEvent, QObject, QPoint, QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QMouseEvent
from PySide6.QtWidgets import QComboBox, QDateEdit, QHBoxLayout, QPushButton, QSizePolicy, QToolButton, QWidget

REOPEN_GUARD = 0.30   # seconds after a popup closed during which a release must not re-open it


def _synth_press(src: QMouseEvent) -> QMouseEvent:
    return QMouseEvent(QEvent.MouseButtonPress, QPointF(src.position()), QPointF(src.globalPosition()),
                       Qt.LeftButton, Qt.LeftButton, src.modifiers())


class ComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._armed = False
        self._closed_at = 0.0

    def hidePopup(self):
        self._closed_at = time.monotonic()
        super().hidePopup()

    def setEditable(self, editable: bool):
        super().setEditable(editable)
        if editable and self.lineEdit() is not None:
            self.lineEdit().installEventFilter(self)

    def eventFilter(self, obj, ev):
        """Up / Down step through the options right away (the completer would only open its popup);
        typing still filters / enters a new value."""
        if (obj is self.lineEdit() and ev.type() == QEvent.KeyPress and ev.key() in (Qt.Key_Up, Qt.Key_Down)
                and not ev.modifiers() & (Qt.AltModifier | Qt.ControlModifier)):
            step = -1 if ev.key() == Qt.Key_Up else 1
            now = self.findText(self.currentText(), Qt.MatchExactly)
            target = now + step if now >= 0 else (0 if step > 0 else self.count() - 1)
            if 0 <= target < self.count():
                self.setCurrentIndex(target)
                self.lineEdit().selectAll()
                self.activated.emit(target)          # same as a choice made with the mouse
            return True
        return super().eventFilter(obj, ev)

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return super().mousePressEvent(e)
        # presses on an editable box's text part go to its line edit, so anything reaching us is arrow/frame
        self._armed = True
        e.accept()

    def mouseReleaseEvent(self, e):
        if self._armed and e.button() == Qt.LeftButton:
            self._armed = False
            if time.monotonic() - self._closed_at > REOPEN_GUARD and self.rect().contains(e.position().toPoint()):
                press = _synth_press(e)
                QTimer.singleShot(20, lambda: QComboBox.mousePressEvent(self, press))
            e.accept()
            return
        super().mouseReleaseEvent(e)


class _HideStamp(QObject):
    """Event filter remembering when a popup (calendar) was last hidden."""

    def __init__(self, owner):
        super().__init__(owner)
        self.at = 0.0

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Hide:
            self.at = time.monotonic()
        return False


class DateEdit(QDateEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._armed = False
        self._stamp = _HideStamp(self)

    def setCalendarPopup(self, enable: bool):
        super().setCalendarPopup(enable)
        if enable:
            self.calendarWidget().installEventFilter(self._stamp)

    def _on_arrow(self, pos: QPoint) -> bool:
        return pos.x() >= self.width() - 28

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.calendarPopup() and self._on_arrow(e.position().toPoint()):
            self._armed = True
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if self._armed and e.button() == Qt.LeftButton:
            self._armed = False
            if time.monotonic() - self._stamp.at > REOPEN_GUARD:
                press = _synth_press(e)
                QTimer.singleShot(20, lambda: QDateEdit.mousePressEvent(self, press))
            e.accept()
            return
        super().mouseReleaseEvent(e)


class DateField(QWidget):
    """Date box with a calendar popup and  - / +  buttons that move the date by one day."""

    dateChanged = Signal(QDate)

    def __init__(self, parent=None):
        super().__init__(parent)
        import theme
        self.edit = DateEdit(self)
        self.edit.setCalendarPopup(True)
        self.edit.setDisplayFormat("dd.MM.yyyy")
        self.edit.dateChanged.connect(self.dateChanged)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self._step("dayMinus", theme.MINUS, "One day earlier", -1))
        row.addWidget(self.edit, 1)
        row.addWidget(self._step("dayPlus", theme.PLUS, "One day later", 1))
        self.setFocusProxy(self.edit)        # Tab stops at the date, not at the buttons

    def _step(self, name: str, icon: str, tip: str, days: int) -> QToolButton:
        b = QToolButton(self)
        b.setObjectName(name)
        b.setIcon(QIcon(icon))
        b.setIconSize(QSize(10, 10))
        b.setToolTip(tip)
        b.setFocusPolicy(Qt.NoFocus)
        b.setAutoRepeat(True)
        b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        b.clicked.connect(lambda: self.edit.setDate(self.edit.date().addDays(days)))
        return b

    def date(self) -> QDate:
        return self.edit.date()

    def setDate(self, d: QDate):
        self.edit.setDate(d)


class FullScreenButton(QPushButton):
    """Toggle that shows a view full screen (F11); the label follows the state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(38)
        self.set_active(False)

    def set_active(self, active: bool):
        import icons
        self.setToolTip("Leave full screen (Esc)" if active else "Full screen (F11)")
        self.setIcon(icons.icon("fullscreen_exit" if active else "fullscreen", "#52514e", 20))


__all__ = ["ComboBox", "DateEdit", "DateField", "FullScreenButton"]
