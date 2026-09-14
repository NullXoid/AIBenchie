"""Exercise the real PowerShell runner with synthetic, non-network gate commands."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

SHELL = shutil.which("pwsh")
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "echolabs_suite_release_gate.ps1"
SKIPS = ["SkipWeb", "SkipAndroid", "SkipDesktop", "SkipBridge", "SkipUniversalE2E",
         "SkipDeployPlan", "SkipDockerSupport", "SkipDistributionHygiene", "SkipRealDeviceUX"]
pytestmark = pytest.mark.skipif(SHELL is None, reason="PowerShell 7 is required; runner qualification is inconclusive without it")


@pytest.fixture
def harness(tmp_path):
    root = tmp_path / "suite"
    for name in (".NullXoid", "AiAssistant", "NullXoidAndroid", "NullBridge/backend", "Lv-7"):
        (root / name).mkdir(parents=True)
    (root / ".NullXoid/package.json").write_text("{}")
    for repo, command in (("AiAssistant", "desktop_release_gate.ps1"),
                          ("NullXoidAndroid", "android_release_gate.ps1"),
                          ("NullBridge/backend", "nullbridge_release_gate.ps1")):
        path = root / repo / "scripts" / command
        path.parent.mkdir()
        path.write_text("$global:LASTEXITCODE = 0\n")
    plan = tmp_path / "plan.json"
    proof = tmp_path / "proof.json"
    plan.write_text("{}")
    proof.write_text("{}")
    driver = tmp_path / "driver.ps1"
    driver.write_text("""$ErrorActionPreference = 'Stop'
$inputData = Get-Content -LiteralPath $args[0] -Raw | ConvertFrom-Json -AsHashtable
$global:GateCalls = $inputData.calls
$global:FailNpm = $inputData.failNpm
function global:npm {
    Add-Content -LiteralPath $global:GateCalls -Value ('npm:' + (Get-Location).Path)
    $global:LASTEXITCODE = $(if ($global:FailNpm) { 7 } else { 0 })
}
function global:python {
    Add-Content -LiteralPath $global:GateCalls -Value ('python:' + (Get-Location).Path)
    $global:LASTEXITCODE = 0
}
$parameters = $inputData.parameters
& $inputData.script @parameters
exit $LASTEXITCODE
""", encoding="utf-8")

    def run(overrides=None, fail_npm=False):
        report = tmp_path / "report.json"
        calls = tmp_path / "calls.txt"
        if calls.exists():
            calls.unlink()
        parameters = dict(SuiteRoot=str(root), ReportPath=str(report), DeployPlanPath=str(plan),
            RealDeviceUXProofPath=str(proof), DesktopIncludeUi=True, BridgeFull=True)
        parameters.update(overrides or {})
        config = tmp_path / "input.json"
        config.write_text(json.dumps(dict(script=str(SCRIPT), parameters=parameters, calls=str(calls), failNpm=fail_npm)))
        result = subprocess.run([SHELL, "-NoProfile", "-File", str(driver), str(config)],
            text=True, capture_output=True, timeout=30)
        assert report.exists(), result.stdout + result.stderr
        return result, json.loads(report.read_text(encoding="utf-8-sig")), calls.read_text() if calls.exists() else ""
    return root, plan, proof, run


def test_full_runner_requires_all_selected_gates(harness):
    _, _, _, run = harness
    result, report, calls = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert report["verdict"] == "pass" and report["coverage_complete"] is True
    assert report["deployment_authorized"] is False
    assert calls and all(item["status"] == "PASS" for item in report["surfaces"])


@pytest.mark.parametrize("skip", SKIPS + ["DesktopIncludeUi", "BridgeFull"])
def test_any_omitted_release_coverage_is_incomplete_not_pass(harness, skip):
    _, _, _, run = harness
    result, report, _ = run({skip: skip in SKIPS})
    assert result.returncode == 2, result.stdout + result.stderr
    assert report["verdict"] == "incomplete" and report["coverage_complete"] is False
    assert any(item["status"] == "SKIPPED" for item in report["surfaces"])


def test_all_skipped_is_not_a_passing_release(harness):
    _, _, _, run = harness
    result, report, calls = run({key: True for key in SKIPS})
    assert result.returncode == 2 and report["verdict"] == "incomplete"
    assert len(report["surfaces"]) == len(SKIPS) and not calls


@pytest.mark.parametrize("missing", ["plan", "proof", "repo"])
def test_missing_prerequisite_blocks_before_any_gate_executes(harness, missing):
    root, plan, proof, run = harness
    if missing == "repo":
        (root / "Lv-7").rmdir()
    else:
        (plan if missing == "plan" else proof).unlink()
    result, report, calls = run()
    assert result.returncode == 2, result.stdout + result.stderr
    assert report["verdict"] == "blocked" and report["coverage_complete"] is False
    assert not calls


def test_ambiguous_web_checkouts_require_explicit_selection(harness):
    root, _, _, run = harness
    other = root / "NullXoid-live"
    other.mkdir()
    (other / "package.json").write_text("{}")
    result, report, calls = run()
    assert result.returncode == 2 and report["failed_surface"] == "web_repository" and not calls
    result, report, calls = run({"WebRepository": str(other)})
    assert result.returncode == 0, result.stdout + result.stderr
    assert Path(report["repositories"]["web"]) == other
    assert f"npm:{other}" in calls


def test_selected_reconciled_desktop_path_is_used(harness):
    root, _, _, run = harness
    selected = root / "reconciled-desktop"
    (root / "AiAssistant").rename(selected)
    result, report, _ = run({"DesktopRepository": str(selected)})
    assert result.returncode == 0, result.stdout + result.stderr
    assert Path(report["repositories"]["desktop"]) == selected


def test_failed_command_overwrites_previous_success(harness):
    _, _, _, run = harness
    assert run()[1]["coverage_complete"] is True
    result, report, _ = run(fail_npm=True)
    assert result.returncode == 7
    assert report["verdict"] == "fail" and report["coverage_complete"] is False


def test_missing_gate_script_is_reported_not_left_as_success(harness):
    root, _, _, run = harness
    assert run()[1]["coverage_complete"] is True
    (root / "AiAssistant/scripts/desktop_release_gate.ps1").unlink()
    result, report, _ = run()
    assert result.returncode == 1, result.stdout + result.stderr
    assert report["verdict"] == "fail" and report["coverage_complete"] is False
