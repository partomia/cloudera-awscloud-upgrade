# Operations log

Newest last. Times in IST. No secret values.

## 2026-11-25 10:45 IST - Tooling written in the EV demo repo

- `scripts/platform_upgrade.py` in EV-Factory-to-Field-Lakehouse (PR #1): resize and upgrade of the shared services.
  Nothing applied: the agent VM had no CDP access key.

## 2026-11-25 12:30 IST - This repository

- Moved the shared-service work here: `fedops.ctl` (status / stop / start of Data Hubs, Impala VW, CDE VC, CAI
  workspace, ported from the demo's `--scope platform`) and `fedops.upgrade` (status / resize / upgrade).
- Targets: Data Lake build `81274879`; CDE VC 48 CPU / 192 GiB; CDE service max instances scaled to match; Impala
  autoscale max 10. Baseline 20 CPU / 80 GiB and max 5 from the demo's config of 2026-11-20, not yet read live.
- Pending: credentials as Cursor secrets, the `federal-cdp-access` skill, the first live `status`.

## 2026-11-25 12:45 IST - First live status (read-only, from the laptop)

- Environment `federal-cdp-env` AVAILABLE. Data Lake `federal-aw-dl` RUNNING, LIGHT_DUTY, Runtime
  `7.3.2-1.cdh7.3.2.p100.81274879`, CM 7.13.2.100, RHEL 9: **already on build 81274879**.
  Candidates: 83281140 (7.3.2, CM 7.13.2.20000), 84928234 (7.3.3, CM 7.13.3.0). The lake reports that the Kafka,
  NiFi and Flink Data Hubs must be stopped before an upgrade.
- Data Hubs, CDE VC, Impala VW running; CAI workspace `modify:finished`.
- CDE service `federal-cde` 1.26.1-h1-b15, r5.4xlarge x 0..50, upgrade available (next step prepare).
  VC `federal-cde-vc` quota 20 CPU / 80 GiB, in use 27 CPU / 103 GiB.
- CDW `federal-impala-1` 2025.0.21.3-3, autoscale 1..5; VW and DBC upgrade to 2026.0.21.4-12 offered.
- Fixed from this output: CDE node ceiling is now computed from the instance type (50 x r5.4xlarge already holds
  48 CPU / 192 GiB: no change); the CDW version comes from `cdhVersion`; a "stop the Data Hubs" answer from the
  Data Lake no longer stops the plan; `FEDERAL_CDP_CLI` with `~` and `FEDERAL_CDP_PROFILE` are honoured.

## 2026-11-25 15:20-16:20 IST - Full stop, then resize (from the laptop)

- EV demo project stop (`platform_ctl.py stop`): two CAI applications and model `evx-uc01-service` stopped, NiFi
  group `EVX - Alert Router` stopped, schedule `rsingh-evx-orchestration` paused, stream runs #1250-#1255 killed
  (they resume from their checkpoints on start).
- `fedops.ctl stop --yes-shared`, 48 min: CAI workspace suspended (24.5 min), NiFi, CDE VC, Impala VW, Flink and
  Kafka stopped. Data Lake and FreeIPA left running.
- `fedops.upgrade resize --yes-shared`: Impala `federal-impala-1` autoscale max 5 -> 10, read back. The update
  starts the VW; suspended it again (`ctl stop --only cdw`). CDE service max instances 50 x r5.4xlarge: no change.
- CDE VC quota still 20 CPU / 80 GiB: `cdp de update-vc` has no quota field (checked on cdpcli 0.9.165), UI step
  pending.

## 2026-11-25 16:30-17:10 IST - CDE upgrade, CDW upgrade failures

- CDE VC quota set in the UI to 100 CPU / 300 GiB (above target), read back. CDE prepare and backup run from the UI;
  `upgrade-service --step upgrade` from the laptop at 16:53, in progress (`Maintenance_ClusterUpgradeInProgress`).
- CDW, from the UI: Impala `federal-impala-1` and Trino `federal-trino-1` upgrade to 2026.0.21.4-12 at 16:36, both
  Error; Trino upgrade retried, Impala rebuild at 16:44. Both still 2025.0.21.3-3, 0 pods.
- Database Catalog `federal-aw-dl-default` had not been upgraded first; `dw upgrade-dbc` to 2026.0.21.4-12 at 16:57
  failed the same way: events stop at "deleting namespace", status Error. Hive `federal-hive-1` still Running.
- Common point: every upgrade hangs deleting its Kubernetes namespace on EKS `env-jjwgzn-dwx-stack-eks` (CDW
  cluster 1.12.5-b291). `dw get-logs` is private-cloud only; kubectl needs valid AWS credentials (laptop's invalid).
  No further CDW change until the namespace cause is known.

## 2026-11-25 20:40 IST - CDE upgrade completed

- Upgrade step finished after 2 h 18 min: CDE `federal-cde` 1.26.1-h1-b15 -> 1.26.2-b291, then held in
  `Maintenance_ClusterUpgradeCompleted` (VC `AppPaused`) until `upgrade-service --step resume`. Resume at 20:39:
  service `ClusterCreationCompleted`, VC `federal-cde-vc` `AppInstalled` (running), all steps completed.
- `fedops.upgrade` now runs the resume step too.

## 2026-11-25 20:44 IST - Database Catalog upgrade retried from the UI

- `federal-aw-dl-default` Deleting for 5.5 min, then Error; no new DBC event since 16:57 ("deleting namespace"):
  the namespace from the 16:57 attempt is still terminating. Retries will fail until it is cleared on EKS.
- Laptop AWS profiles `default` and `981304421142_cldr_poweruser` return InvalidClientTokenId (expired keys).

## 2026-11-26 10:36-11:21 IST - CDW rebuilt on 2026.0.21.4-12

- Database Catalog namespace finally deleted 10:36; catalog Running 10:39 (upgraded from the UI).
- From the UI: Impala, Trino and Hive VWs deleted; Impala recreated as `impala-1795670345-2pbx`, 2026.0.21.4-12,
  autoscale 5..10 groups, HA active-passive, 50 x r5d.4xlarge while awake.
- From the laptop (`dw create-vw`), r5d.4xlarge, ap-south-1a, xsmall (2 executors), auto-suspend 300 s, CDP JWT,
  LDAP groups `federal-aw-cdp-admin-group`, `federal-aw-cdp-user-group`:
  - Hive `federal-hive-1` = `compute-1795671915-kvqz`, 2026.0.21.4-12, autoscale 1..10. Running 11:20.
  - Trino `federal-trino-1` = `trino-1795671924-kqnz`, 2026.0.24.0-37 (2026.0.21.4-12 is not offered for Trino).
    Connectors `hive` and `iceberg` attached by default. Running 11:21.
- The API does not return a VW's LDAP groups; check them in the UI.
