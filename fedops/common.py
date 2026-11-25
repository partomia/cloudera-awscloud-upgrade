"""Config, credentials, the cdp CLI wrapper, dry-run and wait helpers."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRY = False


def load_config(name: str) -> dict:
    return json.loads((ROOT / "config" / f"{name}.json").read_text())


ENV = load_config("environment")
CAP = load_config("capacity")
UPG = load_config("upgrade")
PROJECTS = load_config("projects")["projects"]


def env_file() -> Path | None:
    for p in (os.environ.get("FEDERAL_ENV_FILE"), "~/.config/federal-cdp/federal.env", str(ROOT / "federal.env")):
        if p and Path(p).expanduser().is_file():
            return Path(p).expanduser()
    return None


def load_env() -> Path | None:
    """KEY=VALUE lines into os.environ; variables already set win. Values are never printed."""
    path = env_file()
    if not path:
        return None
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.removeprefix("export ").split("=", 1)
        key, val = key.strip(), val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            val = val[1:-1]
        if val and key not in os.environ:
            os.environ[key] = val
    return path


def say(msg: str) -> None:
    print(msg, flush=True)


def act(what: str, fn, *a, **kw):
    if DRY:
        say(f"  would {what}")
        return None
    say(f"  {what}")
    return fn(*a, **kw)


def wait(what: str, fn, ok: set, bad: tuple = ("FAIL", "CANCEL"), timeout: int = 4 * 3600, poll: int = 30) -> str:
    if DRY:
        return ""
    t0, last = time.time(), None
    while time.time() - t0 < timeout:
        st = str(fn())
        if st != last:
            say(f"    {what}: {st} ({time.time() - t0:.0f} s)")
            last = st
        if st.upper() in {s.upper() for s in ok}:
            return st
        if any(b in st.upper() for b in bad):
            raise SystemExit(f"{what}: {st}")
        time.sleep(poll)
    raise SystemExit(f"{what}: still {last} after {timeout} s")


def _cdp_exe() -> str:
    for exe in (os.environ.get("FEDERAL_CDP_CLI"), str(ROOT / ".venv" / "bin" / "cdp"), shutil.which("cdp")):
        if exe and Path(exe).expanduser().is_file():
            return str(Path(exe).expanduser())
    raise SystemExit("cdp CLI not found: ./scripts/setup.sh, or set FEDERAL_CDP_CLI")


def cdp(*args: str) -> dict:
    glob_args = []
    # an explicit --profile makes cdpcli ignore CDP_ACCESS_KEY_ID / CDP_PRIVATE_KEY
    if os.environ.get("FEDERAL_CDP_PROFILE") and not os.environ.get("CDP_ACCESS_KEY_ID"):
        glob_args += ["--profile", os.environ["FEDERAL_CDP_PROFILE"]]
    if os.environ.get("CDP_REGION"):
        glob_args += ["--cdp-region", os.environ["CDP_REGION"]]
    if os.environ.get("CDP_ENDPOINT_URL"):
        glob_args += ["--endpoint-url", os.environ["CDP_ENDPOINT_URL"]]
    out = subprocess.run([_cdp_exe(), *glob_args, *args], capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(f"cdp {' '.join(args[:2])}: {out.stderr.strip()[:400]}")
    return json.loads(out.stdout) if out.stdout.strip() else {}


def require_credentials() -> None:
    path = load_env()
    have_env = os.environ.get("CDP_ACCESS_KEY_ID") and os.environ.get("CDP_PRIVATE_KEY")
    have_file = Path(os.environ.get("CDP_SHARED_CREDENTIALS_FILE", "~/.cdp/credentials")).expanduser().is_file()
    if not (have_env or have_file):
        raise SystemExit("no CDP credentials: set CDP_ACCESS_KEY_ID and CDP_PRIVATE_KEY (Cursor secrets, "
                         "~/.config/federal-cdp/federal.env, or ./federal.env), or create ~/.cdp/credentials")
    say(f"credentials: {'environment' if have_env else '~/.cdp/credentials'}"
        f"{f' (loaded {path.name})' if path else ''}")


def env_crn() -> str:
    return cdp("environments", "describe-environment", "--environment-name", ENV["environment"])["environment"]["crn"]
