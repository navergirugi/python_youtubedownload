const API = "https://musicdownloader-api.workers.dev";
const $ = (id) => document.getElementById(id);
const log = (m, cls = "") => {
  const el = $("log");
  el.className = cls;
  el.textContent = m;
};
const newRunId = () =>
  Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    ...opts,
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `요청 실패 (${res.status})`);
  return data;
}

async function dispatch(inputs) {
  await api("/api/run", { method: "POST", body: JSON.stringify(inputs) });
}

async function waitForRun(runId, timeoutMs = 15 * 60 * 1000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    await sleep(5000);
    const r = await api(`/api/run/${runId}`);
    if (r.status === "done") return r;
    if (r.status === "failed") {
      const e = new Error(r.error || "작업 실패");
      e.runUrl = r.runUrl;
      throw e;
    }
    const mins = Math.round((Date.now() - started) / 60000);
    log(`처리 중... ${mins}분 경과`, "muted");
  }
  throw new Error("시간 초과 (15분).");
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
$("kind").onchange = () => {
  $("audioOpts").style.display = $("kind").value === "audio" ? "" : "none";
  $("videoOpts").style.display = $("kind").value === "video" ? "" : "none";
};
