# Android (풀네이티브, B안)

기존 Python(`cli.py`/`gui.py`/`app.spec`/`release.yml`)은 그대로 유지. `android/`만 신규.

## 구조
- `MainActivity` + `AppNav` (TOP100/MP3/MP4/URL/설정)
- `core/`: MelonChart(Jsoup) / YoutubeSearch(NewPipeExtractor) / UrlNormalize(search.py 포팅) / DownloadWorker(WorkManager+OkHttp) / MediaConvert(저장 헬퍼)
- `util/`: Naming(naming.py 포팅), Constants(config.py 포팅)

## v1 제한사항 (빌드 검증됨, 2026-09-26 로컬 assembleDebug 성공)
- FFmpeg 미포함: `ffmpeg-kit` 바이너리가 Maven Central에서 회수됨(arthenica 종료). 그래서
  - 음원: 비트레이트 선택(128/192/320k)은 원본 소스 상한으로 동작, 파일은 원본 컨테이너 그대로 저장(.m4a/.opus). MP3 변환·loudnorm 없음.
  - 영상: progressive MP4 직저장(360p/720p; 1080p/best는 progressive 최대, 보통 720p).
- MP3 변환이 필요하면 추후 Media3 Transformer 또는 FFmpeg 바이너리 벤더링으로 추가.

## 로컬 빌드
```bash
cd android
./gradlew assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk (약 18MB, debug 서명)
```

## Release APK
- Actions → `Android APK (Debug)` → `tag` 입력(예: v1.0.15, release.yml과 동일 태그) → Run
- 같은 릴리즈에 `MusicDownloader-android.apk` 첨부됨. `gh release download <tag>`로 desktop zip + APK 함께 받기 가능.
- Debug 서명/사이로드 전용. Play 스토어 등록 시도 금지(YouTube TOS).
