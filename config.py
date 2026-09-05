"""Core configuration and shared constants."""
from __future__ import annotations

import json
import os
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DATA_AUDIO = os.path.join(DATA_DIR, "audio")
DATA_VIDEO = os.path.join(DATA_DIR, "video")

# 사용자 저장위치 설정 (재빌드/재설치에도 유지되도록 홈 디렉토리에 저장)
SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".musicdownloader.json")

YTSEARCH_N = 10

MELON_URL = "https://www.melon.com/chart/index.htm"
MELON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.melon.com/",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

AUDIO_QUERY_TEMPLATE = "{artist} {title} official audio"
VIDEO_QUERY_TEMPLATE = "{artist} {title} official mv"

AUDIO_BITRATES = ("128", "192", "320")
DEFAULT_AUDIO_BITRATE = "192"

# 음량 평준화 (EBU R128 single-pass). 핸드폰 재생시 곡간 음량차 제거용.
# I=-16: 스트리밍 음악 표준 근처 (-14~-16), TP=-1.5: 클리핑 방지, LRA=11: 음악용 다이내믹 범위
LOUDNORM_I = "-16"
LOUDNORM_TP = "-1.5"
LOUDNORM_LRA = "11"

# 라벨 -> yt-dlp format. 360p/720p/1080p 높이 제한, best는 원본 최고.
VIDEO_QUALITIES = ("360p", "720p", "1080p", "best")
DEFAULT_VIDEO_QUALITY = "720p"
VIDEO_FORMATS = {
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "best": "bestvideo+bestaudio/best",
}


def _load_settings() -> dict:
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_settings(d: dict) -> None:
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def get_audio_dir() -> str:
    return _load_settings().get("audio_dir") or DATA_AUDIO


def get_video_dir() -> str:
    return _load_settings().get("video_dir") or DATA_VIDEO


def set_audio_dir(path: str) -> str:
    p = os.path.abspath(os.path.expanduser(path))
    os.makedirs(p, exist_ok=True)
    d = _load_settings()
    d["audio_dir"] = p
    _save_settings(d)
    return p


def set_video_dir(path: str) -> str:
    p = os.path.abspath(os.path.expanduser(path))
    os.makedirs(p, exist_ok=True)
    d = _load_settings()
    d["video_dir"] = p
    _save_settings(d)
    return p


def reset_dirs() -> None:
    d = _load_settings()
    d.pop("audio_dir", None)
    d.pop("video_dir", None)
    _save_settings(d)


class FFmpegMissingError(RuntimeError):
    pass


def ensure_dirs() -> None:
    os.makedirs(get_audio_dir(), exist_ok=True)
    os.makedirs(get_video_dir(), exist_ok=True)


def _bundled_ffmpeg() -> str | None:
    """PyInstaller 번들 옆에 딸려온 ffmpeg 탐색 (릴리즈 빌드용).
    수집 위치가 플랫폼마다 달라(루트/Frameworks/imageio_ffmpeg/binaries)
    prefix + 재귀(깊이 4)로 탐색."""
    import sys

    if not getattr(sys, "frozen", False):
        return None
    base = os.path.dirname(sys.executable)
    meipass = getattr(sys, "_MEIPASS", base)
    roots = (base, meipass,
             os.path.join(base, "..", "Frameworks"),
             os.path.join(base, "..", "Resources"))
    for root in roots:
        root = os.path.normpath(root)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            depth = os.path.relpath(dirpath, root).count(os.sep)
            if depth > 4:
                dirnames[:] = []
                continue
            for name in sorted(filenames):
                if not name.startswith("ffmpeg"):
                    continue
                p = os.path.join(dirpath, name)
                if os.access(p, os.X_OK):
                    return p
    return None


def check_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return path
    bundled = _bundled_ffmpeg()
    if bundled:
        return bundled
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.isfile(exe):
            return exe
    except Exception:
        pass
    raise FFmpegMissingError(
        "ffmpeg을 찾을 수 없습니다. 설치 후 PATH에 등록하세요.\n"
        "macOS: brew install ffmpeg\n"
        "Windows: choco install ffmpeg  (또는 winget install ffmpeg)\n"
        "Ubuntu: sudo apt install ffmpeg -y"
    )
