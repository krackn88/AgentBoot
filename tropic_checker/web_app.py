"""Flask web UI for Tropic Time Checker."""

from __future__ import annotations

import json
import os
import queue
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, render_template, request, send_from_directory

from .api import AccountResult, parse_combo_line
from .engine import CheckerEngine, CheckerStats
from .smoke import run_smoke_checks
from . import storage

WEB_DIR = Path(__file__).resolve().parent / "web"
DATA_ROOT = Path(os.environ.get("TROPIC_DATA_DIR", storage.APP_DIR))

app = Flask(
    __name__,
    template_folder=str(WEB_DIR / "templates"),
    static_folder=str(WEB_DIR / "static"),
)
app.config["SECRET_KEY"] = os.environ.get("TROPIC_SECRET", "tropic-change-me")

# Optional simple auth token for dedi deployment
AUTH_TOKEN = os.environ.get("TROPIC_AUTH_TOKEN", "")


class AppState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.combos: list[tuple[str, str]] = []
        self.proxies: list[str] = []
        self.hits: list[dict[str, Any]] = []
        self.logs: list[str] = []
        self.stats = CheckerStats()
        self.running = False
        self.engine: CheckerEngine | None = None
        self.worker: threading.Thread | None = None
        self.event_subscribers: list[queue.Queue[str]] = []

    def publish(self, event: dict[str, Any]) -> None:
        payload = json.dumps(event)
        dead: list[queue.Queue[str]] = []
        for q in self.event_subscribers:
            try:
                q.put_nowait(payload)
            except queue.Full:
                dead.append(q)
        self.event_subscribers = [q for q in self.event_subscribers if q not in dead]

    def subscribe(self) -> queue.Queue[str]:
        q: queue.Queue[str] = queue.Queue(maxsize=500)
        self.event_subscribers.append(q)
        return q

    def add_log(self, message: str) -> None:
        with self.lock:
            self.logs.append(message)
            if len(self.logs) > 500:
                self.logs = self.logs[-500:]
        self.publish({"type": "log", "message": message})

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "running": self.running,
                "combo_count": len(self.combos),
                "proxy_count": len(self.proxies),
                "hits": list(self.hits),
                "logs": self.logs[-100:],
                "stats": {
                    "total": self.stats.total,
                    "checked": self.stats.checked,
                    "hits": self.stats.hits,
                    "fails": self.stats.fails,
                    "cpm": round(self.stats.cpm, 1),
                },
            }


state = AppState()


def _auth_ok() -> bool:
    if not AUTH_TOKEN:
        return True
    token = request.headers.get("X-Auth-Token") or request.args.get("token", "")
    return token == AUTH_TOKEN


def _require_auth():
    if not _auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    return None


def _result_to_hit(result: AccountResult) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "line": result.summary_line(),
        "combo": result.combo,
        "email": result.email,
        "password": result.password,
        "name": result.display_name,
        "points": result.points or 0,
        "gift_cards": len(result.gift_cards),
        "gift_card_balance": result.gift_card_balance,
        "rewards": [
            {"name": r.get("name"), "expiring_at": r.get("expiring_at")}
            for r in result.rewards
        ],
        "referral_code": (result.profile or {}).get("referral_code"),
    }


def _parse_combos_text(text: str) -> list[tuple[str, str]]:
    combos: list[tuple[str, str]] = []
    for line in text.splitlines():
        parsed = parse_combo_line(line)
        if parsed:
            combos.append(parsed)
    return combos


def _parse_proxies_text(text: str) -> list[str]:
    proxies: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            proxies.append(line)
    return proxies


def _load_persisted() -> None:
    storage.ensure_dirs()
    hits_path = DATA_ROOT / "data" / "hits.json"
    if hits_path.exists():
        try:
            state.hits = json.loads(hits_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    combo_path = DATA_ROOT / "data" / "combos.txt"
    if combo_path.exists():
        state.combos = storage.load_combos(combo_path)
    proxy_path = DATA_ROOT / "data" / "proxies.txt"
    if proxy_path.exists():
        state.proxies = storage.load_proxies(proxy_path)


def _save_hits() -> None:
    path = DATA_ROOT / "data" / "hits.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.hits, indent=2), encoding="utf-8")


def _save_combos() -> None:
    path = DATA_ROOT / "data" / "combos.txt"
    storage.save_combos(path, state.combos)


def _save_proxies() -> None:
    path = DATA_ROOT / "data" / "proxies.txt"
    storage.save_proxies(path, state.proxies)


@app.before_request
def check_auth():
    if request.endpoint in ("static", "index", "health"):
        return None
    if request.path.startswith("/static"):
        return None
    return _require_auth()


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/")
def index():
    return render_template("index.html", auth_token=AUTH_TOKEN)


@app.get("/api/state")
def api_state():
    return jsonify(state.snapshot())


@app.post("/api/combos")
def api_set_combos():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    if text:
        state.combos = _parse_combos_text(text)
    _save_combos()
    state.add_log(f"Loaded {len(state.combos)} combos")
    return jsonify({"combo_count": len(state.combos)})


@app.post("/api/proxies")
def api_set_proxies():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    if text is not None:
        state.proxies = _parse_proxies_text(text)
    _save_proxies()
    state.add_log(f"Loaded {len(state.proxies)} proxies")
    return jsonify({"proxy_count": len(state.proxies)})


@app.post("/api/start")
def api_start():
    if state.running:
        return jsonify({"error": "Already running"}), 400
    data = request.get_json(silent=True) or {}
    threads = int(data.get("threads", 5))
    threads = max(1, min(threads, 50))

    if not state.combos:
        return jsonify({"error": "No combos loaded"}), 400

    state.running = True
    state.stats = CheckerStats(total=len(state.combos))
    combos_snapshot = list(state.combos)

    def on_hit(result: AccountResult) -> None:
        hit = _result_to_hit(result)
        with state.lock:
            state.hits.insert(0, hit)
            combo = (result.email, result.password)
            if combo in state.combos:
                state.combos.remove(combo)
        _save_hits()
        _save_combos()
        snapshot = state.snapshot()
        state.publish({
            "type": "hit",
            "hit": hit,
            "stats": snapshot["stats"],
        })

    def on_fail(result: AccountResult) -> None:
        combo = (result.email, result.password)
        with state.lock:
            if combo in state.combos:
                state.combos.remove(combo)
        _save_combos()

    def on_progress(stats: CheckerStats) -> None:
        with state.lock:
            state.stats = stats
        state.publish({"type": "stats", "stats": state.snapshot()["stats"]})

    def on_log(message: str) -> None:
        state.add_log(message)

    state.engine = CheckerEngine(
        combos=combos_snapshot,
        proxies=state.proxies,
        threads=threads,
        on_hit=on_hit,
        on_fail=on_fail,
        on_progress=on_progress,
        on_log=on_log,
    )

    def run() -> None:
        try:
            state.engine.run()
        finally:
            state.running = False
            _save_combos()
            state.publish({"type": "done"})

    state.worker = threading.Thread(target=run, daemon=True)
    state.worker.start()
    return jsonify({"started": True, "total": len(combos_snapshot)})


@app.post("/api/smoke")
def api_smoke():
    results, all_ok = run_smoke_checks(skip_web=True, proxies=state.proxies)
    payload = [
        {"name": c.name, "status": c.status, "detail": c.detail}
        for c in results
    ]
    for check in results:
        state.add_log(f"SMOKE [{check.status.upper()}] {check.name}: {check.detail}")
    return jsonify({"ok": all_ok, "results": payload})


@app.post("/api/stop")
def api_stop():
    if not state.running:
        return jsonify({"stopped": False, "message": "Not running"})
    if state.engine:
        state.engine.stop()
    with state.lock:
        state.running = False
    state.publish({"type": "stopped"})
    return jsonify({"stopped": True})


@app.delete("/api/hits/<hit_id>")
def api_delete_hit(hit_id: str):
    with state.lock:
        state.hits = [h for h in state.hits if h.get("id") != hit_id]
    _save_hits()
    return jsonify({"deleted": hit_id})


@app.delete("/api/hits")
def api_clear_hits():
    with state.lock:
        state.hits.clear()
    _save_hits()
    return jsonify({"cleared": True})


@app.get("/api/events")
def api_events():
    def stream():
        q = state.subscribe()
        try:
            yield f"data: {json.dumps({'type': 'stats', 'stats': state.snapshot()['stats']})}\n\n"
            while True:
                try:
                    msg = q.get(timeout=15)
                    yield f"data: {msg}\n\n"
                except queue.Empty:
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
        finally:
            if q in state.event_subscribers:
                state.event_subscribers.remove(q)

    return Response(stream(), mimetype="text/event-stream")


_load_persisted()


def create_app() -> Flask:
    return app


def main() -> None:
    host = os.environ.get("TROPIC_HOST", "0.0.0.0")
    port = int(os.environ.get("TROPIC_PORT", "8080"))
    _load_persisted()
    app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    main()
