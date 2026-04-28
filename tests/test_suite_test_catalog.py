from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import aibenchie_local
from aibenchie import suite_test_catalog


def touch_required_files(root: Path, target_name: str) -> None:
    target = next(target for target in suite_test_catalog.build_suite_test_catalog() if target.name == target_name)
    for relative in target.required_paths:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# fixture\n", encoding="utf-8")


def test_catalog_runs_selected_aibenchie_target(monkeypatch, tmp_path):
    touch_required_files(tmp_path, "aibenchie_core")

    def fake_run(command, **kwargs):
        assert kwargs["cwd"] == tmp_path
        assert command[:3] == [suite_test_catalog.sys.executable, "-m", "pytest"]
        return SimpleNamespace(returncode=0, stdout="password=supersecret\nok\n", stderr="")

    monkeypatch.setattr(suite_test_catalog.subprocess, "run", fake_run)

    result = suite_test_catalog.run_suite_tests(
        root=tmp_path,
        env={},
        selected_targets=["aibenchie_core"],
        require_all=True,
    )

    assert result.ok is True
    assert result.results[0].status == "pass"
    assert "supersecret" not in result.results[0].stdout_tail
    assert "password=[REDACTED]" in result.results[0].stdout_tail


def test_missing_repo_skips_by_default_and_fails_when_required(tmp_path):
    optional_result = suite_test_catalog.run_suite_tests(
        root=tmp_path,
        env={},
        selected_targets=["nullbridge_trust_fabric"],
    )
    required_result = suite_test_catalog.run_suite_tests(
        root=tmp_path,
        env={},
        selected_targets=["nullbridge_trust_fabric"],
        require_all=True,
    )

    assert optional_result.ok is True
    assert optional_result.results[0].status == "skip"
    assert optional_result.results[0].failure == "repo_not_found"
    assert required_result.ok is False
    assert required_result.results[0].status == "fail"


def test_catalog_prefers_candidate_with_required_contracts(monkeypatch, tmp_path):
    root = tmp_path / "AIBenchie"
    root.mkdir()
    stale_repo = tmp_path / ".NullXoid"
    active_repo = tmp_path / "Felnx" / "NullXoid"
    stale_repo.mkdir()
    touch_required_files(active_repo, "nullxoid_wrapper_backend")

    def fake_run(command, **kwargs):
        assert kwargs["cwd"] == active_repo
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(suite_test_catalog.subprocess, "run", fake_run)

    result = suite_test_catalog.run_suite_tests(
        root=root,
        env={},
        selected_targets=["nullxoid_wrapper_backend"],
        require_all=True,
    )

    assert result.ok is True
    assert result.results[0].repo == str(active_repo)


def test_catalog_uses_target_python_override(monkeypatch, tmp_path):
    repo = tmp_path / "NullXoid"
    custom_python = tmp_path / "venv" / "bin" / "python"
    touch_required_files(repo, "nullxoid_wrapper_backend")

    def fake_run(command, **kwargs):
        assert kwargs["cwd"] == repo
        assert command[0] == str(custom_python)
        assert command[1:3] == ["-m", "pytest"]
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(suite_test_catalog.subprocess, "run", fake_run)

    result = suite_test_catalog.run_suite_tests(
        root=tmp_path,
        env={
            "AIBENCHIE_NULLXOID_WRAPPER_REPO": str(repo),
            "AIBENCHIE_NULLXOID_WRAPPER_PYTHON": str(custom_python),
        },
        selected_targets=["nullxoid_wrapper_backend"],
        require_all=True,
    )

    assert result.ok is True
    assert result.results[0].command[0] == str(custom_python)


def test_catalog_runs_wrapper_frontend_e2ee_target(monkeypatch, tmp_path):
    repo = tmp_path / "NullXoid"
    touch_required_files(repo, "nullxoid_wrapper_frontend_e2ee")

    def fake_run(command, **kwargs):
        assert kwargs["cwd"] == repo
        assert command[-2:] == ["--prefix", "frontend"]
        assert "test:e2ee" in command
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(suite_test_catalog.subprocess, "run", fake_run)

    result = suite_test_catalog.run_suite_tests(
        root=tmp_path,
        env={"AIBENCHIE_NULLXOID_WRAPPER_REPO": str(repo)},
        selected_targets=["nullxoid_wrapper_frontend_e2ee"],
        require_all=True,
    )

    assert result.ok is True
    assert result.results[0].status == "pass"


def test_android_target_sets_discovered_java_home(monkeypatch, tmp_path):
    repo = tmp_path / "NullXoidAndroid"
    java_home = tmp_path / "jdk"
    java_exe = java_home / "bin" / ("java.exe" if suite_test_catalog.os.name == "nt" else "java")
    touch_required_files(repo, "android_companion_unit")
    java_exe.parent.mkdir(parents=True)
    java_exe.write_text("# fixture\n", encoding="utf-8")

    def fake_run(command, **kwargs):
        assert kwargs["cwd"] == repo
        assert kwargs["env"]["JAVA_HOME"] == str(java_home)
        assert str(java_home / "bin") in kwargs["env"]["PATH"]
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(suite_test_catalog.subprocess, "run", fake_run)

    result = suite_test_catalog.run_suite_tests(
        root=tmp_path,
        env={"AIBENCHIE_JAVA_HOME": str(java_home)},
        selected_targets=["android_companion_unit"],
        include_optional=True,
        require_all=True,
    )

    assert result.ok is True
    assert result.results[0].status == "pass"


def test_catalog_contains_suite_boundaries():
    targets = {target.name: target for target in suite_test_catalog.build_suite_test_catalog()}

    assert "aibenchie_core" in targets
    assert "nullbridge_trust_fabric" in targets
    assert "nullxoid_wrapper_backend" in targets
    assert "nullxoid_wrapper_frontend_e2ee" in targets
    assert "android_companion_unit" in targets
    assert targets["android_companion_unit"].optional is True


def test_unknown_target_fails(tmp_path):
    result = suite_test_catalog.run_suite_tests(root=tmp_path, env={}, selected_targets=["missing_target"])

    assert result.ok is False
    assert result.results[0].name == "missing_target"
    assert result.results[0].failure == "unknown_target"


def test_suite_tests_cli_outputs_json(monkeypatch, capsys):
    class FakeResult:
        ok = True

        def as_dict(self):
            return {
                "ok": True,
                "root": "C:/repo",
                "include_optional": False,
                "require_all": False,
                "selected_targets": ["aibenchie_core"],
                "targets": [],
                "results": [{"name": "aibenchie_core", "status": "pass", "ok": True}],
            }

    monkeypatch.setattr(aibenchie_local, "run_suite_tests_from_env", lambda **kwargs: FakeResult())

    code = aibenchie_local.main(["--suite-tests", "--suite-test-target", "aibenchie_core", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ok"] is True
    assert payload["selected_targets"] == ["aibenchie_core"]
