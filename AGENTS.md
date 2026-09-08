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
config.py    # DATA_AUDIO/VIDEO, 저장위치+메뉴순서 설정(~/.musicdownloader.json), YTSEARCH_N=10, MELON_URL/HEADERS, check_ffmpeg()
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

[Core Principles & Standards]

1. UI/UX 및 디자인 시스템 스탠다드
 - 색상 시스템: 단순 원색 대신 시맨틱 컬러(Semantic Color)와 가독성 높은 톤(oklch, HSL, Slate 등)을 사용한다.
   - 성공/안정: Green 계열
   - 경고/주의: Yellow/Orange/Brown 계열 (예: oklch 베이지/갈색 톤)
   - 에러/위험: Red 계열
   - 정보/알림: Blue/Indigo 계열
 - 아이콘 체계: `lucide-react` 라이브러리를 기준 글로벌 표준 아이콘을 사용한다.
   - 대시보드(Home), 캠페인(Megaphone), 예약(Calendar), 문의/소통(MessageSquare/Headphones), 설정(Settings), 도움말(HelpCircle)
 - 상태 보존 및 Auto-save:
   - 단발성 설정(알림, 다크모드 등)은 [저장] 버튼 없이 즉시 비동기 자동 저장되는 '토글 스위치(Toggle Switch)' 방식을 우선 채택한다.
   - 텍스트 입력의 경우 Debounce 기법을 적용하며, 시각적 상태(저장 중..., 저장됨) 피드백을 제공한다.

2. Tailwind CSS 작성 규칙
 - 임의 값(Arbitrary values) 활용: 디테일한 색상 및 모서리 값은 대괄호 문법을 활용한다. (예: `text-[#7e4600]`, `bg-[oklch(0.97_0.03_80)]`, `rounded-[10px]`)
 - 대괄호 내 공백 처리: 대괄호 안에서 띄어쓰기는 반드시 언더바(`_`)로 대체한다. (예: `p-[12px_14px]`)
 - 투명도 연출: 색상 뒤에 슬래시와 숫자를 붙여 세밀하게 조절한다. (예: `text-[#7e4600]/80`)
 - 그리드 및 반응형 레이아웃: 
   - 12컬럼 또는 4컬럼 그리드를 기본으로 활용하며 `col-span-X`를 이용해 화면을 유연하게 분할한다. (예: 1칸/3칸 분할 시 `grid-cols-4`에 `col-span-3` 적용)

3. 코드 작성 및 답변 형식
 - 코드 제시 시 필수 라이브러리의 `import` 구문을 명확히 포함한다.
 - HTML 스타일을 React + Tailwind로 변환할 경우, 색상/패딩/폰트 크기/행간/아이콘을 1:1로 정확하게 매칭한다.
 - 코드 제공 후에는 [주요 변경 포인트] 및 [디자인 의도]를 bullet point로 명확하게 요약 해설한다.
 - 아이콘 제안 시 메뉴의 의도(소통, 수신, 단순 문의 등)에 맞는 2~3가지 최적의 대안과 이유를 함께 제시한다.