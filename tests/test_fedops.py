"""fedops.ctl and fedops.upgrade against a fake cdp CLI (no network)."""
from __future__ import annotations

import os

import pytest

from fedops import common, ctl, upgrade

ENV, CAP, BUILD = common.ENV, common.CAP["targets"], common.UPG["target_build"]


def _img(gbn, image_id, runtime="7.3.1"):
    return {"imageId": image_id, "componentVersions": {"cdp": f"{runtime}-1.cdh{runtime}.p500.{gbn}", "cdpGBN": gbn,
                                                       "cm": "7.13.1", "os": "redhat8"}}


class FakeCdp:
    def __init__(self, current_gbn="70000000", candidates=(BUILD,), vc_cpu="20", vc_mem="80Gi", vw_max=5,
                 cde_version="1.24.1", vc_status="AppInstalled", instance_type="m5.4xlarge", max_instances=5,
                 vw_version="2025.0.21.3-3", hubs_running=False):
        self.calls = []
        self.current_gbn, self.candidates, self.cde_version = current_gbn, candidates, cde_version
        self.vc_cpu, self.vc_mem, self.vw_max, self.vc_status = vc_cpu, vc_mem, vw_max, vc_status
        self.instance_type, self.max_instances, self.vw_version = instance_type, max_instances, vw_version
        self.hubs_running = hubs_running

    def __call__(self, *args):
        self.calls.append(args)
        a = " ".join(args[:2])
        if a == "environments describe-environment":
            return {"environment": {"crn": "env-crn", "status": "AVAILABLE"}}
        if a == "datalake list-datalakes":
            return {"datalakes": [{"datalakeName": "federal-dl"}]}
        if a == "datalake describe-datalake":
            return {"datalake": {"datalakeName": "federal-dl", "status": "RUNNING", "shape": "LIGHT_DUTY",
                                 "productVersions": [{"name": "CDH", "version": "7.2.18"}]}}
        if a == "datalake upgrade-datalake":
            if "--show-available-images" in args:
                return {"current": _img(self.current_gbn, "img-cur"),
                        "upgradeCandidates": [_img(g, f"img-{g}") for g in self.candidates]}
            if "--dry-run" in args and self.hubs_running:
                raise RuntimeError("cdp datalake upgrade-datalake: There are attached Data Hub clusters in incorrect "
                                   "state: federal-flink,federal-kafka,federal-nifi. Please stop those to be able to "
                                   "perform the upgrade.")
            return {}
        if a == "datalake get-operation":
            return {"operationId": "op0", "operationStatus": "FINISHED"}
        if a == "datahub describe-cluster":
            return {"cluster": {"status": "AVAILABLE"}}
        if a == "de list-services":
            return {"services": [{"name": ENV["cde_service"], "clusterId": "cluster-1", "status": "ClusterCreationCompleted"}]}
        if a == "de describe-service":
            return {"service": {"name": ENV["cde_service"], "clusterId": "cluster-1", "version": self.cde_version,
                                "status": "ClusterCreationCompleted",
                                "resources": {"instance_type": self.instance_type, "min_instances": "0",
                                              "max_instances": str(self.max_instances)}}}
        if a == "de list-vcs":
            return {"vcs": [{"vcName": ENV["cde_vc"], "vcId": "dex-app-1", "status": self.vc_status}]}
        if a == "de describe-vc":
            return {"vc": {"vcName": ENV["cde_vc"], "vcId": "dex-app-1", "status": self.vc_status,
                           "resources": {"cpuRequests": self.vc_cpu, "memRequests": self.vc_mem}}}
        if a == "de get-upgrade-status":
            return {"nextStep": "prepare", "allStepsCompleted": False}
        if a == "dw list-clusters":
            return {"clusters": [{"id": "env-x", "environmentCrn": "env-crn"}]}
        if a == "dw list-vws":
            return {"vws": [{"name": name, "id": f"compute-{i + 1}", "dbcId": "warehouse-1",
                             "status": "Running", "cdhVersion": self.vw_version,
                             "autoscalingOptions": {"minClusters": 1, "maxClusters": self.vw_max}}
                            for i, name in enumerate(ENV["cdw_vws"])]}
        if a in ("dw get-upgrade-vw-versions", "dw get-upgrade-dbc-versions"):
            return {"latestVersion": "2025.0.20.1-9", "latestCDPVersion": f"7.3.1.500-{BUILD}"}
        if a == "ml list-workspaces":
            return {"workspaces": [{"instanceName": ENV["cai_workspace"], "environmentName": ENV["environment"],
                                    "instanceStatus": "installation:finished", "crn": "ws-crn"}]}
        return {}


@pytest.fixture
def fake(monkeypatch):
    f = FakeCdp()
    _wire(f, monkeypatch)
    yield f
    common.DRY = False


def _wire(f, monkeypatch):
    for mod in (common, ctl, upgrade):
        monkeypatch.setattr(mod, "cdp", f)
    return f


def _writes(f):
    reads = ("list-", "describe-", "get-", "--show-available-images", "--dry-run")
    return [x for x in f.calls if not any(r in " ".join(x) for r in reads)]


def test_changes_need_yes_shared():
    for argv in (["upgrade"], ["resize"]):
        with pytest.raises(SystemExit, match="yes-shared"):
            upgrade.main(argv)
    with pytest.raises(SystemExit, match="yes-shared"):
        ctl.main(["stop"])


def test_live_upgrade_needs_projects_stopped(fake, capsys):
    with pytest.raises(SystemExit, match="projects-stopped"):
        upgrade.main(["upgrade", "--yes-shared"])
    assert "python scripts/platform_ctl.py stop" in capsys.readouterr().out
    assert _writes(fake) == []


def test_upgrade_dry_run_plans_every_step_in_order_and_writes_nothing(fake, capsys):
    assert upgrade.main(["upgrade", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert _writes(fake) == []
    assert ("datalake", "upgrade-datalake", "--datalake-name", "federal-dl", "--image-id", f"img-{BUILD}",
            "--dry-run") in fake.calls
    steps = ["validate and prepare", "suspend CAI workspace", "suspend CDE virtual cluster",
             "suspend CDW virtual warehouse", "back up the Data Lake", f"upgrade the Data Lake to 7.3.1-1.cdh7.3.1.p500.{BUILD}",
             "CDE upgrade-service --step prepare", "CDE upgrade-service --step backup",
             "CDE upgrade-service --step upgrade", "CDE upgrade-service --step resume",
             "upgrade CDW Database Catalog warehouse-1 to 2025.0.20.1-9",
             "upgrade CDW VW"]
    pos = [out.index(f"would {s}") for s in steps]
    assert pos == sorted(pos)


def test_missing_build_stops_before_anything_is_stopped(fake):
    fake.candidates = ("80000001",)
    with pytest.raises(SystemExit, match=f"build {BUILD} is not an upgrade candidate"):
        upgrade.main(["upgrade", "--dry-run"])
    assert not any("stop" in " ".join(x) or "suspend" in " ".join(x) for x in fake.calls)


def test_old_cde_blocks_a_7_3_datalake_upgrade(fake):
    fake.cde_version = "1.23.2"
    with pytest.raises(SystemExit, match="upgrade --only cde"):
        upgrade.main(["upgrade", "--dry-run"])


def test_datalake_already_on_build_is_skipped(fake, capsys):
    fake.current_gbn, fake.candidates = BUILD, ()
    upgrade.main(["upgrade", "--dry-run", "--only", "datalake"])
    out = capsys.readouterr().out
    assert f"already runs build {BUILD}" in out
    assert "would back up the Data Lake" not in out


def test_resize_dry_run(fake, capsys):
    upgrade.main(["resize", "--dry-run"])
    out = capsys.readouterr().out
    assert f"autoscale max executor groups 5 -> {CAP['impala_autoscale_max_groups']}" in out
    # 48 CPU / 192 GiB on m5.4xlarge (16 vCPU / 64 GiB) at 80% allocatable is 4 nodes; 5 are allowed
    assert f"CDE service {ENV['cde_service']} max instances 5 (m5.4xlarge): enough" in out
    assert "manual step" in out and "Capacity" in out
    assert _writes(fake) == []


def test_resize_fails_until_vc_quota_reads_back(fake, monkeypatch):
    fake.vw_max = CAP["impala_autoscale_max_groups"]
    with pytest.raises(SystemExit, match="no VC quota update"):
        upgrade.main(["resize", "--yes-shared", "--only", "cde"])
    ok = _wire(FakeCdp(vc_cpu=str(CAP["cde_vc_quota_cpu"]), vc_mem=f"{CAP['cde_vc_quota_gib']}Gi"), monkeypatch)
    monkeypatch.setitem(CAP, "cde_service_max_instances", 5)
    assert upgrade.main(["resize", "--yes-shared", "--only", "cde"]) == 0
    assert _writes(ok) == []


def test_ctl_stop_dry_run_order(fake, capsys):
    ctl.main(["stop", "--dry-run"])
    out = capsys.readouterr().out
    order = ["suspend CAI workspace", "stop Data Hub federal-nifi", "suspend CDE virtual cluster",
             "suspend CDW virtual warehouse", "stop Data Hub federal-flink", "stop Data Hub federal-kafka"]
    pos = [out.index(f"would {s}") for s in order]
    assert pos == sorted(pos)
    assert "project workloads to stop before this" in out
    assert _writes(fake) == []


def test_pick_version_prefers_the_target_build():
    v = {"latestVersion": "L", "latestCDPVersion": "7.3.2-99999999", "compatibleVersion": "C",
         "compatibleCDPVersion": f"7.3.1-{BUILD}"}
    assert upgrade.pick_version(v, BUILD) == "C"
    assert upgrade.pick_version({"latestVersion": "L"}, BUILD) == "L"
    assert upgrade.pick_version({}, BUILD) is None


def test_env_file_loads_without_overriding(tmp_path, monkeypatch):
    f = tmp_path / "federal.env"
    f.write_text("# comment\nexport CDP_ACCESS_KEY_ID='abc'\nCDP_REGION=us-east-1\nEMPTY=\n")
    monkeypatch.setenv("FEDERAL_ENV_FILE", str(f))
    monkeypatch.delenv("CDP_ACCESS_KEY_ID", raising=False)
    monkeypatch.setenv("CDP_REGION", "kept")
    assert common.load_env() == f
    assert os.environ["CDP_ACCESS_KEY_ID"] == "abc"
    assert os.environ["CDP_REGION"] == "kept"
    assert "EMPTY" not in os.environ
    monkeypatch.delenv("CDP_ACCESS_KEY_ID")


def test_cde_node_ceiling_raised_only_when_too_low(fake, capsys):
    fake.max_instances = 2
    upgrade.main(["resize", "--dry-run", "--only", "cde"])
    assert f"would raise CDE service {ENV['cde_service']} max instances 2 -> 4 (m5.4xlarge)" in capsys.readouterr().out
    fake.instance_type, fake.max_instances = "r5.4xlarge", 50
    upgrade.main(["resize", "--dry-run", "--only", "cde"])
    assert "max instances 50 (r5.4xlarge): enough" in capsys.readouterr().out
    assert upgrade.nodes_for_quota("x9.weird", 48, 192) is None


def test_cdw_vw_on_latest_is_not_upgraded_again(fake, capsys):
    fake.vw_version = "2025.0.20.1-9"
    upgrade.main(["upgrade", "--dry-run", "--only", "cdw"])
    out = capsys.readouterr().out
    assert "no upgrade offered (version 2025.0.20.1-9)" in out
    assert "would upgrade CDW VW" not in out


def test_running_data_hubs_do_not_block_the_plan(fake, capsys):
    fake.hubs_running = True
    assert upgrade.main(["upgrade", "--dry-run", "--only", "datalake"]) == 0
    out = capsys.readouterr().out
    assert "expected: the Data Hubs are stopped before the upgrade" in out
    assert out.index("would stop Data Hub federal-kafka") < out.index("would back up the Data Lake")
