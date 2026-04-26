from __future__ import annotations

import shutil
import subprocess

import pytest

from aibenchie import generated_output_policy


def write_bytes(path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_generated_output_policy_passes_for_bounded_reports_and_data(tmp_path):
    write_bytes(tmp_path / "reports" / "runtime" / "summary.json", 128)
    write_bytes(tmp_path / "reports" / "runtime" / "summary.md", 256)
    write_bytes(tmp_path / "data" / "fixture" / "sample.jsonl", 512)
    env = {
        "AIBENCHIE_GENERATED_ROOT": str(tmp_path),
        "AIBENCHIE_GENERATED_RUNTIME_MAX_MB": "1",
        "AIBENCHIE_GENERATED_RUNTIME_FILE_MAX_MB": "1",
        "AIBENCHIE_GENERATED_DATA_MAX_MB": "1",
        "AIBENCHIE_GENERATED_DATA_FILE_MAX_MB": "1",
    }

    result = generated_output_policy.run_generated_output_policy_check(env)

    assert result.ok is True
    assert [budget.name for budget in result.budgets] == ["runtime_reports", "public_data_fixtures"]
    assert result.forbidden_files == []


def test_generated_output_policy_fails_when_runtime_total_exceeds_budget(tmp_path):
    write_bytes(tmp_path / "reports" / "runtime" / "a.json", 900)
    write_bytes(tmp_path / "reports" / "runtime" / "b.json", 900)
    env = {
        "AIBENCHIE_GENERATED_ROOT": str(tmp_path),
        "AIBENCHIE_GENERATED_RUNTIME_MAX_MB": "0.001",
        "AIBENCHIE_GENERATED_RUNTIME_FILE_MAX_MB": "1",
        "AIBENCHIE_GENERATED_DATA_MAX_MB": "1",
        "AIBENCHIE_GENERATED_DATA_FILE_MAX_MB": "1",
    }

    result = generated_output_policy.run_generated_output_policy_check(env)

    assert result.ok is False
    failures = {budget.name: budget.failure for budget in result.budgets if not budget.ok}
    assert failures == {"runtime_reports": "budget_exceeded"}


def test_generated_output_policy_fails_when_single_data_file_exceeds_budget(tmp_path):
    write_bytes(tmp_path / "data" / "fixture" / "huge.jsonl", 2048)
    env = {
        "AIBENCHIE_GENERATED_ROOT": str(tmp_path),
        "AIBENCHIE_GENERATED_RUNTIME_MAX_MB": "1",
        "AIBENCHIE_GENERATED_RUNTIME_FILE_MAX_MB": "1",
        "AIBENCHIE_GENERATED_DATA_MAX_MB": "1",
        "AIBENCHIE_GENERATED_DATA_FILE_MAX_MB": "0.001",
    }

    result = generated_output_policy.run_generated_output_policy_check(env)

    assert result.ok is False
    failures = {budget.name: budget.failure for budget in result.budgets if not budget.ok}
    assert failures == {"public_data_fixtures": "file_budget_exceeded"}


def test_generated_output_policy_fails_when_runtime_report_count_exceeds_limit(tmp_path):
    write_bytes(tmp_path / "reports" / "runtime" / "a.json", 128)
    write_bytes(tmp_path / "reports" / "runtime" / "b.json", 128)
    write_bytes(tmp_path / "reports" / "runtime" / "c.json", 128)
    env = {
        "AIBENCHIE_GENERATED_ROOT": str(tmp_path),
        "AIBENCHIE_GENERATED_RUNTIME_MAX_MB": "1",
        "AIBENCHIE_GENERATED_RUNTIME_FILE_MAX_MB": "1",
        "AIBENCHIE_GENERATED_RUNTIME_MAX_FILES": "2",
        "AIBENCHIE_GENERATED_DATA_MAX_MB": "1",
        "AIBENCHIE_GENERATED_DATA_FILE_MAX_MB": "1",
    }

    result = generated_output_policy.run_generated_output_policy_check(env)

    assert result.ok is False
    failures = {budget.name: budget.failure for budget in result.budgets if not budget.ok}
    assert failures == {"runtime_reports": "file_count_exceeded"}


def test_generated_output_policy_rejects_forbidden_generated_artifacts(tmp_path):
    write_bytes(tmp_path / "reports" / "runtime" / "raw.log", 10)
    write_bytes(tmp_path / "data" / "private_dump.sqlite", 10)
    env = {
        "AIBENCHIE_GENERATED_ROOT": str(tmp_path),
        "AIBENCHIE_GENERATED_RUNTIME_MAX_MB": "1",
        "AIBENCHIE_GENERATED_RUNTIME_FILE_MAX_MB": "1",
        "AIBENCHIE_GENERATED_DATA_MAX_MB": "1",
        "AIBENCHIE_GENERATED_DATA_FILE_MAX_MB": "1",
    }

    result = generated_output_policy.run_generated_output_policy_check(env)

    assert result.ok is False
    assert [item.path for item in result.forbidden_files] == [
        "data/private_dump.sqlite",
        "reports/runtime/raw.log",
    ]


def test_generated_output_policy_ignores_local_private_output_dirs(tmp_path):
    write_bytes(tmp_path / "reports" / "runtime" / ".local" / "raw.log", 4096)
    write_bytes(tmp_path / "data" / "private" / "dump.sqlite", 4096)
    env = {
        "AIBENCHIE_GENERATED_ROOT": str(tmp_path),
        "AIBENCHIE_GENERATED_RUNTIME_MAX_MB": "0.001",
        "AIBENCHIE_GENERATED_RUNTIME_FILE_MAX_MB": "0.001",
        "AIBENCHIE_GENERATED_DATA_MAX_MB": "0.001",
        "AIBENCHIE_GENERATED_DATA_FILE_MAX_MB": "0.001",
    }

    result = generated_output_policy.run_generated_output_policy_check(env)

    assert result.ok is True
    assert result.forbidden_files == []
    assert all(budget.file_count == 0 for budget in result.budgets)


def test_generated_output_policy_rejects_dirty_tracked_generated_outputs(tmp_path):
    if not shutil.which("git"):
        pytest.skip("git is required for tracked generated-output drift checks")

    write_bytes(tmp_path / "reports" / "runtime" / "summary.md", 128)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "aibenchie@example.invalid"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "AIBenchie Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "reports/runtime/summary.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "reports" / "runtime" / "summary.md").write_text("changed\n", encoding="utf-8")
    env = {
        "AIBENCHIE_GENERATED_ROOT": str(tmp_path),
        "AIBENCHIE_GENERATED_RUNTIME_MAX_MB": "1",
        "AIBENCHIE_GENERATED_RUNTIME_FILE_MAX_MB": "1",
        "AIBENCHIE_GENERATED_DATA_MAX_MB": "1",
        "AIBENCHIE_GENERATED_DATA_FILE_MAX_MB": "1",
    }

    result = generated_output_policy.run_generated_output_policy_check(env)

    assert result.ok is False
    assert [(item.path, item.status) for item in result.dirty_tracked_files] == [("reports/runtime/summary.md", "M")]
