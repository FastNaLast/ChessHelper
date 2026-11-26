"""Отрисовка шахматной доски на QPainter (без внешних картинок)."""

from __future__ import annotations

import chess
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

LIGHT = QColor("#EEEED2")
DARK = QColor("#7FA650")
HIGHLIGHT = QColor(255, 214, 74, 120)
WHITE_PIECE = QColor("#FFFFFF")
BLACK_PIECE = QColor("#1B1B1B")

GLYPHS = {
    chess.KING: "\u265A",
    chess.QUEEN: "\u265B",
    chess.ROOK: "\u265C",
    chess.BISHOP: "\u265D",
    chess.KNIGHT: "\u265E",
    chess.PAWN: "\u265F",
}


class BoardView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.board = chess.Board()
        self.flipped = False
        self.last_move = None
        self.setMinimumSize(180, 180)

    def set_board(self, board: chess.Board, last_move=None) -> None:
        self.board = board
        self.last_move = last_move
        self.update()

    def set_flipped(self, flipped: bool) -> None:
        self.flipped = flipped
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        side = min(self.width(), self.height())
        square = side / 8.0
        x0 = (self.width() - side) / 2.0
        y0 = (self.height() - side) / 2.0

        for row in range(8):
            for col in range(8):
                if self.flipped:
                    file_idx, rank_idx = 7 - col, row
                else:
                    file_idx, rank_idx = col, 7 - row
                is_light = (file_idx + rank_idx) % 2 == 1
                rect = QRectF(x0 + col * square, y0 + row * square, square, square)
                painter.fillRect(rect, LIGHT if is_light else DARK)
                if self.last_move is not None and chess.square(file_idx, rank_idx) in (
                    self.last_move.from_square,
                    self.last_move.to_square,
                ):
                    painter.fillRect(rect, HIGHLIGHT)

        font = QFont("Segoe UI Symbol")
        font.setPixelSize(int(square * 0.78))
        painter.setFont(font)

        for square_idx in chess.SQUARES:
            piece = self.board.piece_at(square_idx)
            if piece is None:
                continue
            file_idx = chess.square_file(square_idx)
            rank_idx = chess.square_rank(square_idx)
            if self.flipped:
                col, row = 7 - file_idx, rank_idx
            else:
                col, row = file_idx, 7 - rank_idx
            rect = QRectF(x0 + col * square, y0 + row * square, square, square)

            path = QPainterPath()
            glyph = GLYPHS[piece.piece_type]
            metrics = painter.fontMetrics()
            tw = metrics.horizontalAdvance(glyph)
            th = metrics.ascent()
            path.addText(
                rect.center().x() - tw / 2.0,
                rect.center().y() + th / 2.0 - metrics.descent() / 2.0,
                painter.font(),
                glyph,
            )
            if piece.color == chess.WHITE:
                painter.fillPath(path, WHITE_PIECE)
                painter.setPen(QPen(QColor("#222222"), max(1.0, square * 0.02)))
            else:
                painter.fillPath(path, BLACK_PIECE)
                painter.setPen(QPen(QColor("#E8E8E8"), max(1.0, square * 0.02)))
            painter.drawPath(path)
