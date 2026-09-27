#!/usr/bin/env bash
# 배포된 Workers URL을 docs/app.js 에 반영한다.
#
#   ./tools/set_worker_url.sh https://musicdownloader-api.example.workers.dev
set -euo pipefail

URL="${1:-}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/docs/app.js"

if [ -z "$URL" ] || [ "${URL#https://}" = "$URL" ]; then
  echo "사용법: $0 https://<subdomain>.workers.dev" >&2
  exit 1
fi

python3 - "$APP" "$URL" <<'PY'
import re, sys
path, url = sys.argv[1], sys.argv[2]
src = open(path, encoding="utf-8").read()
new, n = re.subn(r'const API = "[^"]*";', f'const API = "{url}";', src, count=1)
if not n:
    sys.exit('const API 줄을 찾지 못했습니다.')
open(path, "w", encoding="utf-8").write(new)
print(f"API -> {url}")
PY

echo "Pages 반영까지 1~2분 걸려요. 그 뒤로 PWA 가 새 URL 을 씁니다."
