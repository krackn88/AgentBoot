#!/usr/bin/env python3
"""Deploy dist/ to the dedi. Usage: DEDI_PW=... python3 scripts/deploy.py"""
import os, paramiko, pathlib
host=os.environ.get("DEDI_HOST","159.69.76.189"); pw=os.environ["DEDI_PW"]
dist=pathlib.Path(__file__).resolve().parent.parent/"dist"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, username="root", password=pw, timeout=30)
def run(cmd):
    _,o,e=c.exec_command(cmd, timeout=120); print(o.read().decode()); err=e.read().decode()
    if err.strip(): print("ERR:",err[:1000])
run("cp -a /srv/apea/study /srv/apea/study-backup-$(date +%Y%m%d-%H%M%S) && ls -d /srv/apea/study-backup-* | tail -3")
sftp=c.open_sftp()
def mkdir_p(p):
    try: sftp.mkdir(p)
    except IOError: pass
mkdir_p("/srv/apea/study-new")
for f in sorted(dist.rglob("*")):
    rel=str(f.relative_to(dist)); remote=f"/srv/apea/study-new/{rel}"
    if f.is_dir(): mkdir_p(remote)
    else:
        mkdir_p(str(pathlib.PurePosixPath(remote).parent)); sftp.put(str(f), remote); print("uploaded",rel)
sftp.close()
run("rm -rf /srv/apea/study-old && mv /srv/apea/study /srv/apea/study-old && mv /srv/apea/study-new /srv/apea/study && rm -rf /srv/apea/study-old && ls -la /srv/apea/study && du -sh /srv/apea/study")
c.close(); print("DEPLOY DONE")
