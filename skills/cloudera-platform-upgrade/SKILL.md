---
name: cloudera-platform-upgrade
description: >-
  Resizes and upgrades the shared Cloudera on cloud services of the federal
  environment with the cloudera-awscloud-upgrade repo (fedops): CDE virtual
  cluster quota and service nodes, CDW Impala autoscaling, Data Lake Runtime
  upgrade to a given build (backup, validate and prepare, PostgreSQL 14), CDE
  service and CDW DBC/VW upgrades, shared start/stop. Use when asked to
  increase CDE/CDW resources, upgrade the Data Lake or data services, act on an
  "upgrade available" banner, or stop/start the shared services.
---

# Platform resize and upgrade

Repo: https://github.com/partomia/cloudera-awscloud-upgrade. Work from its root with `.venv/bin/python` (`./scripts/setup.sh` first; a fresh Ubuntu VM needs `python3.12-venv`). Targets: `config/capacity.json`, `config/upgrade.json`. Runbook: `docs/UPGRADE_RUNBOOK.md`. CLI facts: `docs/REFERENCES.md`.

Every change hits services all demos share. Act only on what the user named in this conversation; `--yes-shared` only then.

## Before anything

1. Credentials per the `federal-cdp-access` skill: `CDP_ACCESS_KEY_ID` + `CDP_PRIVATE_KEY` from Cursor secrets or `~/.config/federal-cdp/federal.env` (loaded automatically). Missing: stop and ask the user to add them as secrets. Never print them.
2. `python -m fedops.ctl status` and `python -m fedops.upgrade status`. Show the user; note versions and sizes for the log.

## Resize (no downtime)

`python -m fedops.upgrade resize --dry-run`, then `--yes-shared`.

- Impala: `dw update-vw --autoscaling maxClusters=N`, read back.
- CDE service: `de update-service --maximum-instances N`; with `cde_service_max_instances: null` the current max is scaled by the larger of the CPU and memory quota increase.
- CDE VC quota: no CLI/API field. The command prints the UI step (Data Engineering > VC > Edit > Capacity) and exits non-zero until the quota reads back. Hand the UI step to the user unless you have a browser session they signed in.
- Raise only. Record in `config/capacity.json` `changes`.

## Upgrade (downtime)

1. `python -m fedops.upgrade upgrade --dry-run [--build <GBN>]`. The build is the last field of `7.3.1-1.cdh7.3.1.p500.<GBN>`, matched on `componentVersions.cdpGBN`. Not offered: stop, show the offered list, ask.
2. Each demo in `config/projects.json` runs its own project stop (its repo, its rules).
3. `python -m fedops.upgrade upgrade --yes-shared --projects-stopped`: checks (PostgreSQL 14 when the dry run asks; CDE ≥ 1.24 for Runtime 7.3) → validate and prepare → shared stop → Data Lake backup + upgrade (`--skip-backup`, the explicit backup replaces the built-in one) → CDE prepare/backup/upgrade → CDW DBC then VW → shared start → status.
4. Each demo runs its own project start; for the EV demo the producer and nightly DAG stay off unless asked.

Never `cdp environments stop-environment` for this: a stopped Data Lake cannot be upgraded. A failure: fix the cause, rerun the same command (steps read state first). Data Lake has no rollback and upgrade recovery is gone (Nov 2025): Event History + Cloudera support; the backup is the restore point.

## Record

`docs/OPERATIONS_LOG.md` (IST): versions before/after, backup name, sizes before/after, manual steps. README status line. One commit per logical change, hooks on (`.githooks`), no secrets.
