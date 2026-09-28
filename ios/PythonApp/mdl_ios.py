"""iOS 브리지. SwiftUI 쪽에서 부르는 진입점만 모아 둔다.

데스크톱과 로직을 공유하되, iOS 에서는 두 가지를 바꿔야 한다.
- 저장 위치: 앱 번들은 읽기 전용이라 Documents 로 돌린다.
- ffmpeg: 기기 실행이 금지돼 번들에 심은 바이너리 경로를 명시해야 한다.
"""
from __future__ import annotations

import os
import sys


def _documents() -> str:
    return os.path.join(os.path.expanduser("~"), "Documents")


def _redirect_config() -> None:
    import config

    base = _documents()
    config.BASE_DIR = base
    config.DATA_DIR = os.path.join(base, "data")
    config.DATA_AUDIO = os.path.join(config.DATA_DIR, "audio")
    config.DATA_VIDEO = os.path.join(config.DATA_DIR, "video")
    config.SETTINGS_PATH = os.path.join(base, ".musicdownloader.json")
    config.ensure_dirs()


def ffmpeg_path() -> str:
    return os.path.join(_documents(), "bin", "ffmpeg")


def _search(artist: str, title: str, kind: str) -> list[dict]:
    _redirect_config()
    import search
    import config

    if kind == "video":
        query = config.VIDEO_QUERY_TEMPLATE.format(artist=artist, title=title)
    else:
        query = config.AUDIO_QUERY_TEMPLATE.format(artist=artist, title=title)
    cands = search.youtube_search(query, config.YTSEARCH_N, scope="all")
    return [
        {
            "title": c.title,
            "url": c.url,
            "channel": c.channel,
            "duration": c.duration_str,
        }
        for c in cands
    ]


def download(url: str, artist: str, title: str, kind: str, quality: str) -> str:
    _redirect_config()
    import download as dl

    ff = ffmpeg_path()
    if os.path.exists(ff):
        dl._ffmpeg_location = lambda: ff

    if kind == "video":
        return dl.download_video(url, artist, title, quality=quality)
    return dl.download_audio(url, artist, title, bitrate=quality, normalize=False)


def top100() -> list[dict]:
    _redirect_config()
    import melon
    rows = melon.fetch_top100()
    return [{"artist": a, "title": t} for a, t in rows]


def ytdlp_version() -> str:
    import yt_dlp.version
    return yt_dlp.version.__version__


# Swift 가 부르는 단일 진입점. PythonKit 은 속성 이름을 동적으로 찾을 수 없어서
# (fatalError 로 죽는다) 함수 이름은 여기서 문자열로 옮겨 매칭한다.
_DISPATCH = {
    "_search": _search,
    "download": download,
    "top100": top100,
    "ytdlp_version": ytdlp_version,
}


def dispatch(cmd: str) -> str:
    # PythonKit 은 호출을 try! 로 감싸서 예외가 나면 프로세스가 죽는다.
    # 그래서 이 함수는 절대 예외를 던지지 않고 결과를 항상 문자열로 돌려준다.
    import json

    try:
        req = json.loads(cmd)
        name = req.get("fn", "")
        fn = _DISPATCH.get(name)
        if fn is None:
            raise ValueError("알 수 없는 명령: " + name)
        return json.dumps({"ok": True, "data": fn(*req.get("args", []))}, ensure_ascii=False)
    except BaseException as e:
        import traceback
        detail = f"{type(e).__name__}: {e}"
        return json.dumps({"ok": False, "error": detail,
                           "trace": traceback.format_exc()[-1500:]}, ensure_ascii=False)
