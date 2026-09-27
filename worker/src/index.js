const REPO_OWNER = "navergirugi";
const REPO_NAME = "python_youtubedownload";
const WORKFLOW = "pwa.yml";
const BRANCH = "master";

function corsHeaders(env) {
  const origin = env.ALLOWED_ORIGIN || "*";
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
  };
}

function reply(data, status, env) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders(env) },
  });
}

function api(path, env, init = {}) {
  return fetch(`https://api.github.com${path}`, {
    ...init,
    headers: {
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      Authorization: `Bearer ${env.GH_TOKEN}`,
      ...(init.headers || {}),
    },
  });
}

async function dispatch(runId, inputs, env) {
  const res = await api(
    `/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/${WORKFLOW}/dispatches`,
    env,
    { method: "POST", body: JSON.stringify({ ref: BRANCH, inputs }) }
  );
  if (!res.ok) return { error: `dispatch ${res.status}`, detail: (await res.text()).slice(0, 200) };
  return { ok: true };
}

async function findRun(runId, env) {
  const since = new Date(Date.now() - 36e5).toISOString();
  const res = await api(
    `/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/${WORKFLOW}/runs?per_page=30&event=workflow_dispatch&created=>${encodeURIComponent(since)}`,
    env
  );
  if (!res.ok) return null;
  const data = await res.json();
  return (data.workflow_runs || []).find((r) => (r.name || "").includes(runId)) || null;
}

async function getRelease(tag, env) {
  const res = await api(`/repos/${REPO_OWNER}/${REPO_NAME}/releases/tags/${tag}`, env);
  if (!res.ok) return null;
  return res.json();
}

async function deleteRelease(id, env) {
  await api(`/repos/${REPO_OWNER}/${REPO_NAME}/releases/${id}`, env, { method: "DELETE" });
}

function downloadUrl(tag, name) {
  return `https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/download/${tag}/${encodeURIComponent(name)}`;
}

// 이 Worker 는 공개 엔드포인트이고, 실행되는 다운로드가 소유자의 YouTube 계정
// 세션을 쓴다. 남이 일부러 남용하면 그 계정이 밴당되므로 IP 별 요청 수를 제한한다.
// (Worker 아이솔레이트 메모리 기준이라 완벽하진 않지만 우의도성 남용은 막는다.)
const BUCKETS = new Map();
const WINDOW_MS = 60 * 60 * 1000;
const MAX_RUNS_PER_WINDOW = 12;

function rateLimited(ip) {
  const now = Date.now();
  const hits = (BUCKETS.get(ip) || []).filter((t) => now - t < WINDOW_MS);
  if (hits.length >= MAX_RUNS_PER_WINDOW) {
    BUCKETS.set(ip, hits);
    return true;
  }
  hits.push(now);
  BUCKETS.set(ip, hits);
  if (BUCKETS.size > 5000) {
    for (const [k, v] of BUCKETS) {
      if (!v.some((t) => now - t < WINDOW_MS)) BUCKETS.delete(k);
    }
  }
  return false;
}

async function poll(runId, env) {
  const run = await findRun(runId, env);
  if (run && run.status === "completed" && run.conclusion !== "success") {
    return { status: "failed", error: `GitHub 작업 실패 (${run.conclusion})`, runUrl: run.html_url };
  }
  const rel = await getRelease(`pwa-${runId}`, env);
  if (!rel) return { status: "pending" };

  let body = {};
  try {
    body = rel.body ? JSON.parse(rel.body) : {};
  } catch {
    return { status: "failed", error: "결과 형식 오류", runUrl: run?.html_url };
  }

  if (Array.isArray(body)) {
    await deleteRelease(rel.id, env);
    return { status: "done", rows: body };
  }
  if (body.downloaded) {
    const name = body.downloaded.split("/").pop();
    return { status: "done", filename: name, downloadUrl: downloadUrl(rel.tag_name, name) };
  }
  return { status: "pending" };
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders(env) });

    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "");

    if (!env.GH_TOKEN) return reply({ error: "GH_TOKEN secret 미설정" }, 500, env);

    if (request.method === "POST" && path === "/api/run") {
      let b;
      try {
        b = await request.json();
      } catch {
        return reply({ error: "JSON 파싱 실패" }, 400, env);
      }
      if (!b.runId) return reply({ error: "runId 누락" }, 400, env);
      const ip = request.headers.get("CF-Connecting-IP") || "unknown";
      if (rateLimited(ip)) {
        return reply({ error: "요청이 너무 많습니다. 1시간 뒤에 다시 시도해 주세요." }, 429, env);
      }
      const r = await dispatch(b.runId, {
        runId: String(b.runId),
        mode: b.mode === "download" ? "download" : "search",
        artist: String(b.artist ?? "").slice(0, 120),
        title: String(b.title ?? "").slice(0, 120),
        kind: b.kind === "video" ? "video" : "audio",
        quality: String(b.quality ?? "").slice(0, 12),
        url: String(b.url ?? "").slice(0, 300),
      }, env);
      if (r.error) return reply({ error: r.error, detail: r.detail }, 502, env);
      return reply({ runId: b.runId }, 200, env);
    }

    const m = path.match(/^\/api\/run\/([A-Za-z0-9_-]{1,40})$/);
    if (m && request.method === "GET") {
      return reply(await poll(m[1], env), 200, env);
    }

    return reply({ error: "not found" }, 404, env);
  },
};
