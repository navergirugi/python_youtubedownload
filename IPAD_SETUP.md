# iPad 앱 — 구동 방법과 갱신 방법

Music Downloader 를 iPad 에 넣고, 나중에 맥에서 새 버전으로 갈아끼우는 방법입니다.

---

## ⚠️ 현재 상태 (먼저 읽어주세요)

| 항목 | 상태 |
|---|---|
| Xcode 빌드 (시뮬레이터) | ✅ **검증됨** |
| 앱 안에서 Python 3.14 구동 | ✅ **검증됨** |
| 앱 안에서 `yt-dlp` import | ✅ **검증됨** (`yt-dlp 2026.08.19`) |
| 앱 화면 (4탭 UI) | ✅ 빌드됨 |
| 앱에서 실제 검색 | ✅ **검증됨** (10건, 시뮬레이터) |
| 앱에서 실제 다운로드 | ✅ **검증됨** (4.7MB MP3 종단) |
| MP3 변환 (ffmpeg) | ✅ **검증됨** (네이티브 libav, 44100Hz 스테레오 192k) |
| yt-dlp 자동갱신 | ✅ **검증됨** (최신 유지 확인 + 구버전 2024.08.06→2026.08.19 갱신 실측) |
| **실제 iPad 설치** | ❌ **미검증** — 기기에 넣어본 적 없음 |
| 7일 만료 재서명 | ❌ **미검증** |

**남은 것은 실제 기기 설치와 7일 재서명뿐입니다.** 아래 절차는 실제 기기에서 한 번도
돌려보지 않은 경로입니다. 진행하면서 막히면 이 문서를 고치면서 갱신하겠습니다.

검증된 것 (시뮬레이터, `Documents/engine_status.txt` + 산출물 실측):

```
PYTHON_OK yt-dlp=2026.08.19
SEARCH_OK count=10
DOWNLOAD_OK .../아이유 - Celebrity.mp3   # 4.7MB, ID3 태그 포함, m4a 원본 정리됨
```

앱이 크래시하지 않고 Python·yt-dlp 를 실제로 로드한다는 것까지는 확인됐습니다.

---

## 구조 — 왜 서버가 필요 없는가

유튜브는 **데이터센터 IP**(클라우드, VPS)에서 오는 다운로드를 막습니다. 서버에 올리는
방식은 그래서 실패했고, 남은 조건은 "다운로드를 실행하는 기기가 residential IP 를 갖고
있다"였습니다.

**iPad 의 IP 는 residential 이므로 iPad 에서 직접 받으면 서버가 필요 없습니다.**

```
iPad (residential IP)
  └─ Python (XCFramework)      SwiftUI 가 PythonKit 으로 호출
       └─ yt-dlp               데스크톱과 동일한 엔진
            └─ MP3 변환         ffmpeg (아직 미통합)
                 └─ Documents 폴더에 저장
```

| | |
|---|---|
| 서버 | 없음 |
| 맥 | 최초 설치 시에만 필요 |
| 비용 | 0원 |
| 집 밖에서 | 동작 (iPad 의 IP 를 쓰므로) |

---

## 1. 준비

```bash
# Python 런타임 내려받기 (약 250MB, git 에는 안 들어 있음)
./scripts/setup_python_ios.sh
```

`ios/Python.xcframework` 가 생깁니다. 없으면 빌드가 실패합니다. 최초 1회만.

---

## 2. 맥에서 빌드 (시뮬레이터 — 검증된 명령)

```bash
cd ios
xcodebuild -project MusicDownloader.xcodeproj -scheme MusicDownloader \
  -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPad Air 11-inch (M4),OS=26.5' \
  -configuration Debug build \
  ONLY_ACTIVE_ARCH=YES \
  CODE_SIGN_IDENTITY="-" CODE_SIGNING_REQUIRED=NO CODE_SIGNING_ALLOWED=YES
```

플래그가 꼭 필요한 이유 (제거하면 깨집니다):

- `ONLY_ACTIVE_ARCH=YES` — `generic` 으로 빌드하면 `lib-$ARCHS` 가
  `lib-arm64 x86_64`(공백 포함)가 되어 rsync 실패
- `CODE_SIGN_IDENTITY="-"` — `install_python` 이 변환된 extension 을 서명하는데,
  서명을 끄면 `no identity found` 로 죽음

결과물:
`~/Library/Developer/Xcode/DerivedData/MusicDownloader-*/Build/Products/Debug-iphonesimulator/MusicDownloader.app`

---

## 3. iPad 에 넣기 (AltStore 사이드로드)

App Store 규칙상 이 앱은 배포판을 받을 수 없습니다(유튜브 다운로드 앱은 5.2.3 위반).
**사이드로드**가 유일한 경로입니다.

> **아직 기기에서 검증하지 않은 절차입니다.**

### 3-1. Mac 에 AltStore 설치
[altstore.io](https://altstore.io) 에서 `AltStore.app` 를 Applications 에 넣습니다.
안쪽에 **AltServer**(서명 도구)가 들어 있습니다.

### 3-2. 실기기용 .ipa 만들기 (미검증)

> **확인된 사실 (Mac에서, 서명 제외):** `iphoneos` 빌드의 컴파일+링크는 통과합니다 —
> `MusicDownloader.debug.dylib` 19.8MB 안에 `mdl_convert_to_mp3`·libav 심볼이 들어 있습니다.
> 막히는 지점은 `Prepare Python` 단계의 프레임워크 서명뿐이며, Apple ID 서명 신원이 있으면 풀립니다.

```bash
# 팀 ID: Xcode → Settings → Accounts 에 Apple ID 추가 후 Settings → Accounts 에 표시되는 Team ID
xcodebuild -project MusicDownloader.xcodeproj -scheme MusicDownloader \
  -sdk iphoneos -configuration Release \
  -archivePath build/MusicDownloader.xcarchive \
  DEVELOPMENT_TEAM=<팀ID> CODE_SIGN_STYLE=Automatic \
  CODE_SIGNING_ALLOWED=YES -allowProvisioningUpdates
```

`ios/ExportOptions.plist` (파일로 있음 — `YOUR_TEAM_ID`만 본인 팀 ID로 교체, 무료 계정 / 7일 기준):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>method</key>              <string>development</string>
  <key>teamID</key>              <string>팀ID</string>
  <key>signingStyle</key>        <string>automatic</string>
  <key>provisioningProfiles</key><dict/>
</dict></plist>
```

```bash
xcodebuild -exportArchive \
  -archivePath build/MusicDownloader.xcarchive \
  -exportOptionsPlist ExportOptions.plist -exportPath build/
```

### 3-3. iPad 에 설치
1. iPad 를 USB 로 연결 → "이 컴퓨터를 신뢰"
2. 메뉴바 **AltServer** → **Install AltStore on your iPad**
3. `build/MusicDownloader.ipa` 를 AltServer 아이콘에 **드래그 앤 드롭**
4. 설치 후 USB 뽑아도 됩니다

---

## 4. 맥에서 갱신

### 4-1. yt-dlp 업데이트 (가장 자주 필요)

**사실상 가장 중요한 갱신입니다.** 유튜브가 방어를 자주 바꾸기 때문에 yt-dlp 가
오래되면 **앱이 갑자기 아무것도 못 받습니다.** 설정상으로는 아무 오류 없이
"결과 0건"으로 나올 수 있습니다.

```bash
# 데스크톱 venv 의 최신 yt-dlp 를 iOS 번들로 복사
cp -R .venv/lib/python3.14/site-packages/yt_dlp ios/PythonApp/
.venv/bin/python -c "import sys; sys.path.insert(0,'ios/PythonApp'); \
  import yt_dlp; print('yt-dlp', yt_dlp.version.__version__)"
```

그다음 3-3 절에서 다시 빌드·설치합니다.

> 앱 안에 자동 업데이트가 있습니다(설정 탭 → yt-dlp 갱신). 갱신 후에도 안 되면 4-1절로 번들을 교체하세요.

### 4-2. 앱 코드 수정 후

```bash
git pull
./scripts/setup_python_ios.sh   # xcframework 없으면
cd ios && <2절의 xcodebuild 명령>
```

### 4-3. 재서명 · 재설치 (7일 갱신)

무료 Apple ID 서명은 **7일** 뒤 만료됩니다. 만료되면 아이콘은 남지만 실행이 안 됩니다.

AltServer 메뉴에서 해당 앱을 선택해 갱신하거나, 새 `.ipa` 를 다시 드래그합니다.

자동으로 하려면:

1. **Mac** — 시스템 설정 → 일반 → 로그인 항목 → `AltStore.app` 추가
   (Mac 을 켤 때마다 AltServer 가 뜹니다)
2. **iPad** — 설정 → AltStore → **Refresh Background Apps** 켜기

평소 Mac 을 쓰실 때 갱신이 자동으로 일어납니다.
**Mac 을 7일 연속으로 안 켜면** 앱이 만료되고, 그때 Mac 을 켜서 iPad 에서
AltStore 를 한 번 실행하면 갱신됩니다.

---

## 5. 문제 해결

**`Library not loaded: @rpath/Python.framework/Python` 로 죽는다**
→ Embed & Sign 빌드 단계가 없습니다. pbxproj 의 `Embed Frameworks` 페이즈에
`Python.xcframework` 가 `CodeSignOnCopy` 로 들어 있는지 확인하세요.

**`no identity found` 로 빌드가 죽는다**
→ `Prepare Python` 단계에서 서명 신원이 비어 있습니다. 실기기 빌드는 Apple ID 서명이 필수라 우회 불가 — Xcode → Settings → Accounts 에 Apple ID를 추가하고 `DEVELOPMENT_TEAM=<팀ID>` 와 함께 빌드하세요.

**`lib-arm64 x86_64` 로 rsync 가 죽는다**
→ `generic/platform=iOS Simulator` 로 빌드했습니다. 실제 시뮬레이터 기기를
`destination` 에 지정하고 `ONLY_ACTIVE_ARCH=YES` 를 주세요.

**`install_stdlib` 이 경로를 못 찾는다**
→ `install_python` 은 **PROJECT_DIR 기준 상대경로**를 받습니다. 절대경로를 주면
경로가 이중으로 붙습니다.

**앱은 되는데 검색 결과가 0건**
→ yt-dlp 버전이 뒤처졌을 가능성이 높습니다. 4-1 절로 갱신하세요.
(iPad IP 자체가 막힌 경우도 있으므로 같은 기기에서 다른 앱으로도 확인해 보세요)

---

## 관련 파일

| 경로 | 역할 |
|---|---|
| `ios/MusicDownloader/Core/PyBridge.swift` | Python 초기화 + 호출 |
| `ios/MusicDownloader/Core/Engine.swift` | SwiftUI ↔ 엔진 (검색/다운로드/MP3/갱신) |
| `ios/PythonApp/mdl_ios.py` | iOS 어댑터 (저장 경로 등) |
| `ios/PythonApp/yt_dlp/` | 번들된 yt-dlp (갱신 대상) |
| `scripts/setup_python_ios.sh` | Python 런타임 다운로드 |
| `android/README-ANDROID.md` | 안드로이드 빌드 (MP3 변환 포함) |
