from __future__ import annotations

import os
from typing import Any

import httpx

from gadgetforge.catalog import load_catalog
from gadgetforge.composer import compose_script
from gadgetforge.composer import EnabledAction


SYSTEM_PROMPT = """You are AgentBoot, an expert assistant for Frida Gadget and dynamic instrumentation.
You help users:
- Choose and configure modular instrumentation actions
- Write safe, focused Frida JavaScript snippets
- Explain Gadget config (listen/connect/script modes)
- Suggest fine-grained hook strategies

When suggesting scripts, prefer AgentBoot.registerAction patterns and mention RPC toggles.
Be concise. Use markdown for code blocks. Do not assist with malware or unauthorized access — assume authorized security research."""


def _catalog_summary() -> str:
    catalog = load_catalog()
    lines = ["Available modular actions:"]
    for a in catalog.actions:
        lines.append(f"- {a.id}: {a.name} — {a.description}")
    return "\n".join(lines)


async def chat_completion(
    messages: list[dict[str, str]],
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("AGENTBOOT_AI_API_KEY")
    if not key:
        return _offline_response(messages)

    url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model_name = model or os.environ.get("AGENTBOOT_AI_MODEL", "gpt-4o-mini")

    enriched = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + _catalog_summary()},
        *messages,
    ]

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{url}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model_name,
                "messages": enriched,
                "temperature": 0.3,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return {"content": content, "model": model_name, "offline": False}


def _offline_response(messages: list[dict[str, str]]) -> dict[str, Any]:
    """Rule-based helper when no API key is configured."""
    last = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last = m.get("content", "").lower()
            break

    hints: list[str] = []
    suggested: list[EnabledAction] = []

    if "ssl" in last or "pinning" in last or "okhttp" in last:
        suggested.append(
            EnabledAction(id="ssl.unpinning_okhttp", enabled=True, params={"enabled": False})
        )
        hints.append("Enable **ssl.unpinning_okhttp** then toggle it live via RPC once attached.")
    if "trace" in last or "android" in last:
        suggested.append(
            EnabledAction(
                id="trace.java_methods",
                enabled=True,
                params={"className": "android.app.Activity", "methodName": "onCreate"},
            )
        )
    if "native" in last or "libc" in last:
        suggested.append(
            EnabledAction(
                id="hook.native_export",
                enabled=True,
                params={"module": "libc.so", "export": "open"},
            )
        )
    if "ios" in last or "url" in last:
        suggested.append(
            EnabledAction(id="ios.nsurlsession_log", enabled=True, params={"enabled": True})
        )

    if not suggested:
        suggested = [
            EnabledAction(id="runtime.bootstrap", enabled=True),
            EnabledAction(
                id="hook.native_export",
                enabled=True,
                params={"module": "libc.so", "export": "open"},
            ),
        ]
        hints.append(
            "Set `OPENAI_API_KEY` for full AI responses. I can still compose scripts from the action catalog."
        )

    script = compose_script(suggested)
    content = (
        "### AgentBoot (offline mode)\n\n"
        + "\n".join(f"- {h}" for h in hints)
        + "\n\nSuggested composed script:\n\n```javascript\n"
        + script[:4000]
        + ("\n... (truncated)" if len(script) > 4000 else "")
        + "\n```\n\nUse **Listen** gadget config on port 27042, attach with `frida -H device -n Gadget`, then toggle actions in the UI."
    )
    return {"content": content, "model": "offline-heuristics", "offline": True, "suggested_actions": [s.model_dump() for s in suggested]}
