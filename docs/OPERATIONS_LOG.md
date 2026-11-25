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
