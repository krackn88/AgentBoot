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

let hits = [];
let selectedIds = new Set();
let pollTimer = null;
let lastLogCount = 0;
let saveTimer = null;
let sessionCheckedCount = 0;

function showToast(msg) {
  toast.textContent = msg;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2200);
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

function scheduleSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveSession, 600);
}

async function saveSession() {
  try {
    await api("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        combos: combosText.value,
        proxies: proxiesText.value,
        threads: Number(threadsInput.value || 5),
      }),
    });
  } catch (_) {
    /* ignore save errors */
  }
}

async function loadSession() {
  try {
    const data = await api("/api/session");
    if (data.combos) combosText.value = data.combos;
    else if (!proxiesText.value) {
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
  if (sessionCheckedCount > 0) {
    resumeHint.textContent =
      `${sessionCheckedCount} combo(s) already checked — Start will skip those and continue the rest.`;
  } else {
    resumeHint.textContent =
      "Combos and proxies are saved automatically. Already-checked combos are skipped on resume.";
  }
}

combosText.addEventListener("input", scheduleSave);
proxiesText.addEventListener("input", scheduleSave);
threadsInput.addEventListener("change", scheduleSave);

comboFile.addEventListener("change", async () => {
  comboFileName.textContent = comboFile.files[0]?.name || "No file";
  if (comboFile.files[0]) {
    const text = await comboFile.files[0].text();
    combosText.value = combosText.value ? `${combosText.value}\n${text}` : text;
    scheduleSave();
  }
});

proxyFile.addEventListener("change", async () => {
  proxyFileName.textContent = proxyFile.files[0]?.name || "No file";
  if (proxyFile.files[0]) {
    const text = await proxyFile.files[0].text();
    proxiesText.value = proxiesText.value ? `${proxiesText.value}\n${text}` : text;
    scheduleSave();
  }
});

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
  const comboText = combosText.value.trim();
  if (!comboText && !comboFile.files[0]) {
    showToast("Add at least one combo");
    return;
  }

  await saveSession();

  const form = new FormData();
  form.append("combos", combosText.value);
  form.append("proxies", proxiesText.value);
  form.append("threads", String(threadsInput.value || "5"));
  if (comboFile.files[0]) form.append("combo_file", comboFile.files[0]);

  startBtn.disabled = true;
  try {
    const result = await api("/api/jobs/start", { method: "POST", body: form });
    const skipped = result.skipped || 0;
    const queued = result.queued ?? result.total;
    showToast(
      skipped
        ? `Resuming — ${queued} to check, ${skipped} skipped`
        : `Started — ${queued} combo(s)`
    );
    if (!result.running && queued === 0) {
      logBox.textContent = "All combos already checked.";
    } else {
      lastLogCount = 0;
    }
    await poll();
  } catch (err) {
    showToast(err.message || "Failed to start");
    startBtn.disabled = false;
  }
});

stopBtn.addEventListener("click", async () => {
  await api("/api/jobs/stop", { method: "POST" });
  showToast("Stopping...");
});

function updateStatus(data) {
  const total = data.total || 0;
  const checked = data.checked || 0;
  const skipped = data.skipped || 0;
  const pct = total ? Math.round(((checked + skipped) / total) * 100) : 0;
  progressFill.style.width = `${pct}%`;

  const parts = [];
  if (total) parts.push(`${checked + skipped} / ${total} done`);
  if (skipped) parts.push(`${skipped} skipped`);
  parts.push(`${data.hits || 0} hits`);
  parts.push(`${data.fails || 0} fails`);
  if (data.errors) parts.push(`${data.errors} errors`);
  progressStats.textContent = parts.join(" · ");

  statusPill.textContent = data.running ? "Running" : "Idle";
  statusPill.className = `status-pill ${data.running ? "running" : "idle"}`;
  startBtn.disabled = data.running;
  stopBtn.disabled = !data.running;
  resetProgressBtn.disabled = data.running;

  if (data.checked_count !== undefined) {
    sessionCheckedCount = data.checked_count;
    updateResumeHint();
  }

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
    if (!data.running) {
      await loadHits();
      const session = await api("/api/session");
      sessionCheckedCount = session.checked_count || 0;
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
