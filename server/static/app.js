const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const combosText = $("#combosText");
const proxiesText = $("#proxiesText");
const comboFile = $("#comboFile");
const proxyFile = $("#proxyFile");
const comboFileName = $("#comboFileName");
const libraryUpload = $("#libraryUpload");
const libraryList = $("#libraryList");
const refreshLibraryBtn = $("#refreshLibraryBtn");
const importUrl = $("#importUrl");
const importFilename = $("#importFilename");
const importUrlBtn = $("#importUrlBtn");
const quickImports = $("#quickImports");
const startLineInput = $("#startLine");
const threadsInput = $("#threads");
const proxyPreset = $("#proxyPreset");
const rotateProxy = $("#rotateProxy");
const startBtn = $("#startBtn");
const stopBtn = $("#stopBtn");
const resetProgressBtn = $("#resetProgressBtn");
const smokeTestBtn = $("#smokeTestBtn");
const smokeCombo = $("#smokeCombo");
const smokeResult = $("#smokeResult");
const statusPill = $("#statusPill");
const progressFill = $("#progressFill");
const progressStats = $("#progressStats");
const resumeHint = $("#resumeHint");
const resultsList = $("#resultsList");
const logBox = $("#logBox");
const selectAllBtn = $("#selectAllBtn");
const copySelectedBtn = $("#copySelectedBtn");
const deleteSelectedBtn = $("#deleteSelectedBtn");
const copyAllBtn = $("#copyAllBtn");
const exportBtn = $("#exportBtn");
const clearBtn = $("#clearBtn");
const clearLogBtn = $("#clearLogBtn");
const statProgress = $("#statProgress");
const statHits = $("#statHits");
const statCpm = $("#statCpm");
const statBads = $("#statBads");
const statFails = $("#statFails");
const statErrors = $("#statErrors");
const statCurrent = $("#statCurrent");
const toast = $("#toast");

const LARGE_COMBO_THRESHOLD = 2000;
const PROXY_PRESETS = {
  none: "",
  resi: "core-residential.evomi.com:1000:gulley886:tStXC3zZrqpDmVdVQdzF_country-US",
  dc: "169.197.82.58:16963:user86020ad8:60ccd5898179",
};

let hits = [];
let validLogins = [];
let selectedIds = new Set();
let pollTimer = null;
let lastLogSeq = 0;
let lastSessionHits = 0;
let lastSessionFails = 0;
let saveTimer = null;
let sessionCheckedCount = 0;
let storedComboCount = 0;
let combosOnServer = false;
let logLines = [];
let comboSource = "paste";
let selectedLibrary = "";
let resultTab = "hits";
let appConfig = { vs_quick_imports: [] };
let libraryFiles = [];

function showToast(msg) {
  toast.textContent = msg;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 3200);
}

function formatError(detail) {
  if (!detail) return "Request failed";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  }
  return String(detail);
}

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(formatError(err.detail) || res.statusText || "Request failed");
  }
  if (res.headers.get("content-type")?.includes("application/json")) {
    return res.json();
  }
  return res.text();
}

function comboLineCount() {
  const text = combosText.value.trim();
  if (!text) return 0;
  return text.split(/\r?\n/).filter((line) => line.trim()).length;
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function escapeHtml(str) {
  return str
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function fallbackCopy(text) {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.top = "-1000px";
  document.body.appendChild(ta);
  ta.select();
  const ok = document.execCommand("copy");
  document.body.removeChild(ta);
  if (!ok) throw new Error("Copy failed");
}

async function copyText(text) {
  if (!text) {
    showToast("Nothing to copy");
    return;
  }
  try {
    if (navigator.clipboard?.writeText && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
    } else {
      fallbackCopy(text);
    }
    showToast("Copied to clipboard");
  } catch {
    try {
      fallbackCopy(text);
      showToast("Copied to clipboard");
    } catch {
      showToast("Copy failed");
    }
  }
}

function applyProxyPreset(preset, force = false) {
  const value = PROXY_PRESETS[preset];
  if (preset === "custom") {
    proxiesText.disabled = false;
    return;
  }
  if (value !== undefined) {
    proxiesText.value = value;
    proxiesText.disabled = preset !== "none" && !force;
    rotateProxy.checked = preset === "resi";
  }
}

function scheduleSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveSession, 600);
}

async function saveSession() {
  const comboCount = comboLineCount();
  const preset = proxyPreset.value;
  const payload = {
    proxies: preset === "custom" ? proxiesText.value : PROXY_PRESETS[preset] || proxiesText.value,
    threads: Number(threadsInput.value || 5),
    start_line: Number(startLineInput.value || 1),
    rotate_proxy: rotateProxy.checked,
    proxy_preset: preset,
    combo_library: selectedLibrary,
    combos: "",
  };

  if (comboCount > 0 && comboCount <= LARGE_COMBO_THRESHOLD && comboSource === "paste") {
    payload.combos = combosText.value;
  }

  try {
    const result = await api("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (result.combo_count) storedComboCount = result.combo_count;
    if (result.combos_stored) combosOnServer = true;
    updateResumeHint();
  } catch (_) {}
}

function loadSmokeCombo() {
  try {
    const saved = localStorage.getItem("zeus_smoke_combo");
    if (saved) smokeCombo.value = saved;
  } catch (_) {}
}

function saveSmokeCombo() {
  try {
    localStorage.setItem("zeus_smoke_combo", smokeCombo.value);
  } catch (_) {}
}

function updateResumeHint() {
  let comboInfo = "add combos or select from library";

  if (comboSource === "library" && selectedLibrary) {
    const file = libraryFiles.find((f) => f.name === selectedLibrary);
    comboInfo = file
      ? `${file.name} (${file.lines.toLocaleString()} lines)`
      : selectedLibrary;
  } else if (combosOnServer && storedComboCount > 0) {
    comboInfo = `${storedComboCount.toLocaleString()} combos on server`;
  } else if (comboLineCount() > 0) {
    comboInfo = `${comboLineCount().toLocaleString()} in box`;
  }

  const startLine = Number(startLineInput.value || 1);
  const startInfo = startLine > 1 ? ` · from line ${startLine.toLocaleString()}` : "";
  const checked = sessionCheckedCount > 0
    ? ` · ${sessionCheckedCount.toLocaleString()} already checked`
    : "";

  resumeHint.textContent = `${comboInfo}${startInfo}${checked}`;
}

function setComboSource(source) {
  comboSource = source;
  $$(".source-tabs .tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.source === source);
  });
  $$(".source-pane").forEach((pane) => {
    pane.classList.toggle("active", pane.id === `pane-${source}`);
  });
  updateResumeHint();
}

function setResultTab(tab) {
  resultTab = tab;
  selectedIds.clear();
  $$(".result-tab").forEach((el) => {
    el.classList.toggle("active", el.dataset.result === tab);
  });
  renderResults();
}

function currentResults() {
  return resultTab === "hits" ? hits : validLogins;
}

function resultApiBase() {
  return resultTab === "hits" ? "/api/hits" : "/api/valid";
}

function getResultLine(id) {
  return currentResults().find((h) => h.id === id)?.line || "";
}

function updateSelectionButtons() {
  const count = selectedIds.size;
  copySelectedBtn.disabled = count === 0;
  deleteSelectedBtn.disabled = count === 0;
}

function renderResults() {
  const rows = currentResults();
  copyAllBtn.disabled = rows.length === 0;
  exportBtn.disabled = rows.length === 0;

  if (!rows.length) {
    resultsList.innerHTML = `<div class="empty-hits">No ${resultTab === "hits" ? "active hits" : "valid logins"} yet</div>`;
    updateSelectionButtons();
    return;
  }

  resultsList.innerHTML = rows
    .map((row) => `
      <div class="hit-row ${selectedIds.has(row.id) ? "selected" : ""}" data-id="${row.id}">
        <input type="checkbox" class="hit-check" data-id="${row.id}" ${selectedIds.has(row.id) ? "checked" : ""} />
        <span class="hit-line">${escapeHtml(row.line)}</span>
        <div class="hit-actions">
          <button class="btn small ghost copy-one" data-id="${row.id}" type="button">Copy</button>
          <button class="btn small ghost danger delete-one" data-id="${row.id}" type="button">Del</button>
        </div>
      </div>`)
    .join("");

  resultsList.querySelectorAll(".hit-check").forEach((el) => {
    el.addEventListener("change", (e) => {
      const id = Number(e.target.dataset.id);
      if (e.target.checked) selectedIds.add(id);
      else selectedIds.delete(id);
      e.target.closest(".hit-row")?.classList.toggle("selected", e.target.checked);
      updateSelectionButtons();
    });
  });

  resultsList.querySelectorAll(".copy-one").forEach((el) => {
    el.addEventListener("click", () => copyText(getResultLine(Number(el.dataset.id))));
  });

  resultsList.querySelectorAll(".delete-one").forEach((el) => {
    el.addEventListener("click", () => deleteResults([Number(el.dataset.id)]));
  });

  resultsList.querySelectorAll(".hit-line").forEach((el) => {
    el.addEventListener("dblclick", () => {
      const row = el.closest(".hit-row");
      const id = Number(row?.dataset.id);
      if (id) copyText(getResultLine(id));
    });
  });

  updateSelectionButtons();
}

async function loadHits() {
  hits = await api("/api/hits");
  statHits.textContent = String(hits.length);
  if (resultTab === "hits") renderResults();
}

async function loadValid() {
  validLogins = await api("/api/valid");
  if (resultTab === "valid") renderResults();
}

async function loadResults() {
  await Promise.all([loadHits(), loadValid()]);
}

async function deleteResults(ids) {
  if (!ids.length) return;
  await api(`${resultApiBase()}/delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  });
  ids.forEach((id) => selectedIds.delete(id));
  await loadResults();
  showToast(`Deleted ${ids.length} row(s)`);
}

function renderLibrary() {
  if (!libraryFiles.length) {
    libraryList.innerHTML = '<div class="empty-hits">No saved combo files</div>';
    return;
  }

  libraryList.innerHTML = libraryFiles
    .map((file) => `
      <div class="library-item ${selectedLibrary === file.name ? "selected" : ""}" data-name="${escapeHtml(file.name)}">
        <div class="library-meta">
          <div class="library-name">${escapeHtml(file.name)}</div>
          <div class="library-detail">${file.lines.toLocaleString()} lines · ${formatBytes(file.size)}</div>
        </div>
        <button class="btn small ghost danger lib-delete" data-name="${escapeHtml(file.name)}" type="button">Del</button>
      </div>`)
    .join("");

  libraryList.querySelectorAll(".library-item").forEach((el) => {
    el.addEventListener("click", (e) => {
      if (e.target.closest(".lib-delete")) return;
      selectedLibrary = el.dataset.name;
      combosOnServer = false;
      renderLibrary();
      updateResumeHint();
      scheduleSave();
    });
  });

  libraryList.querySelectorAll(".lib-delete").forEach((el) => {
    el.addEventListener("click", async (e) => {
      e.stopPropagation();
      const name = el.dataset.name;
      if (!confirm(`Delete ${name}?`)) return;
      try {
        await api(`/api/combos/${encodeURIComponent(name)}`, { method: "DELETE" });
        if (selectedLibrary === name) selectedLibrary = "";
        await refreshLibrary();
        showToast(`Deleted ${name}`);
      } catch (err) {
        showToast(err.message);
      }
    });
  });
}

async function refreshLibrary() {
  try {
    libraryFiles = await api("/api/combos");
    renderLibrary();
    updateResumeHint();
  } catch (err) {
    showToast(err.message);
  }
}

function renderQuickImports() {
  const items = appConfig.vs_quick_imports || [];
  quickImports.innerHTML = items
    .map((item) => `<button class="btn ghost small quick-import" data-name="${escapeHtml(item.name)}" type="button">${escapeHtml(item.label)}</button>`)
    .join("");

  quickImports.querySelectorAll(".quick-import").forEach((btn) => {
    btn.addEventListener("click", () => importVsCombo(btn.dataset.name));
  });
}

async function importVsCombo(name) {
  const btn = quickImports.querySelector(`[data-name="${name}"]`);
  const prev = btn?.textContent;
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Importing...";
  }
  try {
    const result = await api("/api/combos/import-vs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    showToast(`Imported ${result.name} (${result.lines.toLocaleString()} lines)`);
    selectedLibrary = result.name;
    setComboSource("library");
    await refreshLibrary();
  } catch (err) {
    showToast(err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = prev;
    }
  }
}

function appendLogs(lines, reset = false) {
  if (reset) {
    logLines = [...lines];
    lastLogSeq = 0;
  } else if (lines.length) {
    logLines.push(...lines);
    if (logLines.length > 3000) logLines = logLines.slice(-3000);
  }

  const text = logLines.join("\n");
  if (text !== logBox.textContent) {
    const atBottom = logBox.scrollHeight - logBox.scrollTop - logBox.clientHeight < 40;
    logBox.textContent = text;
    if (atBottom) logBox.scrollTop = logBox.scrollHeight;
  }
}

function updateStatus(data) {
  const total = data.total || data.combo_count || 0;
  const checked = data.checked || 0;
  const skipped = data.skipped || 0;
  const pct = total ? Math.round(((checked + skipped) / total) * 100) : 0;
  progressFill.style.width = `${pct}%`;

  statProgress.textContent = total ? `${checked + skipped} / ${total}` : "—";
  statHits.textContent = String(data.hits ?? hits.length ?? 0);
  statCpm.textContent = data.cpm != null ? String(data.cpm) : "0";
  statBads.textContent = String(data.bads || 0);
  statFails.textContent = String(data.fails || 0);
  statErrors.textContent = String(data.errors || 0);
  statCurrent.textContent = data.current || "—";

  const parts = [];
  if (data.preparing) parts.push("Preparing list...");
  else if (total) parts.push(`${checked + skipped} / ${total} checked`);
  else if (data.combo_count) parts.push(`${data.combo_count.toLocaleString()} loaded`);
  if (skipped) parts.push(`${skipped.toLocaleString()} skipped`);
  if (data.cpm) parts.push(`${data.cpm} CPM`);
  if (data.hits) parts.push(`${data.hits} hits`);
  if (data.fails) parts.push(`${data.fails} valid/inactive`);
  if (data.bads) parts.push(`${data.bads} invalid`);
  if (data.errors) parts.push(`${data.errors} errors`);
  progressStats.textContent = parts.join(" · ") || "Ready";

  let statusLabel = "Idle";
  if (data.preparing) statusLabel = "Preparing";
  else if (data.running) statusLabel = "Running";
  statusPill.textContent = statusLabel;
  statusPill.className = `status-pill ${data.running || data.preparing ? "running" : "idle"}`;

  const busy = Boolean(data.running || data.preparing);
  startBtn.disabled = busy;
  stopBtn.disabled = !busy;
  resetProgressBtn.disabled = busy;
  smokeTestBtn.disabled = busy;

  if (data.combo_count !== undefined) storedComboCount = data.combo_count;
  if (data.combos_stored !== undefined) combosOnServer = Boolean(data.combos_stored);
  if (data.checked_count !== undefined) sessionCheckedCount = data.checked_count;
  if (data.combo_library) selectedLibrary = data.combo_library;
  updateResumeHint();

  if (data.log_seq !== undefined) {
    if (data.log_seq < lastLogSeq) {
      appendLogs(data.logs || [], true);
    } else if ((data.logs || []).length) {
      appendLogs(data.logs, false);
    }
    lastLogSeq = data.log_seq;
  }
}

async function loadSession() {
  loadSmokeCombo();
  try {
    appConfig = await api("/api/config");
    renderQuickImports();

    const data = await api("/api/session");
    storedComboCount = data.combo_count || 0;
    combosOnServer = Boolean(data.combos_stored);
    selectedLibrary = data.combo_library || "";

    if (data.combos) {
      combosText.value = data.combos;
    } else if (combosOnServer && storedComboCount > 0) {
      combosText.value = "";
      combosText.placeholder = `${storedComboCount.toLocaleString()} combos on server`;
    }

    if (data.proxies) proxiesText.value = data.proxies;
    if (data.threads) threadsInput.value = data.threads;
    if (data.start_line) startLineInput.value = data.start_line;
    if (data.rotate_proxy !== undefined) rotateProxy.checked = data.rotate_proxy;
    if (data.proxy_preset) {
      proxyPreset.value = data.proxy_preset;
      applyProxyPreset(data.proxy_preset);
    }

    if (selectedLibrary) setComboSource("library");

    sessionCheckedCount = data.checked_count || 0;
    lastSessionHits = data.hits || 0;
    lastSessionFails = data.fails || 0;
    updateResumeHint();
    appendLogs(data.logs || [], true);
    updateStatus(data);
    await refreshLibrary();
  } catch (_) {}
}

$$(".source-tabs .tab").forEach((tab) => {
  tab.addEventListener("click", () => setComboSource(tab.dataset.source));
});

$$(".result-tab").forEach((tab) => {
  tab.addEventListener("click", () => setResultTab(tab.dataset.result));
});

combosText.addEventListener("input", () => {
  if (comboLineCount() <= LARGE_COMBO_THRESHOLD) combosOnServer = false;
  updateResumeHint();
  scheduleSave();
});
proxiesText.addEventListener("input", () => {
  proxyPreset.value = "custom";
  proxiesText.disabled = false;
  scheduleSave();
});
threadsInput.addEventListener("change", scheduleSave);
startLineInput.addEventListener("change", () => {
  updateResumeHint();
  scheduleSave();
});
rotateProxy.addEventListener("change", scheduleSave);
smokeCombo.addEventListener("input", saveSmokeCombo);

proxyPreset.addEventListener("change", () => {
  applyProxyPreset(proxyPreset.value, true);
  scheduleSave();
});

comboFile.addEventListener("change", () => {
  const file = comboFile.files[0];
  comboFileName.textContent = file ? `${file.name} (${formatBytes(file.size)})` : "No file selected";
  if (file) {
    combosOnServer = true;
    storedComboCount = 0;
    combosText.value = "";
    combosText.placeholder = `${file.name} uploads on Start`;
    setComboSource("paste");
    updateResumeHint();
  }
});

libraryUpload.addEventListener("change", async () => {
  const file = libraryUpload.files[0];
  if (!file) return;
  const form = new FormData();
  form.append("combo_file", file);
  form.append("name", file.name);
  try {
    const result = await api("/api/combos/upload", { method: "POST", body: form });
    showToast(`Uploaded ${result.name} (${result.lines.toLocaleString()} lines)`);
    selectedLibrary = result.name;
    setComboSource("library");
    await refreshLibrary();
  } catch (err) {
    showToast(err.message);
  }
  libraryUpload.value = "";
});

importUrlBtn.addEventListener("click", async () => {
  const url = importUrl.value.trim();
  if (!url) {
    showToast("Enter a URL");
    return;
  }
  importUrlBtn.disabled = true;
  const prev = importUrlBtn.textContent;
  importUrlBtn.textContent = "Importing...";
  try {
    const result = await api("/api/combos/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url,
        filename: importFilename.value.trim(),
      }),
    });
    showToast(`Imported ${result.name} (${result.lines.toLocaleString()} lines)`);
    selectedLibrary = result.name;
    setComboSource("library");
    await refreshLibrary();
  } catch (err) {
    showToast(err.message);
  } finally {
    importUrlBtn.disabled = false;
    importUrlBtn.textContent = prev;
  }
});

refreshLibraryBtn.addEventListener("click", refreshLibrary);

proxyFile.addEventListener("change", async () => {
  const file = proxyFile.files[0];
  if (file && file.size < 512 * 1024) {
    const text = await file.text();
    proxiesText.value = proxiesText.value ? `${proxiesText.value}\n${text}` : text;
    proxyPreset.value = "custom";
    proxiesText.disabled = false;
    scheduleSave();
  }
});

selectAllBtn.addEventListener("click", () => {
  const rows = currentResults();
  if (!rows.length) return;
  const allSelected = selectedIds.size === rows.length;
  selectedIds = allSelected ? new Set() : new Set(rows.map((h) => h.id));
  renderResults();
});

copySelectedBtn.addEventListener("click", async () => {
  const lines = currentResults().filter((h) => selectedIds.has(h.id)).map((h) => h.line);
  if (!lines.length) return;
  await copyText(lines.join("\n"));
});

deleteSelectedBtn.addEventListener("click", async () => {
  await deleteResults([...selectedIds]);
});

copyAllBtn.addEventListener("click", async () => {
  const text = await api(`${resultApiBase()}/export`);
  if (!text.trim()) return;
  await copyText(text);
});

exportBtn.addEventListener("click", () => {
  window.open(`${resultApiBase()}/export`, "_blank");
});

clearBtn.addEventListener("click", async () => {
  const rows = currentResults();
  if (!rows.length) return;
  const label = resultTab === "hits" ? "hits" : "valid logins";
  if (!confirm(`Delete all ${label}?`)) return;
  await api(`${resultApiBase()}/clear`, { method: "POST" });
  selectedIds.clear();
  await loadResults();
  showToast(`${label} cleared`);
});

clearLogBtn.addEventListener("click", () => {
  logLines = [];
  logBox.textContent = "";
});

smokeTestBtn.addEventListener("click", async () => {
  const comboLine = smokeCombo.value.trim()
    || combosText.value.split(/\r?\n/).find((l) => l.trim())
    || "";
  if (!comboLine.trim()) {
    showToast("Add a smoke test combo");
    return;
  }
  saveSmokeCombo();

  smokeTestBtn.disabled = true;
  const prev = smokeTestBtn.textContent;
  smokeTestBtn.textContent = "Testing...";

  const preset = proxyPreset.value;
  const proxyLine = preset === "custom"
    ? proxiesText.value.split(/\r?\n/).find((l) => l.trim()) || ""
    : PROXY_PRESETS[preset] || "";

  try {
    const result = await api("/api/smoke-test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        combo: comboLine,
        proxy: proxyLine,
        rotate_proxy: rotateProxy.checked,
      }),
    });
    smokeResult.hidden = false;
    const ok = result.status === "HIT" || result.status === "FAIL";
    smokeResult.className = `smoke-result ${ok ? "ok" : "fail"}`;
    smokeResult.textContent = `${result.line} (${result.elapsed_ms}ms)`;
    showToast(ok ? `Valid: ${result.status}` : `Smoke test: ${result.status}`);
  } catch (err) {
    smokeResult.hidden = false;
    smokeResult.className = "smoke-result fail";
    smokeResult.textContent = err.message || "Smoke test failed";
    showToast(err.message || "Smoke test failed");
  } finally {
    smokeTestBtn.textContent = prev;
    smokeTestBtn.disabled = false;
  }
});

resetProgressBtn.addEventListener("click", async () => {
  if (!confirm("Clear checked progress? Combos will be re-checked on next start.")) return;
  try {
    const result = await api("/api/progress/reset", { method: "POST" });
    sessionCheckedCount = 0;
    updateResumeHint();
    showToast(`Reset ${result.cleared} checked combo(s)`);
  } catch (err) {
    showToast(err.message);
  }
});

startBtn.addEventListener("click", async () => {
  const hasFile = Boolean(comboFile.files[0]);
  const textCount = comboLineCount();
  const hasStored = combosOnServer && storedComboCount > 0;
  const hasLibrary = comboSource === "library" && selectedLibrary;

  if (!hasFile && textCount === 0 && !hasStored && !hasLibrary) {
    showToast("Add combos or select from library");
    return;
  }

  const form = new FormData();
  form.append("threads", String(threadsInput.value || "5"));
  form.append("start_line", String(startLineInput.value || "1"));
  form.append("rotate_proxy", rotateProxy.checked ? "true" : "false");
  form.append("proxy_preset", proxyPreset.value);

  const preset = proxyPreset.value;
  form.append("proxies", preset === "custom" ? proxiesText.value : PROXY_PRESETS[preset] || proxiesText.value);

  if (hasLibrary) {
    form.append("combo_library", selectedLibrary);
  } else if (hasFile) {
    form.append("combo_file", comboFile.files[0]);
  } else if (textCount > 0) {
    if (textCount > LARGE_COMBO_THRESHOLD) {
      const blob = new Blob([combosText.value], { type: "text/plain" });
      form.append("combo_file", blob, "combos.txt");
    } else {
      form.append("combos", combosText.value);
    }
  } else {
    form.append("use_stored_combos", "true");
  }

  if (proxyFile.files[0]) form.append("proxy_file", proxyFile.files[0]);

  const prevLabel = startBtn.textContent;
  startBtn.disabled = true;
  startBtn.textContent = hasFile || hasLibrary ? "Preparing..." : "Starting...";

  try {
    if (textCount > 0 && textCount <= LARGE_COMBO_THRESHOLD && !hasFile && !hasLibrary) {
      await saveSession();
    }

    const result = await api("/api/jobs/start", { method: "POST", body: form });
    storedComboCount = result.combo_count || storedComboCount;
    combosOnServer = true;
    if (hasFile || textCount > LARGE_COMBO_THRESHOLD) {
      combosText.value = "";
      combosText.placeholder = `${storedComboCount.toLocaleString()} combos on server`;
    }
    updateResumeHint();
    showToast(`Preparing ${(result.combo_count || storedComboCount).toLocaleString()} combos...`);
    lastLogSeq = 0;
    logLines = [];
    logBox.textContent = "";
    lastSessionHits = 0;
    lastSessionFails = 0;
    await poll();
  } catch (err) {
    showToast(err.message || "Failed to start");
  } finally {
    startBtn.textContent = prevLabel;
    try {
      const data = await api("/api/status");
      updateStatus(data);
    } catch (_) {
      startBtn.disabled = false;
    }
  }
});

stopBtn.addEventListener("click", async () => {
  await api("/api/jobs/stop", { method: "POST" });
  showToast("Stopping...");
});

async function poll() {
  try {
    const data = await api(`/api/status?since_log_seq=${lastLogSeq}`);
    updateStatus(data);

    if ((data.hits || 0) > lastSessionHits || (data.fails || 0) > lastSessionFails) {
      lastSessionHits = data.hits || 0;
      lastSessionFails = data.fails || 0;
      await loadResults();
    }

    if (!data.running && !data.preparing) {
      if (lastSessionHits !== (data.hits || 0) || lastSessionFails !== (data.fails || 0)) {
        lastSessionHits = data.hits || 0;
        lastSessionFails = data.fails || 0;
        await loadResults();
      }
      const session = await api("/api/session");
      sessionCheckedCount = session.checked_count || 0;
      storedComboCount = session.combo_count || storedComboCount;
      combosOnServer = Boolean(session.combos_stored);
      updateResumeHint();
    }
  } catch (_) {}
}

function startPolling() {
  if (!pollTimer) pollTimer = setInterval(poll, 500);
  poll();
}

loadSession();
loadResults();
startPolling();
