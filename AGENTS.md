# PROJECT KNOWLEDGE BASE (python_youtubedownload v3 - 단순 재작성)

**Language:** Python 3.14+ | **Core:** yt-dlp, FFmpeg(외부), PySide6, requests+bs4, mutagen, pyinstaller
**Policy:** 전면 단순화. Gemini/Shazam/무음분할/모음집분할/metadata.json/singer.txt 분류 전부 제거.

## OVERVIEW
유튜브 검색 → URL 컨펌(아니면 재검색) → 확정 후 다운로드하는 4기능 앱. CLI(`cli.py`) + GUI(`gui.py`) 제공, PyInstaller 단일파일 패키징.

1. 멜론 TOP100 전체 음원 다운로드 (하이브리드: 차트 크롤링 → 실패시 수동 붙여넣기/파일, 비트레이트 일괄 선택)
2. 가수명+제목 → 음원(MP3) 다운로드 (128/192/320k 선택)
3. 가수명+제목 → 영상(MP4) 다운로드 (360p/720p/1080p/best 선택)
4. URL 직접 → 음원/영상 선택 + 품질 선택 후 다운로드

## STRUCTURE
```
config.py    # DATA_AUDIO/VIDEO, 저장위치 설정(~/.musicdownloader.json), YTSEARCH_N=10, MELON_URL/HEADERS, check_ffmpeg()
models.py    # Candidate(title,url,channel,duration_str), SongEntry(artist,title)
naming.py    # sanitize(), unique_path() '(1)' suffix, song_filename()
search.py    # youtube_search(ytsearchN), merge_candidates(), format_candidates(), confirm_loop_cli(m=더 보기)
download.py  # download_audio(bestaudio→mp3 128/192/320k + loudnorm 평준화), download_video(360p/720p/1080p/best→mp4), mutagen 태깅
melon.py     # fetch_top100(), parse_chart_html(), parse_manual_lines/file(), MelonBlocked
cli.py       # input() 메뉴 1/2/3/4/5/q (5=저장위치) + 검색→컨펌→더 보기→재검색→다운로드
gui.py       # PySide6 5탭 + 결과 테이블 + 컨펌/더 보기 버튼 + 저장위치탭 + 로그 + QThread Worker
app.spec     # PyInstaller onedir+BUNDLE(.app) (GUI)
data/audio/  # MP3 출력 `{가수} - {제목}.mp3`
data/video/  # MP4 출력 `{가수} - {제목}.mp4`
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| 검색+컨펌 | `search.py` | yt-dlp `ytsearchN`만, API키 불필요 |
| 다운로드 | `download.py` | FFmpeg 필수, preflight `check_ffmpeg()` |
| 멜론 | `melon.py` | `tr[data-song-no]` 파싱, 차단시 `MelonBlocked` |
| CLI | `cli.py` | argparse 없음, `resolve_one()` 루프 |
| GUI | `gui.py` | `Worker(QThread)` + table + `QMessageBox` 컨펌 |

## FLOWS (공통: 검색→컨펌→재검색→다운로드)
- Audio query: `"{artist} {title} official audio"` / Video: `"{artist} {title} official mv"`
- 후보 표시: 제목/채널/길이/URL → Y(확정)/n+재검색(r)/q(중단)
- TOP100: `fetch_top100()` → 실패시 붙여넣기(`가수 - 제목` 줄별) → 곡별 검색→컨펌→다운로드 (s=스킵, Q=중단)

## CONVENTIONS
- Filename: `{Artist} - {Title}.mp3/mp4`, 충돌시 ` (1)`, `(2)` — overwrite 금지
- 불법문자 제거: `\/:*?"<>|` / 유니코드(일본어 포함) 보존

## ANTI-PATTERNS (DO NOT)
- Gemini/Selenium/Shazam/silencedetect/metadata.json/singer.txt 부활 금지
- YouTube Data API 키 요구 금지 (yt-dlp만)
- 다운로드 전 URL 컨펌 생략 금지
- `unique_path()` 우회 직접 저장 금지 / 플러그인·DI 과잉설계 금지

## COMMANDS
```bash
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # yt-dlp, PySide6, requests, bs4, mutagen, pyinstaller
# FFmpeg 별도: mac `brew install ffmpeg` / win `choco install ffmpeg`
.venv/bin/python cli.py           # CLI 메뉴
.venv/bin/python gui.py           # GUI 4탭
pyinstaller --noconfirm app.spec  # GUI 단일파일
pyinstaller --onefile cli.py      # CLI 단일파일
```

## DELETE (legacy, 사용중지)
`extractor.py`, `audio_identify.py`, `_shazam_helper.py`, `organize_data.py`, `fix_*.py`, `test_*.py(legacy)`, `metadata.json`, `.gemini_profile/`, `app.py`(구 GUI) — `singer.txt`는 무시.
