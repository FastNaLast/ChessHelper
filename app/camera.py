"""Приём потока с телефона-камеры и калибровка доски (4 угла -> 8x8)."""

from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtCore import QPointF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

GRID = 800  # размер выпрямленной доски в пикселях
CELL = GRID // 8


# ---------------------------------------------------------------- конвертация
def qimage_to_np(image: QImage) -> np.ndarray:
    converted = image.convertToFormat(QImage.Format.Format_RGB888)
    width, height = converted.width(), converted.height()
    buffer = np.frombuffer(converted.constBits(), np.uint8)
    buffer = buffer.reshape(height, converted.bytesPerLine())
    buffer = buffer[:, : width * 3].reshape(height, width, 3)
    return buffer.copy()


def np_to_qimage(array: np.ndarray) -> QImage:
    array = np.ascontiguousarray(array)
    height, width, channels = array.shape
    image = QImage(array.data, width, height, channels * width, QImage.Format.Format_RGB888)
    return image.copy()


# ------------------------------------------------------------------- поток
class StreamReader(QThread):
    """Читает MJPEG/RTSP из cv2.VideoCapture в отдельном потоке."""

    frame = Signal(QImage)
    failed = Signal(str)

    def __init__(self, url: str, parent=None) -> None:
        super().__init__(parent)
        self.url = url
        self._alive = True

    def run(self) -> None:  # noqa: D401
        try:
            source = int(self.url) if self.url.isdigit() else self.url
            capture = cv2.VideoCapture(source)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Не открыть поток: {exc}")
            return
        if not capture.isOpened():
            self.failed.emit(
                f"Не удалось подключиться к {self.url}. Проверь URL и что телефон в той же Wi-Fi."
            )
            return
        try:
            while self._alive:
                ok, frame = capture.read()
                if not ok:
                    self.failed.emit("Поток прервался.")
                    break
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.frame.emit(np_to_qimage(rgb))
                self.msleep(40)
        finally:
            capture.release()

    def stop(self) -> None:
        self._alive = False
        self.wait(2500)


# ---------------------------------------------------------------- калибровка
SQUARE_NAMES = [
    f"{file_name}{rank}"
    for rank in range(8, 0, -1)
    for file_name in "abcdefgh"
]


def warp_board(image: QImage, corners: list[tuple[float, float]]) -> np.ndarray | None:
    """4 угла (TL, TR, BR, BL) в координатах кадра -> выпрямленная доска 800x800."""
    if len(corners) != 4:
        return None
    frame = qimage_to_np(image)
    source = np.array(corners, dtype=np.float32)
    target = np.array(
        [[0, 0], [GRID - 1, 0], [GRID - 1, GRID - 1], [0, GRID - 1]], dtype=np.float32
    )
    matrix = cv2.getPerspectiveTransform(source, target)
    return cv2.warpPerspective(frame, matrix, (GRID, GRID))


def split_cells(warped: np.ndarray) -> dict[str, np.ndarray]:
    """64 клетки: a8 — левый верхний угол, h1 — правый нижний."""
    cells: dict[str, np.ndarray] = {}
    for row in range(8):
        for col in range(8):
            name = f"{'abcdefgh'[col]}{8 - row}"
            cells[name] = warped[row * CELL : (row + 1) * CELL, col * CELL : (col + 1) * CELL]
    return cells


def draw_grid(warped: np.ndarray, highlight: dict[str, tuple[int, int, int]] | None = None) -> np.ndarray:
    canvas = warped.copy()
    for index in range(9):
        offset = min(index * CELL, GRID - 1)
        cv2.line(canvas, (offset, 0), (offset, GRID - 1), (255, 214, 74), 2)
        cv2.line(canvas, (0, offset), (GRID - 1, offset), (255, 214, 74), 2)
    if highlight:
        for name, color in highlight.items():
            row = 8 - int(name[1])
            col = "abcdefgh".index(name[0])
            cv2.rectangle(
                canvas,
                (col * CELL + 2, row * CELL + 2),
                ((col + 1) * CELL - 2, (row + 1) * CELL - 2),
                color,
                3,
            )
    return canvas


# ------------------------------------------------------------- виджет кадра
class FrameView(QWidget):
    """Показывает кадр с камеры и принимает клики в координатах кадра."""

    clicked = Signal(float, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._image: QImage | None = None
        self._points: list[tuple[float, float]] = []
        self.setMinimumHeight(240)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_image(self, image: QImage) -> None:
        self._image = image
        self.update()

    def image(self) -> QImage | None:
        return self._image

    def set_points(self, points: list[tuple[float, float]]) -> None:
        self._points = list(points)
        self.update()

    def points(self) -> list[tuple[float, float]]:
        return list(self._points)

    def _placement(self) -> tuple[float, float, float]:
        if self._image is None:
            return 1.0, 0.0, 0.0
        scale = min(self.width() / self._image.width(), self.height() / self._image.height())
        offset_x = (self.width() - self._image.width() * scale) / 2
        offset_y = (self.height() - self._image.height() * scale) / 2
        return scale, offset_x, offset_y

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._image is None or event.button() != Qt.MouseButton.LeftButton:
            return
        scale, offset_x, offset_y = self._placement()
        x = (event.position().x() - offset_x) / scale
        y = (event.position().y() - offset_y) / scale
        if 0 <= x < self._image.width() and 0 <= y < self._image.height():
            self.clicked.emit(x, y)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#17181B"))
        if self._image is None:
            painter.setPen(QColor("#77797E"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "нет кадра")
            return
        scale, offset_x, offset_y = self._placement()
        painter.drawImage(
            QPointF(offset_x, offset_y),
            self._image.scaled(
                int(self._image.width() * scale),
                int(self._image.height() * scale),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ),
        )
        if len(self._points) >= 2:
            painter.setPen(QPen(QColor("#FFD64A"), 2))
            scaled = [
                QPointF(offset_x + x * scale, offset_y + y * scale) for x, y in self._points
            ]
            for start, end in zip(scaled, scaled[1:] + scaled[:1]):
                painter.drawLine(start, end)
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        for index, (x, y) in enumerate(self._points):
            center = QPointF(offset_x + x * scale, offset_y + y * scale)
            painter.setPen(QPen(QColor("#FFD64A"), 2))
            painter.setBrush(QColor("#1E1F22"))
            painter.drawEllipse(center, 9, 9)
            painter.setPen(QColor("#FFD64A"))
            painter.drawText(
                int(center.x()) - 4, int(center.y()) + 5, str(index + 1)
            )
        painter.setBrush(Qt.BrushStyle.NoBrush)
