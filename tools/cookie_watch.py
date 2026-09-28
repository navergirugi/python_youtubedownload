"""YouTube 쿠키 상태 점검.

갱신은 불가능하다(브라우저 로그인 세션이 필요하므로). 대신 만료를 빨리 알아내기
위해 주기적으로 실제 yt-dlp 호출을 시도하고, 막혔으면 알림을 낸다.

exit 0 = 정상, exit 1 = 쿠키 만료/무효
"""
from __future__ import annotations

import base64
import json
import os
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

    # 간접 확인(extract_info, 별도 extractor-args 등)은 실제로는 되는 조합을
    # 실패로 판정해 거짓 경보를 낸 적이 있다. 앱이 쓰는 그대로 실제 1곡을
    # 내려보고 성공 여부를 그대로 쿠키 상태로 쓴다.
    os.environ["MD_COOKIE_FILE"] = cookies
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import download as download_mod

    produced = ""
    try:
        produced = download_mod.download_audio(
            PROBE_URL, "probe", "probe", normalize=False
        )
    except Exception as e:
        blob = str(e)
        if "not a bot" in blob or "Sign in to confirm" in blob:
            return False, "bot-check (쿠키 만료/무효 또는 IP 차단)"
        if "reload" in blob.lower():
            return False, "player 응답 실패 (쿠키 만료 의심)"
        if "401" in blob or "403" in blob:
            return False, "인증 거부 (쿠키 만료)"
        return False, blob.strip()[:200]
    finally:
        if produced and os.path.exists(produced):
            os.remove(produced)

    return True, "ok (실제 오디오 1곡 다운로드 성공)"


def main() -> None:
    ok, detail = probe()
    print(f"COOKIE_OK={ok} DETAIL={detail}")
    if os.environ.get("STATUS_OUT"):
        with open(os.environ["STATUS_OUT"], "w", encoding="utf-8") as f:
            json.dump({"ok": ok, "detail": detail}, f, ensure_ascii=False)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
