"""GUI: PySide6 4-tab (TOP100 / Audio / Video / URL) + search table + confirm + log."""
from __future__ import annotations

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import config
import download
import melon
import naming
from melon import MelonBlocked
from models import Candidate, SongEntry
from search import MORE_STEP, merge_candidates, youtube_search

APP_STYLE = """
QMainWindow { background: #f2f4f8; }
QWidget { font-size: 13px; }
QTabWidget::pane { border: 1px solid #d5dae1; border-radius: 10px; background: white; }
QTabBar::tab { background: #e6ebf2; color: #333; padding: 8px 14px; margin-right: 4px; border-top-left-radius: 8px; border-top-right-radius: 8px; }
QTabBar::tab:selected { background: white; color: #111; font-weight: bold; }
QPushButton { background: #2f7cf6; color: white; border: none; border-radius: 7px; padding: 8px 14px; font-weight: 600; }
QPushButton:hover { background: #1f68e0; }
QPushButton:disabled { background: #bcc5d0; color: #f0f0f0; }
QLineEdit, QPlainTextEdit, QComboBox { background: white; border: 1px solid #d5dae1; border-radius: 6px; padding: 6px; selection-background-color: #d7e7ff; }
QTableWidget { background: white; border: 1px solid #d5dae1; border-radius: 6px; gridline-color: #eceff3; selection-background-color: #d7e7ff; selection-color: #111; }
QHeaderView::section { background: #eef1f6; color: #333; padding: 6px; border: none; font-weight: 600; }
QLabel { color: #222; }
"""


class Worker(QThread):
    log = Signal(str)
    done = Signal(bool, str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        try:
            result = self._fn(self.log.emit)
            self.done.emit(True, str(result))
        except Exception as e:
            traceback.print_exc()
            self.done.emit(False, str(e))


def _fill_table(table: QTableWidget, cands: list[Candidate]) -> None:
    table.setRowCount(len(cands))
    for r, c in enumerate(cands):
        for col, val in enumerate([c.title, c.channel, c.duration_str, c.url]):
            item = QTableWidgetItem(val)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # read-only
            table.setItem(r, col, item)


class SearchWorker(QThread):
    """유튜브 검색 전용 워커. UI 스레드 블로킹 없이 결과를 시그널로 전달."""
    found = Signal(list)
    failed = Signal(str)

    def __init__(self, query: str, n: int = 10, parent=None):
        super().__init__(parent)
        self._query = query
        self._n = n

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
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.sync_btn = QPushButton("🔍 검색 실행 (표 채우기)")
        self.sync_btn.clicked.connect(self.do_search_sync)
        self.more_btn = QPushButton("➕ 결과 더 보기")
        self.more_btn.clicked.connect(self.on_more)
        btn_row.addWidget(self.sync_btn, 1)
        btn_row.addWidget(self.more_btn, 1)
        layout.addLayout(btn_row)

        self.dl_btn = QPushButton("⬇️ 선택 행 확정 & 다운로드")
        self.dl_btn.clicked.connect(self.on_download)
        layout.addWidget(self.dl_btn)

    def _query(self) -> str:
        from config import AUDIO_QUERY_TEMPLATE, VIDEO_QUERY_TEMPLATE

        a, t = self.artist.text().strip(), self.title.text().strip()
        tpl = AUDIO_QUERY_TEMPLATE if self.mode == "audio" else VIDEO_QUERY_TEMPLATE
        return tpl.format(artist=a, title=t)

    def on_search(self):
        if not self.artist.text().strip() or not self.title.text().strip():
            QMessageBox.warning(self, "입력", "가수명과 제목을 입력하세요.")
            return
        q = self._query()
        self.log_fn(f"검색 중: {q} ...")
        self.search_btn.setEnabled(False)
        self.sync_btn.setEnabled(False)
        self._search_worker = SearchWorker(q)
        self._search_worker.found.connect(self._on_search_found)
        self._search_worker.failed.connect(self._on_search_failed)
        self._search_worker.start()

    def _on_search_found(self, cands):
        self.cands = cands
        _fill_table(self.table, self.cands)
        self.search_btn.setEnabled(True)
        self.sync_btn.setEnabled(True)
        self.log_fn(f"{len(self.cands)}건 표시. 표에서 행 선택 → URL 확인 후 다운로드.")

    def _on_search_failed(self, msg):
        self.search_btn.setEnabled(True)
        self.sync_btn.setEnabled(True)
        self.log_fn(f"검색 실패: {msg}")

    def do_search_sync(self):
        self.on_search()

    def on_more(self):
        if not self.cands:
            self.log_fn("먼저 검색을 실행하세요.")
            return
        q = self._query()
        self.log_fn(f"추가 검색 중: {q} ...")
        self.more_btn.setEnabled(False)
        self._more_worker = SearchWorker(q, n=len(self.cands) + MORE_STEP)
        self._more_worker.found.connect(self._on_more_found)
        self._more_worker.failed.connect(self._on_more_failed)
        self._more_worker.start()

    def _on_more_found(self, cands):
        merged = merge_candidates(self.cands, cands)
        added = len(merged) - len(self.cands)
        self.cands = merged
        _fill_table(self.table, self.cands)
        self.more_btn.setEnabled(True)
        if added:
            self.log_fn(f"{added}건 추가 (전체 {len(self.cands)}건)")
        else:
            self.log_fn("추가 결과가 없습니다.")

    def _on_more_failed(self, msg):
        self.more_btn.setEnabled(True)
        self.log_fn(f"추가 검색 실패: {msg}")

    def on_download(self):
        r = self.table.currentRow()
        if r < 0 or r >= len(self.cands):
            QMessageBox.warning(self, "선택", "표에서 행을 선택하세요. (재검색: 검색어 수정 후 검색 버튼)")
            return
        c = self.cands[r]
        a, t = self.artist.text().strip(), self.title.text().strip()
        q = self.quality.currentText()
        ext = ".mp3" if self.mode == "audio" else ".mp4"
        fname = naming.song_filename(a, t) + ext
        ok = QMessageBox.question(self, "URL 컨펌", f"{c.title}\n{c.url}\n품질: {q}\n파일명: {fname}\n(이름 바꾸려면 위 입력란 수정 후 다시 다운로드)\n\n이 영상으로 다운로드할까요?")
        if ok != QMessageBox.StandardButton.Yes:
            self.log_fn("컨펌 거부 → 검색어 수정 후 재검색하세요.")
            return
        self.dl_btn.setEnabled(False)

        def job(log):
            if self.mode == "audio":
                return download.download_audio(c.url, a, t, bitrate=q)
            return download.download_video(c.url, a, t, quality=q)

        self.worker = Worker(job)
        self.worker.log.connect(self.log_fn)
        self.worker.done.connect(lambda ok_, msg: (self.dl_btn.setEnabled(True), self.log_fn(f"완료: {msg}" if ok_ else f"실패: {msg}")))
        self.worker.start()


class Top100Tab(QWidget):
    def __init__(self, log_fn):
        super().__init__()
        self.log_fn = log_fn
        self.songs: list[SongEntry] = []
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.fetch_btn = QPushButton("📥 멜론 TOP100 가져오기")
        self.fetch_btn.clicked.connect(self.on_fetch)
        self.dl_all_btn = QPushButton("⬇️ 전체 음원 다운로드")
        self.dl_all_btn.clicked.connect(self.on_download_all)
        row.addWidget(self.fetch_btn)
        row.addWidget(self.dl_all_btn)
        layout.addLayout(row)
        qrow = QHBoxLayout()
        qrow.addWidget(QLabel("음원 비트레이트:"))
        self.bitrate = QComboBox()
        self.bitrate.addItems(list(config.AUDIO_BITRATES))
        self.bitrate.setCurrentText(config.DEFAULT_AUDIO_BITRATE)
        qrow.addWidget(self.bitrate)
        qrow.addStretch(1)
        layout.addLayout(qrow)
        self.info = QLabel("차단 시: 아래에 '가수 - 제목' 줄별로 붙여넣고 '수동 로드' 클릭")
        layout.addWidget(self.info)
        self.paste = QPlainTextEdit()
        self.paste.setPlaceholderText("아이유 - Celebrity\nBTS - Dynamite")
        self.paste.setMaximumHeight(100)
        layout.addWidget(self.paste)
        self.manual_btn = QPushButton("📋 수동 로드")
        self.manual_btn.clicked.connect(self.on_manual)
        layout.addWidget(self.manual_btn)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["가수", "제목", "상태"])
        layout.addWidget(self.table, 1)

    def _set_songs(self, songs):
        self.songs = songs
        self.table.setRowCount(len(songs))
        for r, s in enumerate(songs):
            self.table.setItem(r, 0, QTableWidgetItem(s.artist))
            self.table.setItem(r, 1, QTableWidgetItem(s.title))
            self.table.setItem(r, 2, QTableWidgetItem("대기"))

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

    def on_download_all(self):
        if not self.songs:
            return
        br = self.bitrate.currentText()
        self.dl_all_btn.setEnabled(False)

        def job(log):
            from search import youtube_search

            for i, s in enumerate(self.songs):
                log(f"[{i+1}/{len(self.songs)}] {s.artist} - {s.title} 검색... ({br}k)")
                cands = youtube_search(s.query_audio(), n=3)
                if not cands:
                    log("  결과 없음, 스킵")
                    continue
                c = cands[0]
                log(f"  확정: {c.title} {c.url}")
                try:
                    p = download.download_audio(c.url, s.artist, s.title, bitrate=br)
                    log(f"  저장: {p}")
                except Exception as e:
                    log(f"  실패: {e}")
            return "TOP100 완료"

        w = Worker(job)
        w.log.connect(self.log_fn)
        w.done.connect(lambda ok, msg: (self.dl_all_btn.setEnabled(True), self.log_fn(msg)))
        w.start()
        self._worker = w  # keep ref


class UrlTab(QWidget):
    """4번: URL 직접 입력 → 음원/영상 선택 → 품질 선택 → 다운로드."""

    def __init__(self, log_fn):
        super().__init__()
        self.log_fn = log_fn
        self.worker = None
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
        url = self.url.text().strip()
        if not url:
            QMessageBox.warning(self, "입력", "URL을 입력하세요.")
            return
        is_audio = self.kind.currentText().startswith("음원")
        q = self.quality.currentText()
        a, t = self.artist.text().strip(), self.title.text().strip()
        if not a or not t:
            try:
                from yt_dlp import YoutubeDL

                with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                if isinstance(info, dict):
                    a = a or info.get("uploader") or info.get("channel") or "Unknown"
                    t = t or info.get("title") or "url_download"
            except Exception:
                a, t = a or "Unknown", t or "url_download"
        ext = ".mp3" if is_audio else ".mp4"
        fname = naming.song_filename(a, t) + ext
        ok = QMessageBox.question(self, "URL 컨펌", f"{url}\n{a} - {t} ({q})\n파일명: {fname}\n(이름 바꾸려면 위 입력란 수정)\n\n다운로드할까요?")
        if ok != QMessageBox.StandardButton.Yes:
            return
        self.dl_btn.setEnabled(False)

        def job(log):
            if is_audio:
                return download.download_audio(url, a, t, bitrate=q)
            return download.download_video(url, a, t, quality=q)

        self.worker = Worker(job)
        self.worker.done.connect(lambda ok_, msg: (self.dl_btn.setEnabled(True), self.log_fn(f"완료: {msg}" if ok_ else f"실패: {msg}")))
        self.worker.start()


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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎵 Music Downloader")
        self.resize(900, 650)
        central = QWidget()
        layout = QVBoxLayout(central)
        tabs = QTabWidget()
        tabs.addTab(Top100Tab(self.log), "🏆 1. 멜론 TOP100")
        tabs.addTab(SearchTab("audio", self.log), "🎵 2. 음원(MP3)")
        tabs.addTab(SearchTab("video", self.log), "🎬 3. 영상(MP4)")
        tabs.addTab(UrlTab(self.log), "🔗 4. URL 직접")
        tabs.addTab(SettingsTab(self.log), "⚙️ 5. 저장 위치")
        layout.addWidget(tabs, 1)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(160)
        layout.addWidget(self.log_view)
        self.setCentralWidget(central)

    def log(self, msg: str):
        self.log_view.appendPlainText(msg)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
