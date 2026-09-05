"""CLI: input() menu, search -> URL confirm -> re-search -> download."""
from __future__ import annotations

import config
import download
import melon
from melon import MelonBlocked
from models import SongEntry
from search import confirm_loop_cli, merge_candidates, youtube_search


def ask_audio_bitrate() -> str:
    opts = "/".join(config.AUDIO_BITRATES)
    while True:
        v = input(f"음원 비트레이트 [{opts}] (엔터={config.DEFAULT_AUDIO_BITRATE}): ").strip()
        if not v:
            return config.DEFAULT_AUDIO_BITRATE
        if v in config.AUDIO_BITRATES:
            return v
        print(f"{opts} 중 선택하세요.")


def ask_video_quality() -> str:
    opts = "/".join(config.VIDEO_QUALITIES)
    while True:
        v = input(f"영상 화질 [{opts}] (엔터={config.DEFAULT_VIDEO_QUALITY}): ").strip()
        if not v:
            return config.DEFAULT_VIDEO_QUALITY
        if v in config.VIDEO_FORMATS:
            return v
        print(f"{opts} 중 선택하세요.")


def ask_names(artist: str, title: str, input_fn=input) -> tuple[str, str]:
    """다운로드 확정 후 파일명(이름) 수정. 엔터=유지."""
    import naming

    a = input_fn(f"가수명 (엔터={artist}): ").strip() or artist
    t = input_fn(f"제목 (엔터={title}): ").strip() or title
    print(f"파일명: {naming.song_filename(a, t)}")
    return a, t


def resolve_one(query: str):
    from search import MORE_STEP

    q = query
    cands = youtube_search(q)
    while True:
        confirmed, re_q, more = confirm_loop_cli(cands)
        if confirmed:
            return confirmed
        if more:
            extra = youtube_search(q, n=len(cands) + MORE_STEP)
            merged = merge_candidates(cands, extra)
            if len(merged) == len(cands):
                print("추가 결과가 없습니다.")
                continue
            print(f"{len(merged) - len(cands)}건 추가 (전체 {len(merged)}건)")
            cands = merged
            continue
        if re_q:
            q = re_q
            cands = youtube_search(q)
            continue
        return None


def flow_audio(artist: str, title: str, bitrate: str | None = None) -> None:
    entry = SongEntry(artist=artist, title=title)
    c = resolve_one(entry.query_audio())
    if not c:
        print("취소됨.")
        return
    print(f"확정: {c.title} {c.url}")
    artist, title = ask_names(artist, title)
    br = bitrate or ask_audio_bitrate()
    path = download.download_audio(c.url, artist, title, bitrate=br)
    print(f"저장: {path} ({br}k)")


def flow_video(artist: str, title: str, quality: str | None = None) -> None:
    entry = SongEntry(artist=artist, title=title)
    c = resolve_one(entry.query_video())
    if not c:
        print("취소됨.")
        return
    print(f"확정: {c.title} {c.url}")
    artist, title = ask_names(artist, title)
    q = quality or ask_video_quality()
    path = download.download_video(c.url, artist, title, quality=q)
    print(f"저장: {path} ({q})")


def flow_top100() -> None:
    try:
        songs = melon.fetch_top100()
        print(f"멜론 TOP100 {len(songs)}곡 로드.")
    except MelonBlocked as e:
        print(f"{e}\n수동 입력으로 전환합니다.")
        print("형식: '가수 - 제목' 한 줄에 한 곡 (끝내려면 빈 줄 2번 또는 'q')")
        lines: list[str] = []
        while True:
            line = input("> ").strip()
            if line.lower() == "q":
                break
            if not line:
                if lines:
                    break
                continue
            lines.append(line)
        songs, errors = melon.parse_manual_lines("\n".join(lines))
        if errors:
            print(f"무시된 줄: {errors}")
        if not songs:
            print("입력 없음. 중단.")
            return
    br = ask_audio_bitrate()
    print(f"전체 {len(songs)}곡을 {br}k 로 다운로드합니다.")
    for i, s in enumerate(songs, 1):
        print(f"\n[{i}/{len(songs)}] {s.artist} - {s.title}")
        cmd = input("검색할까요? (엔터=예, s=스킵, Q=전체중단): ").strip().lower()
        if cmd == "q":
            break
        if cmd == "s":
            continue
        try:
            flow_audio(s.artist, s.title, bitrate=br)
        except Exception as e:
            print(f"실패: {e}")


def flow_settings() -> None:
    print(f"현재 음원 저장: {config.get_audio_dir()}")
    print(f"현재 영상 저장: {config.get_video_dir()}")
    a = input("새 음원 폴더 (엔터=유지, reset=초기화): ").strip()
    v = input("새 영상 폴더 (엔터=유지, reset=초기화): ").strip()
    if a.lower() == "reset" or v.lower() == "reset":
        config.reset_dirs()
        print("초기화됨.")
        return
    if a:
        print(f"음원 저장: {config.set_audio_dir(a)}")
    if v:
        print(f"영상 저장: {config.set_video_dir(v)}")
    if not a and not v:
        print("변경 없음.")
    names = {"top100": "TOP100", "audio": "음원", "video": "영상"}
    cur = config.get_menu_order()
    print(f"현재 1~3번 순서: {' '.join(names[k] for k in cur)} (4=URL직접, 5=저장위치는 고정)")
    o = input("새 순서 (예: 2 3 1, 엔터=유지): ").strip()
    if o:
        keys = [["top100", "audio", "video"][int(d) - 1] for d in o if d in "123"]
        try:
            new = config.set_menu_order(keys)
            print(f"순서 저장: {' '.join(names[k] for k in new)}")
        except ValueError as e:
            print(f"무시됨: {e}")


def _fetch_title(url: str) -> tuple[str, str]:
    """URL에서 (uploader, title) 조회. 실패시 ('', '')."""
    try:
        from yt_dlp import YoutubeDL

        with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
        if isinstance(info, dict):
            return (info.get("uploader") or info.get("channel") or "", info.get("title") or "")
    except Exception:
        pass
    return "", ""


def flow_url() -> None:
    url = input("유튜브 URL: ").strip()
    if not url:
        return
    kind = input("다운로드 종류 (a=음원, v=영상, 엔터=음원): ").strip().lower()
    is_audio = kind in ("", "a", "audio", "음원")
    uploader, vtitle = _fetch_title(url)
    if vtitle:
        print(f"영상: {vtitle}" + (f" ({uploader})" if uploader else ""))
    artist = input(f"가수명 (엔터={uploader or '자동'}): ").strip() or uploader or "Unknown"
    title = input(f"제목 (엔터={vtitle or '자동'}): ").strip() or vtitle or "url_download"
    print(f"URL 컨펌: {url}")
    ok = input("이 URL로 다운로드할까요? (엔터=예, n=취소): ").strip().lower()
    if ok not in ("", "y", "yes"):
        print("취소됨.")
        return
    try:
        if is_audio:
            br = ask_audio_bitrate()
            path = download.download_audio(url, artist, title, bitrate=br)
            print(f"저장: {path} ({br}k)")
        else:
            q = ask_video_quality()
            path = download.download_video(url, artist, title, quality=q)
            print(f"저장: {path} ({q})")
    except Exception as e:
        print(f"실패: {e}")


def _fix_console_encoding() -> None:
    """윈도우 cp1252 콘솔에서 한글 출력 크래시 방지."""
    import sys

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _mode_actions():
    def _audio():
        a = input("가수명: ").strip()
        t = input("제목: ").strip()
        if a and t:
            flow_audio(a, t)

    def _video():
        a = input("가수명: ").strip()
        t = input("제목: ").strip()
        if a and t:
            flow_video(a, t)

    return {
        "top100": ("멜론 TOP100 전체 음원", flow_top100),
        "audio": ("음원(MP3)", _audio),
        "video": ("영상(MP4)", _video),
    }


def main() -> None:
    _fix_console_encoding()
    print("=" * 60)
    print(" Music Downloader")
    print(" 공통: 유튜브 검색 -> URL 컨펌 -> 아니면 재검색 -> 확정 후 다운로드")
    print("=" * 60)
    while True:
        order = config.get_menu_order()
        actions = _mode_actions()
        labels = {str(i + 1): key for i, key in enumerate(order)}
        menu = " / ".join(f"{i + 1}={actions[k][0]}" for i, k in enumerate(order))
        print(f" 메뉴: {menu} / 4=URL직접 / 5=저장위치")
        sel = input("선택 (1/2/3/4/5, q=종료): ").strip().lower()
        if sel in ("q", ""):
            break
        if sel in labels:
            actions[labels[sel]][1]()
        elif sel == "4":
            flow_url()
        elif sel == "5":
            flow_settings()
        else:
            print("1/2/3/4/5/q 중 선택하세요.")
    print("종료. data/ 폴더를 확인하세요.")


if __name__ == "__main__":
    main()
