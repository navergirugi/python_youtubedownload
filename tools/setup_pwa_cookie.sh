#!/usr/bin/env bash
# PWA 백엔드(GitHub Actions)용 YouTube 쿠키를 저장소에 등록한다.
#
# 왜 필요한가: GitHub Actions 러너 IP는 데이터센터 대역이라 YouTube가
# "Sign in to confirm you're not a bot"로 차단한다. 로그인 쿠키를 싣고 가야 한다.
#
# 사용법:
#   1) 브라우저에서 YouTube 로그인
#   2) 쿠키 내보내기 (아래 참고)
#   3) ./tools/setup_pwa_cookie.sh ~/Downloads/cookies.txt
set -euo pipefail

SRC="${1:-}"
if [ -z "$SRC" ] || [ ! -f "$SRC" ]; then
  echo "사용법: $0 <cookies.txt 경로>" >&2
  echo "" >&2
  echo "내보내기 방법:" >&2
  echo "  - Chrome/Edge: 'Get cookies.txt LOCALLY' 확장 설치 → youtube.com 로그인 → 내보내기" >&2
  echo "  - 또는: yt-dlp --cookies cookies.txt --skip-download 'https://www.youtube.com/watch?v=aqz-KE-bpKQ'" >&2
  exit 1
fi

if ! grep -q "youtube.com" "$SRC"; then
  echo "경고: $SRC 에 youtube.com 항목이 없습니다. 계속할까요? (y/N)" >&2
  read -r ans
  [ "$ans" = "y" ] || exit 1
fi

REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"

# Chrome 은 모든 도메인의 쿠키를 뽑는다(445KB). Actions 시크릿은 48KB 제한이라
# 그대로 넣으면 422 로 실패한다. yt-dlp 에 필요한 youtube.com 쿠키만 남긴다.
FILTERED="$(mktemp)"
awk -F'\t' 'BEGIN{OFS="\t"} /^#/ {print; next} $1==".youtube.com" || $1=="youtube.com" {print}' "$SRC" > "$FILTERED"
KEPT="$(grep -vc '^#' "$FILTERED" || true)"
if [ "${KEPT:-0}" -eq 0 ]; then
  echo " youtube.com 쿠키가 없습니다. YouTube에 로그인된 브라우저인지 확인하세요." >&2
  rm -f "$FILTERED"
  exit 1
fi
B64="$(base64 < "$FILTERED" | tr -d '\n')"
rm -f "$FILTERED"
echo " youtube 쿠키 ${KEPT}개, base64 ${#B64} 바이트로 저장"

echo "→ $REPO 에 YTDL_COOKIES_B64 저장 (기존 값 덮어씀)"
printf '%s' "$B64" | gh secret set YTDL_COOKIES_B64 --repo "$REPO"

echo "완료. 이제 PWA에서 검색/다운로드를 시도해봐."
echo "주의: 쿠키가 만료되면(보통 몇 주) 이 스크립트를 다시 실행해야 한다."
echo "      쿠키는 계정 접근 권한이 있으므로 절대 커밋하거나 공유하지 마라."
