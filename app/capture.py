"""Захват области экрана (для будущего распознавания доски)."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget


def grab_region(region: dict) -> QImage:
    """Снимок прямоугольника экрана: {x, y, w, h} в логических пикселях."""
    import mss
    from PIL import Image

    with mss.mss() as sct:
        monitor = {
            "left": int(region["x"]),
            "top": int(region["y"]),
            "width": max(1, int(region["w"])),
            "height": max(1, int(region["h"])),
        }
        shot = sct.grab(monitor)
        image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        data = image.tobytes("raw", "RGB")
        qimage = QImage(data, image.width, image.height, 3 * image.width, QImage.Format.Format_RGB888)
        return qimage.copy()


class RegionSelector(QWidget):
    """Полупрозрачный оверлей на весь экран: тянем мышью — получаем QRect."""

    selected = Signal(QRect)

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowState(Qt.WindowState.WindowFullScreen)
        self.setWindowOpacity(0.35)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setStyleSheet("background: rgba(0, 0, 0, 200);")
        self._origin = None
        self._current = None
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.geometry())

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._origin = event.position().toPoint()
        self._current = self._origin
        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._origin is not None:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._origin is None:
            return
        self._current = event.position().toPoint()
        rect = QRect(self._origin, self._current).normalized()
        self.close()
        if rect.width() > 8 and rect.height() > 8:
            self.selected.emit(rect)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def paintEvent(self, _event) -> None:  # noqa: N802
        if self._origin is None or self._current is None:
            return
        painter = QPainter(self)
        rect = QRect(self._origin, self._current).normalized()
        painter.setPen(QPen(QColor("#FFD64A"), 2))
        painter.drawRect(rect)
        painter.fillRect(rect, QColor(255, 214, 74, 40))
