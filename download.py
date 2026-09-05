"""Simple mp3/mp4 download engine (no split, no normalize, no identify)."""
from __future__ import annotations

import os
import sys
import tempfile

from yt_dlp import YoutubeDL

import config
import naming


def _progress_hook(d: dict) -> None:
    if d.get("status") == "downloading":
        sys.stdout.write(f"\r다운로드 중... {d.get('_percent_str', '0%')}          ")
        sys.stdout.flush()
    elif d.get("status") == "finished":
        print("\n변환 중...")


def _ffmpeg_location() -> str | None:
    """check_ffmpeg() 실경로의 디렉토리 (yt-dlp ffmpeg_location용).

    yt-dlp는 바이너리 경로 대신 디렉토리를 받으면
    같은 폴더의 ffmpeg+ffprobe를 둘 다 찾는다.
    """
    try:
        exe = config.check_ffmpeg()
    except Exception:
        return None
    d = os.path.dirname(exe)
    return d or None


def _base_opts() -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_progress_hook],
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "geo_bypass": True,
        "nocheckcertificate": False,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.youtube.com/",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        },
        # 403 SABR 차단 우회: android 클라이언트 우선, web 폴백
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        **({"ffmpeg_location": loc} if (loc := _ffmpeg_location()) else {}),
    }
    return opts


def normalize_loudness(path: str, bitrate: str) -> None:
    """EBU R128 single-pass로 음량을 평준화합니다 (in-place). 핸드폰 재생시 곡간 음량차를 없애는 용도."""
    import shutil
    import subprocess

    ffmpeg = config.check_ffmpeg()
    tmp_out = path + ".norm.mp3"
    cmd = [
        ffmpeg, "-y", "-i", path,
        "-filter:a", f"loudnorm=I={config.LOUDNORM_I}:TP={config.LOUDNORM_TP}:LRA={config.LOUDNORM_LRA}",
        "-ar", "44100", "-b:a", f"{bitrate}k",
        tmp_out,
    ]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if r.returncode != 0 or not os.path.exists(tmp_out):
        if os.path.exists(tmp_out):
            os.remove(tmp_out)
        raise RuntimeError("음량 평준화에 실패했습니다.")
    shutil.move(tmp_out, path)


def download_audio(url: str, artist: str, title: str, bitrate: str = config.DEFAULT_AUDIO_BITRATE, normalize: bool = True) -> str:
    if bitrate not in config.AUDIO_BITRATES:
        raise ValueError(f"지원하지 않는 비트레이트: {bitrate} (가능: {', '.join(config.AUDIO_BITRATES)})")
    config.ensure_dirs()
    config.check_ffmpeg()
    base = naming.song_filename(artist, title)
    final = naming.unique_path(config.get_audio_dir(), base, ".mp3")
    tmp = tempfile.mkdtemp(prefix="mdl_audio_")
    opts = {
        **_base_opts(),
        "format": "bestaudio/best",
        "outtmpl": os.path.join(tmp, "%(title)s.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": bitrate}],
    }
    with YoutubeDL(opts) as ydl:
        ydl.download([url])
    # find converted mp3
    mp3s = [os.path.join(tmp, f) for f in os.listdir(tmp) if f.lower().endswith(".mp3")]
    if not mp3s:
        # fallback: any file -> rename
        files = [os.path.join(tmp, f) for f in os.listdir(tmp) if os.path.isfile(os.path.join(tmp, f))]
        if not files:
            raise RuntimeError("다운로드된 파일이 없습니다.")
        mp3s = files
    src = max(mp3s, key=os.path.getsize)
    os.rename(src, final)
    if normalize:
        print("음량 평준화 중... (EBU R128)")
        normalize_loudness(final, bitrate)
    _tag_mp3(final, artist, title)
    return final


def download_video(url: str, artist: str, title: str, quality: str = config.DEFAULT_VIDEO_QUALITY) -> str:
    if quality not in config.VIDEO_FORMATS:
        raise ValueError(f"지원하지 않는 화질: {quality} (가능: {', '.join(config.VIDEO_FORMATS)})")
    config.ensure_dirs()
    config.check_ffmpeg()
    base = naming.song_filename(artist, title)
    final = naming.unique_path(config.get_video_dir(), base, ".mp4")
    tmp = tempfile.mkdtemp(prefix="mdl_video_")
    opts = {
        **_base_opts(),
        "format": config.VIDEO_FORMATS[quality],
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(tmp, "%(title)s.%(ext)s"),
    }
    with YoutubeDL(opts) as ydl:
        ydl.download([url])
    files = [os.path.join(tmp, f) for f in os.listdir(tmp) if os.path.isfile(os.path.join(tmp, f))]
    if not files:
        raise RuntimeError("다운로드된 파일이 없습니다.")
    src = max(files, key=os.path.getsize)
    # ensure mp4 extension
    if not final.lower().endswith(".mp4"):
        final += ".mp4"
    os.rename(src, final)
    return final


def _tag_mp3(path: str, artist: str, title: str) -> None:
    try:
        from mutagen.easyid3 import EasyID3

        audio = EasyID3(path)
        audio["artist"] = artist
        audio["title"] = title
        audio.save()
    except Exception:
        pass
