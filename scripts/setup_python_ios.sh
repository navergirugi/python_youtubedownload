#!/bin/bash
# iOS 빌드에 필요한 서드파티 자산을 내려받는다.
#
# 저장소에 두지 않는 이유:
# - Python.xcframework: 250MB대 바이너리
# - yt_dlp: 서드파티 1049 파일. extractor/shahid.py 에 tvOS 테스트용 샘플 AWS 키가
#   들어 있어 커밋하면 GitHub secret scanning 이 push 를 막는다. 공개 키라 유출
#   위험은 없지만, 갱신 주기도 yt-dlp 가 자주 바뀌므로 빌드 시점에 받아야 한다.
set -euo pipefail

VER="${PYTHON_IOS_TAG:-3.14-b11}"
ASSET="Python-3.14-iOS-support.b11.tar.gz"
URL="https://github.com/beeware/Python-Apple-support/releases/download/${VER}/${ASSET}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT"

if [ ! -d "ios/Python.xcframework" ]; then
  echo "Python iOS 런타임 다운로드 ($VER) ..."
  curl -fL -o ios/py.tgz "$URL"
  tar xzf ios/py.tgz -C ios
  rm -f ios/py.tgz
  echo "  -> ios/Python.xcframework"
else
  echo "ios/Python.xcframework 이미 있음"
fi

# yt-dlp 는 데스크톱 venv 를 그대로 쓴다. 두 사본의 버전이 어긋나면 디버깅이
# 어려우므로 iOS 번들은 항상 여기서 동기화한다.
if [ -x ".venv/bin/python" ]; then
  echo "yt-dlp 를 iOS 번들로 동기화 ..."
  rm -rf ios/PythonApp/yt_dlp
  SITE=$(.venv/bin/python -c "import yt_dlp, os; print(os.path.dirname(os.path.dirname(yt_dlp.__file__)))")
  cp -R "$SITE/yt_dlp" ios/PythonApp/
  .venv/bin/python -c "
import sys
sys.path.insert(0, 'ios/PythonApp')
import yt_dlp
print('  -> yt-dlp', yt_dlp.version.__version__)
"
else
  echo "경고: .venv 가 없어 yt-dlp 동기화 생략 (python3 -m venv .venv 후 pip install -r requirements.txt)"
fi

# mutagen 은 순수 Python 태깅 라이브러리다. yt-dlp 와 같은 이유로 저장소에
# 두지 않고(서드파티), 여기서 venv 사본으로 동기화한다. _tag_mp3 는
# try/except 로 감싸져 있어 없어도 다운로드는 되지만 태그가 빠진다.
if [ -x ".venv/bin/python" ]; then
  if .venv/bin/python -c "import mutagen" 2>/dev/null; then
    echo "mutagen 을 iOS 번들로 동기화 ..."
    rm -rf ios/PythonApp/mutagen
    SITE=$(.venv/bin/python -c "import mutagen, os; print(os.path.dirname(os.path.dirname(mutagen.__file__)))")
    cp -R "$SITE/mutagen" ios/PythonApp/
    echo "  -> mutagen 동기화 완료"
  else
    echo "경고: venv 에 mutagen 없음 (pip install mutagen 권장, 없어도 태그만 생략)"
  fi
fi

# certifi 는 iOS 실기기에서 필수다. iOS 에는 OpenSSL 이 읽을 시스템 CA 번들이
# 없어서(키체인만 있음) 번들에 Mozilla CA 를 넣고 mdl_ios 가 SSL_CERT_FILE 로
# 가리킨다. 없으면 실기기에서 CERTIFICATE_VERIFY_FAILED 로 검색이 죽는다.
if [ -x ".venv/bin/python" ]; then
  if .venv/bin/python -c "import certifi" 2>/dev/null; then
    echo "certifi 를 iOS 번들로 동기화 ..."
    rm -rf ios/PythonApp/certifi
    SITE=$(.venv/bin/python -c "import certifi, os; print(os.path.dirname(os.path.dirname(certifi.__file__)))")
    cp -R "$SITE/certifi" ios/PythonApp/
    echo "  -> certifi 동기화 완료"
  else
    echo "오류: venv 에 certifi 없음. pip install certifi 후 다시 실행 (실기기 SSL 필수)"
    exit 1
  fi
fi
