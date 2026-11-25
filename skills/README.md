# Skills

Source of truth for the Cursor skills behind this repo. Copy each folder to your personal skills store
(`skills/<name>/`) or `~/.cursor/skills/<name>/` on a laptop so agents outside this repo find them too.

| Skill | Purpose |
|---|---|
| `federal-cdp-access/` | How to reach the federal environment (to be added from `~/.cursor/skills/federal-cdp-access/`) |
| `cloudera-platform-upgrade/` | Resize and upgrade of the shared services with `fedops` |

Adding `federal-cdp-access`: copy the folder as is, then remove any literal key, password or token from it and
refer to the variable names in `federal.env.example` instead. The pre-commit hook refuses CDP keys and private
keys, but not every kind of secret.

`federal.env` itself does **not** go into this repo: keep it at `~/.config/federal-cdp/federal.env` and add the
same names as Cursor secrets for cloud agents.
