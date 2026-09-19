# Customer Edition (Windows)

Licensed, hardware-locked, obfuscated build for end customers.

## What customers get

- Single `TropicChecker.exe` (no Python install)
- Obfuscated code (PyArmor + PyInstaller)
- One license per PC (Hardware ID locked)
- Activation screen on first run

## Signing model (Ed25519, asymmetric)

License keys are signed with **Ed25519**. Your `license_secret.txt` is the
**private** signing seed and stays on your license server / build machine. The
build embeds only the derived **public** key into the client
(`tropic_checker/licensing/_secret.py`), so a reverse-engineered client can
verify licenses but **cannot forge** them — forging requires your private key.

## One-time setup (you / vendor)

1. Generate a signing secret (keep private forever):

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

2. Save it as `license_secret.txt` in the repo root (gitignored). Use the **same**
   secret on the license server and every customer build.

## Build customer EXE (Windows machine required)

```bat
build\build_customer_windows.bat
```

Output:

- `dist\customer\release\TropicChecker.exe`
- `dist\TropicChecker-Customer-windows-x64.zip`

## Build customer portable zip (from Linux)

No Windows needed. Hardware-locked and public-key-embedded, with Tcl/Tk bundled
(so the GUI launches), but not PyArmor-obfuscated:

```bash
bash build/build_customer_portable.sh   # needs: msitools, unzip, zip, curl
```

Output: `dist/TropicChecker-Customer-windows-x64.zip`

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
- Only ship the built `TropicChecker.exe` / zip (these contain only the **public** key)
- Ed25519 means a leaked/reverse-engineered client cannot forge licenses — but if
  your **private** `license_secret.txt` leaks, rotate it and rebuild both the
  server config and all customer builds
- Obfuscation raises the bar; determined reversers may still attack native binaries

## Customer data locations

- License: `%APPDATA%\TropicChecker\license.key`
- Checker data: `%USERPROFILE%\.tropic-checker\`
