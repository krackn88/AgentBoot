const $ = (sel) => document.querySelector(sel);

const combosText = $("#combosText");
const proxiesText = $("#proxiesText");
const comboFile = $("#comboFile");
const proxyFile = $("#proxyFile");
const comboFileName = $("#comboFileName");
const proxyFileName = $("#proxyFileName");
const threadsInput = $("#threads");
const startBtn = $("#startBtn");
const stopBtn = $("#stopBtn");
const resetProgressBtn = $("#resetProgressBtn");
const smokeTestBtn = $("#smokeTestBtn");
const smokeResult = $("#smokeResult");
const statusPill = $("#statusPill");
const progressFill = $("#progressFill");
const progressStats = $("#progressStats");
const resumeHint = $("#resumeHint");
const hitsList = $("#hitsList");
const logBox = $("#logBox");
const selectAllBtn = $("#selectAllBtn");
const copySelectedBtn = $("#copySelectedBtn");
const deleteSelectedBtn = $("#deleteSelectedBtn");
const copyAllBtn = $("#copyAllBtn");
const exportHitsBtn = $("#exportHitsBtn");
const clearHitsBtn = $("#clearHitsBtn");
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

let hits = [];
let selectedIds = new Set();
let pollTimer = null;
let lastLogSeq = 0;
let lastSessionHits = 0;
let saveTimer = null;
let sessionCheckedCount = 0;
let storedComboCount = 0;
let combosOnServer = false;
let logLines = [];

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

function scheduleSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveSession, 600);
}

async function saveSession() {
  const comboCount = comboLineCount();
  const payload = {
    proxies: proxiesText.value,
    threads: Number(threadsInput.value || 5),
    combos: "",
  };

  if (comboCount > 0 && comboCount <= LARGE_COMBO_THRESHOLD) {
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

async function loadSession() {
  try {
    const data = await api("/api/session");
    storedComboCount = data.combo_count || 0;
    combosOnServer = Boolean(data.combos_stored);

    if (data.combos) {
      combosText.value = data.combos;
    } else if (combosOnServer && storedComboCount > 0) {
      combosText.value = "";
      combosText.placeholder = `${storedComboCount.toLocaleString()} combos on server`;
    }

    if (data.proxies) proxiesText.value = data.proxies;
    if (data.threads) threadsInput.value = data.threads;
    sessionCheckedCount = data.checked_count || 0;
    lastSessionHits = data.hits || 0;
    updateResumeHint();
    appendLogs(data.logs || [], true);
    updateStatus(data);
  } catch (_) {}
}

function updateResumeHint() {
  const comboInfo = combosOnServer && storedComboCount > 0
    ? `${storedComboCount.toLocaleString()} combos on server`
    : comboLineCount() > 0
      ? `${comboLineCount().toLocaleString()} in box`
      : "add combos or upload a file";

  const checked = sessionCheckedCount > 0
    ? ` · ${sessionCheckedCount.toLocaleString()} already checked`
    : "";

  resumeHint.textContent = `${comboInfo}${checked}`;
}

combosText.addEventListener("input", () => {
  if (comboLineCount() <= LARGE_COMBO_THRESHOLD) combosOnServer = false;
  updateResumeHint();
  scheduleSave();
});
proxiesText.addEventListener("input", scheduleSave);
threadsInput.addEventListener("change", scheduleSave);

comboFile.addEventListener("change", () => {
  const file = comboFile.files[0];
  comboFileName.textContent = file ? `${file.name} (${formatBytes(file.size)})` : "No file selected";
  if (file) {
    combosOnServer = true;
    storedComboCount = 0;
    combosText.value = "";
    combosText.placeholder = `${file.name} uploads on Start`;
    updateResumeHint();
  }
});

proxyFile.addEventListener("change", async () => {
  const file = proxyFile.files[0];
  proxyFileName.textContent = file ? file.name : "No file selected";
  if (file && file.size < 512 * 1024) {
    const text = await file.text();
    proxiesText.value = proxiesText.value ? `${proxiesText.value}\n${text}` : text;
    scheduleSave();
  }
});

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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

function getHitLine(id) {
  return hits.find((h) => h.id === id)?.line || "";
}

function updateSelectionButtons() {
  const count = selectedIds.size;
  copySelectedBtn.disabled = count === 0;
  deleteSelectedBtn.disabled = count === 0;
}

function renderHits() {
  copyAllBtn.disabled = hits.length === 0;
  exportHitsBtn.disabled = hits.length === 0;

  if (!hits.length) {
    hitsList.innerHTML = '<div class="empty-hits">No hits yet</div>';
    updateSelectionButtons();
    return;
  }

  hitsList.innerHTML = hits
    .map((hit) => `
      <div class="hit-row ${selectedIds.has(hit.id) ? "selected" : ""}" data-id="${hit.id}">
        <input type="checkbox" class="hit-check" data-id="${hit.id}" ${selectedIds.has(hit.id) ? "checked" : ""} />
        <span class="hit-line">${escapeHtml(hit.line)}</span>
        <div class="hit-actions">
          <button class="btn small ghost copy-one" data-id="${hit.id}">Copy</button>
          <button class="btn small ghost danger delete-one" data-id="${hit.id}">Del</button>
        </div>
      </div>`)
    .join("");

  hitsList.querySelectorAll(".hit-check").forEach((el) => {
    el.addEventListener("change", (e) => {
      const id = Number(e.target.dataset.id);
      if (e.target.checked) selectedIds.add(id);
      else selectedIds.delete(id);
      e.target.closest(".hit-row")?.classList.toggle("selected", e.target.checked);
      updateSelectionButtons();
    });
  });

  hitsList.querySelectorAll(".copy-one").forEach((el) => {
    el.addEventListener("click", () => copyText(getHitLine(Number(el.dataset.id))));
  });

  hitsList.querySelectorAll(".delete-one").forEach((el) => {
    el.addEventListener("click", () => deleteHits([Number(el.dataset.id)]));
  });

  hitsList.querySelectorAll(".hit-line").forEach((el) => {
    el.addEventListener("dblclick", () => {
      const row = el.closest(".hit-row");
      const id = Number(row?.dataset.id);
      if (id) copyText(getHitLine(id));
    });
  });

  updateSelectionButtons();
}

async function loadHits() {
  hits = await api("/api/hits");
  renderHits();
  statHits.textContent = String(hits.length);
}

async function deleteHits(ids) {
  if (!ids.length) return;
  await api("/api/hits/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  });
  ids.forEach((id) => selectedIds.delete(id));
  await loadHits();
  showToast(`Deleted ${ids.length} hit(s)`);
}

function appendLogs(lines, reset = false) {
  if (reset) {
    logLines = [...lines];
    lastLogSeq = 0;
  } else if (lines.length) {
    logLines.push(...lines);
    if (logLines.length > 3000) {
      logLines = logLines.slice(-3000);
    }
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
  if (data.bads) parts.push(`${data.bads} invalid`);
  if (data.fails) parts.push(`${data.fails} inactive`);
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

selectAllBtn.addEventListener("click", () => {
  if (!hits.length) return;
  const allSelected = selectedIds.size === hits.length;
  selectedIds = allSelected ? new Set() : new Set(hits.map((h) => h.id));
  renderHits();
});

copySelectedBtn.addEventListener("click", async () => {
  const lines = hits.filter((h) => selectedIds.has(h.id)).map((h) => h.line);
  if (!lines.length) return;
  await copyText(lines.join("\n"));
});

deleteSelectedBtn.addEventListener("click", async () => {
  await deleteHits([...selectedIds]);
});

copyAllBtn.addEventListener("click", async () => {
  const text = await api("/api/hits/export");
  if (!text.trim()) return;
  await copyText(text);
});

exportHitsBtn.addEventListener("click", () => {
  window.open("/api/hits/export", "_blank");
});

clearHitsBtn.addEventListener("click", async () => {
  if (!hits.length) return;
  if (!confirm("Delete all hits?")) return;
  await api("/api/hits/clear", { method: "POST" });
  selectedIds.clear();
  await loadHits();
  showToast("Hits cleared");
});

clearLogBtn.addEventListener("click", () => {
  logLines = [];
  logBox.textContent = "";
});

smokeTestBtn.addEventListener("click", async () => {
  const comboLine = combosText.value.split(/\r?\n/).find((l) => l.trim()) || "";
  if (!comboLine.trim()) {
    showToast("Add a combo to test");
    return;
  }

  smokeTestBtn.disabled = true;
  const prev = smokeTestBtn.textContent;
  smokeTestBtn.textContent = "Testing...";

  try {
    const result = await api("/api/smoke-test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        combo: comboLine,
        proxy: proxiesText.value.split(/\r?\n/).find((l) => l.trim()) || "",
      }),
    });
    smokeResult.hidden = false;
    smokeResult.className = `smoke-result ${result.ok ? "ok" : "fail"}`;
    smokeResult.textContent = `${result.line} (${result.elapsed_ms}ms)`;
    showToast(result.ok ? "Smoke test passed" : `Smoke test: ${result.status}`);
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

  if (!hasFile && textCount === 0 && !hasStored) {
    showToast("Add combos first");
    return;
  }

  const form = new FormData();
  form.append("threads", String(threadsInput.value || "5"));
  form.append("proxies", proxiesText.value);

  if (hasFile) {
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
  startBtn.textContent = hasFile ? "Uploading..." : "Starting...";

  try {
    if (textCount > 0 && textCount <= LARGE_COMBO_THRESHOLD && !hasFile) {
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

    if ((data.hits || 0) > lastSessionHits) {
      lastSessionHits = data.hits || 0;
      await loadHits();
    }

    if (!data.running && !data.preparing) {
      if (lastSessionHits !== (data.hits || 0)) {
        lastSessionHits = data.hits || 0;
        await loadHits();
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
loadHits();
startPolling();
