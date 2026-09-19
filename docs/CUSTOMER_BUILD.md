# Customer Edition (Windows)

Licensed, hardware-locked, obfuscated build for end customers.

## What customers get

- Single `TropicChecker.exe` (no Python install)
- Obfuscated code (PyArmor + PyInstaller)
- One license per PC (Hardware ID locked)
- Activation screen on first run

## One-time setup (you / vendor)

1. Generate a signing secret (keep private forever):

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

2. Save it as `license_secret.txt` in the repo root (gitignored).

## Build customer EXE (Windows machine required)

```bat
build\build_customer_windows.bat
```

Output:

- `dist\customer\release\TropicChecker.exe`
- `dist\TropicChecker-Customer-windows-x64.zip`

## Issue a license for a customer

Customer runs the app once, copies **Hardware ID**, sends it to you.

```bash
python tools/issue_license.py --hwid "XXXX-XXXX-XXXX-XXXX" --customer "Customer Name"
```

Optional trial:

```bash
python tools/issue_license.py --hwid "..." --customer "Trial" --days 30
```

Send the printed license key to the customer. They paste it in the activation window.

## Security notes

- **Never** ship `tools/issue_license.py`, `license_secret.txt`, or source code to customers
- Only ship the built `TropicChecker.exe` / zip
- Rotate secret and rebuild if the signing secret leaks
- Obfuscation raises the bar; determined reversers may still attack native binaries

## Customer data locations

- License: `%APPDATA%\TropicChecker\license.key`
- Checker data: `%USERPROFILE%\.tropic-checker\`
