# AgentBoot — Retail Request Checkers (RiskByPass)

RB-powered checkers that validate login and loyalty/rewards API flows for retail sites.

## Requirements

```bash
pip install -r requirements.txt
```

Shared environment:

| Variable | Description |
|---|---|
| `RB_TOKEN` | RiskByPass API token |
| `RB_PROXY` | Proxy as `http://user:pass@host:port` or `host:port:user:pass` |

---

## Michaels.com

Checks sign-in and **Michaels Rewards** balance via `memberLookUp`.

Uses the official RB pattern: **akamai (with page_fp) + tls_forward for all API calls**.

| Variable | Description |
|---|---|
| `MICHAELS_EMAIL` | Test account email |
| `MICHAELS_PASSWORD` | Test account password |

```bash
export RB_TOKEN="your_token"
export RB_PROXY="host:port:user:pass"
export MICHAELS_EMAIL="user@example.com"
export MICHAELS_PASSWORD="secret"

python michaels_checker.py --json
```

### Checks performed

1. **signin_page** — GET `/signin` via curl_cffi (init cookies + scrape akamai JS URL)
2. **rb_akamai** — RB `akamai` with `page_fp`; requires `_abck` segment `0`
3. **sign_in** — RB `tls_forward` POST `/api/usr/user/sign-in-secure`
4. **loyalty_id** — RB `tls_forward` GET `/api/rewards/loyalty/findLoyaltyIdByUserId`
5. **rewards_member_lookup** — RB `tls_forward` POST `/api/rewards/direct/loyalty/memberLookUp`

### RB task types used

| Task | Purpose |
|---|---|
| `akamai` | Trusted `_abck` sensor cookies (always includes `page_fp`) |
| `tls_forward` | All authenticated API calls (sign-in, loyalty, rewards) |

---

## Bloomingdale's

Checks login and loyalty summary with Akamai + optional reCAPTCHA v3.

| Variable | Description |
|---|---|
| `BLOOMINGDALES_EMAIL` | (optional) Test account email |
| `BLOOMINGDALES_PASSWORD` | (optional) Test account password |

```bash
export RB_TOKEN="your_token"
export RB_PROXY="host:port:user:pass"
export BLOOMINGDALES_EMAIL="user@example.com"
export BLOOMINGDALES_PASSWORD="secret"

python bloomingdales_checker.py --profile both
python bloomingdales_checker.py --profile desktop --json
```

### Checks performed

1. **signin_page** — GET `/account/signin` (desktop and/or mobile)
2. **rb_akamai** — RB `akamai` task; reports `_abck` trust segment (`~0~` = trusted)
3. **pre_signin** — GET `/account-xapi/api/account/signin?_deviceType=PC|Phone`
4. **email_verify** — POST `/account-xapi/api/myaccount/email`
5. **rb_recaptcha_v3** — RB captcha token when `signInCaptchaEnabled`
6. **sign_in** — POST `/account-xapi/api/account/signin`
7. **loyalty_accountsummary** — GET `/xapi/loyalty/v1/accountsummary`

---

## Notes

- Do not commit tokens, proxy credentials, or passwords.
- Michaels is Akamai-only on most proxies (no PerimeterX). API POSTs require trusted `_abck` segment `0`.
- RB `tls_forward` uses fields `url`, `method`, `body_base64`, `cookies_dict` (not `target_url`/`target_method`).
