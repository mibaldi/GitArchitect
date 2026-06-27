"""Single-file web dashboard served by the API at ``/``.

Kept as a Python string so it ships with the package (no static-file packaging
needed). It is a dependency-free SPA that talks to the same REST API: submit a
scan, watch its status, download the bundle and view the documentation
(Markdown + Mermaid) rendered live. AI configuration (provider, key, endpoint,
model) lives in a Settings panel and is stored in the browser.
"""

from __future__ import annotations

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Codebase Architect</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
/* "Blueprint": grounded in the subject — software architecture / technical
   drafting. Cool drafting-paper light + blueprint-navy dark, azure accent,
   a faint measured grid, and monospace for every code identifier. */
:root {
  --bg: #eaeef3; --surface: #ffffff; --surface-2: #f4f7fa; --line: #d3dce5;
  --text: #122031; --muted: #5f6e80; --accent: #0b62d6; --accent-soft: #e3edfb;
  --grid: rgba(18,42,72,.05);
  --ok: #0f7a4a; --info: #0b62d6; --warn: #a4660a; --err: #c0322b;
  --shadow: 0 1px 2px rgba(18,32,49,.06), 0 10px 30px rgba(18,32,49,.06);
  --radius: 12px; --mono: "IBM Plex Mono", ui-monospace, monospace;
}
html[data-theme="dark"] {
  --bg: #0a1019; --surface: #0f1a27; --surface-2: #0c1521; --line: #1d2c3d;
  --text: #d9e4f0; --muted: #7e8fa3; --accent: #4c9bff; --accent-soft: #112236;
  --grid: rgba(120,160,210,.06);
  --ok: #34d399; --info: #4c9bff; --warn: #f1b24a; --err: #f4736b;
  --shadow: 0 1px 2px rgba(0,0,0,.45), 0 14px 36px rgba(0,0,0,.4);
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font: 15px/1.6 "IBM Plex Sans", system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
}
h1, h2, h3, .brand { font-family: "Space Grotesk", system-ui, sans-serif; letter-spacing: -.01em; }
a { color: var(--accent); }
button { font: inherit; cursor: pointer; }
.mono { font-family: var(--mono); }

/* topbar */
.topbar {
  height: 60px; display: flex; align-items: center; justify-content: space-between;
  padding: 0 20px; border-bottom: 1px solid var(--line); background: var(--surface);
  position: sticky; top: 0; z-index: 20;
}
.brand { display: flex; align-items: center; gap: 12px; font-weight: 700; font-size: 1.05rem; }
.brand .logo {
  width: 30px; height: 30px; border-radius: 8px; display: grid; place-items: center;
  background: var(--accent); color: #fff; flex: none;
}
.brand small { color: var(--muted); font-weight: 500; font-family: "IBM Plex Sans"; font-size: .78rem; }
.topbar .tools { display: flex; gap: 8px; }
.icon-btn {
  width: 38px; height: 38px; border: 1px solid var(--line); border-radius: 10px;
  background: var(--surface-2); color: var(--text); display: grid; place-items: center;
}
.icon-btn:hover { border-color: var(--accent); color: var(--accent); }

/* layout */
.layout { display: grid; grid-template-columns: 380px 1fr; min-height: calc(100vh - 60px); }
.sidebar { border-right: 1px solid var(--line); padding: 18px; overflow: auto; background: var(--surface-2); }
.main {
  padding: 24px 28px; overflow: auto;
  background-image: linear-gradient(var(--grid) 1px, transparent 1px),
                    linear-gradient(90deg, var(--grid) 1px, transparent 1px);
  background-size: 30px 30px; background-position: -1px -1px;
}

/* card / form */
.card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); }
.scan-card { padding: 16px; }
.scan-card h2 { margin: 0 0 12px; font-size: .95rem; }
label { display: block; font-size: .76rem; color: var(--muted); margin: 12px 0 5px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
input, select {
  width: 100%; padding: 10px 12px; border: 1px solid var(--line); border-radius: 9px;
  background: var(--bg); color: var(--text); font: inherit;
}
input:focus, select:focus { outline: 2px solid var(--accent-soft); border-color: var(--accent); }
.toggle { display: flex; align-items: center; gap: 10px; margin: 14px 0 4px; }
.toggle input { width: auto; }
.toggle label { margin: 0; text-transform: none; letter-spacing: 0; font-size: .85rem; color: var(--text); font-weight: 500; }
.upload-row { margin: 6px 0 4px; }
.upload-label { display: block; margin: 0 0 4px; text-transform: none; letter-spacing: 0; font-size: .78rem; color: var(--muted); font-weight: 500; }
.upload-row input[type=file] { width: 100%; font-size: .8rem; color: var(--muted); }
.btn {
  width: 100%; margin-top: 14px; padding: 11px; border: none; border-radius: 10px;
  background: var(--accent); color: #fff; font-weight: 600; font-family: "Space Grotesk";
}
.btn:hover { filter: brightness(1.07); }
.btn:disabled { opacity: .6; cursor: default; }
.ai-chip {
  margin-top: 10px; font-size: .78rem; color: var(--muted); display: flex; align-items: center; gap: 7px;
}
.ai-chip .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--muted); flex: none; }
.ai-chip.on .dot { background: var(--ok); }
.err { color: var(--err); font-size: .82rem; margin-top: 8px; }

/* scans list */
.scans { margin-top: 22px; }
.scans h3 { font-size: .78rem; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; margin: 0 0 8px; }
.scan-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; }
.scan-list li {
  padding: 10px 12px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface);
  cursor: pointer; display: flex; align-items: center; justify-content: space-between; gap: 8px;
}
.scan-list li:hover { border-color: var(--accent); }
.scan-list li.active { border-color: var(--accent); background: var(--accent-soft); }
.scan-list .name { font-size: .85rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.scan-list .name span { color: var(--muted); font-family: var(--mono); font-size: .76rem; }

.badge { font-size: .68rem; padding: 2px 9px; border-radius: 999px; font-weight: 600; border: 1px solid currentColor; text-transform: capitalize; flex: none; }
.badge.done { color: var(--ok); } .badge.failed { color: var(--err); }
.badge.running, .badge.queued { color: var(--info); }

/* detail */
.empty { display: grid; place-items: center; height: 70vh; text-align: center; color: var(--muted); }
.empty svg { width: 56px; height: 56px; opacity: .5; margin-bottom: 14px; }
.detail-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 4px; }
.detail-head h2 { margin: 0; font-size: 1.25rem; }
.meta { color: var(--muted); font-size: .82rem; margin-bottom: 18px; }
.meta .mono { color: var(--text); }
.summary { display: grid; grid-template-columns: repeat(auto-fill, minmax(118px, 1fr)); gap: 10px; margin-bottom: 20px; }
.summary .stat { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; }
.summary .stat b { display: block; font-family: "Space Grotesk"; font-size: 1.5rem; line-height: 1.1; }
.summary .stat small { color: var(--muted); font-size: .74rem; text-transform: uppercase; letter-spacing: .04em; }
.summary .stat.warn b { color: var(--warn); }
.actions { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }
.actions a, .actions .ghost {
  text-decoration: none; border: 1px solid var(--line); border-radius: 9px; padding: 8px 14px;
  color: var(--text); background: var(--surface); font-weight: 500; font-size: .9rem;
}
.actions a:hover { border-color: var(--accent); color: var(--accent); }
.tabs { display: flex; flex-wrap: wrap; gap: 6px; border-bottom: 1px solid var(--line); padding-bottom: 12px; margin-bottom: 16px; }
.tabs button { border: 1px solid var(--line); background: var(--surface); color: var(--text); border-radius: 8px; padding: 6px 13px; font-size: .85rem; }
.tabs button:hover { border-color: var(--accent); }
.tabs button.active { background: var(--accent); color: #fff; border-color: var(--accent); }

/* rendered docs */
.doc { max-width: 860px; }
.doc h1 { font-size: 1.5rem; margin: 0 0 .4em; }
.doc h2 { font-size: 1.2rem; margin: 1.4em 0 .5em; padding-bottom: .25em; border-bottom: 1px solid var(--line); }
.doc h3, .doc h4 { font-size: 1.02rem; margin: 1.2em 0 .4em; }
.doc table { border-collapse: collapse; width: 100%; margin: .6em 0; font-size: .9rem; }
.doc th, .doc td { border: 1px solid var(--line); padding: 7px 11px; text-align: left; }
.doc th { background: var(--surface-2); }
.doc code { font-family: var(--mono); font-size: .85em; background: var(--accent-soft); color: var(--accent); padding: .08em .4em; border-radius: 5px; }
.doc ul { padding-left: 1.3em; }
.doc .mermaid { background: #ffffff; border: 1px solid var(--line); padding: 16px; border-radius: 10px; margin: .8em 0; text-align: center; }

/* settings slide-over */
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,.4); opacity: 0; pointer-events: none; transition: opacity .2s; z-index: 40; }
.overlay.show { opacity: 1; pointer-events: auto; }
.panel {
  position: fixed; top: 0; right: 0; height: 100%; width: 420px; max-width: 92vw; z-index: 50;
  background: var(--surface); border-left: 1px solid var(--line); box-shadow: var(--shadow);
  transform: translateX(100%); transition: transform .24s ease; display: flex; flex-direction: column;
}
.panel.show { transform: none; }
.panel header { display: flex; align-items: center; justify-content: space-between; padding: 18px 20px; border-bottom: 1px solid var(--line); }
.panel header h2 { margin: 0; font-size: 1.05rem; }
.panel .body { padding: 20px; overflow: auto; }
.panel .hint { margin-top: 16px; padding: 12px 14px; background: var(--surface-2); border: 1px solid var(--line); border-radius: 10px; font-size: .82rem; color: var(--muted); }
.saved { color: var(--ok); font-size: .82rem; margin-top: 8px; min-height: 1.1em; }

.spinner { width: 16px; height: 16px; border: 2px solid var(--line); border-top-color: var(--accent); border-radius: 50%; display: inline-block; animation: spin .7s linear infinite; vertical-align: -3px; }
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 820px) { .layout { grid-template-columns: 1fr; } .sidebar { border-right: none; border-bottom: 1px solid var(--line); } }
</style>
</head>
<body>
<div class="topbar">
  <div class="brand">
    <span class="logo">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M3 21h18M5 21V8l7-5 7 5v13M9 21v-6h6v6"/>
      </svg>
    </span>
    Codebase&nbsp;Architect <small>· architecture docs</small>
  </div>
  <div class="tools">
    <button class="icon-btn" id="themeBtn" title="Toggle theme">◐</button>
    <button class="icon-btn" id="settingsBtn" title="Settings">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg>
    </button>
  </div>
</div>

<div class="layout">
  <aside class="sidebar">
    <form class="card scan-card" id="scanForm">
      <h2>New scan</h2>
      <label>Source</label>
      <input id="location" placeholder="https://github.com/user/repo.git">
      <div class="upload-row">
        <label for="upload" class="upload-label">or upload a .zip / .tar.gz (temporary)</label>
        <input type="file" id="upload" accept=".zip,.tar.gz,.tgz,.tar">
      </div>
      <label>Title (optional)</label>
      <input id="title" placeholder="My Project">
      <div class="toggle">
        <input type="checkbox" id="staticOnly" checked>
        <label for="staticOnly">Static only (no AI narrative)</label>
      </div>
      <div class="ai-chip" id="aiChip"><span class="dot"></span><span id="aiChipText">AI off</span></div>
      <button class="btn" type="submit" id="runBtn">Run scan</button>
      <div class="err" id="formErr"></div>
    </form>
    <div class="scans">
      <h3>Recent scans</h3>
      <ul class="scan-list" id="scanList"></ul>
    </div>
  </aside>

  <main class="main" id="detail">
    <div class="empty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M3 21h18M5 21V8l7-5 7 5v13M9 21v-6h6v6"/>
      </svg>
      <div>Point it at a repo, folder or archive, then read its architecture.</div>
    </div>
  </main>
</div>

<div class="overlay" id="overlay"></div>
<aside class="panel" id="settings">
  <header>
    <h2>Settings</h2>
    <button class="icon-btn" id="closeSettings">✕</button>
  </header>
  <div class="body">
    <form id="settingsForm">
      <label>AI provider</label>
      <select id="provider">
        <option value="">(config default)</option>
        <option>claude</option><option>openai</option><option>openrouter</option>
        <option>gemini</option><option>local</option>
      </select>
      <label>API key</label>
      <input id="apiKey" type="password" placeholder="sk-… (empty for a local runner)">
      <label>Endpoint / base URL (optional)</label>
      <input id="baseUrl" placeholder="http://100.x.y.z:11434/v1">
      <label>Model (optional)</label>
      <input id="model" placeholder="claude-opus-4-8 / gpt-4o-mini / llama3">
      <button class="btn" type="submit">Save settings</button>
      <div class="saved" id="savedMsg"></div>
    </form>
    <div class="hint">
      <b>Local runner (no tokens).</b> Run an agent on your own machine (Mac mini,
      Ollama, LM Studio, Codex) reachable over your tailnet and point the base URL
      at it: provider <b>local</b>/<b>openai</b> for OpenAI-compatible servers, or
      <b>claude</b> for an Anthropic-compatible one. Settings are stored in this browser only.
    </div>
  </div>
</aside>

<script>
const $ = id => document.getElementById(id);
const LS = k => localStorage.getItem("ca." + k) || "";
const SET = (k, v) => localStorage.setItem("ca." + k, v);
let current = null, currentSlug = null, timer = null;

/* theme */
function applyTheme(t) {
  document.documentElement.setAttribute("data-theme", t);
  mermaid.initialize({ startOnLoad: false, theme: "neutral" });
}
applyTheme(LS("theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
$("themeBtn").onclick = () => {
  const t = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  SET("theme", t); applyTheme(t);
};

/* settings panel */
function openSettings(open) {
  $("settings").classList.toggle("show", open);
  $("overlay").classList.toggle("show", open);
  if (open) $("savedMsg").textContent = "";
}
$("settingsBtn").onclick = () => openSettings(true);
$("closeSettings").onclick = () => openSettings(false);
$("overlay").onclick = () => openSettings(false);
["provider", "apiKey", "baseUrl", "model"].forEach(id => { $(id).value = LS(id); });
$("settingsForm").onsubmit = e => {
  e.preventDefault();
  ["provider", "apiKey", "baseUrl", "model"].forEach(id => SET(id, $(id).value.trim()));
  $("savedMsg").textContent = "✓ Saved";
  updateAIChip();
};

/* AI status chip on the scan card */
function updateAIChip() {
  const provider = LS("provider"), base = LS("baseUrl");
  const staticOnly = $("staticOnly").checked;
  const chip = $("aiChip"), text = $("aiChipText");
  if (staticOnly) { chip.classList.remove("on"); text.textContent = "AI off (static only)"; return; }
  const label = provider || "default";
  let host = "";
  try { if (base) host = " @ " + new URL(base).host; } catch (_) { host = base ? " @ custom" : ""; }
  chip.classList.add("on"); text.textContent = "AI: " + label + host;
}
$("staticOnly").onchange = () => { SET("staticOnly", $("staticOnly").checked ? "1" : "0"); updateAIChip(); };
if (LS("staticOnly")) $("staticOnly").checked = LS("staticOnly") === "1";
updateAIChip();

/* api helper */
async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || ("HTTP " + r.status));
  return (r.headers.get("content-type") || "").includes("json") ? r.json() : r.text();
}

async function refreshScans() {
  const scans = await api("/scans");
  const ul = $("scanList");
  ul.innerHTML = scans.length ? "" : '<li style="cursor:default;color:var(--muted)">No scans yet</li>';
  scans.reverse().forEach(s => {
    const li = document.createElement("li");
    if (s.id === current) li.className = "active";
    li.innerHTML = `<span class="name">scan <span>${s.id.slice(5, 13)}</span></span><span class="badge ${s.status}">${s.status}</span>`;
    li.onclick = () => selectScan(s.id);
    ul.appendChild(li);
  });
}

$("scanForm").onsubmit = async e => {
  e.preventDefault();
  $("formErr").textContent = "";
  const staticOnly = $("staticOnly").checked;
  const title = $("title").value.trim();
  const location = $("location").value.trim();
  const file = $("upload").files[0];
  if (!location && !file) {
    $("formErr").textContent = "Enter a Git URL / path, or choose an archive to upload.";
    return;
  }
  const btn = $("runBtn"); btn.disabled = true; btn.textContent = "Starting…";
  try {
    let id;
    if (file) {
      const fd = new FormData();
      fd.append("file", file);
      if (title) fd.append("title", title);
      fd.append("static_only", staticOnly);
      if (!staticOnly) {
        if (LS("provider")) fd.append("ai_provider", LS("provider"));
        if (LS("apiKey")) fd.append("ai_api_key", LS("apiKey"));
        if (LS("baseUrl")) fd.append("ai_base_url", LS("baseUrl"));
        if (LS("model")) fd.append("ai_model", LS("model"));
      }
      ({ id } = await api("/scans/upload", { method: "POST", body: fd }));
    } else {
      const body = {
        location,
        title: title || null,
        static_only: staticOnly,
        ai_provider: staticOnly ? null : (LS("provider") || null),
        ai_api_key: staticOnly ? null : (LS("apiKey") || null),
        ai_base_url: staticOnly ? null : (LS("baseUrl") || null),
        ai_model: staticOnly ? null : (LS("model") || null),
      };
      ({ id } = await api("/scans", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }));
    }
    $("upload").value = "";
    await refreshScans(); selectScan(id);
  } catch (err) { $("formErr").textContent = err.message; }
  finally { btn.disabled = false; btn.textContent = "Run scan"; }
};

async function selectScan(id) {
  current = id; currentSlug = null;
  if (timer) clearInterval(timer);
  await renderDetail(); await refreshScans();
  const job = await api(`/scans/${id}`);
  if (job.status === "queued" || job.status === "running") {
    timer = setInterval(async () => {
      const j = await api(`/scans/${id}`);
      if (j.status !== "queued" && j.status !== "running") { clearInterval(timer); renderDetail(); refreshScans(); }
    }, 1200);
  }
}

async function renderDetail() {
  const job = await api(`/scans/${current}`);
  const d = $("detail");
  if (job.status === "failed") { d.innerHTML = `<div class="detail-head"><h2>Scan failed</h2></div><p class="err">${job.error || ""}</p>`; return; }
  if (job.status !== "done") { d.innerHTML = `<div class="empty"><div><span class="spinner"></span>&nbsp; ${job.status}…</div></div>`; return; }
  const s = job.summary;
  const stat = (b, l, cls = "") => `<div class="stat ${cls}"><b>${b}</b><small>${l}</small></div>`;
  d.innerHTML = `
    <div class="detail-head"><h2>${esc(job.title || job.location)}</h2></div>
    <div class="meta">type <span class="mono">${s.source_type}</span> · base ref <span class="mono">${(s.base_ref || "").slice(0,12)}</span> · ${job.duration_seconds ?? 0}s</div>
    <div class="summary">
      ${stat(s.modules, "modules")}${stat(s.symbols, "symbols")}
      ${stat(s.internal_dependencies, "internal deps")}${stat(s.external_dependencies, "external deps")}
      ${stat(s.entrypoints, "entrypoints")}${stat(s.secrets, "secrets", s.secrets ? "warn" : "")}
      ${stat(s.features ?? "—", "features")}${stat((s.ai_tokens ?? 0), "AI tokens")}
    </div>
    <div class="actions"><a href="/scans/${current}/download">⬇ Download .zip</a></div>
    <div class="tabs" id="tabs"></div>
    <div class="doc" id="content"></div>`;
  const docs = await api(`/scans/${current}/documentation`);
  $("tabs").innerHTML = docs.pages.map(p => `<button data-slug="${p.slug}">${esc(p.title)}</button>`).join("");
  $("tabs").querySelectorAll("button").forEach(b => b.onclick = () => loadPage(b.dataset.slug));
  loadPage(currentSlug || docs.pages[0].slug);
}

async function loadPage(slug) {
  currentSlug = slug;
  document.querySelectorAll("#tabs button").forEach(b => b.classList.toggle("active", b.dataset.slug === slug));
  const page = await api(`/scans/${current}/pages/${slug}`);
  const el = $("content");
  el.innerHTML = marked.parse(page.markdown);
  el.querySelectorAll("code.language-mermaid").forEach(c => {
    const div = document.createElement("div"); div.className = "mermaid"; div.textContent = c.textContent;
    c.closest("pre").replaceWith(div);
  });
  const nodes = el.querySelectorAll(".mermaid");
  if (nodes.length) mermaid.run({ nodes });
}

function esc(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

refreshScans();
</script>
</body>
</html>
"""
