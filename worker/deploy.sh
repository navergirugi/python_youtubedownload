#!/usr/bin/env bash
# Cloudflare Worker 1-command deploy.
#
#   ./worker/deploy.sh
#
# Interactively sets the two secrets, deploys, then tells you whether the
# resulting URL matches the one hardcoded in docs/app.js (and how to fix it
# if not).
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v wrangler >/dev/null 2>&1; then
  echo "wrangler를 설치합니다..."
  npm install -g wrangler
fi

if ! node -e 'process.exit(0)' 2>/dev/null; then
  echo "node가 필요합니다." >&2
  exit 1
fi

echo "==> Cloudflare 로그인"
wrangler login

echo
echo "==> GH_TOKEN (GitHub PAT: workflow + repo 스코프)"
echo "   기존에 쓰던 토큰이 노출됐다면 먼저 GitHub에서 revoke 하세요."
wrangler secret put GH_TOKEN

echo
echo "==> YTDL_COOKIES_B64 (cookies.txt 를 base64)"
echo "   먼저 cookies.txt 를 준비했어야 합니다 (tools/README 참고)."
wrangler secret put YTDL_COOKIES_B64

echo
echo "==> 배포"
OUT="$(wrangler deploy)"
echo "$OUT"

URL="$(printf '%s' "$OUT" | grep -oE 'https://[a-z0-9.-]+\.workers\.dev' | head -n1 || true)"
if [ -z "$URL" ]; then
  echo
  echo "배포 URL을 못 읽었습니다. 위 출력에서 https://...workers.dev 를 확인하세요."
  exit 0
fi

DEFAULT="https://musicdownloader-api.workers.dev"
echo
echo "배포 URL: $URL"
if [ "$URL" = "$DEFAULT" ]; then
  echo "app.js 기본값과 일치합니다. 추가 수정 없음."
else
  echo "app.js 기본값($DEFAULT)과 다릅니다. 아래 명령으로 자동 수정하세요:"
  echo "  ./tools/set_worker_url.sh $URL"
fi
