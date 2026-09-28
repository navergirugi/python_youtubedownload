"""Melon TOP100 hybrid: chart crawl attempt + manual fallback."""
from __future__ import annotations

import requests
from bs4 import BeautifulSoup

import config
from models import SongEntry


class MelonBlocked(RuntimeError):
    pass


def fetch_top100() -> list[SongEntry]:
    try:
        r = requests.get(config.MELON_URL, headers=config.MELON_HEADERS, timeout=15)
    except Exception as e:
        raise MelonBlocked(f"멜론 접속 실패: {e}")
    if r.status_code != 200 or not r.text or len(r.text) < 5000:
        raise MelonBlocked(f"멜론 차단/비정상 응답: status={r.status_code}")
    songs = parse_chart_html(r.text)
    if not songs:
        raise MelonBlocked("멜론 파싱 결과 0건 (차단 또는 셀렉터 변경)")
    return songs[:100]


def parse_chart_html(html: str) -> list[SongEntry]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[SongEntry] = []
    for tr in soup.select("tr[data-song-no]"):
        t = tr.select_one(".ellipsis.rank01 a")
        a = tr.select_one(".ellipsis.rank02 a")
        if not t or not a:
            continue
        title = t.get_text(strip=True)
        artist = a.get_text(strip=True).split(",")[0].strip()
        if title and artist:
            out.append(SongEntry(artist=artist, title=title))
    return out


def parse_manual_lines(text: str) -> tuple[list[SongEntry], list[str]]:
    songs: list[SongEntry] = []
    errors: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "," in line and " - " not in line:
            parts = [p.strip() for p in line.split(",", 1)]
        elif " - " in line:
            parts = [p.strip() for p in line.split(" - ", 1)]
        else:
            errors.append(line)
            continue
        if len(parts) == 2 and parts[0] and parts[1]:
            songs.append(SongEntry(artist=parts[0], title=parts[1]))
        else:
            errors.append(line)
    return songs, errors


def parse_manual_file(path: str) -> tuple[list[SongEntry], list[str]]:
    with open(path, encoding="utf-8") as f:
        return parse_manual_lines(f.read())
