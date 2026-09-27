const API = "https://musicdownloader-api.workers.dev";
const GH = {
  owner: "navergirugi",
  repo: "python_youtubedownload",
  workflow: "pwa.yml",
  branch: "master",
};

const TOKEN_KEY = "md_token";
let mode = "worker"; // 'worker' | 'github' (Worker 미배포 시 토큰 직접 사용 폴백)

const $ = (id) => document.getElementById(id);

// 쿠키 만료를 사용자에게 미리 알린다(검색은 되고 다운로드만 죽는 상태).
// 상태는 cookie_watch 워크플로우가 pwa-status 릴리즈 body 에 JSON 으로 남긴다.
async function showCookieBanner() {
  const el = $("cookieBanner");
  if (!el) return;
  try {
    const res = await fetch(
      "https://api.github.com/repos/navergirugi/python_youtubedownload/releases/tags/pwa-status"
    );
    if (!res.ok) return;
    const body = (await res.json()).body;
    if (body && JSON.parse(body).ok === false) {
      el.hidden = false;
      return;
    }
  } catch {
    /* 상태 확인 실패는 조용히 무시 */
  }
  el.hidden = true;
}
const log = (m, cls = "") => {
  const el = $("log");
  el.className = cls;
  el.textContent = m;
};
const newRunId = () =>
  Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const token = () => localStorage.getItem(TOKEN_KEY) || "";

function useTokenMode() {
  if (mode === "github") return;
  mode = "github";
  $("tokenPanel").hidden = false;
  $("token").value = token();
}

async function workerCall(path, opts) {
  let res;
  try {
    res = await fetch(API + path, {
      ...opts,
      headers: { "Content-Type": "application/json", ...(opts?.headers || {}) },
    });
  } catch {
    useTokenMode();
    return null;
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `요청 실패 (${res.status})`);
  return data;
}

async function ghApi(path, opts = {}) {
  const res = await fetch(`https://api.github.com${path}`, {
    ...opts,
    headers: {
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      ...(token() ? { Authorization: `Bearer ${token()}` } : {}),
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) throw new Error(`GitHub ${res.status}: ${(await res.text()).slice(0, 140)}`);
  return res.status === 204 ? null : res.json();
}

async function dispatch(inputs) {
  if (mode === "worker") {
    const r = await workerCall("/api/run", { method: "POST", body: JSON.stringify(inputs) });
    if (r) return;
  }
  await ghApi(`/repos/${GH.owner}/${GH.repo}/actions/workflows/${GH.workflow}/dispatches`, {
    method: "POST",
    body: JSON.stringify({ ref: GH.branch, inputs }),
  });
}

async function waitForRun(runId, timeoutMs = 15 * 60 * 1000) {
  const started = Date.now();
  const since = new Date(started - 60000).toISOString();
  while (Date.now() - started < timeoutMs) {
    await sleep(5000);
    if (mode === "worker") {
      const r = await workerCall(`/api/run/${runId}`);
      if (r) {
        if (r.status === "done") return r;
        if (r.status === "failed") {
          const e = new Error(r.error || "작업 실패");
          e.runUrl = r.runUrl;
          throw e;
        }
      }
    } else {
      const r = await ghPoll(runId, since);
      if (r) return r;
    }
    log(`처리 중... ${Math.round((Date.now() - started) / 60000)}분 경과`, "muted");
  }
  throw new Error("시간 초과 (15분).");
}

async function ghPoll(runId, sinceIso) {
  const runs = await ghApi(
    `/repos/${GH.owner}/${GH.repo}/actions/workflows/${GH.workflow}/runs` +
      `?per_page=30&event=workflow_dispatch&created=>${encodeURIComponent(sinceIso)}`
  );
  const hit = (runs.workflow_runs || []).find((r) => (r.name || "").includes(runId));
  if (hit && hit.status === "completed" && hit.conclusion !== "success") {
    const e = new Error(`GitHub 작업 실패 (${hit.conclusion})`);
    e.runUrl = hit.html_url;
    throw e;
  }
  let rel;
  try {
    rel = await ghApi(`/repos/${GH.owner}/${GH.repo}/releases/tags/pwa-${runId}`);
  } catch {
    return null;
  }
  let body;
  try {
    body = rel.body ? JSON.parse(rel.body) : {};
  } catch {
    return null;
  }
  if (Array.isArray(body)) {
    await ghApi(`/repos/${GH.owner}/${GH.repo}/releases/${rel.id}`, { method: "DELETE" }).catch(() => {});
    return { status: "done", rows: body };
  }
  if (body.downloaded) {
    const name = body.downloaded.split("/").pop();
    return {
      status: "done",
      filename: name,
      downloadUrl: `https://github.com/${GH.owner}/${GH.repo}/releases/download/${rel.tag_name}/${encodeURIComponent(name)}`,
    };
  }
  return null;
}

function failLog(e) {
  log(`실패: ${e.message}`, "err");
  if (e.runUrl) {
    const a = document.createElement("a");
    a.href = e.runUrl;
    a.target = "_blank";
    a.rel = "noopener";
    a.className = "dl";
    a.style.background = "var(--err)";
    a.textContent = "GitHub 로그 보기";
    $("result").replaceChildren(a);
  }
}

async function doSearch() {
  const artist = $("artist").value.trim();
  const title = $("title").value.trim();
  if (!artist && !title) return log("가수명 또는 제목을 입력하세요.", "err");
  const runId = newRunId();
  log("검색을 요청했어요. 1~2분 걸려요...");
  await dispatch({ runId, mode: "search", artist, title });
  const r = await waitForRun(runId);
  renderResults(r.rows || [], artist, title);
}

function renderResults(rows, artist, title) {
  const box = $("results");
  box.innerHTML = "";
  if (!rows.length) return log("검색 결과가 없어요.", "err");
  log(`${rows.length}건 찾음. 행을 눌러 다운로드하세요.`, "ok");
  rows.forEach((r) => {
    const el = document.createElement("button");
    el.className = "row";
    const t = document.createElement("span");
    t.className = "t";
    t.textContent = r.title;
    const m = document.createElement("span");
    m.className = "m";
    m.textContent = [r.channel, r.duration].filter(Boolean).join(" · ");
    const u = document.createElement("span");
    u.className = "u";
    u.textContent = r.url;
    el.append(t, m, u);
    el.onclick = () => doDownload(r, artist || r.channel, title || r.title);
    box.appendChild(el);
  });
}

async function doDownload(cand, artist, title) {
  const kind = $("kind").value;
  const quality = kind === "audio" ? $("abr").value : $("vres").value;
  const runId = newRunId();
  log(`"${title}" 다운로드 시작. 1~3분 걸려요...`);
  try {
    await dispatch({ runId, mode: "download", url: cand.url, artist, title, kind, quality });
    const r = await waitForRun(runId);
    const a = document.createElement("a");
    a.href = r.downloadUrl;
    a.className = "dl";
    a.textContent = `⬇ ${r.filename}`;
    $("result").replaceChildren(a);
    log(`완료: ${r.filename} — 누르면 Files 앱으로 저장돼요.`, "ok");
  } catch (e) {
    failLog(e);
  }
}

$("btnSearch").onclick = () => doSearch().catch(failLog);
$("tokenSave").onclick = () => {
  localStorage.setItem(TOKEN_KEY, $("token").value.trim());
  log("토큰 저장됨 (이 기기에만 보관).", "ok");
};
$("kind").onchange = () => {
  $("audioOpts").style.display = $("kind").value === "audio" ? "" : "none";
  $("videoOpts").style.display = $("kind").value === "video" ? "" : "none";
};
showCookieBanner();
