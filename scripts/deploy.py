#!/usr/bin/env python3
"""Deploy dist/ to the dedi.

Usage:  DEDI_PW=... python3 scripts/deploy.py [--keep N] [--no-backup]

Each run used to create a full timestamped copy of the site and never remove old
ones, so a day of iteration left 32 directories behind. Now only the most recent
`--keep` backups (default 5) are retained.
"""
import argparse
import os
import pathlib

import paramiko

ap = argparse.ArgumentParser()
ap.add_argument("--keep", type=int, default=5, help="backups to retain")
ap.add_argument("--no-backup", action="store_true")
args = ap.parse_args()

host = os.environ.get("DEDI_HOST", "159.69.76.189")
pw = os.environ["DEDI_PW"]
dist = pathlib.Path(__file__).resolve().parent.parent / "dist"
if not (dist / "index.html").exists():
    raise SystemExit("dist/index.html missing - run npm run build first")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, username="root", password=pw, timeout=30)


def run(cmd, timeout=180):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode()
    err = e.read().decode()
    if out.strip():
        print(out.strip())
    if err.strip():
        print("ERR:", err[:1000])
    return out


if args.no_backup:
    print("skipping backup")
else:
    run("cp -a /srv/apea/study /srv/apea/study-backup-$(date +%Y%m%d-%H%M%S)")
    # prune old backups, newest first
    run(f"ls -1dt /srv/apea/study-backup-* 2>/dev/null | tail -n +{args.keep + 1} | xargs -r rm -rf")
    print(run("ls -1d /srv/apea/study-backup-* 2>/dev/null | wc -l").strip(), "backups retained")

sftp = c.open_sftp()


def mkdir_p(p):
    try:
        sftp.mkdir(p)
    except IOError:
        pass


run("rm -rf /srv/apea/study-new")
mkdir_p("/srv/apea/study-new")
for f in sorted(dist.rglob("*")):
    rel = str(f.relative_to(dist))
    remote = f"/srv/apea/study-new/{rel}"
    if f.is_dir():
        mkdir_p(remote)
    else:
        mkdir_p(str(pathlib.PurePosixPath(remote).parent))
        sftp.put(str(f), remote)
sftp.close()

run("rm -rf /srv/apea/study-old && mv /srv/apea/study /srv/apea/study-old "
    "&& mv /srv/apea/study-new /srv/apea/study && rm -rf /srv/apea/study-old "
    "&& du -sh /srv/apea/study")
c.close()
print("DEPLOY DONE")
