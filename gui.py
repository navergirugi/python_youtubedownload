"""GUI: PySide6 4-tab (TOP100 / Audio / Video / URL) + search table + confirm + log."""
from __future__ import annotations

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QProgressBar,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import config
import download
import melon
import naming
import update
from melon import MelonBlocked
from models import Candidate, SongEntry
from search import MORE_STEP, merge_candidates, youtube_search

APP_STYLE = """
QMainWindow { background: #eef1f6; }
QWidget { font-size: 13px; color: #1e293b; }
QFrame#card { background: white; border: 1px solid #dbe1ea; border-radius: 12px; }
QFrame#sidebar { background: #0f172a; border: none; border-radius: 12px; }
QListWidget#nav { background: transparent; border: none; outline: none; }
QListWidget#nav::item { color: #cbd5e1; padding: 10px 12px; border-radius: 8px; margin: 2px 6px; }
QListWidget#nav::item:selected { background: #2563eb; color: white; font-weight: 700; }
QListWidget#nav::item:hover:!selected { background: #1e293b; color: white; }
QLabel#headerTitle { font-size: 17px; font-weight: 800; color: #0f172a; }
QLabel#versionBadge { background: #e0e9ff; color: #1d4ed8; padding: 4px 10px; border-radius: 10px; font-weight: 700; }
QLabel#ok { color: #15803d; font-weight: 600; }
QLabel#warn { color: #b45309; font-weight: 600; }
QLabel#err { color: #b91c1c; font-weight: 600; }
QLabel#info { color: #1d4ed8; font-weight: 600; }
QPushButton { background: #2563eb; color: white; border: none; border-radius: 8px; padding: 8px 14px; font-weight: 600; }
QPushButton:hover { background: #1d4ed8; }
QPushButton:disabled { background: #b6c0cf; color: #eef1f6; }
QPushButton#ghost { background: #eef2ff; color: #1d4ed8; }
QPushButton#ghost:hover { background: #e0e9ff; }
QPushButton#danger { background: #dc2626; }
QPushButton#danger:hover { background: #b91c1c; }
QLineEdit, QPlainTextEdit { background: white; border: 1px solid #d5dae1; border-radius: 8px; padding: 7px; color: #1e293b; selection-background-color: #d7e7ff; }
QComboBox { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 6px 10px; min-height: 26px; color: #0f172a; font-weight: 600; }
QComboBox:hover { border-color: #2563eb; background: white; }
QComboBox:focus { border-color: #2563eb; background: white; }
QComboBox::drop-down { border: none; border-left: 1px solid #e2e8f0; width: 28px; }
QComboBox QAbstractItemView { background: white; color: #1e293b; selection-background-color: #dbeafe; selection-color: #0f172a; border: 1px solid #cbd5e1; border-radius: 8px; outline: none; }
QComboBox QAbstractItemView::item { padding: 7px 10px; min-height: 24px; }
QComboBox QAbstractItemView::item:selected { background: #dbeafe; }
QTableWidget { background: white; border: 1px solid #dbe1ea; border-radius: 8px; color: #1e293b; gridline-color: #eef1f6; selection-background-color: #dbeafe; selection-color: #0f172a; }
QHeaderView::section { background: #f1f5f9; color: #334155; padding: 7px; border: none; font-weight: 700; }
QPlainTextEdit#log { background: #0f172a; color: #e2e8f0; border-radius: 10px; border: 1px solid #1e293b; }
QProgressBar { background: #e2e8f0; border: none; border-radius: 6px; min-height: 12px; text-align: center; color: #0f172a; }
QProgressBar::chunk { background: #2563eb; border-radius: 6px; }
QProgressBar[busy="true"]::chunk { background: #93c5fd; }
QMessageBox { background: white; }
QMessageBox QLabel { color: #1e293b; }
"""


_THREADS: list[QThread] = []

MENU_LABELS = {"top100": "멜론 TOP100", "audio": "음원 (MP3)", "video": "영상 (MP4)"}
_URL_LABEL = "URL 직접"
_SETTINGS_LABEL = "저장 위치·업데이트"


def build_search_query(mode: str, artist: str, title: str) -> str:
    """가수명/제목 중 하나만 있어도 검색 가능. 둘 다 비면 ''."""
    from config import AUDIO_QUERY_TEMPLATE, VIDEO_QUERY_TEMPLATE

    tpl = AUDIO_QUERY_TEMPLATE if mode == "audio" else VIDEO_QUERY_TEMPLATE
    return " ".join(tpl.format(artist=artist.strip(), title=title.strip()).split())


_NAV_KEYS = {**{v: k for k, v in MENU_LABELS.items()}, _URL_LABEL: "url", _SETTINGS_LABEL: "settings"}


def normalize_nav_order(labels: list[str]) -> list[str]:
    """사이드바 표시 순서 → 페이지 키 순서."""
    return [_NAV_KEYS[l] for l in labels if l in _NAV_KEYS]


def _track(thread: QThread) -> QThread:
    _THREADS.append(thread)
    thread.finished.connect(lambda: _THREADS.remove(thread) if thread in _THREADS else None)
    return thread


class Worker(QThread):
    log = Signal(str)
    progress = Signal(float)
    done = Signal(bool, str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn
        _track(self)

    def run(self):
        try:
            result = self._fn(self.log.emit, self.progress.emit)
            self.done.emit(True, str(result))
        except Exception as e:
            if sys.stderr is not None:  # 창모드 exe(stderr=None) 2차 크래시 방지
                traceback.print_exc()
            self.done.emit(False, str(e))


def _reveal_log(log_fn) -> None:
    """실패 시 숨긴 로그를 자동으로 펼쳐준다."""
    win = getattr(log_fn, "__self__", None)
    show = getattr(win, "reveal_log", None)
    if callable(show):
        show()


def _set_status_label(label, text: str, ok: bool | None) -> None:
    """긴 에러/경로가 창 크기를 밀어내지 않도록 120자로 잘라 표시, 전체는 툴팁."""
    label.setText(text if len(text) <= 120 else text[:117] + "...")
    label.setToolTip(text)
    label.setObjectName("ok" if ok else "err" if ok is False else "")
    label.style().unpolish(label)
    label.style().polish(label)


def _autosize_table(table: QTableWidget, stretch_col: int = 0, max_width: int = 420,
                    fixed_cols: tuple[int, ...] = ()) -> None:
    """컬럼 너비 자동 조절: 내용 기준 + 제목열은 stretch로 남는 공간 흡수.

    fixed_cols는 내용폭(ResizeToContents)으로 고정 → 짧은 값(가수/상태/길이)은
    작게, stretch_col(제목)이 나머지 100%를 흡수.
    """
    table.resizeColumnsToContents()
    header = table.horizontalHeader()
    for c in range(table.columnCount()):
        w = table.columnWidth(c)
        if w > max_width:
            table.setColumnWidth(c, max_width)
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    for c in fixed_cols:
        header.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(stretch_col, QHeaderView.ResizeMode.Stretch)
    header.setStretchLastSection(False)


def _fill_table(table: QTableWidget, cands: list[Candidate]) -> None:
    table.setRowCount(len(cands))
    for r, c in enumerate(cands):
        for col, val in enumerate([c.title, c.channel, c.duration_str, c.url]):
            item = QTableWidgetItem(val)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # read-only
            item.setToolTip(val)
            table.setItem(r, col, item)
    _autosize_table(table, stretch_col=0)


class SearchWorker(QThread):
    """유튜브 검색 전용 워커. UI 스레드 블로킹 없이 결과를 시그널로 전달."""
    found = Signal(list)
    failed = Signal(str)

    def __init__(self, query: str, n: int = 10, parent=None):
        super().__init__(parent)
        self._query = query
        self._n = n
        _track(self)

    def run(self):
        try:
            cands = youtube_search(self._query, n=self._n)
            self.found.emit(cands)
        except Exception as e:
            traceback.print_exc()
            self.failed.emit(str(e))


class SearchTab(QWidget):
    def __init__(self, mode: str, log_fn):
        super().__init__()
        self.mode = mode  # 'audio' | 'video'
        self.log_fn = log_fn
        self.cands: list[Candidate] = []
        self.worker = None

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.artist = QLineEdit()
        self.artist.setPlaceholderText("가수명")
        self.title = QLineEdit()
        self.title.setPlaceholderText("제목")
        self.search_btn = QPushButton("🔍 유튜브 검색")
        self.search_btn.clicked.connect(self.on_search)
        row.addWidget(self.artist, 1)
        row.addWidget(self.title, 1)
        row.addWidget(self.search_btn)
        layout.addLayout(row)

        qrow = QHBoxLayout()
        qrow.addWidget(QLabel("음원 비트레이트:" if mode == "audio" else "영상 화질:"))
        self.quality = QComboBox()
        if mode == "audio":
            self.quality.addItems(list(config.AUDIO_BITRATES))
            self.quality.setCurrentText(config.DEFAULT_AUDIO_BITRATE)
        else:
            self.quality.addItems(list(config.VIDEO_QUALITIES))
            self.quality.setCurrentText(config.DEFAULT_VIDEO_QUALITY)
        qrow.addWidget(self.quality)
        qrow.addStretch(1)
        layout.addLayout(qrow)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["제목", "채널", "길이", "URL"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        _autosize_table(self.table, stretch_col=0)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.sync_btn = QPushButton("🔍 검색 실행 (표 채우기)")
        self.sync_btn.clicked.connect(self.do_search_sync)
        self.more_btn = QPushButton("➕ 결과 더 보기")
        self.more_btn.clicked.connect(self.on_more)
        btn_row.addWidget(self.sync_btn, 1)
        btn_row.addWidget(self.more_btn, 1)
        layout.addLayout(btn_row)

        self.search_busy = QProgressBar()
        self.search_busy.setRange(0, 0)  # 로딩중 무한 바
        self.search_busy.setProperty("busy", True)
        self.search_busy.setVisible(False)
        layout.addWidget(self.search_busy)
        self.search_status = QLabel("")
        layout.addWidget(self.search_status)

        self.dl_btn = QPushButton("⬇️ 선택 행 확정 & 다운로드")
        self.dl_btn.clicked.connect(self.on_download)
        layout.addWidget(self.dl_btn)
        self.dl_bar = QProgressBar()
        self.dl_bar.setRange(0, 100)
        self.dl_bar.setValue(0)
        layout.addWidget(self.dl_bar)
        self.dl_status = QLabel("")
        layout.addWidget(self.dl_status)

    def _query(self) -> str:
        return build_search_query(self.mode, self.artist.text(), self.title.text())

    def _set_searching(self, on: bool, msg: str = "") -> None:
        self.search_busy.setVisible(on)
        self.search_btn.setEnabled(not on)
        self.sync_btn.setEnabled(not on)
        self.more_btn.setEnabled(not on)
        if msg:
            self.search_status.setText(msg)

    def on_search(self):
        if not self.artist.text().strip() and not self.title.text().strip():
            QMessageBox.warning(self, "입력", "가수명 또는 제목 중 하나는 입력하세요.")
            return
        q = self._query()
        self.log_fn(f"검색 중: {q} ...")
        self._set_searching(True, f"검색 중: {q} ...")
        self._search_worker = SearchWorker(q)
        self._search_worker.found.connect(self._on_search_found)
        self._search_worker.failed.connect(self._on_search_failed)
        self._search_worker.start()

    def _on_search_found(self, cands):
        self.cands = cands
        _fill_table(self.table, self.cands)
        self._set_searching(False, f"{len(self.cands)}건 표시. 표에서 행 선택 → URL 확인 후 다운로드.")
        self.log_fn(f"{len(self.cands)}건 표시. 표에서 행 선택 → URL 확인 후 다운로드.")

    def _on_search_failed(self, msg):
        self._set_searching(False, f"검색 실패: {msg}")
        self.log_fn(f"검색 실패: {msg}")

    def do_search_sync(self):
        self.on_search()

    def on_more(self):
        if not self.cands:
            self.log_fn("먼저 검색을 실행하세요.")
            return
        q = self._query()
        self.log_fn(f"추가 검색 중: {q} ...")
        self._set_searching(True, f"추가 검색 중: {q} ...")
        self._more_worker = SearchWorker(q, n=len(self.cands) + MORE_STEP)
        self._more_worker.found.connect(self._on_more_found)
        self._more_worker.failed.connect(self._on_more_failed)
        self._more_worker.start()

    def _on_more_found(self, cands):
        merged = merge_candidates(self.cands, cands)
        added = len(merged) - len(self.cands)
        self.cands = merged
        _fill_table(self.table, self.cands)
        self._set_searching(False)
        if added:
            self.search_status.setText(f"{added}건 추가 (전체 {len(self.cands)}건)")
            self.log_fn(f"{added}건 추가 (전체 {len(self.cands)}건)")
        else:
            self.search_status.setText("추가 결과가 없습니다.")
            self.log_fn("추가 결과가 없습니다.")

    def _on_more_failed(self, msg):
        self._set_searching(False, f"추가 검색 실패: {msg}")
        self.log_fn(f"추가 검색 실패: {msg}")

    def on_download(self):
        r = self.table.currentRow()
        if r < 0 or r >= len(self.cands):
            QMessageBox.warning(self, "선택", "표에서 행을 선택하세요. (재검색: 검색어 수정 후 검색 버튼)")
            return
        c = self.cands[r]
        a, t = self.artist.text().strip(), self.title.text().strip()
        fa, ft = a or c.channel, t or c.title  # 빈 입력은 검색 결과로 폴백
        q = self.quality.currentText()
        ext = ".mp3" if self.mode == "audio" else ".mp4"
        fname = naming.song_filename(fa, ft) + ext
        ok = QMessageBox.question(self, "URL 컨펌", f"{c.title}\n{c.url}\n품질: {q}\n파일명: {fname}\n(이름 바꾸려면 위 입력란 수정 후 다시 다운로드)\n\n이 영상으로 다운로드할까요?")
        if ok != QMessageBox.StandardButton.Yes:
            self.log_fn("컨펌 거부 → 검색어 수정 후 재검색하세요.")
            return
        self.dl_btn.setEnabled(False)
        self.dl_bar.setValue(0)
        self._set_dl_status("다운로드 중...", None)

        def job(log, prog):
            if self.mode == "audio":
                return download.download_audio(c.url, fa, ft, bitrate=q, on_progress=prog)
            return download.download_video(c.url, fa, ft, quality=q, on_progress=prog)

        self.worker = Worker(job)
        self.worker.log.connect(self.log_fn)
        self.worker.progress.connect(self.dl_bar.setValue)
        self.worker.done.connect(self._on_dl_done)
        self.worker.start()

    def _set_dl_status(self, text: str, ok: bool | None) -> None:
        _set_status_label(self.dl_status, text, ok)

    def _on_dl_done(self, ok: bool, msg: str) -> None:
        self.dl_btn.setEnabled(True)
        if ok:
            self.dl_bar.setValue(100)
            self._set_dl_status(f"완료: {msg}", True)
            self.log_fn(f"완료: {msg}")
        else:
            self._set_dl_status(f"실패: {msg}", False)
            self.log_fn(f"실패: {msg}")
            _reveal_log(self.log_fn)


class Top100Tab(QWidget):
    def __init__(self, log_fn):
        super().__init__()
        self.log_fn = log_fn
        self.songs: list[SongEntry] = []
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.fetch_btn = QPushButton("멜론 TOP100 가져오기")
        self.fetch_btn.clicked.connect(self.on_fetch)
        self.dl_all_btn = QPushButton("전체 음원 다운로드")
        self.dl_all_btn.clicked.connect(self.on_download_all)
        self.dl_sel_btn = QPushButton("선택 다운로드")
        self.dl_sel_btn.setObjectName("ghost")
        self.dl_sel_btn.clicked.connect(self.on_download_selected)
        row.addWidget(self.fetch_btn)
        row.addWidget(self.dl_all_btn)
        row.addWidget(self.dl_sel_btn)
        layout.addLayout(row)
        qrow = QHBoxLayout()
        qrow.addWidget(QLabel("음원 비트레이트:"))
        self.bitrate = QComboBox()
        self.bitrate.addItems(list(config.AUDIO_BITRATES))
        self.bitrate.setCurrentText(config.DEFAULT_AUDIO_BITRATE)
        qrow.addWidget(self.bitrate)
        self.sel_info = QLabel("행 클릭+Ctrl/Shift으로 여러 곡 선택 가능")
        self.sel_info.setObjectName("info")
        qrow.addWidget(self.sel_info)
        qrow.addStretch(1)
        layout.addLayout(qrow)
        self.info = QLabel("차단 시: 아래에 '가수 - 제목' 줄별로 붙여넣고 '수동 로드' 클릭")
        layout.addWidget(self.info)
        self.paste = QPlainTextEdit()
        self.paste.setPlaceholderText("아이유 - Celebrity\nBTS - Dynamite")
        self.paste.setMaximumHeight(100)
        layout.addWidget(self.paste)
        self.manual_btn = QPushButton("수동 로드")
        self.manual_btn.setObjectName("ghost")
        self.manual_btn.clicked.connect(self.on_manual)
        layout.addWidget(self.manual_btn)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["가수", "제목", "상태"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._update_sel_info)
        layout.addWidget(self.table, 1)
        self.top_bar = QProgressBar()
        self.top_bar.setRange(0, 100)
        self.top_bar.setValue(0)
        layout.addWidget(self.top_bar)
        self.top_status = QLabel("")
        layout.addWidget(self.top_status)

    def _set_songs(self, songs):
        self.songs = songs
        self.table.setRowCount(len(songs))
        for r, s in enumerate(songs):
            for col, val in enumerate([s.artist, s.title, "대기"]):
                item = QTableWidgetItem(val)
                item.setToolTip(val)
                self.table.setItem(r, col, item)
        _autosize_table(self.table, stretch_col=1, fixed_cols=(0, 2))
        self._update_sel_info()

    def _update_sel_info(self):
        n = len(self.table.selectionModel().selectedRows()) if self.table.selectionModel() else 0
        total = len(self.songs)
        self.sel_info.setText(f"{n}곡 선택 / 전체 {total}곡" if total else "행 클릭+Ctrl/Shift으로 여러 곡 선택 가능")

    def _set_status(self, row: int, text: str):
        item = QTableWidgetItem(text)
        item.setToolTip(text)
        self.table.setItem(row, 2, item)

    def on_fetch(self):
        try:
            songs = melon.fetch_top100()
            self._set_songs(songs)
            self.log_fn(f"TOP100 {len(songs)}곡 로드")
        except MelonBlocked as e:
            self.log_fn(f"{e} → 수동 붙여넣기를 사용하세요.")
            QMessageBox.warning(self, "멜론 차단", f"{e}\n아래에 직접 붙여넣어 주세요.")

    def on_manual(self):
        songs, errors = melon.parse_manual_lines(self.paste.toPlainText())
        self._set_songs(songs)
        self.log_fn(f"수동 {len(songs)}곡 로드 (무시 {len(errors)}줄)")

    def _selected_indices(self) -> list[int]:
        sel = self.table.selectionModel()
        if not sel:
            return []
        return sorted({i.row() for i in sel.selectedRows()})

    def on_download_selected(self):
        idx = self._selected_indices()
        if not idx:
            QMessageBox.warning(self, "선택", "표에서 1곡 이상 선택하세요. (Ctrl/Shift+클릭)")
            return
        self._download_indices(idx)

    def on_download_all(self):
        if not self.songs:
            return
        self._download_indices(list(range(len(self.songs))))

    def _download_indices(self, indices: list[int]):
        br = self.bitrate.currentText()
        self.dl_all_btn.setEnabled(False)
        self.dl_sel_btn.setEnabled(False)
        self.top_bar.setValue(0)
        total = len(indices)
        self._set_top_status(f"{total}곡 다운로드 중... (0/{total})", None)
        for i in indices:
            self._set_status(i, "대기")

        def job(log, prog):
            from search import youtube_search

            ok_cnt, fail_cnt = 0, 0
            for k, i in enumerate(indices):
                s = self.songs[i]
                log(f"[{k+1}/{total}] {s.artist} - {s.title} 검색... ({br}k)")
                base = k / total * 100.0
                step = 100.0 / total
                try:
                    cands = youtube_search(s.query_audio(), n=3)
                except Exception as e:
                    log(f"  검색 실패: {e}")
                    fail_cnt += 1
                    prog(base + step)
                    continue
                if not cands:
                    log("  결과 없음, 스킵")
                    fail_cnt += 1
                    prog(base + step)
                    continue
                c = cands[0]
                log(f"  확정: {c.title} {c.url}")
                try:
                    p = download.download_audio(c.url, s.artist, s.title, bitrate=br,
                                                on_progress=lambda pct, b=base, s_=step: prog(b + pct / 100.0 * s_))
                    log(f"  저장: {p}")
                    ok_cnt += 1
                except Exception as e:
                    log(f"  실패: {e}")
                    fail_cnt += 1
                prog(base + step)
            return f"TOP100 완료 (성공 {ok_cnt}, 실패 {fail_cnt})"

        w = Worker(job)
        w.log.connect(self.log_fn)
        w.progress.connect(self.top_bar.setValue)
        w.done.connect(self._on_top_done)
        w.start()
        self._worker = w  # keep ref

    def _set_top_status(self, text: str, ok: bool | None) -> None:
        _set_status_label(self.top_status, text, ok)

    def _on_top_done(self, ok: bool, msg: str) -> None:
        self.dl_all_btn.setEnabled(True)
        self.dl_sel_btn.setEnabled(True)
        if ok:
            self.top_bar.setValue(100)
            self._set_top_status(msg, True)
            self.log_fn(msg)
        else:
            self._set_top_status(f"실패: {msg}", False)
            self.log_fn(f"실패: {msg}")
            _reveal_log(self.log_fn)


class UrlTab(QWidget):
    """4번: URL 직접 입력 → 음원/영상 선택 → 품질 선택 → 다운로드."""

    def __init__(self, log_fn):
        super().__init__()
        self.log_fn = log_fn
        self.worker = None
        self._meta_worker = None
        layout = QVBoxLayout(self)
        self.url = QLineEdit()
        self.url.setPlaceholderText("유튜브 URL 붙여넣기")
        layout.addWidget(self.url)
        row = QHBoxLayout()
        row.addWidget(QLabel("종류:"))
        self.kind = QComboBox()
        self.kind.addItems(["음원(MP3)", "영상(MP4)"])
        self.kind.currentTextChanged.connect(self._sync_quality)
        row.addWidget(self.kind)
        row.addWidget(QLabel("품질:"))
        self.quality = QComboBox()
        row.addWidget(self.quality)
        row.addStretch(1)
        layout.addLayout(row)
        self._sync_quality()
        meta = QHBoxLayout()
        self.artist = QLineEdit()
        self.artist.setPlaceholderText("가수명 (비워두면 자동)")
        self.title = QLineEdit()
        self.title.setPlaceholderText("제목 (비워두면 자동)")
        meta.addWidget(self.artist, 1)
        meta.addWidget(self.title, 1)
        layout.addLayout(meta)
        self.dl_btn = QPushButton("⬇️ URL 컨펌 후 다운로드")
        self.dl_btn.clicked.connect(self.on_download)
        layout.addWidget(self.dl_btn)
        self.meta_busy = QProgressBar()
        self.meta_busy.setRange(0, 0)
        self.meta_busy.setProperty("busy", True)
        self.meta_busy.setVisible(False)
        layout.addWidget(self.meta_busy)
        self.dl_bar = QProgressBar()
        self.dl_bar.setRange(0, 100)
        self.dl_bar.setValue(0)
        layout.addWidget(self.dl_bar)
        self.dl_status = QLabel("")
        layout.addWidget(self.dl_status)
        layout.addStretch(1)

    def _sync_quality(self, *_):
        self.quality.clear()
        if self.kind.currentText().startswith("음원"):
            self.quality.addItems(list(config.AUDIO_BITRATES))
            self.quality.setCurrentText(config.DEFAULT_AUDIO_BITRATE)
        else:
            self.quality.addItems(list(config.VIDEO_QUALITIES))
            self.quality.setCurrentText(config.DEFAULT_VIDEO_QUALITY)

    def on_download(self):
        raw = self.url.text().strip()
        if not raw:
            QMessageBox.warning(self, "입력", "URL을 입력하세요.")
            return
        from search import extract_youtube_url

        url = extract_youtube_url(raw)
        if not url:
            QMessageBox.warning(self, "입력", "유튜브 영상 URL을 붙여넣으세요. (에러 메시지 등은 URL이 아닙니다)")
            self._set_url_status("유튜브 URL이 아닙니다. 영상 주소를 붙여넣으세요.", False)
            return
        if url != raw:
            self.log_fn(f"URL 추출: {url}")
        is_audio = self.kind.currentText().startswith("음원")
        q = self.quality.currentText()
        a, t = self.artist.text().strip(), self.title.text().strip()
        if a and t:
            self._start_url_download(url, is_audio, q, a, t)
            return
        # 메타조회는 UI 스레드에서 하면 멈춰 보여서 워커로 분리 (최대 30초)
        self.dl_btn.setEnabled(False)
        self.meta_busy.setVisible(True)
        self._set_url_status("영상 정보 조회 중... (최대 30초)", None)
        self.log_fn("영상 정보 조회 중... (최대 30초)")
        base_a, base_t = a, t

        def fetch(log, prog):
            try:
                from yt_dlp import YoutubeDL

                opts = {**download._base_opts(), "skip_download": True}
                with YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
            except Exception as e:
                return f"ERR\t{e}"
            if not isinstance(info, dict):
                return "ERR\t영상 정보를 읽지 못했습니다."
            fa = (base_a or info.get("uploader") or info.get("channel") or "Unknown").replace("\n", " ").replace("\t", " ")
            ft = (base_t or info.get("title") or "url_download").replace("\n", " ").replace("\t", " ")
            return f"OK\t{fa}\t{ft}"

        w = Worker(fetch)
        w.done.connect(lambda ok_, msg: self._on_meta_ready(ok_, msg, url, is_audio, q))
        w.start()
        self._meta_worker = w  # keep ref

    def _set_url_status(self, text: str, ok: bool | None) -> None:
        _set_status_label(self.dl_status, text, ok)

    def _on_meta_ready(self, ok, msg, url, is_audio, q):
        self.dl_btn.setEnabled(True)
        self.meta_busy.setVisible(False)
        if not ok or not msg.startswith("OK\t"):
            err = msg[4:] if msg.startswith("ERR\t") else msg
            self._set_url_status(f"정보 조회 실패: {err}", False)
            self.log_fn(f"정보 조회 실패: {err}")
            QMessageBox.warning(self, "조회 실패", f"영상 정보를 가져오지 못했습니다.\n{err}\n(가수명/제목을 직접 입력하면 건너뜁니다.)")
            _reveal_log(self.log_fn)
            return
        _, a, t = msg.split("\t", 2)
        self._start_url_download(url, is_audio, q, a, t)

    def _start_url_download(self, url, is_audio, q, a, t):
        ext = ".mp3" if is_audio else ".mp4"
        fname = naming.song_filename(a, t) + ext
        ok = QMessageBox.question(self, "URL 컨펌", f"{url}\n{a} - {t} ({q})\n파일명: {fname}\n(이름 바꾸려면 위 입력란 수정)\n\n다운로드할까요?")
        if ok != QMessageBox.StandardButton.Yes:
            return
        self.dl_btn.setEnabled(False)
        self.dl_bar.setValue(0)
        self._set_url_status("다운로드 중...", None)

        def job(log, prog):
            log(f"다운로드 시작: {url} ({q})")
            if is_audio:
                return download.download_audio(url, a, t, bitrate=q, on_progress=prog)
            return download.download_video(url, a, t, quality=q, on_progress=prog)

        self.worker = Worker(job)
        self.worker.log.connect(self.log_fn)
        self.worker.progress.connect(self.dl_bar.setValue)
        self.worker.done.connect(self._on_url_done)
        self.worker.start()

    def _on_url_done(self, ok: bool, msg: str) -> None:
        self.dl_btn.setEnabled(True)
        if ok:
            self.dl_bar.setValue(100)
            self._set_url_status(f"완료: {msg}", True)
            self.log_fn(f"완료: {msg}")
        else:
            self._set_url_status(f"실패: {msg}", False)
            self.log_fn(f"실패: {msg}")
            _reveal_log(self.log_fn)


class SettingsTab(QWidget):
    """5번: 음원/영상 저장 위치 설정 (~/.musicdownloader.json에 유지)."""

    def __init__(self, log_fn):
        super().__init__()
        self.log_fn = log_fn
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("저장 위치 (비워두면 기본 data/ 폴더 사용)"))
        for label, attr in (("음원 폴더:", "audio"), ("영상 폴더:", "video")):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            edit = QLineEdit()
            edit.setPlaceholderText("폴더 경로 (비우면 기본값)")
            browse = QPushButton("📁 찾아보기")
            browse.clicked.connect(lambda _, e=edit: self._browse(e))
            row.addWidget(edit, 1)
            row.addWidget(browse)
            layout.addLayout(row)
            setattr(self, f"{attr}_edit", edit)
        self._refresh()
        save_row = QHBoxLayout()
        self.save_btn = QPushButton("💾 저장")
        self.save_btn.clicked.connect(self.on_save)
        self.reset_btn = QPushButton("↩️ 초기화")
        self.reset_btn.clicked.connect(self.on_reset)
        save_row.addWidget(self.save_btn)
        save_row.addWidget(self.reset_btn)
        save_row.addStretch(1)
        layout.addLayout(save_row)
        layout.addWidget(QLabel("메뉴 순서: 왼쪽 목록에서 직접 드래그로 변경"))
        self.skip_label = QLabel("")
        layout.addWidget(self.skip_label)
        layout.addWidget(self._build_update_card())
        layout.addStretch(1)

    def _refresh(self):
        import json as _json

        try:
            with open(config.SETTINGS_PATH, encoding="utf-8") as f:
                d = _json.load(f)
        except (OSError, ValueError):
            d = {}
        self.audio_edit.setPlaceholderText(d.get("audio_dir") or config.DATA_AUDIO)
        self.video_edit.setPlaceholderText(d.get("video_dir") or config.DATA_VIDEO)

    def _browse(self, edit):
        d = QFileDialog.getExistingDirectory(self, "폴더 선택")
        if d:
            edit.setText(d)

    def on_save(self):
        a, v = self.audio_edit.text().strip(), self.video_edit.text().strip()
        if a:
            config.set_audio_dir(a)
            self.log_fn(f"음원 저장: {config.get_audio_dir()}")
        if v:
            config.set_video_dir(v)
            self.log_fn(f"영상 저장: {config.get_video_dir()}")
        if not a and not v:
            self.log_fn("변경 없음.")
        self.audio_edit.clear()
        self.video_edit.clear()
        self._refresh()

    def on_reset(self):
        config.reset_dirs()
        self._refresh()
        self.log_fn("저장 위치 초기화됨.")

    def _build_update_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        title = QLabel(f"앱 업데이트 (현재 v{config.APP_VERSION})")
        title.setObjectName("info")
        lay.addWidget(title)
        self.update_status = QLabel("아직 확인하지 않았습니다.")
        lay.addWidget(self.update_status)
        brow = QHBoxLayout()
        self.check_btn = QPushButton("업데이트 확인")
        self.check_btn.clicked.connect(self.on_check_update)
        self.skip_reset_btn = QPushButton("스킵 초기화")
        self.skip_reset_btn.setObjectName("ghost")
        self.skip_reset_btn.clicked.connect(self.on_skip_reset)
        brow.addWidget(self.check_btn)
        brow.addWidget(self.skip_reset_btn)
        brow.addStretch(1)
        lay.addLayout(brow)
        self._refresh_skip_label()
        return card

    def _refresh_skip_label(self):
        skipped = config.get_skipped_version()
        base = "스킵한 버전 없음" if not skipped else f"스킵 중: v{skipped}"
        if hasattr(self, "update_status") and getattr(self, "update_status").text().startswith("스킵"):
            pass
        if hasattr(self, "skip_label"):
            self.skip_label.setText(base)

    def on_check_update(self):
        self.check_btn.setEnabled(False)
        self.update_status.setText("확인 중...")
        self._upd_worker = Worker(lambda log, prog: update.fetch_remote_info())
        self._upd_worker.done.connect(self._on_update_checked)
        self._upd_worker.start()

    def _on_update_checked(self, ok, msg):
        self.check_btn.setEnabled(True)
        if not ok:
            self.update_status.setText(f"확인 실패: {msg}")
            self.log_fn(f"업데이트 확인 실패: {msg}")
            return
        import ast as _ast

        try:
            info = _ast.literal_eval(msg) if msg.startswith("{") else {}
        except Exception:
            info = {}
        if not isinstance(info, dict):
            info = {}
        cur = update.parse_version(config.APP_VERSION)
        latest = update.parse_version(info.get("latest", config.APP_VERSION))
        minimum = update.parse_version(info.get("min_required", config.APP_VERSION))
        if cur < minimum:
            self.update_status.setText(f"필수 업데이트: v{info.get('latest')} (현재 v{config.APP_VERSION})")
            ask_update_optional(None, info, force=True, log_fn=self.log_fn)
        elif cur < latest:
            self.update_status.setText(f"선택 업데이트: v{info.get('latest')} (현재 v{config.APP_VERSION})")
            ask_update_optional(None, info, force=False, log_fn=self.log_fn)
        else:
            config.clear_skipped_version()
            self.update_status.setText(f"최신 버전입니다 (v{config.APP_VERSION})")
            self.log_fn("업데이트: 최신 버전입니다.")
        self._refresh_skip_label()

    def on_skip_reset(self):
        config.clear_skipped_version()
        self._refresh_skip_label()
        self.update_status.setText("스킵을 초기화했습니다. 다음 실행 시 다시 알립니다.")
        self.log_fn("업데이트 스킵 초기화됨.")


def ask_update_optional(parent, info: dict, force: bool, log_fn=None) -> bool:
    """업데이트 다이얼로그. True=페이지 이동함."""
    if force:
        QMessageBox.critical(
            parent, "필수 업데이트",
            f"현재 v{config.APP_VERSION} → 최신 v{info.get('latest')} 필수 업데이트가 있습니다.\n"
            f"{info.get('notes', '')}\n다운로드 페이지로 이동합니다.",
        )
        update.open_release_page(info)
        return True
    box = QMessageBox(parent)
    box.setWindowTitle("업데이트 알림")
    box.setText(f"{update.format_notice(info)}\n\n지금 다운로드 페이지로 이동할까요?")
    go_btn = box.addButton("지금 이동", QMessageBox.ButtonRole.YesRole)
    later_btn = box.addButton("나중에", QMessageBox.ButtonRole.NoRole)
    skip_btn = box.addButton("이 버전 다시 묻지 않기", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(go_btn)
    box.exec()
    clicked = box.clickedButton()
    if clicked == go_btn:
        update.open_release_page(info)
        return True
    if clicked == skip_btn:
        update.mark_skipped(info)
        if log_fn:
            log_fn(f"v{info.get('latest')} 다시 묻지 않기로 설정 (설정탭에서 초기화 가능)")
        return False
    if log_fn:
        log_fn("업데이트를 나중에 하기로 했습니다.")
    return False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Music Downloader v{config.APP_VERSION}")
        self.resize(1080, 700)
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Music Downloader")
        title.setObjectName("headerTitle")
        badge = QLabel(f"v{config.APP_VERSION}")
        badge.setObjectName("versionBadge")
        header.addWidget(title)
        header.addWidget(badge)
        header.addStretch(1)
        self.settings_btn = QPushButton("⚙ 설정")
        self.settings_btn.setObjectName("ghost")
        self.settings_btn.clicked.connect(lambda: self._select_page("settings"))
        header.addWidget(self.settings_btn)
        root.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(10)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(190)
        self.nav.setDragEnabled(True)
        self.nav.setAcceptDrops(True)
        self.nav.viewport().setAcceptDrops(True)
        self.nav.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.nav.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.stack = QStackedWidget()
        self._pages: dict[str, QFrame] = {}
        self._page_keys: list[str] = []
        sub = {
            "top100": (lambda: Top100Tab(self.log)),
            "audio": (lambda: SearchTab("audio", self.log)),
            "video": (lambda: SearchTab("video", self.log)),
            "url": (lambda: UrlTab(self.log)),
            "settings": (lambda: SettingsTab(self.log)),
        }
        labels = {"settings": _SETTINGS_LABEL, "url": _URL_LABEL,
                  **{k: MENU_LABELS[k] for k in MENU_LABELS}}
        for key in config.get_menu_order():
            card = QFrame()
            card.setObjectName("card")
            lay = QVBoxLayout(card)
            lay.setContentsMargins(14, 14, 14, 14)
            lay.addWidget(sub[key]())
            self._pages[key] = card
            self._page_keys.append(key)
            self.stack.addWidget(card)
            self.nav.addItem(labels[key])
        settings_card = QFrame()
        settings_card.setObjectName("card")
        settings_lay = QVBoxLayout(settings_card)
        settings_lay.setContentsMargins(14, 14, 14, 14)
        settings_lay.addWidget(sub["settings"]())
        self._pages["settings"] = settings_card
        self._page_keys.append("settings")
        self.stack.addWidget(settings_card)
        self.nav.model().rowsMoved.connect(self._on_nav_moved)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        nav_card = QFrame()
        nav_card.setObjectName("sidebar")
        nav_lay = QVBoxLayout(nav_card)
        nav_lay.setContentsMargins(4, 8, 4, 8)
        nav_lay.addWidget(self.nav)
        body.addWidget(nav_card)
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)

        self.log_panel = QWidget()
        log_layout = QVBoxLayout(self.log_panel)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_head = QHBoxLayout()
        log_head.addWidget(QLabel("로그"))
        log_head.addStretch(1)
        clear_btn = QPushButton("지우기")
        clear_btn.setObjectName("ghost")
        clear_btn.clicked.connect(self.clear_log)
        log_head.addWidget(clear_btn)
        toggle_btn = QPushButton("보이기 (Ctrl+L)")
        toggle_btn.setObjectName("ghost")
        toggle_btn.clicked.connect(self.toggle_log)
        log_head.addWidget(toggle_btn)
        self.log_toggle_btn = toggle_btn
        log_layout.addLayout(log_head)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(150)
        log_layout.addWidget(self.log_view)
        root.addWidget(self.log_panel)
        self.log_panel.setVisible(False)  # 기본 숨김, Ctrl+L로 토글
        self.setCentralWidget(central)
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self.toggle_log)

    def toggle_log(self):
        show = not self.log_panel.isVisible()
        self.log_panel.setVisible(show)
        self.log_toggle_btn.setText("숨기기 (Ctrl+L)" if show else "보이기 (Ctrl+L)")

    def clear_log(self):
        self.log_view.clear()

    def _select_page(self, key: str) -> None:
        if key in self._page_keys:
            if key == "settings":
                self.stack.setCurrentIndex(self._page_keys.index(key))
            else:
                self.nav.setCurrentRow(self._page_keys.index(key))

    def _on_nav_moved(self, *_):
        labels = [self.nav.item(i).text() for i in range(self.nav.count())]
        order = normalize_nav_order(labels)
        cur = self._page_keys[self.stack.currentIndex()] if self._page_keys else "top100"
        self._apply_page_order(order)
        try:
            config.set_menu_order(list(order))
            self.log(f"메뉴 순서 저장: {' · '.join(labels)}")
        except ValueError as e:
            self.log(f"순서 무시됨: {e}")
        self._select_page(cur)

    def _apply_page_order(self, order: list[str]) -> None:
        labels = {"settings": _SETTINGS_LABEL, "url": _URL_LABEL,
                  **{k: MENU_LABELS[k] for k in MENU_LABELS}}
        self.nav.blockSignals(True)
        self.stack.blockSignals(True)
        try:
            while self.stack.count():
                self.stack.removeWidget(self.stack.widget(0))
            while self.nav.count():
                self.nav.takeItem(0)
            self._page_keys = list(order) + ["settings"]
            for key in self._page_keys:
                self.stack.addWidget(self._pages[key])
            for key in order:
                self.nav.addItem(labels[key])
        finally:
            self.nav.blockSignals(False)
            self.stack.blockSignals(False)

    def reveal_log(self):
        if not self.log_panel.isVisible():
            self.toggle_log()

    def log(self, msg: str):
        self.log_view.appendPlainText(msg)

    def closeEvent(self, e):
        for w in list(_THREADS):
            if w.isRunning():
                w.requestInterruption()
        for w in list(_THREADS):
            if w.isRunning() and not w.wait(3000):
                w.terminate()
                w.wait(3000)
        e.accept()


def startup_update_check(win, need: bool, force: bool, info: dict) -> str:
    """창 표시 후 호출되는 시작 업데이트 처리. 'exit'면 즉시 종료해야 함."""
    if need and force:
        ask_update_optional(win, info, force=True)
        return "exit"
    if need:
        ask_update_optional(win, info, force=False)
        return "optional"
    if not info:
        win.log("업데이트 확인 실패: 네트워크 문제로 최신 버전을 확인하지 못했습니다. 새 버전이 있을 수 있으니 Releases를 확인하세요.")
        return "offline"
    return "ok"


def main():
    if sys.stdout is None or sys.stderr is None:  # 창모드 exe stdout=None 크래시 방지
        _null = open(os.devnull, "w")
        sys.stdout = sys.stdout or _null
        sys.stderr = sys.stderr or _null
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)
    win = MainWindow()
    win.show()
    app.processEvents()  # 네트워크 체크 전에 창을 먼저 그려서 '실행 안 됨' 체감 제거
    need, force, info = update.check_update()
    if startup_update_check(win, need, force, info) == "exit":
        sys.exit(1)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
