# AgentBoot GadgetForge

A control framework and web UI for **Frida Gadget** with modular instrumentation actions, runtime RPC toggles, Gadget config export, and an **AI copilot** for building scripts.

## Checker-oriented workflow (login at scale)

Gadget is used **once** to discover the real mobile login chain; HTTP replay runs **at scale** without a device per combo.

1. Enable **checker.okhttp_capture** (Android) or **checker.ios_login_capture** + SSL unpin if needed.
2. Attach Gadget, perform **one** successful login in the app.
3. Open the **Checker** tab → **Build checker recipe from capture** (ordered steps, `{{email}}` / `{{password}}`, token extracts).
4. Tune classification rules (`HIT` / `BAD` / `BAN` / `CAPTCHA` / `RETRY`) in the recipe JSON.
5. Paste combos, set threads/proxies → **Start job** (multi-threaded HTTP replay).

This mirrors patterns used in repo checkers (guest session → login → account APIs) but derives steps from live app traffic instead of manual Charles replay.

## Features

- **Action catalog** — Composable hooks (SSL unpinning, Java tracing, native exports, crypto, iOS network, **login capture**) with per-action parameters
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
