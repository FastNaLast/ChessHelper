"""Шахматный помощник: оверлей поверх окон, Stockfish, разбор PGN, репертуар."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import chess
import chess.pgn
from PySide6.QtCore import QPoint, QSize, Qt, QThread, Signal
from PySide6.QtGui import QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizeGrip,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import config, openings
from .board_widget import BoardView
from .camera import FrameView, StreamReader, draw_grid, np_to_qimage, split_cells, warp_board
from .capture import RegionSelector, grab_region
from .engine import Analyzer
from .hotkey import GlobalHotkey
from .report import analyse_pgn, report_to_markdown
from .repertoire import Repertoire

STYLE = """
QWidget { background: #1E1F22; color: #E8E8E8; font-size: 12px; }
QTabWidget::pane { border: 1px solid #2F3136; border-radius: 6px; }
QTabBar::tab { background: #26282C; padding: 6px 10px; border-radius: 4px; margin-right: 2px; }
QTabBar::tab:selected { background: #3B6E3B; }
QLineEdit, QSpinBox, QComboBox, QTextEdit, QTextBrowser {
    background: #26282C; border: 1px solid #34363B; border-radius: 4px; padding: 4px;
}
QPushButton { background: #2F3136; border: 1px solid #3C3F45; border-radius: 5px; padding: 6px 10px; }
QPushButton:hover { background: #3A3D43; }
QPushButton:disabled { color: #77797E; }
QPushButton#primary { background: #3B6E3B; border-color: #4C8A4C; font-weight: bold; }
QPushButton#primary:hover { background: #478347; }
QToolButton { background: transparent; border: none; font-size: 14px; padding: 2px 6px; }
QToolButton:hover { background: #2F3136; border-radius: 4px; }
QLabel#title { font-weight: bold; font-size: 13px; }
QLabel#hint { color: #9AA0A6; }
"""


class AnalyseJob(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, analyzer: Analyzer, fen: str, depth: int, multipv: int, parent=None) -> None:
        super().__init__(parent)
        self.analyzer = analyzer
        self.fen = fen
        self.depth = depth
        self.multipv = multipv

    def run(self) -> None:  # noqa: D401
        try:
            self.done.emit(self.analyzer.analyse(self.fen, self.depth, self.multipv))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class ReportJob(QThread):
    progress = Signal(int, int)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, analyzer: Analyzer, text: str, depth: int, parent=None) -> None:
        super().__init__(parent)
        self.analyzer = analyzer
        self.text = text
        self.depth = depth

    def run(self) -> None:  # noqa: D401
        try:
            report = analyse_pgn(
                self.text, self.analyzer, depth=self.depth, progress=self.progress.emit
            )
            self.done.emit(report)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__(
            None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.cfg = config.load()
        self.analyzer = Analyzer(self.cfg["engine_path"])
        self.analyzer.configure(self.cfg["threads"], self.cfg["hash_mb"])
        self.repertoire = Repertoire(config.REPERTOIRE_DIR).load()

        self.board = chess.Board()
        self.last_move: chess.Move | None = None
        self._drag_offset: QPoint | None = None
        self._job: AnalyseJob | None = None
        self._report_job: ReportJob | None = None
        self._stream: StreamReader | None = None
        self._warp_label: QLabel | None = None
        self.pgn_text = ""
        self._last_report_markdown = ""

        self.setStyleSheet(STYLE)
        self.setWindowTitle("Шахматный помощник")
        self.setMinimumSize(470, 560)
        self._build_ui()
        self._restore_geometry()
        self._refresh_books()
        self._update_book_hint()

        self.hotkey = GlobalHotkey(self, ord("H"), self.toggle_visibility)
        self.hotkey_ok = self.hotkey.register()
        hint = "Ctrl+Alt+H — скрыть/показать окно."
        self._set_status(
            ("Готов. " + hint) if self.hotkey_ok
            else "Готов. Хоткей Ctrl+Alt+H занят другой программой."
        )

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(4)
        title = QLabel("\u265E Шахматный помощник")
        title.setObjectName("title")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        header.addWidget(title)
        header.addStretch(1)

        self.pin_btn = QToolButton()
        self.pin_btn.setText("\U0001F4CC")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setChecked(bool(self.cfg["always_on_top"]))
        self.pin_btn.setToolTip("Поверх всех окон")
        self.pin_btn.toggled.connect(self._toggle_on_top)
        header.addWidget(self.pin_btn)

        min_btn = QToolButton()
        min_btn.setText("\u2013")
        min_btn.setToolTip("Свернуть")
        min_btn.clicked.connect(self.showMinimized)
        header.addWidget(min_btn)

        close_btn = QToolButton()
        close_btn.setText("\u2715")
        close_btn.setToolTip("Закрыть")
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_analysis_tab(), "Анализ")
        self.tabs.addTab(self._build_pgn_tab(), "Партия")
        self.tabs.addTab(self._build_book_tab(), "Дебют")
        self.tabs.addTab(self._build_camera_tab(), "Камера")
        self.tabs.addTab(self._build_screen_tab(), "Экран")
        root.addWidget(self.tabs, 1)

        footer = QHBoxLayout()
        footer.setSpacing(6)
        footer.addWidget(QLabel("Прозрачность"))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(30, 100)
        self.opacity_slider.setValue(int(self.cfg["opacity"] * 100))
        self.opacity_slider.valueChanged.connect(self._apply_opacity)
        footer.addWidget(self.opacity_slider, 1)
        root.addLayout(footer)

        size_row = QHBoxLayout()
        size_row.setSpacing(6)
        size_row.addWidget(QLabel("Размер"))
        minus_btn = QToolButton()
        minus_btn.setText("\u2212")
        minus_btn.setToolTip("Окно меньше (10%)")
        minus_btn.setAutoRepeat(True)
        minus_btn.setAutoRepeatDelay(400)
        minus_btn.setAutoRepeatInterval(90)
        minus_btn.clicked.connect(lambda: self._resize_step(0.9))
        size_row.addWidget(minus_btn)

        self.size_label = QLabel("")
        self.size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.size_label.setMinimumWidth(66)
        self.size_label.setToolTip("Текущий размер окна. Кнопки − и + меняют его на 10%.")
        size_row.addWidget(self.size_label)

        plus_btn = QToolButton()
        plus_btn.setText("+")
        plus_btn.setToolTip("Окно больше (10%)")
        plus_btn.setAutoRepeat(True)
        plus_btn.setAutoRepeatDelay(400)
        plus_btn.setAutoRepeatInterval(90)
        plus_btn.clicked.connect(lambda: self._resize_step(1.1))
        size_row.addWidget(plus_btn)
        size_row.addStretch(1)

        grip = QSizeGrip(self)
        grip.setFixedSize(14, 14)
        size_row.addWidget(grip)
        root.addLayout(size_row)

        self.status = QLabel("")
        self.status.setObjectName("hint")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self._update_size_label()
        self._apply_opacity(self.opacity_slider.value())

    def _build_analysis_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(6)

        self.fen_edit = QLineEdit(chess.STARTING_FEN)
        self.fen_edit.returnPressed.connect(self.apply_fen)
        layout.addWidget(self.fen_edit)

        row = QHBoxLayout()
        apply_btn = QPushButton("Применить FEN")
        apply_btn.clicked.connect(self.apply_fen)
        row.addWidget(apply_btn)

        paste_btn = QPushButton("Из буфера")
        paste_btn.clicked.connect(self.paste_fen)
        row.addWidget(paste_btn)

        start_btn = QPushButton("Начальная")
        start_btn.clicked.connect(self.reset_board)
        row.addWidget(start_btn)

        flip_btn = QPushButton("Перевернуть")
        flip_btn.clicked.connect(self.flip_board)
        row.addWidget(flip_btn)
        layout.addLayout(row)

        self.board_view = BoardView()
        layout.addWidget(self.board_view, 1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Глубина"))
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(6, 40)
        self.depth_spin.setValue(int(self.cfg["depth"]))
        row2.addWidget(self.depth_spin)

        row2.addWidget(QLabel("Линий"))
        self.multipv_spin = QSpinBox()
        self.multipv_spin.setRange(1, 5)
        self.multipv_spin.setValue(int(self.cfg["multipv"]))
        row2.addWidget(self.multipv_spin)

        self.auto_check = QCheckBox("Сразу анализировать")
        self.auto_check.setChecked(True)
        row2.addWidget(self.auto_check)
        layout.addLayout(row2)

        self.analyse_btn = QPushButton("Анализировать")
        self.analyse_btn.setObjectName("primary")
        self.analyse_btn.clicked.connect(self.start_analysis)
        layout.addWidget(self.analyse_btn)

        self.result_edit = QTextEdit()
        self.result_edit.setReadOnly(True)
        self.result_edit.setMinimumHeight(60)
        layout.addWidget(self.result_edit)
        return page

    def _build_pgn_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(6)

        row = QHBoxLayout()
        open_btn = QPushButton("Открыть PGN")
        open_btn.clicked.connect(self.open_pgn)
        row.addWidget(open_btn)
        paste_btn = QPushButton("Из буфера")
        paste_btn.setToolTip("Вставь PGN, скопированный с chess.com или Lichess")
        paste_btn.clicked.connect(self.paste_pgn)
        row.addWidget(paste_btn)
        self.pgn_label = QLabel("файл не выбран")
        self.pgn_label.setObjectName("hint")
        self.pgn_label.setWordWrap(True)
        row.addWidget(self.pgn_label, 1)
        layout.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Глубина"))
        self.report_depth = QSpinBox()
        self.report_depth.setRange(6, 24)
        self.report_depth.setValue(int(self.cfg["report_depth"]))
        row2.addWidget(self.report_depth)
        self.report_btn = QPushButton("Разобрать партию")
        self.report_btn.setObjectName("primary")
        self.report_btn.clicked.connect(self.start_report)
        row2.addWidget(self.report_btn, 1)
        layout.addLayout(row2)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.report_view = QTextBrowser()
        self.report_view.setOpenExternalLinks(False)
        layout.addWidget(self.report_view, 1)

        save_btn = QPushButton("Сохранить отчёт в reports/")
        save_btn.clicked.connect(self.save_report)
        layout.addWidget(save_btn)
        return page

    def _build_book_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(6)

        hint = QLabel(
            f"Библиотека дебютов ({len(openings.LIBRARY)} линий): напиши название — "
            "файлы не нужны. Можно искать по ходам: «e4 c5»."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.open_search = QLineEdit()
        self.open_search.setPlaceholderText("сицилианская, лондон, каро-канн, e4 c5…")
        self.open_search.setClearButtonEnabled(True)
        self.open_search.textChanged.connect(self._filter_openings)
        self.open_search.returnPressed.connect(self.load_opening)
        layout.addWidget(self.open_search)

        self.open_list = QListWidget()
        self.open_list.setMaximumHeight(138)
        self.open_list.setWordWrap(True)
        self.open_list.setTextElideMode(Qt.ElideRight)
        self.open_list.itemDoubleClicked.connect(lambda _item: self.load_opening())
        layout.addWidget(self.open_list)

        load_btn = QPushButton("Поставить дебют на доску")
        load_btn.setObjectName("primary")
        load_btn.clicked.connect(self.load_opening)
        layout.addWidget(load_btn)

        pgn_hint = QLabel("Мой репертуар из PGN (необязательно)")
        pgn_hint.setObjectName("hint")
        layout.addWidget(pgn_hint)

        row = QHBoxLayout()
        self.book_combo = QComboBox()
        self.book_combo.currentIndexChanged.connect(self._update_book_hint)
        row.addWidget(self.book_combo, 1)
        reload_btn = QPushButton("Обновить")
        reload_btn.clicked.connect(self._reload_books)
        row.addWidget(reload_btn)
        layout.addLayout(row)

        self.book_status = QLabel("")
        self.book_status.setWordWrap(True)
        layout.addWidget(self.book_status)

        row2 = QHBoxLayout()
        play_btn = QPushButton("Сделать книжный ход")
        play_btn.clicked.connect(self.play_book_move)
        row2.addWidget(play_btn)
        back_btn = QPushButton("Назад")
        back_btn.clicked.connect(self.undo_move)
        row2.addWidget(back_btn)
        layout.addLayout(row2)

        self.book_log = QTextEdit()
        self.book_log.setReadOnly(True)
        layout.addWidget(self.book_log, 1)

        self._filter_openings()
        return page

    def _build_camera_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(6)

        hint = QLabel(
            "Телефон над доской: поставь IP Webcam (Android) или DroidCam, возьми URL потока. "
            "IP Webcam: http://ТЕЛЕФОН:8080/video   DroidCam: http://ТЕЛЕФОН:4747/video"
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        row = QHBoxLayout()
        self.cam_url = QLineEdit(self.cfg["camera"]["url"])
        row.addWidget(self.cam_url, 1)
        self.cam_btn = QPushButton("Подключить")
        self.cam_btn.clicked.connect(self.toggle_camera)
        row.addWidget(self.cam_btn)
        layout.addLayout(row)

        self.cam_view = FrameView()
        self.cam_view.clicked.connect(self.add_corner)
        layout.addWidget(self.cam_view, 1)

        self.cam_status = QLabel(
            "Нажми «Подключить», затем отметь 4 угла доски: "
            "1 — a8, 2 — h8, 3 — h1, 4 — a1 (по часовой стрелке)."
        )
        self.cam_status.setObjectName("hint")
        self.cam_status.setWordWrap(True)
        layout.addWidget(self.cam_status)

        row2 = QHBoxLayout()
        reset_btn = QPushButton("Сбросить углы")
        reset_btn.clicked.connect(self.reset_corners)
        row2.addWidget(reset_btn)
        grid_btn = QPushButton("Проверить сетку")
        grid_btn.clicked.connect(self.test_grid)
        row2.addWidget(grid_btn)
        cells_btn = QPushButton("Сохранить клетки")
        cells_btn.clicked.connect(self.save_cells)
        row2.addWidget(cells_btn)
        layout.addLayout(row2)

        corners = self.cfg["camera"].get("corners") or []
        if len(corners) == 4:
            self.cam_view.set_points([(float(x), float(y)) for x, y in corners])
        return page

    def _build_screen_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(6)

        hint = QLabel(
            "Выдели область доски в приложении chess.com. Снимок сохраняется в "
            "reports\\capture.png — по нему настраивается распознавание."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        geo = QHBoxLayout()
        self.cap_spins: dict[str, QSpinBox] = {}
        for key, label in (("x", "X"), ("y", "Y"), ("w", "Ш"), ("h", "В")):
            geo.addWidget(QLabel(label))
            spin = QSpinBox()
            spin.setRange(-10000, 20000)
            spin.setValue(int(self.cfg["capture"][key]))
            geo.addWidget(spin)
            self.cap_spins[key] = spin
        layout.addLayout(geo)

        row = QHBoxLayout()
        select_btn = QPushButton("Выбрать область мышью")
        select_btn.clicked.connect(self.select_region)
        row.addWidget(select_btn)
        grab_btn = QPushButton("Захватить")
        grab_btn.setObjectName("primary")
        grab_btn.clicked.connect(self.capture_region)
        row.addWidget(grab_btn)
        layout.addLayout(row)

        self.preview = QLabel("превью")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(200)
        self.preview.setStyleSheet("background: #26282C; border: 1px solid #34363B;")
        layout.addWidget(self.preview, 1)
        return page

    # -------------------------------------------------------------- window
    def _restore_geometry(self) -> None:
        win = self.cfg.get("window", {})
        width = int(win.get("w") or 470)
        height = int(win.get("h") or 720)
        screens = QGuiApplication.screens()
        available = screens[0].availableGeometry() if screens else None
        if available is not None:
            width = min(width, max(320, available.width() - 24))
            height = min(height, max(360, available.height() - 24))
        x = win.get("x")
        y = win.get("y")
        if x is not None and y is not None:
            x, y = int(x), int(y)
            center = QPoint(x + width // 2, y + height // 2)
            if QGuiApplication.screenAt(center) is None:
                x = y = None
        if x is None and available is not None:
            x = available.right() - width - 16
        if y is None and available is not None:
            y = available.top() + 40
        self.setGeometry(int(x if x is not None else 100), int(y if y is not None else 100), width, height)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 40:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, _event) -> None:  # noqa: N802
        self._drag_offset = None

    def _toggle_on_top(self, checked: bool) -> None:
        self.cfg["always_on_top"] = bool(checked)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked)
        self.show()

    def _apply_opacity(self, value: int) -> None:
        self.setWindowOpacity(max(0.3, value / 100.0))

    def _update_size_label(self) -> None:
        self.size_label.setText(f"{self.width()}\u00d7{self.height()}")

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "size_label"):
            self._update_size_label()

    def _resize_step(self, factor: float) -> None:
        """Меняет размер окна на factor, не выпуская его за пределы экрана."""
        screen = QGuiApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        width = max(self.minimumWidth(), int(round(self.width() * factor)))
        height = max(self.minimumHeight(), int(round(self.height() * factor)))
        if available is not None:
            width = min(width, available.width() - 16)
            height = min(height, available.height() - 16)
        else:
            width = max(width, self.minimumWidth())
            height = max(height, self.minimumHeight())
        if width == self.width() and height == self.height():
            return
        x, y = self.x(), self.y()
        if available is not None:
            x = min(max(x, available.left()), available.right() - width + 1)
            y = min(max(y, available.top()), available.bottom() - height + 1)
        self.setGeometry(x, y, width, height)

    def _set_status(self, text: str) -> None:
        self.status.setText(text)

    def toggle_visibility(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    # --------------------------------------------------------------- board
    def apply_fen(self) -> None:
        text = self.fen_edit.text().strip()
        try:
            board = chess.Board(text)
        except ValueError as exc:
            QMessageBox.warning(self, "FEN", f"Неверный FEN: {exc}")
            return
        self.board = board
        self.last_move = None
        self.board_view.set_board(self.board, None)
        self._update_book_hint()
        self.result_edit.clear()
        if self.auto_check.isChecked() and not self.board.is_game_over(claim_draw=False):
            self.start_analysis()

    def paste_fen(self) -> None:
        text = QGuiApplication.clipboard().text().strip()
        if text:
            self.fen_edit.setText(text)
            self.apply_fen()

    def reset_board(self) -> None:
        self.fen_edit.setText(chess.STARTING_FEN)
        self.apply_fen()

    def flip_board(self) -> None:
        self.board_view.set_flipped(not self.board_view.flipped)

    def undo_move(self) -> None:
        if self.board.move_stack:
            self.board.pop()
            self.last_move = self.board.move_stack[-1] if self.board.move_stack else None
            self.fen_edit.setText(self.board.fen())
            self.board_view.set_board(self.board, self.last_move)
            self._update_book_hint()

    # ------------------------------------------------------------ analysis
    def start_analysis(self) -> None:
        if self._job is not None and self._job.isRunning():
            return
        fen = self.fen_edit.text().strip() or self.board.fen()
        try:
            self.board = chess.Board(fen)
        except ValueError:
            QMessageBox.warning(self, "FEN", "Неверный FEN.")
            return
        self.board_view.set_board(self.board, self.last_move)
        self.analyse_btn.setEnabled(False)
        self._set_status("Анализирую… (Stockfish)")
        self._job = AnalyseJob(
            self.analyzer, fen, self.depth_spin.value(), self.multipv_spin.value(), self
        )
        self._job.done.connect(self._on_analysis)
        self._job.failed.connect(self._on_analysis_failed)
        self._job.start()

    def _on_analysis(self, results) -> None:
        self.analyse_btn.setEnabled(True)
        if not results:
            self.result_edit.setPlainText("Позиция закончилась.")
            self._set_status("Игра окончена.")
            return
        lines = []
        for index, item in enumerate(results, start=1):
            depth = item.get("depth") or self.depth_spin.value()
            lines.append(
                f"{index}. {item['score_text']}  (d{depth})  {item['pv_san'] or item['best_san']}"
            )
        self.result_edit.setPlainText("\n".join(lines))
        best = results[0]
        self._set_status(f"Лучший ход: {best['best_san'] or '—'}   оценка {best['score_text']}")

    def _on_analysis_failed(self, message: str) -> None:
        self.analyse_btn.setEnabled(True)
        self._set_status("Ошибка движка")
        QMessageBox.critical(self, "Stockfish", message)

    # ----------------------------------------------------------------- PGN
    def open_pgn(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Открыть PGN", str(Path.home()), "PGN (*.pgn);;Все файлы (*)"
        )
        if not path:
            return
        try:
            self.pgn_text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            QMessageBox.critical(self, "PGN", str(exc))
            return
        self.pgn_label.setText(Path(path).name)
        self._set_status("PGN загружен. Нажми «Разобрать партию».")

    def paste_pgn(self) -> None:
        text = QGuiApplication.clipboard().text().strip()
        if not text:
            QMessageBox.information(
                self, "PGN", "Буфер обмена пуст. Скопируй партию на chess.com (Share → PGN)."
            )
            return
        game = chess.pgn.read_game(io.StringIO(text))
        moves = len(list(game.mainline())) if game is not None else 0
        if moves == 0:
            QMessageBox.warning(
                self, "PGN", "В буфере нет PGN-партии. Нужен текст с ходами вида «1. e4 e5»."
            )
            return
        self.pgn_text = text
        self.pgn_label.setText(f"из буфера · ходов: {moves}")
        self._set_status("PGN из буфера загружен. Нажми «Разобрать партию».")

    def start_report(self) -> None:
        if not self.pgn_text:
            QMessageBox.information(self, "PGN", "Сначала открой PGN-файл.")
            return
        if self._report_job is not None and self._report_job.isRunning():
            return
        self.report_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self._set_status("Разбираю партию… это может занять пару минут.")
        self._report_job = ReportJob(
            self.analyzer, self.pgn_text, self.report_depth.value(), self
        )
        self._report_job.progress.connect(self._on_report_progress)
        self._report_job.done.connect(self._on_report_done)
        self._report_job.failed.connect(self._on_report_failed)
        self._report_job.start()

    def _on_report_progress(self, current: int, total: int) -> None:
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(current)
            self._set_status(f"Разбор: {current}/{total} полуходов")

    def _on_report_done(self, report) -> None:
        self.report_btn.setEnabled(True)
        self.progress.setVisible(False)
        self._last_report_markdown = report_to_markdown(report)
        self.report_view.setMarkdown(self._last_report_markdown)
        self.tabs.setCurrentIndex(1)
        self._set_status(
            f"Готово: {report.total_moves} ходов, ?? {report.blunders}, ? {report.mistakes}, "
            f"?! {report.inaccuracies}"
        )

    def _on_report_failed(self, message: str) -> None:
        self.report_btn.setEnabled(True)
        self.progress.setVisible(False)
        QMessageBox.critical(self, "Разбор", message)

    def save_report(self) -> None:
        if not self._last_report_markdown:
            QMessageBox.information(self, "Отчёт", "Отчёта пока нет.")
            return
        base = self.pgn_label.text() or "game"
        name = Path(base).stem + "-analysis.md"
        target = config.REPORTS / name
        target.write_text(self._last_report_markdown, encoding="utf-8")
        self._set_status(f"Сохранено: {target}")

    # ----------------------------------------------------------- repertoire
    def _filter_openings(self) -> None:
        query = self.open_search.text().strip()
        hits = openings.search(query)
        self.open_list.clear()
        for opening in hits:
            item = QListWidgetItem(f"{opening.name} · {opening.eco}\n{opening.line}")
            item.setData(Qt.UserRole, opening)
            item.setToolTip(f"{opening.english}\n{opening.line}")
            item.setSizeHint(QSize(0, 44))
            self.open_list.addItem(item)
        if hits:
            self.open_list.setCurrentRow(0)
        elif query:
            self.open_list.addItem(QListWidgetItem("Ничего не найдено — попробуй другое название"))

    def load_opening(self) -> None:
        item = self.open_list.currentItem()
        opening = item.data(Qt.UserRole) if item is not None else None
        if not isinstance(opening, openings.Opening):
            self._set_status("Выбери дебют из списка или напиши название.")
            return
        try:
            board = opening.board()
        except ValueError as exc:
            QMessageBox.warning(self, "Дебют", f"Не удалось прочитать линию: {exc}")
            return
        self.board = board
        self.last_move = board.peek() if board.move_stack else None
        self.fen_edit.setText(board.fen())
        self.board_view.set_board(board, self.last_move)
        self.book_log.append(f"{opening.name} ({opening.eco}, {opening.english})\n   {opening.line}")
        self._set_status(
            f"Дебют: {opening.name} · {opening.eco} · ходов {len(opening.moves)}"
        )
        self._update_book_hint()
        if self.auto_check.isChecked():
            self.start_analysis()

    def _refresh_books(self) -> None:
        self.book_combo.blockSignals(True)
        self.book_combo.clear()
        self.book_combo.addItem("Все дебюты", None)
        for name in self.repertoire.names():
            self.book_combo.addItem(name, name)
        self.book_combo.blockSignals(False)
        if self.repertoire.errors:
            self.book_log.setPlainText("\n".join(self.repertoire.errors))

    def _reload_books(self) -> None:
        self.repertoire.load()
        self._refresh_books()
        self._update_book_hint()
        count = len(self.repertoire.names())
        self._set_status(f"Репертуар загружен: {count} дебют(ов).")

    def _update_book_hint(self) -> None:
        book = self.book_combo.currentData()
        hit = self.repertoire.lookup(self.board, book)
        if hit is None:
            if self.repertoire.names():
                self.book_status.setText("В моём PGN-репертуаре нет хода для этой позиции.")
            else:
                self.book_status.setText(
                    "PGN-репертуар пуст — библиотека дебютов выше работает без файлов."
                )
            return
        self.book_status.setText(
            f"Книжный ход: {hit.san}  (встречается {hit.count} из {hit.total}, "
            f"{hit.share * 100:.0f}%)"
        )

    def play_book_move(self) -> None:
        book = self.book_combo.currentData()
        hit = self.repertoire.lookup(self.board, book)
        if hit is None:
            self._set_status("Для этой позиции книжного хода нет.")
            return
        self.board.push(hit.move)
        self.last_move = hit.move
        self.fen_edit.setText(self.board.fen())
        self.board_view.set_board(self.board, self.last_move)
        self.book_log.append(f"{hit.san}   ← {book or 'любой дебют'}")
        self._update_book_hint()
        if self.auto_check.isChecked():
            self.start_analysis()

    # --------------------------------------------------------------- камера
    def toggle_camera(self) -> None:
        if self._stream is not None and self._stream.isRunning():
            self._stream.stop()
            self._stream = None
            self.cam_btn.setText("Подключить")
            self.cam_status.setText("Поток остановлен.")
            return
        url = self.cam_url.text().strip()
        if not url:
            self.cam_status.setText("Укажи URL потока.")
            return
        self.cfg["camera"]["url"] = url
        self._stream = StreamReader(url, self)
        self._stream.frame.connect(self.cam_view.set_image)
        self._stream.failed.connect(self._on_camera_failed)
        self._stream.start()
        self.cam_btn.setText("Стоп")
        self.cam_status.setText("Подключаюсь к потоку…")

    def _on_camera_failed(self, message: str) -> None:
        self.cam_btn.setText("Подключить")
        self.cam_status.setText(message)
        self._stream = None

    def add_corner(self, x: float, y: float) -> None:
        points = self.cam_view.points()
        if len(points) >= 4:
            points = []
        points.append((x, y))
        self.cam_view.set_points(points)
        if len(points) == 4:
            self.cam_status.setText("4 угла отмечены. Жми «Проверить сетку».")
        else:
            self.cam_status.setText(f"Отмечено {len(points)} из 4 углов.")

    def reset_corners(self) -> None:
        self.cam_view.set_points([])
        self.cam_status.setText("Углы сброшены.")

    def _warped(self):
        image = self.cam_view.image()
        if image is None:
            self.cam_status.setText("Нет кадра: подключи камеру.")
            return None
        points = self.cam_view.points()
        if len(points) != 4:
            self.cam_status.setText("Нужно отметить 4 угла доски.")
            return None
        return warp_board(image, points)

    def test_grid(self) -> None:
        warped = self._warped()
        if warped is None:
            return
        preview = np_to_qimage(draw_grid(warped))
        label = QLabel()
        label.setWindowTitle("Доска после выпрямления")
        label.setPixmap(
            QPixmap.fromImage(preview).scaled(
                560,
                560,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        label.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        label.show()
        self._warp_label = label
        self.cam_status.setText(
            "Если жёлтые линии идут по краям клеток — калибровка верная."
        )

    def save_cells(self) -> None:
        warped = self._warped()
        if warped is None:
            return
        folder = config.REPORTS / "squares"
        folder.mkdir(parents=True, exist_ok=True)
        for name, array in split_cells(warped).items():
            np_to_qimage(array).save(str(folder / f"{name}.png"), "PNG")
        self.cam_status.setText(f"Сохранено 64 клетки: {folder}")

    # --------------------------------------------------------------- screen
    def _region(self) -> dict:
        return {key: spin.value() for key, spin in self.cap_spins.items()}

    def select_region(self) -> None:
        self._selector = RegionSelector()
        self._selector.selected.connect(self._region_selected)
        self._selector.show()

    def _region_selected(self, rect) -> None:
        self.cap_spins["x"].setValue(rect.x())
        self.cap_spins["y"].setValue(rect.y())
        self.cap_spins["w"].setValue(rect.width())
        self.cap_spins["h"].setValue(rect.height())
        self.capture_region()

    def capture_region(self) -> None:
        region = self._region()
        try:
            image = grab_region(region)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Захват", str(exc))
            return
        target = config.REPORTS / "capture.png"
        image.save(str(target), "PNG")
        self.preview.setPixmap(
            QPixmap.fromImage(image).scaled(
                self.preview.width(),
                self.preview.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.cfg["capture"] = region
        self._set_status(f"Снимок сохранён: {target}")

    # -------------------------------------------------------------- closing
    def closeEvent(self, event) -> None:  # noqa: N802
        for job in (self._job, self._report_job):
            if job is not None and job.isRunning():
                job.wait(3000)
        if self._stream is not None:
            self._stream.stop()
            self._stream = None
        self.hotkey.unregister()
        geo = self.geometry()
        self.cfg["window"] = {"x": geo.x(), "y": geo.y(), "w": geo.width(), "h": geo.height()}
        self.cfg["opacity"] = self.opacity_slider.value() / 100.0
        self.cfg["depth"] = self.depth_spin.value()
        self.cfg["multipv"] = self.multipv_spin.value()
        self.cfg["report_depth"] = self.report_depth.value()
        self.cfg["capture"] = self._region()
        self.cfg["camera"] = {
            "url": self.cam_url.text().strip(),
            "corners": [[float(x), float(y)] for x, y in self.cam_view.points()],
        }
        config.save(self.cfg)
        self.analyzer.quit()
        super().closeEvent(event)


def _log_crash() -> Path | None:
    import traceback

    try:
        config.REPORTS.mkdir(parents=True, exist_ok=True)
        target = config.REPORTS / "last-error.txt"
        target.write_text(traceback.format_exc(), encoding="utf-8")
        return target
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Chess Assistant")
    icon = config.PROJECT / "assets" / "icons" / "assistant.ico"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ChessHelper.Assistant")
    except Exception:  # noqa: BLE001
        pass
    try:
        window = MainWindow()
    except Exception as exc:  # noqa: BLE001
        target = _log_crash()
        where = target or "reports\\last-error.txt"
        try:
            QMessageBox.critical(
                None,
                "Шахматный помощник",
                f"Не удалось запуститься:\n{exc}\n\nПодробности: {where}",
            )
        except Exception:  # noqa: BLE001
            pass
        return 1
    window.show()
    return app.exec()
