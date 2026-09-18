# 🌴 Tropic Time Checker

Standalone Tropical Smoothie Cafe account checker with a themed GUI.

## Features

- **Combo loading** — load `email:password` lists from file
- **Proxy support** — rotate proxies (`ip:port` or `ip:port:user:pass`)
- **Multi-threaded** — configurable thread count (1–50)
- **Hits panel** — easy-to-read cards with points, gift cards, rewards
- **Copy hit / copy combo** — one-click clipboard copy
- **Delete hits** — remove individual hits or clear all
- **Auto-save** — combos, proxies, hits, and settings persist to `~/.tropic-checker/`

## Setup

```bash
pip install -r requirements.txt
```

On Linux you may also need:

```bash
sudo apt install python3-tk
```

## Run (Desktop GUI)

```bash
python run_checker.py
```

Or:

```bash
python -m tropic_checker
```

## Run (Web UI)

Local:

```bash
pip install -r requirements.txt
python run_web.py
```

Open http://localhost:8080

### Deploy to a dedicated server

```bash
tar czf tropic-deploy.tar.gz --exclude=.git --exclude=venv .
scp tropic-deploy.tar.gz root@YOUR_SERVER:/tmp/
ssh root@YOUR_SERVER
  mkdir -p /tmp/tropic-deploy && tar xzf /tmp/tropic-deploy.tar.gz -C /tmp/tropic-deploy
  TROPIC_AUTH_TOKEN=your-secret-token bash /tmp/tropic-deploy/deploy/install.sh
```

The install script sets up `/opt/tropic-checker`, a Python venv, and a systemd service on port **8080**.

## Combo format

```
email@example.com:password123
another@mail.com:MyPass!99
```

## Proxy format

```
1.2.3.4:8080
1.2.3.4:8080:user:pass
```

## CLI (legacy)

The original CLI checker is still available:

```bash
python tsc_checker.py "email@example.com:password"
```

## Data locations

| File | Path |
|------|------|
| Settings | `~/.tropic-checker/config.json` |
| Hits | `~/.tropic-checker/data/hits.txt` |
| Combos | `~/.tropic-checker/data/combos.txt` |
| Proxies | `~/.tropic-checker/data/proxies.txt` |

## Notes

- Password encryption: AES-128-CBC (`aesEncryptionTSC` / `encryptionIntVec`)
- Apple/Facebook-only accounts return login error 1016
- Gift cards may be empty on valid accounts
