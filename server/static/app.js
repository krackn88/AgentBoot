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
const statusPill = $("#statusPill");
const progressFill = $("#progressFill");
const progressStats = $("#progressStats");
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

function showToast(msg) {
  toast.textContent = msg;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2200);
}

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

comboFile.addEventListener("change", () => {
  comboFileName.textContent = comboFile.files[0]?.name || "No file";
});
proxyFile.addEventListener("change", () => {
  proxyFileName.textContent = proxyFile.files[0]?.name || "No file";
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

startBtn.addEventListener("click", async () => {
  const form = new FormData();
  form.append("combos", combosText.value);
  form.append("proxies", proxiesText.value);
  form.append("threads", threadsInput.value || "5");
  if (comboFile.files[0]) form.append("combo_file", comboFile.files[0]);
  if (proxyFile.files[0]) form.append("proxy_file", proxyFile.files[0]);

  try {
    await api("/api/jobs/start", { method: "POST", body: form });
    showToast("Job started");
    startPolling();
  } catch (err) {
    showToast(err.message);
  }
});

stopBtn.addEventListener("click", async () => {
  await api("/api/jobs/stop", { method: "POST" });
  showToast("Stopping...");
});

function updateStatus(data) {
  const pct = data.total ? Math.round((data.checked / data.total) * 100) : 0;
  progressFill.style.width = `${pct}%`;
  progressStats.textContent = `${data.checked} / ${data.total} checked · ${data.hits} hits · ${data.fails} fails · ${data.errors} errors`;

  statusPill.textContent = data.running ? "Running" : "Idle";
  statusPill.className = `status-pill ${data.running ? "running" : "idle"}`;
  startBtn.disabled = data.running;
  stopBtn.disabled = !data.running;

  if (data.logs.length > lastLogCount) {
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
    if (!data.running && pollTimer) {
      await loadHits();
    }
  } catch (_) {
    /* ignore transient errors */
  }
}

function startPolling() {
  if (pollTimer) return;
  lastLogCount = 0;
  pollTimer = setInterval(poll, 1000);
  poll();
}

// Default Evomi proxy pre-filled for convenience
proxiesText.value = proxiesText.value || "core-residential.evomi.com:1000:gulley886:tStXC3zZrqpDmVdVQdzF_country-US";

loadHits();
startPolling();
