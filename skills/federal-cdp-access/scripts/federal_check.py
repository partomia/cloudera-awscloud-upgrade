#!/usr/bin/env python3
"""Read-only health check of the federal CDP environment. Changes nothing, prints no secret.

  python3 federal_check.py                       # control plane, Data Lake, Data Hubs, CDW, CAI, CDE
  python3 federal_check.py --impala-table db.t   # also load one table's metadata in Impala (needs impyla)

Reads ~/.config/federal-cdp/federal.env (or FEDERAL_ENV_FILE). Exit 1 if any check fails.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path


def load_env() -> dict:
    path = Path(os.environ.get("FEDERAL_ENV_FILE", "~/.config/federal-cdp/federal.env")).expanduser()
    out = {}
    for line in path.read_text().splitlines():
        m = re.match(r"^(?:export )?([A-Z0-9_]+)=(.*)$", line.strip())
        if m:
            out[m.group(1)] = os.path.expanduser(m.group(2).strip().strip("'\""))
    return out


E = load_env()
FAILED = []


def report(name: str, ok: bool, detail: str) -> None:
    print(f"{'OK  ' if ok else 'FAIL'} {name}: {detail}")
    if not ok:
        FAILED.append(name)


def cdp(*args: str) -> dict:
    exe = E.get("FEDERAL_CDP_CLI") or shutil.which("cdp") or "cdp"
    r = subprocess.run([exe, "--profile", E.get("FEDERAL_CDP_PROFILE", "default"), *args],
                       capture_output=True, text=True, timeout=120)
    if r.returncode:
        raise RuntimeError(r.stderr.strip().splitlines()[-1][:200] if r.stderr.strip() else f"exit {r.returncode}")
    return json.loads(r.stdout or "{}")


def check(name: str, fn) -> None:
    try:
        ok, detail = fn()
        report(name, ok, detail)
    except Exception as e:  # a check failing must not stop the others
        report(name, False, f"{type(e).__name__}: {str(e)[:200]}")


def env_status():
    e = cdp("environments", "describe-environment", "--environment-name", E["FEDERAL_ENV_NAME"])["environment"]
    return e["status"] == "AVAILABLE", f"{e['environmentName']} {e['status']} ({e['region']})"


def datalake():
    d = cdp("datalake", "describe-datalake", "--datalake-name", E["FEDERAL_DATALAKE"])["datalake"]
    return d["status"] == "RUNNING", f"{d['datalakeName']} {d['status']} runtime {d.get('productVersions', [{}])[0].get('version', d.get('runtime', '?')) if d.get('productVersions') else d.get('runtime', '?')}"


def datahubs():
    names = {E[k] for k in ("FEDERAL_DATAHUB_KAFKA", "FEDERAL_DATAHUB_NIFI", "FEDERAL_DATAHUB_FLINK")}
    hubs = cdp("datahub", "list-clusters", "--environment-name", E["FEDERAL_ENV_NAME"])["clusters"]
    got = {c["clusterName"]: c["status"] for c in hubs if c["clusterName"] in names}
    return all(v == "AVAILABLE" for v in got.values()) and len(got) == len(names), ", ".join(f"{k} {v}" for k, v in sorted(got.items()))


def cdw():
    vws = cdp("dw", "list-vws", "--cluster-id", E["FEDERAL_CDW_CLUSTER_ID"])["vws"]
    return all(v["status"] == "Running" for v in vws), ", ".join(f"{v['name']} {v['status']}" for v in vws)


def cai_workspace():
    ws = [w for w in cdp("ml", "list-workspaces")["workspaces"] if w["instanceName"] == E["FEDERAL_CAI_WORKSPACE"]]
    return bool(ws) and ws[0]["instanceStatus"] in ("installation:finished", "modify:finished",
                                                    "upgrade:finished", "resume:finished"), \
        f"{E['FEDERAL_CAI_WORKSPACE']} {ws[0]['instanceStatus'] if ws else 'not found'}"


def cai_api():
    if not E.get("FEDERAL_CAI_API_KEY"):
        return False, "FEDERAL_CAI_API_KEY empty"
    req = urllib.request.Request(E["FEDERAL_CAI_HOST"].rstrip("/") + "/api/v2/projects?page_size=1",
                                 headers={"Authorization": f"Bearer {E['FEDERAL_CAI_API_KEY']}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status == 200, f"API v2 HTTP {r.status}"


def cde():
    vcs = cdp("de", "list-vcs", "--cluster-id", E["FEDERAL_CDE_CLUSTER_ID"])["vcs"]
    vc = [v for v in vcs if v["vcName"] == E["FEDERAL_CDE_VC"]]
    return bool(vc) and vc[0]["status"] == "AppInstalled", f"{E['FEDERAL_CDE_VC']} {vc[0]['status'] if vc else 'not found'}"


def impala(table: str | None):
    def run():
        from impala.dbapi import connect  # impyla: use a project venv that has it
        conn = connect(host=E["FEDERAL_IMPALA_HOST"], port=int(E["FEDERAL_IMPALA_PORT"]), use_ssl=True,
                       use_http_transport=True, http_path=E["FEDERAL_IMPALA_HTTP_PATH"],
                       auth_mechanism=E["FEDERAL_IMPALA_AUTH"], user=E["FEDERAL_WORKLOAD_USER"],
                       password=E["FEDERAL_WORKLOAD_PASSWORD"])
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchall()
        if not table:
            return True, "SELECT 1 (add --impala-table to test the Metastore path)"
        if not re.fullmatch(r"[A-Za-z0-9_]+\.[A-Za-z0-9_]+", table):
            return False, "table must be db.table"
        try:
            cur.execute(f"DESCRIBE {table}")
            return True, f"SELECT 1 and DESCRIBE {table} ({len(cur.fetchall())} columns)"
        except Exception as e:
            stale = "Failure to initialize security context" in str(e)
            return False, ("Metastore Kerberos login of the VW is stale (Failure to initialize security context)"
                           if stale else str(e).splitlines()[0][:200])
    return run


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--impala-table", default=None)
    args = p.parse_args()
    for name, fn in (("environment", env_status), ("data lake", datalake), ("data hubs", datahubs),
                     ("cdw", cdw), ("cai workspace", cai_workspace), ("cai api", cai_api), ("cde", cde),
                     ("impala", impala(args.impala_table))):
        check(name, fn)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
