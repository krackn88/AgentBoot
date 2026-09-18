# Tropical Smoothie Cafe Account Checker

Checks TSC mobile app accounts via `global.tropicalsmoothiecafeapi.com`.

## What it does

1. Encrypts the password with AES-128-CBC (key/IV extracted from the Android app)
2. Logs in via `POST /v1/profile/auth/login`
3. Fetches gift cards (`GET /v1/payment/giftcards`)
4. Fetches rewards balance and profile info

## Setup

```bash
pip install -r requirements.txt
```

## Usage

Single account:

```bash
python3 tsc_checker.py "email@example.com:password"
```

Combo file (`email:password` per line):

```bash
python3 tsc_checker.py combos.txt
```

JSON output:

```bash
python3 tsc_checker.py "email@example.com:password" --json
```

## Encryption details

Recovered from the React Native Hermes bundle (`aesEncrypt` in `aesEncryptionTSC` module):

| Parameter | Value |
|-----------|-------|
| Algorithm | AES-128-CBC |
| Key | `aesEncryptionTSC` |
| IV | `encryptionIntVec` |
| Padding | PKCS7 |
| Output | Base64 ciphertext |

## Notes

- Accounts registered via Apple/Facebook sign-in cannot be checked with email/password.
- Failed login status code `1016` = bad credentials or social-login-only account.
- Gift cards may be empty even on valid accounts (`gift_cards_enabled` can be false).
