"""Generates the small UI icons in assets/ (dropdown arrow, plus, minus). Run once: python make_icons.py"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen

OUT = Path(__file__).resolve().parent / "assets"
INK = QColor("#52514e")
SIZE = 48     # drawn large, shown at ~10px by the stylesheet


def icon(name: str, draw):
    img = QImage(SIZE, SIZE, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(INK, 5.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    draw(p)
    p.end()
    img.save(str(OUT / name))


def arrow_down(p):
    p.drawPolyline([QPointF(10, 18), QPointF(24, 32), QPointF(38, 18)])


def plus(p):
    p.drawLine(QPointF(10, 24), QPointF(38, 24))
    p.drawLine(QPointF(24, 10), QPointF(24, 38))


def minus(p):
    p.drawLine(QPointF(10, 24), QPointF(38, 24))


if __name__ == "__main__":
    app = QGuiApplication([])
    icon("arrow_down.png", arrow_down)
    icon("plus.png", plus)
    icon("minus.png", minus)
    print("icons written to", OUT)
