"""PWA 백엔드 작업 실행기 (pwa.yml이 호출).

YTDL_COOKIES_B64로 주입한 쿠키가 만료되면 yt-dlp가 "Sign in to confirm you're
not a bot"을 던지는데, 그대로 두면 트레이스백만 보여서 원인을 모른다.
여기서 GitHub annotation으로 원인과 remedy를 같이 알려준다.
"""
from __future__ import annotations

import json
import os
import sys

# 이 파일은 tools/에 있으므로 sys.path[0]가 tools/가 된다. CI(python tools/pwa_task.py)
# 처럼 PYTHONPATH 없이 실행되면 search/download 를 못 찾으므로 저장소 루트를 넣는다.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _die(msg: str) -> None:
    print(f"::error::{msg}", flush=True)
    raise SystemExit(1)


def _guard(fn) -> None:
    try:
        fn()
    except SystemExit:
        raise
    except Exception as e:
        blob = str(e)
        if "not a bot" in blob or "Sign in to confirm" in blob:
            _die(
                "YouTube가 이 러너 IP를 봇으로 봤습니다(= 쿠키 만료/무효). "
                "tools/setup_pwa_cookie.sh <cookies.txt> 를 다시 실행하세요."
            )
        _die(f"{type(e).__name__}: {blob[:300]}")


def _search() -> None:
    import search

    q = search.youtube_search(
        f"{os.environ['ARTIST']} {os.environ['TITLE']}".strip(),
        scope=os.environ.get("SCOPE", "music"),
    )
    out = [
        {"title": c.title, "url": c.url, "channel": c.channel, "duration": c.duration_str}
        for c in q
    ]
    with open(f"{os.environ['RUN_ID']}.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print("results:", len(out))


def _download() -> None:
    import download

    kind = os.environ["KIND"]
    kw = {"on_progress": lambda p: print(f"progress {p:.0f}%", flush=True)}
    if kind == "audio":
        path = download.download_audio(
            os.environ["URL"], os.environ["ARTIST"], os.environ["TITLE"],
            bitrate=os.environ["QUALITY"], **kw)
    else:
        path = download.download_video(
            os.environ["URL"], os.environ["ARTIST"], os.environ["TITLE"],
            quality=os.environ["QUALITY"], **kw)
    print("SAVED:", path)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "search":
        _guard(_search)
    elif mode == "download":
        _guard(_download)
    else:
        _die(f"unknown mode: {mode!r}")


if __name__ == "__main__":
    main()
