# Zeus Network Account Checker

Checks Zeus Network credentials against `www.thezeusnetwork.com` (VHX platform) and captures subscription/plan details.

## Setup

```bash
pip install -r requirements.txt
```

## Web UI

Start the checker UI locally:

```bash
./run.sh
# or: PYTHONPATH=. python3 -m uvicorn server.app:app --host 0.0.0.0 --port 8093
```

Open `http://localhost:8093`

Features:

- **Combo sources** — paste, upload, combo library (`data/combos/`), or import from URL (VS dedi quick-import buttons)
- **Start line** — resume from any line in large files
- **Proxy presets** — residential (Evomi US), datacenter, or custom; rotate session toggle for resi
- **Results tabs** — active hits vs valid/inactive logins (stored separately)
- **Progress** — resume skips already-checked combos; reset progress when needed
- **Smoke test** — single combo check before a full run

### Deploy to dedi

```bash
BRANCH=cursor/zeus-checker-cfa6 PORT=8093 bash deploy/deploy.sh
```

Installs to `/opt/zeus-checker` and runs via systemd on port 8093.

## CLI Usage

Single combo:

```bash
python zeus_checker.py "email@example.com:password"
```

Combo file (`email:password` per line):

```bash
python zeus_checker.py -f combos.txt
```

JSON output:

```bash
python zeus_checker.py "email@example.com:password" --json
```

## Output

- `HIT` — valid login with active subscription
- `FAIL` — valid login but inactive/expired subscription
- `BAD` — invalid credentials
- `ERROR` — network, Cloudflare, or site failure

Example:

```
user@example.com:password123 | HIT | Active: Yes | Plan: Zeus Monthly | status=enabled | freq=monthly | renews=2026-10-21
```

## Flow

Based on the HAR capture of the Zeus web login flow:

1. GET `/login` for CSRF token and session cookie (Firefox TLS impersonation via `curl_cffi`)
2. POST `/login` with `email`, `password`, `authenticity_token`
3. On success, fetch `/settings/manage/billing.json` and `/settings/purchases.json` for plan/subscription capture
