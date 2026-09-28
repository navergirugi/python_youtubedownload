# 로컬 백엔드 서버 (iPad 다운로드용)

## 왜 필요한가

GitHub Actions 는 데이터센터 IP 라 YouTube 가 미디어 다운로드를 막는다. 실측 결과:

| | 검색 | 다운로드 |
|---|---|---|
| GitHub Actions | ✅ | ❌ (봇차단 / page needs reload) |
| **이 서버 (집 회선 IP)** | ✅ | ✅ |

쿠키·PO token·player_client 를 모두 시도했으나 Actions IP 에서는 뚫리지 않았다.
결국 **다운로드가 되는 백엔드는 집 회선 IP 뿐**이고, 그게 이 서버다.

## 실행

```bash
.venv/bin/python server/app.py
```

출력에 아이패드용 URL 이 나온다:

```
이 Mac:    http://127.0.0.1:8765/
아이패드:  http://192.168.0.23:8765/   (같은 Wi-Fi 에서 Safari 로 열기)
```

아이패드 Safari 로 접속 → 공유 → 홈 화면에 추가.

## 제약

- **같은 Wi-Fi 에서만** 동작 (Mac 이 켜져 있어야 함)
- 집 밖에서는 쓰려면 유료 VPS/프록시 가 필요 (무료 안 됨)

## 설계

Cloudflare Worker 와 **동일한 API 계약**이라 PWA 프런트를 고칠 필요가 없다.

| 엔드포인트 | 동작 |
|---|---|
| `POST /api/run` | 작업 시작 (search 또는 download) |
| `GET /api/run/:id` | `pending` / `done`(rows 또는 downloadUrl) / `failed` |
| `GET /files/:id/:name` | 완성 파일 서빙 |
| `GET /api/health` | 상태 확인 |

`docs/app.js` 는 `location.origin` 이 GitHub Pages 면 Worker, 아니면
same-origin(즉 이 서버)을 쓰므로 **어느 쪽에서 열어도 동작**한다.

## 주의

- 파일은 `data/_local/<runId>/` 에 쌓이고 6시간 후 정리된다
- 이 서버는 인증이 없다. **같은 Wi-Fi 의 모든 기기가 사용할 수 있다** —
  집 안에만 열려 있으므로 단점이지만, 포트를 외부에 노출하지 말 것
