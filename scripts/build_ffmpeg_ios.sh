#!/bin/bash
# MP3 변환용 최소 ffmpeg 를 iOS arm64 용으로 빌드한다.
#
# 왜 직접 빌드하나:
# - App Store 용 prebuilt 는 없다(바이너리 포함이라 배포 불가)
# - ffmpeg-kit iOS 는 16GB Xcode 요구 + Android 전용 아카이브
# - GPL 코덱(x264 등)을 빼면 LGPL 이라 앱 소스도 자유롭게 닫을 수 있다
#
# 필요한 것만 넣는다: AAC/Opus 디코딩 + MP3(lame) 인코딩. 영상 transcoding 은
# 안 넣어서 크기를 줄인다.
set -euo pipefail

FFVER="${FFMPEG_VERSION:-n8.1.3}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${FFMPEG_WORK:-$ROOT/.cache/ffmpeg-ios}"
OUT="$ROOT/ios/FFmpeg.xcframework"

mkdir -p "$WORK"
cd "$WORK"

# MP3 인코딩에 필요한 lame 을 먼저 iOS 용으로 빌드한다. ffmpeg 는 lame 을
# 외부 의존성으로만 받아들이므로(번들 안 함), 이것이 없으면 configure 단계에서
# --enable-libmp3lame 이 조용히 꺼져 MP3 가 안 나온다.
if [ ! -d lame ]; then
  echo "== lame 소스 받기 =="
  curl -fL -o lame.tar.gz "https://downloads.sourceforge.net/project/lame/lame/3.100/lame-3.100.tar.gz"
  tar xzf lame.tar.gz && rm -f lame.tar.gz
  mv lame-3.100 lame
fi

build_lame() {
  local host="$1" label="$2" sysroot="$3" flag="$4"
  [ -f "$WORK/lame-out-$label/config.status" ] && return 0
  echo "== lame 빌드: $label =="
  rm -rf "$WORK/lame-out-$label"
  cd "$WORK/lame"
  ./configure --host="$host" --target="$host" --prefix="$WORK/lame-out-$label" \
    --disable-shared --enable-static --disable-frontend --disable-decoder \
    --disable-gtktest --disable-analyzer-hooks --disable-gtktest \
    CC=clang "$@" $flag \
    CFLAGS="-Os -arch arm64 -isysroot $sysroot" \
    LDFLAGS="-arch arm64 -isysroot $sysroot"
  make -j"$(sysctl -n hw.ncpu)"
  make install
  cd "$WORK"

  # lame 은 .pc 파일을 설치하지 않는다. ffmpeg configure 는 require( lame/lame.h
  # lame_set_VBR_quality -lmp3lame ) -> check_pkg_config 로 확인하므로, .pc 가 없으면
  # 헤더와 라이브러리가 있어도 "libmp3lame >= 3.98.3 not found" 로 죽는다.
  local prefix="$WORK/lame-out-$label"
  mkdir -p "$prefix/lib/pkgconfig"
  cat > "$prefix/lib/pkgconfig/lame.pc" <<EOF
prefix=$prefix
exec_prefix=\${prefix}
libdir=\${exec_prefix}/lib
includedir=\${prefix}/include

Name: lame
Description: MP3 encoder
Version: 3.100
Libs: -L\${libdir} -lmp3lame
Cflags: -I\${includedir}
EOF
}

build_lame arm-apple-darwin ios "$(xcrun --sdk iphoneos --show-sdk-path)" \
  "--host=arm-apple-darwin --build=x86_64-apple-darwin"
build_lame arm-apple-darwin sim "$(xcrun --sdk iphonesimulator --show-sdk-path)" \
  "--host=arm-apple-darwin --build=x86_64-apple-darwin"

if [ ! -d ffmpeg ]; then
  echo "== ffmpeg $FFVER 소스 받기 =="
  git clone --depth 1 --branch "$FFVER" https://github.com/FFmpeg/FFmpeg.git
fi
cd ffmpeg

# yt-dlp 은 자바스크립트 런타임으로 서명(n-sig)을 푼다. iOS 에서는
# dylib/노드 런타임을 띄울 수 없으므로, libavcodec 안의 EJS 인터프리터를 쓴다.
# libavformat/libavcodec/libswresample 은 configure 가 기본으로 켠다.
# --enable-lib* 로 다시 지정하면 "Unknown option" 으로 configure 가 죽는다.
COMMON=(
  --disable-programs
  --disable-doc
  --disable-avdevice
  --enable-decoder=aac
  --enable-decoder=opus
  --enable-decoder=vorbis
  --enable-parser=aac
  --enable-demuxer=mov
  --enable-demuxer=matroska
  --enable-decoder=h264
  --enable-parser=h264
  --enable-muxer=mp3
  --enable-encoder=libmp3lame
  --enable-libmp3lame
  --enable-network
  --enable-protocol=https
  # --enable-jni/--enable-mediacodec 는 Android 전용이라 iOS configure 가
  # "jni not found" 로 죽는다. iOS 는 VideoToolbox/AudioToolbox 를 쓰는데,
  # 앱은 오디오만 변환하므로 둘 다 필요 없다.
  --enable-pic
  --disable-videotoolbox
  --disable-audiotoolbox
  --disable-iconv
  --disable-x86asm
  # --enable-asm 은 존재하지 않는다(대신 --disable-asm 이 있다). arm64 는
  # 어셈블러가 clang 내장이라 네이티브 최적화가 자동으로 켜진다.
  # 슬라이스별 deployment target 은 --extra-cflags 를 넘기는 쪽에서 합친다.
  # configure 는 같은 플래그를 두 번 받으면 앞의 값을 버린다.
  --extra-ldflags="-Os"
)

build_slice() {
  local label="$1"; shift
  local sysroot="$1"; shift
  local deploy_flag="$1"; shift
  local lame="$WORK/lame-out-$label"
  echo "== 빌드: $label =="

  # 이미 완성된 슬라이스는 재빌드하지 않는다. make clean 이 wipe 하는 걸 막고,
  # 90MB짜리 libavcodec.a 를 매번 다시 만드는 시간을 아낀다.
  if [ -f "$WORK/out-$label/lib/libavcodec.a" ] \
     && nm "$WORK/out-$label/lib/libavcodec.a" 2>/dev/null > "$WORK/.nmsyms" \
     && grep -q "ff_libmp3lame_encoder" "$WORK/.nmsyms"; then
    echo "   이미 빌드됨 (건너뜀)"
    return 0
  fi
  make clean >/dev/null 2>&1 || true
  # ffmpeg configure 는 --host/--target 을 받지 않고, -target 삼중항을 스스로
  # 만들어주지도 않는다. iOS 크로스 컴파일의 정석은 삼중항을 컴파일/링크 플래그에
  # 직접 넣는 것이다. 이게 없으면 링커가 macOS 로 착각해 컴파일러 테스트에서 죽는다:
  #   ld: building for 'macOS', but linking in object file built for 'iOS'
  # (--cc="clang -target ..." 로 주면 configure 가 공백에서 잘라 'clang' 만 남긴다)
  SDKROOT="$sysroot"
  export SDKROOT
  DEPLOY_FLAG="$deploy_flag"
  export DEPLOY_FLAG
  # configure 의 require "libmp3lame >= 3.98.3" lame/lame.h ... 는 check_lib ->
  # check_func_headers 로 간다. pkg-config 를 거치지 않고 기본 include 경로에서
  # lame/lame.h 를 찾으므로, lame 헤더를 --extra-cflags 에 직접 줘야 한다.
  PKG_CONFIG_PATH="$lame/lib/pkgconfig" \
  PKG_CONFIG="$(command -v pkg-config)" \
  ./configure --prefix="$WORK/out-$label" --target-os=darwin \
    --arch=arm64 --enable-cross-compile --disable-stripping \
    --enable-libmp3lame \
    --extra-cflags="-arch arm64 -isysroot $sysroot $DEPLOY_FLAG -I$lame/include" \
    --extra-ldflags="-arch arm64 -isysroot $sysroot $DEPLOY_FLAG -L$lame/lib -lmp3lame" \
    "${COMMON[@]}" "$@"

  if grep -q "CONFIG_LIBMP3LAME=yes" ffbuild/config.mak; then
    echo "   lame 인코더 활성 확인"
  else
    echo "!! $label: lame 활성화 실패" >&2
    exit 1
  fi

  make -j"$(sysctl -n hw.ncpu)"
  make install

  # configure 는 지원 안 되는 플래그를 조용히 무시하고 MP3 인코더를 빼버린다.
  # 심볼이 실제로 들어갔는지 확인해 둔다. 심볼 이름은 ff_libmp3lame_encoder 다
  # (libmp3lame_encoder 가 아니어서 처음에 오탐했다).
  nm "$WORK/out-$label/lib/libavcodec.a" 2>/dev/null > "$WORK/.nmsyms" || true
  if ! grep -q "ff_libmp3lame_encoder" "$WORK/.nmsyms"; then
    echo "!! $label: libmp3lame 이 제외됐다. MP3 인코딩 불가." >&2
    exit 1
  fi
  echo "   lame 인코더 확인됨"
}

# 기기(iOS)
build_slice "ios" "$(xcrun --sdk iphoneos --show-sdk-path)" "-mios-version-min=15.0" \
  --extra-cflags="-Os -fembed-bitcode-marker"

# 시뮬레이터 (검증용)
build_slice "sim" "$(xcrun --sdk iphonesimulator --show-sdk-path)" "-mios-simulator-version-min=15.0" \
  --extra-cflags="-Os -fembed-bitcode-marker"

echo "== xcframework 조립 =="
rm -rf "$OUT"
xcodebuild -create-xcframework \
  -library "$WORK/out-ios/lib/libavformat.a" -headers "$WORK/out-ios/include" \
  -library "$WORK/out-ios/lib/libavcodec.a" -headers "$WORK/out-ios/include" \
  -library "$WORK/out-ios/lib/libavutil.a"  -headers "$WORK/out-ios/include" \
  -library "$WORK/out-ios/lib/libswresample.a" -headers "$WORK/out-ios/include" \
  -library "$WORK/out-sim/lib/libavformat.a" -headers "$WORK/out-sim/include" \
  -library "$WORK/out-sim/lib/libavcodec.a" -headers "$WORK/out-sim/include" \
  -library "$WORK/out-sim/lib/libavutil.a"  -headers "$WORK/out-sim/include" \
  -library "$WORK/out-sim/lib/libswresample.a" -headers "$WORK/out-sim/include" \
  -output "$OUT"

du -sh "$OUT"
echo "완료: $OUT"
