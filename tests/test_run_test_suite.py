from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import ROOT
from training.run_test_suite import (
    load_config,
    read_history,
    resolve_suite,
    suite_command,
    write_summary,
)


CONFIG_PATH = ROOT / "configs" / "test_suites.json"


def test_test_suite_config_loads_and_paths_exist():
    config = load_config(CONFIG_PATH)

    assert config["default_suite"] in config["suites"]
    assert "all" in config["suites"]
    assert "runtime" in config["suites"]
    assert "benchmark_smoke" in config["suites"]

    missing_paths = []
    for suite in config["suites"].values():
        for path in suite["paths"]:
            if not (ROOT / path).exists():
                missing_paths.append(path)
    assert missing_paths == []


def test_suite_command_uses_configured_paths_and_extra_args():
    config = load_config(CONFIG_PATH)
    suite_name, suite = resolve_suite(config, "v1_5_baseline")

    command = suite_command(suite, ["-q"])

    assert suite_name == "v1_5_baseline"
    assert command[1:3] == ["-m", "pytest"]
    assert str(ROOT / "tests" / "test_analyze_v1_5_13_cancel_timeout_fallback_android_contract.py") in command
    assert command[-1] == "-q"


def test_resolve_suite_rejects_unknown_suite():
    config = load_config(CONFIG_PATH)

    try:
        resolve_suite(config, "missing_suite")
    except ValueError as exc:
        assert "unknown suite" in str(exc)
    else:
        raise AssertionError("unknown suite should raise ValueError")


def test_write_summary_tracks_most_used_suites(tmp_path):
    history_path = tmp_path / "history.jsonl"
    summary_path = tmp_path / "summary.json"
    history_records = [
        {"suite": "runtime", "returncode": 0},
        {"suite": "runtime", "returncode": 1},
        {"suite": "benchmark_smoke", "returncode": 0},
    ]
    history_path.write_text("\n".join(json.dumps(item) for item in history_records) + "\n", encoding="utf-8")

    history = read_history(history_path)
    summary = write_summary(history, summary_path)

    assert summary["total_recorded_runs"] == 3
    assert summary["most_used_suites"][0]["suite"] == "runtime"
    assert summary["most_used_suites"][0]["runs"] == 2
    assert summary["most_used_suites"][0]["passes"] == 1
    assert summary["most_used_suites"][0]["failures"] == 1
    assert json.loads(summary_path.read_text(encoding="utf-8"))["total_recorded_runs"] == 3
