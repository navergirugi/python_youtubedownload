"""YouTube 쿠키 상태 점검.

갱신은 불가능하다(브라우저 로그인 세션이 필요하므로). 대신 만료를 빨리 알아내기
위해 주기적으로 실제 yt-dlp 호출을 시도하고, 막혔으면 알림을 낸다.

exit 0 = 정상, exit 1 = 쿠키 만료/무효
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile

PROBE_URL = "https://www.youtube.com/watch?v=rJ5iyzjErr8"


def write_cookies() -> str | None:
    b64 = os.environ.get("YTDL_COOKIES_B64", "").strip()
    if not b64:
        return None
    path = os.path.join(tempfile.mkdtemp(prefix="ck-"), "cookies.txt")
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64))
    os.chmod(path, 0o600)
    return path


def probe() -> tuple[bool, str]:
    cookies = write_cookies()
    if not cookies:
        return False, "YTDL_COOKIES_B64 가 설정되지 않음"
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--cookies", cookies,
        "--extractor-args", "youtube:player_client=web;fetch_pot=never",
        "--skip-download", "--no-warnings", "-j", PROBE_URL,
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    blob = p.stdout + p.stderr
    if p.returncode == 0 and '"url"' in blob:
        return True, "ok"
    if "not a bot" in blob or "Sign in to confirm" in blob:
        return False, "bot-check (쿠키 만료/무효 또는 IP 차단)"
    if "401" in blob or "403" in blob:
        return False, "인증 거부 (쿠키 만료)"
    return False, blob.strip()[:200]


def main() -> None:
    ok, detail = probe()
    print(f"COOKIE_OK={ok} DETAIL={detail}")
    if os.environ.get("STATUS_OUT"):
        with open(os.environ["STATUS_OUT"], "w", encoding="utf-8") as f:
            json.dump({"ok": ok, "detail": detail}, f, ensure_ascii=False)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
