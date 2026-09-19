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

## Build customer editions (Linux or Windows hosts)

From Linux (builds both platforms):

```bash
bash build/build_customer_all.sh
```

Output:

- `dist/TropicChecker-Customer-linux-x86_64.tar.gz`
- `dist/TropicChecker-Customer-windows-x64.zip`

Windows-only obfuscated EXE (optional, requires Windows):

```bat
build\build_customer_windows.bat
```

Upload to the customer portal:

```bash
bash deploy/upload_customer_build.sh
```

## Issue a license (recommended: online dashboard)

1. Deploy license server: see `docs/LICENSE_SERVER.md`
2. Open dashboard → create license → copy **activation code**
3. Customer enters code in app → **Activate Online**

## Issue a license (offline CLI)

```bash
python tools/issue_license.py --hwid "XXXX-XXXX-XXXX-XXXX" --customer "Customer Name"
```

Optional trial: `--days 30`. Customer pastes key under **Offline Key** tab.

## Security notes

- **Never** ship `tools/issue_license.py`, `license_secret.txt`, or source code to customers
- Only ship the built `TropicChecker.exe` / zip
- Rotate secret and rebuild if the signing secret leaks
- Obfuscation raises the bar; determined reversers may still attack native binaries

## Customer data locations

- License: `%APPDATA%\TropicChecker\license.key`
- Checker data: `%USERPROFILE%\.tropic-checker\`
