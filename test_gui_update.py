import gui


class _Win:
    def __init__(self):
        self.logs = []

    def log(self, msg):
        self.logs.append(msg)


def test_startup_forced_returns_exit(monkeypatch):
    calls = []
    monkeypatch.setattr(gui, "ask_update_optional", lambda *a, **k: calls.append((a, k)) or True)
    assert gui.startup_update_check(_Win(), True, True, {"latest": "9.9.9"}) == "exit"
    assert len(calls) == 1


def test_startup_optional_returns_optional(monkeypatch):
    monkeypatch.setattr(gui, "ask_update_optional", lambda *a, **k: False)
    assert gui.startup_update_check(_Win(), True, False, {"latest": "9.9.9"}) == "optional"


def test_startup_offline_logs_and_continues():
    w = _Win()
    assert gui.startup_update_check(w, False, False, {}) == "offline"
    assert w.logs and "네트워크" in w.logs[0]


def test_startup_ok_no_dialog(monkeypatch):
    def _fail(*a, **k):
        raise AssertionError("dialog must not open")
    monkeypatch.setattr(gui, "ask_update_optional", _fail)
    assert gui.startup_update_check(_Win(), False, False, {"latest": "1.0.12"}) == "ok"


def test_build_search_query_both():
    assert gui.build_search_query("audio", "아이유", "Celebrity") == "아이유 Celebrity official audio"


def test_build_search_query_single_field():
    assert gui.build_search_query("audio", "", "Celebrity") == "Celebrity official audio"
    assert gui.build_search_query("video", "BTS", "") == "BTS official mv"


def test_build_search_query_empty():
    assert gui.build_search_query("audio", "", "") == "official audio"


def test_normalize_nav_order_keeps_all_pages():
    assert gui.normalize_nav_order(["URL 직접", "멜론 TOP100", "음원 (MP3)", "영상 (MP4)"]) == [
        "url", "top100", "audio", "video",
    ]


def test_no_window_flag_on_win32():
    import inspect
    import sys

    import download

    src = inspect.getsource(download.normalize_loudness)
    assert "CREATE_NO_WINDOW" in src
    if sys.platform != "win32":
        pass  # 플래그는 win32에서만 전달, 타 플랫폼은 빈 dict


def test_menu_order_migrates_old_3item_save(tmp_path, monkeypatch):
    import json

    import config

    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"menu_order": ["video", "top100", "audio"]}), encoding="utf-8")
    monkeypatch.setattr(config, "SETTINGS_PATH", str(p))
    assert config.get_menu_order() == ["video", "top100", "audio", "url"]


def test_shutil_move_used_for_cross_drive():
    import inspect

    import download

    src = inspect.getsource(download.download_audio) + inspect.getsource(download.download_video)
    assert "shutil.move" in src
    assert "os.rename" not in src


def test_extract_youtube_url():
    from search import extract_youtube_url

    assert extract_youtube_url("https://www.youtube.com/watch?v=h6oAbkzzjS0") == \
        "https://www.youtube.com/watch?v=h6oAbkzzjS0"
    assert extract_youtube_url("https://youtu.be/h6oAbkzzjS0") == \
        "https://www.youtube.com/watch?v=h6oAbkzzjS0"
    assert extract_youtube_url("실패: [WinError 17] 옮길 수 없습니다: C:\\a.mp3 -> E:\\b.mp3") == ""
    assert extract_youtube_url("봐봐 https://www.youtube.com/watch?v=h6oAbkzzjS0 최고다") == \
        "https://www.youtube.com/watch?v=h6oAbkzzjS0"
    assert extract_youtube_url("https://example.com/x") == ""


def test_progress_percent():
    import download

    assert download.progress_percent({"status": "finished"}) == 100.0
    assert download.progress_percent({"status": "downloading", "downloaded_bytes": 50, "total_bytes": 100}) == 50.0
    assert download.progress_percent({"status": "downloading"}) == 0.0
    assert download.progress_percent({"status": "downloading", "downloaded_bytes": 200, "total_bytes": 100}) == 100.0


def test_safe_write_with_none_stdout(monkeypatch):
    import sys

    import download

    monkeypatch.setattr(sys, "stdout", None)
    download._safe_write("hello")  # 크래시 없이 무시
    download._progress_hook({"status": "downloading", "_percent_str": "10%"})
    download._progress_hook({"status": "finished"})
