"""Single-file web dashboard served by the API at ``/``.

Kept as a Python string so it ships with the package (no static-file packaging
needed). It is a dependency-free SPA that talks to the same REST API: submit a
scan, watch its status, download the bundle and view the documentation
(Markdown + Mermaid) rendered live in the browser.
"""

from __future__ import annotations

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Codebase Architect</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
:root { color-scheme: light dark; --line:#8884; --accent:#3b82f6; }
* { box-sizing: border-box; }
body { font: 15px/1.55 system-ui, sans-serif; margin: 0; }
header { padding: .8rem 1.2rem; border-bottom: 1px solid var(--line); display:flex;
         align-items:baseline; gap:.6rem; }
header h1 { font-size: 1.1rem; margin: 0; }
header span { color:#888; font-size:.85rem; }
main { display: grid; grid-template-columns: 360px 1fr; gap: 0; height: calc(100vh - 53px); }
aside { border-right: 1px solid var(--line); padding: 1rem; overflow:auto; }
section.detail { padding: 1rem 1.4rem; overflow:auto; }
label { display:block; font-size:.8rem; color:#888; margin:.6rem 0 .2rem; }
input, select, button { font: inherit; padding: .45rem .6rem; border:1px solid var(--line);
        border-radius:6px; background:Canvas; color:CanvasText; width:100%; }
.row { display:flex; gap:.5rem; align-items:center; }
.row input[type=checkbox] { width:auto; }
button { cursor:pointer; }
button.primary { background: var(--accent); color:#fff; border-color: var(--accent);
        margin-top:.8rem; font-weight:600; }
button.ghost { width:auto; }
h2 { font-size:.95rem; border-bottom:1px solid var(--line); padding-bottom:.3rem; margin-top:1.4rem; }
ul.scans { list-style:none; padding:0; margin:.4rem 0; }
ul.scans li { padding:.45rem .5rem; border-radius:6px; cursor:pointer; display:flex;
        justify-content:space-between; gap:.4rem; }
ul.scans li:hover { background:#8881; }
ul.scans li.active { background:#8882; }
.badge { font-size:.7rem; padding:.05rem .45rem; border-radius:999px; border:1px solid var(--line); }
.badge.done { color:#16a34a; border-color:#16a34a; }
.badge.running, .badge.queued { color:#d97706; border-color:#d97706; }
.badge.failed { color:#dc2626; border-color:#dc2626; }
.summary { display:grid; grid-template-columns: repeat(auto-fill,minmax(120px,1fr)); gap:.5rem;
        margin:.6rem 0; }
.summary div { border:1px solid var(--line); border-radius:8px; padding:.5rem .6rem; }
.summary b { display:block; font-size:1.2rem; }
.summary small { color:#888; }
.tabs { display:flex; flex-wrap:wrap; gap:.3rem; margin:.8rem 0; }
.tabs button { width:auto; padding:.3rem .6rem; font-size:.85rem; }
.tabs button.active { background: var(--accent); color:#fff; border-color:var(--accent); }
.actions { display:flex; gap:.5rem; margin:.6rem 0; flex-wrap:wrap; }
.actions a, .actions button { width:auto; text-decoration:none; display:inline-block;
        border:1px solid var(--line); border-radius:6px; padding:.4rem .7rem; color:CanvasText; }
#content { border-top:1px solid var(--line); margin-top:.8rem; padding-top:.8rem; }
#content table { border-collapse:collapse; }
#content th, #content td { border:1px solid var(--line); padding:.3rem .6rem; }
#content code { background:#8882; padding:.05rem .3rem; border-radius:3px; }
#content pre.mermaid { background:#8881; padding:1rem; border-radius:6px; }
.muted { color:#888; }
.err { color:#dc2626; }
</style>
</head>
<body>
<header><h1>Codebase Architect</h1><span>scan &amp; document any codebase</span></header>
<main>
  <aside>
    <form id="scanForm">
      <label>Source (Git URL, folder, .zip, .tar.gz)</label>
      <input id="location" placeholder="https://github.com/user/repo.git" required>
      <label>Title (optional)</label>
      <input id="title" placeholder="My Project">
      <div class="row" style="margin-top:.6rem">
        <input type="checkbox" id="staticOnly" checked>
        <label for="staticOnly" style="margin:0">Static only (no AI)</label>
      </div>
      <h2 style="margin-top:1rem">AI agent (when not static-only)</h2>
      <label>Provider</label>
      <select id="provider">
        <option value="">(config default)</option>
        <option>claude</option><option>openai</option><option>openrouter</option>
        <option>gemini</option><option>local</option>
      </select>
      <label>API key</label>
      <input id="apiKey" type="password" placeholder="sk-… (leave empty for a local runner)">
      <label>Endpoint / base URL (optional)</label>
      <input id="baseUrl" placeholder="http://100.x.y.z:11434/v1">
      <label>Model (optional)</label>
      <input id="model" placeholder="claude-opus-4-8 / gpt-4o-mini / llama3">
      <small class="muted">Local runner (Mac mini, no tokens): pick <b>local</b> (OpenAI-compatible,
        e.g. Ollama/Codex) or <b>claude</b> (Anthropic-compatible) and set the base URL to its
        tailnet address. Settings are remembered in this browser.</small>
      <button class="primary" type="submit">Scan</button>
      <div id="formErr" class="err"></div>
    </form>
    <h2>Scans</h2>
    <ul class="scans" id="scanList"></ul>
  </aside>
  <section class="detail">
    <div id="detail"><p class="muted">Submit a scan or pick one from the list.</p></div>
  </section>
</main>
<script>
mermaid.initialize({ startOnLoad: false });
let current = null, currentSlug = null, timer = null;

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.status);
  return r.headers.get("content-type")?.includes("json") ? r.json() : r.text();
}

async function refreshScans() {
  const scans = await api("/scans");
  const ul = document.getElementById("scanList");
  ul.innerHTML = "";
  scans.reverse().forEach(s => {
    const li = document.createElement("li");
    if (s.id === current) li.className = "active";
    li.innerHTML = `<span>${s.id.slice(0, 14)}…</span><span class="badge ${s.status}">${s.status}</span>`;
    li.onclick = () => selectScan(s.id);
    ul.appendChild(li);
  });
}

const v = id => document.getElementById(id).value.trim();
const CFG = ["provider", "apiKey", "baseUrl", "model"];

function loadCfg() {
  CFG.forEach(id => { const s = localStorage.getItem("ca." + id); if (s !== null) document.getElementById(id).value = s; });
  const so = localStorage.getItem("ca.staticOnly");
  if (so !== null) document.getElementById("staticOnly").checked = so === "1";
}
function saveCfg() {
  CFG.forEach(id => localStorage.setItem("ca." + id, document.getElementById(id).value));
  localStorage.setItem("ca.staticOnly", document.getElementById("staticOnly").checked ? "1" : "0");
}

document.getElementById("scanForm").onsubmit = async e => {
  e.preventDefault();
  document.getElementById("formErr").textContent = "";
  saveCfg();
  const body = {
    location: v("location"),
    title: v("title") || null,
    static_only: document.getElementById("staticOnly").checked,
    ai_provider: v("provider") || null,
    ai_api_key: v("apiKey") || null,
    ai_base_url: v("baseUrl") || null,
    ai_model: v("model") || null,
  };
  try {
    const { id } = await api("/scans", {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
    });
    await refreshScans();
    selectScan(id);
  } catch (err) { document.getElementById("formErr").textContent = err.message; }
};

async function selectScan(id) {
  current = id; currentSlug = null;
  if (timer) clearInterval(timer);
  await renderDetail();
  await refreshScans();
  const job = await api(`/scans/${id}`);
  if (job.status === "queued" || job.status === "running") {
    timer = setInterval(async () => {
      const j = await api(`/scans/${id}`);
      if (j.status !== "queued" && j.status !== "running") {
        clearInterval(timer); await renderDetail(); await refreshScans();
      }
    }, 1200);
  }
}

async function renderDetail() {
  const job = await api(`/scans/${current}`);
  const d = document.getElementById("detail");
  if (job.status === "failed") {
    d.innerHTML = `<h2>Scan failed</h2><p class="err">${job.error || ""}</p>`; return;
  }
  if (job.status !== "done") {
    d.innerHTML = `<p class="muted">Status: <b>${job.status}</b> — working…</p>`; return;
  }
  const s = job.summary;
  const cell = (b, l) => `<div><b>${b}</b><small>${l}</small></div>`;
  let html = `<h2>${job.title || job.location}</h2>
    <div class="summary">
      ${cell(s.modules, "modules")}${cell(s.symbols, "symbols")}
      ${cell(s.internal_dependencies, "internal deps")}${cell(s.external_dependencies, "external deps")}
      ${cell(s.entrypoints, "entrypoints")}${cell(s.secrets, "secrets")}
      ${cell(s.features ?? "—", "features")}${cell((job.duration_seconds ?? 0) + "s", "elapsed")}
    </div>
    <div class="actions">
      <a href="/scans/${current}/download">⬇ Download .zip</a>
    </div>`;
  const docs = await api(`/scans/${current}/documentation`);
  html += `<div class="tabs">` +
    docs.pages.map(p => `<button data-slug="${p.slug}">${p.title}</button>`).join("") +
    `</div><div id="content" class="muted">Select a page to view it.</div>`;
  d.innerHTML = html;
  d.querySelectorAll(".tabs button").forEach(b => b.onclick = () => loadPage(b.dataset.slug));
  loadPage(currentSlug || docs.pages[0].slug);
}

async function loadPage(slug) {
  currentSlug = slug;
  document.querySelectorAll(".tabs button").forEach(b =>
    b.classList.toggle("active", b.dataset.slug === slug));
  const page = await api(`/scans/${current}/pages/${slug}`);
  const el = document.getElementById("content");
  el.classList.remove("muted");
  el.innerHTML = marked.parse(page.markdown);
  const blocks = el.querySelectorAll("code.language-mermaid");
  blocks.forEach((c, i) => {
    const div = document.createElement("div");
    div.className = "mermaid"; div.textContent = c.textContent;
    c.closest("pre").replaceWith(div);
  });
  if (blocks.length) mermaid.run({ nodes: el.querySelectorAll(".mermaid") });
}

loadCfg();
refreshScans();
</script>
</body>
</html>
"""
