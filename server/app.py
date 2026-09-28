"""로컬 백엔드 서버 — 집 회선 IP에서 돌리는 PWA 백엔드.

GitHub Actions(데이터센터 IP)는 YouTube 가 미디어 다운로드를 막는다. 이 서버는
네 Mac 에서 직접 돌리므로 집 회선 IP 를 쓰고, 그래서 다운로드가 된다.

Cloudflare Worker 와 API 계약을 동일하게 유지해서 PWA 프런트는 수정 없이
바꾸면 된다. 표준 라이브러리만 쓴다.
"""
from __future__ import annotations

import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import quote, unquote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PORT = int(os.environ.get("MD_PORT", "8765"))
SITE_DIR = ROOT / "docs"
SERVE_DIR = ROOT / "data" / "_local"
JOB_TTL_SECONDS = 6 * 60 * 60

JOBS: dict[str, dict] = {}
RUN_ID_RE = re.compile(r"^[a-z0-9]{4,40}$")

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "video/mp4",
    ".webm": "audio/webm",
    ".opus": "audio/opus",
}


def lan_ip() -> str:
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _search(job: dict) -> None:
    import config
    import search

    query = f"{job.get('artist', '')} {job.get('title', '')}".strip()
    if not query:
        raise ValueError("가수명 또는 제목을 입력하세요.")
    cands = search.youtube_search(query, scope="music", flat=True)
    job["rows"] = [
        {"title": c.title, "url": c.url, "channel": c.channel, "duration": c.duration_str}
        for c in cands
    ]


def _download(job: dict) -> None:
    import config
    import download

    url = job.get("url") or ""
    artist = job.get("artist") or "Unknown"
    title = job.get("title") or "untitled"
    kind = job.get("kind") or "audio"
    quality = job.get("quality") or (
        config.DEFAULT_AUDIO_BITRATE if kind == "audio" else config.DEFAULT_VIDEO_QUALITY
    )
    if kind == "audio":
        path = download.download_audio(url, artist, title, bitrate=quality)
    else:
        path = download.download_video(url, artist, title, quality=quality)

    dest = SERVE_DIR / job["id"]
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / os.path.basename(path)
    shutil.move(path, target)
    job["filename"] = target.name
    job["size"] = target.stat().st_size


def _run_job(job: dict) -> None:
    try:
        if job["mode"] == "download":
            _download(job)
        else:
            _search(job)
        job["status"] = "done"
    except Exception as e:  # 사용자에게 사유를 그대로 보여줘야 함
        job["status"] = "failed"
        job["error"] = str(e)[:300]
        sys.stderr.write(f"[local] {job['id']} failed: {e}\n")


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "MusicDownloaderLocal/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[local] " + (fmt % args) + "\n")

    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        origin = self.headers.get("Origin", "*")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code: int, data: dict) -> None:
        self._send(code, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_OPTIONS(self) -> None:
        self._send(204, b"", "text/plain")

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/api/run":
            return self._json(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "JSON 파싱 실패"})

        run_id = str(body.get("runId") or uuid.uuid4().hex[:12])
        if not RUN_ID_RE.match(run_id):
            return self._json(400, {"error": "runId 형식 오류"})

        job = {
            "id": run_id,
            "status": "pending",
            "mode": "download" if body.get("mode") == "download" else "search",
            "artist": str(body.get("artist", ""))[:120],
            "title": str(body.get("title", ""))[:120],
            "url": str(body.get("url", ""))[:300],
            "kind": "video" if body.get("kind") == "video" else "audio",
            "quality": str(body.get("quality", ""))[:12],
            "created": time.time(),
        }
        JOBS[run_id] = job
        threading.Thread(target=_run_job, args=(job,), daemon=True).start()
        self._json(200, {"runId": run_id})

    def do_GET(self) -> None:
        # 파일명에 한글이 들어오면 percent-encoded 로 오므로 반드시 디코딩한다.
        path = unquote(self.path.split("?", 1)[0]).rstrip("/") or "/"

        m = re.match(r"^/api/run/([A-Za-z0-9]+)$", path)
        if m:
            job = JOBS.get(m.group(1))
            if not job:
                return self._json(404, {"error": "알 수 없는 작업입니다."})
            if job["status"] == "done" and job.get("filename"):
                return self._json(200, {
                    "status": "done",
                    "filename": job["filename"],
                    "downloadUrl": f"/files/{job['id']}/{job['filename']}",
                })
            if job["status"] == "done":
                return self._json(200, {"status": "done", "rows": job.get("rows", [])})
            if job["status"] == "failed":
                return self._json(200, {"status": "failed", "error": job.get("error", "실패")})
            return self._json(200, {"status": "pending"})

        m = re.match(r"^/files/([A-Za-z0-9]+)/([^/]+)$", path)
        if m:
            run_id, name = m.group(1), m.group(2)
            if not RUN_ID_RE.match(run_id) or "/" in name or ".." in name:
                return self._json(400, {"error": "잘못된 경로"})
            f = SERVE_DIR / run_id / name
            if not f.is_file():
                return self._json(404, {"error": "파일 없음"})
            ctype = MIME.get(f.suffix.lower(), "application/octet-stream")
            # HTTP 헤더는 latin-1 이라 한글 파일명을 그대로 넣으면 서버가 죽는다.
            # RFC 5987 의 filename* 로 percent-encoding 한다.
            disp = f"attachment; filename*=UTF-8''{quote(name)}"
            return self._send(200, f.read_bytes(), ctype, {"Content-Disposition": disp})

        if path == "/api/health":
            return self._json(200, {"ok": True, "jobs": len(JOBS)})

        rel = "index.html" if path == "/" else path.lstrip("/")
        f = (SITE_DIR / rel).resolve()
        if not str(f).startswith(str(SITE_DIR.resolve())) or not f.is_file():
            return self._json(404, {"error": "not found"})
        ctype = MIME.get(f.suffix.lower(), "application/octet-stream")
        self._send(200, f.read_bytes(), ctype)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def _gc() -> None:
    while True:
        time.sleep(600)
        cutoff = time.time() - JOB_TTL_SECONDS
        for k in [k for k, v in JOBS.items() if v["created"] < cutoff]:
            JOBS.pop(k, None)
        shutil.rmtree(SERVE_DIR, ignore_errors=True)


def main() -> None:
    import config

    SERVE_DIR.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=_gc, daemon=True).start()
    config.ensure_dirs()
    config.check_ffmpeg()
    ip = lan_ip()
    with Server(("0.0.0.0", PORT), Handler) as httpd:
        print(f"Music Downloader 로컬 서버")
        print(f"  이 Mac:  http://127.0.0.1:{PORT}/")
        print(f"  아이패드: http://{ip}:{PORT}/   (같은 Wi-Fi 에서 Safari 로 열기)")
        print(f"  Ctrl+C 로 종료")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n종료.")


if __name__ == "__main__":
    main()
