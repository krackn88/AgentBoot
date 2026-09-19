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
const savedBodyRows = $("#savedBodyRows");
const logBox = $("#logBox");
const selectAllBtn = $("#selectAllBtn");
const copySelectedBtn = $("#copySelectedBtn");
const deleteSelectedBtn = $("#deleteSelectedBtn");
const clearHitsBtn = $("#clearHitsBtn");
const selectAllSavedBtn = $("#selectAllSavedBtn");
const copySelectedSavedBtn = $("#copySelectedSavedBtn");
const deleteSelectedSavedBtn = $("#deleteSelectedSavedBtn");
const copyAllSavedBtn = $("#copyAllSavedBtn");
const exportSavedBtn = $("#exportSavedBtn");
const clearSavedBtn = $("#clearSavedBtn");
const savedCountBadge = $("#savedCountBadge");
const savedPanelToggle = $("#savedPanelToggle");
const savedBody = $("#savedBody");
const savedChevron = $("#savedChevron");
const statProgress = $("#statProgress");
const statHits = $("#statHits");
const statValid = $("#statValid");
const statFails = $("#statFails");
const statErrors = $("#statErrors");
const toast = $("#toast");

const LARGE_COMBO_THRESHOLD = 2000;

let hits = [];
let savedCombos = [];
let selectedIds = new Set();
let selectedSavedIds = new Set();
let pollTimer = null;
let lastLogCount = 0;
let saveTimer = null;
let sessionCheckedCount = 0;
let storedComboCount = 0;
let combosOnServer = false;
let savedPanelOpen = true;

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

function escapeAttr(str) {
  return str.replaceAll('"', "&quot;");
}

function fallbackCopy(text) {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.top = "-1000px";
  ta.style.left = "-1000px";
  document.body.appendChild(ta);
  ta.select();
  ta.setSelectionRange(0, text.length);
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
      showToast("Copy failed — try Download .txt");
    }
  }
}

function getHitLine(id) {
  return hits.find((h) => h.id === id)?.line || "";
}

function getSavedLine(id) {
  return savedCombos.find((s) => s.id === id)?.line || "";
}

function shorten(text, max = 72) {
  if (!text) return "—";
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

function updateSelectionButtons() {
  const count = selectedIds.size;
  copySelectedBtn.disabled = count === 0;
  deleteSelectedBtn.disabled = count === 0;
}

function renderHits() {
  if (!hits.length) {
    hitsBody.innerHTML = '<tr class="empty-row"><td colspan="5">No credit hits yet</td></tr>';
    updateSelectionButtons();
    return;
  }

  hitsBody.innerHTML = hits
    .map((hit) => {
      const capture = [
        `Points ${hit.points || 0}`,
        hit.cc && hit.cc !== "N/A" ? hit.cc : null,
        hit.address && hit.address !== "N/A" ? shorten(hit.address, 56) : null,
      ]
        .filter(Boolean)
        .join(" · ");

      return `
    <tr data-id="${hit.id}">
      <td class="col-check">
        <input type="checkbox" class="hit-check" data-id="${hit.id}" ${selectedIds.has(hit.id) ? "checked" : ""} />
      </td>
      <td><span class="credit-badge">${hit.member_credits}</span></td>
      <td class="account-cell"><strong>${escapeHtml(hit.email)}</strong></td>
      <td class="capture-cell">${escapeHtml(capture)}</td>
      <td class="col-actions">
        <button class="btn small ghost copy-one" data-id="${hit.id}">Copy</button>
        <button class="btn small ghost danger delete-one" data-id="${hit.id}">Del</button>
      </td>
    </tr>`;
    })
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
    el.addEventListener("click", () => copyText(getHitLine(Number(el.dataset.id))));
  });

  hitsBody.querySelectorAll(".delete-one").forEach((el) => {
    el.addEventListener("click", async () => {
      await deleteHits([Number(el.dataset.id)]);
    });
  });

  updateSelectionButtons();
}

function updateSavedSelectionButtons() {
  const count = selectedSavedIds.size;
  copySelectedSavedBtn.disabled = count === 0;
  deleteSelectedSavedBtn.disabled = count === 0;
}

function renderSavedCombos() {
  const count = savedCombos.length;
  savedCountBadge.textContent = `${count.toLocaleString()} saved`;
  copyAllSavedBtn.disabled = count === 0;
  exportSavedBtn.disabled = count === 0;
  clearSavedBtn.disabled = count === 0;

  if (!count) {
    savedBodyRows.innerHTML = '<tr class="empty-row"><td colspan="3">No valid combos saved yet</td></tr>';
    selectedSavedIds.clear();
    updateSavedSelectionButtons();
    return;
  }

  const valid = new Set(savedCombos.map((s) => s.id));
  selectedSavedIds = new Set([...selectedSavedIds].filter((id) => valid.has(id)));

  savedBodyRows.innerHTML = savedCombos
    .map(
      (item) => `
    <tr data-id="${item.id}">
      <td class="col-check">
        <input type="checkbox" class="saved-check" data-id="${item.id}" ${selectedSavedIds.has(item.id) ? "checked" : ""} />
      </td>
      <td><div class="combo-line">${escapeHtml(item.line)}</div></td>
      <td class="col-actions">
        <button class="btn small ghost copy-saved" data-id="${item.id}">Copy</button>
        <button class="btn small ghost danger delete-saved" data-id="${item.id}">Del</button>
      </td>
    </tr>`
    )
    .join("");

  savedBodyRows.querySelectorAll(".saved-check").forEach((el) => {
    el.addEventListener("change", (e) => {
      const id = Number(e.target.dataset.id);
      if (e.target.checked) selectedSavedIds.add(id);
      else selectedSavedIds.delete(id);
      updateSavedSelectionButtons();
    });
  });

  savedBodyRows.querySelectorAll(".copy-saved").forEach((el) => {
    el.addEventListener("click", () => copyText(getSavedLine(Number(el.dataset.id))));
  });

  savedBodyRows.querySelectorAll(".delete-saved").forEach((el) => {
    el.addEventListener("click", async () => {
      await deleteSavedCombos([Number(el.dataset.id)]);
    });
  });

  updateSavedSelectionButtons();
}

async function loadHits() {
  hits = await api("/api/hits");
  const valid = new Set(hits.map((h) => h.id));
  selectedIds = new Set([...selectedIds].filter((id) => valid.has(id)));
  renderHits();
}

async function loadSavedCombos() {
  const data = await api("/api/saved-combos");
  savedCombos = data.items || [];
  if (data.count !== undefined) {
    savedCountBadge.textContent = `${data.count.toLocaleString()} saved`;
  }
  renderSavedCombos();
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

async function deleteSavedCombos(ids) {
  if (!ids.length) return;
  await api("/api/saved-combos/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  });
  ids.forEach((id) => selectedSavedIds.delete(id));
  await loadSavedCombos();
  showToast(`Deleted ${ids.length} combo(s)`);
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

clearHitsBtn.addEventListener("click", async () => {
  if (!hits.length) return;
  if (!confirm("Delete all credit hits?")) return;
  await api("/api/hits/clear", { method: "POST" });
  selectedIds.clear();
  await loadHits();
  showToast("Credit hits cleared");
});

selectAllSavedBtn.addEventListener("click", () => {
  if (!savedCombos.length) return;
  const allSelected = selectedSavedIds.size === savedCombos.length;
  selectedSavedIds = allSelected ? new Set() : new Set(savedCombos.map((s) => s.id));
  renderSavedCombos();
});

copySelectedSavedBtn.addEventListener("click", async () => {
  const lines = savedCombos
    .filter((s) => selectedSavedIds.has(s.id))
    .map((s) => s.line);
  if (!lines.length) return;
  await copyText(lines.join("\n"));
});

deleteSelectedSavedBtn.addEventListener("click", async () => {
  await deleteSavedCombos([...selectedSavedIds]);
});

copyAllSavedBtn.addEventListener("click", async () => {
  const text = await api("/api/saved-combos/export");
  if (!text.trim()) return;
  await copyText(text);
});

exportSavedBtn.addEventListener("click", () => {
  window.open("/api/saved-combos/export", "_blank");
});

clearSavedBtn.addEventListener("click", async () => {
  if (!savedCombos.length) return;
  if (!confirm("Clear all saved valid combos?")) return;
  await api("/api/saved-combos/clear", { method: "POST" });
  await loadSavedCombos();
  showToast("Saved combos cleared");
});

savedPanelToggle.addEventListener("click", () => {
  savedPanelOpen = !savedPanelOpen;
  savedBody.classList.toggle("collapsed", !savedPanelOpen);
  savedChevron.classList.toggle("open", savedPanelOpen);
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

  statProgress.textContent = total ? `${checked + skipped} / ${total}` : "—";
  statHits.textContent = String(data.hits || hits.length || 0);
  statValid.textContent = String(data.valid || 0);
  statFails.textContent = String(data.fails || 0);
  statErrors.textContent = String(data.errors || 0);

  const parts = [];
  if (data.preparing) parts.push("Preparing list...");
  else if (total) parts.push(`${checked + skipped} / ${total} checked`);
  else if (data.combo_count) parts.push(`${data.combo_count.toLocaleString()} loaded`);
  if (skipped) parts.push(`${skipped.toLocaleString()} skipped`);
  if (data.hits) parts.push(`${data.hits} credit hits`);
  if (data.valid) parts.push(`${data.valid} valid saved`);
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

  if (data.combo_count !== undefined) storedComboCount = data.combo_count;
  if (data.combos_stored !== undefined) combosOnServer = Boolean(data.combos_stored);
  if (data.checked_count !== undefined) sessionCheckedCount = data.checked_count;
  if (data.saved_combo_count !== undefined) {
    savedCountBadge.textContent = `${data.saved_combo_count.toLocaleString()} saved`;
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
    if (data.valid > savedCombos.length) await loadSavedCombos();
    if (!data.running && !data.preparing) {
      await loadHits();
      await loadSavedCombos();
      const session = await api("/api/session");
      sessionCheckedCount = session.checked_count || 0;
      storedComboCount = session.combo_count || storedComboCount;
      combosOnServer = Boolean(session.combos_stored);
      updateResumeHint();
    }
  } catch (_) {}
}

function startPolling() {
  if (!pollTimer) pollTimer = setInterval(poll, 1000);
  poll();
}

savedBody.classList.toggle("collapsed", !savedPanelOpen);
savedChevron.classList.toggle("open", savedPanelOpen);

loadSession();
loadHits();
loadSavedCombos();
startPolling();
