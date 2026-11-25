# References and CLI facts

## Cloudera documentation

- Upgrade advisor (Data Lake): https://docs.cloudera.com/cdp-public-cloud/cloud/cdp-upgrade-advisor/topics/mc-data-lake-upgrade-advisor.html
- Data Lake backups: https://docs.cloudera.com/management-console/cloud/data-lakes/topics/mc-data-lake-dr-configure-backups-for-data-lake.html
- Data Lake / Data Hub database upgrade: https://docs.cloudera.com/management-console/cloud/data-lakes/topics/mc-upgrading-database.html
- PDF exports used (not committed): `cdp-pc-upgrade-advisor.pdf`, `mc-data-lakes.pdf`, `cdp-pc-cli.pdf`, `cdp-pc-api-cdp-public.pdf`.

## From the docs

- Order: FreeIPA (optional, separate, before) → Data Lake → Data Hubs (only if required) → data services (CDE, CDW, CAI, DataFlow).
- Data Hubs on Runtime 7.2.16+ work against a newer Data Lake; their upgrade can wait.
- Runtime 7.3.1 needs PostgreSQL 14 on the Data Lake and Data Hub databases first (`start-database-upgrade`, `VERSION_14`).
- Runtime 7.3.1: no Spark 2, Zeppelin removed, CDE 1.23 and older unsupported, OpenJDK 11 clusters cannot upgrade.
- Runtime 7.3.2: JDK 17, RHEL 9.6; no NiFi 1 Flow Management; no KRaft-tech-preview Kafka upgrade.
- Rolling Data Lake upgrade: source 7.2.17.300+, RHEL 8, Enterprise shape only. Otherwise attached Data Hubs and data services must be stopped.
- Medium Duty Data Lakes cannot go to 7.2.18+ without a resize first.
- The built-in pre-upgrade backup can be skipped with `--skip-backup`; we take an explicit `backup-datalake` instead.
- Upgrade recovery (`recover-datalake`) is removed since 2025-11-19: support case instead.

## From the CLI model (cdpcli 0.9.165)

- Runtime string `7.2.17-1.cdh7.2.17.p200.46967063`: version 7.2.17, service pack 200, build (GBN) 46967063.
  Upgrade candidates expose it as `componentVersions.cdpGBN`.
- `datalake upgrade-datalake`: `--image-id | --runtime | --lock-components`, `--dry-run`, `--show-available-images`,
  `--skip-backup`, `--rolling-upgrade-enabled`. Track with `datalake get-operation --datalake-name [--operation-id]`.
- `datalake prepare-datalake-upgrade --datalake <name> --image-id <id>`.
- `datalake backup-datalake --datalake-name --backup-name`, status `backup-datalake-status --backup-id`.
- `de update-vc` takes ACLs, Spark configs and compute override only: **no CPU/memory quota**. Quota is set at
  `create-vc` (`--cpu-requests`, `--memory-requests`) or in the UI.
- `de update-service`: `--minimum-instances`, `--maximum-instances` (+ spot and all-purpose variants).
- `de upgrade-service --step prepare|backup|upgrade|cancel|resume`; `de get-upgrade-status` → `nextStep`, `allStepsCompleted`.
- `dw update-vw --autoscaling maxClusters=N` (also `tShirtSize`, `nodeCount`, `queryIsolationOptions`, `additionalQuota`).
- `dw get-upgrade-dbc-versions` / `get-upgrade-vw-versions` → `latestVersion`, `compatibleVersion` and their CDP versions;
  `dw upgrade-dbc --image-version`, `dw upgrade-vw --dbc-id --image-version`.
- Region and endpoint are not environment variables in cdpcli: `--cdp-region` / `--endpoint-url` (fedops passes
  `CDP_REGION` / `CDP_ENDPOINT_URL`) or `~/.cdp/config`.
