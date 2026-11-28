#!/usr/bin/env python
"""Локальный сервер шахмат для телефона.

ПК считает Stockfish, телефон открывает страницу в браузере.
Запуск: run-phone.bat
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config  # noqa: E402
from app.engine import Analyzer, fmt_score  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
CFG = config.load()
PORT = int(CFG.get("phone", {}).get("port", 8000))

ANALYZER = Analyzer(CFG["engine_path"])
ANALYZER.configure(int(CFG.get("threads", 2)), int(CFG.get("hash_mb", 256)))
ENGINE_LOCK = threading.Lock()

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def level_time(level: int) -> float:
    """Чем выше уровень, тем дольше думает движок."""
    level = max(1, min(20, int(level)))
    return 0.03 + (level / 20.0) ** 2 * 1.2


def position_payload(board: chess.Board) -> dict:
    legal: dict[str, list[str]] = {}
    for move in board.legal_moves:
        legal.setdefault(chess.square_name(move.from_square), []).append(
            chess.square_name(move.to_square)
        )
    over = board.is_game_over(claim_draw=True)
    return {
        "fen": board.fen(),
        "turn": "w" if board.turn == chess.WHITE else "b",
        "check": board.is_check(),
        "game_over": over,
        "result": board.result() if over else None,
        "legal": legal,
    }


def play_engine(board: chess.Board, level: int) -> tuple[chess.Move | None, str]:
    with ENGINE_LOCK:
        ANALYZER.set_skill(level)
        move = ANALYZER.best_move(board.fen(), movetime=level_time(level))
    if move is None:
        return None, ""
    san = board.san(move)
    board.push(move)
    return move, san


class Handler(BaseHTTPRequestHandler):
    server_version = "ChessPhone/1.0"

    # --- служебное ---------------------------------------------------
    def log_message(self, fmt, *args) -> None:  # noqa: A003
        sys.stdout.write("  %s\n" % (fmt % args))

    def _send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_static(self, name: str) -> None:
        target = (STATIC / name).resolve()
        if not str(target).startswith(str(STATIC)) or not target.is_file():
            self.send_error(404, "not found")
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header(
            "Content-Type", CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        )
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    # --- GET ---------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._send_static("index.html")
            return
        if path == "/api/ping":
            self._send_json({"ok": True, "engine": str(CFG["engine_path"])})
            return
        if path in ("/health", "/healthz"):
            self._send_json({"ok": True, "service": "chess-phone"})
            return
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if path.startswith("/api/"):
            self.send_error(404, "unknown api")
            return
        self._send_static(path.lstrip("/"))

    # --- POST --------------------------------------------------------
    def do_POST(self) -> None:  # noqa: N802
        try:
            body = self._read_json()
            if self.path == "/api/new":
                self._send_json(self._new_game(body))
            elif self.path == "/api/move":
                self._send_json(self._move(body))
            elif self.path == "/api/hint":
                self._send_json(self._hint(body))
            elif self.path == "/api/bot":
                self._send_json(self._bot(body))
            elif self.path == "/api/position":
                self._send_json(position_payload(chess.Board(body["fen"])))
            else:
                self.send_error(404, "unknown api")
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._send_json({"error": str(exc)}, status=500)

    # --- API ---------------------------------------------------------
    def _new_game(self, body: dict) -> dict:
        level = int(body.get("level", 8))
        color = body.get("color", "w")
        engine = bool(body.get("engine", True))
        board = chess.Board()
        payload = position_payload(board)
        if color == "b" and engine:
            move, san = play_engine(board, level)
            payload = position_payload(board)
            payload["engine_move"] = {"uci": move.uci() if move else "", "san": san}
        payload["level"] = level
        payload["color"] = color
        return payload

    def _move(self, body: dict) -> dict:
        board = chess.Board(body["fen"])
        level = int(body.get("level", 8))
        want_reply = bool(body.get("reply", True))
        uci = str(body.get("uci", ""))
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return {"error": "плохой ход"}
        if move not in board.legal_moves:
            return {"error": "нелегальный ход"}
        san = board.san(move)
        board.push(move)

        reply = None
        payload = position_payload(board)
        if want_reply and not payload["game_over"]:
            engine_move, engine_san = play_engine(board, level)
            if engine_move is not None:
                reply = {"uci": engine_move.uci(), "san": engine_san}
                payload = position_payload(board)
        payload["player_san"] = san
        payload["engine_move"] = reply
        return payload

    def _hint(self, body: dict) -> dict:
        board = chess.Board(body["fen"])
        depth = int(body.get("depth", 16))
        if board.is_game_over(claim_draw=True):
            return {"best": None, "score": "—", "pv": ""}
        with ENGINE_LOCK:
            ANALYZER.set_skill(20)
            lines = ANALYZER.analyse(board.fen(), depth=depth, multipv=1)
        if not lines:
            return {"best": None, "score": "—", "pv": ""}
        best = lines[0]
        move = best["pv"][0] if best["pv"] else None
        return {
            "best": {
                "uci": move.uci() if move else "",
                "san": best.get("best_san") or "",
                "from": chess.square_name(move.from_square) if move else "",
                "to": chess.square_name(move.to_square) if move else "",
            },
            "score": fmt_score(best["score"]),
            "pv": best.get("pv_san") or "",
        }

    def _bot(self, body: dict) -> dict:
        board = chess.Board(body["fen"])
        level = int(body.get("level", 8))
        my_level = int(body.get("myLevel", 20))
        want_reply = bool(body.get("reply", True))
        if board.is_game_over(claim_draw=True):
            return position_payload(board)
        move, san = play_engine(board, my_level)
        first = {"uci": move.uci() if move else "", "san": san}
        payload = position_payload(board)
        if want_reply and not payload["game_over"]:
            reply, reply_san = play_engine(board, level)
            payload = position_payload(board)
            if reply is not None:
                payload["reply"] = {"uci": reply.uci(), "san": reply_san}
        payload["engine_move"] = first
        return payload


def local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:  # noqa: BLE001
        return "127.0.0.1"
    finally:
        sock.close()


def main() -> int:
    ip = local_ip()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("=" * 52)
    print("  Шахматы на телефоне")
    print("=" * 52)
    print(f"  На телефоне открой:  http://{ip}:{PORT}")
    print(f"  На этом ПК:          http://127.0.0.1:{PORT}")
    print("  Телефон и ПК — в одной Wi-Fi.")
    print("  Остановить: Ctrl+C")
    print("=" * 52)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено.")
    finally:
        server.server_close()
        ANALYZER.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
