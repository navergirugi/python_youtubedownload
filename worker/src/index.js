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
