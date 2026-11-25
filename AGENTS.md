# Agent notes

- Setup: `./scripts/setup.sh`. On a fresh Ubuntu VM install `python3-venv` first (`sudo apt-get update && sudo apt-get install -y python3.12-venv`). Use `.venv/bin/python`.
- Credentials: `CDP_ACCESS_KEY_ID` / `CDP_PRIVATE_KEY` from Cursor secrets or `~/.config/federal-cdp/federal.env`. If missing, stop and ask the user to add them; never ask for values in chat, never print them, never write them to a tracked file.
- Read the skills in `skills/` (`federal-cdp-access` for access, `cloudera-platform-upgrade` for resize and upgrade) before acting on the environment.
- Every command that changes something takes `--dry-run`; show the plan, then run with `--yes-shared` only for services the user named in this conversation.
- Tests: `.venv/bin/python -m pytest -q` (fake `cdp`, no network). New `cdp` calls get a branch in `tests/test_fedops.py::FakeCdp`.
- After a live change: entry in `docs/OPERATIONS_LOG.md` (IST), README status line, `config/capacity.json` `changes` for sizes.
