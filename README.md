# Bloomingdale's Request Checker (RiskByPass)

Checks each step of the Bloomingdale's login and loyalty API flow using **RiskByPass** for Akamai bypass and optional reCAPTCHA v3.

## Requirements

```bash
pip install -r requirements.txt
```

## Environment

| Variable | Description |
|---|---|
| `RB_TOKEN` | RiskByPass API token |
| `RB_PROXY` | Proxy as `http://user:pass@host:port` or `host:port:user:pass` |
| `BLOOMINGDALES_EMAIL` | (optional) Test account email |
| `BLOOMINGDALES_PASSWORD` | (optional) Test account password |

## Usage

```bash
export RB_TOKEN="your_token"
export RB_PROXY="host:port:user:pass"
export BLOOMINGDALES_EMAIL="user@example.com"
export BLOOMINGDALES_PASSWORD="secret"

python bloomingdales_checker.py --profile both
python bloomingdales_checker.py --profile desktop --json
```

## Checks performed

1. **signin_page** — GET `/account/signin` (desktop and/or mobile)
2. **rb_akamai** — RB `akamai` task; reports `_abck` trust segment (`~0~` = trusted)
3. **pre_signin** — GET `/account-xapi/api/account/signin?_deviceType=PC|Phone`
4. **email_verify** — POST `/account-xapi/api/myaccount/email` (required before sign-in in site JS)
5. **rb_recaptcha_v3** — RB captcha token when `signInCaptchaEnabled`
6. **sign_in** — POST `/account-xapi/api/account/signin` (falls back to RB `tls_forward` on 403)
7. **loyalty_accountsummary** — GET `/xapi/loyalty/v1/accountsummary?_pageType=myAccount`

## RB task types used

| Task | Purpose |
|---|---|
| `akamai` | Generate `_abck` / `bm_sz` sensor cookies |
| `recaptchav3` | Login captcha token (`6LeBmfQb...` site key) |
| `tls_forward` | POST fallback when curl gets Akamai 403 |

## Notes

- Desktop **POST** APIs require trusted Akamai (`_abck` segment `0`). RB may return `~-1~` on some proxies; the checker reports this clearly.
- Mobile (`m.bloomingdales.com`) often returns HTTP 200 on sign-in POST but still requires a prior successful **email_verify** to authenticate.
- Do not commit tokens, proxy credentials, or passwords.
