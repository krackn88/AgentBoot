#!/usr/bin/env python3
"""Extract APIGuard metadata and sensor headers from a Charles .chlz capture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from southwest_checker.apiguard.headers import decode_e, decode_g
from southwest_checker.chlz_parser import (
    _headers_dict,
    _load_meta,
    extract_chlz,
    parse_capture,
    save_sensor_config,
)


def iter_sensor_requests(extract_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for meta_path in sorted(extract_dir.glob("*-meta.json")):
        rid = meta_path.stem.replace("-meta", "")
        meta = json.loads(meta_path.read_text())
        hdrs = _headers_dict(meta)
        sensors = {k: v for k, v in hdrs.items() if k.startswith("X-dUblrIiu-")}
        if not sensors:
            continue
        rows.append(
            {
                "id": rid,
                "method": meta.get("method"),
                "path": meta.get("path"),
                "time": meta.get("times", {}).get("start"),
                "sensor_keys": sorted(sensors),
                "a_len": len(sensors.get("X-dUblrIiu-a", "")),
                "a_head": sensors.get("X-dUblrIiu-a", "")[:32],
            }
        )
    return rows


def decode_metadata(sensor_headers: dict[str, str]) -> dict:
    out: dict = {}
    if "X-dUblrIiu-e" in sensor_headers:
        e = decode_e(sensor_headers["X-dUblrIiu-e"])
        sensor = json.loads(e["sensor"].decode("latin1"))
        out["e"] = {
            "pid": sensor.get("pid"),
            "kid": sensor.get("kid"),
            "sdk": sensor.get("sdk"),
            "uri": sensor.get("uri"),
            "cid": sensor.get("cid"),
            "sig": sensor.get("sig"),
        }
    if "X-dUblrIiu-g" in sensor_headers:
        g = decode_g(sensor_headers["X-dUblrIiu-g"])
        sig = json.loads(g["signal"].decode("utf-8"))
        extras = {item["key"]: item["value"] for item in sig.get("signalCvmExtra", []) if "key" in item}
        out["g"] = {
            "kernelId": extras.get("kernelId"),
            "nonce": extras.get("nonce"),
            "all_keys": extras.get("all_keys"),
            "jailbreak": sig.get("signalCvmIOSSysJailbreakDetection", {}).get("jailbreak"),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chlz", type=Path)
    parser.add_argument("--out-config", type=Path, default=Path("/tmp/sensor_config.json"))
    parser.add_argument("--out-meta", type=Path, default=Path("/tmp/chlz_apiguard_meta.json"))
    parser.add_argument("--extract-dir", type=Path, default=Path("/tmp/chlz_extracted"))
    args = parser.parse_args()

    extract_dir = extract_chlz(args.chlz, args.extract_dir)
    capture = parse_capture(args.chlz)
    save_sensor_config(capture, args.out_config)

    meta = {
        "source": str(args.chlz),
        "login_request_id": capture.get("login_request_id"),
        "login_success": bool(capture.get("sample_response", {}).get("access_token")),
        "sensor_header_keys": sorted(capture["sensor_headers"]),
        "decoded": decode_metadata(capture["sensor_headers"]),
        "sensor_requests": iter_sensor_requests(extract_dir),
        "unique_a_headers": len({r["a_head"] for r in iter_sensor_requests(extract_dir)}),
    }
    args.out_meta.write_text(json.dumps(meta, indent=2) + "\n")

    print(json.dumps(meta, indent=2))
    print(f"\nSaved sensor config -> {args.out_config}")
    print(f"Saved metadata -> {args.out_meta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
