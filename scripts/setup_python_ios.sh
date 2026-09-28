#!/bin/bash
# iOS 빌드에 필요한 Python 런타임을 내려받는다.
# Python.xcframework 은 250MB대 바이너리라 git 에 올리지 않으므로
# clone 직후(또는 정리 후) 이 스크립트를 한 번 실행한다.
set -euo pipefail

VER="${PYTHON_IOS_TAG:-3.14-b11}"
ASSET="Python-3.14-iOS-support.b11.tar.gz"
URL="https://github.com/beeware/Python-Apple-support/releases/download/${VER}/${ASSET}"
DEST="$(cd "$(dirname "$0")/.." && pwd)"

cd "$DEST"
if [ -d "ios/Python.xcframework" ]; then
  echo "ios/Python.xcframework 이미 있음 — 건너뜀"
  exit 0
fi

echo "Python iOS 런타임 다운로드 ($VER) ..."
curl -fL -o ios/py.tgz "$URL"
tar xzf ios/py.tgz -C ios
rm -f ios/py.tgz
echo "완료: ios/Python.xcframework"
