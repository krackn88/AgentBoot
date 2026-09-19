# Fabletics Checker

Account checker for **app.fabletics.com** (Fabletics iOS mobile API), built from a Charles Proxy capture of the app.

## What it captures

On a valid login (`HIT`), the checker pulls member credit balances and billing context:

| Category | Fields |
|----------|--------|
| **Member credits** | Available member credits (tokens), store credit balance, membership store credit, max prepaid credits |
| **Membership** | Status, monthly price, next billing date, billing period, skip/due flags |
| **Account** | Name, email |

## API flow

Reverse-engineered from the `.chlz` capture:

1. `GET /api/sessions` — obtain guest JWT from the `Authorization` response header
2. `POST /api/auth/login` — exchange `email:password` for an access token (guest JWT required)
3. Account fetches:
   - `/api/accounts/me/profile`
   - `/api/accounts/me/membership`
   - `/api/accounts/me/membership/period`

## Install

```bash
pip install -r requirements.txt
```

## Usage

Single combo:

```bash
python -m fabletics "email@example.com:password"
```

Combo file:

```bash
python -m fabletics -f combos.txt -t 5 -o hits.txt
```

Proxy defaults to the configured Evomi residential US proxy. Override or disable:

```bash
python -m fabletics "email@example.com:password" --proxy host:port:user:pass
python -m fabletics "email@example.com:password" --no-proxy
```

JSON output:

```bash
python -m fabletics "email@example.com:password" --json
```

## Result statuses

- `HIT` — valid login, account data captured
- `FAIL` — invalid credentials
- `RETRY` — rate limit / server error (exit code 2)
- `ERROR` — unexpected failure

## Notes

- Uses `curl_cffi` with Safari iOS impersonation to pass Cloudflare.
- Residential proxy is enabled by default (Evomi US). Use `--no-proxy` for direct connection.
- The login endpoint blocks datacenter IPs without a proxy.
- Mobile API key and app version are embedded from the capture (`fabletics/config.py`).
