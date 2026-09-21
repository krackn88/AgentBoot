"""Parse Charles Proxy .chlz capture files for Southwest API headers."""

import gzip
import json
import zipfile
from pathlib import Path
from typing import Any


SENSOR_HEADER_PREFIX = "X-dUblrIiu-"


def extract_chlz(chlz_path: str | Path, dest_dir: str | Path | None = None) -> Path:
    """Extract a .chlz zip archive and return the destination directory."""
    chlz_path = Path(chlz_path)
    if dest_dir is None:
        dest_dir = chlz_path.parent / f"{chlz_path.stem}_extracted"
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(chlz_path, "r") as zf:
        zf.extractall(dest_dir)

    return dest_dir


def _load_meta(extract_dir: Path, request_id: str) -> dict[str, Any]:
    meta_path = extract_dir / f"{request_id}-meta.json"
    with open(meta_path, encoding="utf-8") as f:
        return json.load(f)


def _headers_dict(meta: dict[str, Any]) -> dict[str, str]:
    headers = meta.get("request", {}).get("header", {}).get("headers", [])
    return {h["name"]: h["value"] for h in headers}


def _decompress_response(extract_dir: Path, request_id: str) -> bytes | None:
    for suffix in ("-res-enc.dat", "-res.json"):
        path = extract_dir / f"{request_id}{suffix}"
        if not path.exists():
            continue
        data = path.read_bytes()
        if data[:2] == b"\x1f\x8b":
            return gzip.decompress(data)
        return data
    return None


def find_login_request(extract_dir: Path) -> str | None:
    """Find the request ID for the security/token login call."""
    for meta_path in sorted(extract_dir.glob("*-meta.json")):
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        path = meta.get("path", "")
        method = meta.get("method", "")
        if method == "POST" and "/api/security/v4/security/token" in path:
            return meta_path.stem.replace("-meta", "")
    return None


def parse_capture(chlz_path: str | Path) -> dict[str, Any]:
    """
    Parse a Charles .chlz capture and extract login request details.

    Returns a dict with sensor_headers, base_headers, cookies, and sample response fields.
    """
    extract_dir = extract_chlz(chlz_path)
    login_id = find_login_request(extract_dir)
    if not login_id:
        raise ValueError("No login request found in capture (POST /api/security/v4/security/token)")

    meta = _load_meta(extract_dir, login_id)
    all_headers = _headers_dict(meta)

    sensor_headers = {
        k: v for k, v in all_headers.items() if k.startswith(SENSOR_HEADER_PREFIX)
    }
    skip = {"Content-Length", "Host", "Cookie"} | set(sensor_headers)
    base_headers = {k: v for k, v in all_headers.items() if k not in skip}

    cookies = all_headers.get("Cookie", "")

    req_body_path = extract_dir / f"{login_id}-req.dat"
    req_body = req_body_path.read_text(encoding="utf-8") if req_body_path.exists() else ""

    response_raw = _decompress_response(extract_dir, login_id)
    sample_response = None
    if response_raw:
        try:
            sample_response = json.loads(response_raw)
        except json.JSONDecodeError:
            pass

    return {
        "login_request_id": login_id,
        "sensor_headers": sensor_headers,
        "base_headers": base_headers,
        "cookies": cookies,
        "request_body_template": req_body,
        "sample_response": sample_response,
    }


def save_sensor_config(
    capture_data: dict[str, Any],
    output_path: str | Path,
    proxy: str | None = None,
) -> None:
    """Save extracted sensor/base headers to a JSON config file."""
    config = {
        "sensor_headers": capture_data["sensor_headers"],
        "base_headers": capture_data["base_headers"],
        "cookies": capture_data["cookies"],
    }
    if proxy:
        config["proxy"] = proxy
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def load_sensor_config(config_path: str | Path) -> dict[str, Any]:
    """Load sensor headers from a JSON config file."""
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)
