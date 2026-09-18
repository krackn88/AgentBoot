const authToken = document.querySelector('meta[name="auth-token"]')?.content || '';

function headers() {
  const h = { 'Content-Type': 'application/json' };
  if (authToken) h['X-Auth-Token'] = authToken;
  return h;
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: { ...headers(), ...(opts.headers || {}) },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

const els = {
  statusPill: document.getElementById('statusPill'),
  statTotal: document.getElementById('statTotal'),
  statChecked: document.getElementById('statChecked'),
  statHits: document.getElementById('statHits'),
  statFails: document.getElementById('statFails'),
  statCpm: document.getElementById('statCpm'),
  statCombos: document.getElementById('statCombos'),
  comboInput: document.getElementById('comboInput'),
  proxyInput: document.getElementById('proxyInput'),
  comboCount: document.getElementById('comboCount'),
  proxyCount: document.getElementById('proxyCount'),
  threads: document.getElementById('threads'),
  threadVal: document.getElementById('threadVal'),
  hitsList: document.getElementById('hitsList'),
  logBox: document.getElementById('logBox'),
};

function updateStats(stats, comboCount) {
  els.statTotal.textContent = stats.total;
  els.statChecked.textContent = stats.checked;
  els.statHits.textContent = stats.hits;
  els.statFails.textContent = stats.fails;
  els.statCpm.textContent = stats.cpm;
  if (comboCount !== undefined) els.statCombos.textContent = comboCount;
}

function appendLog(msg) {
  els.logBox.textContent += msg + '\n';
  els.logBox.scrollTop = els.logBox.scrollHeight;
}

function renderHits(hits) {
  if (!hits.length) {
    els.hitsList.innerHTML = '<div class="empty">No hits yet — load combos and start checking</div>';
    return;
  }
  els.hitsList.innerHTML = hits.map(hit => `
    <article class="hit-card" data-id="${hit.id}">
      <h3>🌴 HIT — ${hit.name || hit.email}</h3>
      <div class="combo">${hit.combo}</div>
      <div class="meta">
        Points: ${hit.points} • Gift Cards: ${hit.gift_cards}
        ${hit.gift_card_balance ? ` • GC $${hit.gift_card_balance.toFixed(2)}` : ''}
        • Rewards: ${hit.rewards?.length || 0}
        ${hit.referral_code ? ` • Ref: ${hit.referral_code}` : ''}
      </div>
      ${hit.rewards?.length ? `<div class="rewards">${hit.rewards.map(r => `↳ ${r.name}`).join('<br>')}</div>` : ''}
      <div class="actions">
        <button class="btn pink small" onclick="copyText('${escapeJs(hit.line)}')">Copy Hit</button>
        <button class="btn mint small" onclick="copyText('${escapeJs(hit.combo)}')">Copy Combo</button>
        <button class="btn red small" onclick="deleteHit('${hit.id}')">Delete</button>
      </div>
    </article>
  `).join('');
}

function escapeJs(s) {
  return s.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

window.copyText = (text) => navigator.clipboard.writeText(text);
window.deleteHit = async (id) => {
  await api(`/api/hits/${id}`, { method: 'DELETE' });
  const card = document.querySelector(`[data-id="${id}"]`);
  if (card) card.remove();
};

async function refreshState() {
  const data = await api('/api/state');
  updateStats(data.stats, data.combo_count);
  els.comboCount.textContent = `${data.combo_count} combos loaded`;
  els.proxyCount.textContent = `${data.proxy_count} proxies loaded`;
  renderHits(data.hits);
  els.logBox.textContent = data.logs.join('\n');
  setRunning(data.running);
}

function setRunning(running) {
  els.statusPill.textContent = running ? 'Running' : 'Idle';
  els.statusPill.classList.toggle('running', running);
  document.getElementById('startBtn').disabled = running;
}

function connectEvents() {
  const url = authToken ? `/api/events?token=${encodeURIComponent(authToken)}` : '/api/events';
  const es = new EventSource(url);
  es.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === 'log') appendLog(data.message);
    if (data.type === 'stats') updateStats(data.stats);
    if (data.type === 'hit') refreshState();
    if (data.type === 'done') { setRunning(false); refreshState(); }
  };
  es.onerror = () => setTimeout(connectEvents, 3000);
}

els.threads.addEventListener('input', () => {
  els.threadVal.textContent = els.threads.value;
});

document.getElementById('loadCombos').onclick = async () => {
  const data = await api('/api/combos', { method: 'POST', body: JSON.stringify({ text: els.comboInput.value }) });
  els.comboCount.textContent = `${data.combo_count} combos loaded`;
  refreshState();
};

document.getElementById('saveCombos').onclick = () => document.getElementById('loadCombos').click();

document.getElementById('loadProxies').onclick = async () => {
  const data = await api('/api/proxies', { method: 'POST', body: JSON.stringify({ text: els.proxyInput.value }) });
  els.proxyCount.textContent = `${data.proxy_count} proxies loaded`;
};

document.getElementById('saveProxies').onclick = () => document.getElementById('loadProxies').click();

document.getElementById('startBtn').onclick = async () => {
  try {
    await api('/api/start', { method: 'POST', body: JSON.stringify({ threads: Number(els.threads.value) }) });
    setRunning(true);
  } catch (e) { alert(e.message); }
};

document.getElementById('stopBtn').onclick = () => api('/api/stop', { method: 'POST' });

document.getElementById('clearHits').onclick = async () => {
  if (confirm('Clear all hits?')) {
    await api('/api/hits', { method: 'DELETE' });
    refreshState();
  }
};

document.getElementById('copyAllHits').onclick = async () => {
  const data = await api('/api/state');
  const lines = data.hits.map(h => h.line).join('\n');
  if (lines) copyText(lines);
};

document.getElementById('clearLog').onclick = () => { els.logBox.textContent = ''; };

refreshState();
connectEvents();
