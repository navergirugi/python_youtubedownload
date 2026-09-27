# Cloudflare Worker 백엔드 (PWA 공유용)

PWA가 GitHub API를 **직접** 호출하지 않고 이 Worker를 thru 해서 호출하게 만들어
사용자가 **GitHub 토큰을 입력할 필요 없이** URL만 열면 되게 한다.

무료 티어로 충분하다. 무거운 작업(yt-dlp)은 GitHub Actions가 하므로 Worker는
중계 + 폴링만 한다.

## 흐름

```
[사용자 PWA]  ──POST /api/run──▶  [Worker]  ──▶ GitHub Actions (pwa.yml)
     │            secrets 보유      │              yt-dlp
     │                              │                 │
     └────GET /api/run/:id──────────┘◀── 릴리즈 body ◀──┘
```

- `POST /api/run` — 워크플로우 dispatch
- `GET /api/run/:runId` — 폴링. `pending` / `done`(rows 또는 downloadUrl) / `failed`
- 검색 결과는 릴리즈 body에 담겨오며, 읽는 즉시 릴리즈를 삭제한다
- 다운로드는 릴리즈를 남긴다(파일이 살아있어야 하므로). 야간 워크플로우가 정리

## 배포

Cloudflare 계정(무료) 필요.

```bash
cd worker
npm install -g wrangler
wrangler login

# secret 2개 주입
wrangler secret put GH_TOKEN          # GitHub PAT: workflow + repo 스코프
wrangler secret put YTDL_COOKIES_B64  # cookies.txt 를 base64 한 것

wrangler deploy
```

배포 후 출력되는 URL(예: `https://musicdownloader-api.<your-subdomain>.workers.dev`)을
`docs/app.js` 맨 위 `API` 상수에 넣는다. 기본값은 `workers.dev` 기준.

> base64는 이렇게: `base64 < cookies.txt | tr -d '\n'`

## 로컬 테스트

```bash
cd worker && node test/worker.test.mjs   # fetch mock, 18 assertions
```

## 운영 메모

- `GH_TOKEN`이 새 토큰으로 갱신되면 secret을 다시 put 해야 한다
- `YTDL_COOKIES_B64`은 유튜브 쿠키 만료 시(보통 몇 주) 갱신한다.
  안 갱신하면 **다운로드만** 전체 실패하고 검색은 된다
- 검색 릴리즈는 클라이언트가 즉시 삭제하지만, 실패한 런은 야간 워크플로우가 정리한다
