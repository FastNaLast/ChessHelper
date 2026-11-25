"""Разбор партии по PGN: оценка каждого хода и отчёт в Markdown."""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import chess
import chess.engine
import chess.pgn

from .engine import Analyzer


def _mark(loss: int, is_best: bool) -> str:
    if is_best:
        return "\u2713"      # точный ход
    if loss < 20:
        return ""
    if loss < 60:
        return "?!"
    if loss < 150:
        return "?"
    return "??"


def _cp(score: chess.engine.PovScore, turn: chess.Color) -> int:
    """Оценка в сантипешках с точки зрения указанной стороны."""
    pov = score.pov(turn)
    return int(pov.score(mate_score=100000) or 0)


@dataclass
class MoveRow:
    number: int
    color: str
    san: str
    eval_after: int
    best_san: str
    loss: int
    mark: str


@dataclass
class GameReport:
    headers: dict[str, str] = field(default_factory=dict)
    rows: list[MoveRow] = field(default_factory=list)
    blunders: int = 0
    mistakes: int = 0
    inaccuracies: int = 0
    average_loss: float = 0.0
    total_moves: int = 0


def analyse_pgn(
    text: str,
    analyzer: Analyzer,
    depth: int = 12,
    progress=None,
) -> GameReport:
    game = chess.pgn.read_game(io.StringIO(text))
    if game is None:
        raise ValueError("Не удалось прочитать PGN.")

    report = GameReport(headers=dict(game.headers))
    board = game.board()
    node: chess.pgn.ChildNode = game  # type: ignore[assignment]
    total = len(list(game.mainline_moves()))
    ply = 0
    losses: list[int] = []

    while node.variations:
        node = node.variations[0]
        move = node.move
        assert move is not None

        mover = board.turn
        san = board.san(move)

        try:
            infos = analyzer.analyse(board.fen(), depth=depth, multipv=1)
        except Exception:  # noqa: BLE001
            infos = []

        if infos:
            best_cp = _cp(infos[0]["score"], mover)
            best_san = infos[0].get("best_san") or ""
            best_move = infos[0]["pv"][0] if infos[0].get("pv") else None
        else:
            best_cp, best_san, best_move = 0, "", None

        board.push(move)
        ply += 1

        try:
            after = analyzer.analyse(board.fen(), depth=depth, multipv=1)
        except Exception:  # noqa: BLE001
            after = []
        played_cp = -_cp(after[0]["score"], not mover) if after else best_cp

        loss = max(0, best_cp - played_cp)
        if not infos or not after:
            mark = ""
        else:
            mark = _mark(loss, best_move is not None and best_move == move)
        losses.append(loss)

        report.rows.append(
            MoveRow(
                number=(ply + 1) // 2,
                color="белые" if mover == chess.WHITE else "чёрные",
                san=san,
                eval_after=played_cp,
                best_san=best_san,
                loss=loss,
                mark=mark,
            )
        )

        if mark == "??":
            report.blunders += 1
        elif mark == "?":
            report.mistakes += 1
        elif mark == "?!":
            report.inaccuracies += 1

        if progress is not None:
            progress(ply, total)

    report.total_moves = len(report.rows)
    report.average_loss = sum(losses) / len(losses) if losses else 0.0
    return report


def report_to_markdown(report: GameReport) -> str:
    h = report.headers
    lines = [
        "# Разбор партии",
        "",
        f"**Белые:** {h.get('White', '?')}  ",
        f"**Чёрные:** {h.get('Black', '?')}  ",
        f"**Результат:** {h.get('Result', '?')}  ",
        f"**Дебют:** {h.get('Opening', '—')} ({h.get('ECO', '—')})",
        "",
        "## Итоги",
        "",
        f"- Ходов проанализировано: **{report.total_moves}**",
        f"- Грубых ошибок (??): **{report.blunders}**",
        f"- Ошибок (?): **{report.mistakes}**",
        f"- Неточностей (?!): **{report.inaccuracies}**",
        f"- Средняя потеря: **{report.average_loss / 100:.2f}** пешки",
        "",
        "## Ходы",
        "",
        "| № | Сторона | Ход | Оценка | Лучший | Потеря | |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in report.rows:
        lines.append(
            f"| {row.number} | {row.color} | {row.san} | {row.eval_after / 100:+.2f} "
            f"| {row.best_san} | {row.loss / 100:.2f} | {row.mark} |"
        )
    lines.append("")
    return "\n".join(lines)
