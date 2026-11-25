"""
Status, stop or start the shared services of the federal environment, in dependency order.

Layers (config/environment.json): Data Hubs kafka / nifi / flink, CDW virtual warehouses (cdw),
the CDE virtual cluster (cde) and the CAI workspace (cai). Stop runs stop_order (consumers first),
start runs start_order. Every demo on the environment uses these services: stop and start need
--yes-shared, and each demo's project workloads should be stopped first (config/projects.json).
The Data Lake and FreeIPA are never stopped here; status shows them.

  python -m fedops.ctl status
  python -m fedops.ctl stop --dry-run
  python -m fedops.ctl stop --yes-shared [--only cde,cdw]
  python -m fedops.ctl start --yes-shared
"""
from __future__ import annotations

import argparse
import sys

from fedops import common as c
from fedops.common import ENV, act, cdp, say, wait

LAYERS = ("kafka", "flink", "cdw", "cde", "nifi", "cai")


def datalake_status() -> None:
    env = cdp("environments", "describe-environment", "--environment-name", ENV["environment"])["environment"]
    say(f"  environment {ENV['environment']}: {env.get('status')}")
    for dl in cdp("datalake", "list-datalakes", "--environment-name", ENV["environment"])["datalakes"]:
        d = cdp("datalake", "describe-datalake", "--datalake-name", dl["datalakeName"])["datalake"]
        cm = (d.get("clouderaManager") or {}).get("version", "?")
        runtime = next((p["version"] for p in d.get("productVersions") or [] if p.get("name") == "CDH"), "?")
        say(f"  Data Lake {d['datalakeName']}: {d['status']}, shape {d.get('shape')}, Runtime {runtime}, CM {cm}")


def datahub(layer: str, action: str) -> None:
    name = ENV["datahubs"].get(layer)
    if not name:
        return
    status = lambda: cdp("datahub", "describe-cluster", "--cluster-name", name)["cluster"]["status"]  # noqa: E731
    st = status()
    if action == "status":
        say(f"  Data Hub {name}: {st}")
    elif action == "stop" and st != "STOPPED":
        act(f"stop Data Hub {name}", cdp, "datahub", "stop-cluster", "--cluster-name", name)
        wait(name, status, {"STOPPED"}, timeout=2400, poll=20)
    elif action == "start" and st != "AVAILABLE":
        act(f"start Data Hub {name}", cdp, "datahub", "start-cluster", "--cluster-name", name)
        wait(name, status, {"AVAILABLE"}, timeout=3600, poll=20)


def cdw_cluster_id() -> str:
    crn = c.env_crn()
    return next(x["id"] for x in cdp("dw", "list-clusters")["clusters"] if x["environmentCrn"] == crn)


def cdw(action: str) -> None:
    cid = cdw_cluster_id()
    vws = {v["name"]: v for v in cdp("dw", "list-vws", "--cluster-id", cid)["vws"]}
    for name in ENV["cdw_vws"]:
        vw = vws[name]
        status = lambda v=vw: cdp("dw", "describe-vw", "--cluster-id", cid, "--vw-id", v["id"])["vw"]["status"]  # noqa: E731
        if action == "status":
            say(f"  CDW virtual warehouse {name}: {vw['status']}")
        elif action == "stop" and vw["status"].lower() not in ("stopped", "suspended"):
            act(f"suspend CDW virtual warehouse {name}", cdp, "dw", "suspend-vw", "--cluster-id", cid, "--vw-id", vw["id"])
            wait(name, status, {"Stopped", "Suspended"}, bad=("ERROR",), timeout=2400, poll=20)
        elif action == "start" and vw["status"].lower() != "running":
            act(f"start CDW virtual warehouse {name}", cdp, "dw", "start-vw", "--cluster-id", cid, "--vw-id", vw["id"])
            wait(name, status, {"Running"}, bad=("ERROR",), timeout=2400, poll=20)


def cde_ids() -> tuple[str, str, str]:
    svc = next(s for s in cdp("de", "list-services")["services"]
               if s["name"] == ENV["cde_service"] and "delet" not in s["status"].lower())
    vc = next(v for v in cdp("de", "list-vcs", "--cluster-id", svc["clusterId"])["vcs"] if v["vcName"] == ENV["cde_vc"])
    return svc["clusterId"], vc["vcId"], vc["status"]


def cde(action: str) -> None:
    cid, vcid, st = cde_ids()
    ids = ("--cluster-id", cid, "--vc-id", vcid)
    status = lambda: cdp("de", "describe-vc", *ids)["vc"]["status"]  # noqa: E731
    if action == "status":
        say(f"  CDE virtual cluster {ENV['cde_vc']}: {st}")
    elif action == "stop" and "suspend" not in st.lower():
        act(f"suspend CDE virtual cluster {ENV['cde_vc']}", cdp, "de", "suspend-vc", *ids)
        wait(ENV["cde_vc"], status, {"AppSuspended", "Suspended"}, bad=("FAIL",), timeout=2400, poll=20)
    elif action == "start" and "suspend" in st.lower():
        act(f"resume CDE virtual cluster {ENV['cde_vc']}", cdp, "de", "resume-vc", *ids)
        wait(ENV["cde_vc"], status, {"AppInstalled", "Running"}, bad=("FAIL",), timeout=2400, poll=20)


def cai(action: str) -> None:
    def ws():
        return next(w for w in cdp("ml", "list-workspaces")["workspaces"]
                    if w["instanceName"] == ENV["cai_workspace"] and w["environmentName"] == ENV["environment"])
    w = ws()
    st = w["instanceStatus"]
    if action == "status":
        say(f"  CAI workspace {ENV['cai_workspace']}: {st}")
    elif action == "stop" and "suspend" not in st:
        act(f"suspend CAI workspace {ENV['cai_workspace']}", cdp, "ml", "suspend-workspace", "--workspace-crn", w["crn"])
        wait(ENV["cai_workspace"], lambda: ws()["instanceStatus"], {"suspend:finished"}, bad=("FAIL",), timeout=3600)
    elif action == "start" and "suspend" in st:
        act(f"resume CAI workspace {ENV['cai_workspace']}", cdp, "ml", "resume-workspace", "--workspace-crn", w["crn"])
        wait(ENV["cai_workspace"], lambda: ws()["instanceStatus"], {"resume:finished", "installation:finished"},
             bad=("FAIL",), timeout=3600)


SHARED = {"kafka": lambda a: datahub("kafka", a), "flink": lambda a: datahub("flink", a),
          "nifi": lambda a: datahub("nifi", a), "cdw": cdw, "cde": cde, "cai": cai}


def project_reminder(action: str) -> None:
    key = "stop" if action == "stop" else "start"
    say(f"project workloads to {key} {'before' if action == 'stop' else 'after'} this (config/projects.json):")
    for p in c.PROJECTS:
        say(f"  {p['name']}: {p[key]}   ({p['repo']})")


def run(action: str, only: set) -> None:
    if action == "status":
        say("[datalake]")
        try:
            datalake_status()
        except Exception as e:  # noqa: BLE001
            say(f"  ERROR {type(e).__name__}: {e}")
    order = ENV["start_order"] if action == "start" else ENV["stop_order"]
    for name in order:
        if only and name not in only:
            continue
        say(f"[{name}]")
        try:
            SHARED[name](action)
        except Exception as e:  # noqa: BLE001  one layer's failure is reported; status still prints the others
            say(f"  ERROR {type(e).__name__}: {e}")
            if action != "status":
                raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["status", "stop", "start"])
    ap.add_argument("--only", default="", help=f"comma-separated layers from {', '.join(LAYERS)}")
    ap.add_argument("--yes-shared", action="store_true", help="required to stop or start: sibling demos use these")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    c.DRY = a.dry_run
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    if only - set(LAYERS):
        raise SystemExit(f"unknown layers {sorted(only - set(LAYERS))}")
    if a.action != "status" and not (a.yes_shared or a.dry_run):
        raise SystemExit(f"{a.action} touches services every demo shares: add --yes-shared (or --dry-run)")
    if a.action != "status":
        project_reminder(a.action)
    run(a.action, only)
    return 0


if __name__ == "__main__":
    c.require_credentials()
    sys.exit(main())
