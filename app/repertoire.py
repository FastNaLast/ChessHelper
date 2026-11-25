"""Дебютный репертуар: PGN-файлы из data/repertoire."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import chess
import chess.pgn


@dataclass
class BookHit:
    move: chess.Move
    san: str
    count: int
    total: int

    @property
    def share(self) -> float:
        return self.count / self.total if self.total else 0.0


class Repertoire:
    """Каждый *.pgn в папке считается отдельным дебютом (имя = имя файла)."""

    def __init__(self, folder: Path) -> None:
        self.folder = Path(folder)
        self.books: dict[str, dict[str, Counter]] = {}
        self.errors: list[str] = []

    def load(self) -> "Repertoire":
        self.books.clear()
        self.errors.clear()
        if not self.folder.exists():
            self.folder.mkdir(parents=True, exist_ok=True)
            return self
        for path in sorted(self.folder.glob("*.pgn")):
            try:
                self._load_file(path)
            except Exception as exc:  # noqa: BLE001
                self.errors.append(f"{path.name}: {exc}")
        return self

    def _load_file(self, path: Path) -> None:
        table: dict[str, Counter] = {}
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            while True:
                game = chess.pgn.read_game(handle)
                if game is None:
                    break
                board = game.board()
                self._walk(game, board, table)
        if table:
            self.books[path.stem] = table

    @staticmethod
    def _walk(node: chess.pgn.ChildNode, board: chess.Board, table: dict[str, Counter]) -> None:
        for child in node.variations:
            # сначала запоминаем ход для ТЕКУЩЕЙ позиции, потом делаем его
            table.setdefault(board.epd(), Counter())[child.move] += 1
            board.push(child.move)
            Repertoire._walk(child, board, table)
            board.pop()

    # --- queries ------------------------------------------------------
    def names(self) -> list[str]:
        return sorted(self.books)

    def lookup(self, board: chess.Board, book: str | None = None) -> BookHit | None:
        if book:
            tables = [self.books[book]] if book in self.books else []
        else:
            tables = list(self.books.values())
        for table in tables:
            counter = table.get(board.epd())
            if not counter:
                continue
            move, count = counter.most_common(1)[0]
            if move not in board.legal_moves:
                continue
            return BookHit(move, board.san(move), count, sum(counter.values()))
        return None

    def in_book(self, board: chess.Board) -> bool:
        return any(board.epd() in table for table in self.books.values())
