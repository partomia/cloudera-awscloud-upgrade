# Upgrade and resize runbook

All commands from the repo root with `.venv/bin/python`. Read `status` before the first change and after the last.

## 0. Before the window

1. `python -m fedops.ctl status` and `python -m fedops.upgrade status`. Note, for the log: Data Lake Runtime and
   build, CDE version, CDW DBC/VW image, CDE VC quota, Impala autoscale max.
2. The target build must be listed as a Data Lake candidate (`<- target`). If not, the image is not offered for this
   lake (OS, shape, or catalog): stop and check the offered list.
3. CDE 1.23 and older does not support Runtime 7.3.x. `upgrade` refuses until `upgrade --only cde` has run.
4. Free disk: 27 GB on the Cloudera Manager node, 20 GB on every other Data Lake node; the backup dumps the database
   to `/var/tmp` on the backup node first.
5. Backup roles: `DATALAKE_ADMIN_ROLE` and `RANGER_AUDIT_ROLE` can write to the backup location
   (`LOG_ROLE` too, for a restore).
6. `python -m fedops.upgrade upgrade --dry-run` and read the plan.

## 1. Upgrade (downtime)

1. Each demo in `config/projects.json` runs its own project stop (for the EV demo: `python scripts/platform_ctl.py stop`
   in its repo). Streams stop at a checkpoint and resume after.
2. `python -m fedops.upgrade upgrade --yes-shared --projects-stopped`. It runs:
   1. Data Lake checks; PostgreSQL 14 database upgrade if the dry run asks for it;
   2. validate and prepare (no downtime, parcels downloaded);
   3. shared stop: CAI workspace, NiFi, CDE VC, Impala VW, Flink, Kafka;
   4. Data Lake backup `pre-upgrade-<build>-<UTC stamp>`, then upgrade with `--skip-backup`;
   5. CDE: VC resumed, `upgrade-service` prepare → backup → upgrade;
   6. CDW: Database Catalog, then the VW (started first);
   7. shared start in reverse order, then `status`.
3. Each demo runs its own project start. For the EV demo, the producer and nightly DAG stay off unless asked.

Duration is dominated by the Data Lake backup and upgrade; follow progress in the Management Console Event History.

## 2. Resize (no downtime)

1. `python -m fedops.upgrade resize --dry-run`.
2. `python -m fedops.upgrade resize --yes-shared`: Impala autoscale max via `dw update-vw`; CDE service max instances
   via `de update-service`.
3. The CDE VC quota has no public CLI field. In the Data Engineering UI: `federal-cde-vc` > Edit > Capacity, CPU and
   memory to the targets in `config/capacity.json`, save. Rerun `resize --yes-shared`; it exits 0 only when the quota
   reads back.
4. Mark the entry in `config/capacity.json` `changes` as applied, with the date.

## 3. When something fails

- Rerun the same command after fixing the cause: every step reads state first.
- Data Lake: no rollback, and upgrade recovery was removed in November 2025. Collect the Event History, open a
  Cloudera support case. The step-4 backup is the restore point (`cdp datalake restore-datalake --backup-id`).
- Versions shown wrong after manual parcel fixes: `cdp datalake sync-component-versions-from-cm --datalake-name <dl>`.
- CDE: `cdp de get-upgrade-status --cluster-id <id>`; `upgrade-service --step cancel|resume`.
- CDW: VW events with `cdp dw list-vw-events`.
