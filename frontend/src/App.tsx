import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActionDef,
  EnabledAction,
  aiChat,
  attachSession,
  buildGadgetConfig,
  composeScript,
  detachSession,
  fetchActions,
  fetchDevices,
  toggleRuntimeAction,
} from "./api";

type Tab = "script" | "gadget" | "logs";

function defaultParams(action: ActionDef): Record<string, unknown> {
  const p: Record<string, unknown> = {};
  for (const param of action.parameters) {
    if (param.default !== undefined) p[param.key] = param.default;
  }
  return p;
}

export default function App() {
  const [platform, setPlatform] = useState<string>("android");
  const [catalog, setCatalog] = useState<ActionDef[]>([]);
  const [enabled, setEnabled] = useState<Record<string, EnabledAction>>({});
  const [script, setScript] = useState("");
  const [customTail, setCustomTail] = useState("");
  const [tab, setTab] = useState<Tab>("script");
  const [connected, setConnected] = useState(false);
  const [target, setTarget] = useState("Gadget");
  const [deviceId, setDeviceId] = useState<string>("");
  const [devices, setDevices] = useState<{ id: string; name: string }[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [gadgetJson, setGadgetJson] = useState("");
  const [gadgetFile, setGadgetFile] = useState("libfrida-gadget.config.so");
  const [gMode, setGMode] = useState("listen");
  const [gPort, setGPort] = useState(27042);
  const [gAddress, setGAddress] = useState("127.0.0.1");
  const [gOnLoad, setGOnLoad] = useState("wait");
  const [chatInput, setChatInput] = useState("");
  const [chat, setChat] = useState<{ role: "user" | "assistant"; content: string }[]>([
    {
      role: "assistant",
      content:
        "I'm your AgentBoot copilot. Ask me to trace Android APIs, bypass SSL pinning, hook native exports, or export a Gadget config. Set OPENAI_API_KEY on the server for full AI responses.",
    },
  ]);
  const [busy, setBusy] = useState(false);

  const enabledList = useMemo(
    () => Object.values(enabled).filter((e) => e.enabled),
    [enabled]
  );

  const loadCatalog = useCallback(async () => {
    const actions = await fetchActions(platform);
    setCatalog(actions);
    setEnabled((prev) => {
      const next = { ...prev };
      for (const a of actions) {
        if (!next[a.id]) {
          next[a.id] = {
            id: a.id,
            enabled: !!a.required,
            params: defaultParams(a),
          };
        }
      }
      return next;
    });
  }, [platform]);

  useEffect(() => {
    loadCatalog().catch(console.error);
    fetchDevices().then(setDevices).catch(console.error);
  }, [loadCatalog]);

  const refreshScript = useCallback(async () => {
    const s = await composeScript(enabledList, customTail);
    setScript(s);
  }, [enabledList, customTail]);

  useEffect(() => {
    refreshScript().catch(console.error);
  }, [refreshScript]);

  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${window.location.host}/ws/logs`);
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.type === "ping") return;
        setLogs((l) => [
          ...l.slice(-200),
          `[${data.level}] ${data.message}${data.meta ? " " + JSON.stringify(data.meta) : ""}`,
        ]);
      } catch {
        /* ignore */
      }
    };
    return () => ws.close();
  }, []);

  const toggleAction = (id: string, on: boolean) => {
    setEnabled((prev) => ({
      ...prev,
      [id]: { ...prev[id], enabled: on },
    }));
  };

  const setParam = (id: string, key: string, value: unknown) => {
    setEnabled((prev) => ({
      ...prev,
      [id]: {
        ...prev[id],
        params: { ...prev[id].params, [key]: value },
      },
    }));
  };

  const onAttach = async () => {
    setBusy(true);
    try {
      const res = await attachSession({
        device_id: deviceId || null,
        target,
        script,
        actions: enabledList,
      });
      setConnected(res.connected);
    } catch (e) {
      alert(String(e));
    } finally {
      setBusy(false);
    }
  };

  const onDetach = async () => {
    await detachSession();
    setConnected(false);
  };

  const onRuntimeToggle = async (actionId: string, on: boolean) => {
    try {
      await toggleRuntimeAction(actionId, on);
      setLogs((l) => [...l, `[ui] runtime ${actionId} => ${on}`]);
    } catch (e) {
      alert(String(e));
    }
  };

  const onExportGadget = async () => {
    const res = await buildGadgetConfig({
      mode: gMode,
      address: gAddress,
      port: gPort,
      on_load: gOnLoad,
      script_path: gMode === "script" ? "/data/local/tmp/agentboot.js" : undefined,
      gadget_binary_name: "libfrida-gadget",
    });
    setGadgetJson(res.json);
    setGadgetFile(res.filename);
  };

  const onSendChat = async () => {
    const text = chatInput.trim();
    if (!text) return;
    const userMsg = { role: "user" as const, content: text };
    const next = [...chat, userMsg];
    setChat(next);
    setChatInput("");
    setBusy(true);
    try {
      const res = await aiChat(next.map((m) => ({ role: m.role, content: m.content })));
      setChat((c) => [...c, { role: "assistant", content: res.content }]);
      if (res.suggested_actions?.length) {
        setEnabled((prev) => {
          const copy = { ...prev };
          for (const s of res.suggested_actions!) {
            copy[s.id] = s;
          }
          return copy;
        });
      }
    } catch (e) {
      setChat((c) => [...c, { role: "assistant", content: "Error: " + String(e) }]);
    } finally {
      setBusy(false);
    }
  };

  const byCategory = useMemo(() => {
    const m = new Map<string, ActionDef[]>();
    for (const a of catalog) {
      const list = m.get(a.category) ?? [];
      list.push(a);
      m.set(a.category, list);
    }
    return m;
  }, [catalog]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark" />
          <div>
            <h1>AgentBoot GadgetForge</h1>
            <p>Frida Gadget control plane with AI-assisted instrumentation</p>
          </div>
        </div>
        <div className="status-pill">
          <span className={`status-dot ${connected ? "live" : ""}`} />
          {connected ? `Attached · ${target}` : "Disconnected"}
        </div>
      </header>

      <div className="main-grid">
        <aside className="panel">
          <div className="panel-header">Actions</div>
          <div className="toolbar">
            <select
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
              aria-label="Platform"
            >
              <option value="android">Android</option>
              <option value="ios">iOS</option>
              <option value="generic">Generic</option>
            </select>
            <button type="button" className="btn" onClick={() => refreshScript()}>
              Recompose
            </button>
          </div>
          <div className="panel-body">
            {[...byCategory.entries()].map(([cat, items]) => (
              <div key={cat}>
                <div style={{ fontSize: "0.72rem", color: "var(--muted)", margin: "8px 0" }}>
                  {cat}
                </div>
                {items.map((action) => {
                  const state = enabled[action.id];
                  if (!state) return null;
                  return (
                    <div
                      key={action.id}
                      className={`action-card ${state.enabled ? "enabled" : ""}`}
                    >
                      <div className="action-head">
                        <input
                          type="checkbox"
                          checked={state.enabled}
                          disabled={action.required}
                          onChange={(e) => toggleAction(action.id, e.target.checked)}
                        />
                        <div style={{ flex: 1 }}>
                          <div className="action-title">
                            {action.name}
                            <span className="badge">{action.id}</span>
                          </div>
                          <div className="action-desc">{action.description}</div>
                          {connected && state.enabled && action.id !== "runtime.bootstrap" && (
                            <div style={{ marginTop: 8 }}>
                              <button
                                type="button"
                                className="btn"
                                onClick={() => onRuntimeToggle(action.id, true)}
                              >
                                Enable live
                              </button>
                              <button
                                type="button"
                                className="btn"
                                style={{ marginLeft: 6 }}
                                onClick={() => onRuntimeToggle(action.id, false)}
                              >
                                Disable live
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                      {action.parameters.length > 0 && (
                        <div className="param-grid">
                          {action.parameters.map((p) => (
                            <label key={p.key}>
                              {p.label}
                              {p.type === "boolean" ? (
                                <input
                                  type="checkbox"
                                  checked={!!state.params[p.key]}
                                  onChange={(e) => setParam(action.id, p.key, e.target.checked)}
                                />
                              ) : (
                                <input
                                  value={String(state.params[p.key] ?? "")}
                                  onChange={(e) => setParam(action.id, p.key, e.target.value)}
                                />
                              )}
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </aside>

        <main className="center-col">
          <div className="toolbar">
            <select
              value={deviceId}
              onChange={(e) => setDeviceId(e.target.value)}
              aria-label="Device"
            >
              <option value="">Default device</option>
              {devices.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
            <input
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              placeholder="Target (Gadget, bundle id, or pid)"
              style={{
                flex: 1,
                minWidth: 120,
                background: "var(--bg)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: "7px 10px",
                color: "var(--text)",
              }}
            />
            {!connected ? (
              <button type="button" className="btn primary" disabled={busy} onClick={onAttach}>
                Attach & inject
              </button>
            ) : (
              <button type="button" className="btn danger" onClick={onDetach}>
                Detach
              </button>
            )}
          </div>
          <div className="tabs">
            {(["script", "gadget", "logs"] as Tab[]).map((t) => (
              <button
                key={t}
                type="button"
                className={`tab ${tab === t ? "active" : ""}`}
                onClick={() => setTab(t)}
              >
                {t === "script" ? "Composed script" : t === "gadget" ? "Gadget config" : "Event log"}
              </button>
            ))}
          </div>
          {tab === "script" && (
            <>
              <textarea
                className="code-editor"
                value={script}
                onChange={(e) => setScript(e.target.value)}
                spellCheck={false}
              />
              <div style={{ padding: 12, borderTop: "1px solid var(--border)" }}>
                <label style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
                  Custom script tail (appended after actions)
                </label>
                <textarea
                  value={customTail}
                  onChange={(e) => setCustomTail(e.target.value)}
                  style={{
                    width: "100%",
                    minHeight: 64,
                    marginTop: 6,
                    fontFamily: "var(--mono)",
                    fontSize: 12,
                    background: "var(--bg)",
                    border: "1px solid var(--border)",
                    color: "var(--text)",
                    borderRadius: 8,
                    padding: 8,
                  }}
                />
              </div>
            </>
          )}
          {tab === "gadget" && (
            <div className="panel-body">
              <div className="config-form">
                <label>
                  Interaction mode
                  <select value={gMode} onChange={(e) => setGMode(e.target.value)}>
                    <option value="listen">listen (default)</option>
                    <option value="connect">connect</option>
                    <option value="script">script (embedded)</option>
                  </select>
                </label>
                <label>
                  Address
                  <input value={gAddress} onChange={(e) => setGAddress(e.target.value)} />
                </label>
                <label>
                  Port
                  <input
                    type="number"
                    value={gPort}
                    onChange={(e) => setGPort(Number(e.target.value))}
                  />
                </label>
                <label>
                  on_load
                  <select value={gOnLoad} onChange={(e) => setGOnLoad(e.target.value)}>
                    <option value="wait">wait (block until attach)</option>
                    <option value="resume">resume (start app immediately)</option>
                  </select>
                </label>
                <button type="button" className="btn primary" onClick={onExportGadget}>
                  Generate JSON
                </button>
              </div>
              {gadgetJson && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>
                    Save as: <code>{gadgetFile}</code> next to your Gadget library
                  </div>
                  <pre
                    style={{
                      background: "#0a0e13",
                      padding: 12,
                      borderRadius: 8,
                      fontSize: 12,
                      overflow: "auto",
                    }}
                  >
                    {gadgetJson}
                  </pre>
                </div>
              )}
            </div>
          )}
          {tab === "logs" && (
            <div className="panel-body log-stream">
              {logs.length === 0 && (
                <div style={{ color: "var(--muted)" }}>Waiting for script events…</div>
              )}
              {logs.map((line, i) => (
                <div key={i} className={`log-line ${line.includes("error") ? "error" : ""}`}>
                  {line}
                </div>
              ))}
            </div>
          )}
        </main>

        <aside className="panel">
          <div className="panel-header">AI Copilot</div>
          <div className="panel-body" style={{ display: "flex", flexDirection: "column" }}>
            <div className="chat-messages">
              {chat.map((m, i) => (
                <div key={i} className={`chat-bubble ${m.role}`}>
                  {m.content}
                </div>
              ))}
            </div>
            <div className="chat-input-row">
              <textarea
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="e.g. Help me trace OkHttp and bypass pinning for my test build"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) onSendChat();
                }}
              />
              <button
                type="button"
                className="btn primary"
                disabled={busy}
                onClick={onSendChat}
              >
                Ask AgentBoot
              </button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
