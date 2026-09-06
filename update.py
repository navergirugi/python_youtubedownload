"""무서버 강제 업데이트 체크 (GitHub raw version.json을 서버처럼 사용)."""
from __future__ import annotations

import os
import sys
import time
import webbrowser

import config


def parse_version(s: str) -> tuple[int, ...]:
    parts: list[int] = []
    for p in str(s).strip().lstrip("v").split("."):
        num = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(num) if num else 0)
    return tuple(parts) or (0,)


def fetch_remote_info() -> dict:
    import requests

    # raw CDN 캐시(수 분 stale) 우회: 쿼리가 바뀌면 캐시 키가 달라짐
    sep = "&" if "?" in config.UPDATE_URL else "?"
    url = f"{config.UPDATE_URL}{sep}t={int(time.time())}"
    r = requests.get(url, timeout=config.UPDATE_TIMEOUT)
    r.raise_for_status()
    d = r.json()
    return d if isinstance(d, dict) else {}


def check_update() -> tuple[bool, bool, dict]:
    """(업데이트 필요, 강제 여부, 원격 정보) 반환.

    - current < min_required → 강제 (실행 차단)
    - min_required <= current < latest → 선택
    - 네트워크 실패/파싱 실패 → (False, False, {}) : 오프라인 실행 보장
    - SKIP_UPDATE_CHECK=1 환경변수 → (False, False, {}) : 로컬 테스트용 우회
    """
    if os.environ.get("SKIP_UPDATE_CHECK") == "1":
        return False, False, {}
    try:
        info = fetch_remote_info()
        cur = parse_version(config.APP_VERSION)
        latest = parse_version(info.get("latest", config.APP_VERSION))
        minimum = parse_version(info.get("min_required", config.APP_VERSION))
        if cur < minimum:
            return True, True, info
        if cur < latest:
            return True, False, info
        return False, False, info
    except Exception as e:
        if sys.stderr is not None:
            print(f"업데이트 확인 실패: {e}", file=sys.stderr)
        return False, False, {}


def open_release_page(info: dict) -> None:
    url = info.get("url") if isinstance(info, dict) else None
    if url:
        try:
            webbrowser.open(str(url))
        except Exception:
            pass


def format_notice(info: dict) -> str:
    latest = info.get("latest", "?")
    notes = info.get("notes", "")
    url = info.get("url", "")
    msg = f"새 버전 v{latest}이 있습니다."
    if notes:
        msg += f"\n{notes}"
    if url:
        msg += f"\n다운로드: {url}"
    return msg
