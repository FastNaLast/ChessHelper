"""Встроенная библиотека дебютов: имена, ECO, ходы в SAN.

Никаких PGN-файлов не нужно: линии зашиты в код. Поиск идёт по русскому
названию, английскому, псевдонимам и по самим ходам («e4 c5»).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import chess


@dataclass(frozen=True)
class Opening:
    eco: str
    name: str
    english: str
    moves: tuple[str, ...]
    aliases: tuple[str, ...] = ()

    @property
    def line(self) -> str:
        """Ходы с номерами: «1. e4 c5 2. Nf3»."""
        board = chess.Board()
        parts: list[str] = []
        for san in self.moves:
            if board.turn == chess.WHITE:
                parts.append(f"{board.fullmove_number}.")
            parts.append(san)
            board.push_san(san)
        return " ".join(parts)

    def board(self) -> chess.Board:
        board = chess.Board()
        for san in self.moves:
            board.push_san(san)
        return board


def _o(eco: str, name: str, english: str, moves: str, *aliases: str) -> Opening:
    return Opening(eco, name, english, tuple(moves.split()), tuple(aliases))


# fmt: off
LIBRARY: tuple[Opening, ...] = (
    # --- ферзевая пешка -------------------------------------------------
    _o("D00", "Дебют ферзевой пешки", "Queen's Pawn Game", "d4 d5", "ферзевая пешка", "d4"),
    _o("D02", "Лондонская система", "London System", "d4 d5 Bf4", "лондон"),
    _o("A48", "Лондонская против Nf6", "London System vs Nf6", "d4 Nf6 Bf4", "лондон"),
    _o("D04", "Система Колле", "Colle System", "d4 d5 Nf3 Nf6 e3", "колле"),
    _o("D06", "Ферзевый гамбит", "Queen's Gambit", "d4 d5 c4", "ферзевый"),
    _o("D30", "Отказанный ферзевый гамбит", "Queen's Gambit Declined", "d4 d5 c4 e6", "ОФГ", "QGD"),
    _o("D20", "Принятый ферзевый гамбит", "Queen's Gambit Accepted", "d4 d5 c4 dxc4", "ПФГ", "QGA"),
    _o("D50", "Ортодоксальная защита", "Orthodox Defense", "d4 d5 c4 e6 Nc3 Nf6 Bg5", "ортодокс"),
    _o("D10", "Славянская защита", "Slav Defense", "d4 d5 c4 c6", "славянка"),
    _o("D13", "Славянская, обмен", "Slav Exchange", "d4 d5 c4 c6 cxd5 cxd5"),
    _o("D48", "Меранский вариант", "Meran Variation", "d4 d5 c4 c6 Nf3 Nf6 Nc3 e6 e3 Nbd7 Bd3 dxc4 Bxc4 b5", "меран"),
    _o("E00", "Каталонское начало", "Catalan Opening", "d4 Nf6 c4 e6 Nf3 d5 g3", "каталон"),
    _o("E01", "Каталонское, открытое", "Open Catalan", "d4 Nf6 c4 e6 g3 d5 Bg2 dxc4"),
    _o("E20", "Защита Нимцовича", "Nimzo-Indian Defense", "d4 Nf6 c4 e6 Nc3 Bb4", "нимцов", "нимцович"),
    _o("E20", "Нимцович, Цюрихский вариант", "Nimzo Zurich", "d4 Nf6 c4 e6 Nc3 Bb4 e3 O-O Bd3 d5 Nf3 c5", "цюрих"),
    _o("E60", "Староиндийская защита", "King's Indian Defense", "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6", "староиндийская", "королевско-индийская", "КИД", "KID"),
    _o("E76", "Староиндийская, четыре пешки", "Four Pawns Attack", "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 f4", "четыре пешки"),
    _o("E90", "Староиндийская, классика", "KID Classical", "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O Be2 e5 O-O", "классическая КИД"),
    _o("E12", "Новоиндийская защита", "Queen's Indian Defense", "d4 Nf6 c4 e6 Nf3 b6", "новоиндийская"),
    _o("D80", "Защита Грюнфельда", "Grünfeld Defense", "d4 Nf6 c4 g6 Nc3 d5", "грюнфельд", "grunfeld"),
    _o("D85", "Грюнфельд, обмен", "Grünfeld Exchange", "d4 Nf6 c4 g6 Nc3 d5 cxd5 Nxd5 e4 Nxc3 bxc3"),
    _o("A56", "Защита Бенони", "Benoni Defense", "d4 Nf6 c4 c5 d5", "бенони"),
    _o("A60", "Современный Бенони", "Modern Benoni", "d4 Nf6 c4 c5 d5 e6"),
    _o("A80", "Голландская защита", "Dutch Defense", "d4 f5", "голландка", "dutch"),
    _o("A87", "Голландская, ленинградская", "Leningrad Dutch", "d4 f5 c4 Nf6 Nc3 g6", "ленинградка"),
    _o("A90", "Голландская, классическая", "Classical Dutch", "d4 f5 c4 e6 Nf3 Nf6 g3"),
    _o("A51", "Будапештский гамбит", "Budapest Gambit", "d4 Nf6 c4 e5", "будапешт"),
    _o("A45", "Дебют Тромповского", "Trompowsky Attack", "d4 Nf6 Bg5", "тромповский", "тромп"),
    _o("D08", "Контргамбит Альбина", "Albin Countergambit", "d4 d5 c4 e5", "альбин"),

    # --- ферзевый фланг -------------------------------------------------
    _o("A10", "Английское начало", "English Opening", "c4", "английское", "англ"),
    _o("A30", "Английское, симметричное", "Symmetrical English", "c4 c5"),
    _o("A29", "Английское, четыре коня", "Four Knights English", "c4 e5 Nc3 Nf6 Nf3 Nc6", "четыре коня"),
    _o("A26", "Английское, Ботвинник", "Botvinnik English", "c4 e5 Nc3 Nf6 g3", "ботвинник"),
    _o("A04", "Дебют Рети", "Réti Opening", "Nf3 d5 c4", "рети", "reti"),
    _o("A02", "Дебют Бёрда", "Bird's Opening", "f4", "берд", "bird"),
    _o("A01", "Дебют Ларсена", "Larsen's Opening", "b3", "ларсен", "larsen"),
    _o("A00", "Дебют Сокольского", "Sokolsky Opening", "b4", "сокольский"),
    _o("A00", "Дебют Гроба", "Grob's Attack", "g4", "гроб", "grob"),

    # --- открытые начала ------------------------------------------------
    _o("B00", "Королевская пешка", "King's Pawn Game", "e4 e5", "e4 e5", "открытая партия"),
    _o("C60", "Испанская партия", "Ruy Lopez", "e4 e5 Nf3 Nc6 Bb5", "испанка", "испанская", "руй лопес", "руй"),
    _o("C65", "Испанская, берлинская", "Berlin Defense", "e4 e5 Nf3 Nc6 Bb5 Nf6", "берлин"),
    _o("C84", "Испанская, закрытая", "Closed Ruy Lopez", "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5 Bb3 d6 c3 O-O", "закрытая испанка"),
    _o("C80", "Испанская, открытая", "Open Ruy Lopez", "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Nxe4", "открытая испанка"),
    _o("C68", "Испанская, размен", "Exchange Ruy Lopez", "e4 e5 Nf3 Nc6 Bb5 a6 Bxc6", "разменная испанка"),
    _o("C50", "Итальянская партия", "Italian Game", "e4 e5 Nf3 Nc6 Bc4", "итальянка", "итальянская"),
    _o("C50", "Итальянская, джиуоко пиано", "Giuoco Piano", "e4 e5 Nf3 Nc6 Bc4 Bc5", "пиано", "тихая итальянка"),
    _o("C50", "Итальянская, пианиссимо", "Giuoco Pianissimo", "e4 e5 Nf3 Nc6 Bc4 Bc5 d3", "пианиссимо"),
    _o("C55", "Защита двух коней", "Two Knights Defense", "e4 e5 Nf3 Nc6 Bc4 Nf6", "два коня"),
    _o("C45", "Шотландская партия", "Scotch Game", "e4 e5 Nf3 Nc6 d4", "шотландка", "шотландская"),
    _o("C45", "Шотландская, Мизес", "Scotch Mieses", "e4 e5 Nf3 Nc6 d4 exd4 Nxd4", "мизес"),
    _o("C25", "Венская партия", "Vienna Game", "e4 e5 Nc3", "венская", "венка"),
    _o("C29", "Венский гамбит", "Vienna Gambit", "e4 e5 Nc3 Nf6 f4", "венский гамбит"),
    _o("C30", "Королевский гамбит", "King's Gambit", "e4 e5 f4", "королевский гамбит", "КГ"),
    _o("C33", "Королевский гамбит, принятый", "King's Gambit Accepted", "e4 e5 f4 exf4", "принятый КГ"),
    _o("C31", "Королевский гамбит, Фалькбеер", "Falkbeer Countergambit", "e4 e5 f4 d5", "фалькбеер"),
    _o("C51", "Гамбит Эванса", "Evans Gambit", "e4 e5 Nf3 Nc6 Bc4 Bc5 b4", "эванс"),
    _o("C23", "Дебют слона", "Bishop's Opening", "e4 e5 Bc4", "слона"),
    _o("C21", "Центральная партия", "Center Game", "e4 e5 d4 exd4", "центральный гамбит", "центр"),
    _o("C21", "Датский гамбит", "Danish Gambit", "e4 e5 d4 exd4 c3", "датский"),
    _o("C44", "Дебют Понциани", "Ponziani Opening", "e4 e5 Nf3 Nc6 c3", "понциани"),
    _o("C42", "Русская партия", "Petrov Defense", "e4 e5 Nf3 Nf6", "петров", "русская"),
    _o("C47", "Дебют четырёх коней", "Four Knights Game", "e4 e5 Nf3 Nc6 Nc3 Nf6", "четыре коня"),

    # --- сицилианская ---------------------------------------------------
    _o("B20", "Сицилианская защита", "Sicilian Defense", "e4 c5", "сицилианка", "сицилианская"),
    _o("B90", "Сицилианская, Найдорф", "Najdorf Variation", "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6", "найдорф"),
    _o("B70", "Сицилианская, дракон", "Dragon Variation", "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 g6", "дракон"),
    _o("B76", "Дракон, югославская атака", "Yugoslav Attack", "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 g6 Be3 Bg7 f3 O-O Qd2 Nc6 Bc4", "югославка"),
    _o("B40", "Сицилианская, Паульсен", "Paulsen Variation", "e4 c5 Nf3 e6 d4 cxd4 Nxd4 Nc6", "паульсен"),
    _o("B47", "Сицилианская, Тайманов", "Taimanov Variation", "e4 c5 Nf3 e6 d4 cxd4 Nxd4 Nc6 Nc3 Qc7", "тайманов"),
    _o("B33", "Сицилианская, Свешников", "Sveshnikov Variation", "e4 c5 Nf3 Nc6 d4 cxd4 Nxd4 Nf6 Nc3 e5", "свешников"),
    _o("B31", "Сицилианская, Россолимо", "Rossolimo Variation", "e4 c5 Nf3 Nc6 Bb5", "россолимо"),
    _o("B23", "Сицилианская, закрытая", "Closed Sicilian", "e4 c5 Nc3", "закрытая сицилианка"),
    _o("B22", "Сицилианская, Алапин", "Alapin Variation", "e4 c5 c3", "алапин"),
    _o("B21", "Сицилианская, Смит-Морра", "Smith-Morra Gambit", "e4 c5 d4 cxd4 c3", "смит морра", "морра"),

    # --- французская и Каро-Канн ----------------------------------------
    _o("C00", "Французская защита", "French Defense", "e4 e6", "француз", "французская"),
    _o("C11", "Французская, классическая", "French Classical", "e4 e6 d4 d5 Nc3 Nf6", "классическая французская"),
    _o("C15", "Французская, Винавер", "Winawer Variation", "e4 e6 d4 d5 Nc3 Bb4", "винавер"),
    _o("C03", "Французская, Тарраш", "Tarrasch Variation", "e4 e6 d4 d5 Nd2", "тарраш"),
    _o("C01", "Французская, размен", "French Exchange", "e4 e6 d4 d5 exd5 exd5", "разменная французская"),
    _o("B10", "Защита Каро-Канн", "Caro-Kann Defense", "e4 c6", "каро", "каро канн", "кароканн"),
    _o("B18", "Каро-Канн, классический", "Caro-Kann Classical", "e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5", "классический каро"),
    _o("B13", "Каро-Канн, атака Панова", "Panov Attack", "e4 c6 d4 d5 exd5 cxd5 c4", "панов"),
    _o("B13", "Каро-Канн, размен", "Caro-Kann Exchange", "e4 c6 d4 d5 exd5 cxd5", "разменный каро"),

    # --- прочие ответы на e4 --------------------------------------------
    _o("B01", "Скандинавская защита", "Scandinavian Defense", "e4 d5", "скандинавка", "скандинавская"),
    _o("B01", "Скандинавская, Ферзь на a5", "Scandinavian Qa5", "e4 d5 exd5 Qxd5 Nc3 Qa5", "скандинавская Qa5"),
    _o("B02", "Защита Алехина", "Alekhine Defense", "e4 Nf6", "алехин"),
    _o("B07", "Защита Пирца", "Pirc Defense", "e4 d6 d4 Nf6 Nc3 g6", "пирц"),
    _o("B06", "Современная защита", "Modern Defense", "e4 g6 d4 Bg7", "современная"),
)
# fmt: on


def _norm(text: str) -> str:
    text = text.lower().replace("ё", "е")
    text = text.replace("grünfeld", "grunfeld")
    return re.sub(r"\s+", " ", text).strip()


_SAN = re.compile(
    r"^(?:[KQRBN][a-h1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?"
    r"|[a-h](?:x[a-h])?[1-8](?:=[QRBN])?[+#]?"
    r"|O-O(?:-O)?[+#]?)$"
)


def _as_line(query: str) -> str | None:
    """«1. e4 c5» -> «e4 c5», если запрос похож на ходы."""
    tokens = [t for t in query.split() if not re.fullmatch(r"\d+\.(?:\.\.)?", t)]
    if tokens and all(_SAN.match(t) for t in tokens):
        return " ".join(tokens)
    return None


def search(query: str, limit: int = 40) -> list[Opening]:
    """Поиск по названию, псевдонимам или началу партии."""
    q = _norm(query)
    if not q:
        return list(LIBRARY[:limit])

    line = _as_line(q)
    scored: list[tuple[int, Opening]] = []
    for opening in LIBRARY:
        score = 0
        name = _norm(opening.name)
        english = _norm(opening.english)
        short = re.sub(r"^(?:защита|дебют|система|гамбит|начало)\s+", "", name)
        if name.startswith(q) or english.startswith(q) or short.startswith(q):
            score = 100
        elif q in name or q in english or q in short:
            score = 70
        elif any(q in _norm(alias) for alias in opening.aliases):
            score = 60
        if line:
            moves = " ".join(opening.moves)
            if moves.startswith(line):
                score = max(score, 90 if moves == line else 85)
        elif q in " ".join(opening.moves).lower():
            score = max(score, 40)
        if score:
            scored.append((score, opening))

    scored.sort(key=lambda pair: (-pair[0], len(pair[1].name), pair[1].name))
    return [opening for _, opening in scored[:limit]]


def find(name: str) -> Opening | None:
    """Точное (или единственное) совпадение по названию."""
    q = _norm(name)
    for opening in LIBRARY:
        if q in (_norm(opening.name), _norm(opening.english)):
            return opening
    hits = search(name, limit=2)
    return hits[0] if len(hits) == 1 else None
