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
