# AgentBoot GadgetForge

A control framework and web UI for **Frida Gadget** with modular instrumentation actions, runtime RPC toggles, Gadget config export, and an **AI copilot** for building scripts.

## Features

- **Action catalog** — Composable hooks (SSL unpinning, Java tracing, native exports, crypto, iOS network) with per-action parameters
- **Script composer** — Merges enabled actions into a single injectable script with the AgentBoot runtime bootstrap
- **Fine-grained runtime control** — Toggle individual actions over Frida RPC (`setAction`) without reloading the process
- **Gadget config builder** — Generate `listen` / `connect` / `script` JSON for `libfrida-gadget.config.so`
- **Web UI** — Action panel, script editor, config export, live event log, AI assistant sidebar
- **AI** — Set `OPENAI_API_KEY` (or `AGENTBOOT_AI_API_KEY`) for full chat; offline heuristics still suggest actions and compose scripts

## Quick start

### Backend

```bash
cd /path/to/AgentBoot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=.
./scripts/run-api.sh
```

API: `http://127.0.0.1:8787` — OpenAPI docs at `/docs`.

### Frontend (development)

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173` (proxies API/WebSocket to port 8787).

### Production (single server)

```bash
cd frontend && npm install && npm run build
cd .. && PYTHONPATH=. uvicorn backend.main:app --host 0.0.0.0 --port 8787
```

Serve the built UI from `frontend/dist` at the API root.

## Using with Frida Gadget

1. Patch your app with Frida Gadget (e.g. objection, manual embed).
2. Place generated config beside the library (often `libfrida-gadget.config.so` on Android with `android:extractNativeLibs="true"`).
3. Use **listen** mode and attach: `frida -H <device> -n Gadget` (Gadget shows as process name `Gadget`).
4. In the UI, enable actions, **Attach & inject**, then use **Enable live** / **Disable live** for per-hook control.

For early startup hooks, set `on_load` to `wait` and attach before the app resumes.

## Environment

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | AI chat (OpenAI-compatible) |
| `OPENAI_BASE_URL` | Optional alternate API base |
| `AGENTBOOT_AI_MODEL` | Model name (default `gpt-4o-mini`) |

## Tests

```bash
pip install pytest
PYTHONPATH=. pytest tests/
```

## Architecture

```
gadgetforge/          # Core framework
  actions/            # Catalog + JS templates
  composer.py         # Script bundling
  gadget_config.py    # Gadget JSON models
  session.py          # Frida attach + RPC
  ai.py               # Copilot
backend/main.py       # FastAPI
frontend/             # React UI
```

## License

Use responsibly — only on apps and devices you are authorized to test.
