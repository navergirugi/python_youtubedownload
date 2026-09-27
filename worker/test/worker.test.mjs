import worker from "../src/index.js";

const ENV = { GH_TOKEN: "test-token", ALLOWED_ORIGIN: "https://navergirugi.github.io" };

function mockFetch(handlers) {
  const calls = [];
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url, init });
    for (const h of handlers) {
      if (h.match(url, init)) return h.reply(url, init);
    }
    return { ok: false, status: 404, text: async () => "nomatch", json: async () => ({}) };
  };
  return calls;
}

const json = (body, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
  text: async () => JSON.stringify(body),
});

let pass = 0, fail = 0;
function check(name, cond, extra = "") {
  if (cond) { pass++; console.log(`  ok   ${name}`); }
  else { fail++; console.log(`  FAIL ${name} ${extra}`); }
}

const dispatchOk = (url) => url.includes("/dispatches");
const runsPending = (url) => url.includes("/runs?");
const releaseGet = (url) => /releases\/tags\/pwa-/.test(url);
const releaseDel = (url, init) => init?.method === "DELETE";

console.log("1) POST /api/run dispatches");
{
  const calls = mockFetch([{ match: dispatchOk, reply: () => json({}, 204) }]);
  const res = await worker.fetch(
    new Request("https://w.example/api/run", { method: "POST", body: JSON.stringify({ runId: "abc1", mode: "search", artist: "IU" }) }),
    ENV
  );
  const body = await res.json();
  check("200 + runId echoed", res.status === 200 && body.runId === "abc1", JSON.stringify(body));
  const sent = JSON.parse(calls[0].init.body);
  check("mode forwarded", sent.inputs.mode === "search");
  check("artist trimmed/limited", sent.inputs.artist === "IU");
  check("branch forwarded", calls[0].init.body.includes("master"));
}

console.log("2) POST /api/run without runId -> 400");
{
  mockFetch([]);
  const res = await worker.fetch(
    new Request("https://w.example/api/run", { method: "POST", body: JSON.stringify({}) }), ENV);
  check("400", res.status === 400, String(res.status));
}

console.log("3) GET poll -> pending (no run, no release)");
{
  mockFetch([
    { match: runsPending, reply: () => json({ workflow_runs: [] }) },
    { match: releaseGet, reply: () => json({ message: "Not Found" }, 404) },
  ]);
  const res = await worker.fetch(new Request("https://w.example/api/run/abc1"), ENV);
  const b = await res.json();
  check("status pending", b.status === "pending", JSON.stringify(b));
}

console.log("4) GET poll -> done (search rows, release deleted)");
{
  const calls = mockFetch([
    { match: runsPending, reply: () => json({ workflow_runs: [{ name: "pwa-abc1", status: "completed", conclusion: "success" }] }) },
    { match: releaseGet, reply: () => json({ id: 99, tag_name: "pwa-abc1", body: JSON.stringify([{ title: "t", url: "u" }]) }) },
    { match: releaseDel, reply: () => json({}, 204) },
  ]);
  const res = await worker.fetch(new Request("https://w.example/api/run/abc1"), ENV);
  const b = await res.json();
  check("status done", b.status === "done", JSON.stringify(b));
  check("rows returned", Array.isArray(b.rows) && b.rows.length === 1);
  check("release deleted", calls.some((c) => c.init?.method === "DELETE"));
}

console.log("5) GET poll -> failed (run conclusion != success)");
{
  mockFetch([
    { match: runsPending, reply: () => json({ workflow_runs: [{ name: "pwa-abc1", status: "completed", conclusion: "failure", html_url: "https://gh/run" }] }) },
    { match: releaseGet, reply: () => json({}, 404) },
  ]);
  const res = await worker.fetch(new Request("https://w.example/api/run/abc1"), ENV);
  const b = await res.json();
  check("status failed", b.status === "failed", JSON.stringify(b));
  check("runUrl passed", b.runUrl === "https://gh/run");
}

console.log("6) GET poll -> done (download, no delete so file survives)");
{
  const calls = mockFetch([
    { match: runsPending, reply: () => json({ workflow_runs: [{ name: "pwa-abc1", status: "completed", conclusion: "success" }] }) },
    { match: releaseGet, reply: () => json({ id: 100, tag_name: "pwa-abc1", body: JSON.stringify({ downloaded: "/repo/data/audio/IU - Celebrity.mp3" }) }) },
  ]);
  const res = await worker.fetch(new Request("https://w.example/api/run/abc1"), ENV);
  const b = await res.json();
  check("status done", b.status === "done", JSON.stringify(b));
  check("filename", b.filename === "IU - Celebrity.mp3", String(b.filename));
  check("downloadUrl built", /releases\/download\/pwa-abc1\/IU%20-%20Celebrity\.mp3$/.test(b.downloadUrl), String(b.downloadUrl));
  check("NOT deleted (file must survive)", !calls.some((c) => c.init?.method === "DELETE"));
}

console.log("7) CORS preflight + GH_TOKEN missing");
{
  mockFetch([]);
  const opt = await worker.fetch(new Request("https://w.example/api/run", { method: "OPTIONS" }), ENV);
  check("OPTIONS 204", opt.status === 204);
  check("CORS origin header", opt.headers.get("Access-Control-Allow-Origin") === "https://navergirugi.github.io");

  const res = await worker.fetch(new Request("https://w.example/api/run/abc1"), { ALLOWED_ORIGIN: "*" });
  check("500 without GH_TOKEN", res.status === 500, String(res.status));
}

console.log("8) rate limit: 13th run from same IP is rejected");
{
  mockFetch([{ match: dispatchOk, reply: () => json({}, 204) }]);
  const fire = (ip, runId) =>
    worker.fetch(
      new Request("https://w.example/api/run", {
        method: "POST",
        headers: { "CF-Connecting-IP": ip },
        body: JSON.stringify({ runId }),
      }),
      ENV
    );
  const statuses = [];
  for (let i = 1; i <= 13; i++) statuses.push((await fire("10.0.0.1", `r${i}`)).status);
  check("first 12 allowed", statuses.slice(0, 12).every((s) => s === 200), statuses.join(","));
  check("13th is 429", statuses[12] === 429, String(statuses[12]));
  const other = await fire("10.0.0.2", "rX");
  check("different IP unaffected", other.status === 200, String(other.status));
  const b = await (await worker.fetch(
    new Request("https://w.example/api/run", { method: "POST", headers: { "CF-Connecting-IP": "10.0.0.1" }, body: JSON.stringify({ runId: "rY" }) }),
    ENV
  )).json();
  check("429 message is Korean", /너무 많/.test(b.error || ""), String(b.error));
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
