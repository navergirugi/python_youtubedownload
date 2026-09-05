"""무서버 강제 업데이트 체크 (GitHub raw version.json을 서버처럼 사용)."""
from __future__ import annotations

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

    r = requests.get(config.UPDATE_URL, timeout=config.UPDATE_TIMEOUT)
    r.raise_for_status()
    d = r.json()
    return d if isinstance(d, dict) else {}


def check_update() -> tuple[bool, bool, dict]:
    """(업데이트 필요, 강제 여부, 원격 정보) 반환.

    - current < min_required → 강제 (실행 차단)
    - min_required <= current < latest → 선택
    - 네트워크 실패/파싱 실패 → (False, False, {}) : 오프라인 실행 보장
    """
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
    except Exception:
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
