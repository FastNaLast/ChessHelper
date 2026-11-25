"use strict";

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const FILES = "abcdefgh";
const GLYPH = { k: "\u265A", q: "\u265B", r: "\u265C", b: "\u265D", n: "\u265E", p: "\u265F" };

const boardEl = document.getElementById("board");
const statusEl = document.getElementById("status");
const evalEl = document.getElementById("eval");
const hintEl = document.getElementById("hintText");
const levelEl = document.getElementById("level");
const colorEl = document.getElementById("colorSide");
const promoEl = document.getElementById("promo");

const S = {
  fen: START,
  level: 8,
  color: "w",
  turn: "w",
  legal: {},
  selected: null,
  last: null,
  hint: null,
  history: [],
  busy: false,
  over: false,
  check: false,
  result: null,
  pendingPromo: null,
};

function parseFen(fen) {
  const pieces = {};
  const rows = fen.split(" ")[0].split("/");
  rows.forEach((row, index) => {
    let file = 0;
    for (const ch of row) {
      if (/\d/.test(ch)) {
        file += parseInt(ch, 10);
      } else {
        pieces[FILES[file] + (8 - index)] = ch;
        file += 1;
      }
    }
  });
  return pieces;
}

function isMine(piece) {
  const white = piece === piece.toUpperCase();
  return (S.color === "w") === white;
}

function render() {
  const pieces = parseFen(S.fen);
  boardEl.innerHTML = "";

  for (let row = 0; row < 8; row++) {
    for (let col = 0; col < 8; col++) {
      const fileIdx = S.color === "w" ? col : 7 - col;
      const rankIdx = S.color === "w" ? 7 - row : row;
      const name = FILES[fileIdx] + (rankIdx + 1);

      const sq = document.createElement("div");
      sq.className = "sq " + ((fileIdx + rankIdx) % 2 === 1 ? "light" : "dark");
      sq.dataset.square = name;

      if (S.last && (S.last.from === name || S.last.to === name)) sq.classList.add("last");
      if (S.selected === name) sq.classList.add("sel");
      if (S.hint) {
        if (S.hint.from === name) sq.classList.add("hint-a");
        if (S.hint.to === name) sq.classList.add("hint-b");
      }

      const piece = pieces[name];
      if (piece) {
        const span = document.createElement("span");
        span.textContent = GLYPH[piece.toLowerCase()];
        span.className = piece === piece.toUpperCase() ? "piece-white" : "piece-black";
        sq.appendChild(span);
      }

      if (S.selected && (S.legal[S.selected] || []).includes(name)) {
        const marker = document.createElement("span");
        marker.className = piece ? "capture-ring" : "dot";
        sq.appendChild(marker);
      }

      sq.addEventListener("click", () => onSquare(name));
      boardEl.appendChild(sq);
    }
  }

  if (S.check) {
    const king = S.turn === "w" ? "K" : "k";
    for (const [square, piece] of Object.entries(pieces)) {
      if (piece === king) {
        const node = boardEl.querySelector('[data-square="' + square + '"]');
        if (node) node.classList.add("check");
      }
    }
  }

  updateStatus();
}

function updateStatus() {
  if (S.over) {
    statusEl.textContent = "Партия окончена" + (S.result ? " — " + S.result : "");
    return;
  }
  const mine = S.turn === S.color;
  statusEl.textContent = (mine ? "Твой ход" : "Ход Stockfish…") + (S.check ? " · шах" : "");
}

async function api(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}

function applyPayload(payload) {
  S.fen = payload.fen;
  S.legal = payload.legal || {};
  S.turn = payload.turn;
  S.check = Boolean(payload.check);
  S.over = Boolean(payload.game_over);
  S.result = payload.result || null;
  S.selected = null;
}

function setBusy(busy) {
  S.busy = busy;
  for (const id of ["hintBtn", "botBtn", "undoBtn", "newGame"]) {
    document.getElementById(id).disabled = busy;
  }
}

function onSquare(name) {
  if (S.busy || S.over || S.pendingPromo) return;
  const pieces = parseFen(S.fen);
  const piece = pieces[name];

  if (S.selected) {
    const targets = S.legal[S.selected] || [];
    if (targets.includes(name)) {
      doMove(S.selected, name);
      return;
    }
    if (S.selected === name) {
      S.selected = null;
      render();
      return;
    }
  }

  if (piece && S.turn === S.color && isMine(piece)) {
    S.selected = name;
    S.hint = null;
    render();
  }
}

function doMove(from, to) {
  const pieces = parseFen(S.fen);
  const piece = pieces[from];
  const toRank = parseInt(to[1], 10);
  if (piece && piece.toLowerCase() === "p" && (toRank === 8 || toRank === 1)) {
    S.pendingPromo = { from, to };
    promoEl.classList.remove("hidden");
    return;
  }
  sendMove(from + to);
}

async function sendMove(uci) {
  setBusy(true);
  S.hint = null;
  S.selected = null;
  hintEl.textContent = "";
  try {
    const payload = await api("/api/move", { fen: S.fen, uci, level: S.level });
    S.history.push(S.fen);
    S.last = { from: uci.slice(0, 2), to: uci.slice(2, 4) };
    applyPayload(payload);
    if (payload.engine_move && payload.engine_move.uci) {
      S.last = { from: payload.engine_move.uci.slice(0, 2), to: payload.engine_move.uci.slice(2, 4) };
    }
    render();
  } catch (error) {
    hintEl.textContent = "Ошибка: " + error.message;
    render();
  } finally {
    setBusy(false);
  }
}

async function doHint() {
  if (S.busy || S.over) return;
  setBusy(true);
  hintEl.textContent = "Считаю…";
  try {
    const payload = await api("/api/hint", { fen: S.fen, depth: 16 });
    if (payload.best && payload.best.from) {
      S.hint = { from: payload.best.from, to: payload.best.to };
      hintEl.textContent =
        "Лучший ход: " + payload.best.san + "   (" + payload.score + ")\n" + (payload.pv || "");
    } else {
      S.hint = null;
      hintEl.textContent = "Подсказок нет.";
    }
    evalEl.textContent = payload.score || evalEl.textContent;
    render();
  } catch (error) {
    hintEl.textContent = "Ошибка: " + error.message;
  } finally {
    setBusy(false);
  }
}

async function doBot() {
  if (S.busy || S.over) return;
  setBusy(true);
  S.hint = null;
  hintEl.textContent = "Stockfish играет за тебя…";
  try {
    const payload = await api("/api/bot", { fen: S.fen, level: S.level, myLevel: 20 });
    S.history.push(S.fen);
    applyPayload(payload);
    let text = "";
    if (payload.engine_move && payload.engine_move.uci) {
      text = "Сыграно: " + payload.engine_move.san;
      S.last = { from: payload.engine_move.uci.slice(0, 2), to: payload.engine_move.uci.slice(2, 4) };
    }
    if (payload.reply && payload.reply.uci) {
      text += " · ответ: " + payload.reply.san;
      S.last = { from: payload.reply.uci.slice(0, 2), to: payload.reply.uci.slice(2, 4) };
    }
    hintEl.textContent = text;
    render();
  } catch (error) {
    hintEl.textContent = "Ошибка: " + error.message;
  } finally {
    setBusy(false);
  }
}

async function newGame() {
  S.color = colorEl.value;
  S.level = parseInt(levelEl.value, 10);
  S.history = [];
  S.selected = null;
  S.hint = null;
  S.last = null;
  S.result = null;
  hintEl.textContent = "";
  setBusy(true);
  try {
    const payload = await api("/api/new", { color: S.color, level: S.level });
    applyPayload(payload);
    if (payload.engine_move && payload.engine_move.uci) {
      S.last = { from: payload.engine_move.uci.slice(0, 2), to: payload.engine_move.uci.slice(2, 4) };
    }
    evalEl.textContent = "+0.00";
    render();
  } catch (error) {
    hintEl.textContent = "Ошибка: " + error.message;
  } finally {
    setBusy(false);
  }
}

async function doUndo() {
  if (S.busy || !S.history.length) return;
  let fen = S.history.pop();
  while (S.history.length && fen.split(" ")[1] !== S.color) {
    fen = S.history.pop();
  }
  setBusy(true);
  S.hint = null;
  S.last = null;
  try {
    const payload = await api("/api/position", { fen });
    applyPayload(payload);
    render();
  } catch (error) {
    hintEl.textContent = "Ошибка: " + error.message;
  } finally {
    setBusy(false);
  }
}

promoEl.querySelectorAll("button").forEach((button) => {
  button.addEventListener("click", () => {
    const promo = button.dataset.piece;
    const pending = S.pendingPromo;
    S.pendingPromo = null;
    promoEl.classList.add("hidden");
    if (pending) sendMove(pending.from + pending.to + promo);
  });
});

for (let level = 1; level <= 20; level++) {
  const option = document.createElement("option");
  option.value = String(level);
  option.textContent = "Уровень " + level;
  if (level === 8) option.selected = true;
  levelEl.appendChild(option);
}

document.getElementById("hintBtn").addEventListener("click", doHint);
document.getElementById("botBtn").addEventListener("click", doBot);
document.getElementById("undoBtn").addEventListener("click", doUndo);
document.getElementById("newGame").addEventListener("click", newGame);
colorEl.addEventListener("change", () => {
  S.color = colorEl.value;
  render();
});

newGame();
