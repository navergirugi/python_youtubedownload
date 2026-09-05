"""YouTube search + confirm + re-search loop (yt-dlp ytsearch only)."""
from __future__ import annotations

from typing import Callable, Optional

from yt_dlp import YoutubeDL

import config
from models import Candidate


def _fmt_duration(sec: object) -> str:
    try:
        s = int(float(sec))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def youtube_search(query: str, n: int = config.YTSEARCH_N) -> list[Candidate]:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "socket_timeout": 30,
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
    entries = (info or {}).get("entries", []) if isinstance(info, dict) else []
    out: list[Candidate] = []
    for e in entries:
        if not e:
            continue
        vid = e.get("id", "")
        url = e.get("webpage_url") or (f"https://www.youtube.com/watch?v={vid}" if vid else "")
        if not url:
            continue
        out.append(
            Candidate(
                title=e.get("title", "") or "",
                url=url,
                channel=e.get("channel") or e.get("uploader") or "",
                duration_str=_fmt_duration(e.get("duration")),
            )
        )
    return out


def format_candidates(cands: list[Candidate]) -> str:
    lines = []
    for i, c in enumerate(cands, 1):
        meta = " / ".join(x for x in [c.channel, c.duration_str] if x)
        lines.append(f"[{i}] {c.title}" + (f" ({meta})" if meta else "") + f"\n    {c.url}")
    return "\n".join(lines)


MORE_STEP = 10


def merge_candidates(old: list[Candidate], new: list[Candidate]) -> list[Candidate]:
    """중복 URL 제외하고 새 후보만 뒤에 추가."""
    seen = {c.url for c in old}
    return old + [c for c in new if c.url not in seen]


def confirm_loop_cli(
    cands: list[Candidate],
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
) -> tuple[Optional[Candidate], Optional[str], bool]:
    """Returns (confirmed, re_query, want_more). want_more면 호출자가 n을 늘려 재검색 후 merge."""
    if not cands:
        print_fn("검색 결과가 없습니다. 쿼리를 바꿔 다시 검색하세요.")
        q = input_fn("새 검색어 (엔터=중단): ").strip()
        return None, (q or None), False
    print_fn(format_candidates(cands))
    while True:
        ans = input_fn("번호로 확정 (엔터=1번, m=결과 더 보기, r=재검색, q=중단): ").strip().lower()
        if ans in ("", "1") and cands:
            return cands[0], None, False
        if ans == "q":
            return None, None, False
        if ans == "m":
            return None, None, True
        if ans == "r":
            q = input_fn("새 검색어: ").strip()
            return None, (q or None), False
        if ans.isdigit() and 1 <= int(ans) <= len(cands):
            return cands[int(ans) - 1], None, False
        print_fn("잘못된 입력입니다.")
