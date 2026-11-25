---
name: federal-cdp-access
description: >-
  Accesses the shared federal CDP environment (federal-cdp-env, AWS ap-south-1) for admin work,
  CLI and API calls, health checks and upgrades: Data Lake federal-aw-dl, CDW (Impala, Hive, Trino,
  Data Visualization), CAI workspace federal-cml-ws, CDE federal-cde, and the Kafka, NiFi and Flink
  Data Hubs. Loads endpoints and credentials from ~/.config/federal-cdp/federal.env. Use when any
  project needs the federal environment, the cdp or cde CLI, the CAI API v2, Impala, Kafka or Knox,
  or when the user mentions the federal cluster, an upgrade, a restart or a status check.
---

# Federal CDP environment access

## Load the environment

```bash
set -a; source ~/.config/federal-cdp/federal.env; set +a
```

- Every federal endpoint, id and CRN is in that file as `FEDERAL_*`. Read the names you need from it; do not guess hosts.
- Secrets in it: `FEDERAL_WORKLOAD_PASSWORD`, `FEDERAL_CAI_API_KEY`. The CDP access key stays in `~/.cdp/credentials` and the CDE password file in `~/.cde/`; they are not copied there.
- Never print, echo, log, commit or paste a value of a `*_PASSWORD`, `*_KEY` or `*_TOKEN` variable. Print names, lengths or "set / empty". Pass secrets through environment variables, files or stdin, never as command-line arguments in output you show.
- A project's own `.env` (`SPEND_*`, `EVX_*`, `OGX_*`, ...) holds the same values under its prefix. Inside a project, its `.env` and its `scripts/platform_ctl.py` come first; this file is for admin work and for projects without one.
- Template with placeholders: [federal.env.example](federal.env.example). If the real file is missing, copy the template to `~/.config/federal-cdp/federal.env`, `chmod 600`, and ask the user for the secrets.

## Check before and after any change

```bash
<python with impyla> ~/.cursor/skills/federal-cdp-access/scripts/federal_check.py [--impala-table db.table]
```

Read-only. Checks the environment, Data Lake, Data Hubs, CDW virtual warehouses, CAI workspace and API v2 key, CDE virtual cluster and Impala (`SELECT 1`; with `--impala-table`, a `DESCRIBE` that goes through the Hive Metastore). Use a project venv that has impyla (for example `~/Downloads/py_aws/Spend-Analytics/.venv/bin/python`). Run it first, and again after the last change.

## Scope: what the agent may touch

The CDP account holds many environments (pse-emea, psedemo1, ptner-sndbox, caws160, ...). Work only on `FEDERAL_ENV_NAME`; pass `--environment-name`, `--cluster-id` or a CRN from the file on every call, and never act on a resource whose name or CRN is not federal.

| Action | Rule |
|---|---|
| describe, list, status, logs, `SELECT` | Allowed |
| Start or stop a project's own workloads (its CAI apps, models, jobs, CDE jobs and schedules) | Allowed, through the project's `scripts/platform_ctl.py` when it has one |
| Start, stop, suspend or restart a shared service: Data Lake, a Data Hub, a CDW VW or DBC, Data Visualization, the CAI workspace, the CDE service or virtual cluster | Only when the user names that service and the action in this conversation. Sibling projects use them |
| Upgrade, resize, scale, delete, change a quota, rotate a key, change a security setting | Only with the user's explicit approval for that exact change, after a dry run or describe (below) |
| Runs, jobs or tables whose name is not the current project's prefix | Never stop, kill or change them |

## CLIs and APIs

| Service | How |
|---|---|
| Control plane | `cdp` (`FEDERAL_CDP_CLI`, profile `FEDERAL_CDP_PROFILE`): `environments`, `datalake`, `datahub`, `dw`, `ml`, `de` |
| CDE jobs | `cde` (reads `~/.cde/config.yaml`, vcluster `FEDERAL_CDE_VCLUSTER_ENDPOINT`). Python output of a run: `cde run logs --id N --download-all`, then `driver_stdout.log` |
| CAI | API v2: `$FEDERAL_CAI_HOST/api/v2/...`, header `Authorization: Bearer $FEDERAL_CAI_API_KEY` |
| Impala | impyla: host `FEDERAL_IMPALA_HOST`, port 443, `use_ssl`, `use_http_transport`, `http_path=cliservice`, `auth_mechanism=LDAP`, the workload user. Not Kerberos from the client |
| Kafka | `FEDERAL_KAFKA_BOOTSTRAP`, SASL_SSL / PLAIN, the workload user, CA `FEDERAL_CA_PEM`; Schema Registry and SMM through Knox (`FEDERAL_SCHEMA_REGISTRY_URL`, `FEDERAL_SMM_API_URL`) |
| IDBroker (S3 credentials outside Spark) | GET a Knox token from `FEDERAL_IDBROKER_TOKEN_URL` with basic auth, then `FEDERAL_IDBROKER_CAB_URL` with `Authorization: Bearer`; `aws-cab` rejects basic auth (HTTP 401) |

`cdp <service> help` and `cdp <service> <command> help` give the exact flags; check them before a call you have not made before.

## Upgrades and other admin changes

1. Run `federal_check.py` and record the versions (`cdp datalake describe-datalake`, `cdp datahub describe-cluster`, `cdp dw describe-vw`, `cdp ml describe-workspace`, `cdp de describe-service`).
2. Find the upgrade command and its options with `cdp <service> help`. Use its dry-run or check mode (for example `--dry-run`, or a `prepare` / `check` command) where it has one, and show the user the result: target version, downtime, what restarts, and which sibling projects depend on it.
3. Ask for approval of that exact change. Then run it once and poll the describe command until it settles. Do not retry a failed upgrade on your own; read the status reason and report it.
4. Order for a runtime upgrade: Data Lake first, then the Data Hubs, then CDW, CAI and CDE. Each one is shared.
5. Run `federal_check.py` again and report before / after.

## Known issues

- **Impala: "Failure to initialize security context" / "Could not connect to meta store".** The VW `federal-impala-1`'s own Kerberos login to the Data Lake Hive Metastore goes stale. `SELECT 1` and cached tables still work; any table whose metadata must load fails. Not a client problem: every project and CAI see it. Fix (shared, ask first): `cdp dw` suspend then start of `FEDERAL_IMPALA_VW_ID` on `FEDERAL_CDW_CLUSTER_ID`, then `INVALIDATE METADATA` only on the failing tables of the current project. It has come back within hours; report it for a lasting fix.
- **CAI model or app restart returns HTTP 500 "restartModelNotFound" or 404.** The workbench lost the deployment. Create a new deployment of the same build with the old CPU / memory / replicas; for an app, a second `:restart` usually succeeds.
- **CDE run stuck in "starting".** The shared virtual cluster has no room. Headroom is the quota minus the requests of running and starting runs; do not raise the quota or kill other projects' runs.
- **CAI job stuck in "scheduling", then ENGINE_FAILED after 60 min.** The per-user quota is full (every project runs as the same user). Stop unused apps and models of the current project.

## Record

In a project, append what changed to its `docs/PROJECT_LOG.md`: run ids, versions, the approval, no secret values. Commit without `--trailer` or attribution lines.
