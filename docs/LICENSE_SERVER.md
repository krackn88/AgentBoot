# License Server + Dashboard

Online activation API and vendor dashboard for customer editions.

## URLs (dedi)

- **Customer portal (downloads):** http://159.69.76.189:8082/
- **Vendor dashboard:** http://159.69.76.189:8082/admin
- **Activate API:** `POST http://159.69.76.189:8082/api/v1/activate`
- **Validate API:** `POST http://159.69.76.189:8082/api/v1/validate`

## Deploy on dedi

```bash
# Requires license_secret.txt in /opt/tropic-checker/ (same as customer build secret)
bash /opt/tropic-checker/deploy/install_license_server.sh
```

## Upload customer build to portal

Build the customer edition, then upload it. Two ways to build:

- **Fully obfuscated single EXE (Windows only):** `build\build_customer_windows.bat`
- **Portable zip (build from Linux):** `bash build/build_customer_portable.sh`
  — hardware-locked, embeds only the vendor **public** key, bundles Tcl/Tk so
  the GUI launches. Produces `dist/TropicChecker-Customer-windows-x64.zip`.

Then upload to the portal:

```bash
bash deploy/upload_customer_build.sh
```

Files are served at http://159.69.76.189:8082/portal/files/...
The customer download directory is `CUSTOMER_DOWNLOADS_DIR`
(default `/opt/tropic-checker/downloads/customer`).

## Security / access control

The activation + validation APIs and the customer download portal are public by
design. **Management is locked down** so only you can use it:

| Control | How |
|---------|-----|
| Admin token | `LICENSE_ADMIN_TOKEN` (required). Sent as the `X-Admin-Token` header; compared in constant time. |
| No token leak | The `/admin` page never embeds the token — the browser prompts for it and keeps it in that tab's `sessionStorage` only. |
| Header only | The admin token is **not** accepted via `?token=` query string (would leak into logs / history / Referer). |
| IP allowlist | Set `LICENSE_ADMIN_IPS` to your IP(s)/CIDRs (comma separated). Non-allowlisted callers get `404` on `/admin` and `/admin/api/*`. Empty = token-only. |
| Rate limiting | Activation/validation are rate limited per client IP (`LICENSE_RATE_LIMIT`, default 30/min). |
| Proxy spoofing | `X-Forwarded-For` is ignored unless `LICENSE_TRUST_PROXY=true`, so rate limits and the IP allowlist use the real socket peer. |
| Key forgery | License keys are **Ed25519-signed**; only the server holds the private key. See `docs/CUSTOMER_BUILD.md`. |

Recommended for "only me":

```bash
LICENSE_ADMIN_TOKEN="$(openssl rand -hex 24)" \
LICENSE_ADMIN_IPS="203.0.113.5"           \
bash deploy/install_license_server.sh
```

Put the server behind HTTPS (e.g. a reverse proxy with TLS) so tokens, license
keys, and hardware IDs are never sent in clear text; set `LICENSE_TRUST_PROXY=true`
and `LICENSE_PUBLIC_URL=https://…` when you do.

## Vendor workflow

1. Customer downloads the app and runs it — they copy their **Hardware ID** from the activation screen and send it to you
2. Open dashboard → **Create License**
3. Enter customer name, paste their **Hardware ID**, optional email, days until expiry (0 = never)
4. Copy the **activation code** (e.g. `TROPIC-AB12-CD34`) and send to customer
5. Customer enters code in desktop app → **Activate Online** (only works on the PC you locked)

## Dashboard actions

| Action | Effect |
|--------|--------|
| **+30d** | Extend expiry by 30 days (re-issues key if already activated) |
| **Reset PC** | Clears hardware lock — customer can activate on a new machine |
| **Revoke** | Immediately blocks online validation |

## Customer desktop

Built with `TROPIC_LICENSE_API_URL` (default: `http://159.69.76.189:8082`).

On each startup, app validates license online when possible (revoked/expired licenses blocked).

## API reference

### Activate (public)

```http
POST /api/v1/activate
{"activation_code": "TROPIC-AB12-CD34", "hardware_id": "A1B2C3D4..."}
```

Returns: `license_key`, `customer`, `expires_at`

### Validate (public)

```http
POST /api/v1/validate
{"license_key": "TROPIC2....", "hardware_id": "..."}
```

### Admin (header `X-Admin-Token`)

- `GET /admin/api/stats`
- `GET /admin/api/licenses`
- `POST /admin/api/licenses`
- `PATCH /admin/api/licenses/<id>` body `{"action":"revoke|reset_hwid|extend","days":30}`
