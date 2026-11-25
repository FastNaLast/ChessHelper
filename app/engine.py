"""Обёртка над Stockfish (UCI) + форматирование оценки."""

from __future__ import annotations

import threading
from typing import Optional

import chess
import chess.engine


class EngineError(Exception):
    pass


def fmt_score(score: Optional[chess.engine.PovScore]) -> str:
    """Оценка с точки зрения белых: +0.42 / -1.20 / #3 / #-2."""
    if score is None:
        return "?"
    white = score.white()
    if white.is_mate():
        mate = white.mate()
        return f"#{mate}" if mate > 0 else f"#-{abs(mate)}"
    cp = white.score()
    if cp is None:
        return "?"
    return f"{cp / 100:+.2f}"


def pv_to_san(board: chess.Board, pv: list[chess.Move], limit: int = 8) -> str:
    """Превращает главный вариант в читаемые ходы (e4 e5 Nf3 ...)."""
    tmp = board.copy()
    parts: list[str] = []
    for move in pv[:limit]:
        if move not in tmp.legal_moves:
            break
        parts.append(tmp.san(move))
        tmp.push(move)
    return " ".join(parts)


class Analyzer:
    """Один движок на всё приложение, запросы сериализуются."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._engine: Optional[chess.engine.SimpleEngine] = None
        self._lock = threading.Lock()
        self._threads = 2
        self._hash = 256

    # --- lifecycle ---------------------------------------------------
    def _ensure(self) -> chess.engine.SimpleEngine:
        if self._engine is None:
            if not self.path:
                raise EngineError("Не задан путь к движку.")
            try:
                self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
            except Exception as exc:  # noqa: BLE001
                raise EngineError(f"Не удалось запустить Stockfish: {exc}") from exc
            self._engine.configure({"Threads": self._threads, "Hash": self._hash})
        return self._engine

    def configure(self, threads: int, hash_mb: int) -> None:
        self._threads = max(1, int(threads))
        self._hash = max(16, int(hash_mb))
        with self._lock:
            if self._engine is not None:
                self._engine.configure(
                    {"Threads": self._threads, "Hash": self._hash}
                )

    def quit(self) -> None:
        with self._lock:
            if self._engine is not None:
                try:
                    self._engine.quit()
                except Exception:  # noqa: BLE001
                    pass
                self._engine = None

    # --- игра с ограничением силы -------------------------------------
    def set_skill(self, level: int) -> None:
        """0..20 — как «Skill Level» у Stockfish."""
        with self._lock:
            engine = self._ensure()
            engine.configure({"Skill Level": max(0, min(20, int(level)))})

    def best_move(self, fen: str, movetime: float = 0.3) -> chess.Move | None:
        board = chess.Board(fen)
        with self._lock:
            engine = self._ensure()
            result = engine.play(board, chess.engine.Limit(time=max(0.01, movetime)))
        return result.move

    # --- analysis ----------------------------------------------------
    def analyse(
        self, fen: str, depth: int = 16, multipv: int = 3
    ) -> list[dict]:
        board = chess.Board(fen)
        if board.is_game_over(claim_draw=False):
            return []
        with self._lock:
            engine = self._ensure()
            infos = engine.analyse(
                board,
                chess.engine.Limit(depth=max(1, int(depth))),
                multipv=max(1, int(multipv)),
            )
        if isinstance(infos, dict):
            infos = [infos]
        result: list[dict] = []
        for info in infos:
            pv = list(info.get("pv") or [])
            score = info.get("score")
            result.append(
                {
                    "score": score,
                    "score_text": fmt_score(score),
                    "pv": pv,
                    "pv_san": pv_to_san(board, pv) if pv else "",
                    "best_san": board.san(pv[0]) if pv and pv[0] in board.legal_moves else "",
                    "depth": info.get("depth"),
                }
            )
        return result
