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
