export type ActionParam = {
  key: string;
  label: string;
  type: string;
  default?: unknown;
};

export type ActionDef = {
  id: string;
  name: string;
  description: string;
  category: string;
  platforms: string[];
  required?: boolean;
  parameters: ActionParam[];
};

export type EnabledAction = {
  id: string;
  enabled: boolean;
  params: Record<string, unknown>;
};

export type CaptureEvent = {
  ts: number;
  phase: string;
  url: string;
  method: string;
  status?: number;
  response_body?: string;
};

export type CheckerRecipe = {
  name: string;
  base_url: string;
  steps: unknown[];
  classify: unknown[];
  notes?: string;
};

export type CheckerJobStatus = {
  running: boolean;
  total: number;
  checked: number;
  hits: number;
  bad: number;
  retries: number;
  errors: number;
  current: string;
  logs: string[];
  hits_lines: string[];
};

const json = async <T>(res: Response): Promise<T> => {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
};

export async function fetchActions(platform?: string): Promise<ActionDef[]> {
  const q = platform ? `?platform=${encodeURIComponent(platform)}` : "";
  const data = await json<{ actions: ActionDef[] }>(await fetch(`/api/actions${q}`));
  return data.actions;
}

export async function composeScript(
  actions: EnabledAction[],
  customScript = ""
): Promise<string> {
  const data = await json<{ script: string }>(
    await fetch("/api/compose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ actions, custom_script: customScript }),
    })
  );
  return data.script;
}

export type GadgetConfigResult = {
  json: string;
  filename: string;
  notes: Record<string, string>;
};

export async function buildGadgetConfig(body: Record<string, unknown>): Promise<GadgetConfigResult> {
  return json<GadgetConfigResult>(
    await fetch("/api/gadget-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  );
}

export async function attachSession(body: {
  device_id?: string | null;
  target: string;
  script?: string;
  actions: EnabledAction[];
}): Promise<{ connected: boolean; target: string | null }> {
  return json(
    await fetch("/api/session/attach", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  );
}

export async function detachSession(): Promise<void> {
  await fetch("/api/session/detach", { method: "POST" });
}

export async function toggleRuntimeAction(actionId: string, enabled: boolean): Promise<unknown> {
  return json(
    await fetch("/api/session/actions/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_id: actionId, enabled }),
    })
  );
}

export async function aiChat(messages: { role: string; content: string }[]): Promise<{
  content: string;
  offline?: boolean;
  suggested_actions?: EnabledAction[];
}> {
  return json(
    await fetch("/api/ai/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    })
  );
}

export async function fetchDevices(): Promise<{ id: string; name: string; type: string }[]> {
  const data = await json<{ devices: { id: string; name: string; type: string }[] }>(
    await fetch("/api/devices")
  );
  return data.devices;
}

export async function setCaptureFilter(urlPattern: string): Promise<void> {
  await fetch("/api/checker/capture/filter", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url_pattern: urlPattern }),
  });
}

export async function fetchCaptureEvents(limit = 50): Promise<CaptureEvent[]> {
  const data = await json<{ events: CaptureEvent[] }>(
    await fetch(`/api/checker/capture/events?limit=${limit}`)
  );
  return data.events;
}

export async function suggestCheckerRecipe(name?: string): Promise<CheckerRecipe> {
  const q = name ? `?name=${encodeURIComponent(name)}` : "";
  const data = await json<{ recipe: CheckerRecipe }>(
    await fetch(`/api/checker/recipe/suggest${q}`, { method: "POST" })
  );
  return data.recipe;
}

export async function fetchCheckerRecipe(): Promise<CheckerRecipe | null> {
  const data = await json<{ recipe: CheckerRecipe | null }>(await fetch("/api/checker/recipe"));
  return data.recipe;
}

export async function startCheckerJob(body: {
  combos: string[];
  threads: number;
  proxies: string[];
  delay_ms: number;
}): Promise<{ ok: boolean; error?: string; queued?: number }> {
  return json(await fetch("/api/checker/jobs/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }));
}

export async function stopCheckerJob(): Promise<void> {
  await fetch("/api/checker/jobs/stop", { method: "POST" });
}

export async function fetchCheckerJobStatus(): Promise<CheckerJobStatus> {
  return json(await fetch("/api/checker/jobs/status"));
}
