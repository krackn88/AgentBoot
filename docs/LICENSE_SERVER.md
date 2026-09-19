# License Server + Dashboard

Online activation API and vendor dashboard for customer editions.

## URLs (dedi)

- **Dashboard:** http://159.69.76.189:8082
- **Activate API:** `POST http://159.69.76.189:8082/api/v1/activate`
- **Validate API:** `POST http://159.69.76.189:8082/api/v1/validate`

## Deploy on dedi

```bash
# Requires license_secret.txt in /opt/tropic-checker/ (same as customer build secret)
bash /opt/tropic-checker/deploy/install_license_server.sh
```

Set `LICENSE_ADMIN_TOKEN` before install to control dashboard access (shown after install).

## Vendor workflow

1. Open dashboard → **Create License**
2. Enter customer name, optional email, days until expiry (0 = never)
3. Copy the **activation code** (e.g. `TROPIC-AB12-CD34`) and send to customer
4. Customer enters code in desktop app → **Activate Online**

## Dashboard actions

| Action | Effect |
|--------|--------|
| **+30d** | Extend expiry by 30 days (re-issues key if already activated) |
| **Reset PC** | Clears hardware lock — customer can activate on a new machine |
| **Revoke** | Immediately blocks online validation |

## Customer desktop

Built with `TROPIC_LICENSE_API_URL` (default: `http://159.69.76.189:8081`).

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
{"license_key": "TROPIC1....", "hardware_id": "..."}
```

### Admin (header `X-Admin-Token`)

- `GET /admin/api/stats`
- `GET /admin/api/licenses`
- `POST /admin/api/licenses`
- `PATCH /admin/api/licenses/<id>` body `{"action":"revoke|reset_hwid|extend","days":30}`
