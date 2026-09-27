const CFG = {
  owner: "navergirugi",
  repo: "python_youtubedownload",
  workflow: "pwa.yml",
  branch: "master",
};

const TOKEN_KEY = "md_token";
const $ = (id) => document.getElementById(id);
const log = (m, cls = "") => {
  const el = $("log");
  el.className = cls;
  el.textContent = m;
};
const newRunId = () =>
  Date.now().toString(36) + Math.random().toString(36).slice(2, 8);

function token() {
  return localStorage.getItem(TOKEN_KEY) || "";
}
function saveToken(v) {
  localStorage.setItem(TOKEN_KEY, v.trim());
}

async function api(path, opts = {}) {
  const res = await fetch(`https://api.github.com${path}`, {
    ...opts,
    headers: {
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      ...(token() ? { Authorization: `Bearer ${token()}` } : {}),
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`GitHub ${res.status}: ${t.slice(0, 160)}`);
  }
  return res.status === 204 ? null : res.json();
}

async function dispatch(inputs) {
  await api(
    `/repos/${CFG.owner}/${CFG.repo}/actions/workflows/${CFG.workflow}/dispatches`,
    { method: "POST", body: JSON.stringify({ ref: CFG.branch, inputs }) }
  );
}

async function checkRunFailed(runId, sinceIso) {
  const q = `?per_page=30&event=workflow_dispatch&created=>${encodeURIComponent(sinceIso)}`;
  const path = `/repos/${CFG.owner}/${CFG.repo}/actions/workflows/${CFG.workflow}/runs${q}`;
  const data = await api(path);
  const hit = (data.workflow_runs || []).find((r) => (r.name || "").includes(runId));
  if (hit && hit.status === "completed" && hit.conclusion !== "success") {
    const err = new Error(`GitHub 작업 실패 (${hit.conclusion})`);
    err.runUrl = hit.html_url;
    throw err;
  }
}

async function waitForRun(runId, timeoutMs = 15 * 60 * 1000) {
  const tag = `pwa-${runId}`;
  const started = Date.now();
  const sinceIso = new Date(started - 60000).toISOString();
  while (Date.now() - started < timeoutMs) {
    await new Promise((r) => setTimeout(r, 5000));
    const mins = Math.round((Date.now() - started) / 60 / 1000);
    log(`GitHub에서 처리 중... ${mins}분 경과`, "muted");
    try {
      return await api(`/repos/${CFG.owner}/${CFG.repo}/releases/tags/${tag}`);
    } catch (e) {
      if (e.runUrl) throw e;
    }
    await checkRunFailed(runId, sinceIso);
  }
  throw new Error("시간 초과 (15분). GitHub Actions 로그를 확인하세요.");
}

function assetUrl(rel, name) {
  return `https://github.com/${CFG.owner}/${CFG.repo}/releases/download/${rel.tag_name}/${encodeURIComponent(name)}`;
}

async function cleanupRun(rel) {
  try {
    await api(`/repos/${CFG.owner}/${CFG.repo}/releases/${rel.id}`, {
      method: "DELETE",
    });
  } catch {
    /* nightly workflow removes leftovers */
  }
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
  log("검색을 GitHub에 요청했어요. 1~2분 걸려요...");
  await dispatch({ runId, mode: "search", artist, title });
  const rel = await waitForRun(runId);
  const json = rel.assets.find((a) => a.name.endsWith(".json"));
  if (!json) throw new Error("결과 파일이 없어요.");
  const rows = await (await fetch(assetUrl(rel, json.name))).json();
  await cleanupRun(rel);
  renderResults(rows, artist, title);
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
    const rel = await waitForRun(runId);
    const file = rel.assets.find(
      (a) => !a.name.endsWith(".json") && /\.(mp3|mp4|m4a|webm)$/i.test(a.name)
    );
    if (!file) throw new Error("완료된 파일이 없어요. Actions 로그를 확인하세요.");
    const a = document.createElement("a");
    a.href = assetUrl(rel, file.name);
    a.className = "dl";
    a.textContent = `⬇ ${file.name}`;
    $("result").replaceChildren(a);
    log(`완료: ${file.name} — 누르면 Files 앱으로 저장돼요.`, "ok");
    await cleanupRun(rel);
  } catch (e) {
    failLog(e);
  }
}

$("btnSearch").onclick = () => doSearch().catch(failLog);
$("tokenSave").onclick = () => {
  saveToken($("token").value);
  log("토큰 저장됨 (이 기기에만 보관).", "ok");
};
$("token").value = token();
$("kind").onchange = () => {
  $("audioOpts").style.display = $("kind").value === "audio" ? "" : "none";
  $("videoOpts").style.display = $("kind").value === "video" ? "" : "none";
};
if (!token()) log("첫 실행: 아래에 GitHub 토큰을 붙여넣고 저장을 눌러주세요.", "muted");
