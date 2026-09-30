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


def download_raw(url: str, artist: str, title: str, kind: str, quality: str) -> str:
    """ffmpeg 없이 원본 그대로 받는다. iOS용 (변환은 Swift 네이티브가 담당)."""
    _redirect_config()
    import shutil
    import tempfile
    import config
    import naming
    import download as dl
    from yt_dlp import YoutubeDL

    if kind == "video":
        # merge 없이 단일 파일 mp4만 받는다 (ffmpeg 합치기 불가).
        h = {"360p": 360, "720p": 720, "1080p": 1080}.get(quality, 100000)
        format_sel = f"best[height<={h}][ext=mp4]/best[height<={h}]/best"
        outdir = config.get_video_dir()
    else:
        if quality not in config.AUDIO_BITRATES:
            raise ValueError(f"지원하지 않는 비트레이트: {quality}")
        format_sel = "bestaudio/best"
        outdir = config.get_audio_dir()
    base = naming.song_filename(artist, title)
    tmp = tempfile.mkdtemp(prefix="mdl_raw_")
    opts = {
        **dl._base_opts(),
        "format": format_sel,
        "outtmpl": os.path.join(tmp, "%(title)s.%(ext)s"),
    }
    with YoutubeDL(opts) as ydl:
        ydl.download([url])
    files = [os.path.join(tmp, f) for f in os.listdir(tmp)
             if os.path.isfile(os.path.join(tmp, f))]
    if not files:
        raise RuntimeError("다운로드된 파일이 없습니다.")
    src = max(files, key=os.path.getsize)
    _, ext = os.path.splitext(src)
    final = naming.unique_path(outdir, base, ext or ".bin")
    shutil.move(src, final)
    return final


def tag(path: str, artist: str, title: str) -> str:
    import download as dl

    dl._tag_mp3(path, artist, title)
    return path


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
    "download_raw": download_raw,
    "tag": tag,
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
