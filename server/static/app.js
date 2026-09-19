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
const statusPill = $("#statusPill");
const progressFill = $("#progressFill");
const progressStats = $("#progressStats");
const resumeHint = $("#resumeHint");
const hitsBody = $("#hitsBody");
const logBox = $("#logBox");
const selectAllBtn = $("#selectAllBtn");
const copySelectedBtn = $("#copySelectedBtn");
const deleteSelectedBtn = $("#deleteSelectedBtn");
const clearHitsBtn = $("#clearHitsBtn");
const toast = $("#toast");

const LARGE_COMBO_THRESHOLD = 2000;

let hits = [];
let selectedIds = new Set();
let pollTimer = null;
let lastLogCount = 0;
let saveTimer = null;
let sessionCheckedCount = 0;
let storedComboCount = 0;
let combosOnServer = false;

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
  return res.json();
}

function comboLineCount() {
  const text = combosText.value.trim();
  if (!text) return 0;
  return text.split(/\r?\n/).filter((line) => line.trim()).length;
}

function isLargeComboInput() {
  return comboLineCount() > LARGE_COMBO_THRESHOLD || combosOnServer;
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
  } catch (_) {
    /* ignore save errors for large payloads */
  }
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
      combosText.placeholder = `${storedComboCount.toLocaleString()} combos loaded on server (use Start / Resume)`;
    } else if (!proxiesText.value) {
      proxiesText.value =
        "core-residential.evomi.com:1000:gulley886:tStXC3zZrqpDmVdVQdzF_country-US";
    }

    if (data.proxies) proxiesText.value = data.proxies;
    if (data.threads) threadsInput.value = data.threads;
    sessionCheckedCount = data.checked_count || 0;
    updateResumeHint();
    if (data.logs?.length) {
      logBox.textContent = data.logs.join("\n");
      lastLogCount = data.logs.length;
    }
    updateStatus(data);
  } catch (_) {
    proxiesText.value =
      proxiesText.value ||
      "core-residential.evomi.com:1000:gulley886:tStXC3zZrqpDmVdVQdzF_country-US";
  }
}

function updateResumeHint() {
  const comboInfo = combosOnServer && storedComboCount > 0
    ? `${storedComboCount.toLocaleString()} combos on server`
    : comboLineCount() > 0
      ? `${comboLineCount().toLocaleString()} combos in box`
      : "paste combos or upload a file";

  if (sessionCheckedCount > 0) {
    resumeHint.textContent =
      `${comboInfo} · ${sessionCheckedCount.toLocaleString()} already checked — Start skips those and continues.`;
  } else {
    resumeHint.textContent =
      `${comboInfo} · large lists stay on the server (no browser freeze). Already-checked combos are skipped on resume.`;
  }
}

combosText.addEventListener("input", () => {
  if (comboLineCount() <= LARGE_COMBO_THRESHOLD) {
    combosOnServer = false;
  }
  updateResumeHint();
  scheduleSave();
});
proxiesText.addEventListener("input", scheduleSave);
threadsInput.addEventListener("change", scheduleSave);

comboFile.addEventListener("change", () => {
  const file = comboFile.files[0];
  comboFileName.textContent = file ? `${file.name} (${formatBytes(file.size)})` : "No file";
  if (file) {
    combosOnServer = true;
    storedComboCount = 0;
    combosText.value = "";
    combosText.placeholder = `File selected: ${file.name} — will upload on Start (not loaded into browser)`;
    updateResumeHint();
  }
});

proxyFile.addEventListener("change", async () => {
  const file = proxyFile.files[0];
  proxyFileName.textContent = file ? file.name : "No file";
  if (file && file.size < 512 * 1024) {
    const text = await file.text();
    proxiesText.value = proxiesText.value ? `${proxiesText.value}\n${text}` : text;
    scheduleSave();
  } else if (file) {
    proxyFileName.textContent = `${file.name} (uploads on Start)`;
  }
});

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function updateSelectionButtons() {
  const count = selectedIds.size;
  copySelectedBtn.disabled = count === 0;
  deleteSelectedBtn.disabled = count === 0;
}

function renderHits() {
  if (!hits.length) {
    hitsBody.innerHTML = '<tr class="empty-row"><td colspan="3">No hits yet</td></tr>';
    updateSelectionButtons();
    return;
  }

  hitsBody.innerHTML = hits
    .map(
      (hit) => `
    <tr data-id="${hit.id}">
      <td class="col-check">
        <input type="checkbox" class="hit-check" data-id="${hit.id}" ${selectedIds.has(hit.id) ? "checked" : ""} />
      </td>
      <td><div class="hit-line">${escapeHtml(hit.line)}</div></td>
      <td class="col-actions">
        <button class="btn small copy-one" data-line="${escapeAttr(hit.line)}">Copy</button>
        <button class="btn small danger delete-one" data-id="${hit.id}">Del</button>
      </td>
    </tr>`
    )
    .join("");

  hitsBody.querySelectorAll(".hit-check").forEach((el) => {
    el.addEventListener("change", (e) => {
      const id = Number(e.target.dataset.id);
      if (e.target.checked) selectedIds.add(id);
      else selectedIds.delete(id);
      updateSelectionButtons();
    });
  });

  hitsBody.querySelectorAll(".copy-one").forEach((el) => {
    el.addEventListener("click", () => copyText(el.dataset.line));
  });

  hitsBody.querySelectorAll(".delete-one").forEach((el) => {
    el.addEventListener("click", async () => {
      await deleteHits([Number(el.dataset.id)]);
    });
  });

  updateSelectionButtons();
}

function escapeHtml(str) {
  return str
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeAttr(str) {
  return str.replaceAll('"', "&quot;");
}

async function copyText(text) {
  await navigator.clipboard.writeText(text);
  showToast("Copied to clipboard");
}

async function loadHits() {
  hits = await api("/api/hits");
  const valid = new Set(hits.map((h) => h.id));
  selectedIds = new Set([...selectedIds].filter((id) => valid.has(id)));
  renderHits();
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

selectAllBtn.addEventListener("click", () => {
  if (!hits.length) return;
  const allSelected = selectedIds.size === hits.length;
  if (allSelected) {
    selectedIds.clear();
  } else {
    hits.forEach((h) => selectedIds.add(h.id));
  }
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

clearHitsBtn.addEventListener("click", async () => {
  if (!hits.length) return;
  if (!confirm("Delete all hits?")) return;
  await api("/api/hits/clear", { method: "POST" });
  selectedIds.clear();
  await loadHits();
  showToast("All hits cleared");
});

resetProgressBtn.addEventListener("click", async () => {
  if (!confirm("Clear all checked progress? Combos will be re-checked on next start.")) return;
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
    showToast("Add at least one combo (paste, upload, or use stored list)");
    return;
  }

  const form = new FormData();
  form.append("threads", String(threadsInput.value || "5"));
  form.append("proxies", proxiesText.value);

  if (hasFile) {
    form.append("combo_file", comboFile.files[0]);
  } else if (textCount > 0) {
    if (textCount > LARGE_COMBO_THRESHOLD) {
      showToast(`Uploading ${textCount.toLocaleString()} combos to server...`);
      const blob = new Blob([combosText.value], { type: "text/plain" });
      form.append("combo_file", blob, "combos.txt");
    } else {
      form.append("combos", combosText.value);
    }
  } else {
    form.append("use_stored_combos", "true");
  }

  if (proxyFile.files[0]) {
    form.append("proxy_file", proxyFile.files[0]);
  }

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

    showToast(
      result.preparing
        ? `Preparing ${(result.combo_count || storedComboCount).toLocaleString()} combos...`
        : `Started — ${(result.queued || result.combo_count || 0).toLocaleString()} queued`
    );

    lastLogCount = 0;
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

function updateStatus(data) {
  const total = data.total || data.combo_count || 0;
  const checked = data.checked || 0;
  const skipped = data.skipped || 0;
  const pct = total ? Math.round(((checked + skipped) / total) * 100) : 0;
  progressFill.style.width = `${pct}%`;

  const parts = [];
  if (data.preparing) {
    parts.push("Preparing...");
  } else if (total) {
    parts.push(`${checked + skipped} / ${total} done`);
  } else if (data.combo_count) {
    parts.push(`${data.combo_count.toLocaleString()} combos loaded`);
  }
  if (skipped) parts.push(`${skipped.toLocaleString()} skipped`);
  parts.push(`${data.hits || 0} hits`);
  parts.push(`${data.fails || 0} fails`);
  if (data.errors) parts.push(`${data.errors} errors`);
  progressStats.textContent = parts.join(" · ");

  let statusLabel = "Idle";
  if (data.preparing) statusLabel = "Preparing";
  else if (data.running) statusLabel = "Running";
  statusPill.textContent = statusLabel;
  statusPill.className = `status-pill ${data.running || data.preparing ? "running" : "idle"}`;

  const busy = Boolean(data.running || data.preparing);
  startBtn.disabled = busy;
  stopBtn.disabled = !busy;
  resetProgressBtn.disabled = busy;

  if (data.combo_count !== undefined) {
    storedComboCount = data.combo_count;
  }
  if (data.combos_stored !== undefined) {
    combosOnServer = Boolean(data.combos_stored);
  }
  if (data.checked_count !== undefined) {
    sessionCheckedCount = data.checked_count;
  }
  updateResumeHint();

  if (data.logs && data.logs.length > lastLogCount) {
    logBox.textContent = data.logs.join("\n");
    logBox.scrollTop = logBox.scrollHeight;
    lastLogCount = data.logs.length;
  }
}

async function poll() {
  try {
    const data = await api("/api/status");
    updateStatus(data);
    if (data.hits > hits.length) await loadHits();
    if (!data.running && !data.preparing) {
      await loadHits();
      const session = await api("/api/session");
      sessionCheckedCount = session.checked_count || 0;
      storedComboCount = session.combo_count || storedComboCount;
      combosOnServer = Boolean(session.combos_stored);
      updateResumeHint();
    }
  } catch (_) {
    /* ignore transient errors */
  }
}

function startPolling() {
  if (!pollTimer) {
    pollTimer = setInterval(poll, 1000);
  }
  poll();
}

loadSession();
loadHits();
startPolling();
