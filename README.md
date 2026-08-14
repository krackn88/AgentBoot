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

## Michaels.com (easier target)

Checks sign-in and **Michaels Rewards** balance via `memberLookUp`.

| Variable | Description |
|---|---|
| `MICHAELS_EMAIL` | Test account email |
| `MICHAELS_PASSWORD` | Test account password |
| `MICHAELS_PX_APP_ID` | (optional) PerimeterX app id if RB needs it |

```bash
export RB_TOKEN="your_token"
export RB_PROXY="host:port:user:pass"
export MICHAELS_EMAIL="user@example.com"
export MICHAELS_PASSWORD="secret"

python michaels_checker.py --json
```

### Checks performed

1. **signin_page** — GET `/signin`
2. **rb_perimeterx** — RB `perimeterx_invisible` / `perimeterx_hold` for `_px*` cookies
3. **rb_akamai** — optional RB `akamai` if Akamai scripts are present
4. **sign_in** — POST `/api/usr/user/sign-in-secure`
5. **loyalty_id** — GET `/api/rewards/loyalty/findLoyaltyIdByUserId`
6. **rewards_member_lookup** — POST `/api/rewards/direct/loyalty/memberLookUp` (points, vouchers, offers)

### RB task types used

| Task | Purpose |
|---|---|
| `perimeterx_invisible` | Primary bot bypass (`_px3`, `_pxvid`) |
| `perimeterx_hold` | Fallback for press-and-hold challenge |
| `akamai` | Secondary CDN `_abck` if needed |
| `tls_forward` | POST/GET fallback on 403 |

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
- Michaels uses PerimeterX + Akamai; residential proxies work best.
- Bloomingdale's desktop POST APIs require trusted Akamai (`_abck` segment `0`).
