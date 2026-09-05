# Music Downloader (멜론 TOP100 / 음원 / 영상 / URL + URL 컨펌)

유튜브 검색 → URL 컨펌(아니면 재검색) → 확정 후 다운로드하는 4기능 앱. CLI + GUI 지원, macOS/Windows 대응.

## 기능

1. **멜론 TOP100 전체 음원 다운로드** — 차트 크롤링 시도, 차단시 수동 붙여넣기(`가수 - 제목` 줄별)로 폴백
2. **가수명+제목 → 음원(MP3) 다운로드**
3. **가수명+제목 → 영상(MP4) 다운로드**

공통 플로우: `"{가수} {제목} official audio/mv"` 검색 → 제목/채널/길이/URL 후보 표시 → 확정(Y) / 재검색(r) / 중단(q) → 다운로드
- 음원 비트레이트: 128 / 192(기본) / 320k 선택 (TOP100 전체에도 일괄 적용)
- 음량 평준화: 음원은 다운로드 후 EBU R128(`loudnorm I=-16`)로 자동 정규화 — 핸드폰에서 곡간 음량차 없음
- 영상 화질: 360p / 720p(기본) / 1080p / best 선택
- 4번 URL 직접: URL 붙여넣기 → 음원/영상 선택 → 품질 선택 → 가수/제목 자동인식(수정 가능) → 컨펌 후 다운로드
- 이름 수정: 다운로드 확정 후 가수명/제목 수정 가능 (CLI) / GUI 컨펌창에 최종 파일명 표시, 입력란 수정 후 재다운로드
- 저장 위치: CLI 5번 또는 GUI 5탭에서 음원/영상 폴더 지정 (`~/.musicdownloader.json`에 유지, reset=초기화)
- 결과 더 보기: 검색 후 `m`(CLI) / `결과 더 보기`(GUI) → 중복 제외하고 다음 후보 추가

## 맥 실행 명령어

**1회성 준비**
```bash
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg
```

**실행**
```bash
.venv/bin/python cli.py   # 1=TOP100 / 2=MP3 / 3=MP4 / 4=URL직접 / 5=저장위치
.venv/bin/python gui.py   # 5탭 GUI
```

**다운로드 위치**
- MP3 → `data/audio/{가수} - {제목}.mp3`
- MP4 → `data/video/{가수} - {제목}.mp4`
- 중복시 ` (1)`, ` (2)` suffix, overwrite 없음

**앱 빌드 (원할 때만)**
```bash
pyinstaller --noconfirm app.spec  # GUI → dist/MusicDownloader.app
pyinstaller --onefile cli.py      # CLI
```

## GitHub Release (윈도우 빌드)

맥에서는 윈도우용을 못 만들으니 태그만 찍으면 GitHub Actions가 윈도우/맥 둘 다 빌드해서 Release에 올려줘. ffmpeg 내장이라 받는 쪽은 따로 설치 불필요.

```bash
git tag v1.0.0 && git push origin v1.0.0
```
→ Actions 탭에서 빌드 확인 → Releases 페이지에서 `MusicDownloader-win.zip` / `MusicDownloader-mac-app.zip` 다운로드

## 구조

```
config.py  # DATA_AUDIO/VIDEO, 저장위치 설정(~/.musicdownloader.json), check_ffmpeg()
models.py  # Candidate, SongEntry
naming.py  # sanitize(), unique_path() '(1)' suffix
search.py  # youtube_search(ytsearchN), merge_candidates(), confirm_loop_cli(m=더 보기)
download.py# download_audio(mp3 128/192/320k + loudnorm) / download_video(360p/720p/1080p/best)
melon.py   # fetch_top100() + MelonBlocked시 수동 입력 폴백
cli.py     # input() 메뉴 1/2/3/4/5/q (5=저장위치)
gui.py     # PySide6 5탭 + 테이블 + 컨펌/더 보기 + 저장위치탭 + QThread Worker
app.spec   # PyInstaller onedir+BUNDLE(.app) (GUI)
icon.icns  # 맥 독 아이콘
```

## 윈도우

**실행**
```powershell
py -3.14 -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
choco install ffmpeg
.venv\Scripts\python cli.py
.venv\Scripts\python gui.py
```

**앱 빌드**
```powershell
.venv\Scripts\pyinstaller --noconfirm app.spec  # GUI → dist\MusicDownloader\MusicDownloader.exe
.venv\Scripts\pyinstaller --onefile cli.py       # CLI → dist\cli.exe
```
- 참고: `icon.icns`는 맥용이라 윈도우 exe 아이콘은 기본으로 나옴
