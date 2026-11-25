"""Самопроверка без GUI: движок, репертуар, разбор PGN.

Запуск: .venv\\Scripts\\python.exe tools\\selftest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import chess  # noqa: E402

from app import config  # noqa: E402
from app import openings  # noqa: E402
from app.engine import Analyzer  # noqa: E402
from app.repertoire import Repertoire  # noqa: E402
from app.report import analyse_pgn, report_to_markdown  # noqa: E402

SAMPLE_PGN = """[Event "Test"]
[White "A"]
[Black "B"]
[Result "0-1"]

1. f3 e5 2. g4 Qh4# 0-1
"""


def main() -> int:
    ok = True

    print("1) Импорт GUI-модулей...")
    try:
        from app.board_widget import BoardView  # noqa: F401
        from app.main import MainWindow  # noqa: F401
        print("   ок")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"   ОШИБКА: {exc}")

    print("2) Движок...")
    analyzer = Analyzer(str(config.ENGINE_EXE))
    try:
        lines = analyzer.analyse(chess.STARTING_FEN, depth=12, multipv=3)
        for item in lines:
            print(f"   {item['score_text']:>7}  d{item['depth']}  {item['pv_san']}")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"   ОШИБКА: {exc}")

    print("3) Репертуар...")
    book = Repertoire(config.REPERTOIRE_DIR).load()
    print(f"   дебютов: {len(book.names())} -> {', '.join(book.names()) or '—'}")
    board = chess.Board()
    for san in ["d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4", "d6", "Nf3", "O-O", "Be2", "e5"]:
        board.push_san(san)
    hit = book.lookup(board)
    print(f"   ход для позиции после 6...e5: {hit.san if hit else 'нет'}")

    print("4) Библиотека дебютов...")
    bad = []
    for opening in openings.LIBRARY:
        try:
            opening.board()
        except ValueError as exc:
            bad.append(f"{opening.name}: {exc}")
    print(f"   линий: {len(openings.LIBRARY)}, ошибок: {len(bad)}")
    for problem in bad:
        ok = False
        print(f"   ОШИБКА: {problem}")
    hits = openings.search("найдорф")
    print(f"   поиск «найдорф» -> {hits[0].name if hits else 'нет'}")
    if not hits:
        ok = False

    print("5) Разбор партии...")
    try:
        report = analyse_pgn(SAMPLE_PGN, analyzer, depth=8)
        print(
            f"   ходов: {report.total_moves}, ?? {report.blunders}, "
            f"? {report.mistakes}, ?! {report.inaccuracies}, "
            f"средняя потеря {report.average_loss / 100:.2f}"
        )
        markdown = report_to_markdown(report)
        assert "Разбор партии" in markdown
        print("   markdown-отчёт собран")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"   ОШИБКА: {exc}")
    finally:
        analyzer.quit()

    print("\nИТОГ:", "ВСЁ РАБОТАЕТ" if ok else "ЕСТЬ ОШИБКИ")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
