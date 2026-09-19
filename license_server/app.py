"""License activation API + vendor dashboard."""

from __future__ import annotations

import os
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from flask import Flask, abort, jsonify, redirect, render_template, request, send_from_directory

from .db import LicenseDB, validate_hwid
from .portal_files import list_downloads, resolve_file

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("LICENSE_DATA_DIR", APP_DIR.parent / "data" / "license-server"))
DB_PATH = DATA_DIR / "licenses.db"

ADMIN_TOKEN = os.environ.get("LICENSE_ADMIN_TOKEN", "")
API_RATE_LIMIT = int(os.environ.get("LICENSE_RATE_LIMIT", "30"))
PUBLIC_API_URL = os.environ.get(
    "LICENSE_PUBLIC_URL",
    "http://159.69.76.189:8082",
).rstrip("/")

app = Flask(
    __name__,
    template_folder=str(APP_DIR / "templates"),
    static_folder=str(APP_DIR / "static"),
)
db = LicenseDB(DB_PATH)

_rate: dict[str, list[float]] = {}


def _load_signing_secret() -> None:
    secret = os.environ.get("TROPIC_LICENSE_SECRET", "").strip()
    secret_file = Path(os.environ.get("LICENSE_SECRET_FILE", APP_DIR.parent / "license_secret.txt"))
    if not secret and secret_file.is_file():
        secret = secret_file.read_text(encoding="utf-8").strip()
    if not secret:
        return
    import importlib.util

    secret_path = APP_DIR.parent / "tropic_checker" / "licensing" / "_secret.py"
    spec = importlib.util.spec_from_file_location("tropic_lic_secret", secret_path)
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod._LICENSE_SECRET = secret.encode("utf-8")


_load_signing_secret()


def _client_ip() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr or "")


def _rate_ok(ip: str) -> bool:
    now = time.time()
    window = _rate.setdefault(ip, [])
    window[:] = [t for t in window if now - t < 60]
    if len(window) >= API_RATE_LIMIT:
        return False
    window.append(now)
    return True


def _admin_required(fn: Callable[..., Any]):
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        if not ADMIN_TOKEN:
            return jsonify({"error": "LICENSE_ADMIN_TOKEN not configured"}), 503
        token = request.headers.get("X-Admin-Token") or request.args.get("token", "")
        if token != ADMIN_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        return fn(*args, **kwargs)

    return wrapper


def _issue_key(hwid: str, customer: str, expires_at: int | None) -> str:
    from tropic_checker.licensing.license_core import issue_license

    return issue_license(hwid, customer, expires_at=expires_at)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/v1/activate")
def api_activate():
    ip = _client_ip()
    if not _rate_ok(ip):
        return jsonify({"error": "Too many requests — try again in a minute"}), 429

    data = request.get_json(silent=True) or {}
    code = str(data.get("activation_code", "")).strip()
    hwid = str(data.get("hardware_id", "")).replace("-", "").upper()

    if not code or not hwid or len(hwid) < 16:
        return jsonify({"error": "activation_code and hardware_id required"}), 400

    lic = db.get_by_code(code)
    if not lic:
        db.log_activation(None, hwid, ip, False, "invalid code")
        return jsonify({"error": "Invalid activation code"}), 404

    if lic.status == "revoked":
        db.log_activation(lic.id, hwid, ip, False, "revoked")
        return jsonify({"error": "License has been revoked"}), 403

    if lic.effective_status() == "expired":
        db.log_activation(lic.id, hwid, ip, False, "expired")
        return jsonify({"error": "License has expired"}), 403

    if lic.hardware_id and lic.hardware_id != hwid:
        db.log_activation(lic.id, hwid, ip, False, "hwid mismatch")
        msg = (
            "This license is locked to a different PC"
            if not lic.license_key
            else "This code is already activated on another PC"
        )
        return jsonify({"error": msg}), 403

    try:
        license_key = _issue_key(hwid, lic.customer_name, lic.expires_at)
    except Exception as exc:
        return jsonify({"error": f"License signing failed: {exc}"}), 500

    lic = db.activate(lic.id, hwid, license_key)
    db.log_activation(lic.id, hwid, ip, True, "activated")

    return jsonify({
        "license_key": license_key,
        "customer": lic.customer_name,
        "expires_at": lic.expires_at,
        "hardware_id": lic.hardware_id,
    })


@app.post("/api/v1/validate")
def api_validate():
    ip = _client_ip()
    if not _rate_ok(ip):
        return jsonify({"error": "Too many requests"}), 429

    data = request.get_json(silent=True) or {}
    hwid = str(data.get("hardware_id", "")).replace("-", "").upper()
    license_key = str(data.get("license_key", "")).strip()

    if not hwid or not license_key:
        return jsonify({"error": "hardware_id and license_key required"}), 400

    lic = db.get_by_hardware(hwid)
    if not lic or lic.license_key != license_key:
        return jsonify({"valid": False, "error": "License not found on server"}), 404

    if lic.status == "revoked":
        return jsonify({"valid": False, "error": "License revoked"}), 403

    if lic.effective_status() == "expired":
        return jsonify({"valid": False, "error": "License expired"}), 403

    db.touch(lic.id)
    return jsonify({
        "valid": True,
        "customer": lic.customer_name,
        "expires_at": lic.expires_at,
        "status": lic.effective_status(),
    })


@app.get("/")
def portal_home():
    return render_template(
        "portal.html",
        files=list_downloads(),
        api_url=PUBLIC_API_URL,
    )


@app.get("/portal")
def portal_alias():
    return redirect("/", code=302)


@app.get("/portal/files/<path:filename>")
def portal_download(filename: str):
    path = resolve_file(filename)
    if not path:
        abort(404)
    return send_from_directory(path.parent, path.name, as_attachment=True)


@app.get("/admin")
def dashboard():
    return render_template("dashboard.html", admin_token=ADMIN_TOKEN)


@app.get("/admin/api/stats")
@_admin_required
def admin_stats():
    return jsonify(db.stats())


@app.get("/admin/api/licenses")
@_admin_required
def admin_list():
    return jsonify({"licenses": [r.to_dict() for r in db.list_licenses()]})


@app.get("/admin/api/log")
@_admin_required
def admin_log():
    return jsonify({"log": db.recent_log()})


@app.post("/admin/api/licenses")
@_admin_required
def admin_create():
    data = request.get_json(silent=True) or {}
    customer = str(data.get("customer_name", "")).strip()
    if not customer:
        return jsonify({"error": "customer_name required"}), 400
    days = int(data.get("days", 0) or 0)
    hardware_id = str(data.get("hardware_id", "")).strip()
    if not hardware_id:
        return jsonify({"error": "hardware_id required — customer sends this from the app"}), 400
    try:
        validate_hwid(hardware_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    try:
        lic = db.create_license(
            customer,
            email=str(data.get("email", "")),
            days=days if days > 0 else None,
            notes=str(data.get("notes", "")),
            hardware_id=hardware_id,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"license": lic.to_dict()})


@app.patch("/admin/api/licenses/<license_id>")
@_admin_required
def admin_patch(license_id: str):
    data = request.get_json(silent=True) or {}
    action = data.get("action", "")
    if action == "revoke":
        return jsonify({"license": db.revoke(license_id).to_dict()})
    if action == "reset_hwid":
        return jsonify({"license": db.reset_hardware(license_id).to_dict()})
    if action == "extend":
        days = int(data.get("days", 30))
        lic = db.extend(license_id, days)
        if lic.hardware_id and lic.license_key:
            lic = db.activate(
                license_id,
                lic.hardware_id,
                _issue_key(lic.hardware_id, lic.customer_name, lic.expires_at),
            )
        return jsonify({"license": lic.to_dict()})
    return jsonify({"error": "Unknown action"}), 400


def create_app() -> Flask:
    return app
