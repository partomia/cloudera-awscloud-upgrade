# cloudera-awscloud-upgrade

Operations on the shared services of the Cloudera on cloud (AWS) **federal** environment `federal-cdp-env`:
start/stop of the shared layers, capacity changes, and upgrades of the Data Lake, CDE and CDW. Every demo on
the environment (see `config/projects.json`) uses these services, so changes here are planned and logged.

**Status (2026-11-25 12:45 IST):** first live status read. Data Lake already on Runtime 7.3.2 build `81274879`
(7.3.2 build 83281140 and 7.3.3 offered); CDE 1.26.1 and CDW 2025.0.21.3-3 have upgrades on offer. CDE VC
20 CPU / 80 GiB (27 / 103 in use), Impala autoscale 1..5. No change applied yet.

| Task | Command |
|---|---|
| Setup | `./scripts/setup.sh` (`.venv` with pinned `cdpcli`, hooks on) |
| State of everything | `.venv/bin/python -m fedops.ctl status` and `.venv/bin/python -m fedops.upgrade status` |
| Stop / start shared services | `python -m fedops.ctl stop --dry-run`, then `--yes-shared` |
| Raise CDE / CDW capacity | `python -m fedops.upgrade resize --dry-run`, then `--yes-shared` |
| Upgrade | `python -m fedops.upgrade upgrade --dry-run`, then `--yes-shared --projects-stopped` |
| Tests (no network) | `.venv/bin/python -m pytest -q` |

## Credentials

Never committed (`.gitignore` and `.githooks/pre-commit` refuse them). `fedops` reads, in order:

1. variables already in the environment: Cursor cloud agents get them from **Dashboard > Cloud Agents > Secrets**;
2. the first env file found: `$FEDERAL_ENV_FILE`, `~/.config/federal-cdp/federal.env`, `./federal.env`;
3. `~/.cdp/credentials` (the CDP CLI's own file).

Names are in `federal.env.example`. `CDP_REGION` / `CDP_ENDPOINT_URL` are passed to every `cdp` call when set.

## Layout

```text
config/       environment.json (service names, stop/start order), capacity.json, upgrade.json, projects.json
fedops/       common.py (config, credentials, cdp wrapper), ctl.py (status/stop/start), upgrade.py (resize/upgrade)
docs/         UPGRADE_RUNBOOK.md, REFERENCES.md (doc links + CLI facts), OPERATIONS_LOG.md
skills/       Cursor skills for this work; copy each folder to your personal skills store
tests/        fake-cdp tests
```

## Rules of the road

- `status` first and last, `--dry-run` before every change, `--yes-shared` only for services the requester named.
- Stop each demo's project workloads (its own repo) before a shared stop or upgrade; start them after.
- Log every live change in `docs/OPERATIONS_LOG.md` (IST) and sizes in `config/capacity.json` `changes`.
