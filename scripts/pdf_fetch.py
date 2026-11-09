#!/usr/bin/env python3
"""Download the 22 original APEA PDFs from the server for local extraction.

The PDFs are not in the repo (they total ~1.2 GB). Extraction reads them from
disk, so this pulls them once into a temp directory.

Usage:  DEDI_PW=... python3 scripts/pdf_fetch.py [--dest /tmp/pdfs]
"""
import argparse
import os
from pathlib import Path

try:
    import paramiko
except ImportError:
    raise SystemExit("pip install paramiko")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="/tmp/pdfs")
    ap.add_argument("--host", default=os.environ.get("DEDI_HOST", "159.69.76.189"))
    ap.add_argument("--remote", default="/srv/apea/2026-fnp-manuals/pdf")
    args = ap.parse_args()

    pw = os.environ.get("DEDI_PW")
    if not pw:
        raise SystemExit("set DEDI_PW")

    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(args.host, username="root", password=pw, timeout=30)
    _, out, _ = c.exec_command(f"ls {args.remote}")
    names = [n.strip() for n in out.read().decode().split() if n.strip().endswith(".pdf")]

    sftp = c.open_sftp()
    for n in names:
        target = dest / n
        if target.exists():
            print(f"  have {n}")
            continue
        sftp.get(f"{args.remote}/{n}", str(target))
        print(f"  got  {n}  {target.stat().st_size / 1e6:.1f} MB")
    sftp.close()
    c.close()
    print(f"{len(names)} PDFs in {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
